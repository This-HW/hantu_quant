#!/usr/bin/env python3
"""
CorrelationMonitor 단위 테스트
TDD Red-Green-Refactor 사이클
"""

import pytest
from unittest.mock import Mock, patch
import pandas as pd
import numpy as np

from core.risk.correlation.correlation_monitor import (
    CorrelationMonitor,
    CorrelationCheckResult
)


# ========== Fixtures ==========

@pytest.fixture
def monitor_default():
    """기본 설정 CorrelationMonitor (threshold=0.7, max_pairs=2)"""
    return CorrelationMonitor(
        correlation_threshold=0.7,
        max_high_corr_pairs=2
    )


@pytest.fixture
def sample_price_data():
    """샘플 가격 데이터 (3개 종목, 60일)"""
    dates = pd.date_range(start='2024-01-01', periods=60)

    # 종목 A: 기준
    price_a = 10000 + np.cumsum(np.random.normal(0, 100, 60))

    # 종목 B: A와 높은 상관관계 (0.85)
    price_b = price_a * 0.9 + np.random.normal(0, 50, 60)

    # 종목 C: A와 낮은 상관관계 (0.2)
    price_c = 15000 + np.cumsum(np.random.normal(0, 150, 60))

    return {
        '005930': pd.DataFrame({
            'date': dates,
            'close': price_a
        }),
        '000660': pd.DataFrame({
            'date': dates,
            'close': price_b
        }),
        '051910': pd.DataFrame({
            'date': dates,
            'close': price_c
        })
    }


@pytest.fixture
def existing_positions():
    """기존 포지션 (2개)"""
    return {
        '005930': {'quantity': 10, 'avg_price': 70000},
        '000660': {'quantity': 5, 'avg_price': 150000}
    }


# ========== Red: 실패하는 테스트 (기능 검증) ==========

def test_check_new_position_기존_포지션_없음(monitor_default, sample_price_data):
    """정상 케이스: 첫 포지션 추가 (무조건 허용)"""
    result = monitor_default.check_new_position(
        new_stock_code='005930',
        existing_positions={},
        price_data=sample_price_data
    )

    # 1. 결과 타입 확인
    assert isinstance(result, CorrelationCheckResult)

    # 2. 허용됨
    assert result.allowed is True

    # 3. 상관관계 0
    assert result.max_correlation == 0.0

    # 4. 고상관 종목 없음
    assert len(result.high_corr_stocks) == 0

    # 5. 이유 명시
    assert "기존 포지션 없음" in result.reason


def test_check_new_position_낮은_상관관계_허용(monitor_default, sample_price_data, existing_positions):
    """정상 케이스: 낮은 상관관계 종목 추가 허용"""
    # 051910은 기존 종목들과 낮은 상관관계
    result = monitor_default.check_new_position(
        new_stock_code='051910',
        existing_positions=existing_positions,
        price_data=sample_price_data
    )

    # 1. 허용됨
    assert result.allowed is True

    # 2. 최대 상관관계 < threshold
    assert result.max_correlation < monitor_default.correlation_threshold

    # 3. 고상관 종목 없음
    assert len(result.high_corr_stocks) == 0


def test_check_new_position_높은_상관관계_감지(monitor_default, sample_price_data):
    """정상 케이스: 높은 상관관계 감지"""
    # 005930만 보유 중
    existing = {'005930': {'quantity': 10, 'avg_price': 70000}}

    # 000660 추가 시도 (005930과 높은 상관관계)
    result = monitor_default.check_new_position(
        new_stock_code='000660',
        existing_positions=existing,
        price_data=sample_price_data
    )

    # 1. 고상관 종목 감지
    assert len(result.high_corr_stocks) > 0

    # 2. 최대 상관관계 >= threshold
    assert result.max_correlation >= monitor_default.correlation_threshold


def test_check_new_position_고상관_쌍_한도_초과_거부(monitor_default, sample_price_data):
    """정상 케이스: 고상관 쌍 한도 초과로 거부"""
    # 이미 고상관 쌍 2개 보유 (005930-000660, 005930-XXX)
    # Mock을 사용하여 기존 쌍이 2개임을 시뮬레이션
    with patch.object(
        monitor_default,
        '_count_high_corr_pairs',
        return_value=2  # 이미 한도 도달
    ):
        result = monitor_default.check_new_position(
            new_stock_code='051910',
            existing_positions=sample_price_data,
            price_data=sample_price_data
        )

        # 거부됨
        assert result.allowed is False
        assert "한도 초과" in result.reason


def test_check_new_position_신규_종목_데이터_없음(monitor_default, existing_positions, sample_price_data):
    """경계값: 신규 종목 가격 데이터 부재"""
    result = monitor_default.check_new_position(
        new_stock_code='999999',  # 데이터 없음
        existing_positions=existing_positions,
        price_data=sample_price_data
    )

    # 1. 허용됨 (데이터 부족 시 보수적 허용)
    assert result.allowed is True

    # 2. 이유 명시
    assert "데이터 부족" in result.reason


