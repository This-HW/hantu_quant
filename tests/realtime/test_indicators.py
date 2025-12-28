"""
실시간 지표 계산기 테스트
"""

import pytest
from datetime import datetime

from core.realtime.indicators import (
    RealtimeIndicatorCalculator,
    IndicatorConfig,
    IndicatorType,
    IndicatorValue,
)


class TestRealtimeIndicatorCalculator:
    """RealtimeIndicatorCalculator 테스트"""

    @pytest.fixture
    def calculator(self):
        return RealtimeIndicatorCalculator()

    @pytest.fixture
    def calculator_with_data(self):
        """데이터가 준비된 계산기"""
        calc = RealtimeIndicatorCalculator()
        # 30개의 가격 데이터 생성
        for i in range(30):
            price = 70000 + i * 100
            calc.update('005930', {
                'open': price - 50,
                'high': price + 50,
                'low': price - 100,
                'close': price,
                'volume': 1000 + i * 10,
            })
        return calc

    def test_init(self, calculator):
        assert calculator.config is not None
        assert calculator._history_size == 200

    def test_init_custom_config(self):
        config = IndicatorConfig(rsi_period=7, ma_short_period=3)
        calc = RealtimeIndicatorCalculator(config=config)
        assert calc.config.rsi_period == 7
        assert calc.config.ma_short_period == 3

    def test_update_creates_history(self, calculator):
        calculator.update('005930', {'close': 70000, 'volume': 1000})
        assert '005930' in calculator._close_history
        assert len(calculator._close_history['005930']) == 1

    def test_update_multiple_stocks(self, calculator):
        calculator.update('005930', {'close': 70000, 'volume': 1000})
        calculator.update('000660', {'close': 150000, 'volume': 500})
        assert '005930' in calculator._close_history
        assert '000660' in calculator._close_history


class TestRSICalculation:
    """RSI 계산 테스트"""

    @pytest.fixture
    def calculator(self):
        return RealtimeIndicatorCalculator()

    def test_rsi_insufficient_data(self, calculator):
        for i in range(10):
            calculator.update('005930', {'close': 70000 + i, 'volume': 1000})
        indicators = calculator.get_all_indicators('005930')
        assert IndicatorType.RSI not in indicators

    def test_rsi_calculation(self, calculator):
        # 상승 추세 데이터 생성
        for i in range(20):
            calculator.update('005930', {'close': 70000 + i * 100, 'volume': 1000})

        rsi = calculator.get_indicator('005930', IndicatorType.RSI)
        assert rsi is not None
        assert 0 <= rsi.value <= 100
        assert rsi.value > 50  # 상승 추세이므로 50 이상

    def test_rsi_decreasing_trend(self, calculator):
        # 하락 추세 데이터 생성
        for i in range(20):
            calculator.update('005930', {'close': 80000 - i * 100, 'volume': 1000})

        rsi = calculator.get_indicator('005930', IndicatorType.RSI)
        assert rsi is not None
        assert rsi.value < 50  # 하락 추세이므로 50 미만


class TestMovingAverages:
    """이동평균 테스트"""

    @pytest.fixture
    def calculator(self):
        return RealtimeIndicatorCalculator()

    def test_ma_calculation(self, calculator):
        for i in range(25):
            calculator.update('005930', {'close': 70000 + i * 10, 'volume': 1000})

        ma = calculator.get_indicator('005930', IndicatorType.MA)
        assert ma is not None
        assert ma.metadata.get('ma_short') is not None
        assert ma.metadata.get('ma_medium') is not None

    def test_ma_short_greater_on_uptrend(self, calculator):
        for i in range(25):
            calculator.update('005930', {'close': 70000 + i * 100, 'volume': 1000})

        ma = calculator.get_indicator('005930', IndicatorType.MA)
        assert ma.metadata['ma_short'] > ma.metadata['ma_medium']


