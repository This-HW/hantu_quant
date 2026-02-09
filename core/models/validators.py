# -*- coding: utf-8 -*-
"""
Pydantic 데이터 검증 모델 (P2-1)

기능:
- 종목코드 형식 검증 (6자리 숫자)
- 가격/수량 유효성 검증 (양수, 범위)
- 주문 요청 검증
- API 응답 데이터 검증

잘못된 입력으로 인한 런타임 에러 방지
"""

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, Literal, List
from datetime import datetime
from enum import Enum
import re
from core.utils.log_utils import get_logger

logger = get_logger(__name__)


class OrderType(str, Enum):
    """주문 유형"""
    MARKET = "market"       # 시장가
    LIMIT = "limit"         # 지정가
    CONDITION = "condition" # 조건부


class OrderSide(str, Enum):
    """매매 방향"""
    BUY = "buy"
    SELL = "sell"


class StockCode(BaseModel):
    """종목코드 검증 모델

    한국 주식시장 종목코드는 6자리 숫자
    예: 005930 (삼성전자), 000660 (SK하이닉스)
    """
    code: str = Field(..., min_length=6, max_length=6, description="종목코드 (6자리)")

    @field_validator('code')
    @classmethod
    def validate_code(cls, v: str) -> str:
        """종목코드 형식 검증"""
        if not re.match(r'^\d{6}$', v):
            raise ValueError(f'종목코드 형식 오류: {v} (6자리 숫자 필요)')
        return v

    def __str__(self) -> str:
        return self.code


class PriceData(BaseModel):
    """가격 데이터 검증 모델

    가격은 양수, 등락률은 ±30% 범위
    """
    current_price: int = Field(..., gt=0, description="현재가 (원)")
    change: int = Field(default=0, description="전일 대비 변동 (원)")
    change_rate: float = Field(default=0.0, ge=-30.0, le=30.0, description="등락률 (%)")
    volume: int = Field(default=0, ge=0, description="거래량")
    high: Optional[int] = Field(None, gt=0, description="고가")
    low: Optional[int] = Field(None, gt=0, description="저가")
    open: Optional[int] = Field(None, gt=0, description="시가")

    @model_validator(mode='after')
    def validate_high_low(self):
        """고가 >= 저가 검증"""
        if self.high is not None and self.low is not None:
            if self.high < self.low:
                raise ValueError(f'고가({self.high})가 저가({self.low})보다 작을 수 없습니다')
        return self


class VolumeData(BaseModel):
    """거래량 데이터 검증 모델"""
    volume: int = Field(..., ge=0, description="거래량")
    volume_change_rate: float = Field(default=0.0, description="거래량 변화율 (%)")
    avg_volume_5d: Optional[int] = Field(None, ge=0, description="5일 평균 거래량")
    avg_volume_20d: Optional[int] = Field(None, ge=0, description="20일 평균 거래량")

    @property
    def is_volume_surge(self) -> bool:
        """거래량 급증 여부 (20일 평균 대비 2배 이상)"""
        if self.avg_volume_20d and self.avg_volume_20d > 0:
            return self.volume >= self.avg_volume_20d * 2
        return False


class OHLCVData(BaseModel):
    """OHLCV 데이터 검증 모델

    봉 데이터 (일봉/분봉)
    """
    date: str = Field(..., description="날짜 (YYYY-MM-DD 또는 YYYYMMDD)")
    open: int = Field(..., gt=0, description="시가")
    high: int = Field(..., gt=0, description="고가")
    low: int = Field(..., gt=0, description="저가")
    close: int = Field(..., gt=0, description="종가")
    volume: int = Field(..., ge=0, description="거래량")

    @model_validator(mode='after')
    def validate_ohlc(self):
        """OHLC 관계 검증: high >= open, close, low"""
        if self.high < max(self.open, self.close):
            raise ValueError(f'고가({self.high})는 시가({self.open})와 종가({self.close})보다 크거나 같아야 합니다')
        if self.low > min(self.open, self.close):
            raise ValueError(f'저가({self.low})는 시가({self.open})와 종가({self.close})보다 작거나 같아야 합니다')
        if self.high < self.low:
            raise ValueError(f'고가({self.high})가 저가({self.low})보다 작을 수 없습니다')
        return self


class OrderRequest(BaseModel):
    """주문 요청 검증 모델

    매수/매도 주문 파라미터 검증
    """
    stock_code: str = Field(..., min_length=6, max_length=6, description="종목코드")
    quantity: int = Field(..., gt=0, le=100000, description="주문 수량")
    price: Optional[int] = Field(None, gt=0, le=100_000_000, description="주문 가격 (시장가일 때 None)")
    order_type: OrderType = Field(default=OrderType.LIMIT, description="주문 유형")
    order_side: OrderSide = Field(..., description="매매 방향")

    @field_validator('stock_code')
    @classmethod
    def validate_stock_code(cls, v: str) -> str:
        """종목코드 형식 검증"""
        if not re.match(r'^\d{6}$', v):
            raise ValueError(f'종목코드 형식 오류: {v}')
        return v

    @model_validator(mode='after')
    def validate_price_for_order_type(self):
        """지정가 주문 시 가격 필수"""
        if self.order_type == OrderType.LIMIT and self.price is None:
            raise ValueError('지정가 주문에는 가격이 필요합니다')
        return self


