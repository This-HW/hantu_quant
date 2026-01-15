"""
자동 매매 실행 엔진 (Phase 3)
가상계좌를 사용한 실제 주식 자동매매 시스템
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from pathlib import Path
import threading

from ..api.kis_api import KISAPI
from ..config.api_config import APIConfig
from ..trading.trade_journal import TradeJournal
from ..trading.dynamic_stop_loss import DynamicStopLossCalculator, StopLossResult
from ..utils.log_utils import get_logger
from ..utils.telegram_notifier import get_telegram_notifier

logger = get_logger(__name__)

@dataclass
class Position:
    """포지션 정보"""
    stock_code: str
    stock_name: str
    quantity: int
    avg_price: float
    current_price: float
    entry_time: str
    unrealized_pnl: float
    unrealized_return: float
    stop_loss: float
    target_price: float
    
@dataclass
class TradingConfig:
    """매매 설정 (보수적 버전)"""
    max_positions: int = 10          # 최대 보유 종목수
    position_size_method: str = "account_pct"  # 포지션 크기 방법: "fixed", "account_pct", "risk_based", "kelly"
    position_size_value: float = 0.05  # 계좌 대비 5% (10%→5% 보수적)
    fixed_position_size: float = 1000000   # 고정 투자금액 (fixed 모드용)
    stop_loss_pct: float = 0.03      # 손절매 비율 (5%→3% 빠른 손절) - 고정 손절 시 사용
    take_profit_pct: float = 0.08    # 익절매 비율 (10%→8% 현실적 목표) - 고정 익절 시 사용
    max_trades_per_day: int = 15     # 일일 최대 거래횟수 (20→15 제한)
    risk_per_trade: float = 0.015    # 거래당 위험비율 (2%→1.5% 보수적)

    # 포지션 사이징 고급 설정 (보수적)
    max_position_pct: float = 0.08   # 최대 단일 포지션 비율 (15%→8%)
    min_position_size: float = 100000  # 최소 투자금액 (10만원)
    use_kelly_criterion: bool = True   # Kelly Criterion 사용 여부
    kelly_multiplier: float = 0.20     # Kelly 결과에 곱할 보수 계수 (0.25→0.20 더 보수적)

    # ATR 기반 동적 손절/익절 설정 (P1-1)
    use_dynamic_stops: bool = True     # 동적 손절/익절 사용 여부
    atr_period: int = 14               # ATR 계산 기간
    atr_stop_multiplier: float = 2.0   # ATR 기반 손절 배수
    atr_profit_multiplier: float = 3.0 # ATR 기반 익절 배수
    use_trailing_stop: bool = True     # 트레일링 스탑 사용 여부
    trailing_activation_pct: float = 0.02  # 트레일링 활성화 수익률 (2%)

    # 매매 시간 설정
    market_start: str = "09:00"
    market_end: str = "15:30"
    pre_market_start: str = "08:30"  # 매매 준비 시간

    # 매수 조건
    min_volume_ratio: float = 1.5    # 최소 거래량 비율
    max_price_change: float = 0.30   # 최대 가격 변동률 (30%)
    
class TradingEngine:
    """자동 매매 실행 엔진"""

    def __init__(self, config: Optional[TradingConfig] = None):
        """초기화"""
        self.config = config or TradingConfig()
        self.logger = logger
        self.api = None
        self.api_config = None

        # 상태 관리
        self.is_running = False
        self.positions: Dict[str, Position] = {}
        self.daily_trades = 0
        self.start_time = None

        # 매매 기록
        self.journal = TradeJournal()
        self.notifier = get_telegram_notifier()

        # ATR 기반 동적 손절/익절 계산기 (P1-1)
        self.dynamic_stop_calculator = DynamicStopLossCalculator(
            atr_period=self.config.atr_period,
            stop_multiplier=self.config.atr_stop_multiplier,
            profit_multiplier=self.config.atr_profit_multiplier,
            trailing_multiplier=self.config.atr_stop_multiplier * 0.75,  # 트레일링은 손절의 75%
        ) if self.config.use_dynamic_stops else None

        # 데이터 저장 경로
        self.data_dir = Path("data/trading")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.logger.info(
            f"자동 매매 엔진 초기화 완료 "
            f"(동적손절: {'활성화' if self.config.use_dynamic_stops else '비활성화'})"
        )
        
    def _initialize_api(self) -> bool:
        """API 초기화"""
        try:
            self.api_config = APIConfig()
            
            # 가상계좌 설정 확인
            if self.api_config.server != "virtual":
                self.logger.warning("실전 계좌가 설정되어 있습니다. 가상계좌로 변경을 권장합니다.")
                response = input("가상계좌로 변경하시겠습니까? (y/N): ").strip().lower()
                if response == 'y':
                    self.api_config.server = "virtual"
                    self.logger.info("가상계좌 모드로 변경되었습니다.")
                else:
                    self.logger.info("현재 설정 유지")
            
            self.api = KISAPI()
            
            # API 연결 테스트
            if not self.api_config.ensure_valid_token():
                self.logger.error("API 토큰 획득 실패")
                return False
                
            self.logger.info(f"API 초기화 완료 - {self.api_config.server} 모드")
            return True
            
        except Exception as e:
            self.logger.error(f"API 초기화 실패: {e}", exc_info=True)
            return False
            
    def _load_daily_selection(self) -> List[Dict[str, Any]]:
        """일일 선정 종목 로드 (DB 우선, JSON 폴백)"""
        today = datetime.now().strftime("%Y%m%d")
        today_date = datetime.now().date()

        # === 1. DB에서 먼저 로드 시도 ===
        try:
            from core.database.session import DatabaseSession
            from core.database.models import SelectionResult

            db = DatabaseSession()
            with db.get_session() as session:
                results = session.query(SelectionResult).filter(
                    SelectionResult.selection_date == today_date
                ).all()

                if results:
                    selected_stocks = []
                    for r in results:
                        selected_stocks.append({
                            'stock_code': r.stock_code,
                            'stock_name': r.stock_name,
                            'total_score': r.total_score,
                            'technical_score': r.technical_score,
                            'volume_score': r.volume_score,
                            'entry_price': r.entry_price,
                            'target_price': r.target_price,
                            'stop_loss': r.stop_loss,
                            'signal': r.signal,
                            'confidence': r.confidence
                        })
                    self.logger.info(f"일일 선정 종목 DB 로드: {len(selected_stocks)}개")
                    return selected_stocks

        except Exception as e:
            self.logger.warning(f"DB 로드 실패, JSON 폴백: {e}")

        # === 2. JSON 파일에서 폴백 로드 ===
        selection_file = Path(f"data/daily_selection/daily_selection_{today}.json")

        if not selection_file.exists():
            self.logger.warning(f"일일 선정 파일이 없습니다: {selection_file}")
            return []

        try:
            with open(selection_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            selected_stocks = data.get('data', {}).get('selected_stocks', [])
            # stocks 키도 확인 (호환성)
            if not selected_stocks:
                selected_stocks = data.get('stocks', [])
            self.logger.info(f"일일 선정 종목 JSON 로드: {len(selected_stocks)}개")

            return selected_stocks

        except Exception as e:
            self.logger.error(f"일일 선정 종목 로드 실패: {e}", exc_info=True)
            return []
            
    def _is_market_time(self) -> bool:
        """장 시간 확인"""
        now = datetime.now().time()
        start_time = datetime.strptime(self.config.market_start, "%H:%M").time()
        end_time = datetime.strptime(self.config.market_end, "%H:%M").time()
        
        return start_time <= now <= end_time
        
    def _is_tradeable_day(self) -> bool:
        """거래 가능한 날인지 확인 (평일)"""
        return datetime.now().weekday() < 5  # 0=월요일, 6=일요일
        
    def _calculate_position_size(self, stock_code: str, current_price: float, stock_data: Optional[Dict] = None) -> int:
        """고도화된 포지션 크기 계산"""
        try:
            # 1. 현재 계좌 정보 가져오기
            account_balance = self._get_account_balance()
            if account_balance <= 0:
                self.logger.warning("계좌 잔고가 0원입니다")
                return 0
            
            # 2. 포지션 크기 계산 방법 선택
            if self.config.position_size_method == "fixed":
                # 고정 금액
                investment_amount = self.config.fixed_position_size
                
            elif self.config.position_size_method == "account_pct":
                # 계좌 대비 비율 (기본: 10%)
                investment_amount = account_balance * self.config.position_size_value
                
            elif self.config.position_size_method == "risk_based":
                # 리스크 기반 사이징
                investment_amount = self._calculate_risk_based_size(account_balance, current_price)
                
            elif self.config.position_size_method == "kelly":
                # Kelly Criterion 기반
                investment_amount = self._calculate_kelly_size(account_balance, stock_code, stock_data)
                
            else:
                # 기본값: 계좌 대비 비율
                investment_amount = account_balance * self.config.position_size_value
            
            # 3. 안전 장치 적용
            # 최대 포지션 크기 제한 (계좌 대비)
            max_position_amount = account_balance * self.config.max_position_pct
            investment_amount = min(investment_amount, max_position_amount)
            
            # 최소 투자 금액 보장
            investment_amount = max(investment_amount, self.config.min_position_size)
            
            # 가용 자금 확인 (현재 보유 포지션 고려)
            available_cash = self._get_available_cash()
            investment_amount = min(investment_amount, available_cash)
            
            # 4. 수량 계산
            quantity = int(investment_amount / current_price)
            
            # 최소 1주는 매수
            quantity = max(1, quantity)
            
            self.logger.info(f"포지션 사이징: {stock_code} - 투자금액: {investment_amount:,.0f}원, 수량: {quantity}주")
            
            return quantity
            
        except Exception as e:
            self.logger.error(f"포지션 크기 계산 실패 {stock_code}: {e}", exc_info=True)
            return 0
            
    def _get_account_balance(self) -> float:
        """계좌 총 자산 조회"""
        try:
            if not self.api:
                return 0.0

            balance = self.api.get_balance()
            if not balance:
                return 0.0

            # total_eval_amount는 이미 예수금 + 주식평가금액의 합계
            # 따라서 total_eval_amount만 반환하면 됨
            total_eval = balance.get("total_eval_amount", 0)

            return float(total_eval)

        except Exception as e:
            self.logger.error(f"계좌 잔고 조회 실패: {e}", exc_info=True)
            return 0.0
            
    def _get_available_cash(self) -> float:
        """가용 현금 조회"""
        try:
            if not self.api:
                return 0.0
                
            balance = self.api.get_balance()
            if not balance:
                return 0.0
                
            # 예수금만 반환 (주식은 제외)
            return balance.get("deposit", 0)
            
        except Exception as e:
            self.logger.error(f"가용 현금 조회 실패: {e}", exc_info=True)
            return 0.0
            
    def _calculate_risk_based_size(self, account_balance: float, current_price: float) -> float:
        """리스크 기반 포지션 사이징"""
        try:
            # 리스크 허용 금액 = 계좌 x 거래당 위험비율
            risk_amount = account_balance * self.config.risk_per_trade
            
            # 손절매까지의 거리로 포지션 크기 계산
            # 포지션 크기 = 리스크 허용 금액 / 손절매 거리
            stop_distance = current_price * self.config.stop_loss_pct
            
            if stop_distance > 0:
                position_size = risk_amount / stop_distance
                return position_size * current_price
            else:
                return account_balance * self.config.position_size_value
                
        except Exception as e:
            self.logger.error(f"리스크 기반 사이징 계산 실패: {e}", exc_info=True)
            return account_balance * self.config.position_size_value
            
    def _calculate_kelly_size(self, account_balance: float, stock_code: str, stock_data: Optional[Dict]) -> float:
        """Kelly Criterion 기반 포지션 사이징"""
        try:
            if not self.config.use_kelly_criterion:
                return account_balance * self.config.position_size_value
                
            # 과거 성과에서 승률과 평균 수익/손실 계산
            win_rate, avg_win, avg_loss = self._get_historical_performance()
            
            if win_rate <= 0 or avg_win <= 0 or avg_loss <= 0:
                # 데이터 부족 시 기본 비율 사용
                return account_balance * self.config.position_size_value
                
            # Kelly Criterion: f = (bp - q) / b
            # f = 베팅 비율, b = 배당률, p = 승률, q = 패율
            p = win_rate
            q = 1 - win_rate
            b = avg_win / avg_loss  # 승/패 비율
            
            kelly_fraction = (b * p - q) / b
            
            # 보수적 접근: Kelly 결과에 multiplier 적용
            kelly_fraction = kelly_fraction * self.config.kelly_multiplier
            
            # 최대 비율 제한
            kelly_fraction = min(kelly_fraction, self.config.max_position_pct)
            kelly_fraction = max(kelly_fraction, 0.01)  # 최소 1%
            
            position_amount = account_balance * kelly_fraction
            
            self.logger.info(f"Kelly Criterion: 승률={win_rate:.2%}, 배당률={b:.2f}, Kelly비율={kelly_fraction:.2%}")
            
            return position_amount
            
        except Exception as e:
            self.logger.error(f"Kelly 사이징 계산 실패: {e}", exc_info=True)
            return account_balance * self.config.position_size_value
            
    def _get_historical_performance(self) -> Tuple[float, float, float]:
        """과거 성과 데이터 조회 (승률, 평균 수익, 평균 손실)"""
        try:
            # 매매일지에서 과거 30일 데이터 수집
            from datetime import timedelta
            import glob
            
            wins = []
            losses = []
            
            # 최근 30일 매매 요약 파일 찾기
            for i in range(30):
                date = (datetime.now() - timedelta(days=i)).strftime("%Y%m%d")
                summary_file = f"data/trades/trade_summary_{date}.json"
                
                if os.path.exists(summary_file):
                    with open(summary_file, 'r', encoding='utf-8') as f:
                        summary = json.load(f)
                        
                    for detail in summary.get('details', []):
                        pnl = detail.get('pnl', 0)
                        if pnl > 0:
                            wins.append(pnl)
                        elif pnl < 0:
                            losses.append(abs(pnl))
            
            if not wins and not losses:
                # 데이터 없으면 기본값 사용
                return 0.6, 100000, 50000  # 60% 승률, 평균 수익 10만원, 평균 손실 5만원
                
            total_trades = len(wins) + len(losses)
            win_rate = len(wins) / total_trades if total_trades > 0 else 0.5
            avg_win = sum(wins) / len(wins) if wins else 100000
            avg_loss = sum(losses) / len(losses) if losses else 50000
            
            return win_rate, avg_win, avg_loss
            
        except Exception as e:
            self.logger.error(f"과거 성과 조회 실패: {e}", exc_info=True)
            return 0.6, 100000, 50000

    def _calculate_stop_prices(
        self,
        stock_code: str,
        entry_price: int,
        stock_data: Optional[Dict[str, Any]] = None
    ) -> Tuple[float, float, Optional[StopLossResult]]:
        """손절/익절가 계산 (동적 ATR 또는 고정 비율)

        Args:
            stock_code: 종목 코드
            entry_price: 진입가
            stock_data: 종목 데이터 (일봉 데이터 포함 시 ATR 계산 가능)

        Returns:
            (손절가, 익절가, StopLossResult 또는 None)
        """
        try:
            # 동적 손절/익절 사용 시
            if self.config.use_dynamic_stops and self.dynamic_stop_calculator:
                # 일봉 데이터 조회 시도
                df = self._get_ohlcv_data(stock_code)

                if df is not None and len(df) >= self.config.atr_period:
                    # ATR 기반 동적 손절/익절 계산
                    stop_result = self.dynamic_stop_calculator.get_stops(entry_price, df)

                    self.logger.info(
                        f"📊 ATR 기반 동적 손절/익절 적용 - {stock_code}: "
                        f"손절 {stop_result.stop_loss:,}원 ({stop_result.stop_distance_pct:.1%}), "
                        f"익절 {stop_result.take_profit:,}원 ({stop_result.profit_distance_pct:.1%}), "
                        f"ATR {stop_result.atr:.0f}원, 손익비 {stop_result.risk_reward_ratio:.2f}"
                    )

                    # 트레일링 스탑 초기화
                    if self.config.use_trailing_stop:
                        self.dynamic_stop_calculator.init_trailing_stop(
                            stock_code=stock_code,
                            entry_price=entry_price,
                            df=df,
                            activation_threshold=self.config.trailing_activation_pct
                        )

                    return float(stop_result.stop_loss), float(stop_result.take_profit), stop_result
                else:
                    self.logger.warning(
                        f"일봉 데이터 부족 ({len(df) if df is not None else 0}일) - "
                        f"고정 비율 손절/익절 사용: {stock_code}"
                    )

            # 고정 비율 손절/익절 (기본)
            stop_loss = entry_price * (1 - self.config.stop_loss_pct)
            take_profit = entry_price * (1 + self.config.take_profit_pct)

            self.logger.info(
                f"📊 고정 비율 손절/익절 적용 - {stock_code}: "
                f"손절 {stop_loss:,.0f}원 ({self.config.stop_loss_pct:.1%}), "
                f"익절 {take_profit:,.0f}원 ({self.config.take_profit_pct:.1%})"
            )

            return stop_loss, take_profit, None

        except Exception as e:
            self.logger.error(f"손절/익절가 계산 실패 {stock_code}: {e}", exc_info=True)
            # 폴백: 고정 비율
            stop_loss = entry_price * (1 - self.config.stop_loss_pct)
            take_profit = entry_price * (1 + self.config.take_profit_pct)
            return stop_loss, take_profit, None

    def _get_ohlcv_data(self, stock_code: str, days: int = 60) -> Optional['pd.DataFrame']:
        """종목의 OHLCV 일봉 데이터 조회

        Args:
            stock_code: 종목 코드
            days: 조회 일수 (기본 60일)

        Returns:
            OHLCV 데이터프레임 또는 None
        """
        try:
            import pandas as pd

            if not self.api:
                return None

            # KIS API로 일봉 데이터 조회
            history = self.api.get_stock_history(stock_code, period="D", count=days)

            if history is None or len(history) == 0:
                return None

            # 이미 DataFrame인 경우 그대로 반환
            if isinstance(history, pd.DataFrame):
                return history

            # 리스트인 경우 DataFrame으로 변환
            df = pd.DataFrame(history)

            # 컬럼명 표준화 (KIS API 응답에 맞게)
            column_map = {
                'stck_oprc': 'open',
                'stck_hgpr': 'high',
                'stck_lwpr': 'low',
                'stck_clpr': 'close',
                'acml_vol': 'volume'
            }
            df = df.rename(columns=column_map)

            # 숫자 타입 변환
            for col in ['open', 'high', 'low', 'close', 'volume']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            return df

        except Exception as e:
            self.logger.error(f"OHLCV 데이터 조회 실패 {stock_code}: {e}", exc_info=True)
            return None

    def _should_buy(self, stock_data: Dict[str, Any]) -> Tuple[bool, str]:
        """매수 조건 확인"""
        try:
            stock_code = stock_data.get('stock_code')
            current_price = stock_data.get('current_price', 0)
            volume_ratio = stock_data.get('volume_ratio', 0)
            price_change_rate = abs(stock_data.get('change_rate', 0))
            
            # 기본 검증
            if not stock_code or current_price <= 0:
                return False, "가격 정보 부족"
                
            # 이미 보유 중인지 확인
            if stock_code in self.positions:
                return False, "이미 보유 중"
                
            # 최대 포지션 수 확인
            if len(self.positions) >= self.config.max_positions:
                return False, "최대 포지션 수 초과"
                
            # 일일 거래 한도 확인
            if self.daily_trades >= self.config.max_trades_per_day:
                return False, "일일 거래 한도 초과"
                
            # 거래량 조건 확인
            if volume_ratio < self.config.min_volume_ratio:
                return False, f"거래량 부족 ({volume_ratio:.2f})"
                
            # 가격 변동률 확인 (너무 급등/급락한 종목 제외)
            if price_change_rate > self.config.max_price_change:
                return False, f"가격 변동률 초과 ({price_change_rate:.2f}%)"
                
            return True, "매수 조건 충족"
            
        except Exception as e:
            self.logger.error(f"매수 조건 확인 실패: {e}", exc_info=True)
            return False, f"오류: {e}"
            
    def _should_sell(self, position: Position) -> Tuple[bool, str]:
        """매도 조건 확인"""
        try:
            current_return = position.unrealized_return
            
            # 손절매 조건
            if current_return <= -self.config.stop_loss_pct:
                return True, "stop_loss"
                
            # 익절매 조건
            if current_return >= self.config.take_profit_pct:
                return True, "take_profit"
                
            # 시간 기반 매도 (장 마감 30분 전)
            now = datetime.now().time()
            market_end = datetime.strptime(self.config.market_end, "%H:%M").time()
            
            # 30분 전 계산
            market_end_dt = datetime.combine(datetime.today(), market_end)
            sell_time = market_end_dt - timedelta(minutes=30)
            
            if now >= sell_time.time():
                return True, "time_based"
                
            return False, "보유 유지"
            
        except Exception as e:
            self.logger.error(f"매도 조건 확인 실패: {e}", exc_info=True)
            return False, f"오류: {e}"
            
    async def _execute_buy_order(self, stock_data: Dict[str, Any]) -> bool:
        """매수 주문 실행"""
        try:
            stock_code = stock_data['stock_code']
            stock_name = stock_data.get('stock_name', stock_code)
            current_price = stock_data['current_price']
            
            # 포지션 크기 계산 (고도화된 알고리즘 사용)
            quantity = self._calculate_position_size(stock_code, current_price, stock_data)
            
            if quantity <= 0:
                self.logger.warning(f"매수 불가 - 수량이 0: {stock_code}")
                return False
                
            # 주문 가격 (현재가 기준)
            order_price = int(current_price)
            
            # 한투 API 매수 주문 실행
            result = self.api.place_order(
                stock_code=stock_code,
                order_type=self.api.ORDER_TYPE_BUY,  # "02"
                quantity=quantity,
                price=order_price,
                order_division=self.api.ORDER_DIVISION_LIMIT  # "00" (지정가)
            )
            
            if result and result.get('success'):
                # 손절/익절가 계산 (동적 또는 고정)
                stop_loss_price, target_price_value, stop_info = self._calculate_stop_prices(
                    stock_code, int(current_price), stock_data
                )

                # 포지션 기록
                position = Position(
                    stock_code=stock_code,
                    stock_name=stock_name,
                    quantity=quantity,
                    avg_price=current_price,
                    current_price=current_price,
                    entry_time=datetime.now().isoformat(),
                    unrealized_pnl=0.0,
                    unrealized_return=0.0,
                    stop_loss=stop_loss_price,
                    target_price=target_price_value
                )
                
                self.positions[stock_code] = position
                self.daily_trades += 1
                
                # 매매일지 기록 (Phase 2 예측 메타데이터 포함)
                self.journal.log_order(
                    stock_code=stock_code,
                    stock_name=stock_name,
                    side="buy",
                    price=current_price,
                    quantity=quantity,
                    reason="auto_trading",
                    meta={
                        "strategy": "daily_selection",
                        "order_id": result.get("order_id"),
                        "target_price": position.target_price,
                        "stop_loss": position.stop_loss,
                        # Phase 2 예측 정보 (Phase 4 학습용)
                        "entry_price": stock_data.get("entry_price", current_price),
                        "expected_return": stock_data.get("expected_return", 0),
                        "predicted_probability": stock_data.get("confidence", 0.5),
                        "predicted_class": stock_data.get("predicted_class", 1),
                        "model_name": stock_data.get("model_name", "ensemble"),
                        "price_attractiveness": stock_data.get("price_attractiveness", 0)
                    }
                )
                
                self.logger.info(f"매수 완료: {stock_code} {quantity}주 @ {current_price:,.0f}원")
                
                # 텔레그램 알림
                if self.notifier.is_enabled():
                    message = f"""📈 *자동 매수 체결*
                    
