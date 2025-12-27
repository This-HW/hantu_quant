"""
데이터베이스 마이그레이션 테스트 (P3-5)

테스트 항목:
1. 모델 생성
2. 마이그레이션 결과
3. 리포지토리 CRUD
"""

import pytest
import json
import tempfile
from datetime import datetime, date
from pathlib import Path
import sys

# 프로젝트 루트 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database.models import (
    Base,
    Stock,
    WatchlistStock,
    DailySelection,
    TradeHistory,
)
from core.database.repository import (
    WatchlistRepository,
    DailySelectionRepository,
    TradeHistoryRepository,
)
from core.database.migration import (
    DataMigrator,
    MigrationResult,
)


@pytest.fixture
def db_session():
    """테스트용 인메모리 DB 세션"""
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def sample_stock(db_session):
    """테스트용 종목"""
    stock = Stock(code='005930', name='삼성전자', market='KOSPI')
    db_session.add(stock)
    db_session.commit()
    return stock


class TestWatchlistStock:
    """WatchlistStock 모델 테스트"""

    def test_create_watchlist(self, db_session, sample_stock):
        """관심종목 생성"""
        watchlist = WatchlistStock(
            stock_id=sample_stock.id,
            added_date=date.today(),
            total_score=85.5,
            fundamental_score=90.0,
            technical_score=80.0,
        )
        db_session.add(watchlist)
        db_session.commit()

        assert watchlist.id is not None
        assert watchlist.total_score == 85.5

    def test_to_dict(self, db_session, sample_stock):
        """딕셔너리 변환"""
        watchlist = WatchlistStock(
            stock_id=sample_stock.id,
            added_date=date.today(),
            total_score=85.5,
        )
        db_session.add(watchlist)
        db_session.commit()

        d = watchlist.to_dict()
        assert d['total_score'] == 85.5
        assert 'added_date' in d


class TestDailySelection:
    """DailySelection 모델 테스트"""

    def test_create_selection(self, db_session, sample_stock):
        """선정종목 생성"""
        selection = DailySelection(
            stock_id=sample_stock.id,
            selection_date=date.today(),
            total_score=75.0,
            signal='buy',
            signal_strength=0.8,
            target_price=80000,
            stop_loss=70000,
        )
        db_session.add(selection)
        db_session.commit()

        assert selection.id is not None
        assert selection.signal == 'buy'

    def test_to_dict(self, db_session, sample_stock):
        """딕셔너리 변환"""
        selection = DailySelection(
            stock_id=sample_stock.id,
            selection_date=date.today(),
            total_score=75.0,
            signal='buy',
        )
        db_session.add(selection)
        db_session.commit()

        d = selection.to_dict()
        assert d['signal'] == 'buy'


class TestTradeHistory:
    """TradeHistory 모델 테스트"""

    def test_create_trade(self, db_session, sample_stock):
        """거래 이력 생성"""
        trade = TradeHistory(
            stock_id=sample_stock.id,
            order_id='ORD001',
            order_datetime=datetime.now(),
            order_type='market',
            side='buy',
            quantity=100,
            filled_quantity=100,
            filled_price=75000,
            status='filled',
        )
        db_session.add(trade)
        db_session.commit()

        assert trade.id is not None
        assert trade.status == 'filled'

    def test_to_dict(self, db_session, sample_stock):
        """딕셔너리 변환"""
        trade = TradeHistory(
            stock_id=sample_stock.id,
            order_id='ORD002',
            order_datetime=datetime.now(),
            order_type='limit',
            side='sell',
            quantity=50,
        )
        db_session.add(trade)
        db_session.commit()

        d = trade.to_dict()
        assert d['order_id'] == 'ORD002'


class TestWatchlistRepository:
    """WatchlistRepository 테스트"""

    def test_add(self, db_session, sample_stock):
        """추가"""
        repo = WatchlistRepository(db_session)

        watchlist = WatchlistStock(
            stock_id=sample_stock.id,
            added_date=date.today(),
            total_score=85.0,
        )
        result = repo.add(watchlist)
        db_session.commit()

        assert result is not None
        assert result.id is not None

    def test_get_active(self, db_session, sample_stock):
        """활성 조회"""
        repo = WatchlistRepository(db_session)

        watchlist = WatchlistStock(
            stock_id=sample_stock.id,
            added_date=date.today(),
            total_score=85.0,
            status='active',
        )
        repo.add(watchlist)
        db_session.commit()

        active = repo.get_active()
        assert len(active) == 1

    def test_get_top(self, db_session, sample_stock):
        """상위 N개 조회"""
        repo = WatchlistRepository(db_session)

        for score in [90, 85, 80]:
            w = WatchlistStock(
                stock_id=sample_stock.id,
                added_date=date.today(),
                total_score=score,
            )
            repo.add(w)
        db_session.commit()

        top = repo.get_top(2)
        assert len(top) == 2
        assert top[0].total_score == 90


