"""
Real-time data event handlers.

실시간 데이터 이벤트를 처리하고 신호 생성, 시장 분석을 수행합니다.
"""

from typing import Dict, Any, List, Optional
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from dataclasses import dataclass, field
from collections import deque
import statistics
import uuid

from core.utils import get_logger
from core.database import StockRepository
from hantu_common.indicators import RSI, MovingAverage, BollingerBands
from core.database import DatabaseSession
from core.strategy.ensemble.signal_aggregator import SignalAggregator
from core.strategy.ensemble.signal import Signal, SignalType, SignalSource

logger = get_logger(__name__)


@dataclass
class MarketCondition:
    """시장 상황 데이터"""
    timestamp: datetime = field(default_factory=datetime.now)
    bid_ask_spread: float = 0.0
    bid_depth: int = 0
    ask_depth: int = 0
    imbalance_ratio: float = 0.0  # (bid - ask) / (bid + ask)
    pressure: str = "neutral"  # "buy", "sell", "neutral"


@dataclass
class VolumeAnalysis:
    """거래량 분석 결과"""
    current_volume: int = 0
    avg_volume: float = 0.0
    volume_ratio: float = 1.0  # current / avg
    is_surge: bool = False
    surge_threshold: float = 2.0


@dataclass
class VolatilityAnalysis:
    """변동성 분석 결과"""
    current_volatility: float = 0.0
    avg_volatility: float = 0.0
    volatility_ratio: float = 1.0
    is_high: bool = False
    regime: str = "normal"  # "low", "normal", "high", "extreme"


@dataclass
class AbnormalTradingResult:
    """이상 거래 탐지 결과"""
    is_abnormal: bool = False
    reasons: List[str] = field(default_factory=list)
    severity: str = "none"  # "none", "low", "medium", "high"
    stock_code: str = ""


