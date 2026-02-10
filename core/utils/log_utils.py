"""
로깅 유틸리티 모듈 (P2-2)

기능:
- 민감한 정보 마스킹
- JSON 형식 구조화 로깅
- 일별 로그 로테이션 (3일 보관)
- 요청 추적용 trace_id
"""

import logging
import logging.handlers
import json
import re
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional
from contextvars import ContextVar
from core.utils.emoji_filter import EmojiRemovalFilter

# trace_id를 위한 컨텍스트 변수 (스레드 안전)
_trace_id: ContextVar[str] = ContextVar('trace_id', default='')


def get_trace_id() -> str:
    """현재 trace_id 반환"""
    return _trace_id.get()


def set_trace_id(trace_id: Optional[str] = None) -> str:
    """새 trace_id 설정 (없으면 자동 생성)"""
    if trace_id is None:
        trace_id = str(uuid.uuid4())[:8]
    _trace_id.set(trace_id)
    return trace_id


def clear_trace_id():
    """trace_id 초기화"""
    _trace_id.set('')


class TraceIdContext:
    """trace_id 컨텍스트 관리자"""

    def __init__(self, trace_id: Optional[str] = None):
        self.trace_id = trace_id
        self.prev_trace_id = ''

    def __enter__(self):
        self.prev_trace_id = get_trace_id()
        set_trace_id(self.trace_id)
        return get_trace_id()

    def __exit__(self, exc_type, exc_val, exc_tb):
        _trace_id.set(self.prev_trace_id)

# 마스킹할 필드 목록
SENSITIVE_FIELDS = [
    'app_key', 'APP_KEY', 'app_secret', 'APP_SECRET',
    'access_token', 'ACCESS_TOKEN', 'refresh_token', 'REFRESH_TOKEN',
    'account_number', 'ACCOUNT_NUMBER', 'password', 'PASSWORD',
    'token', 'auth', 'key', 'secret'
]

class SensitiveDataFilter(logging.Filter):
    """민감 정보 필터 클래스"""
    
    def __init__(self, fields: Optional[List[str]] = None):
        """초기화
        
        Args:
            fields: 마스킹할 필드 목록 (기본값 사용 시 None)
        """
        super().__init__()
        self.fields = fields or SENSITIVE_FIELDS
        
    def filter(self, record):
        """로그 레코드 필터링"""
        if isinstance(record.msg, str):
            record.msg = self._mask_sensitive_data(record.msg)
            
        return True
        
    def _mask_sensitive_data(self, msg: str) -> str:
        """민감한 정보 마스킹
        
        Args:
            msg: 원본 로그 메시지
            
        Returns:
            마스킹 처리된 메시지
        """
        # JSON 및 dictionary 형식의 민감 데이터 마스킹
        for field in self.fields:
            # JSON 패턴 (예: "access_token": "abcdefg")
            pattern1 = fr'["\']({field})["\']:\s*["\']([^"\']+)["\']'
            msg = re.sub(pattern1, r'"\1": "***MASKED***"', msg, flags=re.IGNORECASE)
            
            # 변수 할당 패턴 (예: access_token=abcdefg)
            pattern2 = fr'({field})\s*=\s*["\']?([^"\'\s,\)]+)'
            msg = re.sub(pattern2, r'\1=***MASKED***', msg, flags=re.IGNORECASE)
            
        return msg


class TraceIdFilter(logging.Filter):
    """
    trace_id를 로그 레코드에 추가하는 필터

    Feature 2.1: 로깅 아키텍처 통합
    """

    def filter(self, record):
        """trace_id를 레코드에 추가"""
        record.trace_id = get_trace_id() or "-"
        return True


