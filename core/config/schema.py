"""
Configuration Schema Definitions

JSON Schema-based validation for configuration files.
"""

from typing import Dict, Any, List, Tuple
import re


# Environment variable schema
ENV_SCHEMA = {
    'required': ['APP_KEY', 'APP_SECRET', 'ACCOUNT_NUMBER'],
    'optional': [
        'ACCOUNT_PROD_CODE',
        'SERVER',
        'TELEGRAM_BOT_TOKEN',
        'TELEGRAM_CHAT_ID',
        'API_SERVER_KEY',
        'API_HOST',
        'API_PORT',
        'LOG_LEVEL',
    ],
    'validations': {
        'SERVER': {
            'type': 'enum',
            'values': ['virtual', 'prod'],
            'default': 'virtual',
        },
        'API_PORT': {
            'type': 'int',
            'min': 1,
            'max': 65535,
            'default': 8000,
        },
        'LOG_LEVEL': {
            'type': 'enum',
            'values': ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
            'default': 'INFO',
        },
        'APP_KEY': {
            'type': 'string',
            'min_length': 1,
        },
        'APP_SECRET': {
            'type': 'string',
            'min_length': 1,
        },
        'ACCOUNT_NUMBER': {
            'type': 'string',
            'pattern': r'^\d{8,12}$',  # 8-12 digit account number
        },
    },
}


# Telegram config schema
TELEGRAM_SCHEMA = {
    'telegram': {
        'type': 'object',
        'properties': {
            'bot_token': {
                'type': 'string',
                'description': 'Telegram bot token',
            },
            'default_chat_ids': {
                'type': 'array',
                'items': {'type': 'string'},
                'description': 'Default chat IDs for notifications',
            },
            'channel_mapping': {
                'type': 'object',
                'description': 'Channel-specific chat ID mapping',
            },
            'notification_settings': {
                'type': 'object',
                'description': 'Notification priority settings',
            },
            'message_format': {
                'type': 'object',
                'description': 'Message formatting options',
            },
            'rate_limiting': {
                'type': 'object',
                'description': 'Rate limiting configuration',
            },
        },
    },
}


class ConfigValidator:
    """
    Configuration validator using schema definitions.

    Validates configuration values against defined schemas and returns
    detailed error messages.
    """

    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def validate_env(self, env_values: Dict[str, str]) -> Tuple[bool, List[str], List[str]]:
        """
        Validate environment variable configuration.

        Args:
            env_values: Dictionary of environment variable values

        Returns:
            Tuple of (is_valid, errors, warnings)
        """
        self.errors = []
        self.warnings = []

        # Check required fields
        for field in ENV_SCHEMA['required']:
            value = env_values.get(field, '')
            if not value:
                self.errors.append(f"Required field '{field}' is not set")

        # Validate field values
        for field, rules in ENV_SCHEMA['validations'].items():
            value = env_values.get(field, '')

            if not value:
                continue  # Skip empty optional fields

            self._validate_field(field, value, rules)

        # Production mode warnings
        if env_values.get('SERVER') == 'prod':
            self.warnings.append("Running in PRODUCTION mode - use caution")

            if not env_values.get('API_SERVER_KEY'):
                self.errors.append("API_SERVER_KEY is required in production mode")

        return len(self.errors) == 0, self.errors, self.warnings

    def _validate_field(self, field: str, value: str, rules: Dict[str, Any]) -> None:
        """Validate a single field against its rules."""
        field_type = rules.get('type', 'string')

        if field_type == 'enum':
            valid_values = rules.get('values', [])
            if value not in valid_values:
                self.errors.append(
                    f"Invalid value for '{field}': '{value}'. "
                    f"Must be one of: {', '.join(valid_values)}"
                )

        elif field_type == 'int':
            try:
                int_value = int(value)
                min_val = rules.get('min')
                max_val = rules.get('max')

                if min_val is not None and int_value < min_val:
                    self.errors.append(f"'{field}' must be >= {min_val}")
                if max_val is not None and int_value > max_val:
                    self.errors.append(f"'{field}' must be <= {max_val}")

            except ValueError:
                self.errors.append(f"'{field}' must be an integer")

        elif field_type == 'string':
            min_length = rules.get('min_length', 0)
            max_length = rules.get('max_length')
            pattern = rules.get('pattern')

            if len(value) < min_length:
                self.errors.append(f"'{field}' must be at least {min_length} characters")

            if max_length and len(value) > max_length:
                self.errors.append(f"'{field}' must be at most {max_length} characters")

            if pattern and not re.match(pattern, value):
                self.errors.append(f"'{field}' has invalid format")

    def validate_telegram_config(self, config: Dict[str, Any]) -> Tuple[bool, List[str], List[str]]:
        """
        Validate Telegram configuration.

        Args:
            config: Telegram configuration dictionary

        Returns:
            Tuple of (is_valid, errors, warnings)
        """
        self.errors = []
        self.warnings = []

        telegram = config.get('telegram', {})

        if not telegram:
            self.warnings.append("Telegram configuration not found - notifications disabled")
            return True, self.errors, self.warnings

        bot_token = telegram.get('bot_token', '')
        chat_ids = telegram.get('default_chat_ids', [])

        if not bot_token:
            self.warnings.append("Telegram bot_token not set - notifications disabled")

        if not chat_ids:
            self.warnings.append("No Telegram chat_ids configured")

        # Validate rate limiting if present
        rate_limiting = telegram.get('rate_limiting', {})
        if rate_limiting:
            max_per_hour = rate_limiting.get('max_messages_per_hour', 20)
            if max_per_hour < 1:
                self.errors.append("max_messages_per_hour must be >= 1")

        return len(self.errors) == 0, self.errors, self.warnings


def validate_config(env_values: Dict[str, str], telegram_config: Dict[str, Any] = None) -> Dict[str, Dict]:
    """
    Validate all configuration.

    Args:
        env_values: Environment variable values
        telegram_config: Optional Telegram configuration

    Returns:
        Dictionary with validation results for each category
    """
    validator = ConfigValidator()
    results = {}

    # Validate environment
    is_valid, errors, warnings = validator.validate_env(env_values)
    results['environment'] = {
        'valid': is_valid,
        'errors': errors,
        'warnings': warnings,
    }

    # Validate Telegram config
    if telegram_config:
        is_valid, errors, warnings = validator.validate_telegram_config(telegram_config)
        results['telegram'] = {
            'valid': is_valid,
            'errors': errors,
            'warnings': warnings,
        }

    return results
