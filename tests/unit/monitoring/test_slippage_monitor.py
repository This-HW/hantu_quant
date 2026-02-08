#!/usr/bin/env python3
"""
SlippageMonitor 단위 테스트
TDD Red-Green-Refactor 사이클
"""

import pytest
import json
import tempfile
from pathlib import Path
from datetime import datetime

from core.monitoring.slippage_monitor import (
    SlippageMonitor,
    SlippageRecord
)


# ========== Fixtures ==========

@pytest.fixture
def temp_save_path():
    """임시 저장 경로"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        yield f.name
    # 테스트 후 삭제
    Path(f.name).unlink(missing_ok=True)


@pytest.fixture
def monitor_temp(temp_save_path):
    """임시 경로를 사용하는 SlippageMonitor"""
    return SlippageMonitor(save_path=temp_save_path)


@pytest.fixture
def monitor_with_data(temp_save_path):
    """사전 데이터가 있는 SlippageMonitor"""
    # 기존 데이터 생성
    existing_data = [
        {
            'stock_code': '005930',
            'stock_name': '삼성전자',
            'order_type': 'buy',
            'expected_price': 70000,
            'executed_price': 70100,
            'quantity': 10,
            'timestamp': '2024-01-01T09:00:00',
            'order_id': 'ORDER001',
            'slippage_rate': -0.001428,
            'slippage_amount': 1000
        },
        {
            'stock_code': '000660',
            'stock_name': 'SK하이닉스',
            'order_type': 'sell',
            'expected_price': 150000,
            'executed_price': 149800,
            'quantity': 5,
            'timestamp': '2024-01-02T14:00:00',
            'order_id': 'ORDER002',
            'slippage_rate': -0.001333,
            'slippage_amount': 1000
        }
    ]

    with open(temp_save_path, 'w', encoding='utf-8') as f:
        json.dump(existing_data, f)

    return SlippageMonitor(save_path=temp_save_path)


# ========== Red: 실패하는 테스트 (기능 검증) ==========

def test_record_slippage_매수_불리한_경우(monitor_temp):
    """정상 케이스: 매수 슬리페이지 (불리)"""
    record = monitor_temp.record_slippage(
        stock_code='005930',
        stock_name='삼성전자',
        order_type='buy',
        expected_price=70000,
        executed_price=70500,  # 예상보다 비싸게 체결
        quantity=10,
        order_id='TEST001'
    )

    # 1. 결과 타입 확인
    assert isinstance(record, SlippageRecord)

    # 2. 슬리페이지 비율 (음수 = 불리)
    assert record.slippage_rate < 0

    # 3. 슬리페이지 금액
    assert record.slippage_amount == 5000  # (70500 - 70000) * 10

    # 4. 기록 추가 확인
    assert len(monitor_temp.records) == 1


def test_record_slippage_매수_유리한_경우(monitor_temp):
    """정상 케이스: 매수 슬리페이지 (유리)"""
    record = monitor_temp.record_slippage(
        stock_code='005930',
        stock_name='삼성전자',
        order_type='buy',
        expected_price=70000,
        executed_price=69500,  # 예상보다 싸게 체결
        quantity=10
    )

    # 1. 슬리페이지 비율 (양수 = 유리)
    assert record.slippage_rate > 0

    # 2. 슬리페이지 금액
    assert record.slippage_amount == 5000


def test_record_slippage_매도_불리한_경우(monitor_temp):
    """정상 케이스: 매도 슬리페이지 (불리)"""
    record = monitor_temp.record_slippage(
        stock_code='000660',
        stock_name='SK하이닉스',
        order_type='sell',
        expected_price=150000,
        executed_price=149000,  # 예상보다 낮게 체결
        quantity=5
    )

    # 1. 슬리페이지 비율 (음수 = 불리)
    assert record.slippage_rate < 0

    # 2. 슬리페이지 금액
    assert record.slippage_amount == 5000  # (150000 - 149000) * 5


def test_record_slippage_매도_유리한_경우(monitor_temp):
    """정상 케이스: 매도 슬리페이지 (유리)"""
    record = monitor_temp.record_slippage(
        stock_code='000660',
        stock_name='SK하이닉스',
        order_type='sell',
        expected_price=150000,
        executed_price=151000,  # 예상보다 높게 체결
        quantity=5
    )

    # 1. 슬리페이지 비율 (양수 = 유리)
    assert record.slippage_rate > 0

    # 2. 슬리페이지 금액
    assert record.slippage_amount == 5000


def test_record_slippage_파일_저장(monitor_temp, temp_save_path):
    """정상 케이스: 슬리페이지 기록 파일 저장"""
    monitor_temp.record_slippage(
        stock_code='005930',
        stock_name='삼성전자',
        order_type='buy',
        expected_price=70000,
        executed_price=70100,
        quantity=10
    )

    # 파일 생성 확인
    assert Path(temp_save_path).exists()

    # 파일 내용 확인
    with open(temp_save_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    assert len(data) == 1
    assert data[0]['stock_code'] == '005930'
    assert data[0]['slippage_rate'] < 0


def test_load_records_기존_데이터_로드(monitor_with_data):
    """정상 케이스: 기존 기록 로드"""
    # 초기화 시 자동 로드됨
    assert len(monitor_with_data.records) == 2

    # 첫 번째 기록 확인
    first_record = monitor_with_data.records[0]
    assert first_record.stock_code == '005930'
    assert first_record.order_type == 'buy'


def test_get_statistics_전체_통계(monitor_with_data):
    """정상 케이스: 전체 슬리페이지 통계"""
    stats = monitor_with_data.get_statistics()

    # 1. 전체 개수
    assert stats['total_count'] == 2

    # 2. 평균 슬리페이지 비율
    assert 'avg_slippage_rate' in stats
    assert isinstance(stats['avg_slippage_rate'], float)

    # 3. 평균 슬리페이지 금액
    assert stats['avg_slippage_amount'] == 1000

    # 4. 유리/불리 개수
    assert stats['favorable_count'] + stats['unfavorable_count'] == 2

    # 5. 유리 비율
    assert 0.0 <= stats['favorable_rate'] <= 1.0


def test_get_statistics_필터_매수만(monitor_with_data):
    """정상 케이스: 매수 주문만 통계"""
    stats = monitor_with_data.get_statistics(order_type='buy')

    # 매수만 1개
    assert stats['total_count'] == 1


def test_get_statistics_필터_매도만(monitor_with_data):
    """정상 케이스: 매도 주문만 통계"""
    stats = monitor_with_data.get_statistics(order_type='sell')

    # 매도만 1개
    assert stats['total_count'] == 1


def test_get_statistics_최근_N개(monitor_with_data):
    """정상 케이스: 최근 N개만 통계"""
    # 추가 기록
    monitor_with_data.record_slippage(
        stock_code='051910',
        stock_name='LG화학',
        order_type='buy',
        expected_price=500000,
        executed_price=500500,
        quantity=2
    )

    # 최근 2개만
    stats = monitor_with_data.get_statistics(last_n=2)
    assert stats['total_count'] == 2


def test_get_statistics_빈_기록(monitor_temp):
    """경계값: 기록이 없을 때 통계"""
    stats = monitor_temp.get_statistics()

    # 모든 값 0
    assert stats['total_count'] == 0
    assert stats['avg_slippage_rate'] == 0.0
    assert stats['avg_slippage_amount'] == 0.0
    assert stats['favorable_count'] == 0
    assert stats['unfavorable_count'] == 0
    assert stats['favorable_rate'] == 0.0


def test_slippage_rate_계산_정확성():
    """슬리페이지 비율 계산 정확성 검증"""
    # 매수: 실제 < 예상 = 유리(양수)
    buy_record = SlippageRecord(
        stock_code='005930',
        stock_name='삼성전자',
        order_type='buy',
        expected_price=100000,
        executed_price=99000,  # 1% 싸게
        quantity=10,
        timestamp=datetime.now().isoformat()
    )
    assert buy_record.slippage_rate == pytest.approx(0.01, rel=1e-3)

    # 매도: 실제 > 예상 = 유리(양수)
    sell_record = SlippageRecord(
        stock_code='000660',
        stock_name='SK하이닉스',
        order_type='sell',
        expected_price=100000,
        executed_price=101000,  # 1% 비싸게
        quantity=5,
        timestamp=datetime.now().isoformat()
    )
    assert sell_record.slippage_rate == pytest.approx(0.01, rel=1e-3)


def test_slippage_amount_계산_정확성():
    """슬리페이지 금액 계산 정확성 검증"""
    record = SlippageRecord(
        stock_code='005930',
        stock_name='삼성전자',
        order_type='buy',
        expected_price=70000,
        executed_price=71000,
        quantity=10,
        timestamp=datetime.now().isoformat()
    )

    # |71000 - 70000| * 10 = 10000
    assert record.slippage_amount == 10000


# ========== 에러 케이스 ==========

def test_record_slippage_expected_price_0(monitor_temp):
    """에러 케이스: 예상 가격 0 (ZeroDivisionError 방지)"""
    record = monitor_temp.record_slippage(
        stock_code='005930',
        stock_name='삼성전자',
        order_type='buy',
        expected_price=0,  # 0으로 나누기
        executed_price=70000,
        quantity=10
    )

    # 슬리페이지 비율 0 반환
    assert record.slippage_rate == 0.0


def test_load_records_파일_없음(temp_save_path):
    """에러 케이스: 저장 파일 없음 (초기화)"""
    # 파일 삭제
    Path(temp_save_path).unlink(missing_ok=True)

    monitor = SlippageMonitor(save_path=temp_save_path)

    # 빈 기록으로 시작
    assert len(monitor.records) == 0


def test_load_records_손상된_파일(temp_save_path):
    """에러 케이스: 손상된 JSON 파일"""
    # 잘못된 JSON 작성
    with open(temp_save_path, 'w') as f:
        f.write("invalid json {{{")

    monitor = SlippageMonitor(save_path=temp_save_path)

    # 빈 기록으로 시작 (에러 무시)
    assert len(monitor.records) == 0


def test_save_records_권한_없음(monitor_temp):
    """에러 케이스: 파일 쓰기 권한 없음"""
    # 읽기 전용 경로 (실제 테스트는 환경에 따라 스킵 가능)
    monitor_temp.save_path = Path('/invalid/path/records.json')

    # 기록 추가 시도 (에러 발생해도 프로그램 중단 안됨)
    try:
        monitor_temp.record_slippage(
            stock_code='005930',
            stock_name='삼성전자',
            order_type='buy',
            expected_price=70000,
            executed_price=70100,
            quantity=10
        )
    except Exception:
        pass  # 에러 발생해도 OK


# ========== Refactor: 테스트 유틸리티 ==========

def create_sample_records(count: int, order_type: str = 'buy'):
    """샘플 SlippageRecord 생성 헬퍼"""
    records = []
    for i in range(count):
        record = SlippageRecord(
            stock_code=f'{i:06d}',
            stock_name=f'종목{i}',
            order_type=order_type,
            expected_price=70000 + i * 1000,
            executed_price=70100 + i * 1000,
            quantity=10,
            timestamp=datetime.now().isoformat(),
            order_id=f'ORDER{i:03d}'
        )
        records.append(record)
    return records


def test_sample_records_헬퍼():
    """create_sample_records 헬퍼 함수 테스트"""
    records = create_sample_records(count=5, order_type='sell')

    assert len(records) == 5
    assert all(r.order_type == 'sell' for r in records)
    assert records[0].stock_code == '000000'
    assert records[4].stock_code == '000004'


def test_get_statistics_최대최소_슬리페이지(monitor_with_data):
    """통계에서 최대/최소 슬리페이지 확인"""
    # 추가 기록 (큰 슬리페이지)
    monitor_with_data.record_slippage(
        stock_code='051910',
        stock_name='LG화학',
        order_type='buy',
        expected_price=500000,
        executed_price=510000,  # 2% 불리
        quantity=1
    )

    stats = monitor_with_data.get_statistics()

    # 최대/최소 존재
    assert 'max_slippage_rate' in stats
    assert 'min_slippage_rate' in stats

    # 최대 슬리페이지 (절대값)
    assert abs(stats['max_slippage_rate']) >= abs(stats['min_slippage_rate'])