종목: {stock_name} ({stock_code})
수량: {quantity:,}주
가격: {current_price:,.0f}원
투자금: {quantity * current_price:,.0f}원

목표가: {position.target_price:,.0f}원 (+{self.config.take_profit_pct:.1%})
손절가: {position.stop_loss:,.0f}원 (-{self.config.stop_loss_pct:.1%})"""
                    
                    self.notifier.send_message(message, "high")
                
                return True
                
            else:
                error_msg = result.get('message', '알 수 없는 오류') if result else "응답 없음"
                self.logger.error(f"매수 주문 실패: {stock_code} - {error_msg}", exc_info=True)
                return False
                
        except Exception as e:
            self.logger.error(f"매수 주문 실행 실패: {e}", exc_info=True)
            return False
            
    async def _execute_sell_order(self, position: Position, reason: str) -> bool:
        """매도 주문 실행"""
        try:
            stock_code = position.stock_code
            
            # 현재가 조회
            price_data = self.api.get_current_price(stock_code)
            if not price_data:
                self.logger.error(f"현재가 조회 실패: {stock_code}", exc_info=True)
                return False
                
            current_price = price_data.get('current_price', position.current_price)
            order_price = int(current_price)
            
            # 한투 API 매도 주문 실행
            result = self.api.place_order(
                stock_code=stock_code,
                order_type=self.api.ORDER_TYPE_SELL,  # "01"
                quantity=position.quantity,
                price=order_price,
                order_division=self.api.ORDER_DIVISION_LIMIT  # "00" (지정가)
            )
            
            if result and result.get('success'):
                # 손익 계산
                pnl = (current_price - position.avg_price) * position.quantity
                return_rate = (current_price - position.avg_price) / position.avg_price
                
                # 매매일지 기록
                self.journal.log_order(
                    stock_code=stock_code,
                    stock_name=position.stock_name,
                    side="sell",
                    price=current_price,
                    quantity=position.quantity,
                    reason=f"auto_trading:{reason}",
                    meta={
                        "pnl": pnl,
                        "return_rate": return_rate,
                        "hold_days": (datetime.now() - datetime.fromisoformat(position.entry_time)).days,
                        "entry_price": position.avg_price,
                        "order_id": result.get("order_id")
                    }
                )
                
                # 포지션 제거
                del self.positions[stock_code]
                self.daily_trades += 1
                
                self.logger.info(f"매도 완료: {stock_code} {position.quantity}주 @ {current_price:,.0f}원 (손익: {pnl:+,.0f}원)")
                
                # 텔레그램 알림
                if self.notifier.is_enabled():
                    pnl_emoji = "💰" if pnl > 0 else "📉" if pnl < 0 else "➖"
                    reason_text = {
                        "stop_loss": "손절매",
                        "take_profit": "익절매", 
                        "time_based": "시간 기반 매도"
                    }.get(reason, reason)
                    
                    message = f"""{pnl_emoji} *자동 매도 체결*
                    
