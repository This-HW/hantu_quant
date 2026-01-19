"""
주문 상태머신 테스트
"""

import pytest

from core.paper_trading.order_state_machine import (
    OrderStateMachine,
    OrderStateMachineManager,
    OrderState,
    OrderEvent,
    StateTransition,
    InvalidTransitionError,
)


class TestOrderStateMachine:
    """OrderStateMachine 테스트"""

    def test_initial_state(self):
        machine = OrderStateMachine("order-001")
        assert machine.state == OrderState.CREATED
        assert machine.is_active is True
        assert machine.is_terminal is False

    def test_custom_initial_state(self):
        machine = OrderStateMachine("order-001", initial_state=OrderState.SUBMITTED)
        assert machine.state == OrderState.SUBMITTED

    def test_valid_transition(self):
        machine = OrderStateMachine("order-001")
        new_state = machine.submit()
        assert new_state == OrderState.PENDING_SUBMIT
        assert machine.state == OrderState.PENDING_SUBMIT

    def test_invalid_transition(self):
        machine = OrderStateMachine("order-001")
        with pytest.raises(InvalidTransitionError) as exc_info:
            machine.fill(100, 70000)  # Cannot fill from CREATED

        assert exc_info.value.current_state == OrderState.CREATED
        assert exc_info.value.event == OrderEvent.FILL

    def test_terminal_state(self):
        machine = OrderStateMachine("order-001")
        machine.submit()
        machine.acknowledge()
        machine.fill(100, 70000)

        assert machine.state == OrderState.FILLED
        assert machine.is_terminal is True
        assert machine.is_active is False

    def test_cannot_transition_from_terminal(self):
        machine = OrderStateMachine("order-001")
        machine.submit()
        machine.reject("Invalid order")

        assert machine.is_terminal is True

        with pytest.raises(InvalidTransitionError):
            machine.submit()


class TestOrderWorkflows:
    """주문 워크플로우 테스트"""

    def test_market_order_workflow(self):
        """시장가 주문 워크플로우"""
        machine = OrderStateMachine("order-001")

        machine.submit()
        assert machine.state == OrderState.PENDING_SUBMIT

        machine.acknowledge()
        assert machine.state == OrderState.SUBMITTED

        machine.fill(100, 70000)
        assert machine.state == OrderState.FILLED
        assert machine.is_terminal is True

    def test_limit_order_workflow(self):
        """지정가 주문 워크플로우"""
        machine = OrderStateMachine("order-001")

        machine.submit()
        machine.acknowledge()
        machine.acknowledge()  # 체결 대기로 전환
        assert machine.state == OrderState.PENDING_FILL

        machine.fill(100, 70000)
        assert machine.state == OrderState.FILLED

    def test_partial_fill_workflow(self):
        """부분 체결 워크플로우"""
        machine = OrderStateMachine("order-001")

        machine.submit()
        machine.acknowledge()
        machine.partial_fill(50, 70000)
        assert machine.state == OrderState.PARTIAL_FILL

        machine.partial_fill(30, 70100)
        assert machine.state == OrderState.PARTIAL_FILL

        machine.fill(20, 70200)
        assert machine.state == OrderState.FILLED

    def test_cancel_workflow(self):
        """취소 워크플로우"""
        machine = OrderStateMachine("order-001")

        machine.submit()
        machine.acknowledge()
        machine.cancel("User requested")
        assert machine.state == OrderState.CANCELLED

    def test_cancel_from_partial_fill(self):
        """부분 체결 후 취소"""
        machine = OrderStateMachine("order-001")

        machine.submit()
        machine.acknowledge()
        machine.partial_fill(50, 70000)
        machine.cancel("Price moved away")
        assert machine.state == OrderState.CANCELLED

    def test_reject_workflow(self):
        """거부 워크플로우"""
        machine = OrderStateMachine("order-001")

        machine.submit()
        machine.reject("Insufficient funds")
        assert machine.state == OrderState.REJECTED

    def test_expire_workflow(self):
        """만료 워크플로우"""
        machine = OrderStateMachine("order-001")

        machine.submit()
        machine.acknowledge()
        machine.expire()
        assert machine.state == OrderState.EXPIRED


