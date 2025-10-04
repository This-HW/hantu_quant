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

# Phase 4: AI 학습 시스템 인터페이스 (새로운 아키텍처)
from .learning import (
    ILearningDataCollector, IFeatureEngineer, IModelTrainer, 
    IPerformanceAnalyzer, IPatternLearner, IParameterOptimizer,
    IBacktestAutomation, ILearningEngine,
    LearningData, FeatureSet, ModelPrediction, PerformanceMetrics,
    PatternResult, OptimizationResult, ModelType, LearningPhase
)

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
    
    # Learning interfaces (Phase 4)
    'ILearningDataCollector',
    'IFeatureEngineer',
    'IModelTrainer',
    'IPerformanceAnalyzer',
    'IPatternLearner',
    'IParameterOptimizer',
    'IBacktestAutomation',
    'ILearningEngine',
    
    # Learning data classes
    'LearningData',
    'FeatureSet',
    'ModelPrediction',
    'PerformanceMetrics',
    'PatternResult',
    'OptimizationResult',
    'ModelType',
    'LearningPhase',
] 