"""
Logging configuration module.
"""

import logging
import logging.handlers
from pathlib import Path
from typing import Optional
from datetime import datetime

from core.config import settings

def setup_logger(name: Optional[str] = None) -> logging.Logger:
    """로거 설정
    
    Args:
        name: 로거 이름 (기본값: None, 루트 로거 사용)
        
    Returns:
        logging.Logger: 설정된 로거
    """
    logger = logging.getLogger(name)
    
    # 이미 핸들러가 설정되어 있다면 스킵
    if logger.handlers:
        return logger
        
    logger.setLevel(settings.LOG_LEVEL)
    
    # 로그 파일명에 날짜 추가
    today = datetime.now().strftime('%Y%m%d')
    log_file = settings.LOG_DIR / f'{today}.log'
    
    # 파일 핸들러 설정
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=30,
        encoding='utf-8'
    )
    file_handler.setFormatter(logging.Formatter(settings.LOG_FORMAT))
    
    # 콘솔 핸들러 설정
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter('%(message)s'))
    
    # 핸들러 추가
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

def get_logger(name: Optional[str] = None) -> logging.Logger:
    """로거 가져오기
    
    Args:
        name: 로거 이름 (기본값: None, 루트 로거 사용)
        
    Returns:
        logging.Logger: 설정된 로거
    """
    return setup_logger(name) 