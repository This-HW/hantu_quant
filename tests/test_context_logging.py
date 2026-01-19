"""
Story 5.2: Context-aware Error Logging 테스트

T-5.2.1: ErrorContext 클래스 설계
T-5.2.2: ContextLogger 래퍼 클래스 구현
T-5.2.3: @log_context 데코레이터 구현
T-5.2.4: Story 5.2 테스트 작성 및 검증
"""

import pytest
import time
import asyncio

from core.utils.log_utils import (
    # ErrorContext
    ErrorContext,
    get_error_context,
    set_error_context,
    ErrorContextManager,
    # ContextLogger
    ContextLogger,
    get_context_logger,
    # Decorators
    log_context,
    log_async_context,
    # Trace ID
    set_trace_id,
    clear_trace_id,
)
from core.exceptions import APITimeoutError


class TestErrorContext:
    """ErrorContext 클래스 테스트"""

    def setup_method(self):
        """테스트 전 컨텍스트 초기화"""
        set_error_context(None)
        clear_trace_id()

    def test_error_context_creation(self):
        """ErrorContext 생성"""
        ctx = ErrorContext(operation="test_operation")
        assert ctx.operation == "test_operation"
        assert ctx.trace_id is not None
        assert ctx.start_time > 0

    def test_error_context_with_all_fields(self):
        """모든 필드 포함 생성"""
        ctx = ErrorContext(
            operation="order_execution",
            component="TradingEngine",
            stock_code="005930",
            order_id="ORD001",
            request_id="REQ001",
            user_context={"user": "test"}
        )
        assert ctx.component == "TradingEngine"
        assert ctx.stock_code == "005930"
        assert ctx.order_id == "ORD001"
        assert ctx.request_id == "REQ001"
        assert ctx.user_context["user"] == "test"

    def test_elapsed_time(self):
        """경과 시간 측정"""
        ctx = ErrorContext(operation="test")
        time.sleep(0.01)  # 10ms
        elapsed = ctx.elapsed_time()
        assert elapsed >= 0.01

    def test_elapsed_ms(self):
        """밀리초 경과 시간"""
        ctx = ErrorContext(operation="test")
        time.sleep(0.01)
        elapsed_ms = ctx.elapsed_ms()
        assert elapsed_ms >= 10

    def test_to_dict(self):
        """딕셔너리 변환"""
        ctx = ErrorContext(
            operation="test",
            component="TestComponent",
            stock_code="005930"
        )
        d = ctx.to_dict()
        assert d["operation"] == "test"
        assert d["trace_id"] is not None
        assert d["component"] == "TestComponent"
        assert d["stock_code"] == "005930"
        assert "elapsed_ms" in d

    def test_with_user_context(self):
        """사용자 컨텍스트 추가"""
        ctx = ErrorContext(operation="test")
        ctx.with_user_context(key1="value1", key2="value2")
        assert ctx.user_context["key1"] == "value1"
        assert ctx.user_context["key2"] == "value2"

    def test_parent_context(self):
        """부모 컨텍스트"""
        parent = ErrorContext(operation="parent_op")
        child = ErrorContext(operation="child_op", parent_context=parent)
        assert child.parent_context == parent
        d = child.to_dict()
        assert d["parent_operation"] == "parent_op"


class TestErrorContextManager:
    """ErrorContextManager 테스트"""

    def setup_method(self):
        set_error_context(None)
        clear_trace_id()

    def test_context_manager_basic(self):
        """기본 컨텍스트 관리자"""
        assert get_error_context() is None

        with ErrorContextManager("test_operation") as ctx:
            assert get_error_context() is not None
            assert get_error_context().operation == "test_operation"

        assert get_error_context() is None

    def test_context_manager_with_component(self):
        """컴포넌트 포함"""
        with ErrorContextManager("op", component="Comp") as ctx:
            assert ctx.component == "Comp"
            assert get_error_context().component == "Comp"

    def test_nested_context_managers(self):
        """중첩 컨텍스트 관리자"""
        with ErrorContextManager("outer") as outer_ctx:
            assert get_error_context().operation == "outer"

            with ErrorContextManager("inner") as inner_ctx:
                assert get_error_context().operation == "inner"
                assert inner_ctx.parent_context == outer_ctx

            assert get_error_context().operation == "outer"

        assert get_error_context() is None

    def test_context_manager_exception_handling(self):
        """예외 발생 시 컨텍스트 복원"""
        try:
            with ErrorContextManager("test"):
                assert get_error_context() is not None
                raise ValueError("test error")
        except ValueError:
            pass

        assert get_error_context() is None

    def test_context_manager_with_user_context(self):
        """사용자 컨텍스트 전달"""
        with ErrorContextManager("op", user_id="123", action="buy") as ctx:
            assert ctx.user_context["user_id"] == "123"
            assert ctx.user_context["action"] == "buy"


class TestContextLogger:
    """ContextLogger 테스트"""

    def setup_method(self):
        set_error_context(None)
        clear_trace_id()

    def test_context_logger_creation(self):
        """ContextLogger 생성"""
        logger = get_context_logger("test")
        assert isinstance(logger, ContextLogger)

    def test_context_logger_log_levels(self):
        """로그 레벨 메서드"""
        logger = get_context_logger("test")
        # 각 레벨 호출 (예외 없이 동작하면 성공)
        logger.debug("debug message")
        logger.info("info message")
        logger.warning("warning message")
        logger.error("error message")
        logger.critical("critical message")

    def test_context_logger_with_context(self):
        """컨텍스트와 함께 로깅"""
        logger = get_context_logger("test")
        set_trace_id("test-trace")

        with ErrorContextManager("test_op", component="TestComp"):
            # 컨텍스트 데이터 확인
            ctx_data = logger._get_context_data()
            assert ctx_data["trace_id"] == "test-trace"
            assert ctx_data["context"]["operation"] == "test_op"

    def test_context_logger_log_error(self):
        """예외 로깅"""
        logger = get_context_logger("test")
        error = APITimeoutError(api_name="KIS")

        # 예외 없이 동작하면 성공
        logger.log_error(error, "API timeout occurred")

    def test_context_logger_exception_method(self):
        """exception 메서드"""
        logger = get_context_logger("test")
        try:
            raise ValueError("test")
        except ValueError:
            logger.exception("An error occurred")