class PositionData(BaseModel):
    """포지션 데이터 검증 모델"""
    stock_code: str = Field(..., min_length=6, max_length=6)
    stock_name: str = Field(default="", description="종목명")
    quantity: int = Field(..., gt=0, description="보유 수량")
    avg_price: int = Field(..., gt=0, description="평균 매수가")
    current_price: int = Field(..., gt=0, description="현재가")
    profit_rate: float = Field(default=0.0, description="수익률 (%)")
    profit_amount: int = Field(default=0, description="평가손익 (원)")

    @field_validator('stock_code')
    @classmethod
    def validate_stock_code(cls, v: str) -> str:
        if not re.match(r'^\d{6}$', v):
            raise ValueError(f'종목코드 형식 오류: {v}')
        return v

    @model_validator(mode='after')
    def calculate_profit(self):
        """수익률/수익금 자동 계산"""
        if self.avg_price > 0:
            expected_rate = (self.current_price - self.avg_price) / self.avg_price * 100
            expected_amount = (self.current_price - self.avg_price) * self.quantity

            # 수익률이 설정되지 않았으면 계산값 사용
            if self.profit_rate == 0.0:
                object.__setattr__(self, 'profit_rate', round(expected_rate, 2))
            if self.profit_amount == 0:
                object.__setattr__(self, 'profit_amount', expected_amount)
        return self


class TradeResult(BaseModel):
    """거래 결과 검증 모델"""
    order_id: str = Field(..., description="주문 ID")
    stock_code: str = Field(..., min_length=6, max_length=6)
    order_side: OrderSide
    order_type: OrderType
    requested_quantity: int = Field(..., gt=0)
    executed_quantity: int = Field(..., ge=0)
    requested_price: Optional[int] = Field(None, gt=0)
    executed_price: Optional[int] = Field(None, gt=0)
    status: Literal["pending", "executed", "partial", "cancelled", "rejected"]
    executed_at: Optional[datetime] = None
    message: str = Field(default="", description="결과 메시지")

    @field_validator('stock_code')
    @classmethod
    def validate_stock_code(cls, v: str) -> str:
        if not re.match(r'^\d{6}$', v):
            raise ValueError(f'종목코드 형식 오류: {v}')
        return v

    @property
    def is_fully_executed(self) -> bool:
        """완전 체결 여부"""
        return self.executed_quantity == self.requested_quantity

    @property
    def fill_rate(self) -> float:
        """체결률 (%)"""
        if self.requested_quantity > 0:
            return self.executed_quantity / self.requested_quantity * 100
        return 0.0


# ========== 편의 함수 ==========

def validate_stock_code(code: str) -> bool:
    """종목코드 유효성 검증

    Args:
        code: 종목코드

    Returns:
        bool: 유효 여부
    """
    try:
        StockCode(code=code)
        return True
    except Exception as e:
        logger.warning(
            f"종목코드 검증 실패: {code}",
            exc_info=False,
            extra={'code': code, 'error': str(e)}
        )
        return False


def validate_price(price: int, change_rate: float = 0.0) -> bool:
    """가격 유효성 검증

    Args:
        price: 가격
        change_rate: 등락률

    Returns:
        bool: 유효 여부
    """
    try:
        PriceData(current_price=price, change_rate=change_rate)
        return True
    except Exception as e:
        logger.warning(
            f"가격 검증 실패: price={price}, change_rate={change_rate}",
            exc_info=False,
            extra={'price': price, 'change_rate': change_rate, 'error': str(e)}
        )
        return False


def parse_ohlcv_list(data_list: List[dict]) -> List[OHLCVData]:
    """OHLCV 리스트 파싱 및 검증

    Args:
        data_list: OHLCV 딕셔너리 리스트

    Returns:
        List[OHLCVData]: 검증된 OHLCV 리스트
    """
    valid_data = []
    for data in data_list:
        try:
            ohlcv = OHLCVData(**data)
            valid_data.append(ohlcv)
        except Exception as e:
            logger.error(
                f"OHLCV 파싱 실패: {e}",
                exc_info=True,
                extra={'item': data}
            )
            continue
    return valid_data


class PeriodDays(BaseModel):
    """조회 기간 검증 모델 (일봉 조회용)

    한국투자증권 API는 최대 365일까지 조회 가능
    """
    days: int = Field(..., ge=1, le=365, description="조회 기간 (1-365일)")

    def __str__(self) -> str:
        return str(self.days)


class CountRange(BaseModel):
    """조회 건수 검증 모델 (체결/분봉 조회용)

    일반적으로 최대 1000건까지 조회 가능
    """
    count: int = Field(..., ge=1, le=1000, description="조회 건수 (1-1000건)")

    def __str__(self) -> str:
        return str(self.count)


def create_order_request(
    stock_code: str,
    quantity: int,
    side: str,
    order_type: str = "limit",
    price: Optional[int] = None
) -> OrderRequest:
    """주문 요청 생성 및 검증

    Args:
        stock_code: 종목코드
        quantity: 수량
        side: 매매 방향 ('buy' or 'sell')
        order_type: 주문 유형 ('market' or 'limit')
        price: 가격 (지정가일 때 필수)

    Returns:
        OrderRequest: 검증된 주문 요청

    Raises:
        ValueError: 검증 실패 시
    """
    return OrderRequest(
        stock_code=stock_code,
        quantity=quantity,
        order_side=OrderSide(side),
        order_type=OrderType(order_type),
        price=price
    )
