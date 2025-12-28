"""
백테스트 엔진 모듈

과거 데이터로 전략을 검증하는 핵심 엔진입니다.
"""

import time
import uuid
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional, Callable
import pandas as pd
import numpy as np
from dataclasses import asdict

from .config import BacktestConfig, PositionSizeMethod
from .result import (
    BacktestResult, BacktestStatus, Trade, Position,
    DailySnapshot, MetricsCalculator
)
from .strategy import BaseStrategy, Signal, SignalType

from ..utils.log_utils import get_logger

logger = get_logger(__name__)


class BacktestEngine:
    """백테스트 엔진"""

    def __init__(self, config: BacktestConfig = None):
        """
        Args:
            config: 백테스트 설정 (None이면 기본 설정 사용)
        """
        self.config = config or BacktestConfig()
        self._reset()

    def _reset(self):
        """내부 상태 초기화"""
        self.cash = self.config.initial_capital
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []
        self.daily_snapshots: List[DailySnapshot] = []
        self.trade_counter = 0
        self.current_date: Optional[str] = None
        self._peak_equity = self.config.initial_capital
        self._daily_trades = 0
        self._daily_start_equity = self.config.initial_capital

    def run(
        self,
        strategy: BaseStrategy,
        data: Dict[str, pd.DataFrame],
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> BacktestResult:
        """
        백테스트 실행

        Args:
            strategy: 백테스트할 전략
            data: 종목별 OHLCV 데이터 {stock_code: DataFrame}
            progress_callback: 진행률 콜백 함수 (current, total)

        Returns:
            BacktestResult: 백테스트 결과
        """
        start_time = time.time()
        self._reset()

        # 결과 객체 초기화
        result = BacktestResult(
            backtest_id=str(uuid.uuid4())[:8],
            strategy_name=strategy.name,
            initial_capital=self.config.initial_capital,
            config_snapshot=self.config.to_dict(),
            status=BacktestStatus.RUNNING
        )

        try:
            # 데이터 검증 및 날짜 범위 설정
            all_dates = self._get_common_dates(data)
            if len(all_dates) == 0:
                raise ValueError("유효한 거래일이 없습니다")

            # 날짜 필터링
            start_date = self.config.start_date or all_dates[0].date()
            end_date = self.config.end_date or all_dates[-1].date()
            all_dates = [d for d in all_dates if start_date <= d.date() <= end_date]

            if len(all_dates) <= self.config.warmup_period:
                raise ValueError(f"데이터가 부족합니다 (워밍업 {self.config.warmup_period}일 필요)")

            result.start_date = str(start_date)
            result.end_date = str(end_date)

            # 전략 초기화
            strategy.initialize(data)

            logger.info(
                f"백테스트 시작: {strategy.name}, "
                f"기간: {start_date} ~ {end_date}, "
                f"종목 수: {len(data)}"
            )

            # 워밍업 기간 이후부터 거래 시작
            trading_dates = all_dates[self.config.warmup_period:]
            total_days = len(trading_dates)

            for day_idx, current_date in enumerate(trading_dates):
                self.current_date = str(current_date.date())
                self._daily_trades = 0

                # 진행률 콜백
                if progress_callback and day_idx % 10 == 0:
                    progress_callback(day_idx, total_days)

                # 1. 기존 포지션 업데이트 (가격, 손절/익절 체크)
                self._update_positions(data, current_date)

                # 2. 손절/익절 처리
                self._check_stops(data, current_date)

                # 3. 일일 최대 손실 체크
                if self._check_daily_loss_limit():
                    continue

                # 4. MDD 체크
                if self._check_max_drawdown():
                    logger.warning(f"최대 낙폭 도달, 거래 중단: {self.current_date}")
                    if self.config.risk.stop_on_max_drawdown:
                        break

                # 5. 전략에서 시그널 생성
                signals = self._generate_signals(strategy, data, current_date)

                # 6. 시그널 실행
                for signal in signals:
                    self._execute_signal(signal, data, current_date)

                # 7. 일별 스냅샷 저장
                self._save_daily_snapshot(data, current_date)

            # 8. 남은 포지션 청산
            self._close_all_positions(data, trading_dates[-1] if trading_dates else all_dates[-1])

            # 9. 결과 계산
            result = self._finalize_result(result)
            result.status = BacktestStatus.COMPLETED

        except Exception as e:
            logger.error(f"백테스트 실패: {e}")
            result.status = BacktestStatus.FAILED
            raise

        finally:
            result.execution_time = time.time() - start_time

        logger.info(f"백테스트 완료: {result.execution_time:.2f}초")
        return result

    def _get_common_dates(self, data: Dict[str, pd.DataFrame]) -> List[pd.Timestamp]:
        """모든 종목의 공통 날짜 추출"""
        if not data:
            return []

        # 모든 날짜 수집
        all_dates = set()
        for df in data.values():
            if df.index.dtype == 'object':
                dates = pd.to_datetime(df.index)
            else:
                dates = df.index
            all_dates.update(dates)

        return sorted(list(all_dates))

    def _update_positions(self, data: Dict[str, pd.DataFrame], current_date: pd.Timestamp):
        """포지션 가격 업데이트"""
        for stock_code, position in list(self.positions.items()):
            if stock_code not in data:
                continue

            df = data[stock_code]
            if current_date not in df.index:
                continue

            current_price = df.loc[current_date, 'close']
            position.update_price(current_price)

    def _check_stops(self, data: Dict[str, pd.DataFrame], current_date: pd.Timestamp):
        """손절/익절 체크 및 실행"""
        for stock_code, position in list(self.positions.items()):
            if stock_code not in data:
                continue

            df = data[stock_code]
            if current_date not in df.index:
                continue

            low_price = df.loc[current_date, 'low']
            high_price = df.loc[current_date, 'high']

            exit_reason = None
            exit_price = None

            # 손절 체크
            if position.stop_loss > 0 and low_price <= position.stop_loss:
                exit_price = position.stop_loss
                exit_reason = "stop_loss"

            # 익절 체크
            elif position.take_profit > 0 and high_price >= position.take_profit:
                exit_price = position.take_profit
                exit_reason = "take_profit"

            # 트레일링 스탑 체크
            elif position.trailing_stop > 0 and low_price <= position.trailing_stop:
                exit_price = position.trailing_stop
                exit_reason = "trailing"

            # 트레일링 스탑 업데이트
            if self.config.risk.use_trailing_stop and position.trailing_stop > 0:
                if high_price > position.highest_price:
                    # ATR 기반 트레일링 (간단 버전: 고점 대비 일정 비율)
                    new_trailing = high_price * (1 - self.config.risk.stop_loss_pct)
                    if new_trailing > position.trailing_stop:
                        position.trailing_stop = new_trailing

            # 청산 실행
            if exit_reason:
                self._close_position(stock_code, exit_price, str(current_date.date()), exit_reason)

    def _check_daily_loss_limit(self) -> bool:
        """일일 최대 손실 체크"""
        current_equity = self._calculate_equity()
        daily_return = (current_equity - self._daily_start_equity) / self._daily_start_equity

        if daily_return <= -self.config.risk.max_daily_loss:
            logger.warning(f"일일 최대 손실 도달: {daily_return:.2%}")
            return True
        return False

    def _check_max_drawdown(self) -> bool:
        """최대 낙폭 체크"""
        current_equity = self._calculate_equity()
        if current_equity > self._peak_equity:
            self._peak_equity = current_equity

        drawdown = (self._peak_equity - current_equity) / self._peak_equity
        return drawdown >= self.config.risk.max_drawdown

    def _generate_signals(
        self,
        strategy: BaseStrategy,
        data: Dict[str, pd.DataFrame],
        current_date: pd.Timestamp
    ) -> List[Signal]:
        """전략에서 시그널 생성"""
        all_signals = []

        for stock_code, df in data.items():
            if current_date not in df.index:
                continue

            # 현재 날짜까지의 데이터만 전달 (미래 데이터 제외)
            idx = df.index.get_loc(current_date)
            historical_data = df.iloc[:idx + 1].copy()
            historical_data.attrs['stock_code'] = stock_code

            # 시그널 생성
            signals = strategy.generate_signals(historical_data, self.positions)
            all_signals.extend(signals)

        return all_signals

    def _execute_signal(
        self,
        signal: Signal,
        data: Dict[str, pd.DataFrame],
        current_date: pd.Timestamp
    ):
        """시그널 실행"""
        stock_code = signal.stock_code

        if stock_code not in data:
            return

        df = data[stock_code]
        if current_date not in df.index:
            return

        if signal.signal_type == SignalType.BUY:
            self._open_position(signal, df, current_date)
        elif signal.signal_type == SignalType.SELL:
            if stock_code in self.positions:
                exit_price = df.loc[current_date, 'close']
                exit_price = self.config.slippage.apply_slippage(exit_price, is_buy=False)
                self._close_position(stock_code, exit_price, str(current_date.date()), "signal")

    def _open_position(
        self,
        signal: Signal,
        df: pd.DataFrame,
        current_date: pd.Timestamp
    ):
        """포지션 진입"""
        stock_code = signal.stock_code

        # 최대 포지션 수 체크
        if len(self.positions) >= self.config.risk.max_positions:
            logger.debug(f"최대 포지션 수 도달: {len(self.positions)}")
            return

        # 이미 포지션이 있으면 스킵
        if stock_code in self.positions:
            return

        # 진입가 계산 (슬리피지 적용)
        entry_price = df.loc[current_date, 'close']
        entry_price = self.config.slippage.apply_slippage(entry_price, is_buy=True)

        # 포지션 크기 계산
        quantity = self._calculate_position_size(entry_price, signal.strength)
        if quantity <= 0:
            return

        # 비용 계산
        trade_value = entry_price * quantity
        commission = self.config.commission.calculate_buy_cost(trade_value)
        total_cost = trade_value + commission

        # 자금 체크
        if total_cost > self.cash:
            # 가능한 수량으로 조정
            available = self.cash - commission
            quantity = int(available / entry_price)
            if quantity <= 0:
                return
            trade_value = entry_price * quantity
            commission = self.config.commission.calculate_buy_cost(trade_value)
            total_cost = trade_value + commission

        # 손절/익절 설정
        if self.config.risk.use_dynamic_stops and signal.stop_loss:
            stop_loss = signal.stop_loss
            take_profit = signal.take_profit or entry_price * (1 + self.config.risk.take_profit_pct)
        else:
            stop_loss = entry_price * (1 - self.config.risk.stop_loss_pct)
            take_profit = entry_price * (1 + self.config.risk.take_profit_pct)

        # 포지션 생성
        position = Position(
            stock_code=stock_code,
            stock_name=df.attrs.get('stock_name', stock_code),
            entry_date=str(current_date.date()),
            entry_price=entry_price,
            quantity=quantity,
            current_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            trailing_stop=stop_loss if self.config.risk.use_trailing_stop else 0,
            highest_price=entry_price
        )

        # 거래 기록
        self.trade_counter += 1
        trade = Trade(
            trade_id=self.trade_counter,
            stock_code=stock_code,
            stock_name=position.stock_name,
            entry_date=str(current_date.date()),
            entry_price=entry_price,
            entry_quantity=quantity,
            entry_commission=commission,
            slippage_cost=abs(df.loc[current_date, 'close'] - entry_price) * quantity
        )

        # 상태 업데이트
        self.cash -= total_cost
        self.positions[stock_code] = position
        self.trades.append(trade)
        self._daily_trades += 1

        logger.debug(
            f"매수: {stock_code} @ {entry_price:,.0f}원 x {quantity}주 "
            f"(손절: {stop_loss:,.0f}, 익절: {take_profit:,.0f})"
        )

    def _close_position(
        self,
        stock_code: str,
        exit_price: float,
        exit_date: str,
        exit_reason: str
    ):
        """포지션 청산"""
        if stock_code not in self.positions:
            return

        position = self.positions[stock_code]
        quantity = position.quantity

        # 비용 계산
        trade_value = exit_price * quantity
        commission = self.config.commission.calculate_sell_cost(trade_value)
        net_proceeds = trade_value - commission

        # 거래 기록 업데이트
        for trade in reversed(self.trades):
            if trade.stock_code == stock_code and not trade.is_closed():
                trade.exit_date = exit_date
                trade.exit_price = exit_price
                trade.exit_quantity = quantity
                trade.exit_reason = exit_reason
                trade.exit_commission = commission

                # 손익 계산
                entry_value = trade.entry_price * trade.entry_quantity
                exit_value = exit_price * quantity
                trade.pnl = exit_value - entry_value
                trade.pnl_pct = trade.pnl / entry_value * 100

                total_cost = trade.entry_commission + commission + trade.slippage_cost
                trade.net_pnl = trade.pnl - total_cost
                trade.net_pnl_pct = trade.net_pnl / entry_value * 100

                # 보유 기간
                entry_dt = datetime.strptime(trade.entry_date, "%Y-%m-%d")
                exit_dt = datetime.strptime(exit_date, "%Y-%m-%d")
                trade.holding_days = (exit_dt - entry_dt).days

                break

        # 상태 업데이트
        self.cash += net_proceeds
        del self.positions[stock_code]

        logger.debug(
            f"매도 ({exit_reason}): {stock_code} @ {exit_price:,.0f}원 x {quantity}주"
        )

    def _close_all_positions(self, data: Dict[str, pd.DataFrame], last_date: pd.Timestamp):
        """모든 포지션 청산"""
        for stock_code in list(self.positions.keys()):
            if stock_code in data:
                df = data[stock_code]
                if last_date in df.index:
                    exit_price = df.loc[last_date, 'close']
                    exit_price = self.config.slippage.apply_slippage(exit_price, is_buy=False)
                    self._close_position(stock_code, exit_price, str(last_date.date()), "end_of_backtest")

    def _calculate_position_size(self, price: float, signal_strength: float = 1.0) -> int:
        """포지션 크기 계산"""
        method = self.config.position_size_method
        value = self.config.position_size_value
        equity = self._calculate_equity()

        # 최대 포지션 크기 제한
        max_position_value = equity * self.config.risk.max_position_size

        if method == PositionSizeMethod.FIXED:
            position_value = value
        elif method == PositionSizeMethod.PERCENT:
            position_value = equity * value * signal_strength
        elif method == PositionSizeMethod.RISK_BASED:
            # 리스크 기반: 손절폭에 따른 수량 계산
            risk_amount = equity * self.config.risk.max_daily_loss
            stop_distance = price * self.config.risk.stop_loss_pct
            position_value = (risk_amount / stop_distance) * price if stop_distance > 0 else 0
        else:  # KELLY
            # 간단한 Kelly 공식 (승률 기반)
            win_rate = 0.5  # 기본값
            position_value = equity * value * (2 * win_rate - 1) * signal_strength

        # 제한 적용
        position_value = min(position_value, max_position_value)
        position_value = min(position_value, self.cash * 0.95)  # 현금의 95%까지만

        quantity = int(position_value / price)
        return max(0, quantity)

    def _calculate_equity(self) -> float:
        """총 자산 계산"""
        positions_value = sum(
            p.current_price * p.quantity for p in self.positions.values()
        )
        return self.cash + positions_value

    def _save_daily_snapshot(self, data: Dict[str, pd.DataFrame], current_date: pd.Timestamp):
        """일별 스냅샷 저장"""
        equity = self._calculate_equity()
        positions_value = sum(p.current_price * p.quantity for p in self.positions.values())

        # 전일 대비 수익률
        if self.daily_snapshots:
            prev_equity = self.daily_snapshots[-1].equity
            daily_pnl = equity - prev_equity
            daily_return = daily_pnl / prev_equity * 100 if prev_equity > 0 else 0
        else:
            daily_pnl = equity - self.config.initial_capital
            daily_return = daily_pnl / self.config.initial_capital * 100

        # 누적 수익률
        cumulative_return = (equity / self.config.initial_capital - 1) * 100

        # 낙폭
        if equity > self._peak_equity:
            self._peak_equity = equity
        drawdown = (equity - self._peak_equity) / self._peak_equity * 100

        snapshot = DailySnapshot(
            date=str(current_date.date()),
            equity=equity,
            cash=self.cash,
            positions_value=positions_value,
            daily_pnl=daily_pnl,
            daily_return=daily_return,
            cumulative_return=cumulative_return,
            drawdown=drawdown,
            num_positions=len(self.positions),
            num_trades=self._daily_trades
        )

        self.daily_snapshots.append(snapshot)

        # 일일 시작 자산 업데이트
        self._daily_start_equity = equity

    def _finalize_result(self, result: BacktestResult) -> BacktestResult:
        """결과 최종 계산"""
        result.final_capital = self._calculate_equity()
        result.trades = self.trades
        result.daily_snapshots = self.daily_snapshots

        # 자산 곡선
        if self.daily_snapshots:
            dates = [s.date for s in self.daily_snapshots]
            equity = [s.equity for s in self.daily_snapshots]
            equity_curve = pd.Series(equity, index=pd.to_datetime(dates))

            # 성과 지표 계산
            metrics = MetricsCalculator.calculate_all_metrics(
                equity_curve,
                self.trades,
                self.config.initial_capital
            )

            # 결과에 지표 적용
            for key, value in metrics.items():
                if hasattr(result, key):
                    setattr(result, key, value)

            # 월별/연별 수익률
            result.monthly_returns = self._calculate_period_returns(equity_curve, 'M')
            result.yearly_returns = self._calculate_period_returns(equity_curve, 'Y')

        # 비용 집계
        result.total_commission = sum(
            t.entry_commission + t.exit_commission for t in self.trades if t.is_closed()
        )
        result.total_slippage = sum(t.slippage_cost for t in self.trades)

        # 비용 영향
        gross_return = sum(t.pnl for t in self.trades if t.is_closed())
        if gross_return != 0:
            result.cost_return_impact = (result.total_commission + result.total_slippage) / abs(gross_return) * 100

        return result

    def _calculate_period_returns(self, equity_curve: pd.Series, period: str) -> Dict[str, float]:
        """기간별 수익률 계산"""
        if len(equity_curve) < 2:
            return {}

        # 새로운 pandas 형식으로 변환 (M -> ME, Y -> YE)
        period_map = {'M': 'ME', 'Y': 'YE'}
        period = period_map.get(period, period)

        resampled = equity_curve.resample(period).last()
        returns = resampled.pct_change().dropna()

        return {str(date.date() if hasattr(date, 'date') else date): ret * 100
                for date, ret in returns.items()}


def run_backtest(
    strategy: BaseStrategy,
    data: Dict[str, pd.DataFrame],
    config: BacktestConfig = None,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> BacktestResult:
    """백테스트 실행 편의 함수"""
    engine = BacktestEngine(config)
    return engine.run(strategy, data, progress_callback)
