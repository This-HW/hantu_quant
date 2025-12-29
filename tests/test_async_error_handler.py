"""
Story 5.5: 비동기 에러 처리 강화 테스트

T-5.5.1: safe_gather() 구현
T-5.5.2: AsyncErrorHandler 클래스 구현
T-5.5.3: 비동기 에러 전파 및 취합 로직
T-5.5.4: Story 5.5 테스트 작성 및 검증
"""

import pytest
import asyncio
from datetime import datetime

from core.async_error_handler import (
    AsyncErrorPolicy,
    AsyncResult,
    AsyncBatchResult,
    safe_gather,
    AsyncErrorHandler,
    async_retry,
    with_timeout,
    AsyncErrorAggregator,
)


class TestAsyncResult:
    """AsyncResult 테스트"""

    def test_ok_result(self):
        """성공 결과"""
        result = AsyncResult.ok("value", task_id="t1", elapsed_ms=100)
        assert result.success is True
        assert result.value == "value"
        assert result.error is None
        assert result.task_id == "t1"
        assert result.elapsed_ms == 100

    def test_fail_result(self):
        """실패 결과"""
        error = ValueError("test error")
        result = AsyncResult.fail(error, task_id="t1", elapsed_ms=50)
        assert result.success is False
        assert result.value is None
        assert result.error == error
        assert result.task_id == "t1"


class TestAsyncBatchResult:
    """AsyncBatchResult 테스트"""

    def test_add_success(self):
        """성공 결과 추가"""
        batch = AsyncBatchResult()
        batch.add(AsyncResult.ok("value1"))
        batch.add(AsyncResult.ok("value2"))

        assert batch.total_count == 2
        assert batch.success_count == 2
        assert batch.failure_count == 0

    def test_add_failure(self):
        """실패 결과 추가"""
        batch = AsyncBatchResult()
        batch.add(AsyncResult.ok("value"))
        batch.add(AsyncResult.fail(ValueError("error")))

        assert batch.total_count == 2
        assert batch.success_count == 1
        assert batch.failure_count == 1
        assert len(batch.errors) == 1

    def test_success_values(self):
        """성공 값 추출"""
        batch = AsyncBatchResult()
        batch.add(AsyncResult.ok("a"))
        batch.add(AsyncResult.fail(ValueError("err")))
        batch.add(AsyncResult.ok("b"))

        values = batch.success_values()
        assert values == ["a", "b"]

    def test_is_all_success(self):
        """전체 성공 확인"""
        batch = AsyncBatchResult()
        batch.add(AsyncResult.ok("a"))
        batch.add(AsyncResult.ok("b"))
        assert batch.is_all_success() is True

        batch.add(AsyncResult.fail(ValueError("err")))
        assert batch.is_all_success() is False

    def test_success_rate(self):
        """성공률 계산"""
        batch = AsyncBatchResult()
        batch.add(AsyncResult.ok("a"))
        batch.add(AsyncResult.ok("b"))
        batch.add(AsyncResult.fail(ValueError("err")))

        assert batch.success_rate() == pytest.approx(2/3)

    def test_to_dict(self):
        """딕셔너리 변환"""
        batch = AsyncBatchResult()
        batch.add(AsyncResult.ok("a"))
        batch.add(AsyncResult.fail(ValueError("err")))
        batch.total_elapsed_ms = 100

        d = batch.to_dict()
        assert d["total_count"] == 2
        assert d["success_count"] == 1
        assert d["failure_count"] == 1
        assert "ValueError" in d["error_types"]


