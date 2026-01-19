"""
학습 오케스트레이터

Task D.1.1: LearningOrchestrator 클래스
Task D.1.2: 일일 학습 스케줄러
Task D.1.3: 학습 큐 관리
"""

import json
import threading
import queue
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import time

from core.learning.retrain.retrain_trigger import get_retrain_trigger
from core.learning.retrain.model_retrainer import get_model_retrainer
from core.learning.retrain.retrain_history import get_retrain_history
from core.learning.weights.dynamic_weight_calculator import get_dynamic_weight_calculator
from core.learning.weights.weight_storage import get_weight_storage
from core.learning.regime.regime_detector import get_regime_detector
from core.learning.regime.regime_strategy_mapper import get_regime_strategy_mapper
from core.utils.log_utils import get_logger

logger = get_logger(__name__)


class LearningTaskType(Enum):
    """학습 작업 타입"""
    WEIGHT_UPDATE = "weight_update"        # 가중치 업데이트
    MODEL_RETRAIN = "model_retrain"        # 모델 재학습
    REGIME_CHECK = "regime_check"          # 레짐 체크
    PERFORMANCE_EVAL = "performance_eval"  # 성능 평가
    FULL_CYCLE = "full_cycle"             # 전체 사이클


class TaskPriority(Enum):
    """작업 우선순위"""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class LearningTask:
    """학습 작업"""
    task_id: str
    task_type: LearningTaskType
    priority: TaskPriority = TaskPriority.NORMAL
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    scheduled_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    status: str = "pending"  # pending, running, completed, failed
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __lt__(self, other):
        """우선순위 비교 (큐 정렬용)"""
        return self.priority.value > other.priority.value


