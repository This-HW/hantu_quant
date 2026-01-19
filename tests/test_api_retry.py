"""
API 재시도 로직 테스트 (P0-1)

테스트 항목:
1. 네트워크 끊김 시뮬레이션 (ConnectionError)
2. 타임아웃 시뮬레이션 (Timeout)
3. 5xx 서버 에러 재시도
4. 4xx 클라이언트 에러 재시도 불가
5. 3회 실패 후 최종 에러 확인
"""

import pytest
from unittest.mock import patch, MagicMock
import requests

from core.api.rest_client import KISRestClient, RetryableAPIError, NonRetryableAPIError


class TestAPIRetryLogic:
    """API 재시도 로직 테스트"""

    @pytest.fixture
    def client(self):
        """KISRestClient 인스턴스 생성 (모킹)"""
        with patch("core.api.rest_client.APIConfig") as mock_config:
            mock_config_instance = MagicMock()
            mock_config_instance.ensure_valid_token.return_value = True
            mock_config.return_value = mock_config_instance

            client = KISRestClient()
            client.config = mock_config_instance
            return client

    def test_successful_request(self, client):
        """성공적인 요청 테스트"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"output": "success"}

        with patch("requests.request", return_value=mock_response):
            result = client._request("GET", "http://test.com/api")

        assert result == {"output": "success"}

    def test_connection_error_retry(self, client):
        """ConnectionError 재시도 테스트"""
        call_count = 0

        def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise requests.ConnectionError("연결 실패")
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"output": "success"}
            return mock_response

        with patch("requests.request", side_effect=mock_request):
            result = client._request("GET", "http://test.com/api")

        assert call_count == 3  # 2번 실패 후 3번째 성공
        assert result == {"output": "success"}

    def test_timeout_error_retry(self, client):
        """Timeout 에러 재시도 테스트"""
        call_count = 0

        def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise requests.Timeout("타임아웃")
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"output": "success"}
            return mock_response

        with patch("requests.request", side_effect=mock_request):
            result = client._request("GET", "http://test.com/api")

        assert call_count == 2  # 1번 실패 후 2번째 성공
        assert result == {"output": "success"}

    def test_5xx_error_retry(self, client):
        """5xx 서버 에러 재시도 테스트"""
        call_count = 0

        def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_response = MagicMock()
            if call_count < 3:
                mock_response.status_code = 503
                mock_response.text = "Service Unavailable"
            else:
                mock_response.status_code = 200
                mock_response.json.return_value = {"output": "success"}
            return mock_response

        with patch("requests.request", side_effect=mock_request):
            result = client._request("GET", "http://test.com/api")

        assert call_count == 3  # 2번 5xx 후 3번째 성공
        assert result == {"output": "success"}

    def test_4xx_error_no_retry(self, client):
        """4xx 클라이언트 에러 재시도 불가 테스트"""
        call_count = 0

        def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_response = MagicMock()
            mock_response.status_code = 400
            mock_response.text = "Bad Request"
            return mock_response

        with patch("requests.request", side_effect=mock_request):
            result = client._request("GET", "http://test.com/api")

        assert call_count == 1  # 재시도 없이 1번만 호출
        assert "error" in result
        assert not result.get("retryable")

    def test_401_unauthorized_no_retry(self, client):
        """401 인증 실패 재시도 불가 테스트"""
        call_count = 0

        def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_response.text = "Unauthorized"
            return mock_response

        with patch("requests.request", side_effect=mock_request):
            result = client._request("GET", "http://test.com/api")

        assert call_count == 1  # 재시도 없이 1번만 호출
        assert "error" in result

    def test_max_retry_exceeded(self, client):
        """최대 재시도 횟수 초과 테스트"""
        call_count = 0

        def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise requests.ConnectionError("연결 실패")

        with patch("requests.request", side_effect=mock_request):
            result = client._request("GET", "http://test.com/api")

        assert call_count == 3  # 최대 3회 시도
        assert "error" in result
        # 재시도 실패 후 원본 에러 메시지 또는 재시도 관련 메시지 확인
        error_msg = result.get("error", "")
        assert "연결" in error_msg or "Connection" in error_msg or "재시도" in error_msg

    def test_token_invalid_no_retry(self, client):
        """토큰 무효 시 재시도 불가 테스트"""
        client.config.ensure_valid_token.return_value = False

        result = client._request("GET", "http://test.com/api")

        assert "error" in result
        assert not result.get("retryable")

    def test_exponential_backoff_timing(self, client):
        """지수 백오프 타이밍 테스트 (대략적인 검증)"""
        import time

        call_times = []

        def mock_request(*args, **kwargs):
            call_times.append(time.time())
            if len(call_times) < 3:
                raise requests.ConnectionError("연결 실패")
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"output": "success"}
            return mock_response

        with patch("requests.request", side_effect=mock_request):
            start_time = time.time()
            result = client._request("GET", "http://test.com/api")
            total_time = time.time() - start_time

        # 최소 2초 + 4초 = 6초 이상 소요 (지수 백오프)
        # 실제로는 2-4초, 4-8초 범위이므로 최소 4초 이상
        assert total_time >= 4.0, f"지수 백오프 적용 확인: {total_time}초 소요"
        assert result == {"output": "success"}


class TestRetryableExceptions:
    """재시도 가능/불가능 예외 테스트"""

    def test_retryable_api_error(self):
        """RetryableAPIError 예외 테스트"""
        with pytest.raises(RetryableAPIError):
            raise RetryableAPIError("5xx 서버 에러")

    def test_non_retryable_api_error(self):
        """NonRetryableAPIError 예외 테스트"""
        with pytest.raises(NonRetryableAPIError):
            raise NonRetryableAPIError("4xx 클라이언트 에러")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
