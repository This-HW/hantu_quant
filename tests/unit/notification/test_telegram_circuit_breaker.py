"""
Telegram Circuit Breaker 테스트

Circuit Breaker 패턴이 네트워크 장애 시 올바르게 동작하는지 검증합니다.
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

from core.notification.telegram_bot import TelegramNotifier, TelegramConfig
from core.notification.alert import Alert, AlertLevel, AlertType


class TestTelegramCircuitBreaker:
    """Circuit Breaker 테스트"""

    @pytest.fixture
    def notifier(self):
        """테스트용 TelegramNotifier 인스턴스"""
        config = TelegramConfig(
            bot_token="test_token",
            chat_id="test_chat_id",
            max_retries=1,
            retry_delay=0.01,  # 테스트 속도를 위해 짧게
        )
        return TelegramNotifier(config=config)

    @pytest.fixture
    def sample_alert(self):
        """테스트용 Alert 인스턴스"""
        return Alert(
            alert_type=AlertType.SYSTEM_START,
            level=AlertLevel.INFO,
            title="테스트 알림",
            message="테스트 메시지입니다.",
        )

    def test_circuit_breaker_initial_state(self, notifier):
        """초기 상태 확인"""
        assert notifier._consecutive_failures == 0
        assert notifier._circuit_open_since is None
        assert not notifier._is_circuit_open()

    def test_circuit_breaker_opens_after_threshold(self, notifier, sample_alert):
        """임계값 초과 시 Circuit Breaker 열림"""
        # 연속 실패 기록
        for i in range(notifier._circuit_breaker_threshold):
            notifier._record_failure()

        # Circuit Breaker가 열려야 함
        assert notifier._is_circuit_open()
        assert notifier._consecutive_failures == notifier._circuit_breaker_threshold
        assert notifier._circuit_open_since is not None

    def test_circuit_breaker_blocks_requests(self, notifier, sample_alert):
        """Circuit Breaker 열린 상태에서 요청 차단"""
        # Circuit Breaker 강제 열기
        notifier._consecutive_failures = notifier._circuit_breaker_threshold
        notifier._circuit_open_since = datetime.now()

        # 요청 시도
        result = notifier.send(sample_alert)

        # 요청이 차단되어야 함
        assert not result.success
        assert "Circuit breaker open" in result.error

    def test_circuit_breaker_resets_on_success(self, notifier):
        """성공 시 Circuit Breaker 리셋"""
        # 실패 기록
        notifier._consecutive_failures = 3
        notifier._circuit_open_since = datetime.now()

        # 성공 시 리셋
        notifier._reset_circuit_breaker()

        # 상태 확인
        assert notifier._consecutive_failures == 0
        assert notifier._circuit_open_since is None
        assert not notifier._is_circuit_open()

    def test_circuit_breaker_auto_reset_after_timeout(self, notifier):
        """타임아웃 후 자동 리셋"""
        # Circuit Breaker 열기
        notifier._consecutive_failures = notifier._circuit_breaker_threshold
        # 리셋 시간 이전으로 설정
        notifier._circuit_open_since = datetime.now() - timedelta(
            seconds=notifier._circuit_breaker_reset_time + 1
        )

        # 타임아웃 후 자동 리셋되어야 함
        assert not notifier._is_circuit_open()
        assert notifier._consecutive_failures == 0

    def test_circuit_breaker_stays_open_before_timeout(self, notifier):
        """타임아웃 전에는 Circuit Breaker 유지"""
        # Circuit Breaker 열기
        notifier._consecutive_failures = notifier._circuit_breaker_threshold
        # 아직 리셋 시간 전
        notifier._circuit_open_since = datetime.now() - timedelta(seconds=10)

        # 여전히 열려있어야 함
        assert notifier._is_circuit_open()

    @patch("urllib.request.urlopen")
    def test_successful_send_resets_circuit_breaker(
        self, mock_urlopen, notifier, sample_alert
    ):
        """성공적인 전송 후 Circuit Breaker 리셋"""
        # Mock 설정 - 성공 응답
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"ok": true, "result": {}}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        # 이전에 실패가 있었음
        notifier._consecutive_failures = 2

        # 성공적인 전송
        result = notifier.send(sample_alert)

        # Circuit Breaker가 리셋되어야 함
        assert result.success
        assert notifier._consecutive_failures == 0

    @patch("urllib.request.urlopen")
    def test_failed_send_increments_failure_count(
        self, mock_urlopen, notifier, sample_alert
    ):
        """실패한 전송 시 실패 카운터 증가"""
        import urllib.error

        # Mock 설정 - 네트워크 에러
        mock_urlopen.side_effect = urllib.error.URLError("Network unreachable")

        # 초기 상태
        assert notifier._consecutive_failures == 0

        # 실패한 전송
        result = notifier.send(sample_alert)

        # 실패 카운터가 증가해야 함
        assert not result.success
        assert notifier._consecutive_failures > 0


class TestCircuitBreakerSettings:
    """Circuit Breaker 설정 테스트"""

    def test_default_threshold(self):
        """기본 임계값 확인"""
        config = TelegramConfig(bot_token="test", chat_id="test")
        notifier = TelegramNotifier(config=config)

        assert notifier._circuit_breaker_threshold == 5

    def test_default_reset_time(self):
        """기본 리셋 시간 확인 (5분 = 300초)"""
        config = TelegramConfig(bot_token="test", chat_id="test")
        notifier = TelegramNotifier(config=config)

        assert notifier._circuit_breaker_reset_time == 300
