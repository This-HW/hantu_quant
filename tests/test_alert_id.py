"""
Story 1.1: Alert 클래스 버그 수정 테스트

T-1.1.1: Alert.id 필드 추가
T-1.1.2: __post_init__에서 UUID 기반 자동 ID 생성
T-1.1.3: MockNotifier, TelegramNotifier의 alert.id 참조 코드 수정
"""

import pytest
import re
from datetime import datetime

from core.notification.alert import Alert, AlertType, AlertLevel, AlertFormatter
from core.notification.notifier import MockNotifier, NotifierConfig, NotificationResult
from core.notification.telegram_bot import TelegramNotifier, TelegramConfig


class TestAlertId:
    """Alert.id 필드 테스트"""

    def test_alert_has_id_field(self):
        """Alert 인스턴스가 id 필드를 가지는지 확인"""
        alert = Alert(
            alert_type=AlertType.SYSTEM_START,
            level=AlertLevel.INFO,
            title="테스트",
            message="테스트 메시지"
        )
        assert hasattr(alert, 'id')
        assert alert.id is not None

    def test_alert_id_auto_generated(self):
        """Alert 생성 시 id가 자동으로 할당되는지 확인"""
        alert = Alert(
            alert_type=AlertType.SYSTEM_START,
            level=AlertLevel.INFO,
            title="테스트",
            message="테스트 메시지"
        )
        assert alert.id is not None
        assert len(alert.id) > 0

    def test_alert_id_is_12_char_hex(self):
        """id 값이 12자리 hex 문자열인지 확인"""
        alert = Alert(
            alert_type=AlertType.SYSTEM_START,
            level=AlertLevel.INFO,
            title="테스트",
            message="테스트 메시지"
        )
        # 12자리 확인
        assert len(alert.id) == 12
        # hex 문자열 확인 (0-9, a-f)
        assert re.match(r'^[0-9a-f]{12}$', alert.id)

    def test_different_alerts_have_different_ids(self):
        """두 Alert 인스턴스의 id가 서로 다른지 확인"""
        alert1 = Alert(
            alert_type=AlertType.SYSTEM_START,
            level=AlertLevel.INFO,
            title="테스트 1",
            message="테스트 메시지 1"
        )
        alert2 = Alert(
            alert_type=AlertType.SYSTEM_START,
            level=AlertLevel.INFO,
            title="테스트 2",
            message="테스트 메시지 2"
        )
        assert alert1.id != alert2.id

    def test_alert_to_dict_includes_id(self):
        """to_dict()에 id가 포함되는지 확인"""
        alert = Alert(
            alert_type=AlertType.SYSTEM_START,
            level=AlertLevel.INFO,
            title="테스트",
            message="테스트 메시지"
        )
        alert_dict = alert.to_dict()
        assert 'id' in alert_dict
        assert alert_dict['id'] == alert.id

    def test_custom_id_can_be_set(self):
        """사용자 지정 id 설정 가능한지 확인"""
        custom_id = "custom123456"
        alert = Alert(
            alert_type=AlertType.SYSTEM_START,
            level=AlertLevel.INFO,
            title="테스트",
            message="테스트 메시지",
            id=custom_id
        )
        assert alert.id == custom_id


class TestMockNotifierWithAlertId:
    """MockNotifier가 alert.id를 정상 사용하는지 테스트"""

    def test_mock_notifier_send_no_attribute_error(self):
        """MockNotifier.send() 호출 시 AttributeError 발생하지 않음"""
        notifier = MockNotifier()
        alert = Alert(
            alert_type=AlertType.SYSTEM_START,
            level=AlertLevel.INFO,
            title="테스트",
            message="테스트 메시지"
        )

        # AttributeError 없이 정상 실행
        result = notifier.send(alert)

        assert isinstance(result, NotificationResult)
        assert result.success is True
        assert result.alert_id == alert.id

    def test_mock_notifier_send_filtered_returns_alert_id(self):
        """필터링된 알림도 alert.id 반환"""
        config = NotifierConfig(min_level=AlertLevel.WARNING)
        notifier = MockNotifier(config)

        # INFO 레벨 알림 (WARNING 이하라 필터링됨)
        alert = Alert(
            alert_type=AlertType.SYSTEM_START,
            level=AlertLevel.DEBUG,
            title="테스트",
            message="테스트 메시지"
        )

        result = notifier.send(alert)

        assert result.success is False
        assert result.alert_id == alert.id


class TestTelegramNotifierWithAlertId:
    """TelegramNotifier가 alert.id를 정상 사용하는지 테스트"""

    def test_telegram_notifier_send_no_attribute_error(self):
        """TelegramNotifier.send() 호출 시 AttributeError 발생하지 않음"""
        # 설정되지 않은 Notifier
        notifier = TelegramNotifier()
        alert = Alert(
            alert_type=AlertType.SYSTEM_START,
            level=AlertLevel.INFO,
            title="테스트",
            message="테스트 메시지"
        )

        # AttributeError 없이 정상 실행
        result = notifier.send(alert)

        assert isinstance(result, NotificationResult)
        assert result.success is False  # 설정되지 않아서 실패
        assert result.alert_id == alert.id

    def test_telegram_notifier_filtered_returns_alert_id(self):
        """필터링된 알림도 alert.id 반환"""
        config = TelegramConfig(
            bot_token="test_token",
            chat_id="test_chat",
            min_level=AlertLevel.WARNING
        )
        notifier = TelegramNotifier(config)

        # DEBUG 레벨 알림 (필터링됨)
        alert = Alert(
            alert_type=AlertType.SYSTEM_START,
            level=AlertLevel.DEBUG,
            title="테스트",
            message="테스트 메시지"
        )

        result = notifier.send(alert)

        assert result.success is False
        assert result.alert_id == alert.id


class TestAlertFormatterWithId:
    """AlertFormatter로 생성된 Alert도 id를 가지는지 테스트"""

    def test_format_trade_entry_has_id(self):
        """format_trade_entry로 생성된 Alert에 id 존재"""
        alert = AlertFormatter.format_trade_entry(
            stock_code="005930",
            stock_name="삼성전자",
            direction="buy",
            price=70000,
            quantity=10,
            signal_source=["RSI", "MACD"],
            confidence=0.85
        )
        assert alert.id is not None
        assert len(alert.id) == 12

    def test_format_system_status_has_id(self):
        """format_system_status로 생성된 Alert에 id 존재"""
        alert = AlertFormatter.format_system_status(
            status="start",
            message="시스템 시작됨"
        )
        assert alert.id is not None
        assert len(alert.id) == 12

    def test_format_circuit_breaker_has_id(self):
        """format_circuit_breaker로 생성된 Alert에 id 존재"""
        alert = AlertFormatter.format_circuit_breaker(
            reason="일간 손실 한도 초과",
            triggered_at=datetime.now()
        )
        assert alert.id is not None
        assert len(alert.id) == 12


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