종목: {position.stock_name} ({stock_code})
수량: {position.quantity:,}주
매도가: {current_price:,.0f}원
매수가: {position.avg_price:,.0f}원

실현손익: {pnl:+,.0f}원
수익률: {return_rate:+.2%}
매도사유: {reason_text}"""
                    
                    priority = "high" if pnl > 0 else "emergency" if pnl < -50000 else "normal"
                    self.notifier.send_message(message, priority)
                
                return True
                
            else:
                error_msg = result.get('message', '알 수 없는 오류') if result else "응답 없음"
                self.logger.error(f"매도 주문 실패: {stock_code} - {error_msg}", exc_info=True)
                return False
                
        except Exception as e:
            self.logger.error(f"매도 주문 실행 실패: {e}", exc_info=True)
            return False
            
    async def _update_positions(self):
        """포지션 현재가 업데이트"""
        try:
            for stock_code, position in self.positions.items():
                # 현재가 조회
                price_data = self.api.get_current_price(stock_code)
                if price_data:
                    current_price = price_data.get('current_price')
                    if current_price and current_price > 0:
                        # 평가손익 계산
                        unrealized_pnl = (current_price - position.avg_price) * position.quantity
                        unrealized_return = (current_price - position.avg_price) / position.avg_price
                        
                        # 포지션 업데이트
                        position.current_price = current_price
                        position.unrealized_pnl = unrealized_pnl
                        position.unrealized_return = unrealized_return
                        
        except Exception as e:
            self.logger.error(f"포지션 업데이트 실패: {e}", exc_info=True)
            
    async def _trading_loop(self):
        """매매 실행 루프"""
        self.logger.info("자동 매매 루프 시작")
        
        while self.is_running:
            try:
                # 거래 가능 시간 확인
                if not self._is_tradeable_day() or not self._is_market_time():
                    await asyncio.sleep(60)  # 1분 대기
                    continue
                    
                # 포지션 현재가 업데이트
                await self._update_positions()
                
                # 매도 신호 확인 (기존 포지션)
                positions_to_sell = []
                for stock_code, position in self.positions.items():
                    should_sell, reason = self._should_sell(position)
                    if should_sell:
                        positions_to_sell.append((position, reason))
                        
                # 매도 실행
                for position, reason in positions_to_sell:
                    await self._execute_sell_order(position, reason)
                    await asyncio.sleep(1)  # API 호출 간격
                    
                # 매수 신호 확인 (신규 매수)
                if len(self.positions) < self.config.max_positions:
                    # 일일 선정 종목 중 매수 대상 찾기
                    selected_stocks = self._load_daily_selection()
                    
                    for stock_data in selected_stocks:
                        if not self.is_running:
                            break
                            
                        should_buy, reason = self._should_buy(stock_data)
                        if should_buy:
                            # 현재가 재조회
                            current_price_data = self.api.get_current_price(stock_data['stock_code'])
                            if current_price_data:
                                stock_data['current_price'] = current_price_data.get('current_price')
                                await self._execute_buy_order(stock_data)
                                await asyncio.sleep(2)  # API 호출 간격
                                
                                # 매수 후 잠시 대기 (한 번에 너무 많이 매수하지 않도록)
                                break
                                
                # 30초 대기 후 다음 사이클
                await asyncio.sleep(30)
                
            except Exception as e:
                self.logger.error(f"매매 루프 오류: {e}", exc_info=True)
                await asyncio.sleep(60)  # 오류 시 1분 대기
                
        self.logger.info("자동 매매 루프 종료")
        
    async def start_trading(self) -> bool:
        """자동 매매 시작"""
        if self.is_running:
            self.logger.warning("이미 매매가 실행 중입니다")
            return False

        try:
            # API 초기화
            if not self._initialize_api():
                return False

            # 거래 가능한 날인지 확인
            if not self._is_tradeable_day():
                self.logger.info("오늘은 거래 가능한 날이 아닙니다 (주말/공휴일)")
                return False

            # ⚠️ 계좌 잔고 확인 (중요!)
            account_balance = self._get_account_balance()
            available_cash = self._get_available_cash()

            if account_balance <= 0 or available_cash <= 0:
                error_msg = f"""
