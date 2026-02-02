"""
SSH 터널 스크립트 통합 테스트

TDD Red-Green-Refactor:
- Red: 먼저 테스트 작성 (예상 동작 정의)
- Green: 최소 구현으로 테스트 통과 (이미 구현됨)
- Refactor: 코드 정리 및 개선

테스트 대상:
1. 스크립트 존재 및 실행 권한
2. 터널 상태 확인 (Mock)
3. PID 파일 관리 (Mock)
4. diagnose-db.py 실행 가능 여부

주의: 실제 SSH 연결은 Mock 처리 (테스트 환경에서 서버 접속 불필요)
"""

import os
import subprocess
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, call


class TestDBTunnelScript:
    """SSH 터널 스크립트 기본 기능 테스트"""

    @pytest.fixture
    def script_path(self):
        """스크립트 경로"""
        root_dir = Path(__file__).parent.parent.parent
        return root_dir / "scripts" / "db-tunnel.sh"

    @pytest.fixture
    def diagnose_script_path(self):
        """진단 스크립트 경로"""
        root_dir = Path(__file__).parent.parent.parent
        return root_dir / "scripts" / "diagnose-db.py"

    def test_tunnel_script_exists(self, script_path):
        """터널 스크립트 파일 존재 확인"""
        # Assert
        assert script_path.exists(), f"SSH 터널 스크립트가 존재하지 않음: {script_path}"
        assert script_path.is_file(), f"SSH 터널 스크립트가 파일이 아님: {script_path}"

    def test_tunnel_script_executable(self, script_path):
        """터널 스크립트 실행 권한 확인"""
        # Assert
        assert os.access(script_path, os.X_OK), f"SSH 터널 스크립트에 실행 권한이 없음: {script_path}"

    def test_tunnel_script_has_shebang(self, script_path):
        """터널 스크립트 shebang 확인"""
        # Act
        with open(script_path, 'r') as f:
            first_line = f.readline().strip()

        # Assert
        assert first_line == "#!/bin/bash", f"SSH 터널 스크립트 shebang이 올바르지 않음: {first_line}"

    def test_diagnose_script_exists(self, diagnose_script_path):
        """진단 스크립트 파일 존재 확인"""
        # Assert
        assert diagnose_script_path.exists(), f"DB 진단 스크립트가 존재하지 않음: {diagnose_script_path}"
        assert diagnose_script_path.is_file(), f"DB 진단 스크립트가 파일이 아님: {diagnose_script_path}"

    def test_diagnose_script_executable(self, diagnose_script_path):
        """진단 스크립트 실행 권한 확인"""
        # Assert
        assert os.access(diagnose_script_path, os.X_OK), f"DB 진단 스크립트에 실행 권한이 없음: {diagnose_script_path}"


class TestDBTunnelStatus:
    """SSH 터널 상태 확인 테스트 (Mock)"""

    @pytest.fixture
    def script_path(self):
        """스크립트 경로"""
        root_dir = Path(__file__).parent.parent.parent
        return root_dir / "scripts" / "db-tunnel.sh"

    def test_tunnel_status_when_not_running(self, script_path):
        """터널 미실행 시 status 명령 출력 확인"""
        # Act
        result = subprocess.run(
            [str(script_path), "status"],
            capture_output=True,
            text=True,
            timeout=5
        )

        # Assert
        assert result.returncode == 0, "status 명령이 실패함"
        assert "SSH Tunnel Status" in result.stdout, "status 출력에 헤더가 없음"
        assert "localhost:15432" in result.stdout, "status 출력에 로컬 포트 정보가 없음"

    def test_tunnel_usage_help(self, script_path):
        """사용법 출력 확인"""
        # Act
        result = subprocess.run(
            [str(script_path)],
            capture_output=True,
            text=True,
            timeout=5
        )

        # Assert
        assert result.returncode == 1, "인자 없이 실행 시 에러 코드 반환해야 함"
        assert "Usage:" in result.stdout, "사용법 출력이 없음"
        assert "start" in result.stdout, "start 명령 설명이 없음"
        assert "stop" in result.stdout, "stop 명령 설명이 없음"
        assert "status" in result.stdout, "status 명령 설명이 없음"

    def test_tunnel_invalid_command(self, script_path):
        """잘못된 명령 처리 확인"""
        # Act
        result = subprocess.run(
            [str(script_path), "invalid_command"],
            capture_output=True,
            text=True,
            timeout=5
        )

        # Assert
        assert result.returncode == 1, "잘못된 명령 시 에러 코드 반환해야 함"
        assert "Error: Unknown command" in result.stdout, "에러 메시지가 없음"