def setup_logging(log_file: str = None, level: int = logging.INFO, add_sensitive_filter: bool = True):
    """로깅 설정

    Args:
        log_file: 로그 파일 경로 (콘솔만 사용 시 None)
        level: 로깅 레벨
        add_sensitive_filter: 민감 정보 필터 사용 여부
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # 기존 핸들러 제거
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # 콘솔 핸들러
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_formatter = logging.Formatter('%(message)s')
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # 파일 핸들러 (설정된 경우)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

    # 필터 적용 (순서: 이모지 제거 → 민감 정보 마스킹)
    emoji_filter = EmojiRemovalFilter()
    for handler in root_logger.handlers:
        handler.addFilter(emoji_filter)

    if add_sensitive_filter:
        sensitive_filter = SensitiveDataFilter()
        for handler in root_logger.handlers:
            handler.addFilter(sensitive_filter)

    return root_logger

def get_logger(name: str) -> logging.Logger:
    """로거 인스턴스 생성

    Args:
        name: 로거 이름 (보통 __name__ 사용)

    Returns:
        로거 인스턴스
    """
    return logging.getLogger(name)


# ========== JSON 구조화 로깅 (P2-2) ==========

class JSONFormatter(logging.Formatter):
    """JSON 형식 로그 포맷터

    로그 분석 및 모니터링 시스템 통합을 위한 구조화된 JSON 출력.
    ELK Stack, CloudWatch Logs 등과 호환.
    """

    def __init__(
        self,
        include_extras: bool = True,
        ensure_ascii: bool = False,
    ):
        """초기화

        Args:
            include_extras: 추가 필드 포함 여부
            ensure_ascii: ASCII만 출력 여부 (한글은 False)
        """
        super().__init__()
        self.include_extras = include_extras
        self.ensure_ascii = ensure_ascii

    def format(self, record: logging.LogRecord) -> str:
        """로그 레코드를 JSON 문자열로 변환"""
        # getMessage() 안전 처리 (pykrx 등 외부 라이브러리 로깅 호환)
        try:
            message = record.getMessage()
        except (TypeError, ValueError):
            # 포맷 실패 시 원본 메시지 사용
            message = str(record.msg) if record.msg else ""
            if record.args:
                message += f" | args={record.args}"

        log_data = {
            'timestamp': datetime.now().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'message': message,
        }

        # trace_id 추가
        trace_id = get_trace_id()
        if trace_id:
            log_data['trace_id'] = trace_id

        # 예외 정보 추가
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)

        # 스택 정보 추가
        if record.stack_info:
            log_data['stack_info'] = self.formatStack(record.stack_info)

        # 추가 필드 (record에 동적으로 추가된 속성)
        if self.include_extras:
            standard_attrs = {
                'name', 'msg', 'args', 'created', 'filename', 'funcName',
                'levelname', 'levelno', 'lineno', 'module', 'msecs',
                'pathname', 'process', 'processName', 'relativeCreated',
                'stack_info', 'exc_info', 'exc_text', 'thread', 'threadName',
                'message', 'asctime', 'taskName'
            }
            extras = {
                k: v for k, v in record.__dict__.items()
                if k not in standard_attrs and not k.startswith('_')
            }
            if extras:
                log_data['extra'] = extras

        return json.dumps(log_data, ensure_ascii=self.ensure_ascii, default=str)


class StructuredLogger:
    """구조화된 로깅을 위한 래퍼 클래스

    로그 메시지에 구조화된 데이터를 쉽게 추가할 수 있습니다.
    """

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def _log(self, level: int, msg: str, **kwargs):
        """구조화된 로그 출력"""
        extra = kwargs.pop('extra', {})
        extra.update(kwargs)
        self.logger.log(level, msg, extra={'data': extra})

    def debug(self, msg: str, **kwargs):
        self._log(logging.DEBUG, msg, **kwargs)

    def info(self, msg: str, **kwargs):
        self._log(logging.INFO, msg, **kwargs)

    def warning(self, msg: str, **kwargs):
        self._log(logging.WARNING, msg, **kwargs)

    def error(self, msg: str, **kwargs):
        self._log(logging.ERROR, msg, **kwargs)

    def critical(self, msg: str, **kwargs):
        self._log(logging.CRITICAL, msg, **kwargs)


def setup_json_logging(
    log_file: str,
    level: int = logging.INFO,
    backup_count: int = 3,  # 로컬 파일 3일 보관 정책 (2026-02-01)
    add_console: bool = True,
    add_sensitive_filter: bool = True,
) -> logging.Logger:
    """JSON 형식 로깅 설정

    Args:
        log_file: 로그 파일 경로
        level: 로깅 레벨
        backup_count: 백업 파일 수 (일수)
        add_console: 콘솔 출력 추가 여부
        add_sensitive_filter: 민감 정보 필터 사용 여부

    Returns:
        설정된 루트 로거
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # 기존 핸들러 제거
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # 일별 로테이션 파일 핸들러 (JSON 형식)
    file_handler = logging.handlers.TimedRotatingFileHandler(
        log_file,
        when='midnight',
        interval=1,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(file_handler)

    # 콘솔 핸들러 (사람이 읽기 쉬운 형식)
    if add_console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

    # 필터 적용 (순서: 이모지 제거 → 민감 정보 마스킹)
    emoji_filter = EmojiRemovalFilter()
    for handler in root_logger.handlers:
        handler.addFilter(emoji_filter)

    if add_sensitive_filter:
        sensitive_filter = SensitiveDataFilter()
        for handler in root_logger.handlers:
            handler.addFilter(sensitive_filter)

    return root_logger


def get_structured_logger(name: str) -> StructuredLogger:
    """구조화된 로거 인스턴스 생성

    Args:
        name: 로거 이름

    Returns:
        StructuredLogger 인스턴스
    """
    return StructuredLogger(logging.getLogger(name))


# ========== Context-aware Error Logging (Story 5.2) ==========

import time  # noqa: E402
import functools  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402
from typing import Callable  # noqa: E402

# 현재 ErrorContext를 위한 컨텍스트 변수
_error_context: ContextVar[Optional['ErrorContext']] = ContextVar('error_context', default=None)


@dataclass
class ErrorContext:
    """
    에러 컨텍스트 정보

    에러 발생 시 추적에 필요한 모든 컨텍스트 정보를 담습니다.

    Story 5.2: Context-aware Error Logging
    T-5.2.1: ErrorContext 클래스 설계
    """
    operation: str                           # 현재 수행 중인 작업 (예: "order_execution", "data_fetch")
    trace_id: str = field(default_factory=lambda: get_trace_id() or set_trace_id())
    start_time: float = field(default_factory=time.time)
    user_context: Dict[str, Any] = field(default_factory=dict)
    parent_context: Optional['ErrorContext'] = None

    # 추가 메타데이터
    component: Optional[str] = None          # 컴포넌트 이름 (예: "TradingEngine", "DataManager")
    stock_code: Optional[str] = None         # 관련 종목 코드
    order_id: Optional[str] = None           # 관련 주문 ID
    request_id: Optional[str] = None         # 요청 ID

    def elapsed_time(self) -> float:
        """경과 시간 (초)"""
        return time.time() - self.start_time

    def elapsed_ms(self) -> float:
        """경과 시간 (밀리초)"""
        return self.elapsed_time() * 1000

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 변환"""
        result = {
            'operation': self.operation,
            'trace_id': self.trace_id,
            'elapsed_ms': round(self.elapsed_ms(), 2),
            'component': self.component,
        }
        if self.stock_code:
            result['stock_code'] = self.stock_code
        if self.order_id:
            result['order_id'] = self.order_id
        if self.request_id:
            result['request_id'] = self.request_id
        if self.user_context:
            result['user_context'] = self.user_context
        if self.parent_context:
            result['parent_operation'] = self.parent_context.operation
        return result

    def with_user_context(self, **kwargs) -> 'ErrorContext':
        """사용자 컨텍스트 추가"""
        self.user_context.update(kwargs)
        return self


def get_error_context() -> Optional[ErrorContext]:
    """현재 ErrorContext 반환"""
    return _error_context.get()


def set_error_context(context: Optional[ErrorContext]) -> None:
    """ErrorContext 설정"""
    _error_context.set(context)


class ErrorContextManager:
    """ErrorContext 컨텍스트 관리자

    with 문을 사용하여 ErrorContext를 스코프 내에서 관리합니다.
    """

    def __init__(
        self,
        operation: str,
        component: Optional[str] = None,
        stock_code: Optional[str] = None,
        order_id: Optional[str] = None,
        **user_context
    ):
        self.context = ErrorContext(
            operation=operation,
            component=component,
            stock_code=stock_code,
            order_id=order_id,
            user_context=user_context,
            parent_context=get_error_context(),
        )
        self.prev_context: Optional[ErrorContext] = None

    def __enter__(self) -> ErrorContext:
        self.prev_context = get_error_context()
        set_error_context(self.context)
        return self.context

    def __exit__(self, exc_type, exc_val, exc_tb):
        set_error_context(self.prev_context)
        return False  # 예외 전파


class ContextLogger:
    """
    Context-aware 로거 래퍼

    기존 로거에 ErrorContext를 자동으로 주입합니다.

    Story 5.2: Context-aware Error Logging
    T-5.2.2: ContextLogger 래퍼 클래스 구현
    """

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def _get_context_data(self) -> Dict[str, Any]:
        """현재 컨텍스트 데이터 수집"""
        data = {}

        # trace_id 추가
        trace_id = get_trace_id()
        if trace_id:
            data['trace_id'] = trace_id

        # ErrorContext 추가
        error_ctx = get_error_context()
        if error_ctx:
            data['context'] = error_ctx.to_dict()

        return data

    def _log(
        self,
        level: int,
        msg: str,
        exc_info: bool = False,
        **kwargs
    ):
        """컨텍스트와 함께 로그 출력"""
        extra = self._get_context_data()
        extra.update(kwargs)

        # extra 속성을 LogRecord에 추가
        self.logger.log(
            level,
            msg,
            exc_info=exc_info,
            extra={'context_data': extra} if extra else {}
        )

    def debug(self, msg: str, **kwargs):
        """DEBUG 레벨 로그"""
        self._log(logging.DEBUG, msg, **kwargs)

    def info(self, msg: str, **kwargs):
        """INFO 레벨 로그"""
        self._log(logging.INFO, msg, **kwargs)

    def warning(self, msg: str, **kwargs):
        """WARNING 레벨 로그"""
        self._log(logging.WARNING, msg, **kwargs)

    def error(self, msg: str, exc_info: bool = False, **kwargs):
        """ERROR 레벨 로그"""
        self._log(logging.ERROR, msg, exc_info=exc_info, **kwargs)

    def critical(self, msg: str, exc_info: bool = False, **kwargs):
        """CRITICAL 레벨 로그"""
        self._log(logging.CRITICAL, msg, exc_info=exc_info, **kwargs)

    def exception(self, msg: str, **kwargs):
        """예외와 함께 ERROR 로그"""
        self._log(logging.ERROR, msg, exc_info=True, **kwargs)

    def log_error(
        self,
        error: Exception,
        msg: Optional[str] = None,
        **kwargs
    ):
        """
        예외를 구조화된 형태로 로깅

        HantuQuantException인 경우 추가 정보도 함께 기록합니다.
        """
        from core.exceptions import HantuQuantException

        error_data = {
            'error_type': type(error).__name__,
            'error_message': str(error),
        }

        if isinstance(error, HantuQuantException):
            error_data['error_code'] = error.error_code
            error_data['error_context'] = error.context
            error_data['severity'] = error.severity.value
            error_data['category'] = error.category.value
            if error.trace_id:
                error_data['error_trace_id'] = error.trace_id

        error_data.update(kwargs)

        log_msg = msg or str(error)
        self._log(logging.ERROR, log_msg, exc_info=True, **error_data)


def get_context_logger(name: str) -> ContextLogger:
    """Context-aware 로거 인스턴스 생성

    Args:
        name: 로거 이름 (보통 __name__ 사용)

    Returns:
        ContextLogger 인스턴스
    """
    return ContextLogger(logging.getLogger(name))


def log_context(
    operation: str,
    component: Optional[str] = None,
    log_entry: bool = True,
    log_exit: bool = True,
    log_exceptions: bool = True,
):
    """
    함수 진입/종료 시 컨텍스트를 자동으로 설정하는 데코레이터

    Story 5.2: Context-aware Error Logging
    T-5.2.3: @log_context 데코레이터 구현

    Args:
        operation: 작업 이름
        component: 컴포넌트 이름
        log_entry: 진입 시 로깅 여부
        log_exit: 종료 시 로깅 여부
        log_exceptions: 예외 발생 시 로깅 여부

    Example:
        @log_context("process_order", component="TradingEngine")
        def process_order(order_id: str):
            ...
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            logger = get_context_logger(func.__module__)

            with ErrorContextManager(operation=operation, component=component) as ctx:
                if log_entry:
                    logger.debug(
                        f"Entering {operation}",
                        function=func.__name__,
                        args_count=len(args),
                        kwargs_keys=list(kwargs.keys()),
                    )

                try:
                    result = func(*args, **kwargs)

                    if log_exit:
                        logger.debug(
                            f"Exiting {operation}",
                            function=func.__name__,
                            elapsed_ms=ctx.elapsed_ms(),
                            success=True,
                        )

                    return result

                except Exception as e:
                    if log_exceptions:
                        logger.log_error(
                            e,
                            f"Exception in {operation}",
                            function=func.__name__,
                            elapsed_ms=ctx.elapsed_ms(),
                        )
                    raise

        return wrapper
    return decorator


def log_async_context(
    operation: str,
    component: Optional[str] = None,
    log_entry: bool = True,
    log_exit: bool = True,
    log_exceptions: bool = True,
):
    """
    비동기 함수용 컨텍스트 데코레이터

    async 함수에 적용 가능합니다.

    Example:
        @log_async_context("fetch_data", component="DataManager")
        async def fetch_data(symbol: str):
            ...
    """

    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            logger = get_context_logger(func.__module__)

            with ErrorContextManager(operation=operation, component=component) as ctx:
                if log_entry:
                    logger.debug(
                        f"Entering async {operation}",
                        function=func.__name__,
                        args_count=len(args),
                        kwargs_keys=list(kwargs.keys()),
                    )

                try:
                    result = await func(*args, **kwargs)

                    if log_exit:
                        logger.debug(
                            f"Exiting async {operation}",
                            function=func.__name__,
                            elapsed_ms=ctx.elapsed_ms(),
                            success=True,
                        )

                    return result

                except Exception as e:
                    if log_exceptions:
                        logger.log_error(
                            e,
                            f"Exception in async {operation}",
                            function=func.__name__,
                            elapsed_ms=ctx.elapsed_ms(),
                        )
                    raise

        return wrapper
    return decorator


# ========== Distributed Tracing (Story 5.3) ==========

from enum import Enum  # noqa: E402


class SpanStatus(Enum):
    """Span 상태"""
    UNSET = "UNSET"
    OK = "OK"
    ERROR = "ERROR"


# 현재 Span을 위한 컨텍스트 변수
_current_span: ContextVar[Optional['SpanContext']] = ContextVar('current_span', default=None)


def generate_span_id() -> str:
    """고유한 span_id 생성 (16자리 hex)"""
    return uuid.uuid4().hex[:16]


def generate_trace_id() -> str:
    """고유한 trace_id 생성 (32자리 hex)"""
    return uuid.uuid4().hex


@dataclass
class SpanContext:
    """
    분산 추적을 위한 Span 컨텍스트

    OpenTelemetry/Jaeger 스타일의 분산 추적을 구현합니다.

    Story 5.3: Distributed Tracing 구현
    T-5.3.1: trace_id 생성 및 전파 로직
    T-5.3.2: SpanContext 클래스 구현
    """
    operation_name: str                        # 작업 이름
    span_id: str = field(default_factory=generate_span_id)
    trace_id: str = field(default_factory=lambda: get_trace_id() or generate_trace_id())
    parent_span_id: Optional[str] = None       # 부모 span ID
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    status: SpanStatus = SpanStatus.UNSET
    tags: Dict[str, Any] = field(default_factory=dict)
    logs: List[Dict[str, Any]] = field(default_factory=list)

    # 추가 메타데이터
    component: Optional[str] = None
    service_name: str = "hantu_quant"

    def finish(self, status: SpanStatus = SpanStatus.OK):
        """Span 종료"""
        self.end_time = time.time()
        self.status = status

    def finish_with_error(self, error: Optional[Exception] = None):
        """에러와 함께 Span 종료"""
        self.end_time = time.time()
        self.status = SpanStatus.ERROR
        if error:
            self.add_log("error", str(error))
            self.set_tag("error.type", type(error).__name__)
            self.set_tag("error.message", str(error))

    def duration_ms(self) -> Optional[float]:
        """Span 지속 시간 (밀리초)"""
        if self.end_time is None:
            return (time.time() - self.start_time) * 1000
        return (self.end_time - self.start_time) * 1000

    def set_tag(self, key: str, value: Any) -> 'SpanContext':
        """태그 설정"""
        self.tags[key] = value
        return self

    def add_log(self, event: str, message: str, **kwargs) -> 'SpanContext':
        """로그 추가"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event": event,
            "message": message,
        }
        log_entry.update(kwargs)
        self.logs.append(log_entry)
        return self

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 변환 (로깅/직렬화용)"""
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "operation_name": self.operation_name,
            "service_name": self.service_name,
            "component": self.component,
            "start_time": datetime.fromtimestamp(self.start_time).isoformat(),
            "end_time": datetime.fromtimestamp(self.end_time).isoformat() if self.end_time else None,
            "duration_ms": round(self.duration_ms(), 2) if self.duration_ms() else None,
            "status": self.status.value,
            "tags": self.tags,
            "logs": self.logs,
        }

    def to_log_dict(self) -> Dict[str, Any]:
        """로그 출력용 축약 딕셔너리"""
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "operation": self.operation_name,
            "duration_ms": round(self.duration_ms(), 2) if self.duration_ms() else None,
            "status": self.status.value,
        }


