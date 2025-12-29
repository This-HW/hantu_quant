"""
Tests for ConfigLoader.

Story Test: Configuration loading and validation
"""

import pytest
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestConfigLoader:
    """Test ConfigLoader functionality."""

    def test_singleton_pattern(self):
        """Test: ConfigLoader uses singleton pattern."""
        # Reset singleton for test
        from core.config import loader
        loader.ConfigLoader._instance = None
        loader.ConfigLoader._config = None

        loader1 = loader.ConfigLoader()
        loader2 = loader.ConfigLoader()

        assert loader1 is loader2

    @patch.dict(os.environ, {
        'APP_KEY': 'test_key',
        'APP_SECRET': 'test_secret',
        'ACCOUNT_NUMBER': '12345678',
        'SERVER': 'virtual',
    }, clear=False)
    def test_load_env_values(self):
        """Test: loads values from environment."""
        from core.config import loader
        loader.ConfigLoader._instance = None
        loader.ConfigLoader._config = None

        config_loader = loader.ConfigLoader()
        config = config_loader.get_config()

        assert config.api.app_key == 'test_key'
        assert config.api.app_secret == 'test_secret'
        assert config.api.account_number == '12345678'
        assert config.api.server == 'virtual'

    @patch.dict(os.environ, {
        'APP_KEY': 'test_key',
        'APP_SECRET': 'test_secret',
        'ACCOUNT_NUMBER': '12345678',
        'SERVER': 'virtual',
    }, clear=False)
    def test_validate_valid_config(self):
        """Test: validates valid configuration."""
        from core.config import loader
        loader.ConfigLoader._instance = None
        loader.ConfigLoader._config = None

        config_loader = loader.ConfigLoader()
        result = config_loader.validate()

        assert result['api']['valid'] is True
        assert len(result['api']['errors']) == 0

    @patch.dict(os.environ, {
        'APP_KEY': '',
        'APP_SECRET': '',
        'ACCOUNT_NUMBER': '',
    }, clear=False)
    def test_validate_missing_required(self):
        """Test: validation fails for missing required fields."""
        from core.config import loader
        loader.ConfigLoader._instance = None
        loader.ConfigLoader._config = None

        config_loader = loader.ConfigLoader()
        result = config_loader.validate()

        assert result['api']['valid'] is False
        assert len(result['api']['errors']) > 0

    @patch.dict(os.environ, {
        'APP_KEY': 'test_key',
        'APP_SECRET': 'test_secret',
        'ACCOUNT_NUMBER': '12345678',
    }, clear=False)
    def test_credential_masking(self):
        """Test: credentials are masked in display."""
        from core.config import loader
        loader.ConfigLoader._instance = None
        loader.ConfigLoader._config = None

        config_loader = loader.ConfigLoader()
        display = config_loader.get_display_config(mask_credentials=True)

        assert '***' in display['api']['app_key'] or display['api']['app_key'] == '(not set)'
        assert '***' in display['api']['app_secret'] or display['api']['app_secret'] == '(not set)'

    @patch.dict(os.environ, {
        'APP_KEY': 'test_key',
        'APP_SECRET': 'test_secret',
        'ACCOUNT_NUMBER': '12345678',
        'SERVER': 'prod',
        'API_SERVER_KEY': '',
    }, clear=False)
    def test_production_requires_api_key(self):
        """Test: production mode requires API_SERVER_KEY."""
        from core.config import loader
        loader.ConfigLoader._instance = None
        loader.ConfigLoader._config = None

        config_loader = loader.ConfigLoader()
        result = config_loader.validate()

        assert result['server']['valid'] is False
        assert any('API_SERVER_KEY' in err for err in result['server']['errors'])


class TestConfigSchema:
    """Test configuration schema validation."""

    def test_validate_server_enum(self):
        """Test: SERVER must be 'virtual' or 'prod'."""
        from core.config.schema import ConfigValidator

        validator = ConfigValidator()
        is_valid, errors, warnings = validator.validate_env({
            'APP_KEY': 'key',
            'APP_SECRET': 'secret',
            'ACCOUNT_NUMBER': '12345678',
            'SERVER': 'invalid',
        })

        assert is_valid is False
        assert any('SERVER' in err for err in errors)

    def test_validate_port_range(self):
        """Test: API_PORT must be valid port number."""
        from core.config.schema import ConfigValidator

        validator = ConfigValidator()
        is_valid, errors, warnings = validator.validate_env({
            'APP_KEY': 'key',
            'APP_SECRET': 'secret',
            'ACCOUNT_NUMBER': '12345678',
            'API_PORT': '99999',  # Invalid port
        })

        assert is_valid is False
        assert any('API_PORT' in err for err in errors)

    def test_validate_log_level_enum(self):
        """Test: LOG_LEVEL must be valid level."""
        from core.config.schema import ConfigValidator

        validator = ConfigValidator()
        is_valid, errors, warnings = validator.validate_env({
            'APP_KEY': 'key',
            'APP_SECRET': 'secret',
            'ACCOUNT_NUMBER': '12345678',
            'LOG_LEVEL': 'INVALID',
        })

        assert is_valid is False
        assert any('LOG_LEVEL' in err for err in errors)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
