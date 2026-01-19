"""
알림 시스템 통합 테스트

Feature 4.1: 알림 시스템 테스트 구축
- T-4.1.1: NotificationManager 단위 테스트
- T-4.1.2: TelegramNotifier Mock 기반 단위 테스트
- T-4.1.3: AlertFormatter 단위 테스트
- T-4.1.4: 알림 시스템 통합 테스트
"""

import pytest
import os
import json
import tempfile
from unittest.mock import Mock, patch, MagicMock

from core.notification.alert import (
    Alert,
    AlertType,
    AlertLevel,
    AlertFormatter,
)
from core.notification.telegram_bot import (
    TelegramNotifier,
    TelegramConfig,
)
from core.notification.config_loader import (
    TelegramConfigLoader,
)
from core.notification.notification_history import (
    NotificationHistoryDB,
    NotificationHistoryEntry,
)
from core.notification.channels import (
    BaseNotificationChannel,
    TelegramChannel,
    ChannelRegistry,
    ChannelType,
    ChannelStatus,
)


class TestAlertFormatter:
    """AlertFormatter 단위 테스트"""

    def test_format_telegram_trade_entry(self):
        """거래 진입 알림 포맷"""
        alert = Alert(
            alert_type=AlertType.TRADE_ENTRY,
            level=AlertLevel.INFO,
            title="매수 주문 체결",
            message="삼성전자 10주 매수 완료",
            data={"stock_code": "005930", "quantity": 10}
        )

        formatted = AlertFormatter.format_telegram(alert)

        assert "매수 주문 체결" in formatted
        assert "삼성전자" in formatted

    def test_format_telegram_system_error(self):
        """시스템 에러 알림 포맷"""
        alert = Alert(
            alert_type=AlertType.SYSTEM_ERROR,
            level=AlertLevel.CRITICAL,
            title="시스템 오류",
            message="API 연결 실패",
        )

        formatted = AlertFormatter.format_telegram(alert)

        assert "시스템 오류" in formatted
        assert "API 연결 실패" in formatted

    def test_format_telegram_with_data(self):
        """데이터 포함 알림 포맷"""
        alert = Alert(
            alert_type=AlertType.SIGNAL_BUY,
            level=AlertLevel.INFO,
            title="매수 신호",
            message="기술적 신호 발생",
            data={"signal_strength": 0.85, "indicator": "MACD"}
        )

        formatted = AlertFormatter.format_telegram(alert)
        assert "매수 신호" in formatted


class TestNotificationHistory:
    """알림 이력 테스트"""

    def setup_method(self):
        """테스트 전 임시 DB 생성"""
        self.temp_file = tempfile.NamedTemporaryFile(
            suffix='.db', delete=False
        )
        self.db_path = self.temp_file.name
        self.temp_file.close()
        self.db = NotificationHistoryDB(self.db_path)

    def teardown_method(self):
        """테스트 후 정리"""
        try:
            os.unlink(self.db_path)
        except:
            pass

    def test_save_and_retrieve(self):
        """저장 및 조회"""
        entry = NotificationHistoryEntry(
            alert_id="test_123",
            alert_type="TRADE_ENTRY",
            level="INFO",
            title="테스트 알림",
            message="테스트 메시지",
            channel="telegram",
            status="sent",
        )

        entry_id = self.db.save(entry)
        assert entry_id > 0

        retrieved = self.db.get_by_id(entry_id)
        assert retrieved is not None
        assert retrieved.alert_id == "test_123"
        assert retrieved.status == "sent"

    def test_get_by_alert_id(self):
        """알림 ID로 조회"""
        for i in range(3):
            entry = NotificationHistoryEntry(
                alert_id="alert_same",
                alert_type="SYSTEM_ERROR",
                level="ERROR",
                title=f"에러 {i}",
                message=f"메시지 {i}",
                channel="telegram",
                status="sent" if i < 2 else "failed",
            )
            self.db.save(entry)

        entries = self.db.get_by_alert_id("alert_same")
        assert len(entries) == 3

    def test_get_recent(self):
        """최근 이력 조회"""
        for i in range(5):
            entry = NotificationHistoryEntry(
                alert_id=f"alert_{i}",
                alert_type="INFO",
                level="INFO",
                title=f"알림 {i}",
                message="",
                channel="telegram",
                status="sent",
            )
            self.db.save(entry)

        recent = self.db.get_recent(limit=3)
        assert len(recent) == 3

    def test_get_failed(self):
        """실패 알림 조회"""
        self.db.save(NotificationHistoryEntry(
            alert_id="success_1",
            alert_type="INFO",
            level="INFO",
            title="성공",
            message="",
            channel="telegram",
            status="sent",
        ))

        self.db.save(NotificationHistoryEntry(
            alert_id="fail_1",
            alert_type="ERROR",
            level="ERROR",
            title="실패",
            message="",
            channel="telegram",
            status="failed",
            error_message="Network error",
        ))

        failed = self.db.get_failed()
        assert len(failed) == 1
        assert failed[0].alert_id == "fail_1"

    def test_get_stats_summary(self):
        """통계 요약"""
        for status in ["sent", "sent", "failed", "filtered"]:
            self.db.save(NotificationHistoryEntry(
                alert_id=f"alert_{status}",
                alert_type="INFO",
                level="INFO",
                title="테스트",
                message="",
                channel="telegram",
                status=status,
            ))

        summary = self.db.get_stats_summary(days=1)
        assert summary["total"] == 4
        assert summary["sent"] == 2
        assert summary["failed"] == 1


