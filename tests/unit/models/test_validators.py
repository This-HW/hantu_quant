# -*- coding: utf-8 -*-
"""
validators.py 단위 테스트

테스트 범위:
- PeriodDays: 조회 기간 검증 (1-365일)
- CountRange: 조회 건수 검증 (1-1000건)
- StockCode: 종목코드 검증 (6자리 숫자)
- PriceData: 가격 데이터 검증
- OHLCVData: OHLCV 관계 검증
- OrderRequest: 주문 요청 검증
"""

import pytest
from pydantic import ValidationError

from core.models.validators import (
    PeriodDays,
    CountRange,
    StockCode,
    PriceData,
    OHLCVData,
    OrderRequest,
    OrderType,
    OrderSide,
    PositionData,
    validate_stock_code,
    validate_price,
    create_order_request,
    parse_ohlcv_list,
)


class TestPeriodDays:
    """PeriodDays 모델 테스트 (조회 기간 검증)"""

    def test_valid_period_minimum(self):
        """정상: 최소 기간 (1일)"""
        period = PeriodDays(days=1)
        assert period.days == 1

    def test_valid_period_maximum(self):
        """정상: 최대 기간 (365일)"""
        period = PeriodDays(days=365)
        assert period.days == 365

    def test_valid_period_middle(self):
        """정상: 중간 값 (100일)"""
        period = PeriodDays(days=100)
        assert period.days == 100

    def test_invalid_period_zero(self):
        """비정상: 0일 (최소값 미만)"""
        with pytest.raises(ValidationError) as exc_info:
            PeriodDays(days=0)
        # Pydantic Field 검증 (ge=1) 에러 또는 커스텀 메시지
        error_str = str(exc_info.value)
        assert "조회 기간" in error_str or "greater than or equal to 1" in error_str

    def test_invalid_period_negative(self):
        """비정상: 음수"""
        with pytest.raises(ValidationError) as exc_info:
            PeriodDays(days=-10)
        error_str = str(exc_info.value)
        assert "조회 기간" in error_str or "greater than or equal to 1" in error_str

    def test_invalid_period_over_maximum(self):
        """비정상: 366일 (최대값 초과)"""
        with pytest.raises(ValidationError) as exc_info:
            PeriodDays(days=366)
        error_str = str(exc_info.value)
        assert "조회 기간" in error_str or "less than or equal to 365" in error_str

    def test_invalid_period_large_number(self):
        """비정상: 매우 큰 숫자"""
        with pytest.raises(ValidationError) as exc_info:
            PeriodDays(days=9999)
        error_str = str(exc_info.value)
        assert "조회 기간" in error_str or "less than or equal to 365" in error_str

    def test_string_representation(self):
        """문자열 변환"""
        period = PeriodDays(days=30)
        assert str(period) == "30"


class TestCountRange:
    """CountRange 모델 테스트 (조회 건수 검증)"""

    def test_valid_count_minimum(self):
        """정상: 최소 건수 (1건)"""
        count = CountRange(count=1)
        assert count.count == 1

    def test_valid_count_maximum(self):
        """정상: 최대 건수 (1000건)"""
        count = CountRange(count=1000)
        assert count.count == 1000

    def test_valid_count_middle(self):
        """정상: 중간 값 (100건)"""
        count = CountRange(count=100)
        assert count.count == 100

    def test_invalid_count_zero(self):
        """비정상: 0건 (최소값 미만)"""
        with pytest.raises(ValidationError) as exc_info:
            CountRange(count=0)
        error_str = str(exc_info.value)
        assert "조회 건수" in error_str or "greater than or equal to 1" in error_str

    def test_invalid_count_negative(self):
        """비정상: 음수"""
        with pytest.raises(ValidationError) as exc_info:
            CountRange(count=-5)
        error_str = str(exc_info.value)
        assert "조회 건수" in error_str or "greater than or equal to 1" in error_str

    def test_invalid_count_over_maximum(self):
        """비정상: 1001건 (최대값 초과)"""
        with pytest.raises(ValidationError) as exc_info:
            CountRange(count=1001)
        error_str = str(exc_info.value)
        assert "조회 건수" in error_str or "less than or equal to 1000" in error_str

    def test_invalid_count_large_number(self):
        """비정상: 매우 큰 숫자"""
        with pytest.raises(ValidationError) as exc_info:
            CountRange(count=99999)
        error_str = str(exc_info.value)
        assert "조회 건수" in error_str or "less than or equal to 1000" in error_str

    def test_string_representation(self):
        """문자열 변환"""
        count = CountRange(count=50)
        assert str(count) == "50"


