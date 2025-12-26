"""
로깅 유틸리티 모듈 (P2-2)

기능:
- 민감한 정보 마스킹
- JSON 형식 구조화 로깅
- 일별 로그 로테이션 (30일 보관)
- 요청 추적용 trace_id
"""

import logging
import logging.handlers
import json
import re
import uuid
import threading
from datetime import datetime
from typing import Dict, List, Any, Optional
from contextvars import ContextVar

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
            msg = re.sub(pattern1, fr'"\1": "***MASKED***"', msg, flags=re.IGNORECASE)
            
            # 변수 할당 패턴 (예: access_token=abcdefg)
            pattern2 = fr'({field})\s*=\s*["\']?([^"\'\s,\)]+)'
            msg = re.sub(pattern2, fr'\1=***MASKED***', msg, flags=re.IGNORECASE)
            
        return msg
        
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
    
    # 민감 정보 필터 적용
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
        log_data = {
            'timestamp': datetime.now().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'message': record.getMessage(),
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
    backup_count: int = 30,
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

    # 민감 정보 필터 적용
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