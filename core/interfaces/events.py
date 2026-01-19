"""
이벤트 관련 인터페이스 정의

이 모듈은 이벤트 기반 통신을 위한 인터페이스들을 정의합니다.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class EventType(Enum):
    """이벤트 타입"""
    MARKET_OPEN = "MARKET_OPEN"
    MARKET_CLOSE = "MARKET_CLOSE"
    PRICE_UPDATE = "PRICE_UPDATE"
    ORDER_FILLED = "ORDER_FILLED"
    ORDER_CANCELLED = "ORDER_CANCELLED"
    POSITION_OPENED = "POSITION_OPENED"
    POSITION_CLOSED = "POSITION_CLOSED"
    SIGNAL_GENERATED = "SIGNAL_GENERATED"
    RISK_ALERT = "RISK_ALERT"
    SYSTEM_ERROR = "SYSTEM_ERROR"
    DATA_UPDATED = "DATA_UPDATED"
    STRATEGY_STARTED = "STRATEGY_STARTED"
    STRATEGY_STOPPED = "STRATEGY_STOPPED"


class EventPriority(Enum):
    """이벤트 우선순위"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class IEvent(ABC):
    """이벤트 인터페이스"""
    event_id: str
    event_type: EventType
    timestamp: datetime
    source: str
    priority: EventPriority = EventPriority.NORMAL
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        pass
    
    @abstractmethod
    def validate(self) -> bool:
        """이벤트 유효성 검증"""
        pass


@dataclass
class MarketEvent(IEvent):
    """시장 이벤트"""
    market_status: str = ""
    market_type: str = "KOSPI"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "priority": self.priority.value,
            "market_status": self.market_status,
            "market_type": self.market_type,
            "data": self.data,
            "metadata": self.metadata
        }
    
    def validate(self) -> bool:
        return all([
            self.event_id,
            self.event_type,
            self.timestamp,
            self.source,
            self.market_status
        ])


@dataclass
class PriceEvent(IEvent):
    """가격 이벤트"""
    stock_code: str = ""
    price: float = 0.0
    volume: int = 0
    change_rate: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "priority": self.priority.value,
            "stock_code": self.stock_code,
            "price": self.price,
            "volume": self.volume,
            "change_rate": self.change_rate,
            "data": self.data,
            "metadata": self.metadata
        }
    
    def validate(self) -> bool:
        return all([
            self.event_id,
            self.event_type,
            self.timestamp,
            self.source,
            self.stock_code,
            self.price >= 0
        ])


@dataclass
class OrderEvent(IEvent):
    """주문 이벤트"""
    order_id: str = ""
    stock_code: str = ""
    order_type: str = ""
    quantity: int = 0
    price: float = 0.0
    status: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "priority": self.priority.value,
            "order_id": self.order_id,
            "stock_code": self.stock_code,
            "order_type": self.order_type,
            "quantity": self.quantity,
            "price": self.price,
            "status": self.status,
            "data": self.data,
            "metadata": self.metadata
        }
    
    def validate(self) -> bool:
        return all([
            self.event_id,
            self.event_type,
            self.timestamp,
            self.source,
            self.order_id,
            self.stock_code,
            self.order_type,
            self.quantity > 0
        ])


@dataclass
class SignalEvent(IEvent):
    """신호 이벤트"""
    signal_type: str = ""
    stock_code: str = ""
    strength: float = 0.0
    confidence: float = 0.0
    strategy_name: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "priority": self.priority.value,
            "signal_type": self.signal_type,
            "stock_code": self.stock_code,
            "strength": self.strength,
            "confidence": self.confidence,
            "strategy_name": self.strategy_name,
            "data": self.data,
            "metadata": self.metadata
        }
    
    def validate(self) -> bool:
        return all([
            self.event_id,
            self.event_type,
            self.timestamp,
            self.source,
            self.signal_type,
            self.stock_code,
            0 <= self.strength <= 100,
            0 <= self.confidence <= 1
        ])


class IEventHandler(ABC):
    """이벤트 핸들러 인터페이스"""
    
    @abstractmethod
    def get_supported_events(self) -> List[EventType]:
        """지원하는 이벤트 타입 목록 반환"""
        pass
    
    @abstractmethod
    async def handle_event(self, event: IEvent) -> bool:
        """이벤트 처리"""
        pass
    
    @abstractmethod
    def get_handler_name(self) -> str:
        """핸들러 이름 반환"""
        pass
    
    @abstractmethod
    def is_enabled(self) -> bool:
        """핸들러 활성화 여부"""
        pass
    
    @abstractmethod
    def enable(self) -> bool:
        """핸들러 활성화"""
        pass
    
    @abstractmethod
    def disable(self) -> bool:
        """핸들러 비활성화"""
        pass


class IEventBus(ABC):
    """이벤트 버스 인터페이스"""
    
    @abstractmethod
    def subscribe(self, event_type: EventType, handler: IEventHandler) -> bool:
        """이벤트 구독"""
        pass
    
    @abstractmethod
    def unsubscribe(self, event_type: EventType, handler: IEventHandler) -> bool:
        """이벤트 구독 해제"""
        pass
    
    @abstractmethod
    async def publish(self, event: IEvent) -> bool:
        """이벤트 발행"""
        pass
    
    @abstractmethod
    def get_subscribers(self, event_type: EventType) -> List[IEventHandler]:
        """이벤트 구독자 목록 조회"""
        pass
    
    @abstractmethod
    def get_all_subscriptions(self) -> Dict[EventType, List[IEventHandler]]:
        """모든 구독 정보 조회"""
        pass
    
    @abstractmethod
    async def start(self) -> bool:
        """이벤트 버스 시작"""
        pass
    
    @abstractmethod
    async def stop(self) -> bool:
        """이벤트 버스 중지"""
        pass
    
    @abstractmethod
    def is_running(self) -> bool:
        """이벤트 버스 실행 상태 확인"""
        pass


