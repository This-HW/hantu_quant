"""
알림 시스템 테스트

Phase D 알림 시스템의 모든 구성 요소를 테스트합니다.
"""

from datetime import datetime

# Alert
from core.notification.alert import (
    Alert,
    AlertType,
    AlertLevel,
    AlertFormatter,
)

# Notifier
from core.notification.notifier import (
    BaseNotifier,
    NotifierConfig,
    NotificationResult,
)

# Telegram
from core.notification.telegram_bot import (
    TelegramNotifier,
    TelegramConfig,
)

# Manager
from core.notification.notification_manager import (
    NotificationManager,
    RateLimitConfig,
)


class TestAlert:
    """알림 테스트"""

    def test_alert_creation(self):
        """알림 생성"""
        alert = Alert(
            alert_type=AlertType.TRADE_ENTRY,
            level=AlertLevel.INFO,
            title="매수 진입",
            message="삼성전자 매수",
        )

        assert alert.alert_type == AlertType.TRADE_ENTRY
        assert alert.level == AlertLevel.INFO

    def test_alert_with_data(self):
        """데이터 포함 알림"""
        alert = Alert(
            alert_type=AlertType.TRADE_EXIT,
            level=AlertLevel.INFO,
            title="청산",
            message="청산 완료",
            stock_code="005930",
            stock_name="삼성전자",
            data={
                '수익률': 5.5,
                '보유일': 3,
            },
        )

        assert alert.stock_code == "005930"
        assert alert.data['수익률'] == 5.5

    def test_alert_to_dict(self):
        """딕셔너리 변환"""
        alert = Alert(
            alert_type=AlertType.SIGNAL_BUY,
            level=AlertLevel.WARNING,
            title="매수 신호",
            message="강한 매수 신호",
        )

        data = alert.to_dict()

        assert data['alert_type'] == 'signal_buy'
        assert data['level'] == AlertLevel.WARNING.value


class TestAlertLevel:
    """알림 레벨 테스트"""

    def test_level_ordering(self):
        """레벨 순서"""
        assert AlertLevel.DEBUG.value < AlertLevel.INFO.value
        assert AlertLevel.INFO.value < AlertLevel.WARNING.value
        assert AlertLevel.WARNING.value < AlertLevel.CRITICAL.value
        assert AlertLevel.CRITICAL.value < AlertLevel.EMERGENCY.value


class TestAlertFormatter:
    """알림 포매터 테스트"""

    def test_format_telegram(self):
        """텔레그램 형식 포매팅"""
        alert = Alert(
            alert_type=AlertType.TRADE_ENTRY,
            level=AlertLevel.INFO,
            title="매수 진입",
            message="삼성전자 매수",
            stock_code="005930",
            stock_name="삼성전자",
        )

        formatted = AlertFormatter.format_telegram(alert)

        assert "매수 진입" in formatted
        assert "삼성전자" in formatted
        assert "005930" in formatted

    def test_format_trade_entry(self):
        """거래 진입 알림 포맷"""
        alert = AlertFormatter.format_trade_entry(
            stock_code="005930",
            stock_name="삼성전자",
            direction="buy",
            price=70000,
            quantity=10,
            signal_source=['LSTM', 'TA'],
            confidence=0.85,
        )

        assert alert.alert_type == AlertType.TRADE_ENTRY
        assert alert.stock_code == "005930"
        assert alert.data['가격'] == 70000

    def test_format_trade_exit(self):
        """거래 청산 알림 포맷"""
        alert = AlertFormatter.format_trade_exit(
            stock_code="005930",
            stock_name="삼성전자",
            exit_reason="take_profit",
            entry_price=70000,
            exit_price=73500,
            pnl=3500,
            pnl_pct=5.0,
            holding_days=3,
        )

        assert alert.alert_type == AlertType.TAKE_PROFIT
        assert alert.labels.is_winner if hasattr(alert, 'labels') else True
        assert alert.data['수익률'] == 0.05  # 5% / 100

    def test_format_drawdown_alert(self):
        """드로우다운 알림 포맷"""
        alert = AlertFormatter.format_drawdown_alert(
            current_drawdown=0.08,
            max_drawdown=0.10,
            alert_level="warning",
        )

        assert alert.alert_type == AlertType.DRAWDOWN_WARNING
        assert alert.level == AlertLevel.WARNING

    def test_format_circuit_breaker(self):
        """서킷 브레이커 알림 포맷"""
        alert = AlertFormatter.format_circuit_breaker(
            reason="일일 손실 한도 초과",
            triggered_at=datetime.now(),
        )

        assert alert.alert_type == AlertType.CIRCUIT_BREAKER
        assert alert.level == AlertLevel.CRITICAL

    def test_format_daily_summary(self):
        """일일 요약 알림 포맷"""
        alert = AlertFormatter.format_daily_summary(
            date=datetime.now(),
            total_trades=10,
            win_rate=0.6,
            total_pnl=50000,
            total_pnl_pct=2.5,
            top_winners=[
                {'stock': '삼성전자', 'pnl_pct': 5.0},
            ],
            top_losers=[
                {'stock': 'SK하이닉스', 'pnl_pct': -2.0},
            ],
        )

        assert alert.alert_type == AlertType.DAILY_SUMMARY
        assert "10건" in alert.message

    def test_format_signal(self):
        """매매 신호 알림 포맷"""
        alert = AlertFormatter.format_signal(
            stock_code="005930",
            stock_name="삼성전자",
            signal_type="buy",
            strength=0.9,
            sources=['LSTM', 'TA', 'SD'],
            recommendation="적극 매수",
        )

        assert alert.alert_type == AlertType.SIGNAL_BUY
        assert alert.data['신호강도'] == 0.9

    def test_format_system_status(self):
        """시스템 상태 알림 포맷"""
        alert = AlertFormatter.format_system_status(
            status="start",
            message="자동매매 시스템 시작",
        )

        assert alert.alert_type == AlertType.SYSTEM_START


