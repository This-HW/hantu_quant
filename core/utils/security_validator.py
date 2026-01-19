"""
보안 설정 검증 유틸리티.
환경변수 및 API 키 보안 검증.
"""

import os
import re
import logging
from pathlib import Path
from typing import List, Tuple, Optional
import hashlib
import hmac

logger = logging.getLogger(__name__)


class SecurityValidator:
    """보안 설정 검증 클래스"""

    # 민감한 환경변수 패턴
    SENSITIVE_ENV_PATTERNS = [
        r'.*KEY.*',
        r'.*SECRET.*',
        r'.*TOKEN.*',
        r'.*PASSWORD.*',
        r'.*PASS.*',
        r'.*CREDENTIAL.*',
        r'.*API.*KEY.*'
    ]

    # 민감한 파일 패턴
    SENSITIVE_FILE_PATTERNS = [
        r'\.env$',
        r'\.env\..*',
        r'.*\.pem$',
        r'.*\.key$',
        r'.*\.cert$',
        r'.*\.crt$',
        r'.*token.*\.json$',
        r'.*config.*\.json$'
    ]

    @classmethod
    def validate_environment(cls) -> Tuple[bool, List[str]]:
        """
        환경 설정 검증.

        Returns:
            튜플 (검증 성공 여부, 경고 메시지 리스트)
        """
        warnings = []
        is_valid = True

        # 1. .env 파일 권한 확인
        env_file = Path('.env')
        if env_file.exists():
            stat = env_file.stat()
            mode = oct(stat.st_mode)[-3:]
            if mode != '600' and mode != '644':
                warnings.append(f".env 파일 권한이 너무 개방적입니다: {mode}")
                is_valid = False

        # 2. 필수 환경변수 확인
        required_vars = ['APP_KEY', 'APP_SECRET', 'ACCOUNT_NUMBER']
        missing_vars = []

        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)

        if missing_vars:
            warnings.append(f"필수 환경변수가 설정되지 않았습니다: {', '.join(missing_vars)}")
            is_valid = False

        # 3. 민감한 정보가 코드에 하드코딩되어 있는지 확인
        hardcoded_patterns = cls._check_hardcoded_secrets()
        if hardcoded_patterns:
            warnings.extend(hardcoded_patterns)
            is_valid = False

        # 4. SERVER 환경변수 확인
        server = os.getenv('SERVER', 'virtual')
        if server not in ['virtual', 'prod']:
            warnings.append(f"잘못된 SERVER 환경변수 값: {server}")
            is_valid = False
        elif server == 'prod':
            warnings.append("실제 투자 환경이 활성화되어 있습니다. 주의하세요!")

        return is_valid, warnings

    @classmethod
    def _check_hardcoded_secrets(cls) -> List[str]:
        """하드코딩된 비밀정보 확인"""
        warnings = []
        patterns = [
            re.compile(r'APP_KEY\s*=\s*["\'][^"\']+["\']'),
            re.compile(r'APP_SECRET\s*=\s*["\'][^"\']+["\']'),
            re.compile(r'TOKEN\s*=\s*["\'][^"\']+["\']'),
            re.compile(r'PASSWORD\s*=\s*["\'][^"\']+["\']')
        ]

        # 제외할 디렉토리/파일 패턴
        exclude_patterns = [
            '.venv', 'venv', '__pycache__', 'node_modules',
            'test', 'example', '.git', 'dist', 'build'
        ]

        # Python 파일 검사 (테스트, 예제, 가상환경 제외)
        for py_file in Path('.').rglob('*.py'):
            file_str = str(py_file).lower()

            # 제외 패턴 확인
            if any(pattern in file_str for pattern in exclude_patterns):
                continue

            try:
                content = py_file.read_text(encoding='utf-8')
                for pattern in patterns:
                    if pattern.search(content):
                        warnings.append(f"하드코딩된 비밀정보 감지: {py_file}")
                        break
            except Exception:
                pass

        return warnings

    @classmethod
    def mask_sensitive_value(cls, value: str, visible_chars: int = 6) -> str:
        """
        민감한 값을 마스킹.

        Args:
            value: 마스킹할 값
            visible_chars: 표시할 문자 수

        Returns:
            마스킹된 문자열
        """
        if not value:
            return ""

        if len(value) <= visible_chars:
            return "*" * len(value)

        return value[:visible_chars] + "..." + "*" * min(10, len(value) - visible_chars)

    @classmethod
    def validate_api_keys(cls, app_key: Optional[str], app_secret: Optional[str]) -> Tuple[bool, List[str]]:
        """
        API 키 검증.

        Args:
            app_key: 앱 키
            app_secret: 앱 시크릿

        Returns:
            튜플 (유효성, 경고 메시지)
        """
        warnings = []
        is_valid = True

        # 키 존재 여부
        if not app_key:
            warnings.append("APP_KEY가 설정되지 않았습니다")
            is_valid = False
        elif len(app_key) < 20:
            warnings.append("APP_KEY가 너무 짧습니다")
            is_valid = False

        if not app_secret:
            warnings.append("APP_SECRET이 설정되지 않았습니다")
            is_valid = False
        elif len(app_secret) < 50:
            warnings.append("APP_SECRET이 너무 짧습니다")
            is_valid = False

        # 테스트/예제 키 확인
        test_patterns = ['test', 'example', 'demo', 'your_']
        if app_key:
            for pattern in test_patterns:
                if pattern.lower() in app_key.lower():
                    warnings.append("테스트/예제 APP_KEY가 사용 중입니다")
                    is_valid = False
                    break

        if app_secret:
            for pattern in test_patterns:
                if pattern.lower() in app_secret.lower():
                    warnings.append("테스트/예제 APP_SECRET이 사용 중입니다")
                    is_valid = False
                    break

        return is_valid, warnings

    @classmethod
    def generate_secure_hash(cls, data: str, salt: str = "") -> str:
        """
        보안 해시 생성.

        Args:
            data: 해시할 데이터
            salt: 솔트 값

        Returns:
            해시 문자열
        """
        return hashlib.sha256((data + salt).encode()).hexdigest()

    @classmethod
    def verify_hmac(cls, data: str, signature: str, key: str) -> bool:
        """
        HMAC 검증.

        Args:
            data: 검증할 데이터
            signature: 서명
            key: 키

        Returns:
            검증 성공 여부
        """
        expected = hmac.new(key.encode(), data.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    @classmethod
    def check_file_permissions(cls, file_path: Path) -> Tuple[bool, Optional[str]]:
        """
        파일 권한 확인.

        Args:
            file_path: 확인할 파일 경로

        Returns:
            튜플 (안전 여부, 경고 메시지)
        """
        if not file_path.exists():
            return True, None

        stat = file_path.stat()
        mode = oct(stat.st_mode)[-3:]

        # 민감한 파일인지 확인
        is_sensitive = any(
            re.match(pattern, str(file_path))
            for pattern in cls.SENSITIVE_FILE_PATTERNS
        )

        if is_sensitive:
            # 민감한 파일은 소유자만 읽기/쓰기 가능해야 함
            if mode not in ['600', '644']:
                return False, f"민감한 파일 {file_path}의 권한이 너무 개방적입니다: {mode}"

        return True, None

    @classmethod
    def sanitize_log_message(cls, message: str) -> str:
        """
        로그 메시지에서 민감한 정보 제거.

        Args:
            message: 원본 메시지

        Returns:
            정제된 메시지
        """
        # API 키 패턴
        patterns = [
            (r'APP_KEY["\']?\s*[:=]\s*["\']?([^"\'\s]+)', 'APP_KEY=***'),
            (r'APP_SECRET["\']?\s*[:=]\s*["\']?([^"\'\s]+)', 'APP_SECRET=***'),
            (r'TOKEN["\']?\s*[:=]\s*["\']?([^"\'\s]+)', 'TOKEN=***'),
            (r'PASSWORD["\']?\s*[:=]\s*["\']?([^"\'\s]+)', 'PASSWORD=***'),
            (r'\b[A-Za-z0-9]{40,}\b', '***REDACTED***')  # 긴 토큰/키
        ]

        result = message
        for pattern, replacement in patterns:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

        return result


def run_security_check() -> bool:
    """
    보안 검사 실행.

    Returns:
        모든 검사 통과 여부
    """
    logger.info("보안 검증 시작...")

    # 환경 검증
    env_valid, env_warnings = SecurityValidator.validate_environment()

    if env_warnings:
        for warning in env_warnings:
            logger.warning(f"⚠️  {warning}")

    # API 키 검증
    app_key = os.getenv('APP_KEY')
    app_secret = os.getenv('APP_SECRET')

    key_valid, key_warnings = SecurityValidator.validate_api_keys(app_key, app_secret)

    if key_warnings:
        for warning in key_warnings:
            logger.warning(f"⚠️  {warning}")

    # 파일 권한 검사
    sensitive_files = [
        Path('.env'),
        Path('data/token'),
        Path('config')
    ]

    file_warnings = []
    for file_path in sensitive_files:
        if file_path.exists():
            safe, warning = SecurityValidator.check_file_permissions(file_path)
            if warning:
                file_warnings.append(warning)

    if file_warnings:
        for warning in file_warnings:
            logger.warning(f"⚠️  {warning}")

    all_valid = env_valid and key_valid and not file_warnings

    if all_valid:
        logger.info("✅ 모든 보안 검사를 통과했습니다.")
    else:
        logger.error("❌ 보안 검사에서 문제가 발견되었습니다.")

    return all_valid


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    success = run_security_check()
    exit(0 if success else 1)