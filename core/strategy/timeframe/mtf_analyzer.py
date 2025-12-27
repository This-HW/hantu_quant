"""
멀티타임프레임 분석기 모듈

월봉, 주봉, 일봉 데이터를 통합 분석하여
추세 정렬도와 진입 타이밍을 판단합니다.
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class Timeframe(Enum):
    """타임프레임 정의"""
    DAILY = "D"
    WEEKLY = "W"
    MONTHLY = "ME"  # pandas 2.x compatible


@dataclass
class TimeframeData:
    """타임프레임별 분석 데이터"""
    timeframe: Timeframe
    trend_direction: int = 0  # 1: 상승, 0: 횡보, -1: 하락
    trend_strength: float = 0.0  # 0.0 ~ 1.0
    ma_position: float = 0.0  # 이평선 대비 위치 (-1 ~ +1)
    momentum: float = 0.0  # 모멘텀 점수
    support_level: float = 0.0
    resistance_level: float = 0.0

    @property
    def is_bullish(self) -> bool:
        """상승 추세 여부"""
        return self.trend_direction > 0 and self.ma_position > 0

    @property
    def is_bearish(self) -> bool:
        """하락 추세 여부"""
        return self.trend_direction < 0 and self.ma_position < 0

    def to_dict(self) -> Dict:
        return {
            'timeframe': self.timeframe.value,
            'trend_direction': self.trend_direction,
            'trend_strength': self.trend_strength,
            'ma_position': self.ma_position,
            'momentum': self.momentum,
            'support_level': self.support_level,
            'resistance_level': self.resistance_level,
        }


@dataclass
class MTFConfig:
    """멀티타임프레임 분석 설정"""
    # 이동평균 기간
    daily_ma_short: int = 20
    daily_ma_long: int = 60
    weekly_ma_short: int = 10
    weekly_ma_long: int = 30
    monthly_ma_short: int = 6
    monthly_ma_long: int = 12

    # 추세 판단 임계값
    trend_threshold: float = 0.02  # 2% 변화 필요

    # 정렬 점수 가중치
    monthly_weight: float = 0.4
    weekly_weight: float = 0.35
    daily_weight: float = 0.25


class MTFAnalyzer:
    """
    멀티타임프레임 분석기

    월봉(대세), 주봉(중기), 일봉(단기)을 통합 분석하여
    추세 정렬도를 계산합니다.
    """

    def __init__(self, config: Optional[MTFConfig] = None):
        self.config = config or MTFConfig()

    def analyze(self, daily_data: pd.DataFrame) -> Dict[Timeframe, TimeframeData]:
        """
        전체 타임프레임 분석

        Args:
            daily_data: 일봉 OHLCV 데이터 (최소 252일 권장)

        Returns:
            타임프레임별 분석 결과
        """
        results = {}

        # 일봉 분석
        results[Timeframe.DAILY] = self._analyze_timeframe(
            daily_data,
            Timeframe.DAILY,
            self.config.daily_ma_short,
            self.config.daily_ma_long
        )

        # 주봉 변환 및 분석
        weekly_data = self._resample_to_weekly(daily_data)
        if len(weekly_data) >= self.config.weekly_ma_long:
            results[Timeframe.WEEKLY] = self._analyze_timeframe(
                weekly_data,
                Timeframe.WEEKLY,
                self.config.weekly_ma_short,
                self.config.weekly_ma_long
            )
        else:
            results[Timeframe.WEEKLY] = TimeframeData(Timeframe.WEEKLY)

        # 월봉 변환 및 분석
        monthly_data = self._resample_to_monthly(daily_data)
        if len(monthly_data) >= self.config.monthly_ma_long:
            results[Timeframe.MONTHLY] = self._analyze_timeframe(
                monthly_data,
                Timeframe.MONTHLY,
                self.config.monthly_ma_short,
                self.config.monthly_ma_long
            )
        else:
            results[Timeframe.MONTHLY] = TimeframeData(Timeframe.MONTHLY)

        return results

    def calculate_alignment_score(
        self,
        analysis: Dict[Timeframe, TimeframeData]
    ) -> float:
        """
        추세 정렬 점수 계산 (0.0 ~ 1.0)

        모든 타임프레임이 같은 방향이면 1.0
        완전히 반대 방향이면 0.0

        Args:
            analysis: 타임프레임별 분석 결과

        Returns:
            정렬 점수 (0.0 ~ 1.0)
        """
        monthly = analysis.get(Timeframe.MONTHLY, TimeframeData(Timeframe.MONTHLY))
        weekly = analysis.get(Timeframe.WEEKLY, TimeframeData(Timeframe.WEEKLY))
        daily = analysis.get(Timeframe.DAILY, TimeframeData(Timeframe.DAILY))

        # 방향 일치 점수
        direction_scores = []

        # 월봉 vs 주봉
        if monthly.trend_direction != 0 and weekly.trend_direction != 0:
            if monthly.trend_direction == weekly.trend_direction:
                direction_scores.append(1.0)
            else:
                direction_scores.append(0.0)
        else:
            direction_scores.append(0.5)

        # 주봉 vs 일봉
        if weekly.trend_direction != 0 and daily.trend_direction != 0:
            if weekly.trend_direction == daily.trend_direction:
                direction_scores.append(1.0)
            else:
                direction_scores.append(0.0)
        else:
            direction_scores.append(0.5)

        # 월봉 vs 일봉
        if monthly.trend_direction != 0 and daily.trend_direction != 0:
            if monthly.trend_direction == daily.trend_direction:
                direction_scores.append(1.0)
            else:
                direction_scores.append(0.0)
        else:
            direction_scores.append(0.5)

        # 가중 평균 정렬 점수
        base_score = np.mean(direction_scores)

        # 추세 강도 반영
        strength_bonus = (
            monthly.trend_strength * self.config.monthly_weight +
            weekly.trend_strength * self.config.weekly_weight +
            daily.trend_strength * self.config.daily_weight
        )

        return min(1.0, base_score * (0.7 + 0.3 * strength_bonus))

    def get_dominant_trend(
        self,
        analysis: Dict[Timeframe, TimeframeData]
    ) -> Tuple[int, float]:
        """
        지배적 추세 방향과 강도 반환

        Args:
            analysis: 타임프레임별 분석 결과

        Returns:
            (방향 [-1, 0, 1], 강도 [0.0 ~ 1.0])
        """
        monthly = analysis.get(Timeframe.MONTHLY, TimeframeData(Timeframe.MONTHLY))
        weekly = analysis.get(Timeframe.WEEKLY, TimeframeData(Timeframe.WEEKLY))
        daily = analysis.get(Timeframe.DAILY, TimeframeData(Timeframe.DAILY))

        # 가중 방향 점수
        weighted_direction = (
            monthly.trend_direction * self.config.monthly_weight +
            weekly.trend_direction * self.config.weekly_weight +
            daily.trend_direction * self.config.daily_weight
        )

        # 가중 강도
        weighted_strength = (
            monthly.trend_strength * self.config.monthly_weight +
            weekly.trend_strength * self.config.weekly_weight +
            daily.trend_strength * self.config.daily_weight
        )

        # 방향 결정
        if weighted_direction > 0.3:
            direction = 1
        elif weighted_direction < -0.3:
            direction = -1
        else:
            direction = 0

        return direction, weighted_strength

    def _analyze_timeframe(
        self,
        data: pd.DataFrame,
        timeframe: Timeframe,
        ma_short: int,
        ma_long: int
    ) -> TimeframeData:
        """개별 타임프레임 분석"""
        if len(data) < ma_long + 5:
            return TimeframeData(timeframe)

        close = data['close']
        high = data['high']
        low = data['low']

        # 이동평균 계산
        ma_s = close.rolling(ma_short).mean()
        ma_l = close.rolling(ma_long).mean()

        current_price = close.iloc[-1]
        current_ma_s = ma_s.iloc[-1]
        current_ma_l = ma_l.iloc[-1]

        # 추세 방향 판단
        ma_diff = (current_ma_s - current_ma_l) / current_ma_l
        price_vs_ma = (current_price - current_ma_l) / current_ma_l

        if ma_diff > self.config.trend_threshold and price_vs_ma > 0:
            trend_direction = 1
        elif ma_diff < -self.config.trend_threshold and price_vs_ma < 0:
            trend_direction = -1
        else:
            trend_direction = 0

        # 추세 강도 (ADX 대용)
        tr = pd.concat([
            high - low,
            abs(high - close.shift(1)),
            abs(low - close.shift(1))
        ], axis=1).max(axis=1)

        atr = tr.rolling(14).mean()
        trend_strength = min(1.0, abs(ma_diff) / 0.1)  # 10% 변화를 최대로

        # 이평선 대비 위치
        ma_position = np.clip(price_vs_ma * 10, -1, 1)

        # 모멘텀 (ROC)
        roc_period = min(20, len(data) - 1)
        momentum = (current_price / close.iloc[-roc_period - 1] - 1) * 100

        # 지지/저항선
        support = low.rolling(20).min().iloc[-1]
        resistance = high.rolling(20).max().iloc[-1]

        return TimeframeData(
            timeframe=timeframe,
            trend_direction=trend_direction,
            trend_strength=trend_strength,
            ma_position=ma_position,
            momentum=momentum,
            support_level=support,
            resistance_level=resistance
        )

    def _resample_to_weekly(self, daily_data: pd.DataFrame) -> pd.DataFrame:
        """일봉을 주봉으로 변환"""
        return daily_data.resample('W').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).dropna()

    def _resample_to_monthly(self, daily_data: pd.DataFrame) -> pd.DataFrame:
        """일봉을 월봉으로 변환"""
        return daily_data.resample('ME').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).dropna()

    def get_timeframe_summary(
        self,
        analysis: Dict[Timeframe, TimeframeData]
    ) -> Dict:
        """타임프레임 분석 요약"""
        direction, strength = self.get_dominant_trend(analysis)
        alignment = self.calculate_alignment_score(analysis)

        direction_str = {1: "BULLISH", 0: "NEUTRAL", -1: "BEARISH"}

        return {
            'dominant_trend': direction_str.get(direction, "NEUTRAL"),
            'trend_strength': strength,
            'alignment_score': alignment,
            'timeframes': {
                tf.value: data.to_dict()
                for tf, data in analysis.items()
            },
            'recommendation': self._get_recommendation(direction, alignment)
        }

    def _get_recommendation(self, direction: int, alignment: float) -> str:
        """투자 권고 생성"""
        if alignment >= 0.8:
            if direction == 1:
                return "STRONG_BUY: 모든 타임프레임 상승 정렬"
            elif direction == -1:
                return "STRONG_SELL: 모든 타임프레임 하락 정렬"
            else:
                return "HOLD: 강한 횡보"
        elif alignment >= 0.6:
            if direction == 1:
                return "BUY: 대체로 상승 추세"
            elif direction == -1:
                return "SELL: 대체로 하락 추세"
            else:
                return "HOLD: 추세 불명확"
        else:
            return "CAUTION: 타임프레임 간 추세 불일치"
