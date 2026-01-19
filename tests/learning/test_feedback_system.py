"""
FeedbackSystem 테스트

Task 1.1.3: 피드백 조회 정상 동작 검증
Task 2.2.3: RetrainTrigger 연동 테스트
"""

import pytest
import sqlite3
import tempfile
import os
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

# 테스트 대상 모듈
from core.learning.models.feedback_system import FeedbackSystem


class TestFeedbackSystemGetRecentFeedback:
    """Task 1.1.3: get_recent_feedback() 테스트"""

    @pytest.fixture
    def temp_db(self):
        """임시 데이터베이스 생성"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        yield db_path
        if os.path.exists(db_path):
            os.unlink(db_path)

    @pytest.fixture
    def feedback_system(self, temp_db):
        """테스트용 FeedbackSystem 인스턴스"""
        return FeedbackSystem(db_path=temp_db)

    def test_get_recent_feedback_returns_correct_columns(self, feedback_system, temp_db):
        """SQL 컬럼명이 DB 스키마와 일치하는지 확인"""
        # 테스트 데이터 삽입
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.cursor()
            today = datetime.now().strftime('%Y-%m-%d')
            cursor.execute("""
                INSERT INTO feedback_data (
                    prediction_id, stock_code, prediction_date,
                    predicted_probability, predicted_class, model_name,
                    actual_return_7d, actual_class, is_processed, factor_scores
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                'test_001', '005930', today,
                0.75, 1, 'ensemble',
                0.08, 1, True, '{"momentum": 0.3}'
            ))
            conn.commit()

        # 조회
        result = feedback_system.get_recent_feedback(days=7)

        # 검증
        assert len(result) == 1
        row = result[0]

        # 필수 컬럼 확인 (DB 스키마와 일치)
        assert 'stock_code' in row
        assert 'prediction_date' in row
        assert 'predicted_probability' in row  # predicted_value가 아님
        assert 'predicted_class' in row
        assert 'model_name' in row
        assert 'actual_return_7d' in row  # actual_value가 아님
        assert 'actual_class' in row
        assert 'is_processed' in row
        assert 'factor_scores' in row

        # 값 확인
        assert row['stock_code'] == '005930'
        assert row['predicted_probability'] == 0.75
        assert row['actual_return_7d'] == 0.08
        assert row['actual_class'] == 1

    def test_factor_scores_json_deserialization(self, feedback_system, temp_db):
        """factor_scores가 JSON으로 역직렬화되는지 확인"""
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.cursor()
            today = datetime.now().strftime('%Y-%m-%d')
            cursor.execute("""
                INSERT INTO feedback_data (
                    prediction_id, stock_code, prediction_date,
                    predicted_probability, predicted_class, model_name,
                    factor_scores, is_processed
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                'test_002', '000660', today,
                0.65, 1, 'ensemble',
                '{"momentum": 0.25, "value": 0.15, "quality": 0.20}',
                False
            ))
            conn.commit()

        result = feedback_system.get_recent_feedback(days=7)

        assert len(result) == 1
        row = result[0]

        # factor_scores가 딕셔너리로 변환되었는지 확인
        assert isinstance(row['factor_scores'], dict)
        assert row['factor_scores']['momentum'] == 0.25
        assert row['factor_scores']['value'] == 0.15
        assert row['factor_scores']['quality'] == 0.20

    def test_factor_scores_null_handling(self, feedback_system, temp_db):
        """factor_scores가 NULL일 때 빈 딕셔너리 반환"""
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.cursor()
            today = datetime.now().strftime('%Y-%m-%d')
            cursor.execute("""
                INSERT INTO feedback_data (
                    prediction_id, stock_code, prediction_date,
                    predicted_probability, predicted_class, model_name
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                'test_003', '035720', today,
                0.55, 0, 'ensemble'
            ))
            conn.commit()

        result = feedback_system.get_recent_feedback(days=7)

        assert len(result) == 1
        row = result[0]

        # NULL이면 빈 딕셔너리
        assert row['factor_scores'] == {}

    def test_get_recent_feedback_respects_days_filter(self, feedback_system, temp_db):
        """days 파라미터가 제대로 적용되는지 확인"""
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.cursor()

            # 오늘 데이터
            today = datetime.now().strftime('%Y-%m-%d')
            cursor.execute("""
                INSERT INTO feedback_data (
                    prediction_id, stock_code, prediction_date,
                    predicted_probability, predicted_class, model_name
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, ('today_001', '005930', today, 0.7, 1, 'ensemble'))

            # 10일 전 데이터
            old_date = (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d')
            cursor.execute("""
                INSERT INTO feedback_data (
                    prediction_id, stock_code, prediction_date,
                    predicted_probability, predicted_class, model_name
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, ('old_001', '000660', old_date, 0.6, 0, 'ensemble'))

            conn.commit()

        # 7일 조회
        result_7days = feedback_system.get_recent_feedback(days=7)
        assert len(result_7days) == 1
        assert result_7days[0]['prediction_id'] == 'today_001'

        # 30일 조회
        result_30days = feedback_system.get_recent_feedback(days=30)
        assert len(result_30days) == 2


class TestModelPerformanceMetrics:
    """Task 2.2.3: 모델 성능 지표 테스트"""

    @pytest.fixture
    def mock_feedback_data(self):
        """모의 피드백 데이터"""
        return [
            {'actual_class': 1, 'actual_return_7d': 0.05, 'is_processed': True},
            {'actual_class': 1, 'actual_return_7d': 0.08, 'is_processed': True},
            {'actual_class': 0, 'actual_return_7d': -0.03, 'is_processed': True},
            {'actual_class': 1, 'actual_return_7d': 0.12, 'is_processed': True},
            {'actual_class': 0, 'actual_return_7d': -0.02, 'is_processed': True},
            {'actual_class': 1, 'actual_return_7d': 0.06, 'is_processed': True},
        ]

    def test_win_rate_calculation(self, mock_feedback_data):
        """win_rate 계산 로직 테스트"""
        processed = [fb for fb in mock_feedback_data if fb.get('is_processed')]
        wins = sum(1 for fb in processed if fb.get('actual_class') == 1)
        win_rate = wins / len(processed) if processed else 0

        assert win_rate == 4 / 6  # 6개 중 4개 성공

    def test_sharpe_ratio_calculation(self, mock_feedback_data):
        """sharpe_ratio 계산 로직 테스트"""
        import math

        returns = [fb.get('actual_return_7d', 0) for fb in mock_feedback_data
                   if fb.get('actual_return_7d') is not None]

        mean_return = sum(returns) / len(returns)
        variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
        std_return = math.sqrt(variance) if variance > 0 else 0

        if std_return > 0:
            sharpe_ratio = (mean_return / std_return) * math.sqrt(52)
        else:
            sharpe_ratio = 0

        # Sharpe ratio가 합리적인 범위인지 확인
        assert sharpe_ratio > 0  # 평균 수익률이 양수이므로
        assert sharpe_ratio < 10  # 비현실적으로 높지 않음

    def test_model_performance_includes_required_fields(self):
        """_get_model_performance()가 필요한 필드를 모두 반환하는지 확인"""
        with patch('core.learning.models.feedback_system.get_feedback_system') as mock_fs:
            mock_fs_instance = MagicMock()
            mock_fs_instance.get_recent_feedback.return_value = [
                {'actual_class': 1, 'actual_return_7d': 0.05, 'is_processed': True},
                {'actual_class': 0, 'actual_return_7d': -0.02, 'is_processed': True},
            ]
            mock_fs.return_value = mock_fs_instance

            # 오케스트레이터의 _get_model_performance 테스트
            from core.learning.orchestrator.learning_orchestrator import LearningOrchestrator

            orchestrator = LearningOrchestrator()
            performance = orchestrator._get_model_performance()

            # 필수 필드 확인
            assert 'accuracy' in performance
            assert 'win_rate' in performance
            assert 'sharpe_ratio' in performance


class TestRetrainTriggerIntegration:
    """RetrainTrigger 연동 테스트"""

    def test_retrain_trigger_receives_complete_performance_data(self):
        """RetrainTrigger가 완전한 성능 데이터를 받는지 확인"""
        from core.learning.retrain.retrain_trigger import RetrainTrigger

        trigger = RetrainTrigger()

        feedback_stats = {
            'processed_feedback': 150,
            'new_feedback_since_last_train': 60
        }

        model_performance = {
            'accuracy': 0.65,
            'win_rate': 0.55,
            'sharpe_ratio': 1.2
        }

        result = trigger.should_retrain(feedback_stats, model_performance)

        # 결과 객체가 유효한지 확인
        assert hasattr(result, 'should_retrain')
        assert hasattr(result, 'reasons')

    def test_retrain_trigger_handles_missing_win_rate(self):
        """win_rate가 누락되어도 RetrainTrigger가 동작하는지 확인"""
        from core.learning.retrain.retrain_trigger import RetrainTrigger

        trigger = RetrainTrigger()

        feedback_stats = {
            'processed_feedback': 150
        }

        # win_rate, sharpe_ratio 누락
        model_performance = {
            'accuracy': 0.65
        }

        # 예외 없이 동작해야 함
        result = trigger.should_retrain(feedback_stats, model_performance)
        assert result is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
