#!/usr/bin/env python3
"""
Task 완료 메트릭 로깅 훅

PostToolUse 이벤트에서 Task 도구 완료를 감지하여
에이전트 실행 메트릭을 기록합니다.

로그 위치: ~/.claude/logs/metrics/YYYY-MM-DD.jsonl
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# 로그 디렉토리 설정
LOG_DIR = Path.home() / ".claude" / "logs" / "metrics"

# 공통 유틸리티 import (스크립트 위치 기반 동적 경로)
hook_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, hook_dir)
try:
    from utils import debug_log, is_debug_mode
except ImportError:
    def debug_log(msg, error=None): pass
    def is_debug_mode(): return False


def ensure_log_dir():
    """로그 디렉토리 생성"""
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def get_log_file() -> Path:
    """오늘 날짜의 로그 파일 경로"""
    return LOG_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.jsonl"


def detect_status(data: dict) -> str:
    """
    Task 실행 상태 감지

    PostToolUse 이벤트에는 tool_result가 포함되어 있으며,
    error 필드로 성공/실패를 판단합니다.

    Returns:
        "success" | "error"
    """
    tool_result = data.get("tool_result", {})

    # tool_result에 error 필드가 있으면 에러
    if "error" in tool_result:
        return "error"

    # 정상 완료
    return "success"


def calculate_duration(data: dict) -> int | None:
    """
    Task 실행 시간 계산 (밀리초)

    PostToolUse 이벤트에 duration_ms가 있으면 사용,
    없으면 None으로 반환 (정보 없음을 명시)

    Returns:
        duration in milliseconds or None if unavailable
    """
    # Claude Code가 duration_ms를 제공하는 경우
    if "duration_ms" in data:
        return int(data["duration_ms"])

    # tool_result에 duration 정보가 있을 수 있음
    tool_result = data.get("tool_result", {})
    if "duration_ms" in tool_result:
        return int(tool_result["duration_ms"])

    # 정보 없으면 None
    debug_log("No duration info available")
    return None


def create_metric_entry(data: dict) -> dict:
    """
    메트릭 로그 항목 생성

    Returns:
        {
            "timestamp": "2026-02-08T10:30:45.123456",
            "session_id": "session-123",
            "agent_type": "implement-code",
            "duration_ms": 1234,
            "duration_source": "provided" | "calculated" | "unavailable",
            "status": "success",
            "tool_use_id": "toolu_xxx"
        }
    """
    tool_input = data.get("tool_input", {})

    # Skill vs Task 파라미터 차이 처리
    tool_name = data.get("tool_name", "")
    if tool_name == "Skill":
        agent_type = f"skill/{tool_input.get('skill', 'unknown')}"
    else:  # Task
        agent_type = tool_input.get("subagent_type", "unknown")

    # duration 계산 및 출처 감지
    duration = calculate_duration(data)

    # duration 출처 결정
    if duration is None:
        duration_source = "unavailable"
    elif "duration_ms" in data:
        duration_source = "provided"
    elif "duration_ms" in data.get("tool_result", {}):
        duration_source = "calculated"
    else:
        duration_source = "unavailable"

    return {
        "timestamp": datetime.now().isoformat(),
        "session_id": data.get("session_id", "unknown"),
        "agent_type": agent_type,
        "duration_ms": duration,
        "duration_source": duration_source,
        "status": detect_status(data),
        "tool_use_id": data.get("tool_use_id", ""),
    }


def write_log(entry: dict):
    """로그 파일에 항목 추가 (JSONL 형식)"""
    ensure_log_dir()
    log_file = get_log_file()

    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def print_to_console(entry: dict):
    """콘솔에 메트릭 출력 (디버그용)"""
    if is_debug_mode():
        agent = entry["agent_type"]
        duration = entry["duration_ms"]
        status = entry["status"]
        duration_str = f"{duration}ms" if duration is not None else "N/A"
        print(
            f"[METRIC] {agent}: {duration_str} ({status})",
            file=sys.stderr
        )


def main():
    """메인 로직"""
    try:
        # stdin에서 훅 데이터 수신
        data = json.load(sys.stdin)

        # Task/Skill 도구인지 확인 (이미 matcher로 필터링되지만 안전하게)
        tool_name = data.get("tool_name", "")
        if tool_name not in ["Task", "Skill"]:
            sys.exit(0)

        # PostToolUse만 처리 - settings.json matcher가 이미 필터링하지만,
        # 설정 변경이나 다른 훅에서 재사용될 경우를 위한 방어적 검증
        hook_event_name = data.get("hook_event_name", "")
        if hook_event_name != "PostToolUse":
            sys.exit(0)

        # 메트릭 항목 생성
        entry = create_metric_entry(data)

        # 파일에 기록
        write_log(entry)

        # 디버그 모드면 콘솔에도 출력
        print_to_console(entry)

        duration_str = f"{entry['duration_ms']}ms" if entry['duration_ms'] is not None else "N/A"
        debug_log(f"Metric logged: {entry['agent_type']} - {duration_str}")

    except json.JSONDecodeError:
        # JSON 파싱 실패 시 조용히 종료 (작업 중단 방지)
        debug_log("JSON parse error", None)
    except Exception as e:
        # 기타 에러도 조용히 종료
        debug_log(f"Metric logging error: {e}", e)

    # 항상 성공으로 종료 (작업 차단 안 함)
    sys.exit(0)


if __name__ == "__main__":
    main()
