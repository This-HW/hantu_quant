#!/usr/bin/env python3
"""
프로젝트 보안 검사 스크립트.
환경변수, 파일 권한, API 키 등을 검증.
"""

import sys
import os
from pathlib import Path
import logging
import argparse
from typing import List, Tuple, Optional

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.utils.security_validator import SecurityValidator

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_git_security() -> Tuple[bool, List[str]]:
    """Git 관련 보안 검사"""
    warnings = []
    is_valid = True

    # .gitignore 확인
    gitignore = Path('.gitignore')
    if not gitignore.exists():
        warnings.append(".gitignore 파일이 없습니다!")
        is_valid = False
    else:
        content = gitignore.read_text()
        required_patterns = ['.env', '*.pem', '*.key', 'data/token/']
        missing = []

        for pattern in required_patterns:
            if pattern not in content:
                missing.append(pattern)

        if missing:
            warnings.append(f".gitignore에 다음 패턴이 누락되었습니다: {', '.join(missing)}")
            is_valid = False

    # 스테이징된 민감한 파일 확인
    import subprocess
    try:
        result = subprocess.run(
            ['git', 'diff', '--cached', '--name-only'],
            capture_output=True, text=True, check=False
        )

        if result.returncode == 0:
            staged_files = result.stdout.strip().split('\n')
            sensitive_patterns = ['.env', 'token', 'secret', 'key', 'password']

            for file in staged_files:
                if file and any(pattern in file.lower() for pattern in sensitive_patterns):
                    warnings.append(f"민감한 파일이 스테이징되어 있습니다: {file}")
                    is_valid = False
    except Exception:
        pass  # git이 설치되지 않은 경우 무시

    return is_valid, warnings


def check_file_permissions() -> Tuple[bool, List[str]]:
    """파일 권한 검사"""
    warnings = []
    is_valid = True

    # 민감한 파일 및 디렉토리 목록 (권장 권한 포함)
    sensitive_items = {
        # 파일: 권장 권한 600 (소유자만 읽기/쓰기)
        '.env': {'type': 'file', 'recommended': '600', 'allowed': ['600']},
        'config/telegram_config.json': {'type': 'file', 'recommended': '600', 'allowed': ['600']},

        # 디렉토리: 권장 권한 700 (소유자만 접근)
        'data/token': {'type': 'dir', 'recommended': '700', 'allowed': ['700']},
        'config': {'type': 'dir', 'recommended': '700', 'allowed': ['700', '755']},
        'data': {'type': 'dir', 'recommended': '700', 'allowed': ['700', '755']},
        'logs': {'type': 'dir', 'recommended': '700', 'allowed': ['700', '755']},
    }

    for file_path, settings in sensitive_items.items():
        path = Path(file_path)
        if path.exists():
            stat = path.stat()
            mode = oct(stat.st_mode)[-3:]

            if mode not in settings['allowed']:
                warnings.append(
                    f"{file_path} 권한이 너무 개방적입니다: {mode} "
                    f"(권장: {settings['recommended']})"
                )
                is_valid = False

    # 토큰 파일 개별 검사
    token_dir = Path('data/token')
    if token_dir.exists():
        for token_file in token_dir.glob('*.json'):
            stat = token_file.stat()
            mode = oct(stat.st_mode)[-3:]
            if mode not in ['600']:
                warnings.append(f"{token_file} 토큰 파일 권한이 너무 개방적입니다: {mode} (권장: 600)")
                is_valid = False

    return is_valid, warnings


def check_dependencies() -> Tuple[bool, List[str]]:
    """의존성 패키지 보안 검사"""
    warnings = []
    is_valid = True

    # requirements.txt 확인
    req_file = Path('requirements.txt')
    if req_file.exists():
        content = req_file.read_text()

        # 버전 고정 확인
        lines = content.strip().split('\n')
        for line in lines:
            if line and not line.startswith('#'):
                if '==' not in line and '>=' not in line:
                    warnings.append(f"버전이 고정되지 않은 패키지: {line}")

    return is_valid, warnings


def check_code_security() -> Tuple[bool, List[str]]:
    """코드 보안 검사"""
    import re
    warnings = []
    is_valid = True

    # 위험한 함수 사용 확인 (정규식 패턴으로 더 정밀하게 검사)
    dangerous_patterns = [
        (r'(?<!#.*)(?<!\w)eval\s*\(', 'eval() 함수 사용'),
        (r'(?<!#.*)(?<!\w)exec\s*\(', 'exec() 함수 사용'),
        (r'(?<!#.*)__import__\s*\(', '__import__ 사용'),
        (r'(?<!#.*)pickle\.loads\s*\(', 'pickle.loads 사용 (안전하지 않은 역직렬화)'),
        # shell=True가 주석이 아닌 곳에서 사용되는지 확인
        (r'^[^#]*shell\s*=\s*True', 'subprocess에서 shell=True 사용')
    ]

    py_files = list(Path('.').rglob('*.py'))
    for py_file in py_files[:50]:  # 처음 50개 파일만 검사 (성능 고려)
        # .venv, test 파일 제외
        file_str = str(py_file)
        if '.venv' in file_str or 'test' in file_str.lower():
            continue

        try:
            content = py_file.read_text(encoding='utf-8')
            lines = content.split('\n')

            for line_num, line in enumerate(lines, 1):
                # 주석 라인 건너뛰기
                stripped = line.strip()
                if stripped.startswith('#'):
                    continue

                for pattern, desc in dangerous_patterns:
                    if re.search(pattern, line, re.IGNORECASE):
                        warnings.append(f"{desc} 감지: {py_file}:{line_num}")
                        is_valid = False
        except Exception:
            pass

    return is_valid, warnings


