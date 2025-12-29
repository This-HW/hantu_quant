"""
LearningOrchestrator 단위 테스트

테스트 대상:
- D.1.1: LearningOrchestrator 클래스
- D.1.2: 일일 학습 스케줄러
- D.1.3: 학습 큐 관리
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from core.learning.orchestrator.learning_orchestrator import (
    LearningOrchestrator,
    LearningTaskType,
    TaskPriority,
    LearningTask,
    get_learning_orchestrator
)


class TestLearningTask:
    """LearningTask 테스트"""

    def test_task_creation(self):
        """작업 생성"""
        task = LearningTask(
            task_id="test_001",
            task_type=LearningTaskType.WEIGHT_UPDATE
        )

        assert task.task_id == "test_001"
        assert task.task_type == LearningTaskType.WEIGHT_UPDATE
        assert task.status == "pending"
        assert task.priority == TaskPriority.NORMAL

    def test_task_priority_comparison(self):
        """작업 우선순위 비교"""
        high = LearningTask(
            task_id="high",
            task_type=LearningTaskType.MODEL_RETRAIN,
            priority=TaskPriority.HIGH
        )
        low = LearningTask(
            task_id="low",
            task_type=LearningTaskType.WEIGHT_UPDATE,
            priority=TaskPriority.LOW
        )

        # 높은 우선순위가 먼저 처리되어야 함
        assert high < low


class TestLearningTaskType:
    """LearningTaskType Enum 테스트"""

    def test_task_types(self):
        """작업 타입 확인"""
        assert LearningTaskType.WEIGHT_UPDATE.value == "weight_update"
        assert LearningTaskType.MODEL_RETRAIN.value == "model_retrain"
        assert LearningTaskType.REGIME_CHECK.value == "regime_check"
        assert LearningTaskType.FULL_CYCLE.value == "full_cycle"


class TestLearningOrchestrator:
    """LearningOrchestrator 테스트"""

    @pytest.fixture
    def orchestrator(self):
        """LearningOrchestrator 인스턴스"""
        return LearningOrchestrator(enable_auto_schedule=False)

    def test_enqueue_task(self, orchestrator):
        """작업 큐 추가"""
        task_id = orchestrator.enqueue_task(
            task_type=LearningTaskType.WEIGHT_UPDATE,
            priority=TaskPriority.NORMAL
        )

        assert task_id is not None
        assert "weight_update" in task_id

    def test_enqueue_task_with_priority(self, orchestrator):
        """우선순위 지정 작업 추가"""
        task_id = orchestrator.enqueue_task(
            task_type=LearningTaskType.MODEL_RETRAIN,
            priority=TaskPriority.CRITICAL
        )

        pending = orchestrator.get_pending_tasks()
        assert len(pending) > 0

    def test_enqueue_scheduled_task(self, orchestrator):
        """예약 작업 추가"""
        scheduled_time = datetime.now() + timedelta(hours=1)

        task_id = orchestrator.enqueue_task(
            task_type=LearningTaskType.REGIME_CHECK,
            scheduled_at=scheduled_time
        )

        pending = orchestrator.get_pending_tasks()
        matching = [t for t in pending if t['task_id'] == task_id]
        assert len(matching) == 1
        assert matching[0]['scheduled_at'] is not None

    def test_process_queue_empty(self, orchestrator):
        """빈 큐 처리"""
        results = orchestrator.process_queue()

        assert results == []

    @patch('core.learning.orchestrator.learning_orchestrator.get_feedback_system')
    def test_process_queue_with_task(self, mock_feedback, orchestrator):
        """작업 큐 처리"""
        # Mock 설정
        mock_fs = MagicMock()
        mock_fs.get_stats.return_value = {'total_count': 50}
        mock_fs.get_recent_feedback.return_value = []
        mock_feedback.return_value = mock_fs

        # 작업 추가
        orchestrator.enqueue_task(
            task_type=LearningTaskType.REGIME_CHECK,
            priority=TaskPriority.NORMAL
        )

        # 처리
        results = orchestrator.process_queue(max_tasks=1)

        assert len(results) == 1
        assert results[0]['task_type'] == 'regime_check'

    def test_register_callback(self, orchestrator):
        """콜백 등록"""
        callback_called = []

        def on_complete(task):
            callback_called.append(task)

        orchestrator.register_callback('on_task_complete', on_complete)

        # 콜백이 등록됨
        assert len(orchestrator._callbacks['on_task_complete']) == 1

    def test_get_status(self, orchestrator):
        """상태 조회"""
        status = orchestrator.get_status()

        assert 'scheduler_running' in status
        assert 'pending_tasks' in status
        assert 'queue_size' in status

    def test_get_pending_tasks_empty(self, orchestrator):
        """빈 대기 작업 목록"""
        pending = orchestrator.get_pending_tasks()

        assert pending == []

    def test_get_completed_tasks_empty(self, orchestrator):
        """빈 완료 작업 목록"""
        completed = orchestrator.get_completed_tasks()

        assert completed == []

    @patch('core.learning.orchestrator.learning_orchestrator.get_feedback_system')
    @patch('core.learning.orchestrator.learning_orchestrator.get_regime_detector')
    def test_run_daily_cycle(self, mock_detector, mock_feedback, orchestrator):
        """일일 사이클 실행"""
        # Mock 설정
        mock_fs = MagicMock()
        mock_fs.get_stats.return_value = {'total_count': 50}
        mock_fs.get_recent_feedback.return_value = []
        mock_feedback.return_value = mock_fs

        mock_rd = MagicMock()
        mock_rd.detect.return_value = MagicMock(
            regime=MagicMock(value='bull'),
            confidence=0.7,
            regime_changed=False
        )
        mock_detector.return_value = mock_rd

        # 실행
        result = orchestrator.run_daily_cycle()

        assert 'started_at' in result
        assert 'steps' in result
        assert result['success']

    def test_start_stop(self, orchestrator):
        """시작/중지"""
        orchestrator.start()
        assert orchestrator._scheduler_running

        orchestrator.stop()
        assert not orchestrator._scheduler_running


class TestTaskPriority:
    """TaskPriority Enum 테스트"""

    def test_priority_values(self):
        """우선순위 값 확인"""
        assert TaskPriority.LOW.value == 0
        assert TaskPriority.NORMAL.value == 1
        assert TaskPriority.HIGH.value == 2
        assert TaskPriority.CRITICAL.value == 3
