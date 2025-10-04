"""
Database models for Hantu Quant.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Index, Date, Numeric, Text, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Stock(Base):
    """주식 종목 정보"""
    __tablename__ = 'stocks'
    
    id = Column(Integer, primary_key=True)
    code = Column(String(20), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    market = Column(String(20), nullable=False)
    sector = Column(String(50))  # 섹터
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # 관계 설정
    prices = relationship('Price', back_populates='stock')
    indicators = relationship('Indicator', back_populates='stock')
    
    def __repr__(self):
        return f"<Stock(code='{self.code}', name='{self.name}')>"

class Price(Base):
    """주가 정보"""
    __tablename__ = 'prices'

    id = Column(Integer, primary_key=True)
    stock_id = Column(Integer, ForeignKey('stocks.id'), nullable=False)
    date = Column(Date, nullable=False)
    open_price = Column(Numeric(10, 2), nullable=False)
    high_price = Column(Numeric(10, 2), nullable=False)
    low_price = Column(Numeric(10, 2), nullable=False)
    close_price = Column(Numeric(10, 2), nullable=False)
    volume = Column(Integer, nullable=False)
    
    # 관계 설정
    stock = relationship('Stock', back_populates='prices')

class Indicator(Base):
    """기술적 지표 정보"""
    __tablename__ = 'indicators'

    id = Column(Integer, primary_key=True)
    stock_id = Column(Integer, ForeignKey('stocks.id'), nullable=False)
    date = Column(Date, nullable=False)
    name = Column(String(50), nullable=False)
    value = Column(Numeric(10, 4), nullable=False)
    meta_data = Column(Text)
    
    # 관계 설정
    stock = relationship('Stock', back_populates='indicators')

class Trade(Base):
    """거래 내역"""
    __tablename__ = 'trades'
    
    id = Column(Integer, primary_key=True)
    stock_id = Column(Integer, ForeignKey('stocks.id'), nullable=False)
    datetime = Column(DateTime, nullable=False)  # 거래 시각
    type = Column(String(10), nullable=False)  # 매수/매도
    price = Column(Float, nullable=False)  # 거래가
    quantity = Column(Integer, nullable=False)  # 수량
    amount = Column(Float, nullable=False)  # 거래금액
    commission = Column(Float, nullable=False)  # 수수료
    strategy = Column(String(50))  # 전략명
    
    # 관계 설정
    stock = relationship('Stock')
    
    # 인덱스 설정
    __table_args__ = (
        Index('ix_trades_datetime', 'datetime'),
        Index('ix_trades_stock_datetime', 'stock_id', 'datetime'),
    )
    
    def __repr__(self):
        return f"<Trade(stock_id={self.stock_id}, type='{self.type}', datetime='{self.datetime}')>"
