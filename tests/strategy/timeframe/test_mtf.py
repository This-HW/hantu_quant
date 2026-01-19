"""
멀티타임프레임 분석 시스템 테스트

MTFAnalyzer, TrendAligner, EntryOptimizer 테스트
"""

import pytest
import pandas as pd
import numpy as np

from core.strategy.timeframe import (
    MTFAnalyzer, TimeframeData, MTFConfig,
    TrendAligner, TrendDirection, TrendAnalysis,
    EntryOptimizer, EntrySignal, SupportResistance
)
from core.strategy.timeframe.mtf_analyzer import Timeframe


# ========== Fixtures ==========

@pytest.fixture
def uptrend_data():
    """상승 추세 일봉 데이터 (1년치)"""
    np.random.seed(42)
    n = 365

    dates = pd.date_range(start='2024-01-01', periods=n, freq='D')
    base_price = 50000

    prices = []
    price = base_price
    for i in range(n):
        # 상승 추세 + 노이즈
        trend = 30 + np.sin(i / 30) * 10
        noise = np.random.randn() * 300
        price = max(price + trend + noise, 10000)
        prices.append(price)

    close = np.array(prices)
    high = close * (1 + np.abs(np.random.randn(n) * 0.015))
    low = close * (1 - np.abs(np.random.randn(n) * 0.015))
    open_price = (high + low) / 2 + np.random.randn(n) * 50
    volume = np.random.randint(500000, 2000000, n)

    return pd.DataFrame({
        'open': open_price,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume
    }, index=dates)


@pytest.fixture
def downtrend_data():
    """하락 추세 일봉 데이터 (1년치)"""
    np.random.seed(123)
    n = 365

    dates = pd.date_range(start='2024-01-01', periods=n, freq='D')
    base_price = 80000

    prices = []
    price = base_price
    for i in range(n):
        trend = -25 + np.cos(i / 30) * 10
        noise = np.random.randn() * 300
        price = max(price + trend + noise, 30000)
        prices.append(price)

    close = np.array(prices)
    high = close * (1 + np.abs(np.random.randn(n) * 0.015))
    low = close * (1 - np.abs(np.random.randn(n) * 0.015))
    open_price = (high + low) / 2 + np.random.randn(n) * 50
    volume = np.random.randint(500000, 2000000, n)

    return pd.DataFrame({
        'open': open_price,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume
    }, index=dates)


@pytest.fixture
def sideways_data():
    """횡보 데이터 (1년치)"""
    np.random.seed(456)
    n = 365

    dates = pd.date_range(start='2024-01-01', periods=n, freq='D')
    base_price = 50000

    prices = []
    price = base_price
    for i in range(n):
        # 횡보: 평균 회귀
        mean_reversion = (base_price - price) * 0.05
        noise = np.random.randn() * 500
        price = max(price + mean_reversion + noise, 40000)
        price = min(price, 60000)
        prices.append(price)

    close = np.array(prices)
    high = close * (1 + np.abs(np.random.randn(n) * 0.02))
    low = close * (1 - np.abs(np.random.randn(n) * 0.02))
    open_price = (high + low) / 2 + np.random.randn(n) * 50
    volume = np.random.randint(300000, 1000000, n)

    return pd.DataFrame({
        'open': open_price,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume
    }, index=dates)


@pytest.fixture
def short_data():
    """짧은 데이터 (50일)"""
    np.random.seed(789)
    n = 50

    dates = pd.date_range(start='2024-01-01', periods=n, freq='D')
    base_price = 50000

    close = base_price + np.cumsum(np.random.randn(n) * 200)
    high = close * 1.01
    low = close * 0.99
    open_price = (high + low) / 2
    volume = np.random.randint(100000, 500000, n)

    return pd.DataFrame({
        'open': open_price,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume
    }, index=dates)


# ========== MTFAnalyzer Tests ==========