class TestLogContextDecorator:
    """log_context 데코레이터 테스트"""

    def setup_method(self):
        set_error_context(None)
        clear_trace_id()

    def test_decorator_sets_context(self):
        """데코레이터가 컨텍스트를 설정"""
        @log_context("test_operation", log_entry=False, log_exit=False)
        def test_func():
            ctx = get_error_context()
            return ctx.operation if ctx else None

        result = test_func()
        assert result == "test_operation"

    def test_decorator_with_component(self):
        """컴포넌트 포함 데코레이터"""
        @log_context("op", component="TestComponent", log_entry=False, log_exit=False)
        def test_func():
            ctx = get_error_context()
            return ctx.component if ctx else None

        result = test_func()
        assert result == "TestComponent"

    def test_decorator_restores_context(self):
        """데코레이터 후 컨텍스트 복원"""
        @log_context("inner", log_entry=False, log_exit=False)
        def inner_func():
            return get_error_context().operation

        with ErrorContextManager("outer"):
            inner_func()
            assert get_error_context().operation == "outer"

    def test_decorator_preserves_return_value(self):
        """반환값 보존"""
        @log_context("op", log_entry=False, log_exit=False)
        def test_func():
            return "result"

        assert test_func() == "result"

    def test_decorator_preserves_function_name(self):
        """함수 이름 보존 (functools.wraps)"""
        @log_context("op")
        def my_function():
            pass

        assert my_function.__name__ == "my_function"

    def test_decorator_propagates_exceptions(self):
        """예외 전파"""
        @log_context("op", log_entry=False, log_exit=False)
        def test_func():
            raise ValueError("test error")

        with pytest.raises(ValueError):
            test_func()

    def test_decorator_with_args(self):
        """인자 있는 함수"""
        @log_context("op", log_entry=False, log_exit=False)
        def test_func(a, b, c=None):
            return a + b + (c or 0)

        assert test_func(1, 2, c=3) == 6


class TestLogAsyncContextDecorator:
    """log_async_context 데코레이터 테스트"""

    def setup_method(self):
        set_error_context(None)
        clear_trace_id()

    def test_async_decorator_sets_context(self):
        """비동기 데코레이터가 컨텍스트를 설정"""
        @log_async_context("async_op", log_entry=False, log_exit=False)
        async def async_func():
            ctx = get_error_context()
            return ctx.operation if ctx else None

        result = asyncio.run(async_func())
        assert result == "async_op"

    def test_async_decorator_with_component(self):
        """컴포넌트 포함 비동기 데코레이터"""
        @log_async_context("op", component="AsyncComp", log_entry=False, log_exit=False)
        async def async_func():
            ctx = get_error_context()
            return ctx.component if ctx else None

        result = asyncio.run(async_func())
        assert result == "AsyncComp"

    def test_async_decorator_preserves_return_value(self):
        """비동기 반환값 보존"""
        @log_async_context("op", log_entry=False, log_exit=False)
        async def async_func():
            return "async_result"

        result = asyncio.run(async_func())
        assert result == "async_result"

    def test_async_decorator_propagates_exceptions(self):
        """비동기 예외 전파"""
        @log_async_context("op", log_entry=False, log_exit=False)
        async def async_func():
            raise ValueError("async error")

        with pytest.raises(ValueError):
            asyncio.run(async_func())

    def test_async_decorator_with_await(self):
        """await 포함 비동기 함수"""
        @log_async_context("op", log_entry=False, log_exit=False)
        async def async_func():
            await asyncio.sleep(0.01)
            return get_error_context().operation

        result = asyncio.run(async_func())
        assert result == "op"


class TestIntegration:
    """통합 테스트"""

    def setup_method(self):
        set_error_context(None)
        clear_trace_id()

    def test_trace_id_propagation(self):
        """trace_id 전파"""
        set_trace_id("test-trace-123")

        with ErrorContextManager("op1"):
            ctx1 = get_error_context()
            with ErrorContextManager("op2"):
                ctx2 = get_error_context()
                # 모든 컨텍스트가 같은 trace_id 공유
                assert ctx1.trace_id == "test-trace-123"
                assert ctx2.trace_id == "test-trace-123"

    def test_context_logger_with_exception(self):
        """예외 발생 시 컨텍스트 로깅"""
        logger = get_context_logger("test")

        @log_context("failing_op", component="FailComp", log_entry=False, log_exit=False)
        def failing_func():
            error = APITimeoutError(api_name="TestAPI")
            raise error

        try:
            failing_func()
        except APITimeoutError as e:
            # 예외를 로깅할 수 있음
            logger.log_error(e, "Operation failed")

    def test_nested_decorators(self):
        """중첩 데코레이터"""
        @log_context("outer_op", log_entry=False, log_exit=False)
        def outer_func():
            @log_context("inner_op", log_entry=False, log_exit=False)
            def inner_func():
                ctx = get_error_context()
                return ctx.operation, ctx.parent_context.operation

            return inner_func()

        inner_op, outer_op = outer_func()
        assert inner_op == "inner_op"
        assert outer_op == "outer_op"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
