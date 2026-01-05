"""
시스템 모니터링 모듈

시스템 상태를 주기적으로 확인하고 이상 발생 시 알림을 전송합니다.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

from core.utils.telegram_notifier import get_telegram_notifier

logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    """알림 레벨"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class MonitoringThresholds:
    """모니터링 임계값 설정"""
    cpu_warning: float = 80.0
    cpu_critical: float = 95.0
    memory_warning: float = 80.0
    memory_critical: float = 95.0
    disk_warning: float = 80.0
    disk_critical: float = 95.0
    db_error_threshold: int = 5  # 5분 내 에러 수
    api_latency_warning: float = 5.0  # 초
    api_latency_critical: float = 10.0  # 초


@dataclass
class MonitoringStatus:
    """모니터링 상태"""
    timestamp: datetime = field(default_factory=datetime.now)
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    disk_percent: float = 0.0
    db_connected: bool = False
    api_connected: bool = False
    scheduler_running: bool = False
    recent_errors: int = 0
    alerts: List[Dict[str, Any]] = field(default_factory=list)


class SystemMonitor:
    """시스템 모니터링 클래스"""

    def __init__(
        self,
        thresholds: Optional[MonitoringThresholds] = None,
        check_interval: int = 300,  # 5분
        enable_telegram: bool = True
    ):
        """
        초기화

        Args:
            thresholds: 모니터링 임계값
            check_interval: 체크 간격 (초)
            enable_telegram: Telegram 알림 활성화
        """
        self.thresholds = thresholds or MonitoringThresholds()
        self.check_interval = check_interval
        self.enable_telegram = enable_telegram
        self._last_alert_time: Dict[str, datetime] = {}
        self._alert_cooldown = timedelta(minutes=30)  # 같은 알림 30분 쿨다운
        self._notifier = get_telegram_notifier() if enable_telegram else None

    def check_system_health(self) -> MonitoringStatus:
        """
        시스템 상태 확인

        Returns:
            MonitoringStatus: 현재 시스템 상태
        """
        status = MonitoringStatus()
        alerts = []

        # 시스템 메트릭 수집
        if PSUTIL_AVAILABLE:
            try:
                status.cpu_percent = psutil.cpu_percent(interval=1)
                status.memory_percent = psutil.virtual_memory().percent
                status.disk_percent = psutil.disk_usage('/').percent
            except Exception as e:
                logger.error(f"시스템 메트릭 수집 실패: {e}")

        # CPU 체크
        if status.cpu_percent >= self.thresholds.cpu_critical:
            alerts.append({
                'type': 'cpu',
                'level': AlertLevel.CRITICAL,
                'message': f'CPU 사용률 위험: {status.cpu_percent:.1f}%'
            })
        elif status.cpu_percent >= self.thresholds.cpu_warning:
            alerts.append({
                'type': 'cpu',
                'level': AlertLevel.WARNING,
                'message': f'CPU 사용률 경고: {status.cpu_percent:.1f}%'
            })

        # 메모리 체크
        if status.memory_percent >= self.thresholds.memory_critical:
            alerts.append({
                'type': 'memory',
                'level': AlertLevel.CRITICAL,
                'message': f'메모리 사용률 위험: {status.memory_percent:.1f}%'
            })
        elif status.memory_percent >= self.thresholds.memory_warning:
            alerts.append({
                'type': 'memory',
                'level': AlertLevel.WARNING,
                'message': f'메모리 사용률 경고: {status.memory_percent:.1f}%'
            })

        # 디스크 체크
        if status.disk_percent >= self.thresholds.disk_critical:
            alerts.append({
                'type': 'disk',
                'level': AlertLevel.CRITICAL,
                'message': f'디스크 사용률 위험: {status.disk_percent:.1f}%'
            })
        elif status.disk_percent >= self.thresholds.disk_warning:
            alerts.append({
                'type': 'disk',
                'level': AlertLevel.WARNING,
                'message': f'디스크 사용률 경고: {status.disk_percent:.1f}%'
            })

        # DB 연결 체크
        status.db_connected = self._check_database_connection()
        if not status.db_connected:
            alerts.append({
                'type': 'database',
                'level': AlertLevel.CRITICAL,
                'message': '데이터베이스 연결 실패'
            })

        # 최근 에러 체크
        status.recent_errors = self._count_recent_errors()
        if status.recent_errors >= self.thresholds.db_error_threshold:
            alerts.append({
                'type': 'errors',
                'level': AlertLevel.ERROR,
                'message': f'최근 5분간 에러 {status.recent_errors}건 발생'
            })

        status.alerts = alerts

        # 알림 전송
        self._process_alerts(alerts)

        return status

    def _check_database_connection(self) -> bool:
        """데이터베이스 연결 확인"""
        try:
            from core.config import settings
            from sqlalchemy import create_engine, text

            engine = create_engine(settings.DATABASE_URL)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            engine.dispose()
            return True
        except Exception as e:
            logger.error(f"DB 연결 확인 실패: {e}")
            return False

    def _count_recent_errors(self, minutes: int = 5) -> int:
        """최근 에러 수 조회"""
        try:
            from core.utils.db_error_handler import get_recent_errors
            from datetime import datetime, timedelta

            errors = get_recent_errors(limit=100)
            cutoff = datetime.now() - timedelta(minutes=minutes)

            recent_count = 0
            for error in errors:
                if error.get('timestamp'):
                    error_time = datetime.fromisoformat(error['timestamp'])
                    if error_time >= cutoff:
                        recent_count += 1

            return recent_count
        except Exception as e:
            logger.error(f"에러 수 조회 실패: {e}")
            return 0

    def _process_alerts(self, alerts: List[Dict[str, Any]]):
        """알림 처리 및 전송"""
        if not self.enable_telegram or not self._notifier:
            return

        for alert in alerts:
            alert_type = alert['type']
            level = alert['level']
            message = alert['message']

            # 쿨다운 체크
            if not self._should_send_alert(alert_type, level):
                continue

            # 알림 전송
            priority = self._get_telegram_priority(level)
            full_message = self._format_alert_message(alert)

            if self._notifier.send_message(full_message, priority):
                self._last_alert_time[f"{alert_type}_{level.value}"] = datetime.now()
                logger.info(f"알림 전송 완료: {alert_type} ({level.value})")

    def _should_send_alert(self, alert_type: str, level: AlertLevel) -> bool:
        """알림 전송 여부 결정 (쿨다운 체크)"""
        key = f"{alert_type}_{level.value}"
        last_time = self._last_alert_time.get(key)

        if not last_time:
            return True

        # CRITICAL은 쿨다운 절반
        cooldown = self._alert_cooldown
        if level == AlertLevel.CRITICAL:
            cooldown = cooldown / 2

        return datetime.now() - last_time >= cooldown

    def _get_telegram_priority(self, level: AlertLevel) -> str:
        """AlertLevel을 Telegram 우선순위로 변환"""
        mapping = {
            AlertLevel.INFO: "info",
            AlertLevel.WARNING: "high",
            AlertLevel.ERROR: "emergency",
            AlertLevel.CRITICAL: "critical"
        }
        return mapping.get(level, "normal")

    def _format_alert_message(self, alert: Dict[str, Any]) -> str:
        """알림 메시지 포맷"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        level = alert['level'].value.upper()
        message = alert['message']

        return f"""*한투 퀀트 시스템 모니터링*

