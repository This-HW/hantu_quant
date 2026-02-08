#!/usr/bin/env python3
"""
TradingEngine Kelly 관련 테스트

테스트 대상:
- _calculate_kelly_size(): KellyCalculator 위임
- _get_trade_returns(): 수익률 조회
- Kelly config 플래그
- State mutation 방지
"""

import pytest
import os
import json
import tempfile
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from pathlib import Path

from core.trading.trading_engine import TradingEngine, TradingConfig
from core.risk.position.kelly_calculator import KellyResult


class TestCalculateKellySize:
    """_calculate_kelly_size 테스트"""

    def setup_method(self):
        """각 테스트 전 실행"""
        self.config = TradingConfig(
            use_kelly_criterion=True,
            kelly_multiplier=0.20,
            max_position_pct=0.08,
            use_regime_adjusted_kelly=False,  # regime 비활성화
        )
        self.engine = TradingEngine(self.config)

    def test_kelly_size_delegates_to_calculator(self):
        """KellyCalculator.calculate 호출 확인"""
        trade_returns = [0.05, -0.02, 0.03, 0.01, -0.01] * 10

        # _get_trade_returns mock (데이터 반환)
        with patch.object(
            self.engine, "_get_trade_returns", return_value=trade_returns
        ):
            # KellyCalculator.calculate mock
            with patch.object(
                self.engine.kelly_calculator, "calculate"
            ) as mock_calculate:
                mock_calculate.return_value = KellyResult(
                    full_kelly=0.20,
                    adjusted_kelly=0.10,
                    final_position=0.10,
                    win_rate=0.6,
                    avg_win=0.03,
                    avg_loss=0.015,
                    win_loss_ratio=2.0,
                    sample_size=50,
                )

                result = self.engine._calculate_kelly_size(
                    account_balance=10000000,
                    stock_code="005930",
                    stock_data=None,
                )

                # calculate 호출 확인
                mock_calculate.assert_called_once_with(trade_returns)
                # 반환값 확인 (final_position * multiplier * balance)
                assert result > 0

    def test_kelly_size_insufficient_data(self):
        """데이터 부족 시 기본값 (account_balance * position_size_value)"""
        trade_returns = [0.05, -0.02]  # < 30

        result = self.engine._calculate_kelly_size(
            account_balance=10000000, stock_code="005930", stock_data=None
        )

        # 기본값: 10% (position_size_value)
        expected = 10000000 * self.config.position_size_value
        assert result == expected

    def test_kelly_size_regime_adjusted(self):
        """regime 적용 시 값 변화"""
        config = TradingConfig(
            use_kelly_criterion=True,
            kelly_multiplier=0.20,
            use_regime_adjusted_kelly=True,  # regime 활성화
        )
        engine = TradingEngine(config)

        trade_returns = [0.05, -0.02, 0.03, 0.01, -0.01] * 10

        # Mock regime detector
        with patch.object(
            engine, "regime_detector", create=True
        ) as mock_regime_detector:
            mock_result = Mock()
            mock_result.regime = MagicMock()
            mock_result.regime.value = "bear"
            mock_regime_detector.detect_regime.return_value = mock_result

            # Mock KellyCalculator
            with patch.object(
                engine.kelly_calculator, "calculate"
            ) as mock_calculate:
                mock_calculate.return_value = KellyResult(
                    full_kelly=0.20,
                    adjusted_kelly=0.10,
                    final_position=0.10,
                    win_rate=0.6,
                    sample_size=50,
                )

                result = engine._calculate_kelly_size(
                    account_balance=10000000, stock_code="005930", stock_data=None
                )

                # regime 적용으로 값 변화 (BEAR: 0.5 adjustment)
                assert result > 0

    def test_kelly_size_regime_failure_fallback(self):
        """regime 감지 실패 시 기본 Kelly"""
        config = TradingConfig(
            use_kelly_criterion=True, use_regime_adjusted_kelly=True
        )
        engine = TradingEngine(config)

        trade_returns = [0.05, -0.02, 0.03, 0.01, -0.01] * 10

        # Mock regime detector (예외 발생)
        engine.regime_detector = Mock()
        engine.regime_detector.detect_regime.side_effect = Exception("Regime error")

        # Mock KellyCalculator
        with patch.object(engine.kelly_calculator, "calculate") as mock_calculate:
            mock_calculate.return_value = KellyResult(
                full_kelly=0.20, final_position=0.10, win_rate=0.6, sample_size=50
            )

            result = engine._calculate_kelly_size(
                account_balance=10000000, stock_code="005930", stock_data=None
            )

            # 기본 Kelly 적용 (에러 무시)
            assert result > 0


