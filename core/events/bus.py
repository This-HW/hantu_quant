"""
이벤트 버스 구현

이 모듈은 이벤트 시스템의 핵심인 이벤트 버스를 구현합니다.
"""

import asyncio
import logging
import uuid
from typing import Dict, List, Optional, Set, Any
from collections import defaultdict, deque
from datetime import datetime
import threading

from ..interfaces.events import IEventBus, IEventHandler, IEvent, EventType
from .types import EventPriority, is_high_priority, is_critical_priority

logger = logging.getLogger(__name__)


class EventBus(IEventBus):
    """이벤트 버스 구현"""
    
    def __init__(self, 
                 max_queue_size: int = 1000,
                 max_workers: int = 10,
                 enable_persistence: bool = False):
        """
        이벤트 버스 초기화
        
        Args:
            max_queue_size: 최대 큐 크기
            max_workers: 최대 워커 수
            enable_persistence: 이벤트 영속성 활성화 여부
        """
        self._v_subscribers: Dict[EventType, Set[IEventHandler]] = defaultdict(set)
        self._v_event_queue: deque = deque(maxlen=max_queue_size)
        self._v_high_priority_queue: deque = deque(maxlen=max_queue_size)
        self._v_critical_priority_queue: deque = deque(maxlen=max_queue_size)
        
        self._v_max_workers = max_workers
        self._v_enable_persistence = enable_persistence
        self._v_is_running = False
        self._v_worker_tasks: List[asyncio.Task] = []
        self._v_lock = threading.RLock()
        
        # 통계
        self._v_published_count = 0
        self._v_processed_count = 0
        self._v_failed_count = 0
        self._v_dropped_count = 0
        self._v_processing_times: List[float] = []
        
        # 이벤트 저장소 (간단한 메모리 저장소)
        self._v_event_store: Dict[str, IEvent] = {}
        self._v_event_history: deque = deque(maxlen=10000)
    
    def subscribe(self, event_type: EventType, handler: IEventHandler) -> bool:
        """이벤트 구독"""
        with self._v_lock:
            if event_type not in handler.get_supported_events():
                logger.warning(f"Handler '{handler.get_handler_name()}' does not support event type '{event_type}'")
                return False
            
            self._v_subscribers[event_type].add(handler)
            logger.info(f"Handler '{handler.get_handler_name()}' subscribed to event type '{event_type}'")
            return True
    
    def unsubscribe(self, event_type: EventType, handler: IEventHandler) -> bool:
        """이벤트 구독 해제"""
        with self._v_lock:
            if event_type in self._v_subscribers:
                self._v_subscribers[event_type].discard(handler)
                logger.info(f"Handler '{handler.get_handler_name()}' unsubscribed from event type '{event_type}'")
                return True
            return False
    
    async def publish(self, event: IEvent) -> bool:
        """이벤트 발행"""
        if not self._v_is_running:
            logger.warning("EventBus is not running. Event will be queued.")
        
        # 이벤트 유효성 검증
        if not event.validate():
            logger.error(f"Invalid event: {event}")
            return False
        
        # 이벤트 ID 생성 (없는 경우)
        if not event.event_id:
            event.event_id = str(uuid.uuid4())
        
        # 이벤트 저장 (영속성 활성화된 경우)
        if self._v_enable_persistence:
            self._v_event_store[event.event_id] = event
        
        # 이벤트 히스토리 추가
        self._v_event_history.append(event)
        
        # 우선순위별 큐에 추가
        if is_critical_priority(event.priority):
            if len(self._v_critical_priority_queue) >= self._v_critical_priority_queue.maxlen:
                self._v_dropped_count += 1
                logger.warning(f"Critical priority queue is full. Dropping event: {event.event_id}")
                return False
            self._v_critical_priority_queue.append(event)
        elif is_high_priority(event.priority):
            if len(self._v_high_priority_queue) >= self._v_high_priority_queue.maxlen:
                self._v_dropped_count += 1
                logger.warning(f"High priority queue is full. Dropping event: {event.event_id}")
                return False
            self._v_high_priority_queue.append(event)
        else:
            if len(self._v_event_queue) >= self._v_event_queue.maxlen:
                self._v_dropped_count += 1
                logger.warning(f"Event queue is full. Dropping event: {event.event_id}")
                return False
            self._v_event_queue.append(event)
        
        self._v_published_count += 1
        logger.debug(f"Event published: {event.event_id} (type: {event.event_type.value})")
        return True
    
    def get_subscribers(self, event_type: EventType) -> List[IEventHandler]:
        """이벤트 구독자 목록 조회"""
        with self._v_lock:
            return list(self._v_subscribers.get(event_type, set()))
    
    def get_all_subscriptions(self) -> Dict[EventType, List[IEventHandler]]:
        """모든 구독 정보 조회"""
        with self._v_lock:
            return {
                event_type: list(handlers)
                for event_type, handlers in self._v_subscribers.items()
            }
    
    async def start(self) -> bool:
        """이벤트 버스 시작"""
        if self._v_is_running:
            logger.warning("EventBus is already running")
            return False
        
        self._v_is_running = True
        
        # 워커 태스크 시작
        for i in range(self._v_max_workers):
            _v_worker_task = asyncio.create_task(self._worker_loop(f"worker-{i}"))
            self._v_worker_tasks.append(_v_worker_task)
        
        logger.info(f"EventBus started with {self._v_max_workers} workers")
        return True
    
    async def stop(self) -> bool:
        """이벤트 버스 중지"""
        if not self._v_is_running:
            logger.warning("EventBus is not running")
            return False
        
        self._v_is_running = False
        
        # 워커 태스크 중지
        for task in self._v_worker_tasks:
            task.cancel()
        
        # 남은 태스크 정리
        if self._v_worker_tasks:
            await asyncio.gather(*self._v_worker_tasks, return_exceptions=True)
        
        self._v_worker_tasks.clear()
        
        logger.info("EventBus stopped")
        return True
    
    def is_running(self) -> bool:
        """이벤트 버스 실행 상태 확인"""
        return self._v_is_running
    
    async def _worker_loop(self, worker_name: str):
        """워커 루프"""
        logger.info(f"EventBus worker '{worker_name}' started")
        
        while self._v_is_running:
            try:
                # 이벤트 가져오기 (우선순위 순서)
                _v_event = await self._get_next_event()
                
                if _v_event:
                    await self._process_event(_v_event)
                else:
                    # 이벤트가 없으면 잠시 대기
                    await asyncio.sleep(0.1)
                    
            except asyncio.CancelledError:
                logger.info(f"EventBus worker '{worker_name}' cancelled")
                break
            except Exception as e:
                logger.error(f"EventBus worker '{worker_name}' error: {str(e)}")
                await asyncio.sleep(1)  # 오류 발생 시 잠시 대기
        
        logger.info(f"EventBus worker '{worker_name}' stopped")
    
    async def _get_next_event(self) -> Optional[IEvent]:
        """다음 이벤트 가져오기 (우선순위 순서)"""
        # 중요 우선순위 큐에서 먼저 가져오기
        if self._v_critical_priority_queue:
            return self._v_critical_priority_queue.popleft()
        
        # 높은 우선순위 큐에서 가져오기
        if self._v_high_priority_queue:
            return self._v_high_priority_queue.popleft()
        
        # 일반 우선순위 큐에서 가져오기
        if self._v_event_queue:
            return self._v_event_queue.popleft()
        
        return None
    
    async def _process_event(self, event: IEvent):
        """이벤트 처리"""
        _v_start_time = asyncio.get_event_loop().time()
        
        try:
            # 구독자 찾기
            _v_handlers = self.get_subscribers(event.event_type)
            
            if not _v_handlers:
                logger.debug(f"No handlers for event type: {event.event_type.value}")
                return
            
            # 모든 핸들러에 이벤트 전달
            _v_tasks = []
            for handler in _v_handlers:
                if handler.is_enabled():
                    _v_task = asyncio.create_task(handler.process_event(event))
                    _v_tasks.append(_v_task)
            
            # 모든 핸들러 처리 완료 대기
            if _v_tasks:
                _v_results = await asyncio.gather(*_v_tasks, return_exceptions=True)
                
                # 결과 처리
                _v_success_count = 0
                for result in _v_results:
                    if isinstance(result, Exception):
                        logger.error(f"Handler failed: {str(result)}")
                        self._v_failed_count += 1
                    elif result:
                        _v_success_count += 1
                
                if _v_success_count > 0:
                    self._v_processed_count += 1
                
                logger.debug(f"Event processed: {event.event_id} ({_v_success_count}/{len(_v_tasks)} handlers succeeded)")
            
        except Exception as e:
            logger.error(f"Failed to process event {event.event_id}: {str(e)}")
            self._v_failed_count += 1
        
        finally:
            # 처리 시간 기록
            _v_processing_time = asyncio.get_event_loop().time() - _v_start_time
            self._v_processing_times.append(_v_processing_time)
            
            # 최근 1000개의 처리 시간만 유지
            if len(self._v_processing_times) > 1000:
                self._v_processing_times.pop(0)
    
    def get_event_stats(self) -> Dict[str, Any]:
        """이벤트 통계 조회"""
        _v_avg_processing_time = 0
        if self._v_processing_times:
            _v_avg_processing_time = sum(self._v_processing_times) / len(self._v_processing_times)
        
        return {
            'is_running': self._v_is_running,
            'published_count': self._v_published_count,
            'processed_count': self._v_processed_count,
            'failed_count': self._v_failed_count,
            'dropped_count': self._v_dropped_count,
            'success_rate': (self._v_processed_count / max(1, self._v_published_count)) * 100,
            'avg_processing_time': _v_avg_processing_time,
            'queue_sizes': {
                'normal': len(self._v_event_queue),
                'high': len(self._v_high_priority_queue),
                'critical': len(self._v_critical_priority_queue)
            },
            'total_subscribers': sum(len(handlers) for handlers in self._v_subscribers.values()),
            'active_workers': len(self._v_worker_tasks)
        }
    
    def get_event_history(self, limit: int = 100) -> List[IEvent]:
        """이벤트 히스토리 조회"""
        return list(self._v_event_history)[-limit:]
    
    def get_stored_event(self, event_id: str) -> Optional[IEvent]:
        """저장된 이벤트 조회"""
        return self._v_event_store.get(event_id)
    
    def clear_event_store(self):
        """이벤트 저장소 정리"""
        self._v_event_store.clear()
        self._v_event_history.clear()
    
    def reset_stats(self):
        """통계 초기화"""
        self._v_published_count = 0
        self._v_processed_count = 0
        self._v_failed_count = 0
        self._v_dropped_count = 0
        self._v_processing_times.clear()
    
    def subscribe_multiple(self, event_types: List[EventType], handler: IEventHandler) -> Dict[EventType, bool]:
        """여러 이벤트 타입에 구독"""
        _v_results = {}
        for event_type in event_types:
            _v_results[event_type] = self.subscribe(event_type, handler)
        return _v_results
    
    def unsubscribe_all(self, handler: IEventHandler) -> int:
        """핸들러의 모든 구독 해제"""
        _v_unsubscribed_count = 0
        
        with self._v_lock:
            for event_type, handlers in self._v_subscribers.items():
                if handler in handlers:
                    handlers.discard(handler)
                    _v_unsubscribed_count += 1
        
        logger.info(f"Handler '{handler.get_handler_name()}' unsubscribed from {_v_unsubscribed_count} event types")
        return _v_unsubscribed_count
    
    def get_queue_status(self) -> Dict[str, Any]:
        """큐 상태 조회"""
        return {
            'normal_queue': {
                'size': len(self._v_event_queue),
                'max_size': self._v_event_queue.maxlen,
                'utilization': len(self._v_event_queue) / self._v_event_queue.maxlen * 100
            },
            'high_priority_queue': {
                'size': len(self._v_high_priority_queue),
                'max_size': self._v_high_priority_queue.maxlen,
                'utilization': len(self._v_high_priority_queue) / self._v_high_priority_queue.maxlen * 100
            },
            'critical_priority_queue': {
                'size': len(self._v_critical_priority_queue),
                'max_size': self._v_critical_priority_queue.maxlen,
                'utilization': len(self._v_critical_priority_queue) / self._v_critical_priority_queue.maxlen * 100
            }
        }
    
    def __str__(self) -> str:
        return f"EventBus(running={self._v_is_running}, subscribers={len(self._v_subscribers)})"
    
    def __repr__(self) -> str:
        return self.__str__() 