⏰ 시간: `{timestamp}`
📊 유형: `{alert['type']}`
🔔 레벨: `{level}`

{message}

💡 시스템 상태를 확인해주세요."""

    def send_status_report(self) -> bool:
        """상태 리포트 전송"""
        status = self.check_system_health()

        # 상태 이모지
        if status.alerts:
            critical_count = sum(1 for a in status.alerts if a['level'] == AlertLevel.CRITICAL)
            if critical_count > 0:
                status_emoji = "🔴"
                status_text = "위험"
            else:
                status_emoji = "🟡"
                status_text = "주의"
        else:
            status_emoji = "🟢"
            status_text = "정상"

        message = f"""📊 *시스템 상태 리포트*

{status_emoji} 전체 상태: `{status_text}`
⏰ 점검 시간: `{status.timestamp.strftime('%Y-%m-%d %H:%M:%S')}`

💻 *시스템 리소스*:
• CPU: `{status.cpu_percent:.1f}%`
• 메모리: `{status.memory_percent:.1f}%`
• 디스크: `{status.disk_percent:.1f}%`

🔌 *서비스 상태*:
• 데이터베이스: {'✅ 연결됨' if status.db_connected else '❌ 연결 실패'}
• 최근 에러: `{status.recent_errors}건` (5분)

🔔 *활성 알림*: `{len(status.alerts)}건`"""

        if status.alerts:
            message += "\n\n*알림 목록*:"
            for alert in status.alerts[:5]:  # 최대 5개
                level_emoji = {
                    AlertLevel.CRITICAL: "🚨",
                    AlertLevel.ERROR: "❌",
                    AlertLevel.WARNING: "⚠️",
                    AlertLevel.INFO: "ℹ️"
                }.get(alert['level'], "📢")
                message += f"\n{level_emoji} {alert['message']}"

        if self._notifier:
            return self._notifier.send_message(message, "normal")
        return False


# 전역 인스턴스
_monitor_instance: Optional[SystemMonitor] = None


def get_system_monitor() -> SystemMonitor:
    """시스템 모니터 인스턴스 가져오기"""
    global _monitor_instance
    if _monitor_instance is None:
        _monitor_instance = SystemMonitor()
    return _monitor_instance


def quick_health_check() -> Dict[str, Any]:
    """빠른 상태 확인 (API용)"""
    monitor = get_system_monitor()
    status = monitor.check_system_health()

    return {
        'healthy': len(status.alerts) == 0,
        'timestamp': status.timestamp.isoformat(),
        'metrics': {
            'cpu_percent': status.cpu_percent,
            'memory_percent': status.memory_percent,
            'disk_percent': status.disk_percent,
        },
        'services': {
            'database': status.db_connected,
        },
        'recent_errors': status.recent_errors,
        'alerts': [
            {
                'type': a['type'],
                'level': a['level'].value,
                'message': a['message']
            }
            for a in status.alerts
        ]
    }