class EventHandler:
    """실시간 이벤트 처리기"""

    # 이상 거래 탐지 임계값
    VOLUME_SURGE_THRESHOLD = 3.0  # 평균 대비 3배
    VOLATILITY_HIGH_THRESHOLD = 2.0  # 평균 대비 2배
    PRICE_SPIKE_THRESHOLD = 0.05  # 5% 급등락
    SPREAD_ABNORMAL_THRESHOLD = 0.02  # 2% 스프레드

    def __init__(self, session=None):
        """초기화

        Args:
            session: 데이터베이스 세션 (기본값: None)
        """
        self.running = False
        if session:
            self.repository = StockRepository(session)
        else:
            db = DatabaseSession()
            self.repository = StockRepository(db.session)

        # 신호 집계기
        self.signal_aggregator = SignalAggregator()

        # 캐시 및 히스토리
        self._price_history: Dict[str, deque] = {}  # stock_code -> prices
        self._volume_history: Dict[str, deque] = {}  # stock_code -> volumes
        self._market_conditions: Dict[str, MarketCondition] = {}
        self._pending_signals: List[Dict] = []

        # 설정
        self._history_size = 100  # 히스토리 보관 개수
        self._min_data_points = 20  # 분석에 필요한 최소 데이터

    async def start(self):
        """이벤트 처리 시작"""
        self.running = True
        logger.info("실시간 이벤트 처리 시작")

    async def stop(self):
        """이벤트 처리 중지"""
        self.running = False
        self._cleanup()
        logger.info("실시간 이벤트 처리 중지")

    async def handle_event(self, data: Dict[str, Any]):
        """
        이벤트 처리

        Args:
            data (Dict[str, Any]): 처리할 이벤트 데이터
        """
        if not self.running:
            return

        try:
            event_type = data.get('type', '').upper()

            if event_type == 'TRADE':
                await self._handle_trade_event(data)
            elif event_type == 'QUOTE':
                await self._handle_quote_event(data)
            elif event_type == 'TICK':
                await self._handle_tick_event(data)
            else:
                logger.warning(f"알 수 없는 이벤트 유형: {event_type}")

        except Exception as e:
            logger.error(f"이벤트 처리 중 오류 발생: {str(e)}", exc_info=True)

    async def _handle_trade_event(self, data: Dict[str, Any]):
        """
        거래 이벤트 처리

        Args:
            data (Dict[str, Any]): 거래 이벤트 데이터
        """
        try:
            stock_code = data.get('symbol', '')
            price = float(data.get('price', 0))
            volume = int(data.get('volume', 0))

            # 가격/거래량 히스토리 업데이트
            self._update_history(stock_code, price, volume)

            # 기술적 지표 업데이트
            await self._update_technical_indicators(data)

            # 거래 신호 생성
            signals = await self._generate_trading_signals(data)

            # 거래 실행
            if signals and signals.get('action') != 'HOLD':
                await self._execute_trades(signals)

        except Exception as e:
            logger.error(f"거래 이벤트 처리 중 오류 발생: {str(e)}", exc_info=True)

    async def _handle_quote_event(self, data: Dict[str, Any]):
        """
        호가 이벤트 처리

        Args:
            data (Dict[str, Any]): 호가 이벤트 데이터
        """
        try:
            # 호가 분석
            analysis = await self._analyze_quote_data(data)

            # 시장 상황 업데이트
            await self._update_market_condition(analysis)

        except Exception as e:
            logger.error(f"호가 이벤트 처리 중 오류 발생: {str(e)}", exc_info=True)

    async def _handle_tick_event(self, data: Dict[str, Any]):
        """
        틱 이벤트 처리

        Args:
            data (Dict[str, Any]): 틱 이벤트 데이터
        """
        try:
            # 거래량 분석
            volume_analysis = await self._analyze_volume(data)

            # 가격 변동성 분석
            volatility_analysis = await self._analyze_volatility(data)

            # 이상 거래 탐지
            abnormal_result = await self._detect_abnormal_trading(
                data, volume_analysis, volatility_analysis
            )

            if abnormal_result.is_abnormal:
                logger.warning(
                    f"이상 거래 감지: {data.get('symbol', 'UNKNOWN')} - "
                    f"심각도: {abnormal_result.severity}, "
                    f"사유: {', '.join(abnormal_result.reasons)}"
                )

        except Exception as e:
            logger.error(f"틱 이벤트 처리 중 오류 발생: {str(e)}", exc_info=True)

    def _update_history(self, stock_code: str, price: float, volume: int):
        """가격/거래량 히스토리 업데이트"""
        if stock_code not in self._price_history:
            self._price_history[stock_code] = deque(maxlen=self._history_size)
            self._volume_history[stock_code] = deque(maxlen=self._history_size)

        self._price_history[stock_code].append(price)
        self._volume_history[stock_code].append(volume)

    async def _update_technical_indicators(self, data: Dict[str, Any]):
        """
        기술적 지표 업데이트

        Args:
            data (Dict[str, Any]): 업데이트할 데이터
        """
        try:
            stock_code = data.get('symbol', '')
            stock = self.repository.get_stock(stock_code)
            if not stock:
                return

            # 가격 데이터 조회
            prices = self.repository.get_stock_prices(
                stock.id,
                start_date=datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            )

            if not prices:
                return

            # RSI 계산
            rsi = RSI(prices).calculate()

            # 이동평균선 계산
            ma = MovingAverage(prices)
            ma5 = ma.calculate(period=5)
            ma20 = ma.calculate(period=20)

            # 볼린저 밴드 계산
            bb = BollingerBands(prices).calculate()

            timestamp = data.get('timestamp', datetime.now())

            # 지표 저장
            self.repository.save_technical_indicator(
                stock_id=stock.id,
                date=timestamp,
                indicator_type='RSI',
                value=float(rsi.iloc[-1]) if len(rsi) > 0 else 50.0
            )

            self.repository.save_technical_indicator(
                stock_id=stock.id,
                date=timestamp,
                indicator_type='MA5',
                value=float(ma5.iloc[-1]) if len(ma5) > 0 else 0.0
            )

            self.repository.save_technical_indicator(
                stock_id=stock.id,
                date=timestamp,
                indicator_type='MA20',
                value=float(ma20.iloc[-1]) if len(ma20) > 0 else 0.0
            )

        except Exception as e:
            logger.error(f"기술적 지표 업데이트 중 오류 발생: {str(e)}", exc_info=True)

    async def _generate_trading_signals(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        매매 신호 생성

        Args:
            data (Dict[str, Any]): 신호 생성에 사용할 데이터

        Returns:
            Dict[str, Any]: 생성된 신호 정보
        """
        try:
            stock_code = data.get('symbol', '')
            price = float(data.get('price', 0))

            # 히스토리 데이터 충분한지 확인
            if stock_code not in self._price_history:
                return {'action': 'HOLD', 'reason': 'Insufficient data'}

            prices = list(self._price_history[stock_code])
            if len(prices) < self._min_data_points:
                return {'action': 'HOLD', 'reason': 'Insufficient history'}

            # 개별 전략 신호 생성
            signals = []

            # 1. 기술적 분석 신호
            ta_signal = self._generate_ta_signal(stock_code, prices, price)
            if ta_signal:
                signals.append(ta_signal)

            # 2. 시장 상황 기반 신호
            market_signal = self._generate_market_signal(stock_code, price)
            if market_signal:
                signals.append(market_signal)

            # 3. 거래량 기반 신호
            volume_signal = self._generate_volume_signal(stock_code)
            if volume_signal:
                signals.append(volume_signal)

            if not signals:
                return {'action': 'HOLD', 'reason': 'No signals generated'}

            # 신호 집계
            final_signal = self.signal_aggregator.aggregate(signals)

            return {
                'action': final_signal.action.name if hasattr(final_signal.action, 'name') else str(final_signal.action),
                'stock_code': stock_code,
                'confidence': final_signal.confidence,
                'strength': final_signal.strength,
                'stop_loss': final_signal.stop_loss,
                'take_profit': final_signal.take_profit,
                'reason': final_signal.reason,
                'sources': [str(s) for s in final_signal.sources],
            }

        except Exception as e:
            logger.error(f"신호 생성 중 오류: {str(e)}", exc_info=True)
            return {'action': 'HOLD', 'reason': f'Error: {str(e)}'}

    def _generate_ta_signal(
        self, stock_code: str, prices: List[float], current_price: float
    ) -> Optional[Signal]:
        """기술적 분석 신호 생성"""
        try:
            if len(prices) < 20:
                return None

            # 이동평균
            ma5 = statistics.mean(prices[-5:])
            ma20 = statistics.mean(prices[-20:])

            # RSI 간이 계산
            gains = []
            losses = []
            for i in range(1, min(15, len(prices))):
                change = prices[-i] - prices[-i-1]
                if change > 0:
                    gains.append(change)
                else:
                    losses.append(abs(change))

            avg_gain = statistics.mean(gains) if gains else 0
            avg_loss = statistics.mean(losses) if losses else 0.001
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))

            # 신호 결정
            signal_type = SignalType.HOLD
            strength = 0.5
            confidence = 0.5
            reason = ""

            # 골든크로스 / 데드크로스
            if ma5 > ma20 and prices[-2] < statistics.mean(prices[-7:-2]):
                signal_type = SignalType.BUY
                strength = 0.7
                confidence = 0.6
                reason = "Golden cross detected"
            elif ma5 < ma20 and prices[-2] > statistics.mean(prices[-7:-2]):
                signal_type = SignalType.SELL
                strength = 0.7
                confidence = 0.6
                reason = "Dead cross detected"

            # RSI 과매수/과매도
            if rsi < 30:
                if signal_type == SignalType.BUY:
                    confidence += 0.1
                else:
                    signal_type = SignalType.BUY
                    strength = 0.6
                    confidence = 0.55
                    reason = "RSI oversold"
            elif rsi > 70:
                if signal_type == SignalType.SELL:
                    confidence += 0.1
                else:
                    signal_type = SignalType.SELL
                    strength = 0.6
                    confidence = 0.55
                    reason = "RSI overbought"

            if signal_type == SignalType.HOLD:
                return None

            # 손절/익절 계산
            volatility = statistics.stdev(prices[-20:]) if len(prices) >= 20 else current_price * 0.02
            stop_loss = current_price - (2 * volatility) if signal_type == SignalType.BUY else current_price + (2 * volatility)
            take_profit = current_price + (3 * volatility) if signal_type == SignalType.BUY else current_price - (3 * volatility)

            return Signal(
                stock_code=stock_code,
                signal_type=signal_type,
                source=SignalSource.TA,
                strength=strength,
                confidence=min(1.0, confidence),
                reason=reason,
                stop_loss=stop_loss,
                take_profit=take_profit,
            )

        except Exception as e:
            logger.error(f"TA 신호 생성 오류: {str(e)}", exc_info=True)
            return None

    def _generate_market_signal(
        self, stock_code: str, current_price: float
    ) -> Optional[Signal]:
        """시장 상황 기반 신호 생성"""
        try:
            condition = self._market_conditions.get(stock_code)
            if not condition:
                return None

            # 호가 불균형 기반 신호
            if abs(condition.imbalance_ratio) < 0.1:
                return None  # 균형 상태

            signal_type = SignalType.HOLD
            strength = 0.5
            confidence = 0.5
            reason = ""

            if condition.imbalance_ratio > 0.3:  # 매수 압력
                signal_type = SignalType.BUY
                strength = min(1.0, 0.5 + condition.imbalance_ratio)
                confidence = 0.55
                reason = f"Strong buy pressure (imbalance: {condition.imbalance_ratio:.2f})"
            elif condition.imbalance_ratio < -0.3:  # 매도 압력
                signal_type = SignalType.SELL
                strength = min(1.0, 0.5 + abs(condition.imbalance_ratio))
                confidence = 0.55
                reason = f"Strong sell pressure (imbalance: {condition.imbalance_ratio:.2f})"
            else:
                return None

            return Signal(
                stock_code=stock_code,
                signal_type=signal_type,
                source=SignalSource.SD,  # Supply/Demand
                strength=strength,
                confidence=confidence,
                reason=reason,
            )

        except Exception as e:
            logger.error(f"시장 신호 생성 오류: {str(e)}", exc_info=True)
            return None

    def _generate_volume_signal(self, stock_code: str) -> Optional[Signal]:
        """거래량 기반 신호 생성"""
        try:
            if stock_code not in self._volume_history:
                return None

            volumes = list(self._volume_history[stock_code])
            if len(volumes) < self._min_data_points:
                return None

            current_volume = volumes[-1]
            avg_volume = statistics.mean(volumes[:-1])
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0

            # 거래량 급증 시에만 신호 생성
            if volume_ratio < 2.0:
                return None

            # 가격 추세와 결합
            prices = list(self._price_history.get(stock_code, []))
            if len(prices) < 5:
                return None

            price_change = (prices[-1] - prices[-5]) / prices[-5] if prices[-5] > 0 else 0

            signal_type = SignalType.HOLD
            strength = min(1.0, 0.5 + (volume_ratio - 2.0) * 0.1)
            confidence = 0.5
            reason = ""

            if price_change > 0.01 and volume_ratio > 2.0:
                signal_type = SignalType.BUY
                confidence = min(0.7, 0.5 + volume_ratio * 0.05)
                reason = f"Volume surge with price increase (vol ratio: {volume_ratio:.1f}x)"
            elif price_change < -0.01 and volume_ratio > 2.0:
                signal_type = SignalType.SELL
                confidence = min(0.7, 0.5 + volume_ratio * 0.05)
                reason = f"Volume surge with price decrease (vol ratio: {volume_ratio:.1f}x)"
            else:
                return None

            return Signal(
                stock_code=stock_code,
                signal_type=signal_type,
                source=SignalSource.SD,
                strength=strength,
                confidence=confidence,
                reason=reason,
            )

        except Exception as e:
            logger.error(f"거래량 신호 생성 오류: {str(e)}", exc_info=True)
            return None

    async def _execute_trades(self, signals: Dict[str, Any]):
        """
        거래 실행

        Args:
            signals: 실행할 신호 정보
        """
        try:
            action = signals.get('action', 'HOLD')
            if action == 'HOLD':
                return

            # 신호를 대기열에 추가 (실제 실행은 TradeEngine에서 처리)
            self._pending_signals.append({
                'signal_id': str(uuid.uuid4()),
                'timestamp': datetime.now(),
                **signals
            })

            logger.info(
                f"거래 신호 생성: {signals.get('stock_code')} - "
                f"{action} (신뢰도: {signals.get('confidence', 0):.2f})"
            )

        except Exception as e:
            logger.error(f"거래 실행 중 오류: {str(e)}", exc_info=True)

    async def _analyze_quote_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        호가 데이터 분석

        Args:
            data (Dict[str, Any]): 분석에 사용할 데이터

        Returns:
            Dict[str, Any]: 분석 결과
        """
        try:
            stock_code = data.get('symbol', '')

            # 호가 데이터 추출
            bid_prices = data.get('bid_prices', [])
            ask_prices = data.get('ask_prices', [])
            bid_volumes = data.get('bid_volumes', [])
            ask_volumes = data.get('ask_volumes', [])

            # 기본값
            result = {
                'stock_code': stock_code,
                'timestamp': datetime.now(),
                'spread': 0.0,
                'spread_pct': 0.0,
                'bid_depth': 0,
                'ask_depth': 0,
                'imbalance_ratio': 0.0,
                'pressure': 'neutral',
            }

            if not bid_prices or not ask_prices:
                return result

            # 스프레드 계산
            best_bid = bid_prices[0] if bid_prices else 0
            best_ask = ask_prices[0] if ask_prices else 0

            if best_bid > 0 and best_ask > 0:
                result['spread'] = best_ask - best_bid
                result['spread_pct'] = result['spread'] / best_bid

            # 호가 깊이 계산
            result['bid_depth'] = sum(bid_volumes) if bid_volumes else 0
            result['ask_depth'] = sum(ask_volumes) if ask_volumes else 0

            # 호가 불균형 비율
            total_depth = result['bid_depth'] + result['ask_depth']
            if total_depth > 0:
                result['imbalance_ratio'] = (
                    result['bid_depth'] - result['ask_depth']
                ) / total_depth

            # 매수/매도 압력 판단
            if result['imbalance_ratio'] > 0.2:
                result['pressure'] = 'buy'
            elif result['imbalance_ratio'] < -0.2:
                result['pressure'] = 'sell'
            else:
                result['pressure'] = 'neutral'

            return result

        except Exception as e:
            logger.error(f"호가 분석 중 오류: {str(e)}", exc_info=True)
            return {}

    async def _update_market_condition(self, analysis: Dict[str, Any]):
        """
        시장 상황 업데이트

        Args:
            analysis (Dict[str, Any]): 분석 결과
        """
        try:
            stock_code = analysis.get('stock_code', '')
            if not stock_code:
                return

            self._market_conditions[stock_code] = MarketCondition(
                timestamp=analysis.get('timestamp', datetime.now()),
                bid_ask_spread=analysis.get('spread_pct', 0.0),
                bid_depth=analysis.get('bid_depth', 0),
                ask_depth=analysis.get('ask_depth', 0),
                imbalance_ratio=analysis.get('imbalance_ratio', 0.0),
                pressure=analysis.get('pressure', 'neutral'),
            )

        except Exception as e:
            logger.error(f"시장 상황 업데이트 중 오류: {str(e)}", exc_info=True)

    async def _analyze_volume(self, data: Dict[str, Any]) -> VolumeAnalysis:
        """
        거래량 분석

        Args:
            data: 틱 데이터

        Returns:
            VolumeAnalysis: 분석 결과
        """
        try:
            stock_code = data.get('symbol', '')
            current_volume = int(data.get('volume', 0))

            result = VolumeAnalysis(current_volume=current_volume)

            if stock_code not in self._volume_history:
                return result

            volumes = list(self._volume_history[stock_code])
            if len(volumes) < 5:
                return result

            result.avg_volume = statistics.mean(volumes)
            result.volume_ratio = (
                current_volume / result.avg_volume
                if result.avg_volume > 0 else 1.0
            )
            result.is_surge = result.volume_ratio >= result.surge_threshold

            return result

        except Exception as e:
            logger.error(f"거래량 분석 중 오류: {str(e)}", exc_info=True)
            return VolumeAnalysis()

    async def _analyze_volatility(self, data: Dict[str, Any]) -> VolatilityAnalysis:
        """
        가격 변동성 분석

        Args:
            data: 틱 데이터

        Returns:
            VolatilityAnalysis: 분석 결과
        """
        try:
            stock_code = data.get('symbol', '')

            result = VolatilityAnalysis()

            if stock_code not in self._price_history:
                return result

            prices = list(self._price_history[stock_code])
            if len(prices) < 10:
                return result

            # 최근 변동성 (최근 10개)
            recent_returns = [
                (prices[i] - prices[i-1]) / prices[i-1]
                for i in range(-9, 0) if prices[i-1] > 0
            ]

            if len(recent_returns) < 5:
                return result

            result.current_volatility = statistics.stdev(recent_returns) if len(recent_returns) > 1 else 0

            # 전체 평균 변동성
            if len(prices) >= 30:
                all_returns = [
                    (prices[i] - prices[i-1]) / prices[i-1]
                    for i in range(1, len(prices)) if prices[i-1] > 0
                ]
                result.avg_volatility = statistics.stdev(all_returns) if len(all_returns) > 1 else result.current_volatility
            else:
                result.avg_volatility = result.current_volatility

            # 변동성 비율
            result.volatility_ratio = (
                result.current_volatility / result.avg_volatility
                if result.avg_volatility > 0 else 1.0
            )

            # 변동성 구간 판단
            if result.volatility_ratio < 0.5:
                result.regime = "low"
            elif result.volatility_ratio < 1.5:
                result.regime = "normal"
            elif result.volatility_ratio < 2.5:
                result.regime = "high"
                result.is_high = True
            else:
                result.regime = "extreme"
                result.is_high = True

            return result

        except Exception as e:
            logger.error(f"변동성 분석 중 오류: {str(e)}", exc_info=True)
            return VolatilityAnalysis()

    async def _detect_abnormal_trading(
        self,
        data: Dict[str, Any],
        volume_analysis: VolumeAnalysis,
        volatility_analysis: VolatilityAnalysis
    ) -> AbnormalTradingResult:
        """
        비정상 거래 탐지

        Args:
            data (Dict[str, Any]): 탐지에 사용할 데이터
            volume_analysis: 거래량 분석 결과
            volatility_analysis: 가격 변동성 분석 결과

        Returns:
            AbnormalTradingResult: 탐지 결과
        """
        try:
            stock_code = data.get('symbol', '')
            result = AbnormalTradingResult(stock_code=stock_code)
            reasons = []
            severity_score = 0

            # 1. 거래량 급증 체크
            if volume_analysis.volume_ratio >= self.VOLUME_SURGE_THRESHOLD:
                reasons.append(
                    f"Volume surge: {volume_analysis.volume_ratio:.1f}x average"
                )
                severity_score += 2

            # 2. 변동성 급등 체크
            if volatility_analysis.volatility_ratio >= self.VOLATILITY_HIGH_THRESHOLD:
                reasons.append(
                    f"High volatility: {volatility_analysis.volatility_ratio:.1f}x average"
                )
                severity_score += 2

            # 3. 가격 급등락 체크
            if stock_code in self._price_history:
                prices = list(self._price_history[stock_code])
                if len(prices) >= 2:
                    price_change = abs(prices[-1] - prices[-2]) / prices[-2] if prices[-2] > 0 else 0
                    if price_change >= self.PRICE_SPIKE_THRESHOLD:
                        reasons.append(f"Price spike: {price_change:.1%}")
                        severity_score += 3

            # 4. 스프레드 이상 체크
            condition = self._market_conditions.get(stock_code)
            if condition and condition.bid_ask_spread >= self.SPREAD_ABNORMAL_THRESHOLD:
                reasons.append(f"Abnormal spread: {condition.bid_ask_spread:.2%}")
                severity_score += 1

            # 5. 호가 극단적 불균형 체크
            if condition and abs(condition.imbalance_ratio) >= 0.7:
                reasons.append(
                    f"Extreme order imbalance: {condition.imbalance_ratio:.2f}"
                )
                severity_score += 2

            # 결과 결정
            if reasons:
                result.is_abnormal = True
                result.reasons = reasons

                if severity_score >= 6:
                    result.severity = "high"
                elif severity_score >= 3:
                    result.severity = "medium"
                else:
                    result.severity = "low"

            return result

        except Exception as e:
            logger.error(f"이상 거래 탐지 중 오류: {str(e)}", exc_info=True)
            return AbnormalTradingResult(stock_code=data.get('symbol', ''))

    def get_pending_signals(self) -> List[Dict]:
        """대기 중인 신호 조회"""
        return self._pending_signals.copy()

    def clear_pending_signals(self):
        """대기 신호 초기화"""
        self._pending_signals.clear()

    def get_market_condition(self, stock_code: str) -> Optional[MarketCondition]:
        """특정 종목 시장 상황 조회"""
        return self._market_conditions.get(stock_code)

    def _cleanup(self):
        """정리 작업"""
        try:
            # 캐시 정리
            self._price_history.clear()
            self._volume_history.clear()
            self._market_conditions.clear()
            self._pending_signals.clear()

            logger.debug("정리 작업 수행 완료")

        except Exception as e:
            logger.error(f"정리 작업 중 오류 발생: {str(e)}", exc_info=True)

    def __del__(self):
        """소멸자"""
        self._cleanup()
