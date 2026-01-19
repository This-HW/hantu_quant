"""
Database service module for API server.
Provides database query functions to replace JSON file loading.
"""

from typing import List, Optional, Dict, Any
from datetime import date
from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker, Session
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.config import settings
from core.database.models import (
    Base,
    Stock as StockModel,
    WatchlistStock,
    DailySelection as DailySelectionModel,
    TradeHistory  # 에러 로그 테이블
)
from core.utils import get_logger

logger = get_logger(__name__)


class DBService:
    """Database service for API server"""

    _instance = None
    _engine = None
    _session_factory = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._init_db()
        self._initialized = True

    def _init_db(self):
        """Initialize database connection"""
        try:
            if settings.DB_TYPE == 'postgresql':
                self._engine = create_engine(
                    settings.DATABASE_URL,
                    pool_size=3,
                    max_overflow=5,
                    pool_timeout=30,
                    pool_pre_ping=True
                )
            else:
                self._engine = create_engine(
                    settings.DATABASE_URL,
                    connect_args={'check_same_thread': False}
                )

            self._session_factory = sessionmaker(bind=self._engine)

            # 테이블 생성 (없는 경우에만)
            Base.metadata.create_all(self._engine)
            logger.info(f"DBService initialized with {settings.DB_TYPE} (tables created/verified)")
        except Exception as e:
            logger.error(f"DBService initialization failed: {e}", exc_info=True)
            raise

    def get_session(self) -> Session:
        """Get a new database session"""
        return self._session_factory()

    def get_watchlist(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get active watchlist stocks

        Args:
            limit: Maximum number of stocks to return

        Returns:
            List of watchlist stock data
        """
        session = self.get_session()
        try:
            results = (
                session.query(WatchlistStock, StockModel)
                .join(StockModel, WatchlistStock.stock_id == StockModel.id)
                .filter(WatchlistStock.status == 'active')
                .order_by(desc(WatchlistStock.total_score))
                .limit(limit)
                .all()
            )

            watchlist = []
            for ws, stock in results:
                watchlist.append({
                    'id': ws.id,
                    'stock_code': stock.code,
                    'stock_name': stock.name,
                    'market': stock.market,
                    'sector': stock.sector,
                    'added_date': ws.added_date.isoformat() if ws.added_date else None,
                    'total_score': ws.total_score,
                    'fundamental_score': ws.fundamental_score,
                    'technical_score': ws.technical_score,
                    'momentum_score': ws.momentum_score,
                    'roe': ws.roe,
                    'per': ws.per,
                    'pbr': ws.pbr,
                    'status': ws.status
                })

            logger.info(f"Loaded {len(watchlist)} watchlist stocks from DB")
            return watchlist

        except Exception as e:
            logger.error(f"Error loading watchlist from DB: {e}", exc_info=True)
            return []
        finally:
            session.close()

    def get_daily_selections(
        self,
        selection_date: Optional[date] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get daily selection stocks

        Args:
            selection_date: Date to filter by (default: latest)
            limit: Maximum number of stocks to return

        Returns:
            List of daily selection data
        """
        session = self.get_session()
        try:
            query = (
                session.query(DailySelectionModel, StockModel)
                .join(StockModel, DailySelectionModel.stock_id == StockModel.id)
            )

            if selection_date:
                query = query.filter(DailySelectionModel.selection_date == selection_date)
            else:
                # Get latest date
                latest_date = session.query(
                    DailySelectionModel.selection_date
                ).order_by(desc(DailySelectionModel.selection_date)).first()

                if latest_date:
                    query = query.filter(
                        DailySelectionModel.selection_date == latest_date[0]
                    )

            results = (
                query
                .order_by(desc(DailySelectionModel.total_score))
                .limit(limit)
                .all()
            )

            selections = []
            for ds, stock in results:
                selections.append({
                    'id': ds.id,
                    'stock_code': stock.code,
                    'stock_name': stock.name,
                    'market': stock.market,
                    'sector': stock.sector,
                    'selection_date': ds.selection_date.isoformat() if ds.selection_date else None,
                    'total_score': ds.total_score,
                    'technical_score': ds.technical_score,
                    'volume_score': ds.volume_score,
                    'momentum_score': ds.momentum_score,
                    'risk_score': ds.risk_score,
                    'rsi': ds.rsi,
                    'macd': ds.macd,
                    'signal': ds.signal,
                    'signal_strength': ds.signal_strength,
                    'target_price': ds.target_price,
                    'stop_loss': ds.stop_loss,
                    'position_size': ds.position_size
                })

            logger.info(f"Loaded {len(selections)} daily selections from DB")
            return selections

        except Exception as e:
            logger.error(f"Error loading daily selections from DB: {e}", exc_info=True)
            return []
        finally:
            session.close()

    def get_stocks(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get stock master list

        Args:
            limit: Maximum number of stocks to return

        Returns:
            List of stock data
        """
        session = self.get_session()
        try:
            results = session.query(StockModel).limit(limit).all()

            stocks = []
            for stock in results:
                stocks.append({
                    'code': stock.code,
                    'name': stock.name,
                    'market': stock.market,
                    'sector': stock.sector
                })

            logger.info(f"Loaded {len(stocks)} stocks from DB")
            return stocks

        except Exception as e:
            logger.error(f"Error loading stocks from DB: {e}", exc_info=True)
            return []
        finally:
            session.close()

    def get_trade_history(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get trade history

        Args:
            start_date: Start date filter
            end_date: End date filter
            limit: Maximum number of trades to return

        Returns:
            List of trade history data
        """
        session = self.get_session()
        try:
            query = (
                session.query(TradeHistory, StockModel)
                .join(StockModel, TradeHistory.stock_id == StockModel.id)
            )

            if start_date:
                query = query.filter(TradeHistory.order_datetime >= start_date)
            if end_date:
                query = query.filter(TradeHistory.order_datetime <= end_date)

            results = (
                query
                .order_by(desc(TradeHistory.order_datetime))
                .limit(limit)
                .all()
            )

            trades = []
            for th, stock in results:
                trades.append({
                    'id': th.id,
                    'order_id': th.order_id,
                    'stock_code': stock.code,
                    'stock_name': stock.name,
                    'order_datetime': th.order_datetime.isoformat() if th.order_datetime else None,
                    'side': th.side,
                    'quantity': th.quantity,
                    'filled_quantity': th.filled_quantity,
                    'price': th.price,
                    'filled_price': th.filled_price,
                    'amount': th.amount,
                    'commission': th.commission,
                    'status': th.status,
                    'strategy': th.strategy
                })

            return trades

        except Exception as e:
            logger.error(f"Error loading trade history from DB: {e}", exc_info=True)
            return []
        finally:
            session.close()


# Singleton instance
db_service = DBService()
