"""
선물 헤징 시스템 테스트 (P3-3)

테스트 항목:
1. 베타 계산
2. 시장 상황 감지
3. 헤지 신호 생성
4. 계약 수 계산
5. 포지션 관리
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import sys

# 프로젝트 루트 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.hedging.futures_hedger import (
    HedgeConfig,
    HedgePosition,
    HedgeSignal,
    HedgeAction,
    PortfolioBeta,
    FuturesHedger,
    MarketCondition,
    KOSPI200_FUTURES_MULTIPLIER,
    MARGIN_RATE,
    create_sample_portfolio,
    create_sample_market_data,
)


def create_test_stock_returns(days: int = 100, beta: float = 1.0) -> pd.Series:
    """테스트용 종목 수익률"""
    np.random.seed(42)
    dates = pd.date_range(end=datetime.now(), periods=days, freq='D')
    market_returns = np.random.randn(days) * 0.01
    stock_returns = market_returns * beta + np.random.randn(days) * 0.005
    return pd.Series(stock_returns, index=dates)


def create_test_market_returns(days: int = 100) -> pd.Series:
    """테스트용 시장 수익률"""
    np.random.seed(42)
    dates = pd.date_range(end=datetime.now(), periods=days, freq='D')
    returns = np.random.randn(days) * 0.01
    return pd.Series(returns, index=dates)


class TestHedgeConfig:
    """HedgeConfig 테스트"""

    def test_default_values(self):
        """기본값 확인"""
        config = HedgeConfig()

        assert config.max_portfolio_loss == 0.03
        assert config.vix_threshold == 25.0
        assert config.target_hedge_ratio == 0.5
        assert config.min_hedge_ratio == 0.3
        assert config.max_hedge_ratio == 1.0

    def test_custom_values(self):
        """사용자 설정"""
        config = HedgeConfig(
            max_portfolio_loss=0.05,
            target_hedge_ratio=0.7,
        )

        assert config.max_portfolio_loss == 0.05
        assert config.target_hedge_ratio == 0.7

    def test_hedge_ratios_by_condition(self):
        """시장 상황별 헤지 비율"""
        config = HedgeConfig()

        assert config.hedge_ratios_by_condition['bullish'] == 0.0
        assert config.hedge_ratios_by_condition['crisis'] == 1.0


class TestHedgePosition:
    """HedgePosition 테스트"""

    def test_create_position(self):
        """포지션 생성"""
        position = HedgePosition(
            contracts=-5,
            entry_price=350.0,
            entry_date=datetime.now(),
            margin_required=50_000_000,
        )

        assert position.contracts == -5
        assert position.entry_price == 350.0
        assert position.is_short

    def test_position_value(self):
        """포지션 가치"""
        position = HedgePosition(
            contracts=-5,
            entry_price=350.0,
            entry_date=datetime.now(),
            margin_required=50_000_000,
            current_price=350.0,
        )

        expected = 5 * 350.0 * KOSPI200_FUTURES_MULTIPLIER
        assert position.position_value == expected

    def test_update_price(self):
        """가격 업데이트"""
        position = HedgePosition(
            contracts=-5,
            entry_price=350.0,
            entry_date=datetime.now(),
            margin_required=50_000_000,
        )

        position.update_price(345.0)

        assert position.current_price == 345.0
        # 매도 포지션, 가격 하락 = 수익
        expected_pnl = 5 * 5.0 * KOSPI200_FUTURES_MULTIPLIER
        assert position.unrealized_pnl == expected_pnl

    def test_update_price_loss(self):
        """가격 상승시 손실"""
        position = HedgePosition(
            contracts=-5,
            entry_price=350.0,
            entry_date=datetime.now(),
            margin_required=50_000_000,
        )

        position.update_price(355.0)

        # 매도 포지션, 가격 상승 = 손실
        expected_pnl = 5 * (-5.0) * KOSPI200_FUTURES_MULTIPLIER
        assert position.unrealized_pnl == expected_pnl

    def test_to_dict(self):
        """딕셔너리 변환"""
        position = HedgePosition(
            contracts=-5,
            entry_price=350.0,
            entry_date=datetime.now(),
            margin_required=50_000_000,
        )

        d = position.to_dict()

        assert d['contracts'] == -5
        assert d['is_short'] is True
        assert 'entry_date' in d


class TestHedgeSignal:
    """HedgeSignal 테스트"""

    def test_create_signal(self):
        """신호 생성"""
        signal = HedgeSignal(
            action=HedgeAction.OPEN,
            contracts=5,
            target_hedge_ratio=0.5,
            reason="테스트",
            market_condition=MarketCondition.BEARISH,
            confidence=0.7,
        )

        assert signal.action == HedgeAction.OPEN
        assert signal.contracts == 5
        assert signal.should_hedge

    def test_should_hedge_open(self):
        """헤지 필요 여부 - OPEN"""
        signal = HedgeSignal(
            action=HedgeAction.OPEN,
            contracts=5,
            target_hedge_ratio=0.5,
            reason="테스트",
            market_condition=MarketCondition.BEARISH,
        )

        assert signal.should_hedge is True

    def test_should_hedge_hold(self):
        """헤지 필요 여부 - HOLD"""
        signal = HedgeSignal(
            action=HedgeAction.HOLD,
            contracts=0,
            target_hedge_ratio=0.5,
            reason="유지",
            market_condition=MarketCondition.NEUTRAL,
        )

        assert signal.should_hedge is False

    def test_to_dict(self):
        """딕셔너리 변환"""
        signal = HedgeSignal(
            action=HedgeAction.OPEN,
            contracts=5,
            target_hedge_ratio=0.5,
            reason="테스트",
            market_condition=MarketCondition.BEARISH,
        )

        d = signal.to_dict()

        assert d['action'] == 'open'
        assert d['market_condition'] == 'bearish'


class TestPortfolioBeta:
    """PortfolioBeta 테스트"""

    def test_create_beta(self):
        """베타 생성"""
        beta = PortfolioBeta(
            portfolio_beta=1.2,
            stock_betas={'005930': 1.1, '000660': 1.3},
            r_squared=0.85,
        )

        assert beta.portfolio_beta == 1.2
        assert len(beta.stock_betas) == 2

    def test_to_dict(self):
        """딕셔너리 변환"""
        beta = PortfolioBeta(
            portfolio_beta=1.2,
            stock_betas={'005930': 1.1},
            r_squared=0.85,
        )

        d = beta.to_dict()

        assert d['portfolio_beta'] == 1.2
        assert 'calculation_date' in d


class TestFuturesHedger:
    """FuturesHedger 테스트"""

    def test_init(self):
        """초기화"""
        hedger = FuturesHedger()

        assert hedger.config is not None
        assert hedger.current_position is None
        assert len(hedger.trade_history) == 0

    def test_init_custom_config(self):
        """사용자 설정으로 초기화"""
        config = HedgeConfig(target_hedge_ratio=0.7)
        hedger = FuturesHedger(config=config)

        assert hedger.config.target_hedge_ratio == 0.7

    def test_calculate_stock_beta(self):
        """개별 종목 베타 계산"""
        hedger = FuturesHedger()

        stock_returns = create_test_stock_returns(100, beta=1.2)
        market_returns = create_test_market_returns(100)

        beta, r_sq = hedger.calculate_stock_beta(stock_returns, market_returns)

        # 시뮬레이션된 데이터이므로 정확히 1.2는 아님
        assert 0.5 < beta < 2.0
        assert 0 <= r_sq <= 1

    def test_calculate_stock_beta_insufficient_data(self):
        """데이터 부족시"""
        hedger = FuturesHedger()

        stock_returns = create_test_stock_returns(10, beta=1.0)
        market_returns = create_test_market_returns(10)

        beta, r_sq = hedger.calculate_stock_beta(stock_returns, market_returns)

        # 데이터 부족시 기본값 반환
        assert beta == 1.0
        assert r_sq == 0.0


class TestMarketCondition:
    """시장 상황 감지 테스트"""

    def test_detect_bullish(self):
        """상승장 감지"""
        hedger = FuturesHedger()

        # 상승 추세 데이터
        df = create_sample_market_data(100)
        df['close'] = df['close'] * np.linspace(0.9, 1.1, 100)

        condition = hedger.detect_market_condition(df, vix=12)

        assert condition in [MarketCondition.BULLISH, MarketCondition.NEUTRAL]

    def test_detect_bearish(self):
        """하락장 감지"""
        hedger = FuturesHedger()

        # 하락 추세 데이터
        df = create_sample_market_data(100)
        df['close'] = df['close'] * np.linspace(1.1, 0.93, 100)

        condition = hedger.detect_market_condition(df, vix=28)

        assert condition in [MarketCondition.BEARISH, MarketCondition.CRISIS]

    def test_detect_crisis(self):
        """급락장 감지"""
        hedger = FuturesHedger()

        # 급락 데이터
        df = create_sample_market_data(100)
        df['close'] = df['close'] * np.linspace(1.0, 0.90, 100)

        condition = hedger.detect_market_condition(df, vix=40)

        assert condition == MarketCondition.CRISIS

    def test_detect_neutral(self):
        """보합장 감지"""
        hedger = FuturesHedger()

        # 보합 데이터
        df = create_sample_market_data(100)

        condition = hedger.detect_market_condition(df)

        assert condition in [MarketCondition.NEUTRAL, MarketCondition.BULLISH, MarketCondition.BEARISH]


class TestHedgeContractCalculation:
    """헤지 계약 수 계산 테스트"""

    def test_calculate_hedge_contracts(self):
        """계약 수 계산"""
        hedger = FuturesHedger()

        contracts = hedger.calculate_hedge_contracts(
            portfolio_value=100_000_000,  # 1억
            portfolio_beta=1.0,
            futures_price=350.0,
            hedge_ratio=1.0,  # 100% 헤지
        )

        # 1억 / (350 * 250,000) = 1.14 → 1계약
        expected = int(round(100_000_000 / (350 * KOSPI200_FUTURES_MULTIPLIER)))
        assert contracts == expected

    def test_calculate_hedge_contracts_partial(self):
        """부분 헤지"""
        hedger = FuturesHedger()

        contracts = hedger.calculate_hedge_contracts(
            portfolio_value=500_000_000,  # 5억
            portfolio_beta=1.2,
            futures_price=350.0,
            hedge_ratio=0.5,  # 50% 헤지
        )

        # 5억 * 1.2 * 0.5 / (350 * 250,000) = 3.43 → 3계약
        expected_value = 500_000_000 * 1.2 * 0.5
        expected = int(round(expected_value / (350 * KOSPI200_FUTURES_MULTIPLIER)))
        assert contracts == expected

    def test_calculate_margin_required(self):
        """필요 증거금 계산"""
        hedger = FuturesHedger()

        margin = hedger.calculate_margin_required(
            contracts=5,
            futures_price=350.0,
        )

        expected = 5 * 350 * KOSPI200_FUTURES_MULTIPLIER * MARGIN_RATE
        assert margin == expected


class TestHedgeSignalGeneration:
    """헤지 신호 생성 테스트"""

    def test_get_hedge_signal_bearish(self):
        """하락장에서 헤지 신호"""
        hedger = FuturesHedger()

        # 하락 추세 데이터
        df = create_sample_market_data(100)
        df['close'] = df['close'] * np.linspace(1.1, 0.95, 100)

        signal = hedger.get_hedge_signal(
            portfolio_value=100_000_000,
            portfolio_beta=1.0,
            market_data=df,
            current_loss=-0.02,
            vix=26,
        )

        assert signal.action in [HedgeAction.OPEN, HedgeAction.INCREASE]
        assert signal.target_hedge_ratio > 0

    def test_get_hedge_signal_with_loss(self):
        """손실 발생시 헤지 강화"""
        hedger = FuturesHedger()
        df = create_sample_market_data(100)

        signal_no_loss = hedger.get_hedge_signal(
            portfolio_value=100_000_000,
            portfolio_beta=1.0,
            market_data=df,
            current_loss=0.0,
        )

        signal_with_loss = hedger.get_hedge_signal(
            portfolio_value=100_000_000,
            portfolio_beta=1.0,
            market_data=df,
            current_loss=-0.05,  # 5% 손실
        )

        # 손실이 크면 헤지 비율 증가
        assert signal_with_loss.target_hedge_ratio >= signal_no_loss.target_hedge_ratio


class TestHedgePositionManagement:
    """헤지 포지션 관리 테스트"""

    def test_open_hedge(self):
        """헤지 오픈"""
        hedger = FuturesHedger()

        signal = HedgeSignal(
            action=HedgeAction.OPEN,
            contracts=5,
            target_hedge_ratio=0.5,
            reason="테스트",
            market_condition=MarketCondition.BEARISH,
        )

        position = hedger.open_hedge(signal, futures_price=350.0)

        assert position is not None
        assert position.contracts == -5  # 매도 포지션
        assert position.entry_price == 350.0
        assert hedger.current_position is not None
        assert len(hedger.trade_history) == 1

    def test_close_hedge(self):
        """헤지 청산"""
        hedger = FuturesHedger()

        # 먼저 오픈
        signal = HedgeSignal(
            action=HedgeAction.OPEN,
            contracts=5,
            target_hedge_ratio=0.5,
            reason="테스트",
            market_condition=MarketCondition.BEARISH,
        )
        hedger.open_hedge(signal, futures_price=350.0)

        # 청산 (가격 하락 = 수익)
        pnl = hedger.close_hedge(futures_price=345.0)

        assert pnl is not None
        assert pnl > 0  # 매도 후 가격 하락 = 수익
        assert hedger.current_position is None
        assert len(hedger.trade_history) == 2

    def test_close_hedge_with_loss(self):
        """헤지 손실 청산"""
        hedger = FuturesHedger()

        # 오픈
        signal = HedgeSignal(
            action=HedgeAction.OPEN,
            contracts=5,
            target_hedge_ratio=0.5,
            reason="테스트",
            market_condition=MarketCondition.BEARISH,
        )
        hedger.open_hedge(signal, futures_price=350.0)

        # 청산 (가격 상승 = 손실)
        pnl = hedger.close_hedge(futures_price=355.0)

        assert pnl is not None
        assert pnl < 0  # 매도 후 가격 상승 = 손실

    def test_adjust_hedge_increase(self):
        """헤지 확대"""
        hedger = FuturesHedger()

        # 초기 오픈
        open_signal = HedgeSignal(
            action=HedgeAction.OPEN,
            contracts=3,
            target_hedge_ratio=0.3,
            reason="초기",
            market_condition=MarketCondition.BEARISH,
        )
        hedger.open_hedge(open_signal, futures_price=350.0)

        # 확대
        increase_signal = HedgeSignal(
            action=HedgeAction.INCREASE,
            contracts=2,
            target_hedge_ratio=0.5,
            reason="확대",
            market_condition=MarketCondition.CRISIS,
        )
        new_contracts = hedger.adjust_hedge(increase_signal, futures_price=348.0)

        assert new_contracts == -5  # -3 + (-2) = -5

    def test_no_position_to_close(self):
        """포지션 없이 청산 시도"""
        hedger = FuturesHedger()

        pnl = hedger.close_hedge(futures_price=350.0)

        assert pnl is None


class TestHedgeStats:
    """헤지 통계 테스트"""

    def test_get_hedge_stats_empty(self):
        """빈 통계"""
        hedger = FuturesHedger()

        stats = hedger.get_hedge_stats()

        assert stats['total_trades'] == 0
        assert stats['current_position'] is None

    def test_get_hedge_stats_with_trades(self):
        """거래 후 통계"""
        hedger = FuturesHedger()

        # 몇 번 거래
        signal = HedgeSignal(
            action=HedgeAction.OPEN,
            contracts=5,
            target_hedge_ratio=0.5,
            reason="테스트",
            market_condition=MarketCondition.BEARISH,
        )
        hedger.open_hedge(signal, futures_price=350.0)
        hedger.close_hedge(futures_price=345.0)

        stats = hedger.get_hedge_stats()

        assert stats['total_trades'] == 2
        assert stats['closed_trades'] == 1
        assert stats['total_pnl'] > 0

    def test_update_position_price(self):
        """포지션 가격 업데이트"""
        hedger = FuturesHedger()

        signal = HedgeSignal(
            action=HedgeAction.OPEN,
            contracts=5,
            target_hedge_ratio=0.5,
            reason="테스트",
            market_condition=MarketCondition.BEARISH,
        )
        hedger.open_hedge(signal, futures_price=350.0)

        hedger.update_position_price(348.0)

        assert hedger.current_position.current_price == 348.0
        assert hedger.current_position.unrealized_pnl > 0


class TestSampleData:
    """샘플 데이터 생성 테스트"""

    def test_create_sample_portfolio(self):
        """샘플 포트폴리오"""
        portfolio = create_sample_portfolio()

        assert len(portfolio) == 5
        assert '005930' in portfolio

        # 비중 합계 = 1
        total_weight = sum(p['weight'] for p in portfolio.values())
        assert abs(total_weight - 1.0) < 0.01

    def test_create_sample_market_data(self):
        """샘플 시장 데이터"""
        df = create_sample_market_data(100)

        assert len(df) == 100
        assert 'open' in df.columns
        assert 'close' in df.columns


class TestMarketConditionEnum:
    """MarketCondition Enum 테스트"""

    def test_enum_values(self):
        """Enum 값"""
        assert MarketCondition.BULLISH.value == "bullish"
        assert MarketCondition.CRISIS.value == "crisis"


class TestHedgeActionEnum:
    """HedgeAction Enum 테스트"""

    def test_enum_values(self):
        """Enum 값"""
        assert HedgeAction.OPEN.value == "open"
        assert HedgeAction.CLOSE.value == "close"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