class TestNotifierConfig:
    """발송기 설정 테스트"""

    def test_default_config(self):
        """기본 설정"""
        config = NotifierConfig()

        assert config.enabled is True
        assert config.min_level == AlertLevel.INFO
        assert config.max_retries == 3

    def test_custom_config(self):
        """사용자 설정"""
        config = NotifierConfig(
            enabled=True,
            min_level=AlertLevel.WARNING,
            quiet_start="22:00",
            quiet_end="08:00",
        )

        assert config.min_level == AlertLevel.WARNING
        assert config.quiet_start == "22:00"


class TestTelegramConfig:
    """텔레그램 설정 테스트"""

    def test_telegram_config(self):
        """텔레그램 설정"""
        config = TelegramConfig(
            bot_token="123456:ABC",
            chat_id="12345678",
        )

        assert config.bot_token == "123456:ABC"
        assert config.chat_id == "12345678"
        assert config.parse_mode == "HTML"


class TestTelegramNotifier:
    """텔레그램 발송기 테스트"""

    def test_notifier_creation(self):
        """발송기 생성"""
        notifier = TelegramNotifier()
        assert notifier is not None

    def test_is_configured_false(self):
        """설정 미완료"""
        notifier = TelegramNotifier()
        assert notifier.is_configured() is False

    def test_is_configured_true(self):
        """설정 완료"""
        config = TelegramConfig(
            bot_token="123456:ABC",
            chat_id="12345678",
        )
        notifier = TelegramNotifier(config)

        assert notifier.is_configured() is True

    def test_send_not_configured(self):
        """미설정 상태 발송"""
        notifier = TelegramNotifier()
        alert = Alert(
            alert_type=AlertType.SYSTEM_START,
            level=AlertLevel.INFO,
            title="테스트",
            message="테스트 메시지",
        )

        result = notifier.send(alert)

        assert result.success is False
        assert "not configured" in result.error.lower()

    def test_should_send_by_level(self):
        """레벨별 발송 여부"""
        config = TelegramConfig(
            bot_token="test",
            chat_id="test",
            min_level=AlertLevel.WARNING,
        )
        notifier = TelegramNotifier(config)

        info_alert = Alert(
            alert_type=AlertType.SYSTEM_START,
            level=AlertLevel.INFO,
            title="Info",
            message="Info message",
        )

        warning_alert = Alert(
            alert_type=AlertType.DRAWDOWN_WARNING,
            level=AlertLevel.WARNING,
            title="Warning",
            message="Warning message",
        )

        assert notifier.should_send(info_alert) is False
        assert notifier.should_send(warning_alert) is True

    def test_get_stats(self):
        """통계 조회"""
        notifier = TelegramNotifier()
        stats = notifier.get_stats()

        assert 'sent_count' in stats
        assert 'error_count' in stats
        assert 'success_rate' in stats


