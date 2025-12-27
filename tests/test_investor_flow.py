"""
투자자 수급 분석기 테스트 (P1-3)

테스트 항목:
1. 순매수량 파싱
2. 투자자 동향 계산
3. 신호 생성 로직
4. 신뢰도 계산
5. 캐시 기능
6. 유틸리티 함수
"""

import pytest
from unittest.mock import Mock, MagicMock

from core.indicators.investor_flow import (
    InvestorFlowAnalyzer,
    InvestorFlowResult,
    InvestorSignal,
    InvestorTrend,
    InvestorType,
    analyze_investor_flow,
)


def create_strong_buy_data() -> dict:
    """외국인 + 기관 모두 순매수 데이터"""
    return {
        'frgn_ntby_qty': '2000000',   # 외국인 200만주 순매수
        'orgn_ntby_qty': '1000000',    # 기관 100만주 순매수
        'prsn_ntby_qty': '-3000000',   # 개인 순매도
    }


def create_strong_sell_data() -> dict:
    """외국인 + 기관 모두 순매도 데이터"""
    return {
        'frgn_ntby_qty': '-2000000',   # 외국인 순매도
        'orgn_ntby_qty': '-1000000',   # 기관 순매도
        'prsn_ntby_qty': '3000000',    # 개인 순매수
    }


def create_buy_data() -> dict:
    """외국인만 순매수 데이터"""
    return {
        'frgn_ntby_qty': '2000000',    # 외국인 순매수
        'orgn_ntby_qty': '100000',     # 기관 중립 (임계값 미달)
        'prsn_ntby_qty': '-2100000',
    }


def create_sell_data() -> dict:
    """기관만 순매도 데이터"""
    return {
        'frgn_ntby_qty': '100000',     # 외국인 중립
        'orgn_ntby_qty': '-1000000',   # 기관 순매도
        'prsn_ntby_qty': '900000',
    }


def create_neutral_data() -> dict:
    """중립 데이터"""
    return {
        'frgn_ntby_qty': '500000',     # 임계값 미달
        'orgn_ntby_qty': '200000',     # 임계값 미달
        'prsn_ntby_qty': '-700000',
    }


class TestInvestorTrend:
    """InvestorTrend 테스트"""

    def test_is_buying(self):
        """순매수 확인"""
        trend = InvestorTrend(
            investor_type=InvestorType.FOREIGN,
            net_buy=1000000,
            trend="buying"
        )
        assert trend.is_buying == True
        assert trend.is_selling == False

    def test_is_selling(self):
        """순매도 확인"""
        trend = InvestorTrend(
            investor_type=InvestorType.INSTITUTION,
            net_buy=-500000,
            trend="selling"
        )
        assert trend.is_buying == False
        assert trend.is_selling == True

    def test_neutral(self):
        """중립"""
        trend = InvestorTrend(
            investor_type=InvestorType.INDIVIDUAL,
            net_buy=0,
            trend="neutral"
        )
        assert trend.is_buying == False
        assert trend.is_selling == False


class TestSignalGeneration:
    """신호 생성 테스트"""

    def test_strong_buy_signal(self):
        """외국인 + 기관 순매수 → strong_buy"""
        analyzer = InvestorFlowAnalyzer()
        data = create_strong_buy_data()

        result = analyzer.analyze_from_data("005930", data)

        assert result.signal == InvestorSignal.STRONG_BUY
        assert result.foreign.trend == "buying"
        assert result.institution.trend == "buying"

    def test_strong_sell_signal(self):
        """외국인 + 기관 순매도 → strong_sell"""
        analyzer = InvestorFlowAnalyzer()
        data = create_strong_sell_data()

        result = analyzer.analyze_from_data("005930", data)

        assert result.signal == InvestorSignal.STRONG_SELL
        assert result.foreign.trend == "selling"
        assert result.institution.trend == "selling"

    def test_buy_signal_foreign_only(self):
        """외국인만 순매수 → buy"""
        analyzer = InvestorFlowAnalyzer()
        data = create_buy_data()

        result = analyzer.analyze_from_data("005930", data)

        assert result.signal == InvestorSignal.BUY
        assert result.foreign.trend == "buying"
        assert result.institution.trend == "neutral"

    def test_sell_signal_inst_only(self):
        """기관만 순매도 → sell"""
        analyzer = InvestorFlowAnalyzer()
        data = create_sell_data()

        result = analyzer.analyze_from_data("005930", data)

        assert result.signal == InvestorSignal.SELL
        assert result.foreign.trend == "neutral"
        assert result.institution.trend == "selling"

    def test_neutral_signal(self):
        """임계값 미달 → neutral"""
        analyzer = InvestorFlowAnalyzer()
        data = create_neutral_data()

        result = analyzer.analyze_from_data("005930", data)

        assert result.signal == InvestorSignal.NEUTRAL
        assert result.foreign.trend == "neutral"
        assert result.institution.trend == "neutral"


