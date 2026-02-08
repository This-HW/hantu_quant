#!/usr/bin/env python3
"""
RegimeAdjuster 테스트

테스트 대상:
- 시장 상황별 Kelly fraction 조정
- RegimeAdjustment dataclass
"""

import pytest
from core.risk.position.regime_adjuster import RegimeAdjuster, RegimeAdjustment
from core.market.market_regime import MarketRegime


class TestRegimeAdjuster:
    """RegimeAdjuster 테스트"""

    def test_adjustment_bull(self):
        """강세장: adjustment factor 1.0"""
        factor = RegimeAdjuster.get_adjustment(MarketRegime.BULL)
        assert factor == 1.0

    def test_adjustment_bear(self):
        """약세장: adjustment factor 0.5"""
        factor = RegimeAdjuster.get_adjustment(MarketRegime.BEAR)
        assert factor == 0.5

    def test_adjustment_sideways(self):
        """횡보장: adjustment factor 0.7"""
        factor = RegimeAdjuster.get_adjustment(MarketRegime.SIDEWAYS)
        assert factor == 0.7

    def test_adjustment_high_vol(self):
        """고변동성: adjustment factor 0.3"""
        factor = RegimeAdjuster.get_adjustment(MarketRegime.HIGH_VOLATILITY)
        assert factor == 0.3

    def test_adjust_kelly_bull(self):
        """강세장: Kelly fraction 유지"""
        kelly = 0.15
        adjustment = RegimeAdjuster.adjust_kelly(kelly, MarketRegime.BULL)

        assert adjustment.original_fraction == 0.15
        assert adjustment.adjusted_fraction == 0.15  # 1.0 * 0.15
        assert adjustment.regime == "bull"
        assert adjustment.adjustment_factor == 1.0

    def test_adjust_kelly_bear(self):
        """약세장: Kelly fraction 50% 감소"""
        kelly = 0.15
        adjustment = RegimeAdjuster.adjust_kelly(kelly, MarketRegime.BEAR)

        assert adjustment.original_fraction == 0.15
        assert adjustment.adjusted_fraction == 0.075  # 0.5 * 0.15
        assert adjustment.regime == "bear"
        assert adjustment.adjustment_factor == 0.5

    def test_adjust_kelly_high_vol(self):
        """고변동성: Kelly fraction 70% 감소"""
        kelly = 0.15
        adjustment = RegimeAdjuster.adjust_kelly(kelly, MarketRegime.HIGH_VOLATILITY)

        assert adjustment.original_fraction == 0.15
        assert adjustment.adjusted_fraction == 0.045  # 0.3 * 0.15
        assert adjustment.regime == "high_vol"
        assert adjustment.adjustment_factor == 0.3

    def test_regime_adjustment_result_fields(self):
        """RegimeAdjustment dataclass 필드 확인"""
        adjustment = RegimeAdjuster.adjust_kelly(0.20, MarketRegime.SIDEWAYS)

        # 필드 존재 확인
        assert hasattr(adjustment, "original_fraction")
        assert hasattr(adjustment, "adjusted_fraction")
        assert hasattr(adjustment, "regime")
        assert hasattr(adjustment, "adjustment_factor")

        # 값 확인
        assert adjustment.original_fraction == 0.20
        assert abs(adjustment.adjusted_fraction - 0.14) < 0.001  # 0.7 * 0.20
        assert adjustment.regime == "sideways"
        assert adjustment.adjustment_factor == 0.7