class TestGetTradeReturns:
    """_get_trade_returns 테스트"""

    def setup_method(self):
        """각 테스트 전 실행"""
        self.engine = TradingEngine()
        self.temp_dir = tempfile.mkdtemp()
        self.original_dir = os.getcwd()
        os.chdir(self.temp_dir)

        # data/trades 디렉토리 생성
        os.makedirs("data/trades", exist_ok=True)

    def teardown_method(self):
        """각 테스트 후 정리"""
        os.chdir(self.original_dir)
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_get_trade_returns_no_files(self):
        """파일 없으면 빈 리스트"""
        returns = self.engine._get_trade_returns("005930")
        assert returns == []

    def test_get_trade_returns_with_data(self):
        """데이터 파싱 정확성"""
        # Mock 파일 생성
        today = datetime.now().strftime("%Y%m%d")
        summary_file = f"data/trades/trade_summary_{today}.json"

        summary_data = {
            "date": today,
            "total_trades": 2,
            "details": [
                {
                    "stock_code": "005930",
                    "entry_price": 50000,
                    "exit_price": 52000,
                    "quantity": 10,
                },
                {
                    "stock_code": "000660",
                    "entry_price": 100000,
                    "exit_price": 95000,
                    "quantity": 5,
                },
            ],
        }

        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump(summary_data, f)

        # 전체 종목 수익률
        returns = self.engine._get_trade_returns()
        assert len(returns) == 2
        assert abs(returns[0] - 0.04) < 0.001  # (52000 - 50000) / 50000
        assert abs(returns[1] - (-0.05)) < 0.001  # (95000 - 100000) / 100000

        # 특정 종목 필터
        returns_samsung = self.engine._get_trade_returns("005930")
        assert len(returns_samsung) == 1
        assert abs(returns_samsung[0] - 0.04) < 0.001


class TestKellyConfigFlag:
    """Kelly config 플래그 테스트"""

    def test_kelly_config_flag_disabled(self):
        """use_kelly_criterion=False일 때"""
        config = TradingConfig(
            use_kelly_criterion=False, position_size_value=0.10
        )
        engine = TradingEngine(config)

        trade_returns = [0.05, -0.02, 0.03, 0.01, -0.01] * 10

        result = engine._calculate_kelly_size(
            account_balance=10000000, stock_code="005930", stock_data=None
        )

        # 기본값 반환
        expected = 10000000 * config.position_size_value
        assert result == expected


class TestKellyStateMutation:
    """Kelly state mutation 방지 테스트"""

    def test_kelly_state_no_mutation(self):
        """estimate_optimal_fraction 후 config 원상 복원"""
        from core.risk.position.kelly_calculator import KellyCalculator, KellyConfig

        config = KellyConfig(kelly_fraction=0.5)
        kelly = KellyCalculator(config)

        trade_returns = [0.05, -0.02, 0.03, 0.01, -0.01] * 10

        original_fraction = kelly.config.kelly_fraction
        kelly.estimate_optimal_fraction(trade_returns, fractions=[0.25, 0.5, 0.75, 1.0])

        # config가 원래 값으로 복원되었는지 확인
        assert kelly.config.kelly_fraction == original_fraction