def get_current_span() -> Optional[SpanContext]:
    """현재 활성 Span 반환"""
    return _current_span.get()


def set_current_span(span: Optional[SpanContext]) -> None:
    """현재 Span 설정"""
    _current_span.set(span)


class SpanContextManager:
    """
    SpanContext 컨텍스트 관리자

    자동으로 부모-자식 관계를 설정하고 trace_id를 전파합니다.
    """

    def __init__(
        self,
        operation_name: str,
        component: Optional[str] = None,
        **tags
    ):
        parent_span = get_current_span()

        # trace_id 전파: 부모 span이 있으면 같은 trace_id 사용
        trace_id = parent_span.trace_id if parent_span else (get_trace_id() or generate_trace_id())

        self.span = SpanContext(
            operation_name=operation_name,
            trace_id=trace_id,
            parent_span_id=parent_span.span_id if parent_span else None,
            component=component,
            tags=tags,
        )
        self.prev_span: Optional[SpanContext] = None
        self.prev_trace_id: str = ""

    def __enter__(self) -> SpanContext:
        self.prev_span = get_current_span()
        self.prev_trace_id = get_trace_id()

        set_current_span(self.span)
        set_trace_id(self.span.trace_id)

        return self.span

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.span.finish_with_error(exc_val)
        else:
            self.span.finish(SpanStatus.OK)

        set_current_span(self.prev_span)
        if self.prev_trace_id:
            set_trace_id(self.prev_trace_id)
        else:
            clear_trace_id()

        return False  # 예외 전파


