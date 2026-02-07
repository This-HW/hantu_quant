"""
StockScreener._fetch_stock_data() 메서드 테스트 (TDD Red-Green-Refactor)

테스트 대상: core.watchlist.stock_screener.StockScreener._fetch_stock_data()

테스트 전략:
1. RestClient를 Mock으로 대체 (실제 API 호출 방지)
2. 기술적 지표 계산 로직 검증 (RSI, MA, 모멘텀 등)
3. 에러 케이스 포함 (API 실패, 빈 데이터, 잘못된 입력 등)
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock, PropertyMock

# Import 시점의 에러를 방지하기 위해 Mock을 먼저 설정
import sys
from unittest.mock import MagicMock

# core.api.rest_client 모듈을 Mock으로 대체 (import 에러 방지)
mock_rest_client_module = MagicMock()
mock_rest_client_module.RestClient = MagicMock
sys.modules['core.api.rest_client'] = mock_rest_client_module

from core.watchlist.stock_screener import StockScreener


# ========== Fixtures ==========

@pytest.fixture
def mock_rest_client():
    """RestClient Mock 생성"""
    mock_client = Mock()
    return mock_client


@pytest.fixture
def sample_price_data():
    """샘플 현재가 데이터"""
    return {
        "current_price": 50000,
        "volume": 1000000,
    }


@pytest.fixture
def sample_stock_info():
    """샘플 종목 상세 정보"""
    return {
        "market_cap": 10000000000,  # 100억
        "per": 12.5,
        "pbr": 1.2,
    }


@pytest.fixture
def sample_chart_data():
    """샘플 일봉 차트 데이터 (120일)"""
    dates = pd.date_range(end=datetime.now(), periods=120, freq="D")

    # 실제 주가 패턴 시뮬레이션 (상승 추세)
    np.random.seed(42)
    base_price = 40000
    trend = np.linspace(0, 10000, 120)  # 상승 추세
    noise = np.random.normal(0, 1000, 120)  # 노이즈
    close_prices = base_price + trend + noise

    chart_df = pd.DataFrame({
        "date": dates,
        "open": close_prices * 0.99,
        "high": close_prices * 1.02,
        "low": close_prices * 0.98,
        "close": close_prices,
        "volume": np.random.randint(500000, 1500000, 120),
    })

    return chart_df


@pytest.fixture
def screener_with_mock(mock_rest_client):
    """Mock RestClient를 주입한 StockScreener 인스턴스"""
    screener = StockScreener()
    screener._rest_client = mock_rest_client
    return screener


# ========== Red: 실패하는 테스트 작성 ==========

class TestFetchStockDataSuccess:
    """정상 케이스: 실제 데이터 조회 및 지표 계산"""

    def test_fetch_stock_data_returns_complete_dict(
        self,
        screener_with_mock,
        mock_rest_client,
        sample_price_data,
        sample_stock_info,
        sample_chart_data
    ):
        """
        테스트: _fetch_stock_data()가 완전한 딕셔너리를 반환하는가?

        검증 항목:
        - 모든 필수 키가 존재하는가?
        - 데이터 타입이 올바른가?
        - 계산된 기술적 지표가 포함되어 있는가?
        """
        # Arrange
        stock_code = "005930"
        mock_rest_client.get_current_price.return_value = sample_price_data
        mock_rest_client.get_stock_info.return_value = sample_stock_info
        mock_rest_client.get_daily_chart.return_value = sample_chart_data

        # Act
        result = screener_with_mock._fetch_stock_data(stock_code)

        # Assert
        assert result is not None, "반환값이 None이 아니어야 함"

        # 필수 키 검증
        required_keys = [
            "stock_code", "stock_name", "sector", "market",
            "current_price", "volume", "market_cap",
            "ma_20", "ma_60", "ma_120",
            "rsi", "volume_ratio",
            "price_momentum_1m", "price_momentum_3m", "price_momentum_6m",
            "volatility",
            "per", "pbr",
        ]
        for key in required_keys:
            assert key in result, f"필수 키 '{key}'가 결과에 없음"

        # 데이터 타입 검증
        assert isinstance(result["stock_code"], str)
        assert isinstance(result["current_price"], (int, float))
        assert isinstance(result["rsi"], float)
        assert isinstance(result["ma_20"], (int, float))

        # API 호출 검증
        mock_rest_client.get_current_price.assert_called_once_with(stock_code)
        mock_rest_client.get_stock_info.assert_called_once_with(stock_code)
        mock_rest_client.get_daily_chart.assert_called_once_with(stock_code, period_days=120)

    def test_rsi_calculation_is_within_valid_range(
        self,
        screener_with_mock,
        mock_rest_client,
        sample_price_data,
        sample_stock_info,
        sample_chart_data
    ):
        """
        테스트: RSI 계산이 올바른가?

        검증 항목:
        - RSI가 0~100 범위 내에 있는가?
        - 상승 추세 데이터에서 RSI > 50인가?
        """
        # Arrange
        stock_code = "005930"
        mock_rest_client.get_current_price.return_value = sample_price_data
        mock_rest_client.get_stock_info.return_value = sample_stock_info
        mock_rest_client.get_daily_chart.return_value = sample_chart_data

        # Act
        result = screener_with_mock._fetch_stock_data(stock_code)

        # Assert
        assert 0 <= result["rsi"] <= 100, f"RSI는 0~100 범위여야 함 (실제: {result['rsi']})"

        # 샘플 데이터는 상승 추세이므로 RSI > 50 기대
        assert result["rsi"] > 50, "상승 추세에서 RSI는 50보다 커야 함"

    def test_moving_averages_calculation(
        self,
        screener_with_mock,
        mock_rest_client,
        sample_price_data,
        sample_stock_info,
        sample_chart_data
    ):
        """
        테스트: 이동평균 계산이 올바른가?

        검증 항목:
        - MA20, MA60, MA120이 양수인가?
        - 상승 추세에서 MA20 > MA60 > MA120인가?
        """
        # Arrange
        stock_code = "005930"
        mock_rest_client.get_current_price.return_value = sample_price_data
        mock_rest_client.get_stock_info.return_value = sample_stock_info
        mock_rest_client.get_daily_chart.return_value = sample_chart_data

        # Act
        result = screener_with_mock._fetch_stock_data(stock_code)

        # Assert
        assert result["ma_20"] > 0, "MA20은 양수여야 함"
        assert result["ma_60"] > 0, "MA60은 양수여야 함"
        assert result["ma_120"] > 0, "MA120은 양수여야 함"

        # 상승 추세에서는 단기 이평선이 장기 이평선보다 위에 있음
        assert result["ma_20"] > result["ma_60"], "MA20 > MA60 (상승 추세)"
        assert result["ma_60"] > result["ma_120"], "MA60 > MA120 (상승 추세)"

    def test_price_momentum_calculation(
        self,
        screener_with_mock,
        mock_rest_client,
        sample_price_data,
        sample_stock_info,
        sample_chart_data
    ):
        """
        테스트: 가격 모멘텀 계산이 올바른가?

        검증 항목:
        - 1개월, 3개월, 6개월 모멘텀이 계산되는가?
        - 상승 추세에서 모멘텀 > 0인가?
        """
        # Arrange
        stock_code = "005930"
        mock_rest_client.get_current_price.return_value = sample_price_data
        mock_rest_client.get_stock_info.return_value = sample_stock_info
        mock_rest_client.get_daily_chart.return_value = sample_chart_data

        # Act
        result = screener_with_mock._fetch_stock_data(stock_code)

        # Assert
        assert "price_momentum_1m" in result
        assert "price_momentum_3m" in result
        assert "price_momentum_6m" in result

        # 상승 추세 데이터이므로 모멘텀 > 0 기대
        assert result["price_momentum_1m"] > 0, "1개월 모멘텀 > 0 (상승 추세)"
        assert result["price_momentum_3m"] > 0, "3개월 모멘텀 > 0 (상승 추세)"
        assert result["price_momentum_6m"] > 0, "6개월 모멘텀 > 0 (상승 추세)"

    def test_volume_ratio_calculation(
        self,
        screener_with_mock,
        mock_rest_client,
        sample_price_data,
        sample_stock_info,
        sample_chart_data
    ):
        """
        테스트: 거래량 비율 계산이 올바른가?

        검증 항목:
        - volume_ratio >= 0인가?
        - 계산 로직이 올바른가?
        """
        # Arrange
        stock_code = "005930"
        mock_rest_client.get_current_price.return_value = sample_price_data
        mock_rest_client.get_stock_info.return_value = sample_stock_info
        mock_rest_client.get_daily_chart.return_value = sample_chart_data

        # Act
        result = screener_with_mock._fetch_stock_data(stock_code)

        # Assert
        assert result["volume_ratio"] >= 0, "거래량 비율은 0 이상이어야 함"

        # 수동 계산 검증
        avg_volume = sample_chart_data["volume"].tail(20).mean()
        expected_ratio = sample_price_data["volume"] / avg_volume
        assert abs(result["volume_ratio"] - expected_ratio) < 0.01, \
            f"거래량 비율 계산 오류 (기대: {expected_ratio:.2f}, 실제: {result['volume_ratio']:.2f})"

    def test_volatility_calculation(
        self,
        screener_with_mock,
        mock_rest_client,
        sample_price_data,
        sample_stock_info,
        sample_chart_data
    ):
        """
        테스트: 변동성 계산이 올바른가?

        검증 항목:
        - volatility >= 0인가?
        - 연율화된 표준편차인가?
        """
        # Arrange
        stock_code = "005930"
        mock_rest_client.get_current_price.return_value = sample_price_data
        mock_rest_client.get_stock_info.return_value = sample_stock_info
        mock_rest_client.get_daily_chart.return_value = sample_chart_data

        # Act
        result = screener_with_mock._fetch_stock_data(stock_code)

        # Assert
        assert result["volatility"] >= 0, "변동성은 0 이상이어야 함"
        assert result["volatility"] < 5.0, "변동성이 너무 큼 (비정상적)"


class TestFetchStockDataAPIFailure:
    """API 호출 실패 케이스"""

    def test_returns_none_when_get_current_price_fails(
        self,
        screener_with_mock,
        mock_rest_client
    ):
        """
        테스트: get_current_price 실패 시 None 반환하는가?
        """
        # Arrange
        stock_code = "005930"
        mock_rest_client.get_current_price.return_value = None

        # Act
        result = screener_with_mock._fetch_stock_data(stock_code)

        # Assert
        assert result is None, "현재가 조회 실패 시 None 반환해야 함"
        mock_rest_client.get_current_price.assert_called_once_with(stock_code)

    def test_handles_exception_in_api_call(
        self,
        screener_with_mock,
        mock_rest_client
    ):
        """
        테스트: API 호출 중 예외 발생 시 None 반환하는가?
        """
        # Arrange
        stock_code = "005930"
        mock_rest_client.get_current_price.side_effect = Exception("Network error")

        # Act
        result = screener_with_mock._fetch_stock_data(stock_code)

        # Assert
        assert result is None, "예외 발생 시 None 반환해야 함"


class TestFetchStockDataEmptyChartData:
    """빈 차트 데이터 처리"""

    def test_handles_empty_chart_data(
        self,
        screener_with_mock,
        mock_rest_client,
        sample_price_data,
        sample_stock_info
    ):
        """
        테스트: 차트 데이터가 없을 때 기본값 사용하는가?

        검증 항목:
        - 빈 DataFrame 반환 시 기본값 사용
        - MA = 현재가
        - RSI = 50.0
        """
        # Arrange
        stock_code = "005930"
        mock_rest_client.get_current_price.return_value = sample_price_data
        mock_rest_client.get_stock_info.return_value = sample_stock_info
        mock_rest_client.get_daily_chart.return_value = pd.DataFrame()  # 빈 DataFrame

        # Act
        result = screener_with_mock._fetch_stock_data(stock_code)

        # Assert
        assert result is not None, "빈 차트 데이터에도 결과 반환해야 함"
        assert result["ma_20"] == sample_price_data["current_price"], "MA20 = 현재가"
        assert result["ma_60"] == sample_price_data["current_price"], "MA60 = 현재가"
        assert result["ma_120"] == sample_price_data["current_price"], "MA120 = 현재가"
        assert result["rsi"] == 50.0, "RSI = 50.0 (기본값)"
        assert result["volume_ratio"] == 1.0, "거래량 비율 = 1.0 (기본값)"

    def test_handles_none_chart_data(
        self,
        screener_with_mock,
        mock_rest_client,
        sample_price_data,
        sample_stock_info
    ):
        """
        테스트: 차트 데이터가 None일 때 기본값 사용하는가?
        """
        # Arrange
        stock_code = "005930"
        mock_rest_client.get_current_price.return_value = sample_price_data
        mock_rest_client.get_stock_info.return_value = sample_stock_info
        mock_rest_client.get_daily_chart.return_value = None

        # Act
        result = screener_with_mock._fetch_stock_data(stock_code)

        # Assert
        assert result is not None
        assert result["rsi"] == 50.0
        assert result["volume_ratio"] == 1.0


class TestFetchStockDataShortChartData:
    """짧은 차트 데이터 처리 (부분 지표 계산)"""

    def test_handles_short_chart_for_ma20(
        self,
        screener_with_mock,
        mock_rest_client,
        sample_price_data,
        sample_stock_info
    ):
        """
        테스트: 20일 미만 데이터 시 MA20 = 현재가인가?
        """
        # Arrange
        stock_code = "005930"
        short_chart = pd.DataFrame({
            "date": pd.date_range(end=datetime.now(), periods=10, freq="D"),
            "close": [45000 + i*100 for i in range(10)],
            "volume": [1000000]*10,
        })

        mock_rest_client.get_current_price.return_value = sample_price_data
        mock_rest_client.get_stock_info.return_value = sample_stock_info
        mock_rest_client.get_daily_chart.return_value = short_chart

        # Act
        result = screener_with_mock._fetch_stock_data(stock_code)

        # Assert
        assert result["ma_20"] == sample_price_data["current_price"], \
            "20일 미만 데이터 시 MA20 = 현재가"

    def test_handles_short_chart_for_rsi(
        self,
        screener_with_mock,
        mock_rest_client,
        sample_price_data,
        sample_stock_info
    ):
        """
        테스트: 15일 미만 데이터 시 RSI = 50.0인가?
        """
        # Arrange
        stock_code = "005930"
        short_chart = pd.DataFrame({
            "date": pd.date_range(end=datetime.now(), periods=10, freq="D"),
            "close": [45000 + i*100 for i in range(10)],
            "volume": [1000000]*10,
        })

        mock_rest_client.get_current_price.return_value = sample_price_data
        mock_rest_client.get_stock_info.return_value = sample_stock_info
        mock_rest_client.get_daily_chart.return_value = short_chart

        # Act
        result = screener_with_mock._fetch_stock_data(stock_code)

        # Assert
        assert result["rsi"] == 50.0, "15일 미만 데이터 시 RSI = 50.0"


class TestFetchStockDataStockInfoFailure:
    """종목 상세 정보 조회 실패"""

    def test_handles_none_stock_info(
        self,
        screener_with_mock,
        mock_rest_client,
        sample_price_data,
        sample_chart_data
    ):
        """
        테스트: get_stock_info 실패 시 기본값(0) 사용하는가?
        """
        # Arrange
        stock_code = "005930"
        mock_rest_client.get_current_price.return_value = sample_price_data
        mock_rest_client.get_stock_info.return_value = None
        mock_rest_client.get_daily_chart.return_value = sample_chart_data

        # Act
        result = screener_with_mock._fetch_stock_data(stock_code)

        # Assert
        assert result is not None
        assert result["market_cap"] == 0, "시가총액 기본값 = 0"
        assert result["per"] == 0, "PER 기본값 = 0"
        assert result["pbr"] == 0, "PBR 기본값 = 0"


class TestFetchStockDataSectorClassification:
    """섹터 분류 로직"""

    def test_sector_classification_from_stock_list(
        self,
        screener_with_mock,
        mock_rest_client,
        sample_price_data,
        sample_stock_info,
        sample_chart_data
    ):
        """
        테스트: 종목 리스트 파일에서 섹터 정보 로드하는가?

        (주의: 파일 I/O가 있으므로 실제 파일 또는 Mock 필요)
        """
        # Arrange
        stock_code = "005930"
        mock_rest_client.get_current_price.return_value = sample_price_data
        mock_rest_client.get_stock_info.return_value = sample_stock_info
        mock_rest_client.get_daily_chart.return_value = sample_chart_data

        # Act
        result = screener_with_mock._fetch_stock_data(stock_code)

        # Assert
        assert "sector" in result
        assert isinstance(result["sector"], str)
        # 삼성전자 → 반도체 (하드코딩된 매핑)
        assert result["sector"] == "반도체", "005930은 반도체 섹터"


class TestFetchStockDataEdgeCases:
    """엣지 케이스"""

    def test_handles_zero_division_in_rsi(
        self,
        screener_with_mock,
        mock_rest_client,
        sample_price_data,
        sample_stock_info
    ):
        """
        테스트: RSI 계산 시 0으로 나누기 처리

        시나리오: avg_loss = 0 (연속 상승)
        """
        # Arrange
        stock_code = "005930"

        # 연속 상승 데이터 (loss = 0)
        up_only_chart = pd.DataFrame({
            "date": pd.date_range(end=datetime.now(), periods=20, freq="D"),
            "close": [40000 + i*1000 for i in range(20)],  # 연속 상승
            "volume": [1000000]*20,
        })

        mock_rest_client.get_current_price.return_value = sample_price_data
        mock_rest_client.get_stock_info.return_value = sample_stock_info
        mock_rest_client.get_daily_chart.return_value = up_only_chart

        # Act
        result = screener_with_mock._fetch_stock_data(stock_code)

        # Assert
        assert result["rsi"] == 100.0, "연속 상승 시 RSI = 100.0"

    def test_handles_zero_volume_in_volume_ratio(
        self,
        screener_with_mock,
        mock_rest_client,
        sample_price_data,
        sample_stock_info
    ):
        """
        테스트: 거래량 비율 계산 시 0으로 나누기 처리
        """
        # Arrange
        stock_code = "005930"

        # 평균 거래량 = 0인 차트 (비현실적이지만 테스트용)
        zero_volume_chart = pd.DataFrame({
            "date": pd.date_range(end=datetime.now(), periods=20, freq="D"),
            "close": [50000]*20,
            "volume": [0]*20,  # 거래량 0
        })

        mock_rest_client.get_current_price.return_value = sample_price_data
        mock_rest_client.get_stock_info.return_value = sample_stock_info
        mock_rest_client.get_daily_chart.return_value = zero_volume_chart

        # Act
        result = screener_with_mock._fetch_stock_data(stock_code)

        # Assert
        # avg_volume = 0 → volume_ratio = 1.0 (기본값)
        assert result["volume_ratio"] == 1.0, "평균 거래량 0 시 기본값 1.0"
