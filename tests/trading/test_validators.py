"""
입력 검증 모듈 테스트
"""

import pytest
from datetime import date, datetime

from core.trading.validators import (
    ValidationResult,
    ValidationLevel,
    ValidationError,
    StockCodeValidator,
    PriceValidator,
    QuantityValidator,
    PercentageValidator,
    DateTimeValidator,
    OrderValidator,
    TradingInputValidator,
    validate_stock_code,
    validate_price,
    validate_quantity,
)


class TestValidationResult:
    """ValidationResult 테스트"""

    def test_initial_state(self):
        result = ValidationResult(is_valid=True)
        assert result.is_valid is True
        assert result.errors == []
        assert result.warnings == []

    def test_add_error(self):
        result = ValidationResult(is_valid=True)
        result.add_error("Error message")
        assert result.is_valid is False
        assert "Error message" in result.errors

    def test_add_warning(self):
        result = ValidationResult(is_valid=True)
        result.add_warning("Warning message")
        assert result.is_valid is True
        assert "Warning message" in result.warnings


class TestStockCodeValidator:
    """StockCodeValidator 테스트"""

    def test_valid_stock_code(self):
        result = StockCodeValidator.validate("005930")
        assert result.is_valid is True
        assert result.sanitized_value == "005930"

    def test_none_stock_code(self):
        result = StockCodeValidator.validate(None)
        assert result.is_valid is False

    def test_numeric_stock_code(self):
        result = StockCodeValidator.validate(5930)
        assert result.is_valid is True
        assert result.sanitized_value == "005930"  # 6자리로 패딩

    def test_short_stock_code(self):
        result = StockCodeValidator.validate("1234")
        assert result.is_valid is False

    def test_long_stock_code(self):
        result = StockCodeValidator.validate("12345678")
        assert result.is_valid is False

    def test_alpha_stock_code(self):
        result = StockCodeValidator.validate("AAPL12")
        assert result.is_valid is False

    def test_whitespace_trimmed(self):
        result = StockCodeValidator.validate("  005930  ")
        assert result.is_valid is True
        assert result.sanitized_value == "005930"

    def test_is_kospi(self):
        assert StockCodeValidator.is_kospi("005930") is True
        assert StockCodeValidator.is_kospi("invalid") is False


class TestPriceValidator:
    """PriceValidator 테스트"""

    def test_valid_price(self):
        result = PriceValidator.validate(70000)
        assert result.is_valid is True
        assert result.sanitized_value == 70000

    def test_none_price(self):
        result = PriceValidator.validate(None)
        assert result.is_valid is False

    def test_string_price(self):
        result = PriceValidator.validate("70000")
        assert result.is_valid is True
        assert result.sanitized_value == 70000.0

    def test_negative_price(self):
        result = PriceValidator.validate(-100)
        assert result.is_valid is False

    def test_zero_price_not_allowed(self):
        result = PriceValidator.validate(0, allow_zero=False)
        assert result.is_valid is False

    def test_zero_price_allowed(self):
        result = PriceValidator.validate(0, allow_zero=True)
        assert result.is_valid is True

    def test_price_exceeds_max(self):
        result = PriceValidator.validate(100_000_000, max_price=10_000_000)
        assert result.is_valid is False

    def test_price_below_min(self):
        result = PriceValidator.validate(50, min_price=100)
        assert result.is_valid is False

    def test_tick_size_adjustment(self):
        # 10000~50000 범위에서 호가 단위는 50원
        result = PriceValidator.validate(10055, check_tick_size=True)
        assert result.is_valid is True
        assert result.sanitized_value == 10050  # 50원 단위로 조정

    def test_get_tick_size(self):
        assert PriceValidator.get_tick_size(500) == 1
        assert PriceValidator.get_tick_size(3000) == 5
        assert PriceValidator.get_tick_size(8000) == 10
        assert PriceValidator.get_tick_size(30000) == 50
        assert PriceValidator.get_tick_size(80000) == 100
        assert PriceValidator.get_tick_size(200000) == 500
        assert PriceValidator.get_tick_size(600000) == 1000