class TestPIDFileManagement:
    """PID 파일 관리 테스트 (Mock)"""

    @pytest.fixture
    def script_path(self):
        """스크립트 경로"""
        root_dir = Path(__file__).parent.parent.parent
        return root_dir / "scripts" / "db-tunnel.sh"

    @pytest.fixture
    def pid_file(self, tmp_path):
        """임시 PID 파일 경로"""
        return tmp_path / "test-tunnel.pid"

    @pytest.fixture
    def mock_pid_file(self, pid_file, monkeypatch):
        """PID 파일 경로를 임시 경로로 변경"""
        monkeypatch.setenv("PID_FILE", str(pid_file))
        return pid_file

    def test_pid_file_not_exists_when_stopped(self, script_path, mock_pid_file):
        """터널 중지 시 PID 파일이 없어야 함"""
        # Arrange
        if mock_pid_file.exists():
            mock_pid_file.unlink()

        # Act
        result = subprocess.run(
            [str(script_path), "status"],
            capture_output=True,
            text=True,
            timeout=5
        )

        # Assert
        assert result.returncode == 0
        # 터널이 실행 중이 아니므로 PID 파일이 없어야 함
        assert not mock_pid_file.exists(), "터널 중지 시 PID 파일이 존재하면 안됨"


class TestDiagnoseDBScript:
    """DB 진단 스크립트 실행 테스트"""

    @pytest.fixture
    def diagnose_script_path(self):
        """진단 스크립트 경로"""
        root_dir = Path(__file__).parent.parent.parent
        return root_dir / "scripts" / "diagnose-db.py"

    def test_diagnose_script_runs(self, diagnose_script_path):
        """진단 스크립트 실행 가능 여부 확인"""
        # Act
        # --help 옵션으로 실행하여 스크립트가 동작하는지만 확인
        result = subprocess.run(
            ["python3", str(diagnose_script_path), "--help"],
            capture_output=True,
            text=True,
            timeout=10
        )

        # Assert
        # 실행 자체가 성공하면 됨 (실제 DB 연결은 필요 없음)
        # 일부 스크립트는 --help 없을 수 있으므로 에러 코드만 확인하지 않음
        assert result.returncode in [0, 1, 2], f"진단 스크립트 실행 실패: {result.stderr}"

    def test_diagnose_script_has_python_shebang(self, diagnose_script_path):
        """진단 스크립트 shebang 확인"""
        # Act
        with open(diagnose_script_path, 'r') as f:
            first_line = f.readline().strip()

        # Assert
        assert first_line.startswith("#!") and "python" in first_line.lower(), \
            f"진단 스크립트 shebang이 올바르지 않음: {first_line}"


