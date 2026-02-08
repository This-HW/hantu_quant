#!/usr/bin/env python3
"""
DataSplitter 단위 테스트
TDD Red-Green-Refactor 사이클
"""

import pytest
from datetime import datetime, timedelta
from core.backtesting.data_splitter import DataSplitter, DataSplit


# ========== Fixtures ==========

@pytest.fixture
def sample_data():
    """테스트용 샘플 데이터 (30일치)"""
    base_date = datetime(2024, 1, 1)
    data = []
    for i in range(30):
        date_str = (base_date + timedelta(days=i)).strftime("%Y-%m-%d")
        data.append({
            'selection_date': date_str,
            'stock_code': f'00{i:04d}',
            'stock_name': f'종목{i}',
            'score': 80.0 + i
        })
    return data


@pytest.fixture
def splitter_default():
    """기본 설정 DataSplitter (70/0/30, purge=5일)"""
    return DataSplitter(train_ratio=0.7, val_ratio=0.0, purge_days=5)


@pytest.fixture
def splitter_with_val():
    """검증 데이터 포함 DataSplitter (60/20/20, purge=3일)"""
    return DataSplitter(train_ratio=0.6, val_ratio=0.2, purge_days=3)


# ========== Red: 실패하는 테스트 (기능 검증) ==========

def test_split_walk_forward_정상_케이스(splitter_default, sample_data):
    """정상 케이스: 30개 데이터를 70/30 분할 + purge 5일"""
    result = splitter_default.split_walk_forward(sample_data)

    # 1. 분할 결과 타입 확인
    assert isinstance(result, DataSplit)
    assert isinstance(result.train_data, list)
    assert isinstance(result.test_data, list)
    assert isinstance(result.split_info, dict)

    # 2. Train 데이터 (70% = 21개)
    assert len(result.train_data) == 21
    assert result.train_data[0]['selection_date'] == "2024-01-01"
    assert result.train_data[-1]['selection_date'] == "2024-01-21"

    # 3. Test 데이터 (purge 5일 후)
    # 2024-01-21 + 5일 = 2024-01-26 이후 데이터
    assert result.test_data[0]['selection_date'] > "2024-01-26"

    # 4. Purged 데이터 확인
    assert result.split_info['purged_samples'] > 0
    assert result.split_info['purged_samples'] <= 5


def test_split_walk_forward_빈_데이터(splitter_default):
    """경계값: 빈 데이터셋"""
    result = splitter_default.split_walk_forward([])

    assert len(result.train_data) == 0
    assert len(result.test_data) == 0
    assert result.split_info['total_samples'] == 0
    assert result.split_info['purged_samples'] == 0


def test_split_walk_forward_데이터_1개(splitter_default):
    """경계값: 데이터 1개 (분할 불가)"""
    data = [{'selection_date': '2024-01-01', 'stock_code': '005930'}]
    result = splitter_default.split_walk_forward(data)

    # Train에 0개 (70% of 1 = 0)
    assert len(result.train_data) == 0
    # Test에 1개 (train이 비어있어서 purge 미적용)
    assert len(result.test_data) == 1


def test_split_walk_forward_purge_적용_확인(splitter_default, sample_data):
    """Purge gap이 올바르게 적용되는지 확인"""
    result = splitter_default.split_walk_forward(sample_data)

    # Train 마지막 날짜
    train_end = datetime.strptime(result.train_data[-1]['selection_date'], "%Y-%m-%d")

    # Test 첫 날짜
    test_start = datetime.strptime(result.test_data[0]['selection_date'], "%Y-%m-%d")

    # 차이가 purge_days보다 커야 함
    gap_days = (test_start - train_end).days
    assert gap_days > splitter_default.purge_days


def test_split_walk_forward_날짜_정렬_확인(sample_data):
    """날짜 순서가 뒤죽박죽인 데이터도 정렬 후 분할"""
    # 데이터 순서 섞기
    import random
    shuffled = sample_data.copy()
    random.shuffle(shuffled)

    splitter = DataSplitter(train_ratio=0.7, val_ratio=0.0, purge_days=3)
    result = splitter.split_walk_forward(shuffled)

    # Train 데이터가 날짜순으로 정렬되어 있는지 확인
    train_dates = [d['selection_date'] for d in result.train_data]
    assert train_dates == sorted(train_dates)

    # Test 데이터도 날짜순
    test_dates = [d['selection_date'] for d in result.test_data]
    assert test_dates == sorted(test_dates)


