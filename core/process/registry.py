"""
Process Registry - Manages service process lifecycle.

Tracks running services via PID files with proper security permissions.

Security:
    - PID files have 0600 permissions (owner read/write only)
    - Run directory has 0700 permissions (owner only)
    - No sensitive data stored in PID files

Usage:
    registry = ProcessRegistry()
    registry.register('scheduler', os.getpid())
    status = registry.get_status('scheduler')
    registry.unregister('scheduler')
"""

import os
import json
import fcntl
import logging
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


logger = logging.getLogger(__name__)


@dataclass
class ProcessStatus:
    """Status information for a service process."""

    service_name: str
    is_running: bool
    pid: Optional[int] = None
    start_time: Optional[datetime] = None
    memory_mb: Optional[float] = None

    @property
    def uptime_str(self) -> Optional[str]:
        """Get human-readable uptime string."""
        if not self.is_running or not self.start_time:
            return None

        delta = datetime.now() - self.start_time
        total_seconds = int(delta.total_seconds())

        if total_seconds < 60:
            return f"{total_seconds}s"
        elif total_seconds < 3600:
            minutes = total_seconds // 60
            seconds = total_seconds % 60
            return f"{minutes}m {seconds}s"
        elif total_seconds < 86400:
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            return f"{hours}h {minutes}m"
        else:
            days = total_seconds // 86400
            hours = (total_seconds % 86400) // 3600
            return f"{days}d {hours}h"


class ProcessRegistry:
    """
    Registry for managing service processes.

    Uses PID files to track running services. Provides methods to register,
    unregister, and query service status.

    Attributes:
        run_dir: Directory for PID files (default: ~/.hantu/run)
    """

    # File permissions (octal)
    DIR_MODE = 0o700   # rwx------
    FILE_MODE = 0o600  # rw-------

    def __init__(self, run_dir: Optional[str] = None):
        """
        Initialize the process registry.

        Args:
            run_dir: Directory for PID files. Defaults to ~/.hantu/run
        """
        if run_dir:
            self._run_dir = Path(run_dir)
        else:
            self._run_dir = Path.home() / '.hantu' / 'run'

        self._ensure_run_dir()

    def _ensure_run_dir(self) -> None:
        """Create run directory with secure permissions if it doesn't exist."""
        if not self._run_dir.exists():
            self._run_dir.mkdir(parents=True, mode=self.DIR_MODE)
            logger.debug(f"Created run directory: {self._run_dir}")
        else:
            # Ensure correct permissions
            current_mode = self._run_dir.stat().st_mode & 0o777
            if current_mode != self.DIR_MODE:
                os.chmod(self._run_dir, self.DIR_MODE)
                logger.debug(f"Fixed permissions on run directory: {self._run_dir}")

    def _get_pid_file(self, service_name: str) -> Path:
        """Get the PID file path for a service."""
        # Sanitize service name to prevent path traversal
        safe_name = "".join(c for c in service_name if c.isalnum() or c in '-_')
        return self._run_dir / f"{safe_name}.pid"

    def register(self, service_name: str, pid: int) -> bool:
        """
        Register a service process.

        Args:
            service_name: Name of the service
            pid: Process ID

        Returns:
            True if registered successfully, False otherwise
        """
        pid_file = self._get_pid_file(service_name)

        try:
            # Create PID file with lock
            with open(pid_file, 'w') as f:
                # Acquire exclusive lock
                fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

                data = {
                    'pid': pid,
                    'service': service_name,
                    'start_time': datetime.now().isoformat(),
                }
                json.dump(data, f)

                # Release lock (will be released on close anyway)
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

            # Set secure permissions
            os.chmod(pid_file, self.FILE_MODE)

            logger.info(f"Registered service '{service_name}' with PID {pid}")
            return True

        except BlockingIOError:
            logger.warning(f"Could not acquire lock for {service_name} - already registered?")
            return False
        except Exception as e:
            logger.error(f"Failed to register service '{service_name}': {e}")
            return False

    def unregister(self, service_name: str) -> bool:
        """
        Unregister a service process.

        Args:
            service_name: Name of the service

        Returns:
            True if unregistered successfully, False otherwise
        """
        pid_file = self._get_pid_file(service_name)

        try:
            if pid_file.exists():
                pid_file.unlink()
                logger.info(f"Unregistered service '{service_name}'")
            return True
        except Exception as e:
            logger.error(f"Failed to unregister service '{service_name}': {e}")
            return False

    def get_status(self, service_name: str) -> ProcessStatus:
        """
        Get the status of a service.

        Args:
            service_name: Name of the service

        Returns:
            ProcessStatus with current service state
        """
        pid_file = self._get_pid_file(service_name)

        if not pid_file.exists():
            return ProcessStatus(service_name=service_name, is_running=False)

        try:
            with open(pid_file, 'r') as f:
                data = json.load(f)

            pid = data.get('pid')
            start_time_str = data.get('start_time')

            if pid is None:
                return ProcessStatus(service_name=service_name, is_running=False)

            # Check if process is actually running
            is_running = self._is_process_running(pid)

            if not is_running:
                # Stale PID file - process is not running
                return ProcessStatus(
                    service_name=service_name,
                    is_running=False,
                    pid=pid,
                )

            # Parse start time
            start_time = None
            if start_time_str:
                try:
                    start_time = datetime.fromisoformat(start_time_str)
                except ValueError:
                    pass

            # Get memory usage if psutil is available
            memory_mb = None
            if PSUTIL_AVAILABLE:
                try:
                    process = psutil.Process(pid)
                    memory_mb = process.memory_info().rss / (1024 * 1024)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

            return ProcessStatus(
                service_name=service_name,
                is_running=True,
                pid=pid,
                start_time=start_time,
                memory_mb=memory_mb,
            )

        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Invalid PID file for '{service_name}': {e}")
            return ProcessStatus(service_name=service_name, is_running=False)
        except Exception as e:
            logger.error(f"Error reading status for '{service_name}': {e}")
            return ProcessStatus(service_name=service_name, is_running=False)

    def list_all(self) -> Dict[str, ProcessStatus]:
        """
        List status of all registered services.

        Returns:
            Dictionary mapping service name to ProcessStatus
        """
        statuses = {}

        try:
            for pid_file in self._run_dir.glob('*.pid'):
                service_name = pid_file.stem
                statuses[service_name] = self.get_status(service_name)
        except Exception as e:
            logger.error(f"Error listing services: {e}")

        return statuses

    def cleanup_stale(self) -> int:
        """
        Remove PID files for processes that are no longer running.

        Returns:
            Number of stale PID files removed
        """
        removed = 0

        for service_name, status in self.list_all().items():
            if not status.is_running and status.pid is not None:
                if self.unregister(service_name):
                    removed += 1
                    logger.info(f"Cleaned up stale PID file for '{service_name}'")

        return removed

    @staticmethod
    def _is_process_running(pid: int) -> bool:
        """
        Check if a process with the given PID is running.

        Args:
            pid: Process ID to check

        Returns:
            True if process is running, False otherwise
        """
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            # Process exists but we don't have permission to signal it
            return True
        except Exception:
            return False
