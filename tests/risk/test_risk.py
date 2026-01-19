"""
리스크 관리 시스템 테스트

KellyCalculator, PositionSizer, CorrelationMatrix, DrawdownMonitor 테스트
"""

import pytest
import pandas as pd
import numpy as np

from core.risk.position import (
    KellyCalculator, KellyConfig, KellyResult,
    PositionSizer, PositionSize, SizingConfig
)
from core.risk.correlation import (
    CorrelationMatrix, CorrelationResult,
    DiversificationScore, DiversificationResult,
    PortfolioOptimizer, OptimizationResult
)
from core.risk.drawdown import (
    DrawdownMonitor, DrawdownStatus, DrawdownConfig,
    CircuitBreaker, BreakerConfig,
    PositionReducer, ReductionPlan
)
from core.risk.drawdown.drawdown_monitor import AlertLevel
from core.risk.drawdown.circuit_breaker import BreakerState
from core.risk.drawdown.position_reducer import ReductionPriority, PositionInfo


# ========== Fixtures ==========

@pytest.fixture
def winning_trades():
    """승률 높은 거래 수익률"""
    np.random.seed(42)
    # 승률 60%, 평균 수익 3%, 평균 손실 2%
    returns = []
    for _ in range(100):
        if np.random.random() < 0.6:
            returns.append(np.random.uniform(0.01, 0.05))
        else:
            returns.append(np.random.uniform(-0.04, -0.01))
    return returns


@pytest.fixture
def losing_trades():
    """승률 낮은 거래 수익률"""
    np.random.seed(123)
    returns = []
    for _ in range(100):
        if np.random.random() < 0.35:
            returns.append(np.random.uniform(0.01, 0.03))
        else:
            returns.append(np.random.uniform(-0.05, -0.02))
    return returns


@pytest.fixture
def sample_price_data():
    """샘플 가격 데이터"""
    np.random.seed(42)
    n = 252

    stocks = {}
    for code in ['005930', '000660', '005380', '035720']:
        dates = pd.date_range(start='2024-01-01', periods=n, freq='D')
        base_price = 50000 + np.random.randint(-10000, 10000)

        prices = []
        price = base_price
        for _ in range(n):
            price = price * (1 + np.random.randn() * 0.02)
            prices.append(max(price, 10000))

        close = np.array(prices)
        stocks[code] = pd.DataFrame({
            'open': close * 0.99,
            'high': close * 1.01,
            'low': close * 0.98,
            'close': close,
            'volume': np.random.randint(100000, 1000000, n)
        }, index=dates)

    return stocks


@pytest.fixture
def sample_positions():
    """샘플 포지션"""
    return {
        '005930': 0.30,
        '000660': 0.25,
        '005380': 0.25,
        '035720': 0.20,
    }


# ========== Kelly Calculator Tests ==========

class TestKellyCalculator:
    """KellyCalculator 테스트"""

    def test_calculator_creation(self):
        """계산기 생성 테스트"""
        config = KellyConfig(kelly_fraction=0.5)
        calc = KellyCalculator(config)
        assert calc.config.kelly_fraction == 0.5

    def test_calculate_with_winning_trades(self, winning_trades):
        """승률 높은 거래 켈리 계산"""
        calc = KellyCalculator()
        result = calc.calculate(winning_trades)

        assert isinstance(result, KellyResult)
        assert result.win_rate > 0.5
        assert result.full_kelly > 0
        assert result.final_position > 0

    def test_calculate_with_losing_trades(self, losing_trades):
        """승률 낮은 거래 켈리 계산"""
        calc = KellyCalculator()
        result = calc.calculate(losing_trades)

        # 손실 많으면 낮은 켈리
        assert result.full_kelly <= 0.2 or result.final_position <= 0.1

    def test_calculate_from_stats(self):
        """통계값에서 직접 계산"""
        calc = KellyCalculator()
        result = calc.calculate_from_stats(
            win_rate=0.55,
            win_loss_ratio=1.5,
            signal_confidence=0.8
        )

        assert result.final_position > 0
        assert result.final_position <= 0.25

    def test_kelly_constraints(self, winning_trades):
        """켈리 제약 조건 테스트"""
        config = KellyConfig(max_position=0.15, min_position=0.05)
        calc = KellyCalculator(config)
        result = calc.calculate(winning_trades)

        assert result.final_position <= 0.15
        if result.final_position > 0:
            assert result.final_position >= 0.05

    def test_insufficient_data(self):
        """데이터 부족 테스트"""
        calc = KellyCalculator()
        result = calc.calculate([0.02, 0.03, -0.01])

        assert result.sample_size == 3
        assert result.final_position == 0.0


# ========== Position Sizer Tests ==========

