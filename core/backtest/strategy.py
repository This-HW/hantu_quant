"""
백테스트 전략 인터페이스 모듈

전략 기본 클래스와 샘플 전략을 제공합니다.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum
import pandas as pd
import numpy as np


class SignalType(Enum):
    """시그널 유형"""
    BUY = 1
    SELL = -1
    HOLD = 0


@dataclass
class Signal:
    """거래 시그널"""
    stock_code: str
    signal_type: SignalType
    price: float
    date: str
    confidence: float = 1.0          # 신뢰도 (0~1)
    strength: float = 1.0            # 시그널 강도 (포지션 크기 조절용)
    reason: str = ""                 # 시그널 발생 이유
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class BaseStrategy(ABC):
    """백테스트 전략 기본 클래스"""

    def __init__(self, name: str = "BaseStrategy", params: Dict[str, Any] = None):
        self.name = name
        self.params = params or {}
        self._indicators: Dict[str, pd.DataFrame] = {}

    @abstractmethod
    def generate_signals(
        self,
        data: pd.DataFrame,
        current_positions: Dict[str, Any]
    ) -> List[Signal]:
        """
        시그널 생성 (하위 클래스에서 구현)

        Args:
            data: OHLCV 데이터 (컬럼: open, high, low, close, volume)
            current_positions: 현재 보유 포지션 {stock_code: Position}

        Returns:
            Signal 리스트
        """
        pass

    def initialize(self, data: Dict[str, pd.DataFrame]):
        """전략 초기화 (선택적 구현)"""
        pass

    def on_trade(self, trade_info: Dict[str, Any]):
        """거래 실행 시 콜백 (선택적 구현)"""
        pass

    def calculate_position_size(
        self,
        signal: Signal,
        capital: float,
        current_price: float
    ) -> int:
        """
        포지션 크기 계산 (선택적 오버라이드)

        Returns:
            주문 수량
        """
        # 기본: 신호 강도에 따른 자본금 비율
        position_value = capital * 0.05 * signal.strength
        quantity = int(position_value / current_price)
        return max(1, quantity)


class MACrossStrategy(BaseStrategy):
    """이동평균 크로스 전략"""

    def __init__(
        self,
        short_period: int = 5,
        long_period: int = 20,
        name: str = "MA Cross"
    ):
        super().__init__(name, {
            'short_period': short_period,
            'long_period': long_period
        })
        self.short_period = short_period
        self.long_period = long_period

    def generate_signals(
        self,
        data: pd.DataFrame,
        current_positions: Dict[str, Any]
    ) -> List[Signal]:
        signals = []

        if len(data) < self.long_period + 1:
            return signals

        # 이동평균 계산
        short_ma = data['close'].rolling(window=self.short_period).mean()
        long_ma = data['close'].rolling(window=self.long_period).mean()

        current_date = str(data.index[-1].date()) if hasattr(data.index[-1], 'date') else str(data.index[-1])
        current_price = data['close'].iloc[-1]
        stock_code = data.attrs.get('stock_code', 'UNKNOWN')

        # 골든 크로스 (매수)
        if (short_ma.iloc[-2] <= long_ma.iloc[-2] and
            short_ma.iloc[-1] > long_ma.iloc[-1]):
            if stock_code not in current_positions:
                signals.append(Signal(
                    stock_code=stock_code,
                    signal_type=SignalType.BUY,
                    price=current_price,
                    date=current_date,
                    confidence=0.8,
                    reason="Golden Cross"
                ))

        # 데드 크로스 (매도)
        elif (short_ma.iloc[-2] >= long_ma.iloc[-2] and
              short_ma.iloc[-1] < long_ma.iloc[-1]):
            if stock_code in current_positions:
                signals.append(Signal(
                    stock_code=stock_code,
                    signal_type=SignalType.SELL,
                    price=current_price,
                    date=current_date,
                    confidence=0.8,
                    reason="Dead Cross"
                ))

        return signals


class RSIMeanReversionStrategy(BaseStrategy):
    """RSI 평균 회귀 전략"""

    def __init__(
        self,
        rsi_period: int = 14,
        oversold: float = 30,
        overbought: float = 70,
        name: str = "RSI Mean Reversion"
    ):
        super().__init__(name, {
            'rsi_period': rsi_period,
            'oversold': oversold,
            'overbought': overbought
        })
        self.rsi_period = rsi_period
        self.oversold = oversold
        self.overbought = overbought

    def _calculate_rsi(self, prices: pd.Series) -> pd.Series:
        """RSI 계산"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()

        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def generate_signals(
        self,
        data: pd.DataFrame,
        current_positions: Dict[str, Any]
    ) -> List[Signal]:
        signals = []

        if len(data) < self.rsi_period + 1:
            return signals

        rsi = self._calculate_rsi(data['close'])

        current_date = str(data.index[-1].date()) if hasattr(data.index[-1], 'date') else str(data.index[-1])
        current_price = data['close'].iloc[-1]
        current_rsi = rsi.iloc[-1]
        prev_rsi = rsi.iloc[-2]
        stock_code = data.attrs.get('stock_code', 'UNKNOWN')

        # 과매도 탈출 (매수)
        if prev_rsi <= self.oversold and current_rsi > self.oversold:
            if stock_code not in current_positions:
                signals.append(Signal(
                    stock_code=stock_code,
                    signal_type=SignalType.BUY,
                    price=current_price,
                    date=current_date,
                    confidence=min(1.0, (self.oversold - prev_rsi) / 10 + 0.5),
                    strength=(self.oversold - min(prev_rsi, current_rsi)) / self.oversold,
                    reason=f"RSI oversold exit ({current_rsi:.1f})"
                ))

        # 과매수 탈출 (매도)
        elif prev_rsi >= self.overbought and current_rsi < self.overbought:
            if stock_code in current_positions:
                signals.append(Signal(
                    stock_code=stock_code,
                    signal_type=SignalType.SELL,
                    price=current_price,
                    date=current_date,
                    confidence=min(1.0, (prev_rsi - self.overbought) / 10 + 0.5),
                    reason=f"RSI overbought exit ({current_rsi:.1f})"
                ))

        return signals


