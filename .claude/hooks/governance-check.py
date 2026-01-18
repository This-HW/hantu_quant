#!/usr/bin/env python3
"""
PostToolUse Hook: 파일/문서 거버넌스 검증

Write 또는 Edit 도구 사용 후 파일 위치가 프로젝트 구조 규칙을 준수하는지 검증합니다.

기능:
1. 문서(.md) 파일 위치 검증
2. 소스 코드 레이어 규칙 검증
3. 금지된 파일명 패턴 검사
4. 임시 테스트 파일 경고

설정 파일:
- .claude/project-structure.yaml (프로젝트별)
- 없으면 기본 규칙 적용
"""

import json
import sys
import os
import re
import fnmatch
from pathlib import Path
from datetime import datetime

# 공통 유틸리티 import (스크립트 위치 기반 동적 경로)
hook_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, hook_dir)
try:
    from utils import get_project_root, debug_log, load_yaml_safe
except ImportError:
    def debug_log(msg, error=None): pass
    def load_yaml_safe(path): return {}
    # get_project_root는 아래에 로컬 정의 유지

# =============================================================================
# 기본 규칙 (project-structure.yaml 없을 때 적용)
# =============================================================================

DEFAULT_RULES = {
    # 문서 위치 규칙
    "docs": {
        "root": "docs/",
        "root_allowed": ["README.md", "CHANGELOG.md", "CONTRIBUTING.md", "LICENSE", "CODE_OF_CONDUCT.md", "CLAUDE.md"],
        "forbidden_patterns": ["src/**/*.md", "**/notes.md", "**/temp*.md", "**/*.txt"],
        "categories": {
            "architecture": "docs/architecture/",
            "api": "docs/api/",
            "guides": "docs/guides/",
            "references": "docs/references/",
            "decisions": "docs/decisions/",
        }
    },
    # 소스 코드 규칙
    "source": {
        "root": "src/",
        "allowed_top_level": ["app", "pages", "widgets", "features", "entities", "shared", "infrastructure"],
    },
    # 테스트 규칙
    "tests": {
        "root": "tests/",
        "scratch_path": "tests/scratch/",
        "scratch_max_age_days": 7,
    },
    # 금지 파일명 패턴
    "forbidden_names": ["temp*", "backup*", "*_old", "*_copy", "*.bak", "test_*"],
}


def load_project_rules(project_root: str) -> dict:
    """프로젝트 규칙 로드 (.claude/project-structure.yaml)"""
    config_path = os.path.join(project_root, ".claude", "project-structure.yaml")

    if os.path.exists(config_path):
        rules = load_yaml_safe(config_path)
        if rules:
            debug_log(f"Loaded project rules from {config_path}")
            return rules

    debug_log("Using default rules")
    return DEFAULT_RULES


def _get_project_root_local() -> str:
    """프로젝트 루트 찾기 (로컬 fallback)"""
    if "CLAUDE_PROJECT_DIR" in os.environ:
        return os.environ["CLAUDE_PROJECT_DIR"]

    cwd = os.getcwd()
    while cwd != "/":
        if os.path.exists(os.path.join(cwd, ".git")):
            return cwd
        cwd = os.path.dirname(cwd)

    return os.getcwd()


# utils.py가 없을 때 로컬 함수 사용
try:
    from utils import get_project_root
except ImportError:
    get_project_root = _get_project_root_local


def is_pattern_match(path: str, pattern: str) -> bool:
    """glob 패턴 매칭"""
    # ** 패턴 처리
    if "**" in pattern:
        regex = pattern.replace(".", r"\.").replace("**", ".*").replace("*", "[^/]*")
        return bool(re.match(regex, path))
    return fnmatch.fnmatch(path, pattern)


def check_forbidden_patterns(file_path: str, rules: dict) -> tuple[bool, str]:
    """금지된 파일명 패턴 검사"""
    filename = os.path.basename(file_path)

    # 금지 파일명 검사
    for pattern in rules.get("forbidden_names", []):
        if is_pattern_match(filename, pattern):
            return False, f"금지된 파일명 패턴: {pattern}"

    return True, ""


