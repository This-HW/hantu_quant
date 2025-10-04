"""Utility facade for logging functions.

통합 로깅 진입점은 log_utils 모듈로 일원화합니다.
기존 from core.utils import get_logger, setup_logger 형태를 유지하기 위해
이곳에서 log_utils를 재노출합니다.
"""

from .log_utils import get_logger, setup_logging as setup_logger  # backward-compat alias

__all__ = [
    'get_logger',
    'setup_logger',
]