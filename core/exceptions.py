"""
Hantu Quant 통합 예외 클래스 정의

이 모듈은 시스템 전체에서 사용하는 예외 클래스 계층을 정의합니다.
모든 도메인별 예외는 HantuQuantException을 상속받습니다.

Feature 5: 에러 추적 및 원인 파악 시스템
Story 5.1: Custom Exception 체계 구축
"""

import traceback
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List, Type


class ErrorSeverity(Enum):
    """에러 심각도"""
    DEBUG = "DEBUG"          # 디버그 정보
    INFO = "INFO"            # 정보성 에러
    WARNING = "WARNING"      # 경고
    ERROR = "ERROR"          # 일반 에러
    CRITICAL = "CRITICAL"    # 치명적 에러
    FATAL = "FATAL"          # 시스템 중단 필요


class ErrorCategory(Enum):
    """에러 카테고리"""
    API = "API"              # API 관련
    TRADING = "TRADING"      # 거래 관련
    DATA = "DATA"            # 데이터 관련
    NETWORK = "NETWORK"      # 네트워크 관련
    CONFIG = "CONFIG"        # 설정 관련
    VALIDATION = "VALIDATION"  # 유효성 검증
    SYSTEM = "SYSTEM"        # 시스템 관련
    NOTIFICATION = "NOTIFICATION"  # 알림 관련
    UNKNOWN = "UNKNOWN"      # 알 수 없음


class HantuQuantException(Exception):
    """
    Hantu Quant 기본 예외 클래스

    모든 커스텀 예외의 기본 클래스입니다.
    error_code와 context 필드를 포함하여 에러 추적을 지원합니다.

    Attributes:
        error_code: 에러 식별 코드 (예: "API_001", "TRADE_002")
        context: 에러 발생 컨텍스트 정보
        severity: 에러 심각도
        category: 에러 카테고리
        timestamp: 에러 발생 시각
        original_error: 원본 예외 (있는 경우)
        trace_id: 분산 추적 ID (있는 경우)
    """

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        original_error: Optional[Exception] = None,
        trace_id: Optional[str] = None,
    ):
        super().__init__(message)
        self.message = message
        self.category = category  # category must be set before _generate_error_code()
        self.severity = severity
        self.error_code = error_code or self._generate_error_code()
        self.context = context or {}
        self.timestamp = datetime.now()
        self.original_error = original_error
        self.trace_id = trace_id
        self._traceback = traceback.format_exc() if original_error else None

    def _generate_error_code(self) -> str:
        """클래스명 기반 기본 에러 코드 생성"""
        return f"{self.category.value}_{self.__class__.__name__.upper()}"

    def to_dict(self) -> Dict[str, Any]:
        """에러 정보를 딕셔너리로 변환"""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "category": self.category.value,
            "severity": self.severity.value,
            "context": self.context,
            "timestamp": self.timestamp.isoformat(),
            "trace_id": self.trace_id,
            "original_error": str(self.original_error) if self.original_error else None,
            "traceback": self._traceback,
        }

    def with_context(self, **kwargs) -> "HantuQuantException":
        """추가 컨텍스트 정보 추가"""
        self.context.update(kwargs)
        return self

    def with_trace_id(self, trace_id: str) -> "HantuQuantException":
        """추적 ID 설정"""
        self.trace_id = trace_id
        return self

    def __str__(self) -> str:
        parts = [f"[{self.error_code}] {self.message}"]
        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            parts.append(f" (context: {context_str})")
        if self.trace_id:
            parts.append(f" [trace: {self.trace_id}]")
        return "".join(parts)

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"message={self.message!r}, "
            f"error_code={self.error_code!r}, "
            f"severity={self.severity.value})"
        )


# ============================================================================
# API 관련 예외
# ============================================================================

class APIException(HantuQuantException):
    """API 관련 기본 예외"""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        original_error: Optional[Exception] = None,
        status_code: Optional[int] = None,
        api_name: Optional[str] = None,
    ):
        super().__init__(
            message=message,
            error_code=error_code or f"API_{status_code or 'ERROR'}",
            context=context,
            severity=severity,
            category=ErrorCategory.API,
            original_error=original_error,
        )
        self.status_code = status_code
        self.api_name = api_name
        if api_name:
            self.context["api_name"] = api_name
        if status_code:
            self.context["status_code"] = status_code


