"""
Redis 모니터링 모듈

Redis 캐싱 시스템의 메트릭을 수집하고 분석합니다.
- 메모리 사용률, 히트율, 키 개수 등 추적
- 임계값 초과 시 알림 생성
- DB에 메트릭 저장 (5분 간격)

Feature: Redis 자동 모니터링
"""

import redis
import time
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum
from dataclasses import dataclass

from core.utils.log_utils import get_logger
from core.api.redis_client import cache

logger = get_logger(__name__)


class HealthStatus(Enum):
    """헬스 상태"""
    OK = "OK"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    ERROR = "ERROR"


@dataclass
class RedisMetricsData:
    """Redis 메트릭 데이터"""
    timestamp: datetime

    # 메모리
    used_memory_mb: float
    max_memory_mb: float
    memory_usage_percent: float
    evicted_keys: int

    # 캐시 성능
    total_keys: int
    keyspace_hits: int
    keyspace_misses: int
    hit_rate_percent: float

    # 성능
    latency_ms: float

    # 상태
    is_available: bool
    fallback_in_use: bool


class RedisMonitor:
    """Redis 모니터링 클래스"""

    # 임계값 설정
    MEMORY_WARNING_THRESHOLD = 0.7  # 70%
    MEMORY_CRITICAL_THRESHOLD = 0.8  # 80%
    HIT_RATE_WARNING_THRESHOLD = 0.5  # 50%
    HIT_RATE_CRITICAL_THRESHOLD = 0.4  # 40%
    LATENCY_WARNING_MS = 50
    LATENCY_CRITICAL_MS = 100

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        """
        초기화

        Args:
            redis_client: Redis 클라이언트 (None이면 자동 감지)
        """
        self._redis = redis_client
        self._fallback_mode = False

        # 자동 감지
        if not self._redis:
            from core.api.redis_client import _redis_client
            self._redis = _redis_client
            self._fallback_mode = self._redis is None

    def collect_metrics(self) -> Optional[RedisMetricsData]:
        """
        Redis 메트릭 수집

        Returns:
            메트릭 데이터 또는 None (수집 실패 시)
        """
        if not self._redis:
            logger.warning("Redis 연결 없음, MemoryCache 폴백 모드")
            return self._get_fallback_metrics()

        try:
            # Redis INFO 명령으로 메트릭 수집
            info = self._redis.info()

            # 메모리 메트릭
            used_memory_bytes = info.get('used_memory', 0)
            used_memory_mb = used_memory_bytes / (1024 * 1024)

            max_memory_bytes = info.get('maxmemory', 0)
            max_memory_mb = max_memory_bytes / (1024 * 1024) if max_memory_bytes > 0 else 0

            memory_usage_percent = (
                (used_memory_bytes / max_memory_bytes * 100) if max_memory_bytes > 0 else 0
            )

            evicted_keys = info.get('evicted_keys', 0)

            # 캐시 성능
            stats = info.get('stats', {})
            keyspace_hits = stats.get('keyspace_hits', 0) if isinstance(stats, dict) else info.get('keyspace_hits', 0)
            keyspace_misses = stats.get('keyspace_misses', 0) if isinstance(stats, dict) else info.get('keyspace_misses', 0)

            total_hits_misses = keyspace_hits + keyspace_misses
            hit_rate_percent = (
                (keyspace_hits / total_hits_misses * 100) if total_hits_misses > 0 else 0
            )

            # 키 개수 (DB 0 기준)
            db0 = info.get('db0', {})
            total_keys = db0.get('keys', 0) if isinstance(db0, dict) else 0

            # 지연시간 (PING 측정)
            latency_ms = self._measure_latency()

            metrics = RedisMetricsData(
                timestamp=datetime.now(),
                used_memory_mb=round(used_memory_mb, 2),
                max_memory_mb=round(max_memory_mb, 2),
                memory_usage_percent=round(memory_usage_percent, 2),
                evicted_keys=evicted_keys,
                total_keys=total_keys,
                keyspace_hits=keyspace_hits,
                keyspace_misses=keyspace_misses,
                hit_rate_percent=round(hit_rate_percent, 2),
                latency_ms=round(latency_ms, 2),
                is_available=True,
                fallback_in_use=False,
            )

            logger.debug(
                f"Redis 메트릭 수집 완료: "
                f"메모리={metrics.memory_usage_percent}%, "
                f"히트율={metrics.hit_rate_percent}%, "
                f"키={metrics.total_keys}"
            )

            return metrics

        except (redis.ConnectionError, redis.TimeoutError) as e:
            logger.warning(f"Redis 연결 에러: {e}, 폴백 메트릭 반환", exc_info=True)
            self._fallback_mode = True
            return self._get_fallback_metrics()

        except Exception as e:
            logger.error(f"Redis 메트릭 수집 실패: {e}", exc_info=True)
            return None

    def _measure_latency(self) -> float:
        """PING 명령으로 지연시간 측정 (밀리초)"""
        if not self._redis:
            return 0.0

        try:
            start = time.time()
            self._redis.ping()
            end = time.time()
            return (end - start) * 1000  # 밀리초 변환
        except Exception:
            return 0.0

    def _get_fallback_metrics(self) -> RedisMetricsData:
        """폴백 모드 메트릭 (MemoryCache 사용 중)"""
        from core.api.redis_client import _memory_cache

        return RedisMetricsData(
            timestamp=datetime.now(),
            used_memory_mb=0.0,
            max_memory_mb=0.0,
            memory_usage_percent=0.0,
            evicted_keys=0,
            total_keys=_memory_cache.size(),
            keyspace_hits=0,
            keyspace_misses=0,
            hit_rate_percent=0.0,
            latency_ms=0.0,
            is_available=False,
            fallback_in_use=True,
        )

    def check_health(self, metrics: Optional[RedisMetricsData] = None) -> HealthStatus:
        """
        헬스 상태 확인

        Args:
            metrics: 메트릭 데이터 (None이면 자동 수집)

        Returns:
            헬스 상태 (OK/WARNING/CRITICAL/ERROR)
        """
        if metrics is None:
            metrics = self.collect_metrics()

        if metrics is None:
            return HealthStatus.ERROR

        if not metrics.is_available:
            return HealthStatus.CRITICAL

        # 메모리 체크
        if metrics.memory_usage_percent >= self.MEMORY_CRITICAL_THRESHOLD * 100:
            return HealthStatus.CRITICAL
        if metrics.memory_usage_percent >= self.MEMORY_WARNING_THRESHOLD * 100:
            return HealthStatus.WARNING

        # 히트율 체크 (히트율이 너무 낮으면 경고)
        if metrics.hit_rate_percent > 0:  # 0이면 아직 데이터 없음
            if metrics.hit_rate_percent <= self.HIT_RATE_CRITICAL_THRESHOLD * 100:
                return HealthStatus.CRITICAL
            if metrics.hit_rate_percent <= self.HIT_RATE_WARNING_THRESHOLD * 100:
                return HealthStatus.WARNING

        # 지연시간 체크
        if metrics.latency_ms >= self.LATENCY_CRITICAL_MS:
            return HealthStatus.CRITICAL
        if metrics.latency_ms >= self.LATENCY_WARNING_MS:
            return HealthStatus.WARNING

        return HealthStatus.OK

    def get_alert_message(self, metrics: RedisMetricsData, health: HealthStatus) -> Optional[str]:
        """
        알림 메시지 생성 (임계값 초과 시)

        Args:
            metrics: 메트릭 데이터
            health: 헬스 상태

        Returns:
            알림 메시지 또는 None (알림 불필요 시)
        """
        if health == HealthStatus.OK:
            return None

        # 상태별 이모지
        emoji_map = {
            HealthStatus.CRITICAL: "🚨",
            HealthStatus.WARNING: "⚠️",
            HealthStatus.ERROR: "❌",
        }
        emoji = emoji_map.get(health, "ℹ️")

        # 문제 식별
        issues = []

        if not metrics.is_available:
            issues.append("• Redis 연결 실패 (MemoryCache 폴백 중)")
        else:
            if metrics.memory_usage_percent >= self.MEMORY_CRITICAL_THRESHOLD * 100:
                issues.append(f"• 메모리 사용률: {metrics.memory_usage_percent}% (**임계값 80% 초과**)")
            elif metrics.memory_usage_percent >= self.MEMORY_WARNING_THRESHOLD * 100:
                issues.append(f"• 메모리 사용률: {metrics.memory_usage_percent}% (주의)")

            if 0 < metrics.hit_rate_percent <= self.HIT_RATE_CRITICAL_THRESHOLD * 100:
                issues.append(f"• 히트율: {metrics.hit_rate_percent}% (**임계값 40% 미만**)")
            elif 0 < metrics.hit_rate_percent <= self.HIT_RATE_WARNING_THRESHOLD * 100:
                issues.append(f"• 히트율: {metrics.hit_rate_percent}% (주의)")

            if metrics.latency_ms >= self.LATENCY_CRITICAL_MS:
                issues.append(f"• 응답 지연: {metrics.latency_ms}ms (**임계값 100ms 초과**)")
            elif metrics.latency_ms >= self.LATENCY_WARNING_MS:
                issues.append(f"• 응답 지연: {metrics.latency_ms}ms (주의)")

            if metrics.evicted_keys > 0:
                issues.append(f"• 메모리 부족으로 삭제된 키: {metrics.evicted_keys}개")

        # 메시지 구성
        timestamp = metrics.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        message = f"""{emoji} *Redis 캐싱 시스템 {health.value}*

`{timestamp}`

**상태:**
{chr(10).join(issues)}

**메트릭:**
• 메모리: {metrics.used_memory_mb}MB / {metrics.max_memory_mb}MB
• 총 키: {metrics.total_keys}개
• 히트/미스: {metrics.keyspace_hits} / {metrics.keyspace_misses}
• 지연시간: {metrics.latency_ms}ms
"""

        return message

    def save_metrics(self, metrics: RedisMetricsData) -> bool:
        """
        메트릭을 DB에 저장

        Args:
            metrics: 메트릭 데이터

        Returns:
            성공 여부
        """
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            from core.config import settings
            from core.database.models import RedisMetrics

            engine = create_engine(settings.DATABASE_URL)
            Session = sessionmaker(bind=engine)
            session = Session()

            try:
                redis_metric = RedisMetrics(
                    timestamp=metrics.timestamp,
                    used_memory_mb=metrics.used_memory_mb,
                    max_memory_mb=metrics.max_memory_mb,
                    memory_usage_percent=metrics.memory_usage_percent,
                    evicted_keys=metrics.evicted_keys,
                    total_keys=metrics.total_keys,
                    keyspace_hits=metrics.keyspace_hits,
                    keyspace_misses=metrics.keyspace_misses,
                    hit_rate_percent=metrics.hit_rate_percent,
                    latency_ms=metrics.latency_ms,
                    is_available=int(metrics.is_available),
                    fallback_in_use=int(metrics.fallback_in_use),
                )

                session.add(redis_metric)
                session.commit()

                logger.debug(f"Redis 메트릭 DB 저장 완료: ID={redis_metric.id}")
                return True

            except Exception as e:
                session.rollback()
                logger.error(f"Redis 메트릭 DB 저장 실패: {e}", exc_info=True)
                return False

            finally:
                session.close()

        except Exception as e:
            logger.error(f"Redis 메트릭 저장 중 예외: {e}", exc_info=True)
            return False
