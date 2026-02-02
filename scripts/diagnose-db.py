#!/usr/bin/env python3
"""
DB Connection Diagnostics Tool

목적: DB 연결 상태 진단 및 문제 해결 가이드
실행: python scripts/diagnose-db.py
"""

import os
import sys
import subprocess
import logging
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가 (core 모듈 import를 위해)
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

# 간단한 로거 설정 (core import 순환 의존성 회피)
logging.basicConfig(
    level=logging.WARNING,  # 에러만 출력
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# ANSI 색상 코드
GREEN = '\033[0;32m'
RED = '\033[0;31m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
NC = '\033[0m'  # No Color

def print_header():
    """진단 도구 헤더 출력"""
    print("=" * 60)
    print("DB Connection Diagnostics")
    print("=" * 60)
    print()


def detect_environment():
    """현재 환경 감지 (settings.py 로직 사용)"""
    try:
        from core.config.settings import ROOT_DIR, DATABASE_URL, DB_TYPE

        root_path = str(ROOT_DIR)

        # HANTU_ENV 환경변수 우선 체크
        env_override = os.getenv('HANTU_ENV', '').lower()
        if env_override:
            env_name = env_override
        else:
            # 경로 기반 감지
            is_local = root_path.startswith("/Users/") or root_path.startswith("/home/user")
            is_server = (
                root_path.startswith("/opt/hantu_quant") or
                root_path.startswith("/opt/") or
                root_path.startswith("/home/ubuntu") or
                root_path.startswith("/srv/")
            )

            if is_local:
                env_name = "local"
            elif is_server:
                env_name = "server"
            else:
                env_name = "unknown"

        print(f"Environment: {BLUE}{env_name}{NC} ({root_path})")

        # DATABASE_URL 출처 표시
        env_db_url = os.getenv('DATABASE_URL')
        if env_db_url:
            print(f"DB URL Source: {YELLOW}.env file (override){NC}")
        else:
            print(f"DB URL Source: {BLUE}auto-detected{NC}")

        print(f"Expected DB URL: {DATABASE_URL}")
        print(f"DB Type: {DB_TYPE}")

        # 로컬 환경에서 포트 경고
        if env_name == "local" and "15432" not in DATABASE_URL:
            print(f"{YELLOW}Warning: Local environment should use port 15432 (SSH tunnel){NC}")
            print(f"{YELLOW}         Current URL uses different port. Check .env file.{NC}")

        print()

        return env_name, DATABASE_URL, DB_TYPE

    except ModuleNotFoundError as e:
        logger.error(f"환경 감지 실패 (의존성 누락): {e}", exc_info=True)
        print(f"{RED}Failed to detect environment: {e}{NC}")
        print()
        print("Missing dependencies. Please install:")
        print("  pip install -r requirements.txt")
        print()
        return "error", None, None

    except Exception as e:
        logger.error(f"환경 감지 실패: {e}", exc_info=True)
        print(f"{RED}Failed to detect environment: {e}{NC}")
        print()
        return "error", None, None


def check_ssh_tunnel():
    """SSH 터널 상태 확인 (로컬만)"""
    print("[1/4] Checking SSH Tunnel...")

    # db-tunnel.sh 스크립트 존재 확인
    tunnel_script = ROOT_DIR / "scripts" / "db-tunnel.sh"
    if not tunnel_script.exists():
        print(f"  {RED}SSH tunnel script not found: {tunnel_script}{NC}")
        return False

    try:
        # db-tunnel.sh status 실행
        result = subprocess.run(
            [str(tunnel_script), "status"],
            capture_output=True,
            text=True,
            timeout=5
        )

        # "Running" 문자열이 있으면 터널 실행 중
        if "Running" in result.stdout or "running" in result.stdout.lower():
            print(f"  {GREEN}SSH Tunnel Running{NC}")
            return True
        else:
            print(f"  {RED}SSH Tunnel Not Running{NC}")
            print()
            print("  To start SSH tunnel:")
            print(f"    {tunnel_script} start")
            print()
            return False

    except subprocess.TimeoutExpired:
        print(f"  {YELLOW}SSH tunnel check timed out{NC}")
        logger.warning("SSH 터널 상태 확인 타임아웃", exc_info=True)
        return False
    except Exception as e:
        print(f"  {YELLOW}Could not check SSH tunnel: {e}{NC}")
        logger.error(f"SSH 터널 상태 확인 실패: {e}", exc_info=True)
        return False


def test_db_connection(database_url: str, env_name: str = "unknown"):
    """PostgreSQL 연결 테스트"""
    print("[2/4] Testing DB Connection...")

    if not database_url:
        print(f"  {RED}No DATABASE_URL configured{NC}")
        return False

    try:
        import psycopg2
        from urllib.parse import urlparse

        # DATABASE_URL 파싱
        parsed = urlparse(database_url)

        # 연결 파라미터 추출
        conn_params = {
            'host': parsed.hostname or 'localhost',
            'port': parsed.port or 5432,
            'database': parsed.path.lstrip('/') if parsed.path else 'postgres',
            'user': parsed.username or 'postgres',
        }

        # 비밀번호는 URL에 있으면 사용, 없으면 .pgpass 의존
        if parsed.password:
            conn_params['password'] = parsed.password

        # 연결 시도
        conn = psycopg2.connect(
            **conn_params,
            connect_timeout=5
        )
        conn.close()

        print(f"  {GREEN}PostgreSQL Connection OK{NC}")
        return True

    except ImportError:
        print(f"  {RED}psycopg2 not installed{NC}")
        print()
        print("  Install with:")
        print("    pip install psycopg2-binary")
        print()
        return False

    except Exception as e:
        print(f"  {RED}Connection Failed: {e}{NC}")
        logger.error(f"DB 연결 실패: {e}", exc_info=True)
        print()
        print("  Possible issues:")

        # 로컬 환경에서 포트 관련 에러
        if env_name == "local" and "15432" not in database_url:
            print(f"    {YELLOW}1. Wrong port configured in .env{NC}")
            print("       Local environment should use port 15432 (SSH tunnel)")
            print("       Update DATABASE_URL in .env:")
            print("         DATABASE_URL=postgresql://hantu@localhost:15432/hantu_quant")
            print("         # Password authentication uses ~/.pgpass file")
            print()

        print("    - PostgreSQL server not running")
        print("    - SSH tunnel not running (for local)")
        print("    - Wrong credentials (check ~/.pgpass)")
        print("    - Firewall blocking connection")
        print()
        return False


def test_db_query(database_url: str, env_name: str = "unknown"):
    """쿼리 테스트"""
    print("[3/4] Query Test...")

    if not database_url:
        print(f"  {RED}No DATABASE_URL configured{NC}")
        return False

    try:
        import psycopg2
        from urllib.parse import urlparse

        parsed = urlparse(database_url)

        conn_params = {
            'host': parsed.hostname or 'localhost',
            'port': parsed.port or 5432,
            'database': parsed.path.lstrip('/') if parsed.path else 'postgres',
            'user': parsed.username or 'postgres',
        }

        if parsed.password:
            conn_params['password'] = parsed.password

        # 연결 및 쿼리 실행
        conn = psycopg2.connect(**conn_params, connect_timeout=5)
        cursor = conn.cursor()

        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]

        cursor.close()
        conn.close()

        # 버전 정보 출력 (간략하게)
        version_short = version.split(',')[0]  # "PostgreSQL 15.x" 부분만
        print(f"  {GREEN}Query Test OK{NC} ({version_short})")
        return True

    except Exception as e:
        print(f"  {RED}Query Failed: {e}{NC}")
        logger.error(f"쿼리 실행 실패: {e}", exc_info=True)
        print()
        print("  Possible issues:")
        print("    - No SELECT permission")
        print("    - Database does not exist")
        print("    - Connection unstable")
        print()
        return False