class TestStateTransitionHistory:
    """상태 전이 이력 테스트"""

    def test_history_recorded(self):
        machine = OrderStateMachine("order-001")
        machine.submit()
        machine.acknowledge()
        machine.fill(100, 70000)

        history = machine.history
        # Initial + 3 transitions = 4 entries
        assert len(history) == 4

    def test_history_details(self):
        machine = OrderStateMachine("order-001")
        machine.submit()
        machine.acknowledge()
        machine.fill(100, 70000)

        history = machine.history
        fill_transition = history[-1]

        assert fill_transition.from_state == OrderState.SUBMITTED
        assert fill_transition.to_state == OrderState.FILLED
        assert fill_transition.event == OrderEvent.FILL
        assert fill_transition.details['filled_quantity'] == 100
        assert fill_transition.details['filled_price'] == 70000


class TestCanTransition:
    """전이 가능 여부 테스트"""

    def test_can_transition_valid(self):
        machine = OrderStateMachine("order-001")
        assert machine.can_transition(OrderEvent.SUBMIT) is True

    def test_can_transition_invalid(self):
        machine = OrderStateMachine("order-001")
        assert machine.can_transition(OrderEvent.FILL) is False

    def test_can_cancel_from_submitted(self):
        machine = OrderStateMachine("order-001")
        machine.submit()
        machine.acknowledge()

        assert machine.can_cancel is True

    def test_cannot_cancel_from_filled(self):
        machine = OrderStateMachine("order-001")
        machine.submit()
        machine.acknowledge()
        machine.fill(100, 70000)

        assert machine.can_cancel is False


class TestValidEvents:
    """유효한 이벤트 목록 테스트"""

    def test_valid_events_from_created(self):
        machine = OrderStateMachine("order-001")
        events = machine.get_valid_events()

        assert OrderEvent.SUBMIT in events
        assert OrderEvent.CANCEL in events
        assert OrderEvent.REJECT in events
        assert OrderEvent.FILL not in events

    def test_valid_events_from_submitted(self):
        machine = OrderStateMachine("order-001")
        machine.submit()
        machine.acknowledge()

        events = machine.get_valid_events()
        assert OrderEvent.FILL in events
        assert OrderEvent.PARTIAL in events
        assert OrderEvent.CANCEL in events


class TestTransitionCallback:
    """전이 콜백 테스트"""

    def test_callback_called(self):
        called = []

        def callback(transition: StateTransition):
            called.append(transition)

        machine = OrderStateMachine("order-001", on_transition=callback)
        machine.submit()

        assert len(called) == 1
        assert called[0].event == OrderEvent.SUBMIT

    def test_callback_error_handled(self):
        def bad_callback(transition: StateTransition):
            raise RuntimeError("Callback error")

        machine = OrderStateMachine("order-001", on_transition=bad_callback)
        # Should not raise
        machine.submit()
        assert machine.state == OrderState.PENDING_SUBMIT


