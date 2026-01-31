#!/usr/bin/env python3
"""
PriceAnalyzer 버그 수정 테스트

수정된 내용:
1. _safe_get_list: None 반환 → [] 반환
2. _analyze_technical_indicators: p_stock_code 미정의 수정
3. 반환 타입: Dict → Tuple
"""

import pytest
from unittest.mock import Mock, patch
from core.daily_selection.price_analyzer import PriceAnalyzer


class TestPriceAnalyzerFixes:
    """PriceAnalyzer 버그 수정 테스트"""

    def setup_method(self):
        """각 테스트 전 실행"""
        self.analyzer = PriceAnalyzer()

    def test_safe_get_list_returns_empty_list_on_none(self):
        """_safe_get_list: None 입력 시 빈 리스트 반환"""
        result = self.analyzer._safe_get_list(None)
        assert result == [], "None 입력 시 빈 리스트를 반환해야 함"

    def test_safe_get_list_returns_empty_list_on_invalid_input(self):
        """_safe_get_list: 잘못된 입력 시 빈 리스트 반환"""
        # 빈 리스트
        assert self.analyzer._safe_get_list([]) == []

        # 숫자가 아닌 값들
        assert self.analyzer._safe_get_list(["a", "b"]) == []

        # 빈 문자열
        assert self.analyzer._safe_get_list("") == []

    def test_safe_get_list_converts_single_value_to_list(self):
        """_safe_get_list: 단일 값은 리스트로 변환"""
        result = self.analyzer._safe_get_list(100)
        assert result == [100.0], "단일 숫자는 리스트로 변환되어야 함"

    def test_safe_get_list_returns_valid_list(self):
        """_safe_get_list: 유효한 리스트는 그대로 반환"""
        input_list = [100, 200, 300]
        result = self.analyzer._safe_get_list(input_list)
        assert result == [100.0, 200.0, 300.0], "유효한 리스트는 float로 변환되어 반환"

    def test_safe_get_list_filters_non_numeric_values(self):
        """_safe_get_list: 숫자가 아닌 값은 필터링"""
        input_list = [100, "invalid", 200, None, 300]
        result = self.analyzer._safe_get_list(input_list)
        assert result == [100.0, 200.0, 300.0], "숫자가 아닌 값은 제거되어야 함"

    @patch('core.daily_selection.price_analyzer.TechnicalIndicators')
    def test_analyze_technical_indicators_with_missing_prices(self, mock_indicators):
        """_analyze_technical_indicators: 가격 데이터 없을 때 처리"""
        # 가격 데이터가 없는 종목
        stock_data = {
            "stock_code": "005930",
            "stock_name": "삼성전자",
            "current_price": 50000,
            "recent_close_prices": None,  # 가격 데이터 없음
            "recent_volumes": None
        }

        score, signals = self.analyzer._analyze_technical_indicators(stock_data)

        # 가격 데이터가 없으면 기본 점수 반환
        assert score == 50.0, "가격 데이터 없을 때 기본 점수 50.0 반환"
        assert signals == [], "가격 데이터 없을 때 신호 없음"

    @patch('core.daily_selection.price_analyzer.TechnicalIndicators')
    def test_analyze_technical_indicators_with_empty_prices(self, mock_indicators):
        """_analyze_technical_indicators: 빈 가격 리스트 처리"""
        stock_data = {
            "stock_code": "005930",
            "stock_name": "삼성전자",
            "current_price": 50000,
            "recent_close_prices": [],  # 빈 리스트
            "recent_volumes": []
        }

        score, signals = self.analyzer._analyze_technical_indicators(stock_data)

        assert score == 50.0, "빈 가격 데이터일 때 기본 점수 50.0 반환"
        assert signals == [], "빈 가격 데이터일 때 신호 없음"

    @patch('core.daily_selection.price_analyzer.TechnicalIndicators')
    def test_analyze_technical_indicators_returns_tuple(self, mock_indicators):
        """_analyze_technical_indicators: Tuple 반환 확인"""
        stock_data = {
            "stock_code": "005930",
            "stock_name": "삼성전자",
            "current_price": 50000,
            "recent_close_prices": [50000, 51000, 52000, 53000, 54000],
            "recent_volumes": [1000000] * 5
        }

        # Mock 설정
        mock_indicators.calculate_bollinger_bands = Mock(return_value=(55000, 52000, 49000))
        mock_indicators.calculate_macd = Mock(return_value=(100, 90, 10))
        mock_indicators.calculate_rsi = Mock(return_value=(50))
        mock_indicators.calculate_stochastic = Mock(return_value=(50, 50))
        mock_indicators.calculate_cci = Mock(return_value=(0))

        result = self.analyzer._analyze_technical_indicators(stock_data)

        # 반환 타입 확인
        assert isinstance(result, tuple), "반환 타입은 Tuple이어야 함"
        assert len(result) == 2, "반환 값은 (score, signals) 2개 요소"

        score, signals = result
        assert isinstance(score, float), "score는 float 타입"
        assert isinstance(signals, list), "signals는 list 타입"

    def test_analyze_technical_indicators_with_single_price_value(self):
        """_analyze_technical_indicators: 단일 가격 값 처리"""
        stock_data = {
            "stock_code": "005930",
            "stock_name": "삼성전자",
            "current_price": 50000,  # 단일 값
            "recent_close_prices": 50000,  # 단일 값 (리스트 아님)
            "recent_volumes": 1000000
        }

        score, signals = self.analyzer._analyze_technical_indicators(stock_data)

        # 단일 값이 리스트로 변환되어 처리되어야 함
        assert isinstance(score, float), "score는 float 타입"
        assert isinstance(signals, list), "signals는 list 타입"

    def test_safe_get_list_edge_cases(self):
        """_safe_get_list: 엣지 케이스 처리"""
        # 0 값
        assert self.analyzer._safe_get_list(0) == [0.0]

        # 음수
        assert self.analyzer._safe_get_list(-100) == [-100.0]

        # 매우 큰 수
        assert self.analyzer._safe_get_list(1e10) == [1e10]

        # float 값
        assert self.analyzer._safe_get_list(123.456) == [123.456]

    @patch('core.daily_selection.price_analyzer.TechnicalIndicators')
    def test_analyze_technical_indicators_no_exception_on_missing_stock_code(self, mock_indicators):
        """_analyze_technical_indicators: stock_code 없어도 예외 발생 안 함"""
        stock_data = {
            # stock_code 없음
            "stock_name": "테스트",
            "current_price": 50000,
            "recent_close_prices": None
        }

        try:
            score, signals = self.analyzer._analyze_technical_indicators(stock_data)
            # 예외 없이 실행되어야 함
            assert True
        except Exception as e:
            pytest.fail(f"stock_code 없을 때 예외 발생: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
