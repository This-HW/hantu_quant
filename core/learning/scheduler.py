"""
학습 스케줄러 모듈

학습 작업의 자동 스케줄링 및 실행을 관리합니다.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
import threading
import time

logger = logging.getLogger(__name__)


class TaskPriority(Enum):
    """작업 우선순위"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class TaskStatus(Enum):
    """작업 상태"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ScheduledTask:
    """스케줄된 작업"""
    name: str
    task_func: Callable
    schedule_type: str  # realtime, daily, weekly, monthly, quarterly
    trigger: str = ""  # 트리거 조건 또는 시간

    # 실행 정보
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    run_count: int = 0
    fail_count: int = 0

    # 설정
    priority: TaskPriority = TaskPriority.NORMAL
    timeout_seconds: int = 3600  # 1시간
    enabled: bool = True

    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'schedule_type': self.schedule_type,
            'trigger': self.trigger,
            'last_run': self.last_run.isoformat() if self.last_run else None,
            'next_run': self.next_run.isoformat() if self.next_run else None,
            'run_count': self.run_count,
            'fail_count': self.fail_count,
            'priority': self.priority.name,
            'enabled': self.enabled,
        }


@dataclass
class TaskResult:
    """작업 실행 결과"""
    task_name: str
    status: TaskStatus
    start_time: datetime
    end_time: datetime
    duration_seconds: float = 0.0
    result: Any = None
    error: str = ""

    def to_dict(self) -> Dict:
        return {
            'task_name': self.task_name,
            'status': self.status.value,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat(),
            'duration_seconds': self.duration_seconds,
            'error': self.error,
        }


class LearningScheduler:
    """
    학습 작업 스케줄 관리

    주기:
    - 실시간: 거래 로그 수집
    - 일간: 당일 성과 분석
    - 주간: 가중치 조정, 파라미터 미세 조정
    - 월간: 모델 재학습, 전략 재평가
    - 분기: 전체 시스템 리뷰
    """

    def __init__(self):
        self._tasks: Dict[str, ScheduledTask] = {}
        self._results: List[TaskResult] = []
        self._running: bool = False
        self._lock = threading.Lock()

    def register_task(
        self,
        name: str,
        task_func: Callable,
        schedule_type: str,
        trigger: str = "",
        priority: TaskPriority = TaskPriority.NORMAL,
        timeout: int = 3600
    ) -> None:
        """
        작업 등록

        Args:
            name: 작업 이름
            task_func: 실행 함수
            schedule_type: 스케줄 유형
            trigger: 트리거 조건
            priority: 우선순위
            timeout: 타임아웃 (초)
        """
        task = ScheduledTask(
            name=name,
            task_func=task_func,
            schedule_type=schedule_type,
            trigger=trigger,
            priority=priority,
            timeout_seconds=timeout,
        )

        # 다음 실행 시간 계산
        task.next_run = self._calculate_next_run(task)

        with self._lock:
            self._tasks[name] = task

        logger.info(f"Task registered: {name} ({schedule_type})")

    def unregister_task(self, name: str) -> bool:
        """작업 해제"""
        with self._lock:
            if name in self._tasks:
                del self._tasks[name]
                logger.info(f"Task unregistered: {name}")
                return True
        return False

    def enable_task(self, name: str) -> bool:
        """작업 활성화"""
        with self._lock:
            if name in self._tasks:
                self._tasks[name].enabled = True
                return True
        return False

    def disable_task(self, name: str) -> bool:
        """작업 비활성화"""
        with self._lock:
            if name in self._tasks:
                self._tasks[name].enabled = False
                return True
        return False

    def _calculate_next_run(self, task: ScheduledTask) -> datetime:
        """다음 실행 시간 계산"""
        now = datetime.now()

        if task.schedule_type == 'realtime':
            return now  # 즉시 실행

        if task.schedule_type == 'daily':
            # 지정된 시간에 실행
            time_str = task.trigger or "16:00"
            hour, minute = map(int, time_str.split(':'))
            next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if next_run <= now:
                next_run += timedelta(days=1)
            return next_run

        if task.schedule_type == 'weekly':
            # 지정된 요일과 시간에 실행
            parts = task.trigger.split()
            day_name = parts[0].lower() if parts else 'friday'
            time_str = parts[1] if len(parts) > 1 else "17:00"

            days = {'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
                    'friday': 4, 'saturday': 5, 'sunday': 6}
            target_day = days.get(day_name, 4)

            hour, minute = map(int, time_str.split(':'))
            days_ahead = target_day - now.weekday()
            if days_ahead <= 0:
                days_ahead += 7

            next_run = now + timedelta(days=days_ahead)
            next_run = next_run.replace(hour=hour, minute=minute, second=0, microsecond=0)
            return next_run

        if task.schedule_type == 'monthly':
            # 지정된 일자와 시간에 실행
            parts = task.trigger.split()
            day = int(parts[0]) if parts else 1
            time_str = parts[1] if len(parts) > 1 else "06:00"

            hour, minute = map(int, time_str.split(':'))
            next_run = now.replace(day=min(day, 28), hour=hour, minute=minute,
                                  second=0, microsecond=0)
            if next_run <= now:
                # 다음 달
                if now.month == 12:
                    next_run = next_run.replace(year=now.year + 1, month=1)
                else:
                    next_run = next_run.replace(month=now.month + 1)
            return next_run

        # 기본: 1일 후
        return now + timedelta(days=1)

    def run_task(self, name: str, **kwargs) -> TaskResult:
        """
        작업 즉시 실행

        Args:
            name: 작업 이름
            **kwargs: 작업 인자

        Returns:
            TaskResult: 실행 결과
        """
        with self._lock:
            if name not in self._tasks:
                return TaskResult(
                    task_name=name,
                    status=TaskStatus.FAILED,
                    start_time=datetime.now(),
                    end_time=datetime.now(),
                    error="Task not found",
                )
            task = self._tasks[name]

        start_time = datetime.now()

        try:
            logger.info(f"Running task: {name}")
            result = task.task_func(**kwargs)

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            task_result = TaskResult(
                task_name=name,
                status=TaskStatus.COMPLETED,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
                result=result,
            )

            # 통계 업데이트
            with self._lock:
                task.last_run = end_time
                task.run_count += 1
                task.next_run = self._calculate_next_run(task)

            logger.info(f"Task completed: {name} ({duration:.2f}s)")

        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            task_result = TaskResult(
                task_name=name,
                status=TaskStatus.FAILED,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
                error=str(e),
            )

            with self._lock:
                task.fail_count += 1

            logger.error(f"Task failed: {name} - {e}")

        # 결과 저장
        with self._lock:
            self._results.append(task_result)
            # 최근 1000개만 유지
            if len(self._results) > 1000:
                self._results = self._results[-1000:]

        return task_result

    def run_scheduled_tasks(self) -> List[TaskResult]:
        """
        스케줄된 작업 실행

        Returns:
            List[TaskResult]: 실행된 작업 결과
        """
        results = []
        now = datetime.now()

        with self._lock:
            tasks_to_run = [
                task for task in self._tasks.values()
                if task.enabled and task.next_run and task.next_run <= now
            ]

        # 우선순위 순으로 정렬
        tasks_to_run.sort(key=lambda t: t.priority.value, reverse=True)

        for task in tasks_to_run:
            result = self.run_task(task.name)
            results.append(result)

        return results

    def trigger_realtime_task(self, trigger: str, **kwargs) -> List[TaskResult]:
        """
        실시간 작업 트리거

        Args:
            trigger: 트리거 이벤트
            **kwargs: 작업 인자

        Returns:
            List[TaskResult]: 실행된 작업 결과
        """
        results = []

        with self._lock:
            tasks = [
                task for task in self._tasks.values()
                if task.schedule_type == 'realtime' and
                task.trigger == trigger and
                task.enabled
            ]

        for task in tasks:
            result = self.run_task(task.name, **kwargs)
            results.append(result)

        return results

    def get_pending_tasks(self) -> List[Dict]:
        """대기 중인 작업 목록"""
        now = datetime.now()

        with self._lock:
            pending = []
            for task in self._tasks.values():
                if not task.enabled:
                    continue
                if task.next_run:
                    time_until = (task.next_run - now).total_seconds()
                    pending.append({
                        'name': task.name,
                        'next_run': task.next_run.isoformat(),
                        'time_until_seconds': max(0, time_until),
                        'schedule_type': task.schedule_type,
                        'priority': task.priority.name,
                    })

            return sorted(pending, key=lambda x: x['time_until_seconds'])

    def get_task_status(self, name: str) -> Optional[Dict]:
        """작업 상태 조회"""
        with self._lock:
            if name in self._tasks:
                return self._tasks[name].to_dict()
        return None

    def get_recent_results(self, n: int = 20) -> List[Dict]:
        """최근 실행 결과"""
        with self._lock:
            return [r.to_dict() for r in self._results[-n:]]

    def get_stats(self) -> Dict[str, Any]:
        """통계 정보"""
        with self._lock:
            total_tasks = len(self._tasks)
            enabled_tasks = sum(1 for t in self._tasks.values() if t.enabled)
            total_runs = sum(t.run_count for t in self._tasks.values())
            total_fails = sum(t.fail_count for t in self._tasks.values())

            by_type = {}
            for task in self._tasks.values():
                st = task.schedule_type
                if st not in by_type:
                    by_type[st] = 0
                by_type[st] += 1

            return {
                'total_tasks': total_tasks,
                'enabled_tasks': enabled_tasks,
                'total_runs': total_runs,
                'total_fails': total_fails,
                'success_rate': (total_runs - total_fails) / total_runs if total_runs > 0 else 0,
                'by_schedule_type': by_type,
            }

    def setup_default_schedule(
        self,
        trade_logger=None,
        performance_analyzer=None,
        failure_analyzer=None,
        lstm_learner=None,
        weight_optimizer=None
    ) -> None:
        """
        기본 스케줄 설정

        Args:
            trade_logger: 거래 로거
            performance_analyzer: 성과 분석기
            failure_analyzer: 실패 분석기
            lstm_learner: LSTM 학습기
            weight_optimizer: 가중치 최적화기
        """
        # 실시간 작업
        if trade_logger:
            self.register_task(
                name="log_trade",
                task_func=lambda **kw: trade_logger.log_trade(**kw),
                schedule_type="realtime",
                trigger="on_trade",
                priority=TaskPriority.HIGH,
            )

        # 일간 작업
        if performance_analyzer:
            self.register_task(
                name="daily_performance_analysis",
                task_func=lambda **kw: performance_analyzer.analyze_patterns(
                    kw.get('trade_logs', [])
                ),
                schedule_type="daily",
                trigger="16:00",
                priority=TaskPriority.NORMAL,
            )

        if failure_analyzer:
            self.register_task(
                name="failure_analysis",
                task_func=lambda **kw: failure_analyzer.analyze_failures(
                    kw.get('losers', [])
                ),
                schedule_type="daily",
                trigger="16:30",
                priority=TaskPriority.NORMAL,
            )

        # 주간 작업
        if weight_optimizer:
            self.register_task(
                name="adjust_ensemble_weights",
                task_func=lambda **kw: weight_optimizer.optimize(force=True),
                schedule_type="weekly",
                trigger="friday 17:00",
                priority=TaskPriority.HIGH,
            )

        # 월간 작업
        if lstm_learner:
            self.register_task(
                name="retrain_lstm",
                task_func=lambda **kw: lstm_learner.retrain(
                    kw.get('training_data', {}), force=False
                ),
                schedule_type="monthly",
                trigger="1 06:00",
                priority=TaskPriority.HIGH,
                timeout=7200,  # 2시간
            )

        logger.info("Default schedule configured")


class SchedulerRunner:
    """
    스케줄러 실행기

    백그라운드에서 스케줄러를 실행합니다.
    """

    def __init__(self, scheduler: LearningScheduler, check_interval: int = 60):
        """
        Args:
            scheduler: 학습 스케줄러
            check_interval: 체크 간격 (초)
        """
        self.scheduler = scheduler
        self.check_interval = check_interval
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """스케줄러 시작"""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

        logger.info("Scheduler runner started")

    def stop(self) -> None:
        """스케줄러 중지"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

        logger.info("Scheduler runner stopped")

    def _run_loop(self) -> None:
        """실행 루프"""
        while self._running:
            try:
                results = self.scheduler.run_scheduled_tasks()
                if results:
                    logger.debug(f"Executed {len(results)} scheduled tasks")
            except Exception as e:
                logger.error(f"Scheduler error: {e}")

            time.sleep(self.check_interval)

    @property
    def is_running(self) -> bool:
        """실행 중 여부"""
        return self._running