def print_summary(results: dict):
    """진단 결과 요약"""
    print("[4/4] Summary")

    all_passed = all(results.values())

    if all_passed:
        print(f"  {GREEN}All checks passed. DB is ready.{NC}")
    else:
        print(f"  {YELLOW}Some checks failed. See details above.{NC}")

    print()


def main():
    """메인 진단 프로세스"""
    print_header()

    # 1. 환경 감지
    env_name, database_url, db_type = detect_environment()

    if env_name == "error":
        sys.exit(1)

    results = {}

    # 2. SSH 터널 체크 (로컬만)
    if env_name == "local":
        results['ssh_tunnel'] = check_ssh_tunnel()
    else:
        print("[1/4] Checking SSH Tunnel...")
        print(f"  {BLUE}Skipped (not needed on server){NC}")
        results['ssh_tunnel'] = True

    print()

    # 3. DB 연결 테스트
    if db_type == 'postgresql':
        results['db_connection'] = test_db_connection(database_url, env_name)
        print()

        # 4. 쿼리 테스트 (연결 성공 시에만)
        if results['db_connection']:
            results['db_query'] = test_db_query(database_url, env_name)
        else:
            print("[3/4] Query Test...")
            print(f"  {YELLOW}Skipped (connection failed){NC}")
            results['db_query'] = False

        print()
    else:
        # SQLite 또는 다른 DB 타입
        print("[2/4] Testing DB Connection...")
        print(f"  {BLUE}Using {db_type} (no connection test needed){NC}")
        results['db_connection'] = True

        print()
        print("[3/4] Query Test...")
        print(f"  {BLUE}Skipped (SQLite){NC}")
        results['db_query'] = True
        print()

    # 5. 요약
    print_summary(results)

    # 종료 코드 (모두 성공: 0, 일부 실패: 1)
    sys.exit(0 if all(results.values()) else 1)


if __name__ == "__main__":
    main()