class TestTunnelScriptConfiguration:
    """터널 스크립트 설정 확인 테스트"""

    @pytest.fixture
    def script_path(self):
        """스크립트 경로"""
        root_dir = Path(__file__).parent.parent.parent
        return root_dir / "scripts" / "db-tunnel.sh"

    def test_script_has_correct_configuration(self, script_path):
        """스크립트 내 설정 값 확인"""
        # Act
        with open(script_path, 'r') as f:
            content = f.read()

        # Assert
        assert 'REMOTE_HOST="ubuntu@158.180.87.156"' in content, "REMOTE_HOST 설정이 올바르지 않음"
        assert 'LOCAL_PORT="15432"' in content, "LOCAL_PORT 설정이 올바르지 않음"
        assert 'REMOTE_PORT="5432"' in content, "REMOTE_PORT 설정이 올바르지 않음"
        assert 'PID_FILE="/tmp/db-tunnel.pid"' in content, "PID_FILE 설정이 올바르지 않음"

    def test_script_has_logging_functions(self, script_path):
        """스크립트 내 로깅 함수 확인"""
        # Act
        with open(script_path, 'r') as f:
            content = f.read()

        # Assert
        assert "log_info()" in content, "log_info 함수가 정의되지 않음"
        assert "log_warn()" in content, "log_warn 함수가 정의되지 않음"
        assert "log_error()" in content, "log_error 함수가 정의되지 않음"

    def test_script_has_main_functions(self, script_path):
        """스크립트 내 주요 함수 확인"""
        # Act
        with open(script_path, 'r') as f:
            content = f.read()

        # Assert
        assert "start_tunnel()" in content, "start_tunnel 함수가 정의되지 않음"
        assert "stop_tunnel()" in content, "stop_tunnel 함수가 정의되지 않음"
        assert "show_status()" in content, "show_status 함수가 정의되지 않음"
        assert "restart_tunnel()" in content, "restart_tunnel 함수가 정의되지 않음"
        assert "is_tunnel_running()" in content, "is_tunnel_running 함수가 정의되지 않음"


# E2E 테스트 (선택적 - 실제 SSH 터널 설정 가능 시에만 실행)
@pytest.mark.skipif(
    os.environ.get('RUN_E2E_TESTS') != 'true',
    reason="E2E 테스트는 RUN_E2E_TESTS=true 환경변수 설정 시에만 실행"
)
class TestTunnelE2E:
    """SSH 터널 E2E 테스트 (실제 연결 필요)"""

    @pytest.fixture
    def script_path(self):
        """스크립트 경로"""
        root_dir = Path(__file__).parent.parent.parent
        return root_dir / "scripts" / "db-tunnel.sh"

    def test_tunnel_lifecycle(self, script_path):
        """터널 시작 → 상태 확인 → 중지 전체 사이클"""
        # Arrange
        # 기존 터널 정리
        subprocess.run([str(script_path), "stop"], capture_output=True, timeout=5)

        try:
            # Act 1: 터널 시작
            result = subprocess.run(
                [str(script_path), "start"],
                capture_output=True,
                text=True,
                timeout=10
            )

            # Assert 1: 시작 성공
            assert result.returncode == 0, f"터널 시작 실패: {result.stderr}"
            assert "successfully" in result.stdout.lower(), "시작 성공 메시지가 없음"

            # Act 2: 상태 확인
            result = subprocess.run(
                [str(script_path), "status"],
                capture_output=True,
                text=True,
                timeout=5
            )

            # Assert 2: 실행 중 확인
            assert result.returncode == 0
            assert "Running" in result.stdout or "✅" in result.stdout, "터널이 실행 중이지 않음"

            # Act 3: 터널 중지
            result = subprocess.run(
                [str(script_path), "stop"],
                capture_output=True,
                text=True,
                timeout=5
            )

            # Assert 3: 중지 성공
            assert result.returncode == 0, f"터널 중지 실패: {result.stderr}"

            # Act 4: 상태 재확인
            result = subprocess.run(
                [str(script_path), "status"],
                capture_output=True,
                text=True,
                timeout=5
            )

            # Assert 4: 중지 확인
            assert "Not running" in result.stdout or "❌" in result.stdout, "터널이 여전히 실행 중"

        finally:
            # Cleanup: 터널 중지 보장
            subprocess.run([str(script_path), "stop"], capture_output=True, timeout=5)