class TestMTFAnalyzer:
    """MTFAnalyzer 테스트"""

    def test_analyzer_creation(self):
        """분석기 생성 테스트"""
        config = MTFConfig(daily_ma_short=10, daily_ma_long=50)
        analyzer = MTFAnalyzer(config)

        assert analyzer.config.daily_ma_short == 10
        assert analyzer.config.daily_ma_long == 50

    def test_analyze_uptrend(self, uptrend_data):
        """상승 추세 분석 테스트"""
        analyzer = MTFAnalyzer()
        result = analyzer.analyze(uptrend_data)

        assert Timeframe.DAILY in result
        assert Timeframe.WEEKLY in result
        assert Timeframe.MONTHLY in result

        daily = result[Timeframe.DAILY]
        assert isinstance(daily, TimeframeData)

    def test_analyze_downtrend(self, downtrend_data):
        """하락 추세 분석 테스트"""
        analyzer = MTFAnalyzer()
        result = analyzer.analyze(downtrend_data)

        daily = result[Timeframe.DAILY]
        # 하락 추세는 -1
        assert daily.trend_direction <= 0

    def test_alignment_score_uptrend(self, uptrend_data):
        """상승 추세 정렬 점수 테스트"""
        analyzer = MTFAnalyzer()
        result = analyzer.analyze(uptrend_data)
        score = analyzer.calculate_alignment_score(result)

        # 정렬 점수는 0~1
        assert 0.0 <= score <= 1.0

    def test_alignment_score_sideways(self, sideways_data):
        """횡보 정렬 점수 테스트"""
        analyzer = MTFAnalyzer()
        result = analyzer.analyze(sideways_data)
        score = analyzer.calculate_alignment_score(result)

        assert 0.0 <= score <= 1.0

    def test_dominant_trend(self, uptrend_data):
        """지배적 추세 테스트"""
        analyzer = MTFAnalyzer()
        result = analyzer.analyze(uptrend_data)
        direction, strength = analyzer.get_dominant_trend(result)

        # 방향: -1, 0, 1
        assert direction in [-1, 0, 1]
        # 강도: 0~1
        assert 0.0 <= strength <= 1.0

    def test_timeframe_summary(self, uptrend_data):
        """타임프레임 요약 테스트"""
        analyzer = MTFAnalyzer()
        result = analyzer.analyze(uptrend_data)
        summary = analyzer.get_timeframe_summary(result)

        assert 'dominant_trend' in summary
        assert 'trend_strength' in summary
        assert 'alignment_score' in summary
        assert 'timeframes' in summary
        assert 'recommendation' in summary

    def test_short_data_handling(self, short_data):
        """짧은 데이터 처리 테스트"""
        analyzer = MTFAnalyzer()
        result = analyzer.analyze(short_data)

        # 데이터 부족해도 에러 없이 처리
        assert Timeframe.DAILY in result


# ========== TrendAligner Tests ==========

