#!/usr/bin/env python3
"""
MarketRegimeDetector 단위 테스트
TDD Red-Green-Refactor 사이클
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
import numpy as np

from core.market.market_regime import (
    MarketRegime,
    RegimeResult,
    MarketRegimeDetector
)


# ========== Fixtures ==========

@pytest.fixture
def detector_default():
    """기본 설정 MarketRegimeDetector"""
    return MarketRegimeDetector(
        lookback_days=60,
        bull_threshold=0.0005,
        bear_threshold=-0.0005,
        high_vol_threshold=0.25
    )


@pytest.fixture
def mock_kospi_bull_data():
    """BULL 시장 데이터 (상승 추세)"""
    base_price = 2500
    dates = []
    data = []

    for i in range(60):
        date = datetime.now() - timedelta(days=60-i)
        # 상승 추세: 일평균 +0.1% (변동 포함)
        price = base_price * (1.001 ** i) + np.random.uniform(-10, 10)
        dates.append(date.strftime("%Y%m%d"))
        data.append({
            'date': dates[-1],
            'open': price - 5,
            'high': price + 10,
            'low': price - 10,
            'close': price,
            'volume': 1000000
        })

    return data


@pytest.fixture
def mock_kospi_bear_data():
    """BEAR 시장 데이터 (하락 추세)"""
    base_price = 2500
    dates = []
    data = []

    for i in range(60):
        date = datetime.now() - timedelta(days=60-i)
        # 하락 추세: 일평균 -0.1%
        price = base_price * (0.999 ** i) + np.random.uniform(-10, 10)
        dates.append(date.strftime("%Y%m%d"))
        data.append({
            'date': dates[-1],
            'open': price + 5,
            'high': price + 10,
            'low': price - 10,
            'close': price,
            'volume': 1000000
        })

    return data


@pytest.fixture
def mock_kospi_sideways_data():
    """SIDEWAYS 시장 데이터 (횡보)"""
    base_price = 2500
    dates = []
    data = []

    for i in range(60):
        date = datetime.now() - timedelta(days=60-i)
        # 횡보: 평균 변동 0%
        price = base_price + np.random.uniform(-20, 20)
        dates.append(date.strftime("%Y%m%d"))
        data.append({
            'date': dates[-1],
            'open': price,
            'high': price + 10,
            'low': price - 10,
            'close': price,
            'volume': 1000000
        })

    return data


@pytest.fixture
def mock_kospi_high_vol_data():
    """HIGH_VOLATILITY 시장 데이터 (고변동성)"""
    base_price = 2500
    dates = []
    data = []

    for i in range(60):
        date = datetime.now() - timedelta(days=60-i)
        # 고변동성: 일변동 ±3%
        change = np.random.uniform(-0.03, 0.03)
        price = base_price * (1 + change)
        dates.append(date.strftime("%Y%m%d"))
        data.append({
            'date': dates[-1],
            'open': price,
            'high': price * 1.03,
            'low': price * 0.97,
            'close': price,
            'volume': 1000000
        })
        base_price = price

    return data


# ========== Red: 실패하는 테스트 (기능 검증) ==========

def test_detect_regime_BULL_판단(detector_default, mock_kospi_bull_data):
    """정상 케이스: BULL 시장 감지"""
    with patch.object(
        detector_default.market_client,
        'get_kospi_history',
        return_value=mock_kospi_bull_data
    ):
        result = detector_default.detect_regime()

        # 1. 결과 타입 확인
        assert isinstance(result, RegimeResult)
        assert isinstance(result.regime, MarketRegime)

        # 2. BULL 판단
        assert result.regime == MarketRegime.BULL

        # 3. 신뢰도 확인 (0.0 ~ 1.0)
        assert 0.0 <= result.confidence <= 1.0

        # 4. 메트릭 존재
        assert 'daily_avg_return' in result.metrics
        assert 'annualized_volatility' in result.metrics
        assert 'sma_20' in result.metrics
        assert 'sma_60' in result.metrics

        # 5. 추세가 양수
        assert result.metrics['daily_avg_return'] > 0


def test_detect_regime_BEAR_판단(detector_default, mock_kospi_bear_data):
    """정상 케이스: BEAR 시장 감지"""
    with patch.object(
        detector_default.market_client,
        'get_kospi_history',
        return_value=mock_kospi_bear_data
    ):
        result = detector_default.detect_regime()

        # 1. BEAR 판단
        assert result.regime == MarketRegime.BEAR

        # 2. 추세가 음수
        assert result.metrics['daily_avg_return'] < 0


def test_detect_regime_SIDEWAYS_판단(detector_default, mock_kospi_sideways_data):
    """정상 케이스: SIDEWAYS 시장 감지"""
    with patch.object(
        detector_default.market_client,
        'get_kospi_history',
        return_value=mock_kospi_sideways_data
    ):
        result = detector_default.detect_regime()

        # 1. SIDEWAYS 판단
        assert result.regime == MarketRegime.SIDEWAYS

        # 2. 추세가 미미 (절대값 작음)
        assert abs(result.metrics['daily_avg_return']) < 0.001


def test_detect_regime_HIGH_VOL_판단(detector_default, mock_kospi_high_vol_data):
    """정상 케이스: HIGH_VOLATILITY 시장 감지"""
    with patch.object(
        detector_default.market_client,
        'get_kospi_history',
        return_value=mock_kospi_high_vol_data
    ):
        result = detector_default.detect_regime()

        # 1. HIGH_VOLATILITY 판단
        assert result.regime == MarketRegime.HIGH_VOLATILITY

        # 2. 변동성이 임계값 초과
        assert result.metrics['annualized_volatility'] > detector_default.high_vol_threshold


def test_detect_regime_기준_날짜_지정(detector_default, mock_kospi_bull_data):
    """정상 케이스: 특정 날짜 기준 감지"""
    reference_date = "2024-01-15"

    with patch.object(
        detector_default.market_client,
        'get_kospi_history',
        return_value=mock_kospi_bull_data
    ):
        result = detector_default.detect_regime(reference_date=reference_date)

        # detected_at이 기준 날짜와 일치
        assert result.detected_at == reference_date


def test_detect_regime_데이터_부족_시_기본값(detector_default):
    """경계값: KOSPI 데이터 부족 시 기본 체제 반환"""
    with patch.object(
        detector_default.market_client,
        'get_kospi_history',
        return_value=[]  # 빈 데이터
    ):
        result = detector_default.detect_regime()

        # 1. 기본 체제: SIDEWAYS
        assert result.regime == MarketRegime.SIDEWAYS

        # 2. 낮은 신뢰도
        assert result.confidence == 0.5

        # 3. 메트릭 비어있음
        assert result.metrics == {}


def test_detect_regime_데이터_20개_미만(detector_default):
    """경계값: 데이터 20개 미만 (분석 불가)"""
    short_data = [
        {'date': (datetime.now() - timedelta(days=i)).strftime("%Y%m%d"), 'close': 2500}
        for i in range(15)  # 15개만
    ]

    with patch.object(
        detector_default.market_client,
        'get_kospi_history',
        return_value=short_data
    ):
        result = detector_default.detect_regime()

        # 기본 체제 반환
        assert result.regime == MarketRegime.SIDEWAYS
        assert result.confidence == 0.5


def test_detect_regime_SMA_크로스오버_확인(detector_default, mock_kospi_bull_data):
    """SMA 크로스오버가 체제 판단에 영향을 주는지 확인"""
    with patch.object(
        detector_default.market_client,
        'get_kospi_history',
        return_value=mock_kospi_bull_data
    ):
        result = detector_default.detect_regime()

        # SMA 20 > SMA 60 (골든 크로스)
        sma_20 = result.metrics['sma_20']
        sma_60 = result.metrics['sma_60']

        if result.regime == MarketRegime.BULL:
            assert sma_20 > sma_60


# ========== 에러 케이스 ==========

def test_detect_regime_API_실패_시_기본값(detector_default):
    """에러 케이스: API 호출 실패"""
    with patch.object(
        detector_default.market_client,
        'get_kospi_history',
        side_effect=Exception("API Error")
    ):
        result = detector_default.detect_regime()

        # 기본 체제 반환 (에러 무시)
        assert result.regime == MarketRegime.SIDEWAYS
        assert result.confidence == 0.5


def test_detector_초기화_음수_lookback():
    """에러 케이스: 음수 lookback_days"""
    # 현재 구현은 음수 검증 없음 (개선 필요)
    detector = MarketRegimeDetector(lookback_days=-10)
    # 에러는 발생하지 않지만, 로직 오류 가능성
    assert detector.lookback_days == -10


def test_detector_초기화_잘못된_threshold():
    """에러 케이스: bull < bear (논리 오류)"""
    # bull_threshold < bear_threshold는 논리적으로 이상함
    detector = MarketRegimeDetector(
        bull_threshold=-0.001,
        bear_threshold=0.001
    )
    # 초기화는 성공하지만 판단 로직 오류 가능
    assert detector.bull_threshold < detector.bear_threshold


# ========== Refactor: 테스트 유틸리티 ==========

def create_mock_kospi_data(
    days: int,
    start_price: float,
    daily_return: float,
    volatility: float = 0.01
):
    """KOSPI 데이터 생성 헬퍼

    Args:
        days: 생성할 일수
        start_price: 시작 가격
        daily_return: 일평균 수익률
        volatility: 일변동성 (표준편차)
    """
    data = []
    price = start_price

    for i in range(days):
        date = datetime.now() - timedelta(days=days-i)
        # 평균 수익률 + 변동성
        ret = daily_return + np.random.normal(0, volatility)
        price = price * (1 + ret)

        data.append({
            'date': date.strftime("%Y%m%d"),
            'open': price * 0.99,
            'high': price * 1.01,
            'low': price * 0.98,
            'close': price,
            'volume': 1000000
        })

    return data


def test_classify_regime_경계값_테스트():
    """_classify_regime 메서드 단독 테스트"""
    detector = MarketRegimeDetector()

    # 1. BULL 경계값 (threshold 직전)
    regime, conf = detector._classify_regime(
        trend=0.00049,  # < 0.0005
        volatility=0.1,
        sma_cross=0.011
    )
    assert regime == MarketRegime.SIDEWAYS  # threshold 미만

    # 2. BULL 경계값 (threshold 직후)
    regime, conf = detector._classify_regime(
        trend=0.00051,  # > 0.0005
        volatility=0.1,
        sma_cross=0.011
    )
    assert regime == MarketRegime.BULL  # threshold 초과

    # 3. HIGH_VOL 우선순위 (추세 무시)
    regime, conf = detector._classify_regime(
        trend=0.01,  # 강한 상승
        volatility=0.26,  # > 0.25
        sma_cross=0.05
    )
    assert regime == MarketRegime.HIGH_VOLATILITY  # 변동성 우선
