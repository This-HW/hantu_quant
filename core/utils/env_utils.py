"""
환경 감지 및 검증 유틸리티

로컬/서버 환경을 자동 감지하고 스케줄러 실행 가능 여부를 판단합니다.
"""

import os
import subprocess
from pathlib import Path
from typing import Tuple, Literal

from core.utils.log_utils import get_logger

logger = get_logger(__name__)

# 환경 타입 정의
EnvType = Literal["local", "server", "test", "unknown"]


def get_environment() -> EnvType:
    """현재 실행 환경 감지

    Returns:
        "local": 로컬 개발 환경 (/Users/*, /home/{user} 등)
        "server": 서버 환경 (/opt/*, /home/ubuntu 등)
        "test": 테스트 환경 (HANTU_ENV=test)
        "unknown": 알 수 없는 환경
    """
    # 1. 환경변수 HANTU_ENV 우선 체크
    env_override = os.getenv('HANTU_ENV', '').lower()
    if env_override in ['local', 'server', 'test']:
        return env_override  # type: ignore

    # 2. 경로 기반 자동 감지
    root_path = str(Path(__file__).parent.parent.parent)

    # 서버 환경 패턴
    is_server = (
        root_path.startswith("/opt/hantu_quant") or
        root_path.startswith("/opt/") or
        root_path.startswith("/home/ubuntu") or
        root_path.startswith("/srv/")
    )
    if is_server:
        return "server"

    # 로컬 환경 패턴
    is_local = (
        root_path.startswith("/Users/") or
        (root_path.startswith("/home/") and
         not root_path.startswith("/home/ubuntu"))
    )
    if is_local:
        return "local"

    # 알 수 없는 환경
    return "unknown"


def check_ssh_tunnel() -> bool:
    """SSH 터널 활성 상태 확인

    Returns:
        True: SSH 터널 실행 중
        False: SSH 터널 중지됨
    """
    try:
        # ps aux로 SSH 터널 프로세스 확인
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True,
            timeout=5
        )

        # SSH 터널 패턴: ssh -f -N -L 15432:localhost:5432
        tunnel_patterns = [
            "15432:localhost:5432",
            "ssh.*-L.*15432"
        ]

        for pattern in tunnel_patterns:
            if pattern in result.stdout:
                return True

        return False

    except Exception as e:
        logger.warning(f"SSH 터널 상태 확인 실패: {e}")
        return False


def can_run_scheduler(force_local: bool = False) -> Tuple[bool, str]:
    """스케줄러 실행 가능 여부 확인

    Args:
        force_local: 로컬에서 강제 실행 허용 (기본: False)

    Returns:
        (실행 가능 여부, 메시지)
    """
    env = get_environment()

    # 서버 환경: 항상 허용
    if env == "server":
        return True, f"✅ 서버 환경 ({os.getcwd()}) - 스케줄러 실행 허용"

    # 테스트 환경: 항상 차단
    if env == "test":
        return False, "❌ 테스트 환경에서는 스케줄러를 실행할 수 없습니다"

    # 로컬 환경: 기본 차단
    if env == "local":
        if not force_local:
            return False, (
                "❌ 로컬 환경에서 스케줄러 실행이 차단되었습니다\n"
                "\n"
                "이유:\n"
                "  - 로컬과 서버 스케줄러가 동시 실행되면 중복 작업 발생\n"
                "  - SSH 터널 연결 끊김 시 DB 에러 알림 스팸 발생\n"
                "\n"
                "해결 방법:\n"
                "  1. 서버 스케줄러 사용 (권장)\n"
                "     → ssh ubuntu@158.180.87.156\n"
                "     → sudo systemctl status hantu-scheduler\n"
                "\n"
                "  2. 로컬에서 강제 실행 (디버깅 전용)\n"
                "     → ./scripts/db-tunnel.sh start  # SSH 터널 시작\n"
                "     → python workflows/integrated_scheduler.py start --force-local\n"
                "\n"
                "  3. 일회성 작업 실행 (권장)\n"
                "     → hantu screen  # 종목 스크리닝\n"
                "     → hantu select  # 일일 선정\n"
            )

        # 강제 실행 플래그 있음: SSH 터널 확인
        tunnel_active = check_ssh_tunnel()
        if not tunnel_active:
            return False, (
                "❌ SSH 터널이 실행 중이지 않습니다\n"
                "\n"
                "SSH 터널을 시작한 후 다시 시도하세요:\n"
                "  → ./scripts/db-tunnel.sh start\n"
                "  → ./scripts/db-tunnel.sh status  # 확인\n"
            )

        return True, (
            "⚠️  로컬 환경에서 스케줄러를 강제 실행합니다\n"
            "\n"
            "주의사항:\n"
            "  - 서버 스케줄러와 중복 실행되지 않도록 주의\n"
            "  - SSH 터널이 끊기면 DB 연결 실패 에러 발생\n"
            "  - Ctrl+C로 중지할 때까지 계속 실행됨\n"
        )

    # 알 수 없는 환경: 차단
    return False, (
        f"❌ 알 수 없는 환경 ({os.getcwd()})\n"
        "\n"
        "HANTU_ENV 환경변수를 설정하세요:\n"
        "  export HANTU_ENV=local   # 로컬 개발\n"
        "  export HANTU_ENV=server  # 서버 배포\n"
    )


def get_environment_info() -> dict:
    """현재 환경 정보 반환

    Returns:
        환경 정보 딕셔너리
    """
    env = get_environment()
    ssh_tunnel = check_ssh_tunnel() if env == "local" else None

    return {
        "environment": env,
        "current_directory": os.getcwd(),
        "ssh_tunnel_active": ssh_tunnel,
        "can_run_scheduler": can_run_scheduler()[0],
    }