class BollingerBreakoutStrategy(BaseStrategy):
    """볼린저 밴드 돌파 전략"""

    def __init__(
        self,
        period: int = 20,
        std_dev: float = 2.0,
        name: str = "Bollinger Breakout"
    ):
        super().__init__(name, {
            'period': period,
            'std_dev': std_dev
        })
        self.period = period
        self.std_dev = std_dev

    def _calculate_bands(self, prices: pd.Series) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """볼린저 밴드 계산"""
        middle = prices.rolling(window=self.period).mean()
        std = prices.rolling(window=self.period).std()
        upper = middle + (std * self.std_dev)
        lower = middle - (std * self.std_dev)
        return upper, middle, lower

    def generate_signals(
        self,
        data: pd.DataFrame,
        current_positions: Dict[str, Any]
    ) -> List[Signal]:
        signals = []

        if len(data) < self.period + 1:
            return signals

        upper, middle, lower = self._calculate_bands(data['close'])

        current_date = str(data.index[-1].date()) if hasattr(data.index[-1], 'date') else str(data.index[-1])
        current_price = data['close'].iloc[-1]
        prev_price = data['close'].iloc[-2]
        stock_code = data.attrs.get('stock_code', 'UNKNOWN')

        # 하단 밴드 터치 후 반등 (매수)
        if prev_price <= lower.iloc[-2] and current_price > lower.iloc[-1]:
            if stock_code not in current_positions:
                signals.append(Signal(
                    stock_code=stock_code,
                    signal_type=SignalType.BUY,
                    price=current_price,
                    date=current_date,
                    confidence=0.7,
                    stop_loss=lower.iloc[-1] * 0.98,
                    take_profit=middle.iloc[-1],
                    reason="Lower band bounce"
                ))

        # 상단 밴드 터치 (매도)
        elif current_price >= upper.iloc[-1]:
            if stock_code in current_positions:
                signals.append(Signal(
                    stock_code=stock_code,
                    signal_type=SignalType.SELL,
                    price=current_price,
                    date=current_date,
                    confidence=0.7,
                    reason="Upper band touch"
                ))

        return signals


