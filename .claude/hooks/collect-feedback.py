#!/usr/bin/env python3
"""
사용자 피드백 수집 훅

사용자가 에이전트 실행 결과에 대해 평가를 남길 수 있습니다.
PostToolUse 훅으로 동작하며, 특정 환경변수가 설정된 경우에만 피드백을 수집합니다.

사용법:
    export CLAUDE_COLLECT_FEEDBACK=1
    export CLAUDE_FEEDBACK_RATING=4  # 1-5
    export CLAUDE_FEEDBACK_COMMENT="Great job!"  # optional

환경변수 설정 후 에이전트 실행하면 피드백이 기록됩니다.
"""

import json
import sys
import os
import fcntl
from datetime import datetime
from pathlib import Path

# 로그 디렉토리
FEEDBACK_DIR = Path.home() / ".claude" / "logs" / "feedback"


def ensure_feedback_dir():
    """피드백 디렉토리 생성"""
    FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)


def get_feedback_file():
    """오늘 날짜의 피드백 파일 경로"""
    today = datetime.now().strftime("%Y-%m-%d")
    return FEEDBACK_DIR / f"{today}.jsonl"


def should_collect_feedback() -> bool:
    """피드백 수집 여부 확인"""
    return os.getenv("CLAUDE_COLLECT_FEEDBACK", "").lower() in ("1", "true", "yes")


def get_feedback_rating() -> float:
    """환경변수에서 평점 가져오기"""
    try:
        rating = float(os.getenv("CLAUDE_FEEDBACK_RATING", "0"))
        # 1-5 범위 검증
        if 1 <= rating <= 5:
            return rating
    except ValueError:
        pass
    return 0.0


def get_feedback_comment() -> str:
    """환경변수에서 코멘트 가져오기"""
    return os.getenv("CLAUDE_FEEDBACK_COMMENT", "")


def get_session_id() -> str:
    """세션 식별자 가져오기"""
    if "CLAUDE_SESSION_ID" in os.environ:
        return os.environ["CLAUDE_SESSION_ID"]

    pid = os.getppid()
    return f"session_{pid}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def log_feedback(entry: dict):
    """피드백 데이터를 JSONL로 기록 (원자적 파일 쓰기)"""
    ensure_feedback_dir()
    feedback_file = get_feedback_file()

    # 원자적 파일 쓰기 (파일 락 사용)
    with open(feedback_file, "a", encoding="utf-8") as f:
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

    # 피드백 수집 모드가 아니면 즉시 종료
    if not should_collect_feedback():
        sys.exit(0)

    # stdin에서 JSON 읽기
    try:
        hook_data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        if os.getenv("CLAUDE_HOOK_DEBUG"):
            print(f"[collect-feedback] JSON parse error: {e}", file=sys.stderr)
        sys.exit(0)

    # Task tool만 처리
    tool_name = hook_data.get("tool", "")
    if tool_name != "Task":
        sys.exit(0)

    # 평점 가져오기
    rating = get_feedback_rating()
    if rating == 0.0:
        if os.getenv("CLAUDE_HOOK_DEBUG"):
            print("[collect-feedback] No valid rating provided", file=sys.stderr)
        sys.exit(0)

    # 에이전트 정보 추출
    tool_input = hook_data.get("parameters", {})
    tool_result = hook_data.get("result", "")

    agent_type = tool_input.get("subagent_type", "unknown")
    model = tool_input.get("model", "default")
    description = tool_input.get("description", "")

    # 피드백 엔트리 생성
    feedback_entry = {
        "timestamp": datetime.now().isoformat(),
        "session_id": get_session_id(),
        "agent_type": agent_type,
        "model": model,
        "description": description,
        "rating": rating,
        "comment": get_feedback_comment(),
        "result_length": len(tool_result),
    }

    # 로그 기록
    log_feedback(feedback_entry)

    # 디버그 모드: 출력
    if os.getenv("CLAUDE_HOOK_DEBUG"):
        print(
            f"[collect-feedback] Logged: {agent_type} - Rating: {rating}/5",
            file=sys.stderr
        )

    # 환경변수 클리어 (한 번만 기록)
    if "CLAUDE_FEEDBACK_RATING" in os.environ:
        del os.environ["CLAUDE_FEEDBACK_RATING"]
    if "CLAUDE_FEEDBACK_COMMENT" in os.environ:
        del os.environ["CLAUDE_FEEDBACK_COMMENT"]

    # 성공 (작업 계속 진행)
    sys.exit(0)


if __name__ == "__main__":
    main()
