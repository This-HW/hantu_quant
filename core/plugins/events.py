"""
플러그인 시스템 이벤트 클래스 정의

이 모듈은 플러그인 시스템에서 발생하는 모든 이벤트를 정의합니다.
기존의 이벤트 시스템을 확장하여 플러그인 관련 이벤트를 처리합니다.
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime

from core.interfaces.plugins import PluginMetadata, PluginState, IPlugin


@dataclass
class PluginEvent:
    """플러그인 관련 기본 이벤트"""
    
    plugin_name: str
    event_type: str = "plugin_event"
    plugin_metadata: Optional[PluginMetadata] = None
    timestamp: Optional[datetime] = None
    context: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.context is None:
            self.context = {}


@dataclass
class PluginDiscoveredEvent(PluginEvent):
    """플러그인 발견 이벤트"""
    
    event_type: str = "plugin_discovered"
    plugin_path: Optional[str] = None
    
    def __post_init__(self):
        super().__post_init__()
        self.context.update({
            "plugin_path": self.plugin_path,
            "metadata": self.plugin_metadata.dict() if self.plugin_metadata else None
        })


@dataclass
class PluginLoadingEvent(PluginEvent):
    """플러그인 로딩 시작 이벤트"""
    
    event_type: str = "plugin_loading"
    
    def __post_init__(self):
        super().__post_init__()
        self.context.update({
            "action": "loading_started"
        })


@dataclass
class PluginLoadedEvent(PluginEvent):
    """플러그인 로드 완료 이벤트"""
    
    event_type: str = "plugin_loaded"
    plugin_instance: Optional[IPlugin] = None
    load_time_ms: Optional[float] = None
    
    def __post_init__(self):
        super().__post_init__()
        self.context.update({
            "load_time_ms": self.load_time_ms,
            "plugin_type": type(self.plugin_instance).__name__ if self.plugin_instance else None
        })


@dataclass
class PluginUnloadingEvent(PluginEvent):
    """플러그인 언로딩 시작 이벤트"""
    
    event_type: str = "plugin_unloading"
    
    def __post_init__(self):
        super().__post_init__()
        self.context.update({
            "action": "unloading_started"
        })


@dataclass
class PluginUnloadedEvent(PluginEvent):
    """플러그인 언로드 완료 이벤트"""
    
    event_type: str = "plugin_unloaded"
    unload_time_ms: Optional[float] = None
    
    def __post_init__(self):
        super().__post_init__()
        self.context.update({
            "unload_time_ms": self.unload_time_ms,
            "action": "unloaded"
        })


@dataclass
class PluginInitializingEvent(PluginEvent):
    """플러그인 초기화 시작 이벤트"""
    
    event_type: str = "plugin_initializing"
    config: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        super().__post_init__()
        self.context.update({
            "config": self.config,
            "action": "initializing_started"
        })


@dataclass
class PluginInitializedEvent(PluginEvent):
    """플러그인 초기화 완료 이벤트"""
    
    event_type: str = "plugin_initialized"
    init_time_ms: Optional[float] = None
    
    def __post_init__(self):
        super().__post_init__()
        self.context.update({
            "init_time_ms": self.init_time_ms,
            "action": "initialized"
        })


@dataclass
class PluginStartingEvent(PluginEvent):
    """플러그인 시작 시작 이벤트"""
    
    event_type: str = "plugin_starting"
    
    def __post_init__(self):
        super().__post_init__()
        self.context.update({
            "action": "starting"
        })


@dataclass
class PluginStartedEvent(PluginEvent):
    """플러그인 시작 완료 이벤트"""
    
    event_type: str = "plugin_started"
    start_time_ms: Optional[float] = None
    
    def __post_init__(self):
        super().__post_init__()
        self.context.update({
            "start_time_ms": self.start_time_ms,
            "action": "started"
        })


@dataclass
class PluginStoppingEvent(PluginEvent):
    """플러그인 중지 시작 이벤트"""
    
    event_type: str = "plugin_stopping"
    
    def __post_init__(self):
        super().__post_init__()
        self.context.update({
            "action": "stopping"
        })


@dataclass
class PluginStoppedEvent(PluginEvent):
    """플러그인 중지 완료 이벤트"""
    
    event_type: str = "plugin_stopped"
    stop_time_ms: Optional[float] = None
    
    def __post_init__(self):
        super().__post_init__()
        self.context.update({
            "stop_time_ms": self.stop_time_ms,
            "action": "stopped"
        })


@dataclass
class PluginStateChangedEvent(PluginEvent):
    """플러그인 상태 변경 이벤트"""
    
    event_type: str = "plugin_state_changed"
    old_state: Optional[PluginState] = None
    new_state: Optional[PluginState] = None
    
    def __post_init__(self):
        super().__post_init__()
        self.context.update({
            "old_state": self.old_state.value if self.old_state else None,
            "new_state": self.new_state.value if self.new_state else None
        })


@dataclass
class PluginErrorEvent(PluginEvent):
    """플러그인 오류 이벤트"""
    
    event_type: str = "plugin_error"
    error: Optional[Exception] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    stack_trace: Optional[str] = None
    
    def __post_init__(self):
        super().__post_init__()
        if self.error:
            self.error_type = type(self.error).__name__
            self.error_message = str(self.error)
            
        self.context.update({
            "error_type": self.error_type,
            "error_message": self.error_message,
            "stack_trace": self.stack_trace
        })


@dataclass
class PluginDependencyEvent(PluginEvent):
    """플러그인 의존성 관련 이벤트"""
    
    event_type: str = "plugin_dependency"
    dependency_name: Optional[str] = None
    dependency_action: Optional[str] = None  # resolved, missing, circular
    dependencies: Optional[List[str]] = None
    
    def __post_init__(self):
        super().__post_init__()
        self.context.update({
            "dependency_name": self.dependency_name,
            "dependency_action": self.dependency_action,
            "dependencies": self.dependencies
        })


@dataclass
class PluginSecurityEvent(PluginEvent):
    """플러그인 보안 관련 이벤트"""
    
    event_type: str = "plugin_security"
    permission: Optional[str] = None
    action: Optional[str] = None  # granted, denied, revoked
    security_level: Optional[str] = None
    
    def __post_init__(self):
        super().__post_init__()
        self.context.update({
            "permission": self.permission,
            "action": self.action,
            "security_level": self.security_level
        })


@dataclass
class PluginResourceEvent(PluginEvent):
    """플러그인 리소스 관련 이벤트"""
    
    event_type: str = "plugin_resource"
    resource_type: Optional[str] = None
    resource_name: Optional[str] = None
    resource_usage: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        super().__post_init__()
        self.context.update({
            "resource_type": self.resource_type,
            "resource_name": self.resource_name,
            "resource_usage": self.resource_usage
        })


@dataclass
class PluginPerformanceEvent(PluginEvent):
    """플러그인 성능 관련 이벤트"""
    
    event_type: str = "plugin_performance"
    metric_name: Optional[str] = None
    metric_value: Optional[float] = None
    metric_unit: Optional[str] = None
    performance_data: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        super().__post_init__()
        self.context.update({
            "metric_name": self.metric_name,
            "metric_value": self.metric_value,
            "metric_unit": self.metric_unit,
            "performance_data": self.performance_data
        })


@dataclass
class PluginRegistryEvent(PluginEvent):
    """플러그인 레지스트리 관련 이벤트"""
    
    event_type: str = "plugin_registry"
    registry_action: Optional[str] = None  # registered, unregistered, updated
    registry_stats: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        super().__post_init__()
        self.context.update({
            "registry_action": self.registry_action,
            "registry_stats": self.registry_stats
        })


@dataclass
class PluginSystemEvent(PluginEvent):
    """플러그인 시스템 전체 관련 이벤트"""
    
    event_type: str = "plugin_system"
    system_action: Optional[str] = None  # startup, shutdown, reload
    system_stats: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        super().__post_init__()
        self.context.update({
            "system_action": self.system_action,
            "system_stats": self.system_stats
        })


# 이벤트 팩토리 함수들
def create_plugin_discovered_event(plugin_name: str, metadata: PluginMetadata, 
                                  plugin_path: str) -> PluginDiscoveredEvent:
    """플러그인 발견 이벤트 생성"""
    return PluginDiscoveredEvent(
        plugin_name=plugin_name,
        plugin_metadata=metadata,
        plugin_path=plugin_path
    )


def create_plugin_error_event(plugin_name: str, error: Exception, 
                            stack_trace: Optional[str] = None) -> PluginErrorEvent:
    """플러그인 오류 이벤트 생성"""
    return PluginErrorEvent(
        plugin_name=plugin_name,
        error=error,
        stack_trace=stack_trace
    )


def create_plugin_state_changed_event(plugin_name: str, old_state: PluginState, 
                                     new_state: PluginState) -> PluginStateChangedEvent:
    """플러그인 상태 변경 이벤트 생성"""
    return PluginStateChangedEvent(
        plugin_name=plugin_name,
        old_state=old_state,
        new_state=new_state
    )


def create_plugin_performance_event(plugin_name: str, metric_name: str, 
                                   metric_value: float, metric_unit: str = "ms") -> PluginPerformanceEvent:
    """플러그인 성능 이벤트 생성"""
    return PluginPerformanceEvent(
        plugin_name=plugin_name,
        metric_name=metric_name,
        metric_value=metric_value,
        metric_unit=metric_unit
    ) 