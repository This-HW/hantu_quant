"""
앙상블 전략 시스템

LSTM + 기술적분석 + 수급분석을 결합한 멀티 전략 앙상블
"""

from .signal import Signal, SignalType, SignalSource, FinalSignal
from .signal_aggregator import SignalAggregator, AggregatorConfig
from .ensemble_engine import EnsembleEngine, EnsembleConfig, LSTMSignalGenerator
from .ta_scorer import TechnicalAnalysisScorer, TAScores
from .supply_demand_scorer import SupplyDemandScorer, SDScores
from .weight_optimizer import WeightOptimizer, OptimizerConfig, PerformanceRecord

__all__ = [
    # Signal types
    'Signal',
    'SignalType',
    'SignalSource',
    'FinalSignal',
    # Aggregator
    'SignalAggregator',
    'AggregatorConfig',
    # Ensemble Engine
    'EnsembleEngine',
    'EnsembleConfig',
    'LSTMSignalGenerator',
    # Scorers
    'TechnicalAnalysisScorer',
    'TAScores',
    'SupplyDemandScorer',
    'SDScores',
    # Weight Optimizer
    'WeightOptimizer',
    'OptimizerConfig',
    'PerformanceRecord',
]