class TestConfidenceCalculation:
    """신뢰도 계산 테스트"""

    def test_strong_buy_high_confidence(self):
        """강한 신호일수록 높은 신뢰도"""
        analyzer = InvestorFlowAnalyzer()
        data = create_strong_buy_data()

        result = analyzer.analyze_from_data("005930", data)

        assert result.confidence >= 0.8  # strong_buy 기본 신뢰도

    def test_buy_medium_confidence(self):
        """일반 매수 신호 중간 신뢰도"""
        analyzer = InvestorFlowAnalyzer()
        data = create_buy_data()

        result = analyzer.analyze_from_data("005930", data)

        assert 0.4 <= result.confidence <= 0.8

    def test_confidence_never_exceeds_1(self):
        """신뢰도는 1.0을 초과하지 않음"""
        analyzer = InvestorFlowAnalyzer()

        # 매우 큰 순매수량
        data = {
            'frgn_ntby_qty': '100000000',  # 1억주
            'orgn_ntby_qty': '50000000',   # 5천만주
            'prsn_ntby_qty': '-150000000',
        }

        result = analyzer.analyze_from_data("005930", data)

        assert result.confidence <= 1.0


class TestThresholds:
    """임계값 테스트"""

    def test_custom_threshold(self):
        """커스텀 임계값 적용"""
        # 낮은 임계값으로 설정
        analyzer = InvestorFlowAnalyzer(
            foreign_threshold=500000,
            inst_threshold=250000,
        )

        # 기본 임계값에서는 중립이지만, 낮은 임계값에서는 매수
        data = {
            'frgn_ntby_qty': '600000',
            'orgn_ntby_qty': '300000',
            'prsn_ntby_qty': '-900000',
        }

        result = analyzer.analyze_from_data("005930", data)

        assert result.signal == InvestorSignal.STRONG_BUY

    def test_small_cap_threshold(self):
        """소형주 임계값"""
        analyzer = InvestorFlowAnalyzer(use_small_cap_threshold=True)

        # 소형주 임계값: 외국인 10만주, 기관 5만주
        assert analyzer.foreign_threshold == 100000
        assert analyzer.inst_threshold == 50000


class TestDataParsing:
    """데이터 파싱 테스트"""

    def test_parse_string_numbers(self):
        """문자열 숫자 파싱"""
        analyzer = InvestorFlowAnalyzer()

        data = {
            'frgn_ntby_qty': '2000000',
            'orgn_ntby_qty': '1000000',
            'prsn_ntby_qty': '-3000000',
        }

        result = analyzer.analyze_from_data("005930", data)

        assert result.foreign.net_buy == 2000000
        assert result.institution.net_buy == 1000000
        assert result.individual.net_buy == -3000000

    def test_parse_integer_numbers(self):
        """정수 값 파싱"""
        analyzer = InvestorFlowAnalyzer()

        data = {
            'frgn_ntby_qty': 2000000,
            'orgn_ntby_qty': 1000000,
            'prsn_ntby_qty': -3000000,
        }

        result = analyzer.analyze_from_data("005930", data)

        assert result.foreign.net_buy == 2000000

    def test_parse_missing_fields(self):
        """필드 누락 시 0으로 처리"""
        analyzer = InvestorFlowAnalyzer()

        data = {
            'frgn_ntby_qty': '2000000',
            # orgn_ntby_qty 누락
        }

        result = analyzer.analyze_from_data("005930", data)

        assert result.foreign.net_buy == 2000000
        assert result.institution.net_buy == 0

    def test_parse_none_values(self):
        """None 값 처리"""
        analyzer = InvestorFlowAnalyzer()

        data = {
            'frgn_ntby_qty': None,
            'orgn_ntby_qty': None,
            'prsn_ntby_qty': None,
        }

        result = analyzer.analyze_from_data("005930", data)

        assert result.foreign.net_buy == 0
        assert result.institution.net_buy == 0


class TestCache:
    """캐시 기능 테스트"""

    def test_cache_stores_result(self):
        """분석 결과 캐시 저장"""
        analyzer = InvestorFlowAnalyzer()
        data = create_strong_buy_data()

        analyzer.analyze_from_data("005930", data)

        cached = analyzer.get_cached_result("005930")
        assert cached is not None
        assert cached.stock_code == "005930"

    def test_get_all_cached(self):
        """모든 캐시 결과 조회"""
        analyzer = InvestorFlowAnalyzer()

        analyzer.analyze_from_data("005930", create_strong_buy_data())
        analyzer.analyze_from_data("000660", create_strong_sell_data())

        all_cached = analyzer.get_all_cached_results()

        assert len(all_cached) == 2
        assert "005930" in all_cached
        assert "000660" in all_cached

    def test_clear_cache(self):
        """캐시 초기화"""
        analyzer = InvestorFlowAnalyzer()

        analyzer.analyze_from_data("005930", create_strong_buy_data())
        analyzer.clear_cache()

        assert analyzer.get_cached_result("005930") is None


