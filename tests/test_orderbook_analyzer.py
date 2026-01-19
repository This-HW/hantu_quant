"""
호가 불균형 분석기 테스트 (P1-2)

테스트 항목:
1. 불균형 비율 계산 정확성
2. 신호 생성 로직
3. 가중평균 가격 계산
4. 스프레드 계산
5. KIS 호가 데이터 파싱
6. 콜백 시스템
7. 캐시 기능
"""

import pytest
from unittest.mock import Mock
from typing import List, Tuple

from core.indicators.orderbook_analyzer import (
    OrderBookAnalyzer,
    OrderBookMonitor,
    OrderBookSignal,
    OrderBookImbalance,
    analyze_orderbook,
)


def create_balanced_orderbook() -> Tuple[List[Tuple[int, int]], List[Tuple[int, int]]]:
    """균형 잡힌 호가 데이터 생성"""
    bids = [(50000 - i * 100, 1000) for i in range(10)]  # 매수
    asks = [(50100 + i * 100, 1000) for i in range(10)]  # 매도
    return bids, asks


def create_buy_pressure_orderbook() -> Tuple[List[Tuple[int, int]], List[Tuple[int, int]]]:
    """매수 압력 호가 데이터 생성 (불균형 > 0.3)"""
    bids = [(50000 - i * 100, 3000) for i in range(10)]  # 매수 많음
    asks = [(50100 + i * 100, 1000) for i in range(10)]  # 매도 적음
    return bids, asks


def create_sell_pressure_orderbook() -> Tuple[List[Tuple[int, int]], List[Tuple[int, int]]]:
    """매도 압력 호가 데이터 생성 (불균형 < -0.3)"""
    bids = [(50000 - i * 100, 1000) for i in range(10)]  # 매수 적음
    asks = [(50100 + i * 100, 3000) for i in range(10)]  # 매도 많음
    return bids, asks


def create_weak_buy_orderbook() -> Tuple[List[Tuple[int, int]], List[Tuple[int, int]]]:
    """약한 매수 호가 데이터 생성 (0.1 < 불균형 < 0.3)"""
    bids = [(50000 - i * 100, 1500) for i in range(10)]  # 매수 약간 많음
    asks = [(50100 + i * 100, 1000) for i in range(10)]
    return bids, asks


class TestImbalanceCalculation:
    """불균형 비율 계산 테스트"""

    def test_balanced_ratio(self):
        """균형 잡힌 호가의 불균형 비율은 0에 가까움"""
        analyzer = OrderBookAnalyzer()
        bids, asks = create_balanced_orderbook()

        result = analyzer.analyze("005930", bids, asks)

        assert -0.1 < result.imbalance_ratio < 0.1
        assert result.signal == OrderBookSignal.NEUTRAL

    def test_strong_buy_ratio(self):
        """강한 매수 압력 불균형 > 0.3"""
        analyzer = OrderBookAnalyzer()
        bids, asks = create_buy_pressure_orderbook()

        result = analyzer.analyze("005930", bids, asks)

        assert result.imbalance_ratio > 0.3
        assert result.signal == OrderBookSignal.STRONG_BUY

    def test_strong_sell_ratio(self):
        """강한 매도 압력 불균형 < -0.3"""
        analyzer = OrderBookAnalyzer()
        bids, asks = create_sell_pressure_orderbook()

        result = analyzer.analyze("005930", bids, asks)

        assert result.imbalance_ratio < -0.3
        assert result.signal == OrderBookSignal.STRONG_SELL

    def test_weak_buy_ratio(self):
        """약한 매수 압력 0.1 < 불균형 < 0.3"""
        analyzer = OrderBookAnalyzer()
        bids, asks = create_weak_buy_orderbook()

        result = analyzer.analyze("005930", bids, asks)

        assert 0.1 <= result.imbalance_ratio <= 0.3
        assert result.signal == OrderBookSignal.BUY

    def test_imbalance_formula(self):
        """불균형 비율 공식 검증: (매수 - 매도) / 총합"""
        analyzer = OrderBookAnalyzer()

        # 매수 8000, 매도 2000 = (8000-2000)/10000 = 0.6
        bids = [(50000, 8000)]
        asks = [(50100, 2000)]

        result = analyzer.analyze("005930", bids, asks)

        expected_ratio = (8000 - 2000) / (8000 + 2000)
        assert abs(result.imbalance_ratio - expected_ratio) < 0.001

    def test_zero_volume_handling(self):
        """잔량이 0인 경우 처리"""
        analyzer = OrderBookAnalyzer()

        bids = []
        asks = []

        result = analyzer.analyze("005930", bids, asks)

        assert result.imbalance_ratio == 0.0
        assert result.signal == OrderBookSignal.NEUTRAL