def trace_operation(
    operation_name: str,
    component: Optional[str] = None,
    log_span: bool = True,
    **default_tags
):
    """
    함수 호출을 자동으로 추적하는 데코레이터

    Story 5.3: Distributed Tracing 구현
    T-5.3.3: @trace_operation 데코레이터 구현

    Args:
        operation_name: 작업 이름
        component: 컴포넌트 이름
        log_span: 완료 시 span 정보 로깅 여부
        **default_tags: 기본 태그

    Example:
        @trace_operation("process_order", component="TradingEngine")
        def process_order(order_id: str):
            ...
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            logger = get_context_logger(func.__module__)

            with SpanContextManager(
                operation_name=operation_name,
                component=component,
                **default_tags
            ) as span:
                span.set_tag("function", func.__name__)
                span.set_tag("module", func.__module__)

                try:
                    result = func(*args, **kwargs)
                    span.set_tag("success", True)

                    if log_span:
                        logger.debug(
                            f"Span completed: {operation_name}",
                            **span.to_log_dict()
                        )

                    return result

                except Exception as e:
                    span.set_tag("success", False)

                    if log_span:
                        logger.error(
                            f"Span failed: {operation_name}",
                            **span.to_log_dict(),
                            error_type=type(e).__name__,
                            error_message=str(e),
                        )
                    raise

        return wrapper
    return decorator


def trace_async_operation(
    operation_name: str,
    component: Optional[str] = None,
    log_span: bool = True,
    **default_tags
):
    """
    비동기 함수 호출을 자동으로 추적하는 데코레이터

    Args:
        operation_name: 작업 이름
        component: 컴포넌트 이름
        log_span: 완료 시 span 정보 로깅 여부
        **default_tags: 기본 태그

    Example:
        @trace_async_operation("fetch_market_data", component="DataManager")
        async def fetch_market_data(symbol: str):
            ...
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            logger = get_context_logger(func.__module__)

            with SpanContextManager(
                operation_name=operation_name,
                component=component,
                **default_tags
            ) as span:
                span.set_tag("function", func.__name__)
                span.set_tag("module", func.__module__)
                span.set_tag("async", True)

                try:
                    result = await func(*args, **kwargs)
                    span.set_tag("success", True)

                    if log_span:
                        logger.debug(
                            f"Async span completed: {operation_name}",
                            **span.to_log_dict()
                        )

                    return result

                except Exception as e:
                    span.set_tag("success", False)

                    if log_span:
                        logger.error(
                            f"Async span failed: {operation_name}",
                            **span.to_log_dict(),
                            error_type=type(e).__name__,
                            error_message=str(e),
                        )
                    raise

        return wrapper
    return decorator