class LearningOrchestrator:
    """
    학습 오케스트레이터 (D.1.1)

    모든 학습 관련 작업을 통합 관리합니다:
    - 재학습 트리거 모니터링
    - 가중치 업데이트 조정
    - 레짐 탐지 및 전략 적용
    - 작업 스케줄링 및 큐 관리
    """

    def __init__(self,
                 data_dir: str = "data/learning",
                 enable_auto_schedule: bool = True):
        """
        초기화

        Args:
            data_dir: 데이터 디렉토리
            enable_auto_schedule: 자동 스케줄링 활성화
        """
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)

        self._enable_auto_schedule = enable_auto_schedule

        # 구성 요소 초기화
        self._retrain_trigger = get_retrain_trigger()
        self._model_retrainer = get_model_retrainer()
        self._retrain_history = get_retrain_history()
        self._weight_calculator = get_dynamic_weight_calculator()
        self._weight_storage = get_weight_storage()
        self._regime_detector = get_regime_detector()
        self._strategy_mapper = get_regime_strategy_mapper()

        # 작업 큐 (D.1.3)
        self._task_queue: queue.PriorityQueue = queue.PriorityQueue()
        self._pending_tasks: Dict[str, LearningTask] = {}
        self._completed_tasks: List[LearningTask] = []
        self._max_completed_history = 100

        # 스케줄러 상태 (D.1.2)
        self._scheduler_running = False
        self._scheduler_thread: Optional[threading.Thread] = None
        self._last_daily_run: Optional[datetime] = None

        # 상태 파일
        self._state_file = self._data_dir / "orchestrator_state.json"
        self._load_state()

        # 콜백
        self._callbacks: Dict[str, List[Callable]] = {
            'on_task_complete': [],
            'on_task_failed': [],
            'on_regime_change': [],
            'on_weight_update': [],
        }

        logger.info("LearningOrchestrator 초기화 완료")

    def start(self):
        """오케스트레이터 시작"""
        if self._scheduler_running:
            logger.warning("오케스트레이터가 이미 실행 중입니다")
            return

        self._scheduler_running = True

        if self._enable_auto_schedule:
            self._scheduler_thread = threading.Thread(
                target=self._scheduler_loop,
                daemon=True
            )
            self._scheduler_thread.start()
            logger.info("학습 스케줄러 시작")

    def stop(self):
        """오케스트레이터 중지"""
        self._scheduler_running = False
        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=5)
        self._save_state()
        logger.info("오케스트레이터 중지")

    def run_daily_cycle(self) -> Dict[str, Any]:
        """
        일일 학습 사이클 실행 (D.1.2)

        Returns:
            실행 결과
        """
        logger.info("=== 일일 학습 사이클 시작 ===")
        results = {
            'started_at': datetime.now().isoformat(),
            'steps': [],
            'success': True
        }

        try:
            # 1. 레짐 체크
            regime_result = self._run_regime_check()
            results['steps'].append({
                'step': 'regime_check',
                'result': regime_result
            })

            # 2. 재학습 조건 체크
            retrain_result = self._run_retrain_check()
            results['steps'].append({
                'step': 'retrain_check',
                'result': retrain_result
            })

            # 3. 가중치 업데이트 체크
            weight_result = self._run_weight_update_check()
            results['steps'].append({
                'step': 'weight_update_check',
                'result': weight_result
            })

            # 4. 성능 평가
            perf_result = self._run_performance_eval()
            results['steps'].append({
                'step': 'performance_eval',
                'result': perf_result
            })

            results['completed_at'] = datetime.now().isoformat()
            self._last_daily_run = datetime.now()
            logger.info("=== 일일 학습 사이클 완료 ===")

        except Exception as e:
            results['success'] = False
            results['error'] = str(e)
            logger.error(f"일일 학습 사이클 오류: {e}", exc_info=True)

        self._save_state()
        return results

    def _run_regime_check(self) -> Dict[str, Any]:
        """레짐 체크 실행"""
        try:
            regime_result = self._regime_detector.detect()

            # 레짐에 따른 가중치 업데이트
            self._strategy_mapper.update_regime(regime_result)

            # 콜백 호출
            if regime_result.regime_changed:
                self._trigger_callbacks('on_regime_change', regime_result)

            return {
                'regime': regime_result.regime.value,
                'confidence': regime_result.confidence,
                'changed': regime_result.regime_changed,
                'weights_updated': True
            }

        except Exception as e:
            logger.error(f"레짐 체크 오류: {e}", exc_info=True)
            return {'error': str(e)}

    def _run_retrain_check(self) -> Dict[str, Any]:
        """재학습 조건 체크"""
        try:
            # 피드백 통계 수집
            from core.learning.models.feedback_system import get_feedback_system
            feedback_system = get_feedback_system()
            feedback_stats = feedback_system.get_stats()

            # 모델 성능 조회
            model_performance = self._get_model_performance()

            # 트리거 체크
            trigger_result = self._retrain_trigger.should_retrain(
                feedback_stats=feedback_stats,
                model_performance=model_performance
            )

            if trigger_result.should_retrain:
                # 재학습 작업 큐에 추가
                self.enqueue_task(
                    task_type=LearningTaskType.MODEL_RETRAIN,
                    priority=TaskPriority.HIGH,
                    metadata={'reasons': [r.value for r in trigger_result.reasons]}
                )

            return {
                'should_retrain': trigger_result.should_retrain,
                'reasons': [r.value for r in trigger_result.reasons],
                'details': trigger_result.details
            }

        except Exception as e:
            logger.error(f"재학습 체크 오류: {e}", exc_info=True)
            return {'error': str(e)}

    def _run_weight_update_check(self) -> Dict[str, Any]:
        """가중치 업데이트 체크"""
        try:
            # 최근 성과 데이터 수집
            from core.learning.models.feedback_system import get_feedback_system
            feedback_system = get_feedback_system()

            recent_feedback = feedback_system.get_recent_feedback(days=7)

            if len(recent_feedback) < 10:
                return {'updated': False, 'reason': 'insufficient_data'}

            # 성과 데이터 구성
            performance_data = []
            factor_scores = []

            for fb in recent_feedback:
                actual_return = fb.get('actual_return_7d') or 0
                performance_data.append({
                    'stock_code': fb.get('stock_code', ''),
                    'pnl_ratio': actual_return,
                    'return': actual_return,
                    'is_win': fb.get('actual_class') == 1
                })
                factor_scores.append(fb.get('factor_scores') or {})

            # 가중치 업데이트 시도
            result = self._weight_calculator.update_from_performance(
                performance_data=performance_data,
                factor_scores=factor_scores,
                reason="daily_update"
            )

            if result:
                self._trigger_callbacks('on_weight_update', result)
                return {
                    'updated': True,
                    'new_weights': result.new_weights,
                    'change_summary': result.change_summary
                }
            else:
                return {'updated': False, 'reason': 'no_significant_change'}

        except Exception as e:
            logger.error(f"가중치 업데이트 체크 오류: {e}", exc_info=True)
            return {'error': str(e)}

    def _run_performance_eval(self) -> Dict[str, Any]:
        """성능 평가 실행"""
        try:
            # 학습 이력 요약
            history_summary = self._retrain_history.get_summary()

            # 가중치 요약
            weight_summary = self._weight_storage.get_version_summary()

            # 레짐 상태
            regime_status = self._strategy_mapper.get_status()

            return {
                'retrain_history': history_summary,
                'weight_status': weight_summary,
                'regime_status': regime_status,
                'evaluation_time': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"성능 평가 오류: {e}", exc_info=True)
            return {'error': str(e)}

    def _get_model_performance(self) -> Dict[str, float]:
        """현재 모델 성능 조회"""
        try:
            # 최근 30일 성공률
            success_rate = self._retrain_history.get_success_rate(30)
            improvement = self._retrain_history.get_average_improvement(30)

            # win_rate, sharpe_ratio 계산을 위해 피드백 데이터 조회
            from core.learning.models.feedback_system import get_feedback_system
            feedback_system = get_feedback_system()
            recent_feedback = feedback_system.get_recent_feedback(days=30)

            # win_rate 계산
            win_rate = 0.0
            if recent_feedback:
                processed = [fb for fb in recent_feedback if fb.get('is_processed')]
                if processed:
                    wins = sum(1 for fb in processed if fb.get('actual_class') == 1)
                    win_rate = wins / len(processed)

            # sharpe_ratio 계산 (일별 수익률 기준)
            sharpe_ratio = 0.0
            returns = [fb.get('actual_return_7d') or 0 for fb in recent_feedback
                       if fb.get('actual_return_7d') is not None]
            if len(returns) >= 5:
                import math
                mean_return = sum(returns) / len(returns)
                variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
                std_return = math.sqrt(variance) if variance > 0 else 0
                if std_return > 0:
                    # 연간화 (7일 수익률 기준, 약 52주)
                    sharpe_ratio = (mean_return / std_return) * math.sqrt(52)

            return {
                'accuracy': success_rate,
                'improvement': improvement,
                'recent_performance': success_rate,
                'win_rate': win_rate,
                'sharpe_ratio': sharpe_ratio
            }
        except Exception as e:
            logger.warning(f"모델 성능 조회 일부 실패: {e}", exc_info=True)
            return {'accuracy': 0.0, 'improvement': 0.0, 'win_rate': 0.0, 'sharpe_ratio': 0.0}

    def enqueue_task(self,
                    task_type: LearningTaskType,
                    priority: TaskPriority = TaskPriority.NORMAL,
                    scheduled_at: Optional[datetime] = None,
                    metadata: Optional[Dict] = None) -> str:
        """
        작업 큐에 추가 (D.1.3)

        Args:
            task_type: 작업 타입
            priority: 우선순위
            scheduled_at: 예약 실행 시간
            metadata: 메타데이터

        Returns:
            작업 ID
        """
        task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{task_type.value}"

        task = LearningTask(
            task_id=task_id,
            task_type=task_type,
            priority=priority,
            scheduled_at=scheduled_at.isoformat() if scheduled_at else None,
            metadata=metadata or {}
        )

        self._pending_tasks[task_id] = task
        self._task_queue.put(task)

        logger.info(f"작업 큐에 추가: {task_id} ({task_type.value})")
        return task_id

    def process_queue(self, max_tasks: int = 5) -> List[Dict[str, Any]]:
        """
        큐의 작업 처리

        Args:
            max_tasks: 최대 처리 작업 수

        Returns:
            처리 결과 목록
        """
        results = []
        processed = 0

        while not self._task_queue.empty() and processed < max_tasks:
            try:
                task = self._task_queue.get_nowait()

                # 예약된 작업 체크
                if task.scheduled_at:
                    scheduled = datetime.fromisoformat(task.scheduled_at)
                    if scheduled > datetime.now():
                        # 아직 시간이 안 됨 - 다시 큐에 넣기
                        self._task_queue.put(task)
                        continue

                # 작업 실행
                result = self._execute_task(task)
                results.append(result)
                processed += 1

            except queue.Empty:
                break

        return results

    def _execute_task(self, task: LearningTask) -> Dict[str, Any]:
        """작업 실행"""
        task.status = "running"
        task.started_at = datetime.now().isoformat()

        logger.info(f"작업 실행 시작: {task.task_id}")

        try:
            if task.task_type == LearningTaskType.WEIGHT_UPDATE:
                result = self._run_weight_update_check()
            elif task.task_type == LearningTaskType.MODEL_RETRAIN:
                result = self._execute_model_retrain(task)
            elif task.task_type == LearningTaskType.REGIME_CHECK:
                result = self._run_regime_check()
            elif task.task_type == LearningTaskType.PERFORMANCE_EVAL:
                result = self._run_performance_eval()
            elif task.task_type == LearningTaskType.FULL_CYCLE:
                result = self.run_daily_cycle()
            else:
                result = {'error': f'Unknown task type: {task.task_type}'}

            task.status = "completed"
            task.completed_at = datetime.now().isoformat()
            task.result = result

            self._trigger_callbacks('on_task_complete', task)
            logger.info(f"작업 완료: {task.task_id}")

        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            task.completed_at = datetime.now().isoformat()

            self._trigger_callbacks('on_task_failed', task)
            logger.error(f"작업 실패: {task.task_id} - {e}", exc_info=True)
            result = {'error': str(e)}

        # 완료 기록
        if task.task_id in self._pending_tasks:
            del self._pending_tasks[task.task_id]

        self._completed_tasks.append(task)
        if len(self._completed_tasks) > self._max_completed_history:
            self._completed_tasks = self._completed_tasks[-self._max_completed_history:]

        return {
            'task_id': task.task_id,
            'task_type': task.task_type.value,
            'status': task.status,
            'result': result
        }

    def _execute_model_retrain(self, task: LearningTask) -> Dict[str, Any]:
        """모델 재학습 실행"""
        try:
            # 피드백 데이터 수집
            from core.learning.models.feedback_system import get_feedback_system
            feedback_system = get_feedback_system()

            raw_feedback = feedback_system.get_recent_feedback(days=90)

            if len(raw_feedback) < 30:
                return {'error': 'insufficient_training_data'}

            # 피드백 데이터를 학습 데이터 형식으로 변환
            training_data = self._convert_feedback_to_training_data(raw_feedback)

            if len(training_data) < 30:
                return {'error': 'insufficient_processed_training_data'}

            # 재학습 실행
            result = self._model_retrainer.retrain(
                training_data=training_data,
                background=False
            )

            return {
                'success': result.success,
                'version': result.version,
                'metrics': result.metrics
            }

        except Exception as e:
            logger.error(f"모델 재학습 실행 오류: {e}", exc_info=True)
            return {'error': str(e)}

    def _convert_feedback_to_training_data(
        self, feedback_list: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """피드백 데이터를 학습 데이터 형식으로 변환

        Args:
            feedback_list: get_recent_feedback() 결과

        Returns:
            ModelRetrainer가 기대하는 학습 데이터 형식
        """
        training_data = []

        for fb in feedback_list:
            # 처리되지 않은 피드백은 건너뜀
            if not fb.get('is_processed'):
                continue

            # actual_class가 없는 경우 건너뜀
            actual_class = fb.get('actual_class')
            if actual_class is None:
                continue

            training_sample = {
                'stock_code': fb.get('stock_code', ''),
                'prediction_date': fb.get('prediction_date', ''),
                'predicted_probability': fb.get('predicted_probability', 0.5),
                'predicted_class': fb.get('predicted_class', 0),
                'actual_class': actual_class,
                'actual_return': fb.get('actual_return_7d', 0),
                'is_win': actual_class == 1,
                'factor_scores': fb.get('factor_scores', {})
            }

            training_data.append(training_sample)

        return training_data

    def _scheduler_loop(self):
        """스케줄러 루프 (D.1.2)"""
        logger.info("스케줄러 루프 시작")

        while self._scheduler_running:
            try:
                now = datetime.now()

                # 일일 사이클 체크 (08:00에 실행)
                if now.hour == 8 and now.minute < 5:
                    if (self._last_daily_run is None or
                        self._last_daily_run.date() < now.date()):
                        self.run_daily_cycle()

                # 큐 처리
                self.process_queue(max_tasks=3)

                # 1분 대기
                time.sleep(60)

            except Exception as e:
                logger.error(f"스케줄러 오류: {e}", exc_info=True)
                time.sleep(60)

        logger.info("스케줄러 루프 종료")

    def register_callback(self,
                         event: str,
                         callback: Callable):
        """콜백 등록"""
        if event in self._callbacks:
            self._callbacks[event].append(callback)

    def _trigger_callbacks(self, event: str, data: Any):
        """콜백 트리거"""
        for callback in self._callbacks.get(event, []):
            try:
                callback(data)
            except Exception as e:
                logger.warning(f"콜백 실행 오류: {e}")

    def get_status(self) -> Dict[str, Any]:
        """상태 정보"""
        return {
            'scheduler_running': self._scheduler_running,
            'pending_tasks': len(self._pending_tasks),
            'queue_size': self._task_queue.qsize(),
            'completed_tasks': len(self._completed_tasks),
            'last_daily_run': self._last_daily_run.isoformat() if self._last_daily_run else None,
            'current_regime': self._strategy_mapper.get_current_regime().value if self._strategy_mapper.get_current_regime() else None,
            'current_weights': self._strategy_mapper.get_current_weights()
        }

    def get_pending_tasks(self) -> List[Dict[str, Any]]:
        """대기 중인 작업 목록"""
        return [
            {
                'task_id': t.task_id,
                'task_type': t.task_type.value,
                'priority': t.priority.value,
                'scheduled_at': t.scheduled_at
            }
            for t in self._pending_tasks.values()
        ]

    def get_completed_tasks(self, limit: int = 20) -> List[Dict[str, Any]]:
        """완료된 작업 목록"""
        recent = self._completed_tasks[-limit:]
        return [
            {
                'task_id': t.task_id,
                'task_type': t.task_type.value,
                'status': t.status,
                'completed_at': t.completed_at
            }
            for t in reversed(recent)
        ]

    def _save_state(self):
        """상태 저장"""
        try:
            state = {
                'last_daily_run': self._last_daily_run.isoformat() if self._last_daily_run else None,
                'completed_tasks_count': len(self._completed_tasks),
                'saved_at': datetime.now().isoformat()
            }
            with open(self._state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"상태 저장 실패: {e}")

    def _load_state(self):
        """상태 로드"""
        try:
            if self._state_file.exists():
                with open(self._state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                if state.get('last_daily_run'):
                    self._last_daily_run = datetime.fromisoformat(state['last_daily_run'])
        except Exception as e:
            logger.warning(f"상태 로드 실패: {e}")


# 싱글톤 인스턴스
_orchestrator_instance: Optional[LearningOrchestrator] = None


def get_learning_orchestrator() -> LearningOrchestrator:
    """LearningOrchestrator 싱글톤 인스턴스 반환"""
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = LearningOrchestrator()
    return _orchestrator_instance