class TestUtilityMethods:
    """유틸리티 메서드 테스트"""

    def test_get_strong_buy_stocks(self):
        """strong_buy 종목 조회"""
        analyzer = InvestorFlowAnalyzer()

        analyzer.analyze_from_data("005930", create_strong_buy_data())
        analyzer.analyze_from_data("000660", create_strong_sell_data())
        analyzer.analyze_from_data("035420", create_neutral_data())

        strong_buy = analyzer.get_strong_buy_stocks()

        assert "005930" in strong_buy
        assert "000660" not in strong_buy
        assert "035420" not in strong_buy

    def test_get_strong_sell_stocks(self):
        """strong_sell 종목 조회"""
        analyzer = InvestorFlowAnalyzer()

        analyzer.analyze_from_data("005930", create_strong_buy_data())
        analyzer.analyze_from_data("000660", create_strong_sell_data())

        strong_sell = analyzer.get_strong_sell_stocks()

        assert "000660" in strong_sell
        assert "005930" not in strong_sell

    def test_get_signal_summary(self):
        """신호별 통계"""
        analyzer = InvestorFlowAnalyzer()

        analyzer.analyze_from_data("005930", create_strong_buy_data())
        analyzer.analyze_from_data("000660", create_strong_sell_data())
        analyzer.analyze_from_data("035420", create_neutral_data())

        summary = analyzer.get_signal_summary()

        assert summary['strong_buy'] == 1
        assert summary['strong_sell'] == 1
        assert summary['neutral'] == 1


class TestInvestorFlowResult:
    """InvestorFlowResult 테스트"""

    def test_to_dict(self):
        """딕셔너리 변환"""
        analyzer = InvestorFlowAnalyzer()
        data = create_strong_buy_data()

        result = analyzer.analyze_from_data("005930", data)
        d = result.to_dict()

        assert d["stock_code"] == "005930"
        assert d["signal"] == "strong_buy"
        assert "foreign_net_buy" in d
        assert "institution_net_buy" in d

    def test_net_buy_total(self):
        """외국인 + 기관 합산"""
        analyzer = InvestorFlowAnalyzer()
        data = create_strong_buy_data()

        result = analyzer.analyze_from_data("005930", data)

        # 2000000 + 1000000 = 3000000
        assert result.net_buy_total == 3000000


class TestAPIIntegration:
    """API 연동 테스트"""

    def test_analyze_without_api(self):
        """API 없이 analyze 호출"""
        analyzer = InvestorFlowAnalyzer()

        result = analyzer.analyze("005930")

        assert result is None

    def test_analyze_with_mock_api(self):
        """Mock API로 analyze"""
        mock_api = Mock()
        mock_api.get_investor_flow.return_value = create_strong_buy_data()

        analyzer = InvestorFlowAnalyzer(kis_api=mock_api)
        result = analyzer.analyze("005930")

        assert result is not None
        assert result.signal == InvestorSignal.STRONG_BUY
        mock_api.get_investor_flow.assert_called_once_with("005930")

    def test_set_kis_api(self):
        """API 클라이언트 설정"""
        analyzer = InvestorFlowAnalyzer()
        mock_api = Mock()

        analyzer.set_kis_api(mock_api)

        assert analyzer.kis_api == mock_api


class TestConvenienceFunction:
    """편의 함수 테스트"""

    def test_analyze_investor_flow_function(self):
        """analyze_investor_flow 함수"""
        data = create_strong_buy_data()

        result = analyze_investor_flow("005930", data)

        assert isinstance(result, InvestorFlowResult)
        assert result.stock_code == "005930"
        assert result.signal == InvestorSignal.STRONG_BUY


class TestEdgeCases:
    """엣지 케이스 테스트"""

    def test_zero_values(self):
        """모든 값이 0인 경우"""
        analyzer = InvestorFlowAnalyzer()

        data = {
            'frgn_ntby_qty': '0',
            'orgn_ntby_qty': '0',
            'prsn_ntby_qty': '0',
        }

        result = analyzer.analyze_from_data("005930", data)

        assert result.signal == InvestorSignal.NEUTRAL
        assert result.foreign.net_buy == 0
        assert result.institution.net_buy == 0

    def test_negative_threshold_boundary(self):
        """음수 임계값 경계"""
        analyzer = InvestorFlowAnalyzer()

        # 정확히 -1,000,000 (외국인 임계값)
        data = {
            'frgn_ntby_qty': '-1000000',
            'orgn_ntby_qty': '0',
            'prsn_ntby_qty': '1000000',
        }

        result = analyzer.analyze_from_data("005930", data)

        # 임계값 미만이므로 중립
        # (-1000000 < -1000000은 거짓)
        assert result.foreign.trend == "neutral"

    def test_invalid_data_type(self):
        """잘못된 데이터 타입"""
        analyzer = InvestorFlowAnalyzer()

        data = {
            'frgn_ntby_qty': 'invalid',
            'orgn_ntby_qty': [],
            'prsn_ntby_qty': {},
        }

        result = analyzer.analyze_from_data("005930", data)

        # 모두 0으로 처리되어야 함
        assert result.foreign.net_buy == 0
        assert result.institution.net_buy == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
