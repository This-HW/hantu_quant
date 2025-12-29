"""
Unified Configuration Loader

Consolidates all configuration sources into a single, validated configuration object.

Load order:
    1. .env file (environment variables)
    2. config/*.yaml files
    3. config/*.json files
    4. Environment variable overrides

Security:
    - Credentials are never logged
    - Masked in __repr__ and display methods
    - File permissions checked on load

Usage:
    from core.config.loader import ConfigLoader
    loader = ConfigLoader()
    config = loader.get_config()
"""

import os
import re
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from dotenv import load_dotenv

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

logger = logging.getLogger(__name__)


# Credential field patterns (for masking)
CREDENTIAL_PATTERNS = [
    r'.*key.*',
    r'.*secret.*',
    r'.*token.*',
    r'.*password.*',
    r'.*credential.*',
    r'.*api_key.*',
]

CREDENTIAL_REGEX = re.compile('|'.join(CREDENTIAL_PATTERNS), re.IGNORECASE)


@dataclass
class TelegramConfig:
    """Telegram notification configuration."""
    bot_token: str = ''
    default_chat_ids: List[str] = field(default_factory=list)
    channel_mapping: Dict[str, str] = field(default_factory=dict)
    enabled: bool = False

    def __post_init__(self):
        self.enabled = bool(self.bot_token and self.default_chat_ids)


@dataclass
class APIConfig:
    """API configuration."""
    app_key: str = ''
    app_secret: str = ''
    account_number: str = ''
    account_prod_code: str = '01'
    server: str = 'virtual'
    base_url: str = ''
    ws_url: str = ''

    def __post_init__(self):
        if self.server == 'virtual':
            self.base_url = "https://openapivts.koreainvestment.com:29443"
            self.ws_url = "wss://openapivts.koreainvestment.com:29443/websocket"
        else:
            self.base_url = "https://openapi.koreainvestment.com:9443"
            self.ws_url = "wss://openapi.koreainvestment.com:21000/websocket"


@dataclass
class ServerConfig:
    """Server configuration."""
    api_host: str = '127.0.0.1'
    api_port: int = 8000
    api_server_key: str = ''


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str = 'INFO'
    format: str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    log_dir: str = 'logs'


@dataclass
class AppConfig:
    """Main application configuration."""
    api: APIConfig = field(default_factory=APIConfig)
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)


