#!/usr/bin/env python3
"""
전략 백테스트 시스템
과거 데이터로 선정 기준 및 매매 전략 검증
"""

import json
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List
from dataclasses import asdict

from core.utils.log_utils import get_logger
from core.api.kis_api import KISAPI
from core.backtesting.trading_costs import TradingCosts
from core.backtesting.models import BacktestResult, Trade

logger = get_logger(__name__)


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
        self.trading_costs = TradingCosts()  # 거래 비용 계산기
        self.price_data_cache = {}  # 가격 데이터 캐시 (look-ahead bias 방지)

    def _to_datetime(self, date_value) -> datetime:
        """str 또는 datetime 객체를 datetime으로 변환"""
        if isinstance(date_value, datetime):
            return date_value
        elif isinstance(date_value, str):
            return datetime.strptime(date_value, "%Y-%m-%d")
        else:
            raise TypeError(f"Unsupported date type: {type(date_value)}")

    def backtest_selection_strategy(
        self,
        start_date: str,
        end_date: str,
        selection_criteria: Dict,
        trading_config: Dict,
        strategy_name: str = "Default"
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
            return BacktestResult.empty("No Data")

        # 2. 가격 데이터 로드 (look-ahead bias 방지)
        self._load_price_data_for_backtest(daily_selections, start_date, end_date)

        # 3. 시뮬레이션 실행
        trades = self._simulate_trading(
            daily_selections,
            trading_config.get('stop_loss_pct', 0.03),
            trading_config.get('take_profit_pct', 0.08),
            trading_config.get('max_holding_days', 10),
            trading_config.get('max_positions', 10)
        )

        # 4. 성과 분석
        result = self._analyze_performance(trades, start_date, end_date, "Historical Strategy")

        self.logger.info(f"백테스트 완료: 승률 {result.win_rate:.1%}, 총수익률 {result.total_return:.2%}")

        return result

    def _load_historical_selections(self, start_date: str, end_date: str) -> List[Dict]:
        """과거 일일 선정 데이터 로드"""
        selections = []

        # datetime 객체가 전달된 경우 문자열로 변환
        if isinstance(start_date, datetime):
            start_date = start_date.strftime("%Y-%m-%d")
        if isinstance(end_date, datetime):
            end_date = end_date.strftime("%Y-%m-%d")

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

    def _load_price_data_for_backtest(self, selections: List[Dict], start_date: str, end_date: str):
        """백테스트용 과거 가격 데이터 로드 (look-ahead bias 방지)

        전체 백테스트 기간의 가격 데이터를 미리 로드하여 캐시에 저장.
        시뮬레이션 시 해당 날짜까지의 데이터만 참조하도록 함.
        """
        import pandas as pd

        # 종목 코드 추출
        stock_codes = set(sel['stock_code'] for sel in selections)
        self.logger.info(f"가격 데이터 로드 시작: {len(stock_codes)}개 종목")

        # datetime 변환
        if isinstance(start_date, str):
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        else:
            start_dt = start_date

        if isinstance(end_date, str):
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        else:
            end_dt = end_date

        # 각 종목의 가격 데이터 로드
        for code in stock_codes:
            try:
                # API를 통해 과거 데이터 조회 (충분한 기간)
                # period=100: 백테스트 기간 + 여유분
                price_df = self.api.get_daily_prices(code, period=100)

                if price_df is None or price_df.empty:
                    self.logger.warning(f"가격 데이터 없음: {code}")
                    continue

                # 인덱스를 datetime으로 변환
                if not isinstance(price_df.index, pd.DatetimeIndex):
                    price_df.index = pd.to_datetime(price_df.index)

                # 백테스트 기간 내 데이터만 필터링
                mask = (price_df.index >= start_dt) & (price_df.index <= end_dt)
                filtered_df = price_df.loc[mask]

                if not filtered_df.empty:
                    self.price_data_cache[code] = filtered_df
                    self.logger.debug(f"가격 데이터 로드 완료: {code} ({len(filtered_df)}일)")
                else:
                    self.logger.warning(f"백테스트 기간 내 데이터 없음: {code}")

            except Exception as e:
                self.logger.error(f"가격 데이터 로드 실패: {code} - {e}", exc_info=True)

        self.logger.info(f"가격 데이터 로드 완료: {len(self.price_data_cache)}개 종목")

    def _simulate_trading(
        self,
        selections: List[Dict],
        stop_loss_pct: float,
        take_profit_pct: float,
        max_holding_days: int,
        max_positions: int = 10
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
            # max_positions는 메서드 파라미터로 전달됨
            if len(portfolio) < max_positions:
                for sel in by_date[date][:max_positions-len(portfolio)]:
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
            trade.holding_days = (
                self._to_datetime(trade.exit_date)
                - self._to_datetime(trade.entry_date)
            ).days
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
        """청산 여부 체크 (과거 데이터 기반, look-ahead bias 방지)"""
        closed = []
        to_remove = []

        for code, trade in portfolio.items():
            holding_days = (
                self._to_datetime(current_date)
                - self._to_datetime(trade.entry_date)
            ).days

            if holding_days == 0:
                continue

            # 캐시된 가격 데이터 조회 (look-ahead bias 방지)
            try:
                if code not in self.price_data_cache:
                    self.logger.warning(f"가격 데이터 없음: {code}")
                    continue

                price_df = self.price_data_cache[code]

                # current_date의 datetime 변환
                current_dt = self._to_datetime(current_date)

                # current_date까지의 데이터만 사용 (미래 데이터 차단)
                # 인덱스가 date 타입인 경우와 datetime 타입인 경우 모두 처리
                if hasattr(price_df.index, 'date'):
                    mask = price_df.index.date <= current_dt.date()
                else:
                    mask = price_df.index <= current_dt

                historical_data = price_df.loc[mask]

                if historical_data.empty:
                    self.logger.warning(f"해당 날짜 가격 데이터 없음: {code} on {current_date}")
                    continue

                # 해당 날짜의 종가 사용
                current_price = historical_data.iloc[-1]['close']

                if current_price <= 0:
                    self.logger.warning(f"유효하지 않은 가격: {code} - {current_price}원")
                    continue

                # 실제 수익률 계산
                return_pct = (current_price - trade.entry_price) / trade.entry_price

                exit_triggered = False

                # 손절 조건
                if return_pct <= -stop_loss_pct:
                    trade.return_pct = return_pct
                    trade.exit_reason = "stop_loss"
                    exit_triggered = True

                # 익절 조건
                elif return_pct >= take_profit_pct:
                    trade.return_pct = return_pct
                    trade.exit_reason = "take_profit"
                    exit_triggered = True

                # 보유 기간 초과
                elif holding_days >= max_holding_days:
                    trade.return_pct = return_pct
                    trade.exit_reason = "time_limit"
                    exit_triggered = True

                if exit_triggered:
                    trade.exit_date = current_date
                    trade.exit_price = current_price
                    trade.holding_days = holding_days
                    closed.append(trade)
                    to_remove.append(code)

                    self.logger.debug(
                        f"청산: {code} - 진입가 {trade.entry_price:,.0f}원, "
                        f"청산가 {current_price:,.0f}원, 수익률 {return_pct:+.2%}, "
                        f"사유: {trade.exit_reason}"
                    )

            except Exception as e:
                self.logger.error(
                    f"청산 체크 오류: {code} on {current_date} - {e}",
                    exc_info=True
                )
                continue

        for code in to_remove:
            del portfolio[code]

        return closed

    def _analyze_performance(self, trades: List[Trade], start_date: str, end_date: str, strategy_name: str) -> BacktestResult:
        """성과 분석 (거래 비용 반영)"""
        if not trades:
            return BacktestResult.empty(strategy_name)

        # 거래 비용을 반영한 실제 수익률 재계산
        adjusted_returns = []
        for t in trades:
            if t.return_pct is None or t.entry_price is None or t.exit_price is None:
                continue

            if t.quantity <= 0:
                self.logger.warning(f"유효하지 않은 수량: {t.stock_code}, quantity={t.quantity}")
                continue

            try:
                # 순손익 계산 (비용 반영)
                net_pnl = self.trading_costs.calculate_net_pnl(
                    buy_price=t.entry_price,
                    sell_price=t.exit_price,
                    quantity=t.quantity
                )

                # 실제 수익률 (비용 반영 후)
                buy_cost = self.trading_costs.calculate_buy_cost(t.entry_price, t.quantity)
                adjusted_return_pct = net_pnl / buy_cost if buy_cost > 0 else 0

                adjusted_returns.append(adjusted_return_pct)

                # Trade 객체 업데이트 (비용 반영 수익률로)
                t.return_pct = adjusted_return_pct

            except Exception as e:
                self.logger.error(f"거래 비용 계산 실패 ({t.stock_code}): {e}", exc_info=True)
                continue

        if not adjusted_returns:
            return BacktestResult.empty(strategy_name)

        winning_trades = [t for t in trades if t.return_pct and t.return_pct > 0]
        losing_trades = [t for t in trades if t.return_pct and t.return_pct < 0]

        win_rate = len(winning_trades) / len(trades) if trades else 0
        avg_return = np.mean(adjusted_returns)
        avg_win = np.mean([t.return_pct for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([t.return_pct for t in losing_trades]) if losing_trades else 0

        total_return = sum(adjusted_returns)

        # ✅ MF-3 수정: Max Drawdown (누적 수익률 곡선 기반)
        cumulative_returns = np.cumsum(adjusted_returns)
        running_max = np.maximum.accumulate(cumulative_returns)
        drawdowns = cumulative_returns - running_max
        max_drawdown = min(drawdowns) if len(drawdowns) > 0 else 0

        # Sharpe Ratio (간단한 계산)
        sharpe = np.mean(adjusted_returns) / np.std(adjusted_returns) * np.sqrt(252) if len(adjusted_returns) > 1 else 0

        # Profit Factor
        total_profit = sum([t.return_pct for t in winning_trades])
        total_loss = abs(sum([t.return_pct for t in losing_trades]))
        profit_factor = total_profit / total_loss if total_loss > 0 else 0

        best_trade = max(adjusted_returns) if adjusted_returns else 0
        worst_trade = min(adjusted_returns) if adjusted_returns else 0

        avg_holding_days = np.mean([t.holding_days for t in trades if t.holding_days is not None]) if trades else 0

        self.logger.info(
            f"성과 분석 완료 (거래비용 반영) - "
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

    def save_result(self, result: BacktestResult, output_path: str):
        """결과 저장"""
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(asdict(result), f, indent=2, ensure_ascii=False)
        self.logger.info(f"백테스트 결과 저장: {output_path}")