class TestStockCode:
    """StockCode 모델 테스트 (종목코드 검증)"""

    def test_valid_stock_code(self):
        """정상: 6자리 숫자"""
        stock = StockCode(code="005930")
        assert stock.code == "005930"
        assert str(stock) == "005930"

    def test_valid_stock_code_leading_zeros(self):
        """정상: 앞에 0이 있는 종목코드"""
        stock = StockCode(code="000660")
        assert stock.code == "000660"

    def test_invalid_stock_code_short(self):
        """비정상: 5자리 (길이 부족)"""
        with pytest.raises(ValidationError) as exc_info:
            StockCode(code="12345")
        error_str = str(exc_info.value)
        assert "종목코드 형식 오류" in error_str or "at least 6 characters" in error_str

    def test_invalid_stock_code_long(self):
        """비정상: 7자리 (길이 초과)"""
        with pytest.raises(ValidationError) as exc_info:
            StockCode(code="1234567")
        error_str = str(exc_info.value)
        assert "종목코드 형식 오류" in error_str or "at most 6 characters" in error_str

    def test_invalid_stock_code_alphabets(self):
        """비정상: 알파벳 포함"""
        with pytest.raises(ValidationError) as exc_info:
            StockCode(code="ABC123")
        assert "종목코드 형식 오류" in str(exc_info.value)

    def test_invalid_stock_code_special_chars(self):
        """비정상: 특수문자 포함"""
        with pytest.raises(ValidationError) as exc_info:
            StockCode(code="123-45")
        assert "종목코드 형식 오류" in str(exc_info.value)

    def test_invalid_stock_code_empty(self):
        """비정상: 빈 문자열"""
        with pytest.raises(ValidationError):
            StockCode(code="")


class TestPriceData:
    """PriceData 모델 테스트 (가격 데이터 검증)"""

    def test_valid_price_data(self):
        """정상: 유효한 가격 데이터"""
        price = PriceData(
            current_price=50000,
            change=1000,
            change_rate=2.5,
            volume=1000000,
            high=51000,
            low=49000,
            open=49500
        )
        assert price.current_price == 50000
        assert price.change == 1000
        assert price.change_rate == 2.5

    def test_invalid_price_negative(self):
        """비정상: 음수 가격"""
        with pytest.raises(ValidationError):
            PriceData(current_price=-1000)

    def test_invalid_price_zero(self):
        """비정상: 0원 (양수 필수)"""
        with pytest.raises(ValidationError):
            PriceData(current_price=0)

    def test_invalid_change_rate_over_limit(self):
        """비정상: 등락률 ±30% 초과"""
        with pytest.raises(ValidationError):
            PriceData(current_price=50000, change_rate=35.0)

        with pytest.raises(ValidationError):
            PriceData(current_price=50000, change_rate=-35.0)

    def test_valid_change_rate_boundary(self):
        """정상: 등락률 경계값 (±30%)"""
        price_up = PriceData(current_price=50000, change_rate=30.0)
        assert price_up.change_rate == 30.0

        price_down = PriceData(current_price=50000, change_rate=-30.0)
        assert price_down.change_rate == -30.0

    def test_invalid_high_low_relationship(self):
        """비정상: 고가 < 저가"""
        with pytest.raises(ValidationError) as exc_info:
            PriceData(
                current_price=50000,
                high=49000,  # 고가가 저가보다 낮음
                low=51000
            )
        assert "고가" in str(exc_info.value) and "저가" in str(exc_info.value)


class TestOHLCVData:
    """OHLCVData 모델 테스트 (OHLCV 관계 검증)"""

    def test_valid_ohlcv_data(self):
        """정상: 유효한 OHLCV 데이터"""
        ohlcv = OHLCVData(
            date="2024-01-15",
            open=50000,
            high=52000,
            low=49000,
            close=51000,
            volume=1000000
        )
        assert ohlcv.open == 50000
        assert ohlcv.high == 52000

    def test_invalid_ohlcv_high_below_open(self):
        """비정상: 고가 < 시가"""
        with pytest.raises(ValidationError) as exc_info:
            OHLCVData(
                date="2024-01-15",
                open=50000,
                high=49000,  # 고가가 시가보다 낮음
                low=48000,
                close=49500,
                volume=1000000
            )
        assert "고가" in str(exc_info.value)

    def test_invalid_ohlcv_low_above_close(self):
        """비정상: 저가 > 종가"""
        with pytest.raises(ValidationError) as exc_info:
            OHLCVData(
                date="2024-01-15",
                open=50000,
                high=52000,
                low=51500,  # 저가가 종가보다 높음
                close=51000,
                volume=1000000
            )
        assert "저가" in str(exc_info.value)

    def test_invalid_ohlcv_high_below_low(self):
        """비정상: 고가 < 저가"""
        with pytest.raises(ValidationError) as exc_info:
            OHLCVData(
                date="2024-01-15",
                open=50000,
                high=49000,  # 고가가 저가보다 낮음
                low=51000,
                close=50000,
                volume=1000000
            )
        error_str = str(exc_info.value)
        # 고가는 시가/종가보다 크거나 같아야 한다는 에러가 먼저 발생할 수 있음
        assert "고가" in error_str

    def test_valid_ohlcv_boundary(self):
        """정상: 시가 = 고가 = 저가 = 종가 (변동 없음)"""
        ohlcv = OHLCVData(
            date="2024-01-15",
            open=50000,
            high=50000,
            low=50000,
            close=50000,
            volume=0
        )
        assert ohlcv.high == ohlcv.low == ohlcv.open == ohlcv.close


