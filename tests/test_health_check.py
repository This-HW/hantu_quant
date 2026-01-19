"""
의존성 헬스체크 테스트 (P2-3)

테스트 항목:
1. 헬스체크 응답 구조
2. 상태 판단 로직
3. 시스템 메트릭 조회
4. 의존성 체크 함수
"""

import pytest
import asyncio
from unittest.mock import MagicMock
from pathlib import Path
import sys
import time
import tempfile

# 프로젝트 루트 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.utils.health_check import (
    HealthCheckResult,
    SystemMetrics,
    HealthStatus,
    get_system_metrics,
    check_database_health,
    check_kis_api_health,
    check_websocket_health,
    determine_health_status,
    perform_health_check,
    PSUTIL_AVAILABLE,
)


class TestHealthCheckResult:
    """HealthCheckResult 테스트"""

    def test_create_healthy_result(self):
        """정상 결과 생성"""
        result = HealthCheckResult(
            healthy=True,
            message="OK"
        )
        assert result.healthy is True
        assert result.message == "OK"
        assert result.latency_ms == 0.0

    def test_create_unhealthy_result(self):
        """비정상 결과 생성"""
        result = HealthCheckResult(
            healthy=False,
            message="Connection failed",
            latency_ms=150.5
        )
        assert result.healthy is False
        assert "Connection failed" in result.message
        assert result.latency_ms == 150.5


class TestSystemMetrics:
    """SystemMetrics 테스트"""

    def test_create_metrics(self):
        """메트릭 생성"""
        metrics = SystemMetrics(
            memory_percent=50.0,
            cpu_percent=30.0,
            disk_percent=60.0
        )
        assert metrics.memory_percent == 50.0
        assert metrics.cpu_percent == 30.0
        assert metrics.disk_percent == 60.0


class TestHealthStatus:
    """HealthStatus 테스트"""

    def test_create_healthy_status(self):
        """healthy 상태 생성"""
        status = HealthStatus(
            status='healthy',
            database=True,
            kis_api=True,
            websocket=True,
            memory_percent=50.0,
            cpu_percent=30.0,
            disk_percent=60.0,
            uptime_seconds=3600.0,
            checks={},
            timestamp='2025-01-01T00:00:00'
        )
        assert status.status == 'healthy'
        assert status.database is True
        assert status.kis_api is True
        assert status.websocket is True

    def test_create_degraded_status(self):
        """degraded 상태 생성"""
        status = HealthStatus(
            status='degraded',
            database=True,
            kis_api=False,
            websocket=True,
            memory_percent=50.0,
            cpu_percent=30.0,
            disk_percent=60.0,
            uptime_seconds=3600.0,
            checks={},
            timestamp='2025-01-01T00:00:00'
        )
        assert status.status == 'degraded'
        assert status.kis_api is False

    def test_create_unhealthy_status(self):
        """unhealthy 상태 생성"""
        status = HealthStatus(
            status='unhealthy',
            database=False,
            kis_api=False,
            websocket=False,
            memory_percent=50.0,
            cpu_percent=30.0,
            disk_percent=60.0,
            uptime_seconds=3600.0,
            checks={},
            timestamp='2025-01-01T00:00:00'
        )
        assert status.status == 'unhealthy'

    def test_to_dict(self):
        """딕셔너리 변환"""
        status = HealthStatus(
            status='healthy',
            database=True,
            kis_api=True,
            websocket=True,
            memory_percent=50.0,
            cpu_percent=30.0,
            disk_percent=60.0,
            uptime_seconds=3600.0,
            checks={'database': {'healthy': True}},
            timestamp='2025-01-01T00:00:00'
        )
        d = status.to_dict()
        assert d['status'] == 'healthy'
        assert d['memory_percent'] == 50.0
        assert 'database' in d['checks']


