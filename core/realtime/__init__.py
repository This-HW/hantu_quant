"""
Real-time data processing package.
"""

from .processor import DataProcessor
from .handlers import EventHandler

__all__ = [
    'DataProcessor',
    'EventHandler'
] 