❌ 자동 매매 시작 실패: 계좌 잔고가 0원입니다!

📋 문제:
   - 총 자산: {account_balance:,.0f}원
   - 가용 현금: {available_cash:,.0f}원

🔧 해결 방법:
   1. 한국투자증권 모의투자 사이트 접속
   2. 모의투자 > 계좌 초기화
   3. 초기 자금 설정 (권장: 1억원)
   4. 상세 가이드: VIRTUAL_ACCOUNT_SETUP.md 참조

💡 테스트: python tests/test_kis_virtual_account.py
"""
                self.logger.error(error_msg)
                print(error_msg)

                # 텔레그램 알림 전송
                if self.notifier.is_enabled():
                    alert_msg = f"""⚠️ *자동 매매 시작 실패*

❌ **문제**: 계좌 잔고 0원

📋 **계좌 정보**:
• 총 자산: {account_balance:,.0f}원
• 가용 현금: {available_cash:,.0f}원

🔧 **해결 방법**:
1. 한투 모의투자 사이트 접속
2. 계좌 초기화 및 자금 설정
3. 권장 초기 자금: 1억원

📚 상세 가이드: VIRTUAL_ACCOUNT_SETUP.md"""

                    self.notifier.send_message(alert_msg, "emergency")

                return False

            self.logger.info(f"계좌 잔고 확인 완료: 총자산 {account_balance:,.0f}원, 가용현금 {available_cash:,.0f}원")

            # 일일 카운터 초기화
            self.daily_trades = 0
            self.start_time = datetime.now()

            # 기존 포지션 로드 (잔고에서)
            await self._load_existing_positions()
            
            # 매매 시작 알림
            if self.notifier.is_enabled():
                message = f"""🚀 *자동 매매 시작*
                