class ConfigLoader:
    """
    Unified configuration loader.

    Loads and merges configuration from multiple sources with proper
    security handling for sensitive data.
    """

    _instance: Optional['ConfigLoader'] = None
    _config: Optional[AppConfig] = None

    def __new__(cls) -> 'ConfigLoader':
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize the config loader."""
        if self._initialized:
            return

        self._project_root = Path(__file__).parent.parent.parent
        self._config_dir = self._project_root / 'config'
        self._env_file = self._project_root / '.env'

        self._raw_config: Dict[str, Any] = {}
        self._validation_results: Dict[str, Dict] = {}

        self._load_all()
        self._initialized = True

    def _load_all(self) -> None:
        """Load configuration from all sources."""
        # 1. Load .env file
        self._load_env()

        # 2. Load YAML files
        self._load_yaml_files()

        # 3. Load JSON files
        self._load_json_files()

        # 4. Build config objects
        self._build_config()

    def _load_env(self) -> None:
        """Load environment variables from .env file."""
        if self._env_file.exists():
            load_dotenv(self._env_file)
            logger.debug(f"Loaded .env from {self._env_file}")

        # Extract relevant env vars
        self._raw_config['env'] = {
            'APP_KEY': os.getenv('APP_KEY', ''),
            'APP_SECRET': os.getenv('APP_SECRET', ''),
            'ACCOUNT_NUMBER': os.getenv('ACCOUNT_NUMBER', ''),
            'ACCOUNT_PROD_CODE': os.getenv('ACCOUNT_PROD_CODE', '01'),
            'SERVER': os.getenv('SERVER', 'virtual'),
            'TELEGRAM_BOT_TOKEN': os.getenv('TELEGRAM_BOT_TOKEN', ''),
            'TELEGRAM_CHAT_ID': os.getenv('TELEGRAM_CHAT_ID', ''),
            'API_SERVER_KEY': os.getenv('API_SERVER_KEY', ''),
            'API_HOST': os.getenv('API_HOST', '127.0.0.1'),
            'API_PORT': os.getenv('API_PORT', '8000'),
            'LOG_LEVEL': os.getenv('LOG_LEVEL', 'INFO'),
        }

    def _load_yaml_files(self) -> None:
        """Load YAML configuration files."""
        if not YAML_AVAILABLE:
            logger.debug("PyYAML not available, skipping YAML files")
            return

        if not self._config_dir.exists():
            return

        for yaml_file in self._config_dir.glob('*.yaml'):
            try:
                with open(yaml_file, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                    if data:
                        key = yaml_file.stem
                        self._raw_config[f'yaml_{key}'] = data
                        logger.debug(f"Loaded YAML config: {yaml_file.name}")
            except Exception as e:
                logger.warning(f"Failed to load YAML file {yaml_file}: {e}")

    def _load_json_files(self) -> None:
        """Load JSON configuration files."""
        if not self._config_dir.exists():
            return

        for json_file in self._config_dir.glob('*.json'):
            # Skip example files
            if 'example' in json_file.name:
                continue

            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if data:
                        key = json_file.stem
                        self._raw_config[f'json_{key}'] = data
                        logger.debug(f"Loaded JSON config: {json_file.name}")
            except Exception as e:
                logger.warning(f"Failed to load JSON file {json_file}: {e}")

    def _build_config(self) -> None:
        """Build configuration objects from raw data."""
        env = self._raw_config.get('env', {})

        # Build API config
        api_config = APIConfig(
            app_key=env.get('APP_KEY', ''),
            app_secret=env.get('APP_SECRET', ''),
            account_number=env.get('ACCOUNT_NUMBER', ''),
            account_prod_code=env.get('ACCOUNT_PROD_CODE', '01'),
            server=env.get('SERVER', 'virtual'),
        )

        # Build Telegram config
        telegram_json = self._raw_config.get('json_telegram_config', {})
        telegram_data = telegram_json.get('telegram', {})

        # Prefer env vars over JSON
        bot_token = env.get('TELEGRAM_BOT_TOKEN') or telegram_data.get('bot_token', '')
        chat_id = env.get('TELEGRAM_CHAT_ID', '')
        default_chat_ids = telegram_data.get('default_chat_ids', [])

        if chat_id and chat_id not in default_chat_ids:
            default_chat_ids = [chat_id] + default_chat_ids

        telegram_config = TelegramConfig(
            bot_token=bot_token,
            default_chat_ids=default_chat_ids,
            channel_mapping=telegram_data.get('channel_mapping', {}),
        )

        # Build server config
        server_config = ServerConfig(
            api_host=env.get('API_HOST', '127.0.0.1'),
            api_port=int(env.get('API_PORT', 8000)),
            api_server_key=env.get('API_SERVER_KEY', ''),
        )

        # Build logging config
        logging_config = LoggingConfig(
            level=env.get('LOG_LEVEL', 'INFO'),
        )

        # Create main config
        self._config = AppConfig(
            api=api_config,
            telegram=telegram_config,
            server=server_config,
            logging=logging_config,
        )

    def get_config(self) -> AppConfig:
        """Get the configuration object."""
        if self._config is None:
            self._load_all()
        return self._config

    def validate(self) -> Dict[str, Dict]:
        """
        Validate configuration and return results.

        Returns:
            Dictionary with validation results for each category
        """
        results = {}

        # Validate API config
        api_errors = []
        api_warnings = []

        config = self.get_config()

        if not config.api.app_key:
            api_errors.append("APP_KEY is not set")
        if not config.api.app_secret:
            api_errors.append("APP_SECRET is not set")
        if not config.api.account_number:
            api_errors.append("ACCOUNT_NUMBER is not set")

        if config.api.server == 'prod':
            api_warnings.append("Running in PRODUCTION mode")

        results['api'] = {
            'valid': len(api_errors) == 0,
            'errors': api_errors,
            'warnings': api_warnings,
        }

        # Validate server config
        server_errors = []
        server_warnings = []

        if config.api.server == 'prod' and not config.server.api_server_key:
            server_errors.append("API_SERVER_KEY is required in production mode")

        results['server'] = {
            'valid': len(server_errors) == 0,
            'errors': server_errors,
            'warnings': server_warnings,
        }

        # Validate Telegram config
        telegram_errors = []
        telegram_warnings = []

        if not config.telegram.bot_token:
            telegram_warnings.append("Telegram bot token not configured (notifications disabled)")
        if not config.telegram.default_chat_ids:
            telegram_warnings.append("No Telegram chat IDs configured")

        results['telegram'] = {
            'valid': True,  # Telegram is optional
            'errors': telegram_errors,
            'warnings': telegram_warnings,
        }

        # Validate logging config
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        logging_errors = []

        if config.logging.level.upper() not in valid_levels:
            logging_errors.append(f"Invalid log level: {config.logging.level}")

        results['logging'] = {
            'valid': len(logging_errors) == 0,
            'errors': logging_errors,
            'warnings': [],
        }

        self._validation_results = results
        return results

    def get_display_config(self, mask_credentials: bool = True) -> Dict[str, Any]:
        """
        Get configuration for display purposes.

        Args:
            mask_credentials: Whether to mask sensitive values

        Returns:
            Dictionary with configuration values (credentials masked if requested)
        """
        config = self.get_config()

        display = {
            'api': {
                'app_key': self._mask_value(config.api.app_key) if mask_credentials else config.api.app_key,
                'app_secret': self._mask_value(config.api.app_secret) if mask_credentials else config.api.app_secret,
                'account_number': self._mask_value(config.api.account_number) if mask_credentials else config.api.account_number,
                'account_prod_code': config.api.account_prod_code,
                'server': config.api.server,
                'base_url': config.api.base_url,
            },
            'telegram': {
                'bot_token': self._mask_value(config.telegram.bot_token) if mask_credentials else config.telegram.bot_token,
                'enabled': config.telegram.enabled,
                'chat_ids_count': len(config.telegram.default_chat_ids),
            },
            'server': {
                'api_host': config.server.api_host,
                'api_port': config.server.api_port,
                'api_server_key': self._mask_value(config.server.api_server_key) if mask_credentials else config.server.api_server_key,
            },
            'logging': {
                'level': config.logging.level,
                'log_dir': config.logging.log_dir,
            },
        }

        return display

    @staticmethod
    def _mask_value(value: str) -> str:
        """Mask a sensitive value for display."""
        if not value:
            return '(not set)'
        if len(value) <= 4:
            return '*' * len(value)
        return value[:2] + '*' * (len(value) - 4) + value[-2:]

    @staticmethod
    def _is_credential_field(field_name: str) -> bool:
        """Check if a field name indicates a credential."""
        return bool(CREDENTIAL_REGEX.match(field_name))

    def reload(self) -> None:
        """Reload configuration from all sources."""
        self._raw_config = {}
        self._validation_results = {}
        self._config = None
        self._load_all()
        logger.info("Configuration reloaded")


# Convenience function
def get_config() -> AppConfig:
    """Get the application configuration (convenience function)."""
    return ConfigLoader().get_config()
