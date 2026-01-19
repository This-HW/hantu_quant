"""
Centralized Log Manager

Provides unified logging configuration with:
- Structured JSON logging format
- Rotating file handlers
- Sensitive data filtering
- Context-aware logging

Usage:
    from core.logging import setup_logging, get_logger

    setup_logging(service_name='scheduler')
    logger = get_logger(__name__)
    logger.info("Service started")
"""

import os
import sys
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict
from logging.handlers import RotatingFileHandler


# Patterns for sensitive data masking
SENSITIVE_PATTERNS = [
    (re.compile(r'(app_?key|appkey)["\s:=]+["\']?([^"\'\s,}]+)', re.IGNORECASE), r'\1=***MASKED***'),
    (re.compile(r'(app_?secret|appsecret)["\s:=]+["\']?([^"\'\s,}]+)', re.IGNORECASE), r'\1=***MASKED***'),
    (re.compile(r'(token|access_token)["\s:=]+["\']?([^"\'\s,}]+)', re.IGNORECASE), r'\1=***MASKED***'),
    (re.compile(r'(password|passwd)["\s:=]+["\']?([^"\'\s,}]+)', re.IGNORECASE), r'\1=***MASKED***'),
    (re.compile(r'(secret)["\s:=]+["\']?([^"\'\s,}]+)', re.IGNORECASE), r'\1=***MASKED***'),
    (re.compile(r'(api_?key)["\s:=]+["\']?([^"\'\s,}]+)', re.IGNORECASE), r'\1=***MASKED***'),
    (re.compile(r'Bearer\s+[A-Za-z0-9\-_\.]+', re.IGNORECASE), 'Bearer ***MASKED***'),
]


class SensitiveDataFilter(logging.Filter):
    """Filter that masks sensitive data in log messages."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Mask sensitive data in the log message."""
        if hasattr(record, 'msg') and record.msg:
            message = str(record.msg)
            for pattern, replacement in SENSITIVE_PATTERNS:
                message = pattern.sub(replacement, message)
            record.msg = message

        if hasattr(record, 'args') and record.args:
            args = list(record.args)
            for i, arg in enumerate(args):
                if isinstance(arg, str):
                    for pattern, replacement in SENSITIVE_PATTERNS:
                        args[i] = pattern.sub(replacement, args[i])
            record.args = tuple(args)

        return True


class JSONFormatter(logging.Formatter):
    """
    JSON log formatter for structured logging.

    Produces log entries in JSON format with standard fields.
    """

    def __init__(self, service_name: str = 'hantu'):
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'service': self.service_name,
            'logger': record.name,
            'message': record.getMessage(),
        }

        # Add file location
        if record.pathname:
            log_data['location'] = {
                'file': os.path.basename(record.pathname),
                'line': record.lineno,
                'function': record.funcName,
            }

        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)

        # Add extra fields
        extra_fields = ['trace_id', 'user_id', 'stock_code', 'request_id']
        for field in extra_fields:
            if hasattr(record, field):
                log_data[field] = getattr(record, field)

        return json.dumps(log_data, ensure_ascii=False)


class ConsoleFormatter(logging.Formatter):
    """
    Human-readable console formatter with colors.
    """

    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
    }
    RESET = '\033[0m'

    def __init__(self, use_colors: bool = True):
        super().__init__(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        self.use_colors = use_colors and sys.stdout.isatty()

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with optional colors."""
        message = super().format(record)

        if self.use_colors:
            color = self.COLORS.get(record.levelname, '')
            if color:
                # Color only the level name
                message = message.replace(
                    record.levelname,
                    f'{color}{record.levelname}{self.RESET}'
                )

        return message


class LogManager:
    """
    Centralized log manager for all services.

    Provides consistent logging configuration across the application.
    """

    _instance: Optional['LogManager'] = None
    _initialized: bool = False

    # Default configuration
    DEFAULT_LOG_DIR = 'logs'
    DEFAULT_MAX_BYTES = 10 * 1024 * 1024  # 10MB
    DEFAULT_BACKUP_COUNT = 5

    def __new__(cls) -> 'LogManager':
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the log manager."""
        if self._initialized:
            return

        self._project_root = Path(__file__).parent.parent.parent
        self._log_dir = self._project_root / self.DEFAULT_LOG_DIR
        self._service_name = 'hantu'
        self._level = logging.INFO
        self._handlers: Dict[str, logging.Handler] = {}

        self._initialized = True

    def setup(
        self,
        service_name: str = 'hantu',
        level: str = 'INFO',
        log_dir: Optional[str] = None,
        json_format: bool = False,
        add_console: bool = True,
        add_file: bool = True,
    ) -> None:
        """
        Configure logging for a service.

        Args:
            service_name: Name of the service (used in log entries)
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_dir: Directory for log files (default: logs/)
            json_format: Use JSON format for file logs
            add_console: Add console handler
            add_file: Add file handler
        """
        self._service_name = service_name
        self._level = getattr(logging, level.upper(), logging.INFO)

        if log_dir:
            self._log_dir = Path(log_dir)

        # Ensure log directory exists
        self._log_dir.mkdir(parents=True, exist_ok=True)

        # Get root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(self._level)

        # Remove existing handlers
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        # Add sensitive data filter
        sensitive_filter = SensitiveDataFilter()

        # Console handler
        if add_console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(self._level)
            console_handler.setFormatter(ConsoleFormatter())
            console_handler.addFilter(sensitive_filter)
            root_logger.addHandler(console_handler)
            self._handlers['console'] = console_handler

        # File handler
        if add_file:
            log_file = self._log_dir / f"{datetime.now().strftime('%Y%m%d')}.log"

            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=self.DEFAULT_MAX_BYTES,
                backupCount=self.DEFAULT_BACKUP_COUNT,
                encoding='utf-8',
            )
            file_handler.setLevel(self._level)

            if json_format:
                file_handler.setFormatter(JSONFormatter(service_name))
            else:
                file_handler.setFormatter(logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                ))

            file_handler.addFilter(sensitive_filter)
            root_logger.addHandler(file_handler)
            self._handlers['file'] = file_handler

        logging.info(f"Logging configured for service '{service_name}' at level {level}")

    def get_logger(self, name: str) -> logging.Logger:
        """
        Get a logger with the given name.

        Args:
            name: Logger name (typically __name__)

        Returns:
            Configured logger instance
        """
        return logging.getLogger(name)


# Module-level convenience functions
_manager: Optional[LogManager] = None


def setup_logging(
    service_name: str = 'hantu',
    level: str = 'INFO',
    log_dir: Optional[str] = None,
    json_format: bool = False,
) -> LogManager:
    """
    Set up logging for a service.

    Args:
        service_name: Name of the service
        level: Log level
        log_dir: Directory for log files
        json_format: Use JSON format

    Returns:
        LogManager instance
    """
    global _manager
    _manager = LogManager()
    _manager.setup(
        service_name=service_name,
        level=level,
        log_dir=log_dir,
        json_format=json_format,
    )
    return _manager


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the given name.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Logger instance
    """
    global _manager
    if _manager is None:
        _manager = LogManager()
        _manager.setup()
    return _manager.get_logger(name)
