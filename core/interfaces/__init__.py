"""
Core interfaces for the Hantu Quant system.

This module provides the core interfaces that define the contracts
for various components of the system, enabling loose coupling and
better testability.
"""

from .api import IAPIClient, IDataProvider, IWebSocketClient
from .analysis import IStockScreener, IPriceAnalyzer, ITechnicalIndicator
from .trading import ITradingStrategy, ITrader, IPositionManager
from .config import IConfigProvider, IAPIConfig, ITradingConfig
from .events import IEventBus, IEventHandler, IEvent
from .data import IDataRepository, StockInfo, PriceData

__all__ = [
    # API interfaces
    'IAPIClient',
    'IDataProvider',
    'IWebSocketClient',
    
    # Analysis interfaces
    'IStockScreener',
    'IPriceAnalyzer',
    'ITechnicalIndicator',
    
    # Trading interfaces
    'ITradingStrategy',
    'ITrader',
    'IPositionManager',
    
    # Configuration interfaces
    'IConfigProvider',
    'IAPIConfig',
    'ITradingConfig',
    
    # Event interfaces
    'IEventBus',
    'IEventHandler',
    'IEvent',
    
    # Data interfaces
    'IDataRepository',
    'StockInfo',
    'PriceData',
] 