"""
Graceful Shutdown Handler

Provides signal handling and cleanup routines for graceful service shutdown.

Features:
    - SIGTERM and SIGINT handling
    - Configurable shutdown timeout
    - Cleanup callback registration
    - Process registry integration

Usage:
    from core.process.shutdown import GracefulShutdown

    shutdown = GracefulShutdown(service_name='scheduler')
    shutdown.register_cleanup(my_cleanup_function)
    shutdown.setup()

    # In your main loop
    while shutdown.is_running:
        do_work()
"""

import os
import signal
import logging
import threading
import time
from typing import Callable, List, Optional
from contextlib import contextmanager

from core.process.registry import ProcessRegistry

logger = logging.getLogger(__name__)


class GracefulShutdown:
    """
    Graceful shutdown handler for services.

    Handles SIGTERM and SIGINT signals, executes cleanup callbacks,
    and ensures proper process registry cleanup.

    Attributes:
        service_name: Name of the service for registry
        timeout: Maximum time to wait for cleanup (seconds)
        is_running: Flag indicating if service should continue running
    """

    DEFAULT_TIMEOUT = 30

    def __init__(
        self,
        service_name: str,
        timeout: int = DEFAULT_TIMEOUT,
        register_process: bool = True,
    ):
        """
        Initialize the shutdown handler.

        Args:
            service_name: Name of the service for process registry
            timeout: Shutdown timeout in seconds
            register_process: Whether to register this process in the registry
        """
        self.service_name = service_name
        self.timeout = timeout
        self._register_process = register_process

        self._is_running = True
        self._shutdown_event = threading.Event()
        self._cleanup_callbacks: List[Callable] = []
        self._registry = ProcessRegistry()

        self._original_sigterm = None
        self._original_sigint = None

    @property
    def is_running(self) -> bool:
        """Check if the service should continue running."""
        return self._is_running and not self._shutdown_event.is_set()

    def setup(self) -> None:
        """
        Set up signal handlers and register process.

        Call this after initializing your service but before entering
        the main loop.
        """
        # Register process
        if self._register_process:
            self._registry.register(self.service_name, os.getpid())
            logger.info(f"Registered service '{self.service_name}' with PID {os.getpid()}")

        # Install signal handlers
        self._original_sigterm = signal.signal(signal.SIGTERM, self._signal_handler)
        self._original_sigint = signal.signal(signal.SIGINT, self._signal_handler)

        logger.debug(f"Signal handlers installed for '{self.service_name}'")

    def register_cleanup(self, callback: Callable[[], None]) -> None:
        """
        Register a cleanup callback to be called during shutdown.

        Callbacks are executed in LIFO order (last registered, first called).

        Args:
            callback: Function to call during shutdown (should be fast)
        """
        self._cleanup_callbacks.append(callback)
        logger.debug(f"Registered cleanup callback: {callback.__name__}")

    def request_shutdown(self) -> None:
        """Request a graceful shutdown (can be called programmatically)."""
        logger.info(f"Shutdown requested for '{self.service_name}'")
        self._is_running = False
        self._shutdown_event.set()

    def wait_for_shutdown(self, check_interval: float = 0.5) -> None:
        """
        Wait for shutdown signal.

        This is useful for services that don't have their own event loop.

        Args:
            check_interval: How often to check for shutdown (seconds)
        """
        while self.is_running:
            time.sleep(check_interval)

    def shutdown(self) -> bool:
        """
        Execute shutdown sequence.

        Returns:
            True if shutdown completed within timeout, False otherwise
        """
        logger.info(f"Starting graceful shutdown for '{self.service_name}'...")
        start_time = time.time()

        # Mark as not running
        self._is_running = False

        # Execute cleanup callbacks in reverse order
        for callback in reversed(self._cleanup_callbacks):
            try:
                elapsed = time.time() - start_time
                if elapsed >= self.timeout:
                    logger.warning("Shutdown timeout reached, skipping remaining cleanup")
                    break

                logger.debug(f"Executing cleanup: {callback.__name__}")
                callback()

            except Exception as e:
                logger.error(f"Error in cleanup callback {callback.__name__}: {e}", exc_info=True)

        # Unregister from process registry
        if self._register_process:
            self._registry.unregister(self.service_name)
            logger.debug(f"Unregistered service '{self.service_name}'")

        # Restore original signal handlers
        if self._original_sigterm:
            signal.signal(signal.SIGTERM, self._original_sigterm)
        if self._original_sigint:
            signal.signal(signal.SIGINT, self._original_sigint)

        elapsed = time.time() - start_time
        success = elapsed < self.timeout

        if success:
            logger.info(f"Graceful shutdown completed in {elapsed:.2f}s")
        else:
            logger.warning(f"Shutdown completed but exceeded timeout ({elapsed:.2f}s > {self.timeout}s)")

        return success

    def _signal_handler(self, signum: int, frame) -> None:
        """Handle shutdown signals."""
        signal_name = signal.Signals(signum).name
        logger.info(f"Received {signal_name} signal")

        # Only handle first signal
        if not self._is_running:
            logger.warning(f"Already shutting down, ignoring {signal_name}")
            return

        self.request_shutdown()

    @contextmanager
    def running_context(self):
        """
        Context manager for running a service with graceful shutdown.

        Usage:
            shutdown = GracefulShutdown('my_service')
            with shutdown.running_context():
                while shutdown.is_running:
                    do_work()
        """
        try:
            self.setup()
            yield self
        finally:
            self.shutdown()


def setup_service_shutdown(
    service_name: str,
    cleanup_callbacks: Optional[List[Callable]] = None,
    timeout: int = 30,
) -> GracefulShutdown:
    """
    Convenience function to set up graceful shutdown for a service.

    Args:
        service_name: Name of the service
        cleanup_callbacks: Optional list of cleanup functions
        timeout: Shutdown timeout in seconds

    Returns:
        Configured GracefulShutdown instance
    """
    shutdown = GracefulShutdown(service_name, timeout=timeout)

    if cleanup_callbacks:
        for callback in cleanup_callbacks:
            shutdown.register_cleanup(callback)

    shutdown.setup()
    return shutdown
