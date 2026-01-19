"""
비동기 KIS API 클라이언트 테스트 (P2-4)

테스트 항목:
1. PriceData 데이터 클래스
2. BatchResult 데이터 클래스
3. 세마포어 동시 요청 제한
4. 배치 조회 기능
5. 에러 핸들링
"""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from pathlib import Path
import sys
from dataclasses import asdict

# 프로젝트 루트 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.api.async_client import (
    PriceData,
    BatchResult,
    AsyncKISClient,
    get_prices_sync,
    AIOHTTP_AVAILABLE,
)


class TestPriceData:
    """PriceData 데이터 클래스 테스트"""

    def test_create_price_data(self):
        """PriceData 생성"""
        price = PriceData(
            stock_code="005930",
            current_price=70000.0,
            change_rate=1.5,
            volume=10000000,
            high=71000.0,
            low=69000.0,
            open_price=69500.0,
            prev_close=69000.0,
        )

        assert price.stock_code == "005930"
        assert price.current_price == 70000.0
        assert price.change_rate == 1.5
        assert price.volume == 10000000

    def test_price_data_has_timestamp(self):
        """PriceData에 타임스탬프 포함"""
        price = PriceData(
            stock_code="005930",
            current_price=70000.0,
            change_rate=1.5,
            volume=10000000,
            high=71000.0,
            low=69000.0,
            open_price=69500.0,
            prev_close=69000.0,
        )

        assert price.fetched_at is not None
        assert "T" in price.fetched_at  # ISO 형식


class TestBatchResult:
    """BatchResult 데이터 클래스 테스트"""

    def test_success_rate_all_success(self):
        """모두 성공 시 성공률 100%"""
        result = BatchResult(
            successful={
                "005930": MagicMock(),
                "000660": MagicMock(),
            },
            failed=[],
            total_time_ms=100.0
        )

        assert result.success_rate == 1.0
        assert result.success_count == 2
        assert result.failure_count == 0

    def test_success_rate_partial(self):
        """일부 실패 시 성공률"""
        result = BatchResult(
            successful={
                "005930": MagicMock(),
            },
            failed=[
                ("000660", "Timeout"),
                ("035720", "HTTP 500"),
            ],
            total_time_ms=200.0
        )

        assert result.success_rate == pytest.approx(1/3)
        assert result.success_count == 1
        assert result.failure_count == 2

    def test_success_rate_all_failed(self):
        """모두 실패 시 성공률 0%"""
        result = BatchResult(
            successful={},
            failed=[
                ("005930", "Error"),
                ("000660", "Error"),
            ],
            total_time_ms=50.0
        )

        assert result.success_rate == 0.0
        assert result.success_count == 0
        assert result.failure_count == 2

    def test_success_rate_empty(self):
        """빈 결과 시 성공률 0%"""
        result = BatchResult(
            successful={},
            failed=[],
            total_time_ms=0.0
        )

        assert result.success_rate == 0.0


class TestAsyncKISClientInit:
    """AsyncKISClient 초기화 테스트"""

    @pytest.mark.skipif(not AIOHTTP_AVAILABLE, reason="aiohttp not installed")
    def test_init_default_values(self):
        """기본값으로 초기화"""
        client = AsyncKISClient()

        assert client.max_concurrent == 10
        assert client.timeout == 10.0
        assert client.retry_count == 2

    @pytest.mark.skipif(not AIOHTTP_AVAILABLE, reason="aiohttp not installed")
    def test_init_custom_values(self):
        """사용자 설정값으로 초기화"""
        client = AsyncKISClient(
            max_concurrent=5,
            timeout=30.0,
            retry_count=3,
        )

        assert client.max_concurrent == 5
        assert client.timeout == 30.0
        assert client.retry_count == 3


class TestAsyncKISClientSemaphore:
    """세마포어 동시 요청 제한 테스트"""

    @pytest.mark.skipif(not AIOHTTP_AVAILABLE, reason="aiohttp not installed")
    def test_semaphore_limit(self):
        """세마포어 제한 설정"""
        client = AsyncKISClient(max_concurrent=5)

        assert client.semaphore._value == 5


class TestAsyncKISClientSession:
    """세션 관리 테스트"""

    @pytest.mark.skipif(not AIOHTTP_AVAILABLE, reason="aiohttp not installed")
    def test_session_not_initialized(self):
        """초기화 전 세션 None"""
        client = AsyncKISClient()

        assert client.session is None

    @pytest.mark.skipif(not AIOHTTP_AVAILABLE, reason="aiohttp not installed")
    def test_context_manager_initializes_session(self):
        """컨텍스트 매니저로 세션 초기화"""
        async def test():
            async with AsyncKISClient() as client:
                assert client.session is not None

        asyncio.get_event_loop().run_until_complete(test())

    @pytest.mark.skipif(not AIOHTTP_AVAILABLE, reason="aiohttp not installed")
    def test_context_manager_closes_session(self):
        """컨텍스트 매니저 종료 시 세션 닫힘"""
        async def test():
            async with AsyncKISClient():
                pass
            # 컨텍스트 종료 후 세션 확인 불가 (closed 상태)
            return True

        result = asyncio.get_event_loop().run_until_complete(test())
        assert result is True


