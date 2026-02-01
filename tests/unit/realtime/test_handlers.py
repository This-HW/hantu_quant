"""PositionMonitor 단위 테스트

Tests:
    - VAL-001: 손절 조건 검증
    - VAL-002: 익절 조건 검증
    - STATE-001: 포지션 상태 전이
    - 콜백 실행
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from core.realtime.processor import RealtimeProcessor
from core.realtime.handlers import PositionMonitor


class TestStopLossConditionValidation:
    """손절 조건 검증 테스트 (VAL-001)"""

    @pytest.mark.asyncio
    async def test_손절_조건_충족_시_이벤트_반환(self):
        """현재가 <= 손절가이면 이벤트 반환"""
        processor = RealtimeProcessor()
        monitor = PositionMonitor(processor)

        # 포지션 추가 (진입가=10000, 손절가=9700)
        processor.add_position("005930", 10000, 10, stop_loss_ratio=0.03)

        # 손절가 이하로 하락
        event = await monitor.check_position("005930", 9700)

        assert event is not None
        assert event["type"] == "stop_loss"
        assert event["stock_code"] == "005930"
        assert event["current_price"] == 9700
        assert event["loss"] < 0

    @pytest.mark.asyncio
    async def test_손절_조건_미충족_시_None(self):
        """현재가 > 손절가이면 None 반환"""
        processor = RealtimeProcessor()
        monitor = PositionMonitor(processor)

        processor.add_position("005930", 10000, 10, stop_loss_ratio=0.03)

        # 손절가보다 높음
        event = await monitor.check_position("005930", 9800)

        assert event is None

    @pytest.mark.asyncio
    async def test_손절_조건_충족_시_상태_전이(self):
        """손절 조건 충족 시 상태가 active → stop_loss_triggered로 전이"""
        processor = RealtimeProcessor()
        monitor = PositionMonitor(processor)

        processor.add_position("005930", 10000, 10, stop_loss_ratio=0.03)

        position = processor.get_position("005930")
        assert position["status"] == "active"

        await monitor.check_position("005930", 9700)

        position = processor.get_position("005930")
        assert position["status"] == "stop_loss_triggered"

    @pytest.mark.asyncio
    async def test_손절_후_재검증_무시(self):
        """이미 손절된 포지션은 재검증하지 않음"""
        processor = RealtimeProcessor()
        monitor = PositionMonitor(processor)

        processor.add_position("005930", 10000, 10, stop_loss_ratio=0.03)

        # 첫 번째 손절
        event1 = await monitor.check_position("005930", 9700)
        assert event1 is not None

        # 두 번째 검증 (이미 triggered 상태)
        event2 = await monitor.check_position("005930", 9600)
        assert event2 is None  # 무시됨


class TestTakeProfitConditionValidation:
    """익절 조건 검증 테스트 (VAL-002)"""

    @pytest.mark.asyncio
    async def test_익절_조건_충족_시_이벤트_반환(self):
        """현재가 >= 익절가이면 이벤트 반환"""
        processor = RealtimeProcessor()
        monitor = PositionMonitor(processor)

        # 포지션 추가 (진입가=10000, 익절가=10500)
        processor.add_position("005930", 10000, 10, take_profit_ratio=0.05)

        # 익절가 이상 상승
        event = await monitor.check_position("005930", 10500)

        assert event is not None
        assert event["type"] == "take_profit"
        assert event["stock_code"] == "005930"
        assert event["current_price"] == 10500
        assert event["profit"] > 0

    @pytest.mark.asyncio
    async def test_익절_조건_미충족_시_None(self):
        """현재가 < 익절가이면 None 반환"""
        processor = RealtimeProcessor()
        monitor = PositionMonitor(processor)

        processor.add_position("005930", 10000, 10, take_profit_ratio=0.05)

        # 익절가보다 낮음
        event = await monitor.check_position("005930", 10400)

        assert event is None

    @pytest.mark.asyncio
    async def test_익절_조건_충족_시_상태_전이(self):
        """익절 조건 충족 시 상태가 active → take_profit_triggered로 전이"""
        processor = RealtimeProcessor()
        monitor = PositionMonitor(processor)

        processor.add_position("005930", 10000, 10, take_profit_ratio=0.05)

        position = processor.get_position("005930")
        assert position["status"] == "active"

        await monitor.check_position("005930", 10500)

        position = processor.get_position("005930")
        assert position["status"] == "take_profit_triggered"


class TestCallbackExecution:
    """콜백 실행 테스트"""

    @pytest.mark.asyncio
    async def test_손절_콜백_실행(self):
        """손절 이벤트 발생 시 등록된 콜백 실행"""
        processor = RealtimeProcessor()
        monitor = PositionMonitor(processor)

        callback_called = False
        callback_event = None

        async def stop_loss_callback(event):
            nonlocal callback_called, callback_event
            callback_called = True
            callback_event = event

        monitor.add_stop_loss_callback(stop_loss_callback)
        processor.add_position("005930", 10000, 10, stop_loss_ratio=0.03)

        await monitor.check_position("005930", 9700)

        assert callback_called is True
        assert callback_event is not None
        assert callback_event["type"] == "stop_loss"

    @pytest.mark.asyncio
    async def test_익절_콜백_실행(self):
        """익절 이벤트 발생 시 등록된 콜백 실행"""
        processor = RealtimeProcessor()
        monitor = PositionMonitor(processor)

        callback_called = False
        callback_event = None

        async def take_profit_callback(event):
            nonlocal callback_called, callback_event
            callback_called = True
            callback_event = event

        monitor.add_take_profit_callback(take_profit_callback)
        processor.add_position("005930", 10000, 10, take_profit_ratio=0.05)

        await monitor.check_position("005930", 10500)

        assert callback_called is True
        assert callback_event is not None
        assert callback_event["type"] == "take_profit"

    @pytest.mark.asyncio
    async def test_알림_콜백_실행(self):
        """이벤트 발생 시 알림 콜백 실행"""
        processor = RealtimeProcessor()
        monitor = PositionMonitor(processor)

        alerts_received = []

        async def alert_callback(alert):
            alerts_received.append(alert)

        monitor.add_alert_callback(alert_callback)
        processor.add_position("005930", 10000, 10, stop_loss_ratio=0.03)

        await monitor.check_position("005930", 9700)

        assert len(alerts_received) == 1
        assert alerts_received[0]["priority"] == "emergency"


class TestTradingEngineIntegration:
    """TradingEngine 통합 테스트"""

    @pytest.mark.skip(reason="Batch 2에서 TradingEngine.sell() 메서드 구현 예정")
    @pytest.mark.asyncio
    async def test_손절_시_자동_매도_주문_실행(self):
        """손절 조건 충족 시 TradingEngine을 통해 자동 매도"""
        processor = RealtimeProcessor()

        # Mock TradingEngine
        mock_engine = MagicMock()
        mock_engine.sell = AsyncMock(return_value={"success": True, "order_number": "12345"})

        monitor = PositionMonitor(processor, trading_engine=mock_engine)

        processor.add_position("005930", 10000, 10, stop_loss_ratio=0.03)

        await monitor.check_position("005930", 9700)

        # TradingEngine.sell 호출 확인
        mock_engine.sell.assert_called_once()
        call_args = mock_engine.sell.call_args
        assert call_args.kwargs["stock_code"] == "005930"
        assert call_args.kwargs["quantity"] == 10
        assert call_args.kwargs["order_type"] == "시장가"
        assert call_args.kwargs["reason"] == "stop_loss"

    @pytest.mark.skip(reason="Batch 2에서 TradingEngine.sell() 메서드 구현 예정")
    @pytest.mark.asyncio
    async def test_익절_시_자동_매도_주문_실행(self):
        """익절 조건 충족 시 TradingEngine을 통해 자동 매도"""
        processor = RealtimeProcessor()

        # Mock TradingEngine
        mock_engine = MagicMock()
        mock_engine.sell = AsyncMock(return_value={"success": True, "order_number": "12345"})

        monitor = PositionMonitor(processor, trading_engine=mock_engine)

        processor.add_position("005930", 10000, 10, take_profit_ratio=0.05)

        await monitor.check_position("005930", 10500)

        # TradingEngine.sell 호출 확인
        mock_engine.sell.assert_called_once()
        call_args = mock_engine.sell.call_args
        assert call_args.kwargs["reason"] == "take_profit"

    @pytest.mark.asyncio
    async def test_TradingEngine_없으면_주문_스킵(self):
        """TradingEngine이 없으면 주문 실행 스킵 (로그만)"""
        processor = RealtimeProcessor()
        monitor = PositionMonitor(processor, trading_engine=None)

        processor.add_position("005930", 10000, 10, stop_loss_ratio=0.03)

        # TradingEngine 없이도 이벤트는 반환됨
        event = await monitor.check_position("005930", 9700)

        assert event is not None
        assert event["type"] == "stop_loss"


class TestPositionMonitoring:
    """포지션 모니터링 테스트"""

    @pytest.mark.asyncio
    async def test_모든_포지션_모니터링(self):
        """여러 포지션을 동시에 모니터링"""
        processor = RealtimeProcessor()
        monitor = PositionMonitor(processor)

        # 3개 포지션 추가
        processor.add_position("005930", 10000, 10, stop_loss_ratio=0.03)
        processor.add_position("000660", 50000, 5, take_profit_ratio=0.05)
        processor.add_position("035720", 30000, 20)

        # 현재가 업데이트 (005930은 손절, 000660은 익절)
        processor.process_realtime_price({"stock_code": "005930", "current_price": 9700, "timestamp": "153000", "volume": 1000})
        processor.process_realtime_price({"stock_code": "000660", "current_price": 52500, "timestamp": "153000", "volume": 1000})
        processor.process_realtime_price({"stock_code": "035720", "current_price": 31000, "timestamp": "153000", "volume": 1000})

        events = await monitor.monitor_all_positions()

        # 2개 이벤트 발생 (손절 1개, 익절 1개)
        assert len(events) == 2
        event_types = [e["type"] for e in events]
        assert "stop_loss" in event_types
        assert "take_profit" in event_types


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
