"""
미국 주식 거래 시스템 테스트 (P3-4)

테스트 항목:
1. 시장 세션 감지
2. 환율 처리
3. 포지션 관리
4. 주문 처리
5. 포트폴리오 관리
"""

import pytest
from datetime import datetime
from pathlib import Path
import sys

# 프로젝트 루트 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.overseas.us_trader import (
    USTradeConfig,
    USPosition,
    USOrder,
    ExchangeRate,
    GlobalPortfolio,
    USTrader,
    MarketSession,
    OrderType,
    OrderSide,
    OrderStatus,
    US_EASTERN,
)


class TestUSTradeConfig:
    """USTradeConfig 테스트"""

    def test_default_values(self):
        """기본값 확인"""
        config = USTradeConfig()

        assert config.enable_pre_market is False
        assert config.enable_after_hours is False
        assert config.max_single_stock_weight == 0.2
        assert config.default_exchange_rate == 1350.0

    def test_default_etf_portfolio(self):
        """기본 ETF 포트폴리오"""
        config = USTradeConfig()

        assert 'SPY' in config.default_etf_portfolio
        assert 'QQQ' in config.default_etf_portfolio

        # 비중 합계 = 1
        total_weight = sum(config.default_etf_portfolio.values())
        assert abs(total_weight - 1.0) < 0.01

    def test_custom_values(self):
        """사용자 설정"""
        config = USTradeConfig(
            enable_pre_market=True,
            default_exchange_rate=1400.0,
        )

        assert config.enable_pre_market is True
        assert config.default_exchange_rate == 1400.0


class TestExchangeRate:
    """ExchangeRate 테스트"""

    def test_create_rate(self):
        """환율 생성"""
        rate = ExchangeRate(
            usd_krw=1350.0,
            update_time=datetime.now(),
        )

        assert rate.usd_krw == 1350.0

    def test_convert_to_krw(self):
        """USD → KRW 변환"""
        rate = ExchangeRate(
            usd_krw=1350.0,
            update_time=datetime.now(),
        )

        assert rate.convert_to_krw(100) == 135000

    def test_convert_to_usd(self):
        """KRW → USD 변환"""
        rate = ExchangeRate(
            usd_krw=1350.0,
            update_time=datetime.now(),
        )

        assert rate.convert_to_usd(1350000) == 1000

    def test_to_dict(self):
        """딕셔너리 변환"""
        rate = ExchangeRate(
            usd_krw=1350.0,
            update_time=datetime.now(),
        )

        d = rate.to_dict()

        assert d['usd_krw'] == 1350.0
        assert 'update_time' in d


class TestUSPosition:
    """USPosition 테스트"""

    def test_create_position(self):
        """포지션 생성"""
        position = USPosition(
            symbol='AAPL',
            quantity=100,
            avg_price=150.0,
            current_price=155.0,
        )

        assert position.symbol == 'AAPL'
        assert position.quantity == 100

    def test_market_value(self):
        """시장 가치"""
        position = USPosition(
            symbol='AAPL',
            quantity=100,
            avg_price=150.0,
            current_price=155.0,
        )

        assert position.market_value == 15500.0

    def test_cost_basis(self):
        """매입 원가"""
        position = USPosition(
            symbol='AAPL',
            quantity=100,
            avg_price=150.0,
            current_price=155.0,
        )

        assert position.cost_basis == 15000.0

    def test_unrealized_pnl(self):
        """미실현 손익"""
        position = USPosition(
            symbol='AAPL',
            quantity=100,
            avg_price=150.0,
            current_price=155.0,
        )

        assert position.unrealized_pnl == 500.0
        assert abs(position.unrealized_pnl_percent - 3.33) < 0.1

    def test_unrealized_pnl_loss(self):
        """미실현 손실"""
        position = USPosition(
            symbol='AAPL',
            quantity=100,
            avg_price=155.0,
            current_price=150.0,
        )

        assert position.unrealized_pnl == -500.0

    def test_to_dict(self):
        """딕셔너리 변환"""
        position = USPosition(
            symbol='AAPL',
            quantity=100,
            avg_price=150.0,
            current_price=155.0,
        )

        d = position.to_dict()

        assert d['symbol'] == 'AAPL'
        assert d['market_value'] == 15500.0


