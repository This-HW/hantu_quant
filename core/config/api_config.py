"""
API configuration management module.
"""

import os
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict
import requests
from dotenv import load_dotenv

from . import settings

logger = logging.getLogger(__name__)

class APIConfig:
    """API 설정 관리 클래스 (싱글톤)"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """초기화"""
        if self._initialized:
            return
            
        # API 설정 로드
        self.app_key = settings.APP_KEY
        self.app_secret = settings.APP_SECRET
        self.account_number = settings.ACCOUNT_NUMBER
        self.account_prod_code = settings.ACCOUNT_PROD_CODE
        self.server = settings.SERVER
        
        # 서버 설정 (virtual: 모의투자, prod: 실제투자)
        if self.server == 'virtual':
            self.base_url = settings.VIRTUAL_URL
            self.ws_url = settings.SOCKET_VIRTUAL_URL
            self._token_file = settings.TOKEN_DIR / 'token_info_virtual.json'
            logger.info("[APIConfig] 모의투자 환경으로 설정되었습니다.")
        else:
            self.base_url = settings.PROD_URL
            self.ws_url = settings.SOCKET_PROD_URL
            self._token_file = settings.TOKEN_DIR / 'token_info_real.json'
            logger.info("[APIConfig] 실제투자 환경으로 설정되었습니다.")
        
        # 토큰 관련 변수
        self.access_token = None
        self.token_expired_at = None
        
        # 토큰 디렉토리 생성
        self._token_file.parent.mkdir(parents=True, exist_ok=True)
        
        # 초기화 완료
        self._initialized = True
        
        # 저장된 토큰 로드
        self._load_token()
        
    def _save_token(self) -> None:
        """토큰 정보 저장"""
        try:
            token_data = {
                'access_token': self.access_token,
                'expired_at': self.token_expired_at.isoformat() if self.token_expired_at else None
            }
            
            with open(self._token_file, 'w') as f:
                json.dump(token_data, f)
                
            logger.debug("[_save_token] 토큰 정보 저장 완료")
            
        except Exception as e:
            logger.error(f"[_save_token] 토큰 정보 저장 중 오류 발생: {str(e)}")
            
    def _load_token(self) -> None:
        """저장된 토큰 정보 로드"""
        try:
            if not self._token_file.exists():
                return
                
            with open(self._token_file, 'r') as f:
                token_data = json.load(f)
                
            self.access_token = token_data.get('access_token')
            expired_at = token_data.get('expired_at')
            
            if expired_at:
                self.token_expired_at = datetime.fromisoformat(expired_at)
                
            logger.debug("[_load_token] 토큰 정보 로드 완료")
            
        except Exception as e:
            logger.error(f"[_load_token] 토큰 정보 로드 중 오류 발생: {str(e)}")
            
    def get_headers(self, include_content_type: bool = True) -> Dict:
        """API 요청 헤더 생성
        
        Args:
            include_content_type: Content-Type 헤더 포함 여부
            
        Returns:
            Dict: 요청 헤더
        """
        headers = {
            'authorization': f'Bearer {self.access_token}' if self.access_token else '',
            'appkey': self.app_key,
            'appsecret': self.app_secret,
        }
        
        if include_content_type:
            headers['content-type'] = 'application/json; charset=utf-8'
            
        return headers
        
    def refresh_token(self, force: bool = False) -> bool:
        """토큰 갱신
        
        Args:
            force: 강제 갱신 여부
            
        Returns:
            bool: 갱신 성공 여부
        """
        try:
            # 토큰이 유효하고 강제 갱신이 아닌 경우
            if not force and self.validate_token():
                return True
                
            url = f"{self.base_url}/oauth2/tokenP"
            
            data = {
                "grant_type": "client_credentials",
                "appkey": self.app_key,
                "appsecret": self.app_secret
            }
            
            response = requests.post(url, json=data, timeout=settings.REQUEST_TIMEOUT)
            
            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data.get('access_token')
                expires_in = int(token_data.get('expires_in', 86400))  # 기본값 24시간
                self.token_expired_at = datetime.now() + timedelta(seconds=expires_in)
                
                # 토큰 정보 저장
                self._save_token()
                
                logger.info("[refresh_token] 토큰 갱신 성공")
                return True
            else:
                logger.error(f"[refresh_token] 토큰 갱신 실패 - 상태 코드: {response.status_code}")
                logger.error(f"[refresh_token] 에러 응답: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"[refresh_token] 토큰 갱신 중 오류 발생: {str(e)}")
            return False
            
    def validate_token(self) -> bool:
        """토큰 유효성 검사
        
        Returns:
            bool: 토큰 유효 여부
        """
        if not self.access_token or not self.token_expired_at:
            return False
            
        # 만료 10분 전부터는 갱신 필요
        if datetime.now() + timedelta(minutes=10) >= self.token_expired_at:
            return False
            
        return True
        
    def ensure_valid_token(self) -> bool:
        """토큰 유효성 보장
        
        Returns:
            bool: 토큰 유효 여부
        """
        if not self.validate_token():
            return self.refresh_token()
        return True
        
    def clear_token(self) -> None:
        """토큰 정보 초기화"""
        self.access_token = None
        self.token_expired_at = None
        
        if self._token_file.exists():
            self._token_file.unlink()
            
        logger.info("[clear_token] 토큰 정보 초기화 완료") 