class TestPositionSizer:
    """PositionSizer 테스트"""

    def test_sizer_creation(self):
        """사이저 생성 테스트"""
        config = SizingConfig(account_risk_per_trade=0.02)
        sizer = PositionSizer(config)
        assert sizer.config.account_risk_per_trade == 0.02

    def test_basic_position_calculation(self):
        """기본 포지션 계산"""
        sizer = PositionSizer()

        result = sizer.calculate_position(
            portfolio_value=100000000,
            entry_price=50000,
            stop_loss=47500,  # 5% 손절
            signal_strength=1.0
        )

        assert isinstance(result, PositionSize)
        assert result.position_pct > 0
        assert result.shares > 0
        assert result.amount > 0

    def test_atr_based_sizing(self, sample_price_data):
        """ATR 기반 사이징"""
        config = SizingConfig(use_atr_sizing=True)
        sizer = PositionSizer(config)

        result = sizer.calculate_position(
            portfolio_value=100000000,
            entry_price=50000,
            stop_loss=47000,
            atr=1500,  # ATR = 1500
            signal_strength=1.0
        )

        assert result.position_pct > 0

    def test_volatility_scaling(self):
        """변동성 스케일링 테스트"""
        config = SizingConfig(use_volatility_scaling=True, target_volatility=0.15)
        sizer = PositionSizer(config)

        # 낮은 변동성 -> 큰 포지션
        low_vol_result = sizer.calculate_position(
            portfolio_value=100000000,
            entry_price=50000,
            stop_loss=47500,
            volatility=0.10,
            signal_strength=1.0
        )

        # 높은 변동성 -> 작은 포지션
        high_vol_result = sizer.calculate_position(
            portfolio_value=100000000,
            entry_price=50000,
            stop_loss=47500,
            volatility=0.30,
            signal_strength=1.0
        )

        assert low_vol_result.position_pct >= high_vol_result.position_pct

    def test_stop_loss_calculation(self):
        """손절가 계산 테스트"""
        sizer = PositionSizer()

        stop = sizer.calculate_stop_loss(
            entry_price=50000,
            atr=1500,
            method='atr'
        )

        # ATR 2배 = 3000 아래
        assert stop < 50000
        assert stop == 50000 - 1500 * 2


# ========== Correlation Matrix Tests ==========

class TestCorrelationMatrix:
    """CorrelationMatrix 테스트"""

    def test_matrix_creation(self):
        """매트릭스 생성 테스트"""
        matrix = CorrelationMatrix(lookback_days=60)
        assert matrix.lookback_days == 60

    def test_calculate_correlation(self, sample_price_data):
        """상관관계 계산 테스트"""
        matrix = CorrelationMatrix()
        result = matrix.calculate(sample_price_data)

        assert isinstance(result, CorrelationResult)
        assert result.correlation_matrix is not None
        assert len(result.correlation_matrix) == len(sample_price_data)

    def test_avg_correlation(self, sample_price_data):
        """평균 상관관계 테스트"""
        matrix = CorrelationMatrix()
        result = matrix.calculate(sample_price_data)

        assert -1 <= result.avg_correlation <= 1

    def test_high_correlation_pairs(self, sample_price_data):
        """고상관 쌍 테스트"""
        matrix = CorrelationMatrix(high_correlation_threshold=0.5)
        result = matrix.calculate(sample_price_data)

        assert isinstance(result.high_correlation_pairs, list)

    def test_pairwise_correlation(self, sample_price_data):
        """쌍별 상관관계 테스트"""
        matrix = CorrelationMatrix()
        corr = matrix.get_pairwise_correlation(
            sample_price_data,
            '005930',
            '000660'
        )

        assert -1 <= corr <= 1


# ========== Diversification Score Tests ==========

class TestDiversificationScore:
    """DiversificationScore 테스트"""

    def test_score_creation(self):
        """점수 계산기 생성 테스트"""
        score = DiversificationScore()
        assert score is not None

    def test_calculate_score(self, sample_positions, sample_price_data):
        """분산 점수 계산"""
        scorer = DiversificationScore()
        result = scorer.calculate(sample_positions, sample_price_data)

        assert isinstance(result, DiversificationResult)
        assert 0 <= result.score <= 1

    def test_score_with_sector_mapping(self, sample_positions, sample_price_data):
        """섹터 매핑 포함 점수"""
        scorer = DiversificationScore()
        sector_mapping = {
            '005930': 'SEMICONDUCTOR',
            '000660': 'SEMICONDUCTOR',
            '005380': 'AUTOMOTIVE',
            '035720': 'INTERNET',
        }

        result = scorer.calculate(
            sample_positions,
            sample_price_data,
            sector_mapping
        )

        # 반도체에 집중되어 있으므로 권고 있을 수 있음
        assert isinstance(result.recommendations, list)

    def test_effective_n(self, sample_positions, sample_price_data):
        """유효 종목 수 테스트"""
        scorer = DiversificationScore()
        result = scorer.calculate(sample_positions, sample_price_data)

        # 유효 N은 1 ~ 실제 종목 수 사이
        assert 1 <= result.effective_n <= len(sample_positions)


