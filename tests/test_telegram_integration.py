"""
Story 1.2: TelegramNotifier 통합 테스트

T-1.2.1: 중복 TelegramNotifier 코드 통합
T-1.2.2: core/notification/telegram_bot.py를 주 구현체로 선정
T-1.2.3: 다른 위치의 TelegramNotifier 코드 제거 및 import 수정
T-1.2.4: TelegramNotifier에서 config_loader 사용하도록 수정
T-1.2.5: 알림 발송 로직에 분산 추적 적용
T-1.2.6: 알림 실패 시 에러 핸들링 강화
T-1.2.7: Story 1.2 테스트 작성 및 검증
"""

import pytest
import os
import json
import tempfile
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from core.notification.telegram_bot import (
    TelegramNotifier,
    TelegramConfig,
    get_telegram_notifier,
    send_telegram_alert,
    send_telegram_message,
)
from core.notification.alert import Alert, AlertType, AlertLevel
from core.notification.notifier import NotificationResult
from core.notification.config_loader import (
    TelegramConfigData,
    TelegramConfigLoader,
    MessageFormatConfig,
    RateLimitingConfig,
)
from core.utils.log_utils import set_trace_id, clear_trace_id


class TestTelegramNotifierInit:
    """TelegramNotifier 초기화 테스트"""

    def setup_method(self):
        """테스트 전 설정"""
        clear_trace_id()
        # 글로벌 인스턴스 초기화
        import core.notification.telegram_bot as tb
        tb._telegram_notifier_instance = None

    def test_init_with_telegram_config(self):
        """TelegramConfig로 초기화"""
        config = TelegramConfig(
            bot_token="test_token",
            chat_id="12345",
            timeout=5,
        )
        notifier = TelegramNotifier(config=config)

        assert notifier.config.bot_token == "test_token"
        assert notifier.config.chat_id == "12345"
        assert notifier.config.timeout == 5

    def test_init_with_config_data(self):
        """TelegramConfigData로 초기화"""
        config_data = TelegramConfigData(
            bot_token="test_token_data",
            chat_id="67890",
            message_format=MessageFormatConfig(use_html=True),
        )
        notifier = TelegramNotifier(config_data=config_data)

        assert notifier.config.bot_token == "test_token_data"
        assert notifier.config.chat_id == "67890"
        assert notifier.config.parse_mode == "HTML"

    def test_init_with_config_path(self):
        """설정 파일 경로로 초기화"""
        # 임시 설정 파일 생성
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False
        ) as f:
            json.dump({
                "telegram": {
                    "bot_token": "file_token",
                    "default_chat_ids": ["11111"],
                }
            }, f)
            config_path = f.name

        try:
            notifier = TelegramNotifier(config_path=config_path)
            assert notifier.config.bot_token == "file_token"
            assert notifier.config.chat_id == "11111"
        finally:
            os.unlink(config_path)

    def test_init_default(self):
        """기본 초기화 (설정 없이)"""
        notifier = TelegramNotifier()
        # 설정이 없어도 에러 발생하지 않아야 함
        assert notifier.config is not None
        assert notifier.is_configured() is False

    def test_convert_config_data_to_config(self):
        """TelegramConfigData -> TelegramConfig 변환"""
        config_data = TelegramConfigData(
            bot_token="convert_token",
            chat_id="99999",
            api_base_url="https://custom.api.telegram.org",
            timeout=30,
            max_retries=5,
            message_format=MessageFormatConfig(use_html=False, use_markdown=True),
        )
        notifier = TelegramNotifier(config_data=config_data)

        assert notifier.config.bot_token == "convert_token"
        assert notifier.config.chat_id == "99999"
        assert notifier.config.api_base_url == "https://custom.api.telegram.org"
        assert notifier.config.timeout == 30
        assert notifier.config.max_retries == 5
        assert notifier.config.parse_mode == "Markdown"


