"""
주문 상태머신 모듈

주문의 상태 전이를 관리하고 검증합니다.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable, Set
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class OrderState(Enum):
    """주문 상태"""
    # 초기 상태
    CREATED = "created"           # 생성됨

    # 제출 단계
    PENDING_SUBMIT = "pending_submit"  # 제출 대기
    SUBMITTED = "submitted"       # 제출됨

    # 체결 단계
    PENDING_FILL = "pending_fill"  # 체결 대기
    PARTIAL_FILL = "partial_fill"  # 부분 체결
    FILLED = "filled"             # 전량 체결

    # 종료 상태
    CANCELLED = "cancelled"       # 취소됨
    REJECTED = "rejected"         # 거부됨
    EXPIRED = "expired"           # 만료됨
    FAILED = "failed"             # 실패


class OrderEvent(Enum):
    """주문 이벤트"""
    SUBMIT = "submit"             # 주문 제출
    ACK = "ack"                   # 접수 확인
    PARTIAL = "partial"           # 부분 체결
    FILL = "fill"                 # 전량 체결
    CANCEL = "cancel"             # 취소 요청
    CANCEL_ACK = "cancel_ack"     # 취소 확인
    REJECT = "reject"             # 거부
    EXPIRE = "expire"             # 만료
    FAIL = "fail"                 # 실패


@dataclass
class StateTransition:
    """상태 전이 기록"""
    from_state: OrderState
    to_state: OrderState
    event: OrderEvent
    timestamp: datetime = field(default_factory=datetime.now)
    details: Dict[str, Any] = field(default_factory=dict)


class InvalidTransitionError(Exception):
    """유효하지 않은 상태 전이 오류"""
    def __init__(self, current_state: OrderState, event: OrderEvent):
        self.current_state = current_state
        self.event = event
        super().__init__(
            f"Invalid transition: {current_state.value} + {event.value}"
        )


class OrderStateMachine:
    """
    주문 상태머신

    주문의 상태 전이를 관리하고 유효성을 검증합니다.
    """

    # 유효한 상태 전이 정의
    # (현재상태, 이벤트) -> 다음상태
    TRANSITIONS: Dict[tuple, OrderState] = {
        # CREATED에서 전이
        (OrderState.CREATED, OrderEvent.SUBMIT): OrderState.PENDING_SUBMIT,
        (OrderState.CREATED, OrderEvent.CANCEL): OrderState.CANCELLED,
        (OrderState.CREATED, OrderEvent.REJECT): OrderState.REJECTED,

        # PENDING_SUBMIT에서 전이
        (OrderState.PENDING_SUBMIT, OrderEvent.ACK): OrderState.SUBMITTED,
        (OrderState.PENDING_SUBMIT, OrderEvent.REJECT): OrderState.REJECTED,
        (OrderState.PENDING_SUBMIT, OrderEvent.FAIL): OrderState.FAILED,
        (OrderState.PENDING_SUBMIT, OrderEvent.CANCEL): OrderState.CANCELLED,

        # SUBMITTED에서 전이
        (OrderState.SUBMITTED, OrderEvent.ACK): OrderState.PENDING_FILL,
        (OrderState.SUBMITTED, OrderEvent.FILL): OrderState.FILLED,
        (OrderState.SUBMITTED, OrderEvent.PARTIAL): OrderState.PARTIAL_FILL,
        (OrderState.SUBMITTED, OrderEvent.CANCEL): OrderState.CANCELLED,
        (OrderState.SUBMITTED, OrderEvent.REJECT): OrderState.REJECTED,
        (OrderState.SUBMITTED, OrderEvent.EXPIRE): OrderState.EXPIRED,

        # PENDING_FILL에서 전이
        (OrderState.PENDING_FILL, OrderEvent.FILL): OrderState.FILLED,
        (OrderState.PENDING_FILL, OrderEvent.PARTIAL): OrderState.PARTIAL_FILL,
        (OrderState.PENDING_FILL, OrderEvent.CANCEL): OrderState.CANCELLED,
        (OrderState.PENDING_FILL, OrderEvent.EXPIRE): OrderState.EXPIRED,

        # PARTIAL_FILL에서 전이
        (OrderState.PARTIAL_FILL, OrderEvent.FILL): OrderState.FILLED,
        (OrderState.PARTIAL_FILL, OrderEvent.PARTIAL): OrderState.PARTIAL_FILL,
        (OrderState.PARTIAL_FILL, OrderEvent.CANCEL): OrderState.CANCELLED,
        (OrderState.PARTIAL_FILL, OrderEvent.EXPIRE): OrderState.EXPIRED,
    }

    # 종료 상태 (더 이상 전이 불가)
    TERMINAL_STATES: Set[OrderState] = {
        OrderState.FILLED,
        OrderState.CANCELLED,
        OrderState.REJECTED,
        OrderState.EXPIRED,
        OrderState.FAILED,
    }

    def __init__(
        self,
        order_id: str,
        initial_state: OrderState = OrderState.CREATED,
        on_transition: Optional[Callable[[StateTransition], None]] = None
    ):
        """
        Args:
            order_id: 주문 ID
            initial_state: 초기 상태
            on_transition: 상태 전이 시 콜백
        """
        self.order_id = order_id
        self._state = initial_state
        self._on_transition = on_transition
        self._history: List[StateTransition] = []

        # 초기 상태 기록
        self._history.append(StateTransition(
            from_state=initial_state,
            to_state=initial_state,
            event=OrderEvent.SUBMIT,  # 초기 이벤트로 사용
            details={'initial': True}
        ))

    @property
    def state(self) -> OrderState:
        """현재 상태"""
        return self._state

    @property
    def is_terminal(self) -> bool:
        """종료 상태 여부"""
        return self._state in self.TERMINAL_STATES

    @property
    def is_active(self) -> bool:
        """활성 상태 여부 (아직 완료되지 않음)"""
        return not self.is_terminal

    @property
    def can_cancel(self) -> bool:
        """취소 가능 여부"""
        return self.can_transition(OrderEvent.CANCEL)

    @property
    def can_fill(self) -> bool:
        """체결 가능 여부"""
        return self.can_transition(OrderEvent.FILL)

    @property
    def history(self) -> List[StateTransition]:
        """상태 전이 이력"""
        return self._history.copy()

    def can_transition(self, event: OrderEvent) -> bool:
        """
        특정 이벤트로 전이 가능한지 확인

        Args:
            event: 확인할 이벤트

        Returns:
            bool: 전이 가능 여부
        """
        return (self._state, event) in self.TRANSITIONS

    def get_valid_events(self) -> List[OrderEvent]:
        """
        현재 상태에서 유효한 이벤트 목록

        Returns:
            List[OrderEvent]: 유효한 이벤트 목록
        """
        return [
            event for (state, event) in self.TRANSITIONS.keys()
            if state == self._state
        ]

    def transition(
        self,
        event: OrderEvent,
        details: Optional[Dict[str, Any]] = None,
        validate_only: bool = False
    ) -> OrderState:
        """
        상태 전이 실행

        Args:
            event: 이벤트
            details: 전이 상세 정보
            validate_only: True면 검증만 수행

        Returns:
            OrderState: 전이 후 상태

        Raises:
            InvalidTransitionError: 유효하지 않은 전이
        """
        # 종료 상태에서는 전이 불가
        if self.is_terminal:
            raise InvalidTransitionError(self._state, event)

        # 전이 유효성 검사
        key = (self._state, event)
        if key not in self.TRANSITIONS:
            raise InvalidTransitionError(self._state, event)

        next_state = self.TRANSITIONS[key]

        if validate_only:
            return next_state

        # 전이 실행
        transition = StateTransition(
            from_state=self._state,
            to_state=next_state,
            event=event,
            details=details or {}
        )

        prev_state = self._state
        self._state = next_state
        self._history.append(transition)

        logger.debug(
            f"Order {self.order_id}: {prev_state.value} -> {next_state.value} "
            f"[{event.value}]"
        )

        # 콜백 실행
        if self._on_transition:
            try:
                self._on_transition(transition)
            except Exception as e:
                logger.error(f"Transition callback error: {e}")

        return next_state

    def submit(self, details: Optional[Dict] = None) -> OrderState:
        """주문 제출"""
        return self.transition(OrderEvent.SUBMIT, details)

    def acknowledge(self, details: Optional[Dict] = None) -> OrderState:
        """접수 확인"""
        return self.transition(OrderEvent.ACK, details)

    def fill(self, filled_quantity: int, filled_price: float) -> OrderState:
        """전량 체결"""
        return self.transition(OrderEvent.FILL, {
            'filled_quantity': filled_quantity,
            'filled_price': filled_price,
        })

    def partial_fill(
        self,
        filled_quantity: int,
        filled_price: float
    ) -> OrderState:
        """부분 체결"""
        return self.transition(OrderEvent.PARTIAL, {
            'filled_quantity': filled_quantity,
            'filled_price': filled_price,
        })

    def cancel(self, reason: str = "") -> OrderState:
        """취소"""
        return self.transition(OrderEvent.CANCEL, {'reason': reason})

    def reject(self, reason: str = "") -> OrderState:
        """거부"""
        return self.transition(OrderEvent.REJECT, {'reason': reason})

    def expire(self) -> OrderState:
        """만료"""
        return self.transition(OrderEvent.EXPIRE)

    def fail(self, reason: str = "") -> OrderState:
        """실패"""
        return self.transition(OrderEvent.FAIL, {'reason': reason})

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 변환"""
        return {
            'order_id': self.order_id,
            'current_state': self._state.value,
            'is_terminal': self.is_terminal,
            'is_active': self.is_active,
            'can_cancel': self.can_cancel,
            'valid_events': [e.value for e in self.get_valid_events()],
            'history': [
                {
                    'from': t.from_state.value,
                    'to': t.to_state.value,
                    'event': t.event.value,
                    'timestamp': t.timestamp.isoformat(),
                    'details': t.details,
                }
                for t in self._history
            ]
        }


