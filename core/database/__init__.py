"""
데이터베이스 모듈 (P3-5 업데이트)

SQLAlchemy 기반 데이터베이스 관리

포함:
- 세션 관리
- 모델 (Stock, Price, Indicator, Trade + WatchlistStock, DailySelection, TradeHistory)
- 리포지토리 (Repository 패턴)
- 마이그레이션 (JSON → DB)
"""

from .session import DatabaseSession
from .models import (
    Base,
    Stock,
    Price,
    Indicator,
    Trade,
    # P3-5 추가 모델
    WatchlistStock,
    DailySelection,
    TradeHistory,
)
from .repository import (
    StockRepository,
    # P3-5 추가 리포지토리
    WatchlistRepository,
    DailySelectionRepository,
    TradeHistoryRepository,
)
from .migration import (
    DataMigrator,
    MigrationResult,
)

__all__ = [
    # Session
    'DatabaseSession',
    # Models
    'Base',
    'Stock',
    'Price',
    'Indicator',
    'Trade',
    'WatchlistStock',
    'DailySelection',
    'TradeHistory',
    # Repositories
    'StockRepository',
    'WatchlistRepository',
    'DailySelectionRepository',
    'TradeHistoryRepository',
    # Migration
    'DataMigrator',
    'MigrationResult',
]
