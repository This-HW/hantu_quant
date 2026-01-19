"""
Pydantic 데이터 검증 모델 테스트 (P2-1)

테스트 항목:
1. 종목코드 검증
2. 가격 데이터 검증
3. OHLCV 데이터 검증
4. 주문 요청 검증
5. 포지션/거래 결과 검증
"""

import pytest
from pydantic import ValidationError

from core.models.validators import (
    StockCode,
    PriceData,
    OrderRequest,
    VolumeData,
    OHLCVData,
    PositionData,
    TradeResult,
    OrderType,
    OrderSide,
    validate_stock_code,
    validate_price,
    parse_ohlcv_list,
    create_order_request,
)


class TestStockCode:
    """종목코드 검증 테스트"""

    def test_valid_stock_code(self):
        """유효한 종목코드"""
        code = StockCode(code="005930")
        assert code.code == "005930"
        assert str(code) == "005930"

    def test_valid_stock_codes(self):
        """다양한 유효 종목코드"""
        valid_codes = ["005930", "000660", "035420", "000001", "999999"]
        for c in valid_codes:
            code = StockCode(code=c)
            assert code.code == c

    def test_invalid_length_short(self):
        """짧은 종목코드"""
        with pytest.raises(ValidationError):
            StockCode(code="12345")

    def test_invalid_length_long(self):
        """긴 종목코드"""
        with pytest.raises(ValidationError):
            StockCode(code="1234567")

    def test_invalid_non_numeric(self):
        """숫자가 아닌 종목코드"""
        with pytest.raises(ValidationError):
            StockCode(code="00593A")

    def test_invalid_with_space(self):
        """공백 포함 종목코드"""
        with pytest.raises(ValidationError):
            StockCode(code="0059 0")


class TestPriceData:
    """가격 데이터 검증 테스트"""

    def test_valid_price_data(self):
        """유효한 가격 데이터"""
        price = PriceData(current_price=50000, change=1000, change_rate=2.0)
        assert price.current_price == 50000
        assert price.change_rate == 2.0

    def test_zero_price_invalid(self):
        """0원 가격 무효"""
        with pytest.raises(ValidationError):
            PriceData(current_price=0)

    def test_negative_price_invalid(self):
        """음수 가격 무효"""
        with pytest.raises(ValidationError):
            PriceData(current_price=-1000)

    def test_change_rate_range(self):
        """등락률 범위 테스트 (-30% ~ +30%)"""
        # 유효 범위
        PriceData(current_price=50000, change_rate=29.9)
        PriceData(current_price=50000, change_rate=-29.9)

        # 범위 초과
        with pytest.raises(ValidationError):
            PriceData(current_price=50000, change_rate=31.0)

        with pytest.raises(ValidationError):
            PriceData(current_price=50000, change_rate=-31.0)

    def test_high_low_validation(self):
        """고가 >= 저가 검증"""
        # 유효
        PriceData(current_price=50000, high=51000, low=49000)

        # 무효 (고가 < 저가)
        with pytest.raises(ValidationError):
            PriceData(current_price=50000, high=49000, low=51000)


class TestVolumeData:
    """거래량 데이터 검증 테스트"""

    def test_valid_volume(self):
        """유효한 거래량 데이터"""
        vol = VolumeData(volume=1000000, avg_volume_20d=500000)
        assert vol.volume == 1000000

    def test_negative_volume_invalid(self):
        """음수 거래량 무효"""
        with pytest.raises(ValidationError):
            VolumeData(volume=-100)

    def test_volume_surge(self):
        """거래량 급증 판단"""
        # 2배 이상이면 급증
        vol = VolumeData(volume=1000000, avg_volume_20d=400000)
        assert vol.is_volume_surge

        # 2배 미만이면 급증 아님
        vol = VolumeData(volume=700000, avg_volume_20d=400000)
        assert not vol.is_volume_surge