class TestSafeGather:
    """safe_gather 테스트"""

    @pytest.mark.asyncio
    async def test_all_success(self):
        """모두 성공"""
        async def success(val):
            return val

        result = await safe_gather(
            success(1),
            success(2),
            success(3),
            notify_errors=False,
        )

        assert result.is_all_success()
        assert result.success_count == 3
        assert set(result.success_values()) == {1, 2, 3}

    @pytest.mark.asyncio
    async def test_partial_failure(self):
        """일부 실패"""
        async def success(val):
            return val

        async def fail():
            raise ValueError("error")

        result = await safe_gather(
            success(1),
            fail(),
            success(2),
            policy=AsyncErrorPolicy.COLLECT_ALL,
            notify_errors=False,
        )

        assert result.total_count == 3
        assert result.success_count == 2
        assert result.failure_count == 1
        assert len(result.errors) == 1

    @pytest.mark.asyncio
    async def test_fail_fast_policy(self):
        """FAIL_FAST 정책"""
        async def slow_success():
            await asyncio.sleep(0.1)
            return "slow"

        async def fast_fail():
            await asyncio.sleep(0.01)
            raise ValueError("fast error")

        result = await safe_gather(
            slow_success(),
            fast_fail(),
            policy=AsyncErrorPolicy.FAIL_FAST,
            notify_errors=False,
        )

        # 첫 실패 후 나머지 취소
        assert result.failure_count >= 1

    @pytest.mark.asyncio
    async def test_empty_gather(self):
        """빈 gather"""
        result = await safe_gather()
        assert result.total_count == 0

    @pytest.mark.asyncio
    async def test_with_timeout(self):
        """타임아웃"""
        async def slow():
            await asyncio.sleep(10)
            return "done"

        result = await safe_gather(
            slow(),
            timeout=0.01,
            notify_errors=False,
        )

        assert result.failure_count == 1


class TestAsyncErrorHandler:
    """AsyncErrorHandler 테스트"""

    @pytest.mark.asyncio
    async def test_run_success(self):
        """성공 실행"""
        handler = AsyncErrorHandler()

        async def success():
            return "result"

        result = await handler.run(success())
        assert result.success is True
        assert result.value == "result"

    @pytest.mark.asyncio
    async def test_run_failure(self):
        """실패 실행"""
        handler = AsyncErrorHandler(notify_errors=False)

        async def fail():
            raise ValueError("error")

        result = await handler.run(fail())
        assert result.success is False
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_run_with_fallback(self):
        """fallback 사용"""
        handler = AsyncErrorHandler(notify_errors=False)

        async def fail():
            raise ValueError("error")

        result = await handler.run(fail(), fallback="default")
        assert result.success is True
        assert result.value == "default"

    @pytest.mark.asyncio
    async def test_run_batch(self):
        """배치 실행"""
        handler = AsyncErrorHandler(notify_errors=False)

        async def task(val):
            return val

        result = await handler.run_batch([
            task(1),
            task(2),
            task(3),
        ])

        assert result.success_count == 3

    def test_get_stats(self):
        """통계 조회"""
        handler = AsyncErrorHandler()
        stats = handler.get_stats()
        assert "success_count" in stats
        assert "error_count" in stats


class TestAsyncRetry:
    """async_retry 데코레이터 테스트"""

    @pytest.mark.asyncio
    async def test_retry_success_first_try(self):
        """첫 시도 성공"""
        @async_retry(max_retries=3)
        async def always_success():
            return "success"

        result = await always_success()
        assert result == "success"

    @pytest.mark.asyncio
    async def test_retry_eventual_success(self):
        """재시도 후 성공"""
        attempts = [0]

        @async_retry(max_retries=3, delay=0.01, notify_on_final_failure=False)
        async def eventual_success():
            attempts[0] += 1
            if attempts[0] < 3:
                raise ValueError("not yet")
            return "success"

        result = await eventual_success()
        assert result == "success"
        assert attempts[0] == 3

    @pytest.mark.asyncio
    async def test_retry_all_failures(self):
        """모든 시도 실패"""
        @async_retry(max_retries=2, delay=0.01, notify_on_final_failure=False)
        async def always_fail():
            raise ValueError("always")

        with pytest.raises(ValueError):
            await always_fail()

    @pytest.mark.asyncio
    async def test_retry_specific_exceptions(self):
        """특정 예외만 재시도"""
        attempts = [0]

        @async_retry(max_retries=3, delay=0.01, exceptions=(ValueError,))
        async def fail_with_type_error():
            attempts[0] += 1
            raise TypeError("not retryable")

        with pytest.raises(TypeError):
            await fail_with_type_error()

        # TypeError는 재시도하지 않음
        assert attempts[0] == 1