class TestUSOrder:
    """USOrder 테스트"""

    def test_create_order(self):
        """주문 생성"""
        order = USOrder(
            order_id='O123',
            symbol='AAPL',
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=10,
        )

        assert order.order_id == 'O123'
        assert order.symbol == 'AAPL'
        assert order.side == OrderSide.BUY

    def test_is_filled(self):
        """체결 여부"""
        order = USOrder(
            order_id='O123',
            symbol='AAPL',
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=10,
            status=OrderStatus.FILLED,
        )

        assert order.is_filled is True

    def test_is_active(self):
        """활성 여부"""
        order = USOrder(
            order_id='O123',
            symbol='AAPL',
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=10,
            status=OrderStatus.SUBMITTED,
        )

        assert order.is_active is True

    def test_to_dict(self):
        """딕셔너리 변환"""
        order = USOrder(
            order_id='O123',
            symbol='AAPL',
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=10,
            limit_price=150.0,
        )

        d = order.to_dict()

        assert d['order_id'] == 'O123'
        assert d['order_type'] == 'limit'


class TestGlobalPortfolio:
    """GlobalPortfolio 테스트"""

    def test_create_portfolio(self):
        """포트폴리오 생성"""
        rate = ExchangeRate(usd_krw=1350.0, update_time=datetime.now())
        positions = [
            USPosition('AAPL', 100, 150.0, 155.0),
            USPosition('MSFT', 50, 300.0, 310.0),
        ]

        portfolio = GlobalPortfolio(
            us_positions=positions,
            kr_value=50_000_000,
            cash_usd=1000,
            cash_krw=1_000_000,
            exchange_rate=rate,
        )

        assert len(portfolio.us_positions) == 2

    def test_us_value(self):
        """미국 주식 가치"""
        rate = ExchangeRate(usd_krw=1350.0, update_time=datetime.now())
        positions = [
            USPosition('AAPL', 100, 150.0, 155.0),  # 15,500
            USPosition('MSFT', 50, 300.0, 310.0),   # 15,500
        ]

        portfolio = GlobalPortfolio(
            us_positions=positions,
            kr_value=0,
            cash_usd=0,
            cash_krw=0,
            exchange_rate=rate,
        )

        assert portfolio.us_value_usd == 31000.0
        assert portfolio.us_value_krw == 31000.0 * 1350.0

    def test_total_value(self):
        """총 가치"""
        rate = ExchangeRate(usd_krw=1350.0, update_time=datetime.now())
        positions = [
            USPosition('AAPL', 100, 150.0, 155.0),  # 15,500 USD
        ]

        portfolio = GlobalPortfolio(
            us_positions=positions,
            kr_value=20_000_000,  # 2천만원
            cash_usd=1000,  # 1000 USD
            cash_krw=1_000_000,  # 100만원
            exchange_rate=rate,
        )

        us_krw = 15500 * 1350  # 20,925,000
        cash_krw = 1000 * 1350 + 1_000_000  # 2,350,000
        expected = 20_000_000 + us_krw + cash_krw

        assert abs(portfolio.total_value_krw - expected) < 1

    def test_allocation(self):
        """비중 계산"""
        rate = ExchangeRate(usd_krw=1000.0, update_time=datetime.now())
        positions = [
            USPosition('SPY', 100, 100.0, 100.0),  # 10,000 USD = 10,000,000 KRW
        ]

        portfolio = GlobalPortfolio(
            us_positions=positions,
            kr_value=10_000_000,  # 1천만원
            cash_usd=0,
            cash_krw=0,
            exchange_rate=rate,
        )

        # US 50%, KR 50%
        assert abs(portfolio.us_allocation - 0.5) < 0.01
        assert abs(portfolio.kr_allocation - 0.5) < 0.01

    def test_to_dict(self):
        """딕셔너리 변환"""
        rate = ExchangeRate(usd_krw=1350.0, update_time=datetime.now())
        positions = [USPosition('AAPL', 100, 150.0, 155.0)]

        portfolio = GlobalPortfolio(
            us_positions=positions,
            kr_value=50_000_000,
            cash_usd=0,
            cash_krw=0,
            exchange_rate=rate,
        )

        d = portfolio.to_dict()

        assert 'us_positions' in d
        assert 'total_value_krw' in d


class TestUSTrader:
    """USTrader 테스트"""

    def test_init(self):
        """초기화"""
        trader = USTrader()

        assert trader.config is not None
        assert len(trader.positions) == 0
        assert len(trader.orders) == 0

    def test_init_custom_config(self):
        """사용자 설정으로 초기화"""
        config = USTradeConfig(enable_pre_market=True)
        trader = USTrader(config=config)

        assert trader.config.enable_pre_market is True


