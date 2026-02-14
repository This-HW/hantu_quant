#!/usr/bin/env python3
"""
Setup Hook: Claude Code 세션 시작 시 환경 검증

트리거: Setup 이벤트 (--init, --init-only, --maintenance)
역할: DB 터널, MCP 서버, 환경 변수 검증
차단: 하지 않음 (경고만, exit 0 필수)

사용법:
  settings.json에서 Setup hook으로 등록

종료 코드:
  0: 항상 (세션 시작 차단 금지)
"""

import json
import sys
import os
import subprocess
from pathlib import Path

# 공통 유틸리티 import (스크립트 위치 기반 동적 경로)
hook_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, hook_dir)
try:
    from utils import debug_log, is_debug_mode, get_project_root
except ImportError:
    def debug_log(msg, error=None): pass
    def is_debug_mode(): return False
    def get_project_root(): return os.getcwd()


# 타임아웃 설정 (초)
MCP_CHECK_TIMEOUT = 5


def check_db_tunnel() -> tuple[bool, str]:
    """
    DB SSH 터널 상태 확인

    Returns:
        (is_ok, message)
    """
    # 환경 변수 확인
    if 'CLAUDE_DB_SSH_HOST' not in os.environ:
        return True, ""  # DB 사용 안 하면 OK

    debug_log("Checking DB SSH tunnel...")

    try:
        # lsof로 포트 확인 (기본 15432)
        local_port = os.environ.get('CLAUDE_DB_LOCAL_PORT', '15432')
        result = subprocess.run(
            ['lsof', '-i', f':{local_port}'],
            capture_output=True,
            timeout=MCP_CHECK_TIMEOUT
        )

        if result.returncode == 0:
            debug_log(f"DB tunnel is running on port {local_port}")
            return True, f"DB SSH 터널 실행 중 (port {local_port})"
        else:
            return False, f"DB SSH 터널이 실행되지 않았습니다. './scripts/db-tunnel.sh start'를 실행하세요."

    except FileNotFoundError:
        debug_log("lsof command not found")
        return True, ""  # lsof 없으면 건너뛰기
    except subprocess.TimeoutExpired:
        debug_log("lsof timeout")
        return False, "DB 터널 확인 타임아웃"
    except Exception as e:
        debug_log(f"DB tunnel check error: {e}", e)
        return True, ""  # 오류 시 건너뛰기


def check_mcp_servers() -> list[str]:
    """
    MCP 서버 연결 검증

    Returns:
        경고 메시지 목록
    """
    warnings = []

    # settings.json 위치 찾기
    project_root = get_project_root()
    settings_path = Path(project_root) / '.claude' / 'settings.json'

    if not settings_path.exists():
        debug_log(f"settings.json not found: {settings_path}")
        return []

    try:
        with open(settings_path, 'r') as f:
            settings = json.load(f)

        mcp_servers = settings.get('mcpServers', {})

        if not mcp_servers:
            debug_log("No MCP servers configured")
            return []

        debug_log(f"Checking {len(mcp_servers)} MCP servers...")

        # npx 존재 여부를 루프 전에 한 번만 확인 (캐싱)
        npx_available = None
        try:
            result = subprocess.run(
                ['which', 'npx'],
                capture_output=True,
                timeout=MCP_CHECK_TIMEOUT
            )
            npx_available = (result.returncode == 0)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            npx_available = None  # 확인 불가

        for name, config in mcp_servers.items():
            command = config.get('command')
            args = config.get('args', [])
            env_vars = config.get('env', {})

            if not command:
                continue

            # 환경 변수 체크
            missing_vars = []
            for var_name, var_value in env_vars.items():
                # ${VAR_NAME} 형식에서 VAR_NAME 추출
                if var_value.startswith('${') and var_value.endswith('}'):
                    env_key = var_value[2:-1]
                    if env_key not in os.environ:
                        missing_vars.append(env_key)

            if missing_vars:
                warnings.append(
                    f"MCP '{name}': 환경 변수 누락 ({', '.join(missing_vars)})"
                )
                continue

            # npx 명령어 실행 가능 여부 확인 (캐싱된 결과 사용)
            if command == 'npx':
                if npx_available is False:
                    warnings.append(f"MCP '{name}': npx 명령어를 찾을 수 없습니다")
                elif npx_available is True:
                    debug_log(f"MCP '{name}': npx available")

    except json.JSONDecodeError as e:
        debug_log(f"settings.json parse error: {e}", e)
    except Exception as e:
        debug_log(f"MCP check error: {e}", e)

    return warnings


def check_env_vars() -> list[str]:
    """
    MCP 외 환경 변수 필수값 확인

    현재 모든 환경 변수는 다른 함수에서 검증됩니다:
    - MCP 관련: check_mcp_servers()
    - DB 관련: check_db_tunnel()

    향후 새 환경 변수 추가 시 이 함수에서 처리합니다.

    Returns:
        경고 메시지 목록
    """
    # 현재 별도 검증 대상 없음 (모두 전용 함수에서 처리)
    debug_log("Non-MCP env vars check completed")
    return []


def main():
    """메인 로직"""
    try:
        # stdin JSON 읽기 (Setup 이벤트는 JSON 없을 수도 있음)
        try:
            if not sys.stdin.isatty():
                data = json.load(sys.stdin)
                debug_log(f"Setup event data: {data}")
        except (json.JSONDecodeError, OSError, ValueError):
            pass  # JSON 없어도 괜찮음

        warnings = []

        # 1. DB 터널 체크
        db_ok, db_message = check_db_tunnel()
        if not db_ok and db_message:
            warnings.append(db_message)
        elif db_ok and db_message:
            debug_log(db_message)

        # 2. MCP 서버 체크
        mcp_warnings = check_mcp_servers()
        warnings.extend(mcp_warnings)

        # 3. 환경 변수 체크
        env_warnings = check_env_vars()
        warnings.extend(env_warnings)

        # 결과 출력
        if warnings:
            print("\n⚠️  Environment Warnings:", file=sys.stderr)
            for w in warnings:
                print(f"  - {w}", file=sys.stderr)
            print("\n💡 설정 방법: docs/guides/environment-variables.md", file=sys.stderr)
            print("", file=sys.stderr)
        else:
            if is_debug_mode():
                print("✅ Environment OK", file=sys.stderr)

        # 경고만 출력, 차단 안 함 (exit 0 필수)
        sys.exit(0)

    except Exception as e:
        debug_log(f"Setup hook error: {e}", e)
        sys.exit(0)  # 오류 시에도 세션 시작 차단 금지


if __name__ == "__main__":
    main()
