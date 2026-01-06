"""데이터베이스 저장소 모듈"""

from typing import List, Optional, Dict, Any
from datetime import datetime
import json
from decimal import Decimal

from sqlalchemy import and_
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from .models import Stock, Price, Indicator, Trade, WatchlistStock, DailySelection, TradeHistory
from .session import DatabaseSession
from core.utils import get_logger

logger = get_logger(__name__)

class StockRepository:
    """주식 데이터 저장소"""

    def __init__(self, session: Session):
        self.session = session

    def save_stock(self, code: str, name: str, market: str, sector: str = None) -> Optional[Stock]:
        """종목 정보 저장"""
        try:
            stock = self.session.query(Stock).filter_by(code=code).first()
            if stock:
                stock.name = name
                stock.market = market
                stock.sector = sector
                logger.debug(f"종목 정보 업데이트: {code} - {name}")
            else:
                stock = Stock(code=code, name=name, market=market, sector=sector)
                self.session.add(stock)
                logger.debug(f"신규 종목 추가: {code} - {name}")
            return stock
        except SQLAlchemyError as e:
            logger.error(f"종목 정보 저장 중 오류 발생: {str(e)}", exc_info=True)
            return None

    def get_stock(self, code: str) -> Optional[Stock]:
        """종목 정보 조회"""
        try:
            stock = self.session.query(Stock).filter_by(code=code).first()
            if stock:
                logger.debug(f"종목 정보 조회: {code} - {stock.name}")
            else:
                logger.debug(f"종목 정보 없음: {code}")
            return stock
        except SQLAlchemyError as e:
            logger.error(f"종목 정보 조회 중 오류 발생: {str(e)}", exc_info=True)
            return None

    def get_all_stocks(self) -> List[Stock]:
        """전체 종목 목록 조회"""
        try:
            stocks = self.session.query(Stock).all()
            logger.debug(f"전체 종목 수: {len(stocks)}개")
            return stocks
        except SQLAlchemyError as e:
            logger.error(f"전체 종목 목록 조회 중 오류 발생: {str(e)}", exc_info=True)
            return []

    def save_price(self, stock_id: int, date: datetime, open_price: Decimal,
                  high_price: Decimal, low_price: Decimal, close_price: Decimal,
                  volume: int) -> Optional[Price]:
        """가격 정보 저장"""
        try:
            price = Price(
                stock_id=stock_id,
                date=date,
                open_price=open_price,
                high_price=high_price,
                low_price=low_price,
                close_price=close_price,
                volume=volume
            )
            self.session.add(price)
            return price
        except SQLAlchemyError as e:
            logger.error(f"가격 정보 저장 중 오류 발생: {str(e)}", exc_info=True)
            return None

    def get_stock_prices(self, stock_id: int, start_date: Optional[datetime] = None,
                        end_date: Optional[datetime] = None) -> List[Price]:
        """가격 정보 조회"""
        try:
            query = self.session.query(Price).filter(Price.stock_id == stock_id)
            if start_date:
                query = query.filter(Price.date >= start_date)
            if end_date:
                query = query.filter(Price.date <= end_date)
            return query.order_by(Price.date).all()
        except SQLAlchemyError as e:
            logger.error(f"가격 정보 조회 중 오류 발생: {str(e)}", exc_info=True)
            return []

    def save_indicator(self, stock_id: int, date: datetime, name: str,
                      value: Decimal, meta_data: Optional[Dict[str, Any]] = None) -> Optional[Indicator]:
        """기술적 지표 저장"""
        try:
            indicator = Indicator(
                stock_id=stock_id,
                date=date,
                name=name,
                value=value,
                meta_data=str(meta_data) if meta_data else None
            )
            self.session.add(indicator)
            return indicator
        except SQLAlchemyError as e:
            logger.error(f"기술적 지표 저장 중 오류 발생: {str(e)}", exc_info=True)
            return None

    def get_indicators(self, stock_id: int, name: str,
                      start_date: Optional[datetime] = None,
                      end_date: Optional[datetime] = None) -> List[Indicator]:
        """기술적 지표 조회"""
        try:
            query = self.session.query(Indicator).filter(
                Indicator.stock_id == stock_id,
                Indicator.name == name
            )
            if start_date:
                query = query.filter(Indicator.date >= start_date)
            if end_date:
                query = query.filter(Indicator.date <= end_date)
            return query.order_by(Indicator.date).all()
        except SQLAlchemyError as e:
            logger.error(f"기술적 지표 조회 중 오류 발생: {str(e)}", exc_info=True)
            return []

    def save_trade(self, stock_id: int, trade_type: str, price: float,
                   quantity: int, amount: float, commission: float,
                   strategy: str = None):
        """거래 내역 저장"""
        try:
            trade = Trade(
                stock_id=stock_id,
                datetime=datetime.now(),
                type=trade_type,
                price=price,
                quantity=quantity,
                amount=amount,
                commission=commission,
                strategy=strategy
            )
            self.session.add(trade)
            logger.info(f"거래 내역 저장: stock_id={stock_id}, {trade_type}, {quantity}주, {amount:,.0f}원")
        except SQLAlchemyError as e:
            logger.error(f"거래 내역 저장 중 오류 발생: {str(e)}", exc_info=True)

    def get_trades(self, stock_id: Optional[int] = None,
                   start_date: Optional[datetime] = None,
                   end_date: Optional[datetime] = None) -> List[Trade]:
        """거래 내역 조회"""
        try:
            query = self.session.query(Trade)
            
            if stock_id:
                query = query.filter_by(stock_id=stock_id)
            if start_date:
                query = query.filter(Trade.datetime >= start_date)
            if end_date:
                query = query.filter(Trade.datetime <= end_date)
                
            trades = query.order_by(Trade.datetime).all()
            logger.debug(f"거래 내역 조회: {len(trades)}개")
            return trades
        except SQLAlchemyError as e:
            logger.error(f"거래 내역 조회 중 오류 발생: {str(e)}", exc_info=True)
            return []