class CombinedStrategy(BaseStrategy):
    """복합 전략 (여러 전략 조합)"""

    def __init__(
        self,
        strategies: List[BaseStrategy],
        min_agreement: int = 2,
        name: str = "Combined Strategy"
    ):
        """
        Args:
            strategies: 조합할 전략 리스트
            min_agreement: 최소 동의 전략 수
        """
        super().__init__(name, {
            'strategies': [s.name for s in strategies],
            'min_agreement': min_agreement
        })
        self.strategies = strategies
        self.min_agreement = min_agreement

    def generate_signals(
        self,
        data: pd.DataFrame,
        current_positions: Dict[str, Any]
    ) -> List[Signal]:
        # 각 전략에서 시그널 수집
        all_signals: Dict[str, List[Signal]] = {}

        for strategy in self.strategies:
            signals = strategy.generate_signals(data, current_positions)
            for signal in signals:
                key = (signal.stock_code, signal.signal_type.value)
                if key not in all_signals:
                    all_signals[key] = []
                all_signals[key].append(signal)

        # 최소 동의 수 이상인 시그널만 반환
        final_signals = []
        for key, signals in all_signals.items():
            if len(signals) >= self.min_agreement:
                # 신뢰도 평균으로 합성
                avg_confidence = np.mean([s.confidence for s in signals])
                combined_reason = " + ".join([s.reason for s in signals])

                final_signal = Signal(
                    stock_code=signals[0].stock_code,
                    signal_type=signals[0].signal_type,
                    price=signals[0].price,
                    date=signals[0].date,
                    confidence=avg_confidence,
                    strength=len(signals) / len(self.strategies),
                    reason=f"Combined ({len(signals)}/{len(self.strategies)}): {combined_reason}"
                )
                final_signals.append(final_signal)

        return final_signals


class LSTMPredictionStrategy(BaseStrategy):
    """LSTM 예측 기반 전략 (기존 모델 활용)"""

    def __init__(
        self,
        model_path: str = None,
        buy_threshold: float = 0.6,
        sell_threshold: float = 0.4,
        name: str = "LSTM Prediction"
    ):
        super().__init__(name, {
            'model_path': model_path,
            'buy_threshold': buy_threshold,
            'sell_threshold': sell_threshold
        })
        self.model_path = model_path
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold
        self.model = None

    def initialize(self, data: Dict[str, pd.DataFrame]):
        """모델 로드"""
        if self.model_path:
            try:
                # 기존 LSTM 모델 로드 시도
                from core.learning.models.prediction_engine import PredictionEngine
                self.model = PredictionEngine()
            except ImportError:
                pass

    def generate_signals(
        self,
        data: pd.DataFrame,
        current_positions: Dict[str, Any]
    ) -> List[Signal]:
        signals = []

        # 모델이 없으면 빈 시그널 반환
        if self.model is None:
            return signals

        current_date = str(data.index[-1].date()) if hasattr(data.index[-1], 'date') else str(data.index[-1])
        current_price = data['close'].iloc[-1]
        stock_code = data.attrs.get('stock_code', 'UNKNOWN')

        try:
            # 예측 수행
            prediction = self.model.predict(data)
            prob = prediction.get('probability', 0.5)

            if prob >= self.buy_threshold and stock_code not in current_positions:
                signals.append(Signal(
                    stock_code=stock_code,
                    signal_type=SignalType.BUY,
                    price=current_price,
                    date=current_date,
                    confidence=prob,
                    strength=(prob - 0.5) * 2,
                    reason=f"LSTM prediction: {prob:.2%}"
                ))
            elif prob <= self.sell_threshold and stock_code in current_positions:
                signals.append(Signal(
                    stock_code=stock_code,
                    signal_type=SignalType.SELL,
                    price=current_price,
                    date=current_date,
                    confidence=1 - prob,
                    reason=f"LSTM prediction: {prob:.2%}"
                ))
        except Exception:
            pass

        return signals
