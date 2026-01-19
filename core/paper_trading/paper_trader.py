"""
페이퍼 트레이딩 모듈

가상 거래 시뮬레이션을 실행하고 관리합니다.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import threading

from .virtual_portfolio import VirtualPortfolio, PortfolioConfig
from .order_executor import (
    OrderExecutor, OrderType, OrderSide, OrderStatus, ExecutionResult
)
from .position_tracker import PositionTracker

logger = logging.getLogger(__name__)


class TradingMode(Enum):
    """트레이딩 모드"""
    MANUAL = "manual"         # 수동 거래
    SIGNAL_BASED = "signal"   # 신호 기반
    STRATEGY = "strategy"     # 전략 자동


@dataclass
class PaperTradingConfig:
    """페이퍼 트레이딩 설정"""
    # 기본 설정
    initial_capital: float = 10_000_000
    commission_rate: float = 0.00015
    slippage_rate: float = 0.001

    # 리스크 관리
    max_position_size: float = 0.2      # 최대 포지션 비중 20%
    max_total_exposure: float = 0.8     # 최대 총 노출 80%
    max_single_loss: float = 0.02       # 단일 종목 최대 손실 2%
    daily_loss_limit: float = 0.05      # 일일 손실 한도 5%

    # 주문 설정
    default_stop_loss_pct: float = 3.0  # 기본 손절 3%
    default_take_profit_pct: float = 5.0  # 기본 익절 5%
    enable_trailing_stop: bool = True
    trailing_stop_pct: float = 2.0      # 트레일링 스탑 2%

    # 운영 설정
    trading_hours_start: str = "09:00"
    trading_hours_end: str = "15:20"
    enable_pre_market: bool = False
    enable_after_hours: bool = False


@dataclass
class TradingSession:
    """트레이딩 세션"""
    session_id: str
    start_time: datetime
    end_time: Optional[datetime] = None

    # 세션 통계
    trades_executed: int = 0
    buy_orders: int = 0
    sell_orders: int = 0
    total_volume: float = 0.0

    # 손익
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    commission_paid: float = 0.0

    # 시작/종료 잔고
    start_balance: float = 0.0
    end_balance: float = 0.0

    # 기록
    trade_log: List[Dict] = field(default_factory=list)

    @property
    def is_active(self) -> bool:
        return self.end_time is None

    @property
    def duration_minutes(self) -> float:
        end = self.end_time or datetime.now()
        return (end - self.start_time).total_seconds() / 60

    @property
    def session_return(self) -> float:
        if self.start_balance <= 0:
            return 0.0
        return ((self.end_balance - self.start_balance) / self.start_balance) * 100

    def to_dict(self) -> Dict:
        return {
            'session_id': self.session_id,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration_minutes': self.duration_minutes,
            'trades_executed': self.trades_executed,
            'buy_orders': self.buy_orders,
            'sell_orders': self.sell_orders,
            'total_volume': self.total_volume,
            'realized_pnl': self.realized_pnl,
            'unrealized_pnl': self.unrealized_pnl,
            'commission_paid': self.commission_paid,
            'start_balance': self.start_balance,
            'end_balance': self.end_balance,
            'session_return': self.session_return,
        }


class PaperTrader:
    """
    페이퍼 트레이더

    가상 거래 시뮬레이션을 실행하고 관리합니다.
    """

    def __init__(
        self,
        config: Optional[PaperTradingConfig] = None,
        notification_callback: Optional[Callable] = None
    ):
        """
        Args:
            config: 페이퍼 트레이딩 설정
            notification_callback: 알림 콜백 함수
        """
        self.config = config or PaperTradingConfig()
        self._notify = notification_callback

        # 포트폴리오 설정
        portfolio_config = PortfolioConfig(
            initial_capital=self.config.initial_capital,
            commission_rate=self.config.commission_rate,
            slippage_pct=self.config.slippage_rate,
            max_position_pct=self.config.max_position_size,
        )

        # 핵심 컴포넌트
        self.portfolio = VirtualPortfolio(portfolio_config)
        self.executor = OrderExecutor(self.portfolio)
        self.tracker = PositionTracker()

        # 세션 관리
        self._current_session: Optional[TradingSession] = None
        self._session_history: List[TradingSession] = []

        # 일일 통계
        self._daily_pnl: float = 0.0
        self._daily_trades: int = 0
        self._trading_paused: bool = False
        self._pause_reason: str = ""

        # 가격 데이터
        self._current_prices: Dict[str, float] = {}

        # 락 (재진입 가능)
        self._lock = threading.RLock()

    def start_session(self, session_id: Optional[str] = None) -> TradingSession:
        """
        트레이딩 세션 시작

        Args:
            session_id: 세션 ID (None이면 자동 생성)

        Returns:
            TradingSession: 시작된 세션
        """
        if self._current_session and self._current_session.is_active:
            logger.warning("Session already active, closing previous session")
            self.end_session()

        session_id = session_id or datetime.now().strftime("%Y%m%d_%H%M%S")

        self._current_session = TradingSession(
            session_id=session_id,
            start_time=datetime.now(),
            start_balance=self.portfolio.total_value,
        )

        # 일일 통계 리셋 (새 날짜일 경우)
        self._reset_daily_stats_if_needed()

        logger.info(f"Trading session started: {session_id}")

        if self._notify:
            self._notify('session_start', self._current_session.to_dict())

        return self._current_session

    def end_session(self) -> Optional[TradingSession]:
        """
        트레이딩 세션 종료

        Returns:
            TradingSession: 종료된 세션
        """
        if not self._current_session:
            return None

        session = self._current_session
        session.end_time = datetime.now()
        session.end_balance = self.portfolio.total_value
        session.unrealized_pnl = self._calculate_unrealized_pnl()

        self._session_history.append(session)
        self._current_session = None

        logger.info(
            f"Trading session ended: {session.session_id} "
            f"(Return: {session.session_return:+.2f}%)"
        )

        if self._notify:
            self._notify('session_end', session.to_dict())

        return session

    def buy(
        self,
        stock_code: str,
        stock_name: str,
        quantity: int,
        price: Optional[float] = None,
        order_type: OrderType = OrderType.MARKET,
        stop_loss_pct: Optional[float] = None,
        take_profit_pct: Optional[float] = None,
        strategy: str = "",
        signal_source: Optional[List[str]] = None,
    ) -> ExecutionResult:
        """
        매수 주문

        Args:
            stock_code: 종목 코드
            stock_name: 종목명
            quantity: 수량
            price: 지정가 (시장가 주문 시 현재가)
            order_type: 주문 유형
            stop_loss_pct: 손절 % (None이면 기본값)
            take_profit_pct: 익절 % (None이면 기본값)
            strategy: 전략명
            signal_source: 신호 소스

        Returns:
            ExecutionResult: 실행 결과
        """
        with self._lock:
            # 거래 가능 여부 체크
            check_result = self._check_can_trade('buy', stock_code, quantity, price)
            if not check_result['allowed']:
                return ExecutionResult(
                    success=False,
                    order_id="",
                    status=OrderStatus.REJECTED,
                    message=check_result['reason'],
                )

            # 현재가 결정
            current_price = price or self._current_prices.get(stock_code, 0)
            if current_price <= 0:
                return ExecutionResult(
                    success=False,
                    order_id="",
                    status=OrderStatus.REJECTED,
                    message="Price not available",
                )

            # 주문 생성
            order = self.executor.create_order(
                stock_code=stock_code,
                stock_name=stock_name,
                side=OrderSide.BUY,
                quantity=quantity,
                order_type=order_type,
                price=price if order_type == OrderType.LIMIT else None,
                strategy=strategy,
                signal_source=signal_source,
            )

            # 주문 제출
            self.executor.submit_order(order.id)

            # 시장가 주문 즉시 실행
            if order_type == OrderType.MARKET:
                result = self.executor.execute_market_order(order.id, current_price)

                if result.success:
                    # 포지션 추적
                    stop_loss = None
                    take_profit = None

                    sl_pct = stop_loss_pct or self.config.default_stop_loss_pct
                    tp_pct = take_profit_pct or self.config.default_take_profit_pct

                    if sl_pct:
                        stop_loss = result.filled_price * (1 - sl_pct / 100)
                    if tp_pct:
                        take_profit = result.filled_price * (1 + tp_pct / 100)

                    trailing_stop = None
                    if self.config.enable_trailing_stop:
                        trailing_stop = self.config.trailing_stop_pct

                    self.tracker.open_position(
                        stock_code=stock_code,
                        stock_name=stock_name,
                        entry_price=result.filled_price,
                        quantity=result.filled_quantity,
                        strategy=strategy,
                        signal_source=signal_source,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        trailing_stop=trailing_stop,
                    )

                    # 세션 통계 업데이트
                    self._update_session_stats('buy', result)

                    if self._notify:
                        self._notify('buy_executed', {
                            'stock_code': stock_code,
                            'stock_name': stock_name,
                            'price': result.filled_price,
                            'quantity': result.filled_quantity,
                            'commission': result.commission,
                        })

                return result

            # 지정가/스탑 주문은 대기
            return ExecutionResult(
                success=True,
                order_id=order.id,
                status=OrderStatus.SUBMITTED,
                message="Order submitted (pending execution)",
            )

    def sell(
        self,
        stock_code: str,
        quantity: Optional[int] = None,
        price: Optional[float] = None,
        order_type: OrderType = OrderType.MARKET,
        reason: str = "",
    ) -> ExecutionResult:
        """
        매도 주문

        Args:
            stock_code: 종목 코드
            quantity: 수량 (None이면 전량)
            price: 지정가
            order_type: 주문 유형
            reason: 매도 사유

        Returns:
            ExecutionResult: 실행 결과
        """
        with self._lock:
            # 보유 확인
            holding = self.portfolio.get_holding(stock_code)
            if not holding:
                return ExecutionResult(
                    success=False,
                    order_id="",
                    status=OrderStatus.REJECTED,
                    message="No holding found",
                )

            sell_qty = quantity or holding.quantity
            sell_qty = min(sell_qty, holding.quantity)

            # 현재가 결정
            current_price = price or self._current_prices.get(stock_code, holding.current_price)
            if current_price <= 0:
                return ExecutionResult(
                    success=False,
                    order_id="",
                    status=OrderStatus.REJECTED,
                    message="Price not available",
                )

            # 주문 생성
            order = self.executor.create_order(
                stock_code=stock_code,
                stock_name=holding.stock_name,
                side=OrderSide.SELL,
                quantity=sell_qty,
                order_type=order_type,
                price=price if order_type == OrderType.LIMIT else None,
                notes=reason,
            )

            # 주문 제출
            self.executor.submit_order(order.id)

            # 시장가 주문 즉시 실행
            if order_type == OrderType.MARKET:
                result = self.executor.execute_market_order(order.id, current_price)

                if result.success:
                    # 포지션 청산
                    self.tracker.close_position(
                        stock_code=stock_code,
                        exit_price=result.filled_price,
                        quantity=result.filled_quantity,
                        reason=reason,
                    )

                    # 세션 통계 업데이트
                    self._update_session_stats('sell', result)

                    # 일일 손익 업데이트
                    self._daily_pnl += result.pnl

                    # 일일 손실 한도 체크
                    self._check_daily_loss_limit()

                    if self._notify:
                        self._notify('sell_executed', {
                            'stock_code': stock_code,
                            'price': result.filled_price,
                            'quantity': result.filled_quantity,
                            'pnl': result.pnl,
                            'reason': reason,
                        })

                return result

            return ExecutionResult(
                success=True,
                order_id=order.id,
                status=OrderStatus.SUBMITTED,
                message="Order submitted (pending execution)",
            )

    def update_prices(self, prices: Dict[str, float]) -> List[ExecutionResult]:
        """
        가격 업데이트 및 주문/스탑 체크

        Args:
            prices: {종목코드: 현재가}

        Returns:
            List[ExecutionResult]: 실행된 주문 결과
        """
        with self._lock:
            self._current_prices.update(prices)

            # 포트폴리오 업데이트
            self.portfolio.update_prices(prices)

            # 포지션 추적기 업데이트
            self.tracker.update_prices(prices)

            results = []

            # 대기 주문 체크
            order_results = self.executor.check_pending_orders(prices)
            results.extend(order_results)

            # 손절/익절 조건 체크
            if not self._trading_paused:
                triggered = self.tracker.check_stop_conditions(prices)

                for trigger in triggered:
                    sell_result = self.sell(
                        stock_code=trigger['stock_code'],
                        reason=trigger['reason'],
                    )
                    results.append(sell_result)

                    if self._notify:
                        self._notify(f"stop_{trigger['reason']}", {
                            'stock_code': trigger['stock_code'],
                            'trigger_price': trigger['trigger_price'],
                            'current_price': trigger['current_price'],
                        })

            # 트레일링 스탑 업데이트
            self.tracker.update_trailing_stops(prices)

            return results

    def get_portfolio_status(self) -> Dict[str, Any]:
        """포트폴리오 상태"""
        snapshot = self.portfolio.get_snapshot()
        position_summary = self.tracker.get_summary()

        return {
            'cash': snapshot.cash,
            'holdings_value': snapshot.holdings_value,
            'total_value': snapshot.total_value,
            'total_pnl': snapshot.total_pnl,
            'total_pnl_pct': snapshot.total_pnl_pct,
            'position_count': position_summary.open_positions,
            'unrealized_pnl': position_summary.total_unrealized_pnl,
            'realized_pnl': position_summary.total_realized_pnl,
            'win_rate': position_summary.win_rate,
            'daily_pnl': self._daily_pnl,
            'trading_paused': self._trading_paused,
            'pause_reason': self._pause_reason,
        }

    def get_holdings(self) -> List[Dict]:
        """보유 종목 목록"""
        return [h.to_dict() for h in self.portfolio.get_holdings().values()]

    def get_pending_orders(self) -> List[Dict]:
        """대기 주문 목록"""
        return [o.to_dict() for o in self.executor.get_pending_orders()]

    def get_positions(self) -> List[Dict]:
        """포지션 목록"""
        return [p.to_dict() for p in self.tracker.get_all_positions()]

    def cancel_order(self, order_id: str) -> ExecutionResult:
        """주문 취소"""
        return self.executor.cancel_order(order_id)

    def cancel_all_orders(self) -> int:
        """모든 대기 주문 취소"""
        return self.executor.cancel_all_pending()

    def close_all_positions(self, reason: str = "close_all") -> List[ExecutionResult]:
        """모든 포지션 청산"""
        results = []

        for position in self.tracker.get_all_positions():
            result = self.sell(
                stock_code=position.stock_code,
                reason=reason,
            )
            results.append(result)

        return results

    def pause_trading(self, reason: str = "") -> None:
        """거래 일시 중지"""
        self._trading_paused = True
        self._pause_reason = reason
        logger.warning(f"Trading paused: {reason}")

        if self._notify:
            self._notify('trading_paused', {'reason': reason})

    def resume_trading(self) -> None:
        """거래 재개"""
        self._trading_paused = False
        self._pause_reason = ""
        logger.info("Trading resumed")

        if self._notify:
            self._notify('trading_resumed', {})

    def _check_can_trade(
        self,
        side: str,
        stock_code: str,
        quantity: int,
        price: Optional[float]
    ) -> Dict[str, Any]:
        """거래 가능 여부 체크"""
        if self._trading_paused:
            return {'allowed': False, 'reason': f"Trading paused: {self._pause_reason}"}

        if side == 'buy':
            # 매수 가능 금액 체크
            est_price = price or self._current_prices.get(stock_code, 0)
            if est_price <= 0:
                return {'allowed': False, 'reason': "Price not available"}

            required = est_price * quantity * (1 + self.config.commission_rate)
            if required > self.portfolio.cash:
                return {'allowed': False, 'reason': "Insufficient cash"}

            # 포지션 크기 체크
            position_value = est_price * quantity
            total_value = self.portfolio.total_value

            if total_value > 0 and position_value / total_value > self.config.max_position_size:
                return {'allowed': False, 'reason': "Exceeds max position size"}

            # 총 노출 체크
            current_exposure = self.portfolio.holdings_value / total_value if total_value > 0 else 0
            new_exposure = current_exposure + (position_value / total_value if total_value > 0 else 0)

            if new_exposure > self.config.max_total_exposure:
                return {'allowed': False, 'reason': "Exceeds max total exposure"}

        return {'allowed': True, 'reason': ''}

    def _check_daily_loss_limit(self) -> None:
        """일일 손실 한도 체크"""
        if self.config.daily_loss_limit <= 0:
            return

        daily_loss_pct = -self._daily_pnl / self.config.initial_capital * 100
        limit_pct = self.config.daily_loss_limit * 100

        if daily_loss_pct >= limit_pct:
            self.pause_trading(
                f"Daily loss limit reached: {daily_loss_pct:.2f}% >= {limit_pct:.2f}%"
            )

    def _update_session_stats(self, side: str, result: ExecutionResult) -> None:
        """세션 통계 업데이트"""
        if not self._current_session:
            return

        session = self._current_session
        session.trades_executed += 1

        if side == 'buy':
            session.buy_orders += 1
        else:
            session.sell_orders += 1
            session.realized_pnl += result.pnl

        session.total_volume += result.filled_price * result.filled_quantity
        session.commission_paid += result.commission

        # 거래 로그
        session.trade_log.append({
            'timestamp': datetime.now().isoformat(),
            'side': side,
            'order_id': result.order_id,
            'price': result.filled_price,
            'quantity': result.filled_quantity,
            'commission': result.commission,
            'pnl': result.pnl,
        })

    def _calculate_unrealized_pnl(self) -> float:
        """미실현 손익 계산"""
        return sum(
            p.unrealized_pnl for p in self.tracker.get_all_positions()
        )

    def _reset_daily_stats_if_needed(self) -> None:
        """일일 통계 리셋 (필요시)"""
        # 세션이 없거나 새 날짜인 경우
        if (not self._session_history or
            self._session_history[-1].start_time.date() != datetime.now().date()):
            self._daily_pnl = 0.0
            self._daily_trades = 0
            self._trading_paused = False
            self._pause_reason = ""

    def get_session_history(
        self,
        days: int = 30
    ) -> List[Dict]:
        """세션 이력"""
        cutoff = datetime.now() - timedelta(days=days)
        sessions = [
            s for s in self._session_history
            if s.start_time >= cutoff
        ]
        return [s.to_dict() for s in sessions]

    def get_performance_report(self) -> Dict[str, Any]:
        """성과 보고서"""
        portfolio = self.portfolio.get_snapshot()
        positions = self.tracker.get_summary()

        # 전체 수익률
        total_return = portfolio.total_pnl_pct

        # 세션 통계
        total_sessions = len(self._session_history)
        profitable_sessions = sum(
            1 for s in self._session_history if s.realized_pnl > 0
        )

        # 거래 통계
        total_trades = sum(s.trades_executed for s in self._session_history)
        total_commission = sum(s.commission_paid for s in self._session_history)

        return {
            'portfolio': {
                'initial_capital': self.config.initial_capital,
                'current_value': portfolio.total_value,
                'total_pnl': portfolio.total_pnl,
                'total_return_pct': total_return,
            },
            'positions': {
                'total_positions': positions.total_positions,
                'open_positions': positions.open_positions,
                'closed_positions': positions.closed_positions,
                'win_rate': positions.win_rate,
                'max_gain': positions.max_gain,
                'max_loss': positions.max_loss,
            },
            'sessions': {
                'total_sessions': total_sessions,
                'profitable_sessions': profitable_sessions,
                'session_win_rate': profitable_sessions / total_sessions * 100 if total_sessions > 0 else 0,
            },
            'trading': {
                'total_trades': total_trades,
                'total_commission': total_commission,
                'daily_pnl': self._daily_pnl,
            },
            'risk': {
                'trading_paused': self._trading_paused,
                'pause_reason': self._pause_reason,
            },
        }

    def export_state(self) -> Dict[str, Any]:
        """상태 내보내기"""
        return {
            'timestamp': datetime.now().isoformat(),
            'config': {
                'initial_capital': self.config.initial_capital,
                'commission_rate': self.config.commission_rate,
                'slippage_rate': self.config.slippage_rate,
            },
            'portfolio': self.portfolio.get_snapshot().to_dict(),
            'positions': self.tracker.export_positions(),
            'executor_stats': self.executor.get_stats(),
            'session': self._current_session.to_dict() if self._current_session else None,
            'daily_stats': {
                'pnl': self._daily_pnl,
                'trades': self._daily_trades,
            },
        }