class TestChannelRegistry:
    """채널 레지스트리 테스트"""

    def setup_method(self):
        """테스트 전 레지스트리 초기화"""
        self.registry = ChannelRegistry()

    def test_register_and_get(self):
        """채널 등록 및 조회"""
        mock_channel = Mock(spec=BaseNotificationChannel)
        mock_channel.name = "test_channel"
        mock_channel.channel_type = ChannelType.TELEGRAM
        mock_channel.status = ChannelStatus.ACTIVE
        mock_channel.is_configured.return_value = True

        self.registry.register(mock_channel)

        retrieved = self.registry.get("test_channel")
        assert retrieved is mock_channel

    def test_get_by_type(self):
        """타입별 채널 조회"""
        telegram1 = Mock(spec=BaseNotificationChannel)
        telegram1.name = "telegram1"
        telegram1.channel_type = ChannelType.TELEGRAM

        telegram2 = Mock(spec=BaseNotificationChannel)
        telegram2.name = "telegram2"
        telegram2.channel_type = ChannelType.TELEGRAM

        email = Mock(spec=BaseNotificationChannel)
        email.name = "email1"
        email.channel_type = ChannelType.EMAIL

        self.registry.register(telegram1)
        self.registry.register(telegram2)
        self.registry.register(email)

        telegram_channels = self.registry.get_by_type(ChannelType.TELEGRAM)
        assert len(telegram_channels) == 2

    def test_list_channels(self):
        """채널 목록 조회"""
        mock_channel = Mock(spec=BaseNotificationChannel)
        mock_channel.name = "test"
        mock_channel.channel_type = ChannelType.TELEGRAM
        mock_channel.get_info.return_value = Mock()

        self.registry.register(mock_channel)

        channels = self.registry.list_channels()
        assert len(channels) == 1


class TestTelegramChannel:
    """TelegramChannel 테스트"""

    def test_is_configured_false_without_config(self):
        """설정 없이 생성 시 False"""
        channel = TelegramChannel(name="test")
        assert channel.is_configured() is False

    @patch('urllib.request.urlopen')
    def test_send_success(self, mock_urlopen):
        """발송 성공"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"ok": True}).encode()
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        # config_path로 초기화하지 않고 직접 notifier 설정
        channel = TelegramChannel(name="test")
        channel._notifier.config.bot_token = "test_token"
        channel._notifier.config.chat_id = "12345"

        alert = Alert(
            alert_type=AlertType.SYSTEM_START,
            level=AlertLevel.INFO,
            title="테스트",
            message="테스트 메시지"
        )

        result = channel.send(alert)
        assert result.success is True
        assert channel._success_count == 1


class TestIntegration:
    """통합 테스트"""

    def setup_method(self):
        """테스트 전 설정"""
        import core.notification.telegram_bot as tb
        tb._telegram_notifier_instance = None

    @patch('urllib.request.urlopen')
    def test_full_notification_flow(self, mock_urlopen):
        """전체 알림 흐름"""
        # Mock 설정
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"ok": True}).encode()
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        # TelegramNotifier 설정
        config = TelegramConfig(
            bot_token="integration_token",
            chat_id="integration_chat",
        )
        notifier = TelegramNotifier(config=config)

        # Alert 생성
        alert = Alert(
            alert_type=AlertType.TRADE_ENTRY,
            level=AlertLevel.INFO,
            title="통합 테스트",
            message="전체 알림 흐름 테스트"
        )

        # 발송
        result = notifier.send(alert)

        # 검증
        assert result.success is True
        assert result.alert_id == alert.id

    def test_config_loader_with_env(self):
        """환경변수 설정 로드"""
        import os
        os.environ["TELEGRAM_BOT_TOKEN"] = "env_test_token"
        os.environ["TELEGRAM_CHAT_ID"] = "env_test_chat"

        try:
            loader = TelegramConfigLoader()
            config = loader.load(validate=False)

            assert config.bot_token == "env_test_token"
            assert config.chat_id == "env_test_chat"
        finally:
            del os.environ["TELEGRAM_BOT_TOKEN"]
            del os.environ["TELEGRAM_CHAT_ID"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
