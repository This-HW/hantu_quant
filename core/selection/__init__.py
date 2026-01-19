"""
Selection 모듈 - 모멘텀 기반 종목 선정 시스템

30년 퀀트 경험 기반 단순하고 견고한 시스템

Components:
- quant_config: 통합 설정
- momentum_selector: 모멘텀 기반 선정
- position_sizer: ATR 기반 포지션 사이징
- realtime_feedback: 실시간 피드백 루프
"""

from core.selection.quant_config import (
    QuantConfig,
    get_quant_config,
    reset_quant_config,
    MarketRegime,
    LiquidityFilter,
    MomentumConfig,
    PositionSizingConfig,
    FeedbackConfig,
    RegimeConfig,
)

from core.selection.momentum_selector import (
    MomentumSelector,
    MomentumScore,
    SelectionResult,
)

from core.selection.position_sizer import (
    PositionSizer,
    PositionSize,
)

from core.selection.realtime_feedback import (
    RealtimeFeedbackLoop,
    get_feedback_loop,
    RollingPerformanceTracker,
    AdaptiveParameterStore,
    TradeResult,
    PerformanceStats,
)

__all__ = [
    # Config
    'QuantConfig',
    'get_quant_config',
    'reset_quant_config',
    'MarketRegime',
    'LiquidityFilter',
    'MomentumConfig',
    'PositionSizingConfig',
    'FeedbackConfig',
    'RegimeConfig',

    # Selector
    'MomentumSelector',
    'MomentumScore',
    'SelectionResult',

    # Position Sizer
    'PositionSizer',
    'PositionSize',

    # Feedback
    'RealtimeFeedbackLoop',
    'get_feedback_loop',
    'RollingPerformanceTracker',
    'AdaptiveParameterStore',
    'TradeResult',
    'PerformanceStats',
]