class TestTelegramNotifierIsConfigured:
    """is_configured() 메서드 테스트"""

    def test_is_configured_with_both(self):
        """토큰과 채팅 ID 모두 있으면 True"""
        config = TelegramConfig(bot_token="token", chat_id="123")
        notifier = TelegramNotifier(config=config)
        assert notifier.is_configured() is True

    def test_is_configured_without_token(self):
        """토큰 없으면 False"""
        config = TelegramConfig(bot_token="", chat_id="123")
        notifier = TelegramNotifier(config=config)
        assert notifier.is_configured() is False

    def test_is_configured_without_chat_id(self):
        """채팅 ID 없으면 False"""
        config = TelegramConfig(bot_token="token", chat_id="")
        notifier = TelegramNotifier(config=config)
        assert notifier.is_configured() is False


class TestTelegramNotifierSend:
    """send() 메서드 테스트"""

    def setup_method(self):
        clear_trace_id()

    def test_send_not_configured(self):
        """설정되지 않은 상태에서 발송"""
        notifier = TelegramNotifier()
        alert = Alert(
            alert_type=AlertType.SYSTEM_START,
            level=AlertLevel.INFO,
            title="테스트",
            message="테스트 메시지"
        )

        result = notifier.send(alert)

        assert result.success is False
        assert result.alert_id == alert.id
        assert "not configured" in result.error

    def test_send_filtered_out(self):
        """필터링되어 발송 안됨"""
        config = TelegramConfig(
            bot_token="token",
            chat_id="123",
            min_level=AlertLevel.WARNING,
        )
        notifier = TelegramNotifier(config=config)

        # DEBUG 레벨은 필터링됨
        alert = Alert(
            alert_type=AlertType.SYSTEM_START,
            level=AlertLevel.DEBUG,
            title="테스트",
            message="테스트 메시지"
        )

        result = notifier.send(alert)

        assert result.success is False
        assert "filtered out" in result.error

    @patch('urllib.request.urlopen')
    def test_send_success(self, mock_urlopen):
        """발송 성공"""
        # Mock 응답 설정
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "ok": True,
            "result": {"message_id": 123}
        }).encode('utf-8')
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        config = TelegramConfig(bot_token="token", chat_id="123")
        notifier = TelegramNotifier(config=config)

        alert = Alert(
            alert_type=AlertType.SYSTEM_START,
            level=AlertLevel.INFO,
            title="테스트",
            message="테스트 메시지"
        )

        result = notifier.send(alert)

        assert result.success is True
        assert result.alert_id == alert.id
        assert notifier._send_count == 1

    @patch('urllib.request.urlopen')
    def test_send_with_trace_id(self, mock_urlopen):
        """trace_id와 함께 발송"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"ok": True}).encode('utf-8')
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        set_trace_id("test-trace-123")

        config = TelegramConfig(bot_token="token", chat_id="123")
        notifier = TelegramNotifier(config=config)

        alert = Alert(
            alert_type=AlertType.SYSTEM_START,
            level=AlertLevel.INFO,
            title="테스트",
            message="테스트 메시지"
        )

        result = notifier.send(alert)
        assert result.success is True


class TestTelegramNotifierSendMessage:
    """_send_message() 메서드 테스트"""

    def setup_method(self):
        clear_trace_id()

    @patch('urllib.request.urlopen')
    def test_send_message_api_error(self, mock_urlopen):
        """API 에러 응답"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "ok": False,
            "description": "Bad Request"
        }).encode('utf-8')
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        config = TelegramConfig(bot_token="token", chat_id="123", max_retries=0)
        notifier = TelegramNotifier(config=config)

        result = notifier._send_message("test", "test_id")

        assert result.success is False
        assert "Bad Request" in result.error

    @patch('urllib.request.urlopen')
    def test_send_message_http_error(self, mock_urlopen):
        """HTTP 에러"""
        import urllib.error
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="test", code=500, msg="Server Error",
            hdrs=None, fp=None
        )

        config = TelegramConfig(bot_token="token", chat_id="123", max_retries=0)
        notifier = TelegramNotifier(config=config)

        result = notifier._send_message("test", "test_id")

        assert result.success is False
        assert "HTTP error" in result.error

    @patch('urllib.request.urlopen')
    def test_send_message_retry(self, mock_urlopen):
        """재시도 로직"""
        import urllib.error

        # 첫 번째는 실패, 두 번째는 성공
        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise urllib.error.URLError("Connection refused")
            else:
                mock_response = MagicMock()
                mock_response.read.return_value = json.dumps({"ok": True}).encode('utf-8')
                mock_response.__enter__ = Mock(return_value=mock_response)
                mock_response.__exit__ = Mock(return_value=False)
                return mock_response

        mock_urlopen.side_effect = side_effect

        config = TelegramConfig(
            bot_token="token", chat_id="123",
            max_retries=2, retry_delay=0.1
        )
        notifier = TelegramNotifier(config=config)

        result = notifier._send_message("test", "test_id")

        assert result.success is True
        assert result.retry_count == 1


