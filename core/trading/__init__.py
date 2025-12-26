# -*- coding: utf-8 -*-
"""
Trading module

Includes:
- TradingEngine: Auto trading execution engine
- DynamicStopLossCalculator: ATR-based dynamic stop loss/take profit
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

__all__ = [
    'DynamicStopLossCalculator',
    'StopLossResult',
    'TrailingStopState',
    'calculate_dynamic_stops',
    'calculate_atr',
]
