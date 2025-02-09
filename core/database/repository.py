"""데이터베이스 저장소 모듈"""

from typing import List, Optional, Dict, Any
from datetime import datetime
import json
from decimal import Decimal

from sqlalchemy import and_
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from .models import Stock, Price, Indicator, Trade
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
            logger.error(f"종목 정보 저장 중 오류 발생: {str(e)}")
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
            logger.error(f"종목 정보 조회 중 오류 발생: {str(e)}")
            return None

    def get_all_stocks(self) -> List[Stock]:
        """전체 종목 목록 조회"""
        try:
            stocks = self.session.query(Stock).all()
            logger.debug(f"전체 종목 수: {len(stocks)}개")
            return stocks
        except SQLAlchemyError as e:
            logger.error(f"전체 종목 목록 조회 중 오류 발생: {str(e)}")
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
            logger.error(f"가격 정보 저장 중 오류 발생: {str(e)}")
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
            logger.error(f"가격 정보 조회 중 오류 발생: {str(e)}")
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
            logger.error(f"기술적 지표 저장 중 오류 발생: {str(e)}")
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
            logger.error(f"기술적 지표 조회 중 오류 발생: {str(e)}")
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
            logger.error(f"거래 내역 저장 중 오류 발생: {str(e)}")

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
            logger.error(f"거래 내역 조회 중 오류 발생: {str(e)}")
            return [] 