class TracingContext:
    """
    전체 요청/작업에 대한 추적 컨텍스트

    HTTP 요청이나 배치 작업의 시작점에서 사용합니다.
    """

    def __init__(
        self,
        operation_name: str = "request",
        trace_id: Optional[str] = None,
        **tags
    ):
        self.operation_name = operation_name
        self.trace_id = trace_id or generate_trace_id()
        self.tags = tags
        self.root_span: Optional[SpanContext] = None
        self.prev_trace_id: str = ""

    def __enter__(self) -> 'TracingContext':
        self.prev_trace_id = get_trace_id()
        set_trace_id(self.trace_id)

        self.root_span = SpanContext(
            operation_name=self.operation_name,
            trace_id=self.trace_id,
            tags=self.tags,
        )
        set_current_span(self.root_span)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.root_span:
            if exc_type is not None:
                self.root_span.finish_with_error(exc_val)
            else:
                self.root_span.finish(SpanStatus.OK)

        set_current_span(None)

        if self.prev_trace_id:
            set_trace_id(self.prev_trace_id)
        else:
            clear_trace_id()

        return False

    def get_trace_id(self) -> str:
        """현재 trace_id 반환"""
        return self.trace_id

    def get_root_span(self) -> Optional[SpanContext]:
        """루트 span 반환"""
        return self.root_span 