"""
Process Management Package

Provides process registry and lifecycle management for Hantu Quant services.
"""

from core.process.registry import ProcessRegistry, ProcessStatus
from core.process.shutdown import GracefulShutdown, setup_service_shutdown

__all__ = [
    'ProcessRegistry',
    'ProcessStatus',
    'GracefulShutdown',
    'setup_service_shutdown',
]
