"""
Story 5.1: Custom Exception 체계 구축 테스트

T-5.1.1: HantuQuantException 기본 클래스 정의
T-5.1.2: 도메인별 Exception 클래스 계층
T-5.1.3: Exception에 error_code, context 필드 추가
T-5.1.4: Story 5.1 테스트 작성 및 검증
"""

import pytest
from datetime import datetime

from core.exceptions import (
    # Base
    HantuQuantException,
    ErrorSeverity,
    ErrorCategory,
    # API
    APIException,
    APIConnectionError,
    APITimeoutError,
    APIAuthenticationError,
    APIRateLimitError,
    APIResponseError,
    # Trading
    TradingException,
    OrderExecutionError,
    OrderValidationError,
    InsufficientFundsError,
    PositionLimitError,
    CircuitBreakerError,
    # Data
    DataException,
    DataFetchError,
    DataParseError,
    DataValidationError,
    DataNotFoundError,
    DataIntegrityError,
    # Config
    ConfigException,
    ConfigNotFoundError,
    ConfigValidationError,
    ConfigMissingKeyError,
    # Notification
    NotificationException,
    NotificationSendError,
    NotificationConfigError,
    # System
    SystemException,
    SystemStartupError,
    SystemShutdownError,
    ResourceExhaustedError,
    # Utilities
    wrap_exception,
    get_error_code,
    get_error_context,
    is_retryable,
    is_critical,
)


class TestHantuQuantException:
    """HantuQuantException 기본 테스트"""

    def test_basic_exception(self):
        """기본 예외 생성"""
        exc = HantuQuantException("테스트 에러")
        assert exc.message == "테스트 에러"
        assert exc.error_code is not None
        assert isinstance(exc.timestamp, datetime)

    def test_exception_with_error_code(self):
        """에러 코드 지정"""
        exc = HantuQuantException("테스트", error_code="TEST_001")
        assert exc.error_code == "TEST_001"

    def test_exception_with_context(self):
        """컨텍스트 지정"""
        context = {"user": "test", "action": "buy"}
        exc = HantuQuantException("테스트", context=context)
        assert exc.context == context
        assert exc.context["user"] == "test"

    def test_exception_with_severity(self):
        """심각도 지정"""
        exc = HantuQuantException("테스트", severity=ErrorSeverity.CRITICAL)
        assert exc.severity == ErrorSeverity.CRITICAL

    def test_exception_with_category(self):
        """카테고리 지정"""
        exc = HantuQuantException("테스트", category=ErrorCategory.API)
        assert exc.category == ErrorCategory.API

    def test_exception_with_original_error(self):
        """원본 예외 래핑"""
        original = ValueError("원본 에러")
        exc = HantuQuantException("래핑된 에러", original_error=original)
        assert exc.original_error == original

    def test_exception_with_trace_id(self):
        """추적 ID 지정"""
        exc = HantuQuantException("테스트", trace_id="trace-123")
        assert exc.trace_id == "trace-123"

    def test_to_dict(self):
        """딕셔너리 변환"""
        exc = HantuQuantException(
            "테스트",
            error_code="TEST_001",
            context={"key": "value"},
            trace_id="trace-123"
        )
        d = exc.to_dict()
        assert d["error_code"] == "TEST_001"
        assert d["message"] == "테스트"
        assert d["context"]["key"] == "value"
        assert d["trace_id"] == "trace-123"
        assert "timestamp" in d

    def test_with_context_chaining(self):
        """컨텍스트 추가 체이닝"""
        exc = HantuQuantException("테스트")
        exc.with_context(user="test", action="buy")
        assert exc.context["user"] == "test"
        assert exc.context["action"] == "buy"

    def test_with_trace_id_chaining(self):
        """추적 ID 추가 체이닝"""
        exc = HantuQuantException("테스트").with_trace_id("trace-456")
        assert exc.trace_id == "trace-456"

    def test_str_representation(self):
        """문자열 표현"""
        exc = HantuQuantException(
            "테스트 에러",
            error_code="TEST_001",
            context={"key": "value"},
            trace_id="trace-123"
        )
        s = str(exc)
        assert "[TEST_001]" in s
        assert "테스트 에러" in s
        assert "key=value" in s
        assert "trace: trace-123" in s

    def test_repr_representation(self):
        """repr 표현"""
        exc = HantuQuantException(
            "테스트",
            error_code="TEST_001",
            severity=ErrorSeverity.ERROR
        )
        r = repr(exc)
        assert "HantuQuantException" in r
        assert "TEST_001" in r