# P3-5: 추가 리포지토리들

class WatchlistRepository:
    """관심종목 리포지토리"""

    def __init__(self, session: Session):
        self.session = session

    def add(self, watchlist: WatchlistStock) -> Optional[WatchlistStock]:
        """관심종목 추가"""
        try:
            self.session.add(watchlist)
            self.session.flush()
            logger.info(f"관심종목 추가: stock_id={watchlist.stock_id}")
            return watchlist
        except SQLAlchemyError as e:
            logger.error(f"관심종목 추가 실패: {e}", exc_info=True)
            return None

    def get_active(self) -> List[WatchlistStock]:
        """활성 관심종목 조회"""
        try:
            return self.session.query(WatchlistStock).filter_by(
                status='active'
            ).order_by(WatchlistStock.total_score.desc()).all()
        except SQLAlchemyError as e:
            logger.error(f"관심종목 조회 실패: {e}", exc_info=True)
            return []

    def get_by_date(self, target_date: datetime) -> List[WatchlistStock]:
        """날짜별 관심종목 조회"""
        try:
            return self.session.query(WatchlistStock).filter(
                WatchlistStock.added_date == target_date.date()
            ).all()
        except SQLAlchemyError as e:
            logger.error(f"관심종목 조회 실패: {e}", exc_info=True)
            return []

    def remove(self, stock_id: int, reason: str = None) -> bool:
        """관심종목 제거 (soft delete)"""
        try:
            watchlist = self.session.query(WatchlistStock).filter_by(
                stock_id=stock_id, status='active'
            ).first()
            if watchlist:
                watchlist.status = 'removed'
                watchlist.removed_date = datetime.now().date()
                watchlist.removal_reason = reason
                logger.info(f"관심종목 제거: stock_id={stock_id}")
                return True
            return False
        except SQLAlchemyError as e:
            logger.error(f"관심종목 제거 실패: {e}", exc_info=True)
            return False

    def get_top(self, n: int = 10) -> List[WatchlistStock]:
        """상위 N개 관심종목"""
        try:
            return self.session.query(WatchlistStock).filter_by(
                status='active'
            ).order_by(WatchlistStock.total_score.desc()).limit(n).all()
        except SQLAlchemyError as e:
            logger.error(f"관심종목 조회 실패: {e}", exc_info=True)
            return []


