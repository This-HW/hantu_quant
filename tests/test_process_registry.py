"""
Tests for ProcessRegistry.

Story Test: Process registry functionality
"""

import pytest
import os
import sys
import tempfile
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.process.registry import ProcessRegistry, ProcessStatus


class TestProcessRegistry:
    """Test ProcessRegistry functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        # Use temporary directory for tests
        self.temp_dir = tempfile.mkdtemp()
        self.registry = ProcessRegistry(run_dir=self.temp_dir)

    def teardown_method(self):
        """Clean up after tests."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_register_process(self):
        """Test: register a process."""
        pid = os.getpid()
        result = self.registry.register('test_service', pid)

        assert result is True

        # Check PID file exists
        pid_file = Path(self.temp_dir) / 'test_service.pid'
        assert pid_file.exists()

    def test_get_status_running(self):
        """Test: get status of running process."""
        pid = os.getpid()  # Current process is running
        self.registry.register('test_service', pid)

        status = self.registry.get_status('test_service')

        assert status.is_running is True
        assert status.pid == pid
        assert status.service_name == 'test_service'

    def test_get_status_not_running(self):
        """Test: get status of non-existent service."""
        status = self.registry.get_status('nonexistent')

        assert status.is_running is False
        assert status.pid is None

    def test_unregister_process(self):
        """Test: unregister a process."""
        pid = os.getpid()
        self.registry.register('test_service', pid)

        result = self.registry.unregister('test_service')

        assert result is True

        # Check PID file removed
        pid_file = Path(self.temp_dir) / 'test_service.pid'
        assert not pid_file.exists()

    def test_list_all(self):
        """Test: list all registered services."""
        pid = os.getpid()
        self.registry.register('service1', pid)
        self.registry.register('service2', pid)

        statuses = self.registry.list_all()

        assert 'service1' in statuses
        assert 'service2' in statuses

    def test_pid_file_permissions(self):
        """Test: PID files have correct permissions (0600)."""
        pid = os.getpid()
        self.registry.register('test_service', pid)

        pid_file = Path(self.temp_dir) / 'test_service.pid'
        mode = pid_file.stat().st_mode & 0o777

        assert mode == 0o600

    def test_run_dir_permissions(self):
        """Test: run directory has correct permissions (0700)."""
        mode = Path(self.temp_dir).stat().st_mode & 0o777

        # Note: temp_dir may have different permissions, check registry creates with correct mode
        new_dir = os.path.join(self.temp_dir, 'subdir')
        new_registry = ProcessRegistry(run_dir=new_dir)

        mode = Path(new_dir).stat().st_mode & 0o777
        assert mode == 0o700

    def test_stale_pid_detection(self):
        """Test: detect stale PID (process not running)."""
        # Register with a PID that doesn't exist
        fake_pid = 999999  # Unlikely to exist
        self.registry.register('stale_service', fake_pid)

        status = self.registry.get_status('stale_service')

        assert status.is_running is False
        assert status.pid == fake_pid  # Still returns the PID for reference

    def test_cleanup_stale(self):
        """Test: cleanup stale PID files."""
        # Register with a PID that doesn't exist
        fake_pid = 999999
        self.registry.register('stale_service', fake_pid)

        # Also register current process
        self.registry.register('running_service', os.getpid())

        removed = self.registry.cleanup_stale()

        assert removed == 1

        # Check stale file removed
        assert not (Path(self.temp_dir) / 'stale_service.pid').exists()

        # Check running service file still exists
        assert (Path(self.temp_dir) / 'running_service.pid').exists()


class TestProcessStatus:
    """Test ProcessStatus dataclass."""

    def test_uptime_str_seconds(self):
        """Test: uptime string for seconds."""
        from datetime import datetime, timedelta

        status = ProcessStatus(
            service_name='test',
            is_running=True,
            pid=123,
            start_time=datetime.now() - timedelta(seconds=30),
        )

        uptime = status.uptime_str
        assert uptime is not None
        assert 's' in uptime

    def test_uptime_str_minutes(self):
        """Test: uptime string for minutes."""
        from datetime import datetime, timedelta

        status = ProcessStatus(
            service_name='test',
            is_running=True,
            pid=123,
            start_time=datetime.now() - timedelta(minutes=5),
        )

        uptime = status.uptime_str
        assert uptime is not None
        assert 'm' in uptime

    def test_uptime_str_not_running(self):
        """Test: uptime string when not running."""
        status = ProcessStatus(
            service_name='test',
            is_running=False,
        )

        assert status.uptime_str is None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
