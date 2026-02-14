"""
Redis 헬스 체크 유틸리티

Redis 모니터링을 간편하게 수행하기 위한 헬퍼 함수들을 제공합니다.

Feature: Redis 자동 모니터링
"""

from typing import Optional, Dict, Any, TypedDict
from datetime import datetime

from core.monitoring.redis_monitor import (
    RedisMonitor,
    RedisMetricsData,
    HealthStatus,
)
from core.utils.log_utils import get_logger

logger = get_logger(__name__)


# ========== 타입 정의 ==========

class RedisStatusDict(TypedDict):
    """Redis 상태 딕셔너리 타입 (타입 안전성 보장)"""
    available: bool
    fallback_mode: bool
    status: str
    memory_usage: float
    hit_rate: float
    total_keys: int
    latency_ms: float


# 글로벌 모니터 인스턴스 (싱글톤)
import threading

_monitor_instance: Optional[RedisMonitor] = None
_monitor_lock = threading.Lock()


def get_redis_monitor() -> RedisMonitor:
    """RedisMonitor 싱글톤 인스턴스 반환 (thread-safe)

    Returns:
        RedisMonitor 인스턴스
    """
    global _monitor_instance

    # Double-checked locking으로 성능과 안전성 보장
    if _monitor_instance is None:
        with _monitor_lock:
            # 락 획득 후 다시 확인 (다른 스레드가 이미 생성했을 수 있음)
            if _monitor_instance is None:
                _monitor_instance = RedisMonitor()

    return _monitor_instance


def check_redis_health() -> Dict[str, Any]:
    """
    Redis 헬스 체크 수행 (간편 API)

    Returns:
        Dict: {
            'status': 'OK' | 'WARNING' | 'CRITICAL' | 'ERROR',
            'metrics': RedisMetricsData 또는 None,
            'alert_message': str 또는 None,
            'timestamp': str
        }
    """
    monitor = get_redis_monitor()

    try:
        # 메트릭 수집
        metrics = monitor.collect_metrics()

        if metrics is None:
            return {
                'status': 'ERROR',
                'metrics': None,
                'alert_message': '❌ Redis 메트릭 수집 실패',
                'timestamp': datetime.now().isoformat(),
            }

        # 헬스 상태 확인
        health = monitor.check_health(metrics)

        # 알림 메시지 생성 (WARNING/CRITICAL/ERROR만)
        alert_message = monitor.get_alert_message(metrics, health)

        return {
            'status': health.value,
            'metrics': metrics,
            'alert_message': alert_message,
            'timestamp': datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error("Redis health check failed", exc_info=True)
        return {
            'status': 'ERROR',
            'metrics': None,
            'alert_message': 'Redis health check unavailable',
            'timestamp': datetime.now().isoformat(),
        }


def collect_and_save_metrics() -> bool:
    """
    Redis 메트릭 수집 및 DB 저장

    SystemMonitor 등에서 주기적으로 호출하기 위한 함수

    Returns:
        bool: 성공 여부
    """
    monitor = get_redis_monitor()

    try:
        # 메트릭 수집
        metrics = monitor.collect_metrics()

        if metrics is None:
            logger.warning("Redis 메트릭 수집 실패 (None 반환)")
            return False

        # DB 저장
        success = monitor.save_metrics(metrics)

        if success:
            logger.debug(
                f"Redis 메트릭 저장 완료: "
                f"메모리={metrics.memory_usage_percent}%, "
                f"히트율={metrics.hit_rate_percent}%"
            )
        else:
            logger.warning("Redis 메트릭 DB 저장 실패")

        return success

    except Exception as e:
        logger.error(f"Redis 메트릭 수집/저장 실패: {e}", exc_info=True)
        return False


def get_redis_status() -> RedisStatusDict:
    """Redis 현재 상태 조회 (타입 안전)

    CLI health 명령 등에서 사용하기 위한 함수

    Returns:
        RedisStatusDict: 타입 안전한 상태 딕셔너리
            - available: Redis 사용 가능 여부
            - fallback_mode: MemoryCache 폴백 여부
            - status: 헬스 상태 ('OK' | 'WARNING' | 'CRITICAL' | 'ERROR')
            - memory_usage: 메모리 사용률 (%)
            - hit_rate: 캐시 히트율 (%)
            - total_keys: 총 키 개수
            - latency_ms: 응답 지연시간 (ms)
    """
    monitor = get_redis_monitor()

    try:
        metrics = monitor.collect_metrics()

        if metrics is None:
            return RedisStatusDict(
                available=False,
                fallback_mode=True,
                status='ERROR',
                memory_usage=0.0,
                hit_rate=0.0,
                total_keys=0,
                latency_ms=0.0,
            )

        health = monitor.check_health(metrics)

        return RedisStatusDict(
            available=metrics.is_available,
            fallback_mode=metrics.fallback_in_use,
            status=health.value,
            memory_usage=metrics.memory_usage_percent,
            hit_rate=metrics.hit_rate_percent,
            total_keys=metrics.total_keys,
            latency_ms=metrics.latency_ms,
        )

    except Exception as e:
        logger.error("Redis status check failed", exc_info=True)
        return RedisStatusDict(
            available=False,
            fallback_mode=True,
            status='ERROR',
            memory_usage=0.0,
            hit_rate=0.0,
            total_keys=0,
            latency_ms=0.0,
        )


def check_redis_before_workflow(workflow_name: str) -> None:
    """워크플로우 실행 전 Redis 헬스 체크 (로깅 전용)

    Phase 1/2 workflow에서 사용하기 위한 함수.
    CRITICAL/ERROR 상태에서도 워크플로우는 계속 진행됨 (MemoryCache 폴백).

    Args:
        workflow_name: 워크플로우 이름 (로깅용)

    Note:
        이 함수는 로깅 목적으로만 사용되며, 워크플로우 실행을 차단하지 않습니다.
        Redis 장애 시 자동으로 MemoryCache로 폴백됩니다.
    """
    logger.info(f"[{workflow_name}] Redis 사전 체크 시작")

    result = check_redis_health()
    status = result['status']

    if status == 'OK':
        logger.info(f"[{workflow_name}] Redis 정상 (OK)")
    elif status == 'WARNING':
        logger.warning(f"[{workflow_name}] Redis 경고 상태 (WARNING) - 계속 진행")
    else:  # CRITICAL or ERROR
        logger.error(
            f"[{workflow_name}] Redis 문제 감지 ({status}) - MemoryCache 폴백으로 계속 진행",
            extra={'alert_message': result.get('alert_message')}
        )


def format_redis_health_summary(metrics: RedisMetricsData) -> str:
    """
    Redis 헬스 요약 포맷 (간단한 1줄)

    Args:
        metrics: Redis 메트릭 데이터

    Returns:
        str: 요약 문자열
    """
    if not metrics.is_available:
        return "❌ Redis 비활성 (MemoryCache 폴백)"

    return (
        f"✅ Redis: 메모리 {metrics.memory_usage_percent}%, "
        f"히트율 {metrics.hit_rate_percent}%, "
        f"키 {metrics.total_keys}개, "
        f"지연 {metrics.latency_ms}ms"
    )
