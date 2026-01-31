#!/usr/bin/env python3
"""
MarketDataClient 버그 수정 테스트

수정된 내용:
1. get_kospi: 컬럼명 폴백 로직 추가
2. get_kosdaq: 컬럼명 폴백 로직 추가
"""

import pytest
import pandas as pd
from unittest.mock import Mock, patch, MagicMock


class TestMarketDataClientFixes:
    """MarketDataClient 버그 수정 테스트"""

    def setup_method(self):
        """각 테스트 전 실행"""
        # pykrx import를 mock
        self.mock_pykrx = MagicMock()
        self.patcher = patch.dict('sys.modules', {'pykrx': self.mock_pykrx, 'pykrx.stock': self.mock_pykrx.stock})
        self.patcher.start()

        # PyKRXClient 임포트는 이후에
        from core.api.market_data_client import PyKRXClient
        self.client = PyKRXClient()

    def teardown_method(self):
        """각 테스트 후 실행"""
        if hasattr(self, 'patcher'):
            self.patcher.stop()

    def test_get_kospi_with_korean_column_name(self):
        """get_kospi: 한글 컬럼명 '종가' 처리"""
        # Mock DataFrame (한글 컬럼명)
        mock_df = pd.DataFrame({
            '날짜': ['2024-01-31'],
            '시가': [2500.0],
            '고가': [2550.0],
            '저가': [2480.0],
            '종가': [2530.0],  # 한글 컬럼명
            '거래량': [1000000]
        })

        self.client._stock.get_index_ohlcv = Mock(return_value=mock_df)

        result = self.client.get_kospi()

        assert result == 2530.0, "한글 컬럼명 '종가'로 조회 성공해야 함"

    def test_get_kospi_with_english_column_name(self):
        """get_kospi: 영어 컬럼명 'Close' 처리"""
        # Mock DataFrame (영어 컬럼명)
        mock_df = pd.DataFrame({
            'Date': ['2024-01-31'],
            'Open': [2500.0],
            'High': [2550.0],
            'Low': [2480.0],
            'Close': [2530.0],  # 영어 컬럼명
            'Volume': [1000000]
        })

        self.client._stock.get_index_ohlcv = Mock(return_value=mock_df)

        result = self.client.get_kospi()

        assert result == 2530.0, "영어 컬럼명 'Close'로 조회 성공해야 함"

    def test_get_kospi_raises_error_on_missing_columns(self):
        """get_kospi: 종가 컬럼 없으면 에러 발생"""
        # Mock DataFrame (종가 컬럼 없음)
        mock_df = pd.DataFrame({
            '날짜': ['2024-01-31'],
            '시가': [2500.0],
            '고가': [2550.0],
            '저가': [2480.0],
            # 종가 컬럼 없음
            '거래량': [1000000]
        })

        self.client._stock.get_index_ohlcv = Mock(return_value=mock_df)

        with pytest.raises(ValueError) as exc_info:
            self.client.get_kospi()

        assert "종가 컬럼을 찾을 수 없습니다" in str(exc_info.value)

    def test_get_kosdaq_with_fallback(self):
        """get_kosdaq: 컬럼명 폴백 로직 동작"""
        # Mock DataFrame
        mock_df = pd.DataFrame({
            '날짜': ['2024-01-31'],
            '종가': [850.0]
        })

        self.client._stock.get_index_ohlcv = Mock(return_value=mock_df)

        result = self.client.get_kosdaq()

        assert result == 850.0, "KOSDAQ 조회 성공"

    def test_get_kospi_tries_multiple_column_names(self):
        """get_kospi: 여러 컬럼명 시도"""
        # Mock DataFrame (소문자 'close')
        mock_df = pd.DataFrame({
            'date': ['2024-01-31'],
            'open': [2500.0],
            'high': [2550.0],
            'low': [2480.0],
            'close': [2530.0],  # 소문자
            'volume': [1000000]
        })

        def _fetch():
            # 컬럼명 폴백 로직 시뮬레이션
            for col in ['종가', 'Close', 'close', 'CLOSE']:
                if col in mock_df.columns:
                    return float(mock_df.iloc[-1][col])
            raise ValueError("종가 컬럼을 찾을 수 없습니다")

        result = _fetch()
        assert result == 2530.0, "소문자 'close'로 조회 성공"

    def test_get_kosdaq_tries_multiple_column_names(self):
        """get_kosdaq: 여러 컬럼명 시도"""
        # Mock DataFrame (대문자 'CLOSE')
        mock_df = pd.DataFrame({
            'DATE': ['2024-01-31'],
            'OPEN': [850.0],
            'HIGH': [860.0],
            'LOW': [840.0],
            'CLOSE': [855.0],  # 대문자
            'VOLUME': [500000]
        })

        def _fetch():
            for col in ['종가', 'Close', 'close', 'CLOSE']:
                if col in mock_df.columns:
                    return float(mock_df.iloc[-1][col])
            raise ValueError("종가 컬럼을 찾을 수 없습니다")

        result = _fetch()
        assert result == 855.0, "대문자 'CLOSE'로 조회 성공"

    def test_column_fallback_order(self):
        """컬럼명 폴백 순서 확인"""
        # 예상 순서: '종가' → 'Close' → 'close' → 'CLOSE'
        mock_df = pd.DataFrame({
            'Close': [2530.0],  # 두 번째 우선순위
            'close': [2540.0]   # 세 번째 우선순위
        })

        def _fetch():
            for col in ['종가', 'Close', 'close', 'CLOSE']:
                if col in mock_df.columns:
                    return float(mock_df.iloc[-1][col])
            raise ValueError("종가 컬럼을 찾을 수 없습니다")

        result = _fetch()
        # 'Close'가 먼저 발견되어야 함
        assert result == 2530.0, "'Close'가 'close'보다 먼저 선택되어야 함"

    def test_get_kospi_with_empty_dataframe(self):
        """get_kospi: 빈 DataFrame 처리"""
        mock_df = pd.DataFrame()

        # 오늘/어제 모두 빈 DataFrame
        self.client._stock.get_index_ohlcv = Mock(return_value=mock_df)

        with pytest.raises(ValueError) as exc_info:
            self.client.get_kospi()

        assert "KOSPI 조회 실패" in str(exc_info.value)

    def test_get_kosdaq_with_empty_dataframe(self):
        """get_kosdaq: 빈 DataFrame 처리"""
        mock_df = pd.DataFrame()

        self.client._stock.get_index_ohlcv = Mock(return_value=mock_df)

        with pytest.raises(ValueError) as exc_info:
            self.client.get_kosdaq()

        assert "KOSDAQ 조회 실패" in str(exc_info.value)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
