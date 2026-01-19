"""
Story 5.4: Silent Failure 제거 및 에러 알림 강화 테스트

T-5.4.1: Silent Failure 패턴 식별 가이드라인 문서화
T-5.4.2: handle_error 유틸리티 함수 구현
T-5.4.3: ErrorNotifier 클래스 구현
T-5.4.4: Story 5.4 테스트 작성 및 검증
"""

import pytest
import asyncio
from unittest.mock import Mock
from datetime import datetime

from core.error_handler import (
    ErrorAction,
    ErrorStats,
    ErrorNotifier,
    get_error_notifier,
    set_error_notifier,
    handle_error,
    error_handler,
    async_error_handler,
    ErrorBoundary,
)
from core.exceptions import (
    HantuQuantException,
    APITimeoutError,
    APIAuthenticationError,
    ErrorSeverity,
)
from core.utils.log_utils import (
    set_trace_id,
    clear_trace_id,
    set_error_context,
    ErrorContextManager,
)


class TestErrorStats:
    """ErrorStats 테스트"""

    def test_record_increments_count(self):
        """에러 기록 시 카운트 증가"""
        stats = ErrorStats()
        assert stats.total_count == 0
        stats.record()
        assert stats.total_count == 1
        stats.record()
        assert stats.total_count == 2

    def test_record_sets_last_occurrence(self):
        """마지막 발생 시각 기록"""
        stats = ErrorStats()
        assert stats.last_occurrence is None
        stats.record()
        assert stats.last_occurrence is not None
        assert isinstance(stats.last_occurrence, datetime)

    def test_count_in_window(self):
        """시간 윈도우 내 발생 횟수"""
        stats = ErrorStats()
        stats.record()
        stats.record()
        stats.record()
        count = stats.count_in_window(minutes=5)
        assert count == 3


class TestErrorNotifier:
    """ErrorNotifier 테스트"""

    def setup_method(self):
        clear_trace_id()
        set_error_context(None)

    def test_notifier_creation(self):
        """ErrorNotifier 생성"""
        notifier = ErrorNotifier()
        assert notifier._notifier is None
        assert notifier._min_severity == ErrorSeverity.WARNING

    def test_notifier_with_min_severity(self):
        """최소 심각도 설정"""
        notifier = ErrorNotifier(min_severity=ErrorSeverity.ERROR)
        assert notifier._min_severity == ErrorSeverity.ERROR

    def test_set_notifier(self):
        """알림 발송기 설정"""
        notifier = ErrorNotifier()
        mock_sender = Mock()
        notifier.set_notifier(mock_sender)
        assert notifier._notifier == mock_sender

    def test_should_notify_respects_severity(self):
        """심각도에 따른 알림 여부"""
        notifier = ErrorNotifier(min_severity=ErrorSeverity.ERROR)

        # WARNING은 ERROR보다 낮으므로 알림 안함
        warning_error = HantuQuantException(
            "warning",
            severity=ErrorSeverity.WARNING
        )
        assert notifier._should_notify(warning_error) is False

        # ERROR는 알림
        error = HantuQuantException(
            "error",
            severity=ErrorSeverity.ERROR
        )
        assert notifier._should_notify(error) is True

        # CRITICAL도 알림
        critical_error = HantuQuantException(
            "critical",
            severity=ErrorSeverity.CRITICAL
        )
        assert notifier._should_notify(critical_error) is True

    def test_rate_limiting(self):
        """Rate limiting 동작"""
        notifier = ErrorNotifier(rate_limit_count=3)

        # 처음 3개는 알림 허용
        for _ in range(3):
            error = APITimeoutError()
            assert notifier._should_notify(error) is True
            notifier._notification_count += 1

        # 4번째부터는 rate limit
        error = APITimeoutError()
        assert notifier._should_notify(error) is False

    def test_notify_without_notifier(self):
        """알림 발송기 없이 notify"""
        notifier = ErrorNotifier()
        error = APITimeoutError()
        result = notifier.notify(error)
        assert result is False

    def test_notify_with_mock_notifier(self):
        """Mock 알림 발송기로 notify"""
        mock_sender = Mock()
        mock_result = Mock()
        mock_result.success = True
        mock_sender.send.return_value = mock_result

        notifier = ErrorNotifier(notifier=mock_sender)
        error = APITimeoutError(api_name="KIS")
        result = notifier.notify(error, "Test error")

        assert result is True
        mock_sender.send.assert_called_once()

    def test_get_stats(self):
        """에러 통계 조회"""
        notifier = ErrorNotifier()
        error = APITimeoutError()
        error_key = notifier._get_error_key(error)

        # 에러 기록
        notifier._error_stats[error_key].record()
        notifier._error_stats[error_key].record()

        stats = notifier.get_stats(error_key)
        assert stats["total_count"] == 2


