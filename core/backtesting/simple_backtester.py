#!/usr/bin/env python3
"""
간단한 백테스트 시스템
일일 선정 데이터의 예상 수익률을 활용한 시뮬레이션
"""

import json
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

from core.utils.log_utils import get_logger
from core.backtesting.trading_costs import TradingCosts

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


class SimpleBacktester:
    """간단한 백테스터 (예상 수익률 기반 시뮬레이션)"""

    def __init__(self, initial_capital: float = 100000000):
        """
        Args:
            initial_capital: 초기 자본금 (기본: 1억원)
        """
        self.logger = logger
        self.initial_capital = initial_capital
        self.trading_costs = TradingCosts()  # 거래 비용 계산기

    def backtest_selection_strategy(
        self,
        start_date: str,
        end_date: str,
        selection_criteria: Dict,
        trading_config: Dict,
        strategy_name: str = "Default"
    ) -> BacktestResult:
        """선정 전략 백테스트

        일일 선정 데이터의 expected_return을 실제 수익률로 가정
        (현실성을 위해 50-70% 달성률 적용)

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
            trading_config.get('achievement_rate', 0.6),  # 예상 수익률 60% 달성
            trading_config.get('max_holding_days', 10)
        )

        # 3. 성과 분석
        result = self._analyze_performance(trades, start_date, end_date, strategy_name)

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

                        # 필드 정규화
                        for stock in stocks:
                            stock['selection_date'] = current_date.strftime("%Y-%m-%d")

                            # entry_price 없으면 current_price 사용
                            if 'entry_price' not in stock:
                                stock['entry_price'] = stock.get('current_price', 0)

                            # expected_return 없으면 target_price로부터 계산
                            if 'expected_return' not in stock:
                                entry = stock['entry_price']
                                target = stock.get('target_price', entry)
                                if entry > 0:
                                    stock['expected_return'] = (target - entry) / entry * 100
                                else:
                                    stock['expected_return'] = 0

                        selections.extend(stocks)

                except Exception as e:
                    self.logger.error(f"데이터 로드 실패 {date_str}: {e}", exc_info=True)

            current_date += timedelta(days=1)

        self.logger.info(f"과거 선정 데이터: {len(selections)}개 종목")
        return selections

    def _simulate_trading(
        self,
        selections: List[Dict],
        achievement_rate: float,
        max_holding_days: int
    ) -> List[Trade]:
        """매매 시뮬레이션 (현실적 버전)

        Args:
            selections: 일일 선정 종목 리스트
            achievement_rate: 예상 수익률 달성률 (0.5 = 50%)
            max_holding_days: 최대 보유 기간
        """
        trades = []

        # 날짜별 그룹화
        by_date = {}
        for sel in selections:
            date = sel.get('selection_date', '2025-01-01')
            if date not in by_date:
                by_date[date] = []
            by_date[date].append(sel)

        # 날짜별로 최대 5종목만 선택
        for date, daily_stocks in sorted(by_date.items()):
            # 상위 5종목만 (confidence 또는 total_score 기준)
            daily_stocks.sort(key=lambda x: x.get('confidence', 0) or x.get('total_score', 0), reverse=True)
            selected = daily_stocks[:5]

            for sel in selected:
                # 예상 수익률 조회
                expected_return = sel.get('expected_return', 0) / 100  # 퍼센트 → 소수

                # 실제 수익률 = 예상 수익률 × 달성률 × 랜덤 노이즈
                # 노이즈: -1.0~1.5 범위 (손실 가능성 포함)
                noise = np.random.uniform(-1.0, 1.5)
                actual_return = expected_return * achievement_rate * noise

                # 거래 비용 반영
                entry_price = sel.get('entry_price', 0)
                if entry_price <= 0:
                    continue

                quantity = 100  # 고정 수량

                # 비용 반영 전 청산가
                gross_exit_price = entry_price * (1 + actual_return)

                # 순손익 계산 (비용 반영)
                net_pnl = self.trading_costs.calculate_net_pnl(
                    buy_price=entry_price,
                    sell_price=gross_exit_price,
                    quantity=quantity
                )

                # 실제 수익률 (비용 반영 후)
                buy_cost = self.trading_costs.calculate_buy_cost(entry_price, quantity)
                net_return = net_pnl / buy_cost if buy_cost > 0 else 0

                # 청산 사유 판단
                if net_return >= 0.10:  # 10% 이상 익절
                    exit_reason = "take_profit"
                elif net_return <= -0.05:  # -5% 이하 손절
                    exit_reason = "stop_loss"
                else:
                    exit_reason = "time_limit"

                # 보유 기간 (랜덤 3~10일)
                holding_days = np.random.randint(3, max_holding_days + 1)

                # Trade 생성
                entry_date = sel.get('selection_date', '2025-01-01')
                exit_date = (datetime.strptime(entry_date, "%Y-%m-%d") +
                            timedelta(days=holding_days)).strftime("%Y-%m-%d")

                trade = Trade(
                    stock_code=sel.get('stock_code', 'UNKNOWN'),
                    stock_name=sel.get('stock_name', 'Unknown'),
                    entry_date=entry_date,
                    entry_price=entry_price,
                    exit_date=exit_date,
                    exit_price=gross_exit_price,
                    quantity=quantity,
                    return_pct=net_return,
                    holding_days=holding_days,
                    exit_reason=exit_reason
                )

                trades.append(trade)

        return trades

    def _analyze_performance(self, trades: List[Trade], start_date: str, end_date: str, strategy_name: str) -> BacktestResult:
        """성과 분석"""
        if not trades:
            return self._empty_result(strategy_name)

        # 거래 분류
        returns = [t.return_pct for t in trades if t.return_pct is not None]
        winning_trades = [t for t in trades if t.return_pct and t.return_pct > 0]
        losing_trades = [t for t in trades if t.return_pct and t.return_pct < 0]

        # 기본 지표
        win_rate = len(winning_trades) / len(trades) if trades else 0
        avg_return = np.mean(returns) if returns else 0
        avg_win = np.mean([t.return_pct for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([t.return_pct for t in losing_trades]) if losing_trades else 0

        total_return = sum(returns)
        best_trade = max(returns) if returns else 0
        worst_trade = min(returns) if returns else 0

        # Max Drawdown (간단한 계산)
        cumulative_returns = np.cumsum(returns)
        running_max = np.maximum.accumulate(cumulative_returns)
        drawdowns = cumulative_returns - running_max
        max_drawdown = min(drawdowns) if len(drawdowns) > 0 else 0

        # Sharpe Ratio (연율화)
        sharpe = (np.mean(returns) / np.std(returns) * np.sqrt(252)) if len(returns) > 1 and np.std(returns) > 0 else 0

        # Profit Factor
        total_profit = sum([t.return_pct for t in winning_trades]) if winning_trades else 0
        total_loss = abs(sum([t.return_pct for t in losing_trades])) if losing_trades else 0
        profit_factor = total_profit / total_loss if total_loss > 0 else 0

        # 평균 보유 기간
        avg_holding_days = np.mean([t.holding_days for t in trades if t.holding_days is not None]) if trades else 0

        self.logger.info(
            f"성과 분석 완료 - "
            f"총거래: {len(trades)}건, 승률: {win_rate:.1%}, "
            f"평균수익률: {avg_return:.2%}, 총수익률: {total_return:.2%}"
        )

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
