"""
섹터 전환 감지 모듈

섹터 순위 및 모멘텀 변화를 감지하여 전환 신호를 생성합니다.
"""

import numpy as np
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from collections import deque
import logging

from .sector_map import Sector
from .sector_analyzer import SectorMetrics

logger = logging.getLogger(__name__)


class TransitionType(Enum):
    """전환 유형"""
    MOMENTUM_SHIFT = "momentum_shift"  # 모멘텀 변화
    RANK_CHANGE = "rank_change"  # 순위 변동
    STRENGTH_REVERSAL = "strength_reversal"  # 강/약세 반전
    LEADERSHIP_CHANGE = "leadership_change"  # 리더십 교체
    BREAKOUT = "breakout"  # 돌파
    BREAKDOWN = "breakdown"  # 붕괴


@dataclass
class TransitionSignal:
    """전환 신호"""
    sector: Sector
    transition_type: TransitionType
    direction: int = 0  # 1: 긍정적 전환, -1: 부정적 전환
    strength: float = 0.0  # 신호 강도 (0.0 ~ 1.0)
    previous_rank: int = 0
    current_rank: int = 0
    previous_momentum: float = 0.0
    current_momentum: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    description: str = ""

    @property
    def rank_change(self) -> int:
        """순위 변화 (양수: 상승, 음수: 하락)"""
        return self.previous_rank - self.current_rank

    @property
    def momentum_change(self) -> float:
        """모멘텀 변화"""
        return self.current_momentum - self.previous_momentum

    def to_dict(self) -> Dict:
        return {
            'sector': self.sector.value,
            'transition_type': self.transition_type.value,
            'direction': self.direction,
            'strength': self.strength,
            'rank_change': self.rank_change,
            'momentum_change': self.momentum_change,
            'description': self.description,
            'timestamp': self.timestamp.isoformat(),
        }


@dataclass
class TransitionConfig:
    """전환 감지 설정"""
    # 순위 변동 임계값
    rank_change_threshold: int = 3  # N위 이상 변동

    # 모멘텀 변화 임계값
    momentum_change_threshold: float = 20.0  # 점수 변화

    # 리더십 전환 감지
    leadership_lookback: int = 5  # 최근 N일 리더십 확인

    # 돌파/붕괴 감지
    breakout_threshold: float = 0.05  # 5% 이상 변화

    # 히스토리 보관
    history_size: int = 30


