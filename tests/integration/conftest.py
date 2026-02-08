#!/usr/bin/env python3
"""
통합 테스트용 pytest fixtures
"""

import json
import pytest
from unittest.mock import MagicMock, patch
from typing import Dict, List


@pytest.fixture
def temp_data_dir(tmp_path):
    """임시 데이터 디렉토리 fixture

    테스트 종료 후 자동으로 정리됩니다.

    Yields:
        Path: 임시 데이터 디렉토리 경로
    """
    # 임시 데이터 디렉토리 생성
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    # 하위 디렉토리 생성
    watchlist_dir = data_dir / "watchlist"
    watchlist_dir.mkdir()

    daily_selection_dir = data_dir / "daily_selection"
    daily_selection_dir.mkdir()

    yield data_dir

    # 테스트 종료 후 자동 정리 (pytest가 tmp_path 처리)


@pytest.fixture
def mock_kis_api():
    """KISAPI 모킹 fixture

    실제 API 호출 없이 테스트용 데이터를 반환합니다.

    Yields:
        MagicMock: 모킹된 KISAPI 인스턴스
    """
    with patch('core.api.kis_api.KISAPI') as mock_cls:
        mock_instance = MagicMock()

        # 기본 메서드 모킹
        mock_instance.get_access_token.return_value = True
        mock_instance.get_balance.return_value = {
            'output1': {'tot_evlu_amt': '10000000'},  # 1천만원
            'output2': []
        }
        mock_instance.get_holdings.return_value = []

        # 가격 데이터 모킹
        import pandas as pd
        import numpy as np

        dates = pd.date_range('2024-01-01', periods=60, freq='D')
        mock_price_data = pd.DataFrame({
            'date': dates,
            'open': np.random.uniform(50000, 52000, 60),
            'high': np.random.uniform(52000, 53000, 60),
            'low': np.random.uniform(49000, 50000, 60),
            'close': np.random.uniform(50000, 52000, 60),
            'volume': np.random.uniform(1000000, 2000000, 60)
        })
        mock_price_data.set_index('date', inplace=True)

        mock_instance.get_daily_prices.return_value = mock_price_data
        mock_instance.get_stock_history.return_value = mock_price_data

        # 종목 정보 모킹
        mock_instance.get_stock_info.return_value = {
            'output': {
                'stck_prpr': '51000',  # 현재가
                'prdy_vrss': '1000',   # 전일대비
                'prdy_ctrt': '2.00',   # 등락률
                'acml_vol': '1500000'  # 거래량
            }
        }

        mock_cls.return_value = mock_instance

        yield mock_instance


@pytest.fixture
def mock_redis():
    """Redis 모킹 fixture (선택)

    캐싱 기능을 모킹하여 실제 Redis 없이 테스트합니다.

    Yields:
        MagicMock: 모킹된 Redis 클라이언트
    """
    with patch('redis.Redis') as mock_redis_cls:
        mock_client = MagicMock()

        # 기본 Redis 메서드 모킹
        mock_client.get.return_value = None
        mock_client.set.return_value = True
        mock_client.delete.return_value = 1
        mock_client.exists.return_value = False
        mock_client.ping.return_value = True

        mock_redis_cls.return_value = mock_client

        yield mock_client