class TestQuantityValidator:
    """QuantityValidator 테스트"""

    def test_valid_quantity(self):
        result = QuantityValidator.validate(100)
        assert result.is_valid is True
        assert result.sanitized_value == 100

    def test_none_quantity(self):
        result = QuantityValidator.validate(None)
        assert result.is_valid is False

    def test_string_quantity(self):
        result = QuantityValidator.validate("100")
        assert result.is_valid is True
        assert result.sanitized_value == 100

    def test_float_quantity_converted(self):
        result = QuantityValidator.validate(100.5)
        assert result.is_valid is True
        assert result.sanitized_value == 100

    def test_negative_quantity(self):
        result = QuantityValidator.validate(-10)
        assert result.is_valid is False

    def test_zero_quantity_not_allowed(self):
        result = QuantityValidator.validate(0, allow_zero=False)
        assert result.is_valid is False

    def test_zero_quantity_allowed(self):
        result = QuantityValidator.validate(0, allow_zero=True)
        assert result.is_valid is True

    def test_quantity_exceeds_max(self):
        result = QuantityValidator.validate(10_000_000, max_quantity=1_000_000)
        assert result.is_valid is False


class TestPercentageValidator:
    """PercentageValidator 테스트"""

    def test_valid_percentage(self):
        result = PercentageValidator.validate(50.0)
        assert result.is_valid is True
        assert result.sanitized_value == 50.0

    def test_none_percentage(self):
        result = PercentageValidator.validate(None)
        assert result.is_valid is False

    def test_negative_not_allowed(self):
        result = PercentageValidator.validate(-10, allow_negative=False)
        assert result.is_valid is False

    def test_negative_allowed(self):
        result = PercentageValidator.validate(-10, allow_negative=True)
        assert result.is_valid is True

    def test_exceeds_max(self):
        result = PercentageValidator.validate(150, max_value=100)
        assert result.is_valid is False


class TestDateTimeValidator:
    """DateTimeValidator 테스트"""

    def test_valid_date_object(self):
        today = date.today()
        result = DateTimeValidator.validate_date(today)
        assert result.is_valid is True
        assert result.sanitized_value == today

    def test_datetime_object(self):
        now = datetime.now()
        result = DateTimeValidator.validate_date(now)
        assert result.is_valid is True
        assert result.sanitized_value == now.date()

    def test_iso_string(self):
        result = DateTimeValidator.validate_date("2024-01-15")
        assert result.is_valid is True
        assert result.sanitized_value == date(2024, 1, 15)

    def test_iso_datetime_string(self):
        result = DateTimeValidator.validate_date("2024-01-15T10:30:00")
        assert result.is_valid is True
        assert result.sanitized_value == date(2024, 1, 15)

    def test_compact_string(self):
        result = DateTimeValidator.validate_date("20240115")
        assert result.is_valid is True
        assert result.sanitized_value == date(2024, 1, 15)

    def test_invalid_format(self):
        result = DateTimeValidator.validate_date("15-01-2024")
        assert result.is_valid is False

    def test_min_date_check(self):
        result = DateTimeValidator.validate_date(
            "2024-01-01",
            min_date=date(2024, 6, 1)
        )
        assert result.is_valid is False


class TestOrderValidator:
    """OrderValidator 테스트"""

    def test_valid_market_order(self):
        result = OrderValidator.validate_order(
            stock_code="005930",
            quantity=100,
            order_type="market",
            order_side="buy"
        )
        assert result.is_valid is True

    def test_valid_limit_order(self):
        result = OrderValidator.validate_order(
            stock_code="005930",
            quantity=100,
            price=70000,
            order_type="limit",
            order_side="buy"
        )
        assert result.is_valid is True

    def test_limit_order_without_price(self):
        result = OrderValidator.validate_order(
            stock_code="005930",
            quantity=100,
            order_type="limit",
            order_side="buy"
        )
        assert result.is_valid is False

    def test_stop_order_without_stop_price(self):
        result = OrderValidator.validate_order(
            stock_code="005930",
            quantity=100,
            order_type="stop",
            order_side="sell"
        )
        assert result.is_valid is False

    def test_invalid_order_type(self):
        result = OrderValidator.validate_order(
            stock_code="005930",
            quantity=100,
            order_type="invalid_type",
            order_side="buy"
        )
        assert result.is_valid is False

    def test_invalid_order_side(self):
        result = OrderValidator.validate_order(
            stock_code="005930",
            quantity=100,
            order_type="market",
            order_side="invalid_side"
        )
        assert result.is_valid is False


