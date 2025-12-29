"""
RegimeDetector 단위 테스트

테스트 대상:
- C.2.1: 규칙 기반 레짐 판단
- C.2.2: 레짐 점수 계산
- C.2.3: 신뢰도 산출
- C.2.4: 레짐 변화 감지/알림
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from core.learning.regime.regime_detector import (
    RegimeDetector,
    RegimeResult,
    RegimeScore,
    get_regime_detector
)
from core.daily_selection.selection_criteria import MarketCondition
from core.learning.regime.market_indicator_collector import MarketIndicators

# 호환성 별칭
MarketRegime = MarketCondition


class TestMarketCondition:
    """MarketCondition Enum 테스트"""

    def test_regime_values(self):
        """레짐 값 확인"""
        assert MarketCondition.BULL_MARKET.value == "bull_market"
        assert MarketCondition.BEAR_MARKET.value == "bear_market"
        assert MarketCondition.SIDEWAYS.value == "sideways"
        assert MarketCondition.VOLATILE.value == "volatile"
        assert MarketCondition.RECOVERY.value == "recovery"


class TestRegimeDetector:
    """RegimeDetector 테스트"""

    @pytest.fixture
    def detector(self):
        """RegimeDetector 인스턴스"""
        return RegimeDetector()

    @pytest.fixture
    def bull_indicators(self):
        """상승장 지표"""
        return MarketIndicators(
            kospi_price=2800.0,
            kospi_change=0.02,
            kospi_20d_return=0.08,
            kosdaq_price=950.0,
            kosdaq_change=0.015,
            advance_decline_ratio=1.8,
            above_ma200_ratio=0.75,
            new_high_ratio=0.15,
            new_low_ratio=0.02,
            market_volatility=12.0,
            vkospi=15.0,
            fear_greed_score=75.0
        )

    @pytest.fixture
    def bear_indicators(self):
        """하락장 지표"""
        return MarketIndicators(
            kospi_price=2200.0,
            kospi_change=-0.025,
            kospi_20d_return=-0.12,
            kosdaq_price=700.0,
            kosdaq_change=-0.03,
            advance_decline_ratio=0.4,
            above_ma200_ratio=0.25,
            new_high_ratio=0.02,
            new_low_ratio=0.15,
            market_volatility=35.0,
            vkospi=40.0,
            fear_greed_score=20.0
        )

    def test_detect_returns_result(self, detector, bull_indicators):
        """레짐 탐지가 결과를 반환하는지 확인"""
        with patch.object(detector._indicator_collector, 'collect', return_value=bull_indicators):
            result = detector.detect()

        assert result is not None
        assert hasattr(result, 'detected_regime')
        assert hasattr(result, 'confidence')

    def test_confidence_range(self, detector, bull_indicators):
        """신뢰도 범위 확인"""
        with patch.object(detector._indicator_collector, 'collect', return_value=bull_indicators):
            result = detector.detect()

        assert 0.0 <= result.confidence <= 1.0

    def test_get_current_regime_initially_none(self, detector):
        """초기 상태에서 현재 레짐은 None"""
        assert detector.get_current_regime() is None

    def test_get_current_regime_after_detect(self, detector, bull_indicators):
        """탐지 후 현재 레짐 반환"""
        with patch.object(detector._indicator_collector, 'collect', return_value=bull_indicators):
            detector.detect()

        regime = detector.get_current_regime()
        assert regime is not None

    def test_get_status(self, detector):
        """상태 조회"""
        status = detector.get_status()
        assert 'current_regime' in status
        assert 'last_detection' in status

    def test_singleton_instance(self):
        """싱글톤 인스턴스 테스트"""
        instance1 = get_regime_detector()
        instance2 = get_regime_detector()
        assert instance1 is instance2
