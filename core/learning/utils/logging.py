"""
Phase 4: AI 학습 시스템 - 로깅 유틸리티
AI 학습 관련 로깅 기능 제공
"""

import logging
import os
from datetime import datetime
from typing import Optional

# 기존 로깅 시스템과 연동
try:
    from core.utils.log_utils import get_logger as get_base_logger
    from core.utils.log_utils import setup_logging
    BASE_LOGGER_AVAILABLE = True
except ImportError:
    BASE_LOGGER_AVAILABLE = False

# 학습 로그 디렉토리 설정
LEARNING_LOG_DIR = "logs/learning"
if not os.path.exists(LEARNING_LOG_DIR):
    os.makedirs(LEARNING_LOG_DIR, exist_ok=True)

# 학습 전용 로그 포맷
LEARNING_FORMAT = '[%(asctime)s] [LEARNING] [%(levelname)s] [%(name)s] %(message)s'
LEARNING_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'


def get_learning_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    AI 학습 시스템 전용 로거 생성
    
    Args:
        name: 로거 이름
        level: 로그 레벨
    
    Returns:
        logging.Logger: 설정된 로거 객체
    """
    # 기존 로깅 시스템 우선 사용
    if BASE_LOGGER_AVAILABLE:
        logger = get_base_logger(name)
        logger.info(f"Learning logger initialized for {name}")
        return logger
    
    # 독립적인 학습 로거 생성
    logger = logging.getLogger(f"learning.{name}")
    
    if not logger.handlers:
        # 콘솔 핸들러
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_formatter = logging.Formatter(LEARNING_FORMAT, LEARNING_DATE_FORMAT)
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
        
        # 파일 핸들러 (일일 로그)
        today = datetime.now().strftime('%Y-%m-%d')
        log_file = os.path.join(LEARNING_LOG_DIR, f"learning_{today}.log")
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(level)
        file_formatter = logging.Formatter(LEARNING_FORMAT, LEARNING_DATE_FORMAT)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
        
        logger.setLevel(level)
        logger.propagate = False
        
        logger.info(f"Independent learning logger initialized for {name}")
    
    return logger


def setup_learning_logging(level: int = logging.INFO) -> None:
    """
    학습 시스템 로깅 설정
    
    Args:
        level: 기본 로그 레벨
    """
    # 기존 로깅 시스템 설정 사용
    if BASE_LOGGER_AVAILABLE:
        setup_logging()
        logger = get_learning_logger(__name__)
        logger.info("Learning logging setup completed using base system")
    else:
        logger = get_learning_logger(__name__)
        logger.info("Learning logging setup completed with independent system")


def log_learning_event(event_type: str, message: str, 
                      module: str = "learning", 
                      extra_data: Optional[dict] = None) -> None:
    """
    학습 이벤트 로깅
    
    Args:
        event_type: 이벤트 타입 (train, predict, optimize, etc.)
        message: 로그 메시지
        module: 모듈 이름
        extra_data: 추가 데이터
    """
    logger = get_learning_logger(module)
    
    # 추가 데이터 포함 메시지 생성
    if extra_data:
        extra_str = " | ".join([f"{k}={v}" for k, v in extra_data.items()])
        full_message = f"[{event_type.upper()}] {message} | {extra_str}"
    else:
        full_message = f"[{event_type.upper()}] {message}"
    
    logger.info(full_message)


def log_performance_metrics(metrics: dict, module: str = "performance") -> None:
    """
    성능 지표 로깅
    
    Args:
        metrics: 성능 지표 딕셔너리
        module: 모듈 이름
    """
    logger = get_learning_logger(module)
    
    metrics_str = " | ".join([f"{k}={v}" for k, v in metrics.items()])
    logger.info(f"[METRICS] {metrics_str}") 