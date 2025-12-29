"""
Story 5.3: Distributed Tracing 구현 테스트

T-5.3.1: trace_id 생성 및 전파 로직
T-5.3.2: SpanContext 클래스 구현
T-5.3.3: @trace_operation 데코레이터 구현
T-5.3.4: Story 5.3 테스트 작성 및 검증
"""

import pytest
import time
import asyncio
import re

from core.utils.log_utils import (
    # Span
    SpanContext,
    SpanStatus,
    SpanContextManager,
    get_current_span,
    set_current_span,
    generate_span_id,
    generate_trace_id,
    # Decorators
    trace_operation,
    trace_async_operation,
    # TracingContext
    TracingContext,
    # Trace ID
    get_trace_id,
    set_trace_id,
    clear_trace_id,
)


class TestSpanIdGeneration:
    """Span ID 생성 테스트"""

    def test_generate_span_id(self):
        """span_id 생성"""
        span_id = generate_span_id()
        assert len(span_id) == 16
        assert re.match(r'^[0-9a-f]{16}$', span_id)

    def test_generate_trace_id(self):
        """trace_id 생성"""
        trace_id = generate_trace_id()
        assert len(trace_id) == 32
        assert re.match(r'^[0-9a-f]{32}$', trace_id)

    def test_unique_span_ids(self):
        """고유한 span_id 생성"""
        ids = [generate_span_id() for _ in range(100)]
        assert len(set(ids)) == 100

    def test_unique_trace_ids(self):
        """고유한 trace_id 생성"""
        ids = [generate_trace_id() for _ in range(100)]
        assert len(set(ids)) == 100


class TestSpanContext:
    """SpanContext 클래스 테스트"""

    def setup_method(self):
        set_current_span(None)
        clear_trace_id()

    def test_span_context_creation(self):
        """SpanContext 생성"""
        span = SpanContext(operation_name="test_op")
        assert span.operation_name == "test_op"
        assert span.span_id is not None
        assert span.trace_id is not None
        assert span.status == SpanStatus.UNSET

    def test_span_context_with_parent(self):
        """부모 span_id 포함"""
        span = SpanContext(
            operation_name="child_op",
            parent_span_id="parent123456789abc"
        )
        assert span.parent_span_id == "parent123456789abc"

    def test_span_finish(self):
        """Span 종료"""
        span = SpanContext(operation_name="test")
        span.finish()
        assert span.status == SpanStatus.OK
        assert span.end_time is not None

    def test_span_finish_with_error(self):
        """에러와 함께 Span 종료"""
        span = SpanContext(operation_name="test")
        error = ValueError("test error")
        span.finish_with_error(error)
        assert span.status == SpanStatus.ERROR
        assert span.tags["error.type"] == "ValueError"
        assert span.tags["error.message"] == "test error"
        assert len(span.logs) == 1

    def test_duration_ms(self):
        """Span 지속 시간"""
        span = SpanContext(operation_name="test")
        time.sleep(0.01)
        span.finish()
        duration = span.duration_ms()
        assert duration is not None
        assert duration >= 10

    def test_set_tag(self):
        """태그 설정"""
        span = SpanContext(operation_name="test")
        span.set_tag("key1", "value1").set_tag("key2", 123)
        assert span.tags["key1"] == "value1"
        assert span.tags["key2"] == 123

    def test_add_log(self):
        """로그 추가"""
        span = SpanContext(operation_name="test")
        span.add_log("event1", "message1", extra="data")
        assert len(span.logs) == 1
        assert span.logs[0]["event"] == "event1"
        assert span.logs[0]["message"] == "message1"
        assert span.logs[0]["extra"] == "data"

    def test_to_dict(self):
        """딕셔너리 변환"""
        span = SpanContext(
            operation_name="test",
            component="TestComp",
        )
        span.set_tag("key", "value")
        span.finish()

        d = span.to_dict()
        assert d["operation_name"] == "test"
        assert d["span_id"] is not None
        assert d["trace_id"] is not None
        assert d["status"] == "OK"
        assert d["tags"]["key"] == "value"
        assert d["duration_ms"] is not None

    def test_to_log_dict(self):
        """로그용 축약 딕셔너리"""
        span = SpanContext(operation_name="test")
        span.finish()
        d = span.to_log_dict()
        assert "trace_id" in d
        assert "span_id" in d
        assert "operation" in d
        assert "duration_ms" in d
        assert "status" in d