class TestOHLCVData:
    """OHLCV 데이터 검증 테스트"""

    def test_valid_ohlcv(self):
        """유효한 OHLCV 데이터"""
        ohlcv = OHLCVData(
            date="2024-01-15",
            open=50000,
            high=51000,
            low=49000,
            close=50500,
            volume=1000000,
        )
        assert ohlcv.close == 50500

    def test_invalid_high_less_than_low(self):
        """고가 < 저가 무효"""
        with pytest.raises(ValidationError):
            OHLCVData(
                date="2024-01-15",
                open=50000,
                high=48000,  # 고가가 저가보다 낮음
                low=49000,
                close=50500,
                volume=1000000,
            )

    def test_invalid_high_less_than_open_close(self):
        """고가 < 시가/종가 무효"""
        with pytest.raises(ValidationError):
            OHLCVData(
                date="2024-01-15",
                open=50000,
                high=49000,  # 고가가 시가보다 낮음
                low=48000,
                close=49500,
                volume=1000000,
            )

    def test_invalid_low_greater_than_open_close(self):
        """저가 > 시가/종가 무효"""
        with pytest.raises(ValidationError):
            OHLCVData(
                date="2024-01-15",
                open=50000,
                high=51000,
                low=50500,  # 저가가 시가보다 높음
                close=50200,
                volume=1000000,
            )

    def test_zero_price_invalid(self):
        """0원 가격 무효"""
        with pytest.raises(ValidationError):
            OHLCVData(
                date="2024-01-15",
                open=0,
                high=51000,
                low=49000,
                close=50500,
                volume=1000000,
            )


class TestOrderRequest:
    """주문 요청 검증 테스트"""

    def test_valid_limit_order(self):
        """유효한 지정가 주문"""
        order = OrderRequest(
            stock_code="005930",
            quantity=10,
            price=70000,
            order_type=OrderType.LIMIT,
            order_side=OrderSide.BUY,
        )
        assert order.stock_code == "005930"
        assert order.quantity == 10

    def test_valid_market_order(self):
        """유효한 시장가 주문"""
        order = OrderRequest(
            stock_code="005930",
            quantity=10,
            order_type=OrderType.MARKET,
            order_side=OrderSide.SELL,
        )
        assert order.price is None

    def test_limit_order_without_price(self):
        """지정가 주문에 가격 없음 무효"""
        with pytest.raises(ValidationError):
            OrderRequest(
                stock_code="005930",
                quantity=10,
                order_type=OrderType.LIMIT,
                order_side=OrderSide.BUY,
                price=None,
            )

    def test_invalid_stock_code(self):
        """무효한 종목코드"""
        with pytest.raises(ValidationError):
            OrderRequest(
                stock_code="SAMSUNG",
                quantity=10,
                price=70000,
                order_type=OrderType.LIMIT,
                order_side=OrderSide.BUY,
            )

    def test_zero_quantity_invalid(self):
        """0 수량 무효"""
        with pytest.raises(ValidationError):
            OrderRequest(
                stock_code="005930",
                quantity=0,
                price=70000,
                order_type=OrderType.LIMIT,
                order_side=OrderSide.BUY,
            )

    def test_quantity_limit(self):
        """수량 제한 (최대 100,000주)"""
        with pytest.raises(ValidationError):
            OrderRequest(
                stock_code="005930",
                quantity=100001,
                price=70000,
                order_type=OrderType.LIMIT,
                order_side=OrderSide.BUY,
            )

    def test_price_limit(self):
        """가격 제한 (최대 1억원)"""
        with pytest.raises(ValidationError):
            OrderRequest(
                stock_code="005930",
                quantity=10,
                price=100_000_001,
                order_type=OrderType.LIMIT,
                order_side=OrderSide.BUY,
            )