@pytest.fixture
def sample_watchlist() -> List[Dict]:
    """테스트용 감시 리스트 fixture

    10개 종목의 샘플 데이터를 제공합니다.

    Returns:
        List[Dict]: 감시 리스트 데이터
    """
    return [
        {
            "stock_code": "005930",
            "stock_name": "삼성전자",
            "technical_score": 75.5,
            "financial_score": 80.2,
            "momentum_score": 70.0,
            "total_score": 75.2,
            "current_price": 71000,
            "volume": 15000000,
            "market_cap": 423000000000000,
            "sector": "전기전자"
        },
        {
            "stock_code": "000660",
            "stock_name": "SK하이닉스",
            "technical_score": 78.0,
            "financial_score": 82.5,
            "momentum_score": 75.0,
            "total_score": 78.5,
            "current_price": 135000,
            "volume": 8000000,
            "market_cap": 98000000000000,
            "sector": "전기전자"
        },
        {
            "stock_code": "035420",
            "stock_name": "NAVER",
            "technical_score": 72.0,
            "financial_score": 70.0,
            "momentum_score": 68.0,
            "total_score": 70.0,
            "current_price": 210000,
            "volume": 500000,
            "market_cap": 34500000000000,
            "sector": "서비스업"
        },
        {
            "stock_code": "035720",
            "stock_name": "카카오",
            "technical_score": 70.0,
            "financial_score": 68.0,
            "momentum_score": 65.0,
            "total_score": 67.7,
            "current_price": 48000,
            "volume": 1200000,
            "market_cap": 21000000000000,
            "sector": "서비스업"
        },
        {
            "stock_code": "051910",
            "stock_name": "LG화학",
            "technical_score": 68.0,
            "financial_score": 75.0,
            "momentum_score": 70.0,
            "total_score": 71.0,
            "current_price": 380000,
            "volume": 300000,
            "market_cap": 26800000000000,
            "sector": "화학"
        },
        {
            "stock_code": "006400",
            "stock_name": "삼성SDI",
            "technical_score": 73.0,
            "financial_score": 77.0,
            "momentum_score": 72.0,
            "total_score": 74.0,
            "current_price": 425000,
            "volume": 250000,
            "market_cap": 29800000000000,
            "sector": "전기전자"
        },
        {
            "stock_code": "207940",
            "stock_name": "삼성바이오로직스",
            "technical_score": 69.0,
            "financial_score": 73.0,
            "momentum_score": 68.0,
            "total_score": 70.0,
            "current_price": 850000,
            "volume": 50000,
            "market_cap": 60500000000000,
            "sector": "의약품"
        },
        {
            "stock_code": "005380",
            "stock_name": "현대차",
            "technical_score": 71.0,
            "financial_score": 74.0,
            "momentum_score": 69.0,
            "total_score": 71.3,
            "current_price": 210000,
            "volume": 800000,
            "market_cap": 45000000000000,
            "sector": "운수장비"
        },
        {
            "stock_code": "000270",
            "stock_name": "기아",
            "technical_score": 70.5,
            "financial_score": 73.0,
            "momentum_score": 68.5,
            "total_score": 70.7,
            "current_price": 95000,
            "volume": 1500000,
            "market_cap": 37800000000000,
            "sector": "운수장비"
        },
        {
            "stock_code": "068270",
            "stock_name": "셀트리온",
            "technical_score": 72.5,
            "financial_score": 71.0,
            "momentum_score": 70.0,
            "total_score": 71.2,
            "current_price": 180000,
            "volume": 600000,
            "market_cap": 24500000000000,
            "sector": "의약품"
        }
    ]


@pytest.fixture
def sample_daily_selection() -> List[Dict]:
    """테스트용 일일 선정 fixture

    3개 종목의 샘플 일일 선정 데이터를 제공합니다.

    Returns:
        List[Dict]: 일일 선정 데이터
    """
    return [
        {
            "stock_code": "005930",
            "stock_name": "삼성전자",
            "entry_price": 71000,
            "target_price": 77000,
            "stop_loss": 67500,
            "confidence": 85.0,
            "technical_score": 82.0,
            "price_attractiveness": 78.0,
            "market_condition": 75.0,
            "risk_score": 20.0,
            "total_score": 80.0,
            "signal_strength": 3,
            "support_level": 69000,
            "resistance_level": 75000,
            "volatility": 0.025,
            "selection_reason": "기술적 반등 + 저평가"
        },
        {
            "stock_code": "000660",
            "stock_name": "SK하이닉스",
            "entry_price": 135000,
            "target_price": 148000,
            "stop_loss": 128000,
            "confidence": 82.0,
            "technical_score": 80.0,
            "price_attractiveness": 75.0,
            "market_condition": 72.0,
            "risk_score": 25.0,
            "total_score": 76.0,
            "signal_strength": 2,
            "support_level": 130000,
            "resistance_level": 145000,
            "volatility": 0.03,
            "selection_reason": "섹터 강세 + 추세 전환"
        },
        {
            "stock_code": "035420",
            "stock_name": "NAVER",
            "entry_price": 210000,
            "target_price": 230000,
            "stop_loss": 199000,
            "confidence": 78.0,
            "technical_score": 75.0,
            "price_attractiveness": 72.0,
            "market_condition": 70.0,
            "risk_score": 22.0,
            "total_score": 72.3,
            "signal_strength": 2,
            "support_level": 205000,
            "resistance_level": 220000,
            "volatility": 0.028,
            "selection_reason": "거래량 급증 + 돌파 시도"
        }
    ]


@pytest.fixture
def sample_watchlist_file(temp_data_dir, sample_watchlist):
    """감시 리스트 파일 fixture

    임시 디렉토리에 감시 리스트 파일을 생성합니다.

    Args:
        temp_data_dir: 임시 데이터 디렉토리
        sample_watchlist: 감시 리스트 데이터

    Returns:
        Path: 생성된 파일 경로
    """
    file_path = temp_data_dir / "watchlist" / "watchlist.json"

    data = {
        "date": "2024-01-15",
        "stocks": sample_watchlist,
        "total_count": len(sample_watchlist)
    }

    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return file_path


@pytest.fixture
def sample_daily_selection_file(temp_data_dir, sample_daily_selection):
    """일일 선정 파일 fixture

    임시 디렉토리에 일일 선정 파일을 생성합니다.

    Args:
        temp_data_dir: 임시 데이터 디렉토리
        sample_daily_selection: 일일 선정 데이터

    Returns:
        Path: 생성된 파일 경로
    """
    file_path = temp_data_dir / "daily_selection" / "latest_selection.json"

    data = {
        "date": "2024-01-15",
        "selected_stocks": sample_daily_selection,
        "total_count": len(sample_daily_selection)
    }

    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return file_path
