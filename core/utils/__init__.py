"""Utility facade for logging and health check functions.

통합 로깅 진입점은 log_utils 모듈로 일원화합니다.
기존 from core.utils import get_logger, setup_logger 형태를 유지하기 위해
이곳에서 log_utils를 재노출합니다.
"""

from .log_utils import get_logger, setup_logging as setup_logger  # backward-compat alias
from .log_utils import (
    JSONFormatter,
    StructuredLogger,
    TraceIdContext,
    setup_json_logging,
    get_structured_logger,
    get_trace_id,
    set_trace_id,
    clear_trace_id,
)
from .health_check import (
    HealthCheckResult,
    SystemMetrics,
    HealthStatus,
    get_system_metrics,
    check_database_health,
    check_kis_api_health,
    check_websocket_health,
    determine_health_status,
    perform_health_check,
    PSUTIL_AVAILABLE,
)
from .db_error_handler import (
    PostgreSQLErrorHandler,
    setup_db_error_logging,
    get_recent_errors,
    mark_error_resolved,
)
from .system_monitor import (
    SystemMonitor,
    MonitoringThresholds,
    MonitoringStatus,
    AlertLevel,
    get_system_monitor,
    quick_health_check,
)

__all__ = [
    # Logging (P2-2)
    'get_logger',
    'setup_logger',
    'JSONFormatter',
    'StructuredLogger',
    'TraceIdContext',
    'setup_json_logging',
    'get_structured_logger',
    'get_trace_id',
    'set_trace_id',
    'clear_trace_id',
    # Health Check (P2-3)
    'HealthCheckResult',
    'SystemMetrics',
    'HealthStatus',
    'get_system_metrics',
    'check_database_health',
    'check_kis_api_health',
    'check_websocket_health',
    'determine_health_status',
    'perform_health_check',
    'PSUTIL_AVAILABLE',
    # DB Error Logging
    'PostgreSQLErrorHandler',
    'setup_db_error_logging',
    'get_recent_errors',
    'mark_error_resolved',
    # System Monitoring
    'SystemMonitor',
    'MonitoringThresholds',
    'MonitoringStatus',
    'AlertLevel',
    'get_system_monitor',
    'quick_health_check',
]