class TestAPIExceptions:
    """API 예외 테스트"""

    def test_api_exception_category(self):
        """API 예외 카테고리"""
        exc = APIException("API 오류")
        assert exc.category == ErrorCategory.API

    def test_api_exception_with_status_code(self):
        """상태 코드 포함"""
        exc = APIException("API 오류", status_code=500, api_name="KIS")
        assert exc.status_code == 500
        assert exc.api_name == "KIS"
        assert exc.context["status_code"] == 500
        assert exc.context["api_name"] == "KIS"

    def test_api_connection_error(self):
        """연결 오류"""
        exc = APIConnectionError()
        assert exc.error_code == "API_CONNECTION_ERROR"

    def test_api_timeout_error(self):
        """타임아웃 오류"""
        exc = APITimeoutError()
        assert exc.error_code == "API_TIMEOUT"

    def test_api_authentication_error(self):
        """인증 오류"""
        exc = APIAuthenticationError()
        assert exc.error_code == "API_AUTH_ERROR"
        assert exc.severity == ErrorSeverity.CRITICAL

    def test_api_rate_limit_error(self):
        """요청 한도 초과"""
        exc = APIRateLimitError(retry_after=60)
        assert exc.error_code == "API_RATE_LIMIT"
        assert exc.retry_after == 60
        assert exc.context["retry_after"] == 60

    def test_api_response_error(self):
        """응답 오류"""
        exc = APIResponseError(response_body='{"error": "bad request"}')
        assert exc.error_code == "API_RESPONSE_ERROR"
        assert "response_body" in exc.context


class TestTradingExceptions:
    """거래 예외 테스트"""

    def test_trading_exception_category(self):
        """거래 예외 카테고리"""
        exc = TradingException("거래 오류")
        assert exc.category == ErrorCategory.TRADING

    def test_trading_exception_with_stock_code(self):
        """종목 코드 포함"""
        exc = TradingException("오류", stock_code="005930", order_id="ORD001")
        assert exc.stock_code == "005930"
        assert exc.order_id == "ORD001"
        assert exc.context["stock_code"] == "005930"

    def test_order_execution_error(self):
        """주문 실행 오류"""
        exc = OrderExecutionError(stock_code="005930")
        assert exc.error_code == "TRADE_ORDER_EXECUTION"
        assert exc.severity == ErrorSeverity.CRITICAL

    def test_order_validation_error(self):
        """주문 유효성 오류"""
        exc = OrderValidationError(validation_errors=["가격 오류", "수량 오류"])
        assert exc.error_code == "TRADE_ORDER_VALIDATION"
        assert exc.validation_errors == ["가격 오류", "수량 오류"]

    def test_insufficient_funds_error(self):
        """잔고 부족"""
        exc = InsufficientFundsError(required=1000000, available=500000)
        assert exc.error_code == "TRADE_INSUFFICIENT_FUNDS"
        assert exc.context["required"] == 1000000
        assert exc.context["available"] == 500000

    def test_position_limit_error(self):
        """포지션 한도 초과"""
        exc = PositionLimitError(limit=10, current=11)
        assert exc.error_code == "TRADE_POSITION_LIMIT"
        assert exc.context["limit"] == 10

    def test_circuit_breaker_error(self):
        """서킷 브레이커"""
        exc = CircuitBreakerError(reason="일간 손실 한도 초과")
        assert exc.error_code == "TRADE_CIRCUIT_BREAKER"
        assert exc.severity == ErrorSeverity.CRITICAL
        assert exc.context["reason"] == "일간 손실 한도 초과"