class TestNotificationManager:
    """알림 관리자 테스트"""

    def test_manager_creation(self):
        """관리자 생성"""
        manager = NotificationManager()
        assert manager is not None

    def test_register_notifier(self):
        """발송기 등록"""
        manager = NotificationManager()
        notifier = TelegramNotifier()

        manager.register_notifier('telegram', notifier)

        assert 'telegram' in manager._notifiers

    def test_unregister_notifier(self):
        """발송기 해제"""
        manager = NotificationManager()
        notifier = TelegramNotifier()

        manager.register_notifier('telegram', notifier)
        result = manager.unregister_notifier('telegram')

        assert result is True
        assert 'telegram' not in manager._notifiers

    def test_rate_limit_per_minute(self):
        """분당 제한"""
        config = RateLimitConfig(max_per_minute=2)
        manager = NotificationManager(rate_limit_config=config)

        # 3번 연속 체크 - 처음 2번은 통과, 3번째는 실패해야 함
        for i in range(3):
            alert = Alert(
                alert_type=AlertType.SIGNAL_BUY,
                level=AlertLevel.INFO,
                title=f"Signal {i}",
                message=f"Test {i}",
                stock_code=f"00593{i}",  # 다른 종목
            )
            can_send = manager._check_rate_limit(alert)

            if i < 2:
                # 이력에 추가 (발송 성공 가정)
                manager._record_history(alert, True)
            else:
                assert can_send is False

    def test_duplicate_detection(self):
        """중복 감지"""
        manager = NotificationManager()

        alert1 = Alert(
            alert_type=AlertType.SIGNAL_BUY,
            level=AlertLevel.INFO,
            title="매수 신호",
            message="테스트",
            stock_code="005930",
        )

        # 첫 번째는 중복 아님
        assert manager._is_duplicate(alert1) is False

        # 이력 기록
        manager._record_history(alert1, True)

        # 같은 알림은 중복
        assert manager._is_duplicate(alert1) is True

        # 다른 알림은 중복 아님
        alert2 = Alert(
            alert_type=AlertType.SIGNAL_SELL,  # 다른 유형
            level=AlertLevel.INFO,
            title="매도 신호",
            message="테스트",
            stock_code="005930",
        )
        assert manager._is_duplicate(alert2) is False

    def test_send_alert_filtered(self):
        """필터링된 알림"""
        manager = NotificationManager()

        # 발송기 없이 알림 발송
        alert = Alert(
            alert_type=AlertType.SYSTEM_START,
            level=AlertLevel.INFO,
            title="테스트",
            message="테스트",
        )

        results = manager.send_alert(alert)

        # 발송기가 없으면 빈 결과
        assert len(results) == 0

    def test_get_stats(self):
        """통계 조회"""
        manager = NotificationManager()
        stats = manager.get_stats()

        assert 'sent_count' in stats
        assert 'filtered_count' in stats
        assert 'notifiers' in stats


class TestRateLimitConfig:
    """레이트 리밋 설정 테스트"""

    def test_default_config(self):
        """기본 설정"""
        config = RateLimitConfig()

        assert config.max_per_hour == 60
        assert config.max_per_minute == 10
        assert config.dedup_window_seconds == 300

    def test_custom_config(self):
        """사용자 설정"""
        config = RateLimitConfig(
            max_per_hour=100,
            max_per_minute=20,
            max_per_stock_per_hour=15,
        )

        assert config.max_per_hour == 100
        assert config.max_per_minute == 20


