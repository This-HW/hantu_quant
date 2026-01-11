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


class ErrorLog(Base):
    """에러 로그 (중앙 집중식 에러 추적)"""
    __tablename__ = 'error_logs'

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.now)
    level = Column(String(20), nullable=False)  # ERROR, CRITICAL, WARNING
    service = Column(String(50), nullable=False)  # api-server, scheduler, etc.
    module = Column(String(100))  # 모듈/파일명
    function = Column(String(100))  # 함수명
    message = Column(Text, nullable=False)  # 에러 메시지
    error_type = Column(String(100))  # Exception 타입
    stack_trace = Column(Text)  # 스택 트레이스
    context = Column(Text)  # JSON 형태의 추가 컨텍스트
    resolved = Column(DateTime)  # 해결 시각
    resolution_note = Column(Text)  # 해결 방법

    __table_args__ = (
        Index('ix_error_logs_timestamp', 'timestamp'),
        Index('ix_error_logs_level', 'level'),
        Index('ix_error_logs_service', 'service'),
    )

    def __repr__(self):
        return f"<ErrorLog(id={self.id}, level={self.level}, service={self.service})>"


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

    # Phase 2 예측 정보 (학습 피드백용)
    entry_price = Column(Float)  # Phase 2 진입가
    target_price = Column(Float)  # Phase 2 목표가
    stop_loss_price = Column(Float)  # Phase 2 손절가
    expected_return = Column(Float)  # Phase 2 예상 수익률 (%)
    predicted_probability = Column(Float)  # Phase 2 신뢰도 (0-1)
    predicted_class = Column(Integer)  # 예측 분류 (0: 실패, 1: 성공)
    model_name = Column(String(50))  # 예측 모델명

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
            # Phase 2 예측 정보
            'entry_price': self.entry_price,
            'target_price': self.target_price,
            'stop_loss_price': self.stop_loss_price,
            'expected_return': self.expected_return,
            'predicted_probability': self.predicted_probability,
            'predicted_class': self.predicted_class,
            'model_name': self.model_name,
        }


# ============================================================
# Phase 4: 학습 시스템 통합 테이블
# ============================================================

class FeedbackData(Base):
    """예측 피드백 데이터 (Phase 4 학습용)"""
    __tablename__ = 'feedback_data'

    id = Column(Integer, primary_key=True)
    prediction_id = Column(String(100), unique=True, nullable=False)
    stock_code = Column(String(20), nullable=False)
    prediction_date = Column(Date, nullable=False)

    # 예측 정보
    predicted_probability = Column(Float, nullable=False)
    predicted_class = Column(Integer, nullable=False)  # 0: 실패, 1: 성공
    model_name = Column(String(50), nullable=False)

    # 실제 결과
    actual_return_7d = Column(Float)
    actual_class = Column(Integer)  # 0: 실패, 1: 성공

    # 피드백 메트릭
    prediction_error = Column(Float)
    absolute_error = Column(Float)
    feedback_date = Column(Date)
    is_processed = Column(Integer, default=0)  # Boolean as Integer for compatibility

    # 추가 정보
    factor_scores = Column(Text)  # JSON 형태로 저장
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        Index('ix_feedback_prediction_id', 'prediction_id'),
        Index('ix_feedback_stock_code', 'stock_code'),
        Index('ix_feedback_prediction_date', 'prediction_date'),
        Index('ix_feedback_model_name', 'model_name'),
    )

    def to_dict(self):
        return {
            'prediction_id': self.prediction_id,
            'stock_code': self.stock_code,
            'prediction_date': self.prediction_date.isoformat() if self.prediction_date else None,
            'predicted_probability': self.predicted_probability,
            'predicted_class': self.predicted_class,
            'model_name': self.model_name,
            'actual_return_7d': self.actual_return_7d,
            'actual_class': self.actual_class,
            'prediction_error': self.prediction_error,
            'is_processed': bool(self.is_processed),
            'factor_scores': self.factor_scores,
        }


class ModelPerformanceHistory(Base):
    """모델 성능 히스토리"""
    __tablename__ = 'model_performance_history'

    id = Column(Integer, primary_key=True)
    model_name = Column(String(50), nullable=False)
    evaluation_date = Column(Date, nullable=False)

    # 성능 메트릭
    accuracy = Column(Float)
    precision_score = Column(Float)
    recall_score = Column(Float)
    f1_score = Column(Float)
    auc_score = Column(Float)
    feedback_count = Column(Integer)

    created_at = Column(DateTime, default=datetime.now)

    __table_args__ = (
        Index('ix_model_perf_model_name', 'model_name'),
        Index('ix_model_perf_eval_date', 'evaluation_date'),
    )


