#!/usr/bin/env python3
"""
성능 모니터링 훅

에이전트 실행 시간, 토큰 사용량, API 호출 수를 추적합니다.
PostToolUse 훅으로 Task 완료 시 메트릭을 기록합니다.

Phase 1 ML: 확장된 로그 스키마
- success: 작업 성공 여부
- scope: Small/Medium/Large
- task_keywords: 주요 키워드 추출
- session_id: 세션 식별자
"""

import json
import sys
import os
import re
import fcntl
from datetime import datetime
from pathlib import Path

# 로그 디렉토리
LOG_DIR = Path.home() / ".claude" / "logs" / "performance"

# 실패 패턴 (result에서 감지)
FAILURE_PATTERNS = [
    r"error",
    r"failed",
    r"exception",
    r"traceback",
    r"cannot",
    r"unable to",
    r"not found",
]

# 작업 규모 키워드
SCOPE_KEYWORDS = {
    "Small": ["fix", "update", "refactor", "단순", "small"],
    "Medium": ["implement", "add", "create", "medium", "기능"],
    "Large": ["design", "architecture", "system", "large", "설계", "전체"],
}


def ensure_log_dir():
    """로그 디렉토리 생성"""
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def get_log_file():
    """오늘 날짜의 로그 파일 경로"""
    today = datetime.now().strftime("%Y-%m-%d")
    return LOG_DIR / f"{today}.jsonl"


def get_session_id() -> str:
    """
    세션 식별자 생성

    1순위: CLAUDE_SESSION_ID 환경변수
    2순위: 프로세스 기반 생성
    """
    if "CLAUDE_SESSION_ID" in os.environ:
        return os.environ["CLAUDE_SESSION_ID"]

    # 프로세스 ID와 시작 시간 기반
    pid = os.getppid()  # 부모 프로세스 (메인 Claude)
    return f"session_{pid}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def detect_success(tool_result: str) -> bool:
    """
    작업 성공 여부 감지

    result에서 실패 패턴을 찾아 판단
    """
    if not tool_result:
        return False

    result_lower = tool_result.lower()

    for pattern in FAILURE_PATTERNS:
        if re.search(pattern, result_lower):
            return False

    return True


def extract_scope(description: str) -> str:
    """
    작업 규모 추출 (Small/Medium/Large)

    description에서 키워드 매칭으로 판단
    """
    if not description:
        return "Medium"

    desc_lower = description.lower()

    # 명시적 규모 표시가 있는지 확인
    for scope in ["small", "medium", "large"]:
        if scope in desc_lower:
            return scope.capitalize()

    # 키워드 기반 판단
    for scope, keywords in SCOPE_KEYWORDS.items():
        for keyword in keywords:
            if keyword in desc_lower:
                return scope

    return "Medium"  # 기본값


def extract_keywords(text: str) -> list:
    """
    텍스트에서 주요 키워드 추출

    간단한 휴리스틱:
    - 3글자 이상 단어
    - 알파벳 또는 한글
    - 중복 제거
    - 최대 10개
    """
    if not text:
        return []

    # 단어 추출 (영문 또는 한글)
    words = re.findall(r'[a-zA-Z가-힣]{3,}', text.lower())

    # 불용어 제거
    stopwords = {
        "the", "and", "for", "with", "from", "this", "that",
        "입니다", "합니다", "있습니다", "됩니다"
    }
    words = [w for w in words if w not in stopwords]

    # 중복 제거 및 빈도순 정렬
    from collections import Counter
    word_counts = Counter(words)
    top_words = [word for word, _ in word_counts.most_common(10)]

    return top_words


def extract_agent_info(tool_input: dict) -> dict:
    """Task tool 입력에서 에이전트 정보 추출"""
    description = tool_input.get("description", "")

    return {
        "agent_type": tool_input.get("subagent_type", "unknown"),
        "model": tool_input.get("model", "default"),
        "description": description,
        "prompt_length": len(tool_input.get("prompt", "")),
        "scope": extract_scope(description),
        "task_keywords": extract_keywords(description),
    }


def extract_performance_metrics(tool_result: str) -> dict:
    """
    Task tool 결과에서 성능 메트릭 추출

    주의: 실제 토큰 수는 Claude Code가 제공하지 않으므로 근사치 사용
    """
    result_length = len(tool_result)

    # 대략적인 토큰 수 (1 token ≈ 4 characters)
    estimated_tokens = result_length // 4

    return {
        "result_length": result_length,
        "estimated_tokens": estimated_tokens,
        "success": detect_success(tool_result),
    }


def log_performance(entry: dict):
    """성능 데이터를 JSONL로 기록 (원자적 파일 쓰기)"""
    ensure_log_dir()
    log_file = get_log_file()

    # 원자적 파일 쓰기 (파일 락 사용)
    with open(log_file, "a", encoding="utf-8") as f:
        # 공유 락 (append는 여러 프로세스가 동시에 가능)
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            try:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except (IOError, OSError):
            # Windows 등 fcntl 미지원 플랫폼에서는 락 없이 진행
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def main():
    """PostToolUse 훅 진입점"""

    # stdin에서 JSON 읽기
    try:
        hook_data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        # JSON 파싱 실패해도 작업은 계속 진행
        if os.getenv("CLAUDE_HOOK_DEBUG"):
            print(f"[monitor-performance] JSON parse error: {e}", file=sys.stderr)
        sys.exit(0)

    # Task tool만 모니터링
    tool_name = hook_data.get("tool", "")
    if tool_name != "Task":
        sys.exit(0)

    # 에이전트 정보 추출
    tool_input = hook_data.get("parameters", {})
    tool_result = hook_data.get("result", "")

    agent_info = extract_agent_info(tool_input)
    perf_metrics = extract_performance_metrics(tool_result)

    # 성능 로그 엔트리 생성 (확장된 스키마)
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "session_id": get_session_id(),
        "agent_type": agent_info["agent_type"],
        "model": agent_info["model"],
        "description": agent_info["description"],
        "scope": agent_info["scope"],
        "task_keywords": agent_info["task_keywords"],
        "prompt_length": agent_info["prompt_length"],
        "result_length": perf_metrics["result_length"],
        "estimated_tokens": perf_metrics["estimated_tokens"],
        "success": perf_metrics["success"],
    }

    # 로그 기록
    log_performance(log_entry)

    # 디버그 모드: 출력
    if os.getenv("CLAUDE_HOOK_DEBUG"):
        print(f"[monitor-performance] Logged: {agent_info['agent_type']} ({agent_info['model']})", file=sys.stderr)

    # 성공 (작업 계속 진행)
    sys.exit(0)


if __name__ == "__main__":
    main()