class TestSpanContextManager:
    """SpanContextManager 테스트"""

    def setup_method(self):
        set_current_span(None)
        clear_trace_id()

    def test_basic_span_context_manager(self):
        """기본 컨텍스트 관리자"""
        assert get_current_span() is None

        with SpanContextManager("test_op") as span:
            assert get_current_span() == span
            assert span.operation_name == "test_op"

        assert get_current_span() is None
        assert span.status == SpanStatus.OK

    def test_span_with_component(self):
        """컴포넌트 포함"""
        with SpanContextManager("op", component="TestComp") as span:
            assert span.component == "TestComp"

    def test_span_with_tags(self):
        """태그 포함"""
        with SpanContextManager("op", key1="val1", key2=123) as span:
            assert span.tags["key1"] == "val1"
            assert span.tags["key2"] == 123

    def test_nested_spans(self):
        """중첩 span"""
        with SpanContextManager("outer_op") as outer_span:
            outer_trace = outer_span.trace_id

            with SpanContextManager("inner_op") as inner_span:
                # 같은 trace_id 공유
                assert inner_span.trace_id == outer_trace
                # 부모-자식 관계
                assert inner_span.parent_span_id == outer_span.span_id
                # 현재 span은 inner
                assert get_current_span() == inner_span

            # inner 종료 후 outer로 복원
            assert get_current_span() == outer_span

    def test_span_exception_handling(self):
        """예외 발생 시 에러 상태"""
        try:
            with SpanContextManager("failing_op") as span:
                raise ValueError("test error")
        except ValueError:
            pass

        assert span.status == SpanStatus.ERROR
        assert get_current_span() is None


class TestTraceOperation:
    """trace_operation 데코레이터 테스트"""

    def setup_method(self):
        set_current_span(None)
        clear_trace_id()

    def test_decorator_creates_span(self):
        """데코레이터가 span 생성"""
        @trace_operation("test_op", log_span=False)
        def test_func():
            span = get_current_span()
            return span.operation_name if span else None

        result = test_func()
        assert result == "test_op"

    def test_decorator_with_component(self):
        """컴포넌트 포함 데코레이터"""
        @trace_operation("op", component="TestComp", log_span=False)
        def test_func():
            span = get_current_span()
            return span.component if span else None

        result = test_func()
        assert result == "TestComp"

    def test_decorator_preserves_return_value(self):
        """반환값 보존"""
        @trace_operation("op", log_span=False)
        def test_func():
            return "result"

        assert test_func() == "result"

    def test_decorator_preserves_function_name(self):
        """함수 이름 보존"""
        @trace_operation("op", log_span=False)
        def my_function():
            pass

        assert my_function.__name__ == "my_function"

    def test_decorator_propagates_exceptions(self):
        """예외 전파"""
        @trace_operation("op", log_span=False)
        def failing_func():
            raise ValueError("error")

        with pytest.raises(ValueError):
            failing_func()

    def test_decorator_with_default_tags(self):
        """기본 태그 포함"""
        @trace_operation("op", log_span=False, env="test", version="1.0")
        def test_func():
            span = get_current_span()
            return span.tags if span else {}

        tags = test_func()
        assert tags["env"] == "test"
        assert tags["version"] == "1.0"

    def test_nested_traced_functions(self):
        """중첩 추적 함수"""
        @trace_operation("outer", log_span=False)
        def outer_func():
            outer_span = get_current_span()
            inner_result = inner_func()
            return outer_span.span_id, inner_result

        @trace_operation("inner", log_span=False)
        def inner_func():
            inner_span = get_current_span()
            return inner_span.parent_span_id

        outer_span_id, inner_parent_span_id = outer_func()
        assert outer_span_id == inner_parent_span_id


class TestTraceAsyncOperation:
    """trace_async_operation 데코레이터 테스트"""

    def setup_method(self):
        set_current_span(None)
        clear_trace_id()

    def test_async_decorator_creates_span(self):
        """비동기 데코레이터가 span 생성"""
        @trace_async_operation("async_op", log_span=False)
        async def async_func():
            span = get_current_span()
            return span.operation_name if span else None

        result = asyncio.run(async_func())
        assert result == "async_op"

    def test_async_decorator_with_component(self):
        """컴포넌트 포함 비동기 데코레이터"""
        @trace_async_operation("op", component="AsyncComp", log_span=False)
        async def async_func():
            span = get_current_span()
            return span.component if span else None

        result = asyncio.run(async_func())
        assert result == "AsyncComp"

    def test_async_decorator_preserves_return(self):
        """비동기 반환값 보존"""
        @trace_async_operation("op", log_span=False)
        async def async_func():
            return "async_result"

        result = asyncio.run(async_func())
        assert result == "async_result"

    def test_async_decorator_propagates_exceptions(self):
        """비동기 예외 전파"""
        @trace_async_operation("op", log_span=False)
        async def async_func():
            raise ValueError("async error")

        with pytest.raises(ValueError):
            asyncio.run(async_func())

    def test_async_sets_async_tag(self):
        """async 태그 설정"""
        @trace_async_operation("op", log_span=False)
        async def async_func():
            span = get_current_span()
            return span.tags.get("async") if span else None

        result = asyncio.run(async_func())
        assert result is True


