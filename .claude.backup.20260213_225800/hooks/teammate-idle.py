#!/usr/bin/env python3
"""
PostToolUse Hook: Teammate Idle 감지 (S-C-09)

Agent Teams 모드에서 Teammate가 지정 시간 내 응답하지 않으면
재시도 또는 강제 진행을 트리거합니다.

동작 방식:
- message/broadcast 결과를 모니터링
- Teammate별 마지막 활동 시간 추적
- STATE-003 상태 머신: IDLE → WORKING → COMPLETED/FAILED
- 최대 3회 재시도 후 강제 진행

설정:
- TEAMMATE_IDLE_TIMEOUT: 초 단위 타임아웃 (기본 300초 = 5분)
- TEAMMATE_MAX_RETRIES: 최대 재시도 횟수 (기본 3회)

사용법:
  settings.json에서 PostToolUse hook으로 등록

종료 코드:
  0: 정상 (허용)
"""

import json
import sys
import os
import time
from pathlib import Path
from datetime import datetime

# 공통 유틸리티 import
hook_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, hook_dir)
try:
    from utils import debug_log, is_debug_mode
except ImportError:
    def debug_log(msg, error=None): pass
    def is_debug_mode(): return False


# 설정 상수 (안전한 환경변수 파싱)
def _safe_int(env_var: str, default: int, min_val: int = 1, max_val: int = 3600) -> int:
    try:
        value = int(os.environ.get(env_var, str(default)))
        if value < min_val or value > max_val:
            return default
        return value
    except (ValueError, TypeError):
        return default

TEAMMATE_IDLE_TIMEOUT = _safe_int('TEAMMATE_IDLE_TIMEOUT', 300, 1, 3600)  # 5분
TEAMMATE_MAX_RETRIES = _safe_int('TEAMMATE_MAX_RETRIES', 3, 1, 100)

# 상태 파일 경로
STATE_DIR = os.path.join(os.environ.get('HOME', '/tmp'), '.claude', 'logs', 'agent-teams')
STATE_FILE = os.path.join(STATE_DIR, 'teammate-activity.json')


def ensure_state_dir():
    """상태 디렉토리 생성"""
    os.makedirs(STATE_DIR, exist_ok=True)


def _validate_state(data) -> dict:
    """로드된 상태 데이터의 타입 검증 (M-2)"""
    if not isinstance(data, dict):
        return None
    if 'teammates' in data and not isinstance(data['teammates'], dict):
        return None
    if 'total_retries' in data and not isinstance(data['total_retries'], (int, float)):
        return None
    return data


def load_state() -> dict:
    """Teammate 활동 상태 로드"""
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r') as f:
                data = json.load(f)
                validated = _validate_state(data)
                if validated is not None:
                    return validated
                debug_log("State file failed type validation, using defaults")
    except (json.JSONDecodeError, IOError) as e:
        debug_log(f"State load error: {e}")

    return {
        'teammates': {},
        'session_start': datetime.now().isoformat(),
        'total_retries': 0,
    }


def save_state(state: dict):
    """Teammate 활동 상태 저장 (파일 락 사용)

    병렬 Teammate가 동시에 상태 파일에 쓰는 경합을 방지합니다.

    플랫폼: macOS/Linux 전용 (fcntl 사용). Windows 미지원.
    """
    import fcntl
    ensure_state_dir()
    old_umask = os.umask(0o077)  # M-1: 상태 파일 소유자만 읽기/쓰기
    try:
        with open(STATE_FILE, 'w') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                json.dump(state, f, indent=2, default=str)
                f.flush()
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except IOError as e:
        debug_log(f"State save error: {e}")
    finally:
        os.umask(old_umask)


def update_teammate_activity(state: dict, teammate_id: str, status: str) -> dict:
    """Teammate 활동 업데이트 (STATE-003)

    상태: IDLE → WORKING → COMPLETED/FAILED
    """
    now = datetime.now().isoformat()

    if teammate_id not in state['teammates']:
        state['teammates'][teammate_id] = {
            'status': 'IDLE',
            'last_activity': now,
            'retry_count': 0,
            'messages_sent': 0,
            'created_at': now,
        }

    teammate = state['teammates'][teammate_id]
    teammate['last_activity'] = now
    teammate['status'] = status

    if status == 'WORKING':
        teammate['messages_sent'] = teammate.get('messages_sent', 0) + 1

    return state


