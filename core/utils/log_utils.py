"""
로깅 유틸리티 모듈.
민감한 정보가 로그에 노출되지 않도록 마스킹 기능 제공.
"""

import logging
import re
from typing import Dict, List, Any, Optional

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