"""
통합 로깅 설정 모듈

Feature 2.1: 로깅 아키텍처 통합
- T-2.1.1: 통합 로깅 설정 파일
- T-2.1.2: 중앙 설정 사용
- T-2.1.3: 로그 디렉토리 구조 통일
- T-2.1.4: 로테이션 적용 확인
"""

import os
import logging
import logging.config
import logging.handlers
from pathlib import Path
from typing import Optional, Dict, Any

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


# 기본 설정 경로
DEFAULT_CONFIG_PATH = "config/logging_config.yaml"

# 기본 로그 디렉토리
DEFAULT_LOG_DIRS = {
    "app": "logs/app",
    "trade": "logs/trade",
    "system": "logs/system",
    "error": "logs/error",
}


def ensure_log_directories(directories: Optional[Dict[str, str]] = None) -> None:
    """
    로그 디렉토리 생성

    Args:
        directories: 디렉토리 매핑 (없으면 기본값 사용)
    """
    dirs = directories or DEFAULT_LOG_DIRS

    for name, path in dirs.items():
        Path(path).mkdir(parents=True, exist_ok=True)


def load_yaml_config(config_path: str) -> Optional[Dict[str, Any]]:
    """
    YAML 설정 파일 로드

    Args:
        config_path: 설정 파일 경로

    Returns:
        설정 딕셔너리 또는 None
    """
    if not HAS_YAML:
        return None

    if not os.path.exists(config_path):
        return None

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception:
        return None


def get_default_config() -> Dict[str, Any]:
    """
    기본 로깅 설정 반환

    Returns:
        logging.config.dictConfig 형식의 설정
    """
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "detailed": {
                "format": "%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "filters": {
            "sensitive_data": {
                "()": "core.utils.log_utils.SensitiveDataFilter",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": "INFO",
                "formatter": "standard",
                "stream": "ext://sys.stdout",
                "filters": ["sensitive_data"],
            },
            "app_file": {
                "class": "logging.handlers.TimedRotatingFileHandler",
                "level": "DEBUG",
                "formatter": "detailed",
                "filename": "logs/app/app.log",
                "when": "midnight",
                "interval": 1,
                "backupCount": 30,
                "encoding": "utf-8",
                "filters": ["sensitive_data"],
            },
            "error_file": {
                "class": "logging.handlers.TimedRotatingFileHandler",
                "level": "ERROR",
                "formatter": "detailed",
                "filename": "logs/error/error.log",
                "when": "midnight",
                "interval": 1,
                "backupCount": 60,
                "encoding": "utf-8",
                "filters": ["sensitive_data"],
            },
        },
        "loggers": {
            "": {  # root logger
                "level": "INFO",
                "handlers": ["console", "app_file", "error_file"],
            },
            "core.trading": {
                "level": "DEBUG",
                "handlers": ["app_file", "error_file"],
                "propagate": False,
            },
            "core.notification": {
                "level": "INFO",
                "handlers": ["app_file", "error_file"],
                "propagate": False,
            },
        },
    }