⏰ 시작 시간: {self.start_time.strftime('%H:%M:%S')}
🏦 계좌 유형: {self.api_config.server}
📊 설정 정보:
• 최대 보유 종목: {self.config.max_positions}개
• 종목당 투자금: {self.config.position_size_value*100:.1f}%
• 손절매: {self.config.stop_loss_pct:.1%}
• 익절매: {self.config.take_profit_pct:.1%}

🤖 AI가 선별한 종목으로 자동매매를 시작합니다!"""
                
                self.notifier.send_message(message, "high")
            
            # 매매 실행
            self.is_running = True
            await self._trading_loop()
            
            return True
            
        except Exception as e:
            self.logger.error(f"자동 매매 시작 실패: {e}", exc_info=True)
            return False
            
    async def stop_trading(self, reason: str = "사용자 요청") -> bool:
        """자동 매매 중지"""
        if not self.is_running:
            self.logger.warning("매매가 실행 중이 아닙니다")
            return False
            
        try:
            self.is_running = False
            
            # 종료 알림
            if self.notifier.is_enabled():
                end_time = datetime.now()
                runtime = end_time - self.start_time if self.start_time else timedelta(0)
                
                # 오늘 거래 요약
                summary = self.journal.compute_daily_summary()
                
                message = f"""⏹️ *자동 매매 종료*
                
