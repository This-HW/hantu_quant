#!/usr/bin/env python3
"""
서브에이전트 실행 로깅 훅

PreToolUse/PostToolUse 이벤트에서 Task 도구 호출을 감지하여
서브에이전트 실행 로그를 기록합니다.

로그 위치: ~/.claude/logs/subagents/YYYY-MM-DD.jsonl
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# 로그 디렉토리 설정
LOG_DIR = Path.home() / ".claude" / "logs" / "subagents"


def ensure_log_dir():
    """로그 디렉토리 생성"""
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def get_log_file() -> Path:
    """오늘 날짜의 로그 파일 경로"""
    return LOG_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.jsonl"


def parse_event_type(hook_event_name: str) -> str:
    """훅 이벤트를 로그 이벤트로 변환"""
    if hook_event_name == "PreToolUse":
        return "START"
    elif hook_event_name == "PostToolUse":
        return "END"
    else:
        return hook_event_name


def create_log_entry(data: dict) -> dict:
    """로그 항목 생성"""
    tool_input = data.get("tool_input", {})

    # 프롬프트 미리보기 (너무 길면 자름)
    prompt = tool_input.get("prompt", "")
    prompt_preview = prompt[:200] + "..." if len(prompt) > 200 else prompt

    return {
        "timestamp": datetime.now().isoformat(),
        "event": parse_event_type(data.get("hook_event_name", "")),
        "session_id": data.get("session_id", "unknown"),
        "agent_type": tool_input.get("subagent_type", "unknown"),
        "description": tool_input.get("description", ""),
        "model": tool_input.get("model", "default"),
        "prompt_preview": prompt_preview,
        "cwd": data.get("cwd", ""),
        "tool_use_id": data.get("tool_use_id", "")
    }


def write_log(entry: dict):
    """로그 파일에 항목 추가"""
    ensure_log_dir()
    log_file = get_log_file()

    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def print_to_console(entry: dict):
    """콘솔에 간단한 로그 출력 (디버그용)"""
    if os.environ.get("CLAUDE_HOOK_DEBUG", "").lower() in ("1", "true", "yes"):
        event = entry["event"]
        agent = entry["agent_type"]
        desc = entry["description"]
        print(f"[SUBAGENT_{event}] {agent}: {desc}", file=sys.stderr)


def main():
    try:
        # stdin에서 훅 데이터 수신
        data = json.load(sys.stdin)

        # Task 도구인지 확인 (이미 matcher로 필터링되지만 안전하게)
        tool_name = data.get("tool_name", "")
        if tool_name != "Task":
            sys.exit(0)

        # 로그 항목 생성
        entry = create_log_entry(data)

        # 파일에 기록
        write_log(entry)

        # 디버그 모드면 콘솔에도 출력
        print_to_console(entry)

    except json.JSONDecodeError:
        # JSON 파싱 실패 시 조용히 종료 (작업 중단 방지)
        pass
    except Exception as e:
        # 기타 에러도 조용히 종료
        if os.environ.get("CLAUDE_HOOK_DEBUG", "").lower() in ("1", "true", "yes"):
            print(f"[ERROR] log-subagent: {e}", file=sys.stderr)

    # 항상 성공으로 종료 (작업 차단 안 함)
    sys.exit(0)


if __name__ == "__main__":
    main()
