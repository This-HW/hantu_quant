"""
포지션 추적 모듈

보유 포지션의 상태, 손익, 리스크를 추적합니다.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class PositionStatus(Enum):
    """포지션 상태"""
    OPEN = "open"           # 열림
    PARTIAL = "partial"     # 부분 청산
    CLOSED = "closed"       # 완전 청산


@dataclass
class Position:
    """포지션"""
    stock_code: str
    stock_name: str

    # 진입 정보
    entry_price: float
    entry_quantity: int
    entry_date: datetime

    # 현재 상태
    current_quantity: int
    current_price: float = 0.0
    status: PositionStatus = PositionStatus.OPEN

    # 청산 정보
    exit_prices: List[float] = field(default_factory=list)
    exit_quantities: List[int] = field(default_factory=list)
    exit_dates: List[datetime] = field(default_factory=list)

    # 수익 정보
    realized_pnl: float = 0.0
    total_commission: float = 0.0

    # 메타데이터
    strategy: str = ""
    signal_source: List[str] = field(default_factory=list)
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    trailing_stop: Optional[float] = None

    @property
    def unrealized_pnl(self) -> float:
        """미실현 손익"""
        if self.current_quantity <= 0 or self.current_price <= 0:
            return 0.0
        return (self.current_price - self.entry_price) * self.current_quantity

    @property
    def unrealized_pnl_pct(self) -> float:
        """미실현 손익률"""
        if self.entry_price <= 0:
            return 0.0
        return ((self.current_price - self.entry_price) / self.entry_price) * 100

    @property
    def total_pnl(self) -> float:
        """총 손익 (실현 + 미실현)"""
        return self.realized_pnl + self.unrealized_pnl

    @property
    def total_pnl_pct(self) -> float:
        """총 손익률"""
        cost = self.entry_price * self.entry_quantity
        if cost <= 0:
            return 0.0
        return (self.total_pnl / cost) * 100

    @property
    def holding_days(self) -> int:
        """보유 일수"""
        return (datetime.now() - self.entry_date).days

    @property
    def market_value(self) -> float:
        """현재 시장가치"""
        return self.current_quantity * self.current_price

    @property
    def cost_basis(self) -> float:
        """원가"""
        return self.entry_price * self.current_quantity

    @property
    def avg_exit_price(self) -> float:
        """평균 청산가"""
        if not self.exit_prices or not self.exit_quantities:
            return 0.0
        total_value = sum(p * q for p, q in zip(self.exit_prices, self.exit_quantities))
        total_qty = sum(self.exit_quantities)
        return total_value / total_qty if total_qty > 0 else 0.0

    def should_stop_loss(self) -> bool:
        """손절 여부"""
        if self.stop_loss is None or self.current_price <= 0:
            return False
        return self.current_price <= self.stop_loss

    def should_take_profit(self) -> bool:
        """익절 여부"""
        if self.take_profit is None or self.current_price <= 0:
            return False
        return self.current_price >= self.take_profit

    def update_trailing_stop(self, atr: Optional[float] = None) -> None:
        """트레일링 스탑 업데이트"""
        if self.trailing_stop is None:
            return

        # ATR 기반 또는 고정 비율 스탑
        if atr:
            new_stop = self.current_price - (atr * 2)
        else:
            new_stop = self.current_price * (1 - self.trailing_stop / 100)

        # 스탑은 상승만 (기존 스탑이 있을 때만)
        if self.stop_loss is None:
            self.stop_loss = new_stop
        elif new_stop > self.stop_loss:
            self.stop_loss = new_stop

    def to_dict(self) -> Dict:
        return {
            'stock_code': self.stock_code,
            'stock_name': self.stock_name,
            'entry_price': self.entry_price,
            'entry_quantity': self.entry_quantity,
            'entry_date': self.entry_date.isoformat(),
            'current_quantity': self.current_quantity,
            'current_price': self.current_price,
            'status': self.status.value,
            'unrealized_pnl': self.unrealized_pnl,
            'unrealized_pnl_pct': self.unrealized_pnl_pct,
            'realized_pnl': self.realized_pnl,
            'total_pnl': self.total_pnl,
            'total_pnl_pct': self.total_pnl_pct,
            'holding_days': self.holding_days,
            'market_value': self.market_value,
            'strategy': self.strategy,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
        }


@dataclass
class PositionSummary:
    """포지션 요약"""
    total_positions: int = 0
    open_positions: int = 0
    closed_positions: int = 0

    total_market_value: float = 0.0
    total_cost_basis: float = 0.0
    total_unrealized_pnl: float = 0.0
    total_realized_pnl: float = 0.0
    total_pnl: float = 0.0
    total_pnl_pct: float = 0.0

    winners: int = 0
    losers: int = 0
    win_rate: float = 0.0

    avg_holding_days: float = 0.0
    max_gain: float = 0.0
    max_loss: float = 0.0

    def to_dict(self) -> Dict:
        return {
            'total_positions': self.total_positions,
            'open_positions': self.open_positions,
            'closed_positions': self.closed_positions,
            'total_market_value': self.total_market_value,
            'total_cost_basis': self.total_cost_basis,
            'total_unrealized_pnl': self.total_unrealized_pnl,
            'total_realized_pnl': self.total_realized_pnl,
            'total_pnl': self.total_pnl,
            'total_pnl_pct': self.total_pnl_pct,
            'winners': self.winners,
            'losers': self.losers,
            'win_rate': self.win_rate,
            'avg_holding_days': self.avg_holding_days,
            'max_gain': self.max_gain,
            'max_loss': self.max_loss,
        }


class PositionTracker:
    """
    포지션 추적기

    모든 포지션의 상태와 성과를 추적합니다.
    """

    def __init__(self):
        # 활성 포지션 {stock_code: Position}
        self._positions: Dict[str, Position] = {}

        # 청산된 포지션
        self._closed_positions: List[Position] = []

        # 이력
        self._position_history: List[Dict] = []

    def open_position(
        self,
        stock_code: str,
        stock_name: str,
        entry_price: float,
        quantity: int,
        strategy: str = "",
        signal_source: Optional[List[str]] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        trailing_stop: Optional[float] = None,
    ) -> Position:
        """
        포지션 열기

        Args:
            stock_code: 종목 코드
            stock_name: 종목명
            entry_price: 진입가
            quantity: 수량
            strategy: 전략명
            signal_source: 신호 소스
            stop_loss: 손절가
            take_profit: 익절가
            trailing_stop: 트레일링 스탑 %

        Returns:
            Position: 생성된 포지션
        """
        # 기존 포지션이 있으면 추가 매수 처리
        if stock_code in self._positions:
            return self._add_to_position(
                stock_code, entry_price, quantity
            )

        position = Position(
            stock_code=stock_code,
            stock_name=stock_name,
            entry_price=entry_price,
            entry_quantity=quantity,
            entry_date=datetime.now(),
            current_quantity=quantity,
            current_price=entry_price,
            strategy=strategy,
            signal_source=signal_source or [],
            stop_loss=stop_loss,
            take_profit=take_profit,
            trailing_stop=trailing_stop,
        )

        self._positions[stock_code] = position

        # 이력 기록
        self._record_event('open', position)

        logger.info(
            f"Position opened: {stock_code} {quantity}주 @ {entry_price:,.0f}원"
        )

        return position

    def _add_to_position(
        self,
        stock_code: str,
        price: float,
        quantity: int
    ) -> Position:
        """기존 포지션에 추가"""
        position = self._positions[stock_code]

        # 평균 단가 계산
        total_cost = (
            position.entry_price * position.current_quantity +
            price * quantity
        )
        total_qty = position.current_quantity + quantity

        position.entry_price = total_cost / total_qty
        position.entry_quantity += quantity
        position.current_quantity = total_qty

        self._record_event('add', position, {
            'add_price': price,
            'add_quantity': quantity,
        })

        logger.info(
            f"Position added: {stock_code} +{quantity}주 @ {price:,.0f}원 "
            f"(평균 {position.entry_price:,.0f}원)"
        )

        return position

    def close_position(
        self,
        stock_code: str,
        exit_price: float,
        quantity: Optional[int] = None,
        reason: str = ""
    ) -> Optional[Dict]:
        """
        포지션 청산

        Args:
            stock_code: 종목 코드
            exit_price: 청산가
            quantity: 청산 수량 (None이면 전량)
            reason: 청산 사유

        Returns:
            Dict: 청산 결과
        """
        if stock_code not in self._positions:
            logger.warning(f"Position not found: {stock_code}")
            return None

        position = self._positions[stock_code]
        close_qty = quantity or position.current_quantity
        close_qty = min(close_qty, position.current_quantity)

        # 실현 손익 계산
        pnl = (exit_price - position.entry_price) * close_qty
        pnl_pct = ((exit_price - position.entry_price) / position.entry_price) * 100

        # 포지션 업데이트
        position.exit_prices.append(exit_price)
        position.exit_quantities.append(close_qty)
        position.exit_dates.append(datetime.now())
        position.realized_pnl += pnl
        position.current_quantity -= close_qty

        result = {
            'stock_code': stock_code,
            'stock_name': position.stock_name,
            'exit_price': exit_price,
            'quantity': close_qty,
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'reason': reason,
            'holding_days': position.holding_days,
        }

        # 전량 청산 시
        if position.current_quantity <= 0:
            position.status = PositionStatus.CLOSED
            self._closed_positions.append(position)
            del self._positions[stock_code]

            self._record_event('close', position, result)

            logger.info(
                f"Position closed: {stock_code} {close_qty}주 @ {exit_price:,.0f}원 "
                f"(PnL: {pnl:+,.0f}원, {pnl_pct:+.2f}%)"
            )
        else:
            position.status = PositionStatus.PARTIAL
            self._record_event('partial_close', position, result)

            logger.info(
                f"Position partial close: {stock_code} {close_qty}주 @ {exit_price:,.0f}원 "
                f"(잔여 {position.current_quantity}주)"
            )

        return result

    def update_prices(self, prices: Dict[str, float]) -> None:
        """
        가격 업데이트

        Args:
            prices: {종목코드: 현재가}
        """
        for stock_code, price in prices.items():
            if stock_code in self._positions:
                self._positions[stock_code].current_price = price

    def check_stop_conditions(
        self,
        prices: Dict[str, float]
    ) -> List[Dict]:
        """
        손절/익절 조건 체크

        Args:
            prices: {종목코드: 현재가}

        Returns:
            List[Dict]: 조건 충족 포지션 목록
        """
        triggered = []

        for stock_code, position in self._positions.items():
            price = prices.get(stock_code, position.current_price)
            position.current_price = price

            if position.should_stop_loss():
                triggered.append({
                    'stock_code': stock_code,
                    'position': position,
                    'reason': 'stop_loss',
                    'trigger_price': position.stop_loss,
                    'current_price': price,
                })

            elif position.should_take_profit():
                triggered.append({
                    'stock_code': stock_code,
                    'position': position,
                    'reason': 'take_profit',
                    'trigger_price': position.take_profit,
                    'current_price': price,
                })

        return triggered

    def update_trailing_stops(
        self,
        prices: Dict[str, float],
        atr_values: Optional[Dict[str, float]] = None
    ) -> None:
        """
        트레일링 스탑 업데이트

        Args:
            prices: {종목코드: 현재가}
            atr_values: {종목코드: ATR}
        """
        for stock_code, position in self._positions.items():
            if position.trailing_stop is not None:
                price = prices.get(stock_code)
                if price:
                    position.current_price = price
                    atr = atr_values.get(stock_code) if atr_values else None
                    position.update_trailing_stop(atr)

    def get_position(self, stock_code: str) -> Optional[Position]:
        """포지션 조회"""
        return self._positions.get(stock_code)

    def get_all_positions(self) -> List[Position]:
        """모든 활성 포지션"""
        return list(self._positions.values())

    def get_closed_positions(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Position]:
        """청산된 포지션 조회"""
        positions = self._closed_positions

        if start_date:
            positions = [
                p for p in positions
                if p.exit_dates and p.exit_dates[-1] >= start_date
            ]

        if end_date:
            positions = [
                p for p in positions
                if p.exit_dates and p.exit_dates[-1] <= end_date
            ]

        return positions

    def get_positions_by_strategy(self, strategy: str) -> List[Position]:
        """전략별 포지션 조회"""
        return [
            p for p in self._positions.values()
            if p.strategy == strategy
        ]

    def get_summary(self) -> PositionSummary:
        """포지션 요약"""
        summary = PositionSummary()

        # 활성 포지션
        open_positions = list(self._positions.values())
        closed_positions = self._closed_positions

        summary.open_positions = len(open_positions)
        summary.closed_positions = len(closed_positions)
        summary.total_positions = summary.open_positions + summary.closed_positions

        # 시장가치 및 손익
        for pos in open_positions:
            summary.total_market_value += pos.market_value
            summary.total_cost_basis += pos.cost_basis
            summary.total_unrealized_pnl += pos.unrealized_pnl

        # 실현 손익
        for pos in closed_positions:
            summary.total_realized_pnl += pos.realized_pnl

            if pos.realized_pnl > 0:
                summary.winners += 1
            elif pos.realized_pnl < 0:
                summary.losers += 1

            if pos.realized_pnl > summary.max_gain:
                summary.max_gain = pos.realized_pnl
            if pos.realized_pnl < summary.max_loss:
                summary.max_loss = pos.realized_pnl

        summary.total_pnl = (
            summary.total_unrealized_pnl + summary.total_realized_pnl
        )

        if summary.total_cost_basis > 0:
            summary.total_pnl_pct = (
                summary.total_pnl / summary.total_cost_basis * 100
            )

        # 승률
        total_closed = summary.winners + summary.losers
        if total_closed > 0:
            summary.win_rate = summary.winners / total_closed * 100

        # 평균 보유일
        all_positions = open_positions + closed_positions
        if all_positions:
            summary.avg_holding_days = sum(
                p.holding_days for p in all_positions
            ) / len(all_positions)

        return summary

    def get_risk_exposure(self) -> Dict[str, Any]:
        """리스크 노출 분석"""
        positions = list(self._positions.values())

        if not positions:
            return {
                'total_exposure': 0,
                'by_strategy': {},
                'concentration': {},
            }

        total_value = sum(p.market_value for p in positions)

        # 전략별 노출
        by_strategy: Dict[str, float] = {}
        for pos in positions:
            strategy = pos.strategy or 'unknown'
            by_strategy[strategy] = by_strategy.get(strategy, 0) + pos.market_value

        # 집중도
        concentration = {}
        for pos in positions:
            if total_value > 0:
                concentration[pos.stock_code] = pos.market_value / total_value * 100

        # 손실 포지션
        losing_positions = [
            p for p in positions if p.unrealized_pnl < 0
        ]

        return {
            'total_exposure': total_value,
            'position_count': len(positions),
            'by_strategy': by_strategy,
            'concentration': concentration,
            'losing_positions': len(losing_positions),
            'total_unrealized_loss': sum(
                p.unrealized_pnl for p in losing_positions
            ),
        }

    def _record_event(
        self,
        event_type: str,
        position: Position,
        details: Optional[Dict] = None
    ) -> None:
        """이벤트 기록"""
        self._position_history.append({
            'timestamp': datetime.now().isoformat(),
            'event_type': event_type,
            'stock_code': position.stock_code,
            'stock_name': position.stock_name,
            'details': details or {},
        })

    def get_history(
        self,
        stock_code: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """이벤트 이력 조회"""
        history = self._position_history

        if stock_code:
            history = [h for h in history if h['stock_code'] == stock_code]

        if event_type:
            history = [h for h in history if h['event_type'] == event_type]

        return history[-limit:]

    def export_positions(self) -> Dict[str, Any]:
        """포지션 데이터 내보내기"""
        return {
            'timestamp': datetime.now().isoformat(),
            'open_positions': [p.to_dict() for p in self._positions.values()],
            'closed_positions': [p.to_dict() for p in self._closed_positions],
            'summary': self.get_summary().to_dict(),
        }
