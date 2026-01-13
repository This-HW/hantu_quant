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


class StockFundamental(Base):
    """종목 재무 데이터 (pykrx에서 수집)"""
    __tablename__ = 'stock_fundamentals'

    id = Column(Integer, primary_key=True)
    stock_code = Column(String(20), nullable=False)
    date = Column(Date, nullable=False)  # 데이터 기준일

    # 재무 지표
    per = Column(Float)  # 주가수익비율
    pbr = Column(Float)  # 주가순자산비율
    eps = Column(Float)  # 주당순이익
    bps = Column(Float)  # 주당순자산
    div = Column(Float)  # 배당수익률
    dps = Column(Float)  # 주당배당금
    roe = Column(Float)  # 자기자본이익률 (계산값)

    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        Index('ix_fundamental_stock_code', 'stock_code'),
        Index('ix_fundamental_date', 'date'),
        Index('ix_fundamental_stock_date', 'stock_code', 'date', unique=True),
    )

    def __repr__(self):
        return f"<StockFundamental(code='{self.stock_code}', date={self.date}, per={self.per})>"

    def to_dict(self):
        return {
            'stock_code': self.stock_code,
            'date': self.date.isoformat() if self.date else None,
            'per': self.per,
            'pbr': self.pbr,
            'eps': self.eps,
            'bps': self.bps,
            'div': self.div,
            'dps': self.dps,
            'roe': self.roe,
        }


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


# ============================================================
# Feature 3: SQLAlchemy 모델 확장 (F-PG-003)
# PostgreSQL 마이그레이션용 신규 모델
# ============================================================

class APICall(Base):
    """API 호출 추적 (T-015)"""
    __tablename__ = 'api_calls'

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.now)
    endpoint = Column(String(200), nullable=False)
    method = Column(String(10), nullable=False)  # GET, POST, PUT, DELETE
    response_time = Column(Float, nullable=False)  # milliseconds
    request_size = Column(Integer)  # bytes
    response_size = Column(Integer)  # bytes
    status_code = Column(Integer)
    success = Column(Integer)  # Boolean: 1=success, 0=failure
    error_message = Column(Text)
    user_agent = Column(String(200))
    ip_address = Column(String(50))
    session_id = Column(String(100))

    __table_args__ = (
        Index('ix_api_calls_timestamp', 'timestamp'),
        Index('ix_api_calls_endpoint', 'endpoint'),
        Index('ix_api_calls_success', 'success'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'endpoint': self.endpoint,
            'method': self.method,
            'response_time': self.response_time,
            'status_code': self.status_code,
            'success': bool(self.success) if self.success is not None else None,
            'error_message': self.error_message,
        }


class ErrorEvent(Base):
    """에러 이벤트 (T-016)"""
    __tablename__ = 'error_events'

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.now)
    error_type = Column(String(100), nullable=False)
    severity = Column(String(20), nullable=False)  # low, medium, high, critical
    component = Column(String(100), nullable=False)
    message = Column(Text, nullable=False)
    stack_trace = Column(Text)
    system_metrics = Column(Text)  # JSON
    affected_users = Column(Integer)
    recovery_attempted = Column(Integer)  # Boolean
    recovery_action = Column(String(200))
    recovery_success = Column(Integer)  # Boolean
    recovery_time = Column(Float)  # seconds
    created_at = Column(DateTime, default=datetime.now)

    __table_args__ = (
        Index('ix_error_events_timestamp', 'timestamp'),
        Index('ix_error_events_error_type', 'error_type'),
        Index('ix_error_events_severity', 'severity'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'error_type': self.error_type,
            'severity': self.severity,
            'component': self.component,
            'message': self.message,
            'recovery_attempted': bool(self.recovery_attempted) if self.recovery_attempted is not None else None,
            'recovery_success': bool(self.recovery_success) if self.recovery_success is not None else None,
            'recovery_time': self.recovery_time,
        }


class RecoveryRule(Base):
    """복구 규칙 (T-017)"""
    __tablename__ = 'recovery_rules'

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    error_pattern = Column(Text, nullable=False)  # Regex pattern
    severity_threshold = Column(String(20), nullable=False)  # low, medium, high, critical
    recovery_actions = Column(Text, nullable=False)  # JSON array
    max_attempts = Column(Integer, default=3)
    cooldown_seconds = Column(Integer, default=300)
    conditions = Column(Text)  # JSON
    enabled = Column(Integer, default=1)  # Boolean
    created_at = Column(DateTime, default=datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'error_pattern': self.error_pattern,
            'severity_threshold': self.severity_threshold,
            'recovery_actions': self.recovery_actions,
            'max_attempts': self.max_attempts,
            'cooldown_seconds': self.cooldown_seconds,
            'enabled': bool(self.enabled) if self.enabled is not None else True,
        }


class StrategyPerformance(Base):
    """전략 성과 (T-018)"""
    __tablename__ = 'strategy_performance'

    id = Column(Integer, primary_key=True)
    strategy_name = Column(String(100), nullable=False)
    date = Column(Date, nullable=False)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)

    # 수익률 지표
    total_return = Column(Float)
    annualized_return = Column(Float)
    volatility = Column(Float)
    sharpe_ratio = Column(Float)
    max_drawdown = Column(Float)

    # 거래 통계
    win_rate = Column(Float)
    avg_win = Column(Float)
    avg_loss = Column(Float)
    profit_factor = Column(Float)
    total_trades = Column(Integer)
    profitable_trades = Column(Integer)
    losing_trades = Column(Integer)

    # 리스크 조정 지표
    calmar_ratio = Column(Float)
    sortino_ratio = Column(Float)
    market_correlation = Column(Float)
    alpha = Column(Float)
    beta = Column(Float)
    information_ratio = Column(Float)

    # JSON 필드
    monthly_returns = Column(Text)  # JSON
    quarterly_returns = Column(Text)  # JSON

    created_at = Column(DateTime, default=datetime.now)

    __table_args__ = (
        Index('ix_strategy_perf_name', 'strategy_name'),
        Index('ix_strategy_perf_date', 'date'),
        Index('ix_strategy_perf_unique', 'strategy_name', 'date', 'period_start', 'period_end', unique=True),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'strategy_name': self.strategy_name,
            'date': self.date.isoformat() if self.date else None,
            'period_start': self.period_start.isoformat() if self.period_start else None,
            'period_end': self.period_end.isoformat() if self.period_end else None,
            'total_return': self.total_return,
            'annualized_return': self.annualized_return,
            'sharpe_ratio': self.sharpe_ratio,
            'max_drawdown': self.max_drawdown,
            'win_rate': self.win_rate,
            'profit_factor': self.profit_factor,
            'alpha': self.alpha,
            'beta': self.beta,
            'monthly_returns': self.monthly_returns,
            'quarterly_returns': self.quarterly_returns,
        }


