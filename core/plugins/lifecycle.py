"""
플러그인 라이프사이클 관리자 구현

이 모듈은 플러그인 라이프사이클 관리 기능을 제공합니다.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timedelta
import threading
import time

from core.interfaces.plugins import (
    IPluginLifecycleManager, IPlugin, PluginState, PluginMetadata
)
from core.plugins.exceptions import (
    PluginStateError, PluginInitializationError, PluginStartError,
    PluginStopError, PluginTimeoutError, PluginException
)
from core.plugins.events import (
    PluginInitializingEvent, PluginInitializedEvent, PluginStartingEvent,
    PluginStartedEvent, PluginStoppingEvent, PluginStoppedEvent,
    PluginStateChangedEvent, PluginErrorEvent, PluginPerformanceEvent
)
from core.events.bus import EventBus
from core.di.injector import DependencyInjector


class PluginLifecycleManager(IPluginLifecycleManager):
    """플러그인 라이프사이클 관리자 구현"""
    
    def __init__(self, event_bus: Optional[EventBus] = None, 
                 default_timeout: float = 30.0):
        """
        플러그인 라이프사이클 관리자 초기화
        
        Args:
            event_bus: 이벤트 버스 (선택적)
            default_timeout: 기본 타임아웃 (초)
        """
        self._event_bus = event_bus
        self._default_timeout = default_timeout
        self._logger = logging.getLogger(self.__class__.__name__)
        
        # 플러그인 상태 관리
        self._plugin_states: Dict[str, PluginState] = {}
        self._plugin_configs: Dict[str, Dict[str, Any]] = {}
        self._plugin_start_times: Dict[str, datetime] = {}
        self._plugin_stop_times: Dict[str, datetime] = {}
        
        # 라이프사이클 이벤트 핸들러
        self._lifecycle_handlers: Dict[str, List[callable]] = {
            "pre_initialize": [],
            "post_initialize": [],
            "pre_start": [],
            "post_start": [],
            "pre_stop": [],
            "post_stop": [],
            "error": []
        }
        
        # 상태 변경 이력
        self._state_history: Dict[str, List[Dict[str, Any]]] = {}
        
        # 성능 메트릭
        self._performance_metrics: Dict[str, Dict[str, Any]] = {}
        
        # 스레드 안전성
        self._lock = threading.RLock()
        
        # 의존성 주입
        if not self._event_bus:
            try:
                self._event_bus = DependencyInjector.get_instance().get_service(EventBus)
            except Exception:
                pass
    
    async def initialize_plugin(self, plugin: IPlugin, config: Dict[str, Any]) -> None:
        """
        플러그인 초기화
        
        Args:
            plugin: 초기화할 플러그인
            config: 플러그인 설정
            
        Raises:
            PluginInitializationError: 초기화 실패
        """
        plugin_name = plugin.name
        
        with self._lock:
            # 현재 상태 확인
            current_state = self.get_plugin_state(plugin)
            if current_state != PluginState.LOADED:
                raise PluginStateError(
                    f"Plugin {plugin_name} must be in LOADED state to initialize, "
                    f"current state: {current_state.value}",
                    plugin_name=plugin_name,
                    current_state=current_state.value,
                    expected_state=PluginState.LOADED.value
                )
        
        try:
            # 초기화 시작 이벤트 및 상태 설정
            await self._emit_plugin_initializing_event(plugin_name, config)
            self.set_plugin_state(plugin, PluginState.INITIALIZING)
            
            # Pre-initialize 핸들러 실행
            await self._execute_lifecycle_handlers("pre_initialize", plugin, config)
            
            # 성능 측정 시작
            start_time = time.time()
            
            # 플러그인 초기화
            await asyncio.wait_for(
                plugin.initialize(config),
                timeout=self._default_timeout
            )
            
            # 성능 측정 종료
            init_time_ms = (time.time() - start_time) * 1000
            
            # 설정 저장
            self._plugin_configs[plugin_name] = config.copy()
            
            # 성능 메트릭 기록
            self._record_performance_metric(plugin_name, "initialization_time_ms", init_time_ms)
            
            # Post-initialize 핸들러 실행
            await self._execute_lifecycle_handlers("post_initialize", plugin, config)
            
            # 초기화 완료 상태 설정
            self.set_plugin_state(plugin, PluginState.INITIALIZED)
            
            # 초기화 완료 이벤트 발생
            await self._emit_plugin_initialized_event(plugin_name, init_time_ms)
            
            self._logger.info(f"Successfully initialized plugin: {plugin_name} ({init_time_ms:.2f}ms)")
            
        except asyncio.TimeoutError:
            await self._handle_plugin_timeout(plugin, "initialization", self._default_timeout)
        except Exception as e:
            await self._handle_plugin_error(plugin, e, "initialization")
    
    async def start_plugin(self, plugin: IPlugin) -> None:
        """
        플러그인 시작
        
        Args:
            plugin: 시작할 플러그인
            
        Raises:
            PluginStartError: 시작 실패
        """
        plugin_name = plugin.name
        
        with self._lock:
            # 현재 상태 확인
            current_state = self.get_plugin_state(plugin)
            if current_state not in [PluginState.INITIALIZED, PluginState.STOPPED]:
                raise PluginStateError(
                    f"Plugin {plugin_name} must be in INITIALIZED or STOPPED state to start, "
                    f"current state: {current_state.value}",
                    plugin_name=plugin_name,
                    current_state=current_state.value,
                    expected_state="INITIALIZED or STOPPED"
                )
        
        try:
            # 시작 이벤트 및 상태 설정
            await self._emit_plugin_starting_event(plugin_name)
            self.set_plugin_state(plugin, PluginState.STARTING)
            
            # Pre-start 핸들러 실행
            await self._execute_lifecycle_handlers("pre_start", plugin)
            
            # 성능 측정 시작
            start_time = time.time()
            
            # 플러그인 시작
            await asyncio.wait_for(
                plugin.start(),
                timeout=self._default_timeout
            )
            
            # 성능 측정 종료
            start_time_ms = (time.time() - start_time) * 1000
            
            # 시작 시간 기록
            self._plugin_start_times[plugin_name] = datetime.now()
            
            # 성능 메트릭 기록
            self._record_performance_metric(plugin_name, "start_time_ms", start_time_ms)
            
            # Post-start 핸들러 실행
            await self._execute_lifecycle_handlers("post_start", plugin)
            
            # 활성 상태 설정
            self.set_plugin_state(plugin, PluginState.ACTIVE)
            
            # 시작 완료 이벤트 발생
            await self._emit_plugin_started_event(plugin_name, start_time_ms)
            
            self._logger.info(f"Successfully started plugin: {plugin_name} ({start_time_ms:.2f}ms)")
            
        except asyncio.TimeoutError:
            await self._handle_plugin_timeout(plugin, "start", self._default_timeout)
        except Exception as e:
            await self._handle_plugin_error(plugin, e, "start")
    
    async def stop_plugin(self, plugin: IPlugin) -> None:
        """
        플러그인 중지
        
        Args:
            plugin: 중지할 플러그인
            
        Raises:
            PluginStopError: 중지 실패
        """
        plugin_name = plugin.name
        
        with self._lock:
            # 현재 상태 확인
            current_state = self.get_plugin_state(plugin)
            if current_state != PluginState.ACTIVE:
                raise PluginStateError(
                    f"Plugin {plugin_name} must be in ACTIVE state to stop, "
                    f"current state: {current_state.value}",
                    plugin_name=plugin_name,
                    current_state=current_state.value,
                    expected_state=PluginState.ACTIVE.value
                )
        
        try:
            # 중지 이벤트 및 상태 설정
            await self._emit_plugin_stopping_event(plugin_name)
            self.set_plugin_state(plugin, PluginState.STOPPING)
            
            # Pre-stop 핸들러 실행
            await self._execute_lifecycle_handlers("pre_stop", plugin)
            
            # 성능 측정 시작
            start_time = time.time()
            
            # 플러그인 중지
            await asyncio.wait_for(
                plugin.stop(),
                timeout=self._default_timeout
            )
            
            # 성능 측정 종료
            stop_time_ms = (time.time() - start_time) * 1000
            
            # 중지 시간 기록
            self._plugin_stop_times[plugin_name] = datetime.now()
            
            # 성능 메트릭 기록
            self._record_performance_metric(plugin_name, "stop_time_ms", stop_time_ms)
            
            # Post-stop 핸들러 실행
            await self._execute_lifecycle_handlers("post_stop", plugin)
            
            # 중지 상태 설정
            self.set_plugin_state(plugin, PluginState.STOPPED)
            
            # 중지 완료 이벤트 발생
            await self._emit_plugin_stopped_event(plugin_name, stop_time_ms)
            
            self._logger.info(f"Successfully stopped plugin: {plugin_name} ({stop_time_ms:.2f}ms)")
            
        except asyncio.TimeoutError:
            await self._handle_plugin_timeout(plugin, "stop", self._default_timeout)
        except Exception as e:
            await self._handle_plugin_error(plugin, e, "stop")
    
    async def restart_plugin(self, plugin: IPlugin) -> None:
        """
        플러그인 재시작
        
        Args:
            plugin: 재시작할 플러그인
        """
        plugin_name = plugin.name
        
        try:
            # 현재 상태 확인
            current_state = self.get_plugin_state(plugin)
            
            # 활성 상태인 경우 먼저 중지
            if current_state == PluginState.ACTIVE:
                await self.stop_plugin(plugin)
            
            # 중지 상태인 경우 시작
            if self.get_plugin_state(plugin) == PluginState.STOPPED:
                await self.start_plugin(plugin)
            else:
                raise PluginStateError(
                    f"Cannot restart plugin {plugin_name} in state {current_state.value}",
                    plugin_name=plugin_name,
                    current_state=current_state.value
                )
                
            self._logger.info(f"Successfully restarted plugin: {plugin_name}")
            
        except Exception as e:
            await self._handle_plugin_error(plugin, e, "restart")
    
    def get_plugin_state(self, plugin: IPlugin) -> PluginState:
        """
        플러그인 상태 조회
        
        Args:
            plugin: 조회할 플러그인
            
        Returns:
            플러그인 상태
        """
        with self._lock:
            return self._plugin_states.get(plugin.name, PluginState.DISCOVERED)
    
    def set_plugin_state(self, plugin: IPlugin, state: PluginState) -> None:
        """
        플러그인 상태 설정
        
        Args:
            plugin: 대상 플러그인
            state: 설정할 상태
        """
        plugin_name = plugin.name
        
        with self._lock:
            old_state = self._plugin_states.get(plugin_name, PluginState.DISCOVERED)
            self._plugin_states[plugin_name] = state
            
            # 상태 변경 이력 기록
            self._record_state_change(plugin_name, old_state, state)
            
            # 상태 변경 이벤트 발생
            if old_state != state:
                asyncio.create_task(
                    self._emit_plugin_state_changed_event(plugin_name, old_state, state)
                )
    
    def get_plugin_config(self, plugin_name: str) -> Optional[Dict[str, Any]]:
        """플러그인 설정 조회"""
        with self._lock:
            return self._plugin_configs.get(plugin_name, {}).copy()
    
    def get_plugin_uptime(self, plugin_name: str) -> Optional[timedelta]:
        """플러그인 업타임 조회"""
        with self._lock:
            start_time = self._plugin_start_times.get(plugin_name)
            if start_time:
                return datetime.now() - start_time
            return None
    
    def get_plugin_performance_metrics(self, plugin_name: str) -> Dict[str, Any]:
        """플러그인 성능 메트릭 조회"""
        with self._lock:
            return self._performance_metrics.get(plugin_name, {}).copy()
    
    def get_plugin_state_history(self, plugin_name: str) -> List[Dict[str, Any]]:
        """플러그인 상태 변경 이력 조회"""
        with self._lock:
            return self._state_history.get(plugin_name, []).copy()
    
    def get_all_plugin_states(self) -> Dict[str, PluginState]:
        """모든 플러그인 상태 조회"""
        with self._lock:
            return self._plugin_states.copy()
    
    def get_lifecycle_statistics(self) -> Dict[str, Any]:
        """라이프사이클 통계 조회"""
        with self._lock:
            state_counts = {}
            for state in PluginState:
                state_counts[state.value] = sum(
                    1 for s in self._plugin_states.values() if s == state
                )
            
            return {
                "total_plugins": len(self._plugin_states),
                "state_counts": state_counts,
                "performance_metrics": len(self._performance_metrics),
                "state_history_entries": sum(
                    len(history) for history in self._state_history.values()
                )
            }
    
    def add_lifecycle_handler(self, event_type: str, handler: callable) -> None:
        """라이프사이클 핸들러 추가"""
        if event_type in self._lifecycle_handlers:
            self._lifecycle_handlers[event_type].append(handler)
    
    def remove_lifecycle_handler(self, event_type: str, handler: callable) -> None:
        """라이프사이클 핸들러 제거"""
        if event_type in self._lifecycle_handlers:
            try:
                self._lifecycle_handlers[event_type].remove(handler)
            except ValueError:
                pass
    
    def _record_state_change(self, plugin_name: str, old_state: PluginState, new_state: PluginState) -> None:
        """상태 변경 기록"""
        if plugin_name not in self._state_history:
            self._state_history[plugin_name] = []
        
        self._state_history[plugin_name].append({
            "timestamp": datetime.now().isoformat(),
            "old_state": old_state.value,
            "new_state": new_state.value
        })
    
    def _record_performance_metric(self, plugin_name: str, metric_name: str, value: float) -> None:
        """성능 메트릭 기록"""
        if plugin_name not in self._performance_metrics:
            self._performance_metrics[plugin_name] = {}
        
        self._performance_metrics[plugin_name][metric_name] = {
            "value": value,
            "timestamp": datetime.now().isoformat()
        }
    
    async def _execute_lifecycle_handlers(self, event_type: str, plugin: IPlugin, *args) -> None:
        """라이프사이클 핸들러 실행"""
        handlers = self._lifecycle_handlers.get(event_type, [])
        
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(plugin, *args)
                else:
                    handler(plugin, *args)
            except Exception as e:
                self._logger.warning(f"Lifecycle handler {handler} failed: {e}")
    
    async def _handle_plugin_timeout(self, plugin: IPlugin, operation: str, timeout: float) -> None:
        """플러그인 타임아웃 처리"""
        plugin_name = plugin.name
        
        # 오류 상태 설정
        self.set_plugin_state(plugin, PluginState.ERROR)
        
        # 타임아웃 오류 생성
        error = PluginTimeoutError(
            f"Plugin {plugin_name} {operation} timed out after {timeout} seconds",
            plugin_name=plugin_name,
            timeout_seconds=timeout
        )
        
        # 오류 이벤트 발생
        await self._emit_plugin_error_event(plugin_name, error)
        
        # 오류 핸들러 실행
        await self._execute_lifecycle_handlers("error", plugin, error)
        
        raise error
    
    async def _handle_plugin_error(self, plugin: IPlugin, error: Exception, operation: str) -> None:
        """플러그인 오류 처리"""
        plugin_name = plugin.name
        
        # 오류 상태 설정
        self.set_plugin_state(plugin, PluginState.ERROR)
        
        # 오류 이벤트 발생
        await self._emit_plugin_error_event(plugin_name, error)
        
        # 오류 핸들러 실행
        await self._execute_lifecycle_handlers("error", plugin, error)
        
        # 적절한 예외 타입으로 변환
        if operation == "initialization":
            raise PluginInitializationError(
                f"Plugin {plugin_name} initialization failed: {str(error)}",
                plugin_name=plugin_name,
                original_error=error
            )
        elif operation == "start":
            raise PluginStartError(
                f"Plugin {plugin_name} start failed: {str(error)}",
                plugin_name=plugin_name,
                original_error=error
            )
        elif operation == "stop":
            raise PluginStopError(
                f"Plugin {plugin_name} stop failed: {str(error)}",
                plugin_name=plugin_name,
                original_error=error
            )
        else:
            raise PluginException(
                f"Plugin {plugin_name} {operation} failed: {str(error)}",
                plugin_name=plugin_name
            )
    
    # 이벤트 발생 헬퍼 메서드들
    async def _emit_plugin_initializing_event(self, plugin_name: str, config: Dict[str, Any]):
        """플러그인 초기화 시작 이벤트 발생"""
        if self._event_bus:
            event = PluginInitializingEvent(
                plugin_name=plugin_name,
                config=config
            )
            await self._event_bus.publish(event)
    
    async def _emit_plugin_initialized_event(self, plugin_name: str, init_time_ms: float):
        """플러그인 초기화 완료 이벤트 발생"""
        if self._event_bus:
            event = PluginInitializedEvent(
                plugin_name=plugin_name,
                init_time_ms=init_time_ms
            )
            await self._event_bus.publish(event)
    
    async def _emit_plugin_starting_event(self, plugin_name: str):
        """플러그인 시작 이벤트 발생"""
        if self._event_bus:
            event = PluginStartingEvent(plugin_name=plugin_name)
            await self._event_bus.publish(event)
    
    async def _emit_plugin_started_event(self, plugin_name: str, start_time_ms: float):
        """플러그인 시작 완료 이벤트 발생"""
        if self._event_bus:
            event = PluginStartedEvent(
                plugin_name=plugin_name,
                start_time_ms=start_time_ms
            )
            await self._event_bus.publish(event)
    
    async def _emit_plugin_stopping_event(self, plugin_name: str):
        """플러그인 중지 이벤트 발생"""
        if self._event_bus:
            event = PluginStoppingEvent(plugin_name=plugin_name)
            await self._event_bus.publish(event)
    
    async def _emit_plugin_stopped_event(self, plugin_name: str, stop_time_ms: float):
        """플러그인 중지 완료 이벤트 발생"""
        if self._event_bus:
            event = PluginStoppedEvent(
                plugin_name=plugin_name,
                stop_time_ms=stop_time_ms
            )
            await self._event_bus.publish(event)
    
    async def _emit_plugin_state_changed_event(self, plugin_name: str, old_state: PluginState, new_state: PluginState):
        """플러그인 상태 변경 이벤트 발생"""
        if self._event_bus:
            event = PluginStateChangedEvent(
                plugin_name=plugin_name,
                old_state=old_state,
                new_state=new_state
            )
            await self._event_bus.publish(event)
    
    async def _emit_plugin_error_event(self, plugin_name: str, error: Exception):
        """플러그인 오류 이벤트 발생"""
        if self._event_bus:
            event = PluginErrorEvent(
                plugin_name=plugin_name,
                error=error
            )
            await self._event_bus.publish(event) 