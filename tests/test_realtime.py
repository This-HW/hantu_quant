"""
Real-time data processing system test.
"""

import pytest
from datetime import datetime
from decimal import Decimal

from core.realtime import DataProcessor, EventHandler
from core.database.session import DatabaseSession
from core.database.repository import StockRepository
from core.utils import get_logger

logger = get_logger(__name__)

@pytest.fixture
def db_session():
    """데이터베이스 세션 픽스처"""
    session = DatabaseSession()
    yield session.session
    session.close()

@pytest.fixture
def repository(db_session):
    """StockRepository 픽스처"""
    return StockRepository(db_session)

@pytest.fixture
def processor(repository):
    """DataProcessor 픽스처"""
    processor = DataProcessor()
    processor.repository = repository
    return processor

@pytest.fixture
def handler(repository):
    """EventHandler 픽스처"""
    handler = EventHandler()
    handler.repository = repository
    return handler

def test_data_normalization(processor):
    """데이터 정규화 테스트"""
    # 테스트 데이터
    data = {
        'code': '005930',
        'timestamp': int(datetime.now().timestamp()),
        'price': 70000,
        'volume': 1000,
        'type': 'trade'
    }
    
    # 데이터 정규화
    normalized = processor._normalize_data(data)
    
    assert normalized is not None
    assert normalized['code'] == '005930'
    assert isinstance(normalized['timestamp'], datetime)
    assert isinstance(normalized['price'], Decimal)
    assert isinstance(normalized['volume'], int)
    assert normalized['type'] == 'TRADE'

def test_data_validation(processor):
    """데이터 검증 테스트"""
    # 유효한 데이터
    valid_data = {
        'code': '005930',
        'timestamp': datetime.now(),
        'price': Decimal('70000'),
        'volume': 1000,
        'type': 'TRADE'
    }
    assert processor._validate_data(valid_data) is True
    
    # 유효하지 않은 데이터
    invalid_data = {
        'code': '',
        'timestamp': 'invalid',
        'price': -1,
        'volume': -100,
        'type': 'INVALID'
    }
    assert processor._validate_data(invalid_data) is False

@pytest.mark.asyncio
async def test_event_handling(handler):
    """이벤트 처리 테스트"""
    # 테스트 데이터
    data = {
        'code': '005930',
        'timestamp': datetime.now(),
        'price': Decimal('70000'),
        'volume': 1000,
        'type': 'TRADE'
    }
    
    # 이벤트 처리
    await handler.handle_event(data)

@pytest.mark.asyncio
async def test_data_processing_pipeline(processor):
    """데이터 처리 파이프라인 테스트"""
    # 프로세서 시작
    await processor.start()
    
    # 테스트 데이터
    data = {
        'code': '005930',
        'timestamp': int(datetime.now().timestamp()),
        'price': 70000,
        'volume': 1000,
        'type': 'trade'
    }
    
    # 데이터 처리
    await processor.process_data(data)
    
    # 버퍼 데이터 확인
    buffer_data = processor.get_buffer_data()
    assert len(buffer_data) > 0
    
    # 프로세서 중지
    await processor.stop()

def test_database_operations(repository, db_session):
    """데이터베이스 작업 테스트"""
    # 종목 정보 저장 테스트
    stock = repository.save_stock(
        code='005930',
        name='삼성전자',
        market='KOSPI'
    )
    db_session.commit()
    
    assert stock is not None
    assert stock.code == '005930'
    assert stock.name == '삼성전자'
    
    # 가격 정보 저장 테스트
    price = repository.save_price(
        stock_id=stock.id,
        date=datetime.now().date(),
        open_price=Decimal('70000'),
        high_price=Decimal('71000'),
        low_price=Decimal('69000'),
        close_price=Decimal('70500'),
        volume=1000000
    )
    db_session.commit()
    
    assert price is not None
    assert price.stock_id == stock.id
    assert price.close_price == Decimal('70500')

if __name__ == '__main__':
    pytest.main(['-v', __file__]) 