class TestDataExceptions:
    """데이터 예외 테스트"""

    def test_data_exception_category(self):
        """데이터 예외 카테고리"""
        exc = DataException("데이터 오류")
        assert exc.category == ErrorCategory.DATA

    def test_data_exception_with_source(self):
        """데이터 소스 포함"""
        exc = DataException("오류", data_source="KIS_API")
        assert exc.data_source == "KIS_API"
        assert exc.context["data_source"] == "KIS_API"

    def test_data_fetch_error(self):
        """조회 오류"""
        exc = DataFetchError()
        assert exc.error_code == "DATA_FETCH_ERROR"

    def test_data_parse_error(self):
        """파싱 오류"""
        exc = DataParseError(raw_data='{"invalid": json}')
        assert exc.error_code == "DATA_PARSE_ERROR"
        assert "raw_data" in exc.context

    def test_data_validation_error(self):
        """유효성 검증 오류"""
        exc = DataValidationError(field="price", expected="positive", actual=-100)
        assert exc.error_code == "DATA_VALIDATION_ERROR"
        assert exc.context["field"] == "price"
        assert exc.context["expected"] == "positive"
        assert exc.context["actual"] == "-100"

    def test_data_not_found_error(self):
        """데이터 없음"""
        exc = DataNotFoundError()
        assert exc.error_code == "DATA_NOT_FOUND"
        assert exc.severity == ErrorSeverity.WARNING

    def test_data_integrity_error(self):
        """무결성 오류"""
        exc = DataIntegrityError()
        assert exc.error_code == "DATA_INTEGRITY_ERROR"
        assert exc.severity == ErrorSeverity.CRITICAL


class TestConfigExceptions:
    """설정 예외 테스트"""

    def test_config_exception_category(self):
        """설정 예외 카테고리"""
        exc = ConfigException("설정 오류")
        assert exc.category == ErrorCategory.CONFIG

    def test_config_not_found_error(self):
        """설정 파일 없음"""
        exc = ConfigNotFoundError(config_file="config.yaml")
        assert exc.error_code == "CONFIG_NOT_FOUND"
        assert exc.context["config_file"] == "config.yaml"

    def test_config_validation_error(self):
        """설정 유효성 오류"""
        exc = ConfigValidationError(validation_errors=["invalid key"])
        assert exc.error_code == "CONFIG_VALIDATION_ERROR"
        assert exc.context["validation_errors"] == ["invalid key"]

    def test_config_missing_key_error(self):
        """필수 키 누락"""
        exc = ConfigMissingKeyError(missing_keys=["api_key", "secret"])
        assert exc.error_code == "CONFIG_MISSING_KEY"
        assert exc.context["missing_keys"] == ["api_key", "secret"]


class TestNotificationExceptions:
    """알림 예외 테스트"""

    def test_notification_exception_category(self):
        """알림 예외 카테고리"""
        exc = NotificationException("알림 오류")
        assert exc.category == ErrorCategory.NOTIFICATION

    def test_notification_send_error(self):
        """발송 오류"""
        exc = NotificationSendError(alert_id="alert-123", notifier_type="telegram")
        assert exc.error_code == "NOTIFICATION_SEND_ERROR"
        assert exc.context["alert_id"] == "alert-123"
        assert exc.context["notifier_type"] == "telegram"

    def test_notification_config_error(self):
        """설정 오류"""
        exc = NotificationConfigError()
        assert exc.error_code == "NOTIFICATION_CONFIG_ERROR"


class TestSystemExceptions:
    """시스템 예외 테스트"""

    def test_system_exception_category(self):
        """시스템 예외 카테고리"""
        exc = SystemException("시스템 오류")
        assert exc.category == ErrorCategory.SYSTEM

    def test_system_startup_error(self):
        """시작 오류"""
        exc = SystemStartupError(component="TradingEngine")
        assert exc.error_code == "SYSTEM_STARTUP_ERROR"
        assert exc.severity == ErrorSeverity.FATAL
        assert exc.context["component"] == "TradingEngine"

    def test_system_shutdown_error(self):
        """종료 오류"""
        exc = SystemShutdownError()
        assert exc.error_code == "SYSTEM_SHUTDOWN_ERROR"
        assert exc.severity == ErrorSeverity.CRITICAL

    def test_resource_exhausted_error(self):
        """리소스 고갈"""
        exc = ResourceExhaustedError(resource_type="memory")
        assert exc.error_code == "SYSTEM_RESOURCE_EXHAUSTED"
        assert exc.context["resource_type"] == "memory"


