#!/usr/bin/env python3
"""
PostToolUse Hook: 토큰 사용량 모니터링 (POL-002, S-C-05)

Agent Teams 모드에서 토큰 사용량을 3계층으로 방어합니다.

3계층 방어:
- 80% 도달: 경고 메시지 출력
- 90% 도달: Round 3 강제 진행 권고
- 100% 도달: 세션 중단 경고

모드별 한도 (POL-002):
- SUBAGENT 모드: 150,000 토큰
- AGENT_TEAMS 모드: 300,000 토큰

설정:
- CLAUDE_COST_LIMIT_SUBAGENT: Subagent 모드 한도 (기본 150000)
- CLAUDE_COST_LIMIT_TEAMS: Agent Teams 모드 한도 (기본 300000)

사용법:
  settings.json에서 PostToolUse hook으로 등록

종료 코드:
  0: 정상 (허용)
"""

import json
import sys
import os
from datetime import datetime
from pathlib import Path

# 공통 유틸리티 import
hook_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, hook_dir)
try:
    from utils import debug_log, is_debug_mode
except ImportError:
    def debug_log(msg, error=None): pass
    def is_debug_mode(): return False


# 설정 상수 (POL-002, 안전한 환경변수 파싱)
def _safe_int(env_var: str, default: int, min_val: int = 1, max_val: int = 10000000) -> int:
    try:
        value = int(os.environ.get(env_var, str(default)))
        if value < min_val or value > max_val:
            return default
        return value
    except (ValueError, TypeError):
        return default

COST_LIMIT_SUBAGENT = _safe_int('CLAUDE_COST_LIMIT_SUBAGENT', 150000)
COST_LIMIT_TEAMS = _safe_int('CLAUDE_COST_LIMIT_TEAMS', 300000)

# 3계층 임계값
THRESHOLD_WARNING = 0.80   # 80%: 경고
THRESHOLD_FORCE = 0.90     # 90%: Round 3 강제 진행
THRESHOLD_ABORT = 1.00     # 100%: 중단

# 상태 파일
STATE_DIR = os.path.join(os.environ.get('HOME', '/tmp'), '.claude', 'logs', 'agent-teams')
USAGE_STATE_FILE = os.path.join(STATE_DIR, 'cost-usage.json')


def ensure_state_dir():
    """상태 디렉토리 생성"""
    os.makedirs(STATE_DIR, exist_ok=True)


def _validate_usage_state(data) -> dict:
    """로드된 사용량 상태의 타입 검증 (M-2)"""
    if not isinstance(data, dict):
        return None
    if 'estimated_usage' in data and not isinstance(data['estimated_usage'], (int, float)):
        return None
    if 'warnings_issued' in data and not isinstance(data['warnings_issued'], list):
        return None
    if 'mode' in data and data['mode'] not in ('SUBAGENT', 'AGENT_TEAMS'):
        return None
    return data


def load_usage_state() -> dict:
    """사용량 상태 로드"""
    try:
        if os.path.exists(USAGE_STATE_FILE):
            with open(USAGE_STATE_FILE, 'r') as f:
                data = json.load(f)
                validated = _validate_usage_state(data)
                if validated is not None:
                    return validated
                debug_log("Usage state file failed type validation, using defaults")
    except (json.JSONDecodeError, IOError) as e:
        debug_log(f"Usage state load error: {e}")

    return {
        'mode': 'SUBAGENT',
        'estimated_usage': 0,
        'session_start': datetime.now().isoformat(),
        'warnings_issued': [],
        'tool_calls': 0,
    }


def save_usage_state(state: dict):
    """사용량 상태 저장"""
    ensure_state_dir()
    old_umask = os.umask(0o077)  # M-1: 상태 파일 소유자만 읽기/쓰기
    try:
        with open(USAGE_STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2, default=str)
    except IOError as e:
        debug_log(f"Usage state save error: {e}")
    finally:
        os.umask(old_umask)


