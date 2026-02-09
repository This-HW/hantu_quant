"""
배치 메트릭 수집 모듈
Phase 2 배치 실행 시 메트릭을 추적하고 DB에 저장
"""

from functools import wraps
from datetime import datetime
from typing import Callable, Dict
from contextvars import ContextVar

from core.utils.log_utils import get_logger

logger = get_logger(__name__)

# ContextVar로 스레드 안전성 보장
_api_call_count: ContextVar[int] = ContextVar('api_call_count', default=0)
_error_count: ContextVar[int] = ContextVar('error_count', default=0)


def track_batch_metrics(phase: str):
    """배치 메트릭 추적 데코레이터

    Args:
        phase: 페이즈 이름 (예: "phase2")

    Returns:
        데코레이터 함수
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            from core.database.models import BatchMetrics
            from core.database.unified_db import get_session

            # 배치 번호 추출
            batch_number = kwargs.get('batch_number', 0)

            # 메트릭 초기화
            _api_call_count.set(0)
            _error_count.set(0)
            start_time = datetime.now()

            logger.info(f"배치 #{batch_number} 메트릭 추적 시작")

            try:
                # 함수 실행
                result = func(*args, **kwargs)

                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()

                # 결과에서 메트릭 추출
                stocks_processed = result.get('stocks_processed', 0) if isinstance(result, dict) else 0
                stocks_selected = result.get('stocks_selected', 0) if isinstance(result, dict) else 0

                # DB 저장
                try:
                    with get_session() as session:
                        metric = BatchMetrics(
                            phase_name=phase,
                            batch_number=batch_number,
                            start_time=start_time,
                            end_time=end_time,
                            duration_seconds=duration,
                            api_calls_count=_api_call_count.get(),
                            stocks_processed=stocks_processed,
                            stocks_selected=stocks_selected,
                            error_count=_error_count.get()
                        )
                        session.add(metric)
                        session.commit()

                        logger.info(
                            f"배치 메트릭 저장: {phase} 배치 #{batch_number}, "
                            f"{duration:.2f}초, {stocks_processed}종목 처리, "
                            f"API 호출: {_api_call_count.get()}회, 에러: {_error_count.get()}건"
                        )
                except Exception as e:
                    logger.error(f"배치 메트릭 저장 실패: {e}", exc_info=True)

                return result

            except Exception as e:
                _error_count.set(_error_count.get() + 1)
                logger.error(f"배치 실행 중 에러 발생: {e}", exc_info=True)
                raise

        return wrapper
    return decorator


def increment_api_call():
    """API 호출 수 증가"""
    _api_call_count.set(_api_call_count.get() + 1)


def increment_error():
    """에러 수 증가"""
    _error_count.set(_error_count.get() + 1)


def get_api_call_count() -> int:
    """현재 API 호출 수 반환"""
    return _api_call_count.get()


def get_error_count() -> int:
    """현재 에러 수 반환"""
    return _error_count.get()