⏰ 종료 시간: {end_time.strftime('%H:%M:%S')}
📝 종료 사유: {reason}
⏱️ 운영 시간: {str(runtime).split('.')[0]}

📊 *오늘의 매매 결과*:
• 총 거래: {summary.get('total_trades', 0)}건
• 실현 손익: {summary.get('realized_pnl', 0):+,.0f}원
• 승률: {summary.get('win_rate', 0)*100:.1f}%

🔄 보유 중인 포지션: {len(self.positions)}개"""
                
                if self.positions:
                    message += "\n\n📋 *보유 종목*:"
                    for code, pos in self.positions.items():
                        message += f"\n• {pos.stock_name}: {pos.unrealized_pnl:+,.0f}원"
                
                self.notifier.send_message(message, "normal")
            
            self.logger.info(f"자동 매매 종료: {reason}")
            return True
            
        except Exception as e:
            self.logger.error(f"자동 매매 종료 실패: {e}", exc_info=True)
            return False
            
    async def _load_existing_positions(self):
        """기존 보유 포지션 로드"""
        try:
            balance = self.api.get_balance()
            if not balance or not balance.get('positions'):
                self.logger.info("기존 보유 포지션이 없습니다")
                return
                
            for stock_code, pos_data in balance['positions'].items():
                if pos_data.get('quantity', 0) > 0:
                    position = Position(
                        stock_code=stock_code,
                        stock_name=pos_data.get('stock_name', stock_code),
                        quantity=pos_data['quantity'],
                        avg_price=pos_data.get('avg_price', 0),
                        current_price=pos_data.get('current_price', 0),
                        entry_time=datetime.now().isoformat(),  # 정확한 매수 시간은 알 수 없음
                        unrealized_pnl=pos_data.get('unrealized_pnl', 0),
                        unrealized_return=pos_data.get('unrealized_return', 0),
                        stop_loss=pos_data.get('avg_price', 0) * (1 - self.config.stop_loss_pct),
                        target_price=pos_data.get('avg_price', 0) * (1 + self.config.take_profit_pct)
                    )
                    
                    self.positions[stock_code] = position
                    
            self.logger.info(f"기존 포지션 로드 완료: {len(self.positions)}개")
            
        except Exception as e:
            self.logger.error(f"기존 포지션 로드 실패: {e}", exc_info=True)
            
    def get_status(self) -> Dict[str, Any]:
        """매매 엔진 상태 조회"""
        return {
            "is_running": self.is_running,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "positions_count": len(self.positions),
            "daily_trades": self.daily_trades,
            "positions": {code: asdict(pos) for code, pos in self.positions.items()},
            "config": asdict(self.config)
        }


# 전역 인스턴스
_trading_engine = None

def get_trading_engine(config: TradingConfig = None) -> TradingEngine:
    """매매 엔진 싱글톤 인스턴스 반환

    Args:
        config: 매매 설정 (최초 생성 시에만 적용, 이후 호출에서는 무시)

    Returns:
        TradingEngine: 매매 엔진 싱글톤 인스턴스
    """
    global _trading_engine
    if _trading_engine is None:
        _trading_engine = TradingEngine(config)
    return _trading_engine


def reset_trading_engine():
    """매매 엔진 싱글톤 초기화 (테스트용)"""
    global _trading_engine
    _trading_engine = None