class TestEMACalculation:
    """EMA 계산 테스트"""

    @pytest.fixture
    def calculator(self):
        return RealtimeIndicatorCalculator()

    def test_ema_calculation(self, calculator):
        for i in range(15):
            calculator.update('005930', {'close': 70000 + i * 100, 'volume': 1000})

        ema = calculator.get_indicator('005930', IndicatorType.EMA)
        assert ema is not None
        assert ema.value > 0

    def test_ema_responds_to_price_changes(self, calculator):
        # 일정 가격
        for i in range(15):
            calculator.update('005930', {'close': 70000, 'volume': 1000})

        ema1 = calculator.get_indicator('005930', IndicatorType.EMA)

        # 급격한 가격 상승
        calculator.update('005930', {'close': 72000, 'volume': 1000})
        ema2 = calculator.get_indicator('005930', IndicatorType.EMA)

        assert ema2.value > ema1.value


class TestMACDCalculation:
    """MACD 계산 테스트"""

    @pytest.fixture
    def calculator(self):
        return RealtimeIndicatorCalculator()

    def test_macd_insufficient_data(self, calculator):
        for i in range(20):
            calculator.update('005930', {'close': 70000 + i, 'volume': 1000})

        macd = calculator.get_indicator('005930', IndicatorType.MACD)
        assert macd is None

    def test_macd_calculation(self, calculator):
        for i in range(30):
            calculator.update('005930', {'close': 70000 + i * 100, 'volume': 1000})

        macd = calculator.get_indicator('005930', IndicatorType.MACD)
        assert macd is not None
        assert 'macd' in macd.metadata
        assert 'signal' in macd.metadata
        assert 'histogram' in macd.metadata


class TestBollingerBands:
    """볼린저 밴드 테스트"""

    @pytest.fixture
    def calculator(self):
        return RealtimeIndicatorCalculator()

    def test_bollinger_calculation(self, calculator):
        for i in range(25):
            calculator.update('005930', {'close': 70000 + (i % 5) * 100, 'volume': 1000})

        bb = calculator.get_indicator('005930', IndicatorType.BOLLINGER)
        assert bb is not None
        assert 'upper' in bb.metadata
        assert 'middle' in bb.metadata
        assert 'lower' in bb.metadata
        assert bb.metadata['upper'] > bb.metadata['middle']
        assert bb.metadata['middle'] > bb.metadata['lower']

    def test_bollinger_percent_b(self, calculator):
        for i in range(25):
            calculator.update('005930', {'close': 70000 + (i % 5) * 100, 'volume': 1000})

        bb = calculator.get_indicator('005930', IndicatorType.BOLLINGER)
        percent_b = bb.metadata.get('percent_b', 0)
        assert 0 <= percent_b <= 1.5  # 밴드 내외로 조금 벗어날 수 있음


class TestStochastic:
    """스토캐스틱 테스트"""

    @pytest.fixture
    def calculator(self):
        return RealtimeIndicatorCalculator()

    def test_stochastic_calculation(self, calculator):
        for i in range(20):
            calculator.update('005930', {
                'open': 70000,
                'high': 70500 + i * 10,
                'low': 69500 - i * 5,
                'close': 70000 + i * 50,
                'volume': 1000,
            })

        stoch = calculator.get_indicator('005930', IndicatorType.STOCHASTIC)
        assert stoch is not None
        assert 'k' in stoch.metadata
        assert 'd' in stoch.metadata
        assert 0 <= stoch.metadata['k'] <= 100
        assert 0 <= stoch.metadata['d'] <= 100


class TestATR:
    """ATR 테스트"""

    @pytest.fixture
    def calculator(self):
        return RealtimeIndicatorCalculator()

    def test_atr_calculation(self, calculator):
        for i in range(20):
            calculator.update('005930', {
                'open': 70000,
                'high': 70500,
                'low': 69500,
                'close': 70000 + i * 10,
                'volume': 1000,
            })

        atr = calculator.get_indicator('005930', IndicatorType.ATR)
        assert atr is not None
        assert atr.value > 0