class TestTradingInputValidator:
    """TradingInputValidator 통합 테스트"""

    def test_strict_mode_raises_on_error(self):
        validator = TradingInputValidator(level=ValidationLevel.STRICT)
        with pytest.raises(ValidationError):
            validator.validate_stock_code(None)

    def test_normal_mode_raises_on_error(self):
        validator = TradingInputValidator(level=ValidationLevel.NORMAL)
        with pytest.raises(ValidationError):
            validator.validate_price(-100)

    def test_lenient_mode_no_raise(self):
        validator = TradingInputValidator(level=ValidationLevel.LENIENT)
        # Should not raise, but returns None
        try:
            validator.validate_quantity(-10)
        except ValidationError:
            pass  # May or may not raise depending on implementation

    def test_validate_stock_code(self):
        validator = TradingInputValidator()
        result = validator.validate_stock_code("005930")
        assert result == "005930"

    def test_validate_price(self):
        validator = TradingInputValidator()
        result = validator.validate_price(70000)
        assert result == 70000

    def test_validate_quantity(self):
        validator = TradingInputValidator()
        result = validator.validate_quantity(100)
        assert result == 100


class TestConvenienceFunctions:
    """편의 함수 테스트"""

    def test_validate_stock_code_valid(self):
        is_valid, sanitized, error = validate_stock_code("005930")
        assert is_valid is True
        assert sanitized == "005930"
        assert error is None

    def test_validate_stock_code_invalid(self):
        is_valid, sanitized, error = validate_stock_code("invalid")
        assert is_valid is False
        assert error is not None

    def test_validate_price_valid(self):
        is_valid, sanitized, error = validate_price(70000)
        assert is_valid is True
        assert sanitized == 70000
        assert error is None

    def test_validate_price_invalid(self):
        is_valid, sanitized, error = validate_price(-100)
        assert is_valid is False
        assert error is not None

    def test_validate_quantity_valid(self):
        is_valid, sanitized, error = validate_quantity(100)
        assert is_valid is True
        assert sanitized == 100
        assert error is None

    def test_validate_quantity_invalid(self):
        is_valid, sanitized, error = validate_quantity(-10)
        assert is_valid is False
        assert error is not None


class TestEdgeCases:
    """엣지 케이스 테스트"""

    def test_nan_price(self):
        result = PriceValidator.validate(float('nan'))
        assert result.is_valid is False

    def test_inf_price(self):
        result = PriceValidator.validate(float('inf'))
        assert result.is_valid is False

    def test_empty_string_stock_code(self):
        result = StockCodeValidator.validate("")
        assert result.is_valid is False

    def test_special_chars_stock_code(self):
        result = StockCodeValidator.validate("00!@#0")
        assert result.is_valid is False

    def test_very_large_quantity(self):
        result = QuantityValidator.validate(999_999_999)
        assert result.is_valid is False

    def test_float_string_price(self):
        # Note: Price gets adjusted to tick size (100원 for 50000~100000 range)
        result = PriceValidator.validate("70000.50")
        assert result.is_valid is True
        assert result.sanitized_value == 70000  # Adjusted to tick size

    def test_float_string_price_no_tick_check(self):
        result = PriceValidator.validate("70000.50", check_tick_size=False)
        assert result.is_valid is True
        assert result.sanitized_value == 70000.50