class TestGetSystemMetrics:
    """get_system_metrics 테스트"""

    def test_returns_metrics(self):
        """메트릭 반환"""
        metrics = get_system_metrics()
        assert isinstance(metrics, SystemMetrics)

    def test_metrics_have_valid_range(self):
        """메트릭 값 범위"""
        metrics = get_system_metrics()
        assert 0 <= metrics.memory_percent <= 100
        assert 0 <= metrics.cpu_percent <= 100
        assert 0 <= metrics.disk_percent <= 100

    def test_psutil_available_flag(self):
        """psutil 사용 가능 여부"""
        # PSUTIL_AVAILABLE이 True/False 중 하나
        assert isinstance(PSUTIL_AVAILABLE, bool)


class TestDetermineHealthStatus:
    """determine_health_status 테스트"""

    def test_all_healthy(self):
        """모든 의존성 정상 -> healthy"""
        status = determine_health_status(
            db_healthy=True,
            api_healthy=True,
            ws_healthy=True
        )
        assert status == 'healthy'

    def test_partial_healthy_db_api(self):
        """DB, API만 정상 -> degraded"""
        status = determine_health_status(
            db_healthy=True,
            api_healthy=True,
            ws_healthy=False
        )
        assert status == 'degraded'

    def test_partial_healthy_only_db(self):
        """DB만 정상 -> degraded"""
        status = determine_health_status(
            db_healthy=True,
            api_healthy=False,
            ws_healthy=False
        )
        assert status == 'degraded'

    def test_partial_healthy_only_api(self):
        """API만 정상 -> degraded"""
        status = determine_health_status(
            db_healthy=False,
            api_healthy=True,
            ws_healthy=False
        )
        assert status == 'degraded'

    def test_partial_healthy_only_ws(self):
        """WebSocket만 정상 -> degraded"""
        status = determine_health_status(
            db_healthy=False,
            api_healthy=False,
            ws_healthy=True
        )
        assert status == 'degraded'

    def test_none_healthy(self):
        """모든 의존성 장애 -> unhealthy"""
        status = determine_health_status(
            db_healthy=False,
            api_healthy=False,
            ws_healthy=False
        )
        assert status == 'unhealthy'


class TestCheckDatabaseHealth:
    """check_database_health 테스트"""

    def test_existing_directory(self):
        """존재하는 디렉토리"""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = asyncio.get_event_loop().run_until_complete(
                check_database_health(Path(temp_dir))
            )
            assert result.healthy is True
            assert "accessible" in result.message.lower()

    def test_non_existing_directory(self):
        """존재하지 않는 디렉토리"""
        result = asyncio.get_event_loop().run_until_complete(
            check_database_health(Path("/non/existing/path"))
        )
        assert result.healthy is False
        assert "not found" in result.message.lower()

    def test_default_data_directory(self):
        """기본 데이터 디렉토리"""
        result = asyncio.get_event_loop().run_until_complete(
            check_database_health()
        )
        # 프로젝트 data 디렉토리 존재 여부에 따라
        assert isinstance(result, HealthCheckResult)
        assert isinstance(result.healthy, bool)


class TestCheckKisApiHealth:
    """check_kis_api_health 테스트"""

    def test_no_client(self):
        """클라이언트 없음"""
        result = asyncio.get_event_loop().run_until_complete(
            check_kis_api_health(None)
        )
        assert result.healthy is False
        assert "not initialized" in result.message.lower()

    def test_successful_connection(self):
        """성공적인 연결"""
        mock_client = MagicMock()
        mock_client.get_current_price.return_value = {"success": True}

        result = asyncio.get_event_loop().run_until_complete(
            check_kis_api_health(mock_client)
        )
        assert result.healthy is True
        assert result.message == "Connected"
        assert result.latency_ms >= 0

    def test_failed_connection(self):
        """실패한 연결"""
        mock_client = MagicMock()
        mock_client.get_current_price.side_effect = Exception("Connection refused")

        result = asyncio.get_event_loop().run_until_complete(
            check_kis_api_health(mock_client)
        )
        assert result.healthy is False
        assert "Connection refused" in result.message

    def test_no_response(self):
        """응답 없음"""
        mock_client = MagicMock()
        mock_client.get_current_price.return_value = None

        result = asyncio.get_event_loop().run_until_complete(
            check_kis_api_health(mock_client)
        )
        assert result.healthy is False
        assert "No response" in result.message