class TestPositionData:
    """포지션 데이터 검증 테스트"""

    def test_valid_position(self):
        """유효한 포지션 데이터"""
        pos = PositionData(
            stock_code="005930",
            stock_name="삼성전자",
            quantity=100,
            avg_price=70000,
            current_price=75000,
        )
        assert pos.quantity == 100
        # 수익률 자동 계산: (75000-70000)/70000 * 100 = 7.14%
        assert pos.profit_rate > 0

    def test_profit_calculation(self):
        """수익률/수익금 자동 계산"""
        pos = PositionData(
            stock_code="005930", quantity=100, avg_price=10000, current_price=12000
        )
        # 수익률: 20%
        assert abs(pos.profit_rate - 20.0) < 0.1
        # 수익금: 200,000원
        assert pos.profit_amount == 200000

    def test_invalid_stock_code(self):
        """무효한 종목코드"""
        with pytest.raises(ValidationError):
            PositionData(
                stock_code="ABCDEF", quantity=100, avg_price=70000, current_price=75000
            )


class TestTradeResult:
    """거래 결과 검증 테스트"""

    def test_valid_trade_result(self):
        """유효한 거래 결과"""
        result = TradeResult(
            order_id="ORD001",
            stock_code="005930",
            order_side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            requested_quantity=100,
            executed_quantity=100,
            requested_price=70000,
            executed_price=70000,
            status="executed",
        )
        assert result.is_fully_executed
        assert result.fill_rate == 100.0

    def test_partial_execution(self):
        """부분 체결"""
        result = TradeResult(
            order_id="ORD002",
            stock_code="005930",
            order_side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            requested_quantity=100,
            executed_quantity=50,
            status="partial",
        )
        assert not result.is_fully_executed
        assert result.fill_rate == 50.0

    def test_invalid_status(self):
        """무효한 상태"""
        with pytest.raises(ValidationError):
            TradeResult(
                order_id="ORD003",
                stock_code="005930",
                order_side=OrderSide.BUY,
                order_type=OrderType.LIMIT,
                requested_quantity=100,
                executed_quantity=0,
                status="invalid_status",
            )


class TestConvenienceFunctions:
    """편의 함수 테스트"""

    def test_validate_stock_code_valid(self):
        """유효 종목코드 검증"""
        assert validate_stock_code("005930")
        assert validate_stock_code("000660")

    def test_validate_stock_code_invalid(self):
        """무효 종목코드 검증"""
        assert not validate_stock_code("12345")
        assert not validate_stock_code("ABCDEF")

    def test_validate_price_valid(self):
        """유효 가격 검증"""
        assert validate_price(50000)
        assert validate_price(50000, 15.0)

    def test_validate_price_invalid(self):
        """무효 가격 검증"""
        assert not validate_price(0)
        assert not validate_price(-1000)
        assert not validate_price(50000, 35.0)

    def test_parse_ohlcv_list(self):
        """OHLCV 리스트 파싱"""
        data_list = [
            {
                "date": "2024-01-15",
                "open": 50000,
                "high": 51000,
                "low": 49000,
                "close": 50500,
                "volume": 1000000,
            },
            {
                "date": "2024-01-16",
                "open": 50500,
                "high": 52000,
                "low": 50000,
                "close": 51500,
                "volume": 1200000,
            },
            {
                "date": "invalid",
                "open": 0,
                "high": 0,
                "low": 0,
                "close": 0,
                "volume": 0,
            },  # 무효 데이터
        ]

        result = parse_ohlcv_list(data_list)

        # 유효한 2개만 파싱됨
        assert len(result) == 2
        assert result[0].date == "2024-01-15"

    def test_create_order_request(self):
        """주문 요청 생성"""
        order = create_order_request(
            stock_code="005930",
            quantity=10,
            side="buy",
            order_type="limit",
            price=70000,
        )

        assert order.stock_code == "005930"
        assert order.order_side == OrderSide.BUY

    def test_create_order_request_invalid(self):
        """무효한 주문 요청 생성"""
        with pytest.raises(Exception):
            create_order_request(
                stock_code="INVALID",
                quantity=10,
                side="buy",
                order_type="limit",
                price=70000,
            )


class TestEnums:
    """Enum 테스트"""

    def test_order_type_values(self):
        """OrderType enum 값"""
        assert OrderType.MARKET.value == "market"
        assert OrderType.LIMIT.value == "limit"

    def test_order_side_values(self):
        """OrderSide enum 값"""
        assert OrderSide.BUY.value == "buy"
        assert OrderSide.SELL.value == "sell"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