# ========== Portfolio Optimizer Tests ==========

class TestPortfolioOptimizer:
    """PortfolioOptimizer 테스트"""

    def test_optimizer_creation(self):
        """최적화기 생성 테스트"""
        optimizer = PortfolioOptimizer(risk_free_rate=0.03)
        assert optimizer.risk_free_rate == 0.03

    def test_min_variance_optimization(self, sample_price_data):
        """최소 분산 최적화"""
        optimizer = PortfolioOptimizer()
        result = optimizer.optimize_min_variance(sample_price_data)

        assert isinstance(result, OptimizationResult)
        assert len(result.weights) == len(sample_price_data)

        # 가중치 합 = 1
        total_weight = sum(result.weights.values())
        assert abs(total_weight - 1.0) < 0.01

    def test_max_sharpe_optimization(self, sample_price_data):
        """최대 샤프 최적화"""
        optimizer = PortfolioOptimizer()
        result = optimizer.optimize_max_sharpe(sample_price_data)

        assert len(result.weights) > 0
        total_weight = sum(result.weights.values())
        assert abs(total_weight - 1.0) < 0.01

    def test_risk_parity_optimization(self, sample_price_data):
        """리스크 패리티 최적화"""
        optimizer = PortfolioOptimizer()
        result = optimizer.optimize_risk_parity(sample_price_data)

        assert len(result.weights) > 0

    def test_compare_methods(self, sample_price_data):
        """방법 비교 테스트"""
        optimizer = PortfolioOptimizer()
        results = optimizer.compare_methods(sample_price_data)

        assert 'min_variance' in results
        assert 'max_sharpe' in results
        assert 'risk_parity' in results


# ========== Drawdown Monitor Tests ==========

class TestDrawdownMonitor:
    """DrawdownMonitor 테스트"""

    def test_monitor_creation(self):
        """모니터 생성 테스트"""
        config = DrawdownConfig(warning_threshold=0.10)
        monitor = DrawdownMonitor(config)
        assert monitor.config.warning_threshold == 0.10

    def test_update_with_growth(self):
        """상승 시 업데이트"""
        monitor = DrawdownMonitor()

        # 초기 값
        status1 = monitor.update(100000)
        status2 = monitor.update(105000)  # 5% 상승

        assert status2.current_drawdown == 0.0
        assert status2.peak_value == 105000

    def test_update_with_decline(self):
        """하락 시 업데이트"""
        monitor = DrawdownMonitor()

        monitor.update(100000)
        monitor.update(110000)  # 피크
        status = monitor.update(99000)  # 10% 하락

        assert status.current_drawdown > 0
        assert status.peak_value == 110000

    def test_alert_levels(self):
        """경고 수준 테스트"""
        config = DrawdownConfig(
            caution_threshold=0.05,
            warning_threshold=0.10,
            critical_threshold=0.15
        )
        monitor = DrawdownMonitor(config)

        monitor.update(100000)  # 피크
        status = monitor.update(88000)  # 12% 하락

        assert status.alert_level == AlertLevel.WARNING

    def test_drawdown_history(self):
        """드로다운 히스토리 테스트"""
        monitor = DrawdownMonitor()

        for i in range(10):
            monitor.update(100000 + i * 1000)

        history = monitor.get_drawdown_history()
        assert len(history) == 10


# ========== Circuit Breaker Tests ==========

class TestCircuitBreaker:
    """CircuitBreaker 테스트"""

    def test_breaker_creation(self):
        """브레이커 생성 테스트"""
        config = BreakerConfig(max_daily_loss=0.03)
        breaker = CircuitBreaker(config)
        assert breaker.config.max_daily_loss == 0.03

    def test_no_trigger_normal(self):
        """정상 상태 테스트"""
        breaker = CircuitBreaker()

        status = DrawdownStatus(
            daily_drawdown=0.01,
            weekly_drawdown=0.02,
            current_drawdown=0.03
        )

        result = breaker.check(status)
        assert result.state == BreakerState.ACTIVE
        assert result.can_trade is True

    def test_trigger_on_daily_loss(self):
        """일간 손실 발동 테스트"""
        config = BreakerConfig(max_daily_loss=0.03)
        breaker = CircuitBreaker(config)

        status = DrawdownStatus(
            daily_drawdown=0.04,  # 4% > 3%
            weekly_drawdown=0.05,
            current_drawdown=0.08
        )

        result = breaker.check(status)
        assert result.state == BreakerState.TRIGGERED
        assert result.current_stage >= 1

    def test_trigger_on_max_drawdown(self):
        """최대 낙폭 발동 테스트"""
        config = BreakerConfig(max_drawdown=0.15)
        breaker = CircuitBreaker(config)

        status = DrawdownStatus(
            daily_drawdown=0.02,
            weekly_drawdown=0.05,
            current_drawdown=0.16  # 16% > 15%
        )

        result = breaker.check(status)
        assert result.current_stage == 3
        assert result.can_trade is False

    def test_force_trigger(self):
        """강제 발동 테스트"""
        breaker = CircuitBreaker()
        breaker.force_trigger("테스트", stage=2)

        assert breaker._state == BreakerState.TRIGGERED
        assert breaker._current_stage == 2

    def test_force_release(self):
        """강제 해제 테스트"""
        breaker = CircuitBreaker()
        breaker.force_trigger("테스트")
        breaker.force_release("테스트 해제")

        assert breaker.is_active is True


