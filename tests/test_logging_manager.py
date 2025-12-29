"""
Tests for LogManager.

Story Test: Centralized logging functionality
"""

import pytest
import os
import sys
import json
import logging
import tempfile
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestLogManager:
    """Test LogManager functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        # Reset LogManager singleton
        from core.logging import manager
        manager._manager = None
        manager.LogManager._instance = None
        manager.LogManager._initialized = False

    def teardown_method(self):
        """Clean up after tests."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

        # Clear all handlers from root logger
        root = logging.getLogger()
        for handler in root.handlers[:]:
            root.removeHandler(handler)

    def test_setup_logging(self):
        """Test: setup_logging configures logging."""
        from core.logging import setup_logging

        setup_logging(
            service_name='test_service',
            level='DEBUG',
            log_dir=self.temp_dir,
        )

        logger = logging.getLogger('test')
        logger.info("Test message")

        # Check log file exists
        log_files = list(Path(self.temp_dir).glob('*.log'))
        assert len(log_files) > 0

    def test_get_logger(self):
        """Test: get_logger returns configured logger."""
        from core.logging import setup_logging, get_logger

        setup_logging(service_name='test', log_dir=self.temp_dir)
        logger = get_logger('my_module')

        assert logger is not None
        assert logger.name == 'my_module'

    def test_log_rotation(self):
        """Test: log rotation works correctly."""
        from core.logging import manager

        mgr = manager.LogManager()
        mgr.setup(
            service_name='test',
            log_dir=self.temp_dir,
        )

        logger = logging.getLogger('rotation_test')

        # Write many messages
        for i in range(100):
            logger.info(f"Test message {i}")

        # Should have at least one log file
        log_files = list(Path(self.temp_dir).glob('*.log*'))
        assert len(log_files) >= 1


class TestSensitiveDataFilter:
    """Test sensitive data filtering."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        from core.logging import manager
        manager._manager = None
        manager.LogManager._instance = None
        manager.LogManager._initialized = False

    def teardown_method(self):
        """Clean up after tests."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

        root = logging.getLogger()
        for handler in root.handlers[:]:
            root.removeHandler(handler)

    def test_mask_app_key(self):
        """Test: app_key is masked in logs."""
        from core.logging.manager import SensitiveDataFilter

        filter = SensitiveDataFilter()

        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='test.py',
            lineno=1,
            msg='appkey=my_secret_key',
            args=(),
            exc_info=None,
        )

        filter.filter(record)

        assert 'my_secret_key' not in record.msg
        assert '***MASKED***' in record.msg

    def test_mask_bearer_token(self):
        """Test: Bearer token is masked in logs."""
        from core.logging.manager import SensitiveDataFilter

        filter = SensitiveDataFilter()

        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='test.py',
            lineno=1,
            msg='Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9',
            args=(),
            exc_info=None,
        )

        filter.filter(record)

        assert 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9' not in record.msg
        assert 'Bearer ***MASKED***' in record.msg

    def test_mask_password(self):
        """Test: password is masked in logs."""
        from core.logging.manager import SensitiveDataFilter

        filter = SensitiveDataFilter()

        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='test.py',
            lineno=1,
            msg='password=secret123',
            args=(),
            exc_info=None,
        )

        filter.filter(record)

        assert 'secret123' not in record.msg
        assert '***MASKED***' in record.msg


class TestJSONFormatter:
    """Test JSON log formatting."""

    def test_json_output(self):
        """Test: JSON output is valid JSON."""
        from core.logging.manager import JSONFormatter

        formatter = JSONFormatter(service_name='test')

        record = logging.LogRecord(
            name='test.module',
            level=logging.INFO,
            pathname='test.py',
            lineno=42,
            msg='Test message',
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        data = json.loads(output)

        assert data['level'] == 'INFO'
        assert data['service'] == 'test'
        assert data['message'] == 'Test message'
        assert 'timestamp' in data

    def test_json_contains_required_fields(self):
        """Test: JSON output contains all required fields."""
        from core.logging.manager import JSONFormatter

        formatter = JSONFormatter(service_name='my_service')

        record = logging.LogRecord(
            name='test',
            level=logging.ERROR,
            pathname='/path/to/file.py',
            lineno=100,
            msg='Error occurred',
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        data = json.loads(output)

        # Required fields
        assert 'timestamp' in data
        assert 'level' in data
        assert 'service' in data
        assert 'message' in data

        assert data['service'] == 'my_service'
        assert data['level'] == 'ERROR'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