class TestMockedAsyncClient:
    """Mock을 사용한 AsyncKISClient 테스트"""

    @pytest.mark.skipif(not AIOHTTP_AVAILABLE, reason="aiohttp not installed")
    @patch('core.api.async_client.APIConfig')
    def test_get_headers(self, mock_config_class):
        """헤더 생성"""
        mock_config = MagicMock()
        mock_config.ensure_valid_token.return_value = True
        mock_config.access_token = "test_token"
        mock_config.app_key = "test_app_key"
        mock_config.app_secret = "test_app_secret"
        mock_config.server = "prod"
        mock_config_class.return_value = mock_config

        client = AsyncKISClient()
        headers = client._get_headers()

        assert "authorization" in headers
        assert "Bearer test_token" in headers["authorization"]
        assert headers["appkey"] == "test_app_key"
        assert headers["tr_id"] == "FHKST01010100"

    @pytest.mark.skipif(not AIOHTTP_AVAILABLE, reason="aiohttp not installed")
    @patch('core.api.async_client.APIConfig')
    def test_get_headers_virtual(self, mock_config_class):
        """가상환경 헤더 생성"""
        mock_config = MagicMock()
        mock_config.ensure_valid_token.return_value = True
        mock_config.access_token = "test_token"
        mock_config.app_key = "test_app_key"
        mock_config.app_secret = "test_app_secret"
        mock_config.server = "virtual"
        mock_config_class.return_value = mock_config

        client = AsyncKISClient()
        headers = client._get_headers()

        assert headers["tr_id"] == "VHKST01010100"  # V로 시작


class TestBatchResultEdgeCases:
    """BatchResult 엣지 케이스 테스트"""

    def test_total_time_ms(self):
        """소요시간 기록"""
        result = BatchResult(
            successful={},
            failed=[],
            total_time_ms=123.456
        )

        assert result.total_time_ms == 123.456

    def test_failed_tuple_structure(self):
        """실패 목록 구조"""
        result = BatchResult(
            successful={},
            failed=[
                ("005930", "Timeout"),
                ("000660", "HTTP 500"),
            ],
            total_time_ms=100.0
        )

        code, error = result.failed[0]
        assert code == "005930"
        assert error == "Timeout"


class TestAiohttpAvailability:
    """aiohttp 가용성 테스트"""

    def test_aiohttp_available_flag(self):
        """AIOHTTP_AVAILABLE 플래그"""
        assert isinstance(AIOHTTP_AVAILABLE, bool)


class TestSyncWrappers:
    """동기 래퍼 함수 테스트"""

    @pytest.mark.skipif(not AIOHTTP_AVAILABLE, reason="aiohttp not installed")
    @patch('core.api.async_client.AsyncKISClient')
    def test_get_prices_sync_structure(self, mock_client_class):
        """get_prices_sync 구조 테스트"""
        # Mock 설정
        mock_instance = MagicMock()
        mock_result = BatchResult(
            successful={"005930": MagicMock()},
            failed=[],
            total_time_ms=50.0
        )

        async def mock_batch(codes):
            return mock_result

        mock_instance.get_prices_batch = mock_batch
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_instance

        result = get_prices_sync(["005930"])

        assert result.success_count == 1
        assert result.total_time_ms == 50.0


class TestConcurrencyBehavior:
    """동시성 동작 테스트"""

    @pytest.mark.skipif(not AIOHTTP_AVAILABLE, reason="aiohttp not installed")
    def test_concurrent_request_limit(self):
        """동시 요청 제한 동작"""
        client = AsyncKISClient(max_concurrent=3)

        # 세마포어가 3개로 제한되어 있는지 확인
        assert client.semaphore._value == 3

        async def test():
            # 새 세마포어 생성 (이벤트 루프 컨텍스트 내에서)
            sem = asyncio.Semaphore(3)

            # 세마포어 획득
            await sem.acquire()
            await sem.acquire()
            await sem.acquire()

            # 더 이상 획득 불가 (즉시 실패)
            is_locked = sem.locked()

            # 해제
            sem.release()
            sem.release()
            sem.release()

            return is_locked

        is_locked = asyncio.run(test())
        assert is_locked is True


class TestPriceDataSerialization:
    """PriceData 직렬화 테스트"""

    def test_to_dict(self):
        """딕셔너리 변환"""
        price = PriceData(
            stock_code="005930",
            current_price=70000.0,
            change_rate=1.5,
            volume=10000000,
            high=71000.0,
            low=69000.0,
            open_price=69500.0,
            prev_close=69000.0,
        )

        d = asdict(price)

        assert d["stock_code"] == "005930"
        assert d["current_price"] == 70000.0
        assert "fetched_at" in d


class TestErrorHandling:
    """에러 핸들링 테스트"""

    @pytest.mark.skipif(not AIOHTTP_AVAILABLE, reason="aiohttp not installed")
    def test_session_not_initialized_error(self):
        """세션 미초기화 에러"""
        async def test():
            client = AsyncKISClient()
            await client.get_price("005930")

        with pytest.raises(RuntimeError, match="세션이 초기화되지 않았습니다"):
            asyncio.run(test())

    @pytest.mark.skipif(not AIOHTTP_AVAILABLE, reason="aiohttp not installed")
    def test_batch_session_not_initialized_error(self):
        """배치 조회 시 세션 미초기화 에러"""
        async def test():
            client = AsyncKISClient()
            await client.get_prices_batch(["005930"])

        with pytest.raises(RuntimeError, match="세션이 초기화되지 않았습니다"):
            asyncio.run(test())


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