class TestTrendAligner:
    """TrendAligner 테스트"""

    def test_aligner_creation(self):
        """정렬기 생성 테스트"""
        aligner = TrendAligner(ma_short=10, ma_long=100)
        assert aligner.ma_short == 10
        assert aligner.ma_long == 100

    def test_analyze_trend_uptrend(self, uptrend_data):
        """상승 추세 분석 테스트"""
        aligner = TrendAligner()
        analysis = aligner.analyze_trend(uptrend_data)

        assert isinstance(analysis, TrendAnalysis)
        assert isinstance(analysis.direction, TrendDirection)

    def test_analyze_trend_downtrend(self, downtrend_data):
        """하락 추세 분석 테스트"""
        aligner = TrendAligner()
        analysis = aligner.analyze_trend(downtrend_data)

        # 하락 추세
        assert analysis.direction.value <= 0

    def test_trend_strength(self, uptrend_data):
        """추세 강도 테스트"""
        aligner = TrendAligner()
        analysis = aligner.analyze_trend(uptrend_data)

        assert 0.0 <= analysis.strength <= 1.0

    def test_align_trends(self, uptrend_data, downtrend_data):
        """추세 정렬 테스트"""
        aligner = TrendAligner()

        # 같은 방향 추세
        up_trend = aligner.analyze_trend(uptrend_data)
        aligner.analyze_trend(downtrend_data)

        alignment = aligner.align_trends({
            'daily': up_trend,
            'weekly': up_trend,
        })

        assert isinstance(alignment.score, float)
        assert 0.0 <= alignment.score <= 1.0

    def test_conflicting_trends(self, uptrend_data, downtrend_data):
        """상충 추세 정렬 테스트"""
        aligner = TrendAligner()

        up_trend = aligner.analyze_trend(uptrend_data)
        down_trend = aligner.analyze_trend(downtrend_data)

        alignment = aligner.align_trends({
            'daily': up_trend,
            'weekly': down_trend,
        })

        # 상충 시 낮은 점수
        assert alignment.score < 0.7

    def test_entry_quality(self, uptrend_data):
        """진입 품질 점수 테스트"""
        aligner = TrendAligner()

        daily_trend = aligner.analyze_trend(uptrend_data)

        quality = aligner.get_entry_quality(daily_trend, daily_trend)

        assert 0.0 <= quality <= 1.0

    def test_ma_cross_detection(self, uptrend_data):
        """이동평균 크로스 감지 테스트"""
        aligner = TrendAligner()
        analysis = aligner.analyze_trend(uptrend_data)

        # 크로스: -1, 0, 1
        assert analysis.ma_cross_signal in [-1, 0, 1]

    def test_trend_analysis_dict(self, uptrend_data):
        """추세 분석 딕셔너리 변환 테스트"""
        aligner = TrendAligner()
        analysis = aligner.analyze_trend(uptrend_data)

        d = analysis.to_dict()

        assert 'direction' in d
        assert 'strength' in d
        assert 'slope' in d


# ========== EntryOptimizer Tests ==========

class TestEntryOptimizer:
    """EntryOptimizer 테스트"""

    def test_optimizer_creation(self):
        """최적화기 생성 테스트"""
        optimizer = EntryOptimizer(atr_period=14, min_risk_reward=1.5)
        assert optimizer.atr_period == 14
        assert optimizer.min_risk_reward == 1.5

    def test_find_support_resistance(self, uptrend_data):
        """지지/저항선 탐색 테스트"""
        optimizer = EntryOptimizer()
        sr = optimizer.find_support_resistance(uptrend_data)

        assert isinstance(sr, SupportResistance)
        assert sr.nearest_support > 0
        assert sr.nearest_resistance > 0
        assert sr.nearest_support < sr.nearest_resistance

    def test_detect_candle_pattern(self, uptrend_data):
        """캔들 패턴 감지 테스트"""
        optimizer = EntryOptimizer()

        from core.strategy.timeframe.entry_optimizer import CandlePattern
        pattern = optimizer.detect_candle_pattern(uptrend_data)

        assert isinstance(pattern, CandlePattern)

    def test_optimize_entry_uptrend(self, uptrend_data):
        """상승 추세 진입 최적화 테스트"""
        optimizer = EntryOptimizer()

        signal = optimizer.optimize_entry(
            uptrend_data,
            TrendDirection.BULL,
            alignment_score=0.8
        )

        assert isinstance(signal, EntrySignal)

    def test_optimize_entry_downtrend(self, downtrend_data):
        """하락 추세 진입 최적화 테스트"""
        optimizer = EntryOptimizer()

        signal = optimizer.optimize_entry(
            downtrend_data,
            TrendDirection.BEAR,
            alignment_score=0.8
        )

        assert isinstance(signal, EntrySignal)

    def test_optimize_entry_neutral(self, sideways_data):
        """횡보 진입 최적화 테스트"""
        optimizer = EntryOptimizer()

        signal = optimizer.optimize_entry(
            sideways_data,
            TrendDirection.NEUTRAL,
            alignment_score=0.5
        )

        # 중립 추세에서는 진입 안함
        assert signal.direction == 0

    def test_entry_signal_risk_reward(self, uptrend_data):
        """진입 신호 손익비 테스트"""
        optimizer = EntryOptimizer(min_risk_reward=1.5)

        signal = optimizer.optimize_entry(
            uptrend_data,
            TrendDirection.STRONG_BULL,
            alignment_score=0.9
        )

        if signal.direction != 0:
            assert signal.risk_reward_ratio >= 1.5

    def test_entry_signal_dict(self, uptrend_data):
        """진입 신호 딕셔너리 변환 테스트"""
        optimizer = EntryOptimizer()

        signal = optimizer.optimize_entry(
            uptrend_data,
            TrendDirection.BULL,
            alignment_score=0.7
        )

        d = signal.to_dict()

        assert 'direction' in d
        assert 'entry_price' in d
        assert 'stop_loss' in d
        assert 'take_profit' in d
        assert 'confidence' in d

    def test_support_resistance_dict(self, uptrend_data):
        """지지/저항선 딕셔너리 변환 테스트"""
        optimizer = EntryOptimizer()
        sr = optimizer.find_support_resistance(uptrend_data)

        d = sr.to_dict()

        assert 'support_levels' in d
        assert 'resistance_levels' in d
        assert 'nearest_support' in d