class MarketRegime(Base):
    """시장 체제 (T-019)"""
    __tablename__ = 'market_regimes'

    id = Column(Integer, primary_key=True)
    date = Column(Date, unique=True, nullable=False)
    regime_type = Column(String(20), nullable=False)  # bull, bear, sideways
    market_return = Column(Float)
    volatility = Column(Float)
    confidence = Column(Float)  # 0-1
    created_at = Column(DateTime, default=datetime.now)

    __table_args__ = (
        Index('ix_market_regime_date', 'date'),
        Index('ix_market_regime_type', 'regime_type'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'date': self.date.isoformat() if self.date else None,
            'regime_type': self.regime_type,
            'market_return': self.market_return,
            'volatility': self.volatility,
            'confidence': self.confidence,
        }


class BacktestPrediction(Base):
    """백테스트 예측 (T-020)"""
    __tablename__ = 'backtest_predictions'

    id = Column(Integer, primary_key=True)
    prediction_id = Column(String(100), unique=True, nullable=False)
    strategy_name = Column(String(100), nullable=False)
    prediction_date = Column(Date, nullable=False)

    # 타겟 정보 (JSON)
    target_stocks = Column(Text, nullable=False)  # JSON array
    predicted_returns = Column(Text, nullable=False)  # JSON dict
    predicted_weights = Column(Text, nullable=False)  # JSON dict

    # 예측 메트릭
    expected_return = Column(Float)
    expected_volatility = Column(Float)
    expected_sharpe_ratio = Column(Float)
    expected_max_drawdown = Column(Float)
    model_confidence = Column(Float)  # 0-1

    # 메타 정보 (JSON)
    feature_importance = Column(Text)  # JSON
    market_conditions = Column(Text)  # JSON

    created_at = Column(DateTime, default=datetime.now)

    # 관계 설정
    actual_performances = relationship('ActualPerformance', back_populates='backtest_prediction')
    performance_comparisons = relationship('PerformanceComparison', back_populates='backtest_prediction')

    __table_args__ = (
        Index('ix_backtest_pred_id', 'prediction_id'),
        Index('ix_backtest_pred_strategy', 'strategy_name'),
        Index('ix_backtest_pred_date', 'prediction_date'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'prediction_id': self.prediction_id,
            'strategy_name': self.strategy_name,
            'prediction_date': self.prediction_date.isoformat() if self.prediction_date else None,
            'target_stocks': self.target_stocks,
            'predicted_returns': self.predicted_returns,
            'predicted_weights': self.predicted_weights,
            'expected_return': self.expected_return,
            'expected_volatility': self.expected_volatility,
            'expected_sharpe_ratio': self.expected_sharpe_ratio,
            'model_confidence': self.model_confidence,
        }


class ActualPerformance(Base):
    """실제 성과 (T-021)"""
    __tablename__ = 'actual_performance'

    id = Column(Integer, primary_key=True)
    performance_id = Column(String(100), unique=True, nullable=False)
    prediction_id = Column(String(100), ForeignKey('backtest_predictions.prediction_id'), nullable=False)
    execution_date = Column(Date, nullable=False)
    completion_date = Column(Date, nullable=False)

    # 실행 정보 (JSON)
    executed_stocks = Column(Text, nullable=False)  # JSON array
    actual_returns = Column(Text, nullable=False)  # JSON dict
    actual_weights = Column(Text, nullable=False)  # JSON dict

    # 실제 메트릭
    actual_return = Column(Float)
    actual_volatility = Column(Float)
    actual_sharpe_ratio = Column(Float)
    actual_max_drawdown = Column(Float)

    # 실행 비용
    execution_costs = Column(Float)
    slippage = Column(Float)
    market_impact = Column(Float)

    # 상태
    status = Column(String(20), nullable=False)  # predicted, executed, completed, cancelled, error

    created_at = Column(DateTime, default=datetime.now)

    # 관계 설정
    backtest_prediction = relationship('BacktestPrediction', back_populates='actual_performances')

    __table_args__ = (
        Index('ix_actual_perf_id', 'performance_id'),
        Index('ix_actual_perf_pred_id', 'prediction_id'),
        Index('ix_actual_perf_status', 'status'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'performance_id': self.performance_id,
            'prediction_id': self.prediction_id,
            'execution_date': self.execution_date.isoformat() if self.execution_date else None,
            'completion_date': self.completion_date.isoformat() if self.completion_date else None,
            'executed_stocks': self.executed_stocks,
            'actual_returns': self.actual_returns,
            'actual_return': self.actual_return,
            'actual_volatility': self.actual_volatility,
            'actual_sharpe_ratio': self.actual_sharpe_ratio,
            'status': self.status,
        }


class PerformanceComparison(Base):
    """성과 비교 (BacktestPrediction 관련)"""
    __tablename__ = 'performance_comparisons'

    id = Column(Integer, primary_key=True)
    comparison_id = Column(String(100), unique=True, nullable=False)
    prediction_id = Column(String(100), ForeignKey('backtest_predictions.prediction_id'), nullable=False)
    comparison_date = Column(Date, nullable=False)

    # 차이 분석
    return_difference = Column(Float)
    volatility_difference = Column(Float)
    sharpe_difference = Column(Float)

    # 정확도 분석
    prediction_accuracy = Column(Float)
    direction_accuracy = Column(Float)
    magnitude_accuracy = Column(Float)
    mean_absolute_error = Column(Float)
    root_mean_square_error = Column(Float)
    correlation = Column(Float)

    # 분석 결과 (JSON)
    analysis_summary = Column(Text)  # JSON
    improvement_suggestions = Column(Text)  # JSON

    created_at = Column(DateTime, default=datetime.now)

    # 관계 설정
    backtest_prediction = relationship('BacktestPrediction', back_populates='performance_comparisons')

    __table_args__ = (
        Index('ix_perf_comp_id', 'comparison_id'),
        Index('ix_perf_comp_pred_id', 'prediction_id'),
    )


class DailyStrategyReturn(Base):
    """일별 전략 수익률"""
    __tablename__ = 'daily_strategy_returns'

    id = Column(Integer, primary_key=True)
    strategy_name = Column(String(100), nullable=False)
    date = Column(Date, nullable=False)
    daily_return = Column(Float)
    cumulative_return = Column(Float)
    portfolio_value = Column(Float)
    benchmark_return = Column(Float)
    active_return = Column(Float)  # strategy - benchmark
    created_at = Column(DateTime, default=datetime.now)

    __table_args__ = (
        Index('ix_daily_return_strategy', 'strategy_name'),
        Index('ix_daily_return_date', 'date'),
        Index('ix_daily_return_unique', 'strategy_name', 'date', unique=True),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'strategy_name': self.strategy_name,
            'date': self.date.isoformat() if self.date else None,
            'daily_return': self.daily_return,
            'cumulative_return': self.cumulative_return,
            'portfolio_value': self.portfolio_value,
            'benchmark_return': self.benchmark_return,
            'active_return': self.active_return,
        }


class StrategyComparison(Base):
    """전략 비교"""
    __tablename__ = 'strategy_comparisons'

    id = Column(Integer, primary_key=True)
    comparison_date = Column(Date, nullable=False)
    period_days = Column(Integer)

    # 비교 결과 (JSON)
    strategies = Column(Text)  # JSON array
    best_performer = Column(String(100))
    worst_performer = Column(String(100))
    performance_spread = Column(Float)
    risk_adjusted_ranking = Column(Text)  # JSON
    correlation_matrix = Column(Text)  # JSON
    statistical_significance = Column(Text)  # JSON

    # 시장 체제별 성과 (JSON)
    bull_market_performance = Column(Text)  # JSON
    bear_market_performance = Column(Text)  # JSON
    sideways_market_performance = Column(Text)  # JSON

    created_at = Column(DateTime, default=datetime.now)

    __table_args__ = (
        Index('ix_strategy_comp_date', 'comparison_date'),
    )


class ModelBaseline(Base):
    """모델 베이스라인"""
    __tablename__ = 'model_baselines'

    id = Column(Integer, primary_key=True)
    model_name = Column(String(100), nullable=False)
    baseline_date = Column(Date, nullable=False)
    accuracy = Column(Float)
    precision_score = Column(Float)
    recall_score = Column(Float)
    f1_score = Column(Float)
    auc_score = Column(Float)
    sample_count = Column(Integer)
    created_at = Column(DateTime, default=datetime.now)

    __table_args__ = (
        Index('ix_model_baseline_name', 'model_name'),
        Index('ix_model_baseline_date', 'baseline_date'),
    )


class PerformanceAlert(Base):
    """성과 알림"""
    __tablename__ = 'performance_alerts'

    id = Column(Integer, primary_key=True)
    model_name = Column(String(100), nullable=False)
    alert_type = Column(String(50), nullable=False)  # accuracy_drop, drift_detected, etc.
    severity = Column(String(20), nullable=False)  # info, warning, error, critical
    message = Column(Text, nullable=False)
    metric_name = Column(String(50))
    current_value = Column(Float)
    baseline_value = Column(Float)
    threshold = Column(Float)
    is_resolved = Column(Integer, default=0)  # Boolean
    resolved_at = Column(DateTime)
    resolution_note = Column(Text)
    created_at = Column(DateTime, default=datetime.now)

    __table_args__ = (
        Index('ix_perf_alert_model', 'model_name'),
        Index('ix_perf_alert_type', 'alert_type'),
        Index('ix_perf_alert_created', 'created_at'),
    )


class NotificationStats(Base):
    """알림 통계"""
    __tablename__ = 'notification_stats'

    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False)
    channel = Column(String(20), nullable=False)  # telegram, email
    total_sent = Column(Integer, default=0)
    total_failed = Column(Integer, default=0)
    total_filtered = Column(Integer, default=0)
    avg_send_time = Column(Float)  # milliseconds
    last_updated = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        Index('ix_notif_stats_date', 'date'),
        Index('ix_notif_stats_unique', 'date', 'channel', unique=True),
    )


class AlertSettings(Base):
    """알림 설정"""
    __tablename__ = 'alert_settings'

    id = Column(Integer, primary_key=True)
    alert_type = Column(String(50), unique=True, nullable=False)
    enabled = Column(Integer, default=1)  # Boolean
    min_level = Column(String(20), default='info')  # info, warning, error, critical
    channels = Column(Text)  # JSON array: ["telegram", "email"]
    cooldown_seconds = Column(Integer, default=300)
    max_per_hour = Column(Integer, default=10)
    template = Column(Text)  # 메시지 템플릿
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class AlertStatistics(Base):
    """알림 통계 (집계)"""
    __tablename__ = 'alert_statistics'

    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False)
    alert_type = Column(String(50), nullable=False)
    level = Column(String(20), nullable=False)
    total_count = Column(Integer, default=0)
    resolved_count = Column(Integer, default=0)
    avg_resolution_time = Column(Float)  # seconds
    last_updated = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        Index('ix_alert_stats_date', 'date'),
        Index('ix_alert_stats_type', 'alert_type'),
        Index('ix_alert_stats_unique', 'date', 'alert_type', 'level', unique=True),
    )