class OrderStateMachineManager:
    """
    주문 상태머신 관리자

    여러 주문의 상태머신을 관리합니다.
    """

    def __init__(
        self,
        on_transition: Optional[Callable[[str, StateTransition], None]] = None
    ):
        """
        Args:
            on_transition: 상태 전이 시 콜백 (order_id, transition)
        """
        self._machines: Dict[str, OrderStateMachine] = {}
        self._on_transition = on_transition

    def create(
        self,
        order_id: str,
        initial_state: OrderState = OrderState.CREATED
    ) -> OrderStateMachine:
        """
        새 주문 상태머신 생성

        Args:
            order_id: 주문 ID
            initial_state: 초기 상태

        Returns:
            OrderStateMachine: 생성된 상태머신
        """
        if order_id in self._machines:
            raise ValueError(f"Order {order_id} already exists")

        def callback(transition: StateTransition):
            if self._on_transition:
                self._on_transition(order_id, transition)

        machine = OrderStateMachine(
            order_id=order_id,
            initial_state=initial_state,
            on_transition=callback
        )

        self._machines[order_id] = machine
        return machine

    def get(self, order_id: str) -> Optional[OrderStateMachine]:
        """주문 상태머신 조회"""
        return self._machines.get(order_id)

    def remove(self, order_id: str) -> bool:
        """주문 상태머신 제거"""
        if order_id in self._machines:
            del self._machines[order_id]
            return True
        return False

    def get_active_orders(self) -> List[str]:
        """활성 주문 ID 목록"""
        return [
            oid for oid, machine in self._machines.items()
            if machine.is_active
        ]

    def get_orders_by_state(self, state: OrderState) -> List[str]:
        """특정 상태의 주문 ID 목록"""
        return [
            oid for oid, machine in self._machines.items()
            if machine.state == state
        ]

    def get_statistics(self) -> Dict[str, Any]:
        """통계"""
        state_counts = {}
        for machine in self._machines.values():
            state = machine.state.value
            state_counts[state] = state_counts.get(state, 0) + 1

        return {
            'total_orders': len(self._machines),
            'active_orders': len(self.get_active_orders()),
            'state_counts': state_counts,
        }

    def transition_all(
        self,
        event: OrderEvent,
        filter_states: Optional[List[OrderState]] = None
    ) -> Dict[str, OrderState]:
        """
        조건에 맞는 모든 주문 상태 전이

        Args:
            event: 이벤트
            filter_states: 대상 상태 필터 (None이면 모든 활성 주문)

        Returns:
            Dict[str, OrderState]: {order_id: 전이 후 상태}
        """
        results = {}

        for order_id, machine in self._machines.items():
            if machine.is_terminal:
                continue

            if filter_states and machine.state not in filter_states:
                continue

            if machine.can_transition(event):
                try:
                    new_state = machine.transition(event)
                    results[order_id] = new_state
                except InvalidTransitionError:
                    pass

        return results

    def cleanup_terminal_orders(self, keep_count: int = 100) -> int:
        """
        종료된 주문 정리

        Args:
            keep_count: 보관할 종료 주문 수

        Returns:
            int: 제거된 주문 수
        """
        terminal_orders = [
            (oid, m) for oid, m in self._machines.items()
            if m.is_terminal
        ]

        if len(terminal_orders) <= keep_count:
            return 0

        # 오래된 것부터 제거
        terminal_orders.sort(key=lambda x: x[1].history[-1].timestamp)
        to_remove = len(terminal_orders) - keep_count

        removed = 0
        for oid, _ in terminal_orders[:to_remove]:
            if self.remove(oid):
                removed += 1

        return removed