# ========== Position Reducer Tests ==========

class TestPositionReducer:
    """PositionReducer 테스트"""

    def test_reducer_creation(self):
        """리듀서 생성 테스트"""
        reducer = PositionReducer(min_position_value=100000)
        assert reducer.min_position_value == 100000

    def test_create_reduction_plan(self):
        """축소 계획 생성 테스트"""
        reducer = PositionReducer()

        positions = {
            '005930': PositionInfo(
                stock_code='005930',
                current_value=30000000,
                current_weight=0.30,
                unrealized_pnl_pct=-0.05
            ),
            '000660': PositionInfo(
                stock_code='000660',
                current_value=25000000,
                current_weight=0.25,
                unrealized_pnl_pct=0.03
            ),
        }

        plan = reducer.create_reduction_plan(
            positions=positions,
            target_reduction_pct=0.30,
            strategy=ReductionPriority.WORST_PERFORMER
        )

        assert isinstance(plan, ReductionPlan)
        assert len(plan.orders) > 0

    def test_emergency_liquidation(self):
        """긴급 청산 테스트"""
        reducer = PositionReducer()

        positions = {
            '005930': PositionInfo(
                stock_code='005930',
                current_value=30000000,
                current_weight=0.50
            ),
            '000660': PositionInfo(
                stock_code='000660',
                current_value=30000000,
                current_weight=0.50
            ),
        }

        plan = reducer.create_emergency_liquidation(positions)

        assert plan.total_reduction_pct == 1.0
        assert len(plan.orders) == 2

    def test_reduction_recommendation(self):
        """축소 권고 테스트"""
        reducer = PositionReducer()

        positions = {
            '005930': PositionInfo(
                stock_code='005930',
                current_value=50000000,
                current_weight=1.0
            ),
        }

        # 낮은 드로다운
        rec_low = reducer.get_reduction_recommendation(positions, 0.05, 0.15)
        assert rec_low['action'] == 'NONE'

        # 높은 드로다운
        rec_high = reducer.get_reduction_recommendation(positions, 0.14, 0.15)
        assert rec_high['action'] in ['REDUCE', 'EMERGENCY']


# ========== Integration Tests ==========

class TestRiskIntegration:
    """리스크 관리 통합 테스트"""

    def test_full_risk_pipeline(self, sample_price_data, sample_positions):
        """전체 리스크 파이프라인"""
        # 1. 상관관계 분석
        corr_matrix = CorrelationMatrix()
        corr_result = corr_matrix.calculate(sample_price_data)

        # 2. 분산투자 점수
        div_scorer = DiversificationScore(corr_matrix)
        div_result = div_scorer.calculate(sample_positions, sample_price_data)

        # 3. 포트폴리오 최적화
        optimizer = PortfolioOptimizer()
        opt_result = optimizer.optimize_min_variance(sample_price_data)

        # 4. 드로다운 모니터링
        dd_monitor = DrawdownMonitor()
        dd_status = dd_monitor.update(100000000)

        # 5. 서킷브레이커 체크
        breaker = CircuitBreaker()
        breaker_status = breaker.check(dd_status)

        # 검증
        assert corr_result.avg_correlation is not None
        assert 0 <= div_result.score <= 1
        assert len(opt_result.weights) > 0
        assert breaker_status.can_trade is True

    def test_position_sizing_with_kelly(self, winning_trades):
        """켈리와 포지션 사이징 통합"""
        kelly = KellyCalculator()
        sizer = PositionSizer(kelly_calculator=kelly)

        result = sizer.calculate_position(
            portfolio_value=100000000,
            entry_price=50000,
            stop_loss=47500,
            signal_strength=1.0,
            trade_returns=winning_trades
        )

        assert result.position_pct > 0
        assert result.kelly_result is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
