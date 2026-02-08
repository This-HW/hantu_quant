#!/usr/bin/env python3
"""
PositionSizer Regime 조정 테스트

테스트 대상:
- calculate_position의 market_regime 파라미터
- Regime-adjusted Kelly 로직
"""

import pytest
from unittest.mock import Mock

from core.risk.position.position_sizer import PositionSizer, SizingConfig
from core.risk.position.kelly_calculator import KellyCalculator, KellyResult
from core.market.market_regime import MarketRegime


class TestPositionSizerRegime:
    """PositionSizer Regime 조정 테스트"""

    def setup_method(self):
        """각 테스트 전 실행"""
        self.config = SizingConfig(
            account_risk_per_trade=0.02,
            max_single_position=0.20,
            use_atr_sizing=False,
            use_volatility_scaling=False,
            use_signal_strength=False,
        )
        self.kelly = KellyCalculator()
        self.sizer = PositionSizer(self.config, self.kelly)

    def test_no_regime_backward_compatible(self):
        """market_regime=None일 때 기존 동작 동일"""
        # 과거 수익률 데이터 (30건 이상)
        trade_returns = [0.05, -0.02, 0.03, 0.01, -0.01] * 10

        result = self.sizer.calculate_position(
            portfolio_value=10000000,
            entry_price=50000,
            stop_loss=48000,
            trade_returns=trade_returns,
            market_regime=None,  # regime 미사용
        )

        # method에 'regime' 포함 안 됨
        assert "regime" not in result.method
        # 기본 Kelly 적용
        assert result.kelly_result is not None

    def test_regime_bull_kelly_unchanged(self):
        """강세장: Kelly multiplier 동일"""
        trade_returns = [0.05, -0.02, 0.03, 0.01, -0.01] * 10

        result_no_regime = self.sizer.calculate_position(
            portfolio_value=10000000,
            entry_price=50000,
            stop_loss=48000,
            trade_returns=trade_returns,
            market_regime=None,
        )

        result_bull = self.sizer.calculate_position(
            portfolio_value=10000000,
            entry_price=50000,
            stop_loss=48000,
            trade_returns=trade_returns,
            market_regime=MarketRegime.BULL,
        )

        # 강세장은 adjustment factor=1.0이므로 결과 동일
        assert result_bull.kelly_result is not None
        assert abs(result_bull.shares - result_no_regime.shares) <= 1
        # method에 'regime' 포함
        assert "regime" in result_bull.method

    def test_regime_bear_kelly_reduced(self):
        """약세장: Kelly multiplier 감소"""
        trade_returns = [0.05, -0.02, 0.03, 0.01, -0.01] * 10

        result_no_regime = self.sizer.calculate_position(
            portfolio_value=10000000,
            entry_price=50000,
            stop_loss=48000,
            trade_returns=trade_returns,
            market_regime=None,
        )

        result_bear = self.sizer.calculate_position(
            portfolio_value=10000000,
            entry_price=50000,
            stop_loss=48000,
            trade_returns=trade_returns,
            market_regime=MarketRegime.BEAR,
        )

        # 약세장은 adjustment factor=0.5이므로 포지션 감소
        assert result_bear.shares < result_no_regime.shares
        assert "regime" in result_bear.method

    def test_method_string_includes_regime(self):
        """method 문자열에 'regime' 포함"""
        trade_returns = [0.05, -0.02, 0.03, 0.01, -0.01] * 10

        result = self.sizer.calculate_position(
            portfolio_value=10000000,
            entry_price=50000,
            stop_loss=48000,
            trade_returns=trade_returns,
            market_regime=MarketRegime.SIDEWAYS,
        )

        assert "regime" in result.method

    def test_method_string_no_regime(self):
        """market_regime=None일 때 'regime' 미포함"""
        trade_returns = [0.05, -0.02, 0.03, 0.01, -0.01] * 10

        result = self.sizer.calculate_position(
            portfolio_value=10000000,
            entry_price=50000,
            stop_loss=48000,
            trade_returns=trade_returns,
            market_regime=None,
        )

        assert "regime" not in result.method

    def test_regime_with_insufficient_trades(self):
        """거래 30건 미만일 때 regime 무시 (Kelly 미사용)"""
        trade_returns = [0.05, -0.02, 0.03]  # < 30

        result = self.sizer.calculate_position(
            portfolio_value=10000000,
            entry_price=50000,
            stop_loss=48000,
            trade_returns=trade_returns,
            market_regime=MarketRegime.BEAR,
        )

        # Kelly 미사용
        assert result.kelly_result is None
        # regime도 적용 안 됨
        assert "regime" not in result.method

    def test_regime_high_vol_significant_reduction(self):
        """고변동성: 큰 폭 감소 (adjustment factor=0.3)"""
        trade_returns = [0.05, -0.02, 0.03, 0.01, -0.01] * 10

        result_no_regime = self.sizer.calculate_position(
            portfolio_value=10000000,
            entry_price=50000,
            stop_loss=48000,
            trade_returns=trade_returns,
            market_regime=None,
        )

        result_high_vol = self.sizer.calculate_position(
            portfolio_value=10000000,
            entry_price=50000,
            stop_loss=48000,
            trade_returns=trade_returns,
            market_regime=MarketRegime.HIGH_VOLATILITY,
        )

        # 고변동성은 adjustment factor=0.3이므로 큰 폭 감소
        assert result_high_vol.shares < result_no_regime.shares * 0.5
        assert "regime" in result_high_vol.method