class APIConnectionError(APIException):
    """API 연결 실패"""

    def __init__(self, message: str = "API 연결 실패", **kwargs):
        super().__init__(message, error_code="API_CONNECTION_ERROR", **kwargs)


class APITimeoutError(APIException):
    """API 타임아웃"""

    def __init__(self, message: str = "API 요청 타임아웃", **kwargs):
        super().__init__(message, error_code="API_TIMEOUT", **kwargs)


class APIAuthenticationError(APIException):
    """API 인증 실패"""

    def __init__(self, message: str = "API 인증 실패", **kwargs):
        super().__init__(
            message,
            error_code="API_AUTH_ERROR",
            severity=ErrorSeverity.CRITICAL,
            **kwargs
        )


class APIRateLimitError(APIException):
    """API 요청 한도 초과"""

    def __init__(
        self,
        message: str = "API 요청 한도 초과",
        retry_after: Optional[int] = None,
        **kwargs
    ):
        super().__init__(message, error_code="API_RATE_LIMIT", **kwargs)
        self.retry_after = retry_after
        if retry_after:
            self.context["retry_after"] = retry_after


class APIResponseError(APIException):
    """API 응답 오류"""

    def __init__(
        self,
        message: str = "API 응답 오류",
        response_body: Optional[str] = None,
        **kwargs
    ):
        super().__init__(message, error_code="API_RESPONSE_ERROR", **kwargs)
        if response_body:
            self.context["response_body"] = response_body[:500]  # 500자 제한


# ============================================================================
# 거래 관련 예외
# ============================================================================

class TradingException(HantuQuantException):
    """거래 관련 기본 예외"""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        original_error: Optional[Exception] = None,
        stock_code: Optional[str] = None,
        order_id: Optional[str] = None,
    ):
        super().__init__(
            message=message,
            error_code=error_code or "TRADE_ERROR",
            context=context,
            severity=severity,
            category=ErrorCategory.TRADING,
            original_error=original_error,
        )
        self.stock_code = stock_code
        self.order_id = order_id
        if stock_code:
            self.context["stock_code"] = stock_code
        if order_id:
            self.context["order_id"] = order_id


class OrderExecutionError(TradingException):
    """주문 실행 오류"""

    def __init__(
        self,
        message: str = "주문 실행 실패",
        **kwargs
    ):
        super().__init__(
            message,
            error_code="TRADE_ORDER_EXECUTION",
            severity=ErrorSeverity.CRITICAL,
            **kwargs
        )


class OrderValidationError(TradingException):
    """주문 유효성 검증 오류"""

    def __init__(
        self,
        message: str = "주문 유효성 검증 실패",
        validation_errors: Optional[List[str]] = None,
        **kwargs
    ):
        super().__init__(message, error_code="TRADE_ORDER_VALIDATION", **kwargs)
        self.validation_errors = validation_errors or []
        if validation_errors:
            self.context["validation_errors"] = validation_errors


class InsufficientFundsError(TradingException):
    """잔고 부족"""

    def __init__(
        self,
        message: str = "잔고 부족",
        required: Optional[float] = None,
        available: Optional[float] = None,
        **kwargs
    ):
        super().__init__(message, error_code="TRADE_INSUFFICIENT_FUNDS", **kwargs)
        if required:
            self.context["required"] = required
        if available:
            self.context["available"] = available


class PositionLimitError(TradingException):
    """포지션 한도 초과"""

    def __init__(
        self,
        message: str = "포지션 한도 초과",
        limit: Optional[int] = None,
        current: Optional[int] = None,
        **kwargs
    ):
        super().__init__(message, error_code="TRADE_POSITION_LIMIT", **kwargs)
        if limit:
            self.context["limit"] = limit
        if current:
            self.context["current"] = current


class CircuitBreakerError(TradingException):
    """서킷 브레이커 발동"""

    def __init__(
        self,
        message: str = "서킷 브레이커 발동",
        reason: Optional[str] = None,
        cooldown_until: Optional[datetime] = None,
        **kwargs
    ):
        super().__init__(
            message,
            error_code="TRADE_CIRCUIT_BREAKER",
            severity=ErrorSeverity.CRITICAL,
            **kwargs
        )
        if reason:
            self.context["reason"] = reason
        if cooldown_until:
            self.context["cooldown_until"] = cooldown_until.isoformat()


