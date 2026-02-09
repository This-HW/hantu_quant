# -*- coding: utf-8 -*-
"""
rest_client.py 입력 검증 통합 테스트

테스트 범위:
- get_daily_chart() 입력 검증
- get_tick_conclusions() 입력 검증
- get_current_price() 입력 검증
- get_stock_info() 입력 검증
- get_orderbook() 입력 검증
- get_investor_flow() 입력 검증
- get_member_flow() 입력 검증
- get_minute_bars() 입력 검증
- place_order() 입력 검증 (MF-1)
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
from datetime import datetime

from core.api.rest_client import KISRestClient
from core.config.api_config import APIConfig


@pytest.fixture
def mock_client():
    """Mock API 클라이언트 생성"""
    with patch('core.api.rest_client.APIConfig') as MockConfig:
        mock_config = Mock(spec=APIConfig)
        mock_config.ensure_valid_token.return_value = True
        mock_config.base_url = "https://mock-api.com"
        mock_config.server = "virtual"
        mock_config.account_number = "12345678"
        mock_config.account_prod_code = "01"
        mock_config.get_headers.return_value = {
            "authorization": "Bearer test_token",
            "appkey": "test_app_key",
            "appsecret": "test_app_secret"
        }
        MockConfig.return_value = mock_config

        client = KISRestClient()
        client.config = mock_config
        yield client


class TestGetDailyChartValidation:
    """get_daily_chart() 입력 검증 테스트"""

    def test_valid_stock_code_and_period(self, mock_client):
        """정상: 유효한 종목코드 및 기간"""
        with patch.object(mock_client, '_request') as mock_request:
            mock_request.return_value = {
                "output2": [
                    {
                        "stck_bsop_date": "20240115",
                        "stck_oprc": "50000",
                        "stck_hgpr": "52000",
                        "stck_lwpr": "49000",
                        "stck_clpr": "51000",
                        "acml_vol": "1000000"
                    }
                ]
            }

            df = mock_client.get_daily_chart("005930", period_days=100)
            assert df is not None
            assert isinstance(df, pd.DataFrame)

    def test_invalid_stock_code_format(self, mock_client):
        """비정상: 잘못된 종목코드 형식"""
        df = mock_client.get_daily_chart("INVALID", period_days=100)
        assert df is None

    def test_invalid_stock_code_short(self, mock_client):
        """비정상: 짧은 종목코드 (5자리)"""
        df = mock_client.get_daily_chart("12345", period_days=100)
        assert df is None

    def test_invalid_stock_code_long(self, mock_client):
        """비정상: 긴 종목코드 (7자리)"""
        df = mock_client.get_daily_chart("1234567", period_days=100)
        assert df is None

    def test_invalid_period_zero(self, mock_client):
        """비정상: 조회 기간 0일"""
        df = mock_client.get_daily_chart("005930", period_days=0)
        assert df is None

    def test_invalid_period_negative(self, mock_client):
        """비정상: 음수 조회 기간"""
        df = mock_client.get_daily_chart("005930", period_days=-10)
        assert df is None

    def test_invalid_period_over_limit(self, mock_client):
        """비정상: 조회 기간 366일 초과"""
        df = mock_client.get_daily_chart("005930", period_days=9999)
        assert df is None

    def test_valid_period_boundary_minimum(self, mock_client):
        """정상: 최소 기간 (1일)"""
        with patch.object(mock_client, '_request') as mock_request:
            mock_request.return_value = {
                "output2": [
                    {
                        "stck_bsop_date": "20240115",
                        "stck_oprc": "50000",
                        "stck_hgpr": "52000",
                        "stck_lwpr": "49000",
                        "stck_clpr": "51000",
                        "acml_vol": "1000000"
                    }
                ]
            }

            df = mock_client.get_daily_chart("005930", period_days=1)
            assert df is not None

    def test_valid_period_boundary_maximum(self, mock_client):
        """정상: 최대 기간 (365일)"""
        with patch.object(mock_client, '_request') as mock_request:
            mock_request.return_value = {
                "output2": [
                    {
                        "stck_bsop_date": "20240115",
                        "stck_oprc": "50000",
                        "stck_hgpr": "52000",
                        "stck_lwpr": "49000",
                        "stck_clpr": "51000",
                        "acml_vol": "1000000"
                    }
                ]
            }

            df = mock_client.get_daily_chart("005930", period_days=365)
            assert df is not None


class TestGetTickConclusionsValidation:
    """get_tick_conclusions() 입력 검증 테스트"""

    def test_valid_stock_code_and_count(self, mock_client):
        """정상: 유효한 종목코드 및 건수"""
        with patch.object(mock_client, '_request') as mock_request:
            mock_request.return_value = {
                "output": [
                    {"stck_cntg_hour": "153000", "stck_prpr": "50000"}
                ]
            }

            df = mock_client.get_tick_conclusions("005930", count=100)
            assert df is not None
            assert isinstance(df, pd.DataFrame)

    def test_invalid_stock_code(self, mock_client):
        """비정상: 잘못된 종목코드"""
        df = mock_client.get_tick_conclusions("INVALID", count=100)
        assert df is None

    def test_invalid_count_zero(self, mock_client):
        """비정상: 조회 건수 0"""
        df = mock_client.get_tick_conclusions("005930", count=0)
        assert df is None

    def test_invalid_count_negative(self, mock_client):
        """비정상: 음수 조회 건수"""
        df = mock_client.get_tick_conclusions("005930", count=-10)
        assert df is None

    def test_invalid_count_over_limit(self, mock_client):
        """비정상: 조회 건수 1000 초과"""
        df = mock_client.get_tick_conclusions("005930", count=1001)
        assert df is None

    def test_valid_count_boundary_minimum(self, mock_client):
        """정상: 최소 건수 (1건)"""
        with patch.object(mock_client, '_request') as mock_request:
            mock_request.return_value = {
                "output": [
                    {"stck_cntg_hour": "153000", "stck_prpr": "50000"}
                ]
            }

            df = mock_client.get_tick_conclusions("005930", count=1)
            assert df is not None

    def test_valid_count_boundary_maximum(self, mock_client):
        """정상: 최대 건수 (1000건)"""
        with patch.object(mock_client, '_request') as mock_request:
            mock_request.return_value = {
                "output": [
                    {"stck_cntg_hour": "153000", "stck_prpr": "50000"}
                ]
            }

            df = mock_client.get_tick_conclusions("005930", count=1000)
            assert df is not None


class TestGetCurrentPriceValidation:
    """get_current_price() 입력 검증 테스트"""

    def test_valid_stock_code(self, mock_client):
        """정상: 유효한 종목코드"""
        with patch.object(mock_client, '_request') as mock_request:
            mock_request.return_value = {
                "output": {
                    "stck_prpr": "50000",
                    "prdy_ctrt": "2.5",
                    "acml_vol": "1000000",
                    "stck_hgpr": "52000",
                    "stck_lwpr": "49000",
                    "stck_oprc": "49500",
                    "hts_avls": "100000000000"
                }
            }

            result = mock_client.get_current_price("005930")
            assert result is not None
            assert result["stock_code"] == "005930"
            assert result["current_price"] == 50000.0

    def test_invalid_stock_code_alphabets(self, mock_client):
        """비정상: 알파벳 포함 종목코드"""
        result = mock_client.get_current_price("INVALID")
        assert result is None

    def test_invalid_stock_code_short(self, mock_client):
        """비정상: 짧은 종목코드"""
        result = mock_client.get_current_price("12345")
        assert result is None

    def test_invalid_stock_code_long(self, mock_client):
        """비정상: 긴 종목코드"""
        result = mock_client.get_current_price("1234567")
        assert result is None

    def test_invalid_stock_code_special_chars(self, mock_client):
        """비정상: 특수문자 포함"""
        result = mock_client.get_current_price("123-45")
        assert result is None

    def test_valid_stock_code_leading_zeros(self, mock_client):
        """정상: 앞에 0이 있는 종목코드"""
        with patch.object(mock_client, '_request') as mock_request:
            mock_request.return_value = {
                "output": {
                    "stck_prpr": "50000",
                    "prdy_ctrt": "2.5",
                    "acml_vol": "1000000",
                    "stck_hgpr": "52000",
                    "stck_lwpr": "49000",
                    "stck_oprc": "49500",
                    "hts_avls": "100000000000"
                }
            }

            result = mock_client.get_current_price("000660")
            assert result is not None
            assert result["stock_code"] == "000660"


class TestGetStockInfoValidation:
    """get_stock_info() 입력 검증 테스트"""

    def test_valid_stock_code(self, mock_client):
        """정상: 유효한 종목코드"""
        with patch.object(mock_client, '_request') as mock_request:
            mock_request.return_value = {
                "output": {
                    "hts_kor_isnm": "삼성전자",
                    "rprs_mrkt_kor_name": "코스피",
                    "stck_prpr": "50000",
                    "hts_avls": "100000000000",
                    "per": "15.5",
                    "pbr": "1.2",
                    "eps": "3000",
                    "bps": "40000"
                }
            }

            result = mock_client.get_stock_info("005930")
            assert result is not None
            assert result["stock_name"] == "삼성전자"

    def test_invalid_stock_code(self, mock_client):
        """비정상: 잘못된 종목코드"""
        result = mock_client.get_stock_info("INVALID")
        assert result is None


class TestGetOrderbookValidation:
    """get_orderbook() 입력 검증 테스트"""

    def test_valid_stock_code(self, mock_client):
        """정상: 유효한 종목코드"""
        with patch.object(mock_client, '_request') as mock_request:
            mock_request.return_value = {
                "output": {
                    "askp1": "51000",
                    "bidp1": "50000"
                }
            }

            result = mock_client.get_orderbook("005930")
            assert result is not None

    def test_invalid_stock_code(self, mock_client):
        """비정상: 잘못된 종목코드"""
        result = mock_client.get_orderbook("INVALID")
        assert result is None


class TestGetInvestorFlowValidation:
    """get_investor_flow() 입력 검증 테스트"""

    def test_valid_stock_code(self, mock_client):
        """정상: 유효한 종목코드"""
        with patch.object(mock_client, '_request') as mock_request:
            mock_request.return_value = {
                "output": {
                    "stck_prpr": "50000"
                }
            }

            result = mock_client.get_investor_flow("005930")
            assert result is not None

    def test_invalid_stock_code(self, mock_client):
        """비정상: 잘못된 종목코드"""
        result = mock_client.get_investor_flow("INVALID")
        assert result is None


class TestGetMemberFlowValidation:
    """get_member_flow() 입력 검증 테스트"""

    def test_valid_stock_code(self, mock_client):
        """정상: 유효한 종목코드"""
        with patch.object(mock_client, '_request') as mock_request:
            mock_request.return_value = {
                "output": {
                    "stck_prpr": "50000"
                }
            }

            result = mock_client.get_member_flow("005930")
            assert result is not None

    def test_invalid_stock_code(self, mock_client):
        """비정상: 잘못된 종목코드"""
        result = mock_client.get_member_flow("INVALID")
        assert result is None


class TestGetMinuteBarsValidation:
    """get_minute_bars() 입력 검증 테스트"""

    def test_valid_stock_code_and_count(self, mock_client):
        """정상: 유효한 종목코드 및 건수"""
        with patch.object(mock_client, '_request') as mock_request:
            mock_request.return_value = {
                "output2": [
                    {"stck_cntg_hour": "153000", "stck_prpr": "50000"}
                ]
            }

            df = mock_client.get_minute_bars("005930", count=60)
            assert df is not None
            assert isinstance(df, pd.DataFrame)

    def test_invalid_stock_code(self, mock_client):
        """비정상: 잘못된 종목코드"""
        df = mock_client.get_minute_bars("INVALID", count=60)
        assert df is None

    def test_invalid_count_zero(self, mock_client):
        """비정상: 조회 건수 0"""
        df = mock_client.get_minute_bars("005930", count=0)
        assert df is None

    def test_invalid_count_over_limit(self, mock_client):
        """비정상: 조회 건수 1000 초과"""
        df = mock_client.get_minute_bars("005930", count=1001)
        assert df is None

    def test_valid_count_boundary(self, mock_client):
        """정상: 최대 건수 (1000건)"""
        with patch.object(mock_client, '_request') as mock_request:
            mock_request.return_value = {
                "output2": [
                    {"stck_cntg_hour": "153000", "stck_prpr": "50000"}
                ]
            }

            df = mock_client.get_minute_bars("005930", count=1000)
            assert df is not None


class TestPlaceOrderValidation:
    """place_order() 입력 검증 테스트 (MF-1 수정 검증)"""

    def test_valid_limit_buy_order(self, mock_client):
        """정상: 유효한 지정가 매수 주문"""
        with patch.object(mock_client, '_request') as mock_request:
            with patch.object(mock_client, '_get_hashkey') as mock_hashkey:
                mock_hashkey.return_value = "test_hash"
                mock_request.return_value = {
                    "rt_cd": "0",
                    "msg1": "주문 성공",
                    "output": {"order_id": "12345"}
                }

                result = mock_client.place_order(
                    stock_code="005930",
                    order_type="02",  # 매수
                    quantity=10,
                    price=60000,
                    order_division="00"  # 지정가
                )

                assert result is not None
                assert result["success"] is True

    def test_valid_market_sell_order(self, mock_client):
        """정상: 유효한 시장가 매도 주문"""
        with patch.object(mock_client, '_request') as mock_request:
            with patch.object(mock_client, '_get_hashkey') as mock_hashkey:
                mock_hashkey.return_value = "test_hash"
                mock_request.return_value = {
                    "rt_cd": "0",
                    "msg1": "주문 성공",
                    "output": {"order_id": "12345"}
                }

                result = mock_client.place_order(
                    stock_code="005930",
                    order_type="01",  # 매도
                    quantity=5,
                    price=0,
                    order_division="01"  # 시장가
                )

                assert result is not None
                assert result["success"] is True

    def test_invalid_stock_code_alphabets(self, mock_client):
        """비정상: 알파벳 포함 종목코드"""
        result = mock_client.place_order(
            stock_code="INVALID",
            order_type="02",
            quantity=10,
            price=60000
        )

        assert result is not None
        assert result["success"] is False
        assert result["error_code"] == "VALIDATION_ERROR"

    def test_invalid_stock_code_short(self, mock_client):
        """비정상: 짧은 종목코드 (5자리)"""
        result = mock_client.place_order(
            stock_code="12345",
            order_type="02",
            quantity=10,
            price=60000
        )

        assert result is not None
        assert result["success"] is False
        assert result["error_code"] == "VALIDATION_ERROR"

    def test_invalid_stock_code_long(self, mock_client):
        """비정상: 긴 종목코드 (7자리)"""
        result = mock_client.place_order(
            stock_code="1234567",
            order_type="02",
            quantity=10,
            price=60000
        )

        assert result is not None
        assert result["success"] is False
        assert result["error_code"] == "VALIDATION_ERROR"

    def test_invalid_quantity_zero(self, mock_client):
        """비정상: 주문 수량 0"""
        result = mock_client.place_order(
            stock_code="005930",
            order_type="02",
            quantity=0,
            price=60000
        )

        assert result is not None
        assert result["success"] is False
        assert result["error_code"] == "VALIDATION_ERROR"

    def test_invalid_quantity_negative(self, mock_client):
        """비정상: 주문 수량 음수"""
        result = mock_client.place_order(
            stock_code="005930",
            order_type="02",
            quantity=-10,
            price=60000
        )

        assert result is not None
        assert result["success"] is False
        assert result["error_code"] == "VALIDATION_ERROR"

    def test_invalid_quantity_over_limit(self, mock_client):
        """비정상: 주문 수량 10000 초과"""
        result = mock_client.place_order(
            stock_code="005930",
            order_type="02",
            quantity=10001,
            price=60000
        )

        assert result is not None
        assert result["success"] is False
        assert result["error_code"] == "VALIDATION_ERROR"

    def test_invalid_limit_order_zero_price(self, mock_client):
        """비정상: 지정가 주문에 가격 0"""
        result = mock_client.place_order(
            stock_code="005930",
            order_type="02",
            quantity=10,
            price=0,
            order_division="00"  # 지정가
        )

        assert result is not None
        assert result["success"] is False
        assert result["error_code"] == "VALIDATION_ERROR"

    def test_invalid_limit_order_negative_price(self, mock_client):
        """비정상: 지정가 주문에 음수 가격"""
        result = mock_client.place_order(
            stock_code="005930",
            order_type="02",
            quantity=10,
            price=-1000,
            order_division="00"  # 지정가
        )

        assert result is not None
        assert result["success"] is False
        assert result["error_code"] == "VALIDATION_ERROR"

    def test_valid_quantity_boundary_minimum(self, mock_client):
        """정상: 최소 수량 (1개)"""
        with patch.object(mock_client, '_request') as mock_request:
            with patch.object(mock_client, '_get_hashkey') as mock_hashkey:
                mock_hashkey.return_value = "test_hash"
                mock_request.return_value = {
                    "rt_cd": "0",
                    "msg1": "주문 성공",
                    "output": {"order_id": "12345"}
                }

                result = mock_client.place_order(
                    stock_code="005930",
                    order_type="02",
                    quantity=1,
                    price=60000
                )

                assert result is not None
                assert result["success"] is True

    def test_valid_quantity_boundary_maximum(self, mock_client):
        """정상: 최대 수량 (10000개)"""
        with patch.object(mock_client, '_request') as mock_request:
            with patch.object(mock_client, '_get_hashkey') as mock_hashkey:
                mock_hashkey.return_value = "test_hash"
                mock_request.return_value = {
                    "rt_cd": "0",
                    "msg1": "주문 성공",
                    "output": {"order_id": "12345"}
                }

                result = mock_client.place_order(
                    stock_code="005930",
                    order_type="02",
                    quantity=10000,
                    price=60000
                )

                assert result is not None
                assert result["success"] is True


class TestValidationErrorMessages:
    """검증 실패 시 에러 메시지 확인"""

    def test_period_days_error_message(self, mock_client):
        """PeriodDays 검증 실패 메시지"""
        df = mock_client.get_daily_chart("005930", period_days=0)
        assert df is None
        # 로그에 "조회 기간은 최소 1일입니다" 메시지 기록됨

    def test_count_range_error_message(self, mock_client):
        """CountRange 검증 실패 메시지"""
        df = mock_client.get_tick_conclusions("005930", count=1001)
        assert df is None
        # 로그에 "조회 건수는 최대 1000건입니다" 메시지 기록됨

    def test_stock_code_error_message(self, mock_client):
        """StockCode 검증 실패 메시지"""
        result = mock_client.get_current_price("INVALID")
        assert result is None
        # 로그에 "종목코드 형식 오류" 메시지 기록됨
