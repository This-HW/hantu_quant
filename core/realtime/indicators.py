"""
실시간 기술적 지표 계산 모듈

스트리밍 데이터에 대한 효율적인 지표 계산을 제공합니다.
"""

import numpy as np
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum

from core.utils import get_logger

logger = get_logger(__name__)


class IndicatorType(Enum):
    """지표 유형"""
    RSI = "rsi"
    MA = "ma"
    EMA = "ema"
    MACD = "macd"
    BOLLINGER = "bollinger"
    STOCHASTIC = "stochastic"
    ATR = "atr"
    VWAP = "vwap"


@dataclass
class IndicatorValue:
    """지표 값"""
    indicator_type: IndicatorType
    value: float
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IndicatorConfig:
    """지표 설정"""
    rsi_period: int = 14
    ma_short_period: int = 5
    ma_medium_period: int = 20
    ma_long_period: int = 60
    ema_period: int = 12
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    bollinger_period: int = 20
    bollinger_std: float = 2.0
    stochastic_k: int = 14
    stochastic_d: int = 3
    atr_period: int = 14
    min_data_points: int = 30


class RealtimeIndicatorCalculator:
    """
    실시간 기술적 지표 계산기

    스트리밍 데이터에 대해 효율적으로 지표를 계산합니다.
    증분 계산을 통해 매번 전체 데이터를 재계산하지 않습니다.
    """

    def __init__(self, config: Optional[IndicatorConfig] = None, history_size: int = 200):
        """
        초기화

        Args:
            config: 지표 설정
            history_size: 히스토리 보관 크기
        """
        self.config = config or IndicatorConfig()
        self._history_size = history_size

        # 종목별 가격 히스토리 (OHLCV)
        self._price_history: Dict[str, deque] = {}  # stock_code -> [(open, high, low, close, volume), ...]
        self._close_history: Dict[str, deque] = {}  # stock_code -> [close, ...]
        self._volume_history: Dict[str, deque] = {}  # stock_code -> [volume, ...]

        # 캐시된 계산 결과
        self._rsi_cache: Dict[str, Dict[str, float]] = {}  # stock_code -> {avg_gain, avg_loss, prev_close}
        self._ema_cache: Dict[str, Dict[int, float]] = {}  # stock_code -> {period: ema_value}
        self._vwap_cache: Dict[str, Dict[str, float]] = {}  # stock_code -> {cumulative_tp_vol, cumulative_vol}

        # 계산된 지표 저장
        self._indicators: Dict[str, Dict[IndicatorType, IndicatorValue]] = {}

    def update(self, stock_code: str, price_data: Dict[str, Any]) -> Dict[IndicatorType, IndicatorValue]:
        """
        가격 데이터 업데이트 및 지표 계산

        Args:
            stock_code: 종목 코드
            price_data: 가격 데이터 {'open', 'high', 'low', 'close', 'volume'}

        Returns:
            Dict[IndicatorType, IndicatorValue]: 계산된 지표들
        """
        try:
            # 가격 데이터 추출
            open_price = float(price_data.get('open', price_data.get('price', 0)))
            high_price = float(price_data.get('high', price_data.get('price', 0)))
            low_price = float(price_data.get('low', price_data.get('price', 0)))
            close_price = float(price_data.get('close', price_data.get('price', 0)))
            volume = int(price_data.get('volume', 0))

            # 히스토리 초기화
            if stock_code not in self._price_history:
                self._price_history[stock_code] = deque(maxlen=self._history_size)
                self._close_history[stock_code] = deque(maxlen=self._history_size)
                self._volume_history[stock_code] = deque(maxlen=self._history_size)
                self._indicators[stock_code] = {}

            # 히스토리 업데이트
            self._price_history[stock_code].append((open_price, high_price, low_price, close_price, volume))
            self._close_history[stock_code].append(close_price)
            self._volume_history[stock_code].append(volume)

            # 지표 계산
            indicators = {}

            closes = list(self._close_history[stock_code])

            # RSI 계산
            rsi_value = self._calculate_rsi(stock_code, closes)
            if rsi_value is not None:
                indicators[IndicatorType.RSI] = IndicatorValue(
                    indicator_type=IndicatorType.RSI,
                    value=rsi_value,
                    metadata={'period': self.config.rsi_period}
                )

            # 이동평균 계산
            ma_values = self._calculate_moving_averages(closes)
            if ma_values:
                indicators[IndicatorType.MA] = IndicatorValue(
                    indicator_type=IndicatorType.MA,
                    value=ma_values.get('ma_short', 0),
                    metadata=ma_values
                )

            # EMA 계산
            ema_value = self._calculate_ema(stock_code, close_price)
            if ema_value is not None:
                indicators[IndicatorType.EMA] = IndicatorValue(
                    indicator_type=IndicatorType.EMA,
                    value=ema_value,
                    metadata={'period': self.config.ema_period}
                )

            # MACD 계산
            macd_result = self._calculate_macd(stock_code, close_price)
            if macd_result:
                indicators[IndicatorType.MACD] = IndicatorValue(
                    indicator_type=IndicatorType.MACD,
                    value=macd_result.get('macd', 0),
                    metadata=macd_result
                )

            # 볼린저 밴드 계산
            bollinger = self._calculate_bollinger_bands(closes)
            if bollinger:
                indicators[IndicatorType.BOLLINGER] = IndicatorValue(
                    indicator_type=IndicatorType.BOLLINGER,
                    value=close_price,  # 현재가
                    metadata=bollinger
                )

            # 스토캐스틱 계산
            stochastic = self._calculate_stochastic(stock_code)
            if stochastic:
                indicators[IndicatorType.STOCHASTIC] = IndicatorValue(
                    indicator_type=IndicatorType.STOCHASTIC,
                    value=stochastic.get('k', 50),
                    metadata=stochastic
                )

            # ATR 계산
            atr_value = self._calculate_atr(stock_code)
            if atr_value is not None:
                indicators[IndicatorType.ATR] = IndicatorValue(
                    indicator_type=IndicatorType.ATR,
                    value=atr_value,
                    metadata={'period': self.config.atr_period}
                )

            # VWAP 계산
            vwap_value = self._calculate_vwap(stock_code, close_price, volume)
            if vwap_value is not None:
                indicators[IndicatorType.VWAP] = IndicatorValue(
                    indicator_type=IndicatorType.VWAP,
                    value=vwap_value,
                    metadata={'price': close_price}
                )

            # 캐시 업데이트
            self._indicators[stock_code] = indicators

            return indicators

        except Exception as e:
            logger.error(f"지표 계산 중 오류: {stock_code} - {str(e)}", exc_info=True)
            return {}

    def _calculate_rsi(self, stock_code: str, closes: List[float]) -> Optional[float]:
        """
        RSI 증분 계산

        첫 번째 계산 후에는 이전 평균 gain/loss를 사용하여 효율적으로 계산
        """
        period = self.config.rsi_period

        if len(closes) < period + 1:
            return None

        if stock_code not in self._rsi_cache:
            # 초기 RSI 계산
            gains = []
            losses = []
            for i in range(1, period + 1):
                change = closes[-period - 1 + i] - closes[-period - 1 + i - 1]
                if change > 0:
                    gains.append(change)
                    losses.append(0)
                else:
                    gains.append(0)
                    losses.append(abs(change))

            avg_gain = sum(gains) / period
            avg_loss = sum(losses) / period

            self._rsi_cache[stock_code] = {
                'avg_gain': avg_gain,
                'avg_loss': avg_loss,
                'prev_close': closes[-1]
            }
        else:
            # 증분 RSI 계산 (Wilder's smoothing)
            cache = self._rsi_cache[stock_code]
            change = closes[-1] - closes[-2]

            current_gain = change if change > 0 else 0
            current_loss = abs(change) if change < 0 else 0

            avg_gain = (cache['avg_gain'] * (period - 1) + current_gain) / period
            avg_loss = (cache['avg_loss'] * (period - 1) + current_loss) / period

            self._rsi_cache[stock_code] = {
                'avg_gain': avg_gain,
                'avg_loss': avg_loss,
                'prev_close': closes[-1]
            }

        cache = self._rsi_cache[stock_code]

        # 변화 없음 (avg_gain과 avg_loss 모두 0) -> 중립 50
        if cache['avg_gain'] == 0 and cache['avg_loss'] == 0:
            return 50.0

        # 손실 없음 -> 100 (강한 상승)
        if cache['avg_loss'] == 0:
            return 100.0

        rs = cache['avg_gain'] / cache['avg_loss']
        rsi = 100 - (100 / (1 + rs))

        return round(rsi, 2)

    def _calculate_moving_averages(self, closes: List[float]) -> Optional[Dict[str, float]]:
        """이동평균 계산"""
        result = {}

        if len(closes) >= self.config.ma_short_period:
            result['ma_short'] = round(sum(closes[-self.config.ma_short_period:]) / self.config.ma_short_period, 2)

        if len(closes) >= self.config.ma_medium_period:
            result['ma_medium'] = round(sum(closes[-self.config.ma_medium_period:]) / self.config.ma_medium_period, 2)

        if len(closes) >= self.config.ma_long_period:
            result['ma_long'] = round(sum(closes[-self.config.ma_long_period:]) / self.config.ma_long_period, 2)

        return result if result else None

    def _calculate_ema(self, stock_code: str, close_price: float) -> Optional[float]:
        """
        EMA 증분 계산
        """
        period = self.config.ema_period
        multiplier = 2 / (period + 1)

        if stock_code not in self._ema_cache:
            self._ema_cache[stock_code] = {}

        if period not in self._ema_cache[stock_code]:
            # 초기값 - SMA 사용
            closes = list(self._close_history[stock_code])
            if len(closes) < period:
                return None
            self._ema_cache[stock_code][period] = sum(closes[-period:]) / period

        # EMA 업데이트
        prev_ema = self._ema_cache[stock_code][period]
        new_ema = (close_price - prev_ema) * multiplier + prev_ema
        self._ema_cache[stock_code][period] = new_ema

        return round(new_ema, 2)

    def _calculate_macd(self, stock_code: str, close_price: float) -> Optional[Dict[str, float]]:
        """
        MACD 계산
        """
        if stock_code not in self._ema_cache:
            self._ema_cache[stock_code] = {}

        # 12일 EMA
        fast_period = self.config.macd_fast
        slow_period = self.config.macd_slow
        signal_period = self.config.macd_signal

        closes = list(self._close_history[stock_code])

        if len(closes) < slow_period:
            return None

        # Fast EMA
        fast_mult = 2 / (fast_period + 1)
        if f'ema_{fast_period}' not in self._ema_cache[stock_code]:
            self._ema_cache[stock_code][f'ema_{fast_period}'] = sum(closes[-fast_period:]) / fast_period
        fast_ema = self._ema_cache[stock_code][f'ema_{fast_period}']
        fast_ema = (close_price - fast_ema) * fast_mult + fast_ema
        self._ema_cache[stock_code][f'ema_{fast_period}'] = fast_ema

        # Slow EMA
        slow_mult = 2 / (slow_period + 1)
        if f'ema_{slow_period}' not in self._ema_cache[stock_code]:
            self._ema_cache[stock_code][f'ema_{slow_period}'] = sum(closes[-slow_period:]) / slow_period
        slow_ema = self._ema_cache[stock_code][f'ema_{slow_period}']
        slow_ema = (close_price - slow_ema) * slow_mult + slow_ema
        self._ema_cache[stock_code][f'ema_{slow_period}'] = slow_ema

        # MACD Line
        macd_line = fast_ema - slow_ema

        # Signal Line
        signal_mult = 2 / (signal_period + 1)
        if 'macd_signal' not in self._ema_cache[stock_code]:
            self._ema_cache[stock_code]['macd_signal'] = macd_line
        signal_line = self._ema_cache[stock_code]['macd_signal']
        signal_line = (macd_line - signal_line) * signal_mult + signal_line
        self._ema_cache[stock_code]['macd_signal'] = signal_line

        # Histogram
        histogram = macd_line - signal_line

        return {
            'macd': round(macd_line, 4),
            'signal': round(signal_line, 4),
            'histogram': round(histogram, 4),
        }

    def _calculate_bollinger_bands(self, closes: List[float]) -> Optional[Dict[str, float]]:
        """볼린저 밴드 계산"""
        period = self.config.bollinger_period
        std_dev = self.config.bollinger_std

        if len(closes) < period:
            return None

        recent = closes[-period:]
        sma = sum(recent) / period
        variance = sum((x - sma) ** 2 for x in recent) / period
        std = variance ** 0.5

        upper = sma + std_dev * std
        lower = sma - std_dev * std

        # %B 계산 (현재 가격의 밴드 내 위치)
        current = closes[-1]
        percent_b = (current - lower) / (upper - lower) if (upper - lower) > 0 else 0.5

        return {
            'upper': round(upper, 2),
            'middle': round(sma, 2),
            'lower': round(lower, 2),
            'percent_b': round(percent_b, 4),
            'bandwidth': round((upper - lower) / sma, 4) if sma > 0 else 0,
        }

    def _calculate_stochastic(self, stock_code: str) -> Optional[Dict[str, float]]:
        """스토캐스틱 계산"""
        k_period = self.config.stochastic_k
        d_period = self.config.stochastic_d

        prices = list(self._price_history[stock_code])

        if len(prices) < k_period:
            return None

        recent = prices[-k_period:]
        highest_high = max(p[1] for p in recent)  # high
        lowest_low = min(p[2] for p in recent)   # low
        current_close = prices[-1][3]             # close

        if highest_high == lowest_low:
            k = 50.0
        else:
            k = ((current_close - lowest_low) / (highest_high - lowest_low)) * 100
            # K 값을 0~100 범위로 클램프
            k = max(0.0, min(100.0, k))

        # D는 K의 이동평균 (간단히 최근 값들 평균 사용)
        if 'stochastic_k_history' not in self._ema_cache.get(stock_code, {}):
            if stock_code not in self._ema_cache:
                self._ema_cache[stock_code] = {}
            self._ema_cache[stock_code]['stochastic_k_history'] = deque(maxlen=d_period)

        self._ema_cache[stock_code]['stochastic_k_history'].append(k)
        k_history = list(self._ema_cache[stock_code]['stochastic_k_history'])
        d = sum(k_history) / len(k_history)

        return {
            'k': round(k, 2),
            'd': round(d, 2),
        }

    def _calculate_atr(self, stock_code: str) -> Optional[float]:
        """ATR (Average True Range) 계산"""
        period = self.config.atr_period
        prices = list(self._price_history[stock_code])

        if len(prices) < period + 1:
            return None

        tr_values = []
        for i in range(-period, 0):
            high = prices[i][1]
            low = prices[i][2]
            prev_close = prices[i - 1][3]

            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            tr_values.append(tr)

        atr = sum(tr_values) / period
        return round(atr, 2)

    def _calculate_vwap(self, stock_code: str, close_price: float, volume: int) -> Optional[float]:
        """VWAP (Volume Weighted Average Price) 계산"""
        if stock_code not in self._vwap_cache:
            self._vwap_cache[stock_code] = {
                'cumulative_tp_vol': 0.0,
                'cumulative_vol': 0,
            }

        # Typical Price
        prices = list(self._price_history[stock_code])
        if not prices:
            return None

        latest = prices[-1]
        typical_price = (latest[1] + latest[2] + latest[3]) / 3  # (H + L + C) / 3

        # 누적 업데이트
        self._vwap_cache[stock_code]['cumulative_tp_vol'] += typical_price * volume
        self._vwap_cache[stock_code]['cumulative_vol'] += volume

        cumulative_vol = self._vwap_cache[stock_code]['cumulative_vol']
        if cumulative_vol == 0:
            return None

        vwap = self._vwap_cache[stock_code]['cumulative_tp_vol'] / cumulative_vol
        return round(vwap, 2)

    def get_indicator(self, stock_code: str, indicator_type: IndicatorType) -> Optional[IndicatorValue]:
        """
        특정 지표 조회

        Args:
            stock_code: 종목 코드
            indicator_type: 지표 유형

        Returns:
            Optional[IndicatorValue]: 지표 값 또는 None
        """
        indicators = self._indicators.get(stock_code, {})
        return indicators.get(indicator_type)

    def get_all_indicators(self, stock_code: str) -> Dict[IndicatorType, IndicatorValue]:
        """
        모든 지표 조회

        Args:
            stock_code: 종목 코드

        Returns:
            Dict[IndicatorType, IndicatorValue]: 모든 지표
        """
        return self._indicators.get(stock_code, {}).copy()

    def get_signal_summary(self, stock_code: str) -> Dict[str, Any]:
        """
        지표 기반 신호 요약

        Args:
            stock_code: 종목 코드

        Returns:
            Dict[str, Any]: 신호 요약 정보
        """
        indicators = self._indicators.get(stock_code, {})

        if not indicators:
            return {'signal': 'NEUTRAL', 'strength': 0, 'reasons': []}

        bullish_signals = []
        bearish_signals = []

        # RSI 분석
        rsi = indicators.get(IndicatorType.RSI)
        if rsi:
            if rsi.value < 30:
                bullish_signals.append(f"RSI 과매도 ({rsi.value:.1f})")
            elif rsi.value > 70:
                bearish_signals.append(f"RSI 과매수 ({rsi.value:.1f})")

        # MA 분석
        ma = indicators.get(IndicatorType.MA)
        if ma and ma.metadata:
            ma_short = ma.metadata.get('ma_short', 0)
            ma_medium = ma.metadata.get('ma_medium', 0)
            if ma_short and ma_medium:
                if ma_short > ma_medium:
                    bullish_signals.append("단기MA > 중기MA")
                else:
                    bearish_signals.append("단기MA < 중기MA")

        # MACD 분석
        macd = indicators.get(IndicatorType.MACD)
        if macd and macd.metadata:
            histogram = macd.metadata.get('histogram', 0)
            if histogram > 0:
                bullish_signals.append(f"MACD 양수 ({histogram:.4f})")
            else:
                bearish_signals.append(f"MACD 음수 ({histogram:.4f})")

        # 볼린저 밴드 분석
        bollinger = indicators.get(IndicatorType.BOLLINGER)
        if bollinger and bollinger.metadata:
            percent_b = bollinger.metadata.get('percent_b', 0.5)
            if percent_b < 0.2:
                bullish_signals.append("볼린저 하단 접근")
            elif percent_b > 0.8:
                bearish_signals.append("볼린저 상단 접근")

        # 스토캐스틱 분석
        stochastic = indicators.get(IndicatorType.STOCHASTIC)
        if stochastic and stochastic.metadata:
            k = stochastic.metadata.get('k', 50)
            d = stochastic.metadata.get('d', 50)
            if k < 20 and k > d:
                bullish_signals.append(f"스토캐스틱 골든크로스 ({k:.1f})")
            elif k > 80 and k < d:
                bearish_signals.append(f"스토캐스틱 데드크로스 ({k:.1f})")

        # 최종 신호 결정
        bullish_count = len(bullish_signals)
        bearish_count = len(bearish_signals)

        if bullish_count > bearish_count + 1:
            signal = 'BULLISH'
            strength = min(1.0, bullish_count * 0.25)
            reasons = bullish_signals
        elif bearish_count > bullish_count + 1:
            signal = 'BEARISH'
            strength = min(1.0, bearish_count * 0.25)
            reasons = bearish_signals
        else:
            signal = 'NEUTRAL'
            strength = 0.0
            reasons = bullish_signals + bearish_signals

        return {
            'signal': signal,
            'strength': round(strength, 2),
            'bullish_count': bullish_count,
            'bearish_count': bearish_count,
            'reasons': reasons,
        }

    def reset_vwap(self, stock_code: str):
        """
        VWAP 리셋 (새 거래일 시작 시 호출)

        Args:
            stock_code: 종목 코드
        """
        if stock_code in self._vwap_cache:
            self._vwap_cache[stock_code] = {
                'cumulative_tp_vol': 0.0,
                'cumulative_vol': 0,
            }

    def clear(self, stock_code: Optional[str] = None):
        """
        캐시 및 히스토리 클리어

        Args:
            stock_code: 종목 코드 (None이면 모두 클리어)
        """
        if stock_code:
            self._price_history.pop(stock_code, None)
            self._close_history.pop(stock_code, None)
            self._volume_history.pop(stock_code, None)
            self._rsi_cache.pop(stock_code, None)
            self._ema_cache.pop(stock_code, None)
            self._vwap_cache.pop(stock_code, None)
            self._indicators.pop(stock_code, None)
        else:
            self._price_history.clear()
            self._close_history.clear()
            self._volume_history.clear()
            self._rsi_cache.clear()
            self._ema_cache.clear()
            self._vwap_cache.clear()
            self._indicators.clear()
