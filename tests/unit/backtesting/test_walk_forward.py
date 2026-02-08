#!/usr/bin/env python3
"""
Walk-Forward Analysis 테스트

테스트 대상:
- WalkForwardConfig
- WalkForwardAnalyzer
- 윈도우 생성 로직
- 백테스트 실행 및 결과 집계
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch
from dataclasses import dataclass

from core.backtesting.walk_forward import (
    WalkForwardConfig,
    WalkForwardAnalyzer,
    WindowResult,
    WalkForwardResult,
)
from core.backtesting.strategy_backtester import BacktestResult


# Mock BacktestResult for testing
def create_mock_backtest_result(
    total_return=0.10,
    sharpe_ratio=1.5,
    total_trades=25,
    win_rate=0.6,
):
    """Mock BacktestResult 생성"""
    result = Mock(spec=BacktestResult)
    result.total_return = total_return
    result.sharpe_ratio = sharpe_ratio
    result.total_trades = total_trades
    result.win_rate = win_rate
    result.max_drawdown = -0.05
    result.profit_factor = 2.0
    return result


class TestWalkForwardConfig:
    """WalkForwardConfig 테스트"""

    def test_config_defaults(self):
        """기본 설정 확인"""
        config = WalkForwardConfig()

        assert config.train_window_days == 180
        assert config.test_window_days == 30
        assert config.step_days == 30
        assert config.min_train_trades == 20
        assert config.purge_days == 5

    def test_config_custom_values(self):
        """커스텀 설정 확인"""
        config = WalkForwardConfig(
            train_window_days=120,
            test_window_days=20,
            step_days=20,
            min_train_trades=15,
            purge_days=3,
        )

        assert config.train_window_days == 120
        assert config.test_window_days == 20
        assert config.step_days == 20
        assert config.min_train_trades == 15
        assert config.purge_days == 3


class TestWalkForwardAnalyzerValidation:
    """WalkForwardAnalyzer 입력 검증 테스트"""

    def test_validation_train_window_zero(self):
        """train_window_days가 0일 때 ValueError"""
        config = WalkForwardConfig(train_window_days=0)

        with pytest.raises(ValueError) as exc_info:
            WalkForwardAnalyzer(config)

        assert "train_window_days must be > 0" in str(exc_info.value)

    def test_validation_train_window_negative(self):
        """train_window_days가 음수일 때 ValueError"""
        config = WalkForwardConfig(train_window_days=-10)

        with pytest.raises(ValueError) as exc_info:
            WalkForwardAnalyzer(config)

        assert "train_window_days must be > 0" in str(exc_info.value)

    def test_validation_test_window_negative(self):
        """test_window_days가 음수일 때 ValueError"""
        config = WalkForwardConfig(test_window_days=-5)

        with pytest.raises(ValueError) as exc_info:
            WalkForwardAnalyzer(config)

        assert "test_window_days must be > 0" in str(exc_info.value)

    def test_validation_step_zero(self):
        """step_days가 0일 때 ValueError"""
        config = WalkForwardConfig(step_days=0)

        with pytest.raises(ValueError) as exc_info:
            WalkForwardAnalyzer(config)

        assert "step_days must be > 0" in str(exc_info.value)


class TestGenerateWindows:
    """윈도우 생성 테스트"""

    def test_generate_windows_basic(self):
        """기본 윈도우 생성 (6개월+1개월, 1년 데이터)"""
        config = WalkForwardConfig(
            train_window_days=180,
            test_window_days=30,
            step_days=30,
            purge_days=5,
        )
        analyzer = WalkForwardAnalyzer(config)

        # 1년 데이터 (2024-01-01 ~ 2024-12-31)
        windows = analyzer._generate_windows("2024-01-01", "2024-12-31")

        # 최소 1개 이상의 윈도우 생성
        assert len(windows) > 0

        # 첫 윈도우 확인
        train_start, train_end, test_start, test_end = windows[0]
        assert train_start == "2024-01-01"

        # train_end = 2024-01-01 + 179일
        expected_train_end = datetime(2024, 1, 1) + timedelta(days=179)
        assert train_end == expected_train_end.strftime("%Y-%m-%d")

        # test_start = train_end + purge_days + 1
        expected_test_start = expected_train_end + timedelta(days=6)
        assert test_start == expected_test_start.strftime("%Y-%m-%d")

    def test_generate_windows_clipping(self):
        """test_end가 end_date 넘으면 클리핑"""
        config = WalkForwardConfig(
            train_window_days=60, test_window_days=30, step_days=60, purge_days=0
        )
        analyzer = WalkForwardAnalyzer(config)

        # 짧은 기간 (100일)
        windows = analyzer._generate_windows("2024-01-01", "2024-04-10")

        # 마지막 윈도우의 test_end가 2024-04-10 이하
        if windows:
            _, _, _, last_test_end = windows[-1]
            assert last_test_end <= "2024-04-10"

    def test_generate_windows_no_room(self):
        """데이터 너무 짧으면 빈 리스트"""
        config = WalkForwardConfig(
            train_window_days=180, test_window_days=30, step_days=30, purge_days=5
        )
        analyzer = WalkForwardAnalyzer(config)

        # train + purge + test보다 짧은 기간
        windows = analyzer._generate_windows("2024-01-01", "2024-02-01")

        assert len(windows) == 0


class TestBacktestWindow:
    """윈도우별 백테스트 테스트"""

    def setup_method(self):
        """각 테스트 전 실행"""
        self.config = WalkForwardConfig(min_train_trades=20)
        self.analyzer = WalkForwardAnalyzer(self.config)

    def test_backtest_window_skip_low_trades(self):
        """min_train_trades 미달 시 None 반환"""
        # Mock backtester
        self.analyzer.backtester = Mock()
        self.analyzer.backtester.backtest_selection_strategy.return_value = (
            create_mock_backtest_result(total_trades=15)  # < 20
        )

        result = self.analyzer._backtest_window(
            window_index=1,
            train_start="2024-01-01",
            train_end="2024-06-30",
            test_start="2024-07-06",
            test_end="2024-08-05",
            selection_criteria={},
            trading_config={},
        )

        assert result is None

    def test_backtest_window_success(self):
        """정상 백테스트"""
        # Mock backtester
        self.analyzer.backtester = Mock()
        train_result = create_mock_backtest_result(
            total_return=0.15, sharpe_ratio=2.0, total_trades=30
        )
        test_result = create_mock_backtest_result(
            total_return=0.10, sharpe_ratio=1.0, total_trades=10
        )

        self.analyzer.backtester.backtest_selection_strategy.side_effect = [
            train_result,
            test_result,
        ]

        result = self.analyzer._backtest_window(
            window_index=1,
            train_start="2024-01-01",
            train_end="2024-06-30",
            test_start="2024-07-06",
            test_end="2024-08-05",
            selection_criteria={},
            trading_config={},
        )

        assert result is not None
        assert result.window_index == 1
        assert result.train_result.total_trades == 30
        assert result.test_result.total_trades == 10
        assert result.overfitting_ratio == 1.0 / 2.0  # test_sharpe / train_sharpe


class TestOverfittingRatio:
    """Overfitting Ratio 계산 테스트"""

    def setup_method(self):
        self.analyzer = WalkForwardAnalyzer()
        self.analyzer.backtester = Mock()

    def test_overfitting_ratio_calculation(self):
        """정상 Overfitting Ratio 계산"""
        train_result = create_mock_backtest_result(sharpe_ratio=2.0, total_trades=30)
        test_result = create_mock_backtest_result(sharpe_ratio=1.0, total_trades=10)

        self.analyzer.backtester.backtest_selection_strategy.side_effect = [
            train_result,
            test_result,
        ]

        result = self.analyzer._backtest_window(
            window_index=1,
            train_start="2024-01-01",
            train_end="2024-06-30",
            test_start="2024-07-06",
            test_end="2024-08-05",
            selection_criteria={},
            trading_config={},
        )

        assert result.overfitting_ratio == 0.5  # 1.0 / 2.0

    def test_overfitting_ratio_zero_train_sharpe(self):
        """train_sharpe=0일 때 ratio=0.0"""
        train_result = create_mock_backtest_result(sharpe_ratio=0.0, total_trades=30)
        test_result = create_mock_backtest_result(sharpe_ratio=1.0, total_trades=10)

        self.analyzer.backtester.backtest_selection_strategy.side_effect = [
            train_result,
            test_result,
        ]

        result = self.analyzer._backtest_window(
            window_index=1,
            train_start="2024-01-01",
            train_end="2024-06-30",
            test_start="2024-07-06",
            test_end="2024-08-05",
            selection_criteria={},
            trading_config={},
        )

        assert result.overfitting_ratio == 0.0


class TestAggregateResults:
    """결과 집계 테스트"""

    def setup_method(self):
        self.config = WalkForwardConfig()
        self.analyzer = WalkForwardAnalyzer(self.config)

    def test_aggregate_results(self):
        """여러 윈도우 결과 종합"""
        # Mock 윈도우 결과 생성
        windows = [
            WindowResult(
                window_index=1,
                train_start="2024-01-01",
                train_end="2024-06-30",
                test_start="2024-07-06",
                test_end="2024-08-05",
                train_result=create_mock_backtest_result(
                    total_return=0.15, sharpe_ratio=2.0
                ),
                test_result=create_mock_backtest_result(
                    total_return=0.10, sharpe_ratio=1.0
                ),
                overfitting_ratio=0.5,
            ),
            WindowResult(
                window_index=2,
                train_start="2024-02-01",
                train_end="2024-07-31",
                test_start="2024-08-06",
                test_end="2024-09-05",
                train_result=create_mock_backtest_result(
                    total_return=0.20, sharpe_ratio=2.5
                ),
                test_result=create_mock_backtest_result(
                    total_return=0.12, sharpe_ratio=1.5
                ),
                overfitting_ratio=0.6,
            ),
        ]

        result = self.analyzer._aggregate_results(windows, self.config)

        assert result.total_windows == 2
        assert result.valid_windows == 2
        assert result.avg_train_sharpe == 2.25  # (2.0 + 2.5) / 2
        assert result.avg_test_sharpe == 1.25  # (1.0 + 1.5) / 2
        assert result.avg_train_return == 0.175  # (0.15 + 0.20) / 2
        assert result.avg_test_return == 0.11  # (0.10 + 0.12) / 2

    def test_consistency_score(self):
        """test 수익률 표준편차"""
        windows = [
            WindowResult(
                window_index=1,
                train_start="",
                train_end="",
                test_start="",
                test_end="",
                train_result=create_mock_backtest_result(total_return=0.15),
                test_result=create_mock_backtest_result(total_return=0.10),
                overfitting_ratio=0.5,
            ),
            WindowResult(
                window_index=2,
                train_start="",
                train_end="",
                test_start="",
                test_end="",
                train_result=create_mock_backtest_result(total_return=0.20),
                test_result=create_mock_backtest_result(total_return=0.20),
                overfitting_ratio=0.6,
            ),
        ]

        result = self.analyzer._aggregate_results(windows, self.config)

        # consistency_score = stdev([0.10, 0.20])
        import statistics

        expected = statistics.stdev([0.10, 0.20])
        assert abs(result.consistency_score - expected) < 0.001


class TestRunFullFlow:
    """전체 플로우 테스트"""

    def test_run_empty_result(self):
        """유효 윈도우 0개일 때"""
        analyzer = WalkForwardAnalyzer()
        analyzer.backtester = Mock()

        # Train 거래 부족 (< 20)
        analyzer.backtester.backtest_selection_strategy.return_value = (
            create_mock_backtest_result(total_trades=5)
        )

        result = analyzer.run(
            start_date="2024-01-01",
            end_date="2024-12-31",
            selection_criteria={},
            trading_config={},
            strategy_name="test",
        )

        assert result.total_windows > 0  # 시도된 윈도우 수 반영
        assert result.valid_windows == 0
        assert result.avg_train_sharpe == 0.0
        assert result.avg_test_sharpe == 0.0

    @patch("core.backtesting.walk_forward.StrategyBacktester")
    def test_run_full_flow(self, MockBacktester):
        """전체 플로우 (mock backtester)"""
        # Mock 인스턴스
        mock_backtester_instance = Mock()
        MockBacktester.return_value = mock_backtester_instance

        # Train/Test 결과 교차 반환
        train_result = create_mock_backtest_result(
            total_return=0.15, sharpe_ratio=2.0, total_trades=30
        )
        test_result = create_mock_backtest_result(
            total_return=0.10, sharpe_ratio=1.0, total_trades=10
        )

        mock_backtester_instance.backtest_selection_strategy.side_effect = [
            train_result,
            test_result,
        ] * 10  # 여러 윈도우 대비

        # 짧은 기간 (윈도우 1개 생성)
        config = WalkForwardConfig(
            train_window_days=60, test_window_days=20, step_days=60, purge_days=0
        )
        analyzer = WalkForwardAnalyzer(config)

        result = analyzer.run(
            start_date="2024-01-01",
            end_date="2024-04-30",
            selection_criteria={"min_score": 70},
            trading_config={"position_size": 0.1},
            strategy_name="test_strategy",
        )

        # 최소 1개 윈도우 처리
        assert result.valid_windows >= 1
        assert result.avg_test_sharpe > 0
        assert result.overall_overfitting_ratio > 0