def test_check_new_position_기존_종목_데이터_부분_누락(monitor_default, sample_price_data):
    """경계값: 기존 종목 일부 데이터 부재"""
    existing = {
        '005930': {'quantity': 10},
        '999999': {'quantity': 5}  # 가격 데이터 없음
    }

    result = monitor_default.check_new_position(
        new_stock_code='051910',
        existing_positions=existing,
        price_data=sample_price_data
    )

    # 데이터 있는 종목만 체크 (에러 발생 안함)
    assert isinstance(result, CorrelationCheckResult)


def test_count_high_corr_pairs_계산_정확성(monitor_default, sample_price_data):
    """_count_high_corr_pairs 메서드 정확성 검증"""
    # 005930과 000660은 높은 상관관계
    stock_codes = ['005930', '000660', '051910']

    count = monitor_default._count_high_corr_pairs(
        stock_codes,
        sample_price_data
    )

    # 최소 1쌍 (005930-000660)
    assert count >= 1


def test_check_new_position_고상관_종목_리스트_형식(monitor_default, sample_price_data):
    """고상관 종목 리스트 형식 확인"""
    existing = {'005930': {'quantity': 10}}

    result = monitor_default.check_new_position(
        new_stock_code='000660',
        existing_positions=existing,
        price_data=sample_price_data
    )

    if result.high_corr_stocks:
        # 형식: "종목코드(상관계수)"
        for stock_info in result.high_corr_stocks:
            assert '(' in stock_info
            assert ')' in stock_info
            # 상관계수 추출
            corr_str = stock_info.split('(')[1].split(')')[0]
            corr_value = float(corr_str)
            assert -1.0 <= corr_value <= 1.0


# ========== 에러 케이스 ==========

def test_check_new_position_상관관계_계산_오류_시_허용(monitor_default, existing_positions):
    """에러 케이스: 상관관계 계산 실패 시 보수적 허용"""
    # 잘못된 price_data (DataFrame 아님)
    bad_price_data = {
        '005930': "invalid",
        '000660': "invalid"
    }

    result = monitor_default.check_new_position(
        new_stock_code='051910',
        existing_positions=existing_positions,
        price_data=bad_price_data
    )

    # 1. 에러 발생해도 허용 (보수적)
    assert result.allowed is True

    # 2. 이유에 데이터 부족 또는 오류 명시
    assert ("데이터 부족" in result.reason or
            "오류" in result.reason or
            "에러" in result.reason)


def test_monitor_초기화_음수_threshold():
    """에러 케이스: 음수 threshold → ValueError 발생"""
    # 검증 로직이 구현됨
    with pytest.raises(ValueError, match="correlation_threshold must be in \\[0, 1\\]"):
        CorrelationMonitor(correlation_threshold=-0.5)


def test_monitor_초기화_threshold_범위_초과():
    """에러 케이스: threshold > 1.0 → ValueError 발생"""
    # 검증 로직이 구현됨
    with pytest.raises(ValueError, match="correlation_threshold must be in \\[0, 1\\]"):
        CorrelationMonitor(correlation_threshold=1.5)


def test_monitor_초기화_max_pairs_음수():
    """에러 케이스: 음수 max_pairs → ValueError 발생"""
    # 검증 로직이 구현됨
    with pytest.raises(ValueError, match="max_high_corr_pairs must be >= 0"):
        CorrelationMonitor(max_high_corr_pairs=-1)


# ========== Refactor: 테스트 유틸리티 ==========

def create_correlated_price_data(
    stock_codes: list,
    days: int,
    correlation: float
):
    """상관관계가 조절된 가격 데이터 생성

    Args:
        stock_codes: 종목 코드 리스트
        days: 생성할 일수
        correlation: 목표 상관계수 (0.0 ~ 1.0)
    """
    dates = pd.date_range(start='2024-01-01', periods=days)
    base_returns = np.random.normal(0, 0.02, days)

    price_data = {}

    for code in stock_codes:
        # 기본 수익률 + 독립 수익률
        independent_returns = np.random.normal(0, 0.02, days)
        combined_returns = (
            correlation * base_returns +
            (1 - correlation) * independent_returns
        )

        # 가격 계산
        prices = 10000 * np.exp(np.cumsum(combined_returns))

        price_data[code] = pd.DataFrame({
            'date': dates,
            'close': prices
        })

    return price_data


def test_상관관계_헬퍼_함수():
    """create_correlated_price_data 헬퍼 함수 테스트"""
    # 높은 상관관계 (0.9)
    high_corr_data = create_correlated_price_data(
        stock_codes=['A', 'B'],
        days=60,
        correlation=0.9
    )

    # 낮은 상관관계 (0.1)
    low_corr_data = create_correlated_price_data(
        stock_codes=['C', 'D'],
        days=60,
        correlation=0.1
    )

    # 데이터 생성 확인
    assert 'A' in high_corr_data
    assert 'B' in high_corr_data
    assert len(high_corr_data['A']) == 60