def check_idle_teammates(state: dict) -> list:
    """타임아웃된 Teammate 목록 반환"""
    idle_teammates = []
    now = time.time()

    for tid, info in state.get('teammates', {}).items():
        if info.get('status') in ('COMPLETED', 'FAILED', 'FORCE_PROCEEDED'):
            continue

        last_activity = info.get('last_activity', '')
        if not last_activity:
            continue

        try:
            last_ts = datetime.fromisoformat(last_activity).timestamp()
            elapsed = now - last_ts

            if elapsed > TEAMMATE_IDLE_TIMEOUT:
                idle_teammates.append({
                    'id': tid,
                    'elapsed_seconds': int(elapsed),
                    'retry_count': info.get('retry_count', 0),
                    'status': info.get('status', 'IDLE'),
                })
        except (ValueError, TypeError):
            continue

    return idle_teammates


def handle_idle_teammate(state: dict, teammate: dict) -> tuple[dict, str]:
    """Idle Teammate 처리

    Returns:
        (updated_state, action): action은 'retry' 또는 'force_proceed'
    """
    tid = teammate['id']
    retry_count = teammate['retry_count']

    if retry_count < TEAMMATE_MAX_RETRIES:
        # 재시도
        state['teammates'][tid]['retry_count'] = retry_count + 1
        state['teammates'][tid]['status'] = 'IDLE'
        state['teammates'][tid]['last_activity'] = datetime.now().isoformat()
        state['total_retries'] = state.get('total_retries', 0) + 1

        debug_log(f"Teammate {tid}: retry {retry_count + 1}/{TEAMMATE_MAX_RETRIES}")
        return state, 'retry'
    else:
        # 최대 재시도 초과 → 강제 진행
        state['teammates'][tid]['status'] = 'FORCE_PROCEEDED'
        state['teammates'][tid]['last_activity'] = datetime.now().isoformat()

        debug_log(f"Teammate {tid}: force proceed (max retries exceeded)")
        return state, 'force_proceed'


def extract_teammate_info(tool_input: dict) -> tuple[str, str]:
    """도구 입력에서 Teammate 정보 추출

    Returns:
        (teammate_id, action_type)
    """
    # 다양한 필드에서 Teammate ID 추출 시도
    teammate_id = (
        tool_input.get('teammate_id', '')
        or tool_input.get('to', '')
        or tool_input.get('target', '')
        or tool_input.get('name', '')
        or 'unknown'
    )

    # 액션 타입 추론
    content = tool_input.get('content', '') or tool_input.get('message', '')
    if content:
        return teammate_id, 'message'

    return teammate_id, 'activity'


def main():
    try:
        input_data = json.load(sys.stdin)

        tool_name = input_data.get('tool_name', '')
        tool_input = input_data.get('tool_input', {})
        tool_result = input_data.get('tool_result', {})

        # Agent Teams 관련 도구만 처리
        if tool_name not in ('message', 'broadcast', 'Task'):
            sys.exit(0)

        state = load_state()

        # message/broadcast 결과 처리: Teammate 활동 기록
        if tool_name in ('message', 'broadcast'):
            teammate_id, action = extract_teammate_info(tool_input)

            if tool_name == 'broadcast':
                # broadcast는 모든 Teammate에게 전달
                for tid in list(state.get('teammates', {}).keys()):
                    state = update_teammate_activity(state, tid, 'WORKING')
            else:
                state = update_teammate_activity(state, teammate_id, 'WORKING')

        # Idle Teammate 감지
        idle_list = check_idle_teammates(state)

        for idle_tm in idle_list:
            state, action = handle_idle_teammate(state, idle_tm)

            if action == 'retry':
                print(
                    f"⏰ Teammate '{idle_tm['id']}' 응답 없음 "
                    f"({idle_tm['elapsed_seconds']}초). "
                    f"재시도 {idle_tm['retry_count'] + 1}/{TEAMMATE_MAX_RETRIES}",
                    file=sys.stderr,
                )
            elif action == 'force_proceed':
                print(
                    f"⚠️ Teammate '{idle_tm['id']}' 최대 재시도 초과 "
                    f"({TEAMMATE_MAX_RETRIES}회). "
                    f"해당 Teammate 결과 없이 진행합니다.",
                    file=sys.stderr,
                )

        save_state(state)
        sys.exit(0)

    except json.JSONDecodeError:
        debug_log("JSON decode error in stdin")
        sys.exit(0)
    except Exception as e:
        debug_log(f"Hook error: {e}", e)
        sys.exit(0)


if __name__ == '__main__':
    main()