# ============================================================================
# 데이터 관련 예외
# ============================================================================

class DataException(HantuQuantException):
    """데이터 관련 기본 예외"""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        original_error: Optional[Exception] = None,
        data_source: Optional[str] = None,
    ):
        super().__init__(
            message=message,
            error_code=error_code or "DATA_ERROR",
            context=context,
            severity=severity,
            category=ErrorCategory.DATA,
            original_error=original_error,
        )
        self.data_source = data_source
        if data_source:
            self.context["data_source"] = data_source


class DataFetchError(DataException):
    """데이터 조회 오류"""

    def __init__(self, message: str = "데이터 조회 실패", **kwargs):
        super().__init__(message, error_code="DATA_FETCH_ERROR", **kwargs)


class DataParseError(DataException):
    """데이터 파싱 오류"""

    def __init__(
        self,
        message: str = "데이터 파싱 실패",
        raw_data: Optional[str] = None,
        **kwargs
    ):
        super().__init__(message, error_code="DATA_PARSE_ERROR", **kwargs)
        if raw_data:
            self.context["raw_data"] = raw_data[:200]  # 200자 제한


class DataValidationError(DataException):
    """데이터 유효성 검증 오류"""

    def __init__(
        self,
        message: str = "데이터 유효성 검증 실패",
        field: Optional[str] = None,
        expected: Optional[Any] = None,
        actual: Optional[Any] = None,
        **kwargs
    ):
        super().__init__(message, error_code="DATA_VALIDATION_ERROR", **kwargs)
        if field:
            self.context["field"] = field
        if expected is not None:
            self.context["expected"] = str(expected)
        if actual is not None:
            self.context["actual"] = str(actual)


class DataNotFoundError(DataException):
    """데이터 없음"""

    def __init__(
        self,
        message: str = "데이터를 찾을 수 없음",
        **kwargs
    ):
        super().__init__(
            message,
            error_code="DATA_NOT_FOUND",
            severity=ErrorSeverity.WARNING,
            **kwargs
        )


class DataIntegrityError(DataException):
    """데이터 무결성 오류"""

    def __init__(
        self,
        message: str = "데이터 무결성 오류",
        **kwargs
    ):
        super().__init__(
            message,
            error_code="DATA_INTEGRITY_ERROR",
            severity=ErrorSeverity.CRITICAL,
            **kwargs
        )


# ============================================================================
# 설정 관련 예외
# ============================================================================

class ConfigException(HantuQuantException):
    """설정 관련 기본 예외"""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        original_error: Optional[Exception] = None,
        config_key: Optional[str] = None,
        config_file: Optional[str] = None,
    ):
        super().__init__(
            message=message,
            error_code=error_code or "CONFIG_ERROR",
            context=context,
            severity=severity,
            category=ErrorCategory.CONFIG,
            original_error=original_error,
        )
        if config_key:
            self.context["config_key"] = config_key
        if config_file:
            self.context["config_file"] = config_file


class ConfigNotFoundError(ConfigException):
    """설정 파일 없음"""

    def __init__(
        self,
        message: str = "설정 파일을 찾을 수 없음",
        **kwargs
    ):
        super().__init__(message, error_code="CONFIG_NOT_FOUND", **kwargs)


class ConfigValidationError(ConfigException):
    """설정 유효성 검증 오류"""

    def __init__(
        self,
        message: str = "설정 유효성 검증 실패",
        validation_errors: Optional[List[str]] = None,
        **kwargs
    ):
        super().__init__(message, error_code="CONFIG_VALIDATION_ERROR", **kwargs)
        if validation_errors:
            self.context["validation_errors"] = validation_errors


class ConfigMissingKeyError(ConfigException):
    """필수 설정 키 누락"""

    def __init__(
        self,
        message: str = "필수 설정 키 누락",
        missing_keys: Optional[List[str]] = None,
        **kwargs
    ):
        super().__init__(message, error_code="CONFIG_MISSING_KEY", **kwargs)
        if missing_keys:
            self.context["missing_keys"] = missing_keys


# ============================================================================
# 알림 관련 예외
# ============================================================================

class NotificationException(HantuQuantException):
    """알림 관련 기본 예외"""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        severity: ErrorSeverity = ErrorSeverity.WARNING,
        original_error: Optional[Exception] = None,
        notifier_type: Optional[str] = None,
    ):
        super().__init__(
            message=message,
            error_code=error_code or "NOTIFICATION_ERROR",
            context=context,
            severity=severity,
            category=ErrorCategory.NOTIFICATION,
            original_error=original_error,
        )
        if notifier_type:
            self.context["notifier_type"] = notifier_type


