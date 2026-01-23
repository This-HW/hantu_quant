"""
Tests for TradeHistory schema migration validation.
Validates that Phase 2 prediction columns are properly added to the database.
"""
import pytest
from datetime import datetime
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from core.database.models import Base, TradeHistory, Stock


@pytest.fixture
def engine():
    """In-memory SQLite engine for testing."""
    engine = create_engine('sqlite:///:memory:', echo=False)
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def session(engine):
    """Database session for testing."""
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestTradeHistorySchema:
    """TradeHistory 스키마 검증 테스트"""

    def test_phase2_columns_exist(self, engine):
        """Phase 2 예측 정보 컬럼 존재 확인"""
        inspector = inspect(engine)
        columns = {col['name'] for col in inspector.get_columns('trade_history')}

        expected_columns = {
            'entry_price',
            'target_price',
            'stop_loss_price',
            'expected_return',
            'predicted_probability',
            'predicted_class',
            'model_name',
        }

        missing = expected_columns - columns
        assert not missing, f"Missing columns: {missing}"

    def test_phase2_column_types(self, engine):
        """Phase 2 컬럼 타입 검증"""
        inspector = inspect(engine)
        columns = {col['name']: str(col['type']) for col in inspector.get_columns('trade_history')}

        # Float 타입 컬럼 (SQLite에서는 FLOAT)
        float_cols = [
            'entry_price',
            'target_price',
            'stop_loss_price',
            'expected_return',
            'predicted_probability',
        ]
        for col in float_cols:
            assert col in columns, f"{col} not found"
            assert 'FLOAT' in columns[col].upper() or 'REAL' in columns[col].upper(), \
                f"{col} should be float type, got {columns[col]}"

        # Integer 타입 컬럼
        assert 'predicted_class' in columns
        assert 'INTEGER' in columns['predicted_class'].upper(), \
            f"predicted_class should be integer type, got {columns['predicted_class']}"

        # String 타입 컬럼
        assert 'model_name' in columns
        assert 'VARCHAR' in columns['model_name'].upper() or 'TEXT' in columns['model_name'].upper(), \
            f"model_name should be string type, got {columns['model_name']}"

    def test_phase2_columns_nullable(self, engine):
        """Phase 2 컬럼 NULL 허용 검증"""
        inspector = inspect(engine)
        columns = {col['name']: col['nullable'] for col in inspector.get_columns('trade_history')}

        nullable_cols = [
            'entry_price',
            'target_price',
            'stop_loss_price',
            'expected_return',
            'predicted_probability',
            'predicted_class',
            'model_name',
        ]

        for col in nullable_cols:
            assert columns.get(col, True), f"{col} should be nullable"


class TestTradeHistoryORM:
    """TradeHistory ORM 동작 테스트"""

    def test_create_with_phase2_fields(self, session):
        """Phase 2 필드를 포함한 TradeHistory 생성"""
        # 테스트용 종목 생성
        stock = Stock(code='999999', name='Test Stock', market='TEST')
        session.add(stock)
        session.flush()

        # Phase 2 필드 포함한 TradeHistory 생성
        trade = TradeHistory(
            stock_id=stock.id,
            order_id='TEST_PHASE2_001',
            order_datetime=datetime.now(),
            order_type='market',
            side='buy',
            quantity=100,
            # Phase 2 예측 정보
            entry_price=50000.0,
            target_price=55000.0,
            stop_loss_price=47500.0,
            expected_return=10.0,
            predicted_probability=0.85,
            predicted_class=1,
            model_name='xgboost_v1',
        )
        session.add(trade)
        session.commit()

        # 검증
        assert trade.id is not None
        assert trade.entry_price == 50000.0
        assert trade.target_price == 55000.0
        assert trade.stop_loss_price == 47500.0
        assert trade.expected_return == 10.0
        assert trade.predicted_probability == 0.85
        assert trade.predicted_class == 1
        assert trade.model_name == 'xgboost_v1'

        # 정리
        session.delete(trade)
        session.delete(stock)
        session.commit()

    def test_create_without_phase2_fields(self, session):
        """Phase 2 필드 없이 TradeHistory 생성 (NULL 허용 확인)"""
        stock = Stock(code='999998', name='Test Stock 2', market='TEST')
        session.add(stock)
        session.flush()

        # Phase 2 필드 없이 생성 (기존 호환성)
        trade = TradeHistory(
            stock_id=stock.id,
            order_id='TEST_NO_PHASE2_001',
            order_datetime=datetime.now(),
            order_type='limit',
            side='sell',
            quantity=50,
        )
        session.add(trade)
        session.commit()

        # Phase 2 필드는 모두 None이어야 함
        assert trade.id is not None
        assert trade.entry_price is None
        assert trade.target_price is None
        assert trade.stop_loss_price is None
        assert trade.expected_return is None
        assert trade.predicted_probability is None
        assert trade.predicted_class is None
        assert trade.model_name is None

        # 정리
        session.delete(trade)
        session.delete(stock)
        session.commit()

    def test_to_dict_includes_phase2_fields(self, session):
        """to_dict() 메서드가 Phase 2 필드를 포함하는지 확인"""
        stock = Stock(code='999997', name='Test Stock 3', market='TEST')
        session.add(stock)
        session.flush()

        trade = TradeHistory(
            stock_id=stock.id,
            order_id='TEST_DICT_001',
            order_datetime=datetime(2026, 1, 23, 10, 0, 0),
            order_type='market',
            side='buy',
            quantity=100,
            entry_price=45000.0,
            target_price=49500.0,
            stop_loss_price=42750.0,
            expected_return=10.0,
            predicted_probability=0.72,
            predicted_class=1,
            model_name='ensemble_v2',
        )
        session.add(trade)
        session.commit()

        result = trade.to_dict()

        # Phase 2 필드 확인
        assert 'entry_price' in result
        assert 'target_price' in result
        assert 'stop_loss_price' in result
        assert 'expected_return' in result
        assert 'predicted_probability' in result
        assert 'predicted_class' in result
        assert 'model_name' in result

        assert result['entry_price'] == 45000.0
        assert result['target_price'] == 49500.0
        assert result['stop_loss_price'] == 42750.0
        assert result['expected_return'] == 10.0
        assert result['predicted_probability'] == 0.72
        assert result['predicted_class'] == 1
        assert result['model_name'] == 'ensemble_v2'

        # 정리
        session.delete(trade)
        session.delete(stock)
        session.commit()

    def test_update_phase2_fields(self, session):
        """Phase 2 필드 업데이트 테스트"""
        stock = Stock(code='999996', name='Test Stock 4', market='TEST')
        session.add(stock)
        session.flush()

        # 처음에는 Phase 2 필드 없이 생성
        trade = TradeHistory(
            stock_id=stock.id,
            order_id='TEST_UPDATE_001',
            order_datetime=datetime.now(),
            order_type='market',
            side='buy',
            quantity=100,
        )
        session.add(trade)
        session.commit()

        # Phase 2 필드 업데이트
        trade.entry_price = 52000.0
        trade.target_price = 57200.0
        trade.stop_loss_price = 49400.0
        trade.expected_return = 10.0
        trade.predicted_probability = 0.68
        trade.predicted_class = 1
        trade.model_name = 'updated_model'
        session.commit()

        # 검증
        refreshed_trade = session.query(TradeHistory).filter_by(order_id='TEST_UPDATE_001').first()
        assert refreshed_trade.entry_price == 52000.0
        assert refreshed_trade.model_name == 'updated_model'

        # 정리
        session.delete(trade)
        session.delete(stock)
        session.commit()


