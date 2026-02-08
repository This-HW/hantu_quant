"""
켈리 공식 계산기 모듈

켈리 기준에 따른 최적 베팅 비율을 계산합니다.
"""

import numpy as np
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass

from core.utils.log_utils import get_logger

logger = get_logger(__name__)


@dataclass
class KellyConfig:
    """켈리 계산 설정"""
    # 켈리 조정 비율
    kelly_fraction: float = 0.5  # Half Kelly (보수적)

    # 포지션 제한
    max_position: float = 0.25  # 최대 25%
    min_position: float = 0.02  # 최소 2%

    # 신뢰구간 조정
    use_confidence_interval: bool = True
    confidence_level: float = 0.95

    # 샘플 요구사항
    min_trades: int = 30


@dataclass
class KellyResult:
    """켈리 계산 결과"""
    full_kelly: float = 0.0  # 완전 켈리 비율
    adjusted_kelly: float = 0.0  # 조정 켈리 비율
    final_position: float = 0.0  # 최종 포지션 비율

    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    win_loss_ratio: float = 0.0

    confidence_interval: Tuple[float, float] = (0.0, 0.0)
    sample_size: int = 0

    def to_dict(self) -> Dict:
        return {
            'full_kelly': self.full_kelly,
            'adjusted_kelly': self.adjusted_kelly,
            'final_position': self.final_position,
            'win_rate': self.win_rate,
            'avg_win': self.avg_win,
            'avg_loss': self.avg_loss,
            'win_loss_ratio': self.win_loss_ratio,
            'confidence_interval': self.confidence_interval,
            'sample_size': self.sample_size,
        }


class KellyCalculator:
    """
    켈리 공식 계산기

    거래 이력 기반으로 최적 포지션 크기를 계산합니다.

    켈리 공식:
    f* = (p * b - q) / b

    where:
        f* = 최적 베팅 비율
        p = 승리 확률
        b = 승리 시 수익률 / 패배 시 손실률 (win/loss ratio)
        q = 패배 확률 (1 - p)
    """

    def __init__(self, config: Optional[KellyConfig] = None):
        self.config = config or KellyConfig()

    def calculate(
        self,
        trade_returns: List[float],
        signal_confidence: float = 1.0
    ) -> KellyResult:
        """
        켈리 비율 계산

        Args:
            trade_returns: 과거 거래 수익률 리스트
            signal_confidence: 현재 신호 신뢰도 (0.0 ~ 1.0)

        Returns:
            KellyResult: 켈리 계산 결과
        """
        if len(trade_returns) < self.config.min_trades:
            return KellyResult(sample_size=len(trade_returns))

        # 승/패 분리
        wins = [r for r in trade_returns if r > 0]
        losses = [r for r in trade_returns if r <= 0]

        if not wins or not losses:
            return KellyResult(sample_size=len(trade_returns))

        # 기본 통계
        win_rate = len(wins) / len(trade_returns)
        avg_win = np.mean(wins)
        avg_loss = abs(np.mean(losses))

        # Win/Loss Ratio
        win_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 0

        # 기본 켈리 공식
        full_kelly = self._calculate_kelly(win_rate, win_loss_ratio)

        # 신뢰구간 조정
        confidence_interval = (0.0, 0.0)
        if self.config.use_confidence_interval:
            full_kelly, confidence_interval = self._adjust_for_uncertainty(
                trade_returns, win_rate, win_loss_ratio
            )

        # 조정 켈리 (Half Kelly 등)
        adjusted_kelly = full_kelly * self.config.kelly_fraction

        # 신호 신뢰도 반영
        adjusted_kelly *= signal_confidence

        # 최종 포지션 (제한 적용)
        final_position = np.clip(
            adjusted_kelly,
            self.config.min_position,
            self.config.max_position
        )

        return KellyResult(
            full_kelly=full_kelly,
            adjusted_kelly=adjusted_kelly,
            final_position=final_position,
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            win_loss_ratio=win_loss_ratio,
            confidence_interval=confidence_interval,
            sample_size=len(trade_returns)
        )

    def calculate_from_stats(
        self,
        win_rate: float,
        win_loss_ratio: float,
        signal_confidence: float = 1.0
    ) -> KellyResult:
        """
        통계값에서 직접 켈리 계산

        Args:
            win_rate: 승률 (0.0 ~ 1.0)
            win_loss_ratio: 평균 승리/손실 비율
            signal_confidence: 신호 신뢰도

        Returns:
            KellyResult: 켈리 계산 결과
        """
        full_kelly = self._calculate_kelly(win_rate, win_loss_ratio)
        adjusted_kelly = full_kelly * self.config.kelly_fraction * signal_confidence

        final_position = np.clip(
            adjusted_kelly,
            self.config.min_position,
            self.config.max_position
        )

        return KellyResult(
            full_kelly=full_kelly,
            adjusted_kelly=adjusted_kelly,
            final_position=final_position,
            win_rate=win_rate,
            win_loss_ratio=win_loss_ratio
        )

    def _calculate_kelly(self, win_rate: float, win_loss_ratio: float) -> float:
        """기본 켈리 공식"""
        if win_loss_ratio <= 0:
            return 0.0

        p = win_rate
        q = 1 - win_rate
        b = win_loss_ratio

        kelly = (p * b - q) / b

        # 음수 켈리는 0으로 (베팅하지 않음)
        return max(0.0, kelly)

    def _adjust_for_uncertainty(
        self,
        trade_returns: List[float],
        win_rate: float,
        win_loss_ratio: float
    ) -> Tuple[float, Tuple[float, float]]:
        """불확실성 조정"""
        n = len(trade_returns)

        # 승률 표준오차
        se_win_rate = np.sqrt(win_rate * (1 - win_rate) / n)

        # 신뢰구간 (z = 1.96 for 95%)
        z = 1.96
        lower_win_rate = max(0, win_rate - z * se_win_rate)
        upper_win_rate = min(1, win_rate + z * se_win_rate)

        # 보수적 켈리 (하위 신뢰구간 사용)
        conservative_kelly = self._calculate_kelly(lower_win_rate, win_loss_ratio)

        return conservative_kelly, (lower_win_rate, upper_win_rate)

    def estimate_optimal_fraction(
        self,
        trade_returns: List[float],
        fractions: List[float] = None
    ) -> Dict[str, float]:
        """
        최적 켈리 분율 추정

        다양한 켈리 분율에 대한 예상 성과 시뮬레이션
        """
        if fractions is None:
            fractions = [0.25, 0.5, 0.75, 1.0]

        results = {}
        original_fraction = self.config.kelly_fraction

        try:
            for fraction in fractions:
                self.config.kelly_fraction = fraction
                kelly_result = self.calculate(trade_returns)

                # 예상 복리 수익률
                expected_growth = self._estimate_growth_rate(
                    trade_returns,
                    kelly_result.final_position
                )

                results[f"kelly_{int(fraction * 100)}"] = {
                    'position': kelly_result.final_position,
                    'expected_growth': expected_growth,
                }
        finally:
            # State mutation 방지: 원래 값으로 복원
            self.config.kelly_fraction = original_fraction

        return results

    def _estimate_growth_rate(
        self,
        trade_returns: List[float],
        position_size: float
    ) -> float:
        """예상 복리 성장률"""
        # G = sum(log(1 + f * r_i)) / n
        log_returns = [
            np.log(1 + position_size * r)
            for r in trade_returns
            if (1 + position_size * r) > 0
        ]

        if not log_returns:
            return 0.0

        return np.mean(log_returns)