class TestOrderStateMachineManager:
    """OrderStateMachineManager 테스트"""

    def test_create_machine(self):
        manager = OrderStateMachineManager()
        machine = manager.create("order-001")

        assert machine.order_id == "order-001"
        assert machine.state == OrderState.CREATED

    def test_duplicate_order_id_raises(self):
        manager = OrderStateMachineManager()
        manager.create("order-001")

        with pytest.raises(ValueError):
            manager.create("order-001")

    def test_get_machine(self):
        manager = OrderStateMachineManager()
        manager.create("order-001")

        machine = manager.get("order-001")
        assert machine is not None
        assert machine.order_id == "order-001"

    def test_get_nonexistent_machine(self):
        manager = OrderStateMachineManager()
        machine = manager.get("nonexistent")
        assert machine is None

    def test_remove_machine(self):
        manager = OrderStateMachineManager()
        manager.create("order-001")

        assert manager.remove("order-001") is True
        assert manager.get("order-001") is None

    def test_get_active_orders(self):
        manager = OrderStateMachineManager()

        manager.create("order-001")
        m2 = manager.create("order-002")
        manager.create("order-003")

        # Fill one order
        m2.submit()
        m2.acknowledge()
        m2.fill(100, 70000)

        active = manager.get_active_orders()
        assert "order-001" in active
        assert "order-002" not in active
        assert "order-003" in active

    def test_get_orders_by_state(self):
        manager = OrderStateMachineManager()

        m1 = manager.create("order-001")
        manager.create("order-002")

        m1.submit()
        m1.acknowledge()

        submitted = manager.get_orders_by_state(OrderState.SUBMITTED)
        created = manager.get_orders_by_state(OrderState.CREATED)

        assert "order-001" in submitted
        assert "order-002" in created

    def test_statistics(self):
        manager = OrderStateMachineManager()

        manager.create("order-001")
        m2 = manager.create("order-002")
        m2.submit()

        stats = manager.get_statistics()
        assert stats['total_orders'] == 2
        assert stats['active_orders'] == 2
        assert stats['state_counts']['created'] == 1
        assert stats['state_counts']['pending_submit'] == 1

    def test_transition_all(self):
        manager = OrderStateMachineManager()

        m1 = manager.create("order-001")
        m2 = manager.create("order-002")
        m3 = manager.create("order-003")

        # Submit all
        m1.submit()
        m2.submit()
        m3.submit()

        # Acknowledge all pending_submit orders
        results = manager.transition_all(
            OrderEvent.ACK,
            filter_states=[OrderState.PENDING_SUBMIT]
        )

        assert len(results) == 3
        assert all(state == OrderState.SUBMITTED for state in results.values())


class TestCleanup:
    """정리 기능 테스트"""

    def test_cleanup_terminal_orders(self):
        manager = OrderStateMachineManager()

        # Create and fill 5 orders
        for i in range(5):
            m = manager.create(f"order-{i:03d}")
            m.submit()
            m.acknowledge()
            m.fill(100, 70000)

        # Create 2 active orders
        manager.create("order-100")
        manager.create("order-101")

        removed = manager.cleanup_terminal_orders(keep_count=2)

        assert removed == 3  # 5 terminal - 2 keep = 3 removed
        assert len(manager.get_active_orders()) == 2

    def test_cleanup_no_removal_needed(self):
        manager = OrderStateMachineManager()

        m = manager.create("order-001")
        m.submit()
        m.acknowledge()
        m.fill(100, 70000)

        removed = manager.cleanup_terminal_orders(keep_count=10)
        assert removed == 0


class TestToDictSerialization:
    """직렬화 테스트"""

    def test_to_dict(self):
        machine = OrderStateMachine("order-001")
        machine.submit()
        machine.acknowledge()

        data = machine.to_dict()

        assert data['order_id'] == "order-001"
        assert data['current_state'] == "submitted"
        assert data['is_terminal'] is False
        assert data['is_active'] is True
        assert len(data['history']) >= 2
        assert isinstance(data['valid_events'], list)


class TestEdgeCases:
    """엣지 케이스 테스트"""

    def test_validate_only_mode(self):
        machine = OrderStateMachine("order-001")

        # Validate without actually transitioning
        next_state = machine.transition(OrderEvent.SUBMIT, validate_only=True)

        assert next_state == OrderState.PENDING_SUBMIT
        assert machine.state == OrderState.CREATED  # State unchanged

    def test_fail_transition(self):
        machine = OrderStateMachine("order-001")
        machine.submit()
        machine.fail("Network error")

        assert machine.state == OrderState.FAILED
        assert machine.is_terminal is True