class TestOrderRequest:
    """OrderRequest 모델 테스트 (주문 요청 검증)"""

    def test_valid_limit_buy_order(self):
        """정상: 지정가 매수 주문"""
        order = OrderRequest(
            stock_code="005930",
            quantity=10,
            price=60000,
            order_type=OrderType.LIMIT,
            order_side=OrderSide.BUY
        )
        assert order.stock_code == "005930"
        assert order.order_type == OrderType.LIMIT
        assert order.price == 60000

    def test_valid_market_sell_order(self):
        """정상: 시장가 매도 주문 (가격 없음)"""
        order = OrderRequest(
            stock_code="005930",
            quantity=10,
            price=None,
            order_type=OrderType.MARKET,
            order_side=OrderSide.SELL
        )
        assert order.price is None
        assert order.order_type == OrderType.MARKET

    def test_invalid_order_limit_without_price(self):
        """비정상: 지정가 주문에 가격 없음"""
        with pytest.raises(ValidationError) as exc_info:
            OrderRequest(
                stock_code="005930",
                quantity=10,
                price=None,  # 지정가인데 가격 없음
                order_type=OrderType.LIMIT,
                order_side=OrderSide.BUY
            )
        assert "가격이 필요합니다" in str(exc_info.value)

    def test_invalid_order_quantity_zero(self):
        """비정상: 수량 0"""
        with pytest.raises(ValidationError):
            OrderRequest(
                stock_code="005930",
                quantity=0,
                price=60000,
                order_type=OrderType.LIMIT,
                order_side=OrderSide.BUY
            )

    def test_invalid_order_quantity_over_limit(self):
        """비정상: 수량 100,000 초과"""
        with pytest.raises(ValidationError):
            OrderRequest(
                stock_code="005930",
                quantity=100001,
                price=60000,
                order_type=OrderType.LIMIT,
                order_side=OrderSide.BUY
            )

    def test_invalid_order_stock_code(self):
        """비정상: 잘못된 종목코드"""
        with pytest.raises(ValidationError) as exc_info:
            OrderRequest(
                stock_code="INVALID",
                quantity=10,
                price=60000,
                order_type=OrderType.LIMIT,
                order_side=OrderSide.BUY
            )
        error_str = str(exc_info.value)
        # 길이 검증 또는 형식 검증 에러
        assert "종목코드" in error_str or "at most 6 characters" in error_str or "stock_code" in error_str


class TestPositionData:
    """PositionData 모델 테스트 (포지션 데이터 검증)"""

    def test_valid_position_profit_auto_calculate(self):
        """정상: 수익률/수익금 자동 계산"""
        position = PositionData(
            stock_code="005930",
            stock_name="삼성전자",
            quantity=10,
            avg_price=60000,
            current_price=66000
        )
        # 수익률: (66000 - 60000) / 60000 * 100 = 10.0%
        # 수익금: (66000 - 60000) * 10 = 60000원
        assert position.profit_rate == 10.0
        assert position.profit_amount == 60000

    def test_valid_position_loss_auto_calculate(self):
        """정상: 손실 자동 계산"""
        position = PositionData(
            stock_code="005930",
            stock_name="삼성전자",
            quantity=10,
            avg_price=60000,
            current_price=54000
        )
        # 수익률: (54000 - 60000) / 60000 * 100 = -10.0%
        # 수익금: (54000 - 60000) * 10 = -60000원
        assert position.profit_rate == -10.0
        assert position.profit_amount == -60000


