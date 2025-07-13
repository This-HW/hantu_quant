"""
이벤트 핸들러 기본 클래스

이 모듈은 이벤트 핸들러의 기본 구현을 제공합니다.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from abc import abstractmethod

from ..interfaces.events import IEventHandler, IEvent, EventType
from .types import EventPriority, is_high_priority

logger = logging.getLogger(__name__)


class BaseEventHandler(IEventHandler):
    """이벤트 핸들러 기본 클래스"""
    
    def __init__(self, 
                 handler_name: str,
                 supported_events: List[EventType],
                 enabled: bool = True,
                 priority_filter: Optional[EventPriority] = None):
        """
        이벤트 핸들러 초기화
        
        Args:
            handler_name: 핸들러 이름
            supported_events: 지원하는 이벤트 타입 목록
            enabled: 핸들러 활성화 여부
            priority_filter: 처리할 최소 우선순위 (None이면 모든 우선순위 처리)
        """
        self._v_handler_name = handler_name
        self._v_supported_events = supported_events
        self._v_enabled = enabled
        self._v_priority_filter = priority_filter
        self._v_processed_count = 0
        self._v_failed_count = 0
        self._v_last_error: Optional[Exception] = None
        self._v_processing_times: List[float] = []
    
    def get_supported_events(self) -> List[EventType]:
        """지원하는 이벤트 타입 목록 반환"""
        return self._v_supported_events.copy()
    
    @abstractmethod
    async def handle_event(self, event: IEvent) -> bool:
        """이벤트 처리 - 하위 클래스에서 구현"""
        pass
    
    def get_handler_name(self) -> str:
        """핸들러 이름 반환"""
        return self._v_handler_name
    
    def is_enabled(self) -> bool:
        """핸들러 활성화 여부"""
        return self._v_enabled
    
    def enable(self) -> bool:
        """핸들러 활성화"""
        self._v_enabled = True
        logger.info(f"EventHandler '{self._v_handler_name}' enabled")
        return True
    
    def disable(self) -> bool:
        """핸들러 비활성화"""
        self._v_enabled = False
        logger.info(f"EventHandler '{self._v_handler_name}' disabled")
        return True
    
    def can_handle_event(self, event: IEvent) -> bool:
        """이벤트 처리 가능 여부 확인"""
        if not self._v_enabled:
            return False
        
        # 지원하는 이벤트 타입인지 확인
        if event.event_type not in self._v_supported_events:
            return False
        
        # 우선순위 필터 확인
        if self._v_priority_filter is not None:
            if event.priority.value < self._v_priority_filter.value:
                return False
        
        return True
    
    async def process_event(self, event: IEvent) -> bool:
        """이벤트 처리 (통계 포함)"""
        if not self.can_handle_event(event):
            return False
        
        _v_start_time = asyncio.get_event_loop().time()
        
        try:
            _v_result = await self.handle_event(event)
            self._v_processed_count += 1
            
            # 처리 시간 기록
            _v_processing_time = asyncio.get_event_loop().time() - _v_start_time
            self._v_processing_times.append(_v_processing_time)
            
            # 최근 100개의 처리 시간만 유지
            if len(self._v_processing_times) > 100:
                self._v_processing_times.pop(0)
            
            return _v_result
            
        except Exception as e:
            self._v_failed_count += 1
            self._v_last_error = e
            logger.error(f"EventHandler '{self._v_handler_name}' failed to process event {event.event_id}: {str(e)}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """핸들러 통계 조회"""
        _v_avg_processing_time = 0
        if self._v_processing_times:
            _v_avg_processing_time = sum(self._v_processing_times) / len(self._v_processing_times)
        
        return {
            'handler_name': self._v_handler_name,
            'enabled': self._v_enabled,
            'supported_events': [event.value for event in self._v_supported_events],
            'processed_count': self._v_processed_count,
            'failed_count': self._v_failed_count,
            'success_rate': (self._v_processed_count - self._v_failed_count) / max(1, self._v_processed_count) * 100,
            'avg_processing_time': _v_avg_processing_time,
            'last_error': str(self._v_last_error) if self._v_last_error else None
        }
    
    def reset_stats(self):
        """통계 초기화"""
        self._v_processed_count = 0
        self._v_failed_count = 0
        self._v_last_error = None
        self._v_processing_times.clear()
    
    def __str__(self) -> str:
        return f"EventHandler(name='{self._v_handler_name}', enabled={self._v_enabled})"
    
    def __repr__(self) -> str:
        return self.__str__()


class AsyncEventHandler(BaseEventHandler):
    """비동기 이벤트 핸들러"""
    
    def __init__(self, 
                 handler_name: str,
                 supported_events: List[EventType],
                 handler_func: callable,
                 enabled: bool = True,
                 priority_filter: Optional[EventPriority] = None):
        """
        비동기 이벤트 핸들러 초기화
        
        Args:
            handler_name: 핸들러 이름
            supported_events: 지원하는 이벤트 타입 목록
            handler_func: 실제 이벤트 처리 함수
            enabled: 핸들러 활성화 여부
            priority_filter: 처리할 최소 우선순위
        """
        super().__init__(handler_name, supported_events, enabled, priority_filter)
        self._v_handler_func = handler_func
    
    async def handle_event(self, event: IEvent) -> bool:
        """이벤트 처리"""
        try:
            if asyncio.iscoroutinefunction(self._v_handler_func):
                return await self._v_handler_func(event)
            else:
                return self._v_handler_func(event)
        except Exception as e:
            logger.error(f"Handler function failed: {str(e)}")
            return False


class FilteredEventHandler(BaseEventHandler):
    """필터링된 이벤트 핸들러"""
    
    def __init__(self, 
                 handler_name: str,
                 supported_events: List[EventType],
                 handler_func: callable,
                 filter_func: callable = None,
                 enabled: bool = True,
                 priority_filter: Optional[EventPriority] = None):
        """
        필터링된 이벤트 핸들러 초기화
        
        Args:
            handler_name: 핸들러 이름
            supported_events: 지원하는 이벤트 타입 목록
            handler_func: 실제 이벤트 처리 함수
            filter_func: 이벤트 필터 함수 (True 반환 시 처리)
            enabled: 핸들러 활성화 여부
            priority_filter: 처리할 최소 우선순위
        """
        super().__init__(handler_name, supported_events, enabled, priority_filter)
        self._v_handler_func = handler_func
        self._v_filter_func = filter_func
    
    def can_handle_event(self, event: IEvent) -> bool:
        """이벤트 처리 가능 여부 확인 (필터 포함)"""
        if not super().can_handle_event(event):
            return False
        
        # 추가 필터 적용
        if self._v_filter_func:
            try:
                return self._v_filter_func(event)
            except Exception as e:
                logger.error(f"Filter function failed: {str(e)}")
                return False
        
        return True
    
    async def handle_event(self, event: IEvent) -> bool:
        """이벤트 처리"""
        try:
            if asyncio.iscoroutinefunction(self._v_handler_func):
                return await self._v_handler_func(event)
            else:
                return self._v_handler_func(event)
        except Exception as e:
            logger.error(f"Handler function failed: {str(e)}")
            return False


class BatchEventHandler(BaseEventHandler):
    """배치 이벤트 핸들러"""
    
    def __init__(self, 
                 handler_name: str,
                 supported_events: List[EventType],
                 batch_handler_func: callable,
                 batch_size: int = 10,
                 batch_timeout: float = 5.0,
                 enabled: bool = True,
                 priority_filter: Optional[EventPriority] = None):
        """
        배치 이벤트 핸들러 초기화
        
        Args:
            handler_name: 핸들러 이름
            supported_events: 지원하는 이벤트 타입 목록
            batch_handler_func: 배치 이벤트 처리 함수
            batch_size: 배치 크기
            batch_timeout: 배치 타임아웃 (초)
            enabled: 핸들러 활성화 여부
            priority_filter: 처리할 최소 우선순위
        """
        super().__init__(handler_name, supported_events, enabled, priority_filter)
        self._v_batch_handler_func = batch_handler_func
        self._v_batch_size = batch_size
        self._v_batch_timeout = batch_timeout
        self._v_event_batch: List[IEvent] = []
        self._v_batch_task: Optional[asyncio.Task] = None
    
    async def handle_event(self, event: IEvent) -> bool:
        """이벤트를 배치에 추가"""
        self._v_event_batch.append(event)
        
        # 배치 크기에 도달하면 즉시 처리
        if len(self._v_event_batch) >= self._v_batch_size:
            await self._process_batch()
            return True
        
        # 타임아웃 태스크 시작
        if not self._v_batch_task or self._v_batch_task.done():
            self._v_batch_task = asyncio.create_task(self._wait_and_process_batch())
        
        return True
    
    async def _wait_and_process_batch(self):
        """타임아웃 후 배치 처리"""
        await asyncio.sleep(self._v_batch_timeout)
        if self._v_event_batch:
            await self._process_batch()
    
    async def _process_batch(self):
        """배치 처리"""
        if not self._v_event_batch:
            return
        
        _v_batch = self._v_event_batch.copy()
        self._v_event_batch.clear()
        
        try:
            if asyncio.iscoroutinefunction(self._v_batch_handler_func):
                await self._v_batch_handler_func(_v_batch)
            else:
                self._v_batch_handler_func(_v_batch)
        except Exception as e:
            logger.error(f"Batch handler function failed: {str(e)}")
    
    def get_batch_stats(self) -> Dict[str, Any]:
        """배치 통계 조회"""
        _v_base_stats = self.get_stats()
        _v_base_stats.update({
            'batch_size': self._v_batch_size,
            'batch_timeout': self._v_batch_timeout,
            'pending_events': len(self._v_event_batch)
        })
        return _v_base_stats 