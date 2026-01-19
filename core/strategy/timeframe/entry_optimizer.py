"""
진입 최적화 모듈

지지/저항선, 캔들 패턴, 거래량을 분석하여
최적의 진입 가격과 손절/익절 레벨을 계산합니다.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging

from .trend_aligner import TrendDirection

logger = logging.getLogger(__name__)


class CandlePattern(Enum):
    """캔들 패턴"""
    HAMMER = "hammer"
    INVERTED_HAMMER = "inverted_hammer"
    ENGULFING_BULL = "engulfing_bull"
    ENGULFING_BEAR = "engulfing_bear"
    DOJI = "doji"
    MORNING_STAR = "morning_star"
    EVENING_STAR = "evening_star"
    NONE = "none"


@dataclass
class SupportResistance:
    """지지/저항선 정보"""
    support_levels: List[float] = field(default_factory=list)
    resistance_levels: List[float] = field(default_factory=list)
    nearest_support: float = 0.0
    nearest_resistance: float = 0.0
    support_strength: float = 0.0
    resistance_strength: float = 0.0

    def to_dict(self) -> Dict:
        return {
            'support_levels': self.support_levels[:3],
            'resistance_levels': self.resistance_levels[:3],
            'nearest_support': self.nearest_support,
            'nearest_resistance': self.nearest_resistance,
            'support_strength': self.support_strength,
            'resistance_strength': self.resistance_strength,
        }


@dataclass
class EntrySignal:
    """진입 신호"""
    direction: int = 0  # 1: 롱, -1: 숏, 0: 진입 안함
    entry_price: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    position_size_pct: float = 0.0  # 권장 포지션 비율
    confidence: float = 0.0
    quality_score: float = 0.0
    candle_pattern: CandlePattern = CandlePattern.NONE
    reasons: List[str] = field(default_factory=list)

    @property
    def risk_reward_ratio(self) -> float:
        """손익비"""
        if self.entry_price == 0 or self.stop_loss == 0:
            return 0.0

        risk = abs(self.entry_price - self.stop_loss)
        reward = abs(self.take_profit - self.entry_price)

        return reward / risk if risk > 0 else 0.0

    def to_dict(self) -> Dict:
        return {
            'direction': self.direction,
            'entry_price': self.entry_price,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'position_size_pct': self.position_size_pct,
            'confidence': self.confidence,
            'quality_score': self.quality_score,
            'risk_reward_ratio': self.risk_reward_ratio,
            'candle_pattern': self.candle_pattern.value,
            'reasons': self.reasons,
        }


class EntryOptimizer:
    """
    진입 최적화기

    다양한 기술적 분석을 통해 최적의 진입점을 찾습니다.
    """

    def __init__(
        self,
        atr_period: int = 14,
        sr_lookback: int = 50,
        min_risk_reward: float = 1.5,
        max_stop_loss_pct: float = 0.05
    ):
        """
        Args:
            atr_period: ATR 계산 기간
            sr_lookback: 지지/저항 분석 기간
            min_risk_reward: 최소 손익비
            max_stop_loss_pct: 최대 손절 비율
        """
        self.atr_period = atr_period
        self.sr_lookback = sr_lookback
        self.min_risk_reward = min_risk_reward
        self.max_stop_loss_pct = max_stop_loss_pct

    def optimize_entry(
        self,
        data: pd.DataFrame,
        trend_direction: TrendDirection,
        alignment_score: float = 0.5
    ) -> EntrySignal:
        """
        진입 최적화

        Args:
            data: OHLCV 데이터
            trend_direction: 추세 방향
            alignment_score: 타임프레임 정렬 점수

        Returns:
            EntrySignal: 최적화된 진입 신호
        """
        if len(data) < self.sr_lookback + 10:
            return EntrySignal()

        current_price = data['close'].iloc[-1]

        # 지지/저항 분석
        sr = self.find_support_resistance(data)

        # 캔들 패턴 분석
        candle_pattern = self.detect_candle_pattern(data)

        # 거래량 확인
        volume_score = self._calculate_volume_score(data)

        # 지지선 접근도
        support_proximity = self._calculate_support_proximity(current_price, sr)

        # 종합 점수 계산
        entry_quality = self._calculate_entry_quality(
            trend_direction,
            alignment_score,
            candle_pattern,
            volume_score,
            support_proximity
        )

        # 진입 결정
        if entry_quality < 0.5:
            return EntrySignal(
                quality_score=entry_quality,
                reasons=["진입 품질 점수 미달"]
            )

        # 방향 결정
        direction = 1 if trend_direction.value > 0 else -1 if trend_direction.value < 0 else 0

        if direction == 0:
            return EntrySignal(
                quality_score=entry_quality,
                reasons=["추세 방향 불명확"]
            )

        # 손절/익절 계산
        atr = self._calculate_atr(data)
        stop_loss, take_profit = self._calculate_risk_levels(
            current_price, direction, atr, sr
        )

        # 손익비 확인
        risk = abs(current_price - stop_loss)
        reward = abs(take_profit - current_price)
        risk_reward = reward / risk if risk > 0 else 0

        if risk_reward < self.min_risk_reward:
            return EntrySignal(
                quality_score=entry_quality,
                reasons=[f"손익비 미달: {risk_reward:.2f} < {self.min_risk_reward}"]
            )

        # 포지션 크기 계산
        position_size = self._calculate_position_size(entry_quality, alignment_score)

        # 이유 생성
        reasons = self._generate_entry_reasons(
            trend_direction, candle_pattern, volume_score, support_proximity
        )

        return EntrySignal(
            direction=direction,
            entry_price=current_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            position_size_pct=position_size,
            confidence=entry_quality,
            quality_score=entry_quality,
            candle_pattern=candle_pattern,
            reasons=reasons
        )

    def find_support_resistance(self, data: pd.DataFrame) -> SupportResistance:
        """지지/저항선 탐색"""
        high = data['high'].iloc[-self.sr_lookback:]
        low = data['low'].iloc[-self.sr_lookback:]
        close = data['close'].iloc[-self.sr_lookback:]
        volume = data['volume'].iloc[-self.sr_lookback:]

        current_price = close.iloc[-1]

        # 피벗 포인트 기반 지지/저항
        pivot_highs = self._find_pivot_points(high, 'high')
        pivot_lows = self._find_pivot_points(low, 'low')

        # 거래량 가중 레벨 식별
        support_levels = self._cluster_levels(
            [l for l in pivot_lows if l < current_price],
            tolerance=current_price * 0.01
        )

        resistance_levels = self._cluster_levels(
            [h for h in pivot_highs if h > current_price],
            tolerance=current_price * 0.01
        )

        # 가장 가까운 레벨
        nearest_support = max(support_levels) if support_levels else current_price * 0.95
        nearest_resistance = min(resistance_levels) if resistance_levels else current_price * 1.05

        # 강도 계산 (터치 횟수 기반)
        support_strength = self._calculate_level_strength(data, nearest_support)
        resistance_strength = self._calculate_level_strength(data, nearest_resistance)

        return SupportResistance(
            support_levels=sorted(support_levels, reverse=True)[:5],
            resistance_levels=sorted(resistance_levels)[:5],
            nearest_support=nearest_support,
            nearest_resistance=nearest_resistance,
            support_strength=support_strength,
            resistance_strength=resistance_strength
        )

    def detect_candle_pattern(self, data: pd.DataFrame) -> CandlePattern:
        """캔들 패턴 감지"""
        if len(data) < 3:
            return CandlePattern.NONE

        open_price = data['open'].iloc[-1]
        high = data['high'].iloc[-1]
        low = data['low'].iloc[-1]
        close = data['close'].iloc[-1]

        prev_open = data['open'].iloc[-2]
        prev_close = data['close'].iloc[-2]

        body = abs(close - open_price)
        upper_shadow = high - max(open_price, close)
        lower_shadow = min(open_price, close) - low
        total_range = high - low

        if total_range == 0:
            return CandlePattern.NONE

        body_ratio = body / total_range

        # 도지
        if body_ratio < 0.1:
            return CandlePattern.DOJI

        # 해머 (하락 추세에서 반전 신호)
        if lower_shadow > body * 2 and upper_shadow < body * 0.5:
            return CandlePattern.HAMMER

        # 역해머
        if upper_shadow > body * 2 and lower_shadow < body * 0.5:
            return CandlePattern.INVERTED_HAMMER

        # 불리시 인걸핑
        prev_body = abs(prev_close - prev_open)
        if (prev_close < prev_open and  # 이전이 음봉
            close > open_price and  # 현재가 양봉
            body > prev_body and  # 현재 몸통이 더 큼
            close > prev_open and  # 현재 종가가 이전 시가 위
            open_price < prev_close):  # 현재 시가가 이전 종가 아래
            return CandlePattern.ENGULFING_BULL

        # 베어리시 인걸핑
        if (prev_close > prev_open and
            close < open_price and
            body > prev_body and
            close < prev_open and
            open_price > prev_close):
            return CandlePattern.ENGULFING_BEAR

        return CandlePattern.NONE

    def _calculate_atr(self, data: pd.DataFrame) -> float:
        """ATR 계산"""
        high = data['high']
        low = data['low']
        close = data['close']

        tr = pd.concat([
            high - low,
            abs(high - close.shift(1)),
            abs(low - close.shift(1))
        ], axis=1).max(axis=1)

        atr = tr.rolling(self.atr_period).mean().iloc[-1]
        return atr

    def _calculate_volume_score(self, data: pd.DataFrame) -> float:
        """거래량 점수 계산"""
        volume = data['volume']
        close = data['close']

        # 거래량 이동평균
        vol_ma = volume.rolling(20).mean()
        current_vol = volume.iloc[-1]

        # 상대 거래량
        rel_volume = current_vol / vol_ma.iloc[-1] if vol_ma.iloc[-1] > 0 else 1.0

        # 가격 상승 시 거래량 증가면 좋음
        price_change = close.pct_change().iloc[-1]
        vol_change = volume.pct_change().iloc[-1]

        if price_change > 0 and vol_change > 0:
            score = min(1.0, rel_volume / 2)
        elif price_change < 0 and vol_change > 0:
            score = 0.3  # 하락 + 거래량 증가 = 부정적
        else:
            score = 0.5

        return score

    def _calculate_support_proximity(
        self,
        current_price: float,
        sr: SupportResistance
    ) -> float:
        """지지선 접근도 점수"""
        if sr.nearest_support == 0:
            return 0.5

        distance_to_support = (current_price - sr.nearest_support) / current_price
        distance_to_resistance = (sr.nearest_resistance - current_price) / current_price

        # 지지선에 가까울수록 높은 점수 (매수 관점)
        if distance_to_support < 0.02:  # 2% 이내
            return 0.9
        elif distance_to_support < 0.05:  # 5% 이내
            return 0.7
        elif distance_to_support < 0.10:  # 10% 이내
            return 0.5
        else:
            return 0.3

    def _calculate_entry_quality(
        self,
        trend_direction: TrendDirection,
        alignment_score: float,
        candle_pattern: CandlePattern,
        volume_score: float,
        support_proximity: float
    ) -> float:
        """진입 품질 점수 계산"""
        score = 0.0

        # 추세 방향 점수 (30%)
        if trend_direction in [TrendDirection.STRONG_BULL, TrendDirection.STRONG_BEAR]:
            score += 0.3
        elif trend_direction in [TrendDirection.BULL, TrendDirection.BEAR]:
            score += 0.2
        else:
            score += 0.05

        # 정렬 점수 (25%)
        score += alignment_score * 0.25

        # 캔들 패턴 점수 (15%)
        bullish_patterns = [
            CandlePattern.HAMMER,
            CandlePattern.ENGULFING_BULL,
            CandlePattern.MORNING_STAR
        ]
        bearish_patterns = [
            CandlePattern.INVERTED_HAMMER,
            CandlePattern.ENGULFING_BEAR,
            CandlePattern.EVENING_STAR
        ]

        if candle_pattern in bullish_patterns and trend_direction.value > 0:
            score += 0.15
        elif candle_pattern in bearish_patterns and trend_direction.value < 0:
            score += 0.15
        elif candle_pattern == CandlePattern.DOJI:
            score += 0.05
        else:
            score += 0.07

        # 거래량 점수 (15%)
        score += volume_score * 0.15

        # 지지선 접근도 (15%)
        score += support_proximity * 0.15

        return min(1.0, score)

    def _calculate_risk_levels(
        self,
        entry_price: float,
        direction: int,
        atr: float,
        sr: SupportResistance
    ) -> Tuple[float, float]:
        """손절/익절 레벨 계산"""
        # ATR 기반 손절
        atr_stop = atr * 2

        if direction == 1:  # 롱
            # 손절: 지지선 또는 ATR 기반 중 가까운 것
            stop_by_atr = entry_price - atr_stop
            stop_by_support = sr.nearest_support * 0.99  # 지지선 약간 아래

            stop_loss = max(stop_by_atr, stop_by_support)

            # 최대 손절 제한
            max_stop = entry_price * (1 - self.max_stop_loss_pct)
            stop_loss = max(stop_loss, max_stop)

            # 익절: 저항선 또는 손익비 기반
            risk = entry_price - stop_loss
            min_reward = risk * self.min_risk_reward

            take_profit = max(
                sr.nearest_resistance * 0.99,
                entry_price + min_reward
            )

        else:  # 숏
            stop_by_atr = entry_price + atr_stop
            stop_by_resistance = sr.nearest_resistance * 1.01

            stop_loss = min(stop_by_atr, stop_by_resistance)

            max_stop = entry_price * (1 + self.max_stop_loss_pct)
            stop_loss = min(stop_loss, max_stop)

            risk = stop_loss - entry_price
            min_reward = risk * self.min_risk_reward

            take_profit = min(
                sr.nearest_support * 1.01,
                entry_price - min_reward
            )

        return stop_loss, take_profit

    def _calculate_position_size(
        self,
        entry_quality: float,
        alignment_score: float
    ) -> float:
        """포지션 크기 비율 계산 (0.0 ~ 1.0)"""
        # 기본 크기
        base_size = 0.5

        # 품질에 따른 조정
        quality_multiplier = entry_quality

        # 정렬에 따른 조정
        alignment_multiplier = 0.5 + alignment_score * 0.5

        size = base_size * quality_multiplier * alignment_multiplier

        return min(1.0, max(0.1, size))

    def _find_pivot_points(
        self,
        series: pd.Series,
        pivot_type: str,
        window: int = 5
    ) -> List[float]:
        """피벗 포인트 찾기"""
        pivots = []

        for i in range(window, len(series) - window):
            if pivot_type == 'high':
                if series.iloc[i] == series.iloc[i - window:i + window + 1].max():
                    pivots.append(series.iloc[i])
            else:
                if series.iloc[i] == series.iloc[i - window:i + window + 1].min():
                    pivots.append(series.iloc[i])

        return pivots

    def _cluster_levels(
        self,
        levels: List[float],
        tolerance: float
    ) -> List[float]:
        """비슷한 레벨 클러스터링"""
        if not levels:
            return []

        sorted_levels = sorted(levels)
        clusters = [[sorted_levels[0]]]

        for level in sorted_levels[1:]:
            if level - clusters[-1][-1] <= tolerance:
                clusters[-1].append(level)
            else:
                clusters.append([level])

        # 각 클러스터의 평균 반환
        return [np.mean(cluster) for cluster in clusters]

    def _calculate_level_strength(
        self,
        data: pd.DataFrame,
        level: float
    ) -> float:
        """레벨 강도 계산 (터치 횟수 기반)"""
        tolerance = level * 0.01  # 1% 오차 허용

        close = data['close'].iloc[-self.sr_lookback:]
        low = data['low'].iloc[-self.sr_lookback:]
        high = data['high'].iloc[-self.sr_lookback:]

        # 해당 레벨 근처 터치 횟수
        touches = 0
        for i in range(len(close)):
            if abs(low.iloc[i] - level) <= tolerance:
                touches += 1
            if abs(high.iloc[i] - level) <= tolerance:
                touches += 1

        # 정규화 (최대 10회를 1.0으로)
        return min(1.0, touches / 10)

    def _generate_entry_reasons(
        self,
        trend_direction: TrendDirection,
        candle_pattern: CandlePattern,
        volume_score: float,
        support_proximity: float
    ) -> List[str]:
        """진입 이유 생성"""
        reasons = []

        # 추세
        if trend_direction in [TrendDirection.STRONG_BULL, TrendDirection.STRONG_BEAR]:
            reasons.append(f"강한 {trend_direction.name} 추세")
        elif trend_direction in [TrendDirection.BULL, TrendDirection.BEAR]:
            reasons.append(f"{trend_direction.name} 추세")

        # 캔들 패턴
        if candle_pattern != CandlePattern.NONE:
            reasons.append(f"캔들 패턴: {candle_pattern.value}")

        # 거래량
        if volume_score > 0.7:
            reasons.append("거래량 확인")
        elif volume_score < 0.4:
            reasons.append("거래량 부족 주의")

        # 지지선
        if support_proximity > 0.7:
            reasons.append("지지선 근접")

        return reasons
