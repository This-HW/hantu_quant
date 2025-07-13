"""
이벤트 타입과 우선순위 정의

이 모듈은 시스템에서 사용하는 이벤트 타입과 우선순위를 정의합니다.
"""

# 인터페이스에서 정의한 타입들을 재export
from ..interfaces.events import EventType, EventPriority

# 추가 유틸리티 함수들
def get_event_type_name(event_type: EventType) -> str:
    """이벤트 타입 이름 조회"""
    return event_type.value

def get_event_priority_level(priority: EventPriority) -> int:
    """이벤트 우선순위 레벨 조회"""
    return priority.value

def is_high_priority(priority: EventPriority) -> bool:
    """높은 우선순위 여부 확인"""
    return priority.value >= EventPriority.HIGH.value

def is_critical_priority(priority: EventPriority) -> bool:
    """중요 우선순위 여부 확인"""
    return priority == EventPriority.CRITICAL

def get_all_event_types() -> list:
    """모든 이벤트 타입 조회"""
    return [event_type for event_type in EventType]

def get_all_event_priorities() -> list:
    """모든 이벤트 우선순위 조회"""
    return [priority for priority in EventPriority]

def parse_event_type(type_str: str) -> EventType:
    """문자열에서 이벤트 타입 파싱"""
    for event_type in EventType:
        if event_type.value == type_str:
            return event_type
    raise ValueError(f"Unknown event type: {type_str}")

def parse_event_priority(priority_str: str) -> EventPriority:
    """문자열에서 이벤트 우선순위 파싱"""
    for priority in EventPriority:
        if priority.name.lower() == priority_str.lower():
            return priority
    raise ValueError(f"Unknown event priority: {priority_str}")

# 이벤트 타입별 기본 우선순위 매핑
DEFAULT_PRIORITY_MAP = {
    EventType.MARKET_OPEN: EventPriority.HIGH,
    EventType.MARKET_CLOSE: EventPriority.HIGH,
    EventType.PRICE_UPDATE: EventPriority.NORMAL,
    EventType.ORDER_FILLED: EventPriority.HIGH,
    EventType.ORDER_CANCELLED: EventPriority.NORMAL,
    EventType.POSITION_OPENED: EventPriority.HIGH,
    EventType.POSITION_CLOSED: EventPriority.HIGH,
    EventType.SIGNAL_GENERATED: EventPriority.NORMAL,
    EventType.RISK_ALERT: EventPriority.CRITICAL,
    EventType.SYSTEM_ERROR: EventPriority.CRITICAL,
    EventType.DATA_UPDATED: EventPriority.LOW,
    EventType.STRATEGY_STARTED: EventPriority.NORMAL,
    EventType.STRATEGY_STOPPED: EventPriority.NORMAL,
}

def get_default_priority(event_type: EventType) -> EventPriority:
    """이벤트 타입의 기본 우선순위 조회"""
    return DEFAULT_PRIORITY_MAP.get(event_type, EventPriority.NORMAL) 