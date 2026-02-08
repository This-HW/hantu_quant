#!/usr/bin/env python3
"""
백테스팅 공통 데이터 모델
SSOT 원칙에 따라 단일 출처에서 관리
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class BacktestResult:
    """백테스트 결과"""
    strategy_name: str
    start_date: str
    end_date: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_return: float
    avg_win: float
    avg_loss: float
    max_drawdown: float
    sharpe_ratio: float
    total_return: float
    profit_factor: float  # 총이익 / 총손실
    best_trade: float
    worst_trade: float
    avg_holding_days: float


@dataclass
class Trade:
    """거래 기록"""
    stock_code: str
    stock_name: str
    entry_date: str
    entry_price: float
    exit_date: Optional[str]
    exit_price: Optional[float]
    quantity: int
    return_pct: Optional[float]
    holding_days: Optional[int]
    exit_reason: Optional[str]  # "stop_loss", "take_profit", "time_limit"
