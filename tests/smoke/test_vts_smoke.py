import os
import subprocess
import sys
import pytest


@pytest.mark.smoke
@pytest.mark.vts
@pytest.mark.skipif(os.getenv("ENABLE_VTS_SMOKE") != "1", reason="ENABLE_VTS_SMOKE=1 일 때만 실행")
def test_vts_smoke_script():
    """scripts/vts_smoke_test.py 가 정상 종료(코드 0)하는지 확인합니다.

    실제 모의투자 주문을 수행하므로 기본적으로는 실행되지 않고,
    환경변수 ENABLE_VTS_SMOKE=1 로 명시적으로 활성화했을 때만 동작합니다.
    """

    cmd = [sys.executable, "scripts/vts_smoke_test.py"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout)
    print(result.stderr, file=sys.stderr)
    assert result.returncode == 0, "VTS 스모크 스크립트가 실패했습니다"