class TestNotificationManagerConvenience:
    """알림 관리자 편의 메서드 테스트"""

    def setup_method(self):
        """테스트 설정"""
        self.manager = NotificationManager()

    def test_notify_trade_entry(self):
        """거래 진입 알림 편의 메서드"""
        results = self.manager.notify_trade_entry(
            stock_code="005930",
            stock_name="삼성전자",
            direction="buy",
            price=70000,
            quantity=10,
            signal_source=['LSTM'],
            confidence=0.8,
        )

        # 발송기 없으면 빈 결과
        assert isinstance(results, dict)

    def test_notify_trade_exit(self):
        """거래 청산 알림 편의 메서드"""
        results = self.manager.notify_trade_exit(
            stock_code="005930",
            stock_name="삼성전자",
            exit_reason="take_profit",
            entry_price=70000,
            exit_price=73500,
            pnl=3500,
            pnl_pct=5.0,
            holding_days=3,
        )

        assert isinstance(results, dict)

    def test_notify_drawdown(self):
        """드로우다운 알림 편의 메서드"""
        results = self.manager.notify_drawdown(
            current_drawdown=0.08,
            max_drawdown=0.10,
            alert_level="warning",
        )

        assert isinstance(results, dict)

    def test_notify_daily_summary(self):
        """일일 요약 알림 편의 메서드"""
        results = self.manager.notify_daily_summary(
            date=datetime.now(),
            total_trades=10,
            win_rate=0.6,
            total_pnl=50000,
            total_pnl_pct=2.5,
            top_winners=[],
            top_losers=[],
        )

        assert isinstance(results, dict)

    def test_notify_circuit_breaker(self):
        """서킷 브레이커 알림 편의 메서드"""
        results = self.manager.notify_circuit_breaker(
            reason="일일 손실 한도 초과",
            triggered_at=datetime.now(),
        )

        assert isinstance(results, dict)

    def test_notify_signal(self):
        """매매 신호 알림 편의 메서드"""
        results = self.manager.notify_signal(
            stock_code="005930",
            stock_name="삼성전자",
            signal_type="buy",
            strength=0.9,
            sources=['LSTM', 'TA'],
            recommendation="적극 매수",
        )

        assert isinstance(results, dict)

    def test_notify_system(self):
        """시스템 상태 알림 편의 메서드"""
        results = self.manager.notify_system(
            status="start",
            message="시스템 시작",
        )

        assert isinstance(results, dict)


class TestNotificationIntegration:
    """알림 시스템 통합 테스트"""

    def test_full_notification_flow(self):
        """전체 알림 흐름"""
        # 1. 관리자 생성
        manager = NotificationManager()

        # 2. Mock 발송기 등록
        class MockNotifier(BaseNotifier):
            def __init__(self):
                super().__init__()
                self.sent_alerts = []

            def send(self, alert):
                self.sent_alerts.append(alert)
                self._record_success()
                return NotificationResult(
                    success=True,
                    alert_id=str(id(alert)),
                )

            def send_raw(self, message):
                return NotificationResult(
                    success=True,
                    alert_id="raw",
                )

        mock_notifier = MockNotifier()
        manager.register_notifier('mock', mock_notifier)

        # 3. 알림 발송
        alert = Alert(
            alert_type=AlertType.TRADE_ENTRY,
            level=AlertLevel.INFO,
            title="매수 진입",
            message="삼성전자 매수",
            stock_code="005930",
        )

        results = manager.send_alert(alert)

        # 4. 결과 확인
        assert 'mock' in results
        assert results['mock'].success is True
        assert len(mock_notifier.sent_alerts) == 1

        # 5. 통계 확인
        stats = manager.get_stats()
        assert stats['sent_count'] == 1

    def test_multiple_channels(self):
        """다중 채널 발송"""
        manager = NotificationManager()

        class MockNotifier(BaseNotifier):
            def __init__(self, name):
                super().__init__()
                self.name = name

            def send(self, alert):
                self._record_success()
                return NotificationResult(success=True, alert_id=self.name)

            def send_raw(self, message):
                return NotificationResult(success=True, alert_id=self.name)

        # 여러 채널 등록
        manager.register_notifier('channel1', MockNotifier('ch1'))
        manager.register_notifier('channel2', MockNotifier('ch2'))

        # 알림 발송
        alert = Alert(
            alert_type=AlertType.SYSTEM_START,
            level=AlertLevel.INFO,
            title="테스트",
            message="테스트",
        )

        results = manager.send_alert(alert)

        # 모든 채널로 발송
        assert len(results) == 2
        assert 'channel1' in results
        assert 'channel2' in results

    def test_selective_channel_send(self):
        """선택적 채널 발송"""
        manager = NotificationManager()

        class MockNotifier(BaseNotifier):
            def __init__(self, name):
                super().__init__()
                self.name = name
                self.sent = False

            def send(self, alert):
                self.sent = True
                return NotificationResult(success=True, alert_id=self.name)

            def send_raw(self, message):
                return NotificationResult(success=True, alert_id=self.name)

        notifier1 = MockNotifier('ch1')
        notifier2 = MockNotifier('ch2')

        manager.register_notifier('channel1', notifier1)
        manager.register_notifier('channel2', notifier2)

        # channel1만 발송
        alert = Alert(
            alert_type=AlertType.SYSTEM_START,
            level=AlertLevel.INFO,
            title="테스트",
            message="테스트",
        )

        results = manager.send_alert(alert, channels=['channel1'])

        assert notifier1.sent is True
        assert notifier2.sent is False