class TestHandleError:
    """handle_error 함수 테스트"""

    def setup_method(self):
        clear_trace_id()
        set_error_context(None)

    def test_handle_error_log_only(self):
        """LOG_ONLY 액션"""
        error = APITimeoutError()
        # 예외 발생하지 않음
        handle_error(error, "Test", action=ErrorAction.LOG_ONLY)

    def test_handle_error_log_and_raise(self):
        """LOG_AND_RAISE 액션"""
        error = APITimeoutError()
        with pytest.raises(APITimeoutError):
            handle_error(error, "Test", action=ErrorAction.LOG_AND_RAISE)

    def test_handle_error_with_context(self):
        """컨텍스트 포함 에러 처리"""
        error = APITimeoutError()
        handle_error(
            error,
            "Test",
            action=ErrorAction.LOG_ONLY,
            context={"user": "test", "action": "fetch"}
        )

    def test_handle_error_with_trace_id(self):
        """trace_id 포함 에러 처리"""
        set_trace_id("test-trace-123")
        error = APITimeoutError()
        handle_error(error, "Test", action=ErrorAction.LOG_ONLY)
        # 로그에 trace_id가 포함되어야 함 (로그 출력 확인은 생략)

    def test_handle_error_reraise_param(self):
        """reraise 파라미터"""
        error = APITimeoutError()
        with pytest.raises(APITimeoutError):
            handle_error(error, "Test", action=ErrorAction.LOG_ONLY, reraise=True)


class TestErrorHandlerDecorator:
    """error_handler 데코레이터 테스트"""

    def setup_method(self):
        clear_trace_id()
        set_error_context(None)

    def test_decorator_catches_exception(self):
        """데코레이터가 예외 처리"""
        @error_handler(action=ErrorAction.LOG_ONLY)
        def failing_func():
            raise ValueError("test")

        # 예외 발생하지 않음
        result = failing_func()
        assert result is None

    def test_decorator_with_fallback(self):
        """fallback 값 반환"""
        @error_handler(fallback=lambda: [])
        def failing_func():
            raise ValueError("test")

        result = failing_func()
        assert result == []

    def test_decorator_with_reraise(self):
        """reraise 시 예외 전파"""
        @error_handler(reraise=True)
        def failing_func():
            raise ValueError("test")

        with pytest.raises(ValueError):
            failing_func()

    def test_decorator_preserves_return(self):
        """정상 반환값 보존"""
        @error_handler()
        def normal_func():
            return "result"

        assert normal_func() == "result"

    def test_decorator_preserves_name(self):
        """함수 이름 보존"""
        @error_handler()
        def my_function():
            pass

        assert my_function.__name__ == "my_function"

    def test_decorator_catch_specific_exception(self):
        """특정 예외만 처리"""
        @error_handler(catch=ValueError, fallback=lambda: "fallback")
        def func():
            raise TypeError("should not be caught")

        with pytest.raises(TypeError):
            func()

        @error_handler(catch=ValueError, fallback=lambda: "fallback")
        def func2():
            raise ValueError("should be caught")

        assert func2() == "fallback"