class ScreeningHistory(Base):
    """스크리닝 이력 (DataSynchronizer용)"""
    __tablename__ = 'screening_history'

    id = Column(Integer, primary_key=True)
    screening_date = Column(Date, nullable=False)
    stock_code = Column(String(20), nullable=False)
    stock_name = Column(String(100))
    total_score = Column(Float)
    fundamental_score = Column(Float)
    technical_score = Column(Float)
    momentum_score = Column(Float)
    passed = Column(Integer, default=0)  # Boolean
    reason = Column(Text)
    created_at = Column(DateTime, default=datetime.now)

    __table_args__ = (
        Index('ix_screening_hist_date', 'screening_date'),
        Index('ix_screening_hist_stock', 'stock_code'),
        Index('ix_screening_hist_unique', 'screening_date', 'stock_code', unique=True),
    )


class SelectionHistory(Base):
    """선정 이력 (DataSynchronizer용)"""
    __tablename__ = 'selection_history'

    id = Column(Integer, primary_key=True)
    selection_date = Column(Date, nullable=False)
    stock_code = Column(String(20), nullable=False)
    stock_name = Column(String(100))
    total_score = Column(Float)
    technical_score = Column(Float)
    volume_score = Column(Float)
    pattern_score = Column(Float)
    entry_price = Column(Float)
    target_price = Column(Float)
    stop_loss = Column(Float)
    expected_return = Column(Float)
    signal = Column(String(20))  # buy, sell, hold
    confidence = Column(Float)
    actual_return_7d = Column(Float)
    is_success = Column(Integer)  # Boolean
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        Index('ix_selection_hist_date', 'selection_date'),
        Index('ix_selection_hist_stock', 'stock_code'),
        Index('ix_selection_hist_unique', 'selection_date', 'stock_code', unique=True),
    )


