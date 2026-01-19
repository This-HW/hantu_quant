"""
입력 검증 모듈

거래 시스템의 입력값을 검증하고 정화합니다.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import List, Optional, Any, Tuple
from enum import Enum

from core.utils import get_logger

logger = get_logger(__name__)


class ValidationError(Exception):
    """검증 오류"""
    def __init__(self, message: str, field: Optional[str] = None, value: Any = None):
        super().__init__(message)
        self.field = field
        self.value = value


class ValidationLevel(Enum):
    """검증 수준"""
    STRICT = "strict"       # 엄격 모드 - 모든 오류 발생
    NORMAL = "normal"       # 일반 모드 - 치명적 오류만 발생
    LENIENT = "lenient"     # 관대 모드 - 경고만 발생


@dataclass
class ValidationResult:
    """검증 결과"""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    sanitized_value: Any = None

    def add_error(self, message: str):
        self.errors.append(message)
        self.is_valid = False

    def add_warning(self, message: str):
        self.warnings.append(message)


class StockCodeValidator:
    """종목 코드 검증기"""

    # 한국 종목 코드 패턴
    KOSPI_PATTERN = re.compile(r'^[0-9]{6}$')  # 6자리 숫자
    KOSDAQ_PATTERN = re.compile(r'^[0-9]{6}$')  # 6자리 숫자
    ETF_PATTERN = re.compile(r'^[0-9]{6}$')    # 6자리 숫자

    # 종목 코드 범위
    KOSPI_RANGES = [(0, 299999), (300001, 399999), (500000, 599999)]
    KOSDAQ_RANGES = [(400000, 499999)]
    ETF_RANGES = [(100000, 199999), (200000, 299999), (300000, 399999)]

    @classmethod
    def validate(cls, stock_code: Any) -> ValidationResult:
        """
        종목 코드 검증

        Args:
            stock_code: 종목 코드

        Returns:
            ValidationResult: 검증 결과
        """
        result = ValidationResult(is_valid=True)

        # 타입 체크
        if stock_code is None:
            result.add_error("종목 코드가 None입니다")
            return result

        if not isinstance(stock_code, str):
            try:
                stock_code = str(stock_code).zfill(6)
                result.add_warning(f"종목 코드가 문자열로 변환되었습니다: {stock_code}")
            except Exception:
                result.add_error("종목 코드를 문자열로 변환할 수 없습니다")
                return result

        # 공백 제거
        stock_code = stock_code.strip()

        # 길이 체크
        if len(stock_code) != 6:
            result.add_error(f"종목 코드는 6자리여야 합니다 (입력: {len(stock_code)}자리)")
            return result

        # 패턴 체크
        if not cls.KOSPI_PATTERN.match(stock_code):
            result.add_error(f"올바른 종목 코드 형식이 아닙니다: {stock_code}")
            return result

        # 숫자 범위 체크
        try:
            code_num = int(stock_code)
            if code_num <= 0:
                result.add_error("종목 코드는 양수여야 합니다")
                return result
        except ValueError:
            result.add_error("종목 코드가 숫자가 아닙니다")
            return result

        result.sanitized_value = stock_code
        return result

    @classmethod
    def is_kospi(cls, stock_code: str) -> bool:
        """KOSPI 종목 여부"""
        try:
            code_num = int(stock_code)
            return any(start <= code_num <= end for start, end in cls.KOSPI_RANGES)
        except ValueError:
            return False

    @classmethod
    def is_kosdaq(cls, stock_code: str) -> bool:
        """KOSDAQ 종목 여부"""
        try:
            code_num = int(stock_code)
            return any(start <= code_num <= end for start, end in cls.KOSDAQ_RANGES)
        except ValueError:
            return False


class PriceValidator:
    """가격 검증기"""

    # 한국 주식 가격 단위 (호가 단위)
    PRICE_UNITS = [
        (0, 1000, 1),
        (1000, 5000, 5),
        (5000, 10000, 10),
        (10000, 50000, 50),
        (50000, 100000, 100),
        (100000, 500000, 500),
        (500000, float('inf'), 1000),
    ]

    @classmethod
    def validate(
        cls,
        price: Any,
        min_price: float = 0,
        max_price: float = 10_000_000,
        allow_zero: bool = False,
        check_tick_size: bool = True
    ) -> ValidationResult:
        """
        가격 검증

        Args:
            price: 가격
            min_price: 최소 가격
            max_price: 최대 가격
            allow_zero: 0 허용 여부
            check_tick_size: 호가 단위 검사 여부

        Returns:
            ValidationResult: 검증 결과
        """
        result = ValidationResult(is_valid=True)

        # 타입 체크
        if price is None:
            result.add_error("가격이 None입니다")
            return result

        try:
            price = float(price)
        except (TypeError, ValueError):
            result.add_error(f"가격을 숫자로 변환할 수 없습니다: {price}")
            return result

        # NaN/Inf 체크
        if price != price or price == float('inf') or price == float('-inf'):
            result.add_error("가격이 유효하지 않은 값입니다 (NaN 또는 무한대)")
            return result

        # 음수 체크
        if price < 0:
            result.add_error(f"가격은 음수일 수 없습니다: {price}")
            return result

        # 0 체크
        if price == 0 and not allow_zero:
            result.add_error("가격은 0일 수 없습니다")
            return result

        # 범위 체크
        if price < min_price:
            result.add_error(f"가격이 최소값({min_price})보다 작습니다: {price}")
            return result

        if price > max_price:
            result.add_error(f"가격이 최대값({max_price})보다 큽니다: {price}")
            return result

        # 호가 단위 검사
        if check_tick_size and price > 0:
            tick_size = cls.get_tick_size(price)
            if price % tick_size != 0:
                # 가장 가까운 호가 단위로 조정
                adjusted = round(price / tick_size) * tick_size
                result.add_warning(
                    f"가격이 호가 단위에 맞지 않아 조정되었습니다: {price} -> {adjusted}"
                )
                price = adjusted

        result.sanitized_value = price
        return result

    @classmethod
    def get_tick_size(cls, price: float) -> int:
        """가격에 대한 호가 단위 반환"""
        for low, high, tick in cls.PRICE_UNITS:
            if low <= price < high:
                return tick
        return 1000

    @classmethod
    def adjust_to_tick(cls, price: float) -> float:
        """호가 단위로 조정"""
        tick_size = cls.get_tick_size(price)
        return round(price / tick_size) * tick_size


class QuantityValidator:
    """수량 검증기"""

    @classmethod
    def validate(
        cls,
        quantity: Any,
        min_quantity: int = 1,
        max_quantity: int = 1_000_000,
        allow_zero: bool = False
    ) -> ValidationResult:
        """
        수량 검증

        Args:
            quantity: 수량
            min_quantity: 최소 수량
            max_quantity: 최대 수량
            allow_zero: 0 허용 여부

        Returns:
            ValidationResult: 검증 결과
        """
        result = ValidationResult(is_valid=True)

        # 타입 체크
        if quantity is None:
            result.add_error("수량이 None입니다")
            return result

        try:
            quantity = int(quantity)
        except (TypeError, ValueError):
            result.add_error(f"수량을 정수로 변환할 수 없습니다: {quantity}")
            return result

        # 음수 체크
        if quantity < 0:
            result.add_error(f"수량은 음수일 수 없습니다: {quantity}")
            return result

        # 0 체크
        if quantity == 0:
            if not allow_zero:
                result.add_error("수량은 0일 수 없습니다")
                return result
            # allow_zero=True면 0은 유효
            result.sanitized_value = quantity
            return result

        # 범위 체크 (0이 아닌 경우에만)
        if quantity < min_quantity:
            result.add_error(f"수량이 최소값({min_quantity})보다 작습니다: {quantity}")
            return result

        if quantity > max_quantity:
            result.add_error(f"수량이 최대값({max_quantity})보다 큽니다: {quantity}")
            return result

        result.sanitized_value = quantity
        return result


class PercentageValidator:
    """퍼센트 검증기"""

    @classmethod
    def validate(
        cls,
        value: Any,
        min_value: float = 0.0,
        max_value: float = 100.0,
        allow_negative: bool = False
    ) -> ValidationResult:
        """
        퍼센트 값 검증

        Args:
            value: 퍼센트 값
            min_value: 최소값
            max_value: 최대값
            allow_negative: 음수 허용 여부

        Returns:
            ValidationResult: 검증 결과
        """
        result = ValidationResult(is_valid=True)

        # 타입 체크
        if value is None:
            result.add_error("퍼센트 값이 None입니다")
            return result

        try:
            value = float(value)
        except (TypeError, ValueError):
            result.add_error(f"퍼센트를 숫자로 변환할 수 없습니다: {value}")
            return result

        # NaN/Inf 체크
        if value != value or value == float('inf') or value == float('-inf'):
            result.add_error("퍼센트가 유효하지 않은 값입니다")
            return result

        # 음수 체크
        if value < 0 and not allow_negative:
            result.add_error(f"퍼센트는 음수일 수 없습니다: {value}")
            return result

        # 범위 체크 (음수 허용 시 음수에 대해서는 min_value 체크 생략)
        if value >= 0 and value < min_value:
            result.add_error(f"퍼센트가 최소값({min_value})보다 작습니다: {value}")
            return result

        if value > max_value:
            result.add_error(f"퍼센트가 최대값({max_value})보다 큽니다: {value}")
            return result

        result.sanitized_value = value
        return result


class DateTimeValidator:
    """날짜/시간 검증기"""

    @classmethod
    def validate_date(
        cls,
        value: Any,
        min_date: Optional[date] = None,
        max_date: Optional[date] = None
    ) -> ValidationResult:
        """
        날짜 검증

        Args:
            value: 날짜 값
            min_date: 최소 날짜
            max_date: 최대 날짜

        Returns:
            ValidationResult: 검증 결과
        """
        result = ValidationResult(is_valid=True)

        # 타입 체크
        if value is None:
            result.add_error("날짜가 None입니다")
            return result

        if isinstance(value, datetime):
            value = value.date()
        elif isinstance(value, str):
            try:
                # ISO 형식 또는 일반 형식 파싱
                if 'T' in value:
                    value = datetime.fromisoformat(value).date()
                else:
                    for fmt in ['%Y-%m-%d', '%Y%m%d', '%Y/%m/%d']:
                        try:
                            value = datetime.strptime(value, fmt).date()
                            break
                        except ValueError:
                            continue
                    else:
                        raise ValueError("지원하지 않는 날짜 형식")
            except ValueError as e:
                result.add_error(f"날짜를 파싱할 수 없습니다: {value} ({str(e)})")
                return result
        elif not isinstance(value, date):
            result.add_error(f"지원하지 않는 날짜 타입입니다: {type(value)}")
            return result

        # 범위 체크
        if min_date and value < min_date:
            result.add_error(f"날짜가 최소값({min_date})보다 이전입니다: {value}")
            return result

        if max_date and value > max_date:
            result.add_error(f"날짜가 최대값({max_date})보다 이후입니다: {value}")
            return result

        result.sanitized_value = value
        return result


class OrderValidator:
    """주문 검증기"""

    VALID_ORDER_TYPES = ['market', 'limit', 'stop', 'stop_limit']
    VALID_ORDER_SIDES = ['buy', 'sell']

    @classmethod
    def validate_order(
        cls,
        stock_code: str,
        quantity: int,
        price: Optional[float] = None,
        order_type: str = 'market',
        order_side: str = 'buy',
        stop_price: Optional[float] = None,
    ) -> ValidationResult:
        """
        주문 검증

        Args:
            stock_code: 종목 코드
            quantity: 수량
            price: 가격 (지정가 주문 시)
            order_type: 주문 유형
            order_side: 주문 방향
            stop_price: 스탑 가격

        Returns:
            ValidationResult: 검증 결과
        """
        result = ValidationResult(is_valid=True)

        # 종목 코드 검증
        code_result = StockCodeValidator.validate(stock_code)
        if not code_result.is_valid:
            result.errors.extend(code_result.errors)
            result.is_valid = False
        result.warnings.extend(code_result.warnings)

        # 수량 검증
        qty_result = QuantityValidator.validate(quantity)
        if not qty_result.is_valid:
            result.errors.extend(qty_result.errors)
            result.is_valid = False
        result.warnings.extend(qty_result.warnings)

        # 주문 유형 검증
        order_type_lower = order_type.lower() if isinstance(order_type, str) else ''
        if order_type_lower not in cls.VALID_ORDER_TYPES:
            result.add_error(
                f"올바른 주문 유형이 아닙니다: {order_type} "
                f"(허용: {cls.VALID_ORDER_TYPES})"
            )

        # 주문 방향 검증
        order_side_lower = order_side.lower() if isinstance(order_side, str) else ''
        if order_side_lower not in cls.VALID_ORDER_SIDES:
            result.add_error(
                f"올바른 주문 방향이 아닙니다: {order_side} "
                f"(허용: {cls.VALID_ORDER_SIDES})"
            )

        # 지정가 주문 시 가격 필수
        if order_type_lower in ['limit', 'stop_limit'] and price is None:
            result.add_error("지정가 주문에는 가격이 필요합니다")
        elif price is not None:
            price_result = PriceValidator.validate(price)
            if not price_result.is_valid:
                result.errors.extend(price_result.errors)
                result.is_valid = False
            result.warnings.extend(price_result.warnings)

        # 스탑 주문 시 스탑 가격 필수
        if order_type_lower in ['stop', 'stop_limit'] and stop_price is None:
            result.add_error("스탑 주문에는 스탑 가격이 필요합니다")
        elif stop_price is not None:
            stop_result = PriceValidator.validate(stop_price)
            if not stop_result.is_valid:
                result.errors.extend(stop_result.errors)
                result.is_valid = False
            result.warnings.extend(stop_result.warnings)

        return result


class TradingInputValidator:
    """
    거래 입력 검증기 (통합)

    모든 거래 관련 입력을 검증하는 통합 인터페이스입니다.
    """

    def __init__(self, level: ValidationLevel = ValidationLevel.NORMAL):
        """
        Args:
            level: 검증 수준
        """
        self.level = level

    def validate_stock_code(self, stock_code: Any) -> str:
        """종목 코드 검증 및 정화"""
        result = StockCodeValidator.validate(stock_code)
        self._handle_result(result, "종목 코드")
        return result.sanitized_value

    def validate_price(
        self,
        price: Any,
        allow_zero: bool = False,
        check_tick_size: bool = True
    ) -> float:
        """가격 검증 및 정화"""
        result = PriceValidator.validate(
            price,
            allow_zero=allow_zero,
            check_tick_size=check_tick_size
        )
        self._handle_result(result, "가격")
        return result.sanitized_value

    def validate_quantity(
        self,
        quantity: Any,
        allow_zero: bool = False
    ) -> int:
        """수량 검증 및 정화"""
        result = QuantityValidator.validate(quantity, allow_zero=allow_zero)
        self._handle_result(result, "수량")
        return result.sanitized_value

    def validate_percentage(
        self,
        value: Any,
        min_value: float = 0.0,
        max_value: float = 100.0,
        allow_negative: bool = False
    ) -> float:
        """퍼센트 검증 및 정화"""
        result = PercentageValidator.validate(
            value,
            min_value=min_value,
            max_value=max_value,
            allow_negative=allow_negative
        )
        self._handle_result(result, "퍼센트")
        return result.sanitized_value

    def validate_order(
        self,
        stock_code: str,
        quantity: int,
        price: Optional[float] = None,
        order_type: str = 'market',
        order_side: str = 'buy',
        stop_price: Optional[float] = None,
    ) -> ValidationResult:
        """주문 검증"""
        result = OrderValidator.validate_order(
            stock_code=stock_code,
            quantity=quantity,
            price=price,
            order_type=order_type,
            order_side=order_side,
            stop_price=stop_price,
        )
        self._handle_result(result, "주문")
        return result

    def _handle_result(self, result: ValidationResult, context: str):
        """검증 결과 처리"""
        # 경고 로깅
        for warning in result.warnings:
            logger.warning(f"[{context}] {warning}")

        # 오류 처리
        if not result.is_valid:
            error_msg = f"[{context}] 검증 실패: " + "; ".join(result.errors)

            if self.level == ValidationLevel.STRICT:
                raise ValidationError(error_msg)
            elif self.level == ValidationLevel.NORMAL:
                logger.error(error_msg)
                raise ValidationError(error_msg)
            else:  # LENIENT
                logger.warning(error_msg)


# 편의 함수
def validate_stock_code(stock_code: Any) -> Tuple[bool, str, Optional[str]]:
    """
    종목 코드 검증

    Returns:
        (is_valid, sanitized_value, error_message)
    """
    result = StockCodeValidator.validate(stock_code)
    error = result.errors[0] if result.errors else None
    return result.is_valid, result.sanitized_value, error


def validate_price(price: Any, check_tick_size: bool = True) -> Tuple[bool, float, Optional[str]]:
    """
    가격 검증

    Returns:
        (is_valid, sanitized_value, error_message)
    """
    result = PriceValidator.validate(price, check_tick_size=check_tick_size)
    error = result.errors[0] if result.errors else None
    return result.is_valid, result.sanitized_value, error


def validate_quantity(quantity: Any) -> Tuple[bool, int, Optional[str]]:
    """
    수량 검증

    Returns:
        (is_valid, sanitized_value, error_message)
    """
    result = QuantityValidator.validate(quantity)
    error = result.errors[0] if result.errors else None
    return result.is_valid, result.sanitized_value, error