def test_split_walk_forward_검증_데이터_포함(splitter_with_val, sample_data):
    """검증 데이터 포함 분할 (60/20/20)"""
    result = splitter_with_val.split_walk_forward(sample_data)

    # 60% = 18개
    assert len(result.train_data) == 18

    # 20% = 6개 (purge 없음)
    assert len(result.val_data) == 6

    # Test는 purge 3일 후
    assert len(result.test_data) > 0


def test_split_walk_forward_split_info_정확성(splitter_default, sample_data):
    """split_info의 통계 정보가 정확한지 확인"""
    result = splitter_default.split_walk_forward(sample_data)

    info = result.split_info

    # 1. 전체 개수
    assert info['total_samples'] == len(sample_data)

    # 2. 각 분할 개수
    assert info['train_samples'] == len(result.train_data)
    assert info['val_samples'] == len(result.val_data)
    assert info['test_samples'] == len(result.test_data)

    # 3. Purged 계산 정확성
    assert (
        info['train_samples'] +
        info['val_samples'] +
        info['test_samples'] +
        info['purged_samples']
    ) == info['total_samples']

    # 4. 날짜 정보 존재
    assert info['train_start'] is not None
    assert info['train_end'] is not None
    assert info['test_start'] is not None
    assert info['test_end'] is not None
    assert info['purge_days'] == splitter_default.purge_days


# ========== 에러 케이스 ==========

def test_splitter_초기화_잘못된_ratio():
    """에러 케이스: train_ratio + val_ratio >= 1.0"""
    with pytest.raises(ValueError, match="test_ratio must be > 0"):
        DataSplitter(train_ratio=0.8, val_ratio=0.3)  # 합 1.1


def test_splitter_초기화_음수_ratio():
    """에러 케이스: 음수 비율 → ValueError 발생"""
    # 음수 검증이 구현되어 있음
    with pytest.raises(ValueError, match="train_ratio must be in \\(0, 1\\]"):
        DataSplitter(train_ratio=-0.1, val_ratio=0.0)


def test_split_walk_forward_잘못된_date_key(splitter_default, sample_data):
    """에러 케이스: 존재하지 않는 날짜 키"""
    with pytest.raises(KeyError):
        splitter_default.split_walk_forward(sample_data, date_key='wrong_date')


def test_split_walk_forward_날짜_형식_오류(splitter_default):
    """에러 케이스: 잘못된 날짜 형식 (purge 계산 시 발생)"""
    data = [
        {'selection_date': '2024/01/01', 'stock_code': '005930'},  # 슬래시 형식
        {'selection_date': '2024/01/02', 'stock_code': '000660'}
    ] * 10  # 충분한 데이터로 train이 생기도록

    # 날짜 형식 오류는 purge 적용 시 datetime.strptime에서 발생
    with pytest.raises(ValueError):
        splitter_default.split_walk_forward(data)


# ========== Refactor: 테스트 유틸리티 ==========

def create_date_range(start: str, days: int):
    """날짜 범위 생성 헬퍼"""
    base = datetime.strptime(start, "%Y-%m-%d")
    return [
        (base + timedelta(days=i)).strftime("%Y-%m-%d")
        for i in range(days)
    ]


def test_purge_gap_계산_정확성():
    """Purge gap이 정확히 계산되는지 검증"""
    dates = create_date_range("2024-01-01", 20)
    data = [{'selection_date': d, 'stock_code': f'{i:06d}'} for i, d in enumerate(dates)]

    splitter = DataSplitter(train_ratio=0.5, val_ratio=0.0, purge_days=3)
    result = splitter.split_walk_forward(data)

    # Train: 10개 (2024-01-01 ~ 2024-01-10)
    # Purge: 3일 (2024-01-11, 2024-01-12, 2024-01-13)
    # Test: 2024-01-14부터

    assert result.train_data[-1]['selection_date'] == "2024-01-10"
    assert result.test_data[0]['selection_date'] > "2024-01-13"