class LearningMetrics(Base):
    """학습 메트릭 (DataSynchronizer용)"""
    __tablename__ = 'learning_metrics'

    id = Column(Integer, primary_key=True)
    metric_date = Column(Date, nullable=False)
    metric_type = Column(String(50), nullable=False)  # screening_accuracy, selection_accuracy, etc.
    model_name = Column(String(100))
    value = Column(Float)
    sample_count = Column(Integer)
    details = Column(Text)  # JSON
    created_at = Column(DateTime, default=datetime.now)

    __table_args__ = (
        Index('ix_learning_metrics_date', 'metric_date'),
        Index('ix_learning_metrics_type', 'metric_type'),
    )


class DailyTracking(Base):
    """일별 추적 (PerformanceTracker용)"""
    __tablename__ = 'daily_tracking'

    id = Column(Integer, primary_key=True)
    tracking_date = Column(Date, nullable=False)
    strategy_name = Column(String(100))
    predicted_return = Column(Float)
    actual_return = Column(Float)
    prediction_error = Column(Float)
    direction_correct = Column(Integer)  # Boolean
    stocks_traded = Column(Text)  # JSON array
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.now)

    __table_args__ = (
        Index('ix_daily_tracking_date', 'tracking_date'),
        Index('ix_daily_tracking_unique', 'tracking_date', 'strategy_name', unique=True),
    )