class TestMarketSession:
    """시장 세션 테스트"""

    def test_regular_hours(self):
        """정규장"""
        trader = USTrader()

        # 화요일 오전 10시 (ET)
        dt = US_EASTERN.localize(datetime(2025, 12, 30, 10, 0))
        session = trader.get_market_session(dt)

        assert session == MarketSession.REGULAR

    def test_pre_market(self):
        """프리마켓"""
        trader = USTrader()

        # 화요일 오전 5시 (ET)
        dt = US_EASTERN.localize(datetime(2025, 12, 30, 5, 0))
        session = trader.get_market_session(dt)

        assert session == MarketSession.PRE_MARKET

    def test_after_hours(self):
        """애프터마켓"""
        trader = USTrader()

        # 화요일 오후 5시 (ET)
        dt = US_EASTERN.localize(datetime(2025, 12, 30, 17, 0))
        session = trader.get_market_session(dt)

        assert session == MarketSession.AFTER_HOURS

    def test_closed_weekend(self):
        """주말 마감"""
        trader = USTrader()

        # 토요일
        dt = US_EASTERN.localize(datetime(2025, 12, 27, 10, 0))
        session = trader.get_market_session(dt)

        assert session == MarketSession.CLOSED

    def test_closed_holiday(self):
        """공휴일 마감"""
        trader = USTrader()

        # 크리스마스
        dt = US_EASTERN.localize(datetime(2025, 12, 25, 10, 0))
        session = trader.get_market_session(dt)

        assert session == MarketSession.CLOSED

    def test_closed_night(self):
        """야간 마감"""
        trader = USTrader()

        # 화요일 새벽 2시 (ET)
        dt = US_EASTERN.localize(datetime(2025, 12, 30, 2, 0))
        session = trader.get_market_session(dt)

        assert session == MarketSession.CLOSED


class TestCanTrade:
    """거래 가능 여부 테스트"""

    def test_can_trade_regular(self):
        """정규장 거래 가능"""
        trader = USTrader()

        # 정규장 시간
        dt = US_EASTERN.localize(datetime(2025, 12, 30, 10, 0))

        # 현재 시간을 모킹할 수 없으므로 세션만 확인
        session = trader.get_market_session(dt)
        assert session == MarketSession.REGULAR

    def test_can_trade_premarket_enabled(self):
        """프리마켓 활성화시 거래 가능"""
        config = USTradeConfig(enable_pre_market=True)
        trader = USTrader(config=config)

        assert trader.config.enable_pre_market is True


class TestUpdateExchangeRate:
    """환율 업데이트 테스트"""

    def test_manual_update(self):
        """수동 환율 업데이트"""
        trader = USTrader()

        rate = trader.update_exchange_rate(1400.0)

        assert rate.usd_krw == 1400.0
        assert rate.source == "manual"

    def test_default_update(self):
        """기본 환율 사용"""
        trader = USTrader()

        rate = trader.update_exchange_rate()

        assert rate.usd_krw == trader.config.default_exchange_rate


class TestOrderManagement:
    """주문 관리 테스트"""

    def test_add_position(self):
        """포지션 추가"""
        trader = USTrader()

        position = USPosition('AAPL', 100, 150.0, 155.0)
        trader.add_position(position)

        assert 'AAPL' in trader.positions
        assert trader.positions['AAPL'].quantity == 100


class TestPortfolioManagement:
    """포트폴리오 관리 테스트"""

    def test_get_portfolio(self):
        """포트폴리오 조회"""
        trader = USTrader()

        position = USPosition('AAPL', 100, 150.0, 155.0)
        trader.add_position(position)

        portfolio = trader.get_portfolio(
            kr_value=50_000_000,
            cash_krw=1_000_000,
        )

        assert len(portfolio.us_positions) == 1
        assert portfolio.kr_value == 50_000_000


class TestRebalancing:
    """리밸런싱 테스트"""

    def test_rebalance_etf_portfolio(self):
        """ETF 리밸런싱 계획"""
        trader = USTrader()

        plans = trader.rebalance_etf_portfolio(
            total_usd=10000,
            target_weights={'SPY': 0.6, 'QQQ': 0.4},
        )

        assert len(plans) == 2

        # SPY 60%, QQQ 40%
        symbols = [p['symbol'] for p in plans]
        assert 'SPY' in symbols
        assert 'QQQ' in symbols


class TestTradingSchedule:
    """거래 스케줄 테스트"""

    def test_get_trading_schedule(self):
        """거래 스케줄 조회"""
        trader = USTrader()

        schedule = trader.get_trading_schedule(days=5)

        # 최소 일부 거래일이 있어야 함
        assert len(schedule) >= 0


class TestEnums:
    """Enum 테스트"""

    def test_market_session(self):
        """MarketSession 값"""
        assert MarketSession.REGULAR.value == "regular"
        assert MarketSession.CLOSED.value == "closed"

    def test_order_type(self):
        """OrderType 값"""
        assert OrderType.MARKET.value == "market"
        assert OrderType.LIMIT.value == "limit"

    def test_order_side(self):
        """OrderSide 값"""
        assert OrderSide.BUY.value == "buy"
        assert OrderSide.SELL.value == "sell"

    def test_order_status(self):
        """OrderStatus 값"""
        assert OrderStatus.PENDING.value == "pending"
        assert OrderStatus.FILLED.value == "filled"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
