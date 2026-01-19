"""
ATR 기반 동적 손절/익절 시스템 테스트 (P1-1)

테스트 항목:
1. ATR 계산 정확성
2. 동적 손절/익절 계산
3. 손절 비율 제한 적용
4. 트레일링 스탑 기능
5. 시장 상황별 배수 조정
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from core.trading.dynamic_stop_loss import (
    DynamicStopLossCalculator,
    StopLossResult,
    TrailingStopState,
    calculate_dynamic_stops,
    calculate_atr,
)


def create_sample_ohlcv(
    days: int = 30, base_price: int = 50000, volatility: float = 0.02
) -> pd.DataFrame:
    """테스트용 OHLCV 데이터 생성"""
    np.random.seed(42)
    dates = [datetime.now() - timedelta(days=i) for i in range(days, 0, -1)]

    prices = [base_price]
    for _ in range(days - 1):
        change = np.random.normal(0, volatility)
        prices.append(int(prices[-1] * (1 + change)))

    data = {
        "date": dates,
        "open": prices,
        "high": [int(p * (1 + np.random.uniform(0, 0.02))) for p in prices],
        "low": [int(p * (1 - np.random.uniform(0, 0.02))) for p in prices],
        "close": prices,
        "volume": [np.random.randint(100000, 1000000) for _ in range(days)],
    }

    return pd.DataFrame(data)


class TestATRCalculation:
    """ATR 계산 테스트"""

    def test_atr_basic(self):
        """기본 ATR 계산 테스트"""
        df = create_sample_ohlcv(days=30)
        calculator = DynamicStopLossCalculator(atr_period=14)

        atr = calculator.calculate_atr(df)

        assert atr > 0
        assert isinstance(atr, float)

    def test_atr_insufficient_data(self):
        """데이터 부족 시 ATR 0 반환"""
        df = create_sample_ohlcv(days=10)  # 14일 미만
        calculator = DynamicStopLossCalculator(atr_period=14)

        atr = calculator.calculate_atr(df)

        assert atr == 0.0

    def test_atr_with_high_volatility(self):
        """고변동성 데이터 ATR 테스트"""
        df = create_sample_ohlcv(days=30, volatility=0.05)  # 5% 변동성
        calculator = DynamicStopLossCalculator(atr_period=14)

        atr_high = calculator.calculate_atr(df)

        df_low = create_sample_ohlcv(days=30, volatility=0.01)  # 1% 변동성
        atr_low = calculator.calculate_atr(df_low)

        # 고변동성 ATR이 저변동성 ATR보다 커야 함
        assert atr_high > atr_low

    def test_atr_from_prices(self):
        """가격 리스트로부터 ATR 계산"""
        calculator = DynamicStopLossCalculator(atr_period=14)

        high = [100 + i for i in range(20)]
        low = [90 + i for i in range(20)]
        close = [95 + i for i in range(20)]

        atr = calculator.calculate_atr_from_prices(high, low, close)

        assert atr > 0

    def test_convenience_function(self):
        """편의 함수 calculate_atr 테스트"""
        df = create_sample_ohlcv(days=30)

        atr = calculate_atr(df, period=14)

        assert atr > 0


class TestDynamicStopCalculation:
    """동적 손절/익절 계산 테스트"""

    def test_basic_stop_calculation(self):
        """기본 손절/익절 계산"""
        df = create_sample_ohlcv(days=30)
        calculator = DynamicStopLossCalculator(
            atr_period=14, stop_multiplier=2.0, profit_multiplier=3.0
        )
        entry_price = 50000

        result = calculator.get_stops(entry_price, df)

        assert isinstance(result, StopLossResult)
        assert result.entry_price == entry_price
        assert result.stop_loss < entry_price
        assert result.take_profit > entry_price
        assert result.atr > 0

    def test_stop_loss_below_entry(self):
        """손절가는 항상 진입가 아래"""
        df = create_sample_ohlcv(days=30)
        calculator = DynamicStopLossCalculator()

        for entry_price in [10000, 50000, 100000]:
            result = calculator.get_stops(entry_price, df)
            assert result.stop_loss < entry_price

    def test_take_profit_above_entry(self):
        """익절가는 항상 진입가 위"""
        df = create_sample_ohlcv(days=30)
        calculator = DynamicStopLossCalculator()

        for entry_price in [10000, 50000, 100000]:
            result = calculator.get_stops(entry_price, df)
            assert result.take_profit > entry_price

    def test_risk_reward_ratio(self):
        """손익비 계산 테스트"""
        df = create_sample_ohlcv(days=30)
        calculator = DynamicStopLossCalculator(
            stop_multiplier=2.0, profit_multiplier=3.0  # 기대 손익비 = 3/2 = 1.5
        )

        result = calculator.get_stops(50000, df)

        # 손익비 = 익절거리 / 손절거리
        assert result.risk_reward_ratio > 1.0

    def test_custom_multipliers(self):
        """커스텀 배수 테스트"""
        df = create_sample_ohlcv(days=30)
        calculator = DynamicStopLossCalculator()
        entry_price = 50000

        result_default = calculator.get_stops(entry_price, df)
        result_custom = calculator.get_stops(
            entry_price, df, custom_stop_mult=1.5, custom_profit_mult=4.0
        )

        # 커스텀 배수로 다른 결과 생성
        assert (
            result_default.stop_loss != result_custom.stop_loss
            or result_default.take_profit != result_custom.take_profit
        )


class TestStopLossLimits:
    """손절 비율 제한 테스트"""

    def test_min_stop_limit(self):
        """최소 손절 비율 제한 테스트"""
        # 매우 낮은 변동성으로 작은 ATR 생성
        df = create_sample_ohlcv(days=30, volatility=0.001)
        calculator = DynamicStopLossCalculator(
            min_stop_pct=0.02, stop_multiplier=1.0  # 최소 2%  # 낮은 배수
        )
        entry_price = 50000

        result = calculator.get_stops(entry_price, df)

        # 손절 비율이 최소 2% 이상
        actual_stop_pct = (entry_price - result.stop_loss) / entry_price
        assert actual_stop_pct >= 0.02 or abs(actual_stop_pct - 0.02) < 0.001

    def test_max_stop_limit(self):
        """최대 손절 비율 제한 테스트"""
        # 매우 높은 변동성으로 큰 ATR 생성
        df = create_sample_ohlcv(days=30, volatility=0.10)  # 10% 변동성
        calculator = DynamicStopLossCalculator(
            max_stop_pct=0.10, stop_multiplier=5.0  # 최대 10%  # 높은 배수
        )
        entry_price = 50000

        result = calculator.get_stops(entry_price, df)

        # 손절 비율이 최대 10% 이하
        actual_stop_pct = (entry_price - result.stop_loss) / entry_price
        assert actual_stop_pct <= 0.10 + 0.001  # 약간의 오차 허용


class TestTrailingStop:
    """트레일링 스탑 테스트"""

    def test_trailing_stop_init(self):
        """트레일링 스탑 초기화"""
        df = create_sample_ohlcv(days=30)
        calculator = DynamicStopLossCalculator()

        state = calculator.init_trailing_stop("005930", 50000, df)

        assert isinstance(state, TrailingStopState)
        assert state.stock_code == "005930"
        assert state.entry_price == 50000
        assert state.highest_price == 50000
        assert state.current_stop == state.initial_stop
        assert not state.is_activated

    def test_trailing_stop_activation(self):
        """트레일링 스탑 활성화 테스트"""
        df = create_sample_ohlcv(days=30)
        calculator = DynamicStopLossCalculator()

        calculator.init_trailing_stop(
            "005930", 50000, df, activation_threshold=0.02  # 2% 수익 시 활성화
        )

        # 2% 미만 상승 - 아직 비활성화
        new_stop, triggered = calculator.update_trailing_stop("005930", 50500)
        state = calculator.get_trailing_state("005930")
        assert not state.is_activated

        # 2% 이상 상승 - 활성화
        new_stop, triggered = calculator.update_trailing_stop("005930", 51000)
        state = calculator.get_trailing_state("005930")
        assert state.is_activated

    def test_trailing_stop_adjustment(self):
        """트레일링 스탑 조정 테스트"""
        df = create_sample_ohlcv(days=30)
        calculator = DynamicStopLossCalculator(trailing_multiplier=1.5)

        state = calculator.init_trailing_stop(
            "005930", 50000, df, activation_threshold=0.01
        )
        initial_stop = state.current_stop

        # 활성화 후 신고가 갱신
        calculator.update_trailing_stop("005930", 51000)  # 활성화
        calculator.update_trailing_stop("005930", 55000)  # 신고가

        state = calculator.get_trailing_state("005930")

        # 손절가가 올라갔어야 함
        assert state.current_stop > initial_stop
        assert state.highest_price == 55000

    def test_trailing_stop_trigger(self):
        """트레일링 스탑 트리거 테스트"""
        df = create_sample_ohlcv(days=30, volatility=0.01)  # 낮은 변동성
        calculator = DynamicStopLossCalculator(trailing_multiplier=1.0)

        state = calculator.init_trailing_stop(
            "005930", 50000, df, activation_threshold=0.01
        )

        # 손절가 아래로 하락
        trigger_price = state.current_stop - 100
        new_stop, triggered = calculator.update_trailing_stop("005930", trigger_price)

        assert triggered

    def test_trailing_stop_never_goes_down(self):
        """트레일링 손절가는 내려가지 않음"""
        df = create_sample_ohlcv(days=30)
        calculator = DynamicStopLossCalculator()

        calculator.init_trailing_stop("005930", 50000, df, activation_threshold=0.01)

        # 상승 후 하락
        calculator.update_trailing_stop("005930", 55000)  # 상승
        state_after_up = calculator.get_trailing_state("005930")
        stop_after_up = state_after_up.current_stop

        calculator.update_trailing_stop("005930", 52000)  # 하락 (손절 미달)
        state_after_down = calculator.get_trailing_state("005930")
        stop_after_down = state_after_down.current_stop

        # 손절가는 유지되어야 함
        assert stop_after_down >= stop_after_up

    def test_remove_trailing_state(self):
        """트레일링 스탑 상태 제거"""
        df = create_sample_ohlcv(days=30)
        calculator = DynamicStopLossCalculator()

        calculator.init_trailing_stop("005930", 50000, df)
        assert calculator.get_trailing_state("005930") is not None

        result = calculator.remove_trailing_state("005930")
        assert result
        assert calculator.get_trailing_state("005930") is None


class TestMarketAdjustedMultipliers:
    """시장 상황별 배수 조정 테스트"""

    def test_volatility_configs(self):
        """변동성별 설정 테스트"""
        calculator = DynamicStopLossCalculator()

        configs = {
            "very_low": (1.5, 2.5, 1.0),
            "low": (1.8, 2.8, 1.2),
            "normal": (2.0, 3.0, 1.5),
            "high": (2.5, 3.5, 2.0),
            "very_high": (3.0, 4.0, 2.5),
        }

        for volatility, expected in configs.items():
            result = calculator.get_market_adjusted_multipliers(volatility)
            assert result == expected

    def test_high_volatility_wider_stops(self):
        """고변동성 시장에서 더 넓은 손절"""
        calculator = DynamicStopLossCalculator()

        normal_mult = calculator.get_market_adjusted_multipliers("normal")
        high_mult = calculator.get_market_adjusted_multipliers("high")

        # 고변동성에서 더 큰 손절 배수
        assert high_mult[0] > normal_mult[0]


class TestConvenienceFunctions:
    """편의 함수 테스트"""

    def test_calculate_dynamic_stops(self):
        """calculate_dynamic_stops 함수 테스트"""
        df = create_sample_ohlcv(days=30)

        result = calculate_dynamic_stops(
            entry_price=50000,
            df=df,
            atr_period=14,
            stop_multiplier=2.0,
            profit_multiplier=3.0,
        )

        assert isinstance(result, StopLossResult)
        assert result.stop_loss < 50000
        assert result.take_profit > 50000


class TestEdgeCases:
    """엣지 케이스 테스트"""

    def test_zero_atr_fallback(self):
        """ATR 0인 경우 기본값 폴백"""
        calculator = DynamicStopLossCalculator()

        # ATR 0으로 직접 계산
        result = calculator.get_stops_from_atr(50000, 0.0)

        # 기본 비율 (3%, 8%) 적용되어야 함
        assert result.stop_loss == int(50000 * 0.97)
        assert result.take_profit == int(50000 * 1.08)

    def test_empty_dataframe(self):
        """빈 데이터프레임 처리"""
        calculator = DynamicStopLossCalculator()
        df = pd.DataFrame()

        atr = calculator.calculate_atr(df)
        assert atr == 0.0

    def test_none_dataframe(self):
        """None 데이터프레임 처리"""
        calculator = DynamicStopLossCalculator()

        atr = calculator.calculate_atr(None)
        assert atr == 0.0

    def test_very_low_entry_price(self):
        """매우 낮은 진입가 처리"""
        df = create_sample_ohlcv(days=30, base_price=1000)
        calculator = DynamicStopLossCalculator()

        result = calculator.get_stops(1000, df)

        assert result.stop_loss > 0
        assert result.take_profit > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
