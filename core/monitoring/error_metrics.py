"""
에러 메트릭스 수집 및 분석 모듈

Feature 5.6: Error Metrics 및 분석 시스템
- T-5.6.1: ErrorMetrics 클래스 정의
- T-5.6.2: 에러 발생 시 메트릭 자동 수집
- T-5.6.3: 에러 통계 조회 API
- T-5.6.4: 반복 에러 패턴 감지 및 알림
"""

import threading
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from collections import defaultdict
from enum import Enum

from core.exceptions import HantuQuantException
from core.utils.log_utils import get_trace_id

logger = logging.getLogger(__name__)


class ErrorTrend(Enum):
    """에러 트렌드"""
    INCREASING = "increasing"
    STABLE = "stable"
    DECREASING = "decreasing"
    SPIKE = "spike"


@dataclass
class ErrorMetric:
    """개별 에러 메트릭"""
    error_code: str
    error_type: str
    category: str
    severity: str
    count: int = 0
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    recovery_count: int = 0
    avg_recovery_time: float = 0.0
    trace_ids: List[str] = field(default_factory=list)

    @property
    def recovery_rate(self) -> float:
        """복구 성공률"""
        if self.count == 0:
            return 0.0
        return self.recovery_count / self.count * 100

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 변환"""
        return {
            "error_code": self.error_code,
            "error_type": self.error_type,
            "category": self.category,
            "severity": self.severity,
            "count": self.count,
            "first_seen": self.first_seen.isoformat() if self.first_seen else None,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "recovery_count": self.recovery_count,
            "recovery_rate": self.recovery_rate,
            "avg_recovery_time": self.avg_recovery_time,
        }


@dataclass
class ErrorPattern:
    """에러 패턴"""
    pattern_id: str
    error_codes: List[str]
    frequency: int  # 시간당 발생 횟수
    first_detected: datetime
    last_detected: datetime
    is_recurring: bool = False
    alert_sent: bool = False


class ErrorMetricsCollector:
    """
    에러 메트릭 수집기

    에러 발생을 추적하고 패턴을 분석합니다.
    """

    def __init__(self):
        self._metrics: Dict[str, ErrorMetric] = {}
        self._recent_errors: List[Dict] = []
        self._patterns: Dict[str, ErrorPattern] = {}
        self._lock = threading.Lock()

        # 설정
        self._max_recent_errors = 1000
        self._pattern_window_minutes = 60
        self._recurring_threshold = 5  # 1시간 내 5회 이상이면 반복 에러

        # 시간별 카운터
        self._hourly_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

    def record_error(
        self,
        error: Exception,
        recovered: bool = False,
        recovery_time: Optional[float] = None,
        context: Optional[Dict] = None,
    ) -> str:
        """
        에러 기록

        Args:
            error: 에러 객체
            recovered: 복구 여부
            recovery_time: 복구 소요 시간 (초)
            context: 추가 컨텍스트

        Returns:
            에러 코드
        """
        with self._lock:
            now = datetime.now()
            trace_id = get_trace_id() or ""

            # 에러 정보 추출
            if isinstance(error, HantuQuantException):
                error_code = error.error_code
                error_type = type(error).__name__
                category = error.category.value if error.category else "unknown"
                severity = error.severity.value if error.severity else "error"
            else:
                error_code = f"EXC_{type(error).__name__.upper()}"
                error_type = type(error).__name__
                category = "unknown"
                severity = "error"

            # 메트릭 업데이트
            if error_code not in self._metrics:
                self._metrics[error_code] = ErrorMetric(
                    error_code=error_code,
                    error_type=error_type,
                    category=category,
                    severity=severity,
                    first_seen=now,
                )

            metric = self._metrics[error_code]
            metric.count += 1
            metric.last_seen = now

            if recovered:
                metric.recovery_count += 1
                if recovery_time:
                    # 이동 평균 계산
                    if metric.avg_recovery_time == 0:
                        metric.avg_recovery_time = recovery_time
                    else:
                        metric.avg_recovery_time = (
                            metric.avg_recovery_time * 0.9 + recovery_time * 0.1
                        )

            if trace_id and trace_id not in metric.trace_ids:
                metric.trace_ids.append(trace_id)
                # 최근 10개만 유지
                if len(metric.trace_ids) > 10:
                    metric.trace_ids = metric.trace_ids[-10:]

            # 최근 에러 기록
            self._recent_errors.append({
                "error_code": error_code,
                "error_type": error_type,
                "category": category,
                "severity": severity,
                "message": str(error)[:200],
                "timestamp": now,
                "trace_id": trace_id,
                "context": context,
            })

            # 최대 개수 유지
            if len(self._recent_errors) > self._max_recent_errors:
                self._recent_errors = self._recent_errors[-self._max_recent_errors:]

            # 시간별 카운터 업데이트
            hour_key = now.strftime("%Y-%m-%d-%H")
            self._hourly_counts[hour_key][error_code] += 1

            # 패턴 감지
            self._detect_patterns(error_code, now)

            return error_code

    def record_recovery(self, error_code: str, recovery_time: float) -> None:
        """
        에러 복구 기록

        Args:
            error_code: 에러 코드
            recovery_time: 복구 소요 시간 (초)
        """
        with self._lock:
            if error_code in self._metrics:
                metric = self._metrics[error_code]
                metric.recovery_count += 1
                if metric.avg_recovery_time == 0:
                    metric.avg_recovery_time = recovery_time
                else:
                    metric.avg_recovery_time = (
                        metric.avg_recovery_time * 0.9 + recovery_time * 0.1
                    )

    def _detect_patterns(self, error_code: str, timestamp: datetime) -> None:
        """반복 에러 패턴 감지"""
        # 최근 1시간 내 같은 에러 발생 횟수 계산
        cutoff = timestamp - timedelta(minutes=self._pattern_window_minutes)
        recent_count = sum(
            1 for e in self._recent_errors
            if e["error_code"] == error_code and e["timestamp"] > cutoff
        )

        if recent_count >= self._recurring_threshold:
            pattern_id = f"RECURRING_{error_code}"

            if pattern_id not in self._patterns:
                self._patterns[pattern_id] = ErrorPattern(
                    pattern_id=pattern_id,
                    error_codes=[error_code],
                    frequency=recent_count,
                    first_detected=timestamp,
                    last_detected=timestamp,
                    is_recurring=True,
                )
                logger.warning(
                    f"Recurring error pattern detected: {error_code} "
                    f"({recent_count} times in last hour)"
                )
            else:
                pattern = self._patterns[pattern_id]
                pattern.frequency = recent_count
                pattern.last_detected = timestamp

    def get_metrics(self, error_code: Optional[str] = None) -> Dict[str, ErrorMetric]:
        """
        메트릭 조회

        Args:
            error_code: 특정 에러 코드 (None이면 전체)

        Returns:
            에러 메트릭 딕셔너리
        """
        with self._lock:
            if error_code:
                if error_code in self._metrics:
                    return {error_code: self._metrics[error_code]}
                return {}
            return dict(self._metrics)

    def get_summary(self) -> Dict[str, Any]:
        """
        에러 요약 통계

        Returns:
            요약 통계 딕셔너리
        """
        with self._lock:
            total_errors = sum(m.count for m in self._metrics.values())
            total_recovered = sum(m.recovery_count for m in self._metrics.values())

            # 카테고리별 통계
            by_category = defaultdict(int)
            by_severity = defaultdict(int)

            for metric in self._metrics.values():
                by_category[metric.category] += metric.count
                by_severity[metric.severity] += metric.count

            # 최근 1시간 에러
            now = datetime.now()
            hour_ago = now - timedelta(hours=1)
            recent_errors = [
                e for e in self._recent_errors
                if e["timestamp"] > hour_ago
            ]

            # 트렌드 계산
            trend = self._calculate_trend()

            return {
                "total_errors": total_errors,
                "unique_error_types": len(self._metrics),
                "total_recovered": total_recovered,
                "recovery_rate": (total_recovered / total_errors * 100) if total_errors > 0 else 0,
                "by_category": dict(by_category),
                "by_severity": dict(by_severity),
                "last_hour_count": len(recent_errors),
                "recurring_patterns": len([p for p in self._patterns.values() if p.is_recurring]),
                "trend": trend.value,
                "timestamp": now.isoformat(),
            }

    def _calculate_trend(self) -> ErrorTrend:
        """에러 트렌드 계산"""
        now = datetime.now()

        # 최근 2시간의 시간별 카운트
        counts = []
        for i in range(2):
            hour = now - timedelta(hours=i)
            hour_key = hour.strftime("%Y-%m-%d-%H")
            count = sum(self._hourly_counts.get(hour_key, {}).values())
            counts.append(count)

        if len(counts) < 2:
            return ErrorTrend.STABLE

        current, previous = counts[0], counts[1]

        if previous == 0:
            return ErrorTrend.STABLE if current == 0 else ErrorTrend.SPIKE

        change_rate = (current - previous) / previous

        if change_rate > 0.5:
            return ErrorTrend.SPIKE
        elif change_rate > 0.1:
            return ErrorTrend.INCREASING
        elif change_rate < -0.1:
            return ErrorTrend.DECREASING
        else:
            return ErrorTrend.STABLE

    def get_top_errors(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        상위 에러 목록

        Args:
            limit: 최대 개수

        Returns:
            상위 에러 목록
        """
        with self._lock:
            sorted_metrics = sorted(
                self._metrics.values(),
                key=lambda m: m.count,
                reverse=True
            )
            return [m.to_dict() for m in sorted_metrics[:limit]]

    def get_recent_errors(
        self,
        limit: int = 50,
        category: Optional[str] = None,
        severity: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        최근 에러 목록

        Args:
            limit: 최대 개수
            category: 카테고리 필터
            severity: 심각도 필터

        Returns:
            최근 에러 목록
        """
        with self._lock:
            errors = self._recent_errors

            if category:
                errors = [e for e in errors if e["category"] == category]

            if severity:
                errors = [e for e in errors if e["severity"] == severity]

            return [
                {
                    **e,
                    "timestamp": e["timestamp"].isoformat()
                }
                for e in reversed(errors[-limit:])
            ]

    def get_patterns(self, recurring_only: bool = True) -> List[Dict[str, Any]]:
        """
        에러 패턴 조회

        Args:
            recurring_only: 반복 패턴만 조회

        Returns:
            패턴 목록
        """
        with self._lock:
            patterns = self._patterns.values()

            if recurring_only:
                patterns = [p for p in patterns if p.is_recurring]

            return [
                {
                    "pattern_id": p.pattern_id,
                    "error_codes": p.error_codes,
                    "frequency": p.frequency,
                    "first_detected": p.first_detected.isoformat(),
                    "last_detected": p.last_detected.isoformat(),
                    "is_recurring": p.is_recurring,
                }
                for p in patterns
            ]

    def cleanup_old_data(self, hours: int = 24) -> int:
        """
        오래된 데이터 정리

        Args:
            hours: 보관 기간

        Returns:
            삭제된 레코드 수
        """
        with self._lock:
            cutoff = datetime.now() - timedelta(hours=hours)
            original_count = len(self._recent_errors)

            self._recent_errors = [
                e for e in self._recent_errors
                if e["timestamp"] > cutoff
            ]

            # 오래된 시간별 카운터 정리
            cutoff_key = cutoff.strftime("%Y-%m-%d-%H")
            old_keys = [k for k in self._hourly_counts.keys() if k < cutoff_key]
            for key in old_keys:
                del self._hourly_counts[key]

            return original_count - len(self._recent_errors)


# 글로벌 인스턴스
_error_metrics: Optional[ErrorMetricsCollector] = None


def get_error_metrics() -> ErrorMetricsCollector:
    """에러 메트릭 수집기 인스턴스"""
    global _error_metrics
    if _error_metrics is None:
        _error_metrics = ErrorMetricsCollector()
    return _error_metrics


def record_error_metric(
    error: Exception,
    recovered: bool = False,
    recovery_time: Optional[float] = None,
    context: Optional[Dict] = None,
) -> str:
    """에러 메트릭 기록 헬퍼 함수"""
    return get_error_metrics().record_error(
        error=error,
        recovered=recovered,
        recovery_time=recovery_time,
        context=context,
    )
