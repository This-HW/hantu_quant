"""
알림 채널 인터페이스

Feature 3.2: 알림 채널 확장 준비
- T-3.2.1: 알림 채널 인터페이스 정의 (BaseNotificationChannel)
- T-3.2.2: 텔레그램 채널을 인터페이스 기반으로 리팩토링
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from enum import Enum
from datetime import datetime

from .alert import Alert
from .notifier import NotificationResult


class ChannelType(Enum):
    """채널 타입"""
    TELEGRAM = "telegram"
    EMAIL = "email"
    SMS = "sms"
    SLACK = "slack"
    WEBHOOK = "webhook"


class ChannelStatus(Enum):
    """채널 상태"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    RATE_LIMITED = "rate_limited"


@dataclass
class ChannelInfo:
    """채널 정보"""
    channel_type: ChannelType
    name: str
    status: ChannelStatus
    is_configured: bool
    last_used: Optional[datetime] = None
    success_count: int = 0
    error_count: int = 0
    metadata: Dict[str, Any] = None

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 변환"""
        return {
            "channel_type": self.channel_type.value,
            "name": self.name,
            "status": self.status.value,
            "is_configured": self.is_configured,
            "last_used": self.last_used.isoformat() if self.last_used else None,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "success_rate": (
                self.success_count / (self.success_count + self.error_count) * 100
                if (self.success_count + self.error_count) > 0
                else 0
            ),
        }


class BaseNotificationChannel(ABC):
    """
    알림 채널 기본 인터페이스

    모든 알림 채널은 이 인터페이스를 구현해야 합니다.
    """

    def __init__(self, name: str, channel_type: ChannelType):
        """
        Args:
            name: 채널 이름
            channel_type: 채널 타입
        """
        self._name = name
        self._channel_type = channel_type
        self._status = ChannelStatus.INACTIVE
        self._last_used: Optional[datetime] = None
        self._success_count = 0
        self._error_count = 0

    @property
    def name(self) -> str:
        """채널 이름"""
        return self._name

    @property
    def channel_type(self) -> ChannelType:
        """채널 타입"""
        return self._channel_type

    @property
    def status(self) -> ChannelStatus:
        """채널 상태"""
        return self._status

    @abstractmethod
    def is_configured(self) -> bool:
        """설정 완료 여부"""
        pass

    @abstractmethod
    def send(self, alert: Alert) -> NotificationResult:
        """
        알림 발송

        Args:
            alert: 알림 객체

        Returns:
            NotificationResult
        """
        pass

    @abstractmethod
    def send_raw(self, message: str, **kwargs) -> NotificationResult:
        """
        원시 메시지 발송

        Args:
            message: 메시지 내용
            **kwargs: 추가 옵션

        Returns:
            NotificationResult
        """
        pass

    @abstractmethod
    def test_connection(self) -> Dict[str, Any]:
        """
        연결 테스트

        Returns:
            테스트 결과
        """
        pass

    def get_info(self) -> ChannelInfo:
        """채널 정보 반환"""
        return ChannelInfo(
            channel_type=self._channel_type,
            name=self._name,
            status=self._status,
            is_configured=self.is_configured(),
            last_used=self._last_used,
            success_count=self._success_count,
            error_count=self._error_count,
        )

    def _record_success(self) -> None:
        """성공 기록"""
        self._success_count += 1
        self._last_used = datetime.now()
        self._status = ChannelStatus.ACTIVE

    def _record_error(self) -> None:
        """에러 기록"""
        self._error_count += 1
        self._last_used = datetime.now()


class TelegramChannel(BaseNotificationChannel):
    """
    텔레그램 채널

    기존 TelegramNotifier를 인터페이스 기반으로 래핑
    """

    def __init__(self, name: str = "telegram_default", config_path: Optional[str] = None):
        """
        Args:
            name: 채널 이름
            config_path: 설정 파일 경로
        """
        super().__init__(name, ChannelType.TELEGRAM)

        # 표준 TelegramNotifier 사용
        from .telegram_bot import TelegramNotifier
        self._notifier = TelegramNotifier(config_path=config_path)

        if self._notifier.is_configured():
            self._status = ChannelStatus.ACTIVE

    def is_configured(self) -> bool:
        """설정 완료 여부"""
        return self._notifier.is_configured()

    def send(self, alert: Alert) -> NotificationResult:
        """알림 발송"""
        result = self._notifier.send(alert)

        if result.success:
            self._record_success()
        else:
            self._record_error()

        return result

    def send_raw(self, message: str, **kwargs) -> NotificationResult:
        """원시 메시지 발송"""
        result = self._notifier.send_raw(message)

        if result.success:
            self._record_success()
        else:
            self._record_error()

        return result

    def test_connection(self) -> Dict[str, Any]:
        """연결 테스트"""
        return self._notifier.test_connection()


class ChannelRegistry:
    """
    채널 레지스트리

    여러 알림 채널을 관리하고 라우팅합니다.
    """

    def __init__(self):
        self._channels: Dict[str, BaseNotificationChannel] = {}

    def register(self, channel: BaseNotificationChannel) -> None:
        """
        채널 등록

        Args:
            channel: 알림 채널
        """
        self._channels[channel.name] = channel

    def unregister(self, name: str) -> bool:
        """
        채널 등록 해제

        Args:
            name: 채널 이름

        Returns:
            성공 여부
        """
        if name in self._channels:
            del self._channels[name]
            return True
        return False

    def get(self, name: str) -> Optional[BaseNotificationChannel]:
        """
        채널 조회

        Args:
            name: 채널 이름

        Returns:
            채널 객체 또는 None
        """
        return self._channels.get(name)

    def get_by_type(self, channel_type: ChannelType) -> List[BaseNotificationChannel]:
        """
        타입별 채널 조회

        Args:
            channel_type: 채널 타입

        Returns:
            채널 목록
        """
        return [
            ch for ch in self._channels.values()
            if ch.channel_type == channel_type
        ]

    def get_active_channels(self) -> List[BaseNotificationChannel]:
        """활성 채널 목록"""
        return [
            ch for ch in self._channels.values()
            if ch.status == ChannelStatus.ACTIVE and ch.is_configured()
        ]

    def send_to_all(self, alert: Alert) -> Dict[str, NotificationResult]:
        """
        모든 활성 채널로 발송

        Args:
            alert: 알림 객체

        Returns:
            채널별 결과
        """
        results = {}
        for channel in self.get_active_channels():
            results[channel.name] = channel.send(alert)
        return results

    def send_to_type(
        self,
        channel_type: ChannelType,
        alert: Alert,
    ) -> Dict[str, NotificationResult]:
        """
        특정 타입 채널로 발송

        Args:
            channel_type: 채널 타입
            alert: 알림 객체

        Returns:
            채널별 결과
        """
        results = {}
        for channel in self.get_by_type(channel_type):
            if channel.is_configured():
                results[channel.name] = channel.send(alert)
        return results

    def list_channels(self) -> List[ChannelInfo]:
        """
        채널 목록 조회

        Returns:
            채널 정보 목록
        """
        return [ch.get_info() for ch in self._channels.values()]


# 글로벌 레지스트리
_channel_registry: Optional[ChannelRegistry] = None


def get_channel_registry() -> ChannelRegistry:
    """채널 레지스트리 싱글톤"""
    global _channel_registry
    if _channel_registry is None:
        _channel_registry = ChannelRegistry()
    return _channel_registry


def register_telegram_channel(
    name: str = "telegram_default",
    config_path: Optional[str] = None,
) -> TelegramChannel:
    """
    텔레그램 채널 등록 헬퍼

    Args:
        name: 채널 이름
        config_path: 설정 경로

    Returns:
        등록된 채널
    """
    channel = TelegramChannel(name=name, config_path=config_path)
    get_channel_registry().register(channel)
    return channel