class TestDailySelectionRepository:
    """DailySelectionRepository 테스트"""

    def test_add(self, db_session, sample_stock):
        """추가"""
        repo = DailySelectionRepository(db_session)

        selection = DailySelection(
            stock_id=sample_stock.id,
            selection_date=date.today(),
            total_score=75.0,
            signal='buy',
        )
        result = repo.add(selection)
        db_session.commit()

        assert result is not None

    def test_get_by_date(self, db_session, sample_stock):
        """날짜별 조회"""
        repo = DailySelectionRepository(db_session)

        selection = DailySelection(
            stock_id=sample_stock.id,
            selection_date=date.today(),
            total_score=75.0,
            signal='buy',
        )
        repo.add(selection)
        db_session.commit()

        results = repo.get_by_date(datetime.now())
        assert len(results) == 1


class TestTradeHistoryRepository:
    """TradeHistoryRepository 테스트"""

    def test_add(self, db_session, sample_stock):
        """추가"""
        repo = TradeHistoryRepository(db_session)

        trade = TradeHistory(
            stock_id=sample_stock.id,
            order_id='ORD003',
            order_datetime=datetime.now(),
            order_type='market',
            side='buy',
            quantity=100,
        )
        result = repo.add(trade)
        db_session.commit()

        assert result is not None

    def test_get_by_order_id(self, db_session, sample_stock):
        """주문 ID로 조회"""
        repo = TradeHistoryRepository(db_session)

        trade = TradeHistory(
            stock_id=sample_stock.id,
            order_id='ORD004',
            order_datetime=datetime.now(),
            order_type='market',
            side='sell',
            quantity=50,
        )
        repo.add(trade)
        db_session.commit()

        result = repo.get_by_order_id('ORD004')
        assert result is not None
        assert result.quantity == 50

    def test_get_recent(self, db_session, sample_stock):
        """최근 거래 조회"""
        repo = TradeHistoryRepository(db_session)

        for i in range(3):
            trade = TradeHistory(
                stock_id=sample_stock.id,
                order_id=f'ORD{i}',
                order_datetime=datetime.now(),
                order_type='market',
                side='buy',
                quantity=10 * (i + 1),
            )
            repo.add(trade)
        db_session.commit()

        recent = repo.get_recent(2)
        assert len(recent) == 2


class TestMigrationResult:
    """MigrationResult 테스트"""

    def test_create_result(self):
        """결과 생성"""
        result = MigrationResult()
        result.total = 10
        result.success = 8
        result.failed = 2

        assert result.success_rate == 0.8

    def test_to_dict(self):
        """딕셔너리 변환"""
        result = MigrationResult()
        result.total = 10
        result.success = 8
        result.failed = 2
        result.errors = ['error1', 'error2']

        d = result.to_dict()
        assert d['total'] == 10
        assert d['success_rate'] == '80.0%'


class TestDataMigrator:
    """DataMigrator 테스트"""

    def test_migrate_watchlist(self, db_session):
        """관심종목 마이그레이션"""
        migrator = DataMigrator(db_session)

        # 테스트 JSON 생성
        data = [
            {
                'code': '005930',
                'name': '삼성전자',
                'total_score': 85.0,
                'added_date': '2024-12-25',
            },
            {
                'code': '000660',
                'name': 'SK하이닉스',
                'total_score': 80.0,
            },
        ]

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(data, f)
            json_path = f.name

        result = migrator.migrate_watchlist(json_path)

        assert result.total == 2
        assert result.success == 2
        assert result.failed == 0

    def test_migrate_daily_selections(self, db_session):
        """선정종목 마이그레이션"""
        migrator = DataMigrator(db_session)

        data = [
            {
                'code': '005930',
                'total_score': 75.0,
                'signal': 'buy',
                'selection_date': '2024-12-25',
            },
        ]

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(data, f)
            json_path = f.name

        result = migrator.migrate_daily_selections(json_path)

        assert result.total == 1
        assert result.success == 1

    def test_migrate_file_not_found(self, db_session):
        """파일 없음"""
        migrator = DataMigrator(db_session)

        result = migrator.migrate_watchlist('/nonexistent/file.json')

        assert result.total == 0
        assert len(result.errors) > 0

    def test_migrate_invalid_json(self, db_session):
        """잘못된 JSON"""
        migrator = DataMigrator(db_session)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('invalid json')
            json_path = f.name

        result = migrator.migrate_watchlist(json_path)

        assert result.total == 0
        assert len(result.errors) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