def estimate_usage(tool_name: str, tool_input: dict) -> int:
    """도구 호출의 예상 사용량 추정 (CALC-002 기반)

    근사치:
    - Read: 파일 크기 기반 (평균 2000)
    - Write/Edit: 콘텐츠 크기 기반
    - message/broadcast: 메시지 크기 기반
    - Task: 에이전트 기본 오버헤드 8000
    - Grep/Glob: 결과 크기 기반 (평균 500)
    """
    base_overhead = 200  # 도구 호출 기본 오버헤드

    if tool_name == 'Read':
        return base_overhead + 2000

    elif tool_name in ('Write', 'Edit'):
        content = tool_input.get('content', '') or tool_input.get('new_string', '')
        return base_overhead + max(len(content) // 4, 500)

    elif tool_name in ('message', 'broadcast'):
        content = tool_input.get('content', '') or tool_input.get('message', '')
        return base_overhead + max(len(content) // 4, 300)

    elif tool_name == 'Task':
        # 서브에이전트 기본 오버헤드 (CALC-002: base 8K per perspective)
        return 8000

    elif tool_name in ('Grep', 'Glob'):
        return base_overhead + 500

    elif tool_name == 'Skill':
        return 5000

    else:
        return base_overhead + 300


def get_limit(mode: str) -> int:
    """모드에 따른 한도 반환"""
    if mode == 'AGENT_TEAMS':
        return COST_LIMIT_TEAMS
    return COST_LIMIT_SUBAGENT


def check_thresholds(state: dict) -> list[str]:
    """임계값 체크 및 경고 메시지 생성"""
    messages = []
    mode = state.get('mode', 'SUBAGENT')
    limit = get_limit(mode)
    used = state.get('estimated_usage', 0)
    ratio = used / limit if limit > 0 else 0
    warnings_issued = state.get('warnings_issued', [])

    if ratio >= THRESHOLD_ABORT and 'abort' not in warnings_issued:
        messages.append(
            f"🚨 사용량 한도 초과! ({used:,}/{limit:,} = {ratio:.0%}) "
            f"[{mode}] 세션을 종료하고 결과를 저장하세요."
        )
        state['warnings_issued'].append('abort')

    elif ratio >= THRESHOLD_FORCE and 'force' not in warnings_issued:
        messages.append(
            f"⚠️ 사용량 90% ({used:,}/{limit:,} = {ratio:.0%}) "
            f"[{mode}] Round 3으로 강제 진행하고 합의를 도출하세요."
        )
        state['warnings_issued'].append('force')

    elif ratio >= THRESHOLD_WARNING and 'warning' not in warnings_issued:
        messages.append(
            f"📊 사용량 80% ({used:,}/{limit:,} = {ratio:.0%}) "
            f"[{mode}] 분석 범위를 줄이거나 라운드를 단축하세요."
        )
        state['warnings_issued'].append('warning')

    return messages


def detect_mode(tool_name: str, state: dict) -> str:
    """현재 모드 감지

    판별 우선순위 (높→낮):
    1. 기존 AGENT_TEAMS 확정 (spawn_team_called=True) → 유지
    2. broadcast 도구 사용 → AGENT_TEAMS 확정 (Lead 전용 도구)
    3. 환경변수 + 기존 상태 → 기존 모드 유지
    4. 기본값 → SUBAGENT
    """
    # 이전에 spawnTeam 호출 기록 있으면 유지
    if state.get('spawn_team_called', False):
        return 'AGENT_TEAMS'

    # broadcast는 Agent Teams Lead만 사용
    if tool_name == 'broadcast':
        state['spawn_team_called'] = True
        return 'AGENT_TEAMS'

    # message는 양쪽 모드에서 사용 가능 → 기존 상태 유지
    if os.environ.get('CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS', '') == '1':
        if state.get('mode') == 'AGENT_TEAMS':
            return 'AGENT_TEAMS'

    return state.get('mode', 'SUBAGENT')


def main():
    try:
        input_data = json.load(sys.stdin)

        tool_name = input_data.get('tool_name', '')
        tool_input = input_data.get('tool_input', {})

        state = load_usage_state()

        # 모드 감지
        state['mode'] = detect_mode(tool_name, state)

        # 사용량 추정 및 누적
        estimated = estimate_usage(tool_name, tool_input)
        state['estimated_usage'] = state.get('estimated_usage', 0) + estimated
        state['tool_calls'] = state.get('tool_calls', 0) + 1

        debug_log(
            f"Usage estimate: +{estimated} = {state['estimated_usage']:,} "
            f"(mode={state['mode']}, tool={tool_name})"
        )

        # 임계값 체크
        warnings = check_thresholds(state)
        for msg in warnings:
            print(msg, file=sys.stderr)

        save_usage_state(state)
        sys.exit(0)

    except json.JSONDecodeError:
        debug_log("JSON decode error in stdin")
        sys.exit(0)
    except Exception as e:
        debug_log(f"Hook error: {e}", e)
        sys.exit(0)


if __name__ == '__main__':
    main()
