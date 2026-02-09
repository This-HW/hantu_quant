"""
보안 강화된 설정 관리 모듈.
환경변수를 안전하게 로드하고 검증.
"""

import os
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from dotenv import load_dotenv
import hashlib
from datetime import datetime

from core.utils.log_utils import get_logger

logger = get_logger(__name__)


class SecureConfig:
    """보안 강화된 설정 관리 클래스"""

    def __init__(self, env_file: Optional[str] = None):
        """
        초기화.

        Args:
            env_file: .env 파일 경로
        """
        self.env_file = env_file or '.env'
        self._config_cache: Dict[str, Any] = {}
        self._load_timestamp: Optional[datetime] = None
        self._config_hash: Optional[str] = None

        # .env 파일 로드
        self._load_env_file()

        # 설정 검증
        self._validate_config()

    def _load_env_file(self):
        """환경 파일 안전하게 로드"""
        env_path = Path(self.env_file)

        if not env_path.exists():
            logger.warning(f".env 파일이 존재하지 않습니다: {env_path}")
            return

        # 파일 권한 확인
        stat = env_path.stat()
        mode = oct(stat.st_mode)[-3:]
        if mode not in ['600', '644']:
            logger.warning(f".env 파일 권한이 너무 개방적입니다: {mode}. 600 또는 644로 변경하세요.")

        # .env 파일 로드
        load_dotenv(self.env_file)
        self._load_timestamp = datetime.now()

        # 설정 해시 생성 (변경 감지용)
        content = env_path.read_text()
        self._config_hash = hashlib.sha256(content.encode()).hexdigest()

    def _validate_config(self):
        """설정 검증"""
        required_vars = {
            'APP_KEY': 'API 앱 키',
            'APP_SECRET': 'API 시크릿 키',
            'ACCOUNT_NUMBER': '계좌번호'
        }

        missing = []
        for var, desc in required_vars.items():
            if not os.getenv(var):
                missing.append(f"{desc} ({var})")

        if missing:
            raise ValueError(f"필수 환경변수가 설정되지 않았습니다: {', '.join(missing)}")

        # SERVER 환경변수 검증
        server = os.getenv('SERVER', 'virtual')
        if server not in ['virtual', 'prod']:
            raise ValueError(f"잘못된 SERVER 값: {server}. 'virtual' 또는 'prod'만 허용됩니다.")

        if server == 'prod':
            logger.warning("실제 투자 환경으로 설정되어 있습니다. 주의하세요!")

    def get(self, key: str, default: Any = None, mask_log: bool = False) -> Any:
        """
        설정 값 가져오기.

        Args:
            key: 환경변수 키
            default: 기본값
            mask_log: 로그에서 마스킹 여부

        Returns:
            설정 값
        """
        # 캐시 확인
        if key in self._config_cache:
            return self._config_cache[key]

        # 환경변수에서 가져오기
        value = os.getenv(key, default)

        # 캐시 저장
        self._config_cache[key] = value

        # 로깅 (민감한 정보는 마스킹)
        if mask_log and value:
            masked = self._mask_sensitive(str(value))
            logger.debug(f"설정 로드: {key}={masked}")
        else:
            logger.debug(f"설정 로드: {key}")

        return value

    def get_secure(self, key: str, default: Any = None) -> Any:
        """
        보안 설정 값 가져오기 (항상 마스킹).

        Args:
            key: 환경변수 키
            default: 기본값

        Returns:
            설정 값
        """
        return self.get(key, default, mask_log=True)

    def _mask_sensitive(self, value: str, visible_chars: int = 6) -> str:
        """민감한 정보 마스킹"""
        if len(value) <= visible_chars:
            return "*" * len(value)

        return value[:visible_chars] + "..." + "*" * min(10, len(value) - visible_chars)

    @property
    def is_production(self) -> bool:
        """실제 투자 환경인지 확인"""
        return self.get('SERVER') == 'prod'

    @property
    def is_virtual(self) -> bool:
        """모의 투자 환경인지 확인"""
        return self.get('SERVER') == 'virtual'

    def get_api_config(self) -> Dict[str, str]:
        """API 설정 반환 (마스킹된 버전)"""
        return {
            'app_key': self.get_secure('APP_KEY'),
            'app_secret': self.get_secure('APP_SECRET'),
            'account_number': self.get('ACCOUNT_NUMBER'),
            'account_prod_code': self.get('ACCOUNT_PROD_CODE', '01'),
            'server': self.get('SERVER', 'virtual')
        }

    def verify_integrity(self) -> bool:
        """설정 파일 무결성 검증"""
        env_path = Path(self.env_file)
        if not env_path.exists():
            return False

        current_content = env_path.read_text()
        current_hash = hashlib.sha256(current_content.encode()).hexdigest()

        if current_hash != self._config_hash:
            logger.warning("설정 파일이 변경되었습니다. 재로드가 필요할 수 있습니다.")
            return False

        return True

    def reload(self):
        """설정 다시 로드"""
        logger.info("설정을 다시 로드합니다...")
        self._config_cache.clear()
        self._load_env_file()
        self._validate_config()

    def clear_cache(self):
        """캐시 초기화"""
        self._config_cache.clear()

    def get_safe_dict(self) -> Dict[str, Any]:
        """안전한 설정 딕셔너리 반환 (민감한 정보 마스킹)"""
        sensitive_keys = ['APP_KEY', 'APP_SECRET', 'TOKEN', 'PASSWORD']
        result = {}

        for key in os.environ:
            value = os.environ[key]
            if any(sensitive in key.upper() for sensitive in sensitive_keys):
                result[key] = self._mask_sensitive(value)
            else:
                result[key] = value

        return result

    def export_safe_config(self, output_file: str):
        """안전한 설정 내보내기 (민감한 정보 제외)"""
        safe_config = {
            'server': self.get('SERVER'),
            'log_level': self.get('LOG_LEVEL', 'INFO'),
            'account_prod_code': self.get('ACCOUNT_PROD_CODE', '01'),
            'config_timestamp': self._load_timestamp.isoformat() if self._load_timestamp else None,
            'is_production': self.is_production
        }

        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(safe_config, f, indent=2, ensure_ascii=False)

        logger.info(f"안전한 설정을 {output_file}에 내보냈습니다.")


# 전역 인스턴스
_secure_config: Optional[SecureConfig] = None


def get_secure_config() -> SecureConfig:
    """보안 설정 인스턴스 가져오기"""
    global _secure_config
    if _secure_config is None:
        _secure_config = SecureConfig()
    return _secure_config


def reload_config():
    """설정 다시 로드"""
    global _secure_config
    if _secure_config:
        _secure_config.reload()
    else:
        _secure_config = SecureConfig()


if __name__ == "__main__":
    # 테스트
    logging.basicConfig(level=logging.INFO)

    config = get_secure_config()

    print("\n=== 보안 설정 테스트 ===")
    print(f"환경: {config.get('SERVER')}")
    print(f"실제 투자: {config.is_production}")
    print(f"모의 투자: {config.is_virtual}")

    print("\n=== API 설정 (마스킹) ===")
    api_config = config.get_api_config()
    for key, value in api_config.items():
        print(f"{key}: {value}")

    print("\n=== 무결성 검증 ===")
    print(f"무결성 검증: {'통과' if config.verify_integrity() else '실패'}")