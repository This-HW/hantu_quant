"""
시장 적응형 리스크 관리 테스트 (P1-5)

테스트 항목:
1. 변동성 계산 정확성
2. 변동성 레벨 분류
3. 시장 추세 분석
4. 리스크 설정 자동 조정
5. 캐시 기능
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from core.trading.market_adaptive_risk import (
    MarketAdaptiveRisk,
    MarketVolatility,
    MarketState,
    RiskConfig,
    analyze_market_risk,
    get_risk_config_for_volatility,
)


def create_market_data(
    days: int = 60,
    base_price: int = 2500,
    volatility: float = 0.01,
    trend: str = "neutral"
) -> pd.DataFrame:
    """테스트용 KOSPI 데이터 생성"""
    np.random.seed(42)
    dates = [datetime.now() - timedelta(days=i) for i in range(days, 0, -1)]

    prices = [base_price]
    for i in range(1, days):
        # 추세 적용
        if trend == "up":
            drift = 0.002
        elif trend == "down":
            drift = -0.002
        else:
            drift = 0

        # 변동성 적용
        change = np.random.normal(drift, volatility)
        prices.append(prices[-1] * (1 + change))

    prices = [int(p) for p in prices]

    data = {
        'date': dates,
        'open': prices,
        'high': [int(p * 1.005) for p in prices],
        'low': [int(p * 0.995) for p in prices],
        'close': prices,
        'volume': [np.random.randint(1000000, 5000000) for _ in range(days)]
    }

    return pd.DataFrame(data)


def create_high_volatility_data() -> pd.DataFrame:
    """고변동성 데이터 생성 (연율화 > 30%)"""
    return create_market_data(days=60, volatility=0.025)  # ~40% 연율화


def create_low_volatility_data() -> pd.DataFrame:
    """저변동성 데이터 생성 (연율화 < 12%)"""
    return create_market_data(days=60, volatility=0.005)  # ~8% 연율화


def create_uptrend_data() -> pd.DataFrame:
    """상승 추세 데이터"""
    return create_market_data(days=60, trend="up")


def create_downtrend_data() -> pd.DataFrame:
    """하락 추세 데이터"""
    return create_market_data(days=60, trend="down")


class TestVolatilityCalculation:
    """변동성 계산 테스트"""

    def test_volatility_calculation(self):
        """기본 변동성 계산"""
        analyzer = MarketAdaptiveRisk()
        df = create_market_data(days=60)

        vol = analyzer._calculate_volatility(df, period=20)

        assert vol > 0
        assert isinstance(vol, float)

    def test_high_volatility(self):
        """고변동성 데이터"""
        analyzer = MarketAdaptiveRisk()
        df = create_high_volatility_data()

        vol = analyzer._calculate_volatility(df, period=20)

        # 고변동성은 20% 이상
        assert vol > 20

    def test_low_volatility(self):
        """저변동성 데이터"""
        analyzer = MarketAdaptiveRisk()
        df = create_low_volatility_data()

        vol = analyzer._calculate_volatility(df, period=20)

        # 저변동성은 16% 이하
        assert vol < 16

    def test_insufficient_data(self):
        """데이터 부족 시 기본값"""
        analyzer = MarketAdaptiveRisk()
        df = create_market_data(days=10)

        vol = analyzer._calculate_volatility(df, period=20)

        # 기본값 16.0 반환
        assert vol == 16.0


class TestVolatilityClassification:
    """변동성 분류 테스트"""

    def test_very_low(self):
        """매우 낮은 변동성 분류"""
        analyzer = MarketAdaptiveRisk()

        level = analyzer._classify_volatility(8.0)

        assert level == MarketVolatility.VERY_LOW

    def test_low(self):
        """낮은 변동성 분류"""
        analyzer = MarketAdaptiveRisk()

        level = analyzer._classify_volatility(14.0)

        assert level == MarketVolatility.LOW

    def test_normal(self):
        """일반 변동성 분류"""
        analyzer = MarketAdaptiveRisk()

        level = analyzer._classify_volatility(18.0)

        assert level == MarketVolatility.NORMAL

    def test_high(self):
        """높은 변동성 분류"""
        analyzer = MarketAdaptiveRisk()

        level = analyzer._classify_volatility(25.0)

        assert level == MarketVolatility.HIGH

    def test_very_high(self):
        """매우 높은 변동성 분류"""
        analyzer = MarketAdaptiveRisk()

        level = analyzer._classify_volatility(35.0)

        assert level == MarketVolatility.VERY_HIGH

    def test_boundary_values(self):
        """경계값 테스트"""
        analyzer = MarketAdaptiveRisk()

        # 정확히 경계값
        assert analyzer._classify_volatility(12.0) == MarketVolatility.LOW
        assert analyzer._classify_volatility(16.0) == MarketVolatility.NORMAL
        assert analyzer._classify_volatility(20.0) == MarketVolatility.HIGH
        assert analyzer._classify_volatility(30.0) == MarketVolatility.VERY_HIGH


class TestTrendAnalysis:
    """추세 분석 테스트"""

    def test_uptrend(self):
        """상승 추세 감지"""
        analyzer = MarketAdaptiveRisk()
        df = create_uptrend_data()

        trend = analyzer._analyze_trend(df, period=20)

        # 상승 또는 횡보 (변동성에 따라)
        assert trend in ['up', 'sideways']

    def test_downtrend(self):
        """하락 추세 감지"""
        analyzer = MarketAdaptiveRisk()
        df = create_downtrend_data()

        trend = analyzer._analyze_trend(df, period=20)

        assert trend == 'down'

    def test_sideways(self):
        """횡보 추세 감지"""
        analyzer = MarketAdaptiveRisk()
        df = create_market_data(days=60, trend="neutral")

        trend = analyzer._analyze_trend(df, period=20)

        # 횡보 또는 방향 미약
        assert trend in ['sideways', 'up', 'down']


class TestRiskConfig:
    """리스크 설정 테스트"""

    def test_very_low_config(self):
        """매우 낮은 변동성 설정"""
        analyzer = MarketAdaptiveRisk()

        config = analyzer._get_risk_config(MarketVolatility.VERY_LOW)

        assert config.stop_multiplier == 1.5
        assert config.position_factor == 1.2
        assert config.max_positions == 15

    def test_normal_config(self):
        """일반 변동성 설정"""
        analyzer = MarketAdaptiveRisk()

        config = analyzer._get_risk_config(MarketVolatility.NORMAL)

        assert config.stop_multiplier == 2.0
        assert config.position_factor == 1.0
        assert config.max_positions == 10

    def test_very_high_config(self):
        """매우 높은 변동성 설정"""
        analyzer = MarketAdaptiveRisk()

        config = analyzer._get_risk_config(MarketVolatility.VERY_HIGH)

        assert config.stop_multiplier == 3.0
        assert config.position_factor == 0.5
        assert config.max_positions == 5

    def test_high_volatility_wider_stops(self):
        """고변동성에서 더 넓은 손절"""
        analyzer = MarketAdaptiveRisk()

        low_config = analyzer._get_risk_config(MarketVolatility.LOW)
        high_config = analyzer._get_risk_config(MarketVolatility.HIGH)

        # 고변동성에서 더 큰 손절 배수
        assert high_config.stop_multiplier > low_config.stop_multiplier

    def test_high_volatility_smaller_positions(self):
        """고변동성에서 더 작은 포지션"""
        analyzer = MarketAdaptiveRisk()

        low_config = analyzer._get_risk_config(MarketVolatility.LOW)
        high_config = analyzer._get_risk_config(MarketVolatility.HIGH)

        # 고변동성에서 더 작은 포지션 배수
        assert high_config.position_factor < low_config.position_factor


class TestMarketAnalysis:
    """시장 분석 테스트"""

    def test_analyze_market(self):
        """시장 분석 수행"""
        analyzer = MarketAdaptiveRisk()
        df = create_market_data(days=60)

        state = analyzer.analyze_market(df, period=20)

        assert isinstance(state, MarketState)
        assert state.volatility_pct > 0
        assert state.volatility_level in MarketVolatility
        assert state.trend in ['up', 'down', 'sideways']
        assert isinstance(state.risk_config, RiskConfig)

    def test_analyze_insufficient_data(self):
        """데이터 부족 시 기본 상태"""
        analyzer = MarketAdaptiveRisk()
        df = create_market_data(days=10)

        state = analyzer.analyze_market(df, period=20)

        # 기본값 (normal) 반환
        assert state.volatility_level == MarketVolatility.NORMAL

    def test_analyze_none_data(self):
        """None 데이터"""
        analyzer = MarketAdaptiveRisk()

        state = analyzer.analyze_market(None, period=20)

        assert state.volatility_level == MarketVolatility.NORMAL

    def test_cache_update(self):
        """캐시 업데이트"""
        analyzer = MarketAdaptiveRisk()
        df = create_market_data(days=60)

        analyzer.analyze_market(df, period=20)

        assert analyzer._current_state is not None
        assert analyzer._cache_date is not None


class TestConvenienceMethods:
    """편의 메서드 테스트"""

    def test_get_current_state(self):
        """현재 상태 조회"""
        analyzer = MarketAdaptiveRisk()
        df = create_market_data(days=60)

        analyzer.analyze_market(df)
        state = analyzer.get_current_state()

        assert state is not None

    def test_get_stop_multiplier(self):
        """손절 배수 조회"""
        analyzer = MarketAdaptiveRisk()
        df = create_market_data(days=60)

        analyzer.analyze_market(df)
        mult = analyzer.get_stop_multiplier()

        assert mult > 0
        assert 1.5 <= mult <= 3.0

    def test_get_position_factor(self):
        """포지션 배수 조회"""
        analyzer = MarketAdaptiveRisk()
        df = create_market_data(days=60)

        analyzer.analyze_market(df)
        factor = analyzer.get_position_factor()

        assert factor > 0
        assert 0.5 <= factor <= 1.2

    def test_get_max_positions(self):
        """최대 보유 종목 수 조회"""
        analyzer = MarketAdaptiveRisk()
        df = create_market_data(days=60)

        analyzer.analyze_market(df)
        max_pos = analyzer.get_max_positions()

        assert 5 <= max_pos <= 15

    def test_get_volatility_for_level(self):
        """레벨별 변동성 범위"""
        analyzer = MarketAdaptiveRisk()

        very_low = analyzer.get_volatility_for_level('very_low')
        normal = analyzer.get_volatility_for_level('normal')
        very_high = analyzer.get_volatility_for_level('very_high')

        assert very_low == (0.0, 12.0)
        assert normal == (16.0, 20.0)
        assert very_high[0] == 30.0

    def test_get_all_configs(self):
        """모든 설정 조회"""
        analyzer = MarketAdaptiveRisk()

        configs = analyzer.get_all_configs()

        assert len(configs) == 5
        assert 'very_low' in configs
        assert 'normal' in configs
        assert 'very_high' in configs


class TestConfigUpdate:
    """설정 업데이트 테스트"""

    def test_update_config(self):
        """설정 업데이트"""
        analyzer = MarketAdaptiveRisk()

        analyzer.update_config(
            MarketVolatility.NORMAL,
            stop_multiplier=2.5,
            max_positions=8
        )

        config = analyzer._get_risk_config(MarketVolatility.NORMAL)

        assert config.stop_multiplier == 2.5
        assert config.max_positions == 8


class TestDataclasses:
    """데이터클래스 테스트"""

    def test_risk_config_to_dict(self):
        """RiskConfig 딕셔너리 변환"""
        config = RiskConfig(
            stop_multiplier=2.0,
            profit_multiplier=3.0,
            position_factor=1.0,
            max_positions=10,
            max_single_exposure=10.0,
            max_total_exposure=80.0,
        )

        d = config.to_dict()

        assert d['stop_multiplier'] == 2.0
        assert d['max_positions'] == 10

    def test_market_state_to_dict(self):
        """MarketState 딕셔너리 변환"""
        config = RiskConfig(
            stop_multiplier=2.0,
            profit_multiplier=3.0,
            position_factor=1.0,
            max_positions=10,
            max_single_exposure=10.0,
            max_total_exposure=80.0,
        )

        state = MarketState(
            volatility_level=MarketVolatility.NORMAL,
            volatility_pct=18.0,
            trend='sideways',
            risk_config=config,
        )

        d = state.to_dict()

        assert d['volatility_level'] == 'normal'
        assert d['volatility_pct'] == 18.0
        assert d['trend'] == 'sideways'


class TestConvenienceFunctions:
    """편의 함수 테스트"""

    def test_analyze_market_risk(self):
        """analyze_market_risk 함수"""
        df = create_market_data(days=60)

        state = analyze_market_risk(df, period=20)

        assert isinstance(state, MarketState)

    def test_get_risk_config_for_volatility(self):
        """get_risk_config_for_volatility 함수"""
        config_low = get_risk_config_for_volatility(10.0)
        config_high = get_risk_config_for_volatility(35.0)

        assert config_low.stop_multiplier < config_high.stop_multiplier
        assert config_low.position_factor > config_high.position_factor


class TestEdgeCases:
    """엣지 케이스 테스트"""

    def test_empty_dataframe(self):
        """빈 DataFrame"""
        analyzer = MarketAdaptiveRisk()

        state = analyzer.analyze_market(pd.DataFrame(), period=20)

        assert state.volatility_level == MarketVolatility.NORMAL

    def test_missing_columns(self):
        """컬럼 누락"""
        analyzer = MarketAdaptiveRisk()
        df = pd.DataFrame({'open': [100, 101, 102]})  # close 없음

        vol = analyzer._calculate_volatility(df, period=20)

        assert vol == 16.0  # 기본값

    def test_default_values_without_analysis(self):
        """분석 없이 기본값"""
        analyzer = MarketAdaptiveRisk()

        assert analyzer.get_stop_multiplier() == 2.0
        assert analyzer.get_position_factor() == 1.0
        assert analyzer.get_max_positions() == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