class IEventStore(ABC):
    """이벤트 저장소 인터페이스"""
    
    @abstractmethod
    def save_event(self, event: IEvent) -> bool:
        """이벤트 저장"""
        pass
    
    @abstractmethod
    def get_event(self, event_id: str) -> Optional[IEvent]:
        """이벤트 조회"""
        pass
    
    @abstractmethod
    def get_events_by_type(self, event_type: EventType, limit: int = 100) -> List[IEvent]:
        """타입별 이벤트 조회"""
        pass
    
    @abstractmethod
    def get_events_by_time_range(self, start_time: datetime, end_time: datetime) -> List[IEvent]:
        """시간 범위별 이벤트 조회"""
        pass
    
    @abstractmethod
    def get_events_by_source(self, source: str, limit: int = 100) -> List[IEvent]:
        """소스별 이벤트 조회"""
        pass
    
    @abstractmethod
    def delete_old_events(self, retention_days: int) -> int:
        """오래된 이벤트 삭제"""
        pass
    
    @abstractmethod
    def get_event_count(self, event_type: EventType = None) -> int:
        """이벤트 개수 조회"""
        pass


class IEventFilter(ABC):
    """이벤트 필터 인터페이스"""
    
    @abstractmethod
    def should_process(self, event: IEvent) -> bool:
        """이벤트 처리 여부 판단"""
        pass
    
    @abstractmethod
    def get_filter_criteria(self) -> Dict[str, Any]:
        """필터 조건 조회"""
        pass
    
    @abstractmethod
    def set_filter_criteria(self, criteria: Dict[str, Any]) -> bool:
        """필터 조건 설정"""
        pass


class IEventProcessor(ABC):
    """이벤트 처리기 인터페이스"""
    
    @abstractmethod
    async def process_event(self, event: IEvent) -> bool:
        """이벤트 처리"""
        pass
    
    @abstractmethod
    def get_processing_stats(self) -> Dict[str, Any]:
        """처리 통계 조회"""
        pass
    
    @abstractmethod
    def reset_stats(self) -> bool:
        """통계 초기화"""
        pass


class IEventScheduler(ABC):
    """이벤트 스케줄러 인터페이스"""
    
    @abstractmethod
    def schedule_event(self, event: IEvent, delay_seconds: int) -> str:
        """이벤트 스케줄링"""
        pass
    
    @abstractmethod
    def schedule_recurring_event(self, event: IEvent, interval_seconds: int) -> str:
        """반복 이벤트 스케줄링"""
        pass
    
    @abstractmethod
    def cancel_scheduled_event(self, schedule_id: str) -> bool:
        """스케줄된 이벤트 취소"""
        pass
    
    @abstractmethod
    def get_scheduled_events(self) -> List[Dict[str, Any]]:
        """스케줄된 이벤트 목록 조회"""
        pass
    
    @abstractmethod
    async def start_scheduler(self) -> bool:
        """스케줄러 시작"""
        pass
    
    @abstractmethod
    async def stop_scheduler(self) -> bool:
        """스케줄러 중지"""
        pass


class IEventMiddleware(ABC):
    """이벤트 미들웨어 인터페이스"""
    
    @abstractmethod
    async def before_publish(self, event: IEvent) -> IEvent:
        """발행 전 처리"""
        pass
    
    @abstractmethod
    async def after_publish(self, event: IEvent, result: bool) -> None:
        """발행 후 처리"""
        pass
    
    @abstractmethod
    async def before_handle(self, event: IEvent, handler: IEventHandler) -> IEvent:
        """핸들링 전 처리"""
        pass
    
    @abstractmethod
    async def after_handle(self, event: IEvent, handler: IEventHandler, result: bool) -> None:
        """핸들링 후 처리"""
        pass
    
    @abstractmethod
    def get_middleware_name(self) -> str:
        """미들웨어 이름 반환"""
        pass


class IEventValidator(ABC):
    """이벤트 유효성 검증 인터페이스"""
    
    @abstractmethod
    def validate_event(self, event: IEvent) -> Tuple[bool, List[str]]:
        """이벤트 유효성 검증"""
        pass
    
    @abstractmethod
    def get_validation_rules(self, event_type: EventType) -> Dict[str, Any]:
        """유효성 검증 규칙 조회"""
        pass
    
    @abstractmethod
    def set_validation_rules(self, event_type: EventType, rules: Dict[str, Any]) -> bool:
        """유효성 검증 규칙 설정"""
        pass


class IEventMetrics(ABC):
    """이벤트 메트릭 인터페이스"""
    
    @abstractmethod
    def record_event_published(self, event_type: EventType) -> None:
        """발행된 이벤트 기록"""
        pass
    
    @abstractmethod
    def record_event_processed(self, event_type: EventType, processing_time: float) -> None:
        """처리된 이벤트 기록"""
        pass
    
    @abstractmethod
    def record_event_failed(self, event_type: EventType, error: str) -> None:
        """실패한 이벤트 기록"""
        pass
    
    @abstractmethod
    def get_event_metrics(self) -> Dict[str, Any]:
        """이벤트 메트릭 조회"""
        pass
    
    @abstractmethod
    def reset_metrics(self) -> bool:
        """메트릭 초기화"""
        pass 