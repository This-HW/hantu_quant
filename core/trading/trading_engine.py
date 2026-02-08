"""
자동 매매 실행 엔진 (Phase 3)
가상계좌를 사용한 실제 주식 자동매매 시스템
"""

import os
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Literal
from dataclasses import dataclass, asdict
from pathlib import Path

from ..api.kis_api import KISAPI
from ..config.api_config import APIConfig
from ..trading.trade_journal import TradeJournal
from ..trading.dynamic_stop_loss import DynamicStopLossCalculator, StopLossResult
from ..utils.log_utils import get_logger
from ..utils.telegram_notifier import get_telegram_notifier
from ..risk.position.kelly_calculator import KellyCalculator
from ..market.market_regime import MarketRegimeDetector

logger = get_logger(__name__)


@dataclass
class Position:
    """포지션 정보 (P0-5b 부분 익절 확장)"""

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

    # P0-5b: 부분 익절 필드
    partial_sold: bool = False  # 1차 익절 완료 여부
    partial_profit_price: Optional[float] = None  # 1차 익절 가격


@dataclass
class TradingConfig:
    """매매 설정 (보수적 버전)"""

    max_positions: int = 10  # 최대 보유 종목수
    position_size_method: str = (
        "account_pct"  # 포지션 크기 방법: "fixed", "account_pct", "risk_based", "kelly"
    )
    position_size_value: float = 0.05  # 계좌 대비 5% (10%→5% 보수적)
    fixed_position_size: float = 1000000  # 고정 투자금액 (fixed 모드용)
    stop_loss_pct: float = 0.03  # 손절매 비율 (5%→3% 빠른 손절) - 고정 손절 시 사용
    take_profit_pct: float = (
        0.08  # 익절매 비율 (10%→8% 현실적 목표) - 고정 익절 시 사용
    )
    max_trades_per_day: int = 15  # 일일 최대 거래횟수 (20→15 제한)
    risk_per_trade: float = 0.015  # 거래당 위험비율 (2%→1.5% 보수적)

    # 포지션 사이징 고급 설정 (보수적)
    max_position_pct: float = 0.08  # 최대 단일 포지션 비율 (15%→8%)
    min_position_size: float = 100000  # 최소 투자금액 (10만원)
    use_kelly_criterion: bool = True  # Kelly Criterion 사용 여부
    kelly_multiplier: float = 0.20  # Kelly 결과에 곱할 보수 계수 (0.25→0.20 더 보수적)

    # ATR 기반 동적 손절/익절 설정 (P1-1)
    use_dynamic_stops: bool = True  # 동적 손절/익절 사용 여부
    atr_period: int = 14  # ATR 계산 기간
    atr_stop_multiplier: float = 2.0  # ATR 기반 손절 배수
    atr_profit_multiplier: float = 3.0  # ATR 기반 익절 배수
    use_trailing_stop: bool = True  # 트레일링 스탑 사용 여부
    trailing_activation_pct: float = 0.02  # 트레일링 활성화 수익률 (2%)

    # 부분 익절 설정 (P0-5b)
    partial_profit_first_pct: float = 0.05  # 1차 익절 기준 (5%)
    partial_profit_first_ratio: float = 0.5  # 1차 익절 비율 (50%)
    partial_profit_second_pct: float = 0.10  # 2차 익절 기준 (10%)

    # 매매 시간 설정
    market_start: str = "09:00"
    market_end: str = "15:30"
    pre_market_start: str = "08:30"  # 매매 준비 시간

    # 매수 조건
    min_volume_ratio: float = 1.5  # 최소 거래량 비율
    max_price_change: float = 0.30  # 최대 가격 변동률 (30%)

    # Dynamic Kelly 설정 (P1)
    use_regime_adjusted_kelly: bool = True  # 시장 상황별 Kelly 조정


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
        self.dynamic_stop_calculator = (
            DynamicStopLossCalculator(
                atr_period=self.config.atr_period,
                stop_multiplier=self.config.atr_stop_multiplier,
                profit_multiplier=self.config.atr_profit_multiplier,
                trailing_multiplier=self.config.atr_stop_multiplier
                * 0.75,  # 트레일링은 손절의 75%
            )
            if self.config.use_dynamic_stops
            else None
        )

        # 데이터 저장 경로
        self.data_dir = Path("data/trading")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # 실시간 피드백 루프 (선택적)
        self._feedback_loop = None

        # Batch 4 기능: CircuitHandler, OpportunityDetector (지연 초기화)
        self._circuit_handler = None
        self._opportunity_detector = None
        self._daily_summary_generator = None

        # Kelly Calculator & Regime Detector (지연 초기화)
        self.kelly_calculator = KellyCalculator()
        self.regime_detector = None  # lazy init

        self.logger.info(
            f"자동 매매 엔진 초기화 완료 "
            f"(동적손절: {'활성화' if self.config.use_dynamic_stops else '비활성화'})"
        )

    def _get_feedback_loop(self):
        """피드백 루프 싱글톤 인스턴스"""
        if self._feedback_loop is None:
            try:
                from core.selection.realtime_feedback import get_feedback_loop

                self._feedback_loop = get_feedback_loop()
            except ImportError:
                self.logger.debug("RealtimeFeedbackLoop 모듈 로드 실패 (무시)")
        return self._feedback_loop

    def _get_circuit_handler(self):
        """서킷 핸들러 싱글톤 인스턴스 (Batch 4-2)"""
        if self._circuit_handler is None:
            try:
                from core.trading.circuit_handler import CircuitHandler

                self._circuit_handler = CircuitHandler(
                    trading_engine=self,
                    notification_manager=None  # 알림은 TradingEngine에서 직접 처리
                )
            except ImportError:
                self.logger.debug("CircuitHandler 모듈 로드 실패 (무시)")
        return self._circuit_handler

    def _get_opportunity_detector(self):
        """추가 매수 기회 감지기 싱글톤 인스턴스 (Batch 4-1)"""
        if self._opportunity_detector is None:
            try:
                from core.trading.opportunity_detector import OpportunityDetector

                self._opportunity_detector = OpportunityDetector()
            except ImportError:
                self.logger.debug("OpportunityDetector 모듈 로드 실패 (무시)")
        return self._opportunity_detector

    def _get_daily_summary_generator(self):
        """일일 요약 생성기 싱글톤 인스턴스 (Batch 4-3)"""
        if self._daily_summary_generator is None:
            try:
                from core.trading.daily_summary import DailySummaryGenerator

                self._daily_summary_generator = DailySummaryGenerator()
            except ImportError:
                self.logger.debug("DailySummaryGenerator 모듈 로드 실패 (무시)")
        return self._daily_summary_generator

    def _record_trade_feedback(
        self,
        stock_code: str,
        stock_name: str,
        entry_price: float,
        exit_price: float,
        entry_time: str,
        pnl: float,
        pnl_pct: float,
        exit_reason: str,
    ):
        """거래 결과를 피드백 루프에 기록"""
        try:
            feedback_loop = self._get_feedback_loop()
            if feedback_loop is None:
                return

            from core.selection.realtime_feedback import TradeResult

            trade_result = TradeResult(
                stock_code=stock_code,
                stock_name=stock_name,
                entry_price=entry_price,
                exit_price=exit_price,
                entry_time=entry_time,
                exit_time=datetime.now().isoformat(),
                pnl=pnl,
                pnl_pct=pnl_pct,
                is_winner=pnl > 0,
                exit_reason=exit_reason,
            )

            feedback_loop.on_trade_closed(trade_result)
            self.logger.debug(f"피드백 기록 완료: {stock_code}")

        except Exception as e:
            self.logger.warning(f"피드백 기록 실패 (무시): {e}", exc_info=True)

    async def sell(
        self,
        stock_code: str,
        quantity: int,
        order_type: Literal["시장가", "지정가"] = "시장가",
        price: Optional[int] = None,
        reason: str = "manual",
    ) -> Dict[str, Any]:
        """매도 주문 실행 (Public Interface)

        Args:
            stock_code: 종목 코드 (6자리)
            quantity: 매도 수량
            order_type: 주문 유형 ("시장가" 또는 "지정가")
            price: 지정가 주문 시 가격 (지정가일 경우 필수)
            reason: 매도 사유

        Returns:
            {
                "success": bool,
                "order_number": str,
                "message": str,
                "pnl": Optional[float],
                "return_rate": Optional[float]
            }

        Raises:
            ValueError: 파라미터 검증 실패 시
        """
        try:
            # === 1. 파라미터 검증 ===
            if not stock_code or len(stock_code) != 6:
                raise ValueError(f"유효하지 않은 종목 코드: {stock_code} (6자리 필요)")

            if quantity <= 0:
                raise ValueError(f"수량은 양수여야 합니다: {quantity}")

            if order_type not in ["시장가", "지정가"]:
                raise ValueError(f"유효하지 않은 주문 유형: {order_type}")

            if order_type == "지정가" and (price is None or price <= 0):
                raise ValueError("지정가 주문 시 가격이 필요합니다")

            # API 초기화 확인
            if not self.api:
                if not self._initialize_api():
                    return {
                        "success": False,
                        "order_number": "",
                        "message": "API 초기화 실패",
                    }

            # === 2. 현재가 조회 ===
            if order_type == "시장가" or price is None:
                price_data = self.api.get_current_price(stock_code)
                if not price_data:
                    self.logger.error(
                        f"현재가 조회 실패: {stock_code}",
                        exc_info=True,
                        extra={"stock_code": stock_code},
                    )
                    return {
                        "success": False,
                        "order_number": "",
                        "message": f"현재가 조회 실패: {stock_code}",
                    }

                current_price = price_data.get("current_price", 0)
                if current_price <= 0:
                    self.logger.error(
                        f"유효하지 않은 현재가: {stock_code} - {current_price}원",
                        exc_info=True,
                        extra={"stock_code": stock_code, "price": current_price},
                    )
                    return {
                        "success": False,
                        "order_number": "",
                        "message": f"유효하지 않은 현재가: {current_price}원",
                    }

                price = int(current_price)

            # === 3. KIS API 주문 실행 ===
            order_division = (
                self.api.ORDER_DIVISION_MARKET
                if order_type == "시장가"
                else self.api.ORDER_DIVISION_LIMIT
            )

            result = self.api.place_order(
                stock_code=stock_code,
                order_type=self.api.ORDER_TYPE_SELL,  # "01"
                quantity=quantity,
                price=price,
                order_division=order_division,
            )

            if not result or not result.get("success"):
                error_msg = (
                    result.get("message", "알 수 없는 오류") if result else "응답 없음"
                )
                self.logger.error(
                    f"매도 주문 실패: {stock_code}",
                    exc_info=True,
                    extra={
                        "stock_code": stock_code,
                        "quantity": quantity,
                        "price": price,
                        "order_type": order_type,
                        "error": error_msg,
                    },
                )
                return {
                    "success": False,
                    "order_number": "",
                    "message": f"매도 주문 실패: {error_msg}",
                }

            # === 4. 손익 계산 ===
            pnl = None
            return_rate = None
            # 변경: result['data']에서 주문번호 추출
            order_data = result.get("data", {})
            order_number = order_data.get("ODNO", order_data.get("ORD_NO", ""))

            # 포지션에서 손익 계산
            if stock_code in self.positions:
                position = self.positions[stock_code]

                pnl = (price - position.avg_price) * quantity
                if position.avg_price > 0:
                    return_rate = (price - position.avg_price) / position.avg_price
                else:
                    return_rate = 0.0
                    self.logger.warning(
                        f"avg_price가 0입니다: {stock_code}",
                        extra={"stock_code": stock_code, "avg_price": position.avg_price},
                    )

                # 매매일지 기록
                self.journal.log_order(
                    stock_code=stock_code,
                    stock_name=position.stock_name,
                    side="sell",
                    price=price,
                    quantity=quantity,
                    reason=f"manual:{reason}",
                    meta={
                        "pnl": pnl,
                        "return_rate": return_rate,
                        "hold_days": (
                            datetime.now() - datetime.fromisoformat(position.entry_time)
                        ).days,
                        "entry_price": position.avg_price,
                        "order_id": order_number,
                        "order_type": order_type,
                    },
                )

                # 실시간 피드백 루프 기록
                self._record_trade_feedback(
                    stock_code=stock_code,
                    stock_name=position.stock_name,
                    entry_price=position.avg_price,
                    exit_price=price,
                    entry_time=position.entry_time,
                    pnl=pnl,
                    pnl_pct=return_rate * 100,
                    exit_reason=reason,
                )

                # 포지션 제거 또는 수량 감소
                if quantity >= position.quantity:
                    # 전량 매도
                    del self.positions[stock_code]
                    self.logger.info(
                        f"포지션 전량 매도: {stock_code} {quantity}주 @ {price:,}원 (손익: {pnl:+,.0f}원)"
                    )
                else:
                    # 일부 매도
                    position.quantity -= quantity
                    position.unrealized_pnl = (
                        price - position.avg_price
                    ) * position.quantity
                    if position.avg_price > 0:
                        position.unrealized_return = (
                            price - position.avg_price
                        ) / position.avg_price
                    else:
                        position.unrealized_return = 0.0
                    self.logger.info(
                        f"포지션 일부 매도: {stock_code} {quantity}주 (잔여: {position.quantity}주) @ {price:,}원"
                    )

            # === 5. 로깅 및 반환 ===
            pnl_str = f" - 손익: {pnl:+,.0f}원" if pnl is not None else ""
            self.logger.info(
                f"매도 완료: {stock_code} {quantity}주 @ {price:,}원 ({order_type}){pnl_str}",
                extra={
                    "stock_code": stock_code,
                    "quantity": quantity,
                    "price": price,
                    "order_type": order_type,
                    "pnl": pnl,
                    "return_rate": return_rate,
                },
            )

            return {
                "success": True,
                "order_number": order_number,
                "message": f"매도 완료: {quantity}주 @ {price:,}원",
                "pnl": pnl,
                "return_rate": return_rate,
            }

        except ValueError as e:
            self.logger.error(
                f"매도 파라미터 검증 실패: {e}",
                exc_info=True,
                extra={"stock_code": stock_code, "quantity": quantity},
            )
            return {"success": False, "order_number": "", "message": str(e)}

        except Exception as e:
            self.logger.error(
                f"매도 실행 실패: {e}",
                exc_info=True,
                extra={
                    "stock_code": stock_code,
                    "quantity": quantity,
                    "price": price,
                    "order_type": order_type,
                },
            )
            return {
                "success": False,
                "order_number": "",
                "message": f"매도 실행 실패: {e}",
            }

    def _initialize_api(self) -> bool:
        """API 초기화"""
        try:
            self.api_config = APIConfig()

            # 실전 계좌 보호 (P0: 서버 환경 블로킹 방지)
            if self.api_config.server != "virtual":
                # TRADING_PROD_ENABLE 환경변수로 실전 거래 명시적 허용 확인
                prod_enable = os.environ.get("TRADING_PROD_ENABLE", "false").lower() == "true"

                if not prod_enable:
                    self.logger.critical(
                        "실전 계좌 사용 시도 감지 - TRADING_PROD_ENABLE=true 설정 필요"
                    )
                    raise RuntimeError(
                        "실전 거래가 차단되었습니다. "
                        "의도적으로 실전 거래를 활성화하려면 환경변수 TRADING_PROD_ENABLE=true를 설정하세요. "
                        "(CLAUDE.md 참조)"
                    )
                else:
                    self.logger.warning(
                        "실전 계좌 모드 활성화됨 (TRADING_PROD_ENABLE=true)"
                    )

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
                results = (
                    session.query(SelectionResult)
                    .filter(SelectionResult.selection_date == today_date)
                    .all()
                )

                if results:
                    selected_stocks = []
                    for r in results:
                        selected_stocks.append(
                            {
                                "stock_code": r.stock_code,
                                "stock_name": r.stock_name,
                                "total_score": r.total_score,
                                "technical_score": r.technical_score,
                                "volume_score": r.volume_score,
                                "entry_price": r.entry_price,
                                "target_price": r.target_price,
                                "stop_loss": r.stop_loss,
                                "signal": r.signal,
                                "confidence": r.confidence,
                            }
                        )
                    self.logger.info(
                        f"일일 선정 종목 DB 로드: {len(selected_stocks)}개"
                    )
                    return selected_stocks

        except Exception as e:
            self.logger.warning(f"DB 로드 실패, JSON 폴백: {e}")

        # === 2. JSON 파일에서 폴백 로드 ===
        selection_file = Path(f"data/daily_selection/daily_selection_{today}.json")

        if not selection_file.exists():
            self.logger.warning(f"일일 선정 파일이 없습니다: {selection_file}")
            return []

        try:
            with open(selection_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 다양한 데이터 형식 지원 (list, dict with data.selected_stocks, dict with stocks)
            if isinstance(data, list):
                selected_stocks = data
            elif isinstance(data, dict):
                selected_stocks = data.get("data", {}).get("selected_stocks", [])
                # stocks 키도 확인 (호환성)
                if not selected_stocks:
                    selected_stocks = data.get("stocks", [])
            else:
                selected_stocks = []
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

    def _calculate_position_size(
        self, stock_code: str, current_price: float, stock_data: Optional[Dict] = None
    ) -> int:
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
                investment_amount = self._calculate_risk_based_size(
                    account_balance, current_price
                )

            elif self.config.position_size_method == "kelly":
                # Kelly Criterion 기반
                investment_amount = self._calculate_kelly_size(
                    account_balance, stock_code, stock_data
                )

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

            self.logger.info(
                f"포지션 사이징: {stock_code} - 투자금액: {investment_amount:,.0f}원, 수량: {quantity}주"
            )

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

    def _calculate_risk_based_size(
        self, account_balance: float, current_price: float
    ) -> float:
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

    def _calculate_kelly_size(
        self, account_balance: float, stock_code: str, stock_data: Optional[Dict]
    ) -> float:
        """Kelly Criterion 기반 포지션 사이징 (KellyCalculator 위임)"""
        try:
            if not self.config.use_kelly_criterion:
                return account_balance * self.config.position_size_value

            # 과거 거래 수익률 조회
            trade_returns = self._get_trade_returns(stock_code)

            if not trade_returns or len(trade_returns) < 30:
                self.logger.warning(
                    f"Kelly: {stock_code} 거래 데이터 부족 ({len(trade_returns) if trade_returns else 0}건)"
                )
                return account_balance * self.config.position_size_value

            # KellyCalculator로 위임 (Half Kelly + 신뢰구간 조정 포함)
            kelly_result = self.kelly_calculator.calculate(trade_returns)

            # final_position은 이미 Half Kelly + confidence interval + min/max clip 적용됨
            kelly_fraction = kelly_result.final_position

            # Regime-adjusted Kelly
            if self.config.use_regime_adjusted_kelly:
                try:
                    if self.regime_detector is None:
                        self.regime_detector = MarketRegimeDetector()
                    regime_result = self.regime_detector.detect_regime()

                    from ..risk.position.regime_adjuster import RegimeAdjuster
                    adjustment = RegimeAdjuster.adjust_kelly(kelly_fraction, regime_result.regime)
                    kelly_fraction = adjustment.adjusted_fraction

                    self.logger.info(
                        f"Kelly Regime-adjusted: {regime_result.regime.value} "
                        f"({adjustment.original_fraction:.4f} → {adjustment.adjusted_fraction:.4f})"
                    )
                except Exception as e:
                    self.logger.warning(f"Regime 감지 실패, 기본 Kelly 사용: {e}", exc_info=True)

            # TradingEngine 포지션 제한 적용 (kelly_multiplier는 KellyCalculator에서 이미 조정됨)
            kelly_fraction = min(kelly_fraction, self.config.max_position_pct)
            kelly_fraction = max(kelly_fraction, 0.01)

            position_amount = account_balance * kelly_fraction

            self.logger.info(
                f"Kelly Criterion: {stock_code} 승률={kelly_result.win_rate:.2%}, "
                f"Kelly비율={kelly_fraction:.2%}, 투자금액={position_amount:,.0f}원"
            )

            return position_amount

        except Exception as e:
            self.logger.error(f"Kelly 사이징 계산 실패: {e}", exc_info=True)
            return account_balance * self.config.position_size_value

    def _get_trade_returns(self, stock_code: str = None, days: int = 60) -> List[float]:
        """과거 거래 수익률(%) 조회

        Args:
            stock_code: 종목 코드 (None이면 전체)
            days: 조회 기간 (일)

        Returns:
            수익률 리스트 (예: [0.03, -0.01, 0.05, ...])
        """
        try:
            returns = []

            for i in range(days):
                date = (datetime.now() - timedelta(days=i)).strftime("%Y%m%d")
                summary_file = f"data/trades/trade_summary_{date}.json"

                if os.path.exists(summary_file):
                    try:
                        with open(summary_file, "r", encoding="utf-8") as f:
                            summary = json.load(f)
                    except json.JSONDecodeError as e:
                        self.logger.warning(f"거래 요약 파일 파싱 실패 {date}: {e}")
                        continue
                    except Exception as e:
                        self.logger.error(f"거래 요약 파일 로드 실패 {date}: {e}", exc_info=True)
                        continue

                    # 파일이 비어있거나 details가 없는 경우 처리
                    if not summary or not isinstance(summary, dict):
                        self.logger.warning(f"거래 요약 파일이 비어있거나 잘못된 형식 {date}")
                        continue

                    for detail in summary.get("details", []):
                        # stock_code 필터
                        if stock_code and detail.get("stock_code") != stock_code:
                            continue

                        entry_price = detail.get("entry_price", 0)
                        exit_price = detail.get("exit_price", 0)

                        if entry_price > 0 and exit_price > 0:
                            return_pct = (exit_price - entry_price) / entry_price
                            returns.append(return_pct)
                        elif detail.get("pnl") and entry_price > 0:
                            # pnl만 있는 경우 수익률 환산
                            return_pct = detail["pnl"] / (entry_price * detail.get("quantity", 1))
                            returns.append(return_pct)

            return returns

        except Exception as e:
            self.logger.error(f"과거 거래 수익률 조회 실패: {e}", exc_info=True)
            return []

    def calculate_dynamic_stop(self, stock_code: str, entry_price: float) -> float:
        """변동성별 차등 손절가 계산 (P0-5a)

        Args:
            stock_code: 종목 코드
            entry_price: 진입가

        Returns:
            손절가
        """
        try:
            # ATR 조회
            df = self._get_ohlcv_data(stock_code)

            if df is None or len(df) < self.config.atr_period:
                # 데이터 부족 시 기본 손절 비율 사용
                return entry_price * (1 - self.config.stop_loss_pct)

            # ATR 계산
            if self.dynamic_stop_calculator:
                atr = self.dynamic_stop_calculator.calculate_atr(df)
            else:
                return entry_price * (1 - self.config.stop_loss_pct)

            atr_percent = atr / entry_price if entry_price > 0 else 0

            # 변동성별 차등 손절 비율 (P0-5a)
            if atr_percent < 0.03:  # 저변동성
                stop_loss_pct = 0.03
                volatility_level = "저변동성"
            elif atr_percent < 0.05:  # 중간
                stop_loss_pct = 0.05
                volatility_level = "중간변동성"
            else:  # 고변동성
                stop_loss_pct = 0.07
                volatility_level = "고변동성"

            stop_loss = entry_price * (1 - stop_loss_pct)

            self.logger.info(
                f"변동성별 차등 손절 - {stock_code}: "
                f"ATR {atr:.0f}원 ({atr_percent:.2%}), {volatility_level}, "
                f"손절비율 {stop_loss_pct:.1%}, 손절가 {stop_loss:,.0f}원"
            )

            return stop_loss

        except Exception as e:
            self.logger.error(f"변동성별 손절 계산 실패 {stock_code}: {e}", exc_info=True)
            return entry_price * (1 - self.config.stop_loss_pct)

    def _calculate_stop_prices(
        self,
        stock_code: str,
        entry_price: int,
        stock_data: Optional[Dict[str, Any]] = None,
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
                    stop_result = self.dynamic_stop_calculator.get_stops(
                        entry_price, df
                    )

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
                            activation_threshold=self.config.trailing_activation_pct,
                        )

                    return (
                        float(stop_result.stop_loss),
                        float(stop_result.take_profit),
                        stop_result,
                    )
                else:
                    self.logger.warning(
                        f"일봉 데이터 부족 ({len(df) if df is not None else 0}일) - "
                        f"변동성별 차등 손절 사용: {stock_code}"
                    )
                    # P0-5a: 변동성별 차등 손절 사용
                    stop_loss = self.calculate_dynamic_stop(stock_code, entry_price)
                    take_profit = entry_price * (1 + self.config.take_profit_pct)
                    return stop_loss, take_profit, None

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

    def _get_ohlcv_data(self, stock_code: str, days: int = 60) -> Optional[Any]:
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
                "stck_oprc": "open",
                "stck_hgpr": "high",
                "stck_lwpr": "low",
                "stck_clpr": "close",
                "acml_vol": "volume",
            }
            df = df.rename(columns=column_map)

            # 숫자 타입 변환
            for col in ["open", "high", "low", "close", "volume"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            return df

        except Exception as e:
            self.logger.error(
                f"OHLCV 데이터 조회 실패 {stock_code}: {e}", exc_info=True
            )
            return None

    def _should_buy(self, stock_data: Dict[str, Any]) -> Tuple[bool, str]:
        """매수 조건 확인"""
        try:
            stock_code = stock_data.get("stock_code")
            current_price = stock_data.get("current_price", 0)
            volume_ratio = stock_data.get("volume_ratio", 0)
            price_change_rate = abs(stock_data.get("change_rate", 0))

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

    async def check_partial_profit(self, position: Position) -> bool:
        """부분 익절 체크 (P0-5b)

        Args:
            position: 포지션 정보

        Returns:
            부분 익절 실행 여부
        """
        try:
            current_return = position.unrealized_return

            # 1차 익절: config에서 비율 읽기
            if current_return >= self.config.partial_profit_first_pct and not position.partial_sold:
                sell_quantity = int(position.quantity * self.config.partial_profit_first_ratio)

                if sell_quantity <= 0:
                    self.logger.warning(f"부분 익절 수량 부족: {position.stock_code}")
                    return False

                self.logger.info(
                    f"📊 1차 부분 익절 조건 충족 - {position.stock_code}: "
                    f"수익률 {current_return:.1%}, 수량 {sell_quantity}주 매도 "
                    f"(기준: {self.config.partial_profit_first_pct:.1%}, "
                    f"비율: {self.config.partial_profit_first_ratio:.1%})"
                )

                result = await self.sell(
                    stock_code=position.stock_code,
                    quantity=sell_quantity,
                    order_type="시장가",
                    reason="partial_profit_1"
                )

                if result.get("success"):
                    position.partial_sold = True
                    position.partial_profit_price = position.current_price
                    # sell() 내부에서 이미 position.quantity 차감됨
                    self.logger.info(
                        f"✅ 1차 부분 익절 완료 - {position.stock_code}: "
                        f"{sell_quantity}주 @ {position.current_price:,.0f}원, "
                        f"잔여 {position.quantity}주"
                    )
                    return True
                else:
                    self.logger.error(
                        f"1차 부분 익절 실패: {position.stock_code} - {result.get('message')}",
                        exc_info=True
                    )
                    return False

            # 2차 익절: config에서 비율 읽기
            elif current_return >= self.config.partial_profit_second_pct:
                self.logger.info(
                    f"📊 2차 익절 조건 충족 - {position.stock_code}: "
                    f"수익률 {current_return:.1%}, 잔여 {position.quantity}주 전량 매도 "
                    f"(기준: {self.config.partial_profit_second_pct:.1%})"
                )

                result = await self.sell(
                    stock_code=position.stock_code,
                    quantity=position.quantity,
                    order_type="시장가",
                    reason="take_profit"
                )

                if result.get("success"):
                    self.logger.info(
                        f"✅ 2차 익절 완료 - {position.stock_code}: "
                        f"{position.quantity}주 @ {position.current_price:,.0f}원"
                    )
                    return True
                else:
                    self.logger.error(
                        f"2차 익절 실패: {position.stock_code} - {result.get('message')}",
                        exc_info=True
                    )
                    return False

            return False

        except Exception as e:
            self.logger.error(
                f"부분 익절 체크 실패: {position.stock_code} - {e}",
                exc_info=True
            )
            return False

    def _should_sell(self, position: Position) -> Tuple[bool, str]:
        """매도 조건 확인"""
        try:
            current_return = position.unrealized_return

            # 손절매 조건
            if current_return <= -self.config.stop_loss_pct:
                return True, "stop_loss"

            # 익절매 조건 (부분 익절 미사용 시에만)
            if not position.partial_sold and current_return >= self.config.take_profit_pct:
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
            stock_code = stock_data["stock_code"]
            stock_name = stock_data.get("stock_name", stock_code)
            current_price = stock_data["current_price"]

            # 포지션 크기 계산 (고도화된 알고리즘 사용)
            quantity = self._calculate_position_size(
                stock_code, current_price, stock_data
            )

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
                order_division=self.api.ORDER_DIVISION_LIMIT,  # "00" (지정가)
            )

            if result and result.get("success"):
                # 손절/익절가 계산 (동적 또는 고정)
                stop_loss_price, target_price_value, stop_info = (
                    self._calculate_stop_prices(
                        stock_code, int(current_price), stock_data
                    )
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
                    target_price=target_price_value,
                )

                self.positions[stock_code] = position
                self.daily_trades += 1

                # 매매일지 기록 (Phase 2 예측 메타데이터 포함)
                order_data = result.get("data", {})
                order_id = order_data.get("ODNO", order_data.get("ORD_NO", ""))
                self.journal.log_order(
                    stock_code=stock_code,
                    stock_name=stock_name,
                    side="buy",
                    price=current_price,
                    quantity=quantity,
                    reason="auto_trading",
                    meta={
                        "strategy": "daily_selection",
                        "order_id": order_id,
                        "target_price": position.target_price,
                        "stop_loss": position.stop_loss,
                        # Phase 2 예측 정보 (Phase 4 학습용)
                        "entry_price": stock_data.get("entry_price", current_price),
                        "expected_return": stock_data.get("expected_return", 0),
                        "predicted_probability": stock_data.get("confidence", 0.5),
                        "predicted_class": stock_data.get("predicted_class", 1),
                        "model_name": stock_data.get("model_name", "ensemble"),
                        "price_attractiveness": stock_data.get(
                            "price_attractiveness", 0
                        ),
                    },
                )

                self.logger.info(
                    f"매수 완료: {stock_code} {quantity}주 @ {current_price:,.0f}원"
                )

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
                error_msg = (
                    result.get("message", "알 수 없는 오류") if result else "응답 없음"
                )
                self.logger.error(
                    f"매수 주문 실패: {stock_code} - {error_msg}", exc_info=True
                )
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

            current_price = price_data.get("current_price", position.current_price)
            order_price = int(current_price)

            # 한투 API 매도 주문 실행
            result = self.api.place_order(
                stock_code=stock_code,
                order_type=self.api.ORDER_TYPE_SELL,  # "01"
                quantity=position.quantity,
                price=order_price,
                order_division=self.api.ORDER_DIVISION_LIMIT,  # "00" (지정가)
            )

            if result and result.get("success"):
                # 손익 계산
                if position.avg_price <= 0:
                    self.logger.warning(f"유효하지 않은 평균 매입가: {position.avg_price}")
                    return None
                pnl = (current_price - position.avg_price) * position.quantity
                return_rate = (current_price - position.avg_price) / position.avg_price

                # 매매일지 기록
                order_data = result.get("data", {})
                order_id = order_data.get("ODNO", order_data.get("ORD_NO", ""))
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
                        "hold_days": (
                            datetime.now() - datetime.fromisoformat(position.entry_time)
                        ).days,
                        "entry_price": position.avg_price,
                        "order_id": order_id,
                    },
                )

                # 포지션 제거
                del self.positions[stock_code]
                self.daily_trades += 1

                self.logger.info(
                    f"매도 완료: {stock_code} {position.quantity}주 @ {current_price:,.0f}원 (손익: {pnl:+,.0f}원)"
                )

                # 실시간 피드백 루프에 거래 결과 기록
                self._record_trade_feedback(
                    stock_code=stock_code,
                    stock_name=position.stock_name,
                    entry_price=position.avg_price,
                    exit_price=current_price,
                    entry_time=position.entry_time,
                    pnl=pnl,
                    pnl_pct=return_rate * 100,
                    exit_reason=reason,
                )

                # 텔레그램 알림
                if self.notifier.is_enabled():
                    pnl_emoji = "💰" if pnl > 0 else "📉" if pnl < 0 else "➖"
                    reason_text = {
                        "stop_loss": "손절매",
                        "take_profit": "익절매",
                        "time_based": "시간 기반 매도",
                    }.get(reason, reason)

                    message = f"""{pnl_emoji} *자동 매도 체결*
                    
종목: {position.stock_name} ({stock_code})
수량: {position.quantity:,}주
매도가: {current_price:,.0f}원
매수가: {position.avg_price:,.0f}원

실현손익: {pnl:+,.0f}원
수익률: {return_rate:+.2%}
매도사유: {reason_text}"""

                    priority = (
                        "high" if pnl > 0 else "emergency" if pnl < -50000 else "normal"
                    )
                    self.notifier.send_message(message, priority)

                return True

            else:
                error_msg = (
                    result.get("message", "알 수 없는 오류") if result else "응답 없음"
                )
                self.logger.error(
                    f"매도 주문 실패: {stock_code} - {error_msg}", exc_info=True
                )
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
                    current_price = price_data.get("current_price")
                    if current_price and current_price > 0:
                        # 평가손익 계산
                        unrealized_pnl = (
                            current_price - position.avg_price
                        ) * position.quantity
                        unrealized_return = (
                            current_price - position.avg_price
                        ) / position.avg_price

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

                # P0-5b: 부분 익절 체크 (기존 포지션)
                for stock_code, position in list(self.positions.items()):
                    await self.check_partial_profit(position)
                    await asyncio.sleep(0.5)  # API 호출 간격

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
                            current_price_data = self.api.get_current_price(
                                stock_data["stock_code"]
                            )
                            if current_price_data:
                                stock_data["current_price"] = current_price_data.get(
                                    "current_price"
                                )
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

            self.logger.info(
                f"계좌 잔고 확인 완료: 총자산 {account_balance:,.0f}원, 가용현금 {available_cash:,.0f}원"
            )

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
                runtime = (
                    end_time - self.start_time if self.start_time else timedelta(0)
                )

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
            if not balance or not balance.get("positions"):
                self.logger.info("기존 보유 포지션이 없습니다")
                return

            for stock_code, pos_data in balance["positions"].items():
                if pos_data.get("quantity", 0) > 0:
                    position = Position(
                        stock_code=stock_code,
                        stock_name=pos_data.get("stock_name", stock_code),
                        quantity=pos_data["quantity"],
                        avg_price=pos_data.get("avg_price", 0),
                        current_price=pos_data.get("current_price", 0),
                        entry_time=datetime.now().isoformat(),  # 정확한 매수 시간은 알 수 없음
                        unrealized_pnl=pos_data.get("unrealized_pnl", 0),
                        unrealized_return=pos_data.get("unrealized_return", 0),
                        stop_loss=pos_data.get("avg_price", 0)
                        * (1 - self.config.stop_loss_pct),
                        target_price=pos_data.get("avg_price", 0)
                        * (1 + self.config.take_profit_pct),
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
            "config": asdict(self.config),
        }

    # ========================================
    # Batch 4 기능: 고급 매매 기능
    # ========================================

    def check_circuit_breaker(self) -> Tuple[bool, str]:
        """서킷 브레이커 상태 확인 및 대응 (Batch 4-2)

        Returns:
            Tuple[bool, str]: (거래 가능 여부, 상태 메시지)
        """
        try:
            from core.risk.drawdown.circuit_breaker import CircuitBreaker
            from core.risk.drawdown.drawdown_monitor import DrawdownMonitor

            monitor = DrawdownMonitor()
            breaker = CircuitBreaker()

            # 현재 드로다운 상태 계산 - 계좌 총 자산 조회 필요
            portfolio_value = self._get_account_balance()
            drawdown_status = monitor.update(portfolio_value)

            # 서킷 브레이커 체크
            breaker_status = breaker.check(drawdown_status)

            # CircuitHandler로 대응
            handler = self._get_circuit_handler()
            if handler:
                response = handler.handle_circuit_event(breaker_status)
                self.logger.info(
                    f"서킷브레이커 체크: {response.action}, "
                    f"포지션제한: {response.position_limit:.0%}"
                )
                return breaker_status.can_trade, response.message

            return breaker_status.can_trade, breaker_status.trigger_reason or "정상"

        except ImportError:
            self.logger.debug("서킷브레이커 모듈 없음 (무시)")
            return True, "서킷브레이커 비활성화"
        except Exception as e:
            self.logger.error(f"서킷브레이커 체크 실패: {e}", exc_info=True)
            return True, f"체크 실패: {e}"

    def scan_additional_buy_opportunities(self) -> List[Dict[str, Any]]:
        """추가 매수 기회 스캔 (Batch 4-1)

        보유 중인 포지션 중 추가 매수 조건을 충족하는 종목을 찾습니다.

        Returns:
            List[Dict]: 추가 매수 기회 목록
        """
        opportunities = []

        try:
            detector = self._get_opportunity_detector()
            if detector is None:
                return opportunities

            for stock_code, position in self.positions.items():
                # 포지션 데이터 구성 (detect_additional_buy 인터페이스에 맞춤)
                position_data = {
                    'stock_code': position.stock_code,
                    'stock_name': position.stock_name,
                    'quantity': position.quantity,
                    'avg_price': position.avg_price,
                    'entry_time': position.entry_time
                }

                # 올바른 메서드 호출: detect_additional_buy(p_position, p_current_price, p_rsi)
                opportunity = detector.detect_additional_buy(
                    p_position=position_data,
                    p_current_price=position.current_price,
                    p_rsi=None  # RSI는 별도 조회 필요 시 추가
                )

                if opportunity:
                    opportunities.append({
                        'stock_code': opportunity.stock_code,
                        'stock_name': opportunity.stock_name,
                        'reason': opportunity.reason,
                        'current_price': opportunity.current_price,
                        'recommended_quantity': opportunity.recommended_quantity,
                        'confidence': opportunity.confidence
                    })

            if opportunities:
                self.logger.info(f"추가 매수 기회 발견: {len(opportunities)}개")

            return opportunities

        except Exception as e:
            self.logger.error(f"추가 매수 기회 스캔 실패: {e}", exc_info=True)
            return []

    def generate_daily_summary(self) -> Optional[str]:
        """일일 거래 요약 생성 (Batch 4-3)

        Returns:
            Optional[str]: 텔레그램 형식의 요약 메시지 (실패 시 None)
        """
        try:
            generator = self._get_daily_summary_generator()
            if generator is None:
                return None

            # 요약 보고서 생성
            report = generator.generate_summary()

            # 텔레그램 형식으로 변환
            message = report.to_telegram_message()

            self.logger.info(
                f"일일 요약 생성: 거래 {report.trade_summary.total_trades}건, "
                f"실현손익 {report.trade_summary.total_pnl:+,.0f}원"
            )

            return message

        except Exception as e:
            self.logger.error(f"일일 요약 생성 실패: {e}", exc_info=True)
            return None

    def get_circuit_handler_restrictions(self) -> Dict[str, Any]:
        """현재 서킷 브레이커 제한 정보 조회

        Returns:
            Dict: 현재 적용 중인 거래 제한 정보
        """
        try:
            handler = self._get_circuit_handler()
            if handler:
                return handler.get_current_restrictions()
            return {"active": False, "position_limit": 1.0, "message": "비활성화"}
        except Exception as e:
            self.logger.error(f"제한 정보 조회 실패: {e}", exc_info=True)
            return {"active": False, "error": str(e)}


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
