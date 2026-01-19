"""
Story 1.3: 텔레그램 설정 체계 정립 테스트

T-1.3.1: TelegramConfig 클래스 정의
T-1.3.2: telegram_config.json 템플릿 생성
T-1.3.3: 설정 로딩 및 검증 로직
T-1.3.4: Story 1.3 테스트 작성 및 검증
"""

import pytest
import os
import json
import tempfile
from unittest.mock import patch

from core.notification.config_loader import (
    TelegramConfigData,
    TelegramConfigLoader,
    NotificationLevelConfig,
    MessageFormatConfig,
    RateLimitingConfig,
    reload_telegram_config,
)
from core.exceptions import ConfigValidationError


class TestTelegramConfigData:
    """TelegramConfigData 테스트"""

    def test_default_values(self):
        """기본값 확인"""
        config = TelegramConfigData()
        assert config.bot_token == ""
        assert config.chat_id == ""
        assert config.default_chat_ids == []
        assert config.timeout == 10
        assert config.max_retries == 3

    def test_is_configured_false(self):
        """설정 미완료 확인"""
        config = TelegramConfigData()
        assert config.is_configured() is False

    def test_is_configured_with_token_and_chat_id(self):
        """토큰과 채팅 ID로 설정 완료"""
        config = TelegramConfigData(bot_token="token", chat_id="123")
        assert config.is_configured() is True

    def test_is_configured_with_default_chat_ids(self):
        """기본 채팅 ID 목록으로 설정 완료"""
        config = TelegramConfigData(
            bot_token="token",
            default_chat_ids=["123", "456"]
        )
        assert config.is_configured() is True

    def test_get_primary_chat_id(self):
        """기본 채팅 ID 조회"""
        config = TelegramConfigData(chat_id="primary")
        assert config.get_primary_chat_id() == "primary"

    def test_get_primary_chat_id_from_list(self):
        """목록에서 기본 채팅 ID 조회"""
        config = TelegramConfigData(default_chat_ids=["first", "second"])
        assert config.get_primary_chat_id() == "first"

    def test_get_channel_chat_id(self):
        """채널별 채팅 ID 조회"""
        config = TelegramConfigData(
            chat_id="default",
            channel_mapping={"alerts": "alert_chat", "errors": "error_chat"}
        )
        assert config.get_channel_chat_id("alerts") == "alert_chat"
        assert config.get_channel_chat_id("errors") == "error_chat"
        assert config.get_channel_chat_id("unknown") == "default"

    def test_to_dict_masks_sensitive(self):
        """딕셔너리 변환 시 민감 정보 마스킹"""
        config = TelegramConfigData(
            bot_token="my_secret_token",
            chat_id="12345678"
        )
        d = config.to_dict()
        assert d["bot_token"] == "***"
        assert "1234" in d["chat_id"]
        assert "***" in d["chat_id"]


class TestNotificationLevelConfig:
    """NotificationLevelConfig 테스트"""

    def test_default_values(self):
        """기본값"""
        config = NotificationLevelConfig()
        assert config.enabled is True
        assert config.sound is False
        assert config.vibrate is False

    def test_custom_values(self):
        """커스텀 값"""
        config = NotificationLevelConfig(enabled=False, sound=True, vibrate=True)
        assert config.enabled is False
        assert config.sound is True
        assert config.vibrate is True


class TestMessageFormatConfig:
    """MessageFormatConfig 테스트"""

    def test_default_values(self):
        """기본값"""
        config = MessageFormatConfig()
        assert config.use_html is True
        assert config.use_markdown is False
        assert config.include_timestamp is True


class TestRateLimitingConfig:
    """RateLimitingConfig 테스트"""

    def test_default_values(self):
        """기본값"""
        config = RateLimitingConfig()
        assert config.max_messages_per_hour == 20
        assert config.max_messages_per_day == 100
        assert config.cooldown_seconds == 60


