"""
기술적 분석 점수 계산 모듈

다중 기술적 지표를 분석하여 -100 ~ +100 점수로 변환합니다.
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional
from dataclasses import dataclass

from .signal import Signal, SignalType, SignalSource


@dataclass
class TAScores:
    """기술적 분석 점수 결과"""
    # 추세 지표 (40%)
    ma_cross: float = 0.0
    macd: float = 0.0
    adx: float = 0.0

    # 모멘텀 지표 (30%)
    rsi: float = 0.0
    stochastic: float = 0.0
    cci: float = 0.0

    # 변동성 지표 (15%)
    bollinger: float = 0.0
    atr_position: float = 0.0

    # 거래량 지표 (15%)
    volume: float = 0.0
    obv: float = 0.0

    @property
    def weighted_total(self) -> float:
        """가중 종합 점수"""
        trend = (self.ma_cross + self.macd + self.adx) / 3 * 0.40
        momentum = (self.rsi + self.stochastic + self.cci) / 3 * 0.30
        volatility = (self.bollinger + self.atr_position) / 2 * 0.15
        volume_score = (self.volume + self.obv) / 2 * 0.15

        return trend + momentum + volatility + volume_score

    def to_dict(self) -> Dict[str, float]:
        return {
            'ma_cross': self.ma_cross,
            'macd': self.macd,
            'adx': self.adx,
            'rsi': self.rsi,
            'stochastic': self.stochastic,
            'cci': self.cci,
            'bollinger': self.bollinger,
            'atr_position': self.atr_position,
            'volume': self.volume,
            'obv': self.obv,
            'weighted_total': self.weighted_total,
        }


class TechnicalAnalysisScorer:
    """
    기술적 분석 점수 계산기

    각 지표를 -100 ~ +100 점수로 정규화하여
    종합적인 기술적 분석 신호를 생성합니다.
    """

    def __init__(self,
                 ma_short: int = 5,
                 ma_long: int = 20,
                 rsi_period: int = 14,
                 macd_fast: int = 12,
                 macd_slow: int = 26,
                 macd_signal: int = 9,
                 bb_period: int = 20,
                 bb_std: float = 2.0):
        """
        Args:
            ma_short: 단기 이동평균 기간
            ma_long: 장기 이동평균 기간
            rsi_period: RSI 기간
            macd_fast: MACD 빠른 기간
            macd_slow: MACD 느린 기간
            macd_signal: MACD 시그널 기간
            bb_period: 볼린저밴드 기간
            bb_std: 볼린저밴드 표준편차 배수
        """
        self.ma_short = ma_short
        self.ma_long = ma_long
        self.rsi_period = rsi_period
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal
        self.bb_period = bb_period
        self.bb_std = bb_std

    def calculate_scores(self, data: pd.DataFrame) -> TAScores:
        """
        전체 기술적 분석 점수 계산

        Args:
            data: OHLCV DataFrame (columns: open, high, low, close, volume)

        Returns:
            TAScores: 각 지표별 점수
        """
        if len(data) < max(self.ma_long, self.bb_period, 26) + 10:
            return TAScores()

        scores = TAScores()

        # 추세 지표
        scores.ma_cross = self._calculate_ma_cross_score(data)
        scores.macd = self._calculate_macd_score(data)
        scores.adx = self._calculate_adx_score(data)

        # 모멘텀 지표
        scores.rsi = self._calculate_rsi_score(data)
        scores.stochastic = self._calculate_stochastic_score(data)
        scores.cci = self._calculate_cci_score(data)

        # 변동성 지표
        scores.bollinger = self._calculate_bollinger_score(data)
        scores.atr_position = self._calculate_atr_score(data)

        # 거래량 지표
        scores.volume = self._calculate_volume_score(data)
        scores.obv = self._calculate_obv_score(data)

        return scores

    def generate_signal(self, data: pd.DataFrame, stock_code: str) -> Signal:
        """
        기술적 분석 기반 신호 생성

        점수 해석:
        - +60 이상: 강한 매수
        - +30 ~ +60: 약한 매수
        - -30 ~ +30: 중립
        - -60 ~ -30: 약한 매도
        - -60 이하: 강한 매도
        """
        scores = self.calculate_scores(data)
        total_score = scores.weighted_total

        current_price = data['close'].iloc[-1]

        if total_score >= 60:
            return Signal(
                signal_type=SignalType.BUY,
                source=SignalSource.TA,
                stock_code=stock_code,
                strength=2.0,
                confidence=min(1.0, total_score / 100),
                price=current_price,
                reason=f"TA Strong Buy (score: {total_score:.1f})",
                metadata={'scores': scores.to_dict()}
            )
        elif total_score >= 30:
            return Signal(
                signal_type=SignalType.BUY,
                source=SignalSource.TA,
                stock_code=stock_code,
                strength=1.0,
                confidence=total_score / 100,
                price=current_price,
                reason=f"TA Buy (score: {total_score:.1f})",
                metadata={'scores': scores.to_dict()}
            )
        elif total_score <= -60:
            return Signal(
                signal_type=SignalType.SELL,
                source=SignalSource.TA,
                stock_code=stock_code,
                strength=2.0,
                confidence=min(1.0, abs(total_score) / 100),
                price=current_price,
                reason=f"TA Strong Sell (score: {total_score:.1f})",
                metadata={'scores': scores.to_dict()}
            )
        elif total_score <= -30:
            return Signal(
                signal_type=SignalType.SELL,
                source=SignalSource.TA,
                stock_code=stock_code,
                strength=1.0,
                confidence=abs(total_score) / 100,
                price=current_price,
                reason=f"TA Sell (score: {total_score:.1f})",
                metadata={'scores': scores.to_dict()}
            )
        else:
            return Signal(
                signal_type=SignalType.HOLD,
                source=SignalSource.TA,
                stock_code=stock_code,
                strength=0.0,
                confidence=0.5,
                price=current_price,
                reason=f"TA Neutral (score: {total_score:.1f})",
                metadata={'scores': scores.to_dict()}
            )

    def _calculate_ma_cross_score(self, data: pd.DataFrame) -> float:
        """
        이동평균 크로스 점수 (-100 ~ +100)

        골든크로스: +50 ~ +100
        데드크로스: -50 ~ -100
        위치에 따른 추가 점수
        """
        close = data['close']
        ma_short = close.rolling(self.ma_short).mean()
        ma_long = close.rolling(self.ma_long).mean()

        current_price = close.iloc[-1]
        current_short = ma_short.iloc[-1]
        current_long = ma_long.iloc[-1]
        prev_short = ma_short.iloc[-2]
        prev_long = ma_long.iloc[-2]

        score = 0.0

        # 크로스 감지
        if prev_short <= prev_long and current_short > current_long:
            score += 50  # 골든크로스
        elif prev_short >= prev_long and current_short < current_long:
            score -= 50  # 데드크로스

        # 현재 위치에 따른 점수
        if current_price > current_short > current_long:
            score += 30  # 강한 상승 추세
        elif current_price > current_short:
            score += 15
        elif current_price < current_short < current_long:
            score -= 30  # 강한 하락 추세
        elif current_price < current_short:
            score -= 15

        # MA 이격도
        gap_pct = (current_short - current_long) / current_long * 100
        score += np.clip(gap_pct * 5, -20, 20)

        return np.clip(score, -100, 100)

    def _calculate_macd_score(self, data: pd.DataFrame) -> float:
        """
        MACD 점수 (-100 ~ +100)

        MACD 히스토그램 기반 점수화
        """
        close = data['close']

        ema_fast = close.ewm(span=self.macd_fast, adjust=False).mean()
        ema_slow = close.ewm(span=self.macd_slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=self.macd_signal, adjust=False).mean()
        histogram = macd_line - signal_line

        current_hist = histogram.iloc[-1]
        prev_hist = histogram.iloc[-2]
        current_macd = macd_line.iloc[-1]
        current_signal = signal_line.iloc[-1]

        score = 0.0

        # MACD 크로스
        if macd_line.iloc[-2] <= signal_line.iloc[-2] and current_macd > current_signal:
            score += 40  # 매수 크로스
        elif macd_line.iloc[-2] >= signal_line.iloc[-2] and current_macd < current_signal:
            score -= 40  # 매도 크로스

        # 히스토그램 방향 및 크기
        if current_hist > 0:
            if current_hist > prev_hist:
                score += 30  # 상승 가속
            else:
                score += 15  # 상승 감속
        else:
            if current_hist < prev_hist:
                score -= 30  # 하락 가속
            else:
                score -= 15  # 하락 감속

        # 제로라인 위치
        if current_macd > 0:
            score += 15
        else:
            score -= 15

        return np.clip(score, -100, 100)

    def _calculate_rsi_score(self, data: pd.DataFrame) -> float:
        """
        RSI 점수 (-100 ~ +100)

        과매수/과매도 및 다이버전스 분석
        """
        close = data['close']
        delta = close.diff()

        gain = delta.where(delta > 0, 0).rolling(self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(self.rsi_period).mean()

        rs = gain / loss.replace(0, np.inf)
        rsi = 100 - (100 / (1 + rs))

        current_rsi = rsi.iloc[-1]
        prev_rsi = rsi.iloc[-2]

        score = 0.0

        # 기본 RSI 점수
        if current_rsi < 30:
            score = 50 + (30 - current_rsi) * 1.67  # 50 ~ 100
        elif current_rsi > 70:
            score = -50 - (current_rsi - 70) * 1.67  # -50 ~ -100
        else:
            score = (50 - current_rsi) * 1.25  # -25 ~ +25

        # 반전 신호 가점
        if prev_rsi < 30 and current_rsi > 30:
            score += 20  # 과매도 탈출
        elif prev_rsi > 70 and current_rsi < 70:
            score -= 20  # 과매수 탈출

        # 다이버전스 체크
        divergence = self._check_divergence(close, rsi)
        if divergence == 'bullish':
            score += 30
        elif divergence == 'bearish':
            score -= 30

        return np.clip(score, -100, 100)

    def _calculate_stochastic_score(self, data: pd.DataFrame) -> float:
        """
        스토캐스틱 점수 (-100 ~ +100)
        """
        high = data['high']
        low = data['low']
        close = data['close']

        lowest_low = low.rolling(14).min()
        highest_high = high.rolling(14).max()

        k = 100 * (close - lowest_low) / (highest_high - lowest_low + 1e-10)
        d = k.rolling(3).mean()

        current_k = k.iloc[-1]
        current_d = d.iloc[-1]
        prev_k = k.iloc[-2]
        prev_d = d.iloc[-2]

        score = 0.0

        # 과매수/과매도
        if current_k < 20:
            score += 40 + (20 - current_k) * 2
        elif current_k > 80:
            score -= 40 - (current_k - 80) * 2

        # %K, %D 크로스
        if prev_k <= prev_d and current_k > current_d and current_k < 30:
            score += 30  # 저점 골든크로스
        elif prev_k >= prev_d and current_k < current_d and current_k > 70:
            score -= 30  # 고점 데드크로스

        return np.clip(score, -100, 100)

    def _calculate_cci_score(self, data: pd.DataFrame) -> float:
        """
        CCI 점수 (-100 ~ +100)
        """
        tp = (data['high'] + data['low'] + data['close']) / 3
        sma = tp.rolling(20).mean()
        mad = tp.rolling(20).apply(lambda x: np.abs(x - x.mean()).mean())

        cci = (tp - sma) / (0.015 * mad + 1e-10)
        current_cci = cci.iloc[-1]

        score = 0.0

        if current_cci < -100:
            score = 50 + min(50, (-100 - current_cci) / 2)
        elif current_cci > 100:
            score = -50 - min(50, (current_cci - 100) / 2)
        else:
            score = -current_cci / 2

        return np.clip(score, -100, 100)

    def _calculate_adx_score(self, data: pd.DataFrame) -> float:
        """
        ADX 점수 (0 ~ +100, 추세 강도)

        ADX 자체는 방향성이 없으므로 추세 강도만 측정
        DI+, DI-로 방향 결정
        """
        high = data['high']
        low = data['low']
        close = data['close']

        plus_dm = high.diff()
        minus_dm = -low.diff()

        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)

        tr = pd.concat([
            high - low,
            (high - close.shift()).abs(),
            (low - close.shift()).abs()
        ], axis=1).max(axis=1)

        atr = tr.rolling(14).mean()
        plus_di = 100 * (plus_dm.rolling(14).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(14).mean() / atr)

        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di + 1e-10)
        adx = dx.rolling(14).mean()

        current_adx = adx.iloc[-1]
        current_plus_di = plus_di.iloc[-1]
        current_minus_di = minus_di.iloc[-1]

        # 추세 강도 기반 점수
        if current_adx < 20:
            strength_score = 0  # 약한 추세
        elif current_adx < 40:
            strength_score = 30  # 중간 추세
        else:
            strength_score = 60  # 강한 추세

        # 방향 결정
        if current_plus_di > current_minus_di:
            return strength_score  # 상승 추세
        else:
            return -strength_score  # 하락 추세

    def _calculate_bollinger_score(self, data: pd.DataFrame) -> float:
        """
        볼린저밴드 점수 (-100 ~ +100)
        """
        close = data['close']
        middle = close.rolling(self.bb_period).mean()
        std = close.rolling(self.bb_period).std()
        upper = middle + self.bb_std * std
        lower = middle - self.bb_std * std

        current_price = close.iloc[-1]
        current_upper = upper.iloc[-1]
        current_lower = lower.iloc[-1]
        current_middle = middle.iloc[-1]
        prev_price = close.iloc[-2]
        prev_lower = lower.iloc[-2]
        prev_upper = upper.iloc[-2]

        # BB 내 위치 (0~1)
        bb_position = (current_price - current_lower) / (current_upper - current_lower + 1e-10)

        score = 0.0

        # 하단 터치 후 반등
        if prev_price <= prev_lower and current_price > current_lower:
            score += 50

        # 상단 터치
        if current_price >= current_upper:
            score -= 40

        # 위치 기반 점수
        if bb_position < 0.2:
            score += 30  # 하단 근처
        elif bb_position > 0.8:
            score -= 30  # 상단 근처

        # 밴드 폭 (스퀴즈 감지)
        band_width = (current_upper - current_lower) / current_middle
        if band_width < 0.05:
            score += 10  # 스퀴즈 (변동성 확대 예상)

        return np.clip(score, -100, 100)

    def _calculate_atr_score(self, data: pd.DataFrame) -> float:
        """
        ATR 기반 점수 (변동성 위치)
        """
        high = data['high']
        low = data['low']
        close = data['close']

        tr = pd.concat([
            high - low,
            (high - close.shift()).abs(),
            (low - close.shift()).abs()
        ], axis=1).max(axis=1)

        atr = tr.rolling(14).mean()
        atr_percentile = atr.rank(pct=True).iloc[-1]

        # 높은 변동성은 중립~약간 부정적
        if atr_percentile > 0.8:
            return -20  # 고변동성
        elif atr_percentile < 0.2:
            return 20  # 저변동성 (스퀴즈)
        return 0

    def _calculate_volume_score(self, data: pd.DataFrame) -> float:
        """
        거래량 점수 (-100 ~ +100)
        """
        close = data['close']
        volume = data['volume']

        volume_ma = volume.rolling(20).mean()
        volume_ratio = volume.iloc[-1] / (volume_ma.iloc[-1] + 1e-10)

        price_change = close.pct_change().iloc[-1]

        score = 0.0

        # 거래량 급증 + 가격 상승
        if volume_ratio > 2.0 and price_change > 0.01:
            score += 60
        elif volume_ratio > 1.5 and price_change > 0:
            score += 30

        # 거래량 급증 + 가격 하락
        if volume_ratio > 2.0 and price_change < -0.01:
            score -= 60
        elif volume_ratio > 1.5 and price_change < 0:
            score -= 30

        # 거래량 감소
        if volume_ratio < 0.5:
            score *= 0.5  # 신뢰도 감소

        return np.clip(score, -100, 100)

    def _calculate_obv_score(self, data: pd.DataFrame) -> float:
        """
        OBV 점수 (-100 ~ +100)
        """
        close = data['close']
        volume = data['volume']

        obv = (np.sign(close.diff()) * volume).cumsum()
        obv_ma = obv.rolling(20).mean()

        current_obv = obv.iloc[-1]
        current_obv_ma = obv_ma.iloc[-1]
        prev_obv = obv.iloc[-2]

        score = 0.0

        # OBV 추세
        if current_obv > current_obv_ma:
            score += 30
        else:
            score -= 30

        # OBV 방향
        if current_obv > prev_obv:
            score += 20
        else:
            score -= 20

        # 가격-OBV 다이버전스
        price_trend = close.iloc[-1] > close.iloc[-5]
        obv_trend = current_obv > obv.iloc[-5]

        if price_trend and not obv_trend:
            score -= 25  # 베어리시 다이버전스
        elif not price_trend and obv_trend:
            score += 25  # 불리시 다이버전스

        return np.clip(score, -100, 100)

    def _check_divergence(self, price: pd.Series, indicator: pd.Series,
                         lookback: int = 14) -> Optional[str]:
        """
        다이버전스 감지

        Returns:
            'bullish': 상승 다이버전스
            'bearish': 하락 다이버전스
            None: 다이버전스 없음
        """
        price_recent = price.tail(lookback)
        ind_recent = indicator.tail(lookback)

        # 가격 저점 vs 지표 저점
        price_low_idx = price_recent.idxmin()
        ind_low_idx = ind_recent.idxmin()

        # 최근 저점이 이전 저점보다 낮은데 지표는 높은 경우 (상승 다이버전스)
        if (price_recent.iloc[-1] < price_recent.iloc[0] and
            ind_recent.iloc[-1] > ind_recent.iloc[0]):
            return 'bullish'

        # 최근 고점이 이전 고점보다 높은데 지표는 낮은 경우 (하락 다이버전스)
        if (price_recent.iloc[-1] > price_recent.iloc[0] and
            ind_recent.iloc[-1] < ind_recent.iloc[0]):
            return 'bearish'

        return None