class TestTradeHistoryEdgeCases:
    """TradeHistory 엣지 케이스 테스트"""

    def test_predicted_probability_boundary(self, session):
        """predicted_probability 경계값 테스트 (0-1)"""
        stock = Stock(code='999995', name='Test Stock 5', market='TEST')
        session.add(stock)
        session.flush()

        # 최소값 (0)
        trade_min = TradeHistory(
            stock_id=stock.id,
            order_id='TEST_PROB_MIN',
            order_datetime=datetime.now(),
            order_type='market',
            side='buy',
            quantity=100,
            predicted_probability=0.0,
        )
        session.add(trade_min)

        # 최대값 (1)
        trade_max = TradeHistory(
            stock_id=stock.id,
            order_id='TEST_PROB_MAX',
            order_datetime=datetime.now(),
            order_type='market',
            side='buy',
            quantity=100,
            predicted_probability=1.0,
        )
        session.add(trade_max)

        session.commit()

        assert trade_min.predicted_probability == 0.0
        assert trade_max.predicted_probability == 1.0

        # 정리
        session.delete(trade_min)
        session.delete(trade_max)
        session.delete(stock)
        session.commit()

    def test_predicted_class_values(self, session):
        """predicted_class 값 테스트 (0: 실패, 1: 성공)"""
        stock = Stock(code='999994', name='Test Stock 6', market='TEST')
        session.add(stock)
        session.flush()

        # 실패 예측 (0)
        trade_fail = TradeHistory(
            stock_id=stock.id,
            order_id='TEST_CLASS_FAIL',
            order_datetime=datetime.now(),
            order_type='market',
            side='buy',
            quantity=100,
            predicted_class=0,
        )
        session.add(trade_fail)

        # 성공 예측 (1)
        trade_success = TradeHistory(
            stock_id=stock.id,
            order_id='TEST_CLASS_SUCCESS',
            order_datetime=datetime.now(),
            order_type='market',
            side='buy',
            quantity=100,
            predicted_class=1,
        )
        session.add(trade_success)

        session.commit()

        assert trade_fail.predicted_class == 0
        assert trade_success.predicted_class == 1

        # 정리
        session.delete(trade_fail)
        session.delete(trade_success)
        session.delete(stock)
        session.commit()

    def test_model_name_max_length(self, session):
        """model_name 최대 길이 테스트 (50자)"""
        stock = Stock(code='999993', name='Test Stock 7', market='TEST')
        session.add(stock)
        session.flush()

        long_name = 'a' * 50  # 정확히 50자

        trade = TradeHistory(
            stock_id=stock.id,
            order_id='TEST_MODEL_NAME_LONG',
            order_datetime=datetime.now(),
            order_type='market',
            side='buy',
            quantity=100,
            model_name=long_name,
        )
        session.add(trade)
        session.commit()

        assert len(trade.model_name) == 50

        # 정리
        session.delete(trade)
        session.delete(stock)
        session.commit()