class TestWithTimeout:
    """with_timeout 테스트"""

    @pytest.mark.asyncio
    async def test_success_within_timeout(self):
        """타임아웃 내 성공"""
        async def fast():
            return "result"

        result = await with_timeout(fast(), timeout=1.0)
        assert result.success is True
        assert result.value == "result"

    @pytest.mark.asyncio
    async def test_timeout_exceeded(self):
        """타임아웃 초과"""
        async def slow():
            await asyncio.sleep(10)
            return "never"

        result = await with_timeout(slow(), timeout=0.01, notify=False)
        assert result.success is False
        assert isinstance(result.error, asyncio.TimeoutError)

    @pytest.mark.asyncio
    async def test_timeout_with_fallback(self):
        """타임아웃 시 fallback"""
        async def slow():
            await asyncio.sleep(10)
            return "never"

        result = await with_timeout(
            slow(),
            timeout=0.01,
            fallback="default",
            notify=False
        )
        assert result.success is True
        assert result.value == "default"


class TestAsyncErrorAggregator:
    """AsyncErrorAggregator 테스트"""

    @pytest.mark.asyncio
    async def test_add_error(self):
        """에러 추가"""
        aggregator = AsyncErrorAggregator("test_op")
        await aggregator.add_error("task1", ValueError("error1"))
        await aggregator.add_error("task2", TypeError("error2"))

        assert aggregator.error_count() == 2
        assert aggregator.has_errors() is True

    @pytest.mark.asyncio
    async def test_get_errors(self):
        """에러 목록 조회"""
        aggregator = AsyncErrorAggregator()
        error = ValueError("test")
        await aggregator.add_error("task1", error)

        errors = aggregator.get_errors()
        assert len(errors) == 1
        assert errors[0][0] == "task1"
        assert errors[0][1] == error

    def test_report(self):
        """보고서 생성"""
        aggregator = AsyncErrorAggregator("batch_op")
        # 동기적으로 에러 추가 (테스트용)
        aggregator._errors.append(("t1", ValueError("e1"), datetime.now()))
        aggregator._errors.append(("t2", TypeError("e2"), datetime.now()))

        report = aggregator.report()
        assert report["operation"] == "batch_op"
        assert report["error_count"] == 2
        assert len(report["errors"]) == 2

    def test_clear(self):
        """에러 초기화"""
        aggregator = AsyncErrorAggregator()
        aggregator._errors.append(("t1", ValueError("e1"), datetime.now()))
        aggregator.clear()
        assert aggregator.error_count() == 0

    @pytest.mark.asyncio
    async def test_notify_if_errors(self):
        """에러 알림"""
        aggregator = AsyncErrorAggregator()

        # 에러 없으면 알림 안함
        result = await aggregator.notify_if_errors(threshold=1)
        assert result is False

        # 에러 있으면 알림
        await aggregator.add_error("task1", ValueError("error"))
        result = await aggregator.notify_if_errors(threshold=1)
        assert result is True


class TestIntegration:
    """통합 테스트"""

    @pytest.mark.asyncio
    async def test_safe_gather_with_handler(self):
        """safe_gather와 AsyncErrorHandler 통합"""
        handler = AsyncErrorHandler(
            policy=AsyncErrorPolicy.PARTIAL_SUCCESS,
            notify_errors=False
        )

        async def task(val, fail=False):
            if fail:
                raise ValueError(f"failed: {val}")
            return val * 2

        result = await handler.run_batch([
            task(1),
            task(2, fail=True),
            task(3),
        ])

        assert result.success_count == 2
        assert result.failure_count == 1
        assert set(result.success_values()) == {2, 6}

    @pytest.mark.asyncio
    async def test_aggregator_with_gather(self):
        """Aggregator와 safe_gather 통합"""
        aggregator = AsyncErrorAggregator("batch_fetch")

        async def fetch(idx):
            if idx == 2:
                error = ValueError(f"fetch {idx} failed")
                await aggregator.add_error(f"fetch_{idx}", error)
                raise error
            return f"data_{idx}"

        result = await safe_gather(
            fetch(1),
            fetch(2),
            fetch(3),
            notify_errors=False,
        )

        assert aggregator.error_count() == 1
        assert result.failure_count == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