class TestSignalGeneration:
    """신호 생성 테스트"""

    def test_signal_thresholds(self):
        """신호 임계값 테스트"""
        analyzer = OrderBookAnalyzer(
            strong_threshold=0.3,
            weak_threshold=0.1
        )

        # 직접 신호 계산 테스트
        signal, conf = analyzer._calculate_signal(0.4)
        assert signal == OrderBookSignal.STRONG_BUY

        signal, conf = analyzer._calculate_signal(0.2)
        assert signal == OrderBookSignal.BUY

        signal, conf = analyzer._calculate_signal(0.05)
        assert signal == OrderBookSignal.NEUTRAL

        signal, conf = analyzer._calculate_signal(-0.2)
        assert signal == OrderBookSignal.SELL

        signal, conf = analyzer._calculate_signal(-0.4)
        assert signal == OrderBookSignal.STRONG_SELL

    def test_confidence_calculation(self):
        """신뢰도 계산 테스트"""
        analyzer = OrderBookAnalyzer()

        # 강한 신호일수록 높은 신뢰도
        signal_strong, conf_strong = analyzer._calculate_signal(0.5)
        signal_weak, conf_weak = analyzer._calculate_signal(0.15)

        assert conf_strong > conf_weak

    def test_custom_thresholds(self):
        """커스텀 임계값 적용"""
        analyzer = OrderBookAnalyzer(
            strong_threshold=0.4,  # 기본값 0.3 대신
            weak_threshold=0.2    # 기본값 0.1 대신
        )

        # 0.3은 이제 neutral
        signal, _ = analyzer._calculate_signal(0.3)
        assert signal == OrderBookSignal.BUY  # strong이 아닌 일반 buy

        signal, _ = analyzer._calculate_signal(0.15)
        assert signal == OrderBookSignal.NEUTRAL  # weak_threshold보다 낮으므로 neutral


class TestWeightedPrice:
    """가중평균 가격 계산 테스트"""

    def test_weighted_average(self):
        """가중평균 계산 정확성"""
        analyzer = OrderBookAnalyzer()

        # (50000 * 1000 + 49900 * 2000) / 3000 = 49933.33...
        orders = [(50000, 1000), (49900, 2000)]
        weighted = analyzer._calculate_weighted_price(orders)

        expected = (50000 * 1000 + 49900 * 2000) / 3000
        assert abs(weighted - expected) < 0.01

    def test_empty_orders(self):
        """빈 호가 리스트 처리"""
        analyzer = OrderBookAnalyzer()

        weighted = analyzer._calculate_weighted_price([])
        assert weighted == 0.0

    def test_single_order(self):
        """단일 호가 처리"""
        analyzer = OrderBookAnalyzer()

        orders = [(50000, 1000)]
        weighted = analyzer._calculate_weighted_price(orders)

        assert weighted == 50000


class TestSpreadCalculation:
    """스프레드 계산 테스트"""

    def test_spread_calculation(self):
        """스프레드 계산 정확성"""
        analyzer = OrderBookAnalyzer()

        bids = [(50000, 1000)]  # 최우선 매수호가
        asks = [(50100, 1000)]  # 최우선 매도호가

        spread = analyzer._calculate_spread(bids, asks)

        # (50100 - 50000) / 50000 * 100 = 0.2%
        expected = (50100 - 50000) / 50000 * 100
        assert abs(spread - expected) < 0.001

    def test_spread_empty_orders(self):
        """빈 호가 리스트 스프레드"""
        analyzer = OrderBookAnalyzer()

        spread = analyzer._calculate_spread([], [])
        assert spread == 0.0


