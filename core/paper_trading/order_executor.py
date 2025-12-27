"""
주문 실행 모듈

가상 주문의 생성, 실행, 추적을 담당합니다.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


class OrderType(Enum):
    """주문 유형"""
    MARKET = "market"         # 시장가
    LIMIT = "limit"           # 지정가
    STOP = "stop"             # 스탑
    STOP_LIMIT = "stop_limit"  # 스탑 리밋


class OrderSide(Enum):
    """주문 방향"""
    BUY = "buy"
    SELL = "sell"


class OrderStatus(Enum):
    """주문 상태"""
    PENDING = "pending"       # 대기
    SUBMITTED = "submitted"   # 제출됨
    PARTIAL = "partial"       # 부분 체결
    FILLED = "filled"         # 전량 체결
    CANCELLED = "cancelled"   # 취소됨
    REJECTED = "rejected"     # 거부됨
    EXPIRED = "expired"       # 만료


@dataclass
class Order:
    """주문"""
    id: str
    stock_code: str
    stock_name: str
    side: OrderSide
    order_type: OrderType
    quantity: int
    price: Optional[float] = None  # 지정가
    stop_price: Optional[float] = None  # 스탑가

    # 상태
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: int = 0
    filled_price: float = 0.0
    commission: float = 0.0

    # 타임스탬프
    created_at: datetime = field(default_factory=datetime.now)
    submitted_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None

    # 메타데이터
    strategy: str = ""
    signal_source: List[str] = field(default_factory=list)
    notes: str = ""

    @property
    def is_buy(self) -> bool:
        return self.side == OrderSide.BUY

    @property
    def is_sell(self) -> bool:
        return self.side == OrderSide.SELL

    @property
    def is_complete(self) -> bool:
        return self.status in [
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
            OrderStatus.EXPIRED,
        ]

    @property
    def remaining_quantity(self) -> int:
        return self.quantity - self.filled_quantity

    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'stock_code': self.stock_code,
            'stock_name': self.stock_name,
            'side': self.side.value,
            'order_type': self.order_type.value,
            'quantity': self.quantity,
            'price': self.price,
            'stop_price': self.stop_price,
            'status': self.status.value,
            'filled_quantity': self.filled_quantity,
            'filled_price': self.filled_price,
            'commission': self.commission,
            'created_at': self.created_at.isoformat(),
            'submitted_at': self.submitted_at.isoformat() if self.submitted_at else None,
            'filled_at': self.filled_at.isoformat() if self.filled_at else None,
            'strategy': self.strategy,
            'signal_source': self.signal_source,
            'notes': self.notes,
        }


@dataclass
class ExecutionResult:
    """실행 결과"""
    success: bool
    order_id: str
    status: OrderStatus
    message: str = ""
    filled_quantity: int = 0
    filled_price: float = 0.0
    commission: float = 0.0
    pnl: float = 0.0

    def to_dict(self) -> Dict:
        return {
            'success': self.success,
            'order_id': self.order_id,
            'status': self.status.value,
            'message': self.message,
            'filled_quantity': self.filled_quantity,
            'filled_price': self.filled_price,
            'commission': self.commission,
            'pnl': self.pnl,
        }


class OrderExecutor:
    """
    주문 실행기

    가상 주문을 생성하고 실행합니다.
    """

    def __init__(self, portfolio):
        """
        Args:
            portfolio: VirtualPortfolio 인스턴스
        """
        from .virtual_portfolio import VirtualPortfolio
        self.portfolio: VirtualPortfolio = portfolio

        # 주문 관리
        self._orders: Dict[str, Order] = {}
        self._pending_orders: List[str] = []
        self._order_history: List[Order] = []

    def create_order(
        self,
        stock_code: str,
        stock_name: str,
        side: OrderSide,
        quantity: int,
        order_type: OrderType = OrderType.MARKET,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        strategy: str = "",
        signal_source: Optional[List[str]] = None,
        notes: str = ""
    ) -> Order:
        """
        주문 생성

        Args:
            stock_code: 종목 코드
            stock_name: 종목명
            side: 매수/매도
            quantity: 수량
            order_type: 주문 유형
            price: 지정가
            stop_price: 스탑가
            strategy: 전략명
            signal_source: 신호 소스
            notes: 비고

        Returns:
            Order: 생성된 주문
        """
        order_id = str(uuid.uuid4())[:8]

        order = Order(
            id=order_id,
            stock_code=stock_code,
            stock_name=stock_name,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
            strategy=strategy,
            signal_source=signal_source or [],
            notes=notes,
        )

        self._orders[order_id] = order

        logger.info(
            f"Order created: {order_id} - {side.value.upper()} "
            f"{stock_code} {quantity}주"
        )

        return order

    def submit_order(self, order_id: str) -> ExecutionResult:
        """
        주문 제출

        Args:
            order_id: 주문 ID

        Returns:
            ExecutionResult: 실행 결과
        """
        if order_id not in self._orders:
            return ExecutionResult(
                success=False,
                order_id=order_id,
                status=OrderStatus.REJECTED,
                message="Order not found",
            )

        order = self._orders[order_id]

        if order.is_complete:
            return ExecutionResult(
                success=False,
                order_id=order_id,
                status=order.status,
                message="Order already complete",
            )

        order.status = OrderStatus.SUBMITTED
        order.submitted_at = datetime.now()

        # 시장가 주문은 즉시 실행 시도
        if order.order_type == OrderType.MARKET:
            self._pending_orders.append(order_id)

        # 지정가/스탑 주문은 대기열에 추가
        else:
            self._pending_orders.append(order_id)

        return ExecutionResult(
            success=True,
            order_id=order_id,
            status=order.status,
            message="Order submitted",
        )

    def execute_market_order(
        self,
        order_id: str,
        current_price: float
    ) -> ExecutionResult:
        """
        시장가 주문 실행

        Args:
            order_id: 주문 ID
            current_price: 현재가

        Returns:
            ExecutionResult: 실행 결과
        """
        if order_id not in self._orders:
            return ExecutionResult(
                success=False,
                order_id=order_id,
                status=OrderStatus.REJECTED,
                message="Order not found",
            )

        order = self._orders[order_id]

        if order.side == OrderSide.BUY:
            result = self.portfolio.buy(
                stock_code=order.stock_code,
                stock_name=order.stock_name,
                price=current_price,
                quantity=order.quantity,
            )
        else:
            result = self.portfolio.sell(
                stock_code=order.stock_code,
                price=current_price,
                quantity=order.quantity,
            )

        if result['success']:
            order.status = OrderStatus.FILLED
            order.filled_quantity = order.quantity
            order.filled_price = result['price']
            order.commission = result['commission']
            order.filled_at = datetime.now()

            # 대기열에서 제거
            if order_id in self._pending_orders:
                self._pending_orders.remove(order_id)

            # 히스토리 추가
            self._order_history.append(order)

            return ExecutionResult(
                success=True,
                order_id=order_id,
                status=OrderStatus.FILLED,
                message="Order filled",
                filled_quantity=order.quantity,
                filled_price=order.filled_price,
                commission=order.commission,
                pnl=result.get('realized_pnl', 0.0),
            )
        else:
            order.status = OrderStatus.REJECTED

            return ExecutionResult(
                success=False,
                order_id=order_id,
                status=OrderStatus.REJECTED,
                message=result.get('error', 'Execution failed'),
            )

    def check_pending_orders(
        self,
        current_prices: Dict[str, float]
    ) -> List[ExecutionResult]:
        """
        대기 주문 체크 및 실행

        Args:
            current_prices: {종목코드: 현재가}

        Returns:
            List[ExecutionResult]: 실행 결과 리스트
        """
        results = []

        for order_id in list(self._pending_orders):
            order = self._orders.get(order_id)
            if not order:
                continue

            price = current_prices.get(order.stock_code)
            if price is None:
                continue

            should_execute = False

            if order.order_type == OrderType.MARKET:
                should_execute = True

            elif order.order_type == OrderType.LIMIT:
                if order.is_buy and price <= order.price:
                    should_execute = True
                elif order.is_sell and price >= order.price:
                    should_execute = True

            elif order.order_type == OrderType.STOP:
                if order.is_buy and price >= order.stop_price:
                    should_execute = True
                elif order.is_sell and price <= order.stop_price:
                    should_execute = True

            if should_execute:
                result = self.execute_market_order(order_id, price)
                results.append(result)

        return results

    def cancel_order(self, order_id: str) -> ExecutionResult:
        """
        주문 취소

        Args:
            order_id: 주문 ID

        Returns:
            ExecutionResult: 실행 결과
        """
        if order_id not in self._orders:
            return ExecutionResult(
                success=False,
                order_id=order_id,
                status=OrderStatus.REJECTED,
                message="Order not found",
            )

        order = self._orders[order_id]

        if order.is_complete:
            return ExecutionResult(
                success=False,
                order_id=order_id,
                status=order.status,
                message="Order already complete",
            )

        order.status = OrderStatus.CANCELLED

        if order_id in self._pending_orders:
            self._pending_orders.remove(order_id)

        return ExecutionResult(
            success=True,
            order_id=order_id,
            status=OrderStatus.CANCELLED,
            message="Order cancelled",
        )

    def cancel_all_pending(self) -> int:
        """
        모든 대기 주문 취소

        Returns:
            int: 취소된 주문 수
        """
        count = 0
        for order_id in list(self._pending_orders):
            result = self.cancel_order(order_id)
            if result.success:
                count += 1

        return count

    def get_order(self, order_id: str) -> Optional[Order]:
        """주문 조회"""
        return self._orders.get(order_id)

    def get_pending_orders(self) -> List[Order]:
        """대기 주문 목록"""
        return [
            self._orders[oid] for oid in self._pending_orders
            if oid in self._orders
        ]

    def get_order_history(
        self,
        stock_code: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Order]:
        """주문 이력"""
        history = self._order_history

        if stock_code:
            history = [o for o in history if o.stock_code == stock_code]

        if limit:
            history = history[-limit:]

        return history

    def get_stats(self) -> Dict[str, Any]:
        """통계"""
        filled_orders = [
            o for o in self._order_history
            if o.status == OrderStatus.FILLED
        ]

        buy_orders = [o for o in filled_orders if o.is_buy]
        sell_orders = [o for o in filled_orders if o.is_sell]

        return {
            'total_orders': len(self._orders),
            'pending_orders': len(self._pending_orders),
            'filled_orders': len(filled_orders),
            'buy_orders': len(buy_orders),
            'sell_orders': len(sell_orders),
            'total_commission': sum(o.commission for o in filled_orders),
        }
