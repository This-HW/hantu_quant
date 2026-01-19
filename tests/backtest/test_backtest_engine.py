"""
백테스트 엔진 테스트

핵심 기능 검증을 위한 단위 테스트입니다.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime

import sys
sys.path.insert(0, '/home/user/hantu_quant')

from core.backtest import (
    BacktestConfig,
    BacktestEngine,
    BacktestResult,
    BacktestStatus,
    Trade,
    MACrossStrategy,
    RSIMeanReversionStrategy,
    BollingerBreakoutStrategy,
    CombinedStrategy,
    CommissionConfig,
    SlippageConfig,
    RiskConfig,
    MetricsCalculator,
)


# ============== Fixtures ==============

@pytest.fixture
def sample_data():
    """샘플 OHLCV 데이터 생성"""
    np.random.seed(42)
    days = 200

    dates = pd.date_range(end=datetime.now(), periods=days, freq='B')

    # 상승 추세 데이터
    returns = np.random.randn(days) * 0.015
    price_mult = np.cumprod(1 + returns) * 1.2
    close = 50000 * price_mult

    df = pd.DataFrame({
        'open': close * (1 + np.random.randn(days) * 0.005),
        'high': close * (1 + np.abs(np.random.randn(days)) * 0.01),
        'low': close * (1 - np.abs(np.random.randn(days)) * 0.01),
        'close': close,
        'volume': np.random.randint(100000, 1000000, days)
    }, index=dates)

    df.attrs['stock_code'] = '005930'
    df.attrs['stock_name'] = '삼성전자'

    return {'005930': df}


@pytest.fixture
def multi_stock_data(sample_data):
    """여러 종목 데이터"""
    data = sample_data.copy()

    # 추가 종목 생성
    for code in ['035720', '000660']:
        np.random.seed(hash(code) % 2**31)
        base_df = sample_data['005930'].copy()
        base_df['close'] = base_df['close'] * (0.8 + np.random.random() * 0.4)
        base_df['open'] = base_df['close'] * (1 + np.random.randn(len(base_df)) * 0.005)
        base_df['high'] = base_df['close'] * (1 + np.abs(np.random.randn(len(base_df))) * 0.01)
        base_df['low'] = base_df['close'] * (1 - np.abs(np.random.randn(len(base_df))) * 0.01)
        base_df.attrs['stock_code'] = code
        base_df.attrs['stock_name'] = f'종목_{code}'
        data[code] = base_df

    return data


@pytest.fixture
def default_config():
    """기본 백테스트 설정"""
    return BacktestConfig(
        initial_capital=100_000_000,
        position_size_value=0.1,
        warmup_period=20
    )


# ============== Config Tests ==============

class TestBacktestConfig:
    """설정 테스트"""

    def test_default_config(self):
        """기본 설정 생성"""
        config = BacktestConfig()
        assert config.initial_capital == 100_000_000
        assert config.position_size_value == 0.05
        assert config.warmup_period == 20

    def test_custom_config(self):
        """커스텀 설정"""
        config = BacktestConfig(
            initial_capital=50_000_000,
            position_size_value=0.1
        )
        assert config.initial_capital == 50_000_000
        assert config.position_size_value == 0.1

    def test_invalid_capital(self):
        """잘못된 초기 자본금"""
        with pytest.raises(ValueError):
            BacktestConfig(initial_capital=-1000)

    def test_config_to_dict(self):
        """설정 딕셔너리 변환"""
        config = BacktestConfig()
        d = config.to_dict()
        assert 'initial_capital' in d
        assert 'position_size_value' in d


class TestCommissionConfig:
    """수수료 설정 테스트"""

    def test_buy_cost(self):
        """매수 비용 계산"""
        commission = CommissionConfig(buy_rate=0.00015)
        cost = commission.calculate_buy_cost(10_000_000)
        assert cost == pytest.approx(1500, rel=0.01)

    def test_sell_cost(self):
        """매도 비용 계산 (수수료 + 세금)"""
        commission = CommissionConfig(sell_rate=0.00015, tax_rate=0.0023)
        cost = commission.calculate_sell_cost(10_000_000)
        expected = 10_000_000 * 0.00015 + 10_000_000 * 0.0023
        assert cost == pytest.approx(expected, rel=0.01)


class TestSlippageConfig:
    """슬리피지 설정 테스트"""

    def test_buy_slippage(self):
        """매수 슬리피지 (가격 상승)"""
        slippage = SlippageConfig(value=0.001)
        price = slippage.apply_slippage(50000, is_buy=True)
        assert price > 50000
        assert price == pytest.approx(50050, rel=0.01)

    def test_sell_slippage(self):
        """매도 슬리피지 (가격 하락)"""
        slippage = SlippageConfig(value=0.001)
        price = slippage.apply_slippage(50000, is_buy=False)
        assert price < 50000
        assert price == pytest.approx(49950, rel=0.01)


# ============== Strategy Tests ==============

class TestMACrossStrategy:
    """이동평균 크로스 전략 테스트"""

    def test_strategy_creation(self):
        """전략 생성"""
        strategy = MACrossStrategy(short_period=5, long_period=20)
        assert strategy.short_period == 5
        assert strategy.long_period == 20

    def test_no_signal_insufficient_data(self, sample_data):
        """데이터 부족시 시그널 없음"""
        strategy = MACrossStrategy(short_period=5, long_period=20)
        short_data = sample_data['005930'].iloc[:15].copy()
        short_data.attrs['stock_code'] = '005930'

        signals = strategy.generate_signals(short_data, {})
        assert len(signals) == 0


class TestRSIStrategy:
    """RSI 전략 테스트"""

    def test_rsi_calculation(self):
        """RSI 계산"""
        strategy = RSIMeanReversionStrategy(rsi_period=14)

        # 상승 데이터
        prices = pd.Series([100 + i for i in range(20)])
        rsi = strategy._calculate_rsi(prices)

        # 상승장에서 RSI는 높아야 함
        assert rsi.iloc[-1] > 50


class TestBollingerStrategy:
    """볼린저 밴드 전략 테스트"""

    def test_bands_calculation(self):
        """밴드 계산"""
        strategy = BollingerBreakoutStrategy(period=20, std_dev=2.0)

        prices = pd.Series(np.random.randn(50).cumsum() + 100)
        upper, middle, lower = strategy._calculate_bands(prices)

        assert len(upper) == len(prices)
        # NaN 제외하고 비교 (처음 period-1 개는 NaN)
        valid_upper = upper.dropna()
        valid_middle = middle.dropna()
        valid_lower = lower.dropna()
        assert all(valid_upper > valid_middle)
        assert all(valid_middle > valid_lower)


class TestCombinedStrategy:
    """복합 전략 테스트"""

    def test_combined_creation(self):
        """복합 전략 생성"""
        strategies = [
            MACrossStrategy(),
            RSIMeanReversionStrategy()
        ]
        combined = CombinedStrategy(strategies, min_agreement=2)

        assert len(combined.strategies) == 2
        assert combined.min_agreement == 2


# ============== Engine Tests ==============

class TestBacktestEngine:
    """백테스트 엔진 테스트"""

    def test_engine_creation(self, default_config):
        """엔진 생성"""
        engine = BacktestEngine(default_config)
        assert engine.config == default_config
        assert engine.cash == default_config.initial_capital

    def test_basic_backtest(self, sample_data, default_config):
        """기본 백테스트 실행"""
        strategy = MACrossStrategy(short_period=5, long_period=20)
        engine = BacktestEngine(default_config)

        result = engine.run(strategy, sample_data)

        assert result.status == BacktestStatus.COMPLETED
        assert result.initial_capital == default_config.initial_capital
        assert result.final_capital > 0

    def test_multiple_stocks(self, multi_stock_data, default_config):
        """여러 종목 백테스트"""
        strategy = MACrossStrategy()
        engine = BacktestEngine(default_config)

        result = engine.run(strategy, multi_stock_data)

        assert result.status == BacktestStatus.COMPLETED
        assert len(result.daily_snapshots) > 0

    def test_result_metrics(self, sample_data, default_config):
        """결과 지표 검증"""
        strategy = MACrossStrategy()
        engine = BacktestEngine(default_config)

        result = engine.run(strategy, sample_data)

        # 기본 지표 존재 확인
        assert hasattr(result, 'total_return')
        assert hasattr(result, 'sharpe_ratio')
        assert hasattr(result, 'max_drawdown')
        assert hasattr(result, 'win_rate')

    def test_trades_recorded(self, sample_data, default_config):
        """거래 기록 확인"""
        strategy = MACrossStrategy()
        engine = BacktestEngine(default_config)

        result = engine.run(strategy, sample_data)

        # 거래 내역 확인
        assert isinstance(result.trades, list)
        if result.total_trades > 0:
            trade = result.trades[0]
            assert hasattr(trade, 'stock_code')
            assert hasattr(trade, 'entry_price')

    def test_daily_snapshots(self, sample_data, default_config):
        """일별 스냅샷 확인"""
        strategy = MACrossStrategy()
        engine = BacktestEngine(default_config)

        result = engine.run(strategy, sample_data)

        assert len(result.daily_snapshots) > 0
        snapshot = result.daily_snapshots[0]
        assert hasattr(snapshot, 'equity')
        assert hasattr(snapshot, 'cash')

    def test_commission_applied(self, sample_data):
        """수수료 적용 확인"""
        config = BacktestConfig(
            initial_capital=100_000_000,
            commission=CommissionConfig(buy_rate=0.001, sell_rate=0.001)
        )
        strategy = MACrossStrategy()
        engine = BacktestEngine(config)

        result = engine.run(strategy, sample_data)

        # 거래가 있으면 수수료도 있어야 함
        if result.total_trades > 0:
            assert result.total_commission > 0


# ============== Result Tests ==============

class TestBacktestResult:
    """백테스트 결과 테스트"""

    def test_result_creation(self):
        """결과 객체 생성"""
        result = BacktestResult(
            backtest_id='test001',
            strategy_name='Test Strategy',
            initial_capital=100_000_000
        )
        assert result.backtest_id == 'test001'
        assert result.status == BacktestStatus.PENDING

    def test_result_summary(self, sample_data, default_config):
        """결과 요약"""
        strategy = MACrossStrategy()
        engine = BacktestEngine(default_config)
        result = engine.run(strategy, sample_data)

        summary = result.summary()
        assert '백테스트 결과' in summary
        assert '총 수익률' in summary

    def test_result_to_dict(self, sample_data, default_config):
        """결과 딕셔너리 변환"""
        strategy = MACrossStrategy()
        engine = BacktestEngine(default_config)
        result = engine.run(strategy, sample_data)

        d = result.to_dict()
        assert 'total_return' in d
        assert 'sharpe_ratio' in d


class TestTrade:
    """거래 기록 테스트"""

    def test_trade_creation(self):
        """거래 객체 생성"""
        trade = Trade(
            trade_id=1,
            stock_code='005930',
            stock_name='삼성전자',
            entry_date='2024-01-01',
            entry_price=70000,
            entry_quantity=100
        )
        assert trade.trade_id == 1
        assert not trade.is_closed()

    def test_trade_closed(self):
        """거래 청산 확인"""
        trade = Trade(
            trade_id=1,
            stock_code='005930',
            stock_name='삼성전자',
            entry_date='2024-01-01',
            entry_price=70000,
            entry_quantity=100,
            exit_date='2024-01-10',
            exit_price=75000,
            exit_quantity=100,
            net_pnl=500000
        )
        assert trade.is_closed()
        assert trade.is_winner()


# ============== Metrics Tests ==============

class TestMetricsCalculator:
    """지표 계산기 테스트"""

    def test_calculate_metrics(self):
        """지표 계산"""
        # 샘플 자산 곡선
        dates = pd.date_range(start='2024-01-01', periods=100, freq='B')
        returns = np.random.randn(100) * 0.01 + 0.0005
        equity = 100_000_000 * np.cumprod(1 + returns)
        equity_curve = pd.Series(equity, index=dates)

        trades = []

        metrics = MetricsCalculator.calculate_all_metrics(
            equity_curve, trades, 100_000_000
        )

        assert 'total_return' in metrics
        assert 'sharpe_ratio' in metrics
        assert 'max_drawdown' in metrics

    def test_drawdown_calculation(self):
        """낙폭 계산"""
        # 상승 후 하락 패턴
        equity = pd.Series([100, 110, 120, 115, 110, 105, 115])

        metrics = MetricsCalculator.calculate_all_metrics(
            equity, [], 100
        )

        # MDD는 음수여야 함
        assert metrics['max_drawdown'] < 0


# ============== Integration Tests ==============

class TestIntegration:
    """통합 테스트"""

    def test_full_workflow(self, multi_stock_data):
        """전체 워크플로우"""
        # 설정
        config = BacktestConfig(
            initial_capital=100_000_000,
            position_size_value=0.05,
            risk=RiskConfig(
                max_positions=5,
                stop_loss_pct=0.03,
                take_profit_pct=0.08
            )
        )

        # 전략
        strategy = MACrossStrategy(short_period=5, long_period=20)

        # 백테스트
        engine = BacktestEngine(config)
        result = engine.run(strategy, multi_stock_data)

        # 검증
        assert result.status == BacktestStatus.COMPLETED
        assert result.final_capital > 0
        assert len(result.daily_snapshots) > 0

        # 지표 범위 검증
        assert -100 <= result.total_return <= 1000  # -100% ~ 1000%
        assert result.max_drawdown <= 0  # MDD는 0 이하
        assert 0 <= result.win_rate <= 100  # 승률 0~100%

    def test_strategy_comparison(self, multi_stock_data):
        """전략 비교"""
        config = BacktestConfig(initial_capital=100_000_000)

        strategies = [
            MACrossStrategy(5, 20),
            RSIMeanReversionStrategy(),
        ]

        results = []
        for strategy in strategies:
            engine = BacktestEngine(config)
            result = engine.run(strategy, multi_stock_data)
            results.append(result)

        # 모든 결과가 유효해야 함
        assert all(r.status == BacktestStatus.COMPLETED for r in results)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
