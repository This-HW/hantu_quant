"""
알림 발송기 기본 모듈

알림 발송의 기본 인터페이스를 정의합니다.
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from .alert import Alert, AlertLevel

logger = logging.getLogger(__name__)


@dataclass
class NotifierConfig:
    """발송기 설정"""
    # 활성화
    enabled: bool = True

    # 최소 알림 레벨
    min_level: AlertLevel = AlertLevel.INFO

    # 조용한 시간 (HH:MM 형식)
    quiet_start: Optional[str] = None  # 예: "22:00"
    quiet_end: Optional[str] = None    # 예: "08:00"

    # 재시도 설정
    max_retries: int = 3
    retry_delay: float = 1.0  # 초

    # 배치 설정
    batch_enabled: bool = False
    batch_interval: int = 60  # 초
    batch_max_size: int = 10


@dataclass
class NotificationResult:
    """발송 결과"""
    success: bool
    alert_id: str
    timestamp: datetime = field(default_factory=datetime.now)
    error: str = ""
    retry_count: int = 0
    response: Any = None

    def to_dict(self) -> Dict:
        return {
            'success': self.success,
            'alert_id': self.alert_id,
            'timestamp': self.timestamp.isoformat(),
            'error': self.error,
            'retry_count': self.retry_count,
        }


class BaseNotifier(ABC):
    """
    알림 발송기 기본 클래스

    모든 알림 발송기는 이 클래스를 상속합니다.
    """

    def __init__(self, config: Optional[NotifierConfig] = None):
        """
        Args:
            config: 발송기 설정
        """
        self.config = config or NotifierConfig()
        self._sent_count: int = 0
        self._error_count: int = 0
        self._last_sent: Optional[datetime] = None
        self._pending_batch: List[Alert] = []

    @abstractmethod
    def send(self, alert: Alert) -> NotificationResult:
        """
        알림 발송

        Args:
            alert: 알림 객체

        Returns:
            NotificationResult: 발송 결과
        """
        pass

    @abstractmethod
    def send_raw(self, message: str) -> NotificationResult:
        """
        원시 메시지 발송

        Args:
            message: 메시지 문자열

        Returns:
            NotificationResult: 발송 결과
        """
        pass

    def should_send(self, alert: Alert) -> bool:
        """
        알림 발송 여부 판단

        Args:
            alert: 알림 객체

        Returns:
            bool: 발송 여부
        """
        if not self.config.enabled:
            return False

        # 레벨 체크
        if alert.level.value < self.config.min_level.value:
            return False

        # 조용한 시간 체크
        if self._is_quiet_time():
            # CRITICAL 이상은 조용한 시간에도 발송
            if alert.level.value < AlertLevel.CRITICAL.value:
                return False

        return True

    def _is_quiet_time(self) -> bool:
        """조용한 시간 여부"""
        if not self.config.quiet_start or not self.config.quiet_end:
            return False

        now = datetime.now().time()

        start_hour, start_min = map(int, self.config.quiet_start.split(':'))
        end_hour, end_min = map(int, self.config.quiet_end.split(':'))

        from datetime import time
        quiet_start = time(start_hour, start_min)
        quiet_end = time(end_hour, end_min)

        if quiet_start <= quiet_end:
            return quiet_start <= now <= quiet_end
        else:
            # 자정 넘어가는 경우 (예: 22:00 ~ 08:00)
            return now >= quiet_start or now <= quiet_end

    def queue_for_batch(self, alert: Alert) -> bool:
        """
        배치 큐에 추가

        Args:
            alert: 알림 객체

        Returns:
            bool: 성공 여부
        """
        if not self.config.batch_enabled:
            return False

        self._pending_batch.append(alert)

        # 배치 크기 초과 시 즉시 발송
        if len(self._pending_batch) >= self.config.batch_max_size:
            self.flush_batch()

        return True

    def flush_batch(self) -> List[NotificationResult]:
        """
        배치 발송

        Returns:
            List[NotificationResult]: 발송 결과 리스트
        """
        if not self._pending_batch:
            return []

        results = []
        for alert in self._pending_batch:
            result = self.send(alert)
            results.append(result)

        self._pending_batch.clear()
        return results

    def get_stats(self) -> Dict[str, Any]:
        """통계 조회"""
        return {
            'enabled': self.config.enabled,
            'sent_count': self._sent_count,
            'error_count': self._error_count,
            'success_rate': (
                self._sent_count / (self._sent_count + self._error_count)
                if (self._sent_count + self._error_count) > 0 else 0
            ),
            'last_sent': self._last_sent.isoformat() if self._last_sent else None,
            'pending_batch': len(self._pending_batch),
        }

    def _record_success(self) -> None:
        """성공 기록"""
        self._sent_count += 1
        self._last_sent = datetime.now()

    def _record_error(self) -> None:
        """오류 기록"""
        self._error_count += 1
