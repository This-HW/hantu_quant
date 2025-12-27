"""
추세 정렬기 모듈

여러 타임프레임의 추세를 분석하고 정렬 상태를 평가합니다.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class TrendDirection(Enum):
    """추세 방향"""
    STRONG_BULL = 2
    BULL = 1
    NEUTRAL = 0
    BEAR = -1
    STRONG_BEAR = -2


@dataclass
class TrendAnalysis:
    """추세 분석 결과"""
    direction: TrendDirection
    strength: float = 0.0  # 0.0 ~ 1.0
    slope: float = 0.0  # 기울기
    volatility: float = 0.0  # 변동성
    ma_cross_signal: int = 0  # 1: 골든크로스, -1: 데드크로스, 0: 없음
    higher_highs: int = 0  # 고점 상승 횟수
    lower_lows: int = 0  # 저점 하락 횟수

    @property
    def is_trending(self) -> bool:
        """추세 존재 여부"""
        return self.direction not in [TrendDirection.NEUTRAL]

    @property
    def is_strong(self) -> bool:
        """강한 추세 여부"""
        return self.direction in [TrendDirection.STRONG_BULL, TrendDirection.STRONG_BEAR]

    def to_dict(self) -> Dict:
        return {
            'direction': self.direction.name,
            'strength': self.strength,
            'slope': self.slope,
            'volatility': self.volatility,
            'ma_cross_signal': self.ma_cross_signal,
            'higher_highs': self.higher_highs,
            'lower_lows': self.lower_lows,
        }


@dataclass
class AlignmentResult:
    """추세 정렬 결과"""
    score: float = 0.0  # 0.0 ~ 1.0
    direction: TrendDirection = TrendDirection.NEUTRAL
    aligned_count: int = 0
    total_timeframes: int = 0
    conflicts: List[str] = field(default_factory=list)

    @property
    def is_aligned(self) -> bool:
        """정렬 여부 (점수 0.7 이상)"""
        return self.score >= 0.7

    @property
    def alignment_ratio(self) -> float:
        """정렬 비율"""
        return self.aligned_count / self.total_timeframes if self.total_timeframes > 0 else 0

    def to_dict(self) -> Dict:
        return {
            'score': self.score,
            'direction': self.direction.name,
            'aligned_count': self.aligned_count,
            'total_timeframes': self.total_timeframes,
            'is_aligned': self.is_aligned,
            'conflicts': self.conflicts,
        }


class TrendAligner:
    """
    추세 정렬기

    여러 타임프레임의 추세를 분석하고
    정렬 상태를 평가하여 거래 신호를 생성합니다.
    """

    def __init__(
        self,
        ma_short: int = 20,
        ma_medium: int = 50,
        ma_long: int = 200,
        trend_lookback: int = 20
    ):
        """
        Args:
            ma_short: 단기 이동평균 기간
            ma_medium: 중기 이동평균 기간
            ma_long: 장기 이동평균 기간
            trend_lookback: 추세 분석 기간
        """
        self.ma_short = ma_short
        self.ma_medium = ma_medium
        self.ma_long = ma_long
        self.trend_lookback = trend_lookback

    def analyze_trend(self, data: pd.DataFrame) -> TrendAnalysis:
        """
        추세 분석

        Args:
            data: OHLCV 데이터

        Returns:
            TrendAnalysis: 추세 분석 결과
        """
        if len(data) < self.ma_long + 10:
            return TrendAnalysis(direction=TrendDirection.NEUTRAL)

        close = data['close']
        high = data['high']
        low = data['low']

        # 이동평균 계산
        ma_s = close.rolling(self.ma_short).mean()
        ma_m = close.rolling(self.ma_medium).mean()
        ma_l = close.rolling(self.ma_long).mean()

        current_price = close.iloc[-1]

        # 추세 방향 결정
        direction = self._determine_direction(
            current_price,
            ma_s.iloc[-1],
            ma_m.iloc[-1],
            ma_l.iloc[-1]
        )

        # 추세 강도 계산
        strength = self._calculate_strength(data, ma_s, ma_m, ma_l)

        # 기울기 계산
        slope = self._calculate_slope(close)

        # 변동성 계산
        volatility = self._calculate_volatility(close)

        # 이동평균 크로스 신호
        ma_cross = self._detect_ma_cross(ma_s, ma_m)

        # 고점/저점 패턴
        higher_highs, lower_lows = self._analyze_swing_pattern(high, low)

        return TrendAnalysis(
            direction=direction,
            strength=strength,
            slope=slope,
            volatility=volatility,
            ma_cross_signal=ma_cross,
            higher_highs=higher_highs,
            lower_lows=lower_lows
        )

    def align_trends(
        self,
        trend_analyses: Dict[str, TrendAnalysis]
    ) -> AlignmentResult:
        """
        추세 정렬 분석

        Args:
            trend_analyses: {타임프레임: 추세분석} 딕셔너리

        Returns:
            AlignmentResult: 정렬 결과
        """
        if not trend_analyses:
            return AlignmentResult()

        directions = []
        strengths = []
        conflicts = []

        for tf, analysis in trend_analyses.items():
            directions.append(analysis.direction.value)
            strengths.append(analysis.strength)

        # 방향 일치 검사
        positive_count = sum(1 for d in directions if d > 0)
        negative_count = sum(1 for d in directions if d < 0)
        neutral_count = sum(1 for d in directions if d == 0)
        total = len(directions)

        # 지배적 방향 결정
        if positive_count > total / 2:
            dominant_direction = TrendDirection.BULL
            aligned_count = positive_count
        elif negative_count > total / 2:
            dominant_direction = TrendDirection.BEAR
            aligned_count = negative_count
        else:
            dominant_direction = TrendDirection.NEUTRAL
            aligned_count = neutral_count

        # 강한 추세인지 확인
        avg_strength = np.mean(strengths)
        if avg_strength > 0.7:
            if dominant_direction == TrendDirection.BULL:
                dominant_direction = TrendDirection.STRONG_BULL
            elif dominant_direction == TrendDirection.BEAR:
                dominant_direction = TrendDirection.STRONG_BEAR

        # 충돌 감지
        for tf, analysis in trend_analyses.items():
            if analysis.direction.value * dominant_direction.value < 0:
                conflicts.append(f"{tf}: {analysis.direction.name}")

        # 정렬 점수 계산
        alignment_score = self._calculate_alignment_score(
            directions, strengths, aligned_count, total
        )

        return AlignmentResult(
            score=alignment_score,
            direction=dominant_direction,
            aligned_count=aligned_count,
            total_timeframes=total,
            conflicts=conflicts
        )

    def get_entry_quality(
        self,
        daily_trend: TrendAnalysis,
        weekly_trend: TrendAnalysis,
        monthly_trend: Optional[TrendAnalysis] = None
    ) -> float:
        """
        진입 품질 점수 계산 (0.0 ~ 1.0)

        높은 점수 = 좋은 진입 타이밍
        """
        scores = []

        # 일봉-주봉 정렬
        if daily_trend.direction.value * weekly_trend.direction.value > 0:
            scores.append(1.0)
        elif daily_trend.direction.value * weekly_trend.direction.value < 0:
            scores.append(0.0)
        else:
            scores.append(0.5)

        # 월봉 추가 정렬 (있는 경우)
        if monthly_trend:
            if monthly_trend.direction.value * daily_trend.direction.value > 0:
                scores.append(1.0)
            elif monthly_trend.direction.value * daily_trend.direction.value < 0:
                scores.append(0.0)
            else:
                scores.append(0.5)

        # 추세 강도 반영
        strength_bonus = (daily_trend.strength + weekly_trend.strength) / 2

        # 골든/데드 크로스 보너스
        cross_bonus = 0.0
        if daily_trend.ma_cross_signal == 1:  # 골든크로스
            cross_bonus = 0.1
        elif daily_trend.ma_cross_signal == -1:  # 데드크로스
            cross_bonus = 0.1  # 공매도용

        base_score = np.mean(scores)
        final_score = base_score * (0.7 + 0.3 * strength_bonus) + cross_bonus

        return min(1.0, final_score)

    def _determine_direction(
        self,
        price: float,
        ma_s: float,
        ma_m: float,
        ma_l: float
    ) -> TrendDirection:
        """추세 방향 결정"""
        # 이평선 정렬 상태
        above_all = price > ma_s > ma_m > ma_l
        below_all = price < ma_s < ma_m < ma_l
        above_short = price > ma_s
        above_long = price > ma_l

        if above_all:
            return TrendDirection.STRONG_BULL
        elif below_all:
            return TrendDirection.STRONG_BEAR
        elif above_short and above_long:
            return TrendDirection.BULL
        elif not above_short and not above_long:
            return TrendDirection.BEAR
        else:
            return TrendDirection.NEUTRAL

    def _calculate_strength(
        self,
        data: pd.DataFrame,
        ma_s: pd.Series,
        ma_m: pd.Series,
        ma_l: pd.Series
    ) -> float:
        """추세 강도 계산"""
        close = data['close']
        current_price = close.iloc[-1]

        # 가격의 이평선 대비 위치
        deviation_s = (current_price - ma_s.iloc[-1]) / ma_s.iloc[-1]
        deviation_l = (current_price - ma_l.iloc[-1]) / ma_l.iloc[-1]

        # 이평선 간 거리
        ma_spread = abs((ma_s.iloc[-1] - ma_l.iloc[-1]) / ma_l.iloc[-1])

        # ADX 대용 (방향성 움직임)
        high = data['high']
        low = data['low']

        plus_dm = high.diff().clip(lower=0)
        minus_dm = (-low.diff()).clip(lower=0)

        tr = pd.concat([
            high - low,
            abs(high - close.shift(1)),
            abs(low - close.shift(1))
        ], axis=1).max(axis=1)

        atr = tr.rolling(14).mean()
        plus_di = (plus_dm.rolling(14).mean() / atr * 100).iloc[-1]
        minus_di = (minus_dm.rolling(14).mean() / atr * 100).iloc[-1]

        dx = abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10) * 100
        adx_proxy = min(1.0, dx / 50)

        # 종합 강도
        strength = (
            abs(deviation_l) * 0.3 +
            ma_spread * 5 +
            adx_proxy * 0.4
        )

        return min(1.0, strength)

    def _calculate_slope(self, close: pd.Series) -> float:
        """가격 기울기 계산"""
        lookback = min(self.trend_lookback, len(close) - 1)
        if lookback < 5:
            return 0.0

        x = np.arange(lookback)
        y = close.iloc[-lookback:].values

        # 선형 회귀 기울기
        slope = np.polyfit(x, y, 1)[0]

        # 정규화 (평균 가격 대비 일간 변화율)
        avg_price = np.mean(y)
        normalized_slope = slope / avg_price * 100

        return normalized_slope

    def _calculate_volatility(self, close: pd.Series) -> float:
        """변동성 계산"""
        returns = close.pct_change().dropna()
        if len(returns) < 10:
            return 0.0

        volatility = returns.tail(20).std() * np.sqrt(252)  # 연율화
        return min(1.0, volatility)

    def _detect_ma_cross(self, ma_s: pd.Series, ma_m: pd.Series) -> int:
        """이동평균 크로스 감지"""
        if len(ma_s) < 3:
            return 0

        # 현재와 이전 상태
        current_above = ma_s.iloc[-1] > ma_m.iloc[-1]
        prev_above = ma_s.iloc[-2] > ma_m.iloc[-2]

        if current_above and not prev_above:
            return 1  # 골든크로스
        elif not current_above and prev_above:
            return -1  # 데드크로스
        return 0

    def _analyze_swing_pattern(
        self,
        high: pd.Series,
        low: pd.Series
    ) -> Tuple[int, int]:
        """스윙 고점/저점 패턴 분석"""
        lookback = min(self.trend_lookback, len(high) - 1)
        if lookback < 10:
            return 0, 0

        highs = high.iloc[-lookback:]
        lows = low.iloc[-lookback:]

        # 로컬 고점/저점 찾기
        window = 5
        local_highs = []
        local_lows = []

        for i in range(window, lookback - window):
            if highs.iloc[i] == highs.iloc[i - window:i + window + 1].max():
                local_highs.append(highs.iloc[i])
            if lows.iloc[i] == lows.iloc[i - window:i + window + 1].min():
                local_lows.append(lows.iloc[i])

        # Higher Highs 카운트
        higher_highs = 0
        for i in range(1, len(local_highs)):
            if local_highs[i] > local_highs[i - 1]:
                higher_highs += 1

        # Lower Lows 카운트
        lower_lows = 0
        for i in range(1, len(local_lows)):
            if local_lows[i] < local_lows[i - 1]:
                lower_lows += 1

        return higher_highs, lower_lows

    def _calculate_alignment_score(
        self,
        directions: List[int],
        strengths: List[float],
        aligned_count: int,
        total: int
    ) -> float:
        """정렬 점수 계산"""
        if total == 0:
            return 0.0

        # 기본 정렬 비율
        alignment_ratio = aligned_count / total

        # 강도 가중 보너스
        avg_strength = np.mean(strengths)

        # 방향 일관성 보너스
        direction_variance = np.var(directions)
        consistency_bonus = max(0, 1 - direction_variance)

        score = alignment_ratio * 0.6 + avg_strength * 0.2 + consistency_bonus * 0.2

        return min(1.0, score)
