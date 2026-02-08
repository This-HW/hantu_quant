"""
시장 상황별 Kelly fraction 조정 모듈

MarketRegime에 따라 Kelly fraction을 동적으로 조절합니다.
"""

from dataclasses import dataclass

from core.market.market_regime import MarketRegime
from core.utils.log_utils import get_logger

logger = get_logger(__name__)


@dataclass
class RegimeAdjustment:
    """Regime 조정 결과"""
    original_fraction: float
    adjusted_fraction: float
    regime: str
    adjustment_factor: float


class RegimeAdjuster:
    """시장 상황별 Kelly fraction 동적 조정"""

    ADJUSTMENT_MAP = {
        MarketRegime.BULL: 1.0,        # 강세장: 기본 유지
        MarketRegime.SIDEWAYS: 0.7,    # 횡보: 30% 감소
        MarketRegime.BEAR: 0.5,        # 약세장: 50% 감소
        MarketRegime.HIGH_VOLATILITY: 0.3,  # 고변동성: 70% 감소
    }

    @classmethod
    def get_adjustment(cls, regime: MarketRegime) -> float:
        """Regime에 따른 adjustment factor 반환 (0.3 ~ 1.0)

        Args:
            regime: 시장 체제

        Returns:
            조정 계수 (0.3 ~ 1.0)
        """
        factor = cls.ADJUSTMENT_MAP.get(regime)
        if factor is None:
            logger.warning(f"Unknown regime {regime}, using default factor 0.5")
            factor = 0.5
        else:
            logger.debug(f"Regime adjustment: {regime.value} → factor={factor}")
        return factor

    @classmethod
    def adjust_kelly(cls, kelly_fraction: float, regime: MarketRegime) -> RegimeAdjustment:
        """Kelly fraction에 regime 조정 적용

        Args:
            kelly_fraction: 원래 Kelly fraction
            regime: 시장 체제

        Returns:
            RegimeAdjustment: 조정 결과
        """
        factor = cls.get_adjustment(regime)
        adjusted = kelly_fraction * factor

        return RegimeAdjustment(
            original_fraction=kelly_fraction,
            adjusted_fraction=adjusted,
            regime=regime.value,
            adjustment_factor=factor
        )
