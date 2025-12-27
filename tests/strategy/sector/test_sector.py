"""
섹터 로테이션 전략 시스템 테스트

SectorMap, SectorAnalyzer, RotationEngine, TransitionDetector 테스트
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from core.strategy.sector import (
    SectorMap, Sector, KOSPI_SECTORS,
    SectorAnalyzer, SectorMetrics,
    RotationEngine, SectorAllocation,
    TransitionDetector, TransitionSignal
)
from core.strategy.sector.transition_detector import TransitionType


# ========== Fixtures ==========

@pytest.fixture
def sector_map():
    """테스트용 섹터 맵"""
    return SectorMap()


@pytest.fixture
def sample_stock_data():
    """샘플 종목 데이터"""
    np.random.seed(42)
    n = 180  # 6개월

    stocks = {
        # 반도체
        "005930": _generate_uptrend_data(n, 70000),  # 삼성전자
        "000660": _generate_uptrend_data(n, 150000),  # SK하이닉스
        # 자동차
        "005380": _generate_sideways_data(n, 200000),  # 현대차
        "000270": _generate_downtrend_data(n, 100000),  # 기아
        # 금융
        "105560": _generate_sideways_data(n, 60000),  # KB금융
        "055550": _generate_downtrend_data(n, 40000),  # 신한지주
        # 인터넷
        "035720": _generate_uptrend_data(n, 50000),  # 카카오
        "035420": _generate_uptrend_data(n, 200000),  # NAVER
    }

    return stocks


@pytest.fixture
def market_data():
    """시장 지수 데이터"""
    np.random.seed(100)
    n = 180

    dates = pd.date_range(start='2024-01-01', periods=n, freq='D')
    base_price = 2500

    prices = []
    price = base_price
    for _ in range(n):
        price = price * (1 + np.random.randn() * 0.01)
        prices.append(price)

    return pd.DataFrame({
        'open': prices,
        'high': [p * 1.01 for p in prices],
        'low': [p * 0.99 for p in prices],
        'close': prices,
        'volume': np.random.randint(1000000, 5000000, n)
    }, index=dates)


def _generate_uptrend_data(n: int, base_price: float) -> pd.DataFrame:
    """상승 추세 데이터 생성"""
    dates = pd.date_range(start='2024-01-01', periods=n, freq='D')

    prices = []
    price = base_price
    for i in range(n):
        trend = 0.001 + np.random.randn() * 0.02
        price = price * (1 + trend)
        prices.append(price)

    close = np.array(prices)
    return pd.DataFrame({
        'open': close * 0.99,
        'high': close * 1.01,
        'low': close * 0.98,
        'close': close,
        'volume': np.random.randint(100000, 1000000, n)
    }, index=dates)


def _generate_downtrend_data(n: int, base_price: float) -> pd.DataFrame:
    """하락 추세 데이터 생성"""
    dates = pd.date_range(start='2024-01-01', periods=n, freq='D')

    prices = []
    price = base_price
    for i in range(n):
        trend = -0.001 + np.random.randn() * 0.02
        price = price * (1 + trend)
        prices.append(max(price, base_price * 0.5))

    close = np.array(prices)
    return pd.DataFrame({
        'open': close * 1.01,
        'high': close * 1.02,
        'low': close * 0.99,
        'close': close,
        'volume': np.random.randint(100000, 1000000, n)
    }, index=dates)


def _generate_sideways_data(n: int, base_price: float) -> pd.DataFrame:
    """횡보 데이터 생성"""
    dates = pd.date_range(start='2024-01-01', periods=n, freq='D')

    prices = []
    price = base_price
    for i in range(n):
        mean_reversion = (base_price - price) * 0.1
        noise = np.random.randn() * base_price * 0.01
        price = price + mean_reversion + noise
        prices.append(price)

    close = np.array(prices)
    return pd.DataFrame({
        'open': close * (1 + np.random.randn(n) * 0.005),
        'high': close * 1.01,
        'low': close * 0.99,
        'close': close,
        'volume': np.random.randint(100000, 1000000, n)
    }, index=dates)


# ========== SectorMap Tests ==========

class TestSectorMap:
    """SectorMap 테스트"""

    def test_sector_map_creation(self, sector_map):
        """섹터 맵 생성 테스트"""
        assert sector_map is not None
        assert len(sector_map.get_active_sectors()) > 0

    def test_get_sector(self, sector_map):
        """섹터 조회 테스트"""
        sector = sector_map.get_sector("005930")
        assert sector == Sector.SEMICONDUCTOR

    def test_get_unknown_sector(self, sector_map):
        """알 수 없는 종목 테스트"""
        sector = sector_map.get_sector("999999")
        assert sector == Sector.OTHER

    def test_get_stocks_in_sector(self, sector_map):
        """섹터 종목 조회 테스트"""
        stocks = sector_map.get_stocks_in_sector(Sector.SEMICONDUCTOR)
        assert "005930" in stocks
        assert "000660" in stocks

    def test_get_sector_info(self, sector_map):
        """섹터 정보 조회 테스트"""
        info = sector_map.get_sector_info(Sector.SEMICONDUCTOR)
        assert info.sector == Sector.SEMICONDUCTOR
        assert info.stock_count >= 2
        assert info.total_weight > 0

    def test_get_stock_info(self, sector_map):
        """종목 정보 조회 테스트"""
        info = sector_map.get_stock_info("005930")
        assert info is not None
        assert info['name'] == "삼성전자"
        assert info['sector'] == Sector.SEMICONDUCTOR

    def test_add_stock(self, sector_map):
        """종목 추가 테스트"""
        sector_map.add_stock("999999", "테스트종목", Sector.OTHER, 0.01)
        info = sector_map.get_stock_info("999999")
        assert info is not None
        assert info['name'] == "테스트종목"

    def test_remove_stock(self, sector_map):
        """종목 제거 테스트"""
        sector_map.add_stock("888888", "삭제종목", Sector.OTHER, 0.01)
        sector_map.remove_stock("888888")
        info = sector_map.get_stock_info("888888")
        assert info is None

    def test_sector_weights(self, sector_map):
        """섹터 가중치 테스트"""
        weights = sector_map.get_sector_weights()
        assert Sector.SEMICONDUCTOR in weights
        assert weights[Sector.SEMICONDUCTOR] > 0

    def test_sector_statistics(self, sector_map):
        """섹터 통계 테스트"""
        stats = sector_map.get_sector_statistics()
        assert 'total_stocks' in stats
        assert 'total_sectors' in stats
        assert 'sectors' in stats


# ========== SectorAnalyzer Tests ==========

class TestSectorAnalyzer:
    """SectorAnalyzer 테스트"""

    def test_analyzer_creation(self, sector_map):
        """분석기 생성 테스트"""
        analyzer = SectorAnalyzer(sector_map)
        assert analyzer is not None

    def test_analyze_sector(self, sector_map, sample_stock_data, market_data):
        """섹터 분석 테스트"""
        analyzer = SectorAnalyzer(sector_map)
        metrics = analyzer.analyze_sector(
            Sector.SEMICONDUCTOR,
            sample_stock_data,
            market_data
        )

        assert isinstance(metrics, SectorMetrics)
        assert metrics.sector == Sector.SEMICONDUCTOR
        assert metrics.stock_count > 0

    def test_analyze_all_sectors(self, sector_map, sample_stock_data, market_data):
        """전체 섹터 분석 테스트"""
        analyzer = SectorAnalyzer(sector_map)
        metrics = analyzer.analyze_all_sectors(sample_stock_data, market_data)

        assert len(metrics) > 0
        for sector, m in metrics.items():
            assert isinstance(m, SectorMetrics)

    def test_rank_sectors(self, sector_map, sample_stock_data, market_data):
        """섹터 순위 테스트"""
        analyzer = SectorAnalyzer(sector_map)
        metrics = analyzer.analyze_all_sectors(sample_stock_data, market_data)
        ranked = analyzer.rank_sectors(metrics)

        # 순위가 1부터 시작
        assert ranked[0][2] == 1

        # 모멘텀 점수 내림차순
        for i in range(len(ranked) - 1):
            assert ranked[i][1].momentum_score >= ranked[i + 1][1].momentum_score

    def test_top_sectors(self, sector_map, sample_stock_data, market_data):
        """상위 섹터 조회 테스트"""
        analyzer = SectorAnalyzer(sector_map)
        metrics = analyzer.analyze_all_sectors(sample_stock_data, market_data)
        top = analyzer.get_top_sectors(metrics, n=3)

        assert len(top) <= 3
        assert all(isinstance(s, Sector) for s in top)

    def test_bottom_sectors(self, sector_map, sample_stock_data, market_data):
        """하위 섹터 조회 테스트"""
        analyzer = SectorAnalyzer(sector_map)
        metrics = analyzer.analyze_all_sectors(sample_stock_data, market_data)
        bottom = analyzer.get_bottom_sectors(metrics, n=3)

        assert len(bottom) <= 3

    def test_sector_metrics_dict(self, sector_map, sample_stock_data, market_data):
        """섹터 지표 딕셔너리 변환 테스트"""
        analyzer = SectorAnalyzer(sector_map)
        metrics = analyzer.analyze_sector(
            Sector.SEMICONDUCTOR,
            sample_stock_data,
            market_data
        )

        d = metrics.to_dict()
        assert 'sector' in d
        assert 'return_1m' in d
        assert 'momentum_score' in d

    def test_sector_summary(self, sector_map, sample_stock_data, market_data):
        """섹터 요약 테스트"""
        analyzer = SectorAnalyzer(sector_map)
        metrics = analyzer.analyze_all_sectors(sample_stock_data, market_data)
        summary = analyzer.get_sector_summary(metrics)

        assert 'total_sectors' in summary
        assert 'top_3' in summary
        assert 'average_momentum' in summary


# ========== RotationEngine Tests ==========

class TestRotationEngine:
    """RotationEngine 테스트"""

    def test_engine_creation(self, sector_map):
        """엔진 생성 테스트"""
        engine = RotationEngine(sector_map)
        assert engine is not None

    def test_calculate_allocation(self, sector_map, sample_stock_data, market_data):
        """배분 계산 테스트"""
        engine = RotationEngine(sector_map)
        allocation = engine.calculate_allocation(sample_stock_data, market_data)

        assert len(allocation) > 0

        # 배분 합계가 1.0
        total_weight = sum(a.weight for a in allocation.values())
        assert abs(total_weight - 1.0) < 0.01

    def test_allocation_structure(self, sector_map, sample_stock_data, market_data):
        """배분 구조 테스트"""
        engine = RotationEngine(sector_map)
        allocation = engine.calculate_allocation(sample_stock_data, market_data)

        for sector, alloc in allocation.items():
            assert isinstance(alloc, SectorAllocation)
            assert alloc.sector == sector
            assert 0 <= alloc.weight <= 1

    def test_rebalance_recommendations(self, sector_map, sample_stock_data, market_data):
        """리밸런싱 권고 테스트"""
        engine = RotationEngine(sector_map)

        # 첫 번째 배분
        engine.calculate_allocation(sample_stock_data, market_data)

        # 두 번째 배분 (데이터 약간 변경)
        modified_data = sample_stock_data.copy()
        engine.calculate_allocation(modified_data, market_data)

        recommendation = engine.get_rebalance_recommendations()

        assert 'needs_rebalance' in recommendation
        assert 'changes' in recommendation

    def test_stock_recommendations(self, sector_map, sample_stock_data, market_data):
        """종목 권고 테스트"""
        engine = RotationEngine(sector_map)
        allocation = engine.calculate_allocation(sample_stock_data, market_data)

        recommendations = engine.get_stock_recommendations(
            allocation,
            total_capital=100000000,  # 1억원
            stock_data=sample_stock_data
        )

        assert len(recommendations) > 0
        for stock, rec in recommendations.items():
            assert 'capital' in rec
            assert 'shares' in rec

    def test_allocation_summary(self, sector_map, sample_stock_data, market_data):
        """배분 요약 테스트"""
        engine = RotationEngine(sector_map)
        engine.calculate_allocation(sample_stock_data, market_data)

        summary = engine.get_allocation_summary()

        assert 'total_sectors' in summary
        assert 'sectors' in summary

    def test_allocation_history(self, sector_map, sample_stock_data, market_data):
        """배분 히스토리 테스트"""
        engine = RotationEngine(sector_map)

        # 여러 번 배분 계산
        for _ in range(3):
            engine.calculate_allocation(sample_stock_data, market_data)

        history = engine.get_history(n=5)
        assert len(history) <= 5


# ========== TransitionDetector Tests ==========

class TestTransitionDetector:
    """TransitionDetector 테스트"""

    def test_detector_creation(self):
        """감지기 생성 테스트"""
        detector = TransitionDetector()
        assert detector is not None

    def test_update_and_detect(self, sector_map, sample_stock_data, market_data):
        """업데이트 및 감지 테스트"""
        analyzer = SectorAnalyzer(sector_map)
        detector = TransitionDetector()

        # 첫 번째 업데이트
        metrics1 = analyzer.analyze_all_sectors(sample_stock_data, market_data)
        signals1 = detector.update(metrics1)

        # 두 번째 업데이트 (데이터 변경)
        modified_data = sample_stock_data.copy()
        # 반도체 가격 급등 시뮬레이션
        for stock in ["005930", "000660"]:
            if stock in modified_data:
                modified_data[stock] = modified_data[stock].copy()
                modified_data[stock]['close'] = modified_data[stock]['close'] * 1.1

        metrics2 = analyzer.analyze_all_sectors(modified_data, market_data)
        signals2 = detector.update(metrics2)

        # 두 번째 업데이트에서 신호가 발생할 수 있음
        assert isinstance(signals2, list)

    def test_transition_signal_structure(self):
        """전환 신호 구조 테스트"""
        signal = TransitionSignal(
            sector=Sector.SEMICONDUCTOR,
            transition_type=TransitionType.MOMENTUM_SHIFT,
            direction=1,
            strength=0.8,
            previous_rank=5,
            current_rank=2,
            previous_momentum=20.0,
            current_momentum=50.0,
            description="테스트"
        )

        assert signal.rank_change == 3  # 5→2 = 3위 상승
        assert signal.momentum_change == 30.0

    def test_recent_signals(self, sector_map, sample_stock_data, market_data):
        """최근 신호 조회 테스트"""
        analyzer = SectorAnalyzer(sector_map)
        detector = TransitionDetector()

        # 여러 번 업데이트
        for i in range(5):
            metrics = analyzer.analyze_all_sectors(sample_stock_data, market_data)
            detector.update(metrics)

        signals = detector.get_recent_signals(n=10)
        assert isinstance(signals, list)

    def test_sector_trend(self, sector_map, sample_stock_data, market_data):
        """섹터 추세 테스트"""
        analyzer = SectorAnalyzer(sector_map)
        detector = TransitionDetector()

        # 여러 번 업데이트
        for _ in range(5):
            metrics = analyzer.analyze_all_sectors(sample_stock_data, market_data)
            detector.update(metrics)

        trend = detector.get_sector_trend(Sector.SEMICONDUCTOR)
        assert 'sector' in trend

    def test_rotation_summary(self, sector_map, sample_stock_data, market_data):
        """로테이션 요약 테스트"""
        analyzer = SectorAnalyzer(sector_map)
        detector = TransitionDetector()

        # 여러 번 업데이트
        for _ in range(3):
            metrics = analyzer.analyze_all_sectors(sample_stock_data, market_data)
            detector.update(metrics)

        summary = detector.get_rotation_summary()
        assert 'rising_sectors' in summary or 'status' in summary

    def test_clear_history(self, sector_map, sample_stock_data, market_data):
        """히스토리 초기화 테스트"""
        analyzer = SectorAnalyzer(sector_map)
        detector = TransitionDetector()

        metrics = analyzer.analyze_all_sectors(sample_stock_data, market_data)
        detector.update(metrics)

        detector.clear_history()

        summary = detector.get_rotation_summary()
        assert summary.get('status') == '데이터 부족'


# ========== Integration Tests ==========

class TestSectorIntegration:
    """섹터 로테이션 통합 테스트"""

    def test_full_rotation_pipeline(self, sector_map, sample_stock_data, market_data):
        """전체 로테이션 파이프라인 테스트"""
        # 1. 섹터 분석
        analyzer = SectorAnalyzer(sector_map)
        metrics = analyzer.analyze_all_sectors(sample_stock_data, market_data)

        assert len(metrics) > 0

        # 2. 배분 계산
        engine = RotationEngine(sector_map, analyzer)
        allocation = engine.calculate_allocation(sample_stock_data, market_data)

        assert len(allocation) > 0
        total_weight = sum(a.weight for a in allocation.values())
        assert abs(total_weight - 1.0) < 0.01

        # 3. 종목 권고
        recommendations = engine.get_stock_recommendations(
            allocation,
            total_capital=100000000,
            stock_data=sample_stock_data
        )

        assert len(recommendations) > 0

        # 4. 전환 감지
        detector = TransitionDetector()
        signals = detector.update(metrics)

        assert isinstance(signals, list)

    def test_multi_period_analysis(self, sector_map, sample_stock_data, market_data):
        """다기간 분석 테스트"""
        analyzer = SectorAnalyzer(sector_map)
        engine = RotationEngine(sector_map, analyzer)
        detector = TransitionDetector()

        # 여러 기간 시뮬레이션
        allocations = []

        for period in range(5):
            # 데이터 약간 변경
            modified_data = {}
            for stock, data in sample_stock_data.items():
                modified = data.copy()
                noise = 1 + np.random.randn() * 0.05
                modified['close'] = modified['close'] * noise
                modified_data[stock] = modified

            # 분석 및 배분
            metrics = analyzer.analyze_all_sectors(modified_data, market_data)
            allocation = engine.calculate_allocation(modified_data, market_data)
            signals = detector.update(metrics)

            allocations.append(allocation)

        # 모든 배분이 유효한지 확인
        for alloc in allocations:
            total = sum(a.weight for a in alloc.values())
            assert abs(total - 1.0) < 0.01


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
