#!/usr/bin/env python3
"""
전략 백테스트 시스템
과거 데이터로 선정 기준 및 매매 전략 검증
"""

from datetime import datetime
from typing import Dict, List

from core.utils.log_utils import get_logger
from core.backtesting.base_backtester import BaseBacktester
from core.backtesting.models import BacktestResult, Trade

logger = get_logger(__name__)


class StrategyBacktester(BaseBacktester):
    """전략 백테스터 (BaseBacktester 상속)"""

    def _get_strategy_name(self) -> str:
        """전략명 반환 (기본값)"""
        return "Historical Strategy"

    def backtest_selection_strategy(
        self,
        start_date: str,
        end_date: str,
        selection_criteria: Dict,
        trading_config: Dict,
        strategy_name: str = "Default"
    ) -> BacktestResult:
        """선정 전략 백테스트 (공개 API)

        Args:
            start_date: 시작일 (YYYY-MM-DD)
            end_date: 종료일 (YYYY-MM-DD)
            selection_criteria: 선정 기준 (미사용, 향후 확장용)
            trading_config: 매매 설정
            strategy_name: 전략명

        Returns:
            BacktestResult: 백테스트 결과
        """
        # 부모의 backtest() 메서드 호출 (strategy_name 전달)
        return self.backtest(
            start_date=start_date,
            end_date=end_date,
            strategy_name=strategy_name,
            stop_loss_pct=trading_config.get('stop_loss_pct', 0.03),
            take_profit_pct=trading_config.get('take_profit_pct', 0.08),
            max_holding_days=trading_config.get('max_holding_days', 10),
            max_positions=trading_config.get('max_positions', 10)
        )

    def _simulate_trading(self, selections: List[Dict], **kwargs) -> List[Trade]:
        """매매 시뮬레이션 (BaseBacktester 추상 메서드 구현)

        Args:
            selections: 일일 선정 데이터 목록
            **kwargs: 매매 설정 파라미터
                - stop_loss_pct: 손절 비율
                - take_profit_pct: 익절 비율
                - max_holding_days: 최대 보유 기간
                - max_positions: 최대 포지션 수

        Returns:
            List[Trade]: 거래 목록
        """
        # kwargs에서 매매 설정 추출
        stop_loss_pct = kwargs.get('stop_loss_pct', 0.03)
        take_profit_pct = kwargs.get('take_profit_pct', 0.08)
        max_holding_days = kwargs.get('max_holding_days', 10)
        max_positions = kwargs.get('max_positions', 10)
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