class DailyAccuracy(Base):
    """일별 정확도 (AccuracyTracker용)"""
    __tablename__ = 'daily_accuracy'

    id = Column(Integer, primary_key=True)
    accuracy_date = Column(Date, nullable=False)
    model_name = Column(String(100))
    prediction_type = Column(String(50))  # screening, selection
    total_predictions = Column(Integer)
    correct_predictions = Column(Integer)
    accuracy = Column(Float)
    precision_score = Column(Float)
    recall_score = Column(Float)
    f1_score = Column(Float)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.now)

    __table_args__ = (
        Index('ix_daily_accuracy_date', 'accuracy_date'),
        Index('ix_daily_accuracy_model', 'model_name'),
        Index('ix_daily_accuracy_unique', 'accuracy_date', 'model_name', 'prediction_type', unique=True),
    )


class ModelPerformance(Base):
    """모델 성과 (ModelPerformanceMonitor용)"""
    __tablename__ = 'model_performance'

    id = Column(Integer, primary_key=True)
    model_name = Column(String(100), nullable=False)
    evaluation_date = Column(Date, nullable=False)
    accuracy = Column(Float)
    precision_score = Column(Float)
    recall_score = Column(Float)
    f1_score = Column(Float)
    auc_score = Column(Float)
    sample_count = Column(Integer)
    metrics_json = Column(Text)  # JSON with additional metrics
    created_at = Column(DateTime, default=datetime.now)

    __table_args__ = (
        Index('ix_model_perf_name', 'model_name'),
        Index('ix_model_perf_date', 'evaluation_date'),
    )