class TestKISParsing:
    """KIS 호가 데이터 파싱 테스트"""

    def test_parse_kis_orderbook(self):
        """KIS H0STASP0 형식 파싱"""
        analyzer = OrderBookAnalyzer()

        raw_data = {
            'ASKP1': '50100', 'ASKP_RSQN1': '1000',
            'ASKP2': '50200', 'ASKP_RSQN2': '2000',
            'BIDP1': '50000', 'BIDP_RSQN1': '1500',
            'BIDP2': '49900', 'BIDP_RSQN2': '2500',
        }

        bids, asks = analyzer._parse_kis_orderbook(raw_data)

        assert len(asks) >= 2
        assert len(bids) >= 2
        assert asks[0] == (50100, 1000)
        assert bids[0] == (50000, 1500)

    def test_parse_missing_data(self):
        """누락된 데이터 처리"""
        analyzer = OrderBookAnalyzer()

        raw_data = {
            'ASKP1': '50100', 'ASKP_RSQN1': '1000',
            # ASKP2 없음
            'BIDP1': '50000', 'BIDP_RSQN1': '1500',
        }

        bids, asks = analyzer._parse_kis_orderbook(raw_data)

        assert len(asks) >= 1
        assert len(bids) >= 1

    def test_analyze_from_raw(self):
        """원시 데이터로부터 분석"""
        analyzer = OrderBookAnalyzer()

        raw_data = {
            'ASKP1': '50100', 'ASKP_RSQN1': '1000',
            'ASKP2': '50200', 'ASKP_RSQN2': '1000',
            'BIDP1': '50000', 'BIDP_RSQN1': '3000',
            'BIDP2': '49900', 'BIDP_RSQN2': '3000',
        }

        result = analyzer.analyze_from_raw("005930", raw_data)

        assert isinstance(result, OrderBookImbalance)
        assert result.stock_code == "005930"
        assert result.imbalance_ratio > 0  # 매수 우세


class TestCallbacks:
    """콜백 시스템 테스트"""

    def test_add_callback(self):
        """콜백 등록"""
        analyzer = OrderBookAnalyzer()
        callback = Mock()

        analyzer.add_signal_callback(callback)

        assert callback in analyzer._signal_callbacks

    def test_callback_called_on_signal(self):
        """신호 발생 시 콜백 호출"""
        analyzer = OrderBookAnalyzer()
        callback = Mock()
        analyzer.add_signal_callback(callback)

        # 강한 신호 생성
        bids, asks = create_buy_pressure_orderbook()
        analyzer.analyze("005930", bids, asks)

        # 콜백이 호출되어야 함
        callback.assert_called_once()

    def test_callback_not_called_on_neutral(self):
        """중립 신호 시 콜백 미호출"""
        analyzer = OrderBookAnalyzer()
        callback = Mock()
        analyzer.add_signal_callback(callback)

        # 균형 잡힌 호가
        bids, asks = create_balanced_orderbook()
        analyzer.analyze("005930", bids, asks)

        # 콜백이 호출되지 않아야 함
        callback.assert_not_called()

    def test_remove_callback(self):
        """콜백 제거"""
        analyzer = OrderBookAnalyzer()
        callback = Mock()

        analyzer.add_signal_callback(callback)
        analyzer.remove_signal_callback(callback)

        assert callback not in analyzer._signal_callbacks


class TestCache:
    """캐시 기능 테스트"""

    def test_cache_stores_result(self):
        """분석 결과 캐시 저장"""
        analyzer = OrderBookAnalyzer()
        bids, asks = create_balanced_orderbook()

        analyzer.analyze("005930", bids, asks)

        cached = analyzer.get_cached_result("005930")
        assert cached is not None
        assert cached.stock_code == "005930"

    def test_cache_updates_on_new_analysis(self):
        """새 분석 시 캐시 업데이트"""
        analyzer = OrderBookAnalyzer()

        # 첫 번째 분석
        bids1, asks1 = create_balanced_orderbook()
        analyzer.analyze("005930", bids1, asks1)

        # 두 번째 분석 (다른 데이터)
        bids2, asks2 = create_buy_pressure_orderbook()
        result2 = analyzer.analyze("005930", bids2, asks2)

        cached = analyzer.get_cached_result("005930")

        # 캐시가 업데이트됨
        assert cached.imbalance_ratio == result2.imbalance_ratio

    def test_get_all_cached(self):
        """모든 캐시 결과 조회"""
        analyzer = OrderBookAnalyzer()
        bids, asks = create_balanced_orderbook()

        analyzer.analyze("005930", bids, asks)
        analyzer.analyze("000660", bids, asks)

        all_cached = analyzer.get_all_cached_results()

        assert len(all_cached) == 2
        assert "005930" in all_cached
        assert "000660" in all_cached

    def test_clear_cache(self):
        """캐시 초기화"""
        analyzer = OrderBookAnalyzer()
        bids, asks = create_balanced_orderbook()

        analyzer.analyze("005930", bids, asks)
        analyzer.clear_cache()

        assert analyzer.get_cached_result("005930") is None