class TestTelegramConfigLoader:
    """TelegramConfigLoader 테스트"""

    def test_load_empty_config(self):
        """빈 설정 로드"""
        loader = TelegramConfigLoader(config_path="/nonexistent/path")
        config = loader.load(validate=False)
        assert config.bot_token == ""

    def test_load_from_json_file(self):
        """JSON 파일에서 로드"""
        config_data = {
            "telegram": {
                "bot_token": "test_token",
                "default_chat_ids": ["123"],
                "notification_settings": {
                    "emergency": {"enabled": True, "sound": True}
                }
            }
        }

        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.json',
            delete=False
        ) as f:
            json.dump(config_data, f)
            temp_path = f.name

        try:
            loader = TelegramConfigLoader(config_path=temp_path)
            config = loader.load(validate=False)

            assert config.bot_token == "test_token"
            assert config.default_chat_ids == ["123"]
            assert "emergency" in config.notification_settings
        finally:
            os.unlink(temp_path)

    def test_load_without_telegram_key(self):
        """telegram 키 없는 JSON 로드"""
        config_data = {
            "bot_token": "direct_token",
            "default_chat_ids": ["456"]
        }

        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.json',
            delete=False
        ) as f:
            json.dump(config_data, f)
            temp_path = f.name

        try:
            loader = TelegramConfigLoader(config_path=temp_path)
            config = loader.load(validate=False)

            assert config.bot_token == "direct_token"
        finally:
            os.unlink(temp_path)

    def test_env_override(self):
        """환경변수 오버라이드"""
        config_data = {
            "telegram": {
                "bot_token": "file_token",
                "default_chat_ids": ["123"]
            }
        }

        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.json',
            delete=False
        ) as f:
            json.dump(config_data, f)
            temp_path = f.name

        try:
            with patch.dict(os.environ, {
                "TELEGRAM_BOT_TOKEN": "env_token",
                "TELEGRAM_CHAT_ID": "env_chat"
            }):
                loader = TelegramConfigLoader(config_path=temp_path)
                config = loader.load(validate=False)

                # 환경변수가 우선
                assert config.bot_token == "env_token"
                assert config.chat_id == "env_chat"
        finally:
            os.unlink(temp_path)

    def test_validate_rate_limiting(self):
        """Rate limiting 검증"""
        config = TelegramConfigData()
        config.rate_limiting = RateLimitingConfig(
            max_messages_per_hour=0,  # 잘못된 값
            max_messages_per_day=100,
            cooldown_seconds=60
        )

        loader = TelegramConfigLoader()
        with pytest.raises(ConfigValidationError):
            loader.validate(config)

    def test_validate_warnings(self):
        """검증 경고"""
        config = TelegramConfigData()
        config.timeout = 100  # 권장 범위 초과

        loader = TelegramConfigLoader()
        warnings = loader.validate(config)

        assert any("timeout" in w for w in warnings)

    def test_invalid_json(self):
        """잘못된 JSON 파일"""
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.json',
            delete=False
        ) as f:
            f.write("{ invalid json }")
            temp_path = f.name

        try:
            loader = TelegramConfigLoader(config_path=temp_path)
            with pytest.raises(ConfigValidationError):
                loader.load()
        finally:
            os.unlink(temp_path)

    def test_get_config_caching(self):
        """설정 캐싱"""
        loader = TelegramConfigLoader(config_path="/nonexistent")
        config1 = loader.get_config()
        config2 = loader.get_config()
        assert config1 is config2


class TestCreateExampleConfig:
    """예제 설정 파일 생성 테스트"""

    def test_create_example_config(self):
        """예제 파일 생성"""
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "config", "telegram_config.json.example")
            result = TelegramConfigLoader.create_example_config(path)

            assert os.path.exists(result)

            with open(result, 'r') as f:
                data = json.load(f)

            assert "telegram" in data
            assert "bot_token" in data["telegram"]
            assert "notification_settings" in data["telegram"]


class TestGlobalFunctions:
    """글로벌 함수 테스트"""

    def test_get_telegram_config(self):
        """get_telegram_config 함수"""
        with patch.dict(os.environ, {
            "TELEGRAM_BOT_TOKEN": "test_token",
            "TELEGRAM_CHAT_ID": "test_chat"
        }):
            config = reload_telegram_config()
            assert config.bot_token == "test_token"
            assert config.chat_id == "test_chat"

    def test_reload_telegram_config(self):
        """설정 다시 로드"""
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "token1"}):
            config1 = reload_telegram_config()

        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "token2"}):
            config2 = reload_telegram_config()

        assert config1.bot_token == "token1"
        assert config2.bot_token == "token2"


class TestIntegration:
    """통합 테스트"""

    def test_full_config_load(self):
        """전체 설정 로드"""
        config_data = {
            "telegram": {
                "bot_token": "full_test_token",
                "default_chat_ids": ["123", "456"],
                "channel_mapping": {
                    "auto_trade": "trade_chat",
                    "alerts": "alert_chat"
                },
                "notification_settings": {
                    "emergency": {"enabled": True, "sound": True, "vibrate": True},
                    "normal": {"enabled": True, "sound": False, "vibrate": False}
                },
                "message_format": {
                    "use_html": True,
                    "include_timestamp": True,
                    "max_stocks_shown": 10
                },
                "rate_limiting": {
                    "max_messages_per_hour": 30,
                    "max_messages_per_day": 200,
                    "cooldown_seconds": 30
                }
            }
        }

        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.json',
            delete=False
        ) as f:
            json.dump(config_data, f)
            temp_path = f.name

        try:
            loader = TelegramConfigLoader(config_path=temp_path)
            config = loader.load()

            # 기본 설정
            assert config.bot_token == "full_test_token"
            assert len(config.default_chat_ids) == 2
            assert config.is_configured() is True

            # 채널 매핑
            assert config.get_channel_chat_id("auto_trade") == "trade_chat"
            assert config.get_channel_chat_id("alerts") == "alert_chat"

            # 알림 설정
            assert config.notification_settings["emergency"].sound is True
            assert config.notification_settings["normal"].sound is False

            # 메시지 포맷
            assert config.message_format.use_html is True
            assert config.message_format.max_stocks_shown == 10

            # Rate limiting
            assert config.rate_limiting.max_messages_per_hour == 30
            assert config.rate_limiting.cooldown_seconds == 30

        finally:
            os.unlink(temp_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
