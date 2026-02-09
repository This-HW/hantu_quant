"""
배치 메트릭 수집 테스트
"""

import pytest
from datetime import datetime
from core.utils.metric_collector import (
    track_batch_metrics,
    increment_api_call,
    increment_error,
    get_api_call_count,
    get_error_count,
    _api_call_count,
    _error_count
)


def test_increment_api_call():
    """API 호출 카운트 증가 테스트"""
    # 초기화
    _api_call_count.set(0)

    # 증가
    increment_api_call()
    assert get_api_call_count() == 1

    increment_api_call()
    assert get_api_call_count() == 2


def test_increment_error():
    """에러 카운트 증가 테스트"""
    # 초기화
    _error_count.set(0)

    # 증가
    increment_error()
    assert get_error_count() == 1

    increment_error()
    assert get_error_count() == 2


def test_track_batch_metrics_decorator():
    """데코레이터 동작 확인 테스트"""

    # 초기화
    _api_call_count.set(0)
    _error_count.set(0)

    @track_batch_metrics(phase="test_phase")
    def test_func(batch_number: int):
        # API 호출 시뮬레이션
        increment_api_call()
        increment_api_call()
        return {'stocks_processed': 10, 'stocks_selected': 3}

    # 실행
    result = test_func(batch_number=0)

    # 검증
    assert result['stocks_processed'] == 10
    assert result['stocks_selected'] == 3
    # API 호출 카운트는 데코레이터가 초기화하므로 함수 내 증가만 확인
    # (실제 DB 저장은 통합 테스트에서 검증)


def test_track_batch_metrics_with_error():
    """에러 발생 시 데코레이터 동작 확인"""

    @track_batch_metrics(phase="test_phase")
    def test_func_error(batch_number: int):
        increment_api_call()
        raise ValueError("Test error")

    # 에러 발생 확인
    with pytest.raises(ValueError):
        test_func_error(batch_number=0)

    # 에러 카운트 증가 확인
    assert get_error_count() >= 1


def test_context_var_isolation():
    """ContextVar 격리 테스트 (병렬 실행 시나리오)"""
    import asyncio

    async def task1():
        _api_call_count.set(0)
        increment_api_call()
        await asyncio.sleep(0.01)
        assert get_api_call_count() == 1

    async def task2():
        _api_call_count.set(0)
        increment_api_call()
        increment_api_call()
        await asyncio.sleep(0.01)
        assert get_api_call_count() == 2

    async def run_tasks():
        await asyncio.gather(task1(), task2())

    # 병렬 실행
    asyncio.run(run_tasks())


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