class TestCheckWebSocketHealth:
    """check_websocket_health 테스트"""

    def test_no_client(self):
        """클라이언트 없음 (기본 ready)"""
        result = asyncio.get_event_loop().run_until_complete(
            check_websocket_health(None)
        )
        assert result.healthy is True
        assert "ready" in result.message.lower()

    def test_with_client(self):
        """클라이언트 있음"""
        mock_ws = MagicMock()

        result = asyncio.get_event_loop().run_until_complete(
            check_websocket_health(mock_ws)
        )
        assert result.healthy is True
        assert "connected" in result.message.lower()


class TestPerformHealthCheck:
    """perform_health_check 통합 테스트"""

    def test_full_health_check(self):
        """전체 헬스체크"""
        with tempfile.TemporaryDirectory() as temp_dir:
            mock_kis = MagicMock()
            mock_kis.get_current_price.return_value = {"success": True}

            mock_ws = MagicMock()

            start_time = time.time() - 3600  # 1시간 전

            result = asyncio.get_event_loop().run_until_complete(
                perform_health_check(
                    kis_client=mock_kis,
                    ws_client=mock_ws,
                    data_dir=Path(temp_dir),
                    server_start_time=start_time
                )
            )

            assert isinstance(result, HealthStatus)
            assert result.status == 'healthy'
            assert result.database is True
            assert result.kis_api is True
            assert result.websocket is True
            assert result.uptime_seconds >= 3600

    def test_degraded_health_check(self):
        """일부 실패 헬스체크"""
        with tempfile.TemporaryDirectory() as temp_dir:
            mock_kis = MagicMock()
            mock_kis.get_current_price.side_effect = Exception("API Error")

            result = asyncio.get_event_loop().run_until_complete(
                perform_health_check(
                    kis_client=mock_kis,
                    ws_client=None,
                    data_dir=Path(temp_dir),
                    server_start_time=time.time()
                )
            )

            assert result.status == 'degraded'
            assert result.database is True
            assert result.kis_api is False
            assert result.websocket is True

    def test_unhealthy_check(self):
        """모두 실패 헬스체크"""
        mock_kis = MagicMock()
        mock_kis.get_current_price.side_effect = Exception("API Error")

        result = asyncio.get_event_loop().run_until_complete(
            perform_health_check(
                kis_client=mock_kis,
                ws_client=None,
                data_dir=Path("/non/existing/path"),
                server_start_time=time.time()
            )
        )

        # DB와 WebSocket 실패, API도 실패
        # WebSocket은 None이면 기본 ready 반환
        assert result.kis_api is False
        assert result.database is False

    def test_checks_dict_structure(self):
        """checks 딕셔너리 구조"""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = asyncio.get_event_loop().run_until_complete(
                perform_health_check(
                    data_dir=Path(temp_dir)
                )
            )

            assert 'database' in result.checks
            assert 'kis_api' in result.checks
            assert 'websocket' in result.checks

            for key, value in result.checks.items():
                assert 'healthy' in value
                assert 'message' in value

    def test_timestamp_format(self):
        """타임스탬프 형식"""
        result = asyncio.get_event_loop().run_until_complete(
            perform_health_check()
        )

        # ISO 형식 확인
        assert 'T' in result.timestamp
        assert len(result.timestamp) >= 19  # 최소 YYYY-MM-DDTHH:MM:SS


class TestEdgeCases:
    """엣지 케이스 테스트"""

    def test_metrics_without_psutil(self):
        """psutil 없을 때"""
        # get_system_metrics가 예외 없이 동작해야 함
        metrics = get_system_metrics()
        assert metrics is not None

    def test_uptime_without_start_time(self):
        """시작 시간 없을 때"""
        result = asyncio.get_event_loop().run_until_complete(
            perform_health_check(server_start_time=None)
        )
        assert result.uptime_seconds == 0.0

    def test_concurrent_health_checks(self):
        """동시 헬스체크"""
        async def run_checks():
            tasks = [perform_health_check() for _ in range(5)]
            results = await asyncio.gather(*tasks)
            return results

        results = asyncio.get_event_loop().run_until_complete(run_checks())

        assert len(results) == 5
        for result in results:
            assert isinstance(result, HealthStatus)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
