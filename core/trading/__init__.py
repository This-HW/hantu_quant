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
]
