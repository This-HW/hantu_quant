"""RealtimeProcessor 단위 테스트

Tests:
    - 손절가 계산 (CALC-001)
    - 익절가 계산 (CALC-002)
    - 포지션 관리
    - 가격 버퍼 관리
"""

import pytest
from collections import deque
from core.realtime.processor import RealtimeProcessor


class TestStopLossCalculation:
    """손절가 계산 테스트 (CALC-001)"""

    def test_고정비율_손절가_계산(self):
        """고정 비율 방식 손절가 계산 (ATR 없음)"""
        processor = RealtimeProcessor()

        entry_price = 10000
        stop_loss_ratio = 0.03  # 3%

        result = processor.calculate_stop_loss(entry_price, stop_loss_ratio)

        expected = 10000 * (1 - 0.03)  # 9700
        assert result == expected

    def test_ATR_손절가_계산_ATR_더_큼(self):
        """ATR 기반 손절가가 고정비율보다 큰 경우"""
        processor = RealtimeProcessor()

        entry_price = 10000
        stop_loss_ratio = 0.03  # 3% → 9700
        atr = 200  # ATR * 2 = 400 → 9600

        result = processor.calculate_stop_loss(entry_price, stop_loss_ratio, atr)

        # max(9700, 9600) = 9700 (보수적 손절 = 더 높은 값)
        assert result == 9700

    def test_ATR_손절가_계산_고정비율_더_큼(self):
        """ATR 기반 손절가가 고정비율보다 작은 경우"""
        processor = RealtimeProcessor()

        entry_price = 10000
        stop_loss_ratio = 0.03  # 3% → 9700
        atr = 100  # ATR * 2 = 200 → 9800

        result = processor.calculate_stop_loss(entry_price, stop_loss_ratio, atr)

        # max(9700, 9800) = 9800 (보수적 손절 = 더 높은 값)
        assert result == 9800

    def test_ATR_0인_경우_고정비율_사용(self):
        """ATR이 0인 경우 고정비율 사용"""
        processor = RealtimeProcessor()

        entry_price = 10000
        stop_loss_ratio = 0.05
        atr = 0  # ATR이 0

        result = processor.calculate_stop_loss(entry_price, stop_loss_ratio, atr)

        expected = 10000 * (1 - 0.05)
        assert result == expected


class TestTakeProfitCalculation:
    """익절가 계산 테스트 (CALC-002)"""

    def test_고정비율_익절가_계산(self):
        """고정 비율 방식 익절가 계산 (ATR 없음)"""
        processor = RealtimeProcessor()

        entry_price = 10000
        take_profit_ratio = 0.05  # 5%

        result = processor.calculate_take_profit(entry_price, take_profit_ratio)

        expected = 10000 * (1 + 0.05)  # 10500
        assert result == expected

    def test_ATR_익절가_계산_ATR_더_큼(self):
        """ATR 기반 익절가가 고정비율보다 큰 경우"""
        processor = RealtimeProcessor()

        entry_price = 10000
        take_profit_ratio = 0.05  # 5% → 10500
        atr = 300  # ATR * 3 = 900 → 10900

        result = processor.calculate_take_profit(entry_price, take_profit_ratio, atr)

        # max(10500, 10900) = 10900 (보수적 익절 = 더 높은 값)
        assert result == 10900

    def test_ATR_익절가_계산_고정비율_더_큼(self):
        """ATR 기반 익절가가 고정비율보다 작은 경우"""
        processor = RealtimeProcessor()

        entry_price = 10000
        take_profit_ratio = 0.05  # 5% → 10500
        atr = 100  # ATR * 3 = 300 → 10300

        result = processor.calculate_take_profit(entry_price, take_profit_ratio, atr)

        # max(10500, 10300) = 10500 (보수적 익절 = 더 높은 값)
        assert result == 10500


class TestPositionManagement:
    """포지션 관리 테스트"""

    def test_포지션_추가_성공(self):
        """포지션 추가 시 손절/익절가 자동 계산"""
        processor = RealtimeProcessor()

        processor.add_position(
            stock_code="005930",
            entry_price=70000,
            quantity=10,
            stop_loss_ratio=0.03,
            take_profit_ratio=0.05,
            atr=500
        )

        position = processor.get_position("005930")

        assert position is not None
        assert position["entry_price"] == 70000
        assert position["quantity"] == 10
        assert position["stop_loss_price"] > 0
        assert position["take_profit_price"] > 70000
        assert position["status"] == "active"

    def test_포지션_제거_성공(self):
        """포지션 제거"""
        processor = RealtimeProcessor()

        processor.add_position("005930", 70000, 10)
        assert processor.get_position("005930") is not None

        processor.remove_position("005930")
        assert processor.get_position("005930") is None

    def test_포지션_없는_종목_조회(self):
        """포지션이 없는 종목 조회 시 None 반환"""
        processor = RealtimeProcessor()

        result = processor.get_position("999999")
        assert result is None


class TestPriceBufferManagement:
    """가격 버퍼 관리 테스트"""

    def test_가격_버퍼_자동_생성(self):
        """가격 데이터 처리 시 버퍼 자동 생성"""
        processor = RealtimeProcessor(buffer_maxlen=100)

        data = {
            "stock_code": "005930",
            "current_price": 70000,
            "timestamp": "153000",
            "volume": 1000,
        }

        processor.process_realtime_price(data)

        buffer = processor.get_price_buffer("005930")
        assert len(buffer) == 1
        assert buffer[0]["price"] == 70000

    def test_가격_버퍼_FIFO_overflow(self):
        """버퍼 크기 초과 시 FIFO 방식으로 overflow"""
        processor = RealtimeProcessor(buffer_maxlen=3)

        # 4개 추가 (maxlen=3이므로 첫 번째 제거됨)
        for i in range(4):
            data = {
                "stock_code": "005930",
                "current_price": 70000 + i,
                "timestamp": f"15300{i}",
                "volume": 1000,
            }
            processor.process_realtime_price(data)

        buffer = processor.get_price_buffer("005930")

        assert len(buffer) == 3  # maxlen 유지
        assert buffer[0]["price"] == 70001  # 첫 번째(70000) 제거됨
        assert buffer[-1]["price"] == 70003

    def test_포지션_미실현손익_계산(self):
        """포지션이 있는 종목의 실시간 가격 처리 시 미실현 손익 계산"""
        processor = RealtimeProcessor()

        # 포지션 추가
        processor.add_position("005930", 70000, 10)

        # 가격 상승
        data = {
            "stock_code": "005930",
            "current_price": 71000,
            "timestamp": "153000",
            "volume": 1000,
        }

        result = processor.process_realtime_price(data)

        assert result is not None
        assert result["current_price"] == 71000
        assert result["unrealized_pnl"] == (71000 - 70000) * 10  # +10000

    def test_가격_버퍼_limit_조회(self):
        """가격 버퍼 제한 개수 조회"""
        processor = RealtimeProcessor()

        # 10개 추가
        for i in range(10):
            data = {
                "stock_code": "005930",
                "current_price": 70000 + i,
                "timestamp": f"15300{i}",
                "volume": 1000,
            }
            processor.process_realtime_price(data)

        # 최근 5개만 조회
        buffer = processor.get_price_buffer("005930", limit=5)

        assert len(buffer) == 5
        assert buffer[0]["price"] == 70005
        assert buffer[-1]["price"] == 70009


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
