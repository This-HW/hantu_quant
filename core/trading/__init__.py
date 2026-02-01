# -*- coding: utf-8 -*-
"""
Trading module

Includes:
- TradingEngine: Auto trading execution engine
- DynamicStopLossCalculator: ATR-based dynamic stop loss/take profit
- MarketAdaptiveRisk: Market volatility based risk management
- TradeJournal: Trade logging
- SellEngine: Sell engine
- AutoTrader: Auto trader
- CircuitHandler: Circuit breaker response handler (Batch 4-2)
- OpportunityDetector: Additional buy opportunity detection (Batch 4-1)
- DailySummaryGenerator: Daily performance summary (Batch 4-3)
"""

from .dynamic_stop_loss import (
    DynamicStopLossCalculator,
    StopLossResult,
    TrailingStopState,
    calculate_dynamic_stops,
    calculate_atr,
)

from .market_adaptive_risk import (
    MarketAdaptiveRisk,
    MarketVolatility,
    MarketState,
    RiskConfig,
    analyze_market_risk,
    get_risk_config_for_volatility,
)

from .validators import (
    TradingInputValidator,
    ValidationResult,
    ValidationLevel,
    ValidationError,
    StockCodeValidator,
    PriceValidator,
    QuantityValidator,
    OrderValidator,
    validate_stock_code,
    validate_price,
    validate_quantity,
)

from .circuit_handler import (
    CircuitHandler,
    CircuitResponse,
)

from .opportunity_detector import (
    OpportunityDetector,
    OpportunityConfig,
    AdditionalBuyOpportunity,
)

from .daily_summary import (
    DailySummaryGenerator,
    DailySummaryReport,
    TradeSummary,
    PositionSummary,
)

__all__ = [
    # Dynamic Stop Loss (P1-1)
    'DynamicStopLossCalculator',
    'StopLossResult',
    'TrailingStopState',
    'calculate_dynamic_stops',
    'calculate_atr',
    # Market Adaptive Risk (P1-5)
    'MarketAdaptiveRisk',
    'MarketVolatility',
    'MarketState',
    'RiskConfig',
    'analyze_market_risk',
    'get_risk_config_for_volatility',
    # Validators (N-03)
    'TradingInputValidator',
    'ValidationResult',
    'ValidationLevel',
    'ValidationError',
    'StockCodeValidator',
    'PriceValidator',
    'QuantityValidator',
    'OrderValidator',
    'validate_stock_code',
    'validate_price',
    'validate_quantity',
    # Circuit Handler (Batch 4-2)
    'CircuitHandler',
    'CircuitResponse',
    # Opportunity Detector (Batch 4-1)
    'OpportunityDetector',
    'OpportunityConfig',
    'AdditionalBuyOpportunity',
    # Daily Summary (Batch 4-3)
    'DailySummaryGenerator',
    'DailySummaryReport',
    'TradeSummary',
    'PositionSummary',
]