def convert_yaml_to_dictconfig(yaml_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    YAML 설정을 dictConfig 형식으로 변환

    Args:
        yaml_config: YAML에서 로드한 설정

    Returns:
        dictConfig 형식의 설정
    """
    # 기본 구조
    config = {
        "version": yaml_config.get("version", 1),
        "disable_existing_loggers": yaml_config.get("disable_existing_loggers", False),
    }

    # 포맷터 변환
    if "formatters" in yaml_config:
        config["formatters"] = {}
        for name, fmt_config in yaml_config["formatters"].items():
            if isinstance(fmt_config, dict):
                config["formatters"][name] = fmt_config
            else:
                config["formatters"][name] = {"format": fmt_config}

    # 필터 변환
    if "filters" in yaml_config:
        config["filters"] = {}
        for name, flt_config in yaml_config["filters"].items():
            if isinstance(flt_config, dict) and "class" in flt_config:
                config["filters"][name] = {"()": flt_config["class"]}
            else:
                config["filters"][name] = flt_config

    # 핸들러 변환
    if "handlers" in yaml_config:
        config["handlers"] = yaml_config["handlers"]

    # 로거 변환
    if "loggers" in yaml_config:
        config["loggers"] = {}
        for name, logger_config in yaml_config["loggers"].items():
            if name == "root":
                config["root"] = logger_config
            else:
                config["loggers"][name] = logger_config

    return config


def setup_logging(
    config_path: Optional[str] = None,
    level: Optional[str] = None,
    force_console: bool = False,
) -> bool:
    """
    통합 로깅 설정

    Args:
        config_path: 설정 파일 경로 (None이면 기본 경로)
        level: 로그 레벨 오버라이드
        force_console: 콘솔 전용 모드

    Returns:
        설정 성공 여부
    """
    # 로그 디렉토리 생성
    ensure_log_directories()

    # 설정 로드
    config_path = config_path or DEFAULT_CONFIG_PATH
    yaml_config = load_yaml_config(config_path)

    if yaml_config:
        try:
            config = convert_yaml_to_dictconfig(yaml_config)
        except Exception:
            config = get_default_config()
    else:
        config = get_default_config()

    # 레벨 오버라이드
    if level:
        if "root" in config:
            config["root"]["level"] = level
        elif "" in config.get("loggers", {}):
            config["loggers"][""]["level"] = level

    # 콘솔 전용 모드
    if force_console:
        config["handlers"] = {
            "console": config.get("handlers", {}).get("console", {
                "class": "logging.StreamHandler",
                "level": "DEBUG",
                "stream": "ext://sys.stdout",
            })
        }
        if "root" in config:
            config["root"]["handlers"] = ["console"]
        for logger_config in config.get("loggers", {}).values():
            logger_config["handlers"] = ["console"]

    try:
        logging.config.dictConfig(config)
        return True
    except Exception as e:
        # 기본 설정으로 폴백
        logging.basicConfig(
            level=level or "INFO",
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        )
        logging.warning(f"Failed to apply logging config, using basic config: {e}")
        return False


def get_logger(name: str) -> logging.Logger:
    """
    로거 가져오기

    Args:
        name: 로거 이름

    Returns:
        logging.Logger 인스턴스
    """
    return logging.getLogger(name)


def set_log_level(logger_name: str, level: str) -> None:
    """
    특정 로거의 레벨 변경

    Args:
        logger_name: 로거 이름 (빈 문자열이면 루트)
        level: 로그 레벨
    """
    logger = logging.getLogger(logger_name)
    logger.setLevel(level.upper())


def add_file_handler(
    logger_name: str,
    filename: str,
    level: str = "DEBUG",
    rotate: bool = True,
    backup_count: int = 30,
) -> logging.Handler:
    """
    파일 핸들러 추가

    Args:
        logger_name: 로거 이름
        filename: 로그 파일 경로
        level: 로그 레벨
        rotate: 로테이션 여부
        backup_count: 보관 일수

    Returns:
        추가된 핸들러
    """
    # 디렉토리 생성
    Path(filename).parent.mkdir(parents=True, exist_ok=True)

    if rotate:
        handler = logging.handlers.TimedRotatingFileHandler(
            filename=filename,
            when="midnight",
            interval=1,
            backupCount=backup_count,
            encoding="utf-8",
        )
    else:
        handler = logging.FileHandler(filename, encoding="utf-8")

    handler.setLevel(level.upper())
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))

    logger = logging.getLogger(logger_name)
    logger.addHandler(handler)

    return handler


# 모듈 로드 시 기본 설정 적용 (선택적)
_initialized = False


def initialize_logging_once() -> None:
    """로깅 초기화 (한 번만)"""
    global _initialized
    if not _initialized:
        setup_logging()
        _initialized = True
