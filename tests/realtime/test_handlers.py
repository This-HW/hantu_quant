"""
실시간 핸들러 테스트
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, patch
from collections import deque

from core.realtime.handlers import (
    EventHandler,
    MarketCondition,
    VolumeAnalysis,
    VolatilityAnalysis,
)


def run_async(coro):
    """동기 함수에서 비동기 실행"""
    return asyncio.get_event_loop().run_until_complete(coro)


class TestEventHandler:
    """EventHandler 테스트"""

    @pytest.fixture
    def handler(self):
        with patch('core.realtime.handlers.DatabaseSession'):
            with patch('core.realtime.handlers.StockRepository'):
                return EventHandler(session=Mock())

    def test_init(self, handler):
        assert handler.running is False
        assert handler._history_size == 100

    def test_start_stop(self, handler):
        run_async(handler.start())
        assert handler.running is True
        run_async(handler.stop())
        assert handler.running is False

    def test_update_history(self, handler):
        handler._update_history('005930', 70000, 1000)
        assert '005930' in handler._price_history
        assert 70000 in handler._price_history['005930']

    def test_update_history_maxlen(self, handler):
        for i in range(150):
            handler._update_history('005930', 70000 + i, 1000)
        assert len(handler._price_history['005930']) == 100


class TestTradingSignals:
    """거래 신호 생성 테스트"""

    @pytest.fixture
    def handler_with_history(self):
        with patch('core.realtime.handlers.DatabaseSession'):
            with patch('core.realtime.handlers.StockRepository'):
                handler = EventHandler(session=Mock())
                prices = [70000 + i * 10 for i in range(50)]
                volumes = [1000 + i * 10 for i in range(50)]
                handler._price_history['005930'] = deque(prices, maxlen=100)
                handler._volume_history['005930'] = deque(volumes, maxlen=100)
                return handler

    def test_generate_signals_insufficient_data(self, handler_with_history):
        data = {'symbol': 'UNKNOWN', 'price': 70000}
        signals = run_async(handler_with_history._generate_trading_signals(data))
        assert signals['action'] == 'HOLD'

    def test_generate_signals_with_data(self, handler_with_history):
        data = {'symbol': '005930', 'price': 70500}
        signals = run_async(handler_with_history._generate_trading_signals(data))
        assert signals['action'] in ['BUY', 'SELL', 'HOLD']

    def test_generate_ta_signal_insufficient_data(self, handler_with_history):
        signal = handler_with_history._generate_ta_signal('005930', [1, 2, 3], 70000)
        assert signal is None

    def test_generate_market_signal_no_condition(self, handler_with_history):
        signal = handler_with_history._generate_market_signal('005930', 70000)
        assert signal is None

    def test_generate_market_signal_buy_pressure(self, handler_with_history):
        handler_with_history._market_conditions['005930'] = MarketCondition(
            imbalance_ratio=0.5, pressure='buy'
        )
        signal = handler_with_history._generate_market_signal('005930', 70000)
        assert signal is not None


class TestQuoteAnalysis:
    """호가 분석 테스트"""

    @pytest.fixture
    def handler(self):
        with patch('core.realtime.handlers.DatabaseSession'):
            with patch('core.realtime.handlers.StockRepository'):
                return EventHandler(session=Mock())

    def test_analyze_quote_empty(self, handler):
        data = {'symbol': '005930'}
        result = run_async(handler._analyze_quote_data(data))
        assert result['stock_code'] == '005930'
        assert result['pressure'] == 'neutral'

    def test_analyze_quote_with_data(self, handler):
        data = {
            'symbol': '005930',
            'bid_prices': [70000, 69900],
            'ask_prices': [70100, 70200],
            'bid_volumes': [1000, 500],
            'ask_volumes': [800, 400],
        }
        result = run_async(handler._analyze_quote_data(data))
        assert result['spread'] == 100
        assert result['bid_depth'] == 1500

    def test_analyze_quote_sell_pressure(self, handler):
        data = {
            'symbol': '005930',
            'bid_prices': [70000],
            'ask_prices': [70100],
            'bid_volumes': [500],
            'ask_volumes': [2000],
        }
        result = run_async(handler._analyze_quote_data(data))
        assert result['pressure'] == 'sell'

    def test_update_market_condition(self, handler):
        analysis = {
            'stock_code': '005930',
            'timestamp': datetime.now(),
            'spread_pct': 0.001,
            'bid_depth': 1000,
            'ask_depth': 800,
            'imbalance_ratio': 0.11,
            'pressure': 'buy',
        }
        run_async(handler._update_market_condition(analysis))
        condition = handler._market_conditions.get('005930')
        assert condition is not None
        assert condition.pressure == 'buy'


class TestVolumeVolatilityAnalysis:
    """거래량/변동성 분석 테스트"""

    @pytest.fixture
    def handler_with_data(self):
        with patch('core.realtime.handlers.DatabaseSession'):
            with patch('core.realtime.handlers.StockRepository'):
                handler = EventHandler(session=Mock())
                prices = [70000 + (i % 10) * 100 for i in range(50)]
                volumes = [1000 + (i % 5) * 100 for i in range(50)]
                handler._price_history['005930'] = deque(prices, maxlen=100)
                handler._volume_history['005930'] = deque(volumes, maxlen=100)
                return handler

    def test_analyze_volume_no_data(self, handler_with_data):
        data = {'symbol': 'UNKNOWN', 'volume': 1000}
        result = run_async(handler_with_data._analyze_volume(data))
        assert result.current_volume == 1000
        assert result.is_surge is False

    def test_analyze_volume_surge(self, handler_with_data):
        data = {'symbol': '005930', 'volume': 10000}
        result = run_async(handler_with_data._analyze_volume(data))
        assert result.volume_ratio > 1

    def test_analyze_volatility_no_data(self, handler_with_data):
        data = {'symbol': 'UNKNOWN'}
        result = run_async(handler_with_data._analyze_volatility(data))
        assert result.regime == "normal"

    def test_analyze_volatility_with_data(self, handler_with_data):
        data = {'symbol': '005930'}
        result = run_async(handler_with_data._analyze_volatility(data))
        assert result.regime in ["low", "normal", "high", "extreme"]


class TestAbnormalTrading:
    """이상 거래 감지 테스트"""

    @pytest.fixture
    def handler(self):
        with patch('core.realtime.handlers.DatabaseSession'):
            with patch('core.realtime.handlers.StockRepository'):
                handler = EventHandler(session=Mock())
                prices = [70000 + i * 10 for i in range(50)]
                handler._price_history['005930'] = deque(prices, maxlen=100)
                return handler

    def test_detect_no_abnormal(self, handler):
        data = {'symbol': '005930'}
        volume = VolumeAnalysis(volume_ratio=1.5)
        volatility = VolatilityAnalysis(volatility_ratio=1.0)
        result = run_async(handler._detect_abnormal_trading(data, volume, volatility))
        assert result.is_abnormal is False

    def test_detect_volume_surge(self, handler):
        data = {'symbol': '005930'}
        volume = VolumeAnalysis(volume_ratio=5.0)
        volatility = VolatilityAnalysis(volatility_ratio=1.0)
        result = run_async(handler._detect_abnormal_trading(data, volume, volatility))
        assert result.is_abnormal is True

    def test_detect_high_volatility(self, handler):
        data = {'symbol': '005930'}
        volume = VolumeAnalysis(volume_ratio=1.0)
        volatility = VolatilityAnalysis(volatility_ratio=3.0)
        result = run_async(handler._detect_abnormal_trading(data, volume, volatility))
        assert result.is_abnormal is True

    def test_detect_price_spike(self, handler):
        prices = [70000] * 48 + [70000, 75000]
        handler._price_history['005930'] = deque(prices, maxlen=100)
        data = {'symbol': '005930'}
        result = run_async(handler._detect_abnormal_trading(data, VolumeAnalysis(), VolatilityAnalysis()))
        assert result.is_abnormal is True


class TestPendingSignals:
    """대기 신호 관리 테스트"""

    @pytest.fixture
    def handler(self):
        with patch('core.realtime.handlers.DatabaseSession'):
            with patch('core.realtime.handlers.StockRepository'):
                return EventHandler(session=Mock())

    def test_execute_trades_hold(self, handler):
        run_async(handler._execute_trades({'action': 'HOLD'}))
        assert len(handler._pending_signals) == 0

    def test_execute_trades_buy(self, handler):
        run_async(handler._execute_trades({'action': 'BUY', 'stock_code': '005930'}))
        assert len(handler._pending_signals) == 1

    def test_get_pending_signals(self, handler):
        handler._pending_signals = [{'action': 'BUY'}]
        signals = handler.get_pending_signals()
        assert len(signals) == 1
        signals.clear()
        assert len(handler._pending_signals) == 1

    def test_clear_pending_signals(self, handler):
        handler._pending_signals = [{'action': 'BUY'}]
        handler.clear_pending_signals()
        assert len(handler._pending_signals) == 0


class TestCleanup:
    """정리 기능 테스트"""

    @pytest.fixture
    def handler(self):
        with patch('core.realtime.handlers.DatabaseSession'):
            with patch('core.realtime.handlers.StockRepository'):
                handler = EventHandler(session=Mock())
                handler._price_history['005930'] = deque([70000], maxlen=100)
                handler._market_conditions['005930'] = MarketCondition()
                handler._pending_signals = [{'action': 'BUY'}]
                return handler

    def test_cleanup(self, handler):
        handler._cleanup()
        assert len(handler._price_history) == 0
        assert len(handler._pending_signals) == 0

    def test_get_market_condition(self, handler):
        assert handler.get_market_condition('005930') is not None
        assert handler.get_market_condition('UNKNOWN') is None


class TestIntegration:
    """통합 테스트"""

    @pytest.fixture
    def handler(self):
        with patch('core.realtime.handlers.DatabaseSession'):
            with patch('core.realtime.handlers.StockRepository'):
                return EventHandler(session=Mock())

    def test_full_trade_flow(self, handler):
        run_async(handler.start())
        for i in range(30):
            run_async(handler.handle_event({
                'type': 'TRADE',
                'symbol': '005930',
                'price': 70000 + i * 10,
                'volume': 1000,
            }))
        assert len(handler._price_history['005930']) == 30
        run_async(handler.stop())

    def test_full_quote_flow(self, handler):
        run_async(handler.start())
        run_async(handler.handle_event({
            'type': 'QUOTE',
            'symbol': '005930',
            'bid_prices': [70000],
            'ask_prices': [70100],
            'bid_volumes': [1000],
            'ask_volumes': [800],
        }))
        assert handler.get_market_condition('005930') is not None
        run_async(handler.stop())