class TestUtilityFunctions:
    """유틸리티 함수 테스트"""

    def test_wrap_exception(self):
        """예외 래핑"""
        original = ValueError("원본 오류")
        wrapped = wrap_exception(original, APIException, api_name="KIS")
        assert isinstance(wrapped, APIException)
        assert wrapped.original_error == original
        assert wrapped.context["api_name"] == "KIS"

    def test_wrap_exception_with_custom_message(self):
        """커스텀 메시지로 래핑"""
        original = ValueError("원본")
        wrapped = wrap_exception(original, message="새 메시지")
        assert wrapped.message == "새 메시지"

    def test_get_error_code(self):
        """에러 코드 추출"""
        exc = HantuQuantException("테스트", error_code="TEST_001")
        assert get_error_code(exc) == "TEST_001"
        assert get_error_code(ValueError("일반")) is None

    def test_get_error_context(self):
        """컨텍스트 추출"""
        exc = HantuQuantException("테스트", context={"key": "value"})
        assert get_error_context(exc) == {"key": "value"}
        assert get_error_context(ValueError("일반")) == {}

    def test_is_retryable(self):
        """재시도 가능 체크"""
        assert is_retryable(APITimeoutError()) is True
        assert is_retryable(APIConnectionError()) is True
        assert is_retryable(APIRateLimitError()) is True
        assert is_retryable(DataFetchError()) is True
        assert is_retryable(APIAuthenticationError()) is False
        assert is_retryable(OrderExecutionError()) is False

    def test_is_retryable_standard_exceptions(self):
        """표준 예외 재시도 가능 체크"""
        assert is_retryable(ConnectionError()) is True
        assert is_retryable(TimeoutError()) is True
        assert is_retryable(ValueError()) is False

    def test_is_critical(self):
        """치명적 에러 체크"""
        assert is_critical(SystemStartupError()) is True
        assert is_critical(APIAuthenticationError()) is True
        assert is_critical(CircuitBreakerError()) is True
        assert is_critical(APITimeoutError()) is False
        assert is_critical(DataNotFoundError()) is False
        assert is_critical(ValueError()) is False


class TestExceptionHierarchy:
    """예외 계층 테스트"""

    def test_all_exceptions_inherit_from_base(self):
        """모든 예외가 기본 클래스 상속"""
        exceptions = [
            APIException("test"),
            TradingException("test"),
            DataException("test"),
            ConfigException("test"),
            NotificationException("test"),
            SystemException("test"),
        ]
        for exc in exceptions:
            assert isinstance(exc, HantuQuantException)

    def test_api_exceptions_inherit_from_api_base(self):
        """API 예외가 APIException 상속"""
        exceptions = [
            APIConnectionError(),
            APITimeoutError(),
            APIAuthenticationError(),
            APIRateLimitError(),
            APIResponseError(),
        ]
        for exc in exceptions:
            assert isinstance(exc, APIException)
            assert isinstance(exc, HantuQuantException)

    def test_trading_exceptions_inherit_from_trading_base(self):
        """거래 예외가 TradingException 상속"""
        exceptions = [
            OrderExecutionError(),
            OrderValidationError(),
            InsufficientFundsError(),
            PositionLimitError(),
            CircuitBreakerError(),
        ]
        for exc in exceptions:
            assert isinstance(exc, TradingException)
            assert isinstance(exc, HantuQuantException)

    def test_exception_is_catchable_as_exception(self):
        """표준 Exception으로 catch 가능"""
        exc = APITimeoutError()
        assert isinstance(exc, Exception)

    def test_exception_can_be_raised_and_caught(self):
        """raise/catch 동작"""
        with pytest.raises(HantuQuantException) as exc_info:
            raise APITimeoutError(api_name="KIS")

        assert exc_info.value.error_code == "API_TIMEOUT"
        assert exc_info.value.context["api_name"] == "KIS"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
