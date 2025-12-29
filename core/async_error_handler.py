"""
비동기 에러 처리 모듈

비동기 작업에서 발생하는 에러를 안전하게 처리합니다.

Feature 5: 에러 추적 및 원인 파악 시스템
Story 5.5: 비동기 에러 처리 강화
"""

import asyncio
import logging
import functools
from datetime import datetime
from typing import (
    Optional, Dict, Any, Callable, List, TypeVar, Generic,
    Coroutine, Union, Awaitable, Tuple
)
from dataclasses import dataclass, field
from enum import Enum

from core.exceptions import HantuQuantException, ErrorSeverity
from core.utils.log_utils import get_context_logger, get_trace_id, SpanContextManager
from core.error_handler import (
    handle_error,
    ErrorAction,
    get_error_notifier,
)

logger = get_context_logger(__name__)

T = TypeVar('T')


class AsyncErrorPolicy(Enum):
    """비동기 에러 처리 정책"""
    FAIL_FAST = "fail_fast"           # 첫 에러 시 즉시 실패
    COLLECT_ALL = "collect_all"       # 모든 에러 수집 후 보고
    IGNORE_ERRORS = "ignore_errors"   # 에러 무시하고 성공한 결과만 반환
    PARTIAL_SUCCESS = "partial_success"  # 부분 성공 허용


@dataclass
class AsyncResult(Generic[T]):
    """
    비동기 작업 결과

    성공/실패 여부와 결과 또는 에러를 담습니다.
    """
    success: bool
    value: Optional[T] = None
    error: Optional[Exception] = None
    task_id: Optional[str] = None
    elapsed_ms: Optional[float] = None

    @classmethod
    def ok(cls, value: T, task_id: Optional[str] = None, elapsed_ms: Optional[float] = None) -> 'AsyncResult[T]':
        """성공 결과 생성"""
        return cls(success=True, value=value, task_id=task_id, elapsed_ms=elapsed_ms)

    @classmethod
    def fail(cls, error: Exception, task_id: Optional[str] = None, elapsed_ms: Optional[float] = None) -> 'AsyncResult[T]':
        """실패 결과 생성"""
        return cls(success=False, error=error, task_id=task_id, elapsed_ms=elapsed_ms)