class TestValidatorHelpers:
    """편의 함수 테스트"""

    def test_validate_stock_code_valid(self):
        """정상: 유효한 종목코드"""
        assert validate_stock_code("005930") is True
        assert validate_stock_code("000660") is True

    def test_validate_stock_code_invalid(self):
        """비정상: 잘못된 종목코드"""
        assert validate_stock_code("INVALID") is False
        assert validate_stock_code("12345") is False
        assert validate_stock_code("") is False

    def test_validate_price_valid(self):
        """정상: 유효한 가격"""
        assert validate_price(50000, 2.5) is True
        assert validate_price(1000, -5.0) is True

    def test_validate_price_invalid(self):
        """비정상: 잘못된 가격"""
        assert validate_price(-1000, 0.0) is False  # 음수 가격
        assert validate_price(50000, 35.0) is False  # 등락률 초과

    def test_create_order_request_valid(self):
        """정상: 주문 요청 생성"""
        order = create_order_request(
            stock_code="005930",
            quantity=10,
            side="buy",
            order_type="limit",
            price=60000
        )
        assert order.stock_code == "005930"
        assert order.order_side == OrderSide.BUY
        assert order.order_type == OrderType.LIMIT

    def test_create_order_request_invalid(self):
        """비정상: 잘못된 주문 요청"""
        with pytest.raises(ValidationError):
            create_order_request(
                stock_code="INVALID",
                quantity=10,
                side="buy",
                order_type="limit",
                price=60000
            )


class TestParseOHLCVList:
    """parse_ohlcv_list 함수 테스트 (MF-2 수정 검증)"""

    def test_parse_valid_ohlcv_list(self):
        """정상: 유효한 OHLCV 리스트 파싱"""
        data_list = [
            {
                "date": "2024-01-15",
                "open": 50000,
                "high": 52000,
                "low": 49000,
                "close": 51000,
                "volume": 1000000
            },
            {
                "date": "2024-01-16",
                "open": 51000,
                "high": 53000,
                "low": 50000,
                "close": 52000,
                "volume": 1500000
            }
        ]
        result = parse_ohlcv_list(data_list)
        assert len(result) == 2
        assert result[0].close == 51000
        assert result[1].close == 52000

    def test_parse_empty_list(self):
        """정상: 빈 리스트"""
        result = parse_ohlcv_list([])
        assert result == []

    def test_parse_with_invalid_data(self, caplog):
        """비정상: 일부 무효한 데이터 (로그 기록 확인)"""
        data_list = [
            {
                "date": "2024-01-15",
                "open": 50000,
                "high": 52000,
                "low": 49000,
                "close": 51000,
                "volume": 1000000
            },
            {
                "date": "2024-01-16",
                "open": 50000,
                "high": 49000,  # 고가 < 시가 (무효)
                "low": 48000,
                "close": 49500,
                "volume": 1000000
            },
            {
                "date": "2024-01-17",
                "open": 51000,
                "high": 53000,
                "low": 50000,
                "close": 52000,
                "volume": 1500000
            }
        ]

        result = parse_ohlcv_list(data_list)

        # 유효한 데이터만 반환 (1번째, 3번째)
        assert len(result) == 2
        assert result[0].close == 51000
        assert result[1].close == 52000

        # 에러 로그 기록 확인 (MF-2 수정 검증)
        assert "OHLCV 파싱 실패" in caplog.text

    def test_parse_all_invalid_data(self, caplog):
        """비정상: 모든 데이터 무효 (빈 리스트 반환 + 로그)"""
        data_list = [
            {
                "date": "2024-01-15",
                "open": 50000,
                "high": 49000,  # 고가 < 시가 (무효)
                "low": 48000,
                "close": 49500,
                "volume": 1000000
            },
            {
                "date": "2024-01-16",
                "open": -1000,  # 음수 (무효)
                "high": 52000,
                "low": 49000,
                "close": 51000,
                "volume": 1000000
            }
        ]

        result = parse_ohlcv_list(data_list)

        # 빈 리스트 반환
        assert result == []

        # 2개 에러 로그 기록 확인
        assert caplog.text.count("OHLCV 파싱 실패") == 2

    def test_parse_missing_fields(self, caplog):
        """비정상: 필수 필드 누락 (로그 기록 확인)"""
        data_list = [
            {
                "date": "2024-01-15",
                "open": 50000,
                # high 필드 누락
                "low": 49000,
                "close": 51000,
                "volume": 1000000
            }
        ]

        result = parse_ohlcv_list(data_list)

        # 빈 리스트 반환
        assert result == []

        # 에러 로그 기록 확인
        assert "OHLCV 파싱 실패" in caplog.text