def check_doc_location(file_path: str, rules: dict, project_root: str) -> tuple[bool, str]:
    """문서 파일 위치 검증"""
    if not file_path.endswith(".md"):
        return True, ""

    rel_path = os.path.relpath(file_path, project_root)

    # 에이전트 정의 파일은 예외 (agents/ 폴더)
    if rel_path.startswith("agents/") or "/agents/" in rel_path:
        return True, ""

    # ~/.claude/agents/ 경로도 예외
    if "/.claude/agents/" in file_path or file_path.startswith(os.path.expanduser("~/.claude/agents/")):
        return True, ""
    doc_rules = rules.get("docs", DEFAULT_RULES["docs"])

    # 루트 허용 문서 체크
    if "/" not in rel_path:
        if rel_path in doc_rules.get("root_allowed", []):
            return True, ""
        else:
            return False, f"루트에 허용되지 않는 문서입니다. 허용: {doc_rules.get('root_allowed', [])}"

    # 금지 패턴 체크
    for pattern in doc_rules.get("forbidden_patterns", []):
        if is_pattern_match(rel_path, pattern):
            return False, f"금지된 위치입니다: {pattern}"

    # docs/ 폴더 내 문서는 OK
    if rel_path.startswith(doc_rules.get("root", "docs/")):
        return True, ""

    # 그 외 위치는 경고
    categories = doc_rules.get("categories", {})
    suggestion = "\n".join([f"  - {k}: {v}" for k, v in categories.items()])
    return False, f"문서는 docs/ 폴더에 위치해야 합니다.\n올바른 위치:\n{suggestion}"


def check_source_location(file_path: str, rules: dict, project_root: str) -> tuple[bool, str]:
    """소스 코드 위치 검증"""
    rel_path = os.path.relpath(file_path, project_root)
    source_rules = rules.get("source", DEFAULT_RULES["source"])
    src_root = source_rules.get("root", "src/")

    if not rel_path.startswith(src_root):
        return True, ""  # src/ 밖은 다른 규칙으로

    # src/ 내부 경로 분석
    inner_path = rel_path[len(src_root):]
    parts = inner_path.split("/")

    if len(parts) > 0:
        top_level = parts[0]
        allowed = source_rules.get("allowed_top_level", [])

        if top_level not in allowed and top_level != "":
            return False, f"src/ 내 허용되지 않는 폴더: {top_level}\n허용: {allowed}"

    return True, ""


def check_scratch_test(file_path: str, rules: dict, project_root: str) -> tuple[bool, str]:
    """임시 테스트 파일 경고"""
    rel_path = os.path.relpath(file_path, project_root)
    test_rules = rules.get("tests", DEFAULT_RULES["tests"])
    scratch_path = test_rules.get("scratch_path", "tests/scratch/")

    if rel_path.startswith(scratch_path):
        max_age = test_rules.get("scratch_max_age_days", 7)
        return True, f"⚠️ 임시 테스트 파일입니다. {max_age}일 후 또는 PR 머지 전 삭제하세요."

    return True, ""


def validate_file(file_path: str) -> tuple[bool, str]:
    """파일 위치 종합 검증"""
    project_root = get_project_root()
    rules = load_project_rules(project_root)

    messages = []
    is_valid = True

    # 1. 금지 패턴 검사
    valid, msg = check_forbidden_patterns(file_path, rules)
    if not valid:
        is_valid = False
        messages.append(f"❌ {msg}")

    # 2. 문서 위치 검사
    valid, msg = check_doc_location(file_path, rules, project_root)
    if not valid:
        is_valid = False
        messages.append(f"❌ {msg}")
    elif msg:
        messages.append(msg)

    # 3. 소스 위치 검사
    valid, msg = check_source_location(file_path, rules, project_root)
    if not valid:
        is_valid = False
        messages.append(f"❌ {msg}")

    # 4. 임시 테스트 경고
    valid, msg = check_scratch_test(file_path, rules, project_root)
    if msg:
        messages.append(msg)

    return is_valid, "\n".join(messages)


def main():
    try:
        input_data = json.load(sys.stdin)

        tool_name = input_data.get('tool_name', '')
        tool_input = input_data.get('tool_input', {})

        # Write 또는 Edit 도구만 검사
        if tool_name not in ('Write', 'Edit'):
            sys.exit(0)

        file_path = tool_input.get('file_path', '')
        if not file_path:
            sys.exit(0)

        # 검증
        is_valid, message = validate_file(file_path)

        if message:
            print(f"\n📐 거버넌스 검사: {os.path.basename(file_path)}")
            print(message)
            print()

        # 경고만 하고 차단하지는 않음 (exit 0)
        # 차단하려면 exit 2
        sys.exit(0)

    except Exception as e:
        # 에러 발생해도 작업 중단하지 않음
        debug_log(f"Governance check error: {e}", e)
        sys.exit(0)


if __name__ == '__main__':
    main()
