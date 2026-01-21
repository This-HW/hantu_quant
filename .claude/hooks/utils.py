#!/usr/bin/env python3
"""
Hooks 공통 유틸리티

여러 hook 스크립트에서 공통으로 사용하는 함수들을 모아놓은 모듈입니다.
"""

import os
import sys
import traceback
from pathlib import Path


# 상수
FORMATTER_TIMEOUT_SECONDS = 30
DEFAULT_SCRATCH_MAX_AGE_DAYS = 7


def get_project_root() -> str:
    """
    프로젝트 루트 디렉토리 찾기

    우선순위:
    1. CLAUDE_PROJECT_DIR 환경변수
    2. .git 폴더가 있는 상위 디렉토리
    3. 현재 디렉토리
    """
    # 환경변수에서
    if "CLAUDE_PROJECT_DIR" in os.environ:
        return os.environ["CLAUDE_PROJECT_DIR"]

    # 현재 디렉토리에서 .git 찾기
    cwd = os.getcwd()
    while cwd != "/":
        if os.path.exists(os.path.join(cwd, ".git")):
            return cwd
        cwd = os.path.dirname(cwd)

    return os.getcwd()


def is_debug_mode() -> bool:
    """디버그 모드 확인 (CLAUDE_HOOK_DEBUG 환경변수)"""
    return os.environ.get('CLAUDE_HOOK_DEBUG', '').lower() in ('1', 'true', 'yes')


def debug_log(message: str, error: Exception = None):
    """
    디버그 로그 출력

    CLAUDE_HOOK_DEBUG=1 환경변수가 설정된 경우에만 출력됩니다.
    """
    if not is_debug_mode():
        return

    print(f"[DEBUG] {message}", file=sys.stderr)
    if error:
        traceback.print_exc(file=sys.stderr)


def safe_path(file_path: str) -> bool:
    """
    경로 안전성 검사

    Path traversal 공격 방지를 위한 기본 검사
    """
    if not file_path:
        return False

    # Path traversal 방지
    if '..' in file_path:
        debug_log(f"Path traversal detected: {file_path}")
        return False

    return True


def format_size(size: int) -> str:
    """파일 크기를 읽기 쉬운 형식으로 변환"""
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"


def load_yaml_safe(file_path: str) -> dict:
    """
    YAML 파일 안전하게 로드

    PyYAML이 설치되지 않은 경우 빈 dict 반환
    """
    try:
        import yaml
        with open(file_path, 'r') as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        debug_log("PyYAML not installed, skipping YAML load")
        return {}
    except Exception as e:
        debug_log(f"YAML load error: {file_path}", e)
        return {}
