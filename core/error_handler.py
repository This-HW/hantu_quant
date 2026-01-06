"""
에러 처리 및 알림 모듈

Silent Failure를 방지하고 에러 발생 시 즉시 알림을 보냅니다.

Feature 5: 에러 추적 및 원인 파악 시스템
Story 5.4: Silent Failure 제거 및 에러 알림 강화
"""

import logging
import functools
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Callable, List, Type, Union
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import threading

from core.exceptions import (
    HantuQuantException,
    ErrorSeverity,
    ErrorCategory,
    is_critical,
    is_retryable,
)
from core.utils.log_utils import (
    get_context_logger,
    get_trace_id,
    get_error_context,
    ErrorContextManager,
)

logger = get_context_logger(__name__)


class ErrorAction(Enum):
    """에러 발생 시 수행할 액션"""
    LOG_ONLY = "log_only"          # 로깅만 수행
    LOG_AND_ALERT = "log_and_alert"  # 로깅 + 알림
    LOG_AND_RAISE = "log_and_raise"  # 로깅 + 예외 발생
    FULL = "full"                  # 로깅 + 알림 + 예외 발생


@dataclass
class ErrorStats:
    """에러 통계"""
    total_count: int = 0
    last_occurrence: Optional[datetime] = None
    occurrences: List[datetime] = field(default_factory=list)

    def record(self):
        """에러 발생 기록"""
        now = datetime.now()
        self.total_count += 1
        self.last_occurrence = now
        self.occurrences.append(now)

        # 최근 1시간 데이터만 유지
        cutoff = now - timedelta(hours=1)
        self.occurrences = [t for t in self.occurrences if t > cutoff]

    def count_in_window(self, minutes: int = 5) -> int:
        """지정 시간 내 발생 횟수"""
        cutoff = datetime.now() - timedelta(minutes=minutes)
        return sum(1 for t in self.occurrences if t > cutoff)