class TransitionDetector:
    """
    섹터 전환 감지기

    섹터 간 자금 이동 및 모멘텀 변화를 감지합니다.
    """

    def __init__(self, config: Optional[TransitionConfig] = None):
        self.config = config or TransitionConfig()

        # 섹터 지표 히스토리
        self._metrics_history: deque = deque(maxlen=self.config.history_size)

        # 순위 히스토리
        self._rank_history: deque = deque(maxlen=self.config.history_size)

        # 감지된 전환 신호
        self._signals: List[TransitionSignal] = []

    def update(
        self,
        metrics: Dict[Sector, SectorMetrics]
    ) -> List[TransitionSignal]:
        """
        지표 업데이트 및 전환 감지

        Args:
            metrics: 현재 섹터 지표

        Returns:
            감지된 전환 신호 리스트
        """
        signals = []

        # 이전 데이터가 있으면 전환 감지
        if len(self._metrics_history) > 0:
            previous_metrics = self._metrics_history[-1]
            signals = self._detect_transitions(previous_metrics, metrics)

        # 순위 계산 및 저장
        current_ranks = self._calculate_ranks(metrics)

        # 히스토리 업데이트
        self._metrics_history.append(metrics.copy())
        self._rank_history.append(current_ranks)

        # 신호 저장
        self._signals.extend(signals)

        return signals

    def _detect_transitions(
        self,
        previous: Dict[Sector, SectorMetrics],
        current: Dict[Sector, SectorMetrics]
    ) -> List[TransitionSignal]:
        """전환 감지"""
        signals = []

        # 순위 계산
        prev_ranks = self._calculate_ranks(previous)
        curr_ranks = self._calculate_ranks(current)

        for sector in current:
            if sector not in previous:
                continue

            prev_m = previous[sector]
            curr_m = current[sector]

            prev_rank = prev_ranks.get(sector, 99)
            curr_rank = curr_ranks.get(sector, 99)

            # 1. 순위 변동 감지
            rank_change = prev_rank - curr_rank
            if abs(rank_change) >= self.config.rank_change_threshold:
                signals.append(self._create_rank_signal(
                    sector, prev_rank, curr_rank, prev_m, curr_m
                ))

            # 2. 모멘텀 급변 감지
            momentum_change = curr_m.momentum_score - prev_m.momentum_score
            if abs(momentum_change) >= self.config.momentum_change_threshold:
                signals.append(self._create_momentum_signal(
                    sector, prev_m, curr_m
                ))

            # 3. 강/약세 반전 감지
            if self._detect_strength_reversal(prev_m, curr_m):
                signals.append(self._create_reversal_signal(
                    sector, prev_m, curr_m
                ))

        # 4. 리더십 전환 감지
        leadership_signal = self._detect_leadership_change(prev_ranks, curr_ranks, current)
        if leadership_signal:
            signals.append(leadership_signal)

        return signals

    def _calculate_ranks(
        self,
        metrics: Dict[Sector, SectorMetrics]
    ) -> Dict[Sector, int]:
        """섹터 순위 계산"""
        sorted_sectors = sorted(
            metrics.items(),
            key=lambda x: x[1].momentum_score,
            reverse=True
        )
        return {sector: rank + 1 for rank, (sector, _) in enumerate(sorted_sectors)}

    def _create_rank_signal(
        self,
        sector: Sector,
        prev_rank: int,
        curr_rank: int,
        prev_m: SectorMetrics,
        curr_m: SectorMetrics
    ) -> TransitionSignal:
        """순위 변동 신호 생성"""
        rank_change = prev_rank - curr_rank
        direction = 1 if rank_change > 0 else -1

        # 강도 계산 (순위 변화량 기반)
        strength = min(1.0, abs(rank_change) / 5)

        if rank_change > 0:
            description = f"{sector.value} 섹터 {abs(rank_change)}위 상승 ({prev_rank}→{curr_rank})"
        else:
            description = f"{sector.value} 섹터 {abs(rank_change)}위 하락 ({prev_rank}→{curr_rank})"

        return TransitionSignal(
            sector=sector,
            transition_type=TransitionType.RANK_CHANGE,
            direction=direction,
            strength=strength,
            previous_rank=prev_rank,
            current_rank=curr_rank,
            previous_momentum=prev_m.momentum_score,
            current_momentum=curr_m.momentum_score,
            description=description
        )

    def _create_momentum_signal(
        self,
        sector: Sector,
        prev_m: SectorMetrics,
        curr_m: SectorMetrics
    ) -> TransitionSignal:
        """모멘텀 변화 신호 생성"""
        momentum_change = curr_m.momentum_score - prev_m.momentum_score
        direction = 1 if momentum_change > 0 else -1

        strength = min(1.0, abs(momentum_change) / 50)

        if momentum_change > 0:
            description = f"{sector.value} 모멘텀 급등 ({prev_m.momentum_score:.1f}→{curr_m.momentum_score:.1f})"
            transition_type = TransitionType.BREAKOUT
        else:
            description = f"{sector.value} 모멘텀 급락 ({prev_m.momentum_score:.1f}→{curr_m.momentum_score:.1f})"
            transition_type = TransitionType.BREAKDOWN

        return TransitionSignal(
            sector=sector,
            transition_type=transition_type,
            direction=direction,
            strength=strength,
            previous_momentum=prev_m.momentum_score,
            current_momentum=curr_m.momentum_score,
            description=description
        )

    def _create_reversal_signal(
        self,
        sector: Sector,
        prev_m: SectorMetrics,
        curr_m: SectorMetrics
    ) -> TransitionSignal:
        """강/약세 반전 신호 생성"""
        # 강세→약세 또는 약세→강세 전환
        was_strong = prev_m.is_strong
        is_strong = curr_m.is_strong
        was_weak = prev_m.is_weak
        is_weak = curr_m.is_weak

        if was_weak and is_strong:
            direction = 1
            description = f"{sector.value} 약세→강세 반전"
        elif was_strong and is_weak:
            direction = -1
            description = f"{sector.value} 강세→약세 반전"
        else:
            direction = 1 if curr_m.momentum_score > prev_m.momentum_score else -1
            description = f"{sector.value} 추세 전환"

        return TransitionSignal(
            sector=sector,
            transition_type=TransitionType.STRENGTH_REVERSAL,
            direction=direction,
            strength=0.8,
            previous_momentum=prev_m.momentum_score,
            current_momentum=curr_m.momentum_score,
            description=description
        )

    def _detect_strength_reversal(
        self,
        prev_m: SectorMetrics,
        curr_m: SectorMetrics
    ) -> bool:
        """강/약세 반전 여부 감지"""
        # 강세→약세 전환
        if prev_m.is_strong and curr_m.is_weak:
            return True

        # 약세→강세 전환
        if prev_m.is_weak and curr_m.is_strong:
            return True

        # 중립에서 강/약세로 전환
        if not prev_m.is_strong and not prev_m.is_weak:
            if curr_m.is_strong or curr_m.is_weak:
                return True

        return False

    def _detect_leadership_change(
        self,
        prev_ranks: Dict[Sector, int],
        curr_ranks: Dict[Sector, int],
        current_metrics: Dict[Sector, SectorMetrics]
    ) -> Optional[TransitionSignal]:
        """리더십 전환 감지"""
        # 이전 1위
        prev_leader = min(prev_ranks.items(), key=lambda x: x[1])[0] if prev_ranks else None

        # 현재 1위
        curr_leader = min(curr_ranks.items(), key=lambda x: x[1])[0] if curr_ranks else None

        if prev_leader and curr_leader and prev_leader != curr_leader:
            curr_m = current_metrics.get(curr_leader)
            if curr_m:
                return TransitionSignal(
                    sector=curr_leader,
                    transition_type=TransitionType.LEADERSHIP_CHANGE,
                    direction=1,
                    strength=0.9,
                    previous_rank=prev_ranks.get(curr_leader, 99),
                    current_rank=1,
                    current_momentum=curr_m.momentum_score,
                    description=f"리더십 전환: {prev_leader.value}→{curr_leader.value}"
                )

        return None

    def get_recent_signals(
        self,
        n: int = 10,
        sector: Optional[Sector] = None,
        transition_type: Optional[TransitionType] = None
    ) -> List[TransitionSignal]:
        """최근 전환 신호 조회"""
        signals = self._signals[-n * 2:]  # 충분히 가져옴

        if sector:
            signals = [s for s in signals if s.sector == sector]

        if transition_type:
            signals = [s for s in signals if s.transition_type == transition_type]

        return signals[-n:]

    def get_sector_trend(
        self,
        sector: Sector
    ) -> Dict:
        """섹터 추세 분석"""
        if len(self._rank_history) < 2:
            return {'status': '데이터 부족'}

        # 최근 순위 추이
        ranks = [h.get(sector, 99) for h in self._rank_history]
        momenta = [
            h.get(sector).momentum_score if h.get(sector) else 0
            for h in self._metrics_history
        ]

        # 추세 계산
        if len(ranks) >= 5:
            rank_trend = np.polyfit(range(len(ranks)), ranks, 1)[0]
            momentum_trend = np.polyfit(range(len(momenta)), momenta, 1)[0]
        else:
            rank_trend = 0
            momentum_trend = 0

        return {
            'sector': sector.value,
            'current_rank': ranks[-1] if ranks else 0,
            'rank_trend': 'improving' if rank_trend < 0 else 'declining',
            'momentum_trend': 'positive' if momentum_trend > 0 else 'negative',
            'recent_ranks': ranks[-5:],
            'recent_momenta': momenta[-5:],
        }

    def get_rotation_summary(self) -> Dict:
        """로테이션 요약"""
        if len(self._rank_history) < 2:
            return {'status': '데이터 부족'}

        current_ranks = dict(self._rank_history[-1]) if self._rank_history else {}
        previous_ranks = dict(self._rank_history[-2]) if len(self._rank_history) > 1 else {}

        # 상승/하락 섹터
        rising = []
        falling = []

        for sector, curr_rank in current_ranks.items():
            prev_rank = previous_ranks.get(sector, curr_rank)
            change = prev_rank - curr_rank

            if change > 0:
                rising.append((sector.value, change))
            elif change < 0:
                falling.append((sector.value, abs(change)))

        return {
            'rising_sectors': sorted(rising, key=lambda x: x[1], reverse=True)[:3],
            'falling_sectors': sorted(falling, key=lambda x: x[1], reverse=True)[:3],
            'recent_signals': len([s for s in self._signals[-10:] if s.direction > 0]),
            'total_signals': len(self._signals),
        }

    def clear_history(self):
        """히스토리 초기화"""
        self._metrics_history.clear()
        self._rank_history.clear()
        self._signals.clear()
