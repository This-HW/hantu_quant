"""
미국 주식 거래 시스템 (P3-4)

KIS 해외주식 API 기반 미국 주식 거래

Features:
- 미국 장 시간 관리
- 환율 자동 계산
- ETF 기반 분산 포트폴리오
- 주문 관리

Usage:
    trader = USTrader(kis_api)

    # 환율 조회
    rate = trader.get_exchange_rate()

    # 주문
    order = trader.buy('AAPL', quantity=10, order_type='market')

    # 포트폴리오 조회
    portfolio = trader.get_portfolio()
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from enum import Enum
import pytz

logger = logging.getLogger(__name__)


# 미국 동부 시간대
US_EASTERN = pytz.timezone('US/Eastern')
KST = pytz.timezone('Asia/Seoul')


class MarketSession(Enum):
    """미국 장 세션"""
    PRE_MARKET = "pre_market"  # 프리마켓 (4:00-9:30 ET)
    REGULAR = "regular"  # 정규장 (9:30-16:00 ET)
    AFTER_HOURS = "after_hours"  # 애프터마켓 (16:00-20:00 ET)
    CLOSED = "closed"  # 장 마감


class OrderType(Enum):
    """주문 유형"""
    MARKET = "market"  # 시장가
    LIMIT = "limit"  # 지정가
    STOP = "stop"  # 스탑
    STOP_LIMIT = "stop_limit"  # 스탑 리밋


class OrderSide(Enum):
    """주문 방향"""
    BUY = "buy"
    SELL = "sell"


class OrderStatus(Enum):
    """주문 상태"""
    PENDING = "pending"
    SUBMITTED = "submitted"
    FILLED = "filled"
    PARTIALLY_FILLED = "partial"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass
class USTradeConfig:
    """미국 주식 거래 설정"""
    # 거래 시간
    enable_pre_market: bool = False  # 프리마켓 거래
    enable_after_hours: bool = False  # 애프터마켓 거래

    # 분산 투자
    max_single_stock_weight: float = 0.2  # 단일 종목 최대 비중 20%
    min_positions: int = 5  # 최소 종목 수
    max_positions: int = 20  # 최대 종목 수

    # ETF 포트폴리오
    default_etf_portfolio: Dict[str, float] = field(default_factory=lambda: {
        'SPY': 0.4,   # S&P 500
        'QQQ': 0.3,   # NASDAQ 100
        'IWM': 0.15,  # Russell 2000
        'VEA': 0.15,  # 선진국 (미국 제외)
    })

    # 비용
    commission_per_share: float = 0.0  # 주당 수수료 (대부분 0)
    min_commission: float = 0.0  # 최소 수수료

    # 환율
    default_exchange_rate: float = 1350.0  # 기본 환율 (KRW/USD)


@dataclass
class ExchangeRate:
    """환율 정보"""
    usd_krw: float  # USD/KRW 환율
    update_time: datetime
    source: str = "api"

    def convert_to_krw(self, usd_amount: float) -> float:
        """USD → KRW"""
        return usd_amount * self.usd_krw

    def convert_to_usd(self, krw_amount: float) -> float:
        """KRW → USD"""
        return krw_amount / self.usd_krw

    def to_dict(self) -> Dict:
        return {
            'usd_krw': self.usd_krw,
            'update_time': self.update_time.isoformat(),
            'source': self.source,
        }


@dataclass
class USPosition:
    """미국 주식 포지션"""
    symbol: str  # 티커 (예: AAPL)
    quantity: int  # 보유 수량
    avg_price: float  # 평균 매입가 (USD)
    current_price: float  # 현재가 (USD)
    currency: str = "USD"

    @property
    def market_value(self) -> float:
        """시장 가치 (USD)"""
        return self.quantity * self.current_price

    @property
    def cost_basis(self) -> float:
        """매입 원가 (USD)"""
        return self.quantity * self.avg_price

    @property
    def unrealized_pnl(self) -> float:
        """미실현 손익 (USD)"""
        return self.market_value - self.cost_basis

    @property
    def unrealized_pnl_percent(self) -> float:
        """미실현 손익률"""
        if self.cost_basis == 0:
            return 0.0
        return (self.unrealized_pnl / self.cost_basis) * 100

    def to_dict(self) -> Dict:
        return {
            'symbol': self.symbol,
            'quantity': self.quantity,
            'avg_price': self.avg_price,
            'current_price': self.current_price,
            'market_value': self.market_value,
            'cost_basis': self.cost_basis,
            'unrealized_pnl': self.unrealized_pnl,
            'unrealized_pnl_percent': self.unrealized_pnl_percent,
        }


@dataclass
class USOrder:
    """미국 주식 주문"""
    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: int
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: int = 0
    filled_price: Optional[float] = None
    created_at: datetime = field(default_factory=datetime.now)
    filled_at: Optional[datetime] = None

    @property
    def is_filled(self) -> bool:
        return self.status == OrderStatus.FILLED

    @property
    def is_active(self) -> bool:
        return self.status in [OrderStatus.PENDING, OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED]

    def to_dict(self) -> Dict:
        return {
            'order_id': self.order_id,
            'symbol': self.symbol,
            'side': self.side.value,
            'order_type': self.order_type.value,
            'quantity': self.quantity,
            'limit_price': self.limit_price,
            'stop_price': self.stop_price,
            'status': self.status.value,
            'filled_quantity': self.filled_quantity,
            'filled_price': self.filled_price,
            'created_at': self.created_at.isoformat(),
            'filled_at': self.filled_at.isoformat() if self.filled_at else None,
        }


@dataclass
class GlobalPortfolio:
    """글로벌 분산 포트폴리오"""
    us_positions: List[USPosition]
    kr_value: float  # 한국 주식 가치 (KRW)
    cash_usd: float  # USD 현금
    cash_krw: float  # KRW 현금
    exchange_rate: ExchangeRate

    @property
    def us_value_usd(self) -> float:
        """미국 주식 가치 (USD)"""
        return sum(p.market_value for p in self.us_positions)

    @property
    def us_value_krw(self) -> float:
        """미국 주식 가치 (KRW)"""
        return self.exchange_rate.convert_to_krw(self.us_value_usd)

    @property
    def total_value_krw(self) -> float:
        """총 자산 가치 (KRW)"""
        total_cash_krw = self.cash_krw + self.exchange_rate.convert_to_krw(self.cash_usd)
        return self.kr_value + self.us_value_krw + total_cash_krw

    @property
    def us_allocation(self) -> float:
        """미국 비중"""
        if self.total_value_krw == 0:
            return 0.0
        return self.us_value_krw / self.total_value_krw

    @property
    def kr_allocation(self) -> float:
        """한국 비중"""
        if self.total_value_krw == 0:
            return 0.0
        return self.kr_value / self.total_value_krw

    def get_position_weights(self) -> Dict[str, float]:
        """종목별 비중"""
        weights = {}
        for pos in self.us_positions:
            if self.total_value_krw > 0:
                pos_value_krw = self.exchange_rate.convert_to_krw(pos.market_value)
                weights[pos.symbol] = pos_value_krw / self.total_value_krw
        return weights

    def to_dict(self) -> Dict:
        return {
            'us_positions': [p.to_dict() for p in self.us_positions],
            'kr_value': self.kr_value,
            'cash_usd': self.cash_usd,
            'cash_krw': self.cash_krw,
            'exchange_rate': self.exchange_rate.to_dict(),
            'us_value_usd': self.us_value_usd,
            'us_value_krw': self.us_value_krw,
            'total_value_krw': self.total_value_krw,
            'us_allocation': self.us_allocation,
            'kr_allocation': self.kr_allocation,
        }


class USTrader:
    """미국 주식 트레이더

    Usage:
        trader = USTrader()

        # 장 시간 확인
        session = trader.get_market_session()

        # 주문
        if session == MarketSession.REGULAR:
            order = trader.buy('AAPL', 10)

        # 포트폴리오
        portfolio = trader.get_portfolio()
    """

    # 미국 공휴일 (간단히 주요 공휴일만)
    US_HOLIDAYS_2025 = [
        datetime(2025, 1, 1),   # New Year's Day
        datetime(2025, 1, 20),  # MLK Day
        datetime(2025, 2, 17),  # Presidents' Day
        datetime(2025, 4, 18),  # Good Friday
        datetime(2025, 5, 26),  # Memorial Day
        datetime(2025, 6, 19),  # Juneteenth
        datetime(2025, 7, 4),   # Independence Day
        datetime(2025, 9, 1),   # Labor Day
        datetime(2025, 11, 27), # Thanksgiving
        datetime(2025, 12, 25), # Christmas
    ]

    def __init__(
        self,
        config: Optional[USTradeConfig] = None,
        kis_api: Optional[Any] = None,
    ):
        """초기화

        Args:
            config: 거래 설정
            kis_api: KIS API 클라이언트
        """
        self.config = config or USTradeConfig()
        self.kis_api = kis_api

        self.positions: Dict[str, USPosition] = {}
        self.orders: Dict[str, USOrder] = {}
        self.exchange_rate = ExchangeRate(
            usd_krw=self.config.default_exchange_rate,
            update_time=datetime.now(),
            source="default",
        )

        logger.info("USTrader 초기화 완료")

    def get_market_session(self, dt: Optional[datetime] = None) -> MarketSession:
        """현재 미국 장 세션 확인

        Args:
            dt: 확인할 시간 (None이면 현재)

        Returns:
            MarketSession
        """
        if dt is None:
            dt = datetime.now(US_EASTERN)
        elif dt.tzinfo is None:
            dt = US_EASTERN.localize(dt)
        else:
            dt = dt.astimezone(US_EASTERN)

        # 주말 체크
        if dt.weekday() >= 5:  # 토, 일
            return MarketSession.CLOSED

        # 공휴일 체크
        date_only = dt.date()
        for holiday in self.US_HOLIDAYS_2025:
            if holiday.date() == date_only:
                return MarketSession.CLOSED

        current_time = dt.time()

        # 시간대별 세션
        pre_market_start = time(4, 0)
        regular_start = time(9, 30)
        regular_end = time(16, 0)
        after_hours_end = time(20, 0)

        if pre_market_start <= current_time < regular_start:
            return MarketSession.PRE_MARKET
        elif regular_start <= current_time < regular_end:
            return MarketSession.REGULAR
        elif regular_end <= current_time < after_hours_end:
            return MarketSession.AFTER_HOURS
        else:
            return MarketSession.CLOSED

    def get_next_market_open(self, dt: Optional[datetime] = None) -> datetime:
        """다음 장 오픈 시간 (KST)

        Args:
            dt: 기준 시간

        Returns:
            다음 정규장 오픈 시간 (KST)
        """
        if dt is None:
            dt = datetime.now(US_EASTERN)
        elif dt.tzinfo is None:
            dt = US_EASTERN.localize(dt)

        # 다음 장 시작 시간 찾기
        current = dt
        for _ in range(10):  # 최대 10일 탐색
            session = self.get_market_session(current)

            if session == MarketSession.CLOSED:
                # 다음날로
                current = current.replace(hour=9, minute=30, second=0, microsecond=0)
                current += timedelta(days=1)
            elif session == MarketSession.PRE_MARKET:
                # 같은 날 정규장 시작
                next_open = current.replace(hour=9, minute=30, second=0, microsecond=0)
                return next_open.astimezone(KST)
            else:
                # 이미 열려있으면 다음날
                current = current.replace(hour=9, minute=30, second=0, microsecond=0)
                current += timedelta(days=1)

        return current.astimezone(KST)

    def update_exchange_rate(self, rate: Optional[float] = None) -> ExchangeRate:
        """환율 업데이트

        Args:
            rate: 직접 지정 환율 (없으면 API 조회)

        Returns:
            ExchangeRate
        """
        if rate is not None:
            self.exchange_rate = ExchangeRate(
                usd_krw=rate,
                update_time=datetime.now(),
                source="manual",
            )
        elif self.kis_api:
            try:
                # KIS API에서 환율 조회 (구현 필요)
                # api_rate = self.kis_api.get_exchange_rate('USD', 'KRW')
                api_rate = self.config.default_exchange_rate  # 임시
                self.exchange_rate = ExchangeRate(
                    usd_krw=api_rate,
                    update_time=datetime.now(),
                    source="api",
                )
            except Exception as e:
                logger.warning(f"환율 조회 실패: {e}")
        else:
            self.exchange_rate = ExchangeRate(
                usd_krw=self.config.default_exchange_rate,
                update_time=datetime.now(),
                source="default",
            )

        return self.exchange_rate

    def get_quote(self, symbol: str) -> Dict[str, Any]:
        """시세 조회

        Args:
            symbol: 티커

        Returns:
            시세 정보
        """
        if self.kis_api:
            try:
                # KIS API에서 시세 조회 (구현 필요)
                # return self.kis_api.get_us_quote(symbol)
                pass
            except Exception as e:
                logger.error(f"시세 조회 실패 {symbol}: {e}", exc_info=True)

        # 더미 데이터
        return {
            'symbol': symbol,
            'price': 0.0,
            'change': 0.0,
            'change_percent': 0.0,
            'volume': 0,
        }

    def can_trade(self) -> Tuple[bool, str]:
        """거래 가능 여부

        Returns:
            (가능 여부, 사유)
        """
        session = self.get_market_session()

        if session == MarketSession.REGULAR:
            return True, "정규장"

        if session == MarketSession.PRE_MARKET and self.config.enable_pre_market:
            return True, "프리마켓"

        if session == MarketSession.AFTER_HOURS and self.config.enable_after_hours:
            return True, "애프터마켓"

        next_open = self.get_next_market_open()
        return False, f"장 마감 (다음 오픈: {next_open.strftime('%Y-%m-%d %H:%M')} KST)"

    def buy(
        self,
        symbol: str,
        quantity: int,
        order_type: str = "market",
        limit_price: Optional[float] = None,
    ) -> Optional[USOrder]:
        """매수 주문

        Args:
            symbol: 티커
            quantity: 수량
            order_type: 주문 유형
            limit_price: 지정가

        Returns:
            USOrder or None
        """
        can, reason = self.can_trade()
        if not can:
            logger.warning(f"거래 불가: {reason}")
            return None

        order = USOrder(
            order_id=f"O{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            symbol=symbol.upper(),
            side=OrderSide.BUY,
            order_type=OrderType(order_type),
            quantity=quantity,
            limit_price=limit_price,
            status=OrderStatus.PENDING,
        )

        # 실제 주문 (KIS API)
        if self.kis_api:
            try:
                # result = self.kis_api.place_us_order(order)
                order.status = OrderStatus.SUBMITTED
            except Exception as e:
                logger.error(f"주문 실패: {e}", exc_info=True)
                order.status = OrderStatus.REJECTED
                return None

        self.orders[order.order_id] = order
        logger.info(f"매수 주문: {symbol} {quantity}주")

        return order

    def sell(
        self,
        symbol: str,
        quantity: int,
        order_type: str = "market",
        limit_price: Optional[float] = None,
    ) -> Optional[USOrder]:
        """매도 주문

        Args:
            symbol: 티커
            quantity: 수량
            order_type: 주문 유형
            limit_price: 지정가

        Returns:
            USOrder or None
        """
        can, reason = self.can_trade()
        if not can:
            logger.warning(f"거래 불가: {reason}")
            return None

        # 보유량 확인
        symbol = symbol.upper()
        if symbol in self.positions:
            if self.positions[symbol].quantity < quantity:
                logger.warning(f"보유량 부족: {symbol}")
                return None
        else:
            logger.warning(f"미보유 종목: {symbol}")
            return None

        order = USOrder(
            order_id=f"O{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            symbol=symbol,
            side=OrderSide.SELL,
            order_type=OrderType(order_type),
            quantity=quantity,
            limit_price=limit_price,
            status=OrderStatus.PENDING,
        )

        if self.kis_api:
            try:
                # result = self.kis_api.place_us_order(order)
                order.status = OrderStatus.SUBMITTED
            except Exception as e:
                logger.error(f"주문 실패: {e}", exc_info=True)
                order.status = OrderStatus.REJECTED
                return None

        self.orders[order.order_id] = order
        logger.info(f"매도 주문: {symbol} {quantity}주")

        return order

    def cancel_order(self, order_id: str) -> bool:
        """주문 취소

        Args:
            order_id: 주문 ID

        Returns:
            성공 여부
        """
        if order_id not in self.orders:
            return False

        order = self.orders[order_id]
        if not order.is_active:
            return False

        if self.kis_api:
            try:
                # self.kis_api.cancel_us_order(order_id)
                pass
            except Exception as e:
                logger.error(f"취소 실패: {e}", exc_info=True)
                return False

        order.status = OrderStatus.CANCELLED
        logger.info(f"주문 취소: {order_id}")

        return True

    def get_portfolio(
        self,
        kr_value: float = 0.0,
        cash_krw: float = 0.0,
    ) -> GlobalPortfolio:
        """글로벌 포트폴리오 조회

        Args:
            kr_value: 한국 주식 가치
            cash_krw: KRW 현금

        Returns:
            GlobalPortfolio
        """
        self.update_exchange_rate()

        # 현재가 업데이트
        for symbol, position in self.positions.items():
            quote = self.get_quote(symbol)
            if quote and quote.get('price', 0) > 0:
                position.current_price = quote['price']

        return GlobalPortfolio(
            us_positions=list(self.positions.values()),
            kr_value=kr_value,
            cash_usd=0.0,  # API에서 조회
            cash_krw=cash_krw,
            exchange_rate=self.exchange_rate,
        )

    def rebalance_etf_portfolio(
        self,
        total_usd: float,
        target_weights: Optional[Dict[str, float]] = None,
    ) -> List[Dict[str, Any]]:
        """ETF 포트폴리오 리밸런싱 계획

        Args:
            total_usd: 총 투자금액 (USD)
            target_weights: 목표 비중 (없으면 기본 ETF)

        Returns:
            리밸런싱 계획
        """
        if target_weights is None:
            target_weights = self.config.default_etf_portfolio

        # 비중 합계 검증
        total_weight = sum(target_weights.values())
        if abs(total_weight - 1.0) > 0.01:
            logger.warning(f"비중 합계 != 1.0: {total_weight}")
            # 정규화
            target_weights = {k: v/total_weight for k, v in target_weights.items()}

        plans = []
        for symbol, weight in target_weights.items():
            target_value = total_usd * weight
            quote = self.get_quote(symbol)
            price = quote.get('price') or 100.0  # 0이거나 None이면 기본값 사용

            if price > 0:
                target_qty = int(target_value / price)
            else:
                target_qty = 0

            current_qty = self.positions.get(symbol, USPosition(symbol, 0, 0, 0)).quantity
            diff_qty = target_qty - current_qty

            if diff_qty != 0:
                plans.append({
                    'symbol': symbol,
                    'action': 'buy' if diff_qty > 0 else 'sell',
                    'quantity': abs(diff_qty),
                    'target_weight': weight,
                    'estimated_value': abs(diff_qty) * price,
                })

        return plans

    def execute_rebalance(
        self,
        plans: List[Dict[str, Any]],
    ) -> List[USOrder]:
        """리밸런싱 실행

        Args:
            plans: 리밸런싱 계획

        Returns:
            실행된 주문 목록
        """
        orders = []

        # 매도 먼저
        for plan in plans:
            if plan['action'] == 'sell':
                order = self.sell(plan['symbol'], plan['quantity'])
                if order:
                    orders.append(order)

        # 그 다음 매수
        for plan in plans:
            if plan['action'] == 'buy':
                order = self.buy(plan['symbol'], plan['quantity'])
                if order:
                    orders.append(order)

        return orders

    def add_position(self, position: USPosition):
        """포지션 추가 (테스트용)"""
        self.positions[position.symbol] = position

    def get_trading_schedule(self, days: int = 5) -> List[Dict[str, Any]]:
        """거래 스케줄 조회

        Args:
            days: 조회 일수

        Returns:
            스케줄 목록
        """
        schedule = []
        current = datetime.now(US_EASTERN)

        for i in range(days):
            check_date = current + timedelta(days=i)
            session = self.get_market_session(
                check_date.replace(hour=10, minute=0)
            )

            if session != MarketSession.CLOSED:
                open_time = check_date.replace(hour=9, minute=30).astimezone(KST)
                close_time = check_date.replace(hour=16, minute=0).astimezone(KST)

                schedule.append({
                    'date': check_date.strftime('%Y-%m-%d'),
                    'day': check_date.strftime('%A'),
                    'open_kst': open_time.strftime('%H:%M'),
                    'close_kst': close_time.strftime('%H:%M'),
                    'is_today': i == 0,
                })

        return schedule