# ========== Integration Tests ==========

class TestMTFIntegration:
    """MTF 통합 테스트"""

    def test_full_analysis_pipeline(self, uptrend_data):
        """전체 분석 파이프라인 테스트"""
        # 1. MTF 분석
        mtf_analyzer = MTFAnalyzer()
        mtf_result = mtf_analyzer.analyze(uptrend_data)
        alignment_score = mtf_analyzer.calculate_alignment_score(mtf_result)

        # 2. 추세 정렬
        aligner = TrendAligner()
        daily_trend = aligner.analyze_trend(uptrend_data)

        # 3. 진입 최적화
        optimizer = EntryOptimizer()
        entry_signal = optimizer.optimize_entry(
            uptrend_data,
            daily_trend.direction,
            alignment_score
        )

        # 결과 검증
        assert alignment_score >= 0.0
        assert daily_trend.direction is not None
        assert entry_signal is not None

    def test_multi_stock_analysis(self, uptrend_data, downtrend_data):
        """다중 종목 분석 테스트"""
        mtf_analyzer = MTFAnalyzer()
        aligner = TrendAligner()
        optimizer = EntryOptimizer()

        stocks = {
            '005930': uptrend_data,
            '000660': downtrend_data,
        }

        results = {}

        for code, data in stocks.items():
            mtf_result = mtf_analyzer.analyze(data)
            alignment = mtf_analyzer.calculate_alignment_score(mtf_result)
            trend = aligner.analyze_trend(data)
            entry = optimizer.optimize_entry(data, trend.direction, alignment)

            results[code] = {
                'alignment': alignment,
                'trend': trend.direction.name,
                'entry': entry.direction,
            }

        assert len(results) == 2
        assert '005930' in results
        assert '000660' in results

    def test_signal_quality_correlation(self, uptrend_data, sideways_data):
        """신호 품질 상관관계 테스트"""
        mtf_analyzer = MTFAnalyzer()
        optimizer = EntryOptimizer()

        # 상승 추세 분석
        up_mtf = mtf_analyzer.analyze(uptrend_data)
        up_alignment = mtf_analyzer.calculate_alignment_score(up_mtf)

        # 횡보 분석
        side_mtf = mtf_analyzer.analyze(sideways_data)
        side_alignment = mtf_analyzer.calculate_alignment_score(side_mtf)

        # 정렬이 잘 된 경우가 더 높은 점수를 받아야 함
        up_entry = optimizer.optimize_entry(
            uptrend_data,
            TrendDirection.BULL,
            up_alignment
        )

        side_entry = optimizer.optimize_entry(
            sideways_data,
            TrendDirection.NEUTRAL,
            side_alignment
        )

        # 상승 추세의 품질이 더 높아야 함 (강한 추세이므로)
        assert up_entry.quality_score >= side_entry.quality_score


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