class ScreeningResult(Base):
    """스크리닝 결과 (Phase 1)"""
    __tablename__ = 'screening_results'

    id = Column(Integer, primary_key=True)
    screening_date = Column(Date, nullable=False)
    stock_code = Column(String(20), nullable=False)
    stock_name = Column(String(100))

    # 스코어
    total_score = Column(Float)
    fundamental_score = Column(Float)
    technical_score = Column(Float)
    momentum_score = Column(Float)

    # 통과 여부
    passed = Column(Integer, default=0)  # Boolean

    # 재무 지표
    roe = Column(Float)
    per = Column(Float)
    pbr = Column(Float)
    debt_ratio = Column(Float)

    created_at = Column(DateTime, default=datetime.now)

    __table_args__ = (
        Index('ix_screening_date', 'screening_date'),
        Index('ix_screening_stock_code', 'stock_code'),
    )


class SelectionResult(Base):
    """선정 결과 (Phase 2)"""
    __tablename__ = 'selection_results'

    id = Column(Integer, primary_key=True)
    selection_date = Column(Date, nullable=False)
    stock_code = Column(String(20), nullable=False)
    stock_name = Column(String(100))

    # 스코어
    total_score = Column(Float)
    technical_score = Column(Float)
    volume_score = Column(Float)
    pattern_score = Column(Float)
    risk_score = Column(Float)

    # 거래 정보
    entry_price = Column(Float)
    target_price = Column(Float)
    stop_loss = Column(Float)
    expected_return = Column(Float)
    confidence = Column(Float)

    # 신호
    signal = Column(String(20))  # buy, sell, hold
    selection_reason = Column(Text)
    market_condition = Column(String(50))

    # 결과 (7일 후 업데이트)
    actual_return_7d = Column(Float)
    is_success = Column(Integer)  # 0: 실패, 1: 성공

    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        Index('ix_selection_date', 'selection_date'),
        Index('ix_selection_stock_code', 'stock_code'),
    )


class NotificationHistory(Base):
    """알림 이력"""
    __tablename__ = 'notification_history'

    id = Column(Integer, primary_key=True)
    alert_id = Column(String(50))
    alert_type = Column(String(50))
    level = Column(String(20))  # info, warning, error, critical
    title = Column(String(200))
    message = Column(Text)
    channel = Column(String(20))  # telegram, email
    recipient = Column(String(100))
    status = Column(String(20))  # sent, failed, filtered
    error_message = Column(Text)
    trace_id = Column(String(50))
    created_at = Column(DateTime, default=datetime.now)
    sent_at = Column(DateTime)
    response_data = Column(Text)

    __table_args__ = (
        Index('ix_notification_alert_id', 'alert_id'),
        Index('ix_notification_created_at', 'created_at'),
        Index('ix_notification_status', 'status'),
    )


class SystemAlert(Base):
    """시스템 알림"""
    __tablename__ = 'system_alerts'

    id = Column(Integer, primary_key=True)
    alert_type = Column(String(50), nullable=False)
    level = Column(String(20), nullable=False)  # info, warning, error, critical
    title = Column(String(200))
    message = Column(Text)
    source = Column(String(100))  # 발생 소스
    is_resolved = Column(Integer, default=0)
    resolved_at = Column(DateTime)
    resolution_note = Column(Text)
    created_at = Column(DateTime, default=datetime.now)

    __table_args__ = (
        Index('ix_system_alert_type', 'alert_type'),
        Index('ix_system_alert_level', 'level'),
        Index('ix_system_alert_created_at', 'created_at'),
    )


class PerformanceTracking(Base):
    """성과 추적"""
    __tablename__ = 'performance_tracking'

    id = Column(Integer, primary_key=True)
    tracking_date = Column(Date, nullable=False)
    stock_code = Column(String(20))

    # 일일 성과
    daily_return = Column(Float)
    cumulative_return = Column(Float)
    win_rate = Column(Float)
    trade_count = Column(Integer)

    # 리스크 메트릭
    max_drawdown = Column(Float)
    sharpe_ratio = Column(Float)
    volatility = Column(Float)

    created_at = Column(DateTime, default=datetime.now)

    __table_args__ = (
        Index('ix_perf_tracking_date', 'tracking_date'),
    )


class AccuracyTracking(Base):
    """정확도 추적"""
    __tablename__ = 'accuracy_tracking'

    id = Column(Integer, primary_key=True)
    tracking_date = Column(Date, nullable=False)
    model_name = Column(String(50))
    prediction_type = Column(String(50))  # screening, selection

    # 정확도 메트릭
    total_predictions = Column(Integer)
    correct_predictions = Column(Integer)
    accuracy = Column(Float)
    precision_score = Column(Float)
    recall_score = Column(Float)
    f1_score = Column(Float)

    created_at = Column(DateTime, default=datetime.now)

    __table_args__ = (
        Index('ix_accuracy_tracking_date', 'tracking_date'),
        Index('ix_accuracy_model_name', 'model_name'),
    )
