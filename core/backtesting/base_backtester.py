#!/usr/bin/env python3
"""
백테스터 추상 베이스 클래스
Template Method Pattern 적용
"""

import json
import numpy as np
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List
from dataclasses import asdict

from core.utils.log_utils import get_logger
from core.api.kis_api import KISAPI
from core.backtesting.trading_costs import TradingCosts
from core.backtesting.models import BacktestResult, Trade

logger = get_logger(__name__)


class BaseBacktester(ABC):
    """백테스터 추상 베이스 클래스

    Template Method Pattern:
    - backtest(): 템플릿 메서드 (공통 플로우)
    - _simulate_trading(): 추상 메서드 (전략별 구현)
    - _get_strategy_name(): 추상 메서드 (전략명 반환)
    """

    def __init__(self, initial_capital: float = 100000000):
        """
        Args:
            initial_capital: 초기 자본금 (기본: 1억원)
        """
        self.logger = logger
        self.initial_capital = initial_capital
        self.api = KISAPI()
        self.trading_costs = TradingCosts()
        self.price_data_cache: Dict = {}  # 가격 데이터 캐시

    def backtest(
        self,
        start_date: str,
        end_date: str,
        **kwargs
    ) -> BacktestResult:
        """백테스트 템플릿 메서드 (공통 플로우)

        Args:
            start_date: 시작일 (YYYY-MM-DD)
            end_date: 종료일 (YYYY-MM-DD)
            **kwargs: 전략별 추가 파라미터

        Returns:
            BacktestResult: 백테스트 결과
        """
        strategy_name = self._get_strategy_name()
        self.logger.info(f"백테스트 시작 [{strategy_name}]: {start_date} ~ {end_date}")

        try:
            # 캐시 초기화 (이전 backtest 잔여 데이터 방지)
            self.price_data_cache = {}

            # 1. 과거 일일 선정 데이터 로드
            daily_selections = self._load_historical_selections(start_date, end_date)

            if not daily_selections:
                self.logger.warning("백테스트할 데이터가 없습니다")
                return BacktestResult.empty(strategy_name)

            # 2. 가격 데이터 로드 (look-ahead bias 방지)
            self._load_price_data_for_backtest(daily_selections, start_date, end_date)

            # 3. 시뮬레이션 실행 (전략별 구현)
            trades = self._simulate_trading(daily_selections, **kwargs)

            # 4. 성과 분석
            result = self._analyze_performance(trades, start_date, end_date, strategy_name)

            self.logger.info(
                f"백테스트 완료 [{strategy_name}]: "
                f"승률 {result.win_rate:.1%}, 총수익률 {result.total_return:.2%}"
            )

            return result

        except Exception as e:
            self.logger.error(f"백테스트 실패 [{strategy_name}]: {e}", exc_info=True)
            return BacktestResult.empty(strategy_name)

    @abstractmethod
    def _simulate_trading(self, selections: List[Dict], **kwargs) -> List[Trade]:
        """매매 시뮬레이션 (전략별 구현 필요)

        Args:
            selections: 일일 선정 데이터 목록
            **kwargs: 전략별 추가 파라미터

        Returns:
            List[Trade]: 거래 목록
        """
        pass

    @abstractmethod
    def _get_strategy_name(self) -> str:
        """전략명 반환 (전략별 구현 필요)"""
        pass

    def _load_historical_selections(self, start_date: str, end_date: str) -> List[Dict]:
        """과거 일일 선정 데이터 로드

        Args:
            start_date: 시작일 (YYYY-MM-DD)
            end_date: 종료일 (YYYY-MM-DD)

        Returns:
            List[Dict]: 선정 데이터 목록
        """
        selections = []

        try:
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

        except Exception as e:
            self.logger.error(f"선정 데이터 로드 실패: {e}", exc_info=True)
            return []

    def _load_price_data_for_backtest(
        self,
        selections: List[Dict],
        start_date: str,
        end_date: str
    ):
        """백테스트용 과거 가격 데이터 로드 (look-ahead bias 방지)

        Args:
            selections: 선정 데이터 목록
            start_date: 시작일
            end_date: 종료일
        """
        import pandas as pd

        try:
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

        except Exception as e:
            self.logger.error(f"가격 데이터 로드 프로세스 실패: {e}", exc_info=True)

    def _analyze_performance(
        self,
        trades: List[Trade],
        start_date: str,
        end_date: str,
        strategy_name: str
    ) -> BacktestResult:
        """성과 분석 (거래 비용 반영)

        Args:
            trades: 거래 목록
            start_date: 시작일
            end_date: 종료일
            strategy_name: 전략명

        Returns:
            BacktestResult: 백테스트 결과
        """
        if not trades:
            return BacktestResult.empty(strategy_name)

        try:
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

            # Max Drawdown (누적 수익률 곡선 기반)
            cumulative_returns = np.cumsum(adjusted_returns)
            running_max = np.maximum.accumulate(cumulative_returns)
            drawdowns = cumulative_returns - running_max
            max_drawdown = min(drawdowns) if len(drawdowns) > 0 else 0

            # Sharpe Ratio
            std_returns = np.std(adjusted_returns) if len(adjusted_returns) > 1 else 0
            sharpe = (
                np.mean(adjusted_returns) / std_returns * np.sqrt(252)
                if std_returns > 0 else 0
            )

            # Profit Factor
            total_profit = sum([t.return_pct for t in winning_trades])
            total_loss = abs(sum([t.return_pct for t in losing_trades]))
            profit_factor = total_profit / total_loss if total_loss > 0 else 0

            best_trade = max(adjusted_returns) if adjusted_returns else 0
            worst_trade = min(adjusted_returns) if adjusted_returns else 0

            avg_holding_days = (
                np.mean([t.holding_days for t in trades if t.holding_days is not None])
                if trades else 0
            )

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

        except Exception as e:
            self.logger.error(f"성과 분석 실패: {e}", exc_info=True)
            return BacktestResult.empty(strategy_name)

    def save_result(self, result: BacktestResult, output_path: str):
        """결과 저장

        Args:
            result: 백테스트 결과
            output_path: 저장 경로
        """
        try:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(asdict(result), f, indent=2, ensure_ascii=False)
            self.logger.info(f"백테스트 결과 저장: {output_path}")

        except Exception as e:
            self.logger.error(f"결과 저장 실패 ({output_path}): {e}", exc_info=True)

    def _to_datetime(self, date_value) -> datetime:
        """str 또는 datetime 객체를 datetime으로 변환

        Args:
            date_value: 날짜 (str 또는 datetime)

        Returns:
            datetime: 변환된 datetime 객체
        """
        if isinstance(date_value, datetime):
            return date_value
        elif isinstance(date_value, str):
            return datetime.strptime(date_value, "%Y-%m-%d")
        else:
            raise TypeError(f"Unsupported date type: {type(date_value)}")