class TestTelegramNotifierStats:
    """통계 메서드 테스트"""

    def test_get_stats_initial(self):
        """초기 통계"""
        notifier = TelegramNotifier()
        stats = notifier.get_stats()

        assert stats["send_count"] == 0
        assert stats["error_count"] == 0
        assert stats["success_rate"] == 0.0
        assert stats["last_send_time"] is None

    @patch('urllib.request.urlopen')
    def test_get_stats_after_send(self, mock_urlopen):
        """발송 후 통계"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"ok": True}).encode('utf-8')
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        config = TelegramConfig(bot_token="token", chat_id="123")
        notifier = TelegramNotifier(config=config)

        alert = Alert(
            alert_type=AlertType.SYSTEM_START,
            level=AlertLevel.INFO,
            title="테스트",
            message="테스트"
        )
        notifier.send(alert)

        stats = notifier.get_stats()
        assert stats["send_count"] == 1
        assert stats["success_rate"] == 1.0
        assert stats["last_send_time"] is not None

    def test_get_config_info(self):
        """설정 정보 조회 (마스킹)"""
        config = TelegramConfig(
            bot_token="secret_token_12345",
            chat_id="123456789",
        )
        notifier = TelegramNotifier(config=config)

        info = notifier.get_config_info()

        assert info["bot_token_set"] is True
        assert "***" in info["chat_id"]
        assert "1234" in info["chat_id"]  # 첫 4자리만 보임


class TestSingletonPattern:
    """싱글톤 패턴 테스트"""

    def setup_method(self):
        import core.notification.telegram_bot as tb
        tb._telegram_notifier_instance = None

    def test_get_telegram_notifier_singleton(self):
        """싱글톤 인스턴스"""
        notifier1 = get_telegram_notifier()
        notifier2 = get_telegram_notifier()

        assert notifier1 is notifier2

    def test_get_telegram_notifier_force_reload(self):
        """강제 재로드"""
        notifier1 = get_telegram_notifier()
        notifier2 = get_telegram_notifier(force_reload=True)

        assert notifier1 is not notifier2


class TestHelperFunctions:
    """헬퍼 함수 테스트"""

    def setup_method(self):
        import core.notification.telegram_bot as tb
        tb._telegram_notifier_instance = None

    def test_send_telegram_alert(self):
        """send_telegram_alert 헬퍼"""
        alert = Alert(
            alert_type=AlertType.SYSTEM_START,
            level=AlertLevel.INFO,
            title="테스트",
            message="테스트"
        )

        # 설정 없이 호출 (실패하지만 에러 없이)
        result = send_telegram_alert(alert)
        assert result.success is False

    def test_send_telegram_message(self):
        """send_telegram_message 헬퍼"""
        # 설정 없이 호출 (실패하지만 에러 없이)
        result = send_telegram_message("테스트 메시지")
        assert result.success is False


class TestAsyncSend:
    """비동기 발송 테스트"""

    def test_send_async_starts_worker(self):
        """비동기 발송 시 워커 시작"""
        config = TelegramConfig(bot_token="token", chat_id="123")
        notifier = TelegramNotifier(config=config)

        alert = Alert(
            alert_type=AlertType.SYSTEM_START,
            level=AlertLevel.INFO,
            title="테스트",
            message="테스트"
        )

        notifier.send_async(alert)

        assert notifier._running is True
        assert notifier._worker_thread is not None

        # 정리
        notifier._stop_worker()

    def test_stop_worker(self):
        """워커 중지"""
        config = TelegramConfig(bot_token="token", chat_id="123")
        notifier = TelegramNotifier(config=config)

        notifier._start_worker()
        assert notifier._running is True

        notifier._stop_worker()
        assert notifier._running is False


class TestSendRaw:
    """send_raw() 테스트"""

    def test_send_raw_not_configured(self):
        """설정 없이 raw 발송"""
        notifier = TelegramNotifier()
        result = notifier.send_raw("테스트 메시지")

        assert result.success is False
        assert "not configured" in result.error

    @patch('urllib.request.urlopen')
    def test_send_raw_success(self, mock_urlopen):
        """raw 메시지 발송 성공"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"ok": True}).encode('utf-8')
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        config = TelegramConfig(bot_token="token", chat_id="123")
        notifier = TelegramNotifier(config=config)

        result = notifier.send_raw("원시 메시지")

        assert result.success is True
        assert result.alert_id == "raw"