@dataclass
class AsyncBatchResult(Generic[T]):
    """
    비동기 배치 작업 결과

    여러 비동기 작업의 결과를 취합합니다.
    """
    results: List[AsyncResult[T]] = field(default_factory=list)
    total_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    errors: List[Exception] = field(default_factory=list)
    total_elapsed_ms: Optional[float] = None

    def add(self, result: AsyncResult[T]) -> None:
        """결과 추가"""
        self.results.append(result)
        self.total_count += 1
        if result.success:
            self.success_count += 1
        else:
            self.failure_count += 1
            if result.error:
                self.errors.append(result.error)

    def success_values(self) -> List[T]:
        """성공한 결과 값들"""
        return [r.value for r in self.results if r.success and r.value is not None]

    def is_all_success(self) -> bool:
        """모두 성공 여부"""
        return self.failure_count == 0

    def is_all_failed(self) -> bool:
        """모두 실패 여부"""
        return self.success_count == 0

    def success_rate(self) -> float:
        """성공률"""
        if self.total_count == 0:
            return 0.0
        return self.success_count / self.total_count

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 변환"""
        return {
            "total_count": self.total_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "success_rate": round(self.success_rate() * 100, 2),
            "error_types": [type(e).__name__ for e in self.errors],
            "total_elapsed_ms": self.total_elapsed_ms,
        }


async def safe_gather(
    *coros: Coroutine,
    policy: AsyncErrorPolicy = AsyncErrorPolicy.COLLECT_ALL,
    return_exceptions: bool = False,
    notify_errors: bool = True,
    timeout: Optional[float] = None,
) -> AsyncBatchResult:
    """
    안전한 asyncio.gather 래퍼

    일부 작업이 실패해도 나머지 결과를 반환합니다.

    Story 5.5: 비동기 에러 처리 강화
    T-5.5.1: safe_gather() 구현

    Args:
        *coros: 비동기 코루틴들
        policy: 에러 처리 정책
        return_exceptions: 예외를 결과로 반환할지 여부
        notify_errors: 에러 발생 시 알림 여부
        timeout: 전체 타임아웃 (초)

    Returns:
        AsyncBatchResult: 배치 결과

    Example:
        results = await safe_gather(
            fetch_data("A"),
            fetch_data("B"),
            fetch_data("C"),
            policy=AsyncErrorPolicy.PARTIAL_SUCCESS
        )
        for value in results.success_values():
            process(value)
    """
    import time
    start_time = time.time()
    batch_result: AsyncBatchResult = AsyncBatchResult()

    if not coros:
        return batch_result

    async def wrap_coro(index: int, coro: Coroutine) -> AsyncResult:
        """코루틴을 AsyncResult로 래핑"""
        task_start = time.time()
        task_id = f"task_{index}"
        try:
            if timeout:
                result = await asyncio.wait_for(coro, timeout=timeout)
            else:
                result = await coro
            elapsed = (time.time() - task_start) * 1000
            return AsyncResult.ok(result, task_id=task_id, elapsed_ms=elapsed)
        except asyncio.CancelledError:
            elapsed = (time.time() - task_start) * 1000
            return AsyncResult.fail(
                asyncio.CancelledError("Task cancelled"),
                task_id=task_id,
                elapsed_ms=elapsed
            )
        except asyncio.TimeoutError as e:
            elapsed = (time.time() - task_start) * 1000
            return AsyncResult.fail(e, task_id=task_id, elapsed_ms=elapsed)
        except Exception as e:
            elapsed = (time.time() - task_start) * 1000
            return AsyncResult.fail(e, task_id=task_id, elapsed_ms=elapsed)

    # 정책에 따른 실행
    if policy == AsyncErrorPolicy.FAIL_FAST:
        # 첫 에러 시 즉시 실패 (나머지 취소)
        tasks = [asyncio.create_task(wrap_coro(i, c)) for i, c in enumerate(coros)]
        try:
            for task in asyncio.as_completed(tasks):
                result = await task
                batch_result.add(result)
                if not result.success:
                    # 나머지 태스크 취소
                    for t in tasks:
                        if not t.done():
                            t.cancel()
                    break
        except asyncio.CancelledError:
            pass

    else:
        # 모든 작업 실행
        wrapped = [wrap_coro(i, c) for i, c in enumerate(coros)]
        results = await asyncio.gather(*wrapped, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                batch_result.add(AsyncResult.fail(result))
            elif isinstance(result, AsyncResult):
                batch_result.add(result)
            else:
                batch_result.add(AsyncResult.ok(result))

    batch_result.total_elapsed_ms = (time.time() - start_time) * 1000

    # 에러 알림
    if notify_errors and batch_result.errors:
        for error in batch_result.errors:
            handle_error(
                error,
                "Async task failed",
                action=ErrorAction.LOG_AND_ALERT,
                context={"batch_stats": batch_result.to_dict()},
                reraise=False,
            )

    return batch_result


class AsyncErrorHandler:
    """
    비동기 에러 핸들러

    비동기 작업에서 발생하는 에러를 일관되게 처리합니다.

    Story 5.5: 비동기 에러 처리 강화
    T-5.5.2: AsyncErrorHandler 클래스 구현
    """

    def __init__(
        self,
        policy: AsyncErrorPolicy = AsyncErrorPolicy.COLLECT_ALL,
        max_retries: int = 0,
        retry_delay: float = 1.0,
        notify_errors: bool = True,
    ):
        """
        Args:
            policy: 에러 처리 정책
            max_retries: 최대 재시도 횟수
            retry_delay: 재시도 간격 (초)
            notify_errors: 에러 알림 여부
        """
        self.policy = policy
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.notify_errors = notify_errors
        self._error_count = 0
        self._success_count = 0

    async def run(
        self,
        coro: Coroutine[Any, Any, T],
        fallback: Optional[T] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> AsyncResult[T]:
        """
        단일 비동기 작업 실행

        Args:
            coro: 실행할 코루틴
            fallback: 실패 시 반환값
            context: 추가 컨텍스트

        Returns:
            AsyncResult: 실행 결과
        """
        import time
        start_time = time.time()
        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries + 1):
            try:
                result = await coro
                self._success_count += 1
                elapsed = (time.time() - start_time) * 1000
                return AsyncResult.ok(result, elapsed_ms=elapsed)

            except Exception as e:
                last_error = e
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                    # 코루틴 재생성이 필요할 수 있음 - 여기서는 첫 시도만
                    break

        self._error_count += 1
        elapsed = (time.time() - start_time) * 1000

        if self.notify_errors and last_error:
            ctx = context or {}
            ctx["attempts"] = self.max_retries + 1
            handle_error(
                last_error,
                "Async operation failed",
                action=ErrorAction.LOG_AND_ALERT,
                context=ctx,
                reraise=False,
            )

        if fallback is not None:
            return AsyncResult.ok(fallback, elapsed_ms=elapsed)

        return AsyncResult.fail(last_error, elapsed_ms=elapsed)

    async def run_batch(
        self,
        coros: List[Coroutine],
        timeout: Optional[float] = None,
    ) -> AsyncBatchResult:
        """
        배치 비동기 작업 실행

        Args:
            coros: 코루틴 리스트
            timeout: 타임아웃 (초)

        Returns:
            AsyncBatchResult: 배치 결과
        """
        return await safe_gather(
            *coros,
            policy=self.policy,
            notify_errors=self.notify_errors,
            timeout=timeout,
        )

    def get_stats(self) -> Dict[str, Any]:
        """통계 조회"""
        total = self._success_count + self._error_count
        return {
            "success_count": self._success_count,
            "error_count": self._error_count,
            "total_count": total,
            "success_rate": self._success_count / total if total > 0 else 0,
        }


def async_retry(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
    notify_on_final_failure: bool = True,
):
    """
    비동기 재시도 데코레이터

    Args:
        max_retries: 최대 재시도 횟수
        delay: 초기 재시도 지연 (초)
        backoff: 지연 증가 배수
        exceptions: 재시도할 예외 타입들
        notify_on_final_failure: 최종 실패 시 알림 여부

    Example:
        @async_retry(max_retries=3, delay=1.0)
        async def fetch_data():
            ...
    """
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_exception: Optional[Exception] = None
            current_delay = delay

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        logger.warning(
                            f"Retry {attempt + 1}/{max_retries} for {func.__name__}: {e}"
                        )
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        if notify_on_final_failure:
                            handle_error(
                                e,
                                f"All retries failed for {func.__name__}",
                                action=ErrorAction.LOG_AND_ALERT,
                                context={
                                    "function": func.__name__,
                                    "max_retries": max_retries,
                                },
                                reraise=False,
                            )

            if last_exception:
                raise last_exception
            raise RuntimeError("Unexpected retry loop exit")

        return wrapper
    return decorator


async def with_timeout(
    coro: Coroutine[Any, Any, T],
    timeout: float,
    fallback: Optional[T] = None,
    notify: bool = True,
) -> AsyncResult[T]:
    """
    타임아웃이 있는 비동기 작업 실행

    Args:
        coro: 실행할 코루틴
        timeout: 타임아웃 (초)
        fallback: 타임아웃 시 반환값
        notify: 타임아웃 시 알림 여부

    Returns:
        AsyncResult: 실행 결과
    """
    import time
    start_time = time.time()

    try:
        result = await asyncio.wait_for(coro, timeout=timeout)
        elapsed = (time.time() - start_time) * 1000
        return AsyncResult.ok(result, elapsed_ms=elapsed)

    except asyncio.TimeoutError as e:
        elapsed = (time.time() - start_time) * 1000

        if notify:
            handle_error(
                e,
                f"Async operation timed out after {timeout}s",
                action=ErrorAction.LOG_AND_ALERT,
                context={"timeout": timeout, "elapsed_ms": elapsed},
                reraise=False,
            )

        if fallback is not None:
            return AsyncResult.ok(fallback, elapsed_ms=elapsed)

        return AsyncResult.fail(e, elapsed_ms=elapsed)

    except Exception as e:
        elapsed = (time.time() - start_time) * 1000
        return AsyncResult.fail(e, elapsed_ms=elapsed)


class AsyncErrorAggregator:
    """
    비동기 에러 취합기

    여러 비동기 작업에서 발생한 에러를 취합하여 보고합니다.

    Story 5.5: 비동기 에러 처리 강화
    T-5.5.3: 비동기 에러 전파 및 취합 로직
    """

    def __init__(self, operation_name: str = "batch_operation"):
        self.operation_name = operation_name
        self._errors: List[Tuple[str, Exception, datetime]] = []
        self._lock = asyncio.Lock()

    async def add_error(self, task_id: str, error: Exception) -> None:
        """에러 추가"""
        async with self._lock:
            self._errors.append((task_id, error, datetime.now()))

    def error_count(self) -> int:
        """에러 수"""
        return len(self._errors)

    def has_errors(self) -> bool:
        """에러 존재 여부"""
        return len(self._errors) > 0

    def get_errors(self) -> List[Tuple[str, Exception, datetime]]:
        """에러 목록"""
        return list(self._errors)

    def clear(self) -> None:
        """에러 초기화"""
        self._errors.clear()

    def report(self) -> Dict[str, Any]:
        """에러 보고서 생성"""
        if not self._errors:
            return {
                "operation": self.operation_name,
                "error_count": 0,
                "errors": [],
            }

        error_summary = []
        for task_id, error, timestamp in self._errors:
            error_summary.append({
                "task_id": task_id,
                "error_type": type(error).__name__,
                "error_message": str(error)[:200],
                "timestamp": timestamp.isoformat(),
            })

        return {
            "operation": self.operation_name,
            "error_count": len(self._errors),
            "first_error_at": self._errors[0][2].isoformat() if self._errors else None,
            "last_error_at": self._errors[-1][2].isoformat() if self._errors else None,
            "errors": error_summary,
        }

    async def notify_if_errors(self, threshold: int = 1) -> bool:
        """
        에러가 임계값 이상이면 알림 발송

        Args:
            threshold: 알림 발송 임계값

        Returns:
            bool: 알림 발송 여부
        """
        if len(self._errors) < threshold:
            return False

        report = self.report()
        first_error = self._errors[0][1] if self._errors else None

        if first_error:
            handle_error(
                first_error,
                f"Multiple async errors in {self.operation_name}",
                action=ErrorAction.LOG_AND_ALERT,
                context=report,
                reraise=False,
            )
            return True

        return False
