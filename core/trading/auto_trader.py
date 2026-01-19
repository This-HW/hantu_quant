import logging
from datetime import datetime
from typing import Dict, List, Optional
import pandas as pd

from core.api.kis_api import KISAPI
from hantu_backtest.strategies.base import BacktestStrategy
from core.trading.sell_engine import SellEngine, SellSignal
from core.trading.trade_journal import TradeJournal
from core.config.trading_config import (
    MAX_STOCKS,
    MAX_TRADES_PER_DAY, MAX_TRADES_PER_STOCK,
    MARKET_START_TIME, MARKET_END_TIME,
    MAX_RELATIVE_SPREAD, UPTICK_RATIO_BUY_MIN
)

logger = logging.getLogger(__name__)

class AutoTrader:
    """매수-매도 통합 자동 매매 트레이더"""
    
    def __init__(self, api: KISAPI, strategy: BacktestStrategy, sell_config: Optional[Dict] = None):
        self.api = api
        self.strategy = strategy
        self.positions: Dict[str, Dict] = {}  # 보유 포지션
        self.buy_count = 0  # 당일 매수 횟수
        self.sell_count = 0  # 당일 매도 횟수
        
        # 매도 엔진 초기화
        self.sell_engine = SellEngine(sell_config)
        self.journal = TradeJournal()
        
        logger.info("매수-매도 통합 자동 매매 시스템 초기화 완료")
        
    def reset_daily_counts(self):
        """일일 거래 횟수 초기화"""
        self.buy_count = 0
        self.sell_count = 0
        
    def is_market_open(self) -> bool:
        """장 운영 시간 확인"""
        now = datetime.now().strftime('%H:%M')
        return MARKET_START_TIME <= now <= MARKET_END_TIME
        
    async def start(self, target_codes: List[str]):
        """자동 매매 시작"""
        logger.info("자동 매매를 시작합니다.")
        
        try:
            # 보유 종목 정보 초기화
            balance = self.api.get_balance()
            if not balance:
                logger.error("잔고 조회 실패")
                return False
                
            for code, quantity in balance.items():
                self.positions[code] = {
                    'quantity': quantity,
                    'entry_price': 0  # TODO: 평균 매수가 조회 필요
                }
                
            # 실시간 데이터 수신 시작
            ws_success = await self.api.start_real_time(target_codes)
            if not ws_success:
                logger.error("WebSocket 연결 실패")
                return False
                
            logger.info(f"{len(target_codes)}개 종목에 대한 실시간 데이터 수신 시작")
            return True
            
        except Exception as e:
            logger.error(f"자동 매매 시작 중 오류 발생: {str(e)}", exc_info=True)
            return False
        
    async def stop(self):
        """자동 매매 종료"""
        logger.info("자동 매매를 종료합니다.")
        try:
            # API 연결 종료
            await self.api.close()
            logger.info("API 연결이 종료되었습니다.")
            return True
        except Exception as e:
            logger.error(f"자동 매매 종료 중 오류 발생: {str(e)}", exc_info=True)
            return False
        
    def update_price_data(self, code: str, price_data: pd.DataFrame):
        """가격 데이터 업데이트 및 매매 신호 처리"""
        if not self.is_market_open():
            return
            
        # 매수 로직
        if (len(self.positions) < MAX_STOCKS and 
            self.buy_count < MAX_TRADES_PER_DAY and
            code not in self.positions):
            # 보조 데이터 수집(분봉/호가/체결)
            ob, _ticks = None, None
            try:
                ob = self.api.get_orderbook(code)
                tdf = self.api.get_tick_conclusions(code)
                # 간단한 업틱 비율 계산 예시
                if tdf is not None and not tdf.empty:
                    # 가정: 체결가 컬럼명은 문서 기준으로 변환 필요. 여기서는 존재 가정.
                    prices = pd.to_numeric(tdf.get('stck_prpr', pd.Series(dtype=float)), errors='coerce').dropna()
                    deltas = prices.diff().fillna(0)
                    uptick_ratio = float((deltas > 0).sum()) / max(1, len(deltas))
                else:
                    uptick_ratio = None
            except Exception:
                uptick_ratio = None

            # 간단한 진입 가드: 스프레드/업틱 기준
            spread_ok = True
            if ob:
                try:
                    b = float(next((v for k, v in ob.items() if k.lower().startswith('bidp1')), 0))
                    a = float(next((v for k, v in ob.items() if k.lower().startswith('askp1')), 0))
                    if a > 0 and b > 0:
                        rel_spread = (a - b) / ((a + b) / 2)
                        spread_ok = rel_spread <= MAX_RELATIVE_SPREAD
                except Exception:
                    spread_ok = True
            uptick_ok = (uptick_ratio is None) or (uptick_ratio >= UPTICK_RATIO_BUY_MIN)

            if spread_ok and uptick_ok and self.strategy.should_buy(price_data):
                # 시그널 기록
                self.journal.log_signal(
                    stock_code=code,
                    stock_name=None,
                    side="buy",
                    reason="strategy_should_buy",
                    meta={"orderbook": bool(ob), "uptick_ratio": uptick_ratio},
                )
                self._execute_buy(code, price_data)
                
        # 매도 로직
        elif code in self.positions and self.sell_count < MAX_TRADES_PER_STOCK:
            if self.strategy.should_sell(price_data, self.positions[code]):
                # 시그널 기록
                self.journal.log_signal(
                    stock_code=code,
                    stock_name=None,
                    side="sell",
                    reason="strategy_should_sell",
                    meta={"reason": "n/a"},
                )
                self._execute_sell(code)
                
    def _execute_buy(self, code: str, price_data: pd.DataFrame):
        """매수 실행"""
        try:
            current_price = price_data['Close'].iloc[-1]
            balance = self.api.get_balance()
            # API 표준화된 키 사용 (deposit)
            available_cash = float(balance.get('deposit', 0)) if isinstance(balance, dict) else 0.0
            
            quantity = self.strategy.calculate_position_size(current_price, available_cash)
            if quantity <= 0:
                return
                
            result = self.api.market_buy(code, quantity)
            if result:
                logger.info(f"매수 주문 성공: {code} {quantity}주")
                self.positions[code] = {
                    'quantity': quantity,
                    'entry_price': current_price
                }
                self.buy_count += 1
                # 주문 기록
                self.journal.log_order(
                    stock_code=code,
                    stock_name=None,
                    side="buy",
                    price=current_price,
                    quantity=quantity,
                    reason="market_buy",
                )
                
        except Exception as e:
            logger.error(f"매수 실행 중 오류 발생: {e}", exc_info=True)
            
    def _execute_sell(self, code: str):
        """매도 실행"""
        try:
            position = self.positions[code]
            result = self.api.market_sell(code, position['quantity'])
            
            if result:
                logger.info(f"매도 주문 성공: {code} {position['quantity']}주")
                # 주문 기록
                self.journal.log_order(
                    stock_code=code,
                    stock_name=None,
                    side="sell",
                    price=position.get('entry_price', 0.0),  # 실제 체결가를 API에서 가져올 수 있으면 교체
                    quantity=position['quantity'],
                    reason="market_sell",
                )
                del self.positions[code]
                self.sell_count += 1
                
        except Exception as e:
            logger.error(f"매도 실행 중 오류 발생: {e}", exc_info=True)
            
    def get_trading_status(self) -> Dict:
        """거래 상태 조회"""
        return {
            'positions': self.positions,
            'buy_count': self.buy_count,
            'sell_count': self.sell_count,
            'sell_engine_positions': self.sell_engine.get_positions_summary()
        }
    
    def sync_positions_to_sell_engine(self):
        """현재 포지션을 매도 엔진에 동기화"""
        try:
            logger.info("포지션을 매도 엔진에 동기화 중...")
            
            for code, position in self.positions.items():
                # 종목 정보 조회
                stock_info = self.api.get_stock_info(code)
                stock_name = stock_info.get('stock_name', code) if stock_info else code
                
                # 현재가 조회
                current_price = self.api.get_current_price(code)
                if not current_price:
                    logger.warning(f"현재가 조회 실패: {code}")
                    continue
                
                # 매도 엔진에 포지션 추가
                entry_price = position.get('entry_price', current_price)
                quantity = position.get('quantity', 0)
                entry_date = position.get('entry_date', datetime.now().strftime('%Y-%m-%d'))
                
                success = self.sell_engine.add_position(
                    stock_code=code,
                    stock_name=stock_name,
                    entry_price=entry_price,
                    quantity=quantity,
                    entry_date=entry_date
                )
                
                if success:
                    logger.info(f"매도 엔진 포지션 추가: {code} ({stock_name})")
                else:
                    logger.error(f"매도 엔진 포지션 추가 실패: {code}", exc_info=True)
            
            logger.info("포지션 동기화 완료")
            
        except Exception as e:
            logger.error(f"포지션 동기화 오류: {e}", exc_info=True)
    
    def check_and_execute_sell_signals(self, target_codes: List[str]):
        """매도 신호 확인 및 실행"""
        try:
            for code in target_codes:
                # 포지션이 있는 종목만 확인
                if code not in self.positions:
                    continue
                
                # 현재가 및 지표 조회
                current_price = self.api.get_current_price(code)
                if not current_price:
                    continue
                
                # 기술적 지표 조회 (필요시 구현)
                indicators = self._get_technical_indicators(code)
                
                # 종목 데이터 구성
                stock_data = {
                    'stock_code': code,
                    'current_price': current_price,
                    'indicators': indicators,
                    'timestamp': datetime.now().isoformat()
                }
                
                # 매도 신호 확인
                sell_signals = self.sell_engine.check_sell_signals(stock_data)
                
                if sell_signals:
                    # 모든 신호를 저널에 기록
                    for sig in sell_signals:
                        self.journal.log_signal(
                            stock_code=code,
                            stock_name=None,
                            side="sell",
                            reason=f"sell_engine:{sig.signal_type.value}",
                            meta={
                                "strength": sig.signal_strength,
                                "confidence": sig.confidence,
                                "current_return": sig.current_return,
                            },
                        )
                    # 가장 강한 신호 선택
                    primary_signal = sell_signals[0]
                    
                    logger.info(f"매도 신호 감지: {code} - {primary_signal.signal_type.value}")
                    logger.info(f"신호 강도: {primary_signal.signal_strength:.2f}")
                    logger.info(f"매도 사유: {primary_signal.reason}")
                    
                    # 매도 실행
                    if self._should_execute_sell(primary_signal):
                        self._execute_intelligent_sell(primary_signal)
                    
        except Exception as e:
            logger.error(f"매도 신호 확인 오류: {e}", exc_info=True)
    
    def _get_technical_indicators(self, stock_code: str) -> Dict[str, float]:
        """기술적 지표 조회 (기본 구현)"""
        try:
            # TODO: 실제 기술적 지표 계산 로직 구현
            # 현재는 기본값으로 대체
            return {
                'rsi': 50.0,
                'macd': 0.0,
                'macd_signal': 0.0,
                'macd_histogram': 0.0,
                'bollinger_upper': 0.0,
                'bollinger_lower': 0.0,
                'bollinger_position': 0.5
            }
        except Exception as e:
            logger.error(f"기술적 지표 조회 오류: {e}", exc_info=True)
            return {}
    
    def _should_execute_sell(self, sell_signal: SellSignal) -> bool:
        """매도 실행 여부 결정"""
        try:
            # 신호 강도 기준
            if sell_signal.signal_strength < 0.3:
                logger.debug(f"신호 강도 부족으로 매도 미실행: {sell_signal.signal_strength:.2f}")
                return False
            
            # 거래 횟수 제한 확인
            if self.sell_count >= MAX_TRADES_PER_DAY:
                logger.warning("일일 매도 횟수 한계 도달")
                return False
            
            # 장 운영 시간 확인
            if not self.is_market_open():
                logger.debug("장 운영 시간 외 매도 신호 무시")
                return False
            
            # 스톱로스나 트레일링 스톱은 즉시 실행
            urgent_signals = ['stop_loss', 'trailing_stop']
            if sell_signal.signal_type.value in urgent_signals:
                return True
            
            # 기타 신호는 신뢰도 기준 추가 확인
            if sell_signal.confidence < 0.6:
                logger.debug(f"신뢰도 부족으로 매도 미실행: {sell_signal.confidence:.2f}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"매도 실행 여부 판단 오류: {e}", exc_info=True)
            return False
    
    def _execute_intelligent_sell(self, sell_signal: SellSignal):
        """지능형 매도 실행"""
        try:
            stock_code = sell_signal.stock_code
            
            # 매도 비율 결정
            sell_ratio = self._determine_sell_ratio(sell_signal)
            
            logger.info(f"지능형 매도 실행: {stock_code}")
            logger.info(f"매도 비율: {sell_ratio*100:.0f}%")
            logger.info(f"매도 사유: {sell_signal.reason}")
            
            # 매도 엔진으로 주문 실행
            success = self.sell_engine.execute_sell_order(sell_signal, sell_ratio)
            
            if success:
                # AutoTrader 포지션도 업데이트
                if sell_ratio >= 1.0:
                    # 전량 매도
                    if stock_code in self.positions:
                        del self.positions[stock_code]
                else:
                    # 부분 매도
                    if stock_code in self.positions:
                        current_quantity = self.positions[stock_code]['quantity']
                        new_quantity = int(current_quantity * (1 - sell_ratio))
                        self.positions[stock_code]['quantity'] = new_quantity
                
                self.sell_count += 1
                logger.info(f"매도 완료: {stock_code} - {sell_signal.signal_type.value}")
                
                # 텔레그램 알림 발송 (선택적)
                self._send_sell_notification(sell_signal, sell_ratio)
            else:
                logger.error(f"매도 실행 실패: {stock_code}", exc_info=True)
            
        except Exception as e:
            logger.error(f"지능형 매도 실행 오류: {e}", exc_info=True)
    
    def _determine_sell_ratio(self, sell_signal: SellSignal) -> float:
        """매도 비율 결정"""
        try:
            signal_type = sell_signal.signal_type.value
            
            # 손실 제한 신호들은 전량 매도
            if signal_type in ['stop_loss', 'trailing_stop']:
                return 1.0
            
            # 수익 실현 신호는 부분 매도
            if signal_type == 'take_profit':
                return 0.5  # 50% 부분 매도
            
            # 기술적 신호들은 신호 강도에 따라 조절
            if signal_type in ['rsi_overbought', 'bollinger_reversal', 'macd_bearish']:
                base_ratio = 0.3
                signal_multiplier = sell_signal.signal_strength
                return min(1.0, base_ratio + signal_multiplier * 0.5)
            
            # 시간 기반 신호는 25% 부분 매도
            if signal_type == 'time_based':
                return 0.25
            
            # 기본값
            return 0.5
            
        except Exception as e:
            logger.error(f"매도 비율 결정 오류: {e}", exc_info=True)
            return 0.5
    
    def _send_sell_notification(self, sell_signal: SellSignal, sell_ratio: float):
        """매도 알림 발송"""
        try:
            from core.utils.telegram_notifier import get_telegram_notifier
            
            message = f"💰 매도 완료\n"
            message += f"종목: {sell_signal.stock_name} ({sell_signal.stock_code})\n"
            message += f"매도사유: {sell_signal.reason}\n"
            message += f"매도비율: {sell_ratio*100:.0f}%\n"
            message += f"수익률: {sell_signal.current_return*100:.1f}%\n"
            message += f"신호강도: {sell_signal.signal_strength:.2f}\n"
            message += f"시간: {datetime.now().strftime('%H:%M:%S')}"
            
            notifier = get_telegram_notifier()
            notifier.send_message(message)
            
        except Exception as e:
            logger.debug(f"매도 알림 발송 실패: {e}")  # 에러지만 치명적이지 않음 