def generate_security_report(output_file: Optional[str] = None):
    """보안 검사 보고서 생성"""
    logger.info("=" * 60)
    logger.info("프로젝트 보안 검사 시작")
    logger.info("=" * 60)

    all_valid = True
    report = []

    # 1. 환경 설정 검사
    logger.info("\n[1/5] 환경 설정 검사...")
    env_valid, env_warnings = SecurityValidator.validate_environment()
    all_valid &= env_valid
    report.append(("환경 설정", env_valid, env_warnings))

    # 2. API 키 검사
    logger.info("\n[2/5] API 키 검사...")
    app_key = os.getenv('APP_KEY')
    app_secret = os.getenv('APP_SECRET')
    key_valid, key_warnings = SecurityValidator.validate_api_keys(app_key, app_secret)
    all_valid &= key_valid
    report.append(("API 키", key_valid, key_warnings))

    # 3. Git 보안 검사
    logger.info("\n[3/5] Git 보안 검사...")
    git_valid, git_warnings = check_git_security()
    all_valid &= git_valid
    report.append(("Git 보안", git_valid, git_warnings))

    # 4. 파일 권한 검사
    logger.info("\n[4/5] 파일 권한 검사...")
    perm_valid, perm_warnings = check_file_permissions()
    all_valid &= perm_valid
    report.append(("파일 권한", perm_valid, perm_warnings))

    # 5. 코드 보안 검사
    logger.info("\n[5/5] 코드 보안 검사...")
    code_valid, code_warnings = check_code_security()
    all_valid &= code_valid
    report.append(("코드 보안", code_valid, code_warnings))

    # 결과 출력
    logger.info("\n" + "=" * 60)
    logger.info("검사 결과 요약")
    logger.info("=" * 60)

    for category, valid, warnings in report:
        status = "✅ 통과" if valid else "❌ 실패"
        logger.info(f"\n{category}: {status}")
        if warnings:
            for warning in warnings:
                logger.warning(f"  ⚠️  {warning}")

    logger.info("\n" + "=" * 60)
    if all_valid:
        logger.info("✅ 모든 보안 검사를 통과했습니다!")
    else:
        logger.error("❌ 보안 문제가 발견되었습니다. 위의 경고를 확인하세요.")

    # 보고서 파일 저장
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("프로젝트 보안 검사 보고서\n")
            f.write("=" * 60 + "\n\n")

            for category, valid, warnings in report:
                status = "통과" if valid else "실패"
                f.write(f"\n{category}: {status}\n")
                if warnings:
                    for warning in warnings:
                        f.write(f"  - {warning}\n")

            f.write("\n" + "=" * 60 + "\n")
            f.write(f"최종 결과: {'모든 검사 통과' if all_valid else '보안 문제 발견'}\n")

        logger.info(f"\n보고서가 {output_file}에 저장되었습니다.")

    return all_valid


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description='프로젝트 보안 검사')
    parser.add_argument(
        '--output', '-o',
        type=str,
        help='보고서 출력 파일 경로'
    )
    parser.add_argument(
        '--fix', '-f',
        action='store_true',
        help='자동으로 수정 가능한 문제 해결 시도'
    )

    args = parser.parse_args()

    if args.fix:
        logger.info("자동 수정 모드 활성화...")

        # 민감한 파일 권한 수정 (600)
        sensitive_files = ['.env', 'config/telegram_config.json']
        for file_path in sensitive_files:
            path = Path(file_path)
            if path.exists() and path.is_file():
                os.chmod(path, 0o600)
                logger.info(f"{file_path} 파일 권한을 600으로 변경했습니다.")

        # 민감한 디렉토리 권한 수정 (700)
        sensitive_dirs = ['data/token', 'config', 'data', 'logs']
        for dir_path in sensitive_dirs:
            path = Path(dir_path)
            if path.exists() and path.is_dir():
                os.chmod(path, 0o700)
                logger.info(f"{dir_path} 디렉토리 권한을 700으로 변경했습니다.")

        # 토큰 파일들 개별 권한 수정
        token_dir = Path('data/token')
        if token_dir.exists():
            for token_file in token_dir.glob('*.json'):
                os.chmod(token_file, 0o600)
                logger.info(f"{token_file} 토큰 파일 권한을 600으로 변경했습니다.")

    # 보안 검사 실행
    success = generate_security_report(args.output)

    # 종료 코드 반환
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()