class TestAsyncErrorHandler:
    """async_error_handler 데코레이터 테스트"""

    def setup_method(self):
        clear_trace_id()
        set_error_context(None)

    def test_async_decorator_catches_exception(self):
        """비동기 데코레이터가 예외 처리"""
        @async_error_handler(action=ErrorAction.LOG_ONLY)
        async def async_failing():
            raise ValueError("test")

        result = asyncio.run(async_failing())
        assert result is None

    def test_async_decorator_with_fallback(self):
        """비동기 fallback"""
        @async_error_handler(fallback=lambda: "default")
        async def async_failing():
            raise ValueError("test")

        result = asyncio.run(async_failing())
        assert result == "default"

    def test_async_decorator_with_reraise(self):
        """비동기 reraise"""
        @async_error_handler(reraise=True)
        async def async_failing():
            raise ValueError("test")

        with pytest.raises(ValueError):
            asyncio.run(async_failing())

    def test_async_decorator_preserves_return(self):
        """비동기 정상 반환값 보존"""
        @async_error_handler()
        async def async_normal():
            return "async_result"

        result = asyncio.run(async_normal())
        assert result == "async_result"


class TestErrorBoundary:
    """ErrorBoundary 테스트"""

    def setup_method(self):
        clear_trace_id()
        set_error_context(None)

    def test_boundary_no_error(self):
        """에러 없는 경우"""
        with ErrorBoundary("test_op") as boundary:
            boundary.value = "success"

        assert boundary.value == "success"
        assert boundary.has_error() is False

    def test_boundary_with_error(self):
        """에러 발생 시 처리"""
        with ErrorBoundary("test_op", reraise=False) as boundary:
            raise ValueError("test")

        assert boundary.has_error() is True
        assert isinstance(boundary.error, ValueError)

    def test_boundary_with_fallback(self):
        """fallback 값 설정"""
        with ErrorBoundary("test_op", fallback="default", reraise=False) as boundary:
            raise ValueError("test")

        assert boundary.value == "default"

    def test_boundary_reraise(self):
        """reraise 시 예외 전파"""
        with pytest.raises(ValueError):
            with ErrorBoundary("test_op", reraise=True):
                raise ValueError("test")

    def test_boundary_preserves_value(self):
        """정상 값 보존"""
        with ErrorBoundary("test_op") as boundary:
            data = {"key": "value"}
            boundary.value = data

        assert boundary.value == {"key": "value"}


class TestGlobalErrorNotifier:
    """글로벌 ErrorNotifier 테스트"""

    def test_get_error_notifier_singleton(self):
        """싱글톤 패턴"""
        notifier1 = get_error_notifier()
        notifier2 = get_error_notifier()
        assert notifier1 is notifier2

    def test_set_error_notifier(self):
        """글로벌 notifier 설정"""
        custom_notifier = ErrorNotifier(min_severity=ErrorSeverity.CRITICAL)
        set_error_notifier(custom_notifier)
        assert get_error_notifier() is custom_notifier


class TestIntegration:
    """통합 테스트"""

    def setup_method(self):
        clear_trace_id()
        set_error_context(None)

    def test_error_handler_with_context(self):
        """컨텍스트와 함께 에러 처리"""
        with ErrorContextManager("test_operation", component="TestComp"):
            @error_handler(action=ErrorAction.LOG_ONLY)
            def failing_func():
                raise APITimeoutError(api_name="KIS")

            failing_func()

    def test_nested_error_handlers(self):
        """중첩 에러 핸들러"""
        @error_handler(fallback=lambda: "outer_fallback")
        def outer_func():
            @error_handler(fallback=lambda: "inner_fallback")
            def inner_func():
                raise ValueError("inner error")
            return inner_func()

        result = outer_func()
        assert result == "inner_fallback"

    def test_hantu_exception_with_notifier(self):
        """HantuQuantException 알림 테스트"""
        mock_sender = Mock()
        mock_result = Mock()
        mock_result.success = True
        mock_sender.send.return_value = mock_result

        notifier = ErrorNotifier(
            notifier=mock_sender,
            min_severity=ErrorSeverity.WARNING
        )

        error = APIAuthenticationError(api_name="KIS")
        result = notifier.notify(error, "Auth failed")

        assert result is True
        mock_sender.send.assert_called_once()

        # 전달된 Alert 확인
        call_args = mock_sender.send.call_args
        alert = call_args[0][0]
        assert "error_code" in alert.data
        assert alert.data["error_code"] == "API_AUTH_ERROR"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