class TestVWAP:
    """VWAP 테스트"""

    @pytest.fixture
    def calculator(self):
        return RealtimeIndicatorCalculator()

    def test_vwap_calculation(self, calculator):
        calculator.update('005930', {
            'high': 70500,
            'low': 69500,
            'close': 70000,
            'volume': 1000,
        })

        vwap = calculator.get_indicator('005930', IndicatorType.VWAP)
        assert vwap is not None
        assert vwap.value > 0

    def test_vwap_reset(self, calculator):
        calculator.update('005930', {
            'high': 70500,
            'low': 69500,
            'close': 70000,
            'volume': 1000,
        })

        calculator.reset_vwap('005930')

        assert calculator._vwap_cache['005930']['cumulative_vol'] == 0


class TestSignalSummary:
    """신호 요약 테스트"""

    @pytest.fixture
    def calculator_with_data(self):
        calc = RealtimeIndicatorCalculator()
        for i in range(30):
            calc.update('005930', {
                'open': 70000 + i * 50,
                'high': 70100 + i * 50,
                'low': 69900 + i * 50,
                'close': 70000 + i * 100,  # 상승 추세
                'volume': 1000 + i * 10,
            })
        return calc

    def test_signal_summary(self, calculator_with_data):
        summary = calculator_with_data.get_signal_summary('005930')
        assert 'signal' in summary
        assert summary['signal'] in ['BULLISH', 'BEARISH', 'NEUTRAL']
        assert 'strength' in summary
        assert 'reasons' in summary

    def test_signal_summary_no_data(self):
        calc = RealtimeIndicatorCalculator()
        summary = calc.get_signal_summary('UNKNOWN')
        assert summary['signal'] == 'NEUTRAL'
        assert summary['strength'] == 0


class TestClear:
    """클리어 기능 테스트"""

    @pytest.fixture
    def calculator_with_data(self):
        calc = RealtimeIndicatorCalculator()
        for i in range(20):
            calc.update('005930', {'close': 70000 + i, 'volume': 1000})
            calc.update('000660', {'close': 150000 + i, 'volume': 500})
        return calc

    def test_clear_specific_stock(self, calculator_with_data):
        calculator_with_data.clear('005930')
        assert '005930' not in calculator_with_data._close_history
        assert '000660' in calculator_with_data._close_history

    def test_clear_all(self, calculator_with_data):
        calculator_with_data.clear()
        assert len(calculator_with_data._close_history) == 0
        assert len(calculator_with_data._indicators) == 0


class TestIndicatorValue:
    """IndicatorValue 데이터클래스 테스트"""

    def test_indicator_value_creation(self):
        iv = IndicatorValue(
            indicator_type=IndicatorType.RSI,
            value=50.5,
            metadata={'period': 14}
        )
        assert iv.indicator_type == IndicatorType.RSI
        assert iv.value == 50.5
        assert iv.metadata['period'] == 14
        assert isinstance(iv.timestamp, datetime)


class TestIndicatorConfig:
    """IndicatorConfig 데이터클래스 테스트"""

    def test_default_config(self):
        config = IndicatorConfig()
        assert config.rsi_period == 14
        assert config.ma_short_period == 5
        assert config.macd_fast == 12

    def test_custom_config(self):
        config = IndicatorConfig(rsi_period=7, bollinger_std=2.5)
        assert config.rsi_period == 7
        assert config.bollinger_std == 2.5


class TestEdgeCases:
    """엣지 케이스 테스트"""

    @pytest.fixture
    def calculator(self):
        return RealtimeIndicatorCalculator()

    def test_zero_volume(self, calculator):
        calculator.update('005930', {'close': 70000, 'volume': 0})
        # 오류 없이 처리되어야 함
        assert '005930' in calculator._close_history

    def test_same_prices(self, calculator):
        for _ in range(20):
            calculator.update('005930', {'close': 70000, 'volume': 1000})

        # RSI는 50에 가까워야 함 (변화 없음)
        rsi = calculator.get_indicator('005930', IndicatorType.RSI)
        if rsi:
            assert 45 <= rsi.value <= 55

    def test_missing_ohlc_uses_close(self, calculator):
        # close만 있는 경우 처리
        calculator.update('005930', {'price': 70000, 'volume': 1000})
        assert len(calculator._price_history['005930']) == 1
