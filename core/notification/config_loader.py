"""
텔레그램 설정 로더 모듈

설정 파일 로딩, 검증, 환경변수 통합을 담당합니다.

Feature 1: 알림 시스템 통합
Story 1.3: 텔레그램 설정 체계 정립
"""

import os
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

from core.exceptions import (
    ConfigValidationError,
)

logger = logging.getLogger(__name__)


# 기본 설정 경로
DEFAULT_CONFIG_PATHS = [
    "config/telegram_config.json",
    "telegram_config.json",
    ".telegram_config.json",
]


@dataclass
class NotificationLevelConfig:
    """알림 레벨별 설정"""
    enabled: bool = True
    sound: bool = False
    vibrate: bool = False


@dataclass
class MessageFormatConfig:
    """메시지 포맷 설정"""
    use_markdown: bool = False
    use_html: bool = True
    include_timestamp: bool = True
    include_charts: bool = False
    max_stocks_shown: int = 5


@dataclass
class RateLimitingConfig:
    """Rate limiting 설정"""
    max_messages_per_hour: int = 20
    max_messages_per_day: int = 100
    cooldown_seconds: int = 60


@dataclass
class TelegramConfigData:
    """
    텔레그램 설정 데이터 클래스

    Story 1.3: 텔레그램 설정 체계 정립
    T-1.3.1: TelegramConfig 클래스 정의
    """
    bot_token: str = ""
    chat_id: str = ""
    default_chat_ids: List[str] = field(default_factory=list)
    channel_mapping: Dict[str, str] = field(default_factory=dict)

    # 레벨별 알림 설정
    notification_settings: Dict[str, NotificationLevelConfig] = field(default_factory=dict)

    # 메시지 포맷 설정
    message_format: MessageFormatConfig = field(default_factory=MessageFormatConfig)

    # Rate limiting 설정
    rate_limiting: RateLimitingConfig = field(default_factory=RateLimitingConfig)

    # API 설정
    api_base_url: str = "https://api.telegram.org"
    timeout: int = 10
    max_retries: int = 3
    retry_delay: float = 1.0

    def is_configured(self) -> bool:
        """설정 완료 여부"""
        return bool(self.bot_token and (self.chat_id or self.default_chat_ids))

    def get_primary_chat_id(self) -> Optional[str]:
        """기본 채팅 ID 반환"""
        if self.chat_id:
            return self.chat_id
        if self.default_chat_ids:
            return self.default_chat_ids[0]
        return None

    def get_channel_chat_id(self, channel: str) -> Optional[str]:
        """채널별 채팅 ID 반환"""
        if channel in self.channel_mapping:
            return self.channel_mapping[channel]
        return self.get_primary_chat_id()

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 변환 (민감 정보 마스킹)"""
        return {
            "bot_token": "***" if self.bot_token else "",
            "chat_id": self.chat_id[:4] + "***" if self.chat_id else "",
            "default_chat_ids_count": len(self.default_chat_ids),
            "channel_mapping_count": len(self.channel_mapping),
            "api_base_url": self.api_base_url,
            "is_configured": self.is_configured(),
        }


class TelegramConfigLoader:
    """
    텔레그램 설정 로더

    JSON 파일과 환경변수에서 설정을 로드합니다.

    Story 1.3: 텔레그램 설정 체계 정립
    T-1.3.3: 설정 로딩 및 검증 로직
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Args:
            config_path: 설정 파일 경로 (None이면 기본 경로 탐색)
        """
        self.config_path = config_path
        self._config: Optional[TelegramConfigData] = None

    def load(self, validate: bool = True) -> TelegramConfigData:
        """
        설정 로드

        1. 환경변수에서 기본 설정 로드
        2. 설정 파일이 있으면 파일에서 추가 로드
        3. 환경변수가 파일 설정을 오버라이드

        Args:
            validate: 검증 수행 여부

        Returns:
            TelegramConfigData: 로드된 설정

        Raises:
            ConfigValidationError: 검증 실패 시
        """
        config = TelegramConfigData()

        # 1. 설정 파일 로드
        file_config = self._load_from_file()
        if file_config:
            config = self._merge_file_config(config, file_config)

        # 2. 환경변수 오버라이드
        config = self._override_from_env(config)

        # 3. 검증
        if validate:
            self.validate(config)

        self._config = config
        return config

    def _find_config_file(self) -> Optional[Path]:
        """설정 파일 탐색"""
        if self.config_path:
            path = Path(self.config_path)
            if path.exists():
                return path
            return None

        for path_str in DEFAULT_CONFIG_PATHS:
            path = Path(path_str)
            if path.exists():
                return path

        return None

    def _load_from_file(self) -> Optional[Dict[str, Any]]:
        """파일에서 설정 로드"""
        config_file = self._find_config_file()

        if not config_file:
            logger.debug("No config file found, using environment variables only")
            return None

        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            logger.info(f"Loaded config from {config_file}")

            # telegram 키 하위 구조 처리
            if "telegram" in data:
                return data["telegram"]
            return data

        except json.JSONDecodeError as e:
            raise ConfigValidationError(
                f"Invalid JSON in config file: {e}",
                config_file=str(config_file)
            )
        except Exception as e:
            logger.warning(f"Failed to load config file: {e}")
            return None

    def _merge_file_config(
        self,
        config: TelegramConfigData,
        file_config: Dict[str, Any]
    ) -> TelegramConfigData:
        """파일 설정 병합"""
        # 기본 설정
        if "bot_token" in file_config:
            config.bot_token = file_config["bot_token"]

        if "default_chat_ids" in file_config:
            config.default_chat_ids = file_config["default_chat_ids"]
            if config.default_chat_ids:
                config.chat_id = str(config.default_chat_ids[0])

        if "channel_mapping" in file_config:
            config.channel_mapping = file_config["channel_mapping"]

        # 알림 레벨 설정
        if "notification_settings" in file_config:
            ns = file_config["notification_settings"]
            for level, settings in ns.items():
                config.notification_settings[level] = NotificationLevelConfig(
                    enabled=settings.get("enabled", True),
                    sound=settings.get("sound", False),
                    vibrate=settings.get("vibrate", False),
                )

        # 메시지 포맷 설정
        if "message_format" in file_config:
            mf = file_config["message_format"]
            config.message_format = MessageFormatConfig(
                use_markdown=mf.get("use_markdown", False),
                use_html=mf.get("use_html", True),
                include_timestamp=mf.get("include_timestamp", True),
                include_charts=mf.get("include_charts", False),
                max_stocks_shown=mf.get("max_stocks_shown", 5),
            )

        # Rate limiting 설정
        if "rate_limiting" in file_config:
            rl = file_config["rate_limiting"]
            config.rate_limiting = RateLimitingConfig(
                max_messages_per_hour=rl.get("max_messages_per_hour", 20),
                max_messages_per_day=rl.get("max_messages_per_day", 100),
                cooldown_seconds=rl.get("cooldown_seconds", 60),
            )

        return config

    def _override_from_env(self, config: TelegramConfigData) -> TelegramConfigData:
        """환경변수로 설정 오버라이드"""
        # 필수 설정
        env_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if env_token:
            config.bot_token = env_token

        env_chat_id = os.getenv("TELEGRAM_CHAT_ID")
        if env_chat_id:
            config.chat_id = env_chat_id

        # 추가 환경변수
        env_timeout = os.getenv("TELEGRAM_TIMEOUT")
        if env_timeout:
            try:
                config.timeout = int(env_timeout)
            except ValueError:
                pass

        env_max_retries = os.getenv("TELEGRAM_MAX_RETRIES")
        if env_max_retries:
            try:
                config.max_retries = int(env_max_retries)
            except ValueError:
                pass

        return config

    def validate(self, config: TelegramConfigData) -> List[str]:
        """
        설정 검증

        Args:
            config: 검증할 설정

        Returns:
            List[str]: 경고 메시지 목록

        Raises:
            ConfigMissingKeyError: 필수 설정 누락 시
            ConfigValidationError: 검증 실패 시
        """
        warnings = []
        missing_keys = []

        # 필수 설정 체크 (경고만, 에러 아님)
        if not config.bot_token:
            warnings.append("bot_token is not configured")

        if not config.chat_id and not config.default_chat_ids:
            warnings.append("No chat_id configured")

        # 값 범위 검증
        if config.timeout < 1 or config.timeout > 60:
            warnings.append(f"timeout ({config.timeout}) should be between 1 and 60")

        if config.max_retries < 0 or config.max_retries > 10:
            warnings.append(f"max_retries ({config.max_retries}) should be between 0 and 10")

        # Rate limiting 검증
        if config.rate_limiting.max_messages_per_hour < 1:
            raise ConfigValidationError(
                "max_messages_per_hour must be at least 1"
            )

        if config.rate_limiting.max_messages_per_day < config.rate_limiting.max_messages_per_hour:
            warnings.append(
                "max_messages_per_day is less than max_messages_per_hour"
            )

        # 경고 로깅
        for warning in warnings:
            logger.warning(f"Config warning: {warning}")

        return warnings

    def get_config(self) -> TelegramConfigData:
        """캐시된 설정 반환 (없으면 로드)"""
        if self._config is None:
            self.load()
        return self._config

    @staticmethod
    def create_example_config(path: str = "config/telegram_config.json.example") -> str:
        """
        예제 설정 파일 생성

        Args:
            path: 생성할 파일 경로

        Returns:
            str: 생성된 파일 경로
        """
        example = {
            "telegram": {
                "bot_token": "YOUR_TELEGRAM_BOT_TOKEN_HERE",
                "default_chat_ids": ["YOUR_CHAT_ID_HERE"],
                "channel_mapping": {
                    "auto_trade": "YOUR_CHAT_ID_HERE",
                    "alerts": "YOUR_CHAT_ID_HERE",
                    "errors": "YOUR_CHAT_ID_HERE"
                },
                "notification_settings": {
                    "emergency": {"enabled": True, "sound": True, "vibrate": True},
                    "high": {"enabled": True, "sound": True, "vibrate": False},
                    "normal": {"enabled": True, "sound": False, "vibrate": False},
                    "low": {"enabled": True, "sound": False, "vibrate": False}
                },
                "message_format": {
                    "use_markdown": False,
                    "use_html": True,
                    "include_timestamp": True,
                    "include_charts": False,
                    "max_stocks_shown": 5
                },
                "rate_limiting": {
                    "max_messages_per_hour": 20,
                    "max_messages_per_day": 100,
                    "cooldown_seconds": 60
                }
            }
        }

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(example, f, indent=2, ensure_ascii=False)

        return path


# 글로벌 설정 로더 인스턴스
_config_loader: Optional[TelegramConfigLoader] = None


def get_telegram_config(config_path: Optional[str] = None) -> TelegramConfigData:
    """
    텔레그램 설정 가져오기

    Args:
        config_path: 설정 파일 경로

    Returns:
        TelegramConfigData: 텔레그램 설정
    """
    global _config_loader

    if _config_loader is None or config_path is not None:
        _config_loader = TelegramConfigLoader(config_path)

    return _config_loader.get_config()


def reload_telegram_config(config_path: Optional[str] = None) -> TelegramConfigData:
    """설정 다시 로드"""
    global _config_loader
    _config_loader = TelegramConfigLoader(config_path)
    return _config_loader.load()