class NotificationSendError(NotificationException):
    """알림 발송 실패"""

    def __init__(
        self,
        message: str = "알림 발송 실패",
        alert_id: Optional[str] = None,
        **kwargs
    ):
        super().__init__(message, error_code="NOTIFICATION_SEND_ERROR", **kwargs)
        if alert_id:
            self.context["alert_id"] = alert_id


class NotificationConfigError(NotificationException):
    """알림 설정 오류"""

    def __init__(
        self,
        message: str = "알림 설정 오류",
        **kwargs
    ):
        super().__init__(message, error_code="NOTIFICATION_CONFIG_ERROR", **kwargs)


# ============================================================================
# 시스템 관련 예외
# ============================================================================

class SystemException(HantuQuantException):
    """시스템 관련 기본 예외"""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        original_error: Optional[Exception] = None,
        component: Optional[str] = None,
    ):
        super().__init__(
            message=message,
            error_code=error_code or "SYSTEM_ERROR",
            context=context,
            severity=severity,
            category=ErrorCategory.SYSTEM,
            original_error=original_error,
        )
        if component:
            self.context["component"] = component


class SystemStartupError(SystemException):
    """시스템 시작 오류"""

    def __init__(
        self,
        message: str = "시스템 시작 실패",
        **kwargs
    ):
        super().__init__(
            message,
            error_code="SYSTEM_STARTUP_ERROR",
            severity=ErrorSeverity.FATAL,
            **kwargs
        )


class SystemShutdownError(SystemException):
    """시스템 종료 오류"""

    def __init__(
        self,
        message: str = "시스템 종료 실패",
        **kwargs
    ):
        super().__init__(
            message,
            error_code="SYSTEM_SHUTDOWN_ERROR",
            severity=ErrorSeverity.CRITICAL,
            **kwargs
        )


class ResourceExhaustedError(SystemException):
    """리소스 고갈"""

    def __init__(
        self,
        message: str = "시스템 리소스 고갈",
        resource_type: Optional[str] = None,
        **kwargs
    ):
        super().__init__(
            message,
            error_code="SYSTEM_RESOURCE_EXHAUSTED",
            severity=ErrorSeverity.CRITICAL,
            **kwargs
        )
        if resource_type:
            self.context["resource_type"] = resource_type


# ============================================================================
# 유틸리티 함수
# ============================================================================

def wrap_exception(
    original: Exception,
    exception_class: Type[HantuQuantException] = HantuQuantException,
    message: Optional[str] = None,
    **kwargs
) -> HantuQuantException:
    """
    표준 예외를 HantuQuantException으로 래핑

    Args:
        original: 원본 예외
        exception_class: 래핑할 예외 클래스
        message: 추가 메시지 (없으면 원본 메시지 사용)
        **kwargs: 추가 인자

    Returns:
        HantuQuantException: 래핑된 예외
    """
    msg = message or str(original)
    return exception_class(
        message=msg,
        original_error=original,
        **kwargs
    )


def get_error_code(error: Exception) -> Optional[str]:
    """예외에서 에러 코드 추출"""
    if isinstance(error, HantuQuantException):
        return error.error_code
    return None


def get_error_context(error: Exception) -> Dict[str, Any]:
    """예외에서 컨텍스트 추출"""
    if isinstance(error, HantuQuantException):
        return error.context
    return {}


def is_retryable(error: Exception) -> bool:
    """재시도 가능한 에러인지 확인"""
    retryable_codes = [
        "API_TIMEOUT",
        "API_CONNECTION_ERROR",
        "API_RATE_LIMIT",
        "DATA_FETCH_ERROR",
    ]

    if isinstance(error, HantuQuantException):
        return error.error_code in retryable_codes

    # 표준 예외 타입 체크
    retryable_types = (ConnectionError, TimeoutError, OSError)
    return isinstance(error, retryable_types)


def is_critical(error: Exception) -> bool:
    """치명적 에러인지 확인"""
    if isinstance(error, HantuQuantException):
        return error.severity in (ErrorSeverity.CRITICAL, ErrorSeverity.FATAL)
    return False