class TestConnectionTest:
    """연결 테스트 메서드 테스트"""

    def test_test_connection_not_configured(self):
        """설정 없이 연결 테스트"""
        notifier = TelegramNotifier()
        result = notifier.test_connection()

        assert result["success"] is False
        assert "Not configured" in result["error"]

    @patch('urllib.request.urlopen')
    def test_test_connection_success(self, mock_urlopen):
        """연결 테스트 성공"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "ok": True,
            "result": {
                "first_name": "TestBot",
                "username": "test_bot"
            }
        }).encode('utf-8')
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        config = TelegramConfig(bot_token="token", chat_id="123")
        notifier = TelegramNotifier(config=config)

        result = notifier.test_connection()

        assert result["success"] is True
        assert result["bot_name"] == "TestBot"
        assert result["bot_username"] == "test_bot"


class TestIntegration:
    """통합 테스트"""

    def setup_method(self):
        clear_trace_id()
        import core.notification.telegram_bot as tb
        tb._telegram_notifier_instance = None

    @patch('urllib.request.urlopen')
    def test_full_send_flow(self, mock_urlopen):
        """전체 발송 흐름"""
        # Mock 설정
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "ok": True,
            "result": {"message_id": 999}
        }).encode('utf-8')
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        # trace_id 설정
        set_trace_id("integration-test-trace")

        # TelegramConfigData로 초기화
        config_data = TelegramConfigData(
            bot_token="integration_token",
            chat_id="integration_chat",
            message_format=MessageFormatConfig(use_html=True),
        )
        notifier = TelegramNotifier(config_data=config_data)

        # Alert 발송
        alert = Alert(
            alert_type=AlertType.TRADE_ENTRY,
            level=AlertLevel.INFO,
            title="매수 주문",
            message="삼성전자 10주 매수",
            data={"stock_code": "005930", "quantity": 10}
        )

        result = notifier.send(alert)

        # 검증
        assert result.success is True
        assert result.alert_id == alert.id

        stats = notifier.get_stats()
        assert stats["send_count"] == 1
        assert stats["error_count"] == 0

    @patch('urllib.request.urlopen')
    def test_error_handling_flow(self, mock_urlopen):
        """에러 핸들링 흐름"""
        import urllib.error

        # 계속 실패하도록 설정
        mock_urlopen.side_effect = urllib.error.URLError("Network error")

        config_data = TelegramConfigData(
            bot_token="error_token",
            chat_id="error_chat",
            max_retries=1,
            retry_delay=0.01,
        )
        notifier = TelegramNotifier(config_data=config_data)

        alert = Alert(
            alert_type=AlertType.SYSTEM_ERROR,
            level=AlertLevel.WARNING,
            title="에러 알림",
            message="시스템 에러 발생"
        )

        result = notifier.send(alert)

        assert result.success is False
        assert notifier._error_count >= 1  # 에러 카운트 증가 확인

        stats = notifier.get_stats()
        assert stats["error_count"] >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