class ErrorNotifier:
    """
    에러 알림 관리자

    에러 발생 시 적절한 채널로 알림을 보냅니다.
    알림 폭주 방지를 위한 rate limiting을 지원합니다.

    Story 5.4: Silent Failure 제거 및 에러 알림 강화
    T-5.4.3: ErrorNotifier 클래스 구현
    """

    def __init__(
        self,
        notifier: Optional[Any] = None,
        min_severity: ErrorSeverity = ErrorSeverity.WARNING,
        rate_limit_window: int = 5,  # 분
        rate_limit_count: int = 10,  # 윈도우 내 최대 알림 수
    ):
        """
        Args:
            notifier: 알림 발송기 (NotificationManager 또는 BaseNotifier)
            min_severity: 최소 알림 레벨
            rate_limit_window: Rate limit 윈도우 (분)
            rate_limit_count: 윈도우 내 최대 알림 수
        """
        self._notifier = notifier
        self._min_severity = min_severity
        self._rate_limit_window = rate_limit_window
        self._rate_limit_count = rate_limit_count
        self._error_stats: Dict[str, ErrorStats] = defaultdict(ErrorStats)
        self._lock = threading.Lock()
        self._notification_count = 0
        self._notification_window_start = datetime.now()

    def set_notifier(self, notifier: Any) -> None:
        """알림 발송기 설정"""
        self._notifier = notifier

    def _get_error_key(self, error: Exception) -> str:
        """에러 식별 키 생성"""
        if isinstance(error, HantuQuantException):
            return f"{error.error_code}:{error.category.value}"
        return f"{type(error).__name__}:{str(error)[:50]}"

    def _should_notify(self, error: Exception) -> bool:
        """알림 발송 여부 결정"""
        # 심각도 체크
        if isinstance(error, HantuQuantException):
            severity_order = [
                ErrorSeverity.DEBUG,
                ErrorSeverity.INFO,
                ErrorSeverity.WARNING,
                ErrorSeverity.ERROR,
                ErrorSeverity.CRITICAL,
                ErrorSeverity.FATAL,
            ]
            try:
                if severity_order.index(error.severity) < severity_order.index(self._min_severity):
                    return False
            except ValueError:
                pass

        # Rate limit 체크
        with self._lock:
            now = datetime.now()
            if now - self._notification_window_start > timedelta(minutes=self._rate_limit_window):
                self._notification_window_start = now
                self._notification_count = 0

            if self._notification_count >= self._rate_limit_count:
                return False

        return True

    def notify(
        self,
        error: Exception,
        message: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        에러 알림 발송

        Args:
            error: 예외 객체
            message: 추가 메시지
            context: 추가 컨텍스트

        Returns:
            bool: 알림 발송 성공 여부
        """
        if not self._should_notify(error):
            return False

        # 에러 통계 기록
        error_key = self._get_error_key(error)
        with self._lock:
            self._error_stats[error_key].record()
            self._notification_count += 1

        # 알림 발송
        if self._notifier is None:
            logger.warning("ErrorNotifier: notifier not configured")
            return False

        try:
            from core.notification.alert import Alert, AlertType, AlertLevel

            # 에러 정보 수집
            alert_data = {
                "error_type": type(error).__name__,
                "error_message": str(error),
            }

            if isinstance(error, HantuQuantException):
                alert_data["error_code"] = error.error_code
                alert_data["category"] = error.category.value
                alert_data["severity"] = error.severity.value
                if error.context:
                    alert_data["error_context"] = error.context

            # trace_id 추가
            trace_id = get_trace_id()
            if trace_id:
                alert_data["trace_id"] = trace_id

            # ErrorContext 추가
            error_ctx = get_error_context()
            if error_ctx:
                alert_data["operation"] = error_ctx.operation
                if error_ctx.component:
                    alert_data["component"] = error_ctx.component

            # 추가 컨텍스트 병합
            if context:
                alert_data.update(context)

            # 알림 레벨 결정
            if isinstance(error, HantuQuantException):
                if error.severity in (ErrorSeverity.CRITICAL, ErrorSeverity.FATAL):
                    alert_level = AlertLevel.CRITICAL
                elif error.severity == ErrorSeverity.ERROR:
                    alert_level = AlertLevel.WARNING
                else:
                    alert_level = AlertLevel.INFO
            else:
                alert_level = AlertLevel.WARNING

            # Alert 생성 및 발송
            alert = Alert(
                alert_type=AlertType.SYSTEM_ERROR,
                level=alert_level,
                title=message or f"Error: {type(error).__name__}",
                message=str(error),
                data=alert_data,
                tags=["error", "auto-notification"],
            )

            result = self._notifier.send(alert)
            return result.success if hasattr(result, 'success') else bool(result)

        except Exception as e:
            logger.error(f"Failed to send error notification: {e}", exc_info=True)
            return False

    def get_stats(self, error_key: Optional[str] = None) -> Dict[str, Any]:
        """에러 통계 조회"""
        with self._lock:
            if error_key:
                stats = self._error_stats.get(error_key)
                if stats:
                    return {
                        "error_key": error_key,
                        "total_count": stats.total_count,
                        "last_occurrence": stats.last_occurrence.isoformat() if stats.last_occurrence else None,
                        "count_5min": stats.count_in_window(5),
                        "count_1hour": len(stats.occurrences),
                    }
                return {}

            return {
                key: {
                    "total_count": stats.total_count,
                    "count_5min": stats.count_in_window(5),
                }
                for key, stats in self._error_stats.items()
            }


# 글로벌 ErrorNotifier 인스턴스
_error_notifier: Optional[ErrorNotifier] = None


def get_error_notifier() -> ErrorNotifier:
    """글로벌 ErrorNotifier 반환"""
    global _error_notifier
    if _error_notifier is None:
        _error_notifier = ErrorNotifier()
    return _error_notifier


def set_error_notifier(notifier: ErrorNotifier) -> None:
    """글로벌 ErrorNotifier 설정"""
    global _error_notifier
    _error_notifier = notifier


def handle_error(
    error: Exception,
    message: Optional[str] = None,
    action: ErrorAction = ErrorAction.LOG_AND_ALERT,
    context: Optional[Dict[str, Any]] = None,
    notify: bool = True,
    reraise: bool = False,
) -> None:
    """
    에러 처리 유틸리티 함수

    Silent Failure를 방지하기 위한 표준 에러 처리 함수입니다.
    로깅, 알림, 예외 발생을 일관되게 처리합니다.

    Story 5.4: Silent Failure 제거 및 에러 알림 강화
    T-5.4.2: handle_error 유틸리티 함수 구현

    Args:
        error: 예외 객체
        message: 로그 메시지
        action: 수행할 액션
        context: 추가 컨텍스트
        notify: 알림 발송 여부 (action이 LOG_ONLY가 아닐 때)
        reraise: 예외 재발생 여부 (action이 LOG_AND_RAISE 또는 FULL일 때)

    Example:
        try:
            risky_operation()
        except Exception as e:
            handle_error(e, "Operation failed", action=ErrorAction.LOG_AND_ALERT)
    """
    ctx = context or {}

    # trace_id 추가
    trace_id = get_trace_id()
    if trace_id:
        ctx["trace_id"] = trace_id

    # ErrorContext 추가
    error_ctx = get_error_context()
    if error_ctx:
        ctx["operation"] = error_ctx.operation
        ctx["elapsed_ms"] = error_ctx.elapsed_ms()

    # 1. 항상 로깅
    log_msg = message or str(error)

    if isinstance(error, HantuQuantException):
        logger.log_error(error, log_msg, **ctx)
    else:
        logger.error(
            log_msg,
            exc_info=True,
            error_type=type(error).__name__,
            error_message=str(error),
            **ctx
        )

    # 2. 알림 발송
    should_notify = action in (ErrorAction.LOG_AND_ALERT, ErrorAction.FULL) and notify
    if should_notify:
        notifier = get_error_notifier()
        notifier.notify(error, message, ctx)

    # 3. 예외 재발생
    should_reraise = action in (ErrorAction.LOG_AND_RAISE, ErrorAction.FULL) or reraise
    if should_reraise:
        raise error


def error_handler(
    action: ErrorAction = ErrorAction.LOG_AND_ALERT,
    message: Optional[str] = None,
    notify: bool = True,
    reraise: bool = False,
    catch: Union[Type[Exception], tuple] = Exception,
    fallback: Optional[Callable] = None,
):
    """
    에러 처리 데코레이터

    함수에서 발생하는 예외를 자동으로 처리합니다.

    Args:
        action: 에러 발생 시 액션
        message: 에러 메시지 템플릿
        notify: 알림 발송 여부
        reraise: 예외 재발생 여부
        catch: 처리할 예외 타입(들)
        fallback: 에러 시 반환할 값을 생성하는 함수

    Example:
        @error_handler(action=ErrorAction.LOG_AND_ALERT)
        def risky_function():
            ...

        @error_handler(fallback=lambda: [])
        def get_items():
            ...
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except catch as e:
                error_msg = message or f"Error in {func.__name__}"
                handle_error(
                    e,
                    error_msg,
                    action=action,
                    context={"function": func.__name__},
                    notify=notify,
                    reraise=reraise,
                )

                if fallback is not None:
                    return fallback()
                return None

        return wrapper
    return decorator


def async_error_handler(
    action: ErrorAction = ErrorAction.LOG_AND_ALERT,
    message: Optional[str] = None,
    notify: bool = True,
    reraise: bool = False,
    catch: Union[Type[Exception], tuple] = Exception,
    fallback: Optional[Callable] = None,
):
    """
    비동기 에러 처리 데코레이터

    비동기 함수에서 발생하는 예외를 자동으로 처리합니다.
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except catch as e:
                error_msg = message or f"Error in {func.__name__}"
                handle_error(
                    e,
                    error_msg,
                    action=action,
                    context={"function": func.__name__, "async": True},
                    notify=notify,
                    reraise=reraise,
                )

                if fallback is not None:
                    return fallback()
                return None

        return wrapper
    return decorator


class ErrorBoundary:
    """
    에러 경계 컨텍스트 관리자

    코드 블록에서 발생하는 에러를 일관되게 처리합니다.

    Example:
        with ErrorBoundary("processing_orders", notify=True):
            process_orders()

        # 또는 fallback 사용
        with ErrorBoundary("get_data", fallback=[]) as result:
            data = get_data()
            result.value = data
    """

    def __init__(
        self,
        operation: str,
        action: ErrorAction = ErrorAction.LOG_AND_ALERT,
        notify: bool = True,
        reraise: bool = False,
        fallback: Any = None,
    ):
        self.operation = operation
        self.action = action
        self.notify = notify
        self.reraise = reraise
        self.fallback = fallback
        self.value: Any = None
        self.error: Optional[Exception] = None

    def __enter__(self) -> 'ErrorBoundary':
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.error = exc_val
            handle_error(
                exc_val,
                f"Error in {self.operation}",
                action=self.action,
                context={"operation": self.operation},
                notify=self.notify,
                reraise=self.reraise,
            )

            if self.fallback is not None:
                self.value = self.fallback

            # reraise가 False면 예외 억제
            return not self.reraise

        return False

    def has_error(self) -> bool:
        """에러 발생 여부"""
        return self.error is not None


# ============================================================================
# Silent Failure 패턴 방지 가이드라인
# Story 5.4: T-5.4.1: Silent Failure 패턴 식별 가이드라인
# ============================================================================
"""
Silent Failure 패턴 식별 가이드라인

## 문제가 되는 패턴 (Anti-patterns)

1. 빈 except 블록:
   ```python
   try:
       risky_operation()
   except:
       pass  # ❌ Silent failure
   ```

2. 로깅 없는 예외 처리:
   ```python
   try:
       risky_operation()
   except Exception:
       return None  # ❌ 에러 정보 손실
   ```

3. 일반적인 catch-all:
   ```python
   try:
       specific_operation()
   except Exception as e:
       print(str(e))  # ❌ 컨텍스트 없음
   ```

## 권장 패턴 (Best Practices)

1. handle_error 사용:
   ```python
   try:
       risky_operation()
   except Exception as e:
       handle_error(e, "Operation failed", action=ErrorAction.LOG_AND_ALERT)
   ```

2. error_handler 데코레이터:
   ```python
   @error_handler(action=ErrorAction.LOG_AND_ALERT)
   def risky_function():
       ...
   ```

3. ErrorBoundary 컨텍스트:
   ```python
   with ErrorBoundary("processing", notify=True) as boundary:
       process_data()
   if boundary.has_error():
       use_fallback()
   ```

4. 구체적인 예외 처리:
   ```python
   try:
       api_call()
   except APITimeoutError as e:
       handle_error(e, "API timeout", action=ErrorAction.LOG_AND_ALERT)
       return cached_data()
   except APIAuthenticationError as e:
       handle_error(e, "Auth failed", action=ErrorAction.FULL)  # 재발생
   ```

## 검사 방법

코드에서 다음 패턴을 검색:
- `except:` (bare except)
- `except Exception:` 다음에 `pass`
- `except Exception:` 다음에 `return`만 있는 경우
- logging 없는 except 블록
"""