class TestTracingContext:
    """TracingContext 테스트"""

    def setup_method(self):
        set_current_span(None)
        clear_trace_id()

    def test_tracing_context_basic(self):
        """기본 TracingContext"""
        with TracingContext("request") as ctx:
            assert ctx.trace_id is not None
            assert get_trace_id() == ctx.trace_id
            assert get_current_span() is not None

        assert get_current_span() is None

    def test_tracing_context_with_custom_trace_id(self):
        """커스텀 trace_id"""
        with TracingContext("request", trace_id="custom-trace-123") as ctx:
            assert ctx.trace_id == "custom-trace-123"
            assert get_trace_id() == "custom-trace-123"

    def test_tracing_context_with_tags(self):
        """태그 포함 TracingContext"""
        with TracingContext("request", user_id="123", endpoint="/api") as ctx:
            assert ctx.tags["user_id"] == "123"
            assert ctx.tags["endpoint"] == "/api"

    def test_tracing_context_spans_share_trace_id(self):
        """TracingContext 내 span들이 trace_id 공유"""
        with TracingContext("request") as ctx:
            trace_id = ctx.trace_id

            with SpanContextManager("operation1") as span1:
                assert span1.trace_id == trace_id

            with SpanContextManager("operation2") as span2:
                assert span2.trace_id == trace_id

    def test_tracing_context_exception_handling(self):
        """예외 발생 시 처리"""
        try:
            with TracingContext("failing_request") as ctx:
                raise ValueError("request error")
        except ValueError:
            pass

        assert ctx.root_span.status == SpanStatus.ERROR
        assert get_current_span() is None


class TestTraceIdPropagation:
    """trace_id 전파 테스트"""

    def setup_method(self):
        set_current_span(None)
        clear_trace_id()

    def test_trace_id_propagates_through_spans(self):
        """span 간 trace_id 전파"""
        with TracingContext("request") as ctx:
            root_trace = ctx.trace_id

            @trace_operation("op1", log_span=False)
            def func1():
                span = get_current_span()
                return span.trace_id if span else None

            @trace_operation("op2", log_span=False)
            def func2():
                span = get_current_span()
                return span.trace_id if span else None

            assert func1() == root_trace
            assert func2() == root_trace

    def test_nested_functions_share_trace_id(self):
        """중첩 함수들이 trace_id 공유"""
        collected_trace_ids = []

        @trace_operation("outer", log_span=False)
        def outer_func():
            span = get_current_span()
            collected_trace_ids.append(span.trace_id)
            inner_func()

        @trace_operation("inner", log_span=False)
        def inner_func():
            span = get_current_span()
            collected_trace_ids.append(span.trace_id)
            deepest_func()

        @trace_operation("deepest", log_span=False)
        def deepest_func():
            span = get_current_span()
            collected_trace_ids.append(span.trace_id)

        outer_func()

        # 모든 함수가 같은 trace_id 사용
        assert len(set(collected_trace_ids)) == 1

    def test_parent_child_relationship(self):
        """부모-자식 관계"""
        span_ids = {}

        @trace_operation("level1", log_span=False)
        def level1():
            span = get_current_span()
            span_ids["level1"] = span.span_id
            span_ids["level1_parent"] = span.parent_span_id
            level2()

        @trace_operation("level2", log_span=False)
        def level2():
            span = get_current_span()
            span_ids["level2"] = span.span_id
            span_ids["level2_parent"] = span.parent_span_id
            level3()

        @trace_operation("level3", log_span=False)
        def level3():
            span = get_current_span()
            span_ids["level3"] = span.span_id
            span_ids["level3_parent"] = span.parent_span_id

        level1()

        # level1 -> level2 -> level3 관계 확인
        assert span_ids["level2_parent"] == span_ids["level1"]
        assert span_ids["level3_parent"] == span_ids["level2"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
