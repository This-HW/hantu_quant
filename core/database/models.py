"""
Database models for Hantu Quant.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Index, Date, Numeric, Text, Enum
from sqlalchemy.orm import relationship, declarative_base

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


# P3-5: 추가 모델들

class WatchlistStock(Base):
    """관심종목 (Phase 1 결과)"""
    __tablename__ = 'watchlist_stocks'

    id = Column(Integer, primary_key=True)
    stock_id = Column(Integer, ForeignKey('stocks.id'), nullable=False)
    added_date = Column(Date, nullable=False)  # 편입일

    # 스코어 정보
    total_score = Column(Float, nullable=False)  # 종합 점수
    fundamental_score = Column(Float)  # 재무 점수
    technical_score = Column(Float)  # 기술적 점수
    momentum_score = Column(Float)  # 모멘텀 점수

    # 재무 지표
    roe = Column(Float)
    per = Column(Float)
    pbr = Column(Float)
    debt_ratio = Column(Float)

    # 상태
    status = Column(String(20), default='active')  # active, removed
    removed_date = Column(Date)
    removal_reason = Column(String(200))

    # 관계 설정
    stock = relationship('Stock')

    # 인덱스 설정
    __table_args__ = (
        Index('ix_watchlist_added_date', 'added_date'),
        Index('ix_watchlist_status', 'status'),
    )

    def __repr__(self):
        return f"<WatchlistStock(stock_id={self.stock_id}, score={self.total_score:.1f})>"

    def to_dict(self):
        return {
            'id': self.id,
            'stock_id': self.stock_id,
            'added_date': self.added_date.isoformat() if self.added_date else None,
            'total_score': self.total_score,
            'fundamental_score': self.fundamental_score,
            'technical_score': self.technical_score,
            'momentum_score': self.momentum_score,
            'status': self.status,
        }


class DailySelection(Base):
    """일일 선정종목 (Phase 2 결과)"""
    __tablename__ = 'daily_selections'

    id = Column(Integer, primary_key=True)
    stock_id = Column(Integer, ForeignKey('stocks.id'), nullable=False)
    selection_date = Column(Date, nullable=False)  # 선정일

    # 스코어 정보
    total_score = Column(Float, nullable=False)
    technical_score = Column(Float)  # 기술적 신호 점수
    volume_score = Column(Float)  # 거래량 점수
    momentum_score = Column(Float)  # 모멘텀 점수
    risk_score = Column(Float)  # 리스크 점수

    # 기술 지표
    rsi = Column(Float)
    macd = Column(Float)
    bb_position = Column(Float)  # 볼린저밴드 위치 (0-1)

    # 거래 정보
    target_price = Column(Float)  # 목표가
    stop_loss = Column(Float)  # 손절가
    position_size = Column(Float)  # 추천 비중

    # 신호
    signal = Column(String(20))  # buy, sell, hold
    signal_strength = Column(Float)  # 신호 강도 (0-1)

    # 결과 (나중에 업데이트)
    actual_return = Column(Float)  # 실제 수익률
    result_date = Column(Date)  # 결과 확정일

    # 관계 설정
    stock = relationship('Stock')

    # 인덱스 설정
    __table_args__ = (
        Index('ix_daily_selection_date', 'selection_date'),
        Index('ix_daily_selection_signal', 'signal'),
    )

    def __repr__(self):
        return f"<DailySelection(stock_id={self.stock_id}, date={self.selection_date}, signal={self.signal})>"

    def to_dict(self):
        return {
            'id': self.id,
            'stock_id': self.stock_id,
            'selection_date': self.selection_date.isoformat() if self.selection_date else None,
            'total_score': self.total_score,
            'signal': self.signal,
            'signal_strength': self.signal_strength,
            'target_price': self.target_price,
            'stop_loss': self.stop_loss,
            'actual_return': self.actual_return,
        }


class TradeHistory(Base):
    """거래 이력 (상세)"""
    __tablename__ = 'trade_history'

    id = Column(Integer, primary_key=True)
    stock_id = Column(Integer, ForeignKey('stocks.id'), nullable=False)

    # 주문 정보
    order_id = Column(String(50), unique=True)
    order_datetime = Column(DateTime, nullable=False)
    order_type = Column(String(20), nullable=False)  # market, limit
    side = Column(String(10), nullable=False)  # buy, sell

    # 체결 정보
    filled_datetime = Column(DateTime)
    quantity = Column(Integer, nullable=False)
    filled_quantity = Column(Integer, default=0)
    price = Column(Float)  # 지정가
    filled_price = Column(Float)  # 체결가

    # 금액
    amount = Column(Float)  # 거래금액
    commission = Column(Float, default=0)  # 수수료
    tax = Column(Float, default=0)  # 세금

    # 메타
    strategy = Column(String(50))  # 전략명
    signal_source = Column(String(50))  # 신호 출처
    daily_selection_id = Column(Integer, ForeignKey('daily_selections.id'))

    # 상태
    status = Column(String(20), default='pending')  # pending, filled, cancelled, rejected
    error_message = Column(Text)

    # 관계 설정
    stock = relationship('Stock')
    daily_selection = relationship('DailySelection')

    # 인덱스 설정
    __table_args__ = (
        Index('ix_trade_history_order_datetime', 'order_datetime'),
        Index('ix_trade_history_status', 'status'),
        Index('ix_trade_history_strategy', 'strategy'),
    )

    def __repr__(self):
        return f"<TradeHistory(order_id={self.order_id}, side={self.side}, status={self.status})>"

    def to_dict(self):
        return {
            'id': self.id,
            'order_id': self.order_id,
            'stock_id': self.stock_id,
            'order_datetime': self.order_datetime.isoformat() if self.order_datetime else None,
            'side': self.side,
            'quantity': self.quantity,
            'filled_quantity': self.filled_quantity,
            'filled_price': self.filled_price,
            'amount': self.amount,
            'status': self.status,
        }