class TestSignalSummary:
    """신호 통계 테스트"""

    def test_signal_summary(self):
        """신호별 통계"""
        analyzer = OrderBookAnalyzer()

        # 다양한 신호 생성
        bids_buy, asks_buy = create_buy_pressure_orderbook()
        bids_sell, asks_sell = create_sell_pressure_orderbook()
        bids_neutral, asks_neutral = create_balanced_orderbook()

        analyzer.analyze("005930", bids_buy, asks_buy)    # STRONG_BUY
        analyzer.analyze("000660", bids_sell, asks_sell)  # STRONG_SELL
        analyzer.analyze("035420", bids_neutral, asks_neutral)  # NEUTRAL

        summary = analyzer.get_signal_summary()

        assert summary[OrderBookSignal.STRONG_BUY.value] == 1
        assert summary[OrderBookSignal.STRONG_SELL.value] == 1
        assert summary[OrderBookSignal.NEUTRAL.value] == 1


class TestOrderBookImbalanceDataclass:
    """OrderBookImbalance 데이터클래스 테스트"""

    def test_to_dict(self):
        """딕셔너리 변환"""
        imbalance = OrderBookImbalance(
            stock_code="005930",
            bid_volume=10000,
            ask_volume=8000,
            total_volume=18000,
            imbalance_ratio=0.11,
            signal=OrderBookSignal.BUY,
            confidence=0.5,
        )

        d = imbalance.to_dict()

        assert d["stock_code"] == "005930"
        assert d["bid_volume"] == 10000
        assert d["signal"] == "buy"


class TestConvenienceFunction:
    """편의 함수 테스트"""

    def test_analyze_orderbook_function(self):
        """analyze_orderbook 함수"""
        bids, asks = create_buy_pressure_orderbook()

        result = analyze_orderbook("005930", bids, asks, levels=5)

        assert isinstance(result, OrderBookImbalance)
        assert result.stock_code == "005930"


class TestOrderBookMonitor:
    """OrderBookMonitor 테스트"""

    def test_init_without_dependencies(self):
        """의존성 없이 초기화"""
        monitor = OrderBookMonitor()

        assert monitor.analyzer is not None
        assert monitor.ws_client is None
        assert not monitor.is_running

    def test_init_with_analyzer(self):
        """커스텀 analyzer로 초기화"""
        analyzer = OrderBookAnalyzer(levels=5)
        monitor = OrderBookMonitor(analyzer=analyzer)

        assert monitor.analyzer.levels == 5

    def test_set_websocket_client(self):
        """WebSocket 클라이언트 설정"""
        monitor = OrderBookMonitor()
        mock_ws = Mock()

        monitor.set_websocket_client(mock_ws)

        assert monitor.ws_client == mock_ws

    def test_start_monitoring_without_ws(self):
        """WebSocket 없이 모니터링 시작 실패"""
        import asyncio
        monitor = OrderBookMonitor()

        result = asyncio.get_event_loop().run_until_complete(
            monitor.start_monitoring(["005930"])
        )

        assert result == False
        assert not monitor.is_running

    def test_on_orderbook_data(self):
        """호가 데이터 수신 처리"""
        monitor = OrderBookMonitor()

        data = {
            'MKSC_SHRN_ISCD': '005930',
            'ASKP1': '50100', 'ASKP_RSQN1': '1000',
            'BIDP1': '50000', 'BIDP_RSQN1': '3000',
        }

        monitor._on_orderbook_data(data)

        # 분석 결과가 캐시에 저장됨
        cached = monitor.analyzer.get_cached_result("005930")
        assert cached is not None

    def test_monitoring_stocks_property(self):
        """모니터링 중인 종목 리스트"""
        monitor = OrderBookMonitor()
        monitor._monitoring_stocks = ["005930", "000660"]

        stocks = monitor.monitoring_stocks

        assert stocks == ["005930", "000660"]
        # 복사본 반환 확인
        stocks.append("035420")
        assert "035420" not in monitor._monitoring_stocks


class TestLevelFiltering:
    """호가 레벨 필터링 테스트"""

    def test_analyze_with_custom_levels(self):
        """커스텀 레벨 수로 분석"""
        analyzer = OrderBookAnalyzer(levels=10)

        # 10개 레벨 생성
        bids = [(50000 - i * 100, 1000 + i * 100) for i in range(10)]
        asks = [(50100 + i * 100, 1000 + i * 100) for i in range(10)]

        result_all = analyzer.analyze("005930", bids, asks, levels=10)
        result_five = analyzer.analyze("005930", bids, asks, levels=5)

        # 레벨 수에 따라 잔량 합계가 다름
        assert result_all.total_volume > result_five.total_volume


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
