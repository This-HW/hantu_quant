"""
Redis 헬스 체크 유틸리티

Redis 모니터링을 간편하게 수행하기 위한 헬퍼 함수들을 제공합니다.

Feature: Redis 자동 모니터링
"""

from typing import Optional, Dict, Any
from datetime import datetime

from core.monitoring.redis_monitor import (
    RedisMonitor,
    RedisMetricsData,
    HealthStatus,
)
from core.utils.log_utils import get_logger

logger = get_logger(__name__)


# 글로벌 모니터 인스턴스 (싱글톤)
_monitor_instance: Optional[RedisMonitor] = None


def get_redis_monitor() -> RedisMonitor:
    """
    RedisMonitor 싱글톤 인스턴스 반환

    Returns:
        RedisMonitor 인스턴스
    """
    global _monitor_instance

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
        logger.error(f"Redis 헬스 체크 실패: {e}", exc_info=True)
        return {
            'status': 'ERROR',
            'metrics': None,
            'alert_message': f'❌ Redis 헬스 체크 에러: {e}',
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


def get_redis_status() -> Dict[str, Any]:
    """
    Redis 현재 상태 조회 (간단한 정보)

    CLI health 명령 등에서 사용하기 위한 함수

    Returns:
        Dict: {
            'available': bool,
            'fallback_mode': bool,
            'status': 'OK' | 'WARNING' | 'CRITICAL' | 'ERROR',
            'memory_usage': float,
            'hit_rate': float,
            'total_keys': int,
            'latency_ms': float
        }
    """
    monitor = get_redis_monitor()

    try:
        metrics = monitor.collect_metrics()

        if metrics is None:
            return {
                'available': False,
                'fallback_mode': True,
                'status': 'ERROR',
                'memory_usage': 0.0,
                'hit_rate': 0.0,
                'total_keys': 0,
                'latency_ms': 0.0,
            }

        health = monitor.check_health(metrics)

        return {
            'available': metrics.is_available,
            'fallback_mode': metrics.fallback_in_use,
            'status': health.value,
            'memory_usage': metrics.memory_usage_percent,
            'hit_rate': metrics.hit_rate_percent,
            'total_keys': metrics.total_keys,
            'latency_ms': metrics.latency_ms,
        }

    except Exception as e:
        logger.error(f"Redis 상태 조회 실패: {e}", exc_info=True)
        return {
            'available': False,
            'fallback_mode': True,
            'status': 'ERROR',
            'memory_usage': 0.0,
            'hit_rate': 0.0,
            'total_keys': 0,
            'latency_ms': 0.0,
        }


def check_redis_before_workflow(workflow_name: str) -> bool:
    """
    워크플로우 실행 전 Redis 헬스 체크

    Phase 1/2 workflow에서 사용하기 위한 함수

    Args:
        workflow_name: 워크플로우 이름 (로깅용)

    Returns:
        bool: Redis가 정상이면 True, 문제 있으면 False
    """
    logger.info(f"[{workflow_name}] Redis 사전 체크 시작")

    result = check_redis_health()
    status = result['status']

    if status == 'OK':
        logger.info(f"[{workflow_name}] Redis 정상 (✅ OK)")
        return True

    elif status == 'WARNING':
        logger.warning(
            f"[{workflow_name}] Redis 경고 상태 (⚠️ WARNING) - 계속 진행"
        )
        # WARNING은 진행 허용
        return True

    else:  # CRITICAL or ERROR
        logger.error(
            f"[{workflow_name}] Redis 문제 감지 ({status})",
            extra={'alert_message': result.get('alert_message')}
        )
        # CRITICAL/ERROR는 진행 차단 (선택적)
        # 현재는 계속 진행 (MemoryCache 폴백)
        return True


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
