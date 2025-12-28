"""
페이퍼 트레이딩 모듈

실제 자금 없이 전략을 테스트할 수 있는 시뮬레이션 환경을 제공합니다.
"""

from .virtual_portfolio import (
    VirtualPortfolio,
    PortfolioConfig,
    PortfolioSnapshot,
)
from .order_executor import (
    OrderExecutor,
    Order,
    OrderType,
    OrderSide,
    OrderStatus,
    ExecutionResult,
)
from .position_tracker import (
    PositionTracker,
    Position,
    PositionStatus,
    PositionSummary,
)
from .paper_trader import (
    PaperTrader,
    PaperTradingConfig,
    TradingSession,
)
from .order_state_machine import (
    OrderStateMachine,
    OrderStateMachineManager,
    OrderState,
    OrderEvent,
    StateTransition,
    InvalidTransitionError,
)

__all__ = [
    # Portfolio
    'VirtualPortfolio',
    'PortfolioConfig',
    'PortfolioSnapshot',
    # Order
    'OrderExecutor',
    'Order',
    'OrderType',
    'OrderSide',
    'OrderStatus',
    'ExecutionResult',
    # Position
    'PositionTracker',
    'Position',
    'PositionStatus',
    'PositionSummary',
    # Trader
    'PaperTrader',
    'PaperTradingConfig',
    'TradingSession',
    # State Machine
    'OrderStateMachine',
    'OrderStateMachineManager',
    'OrderState',
    'OrderEvent',
    'StateTransition',
    'InvalidTransitionError',
]