class DailySelectionRepository:
    """일일 선정종목 리포지토리"""

    def __init__(self, session: Session):
        self.session = session

    def add(self, selection: DailySelection) -> Optional[DailySelection]:
        """선정종목 추가"""
        try:
            self.session.add(selection)
            self.session.flush()
            logger.info(f"선정종목 추가: stock_id={selection.stock_id}, date={selection.selection_date}")
            return selection
        except SQLAlchemyError as e:
            logger.error(f"선정종목 추가 실패: {e}", exc_info=True)
            return None

    def get_by_date(self, target_date: datetime) -> List[DailySelection]:
        """날짜별 선정종목 조회"""
        try:
            return self.session.query(DailySelection).filter(
                DailySelection.selection_date == target_date.date()
            ).order_by(DailySelection.total_score.desc()).all()
        except SQLAlchemyError as e:
            logger.error(f"선정종목 조회 실패: {e}", exc_info=True)
            return []

    def get_by_signal(self, signal: str, days: int = 30) -> List[DailySelection]:
        """신호별 선정종목 조회"""
        try:
            from datetime import timedelta
            start_date = datetime.now().date() - timedelta(days=days)
            return self.session.query(DailySelection).filter(
                DailySelection.signal == signal,
                DailySelection.selection_date >= start_date
            ).order_by(DailySelection.selection_date.desc()).all()
        except SQLAlchemyError as e:
            logger.error(f"선정종목 조회 실패: {e}", exc_info=True)
            return []

    def update_result(self, selection_id: int, actual_return: float) -> bool:
        """결과 업데이트"""
        try:
            selection = self.session.query(DailySelection).get(selection_id)
            if selection:
                selection.actual_return = actual_return
                selection.result_date = datetime.now().date()
                logger.info(f"선정종목 결과 업데이트: id={selection_id}, return={actual_return:.2%}")
                return True
            return False
        except SQLAlchemyError as e:
            logger.error(f"결과 업데이트 실패: {e}", exc_info=True)
            return False

    def get_performance_stats(self, days: int = 30) -> Dict:
        """성과 통계"""
        try:
            from datetime import timedelta
            start_date = datetime.now().date() - timedelta(days=days)
            selections = self.session.query(DailySelection).filter(
                DailySelection.selection_date >= start_date,
                DailySelection.actual_return.isnot(None)
            ).all()

            if not selections:
                return {}

            returns = [s.actual_return for s in selections]
            wins = sum(1 for r in returns if r > 0)

            return {
                'total_count': len(returns),
                'win_count': wins,
                'win_rate': wins / len(returns) if returns else 0,
                'avg_return': sum(returns) / len(returns) if returns else 0,
                'max_return': max(returns) if returns else 0,
                'min_return': min(returns) if returns else 0,
            }
        except SQLAlchemyError as e:
            logger.error(f"성과 통계 조회 실패: {e}", exc_info=True)
            return {}


class TradeHistoryRepository:
    """거래 이력 리포지토리"""

    def __init__(self, session: Session):
        self.session = session

    def add(self, trade: TradeHistory) -> Optional[TradeHistory]:
        """거래 이력 추가"""
        try:
            self.session.add(trade)
            self.session.flush()
            logger.info(f"거래 이력 추가: order_id={trade.order_id}")
            return trade
        except SQLAlchemyError as e:
            logger.error(f"거래 이력 추가 실패: {e}", exc_info=True)
            return None

    def get_by_order_id(self, order_id: str) -> Optional[TradeHistory]:
        """주문 ID로 조회"""
        try:
            return self.session.query(TradeHistory).filter_by(order_id=order_id).first()
        except SQLAlchemyError as e:
            logger.error(f"거래 이력 조회 실패: {e}", exc_info=True)
            return None

    def get_by_status(self, status: str) -> List[TradeHistory]:
        """상태별 조회"""
        try:
            return self.session.query(TradeHistory).filter_by(
                status=status
            ).order_by(TradeHistory.order_datetime.desc()).all()
        except SQLAlchemyError as e:
            logger.error(f"거래 이력 조회 실패: {e}", exc_info=True)
            return []

    def get_recent(self, limit: int = 50) -> List[TradeHistory]:
        """최근 거래 이력"""
        try:
            return self.session.query(TradeHistory).order_by(
                TradeHistory.order_datetime.desc()
            ).limit(limit).all()
        except SQLAlchemyError as e:
            logger.error(f"거래 이력 조회 실패: {e}", exc_info=True)
            return []

    def update_status(self, order_id: str, status: str, filled_price: float = None) -> bool:
        """상태 업데이트"""
        try:
            trade = self.session.query(TradeHistory).filter_by(order_id=order_id).first()
            if trade:
                trade.status = status
                if filled_price:
                    trade.filled_price = filled_price
                    trade.filled_datetime = datetime.now()
                logger.info(f"거래 상태 업데이트: order_id={order_id}, status={status}")
                return True
            return False
        except SQLAlchemyError as e:
            logger.error(f"상태 업데이트 실패: {e}", exc_info=True)
            return False

    def get_by_strategy(self, strategy: str, days: int = 30) -> List[TradeHistory]:
        """전략별 거래 이력"""
        try:
            from datetime import timedelta
            start_date = datetime.now() - timedelta(days=days)
            return self.session.query(TradeHistory).filter(
                TradeHistory.strategy == strategy,
                TradeHistory.order_datetime >= start_date
            ).order_by(TradeHistory.order_datetime.desc()).all()
        except SQLAlchemyError as e:
            logger.error(f"거래 이력 조회 실패: {e}", exc_info=True)
            return []