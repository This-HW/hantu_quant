"""
RetrainTrigger 단위 테스트

테스트 대상:
- A.1.1: RetrainTrigger 클래스
- A.1.2: 재학습 조건 정의
"""

import pytest

from core.learning.retrain.retrain_trigger import (
    RetrainTrigger,
    RetrainReason,
    RetrainConfig
)


class TestRetrainConfig:
    """재학습 설정 테스트"""

    def test_default_config(self):
        """기본 설정 값 확인"""
        config = RetrainConfig()
        assert config.min_feedback_count == 100
        assert config.accuracy_drop_threshold == 0.10
        assert config.max_days_without_retrain == 30
        assert config.min_days_between_retrain == 7

    def test_custom_config(self):
        """커스텀 설정"""
        config = RetrainConfig(
            min_feedback_count=50,
            accuracy_drop_threshold=0.05
        )
        assert config.min_feedback_count == 50
        assert config.accuracy_drop_threshold == 0.05

    def test_validate_success(self):
        """유효한 설정 검증"""
        config = RetrainConfig()
        is_valid, errors = config.validate()
        assert is_valid
        assert len(errors) == 0


class TestRetrainTrigger:
    """RetrainTrigger 테스트"""

    @pytest.fixture
    def trigger(self):
        """RetrainTrigger 인스턴스"""
        return RetrainTrigger()

    @pytest.fixture
    def sufficient_feedback_stats(self):
        """충분한 피드백 통계"""
        return {
            'processed_feedback': 150,
            'new_feedback_since_last_train': 60,
        }

    @pytest.fixture
    def good_model_performance(self):
        """좋은 모델 성능"""
        return {
            'accuracy': 0.70,
            'win_rate': 0.55,
            'sharpe_ratio': 1.0
        }

    def test_force_retrain(self, trigger):
        """강제 재학습 테스트"""
        result = trigger.should_retrain(
            feedback_stats={},
            model_performance={},
            force=True
        )

        assert result.should_retrain
        assert RetrainReason.MANUAL_REQUEST in result.reasons

    def test_record_retrain(self, trigger):
        """재학습 완료 기록"""
        trigger.record_retrain(accuracy=0.75)

        status = trigger.get_status()
        assert status['baseline_accuracy'] == 0.75
        assert status['last_retrain_date'] is not None

    def test_get_status(self, trigger):
        """상태 조회"""
        status = trigger.get_status()

        assert 'last_retrain_date' in status
        assert 'baseline_accuracy' in status
        assert 'in_cooldown' in status
        assert 'config' in status


class TestRetrainReason:
    """RetrainReason Enum 테스트"""

    def test_reason_values(self):
        """이유 값 확인"""
        assert RetrainReason.SUFFICIENT_FEEDBACK.value == "sufficient_feedback"
        assert RetrainReason.ACCURACY_DROP.value == "accuracy_drop"
        assert RetrainReason.TIME_BASED.value == "time_based"
        assert RetrainReason.PERFORMANCE_DEGRADATION.value == "performance_degradation"
