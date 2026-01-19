"""
BasePlugin 클래스 구현

이 모듈은 모든 플러그인이 상속받아야 하는 기본 클래스를 정의합니다.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from datetime import datetime
import threading

from core.interfaces.plugins import IPlugin, PluginMetadata, PluginState
from core.plugins.exceptions import (
    PluginInitializationError, PluginStartError,
    PluginStopError, PluginStateError
)
from core.events.bus import EventBus
from core.di.injector import DependencyInjector


class BasePlugin(IPlugin, ABC):
    """플러그인 기본 구현 클래스"""
    
    def __init__(self, name: str, version: str, description: str = "",
                 author: str = "", category: str = "general"):
        """
        플러그인 초기화
        
        Args:
            name: 플러그인 이름
            version: 플러그인 버전
            description: 플러그인 설명
            author: 플러그인 작성자
            category: 플러그인 카테고리
        """
        self._name = name
        self._version = version
        self._description = description
        self._author = author
        self._category = category
        
        # 플러그인 상태 관리
        self._state = PluginState.DISCOVERED
        self._state_lock = threading.RLock()
        
        # 설정 및 의존성
        self._config: Dict[str, Any] = {}
        self._dependencies: List[str] = []
        self._interfaces: List[str] = []
        
        # 런타임 정보
        self._start_time: Optional[datetime] = None
        self._stop_time: Optional[datetime] = None
        self._error_count = 0
        self._last_error: Optional[Exception] = None
        
        # 이벤트 버스 및 로거
        self._event_bus: Optional[EventBus] = None
        self._logger: Optional[logging.Logger] = None
        
        # 리소스 관리
        self._resources: Dict[str, Any] = {}
        self._cleanup_callbacks: List[callable] = []
        
        # 성능 메트릭
        self._performance_metrics: Dict[str, Any] = {}
        
        # 의존성 주입 설정
        self._setup_dependency_injection()
        
        # 로거 설정
        self._setup_logger()
    
    def _setup_dependency_injection(self):
        """의존성 주입 설정"""
        try:
            # 이벤트 버스 주입
            self._event_bus = DependencyInjector.get_instance().get_service(EventBus)
        except Exception:
            # 이벤트 버스가 없는 경우 무시
            pass
    
    def _setup_logger(self):
        """로거 설정"""
        self._logger = logging.getLogger(f"plugin.{self._name}")
        self._logger.setLevel(logging.INFO)
    
    @property
    def name(self) -> str:
        """플러그인 이름"""
        return self._name
    
    @property
    def version(self) -> str:
        """플러그인 버전"""
        return self._version
    
    @property
    def state(self) -> PluginState:
        """플러그인 상태"""
        with self._state_lock:
            return self._state
    
    @property
    def logger(self) -> logging.Logger:
        """플러그인 로거"""
        return self._logger
    
    @property
    def config(self) -> Dict[str, Any]:
        """플러그인 설정"""
        return self._config.copy()
    
    def _set_state(self, new_state: PluginState):
        """
        플러그인 상태 설정 (내부 사용)
        
        Args:
            new_state: 새로운 상태
        """
        with self._state_lock:
            old_state = self._state
            self._state = new_state
            
            # 상태 변경 이벤트 발생
            if self._event_bus:
                try:
                    from core.plugins.events import create_plugin_state_changed_event
                    event = create_plugin_state_changed_event(
                        plugin_name=self._name,
                        old_state=old_state,
                        new_state=new_state
                    )
                    asyncio.create_task(self._event_bus.publish(event))
                except Exception as e:
                    self._logger.warning(f"Failed to publish state change event: {e}")
    
    def _validate_state_transition(self, target_state: PluginState):
        """
        상태 전환 유효성 검사
        
        Args:
            target_state: 대상 상태
            
        Raises:
            PluginStateError: 유효하지 않은 상태 전환
        """
        current_state = self._state
        
        # 유효한 상태 전환 매핑
        valid_transitions = {
            PluginState.DISCOVERED: [PluginState.LOADING, PluginState.ERROR],
            PluginState.LOADING: [PluginState.LOADED, PluginState.ERROR],
            PluginState.LOADED: [PluginState.INITIALIZING, PluginState.UNLOADING, PluginState.ERROR],
            PluginState.INITIALIZING: [PluginState.INITIALIZED, PluginState.ERROR],
            PluginState.INITIALIZED: [PluginState.STARTING, PluginState.STOPPING, PluginState.ERROR],
            PluginState.STARTING: [PluginState.ACTIVE, PluginState.ERROR],
            PluginState.ACTIVE: [PluginState.STOPPING, PluginState.ERROR],
            PluginState.STOPPING: [PluginState.STOPPED, PluginState.ERROR],
            PluginState.STOPPED: [PluginState.STARTING, PluginState.UNLOADING, PluginState.ERROR],
            PluginState.UNLOADING: [PluginState.UNLOADED, PluginState.ERROR],
            PluginState.UNLOADED: [PluginState.LOADING],
            PluginState.ERROR: [PluginState.LOADING, PluginState.UNLOADING]
        }
        
        if target_state not in valid_transitions.get(current_state, []):
            raise PluginStateError(
                f"Invalid state transition from {current_state.value} to {target_state.value}",
                plugin_name=self._name,
                current_state=current_state.value,
                expected_state=target_state.value
            )
    
    def get_metadata(self) -> PluginMetadata:
        """플러그인 메타데이터 반환"""
        return PluginMetadata(
            name=self._name,
            version=self._version,
            description=self._description,
            author=self._author,
            category=self._category,
            interfaces=self._interfaces.copy(),
            dependencies=self._dependencies.copy(),
            entry_point=f"{self.__module__}:{self.__class__.__name__}"
        )
    
    async def initialize(self, config: Dict[str, Any]) -> None:
        """
        플러그인 초기화
        
        Args:
            config: 플러그인 설정
            
        Raises:
            PluginInitializationError: 초기화 실패
        """
        try:
            self._validate_state_transition(PluginState.INITIALIZING)
            self._set_state(PluginState.INITIALIZING)
            
            # 설정 저장
            self._config = config.copy()
            
            # 설정 검증
            self._validate_config(config)
            
            # 실제 초기화 로직 실행
            await self._on_initialize(config)
            
            # 초기화 완료 상태로 변경
            self._set_state(PluginState.INITIALIZED)
            
            self._logger.info(f"Plugin {self._name} initialized successfully")
            
        except Exception as e:
            self._set_state(PluginState.ERROR)
            self._last_error = e
            self._error_count += 1
            
            error_msg = f"Failed to initialize plugin {self._name}: {str(e)}"
            self._logger.error(error_msg)
            
            raise PluginInitializationError(
                error_msg,
                plugin_name=self._name,
                original_error=e
            )
    
    async def start(self) -> None:
        """
        플러그인 시작
        
        Raises:
            PluginStartError: 시작 실패
        """
        try:
            self._validate_state_transition(PluginState.STARTING)
            self._set_state(PluginState.STARTING)
            
            # 시작 시간 기록
            self._start_time = datetime.now()
            
            # 실제 시작 로직 실행
            await self._on_start()
            
            # 활성화 상태로 변경
            self._set_state(PluginState.ACTIVE)
            
            self._logger.info(f"Plugin {self._name} started successfully")
            
        except Exception as e:
            self._set_state(PluginState.ERROR)
            self._last_error = e
            self._error_count += 1
            
            error_msg = f"Failed to start plugin {self._name}: {str(e)}"
            self._logger.error(error_msg)
            
            raise PluginStartError(
                error_msg,
                plugin_name=self._name,
                original_error=e
            )
    
    async def stop(self) -> None:
        """
        플러그인 중지
        
        Raises:
            PluginStopError: 중지 실패
        """
        try:
            self._validate_state_transition(PluginState.STOPPING)
            self._set_state(PluginState.STOPPING)
            
            # 중지 시간 기록
            self._stop_time = datetime.now()
            
            # 실제 중지 로직 실행
            await self._on_stop()
            
            # 중지 상태로 변경
            self._set_state(PluginState.STOPPED)
            
            self._logger.info(f"Plugin {self._name} stopped successfully")
            
        except Exception as e:
            self._set_state(PluginState.ERROR)
            self._last_error = e
            self._error_count += 1
            
            error_msg = f"Failed to stop plugin {self._name}: {str(e)}"
            self._logger.error(error_msg)
            
            raise PluginStopError(
                error_msg,
                plugin_name=self._name,
                original_error=e
            )
    
    async def cleanup(self) -> None:
        """플러그인 정리"""
        try:
            # 정리 콜백 실행
            for callback in self._cleanup_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback()
                    else:
                        callback()
                except Exception as e:
                    self._logger.warning(f"Cleanup callback failed: {e}")
            
            # 리소스 정리
            await self._cleanup_resources()
            
            # 실제 정리 로직 실행
            await self._on_cleanup()
            
            self._logger.info(f"Plugin {self._name} cleaned up successfully")
            
        except Exception as e:
            self._logger.error(f"Failed to cleanup plugin {self._name}: {e}", exc_info=True)
            raise
    
    def get_status(self) -> Dict[str, Any]:
        """플러그인 상태 반환"""
        return {
            "name": self._name,
            "version": self._version,
            "state": self._state.value,
            "start_time": self._start_time.isoformat() if self._start_time else None,
            "stop_time": self._stop_time.isoformat() if self._stop_time else None,
            "error_count": self._error_count,
            "last_error": str(self._last_error) if self._last_error else None,
            "uptime_seconds": (datetime.now() - self._start_time).total_seconds() if self._start_time else 0,
            "performance_metrics": self._performance_metrics.copy(),
            "resource_usage": self._get_resource_usage()
        }
    
    def add_cleanup_callback(self, callback: callable):
        """정리 콜백 추가"""
        self._cleanup_callbacks.append(callback)
    
    def add_resource(self, name: str, resource: Any):
        """리소스 추가"""
        self._resources[name] = resource
    
    def get_resource(self, name: str) -> Any:
        """리소스 조회"""
        return self._resources.get(name)
    
    def record_performance_metric(self, metric_name: str, value: float, unit: str = "ms"):
        """성능 메트릭 기록"""
        self._performance_metrics[metric_name] = {
            "value": value,
            "unit": unit,
            "timestamp": datetime.now().isoformat()
        }
    
    def get_config_value(self, key: str, default: Any = None) -> Any:
        """설정값 조회"""
        return self._config.get(key, default)
    
    def set_config_value(self, key: str, value: Any):
        """설정값 설정"""
        self._config[key] = value
    
    # 추상 메서드들 (하위 클래스에서 구현)
    @abstractmethod
    async def _on_initialize(self, config: Dict[str, Any]) -> None:
        """초기화 로직 구현"""
        pass
    
    @abstractmethod
    async def _on_start(self) -> None:
        """시작 로직 구현"""
        pass
    
    @abstractmethod
    async def _on_stop(self) -> None:
        """중지 로직 구현"""
        pass
    
    @abstractmethod
    async def _on_cleanup(self) -> None:
        """정리 로직 구현"""
        pass
    
    # 선택적 구현 메서드들
    def _validate_config(self, config: Dict[str, Any]) -> None:
        """
        설정 검증 (선택적 구현)
        
        Args:
            config: 검증할 설정
            
        Raises:
            PluginConfigurationError: 설정 오류
        """
        pass
    
    async def _cleanup_resources(self) -> None:
        """리소스 정리 (선택적 구현)"""
        self._resources.clear()
    
    def _get_resource_usage(self) -> Dict[str, Any]:
        """리소스 사용량 조회 (선택적 구현)"""
        return {
            "resource_count": len(self._resources),
            "cleanup_callbacks": len(self._cleanup_callbacks)
        }
    
    def __str__(self) -> str:
        return f"Plugin(name={self._name}, version={self._version}, state={self._state.value})"
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self._name} v{self._version}>" 