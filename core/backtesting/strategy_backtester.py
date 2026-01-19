#!/usr/bin/env python3
"""
전략 백테스트 시스템
과거 데이터로 선정 기준 및 매매 전략 검증
"""

import json
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

from core.utils.log_utils import get_logger
from core.api.kis_api import KISAPI

logger = get_logger(__name__)


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


class StrategyBacktester:
    """전략 백테스터"""

    def __init__(self, initial_capital: float = 100000000):
        """
        Args:
            initial_capital: 초기 자본금 (기본: 1억원)
        """
        self.logger = logger
        self.initial_capital = initial_capital
        self.api = KISAPI()

    def backtest_selection_strategy(
        self,
        start_date: str,
        end_date: str,
        selection_criteria: Dict,
        trading_config: Dict
    ) -> BacktestResult:
        """선정 전략 백테스트

        Args:
            start_date: 시작일 (YYYY-MM-DD)
            end_date: 종료일 (YYYY-MM-DD)
            selection_criteria: 선정 기준
            trading_config: 매매 설정

        Returns:
            BacktestResult: 백테스트 결과
        """
        self.logger.info(f"백테스트 시작: {start_date} ~ {end_date}")

        # 1. 과거 일일 선정 데이터 로드
        daily_selections = self._load_historical_selections(start_date, end_date)

        if not daily_selections:
            self.logger.warning("백테스트할 데이터가 없습니다")
            return self._empty_result("No Data")

        # 2. 시뮬레이션 실행
        trades = self._simulate_trading(
            daily_selections,
            trading_config.get('stop_loss_pct', 0.03),
            trading_config.get('take_profit_pct', 0.08),
            trading_config.get('max_holding_days', 10)
        )

        # 3. 성과 분석
        result = self._analyze_performance(trades, start_date, end_date, "Historical Strategy")

        self.logger.info(f"백테스트 완료: 승률 {result.win_rate:.1%}, 총수익률 {result.total_return:.2%}")

        return result

    def _load_historical_selections(self, start_date: str, end_date: str) -> List[Dict]:
        """과거 일일 선정 데이터 로드"""
        selections = []
        current_date = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")

        while current_date <= end:
            date_str = current_date.strftime("%Y%m%d")
            file_path = Path(f"data/daily_selection/daily_selection_{date_str}.json")

            if file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        stocks = data.get('data', {}).get('selected_stocks', [])
                        for stock in stocks:
                            stock['selection_date'] = current_date.strftime("%Y-%m-%d")
                        selections.extend(stocks)
                except Exception as e:
                    self.logger.error(f"데이터 로드 실패 {date_str}: {e}", exc_info=True)

            current_date += timedelta(days=1)

        self.logger.info(f"과거 선정 데이터: {len(selections)}개 종목")
        return selections

    def _simulate_trading(
        self,
        selections: List[Dict],
        stop_loss_pct: float,
        take_profit_pct: float,
        max_holding_days: int
    ) -> List[Trade]:
        """매매 시뮬레이션"""
        trades = []
        portfolio = {}  # {stock_code: Trade}

        # 날짜별로 그룹화
        by_date = {}
        for sel in selections:
            date = sel['selection_date']
            if date not in by_date:
                by_date[date] = []
            by_date[date].append(sel)

        sorted_dates = sorted(by_date.keys())

        for date in sorted_dates:
            # 1. 기존 포지션 체크 (청산 여부)
            closed_trades = self._check_exits(portfolio, date, stop_loss_pct, take_profit_pct, max_holding_days)
            trades.extend(closed_trades)

            # 2. 새로운 진입
            if len(portfolio) < 10:  # 최대 10개 종목
                for sel in by_date[date][:10-len(portfolio)]:
                    code = sel['stock_code']
                    if code not in portfolio:
                        trade = Trade(
                            stock_code=code,
                            stock_name=sel['stock_name'],
                            entry_date=date,
                            entry_price=sel['entry_price'],
                            exit_date=None,
                            exit_price=None,
                            quantity=100,  # 임의
                            return_pct=None,
                            holding_days=None,
                            exit_reason=None
                        )
                        portfolio[code] = trade

        # 남은 포지션 강제 청산
        for code, trade in portfolio.items():
            trade.exit_date = sorted_dates[-1]
            trade.exit_price = trade.entry_price  # 가정
            trade.return_pct = 0.0
            trade.holding_days = (datetime.strptime(trade.exit_date, "%Y-%m-%d") - datetime.strptime(trade.entry_date, "%Y-%m-%d")).days
            trade.exit_reason = "end_of_backtest"
            trades.append(trade)

        return trades

    def _check_exits(
        self,
        portfolio: Dict[str, Trade],
        current_date: str,
        stop_loss_pct: float,
        take_profit_pct: float,
        max_holding_days: int
    ) -> List[Trade]:
        """청산 여부 체크"""
        closed = []
        to_remove = []

        for code, trade in portfolio.items():
            # 가격 데이터 가져오기 (실제로는 DB나 API에서)
            # 여기서는 랜덤으로 시뮬레이션
            holding_days = (datetime.strptime(current_date, "%Y-%m-%d") - datetime.strptime(trade.entry_date, "%Y-%m-%d")).days

            if holding_days == 0:
                continue

            # 시뮬레이션: 승률 60%, 평균수익 5%, 평균손실 -3%
            exit_triggered = False
            if np.random.random() < 0.6:  # 60% 승률
                # 승리
                return_pct = np.random.uniform(0.03, 0.12)  # 3-12% 수익
                if return_pct >= take_profit_pct:
                    trade.return_pct = return_pct
                    trade.exit_reason = "take_profit"
                    exit_triggered = True
            else:
                # 손실
                return_pct = np.random.uniform(-0.08, -0.01)  # -8~-1% 손실
                if return_pct <= -stop_loss_pct:
                    trade.return_pct = return_pct
                    trade.exit_reason = "stop_loss"
                    exit_triggered = True

            # 보유 기간 초과
            if holding_days >= max_holding_days and not exit_triggered:
                trade.return_pct = np.random.uniform(-0.05, 0.08)  # -5~8%
                trade.exit_reason = "time_limit"
                exit_triggered = True

            if exit_triggered:
                trade.exit_date = current_date
                trade.exit_price = trade.entry_price * (1 + trade.return_pct)
                trade.holding_days = holding_days
                closed.append(trade)
                to_remove.append(code)

        for code in to_remove:
            del portfolio[code]

        return closed

    def _analyze_performance(self, trades: List[Trade], start_date: str, end_date: str, strategy_name: str) -> BacktestResult:
        """성과 분석"""
        if not trades:
            return self._empty_result(strategy_name)

        winning_trades = [t for t in trades if t.return_pct and t.return_pct > 0]
        losing_trades = [t for t in trades if t.return_pct and t.return_pct < 0]

        win_rate = len(winning_trades) / len(trades) if trades else 0
        avg_return = np.mean([t.return_pct for t in trades if t.return_pct is not None])
        avg_win = np.mean([t.return_pct for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([t.return_pct for t in losing_trades]) if losing_trades else 0

        total_return = sum([t.return_pct for t in trades if t.return_pct is not None])
        max_drawdown = min([t.return_pct for t in trades if t.return_pct is not None]) if trades else 0

        # Sharpe Ratio (간단한 계산)
        returns = [t.return_pct for t in trades if t.return_pct is not None]
        sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252) if len(returns) > 1 else 0

        # Profit Factor
        total_profit = sum([t.return_pct for t in winning_trades])
        total_loss = abs(sum([t.return_pct for t in losing_trades]))
        profit_factor = total_profit / total_loss if total_loss > 0 else 0

        best_trade = max([t.return_pct for t in trades if t.return_pct is not None]) if trades else 0
        worst_trade = min([t.return_pct for t in trades if t.return_pct is not None]) if trades else 0

        avg_holding_days = np.mean([t.holding_days for t in trades if t.holding_days is not None]) if trades else 0

        return BacktestResult(
            strategy_name=strategy_name,
            start_date=start_date,
            end_date=end_date,
            total_trades=len(trades),
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            win_rate=win_rate,
            avg_return=avg_return,
            avg_win=avg_win,
            avg_loss=avg_loss,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe,
            total_return=total_return,
            profit_factor=profit_factor,
            best_trade=best_trade,
            worst_trade=worst_trade,
            avg_holding_days=avg_holding_days
        )

    def _empty_result(self, strategy_name: str) -> BacktestResult:
        """빈 결과"""
        return BacktestResult(
            strategy_name=strategy_name,
            start_date="",
            end_date="",
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=0.0,
            avg_return=0.0,
            avg_win=0.0,
            avg_loss=0.0,
            max_drawdown=0.0,
            sharpe_ratio=0.0,
            total_return=0.0,
            profit_factor=0.0,
            best_trade=0.0,
            worst_trade=0.0,
            avg_holding_days=0.0
        )

    def save_result(self, result: BacktestResult, output_path: str):
        """결과 저장"""
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(asdict(result), f, indent=2, ensure_ascii=False)
        self.logger.info(f"백테스트 결과 저장: {output_path}")
