"""
플러그인 시스템 모듈

이 모듈은 한투 퀀트 프로젝트의 플러그인 시스템을 제공합니다.
동적 모듈 로딩, 플러그인 라이프사이클 관리, 의존성 관리 등을 지원합니다.

주요 구성요소:
- BasePlugin: 모든 플러그인의 기본 클래스
- PluginLoader: 플러그인 동적 로딩
- PluginRegistry: 플러그인 등록 및 관리
- PluginLifecycleManager: 플러그인 라이프사이클 관리
- PluginManager: 통합 플러그인 관리자
- plugin: 플러그인 데코레이터
"""

from core.interfaces.plugins import (
    PluginState,
    PluginMetadata,
    IPlugin,
    IPluginLoader,
    IPluginRegistry,
    IPluginLifecycleManager,
    IPluginSecurityManager,
    IPluginManager,
    IPluginEventHandler
)

from core.plugins.base import BasePlugin
from core.plugins.loader import PluginLoader
from core.plugins.registry import PluginRegistry
from core.plugins.lifecycle import PluginLifecycleManager
from core.plugins.decorators import plugin, register, get_registered_plugins, get_plugin_by_name
from core.plugins.exceptions import (
    PluginException,
    PluginLoadError,
    PluginInitializationError,
    PluginStartError,
    PluginStopError,
    PluginUnloadError,
    PluginDependencyError,
    PluginValidationError,
    PluginSecurityError,
    PluginVersionError,
    PluginNotFoundError,
    PluginAlreadyExistsError,
    PluginStateError,
    PluginTimeoutError,
    PluginConfigurationError,
    PluginMetadataError,
    PluginInterfaceError,
    PluginRuntimeError,
    PluginResourceError,
    format_plugin_error,
    is_plugin_error,
    get_error_code
)

from core.plugins.events import (
    PluginEvent,
    PluginDiscoveredEvent,
    PluginLoadingEvent,
    PluginLoadedEvent,
    PluginUnloadingEvent,
    PluginUnloadedEvent,
    PluginInitializingEvent,
    PluginInitializedEvent,
    PluginStartingEvent,
    PluginStartedEvent,
    PluginStoppingEvent,
    PluginStoppedEvent,
    PluginStateChangedEvent,
    PluginErrorEvent,
    PluginDependencyEvent,
    PluginSecurityEvent,
    PluginResourceEvent,
    PluginPerformanceEvent,
    PluginRegistryEvent,
    PluginSystemEvent,
    create_plugin_discovered_event,
    create_plugin_error_event,
    create_plugin_state_changed_event,
    create_plugin_performance_event
)

# 버전 정보
__version__ = "1.0.0"
__author__ = "HantuQuant Team"

# 모듈 레벨 상수
DEFAULT_PLUGIN_TIMEOUT = 30.0  # 초
DEFAULT_PLUGIN_DIRECTORY = "plugins"
PLUGIN_METADATA_FILE = "plugin_info.json"
PLUGIN_CONFIG_FILE = "config.json"

# 플러그인 카테고리
PLUGIN_CATEGORIES = {
    "strategy": "Trading Strategy Plugins",
    "indicator": "Technical Indicator Plugins",
    "analyzer": "Analysis Plugins",
    "data": "Data Provider Plugins",
    "utility": "Utility Plugins",
    "connector": "External Connector Plugins",
    "risk": "Risk Management Plugins",
    "optimization": "Optimization Plugins",
    "notification": "Notification Plugins",
    "general": "General Purpose Plugins"
}

# 플러그인 권한
PLUGIN_PERMISSIONS = {
    "market_data": "Access to market data",
    "trading": "Trading operations",
    "config": "System configuration access",
    "file_system": "File system access",
    "network": "Network access",
    "database": "Database access",
    "logging": "Logging access",
    "events": "Event system access",
    "metrics": "Metrics collection",
    "admin": "Administrative operations"
}

# 편의 함수들
def get_plugin_categories() -> dict:
    """플러그인 카테고리 목록 반환"""
    return PLUGIN_CATEGORIES.copy()

def get_plugin_permissions() -> dict:
    """플러그인 권한 목록 반환"""
    return PLUGIN_PERMISSIONS.copy()

def validate_plugin_category(category: str) -> bool:
    """플러그인 카테고리 유효성 검사"""
    return category in PLUGIN_CATEGORIES

def validate_plugin_permission(permission: str) -> bool:
    """플러그인 권한 유효성 검사"""
    return permission in PLUGIN_PERMISSIONS

# 플러그인 시스템 상태
class PluginSystemStatus:
    """플러그인 시스템 상태 정보"""
    
    def __init__(self):
        self.is_initialized = False
        self.plugin_count = 0
        self.active_plugins = 0
        self.error_plugins = 0
        self.startup_time = None
        self.last_update = None
    
    def to_dict(self) -> dict:
        """딕셔너리로 변환"""
        return {
            "is_initialized": self.is_initialized,
            "plugin_count": self.plugin_count,
            "active_plugins": self.active_plugins,
            "error_plugins": self.error_plugins,
            "startup_time": self.startup_time.isoformat() if self.startup_time else None,
            "last_update": self.last_update.isoformat() if self.last_update else None
        }

# 전역 플러그인 시스템 상태
_plugin_system_status = PluginSystemStatus()

def get_plugin_system_status() -> PluginSystemStatus:
    """플러그인 시스템 상태 반환"""
    return _plugin_system_status

# 플러그인 개발 헬퍼 함수들
def create_plugin_metadata(name: str, version: str, description: str = "",
                          author: str = "", category: str = "general",
                          interfaces: list = None, dependencies: list = None,
                          permissions: list = None, **kwargs) -> PluginMetadata:
    """플러그인 메타데이터 생성 헬퍼"""
    return PluginMetadata(
        name=name,
        version=version,
        description=description,
        author=author,
        category=category,
        interfaces=interfaces or [],
        dependencies=dependencies or [],
        entry_point=f"{name}:main",
        permissions=permissions,
        **kwargs
    )

def validate_plugin_metadata(metadata: PluginMetadata) -> bool:
    """플러그인 메타데이터 유효성 검사"""
    try:
        # 필수 필드 검사
        if not metadata.name or not metadata.version:
            return False
        
        # 카테고리 검사
        if not validate_plugin_category(metadata.category):
            return False
        
        # 권한 검사
        if metadata.permissions:
            for permission in metadata.permissions:
                if not validate_plugin_permission(permission):
                    return False
        
        return True
    except Exception:
        return False

# 플러그인 디렉토리 헬퍼
def get_default_plugin_directories() -> list:
    """기본 플러그인 디렉토리 목록 반환"""
    return [
        "plugins",
        "plugins/strategies",
        "plugins/indicators",
        "plugins/analyzers",
        "plugins/data",
        "plugins/utilities"
    ]

# 에러 헬퍼 함수들
def handle_plugin_error(plugin_name: str, error: Exception, 
                       context: str = "") -> PluginErrorEvent:
    """플러그인 에러 처리 헬퍼"""
    error_event = create_plugin_error_event(plugin_name, error)
    if context:
        error_event.context["error_context"] = context
    return error_event

# 모듈 초기화 함수
def initialize_plugin_system():
    """플러그인 시스템 초기화"""
    global _plugin_system_status
    from datetime import datetime
    
    _plugin_system_status.is_initialized = True
    _plugin_system_status.startup_time = datetime.now()
    _plugin_system_status.last_update = datetime.now()

# 모듈 정리 함수
def cleanup_plugin_system():
    """플러그인 시스템 정리"""
    global _plugin_system_status
    _plugin_system_status.is_initialized = False
    _plugin_system_status.plugin_count = 0
    _plugin_system_status.active_plugins = 0
    _plugin_system_status.error_plugins = 0

# 공개 API
__all__ = [
    # 인터페이스
    "PluginState",
    "PluginMetadata",
    "IPlugin",
    "IPluginLoader",
    "IPluginRegistry",
    "IPluginLifecycleManager",
    "IPluginSecurityManager",
    "IPluginManager",
    "IPluginEventHandler",
    
    # 기본 클래스
    "BasePlugin",
    "PluginLoader",
    "PluginRegistry",
    "PluginLifecycleManager",
    
    # 예외 클래스
    "PluginException",
    "PluginLoadError",
    "PluginInitializationError",
    "PluginStartError",
    "PluginStopError",
    "PluginUnloadError",
    "PluginDependencyError",
    "PluginValidationError",
    "PluginSecurityError",
    "PluginVersionError",
    "PluginNotFoundError",
    "PluginAlreadyExistsError",
    "PluginStateError",
    "PluginTimeoutError",
    "PluginConfigurationError",
    "PluginMetadataError",
    "PluginInterfaceError",
    "PluginRuntimeError",
    "PluginResourceError",
    
    # 이벤트 클래스
    "PluginEvent",
    "PluginDiscoveredEvent",
    "PluginLoadingEvent",
    "PluginLoadedEvent",
    "PluginUnloadingEvent",
    "PluginUnloadedEvent",
    "PluginInitializingEvent",
    "PluginInitializedEvent",
    "PluginStartingEvent",
    "PluginStartedEvent",
    "PluginStoppingEvent",
    "PluginStoppedEvent",
    "PluginStateChangedEvent",
    "PluginErrorEvent",
    "PluginDependencyEvent",
    "PluginSecurityEvent",
    "PluginResourceEvent",
    "PluginPerformanceEvent",
    "PluginRegistryEvent",
    "PluginSystemEvent",
    
    # 헬퍼 함수
    "format_plugin_error",
    "is_plugin_error",
    "get_error_code",
    "create_plugin_discovered_event",
    "create_plugin_error_event",
    "create_plugin_state_changed_event",
    "create_plugin_performance_event",
    "get_plugin_categories",
    "get_plugin_permissions",
    "validate_plugin_category",
    "validate_plugin_permission",
    "get_plugin_system_status",
    "create_plugin_metadata",
    "validate_plugin_metadata",
    "get_default_plugin_directories",
    "handle_plugin_error",
    "initialize_plugin_system",
    "cleanup_plugin_system",
    
    # 상수
    "DEFAULT_PLUGIN_TIMEOUT",
    "DEFAULT_PLUGIN_DIRECTORY",
    "PLUGIN_METADATA_FILE",
    "PLUGIN_CONFIG_FILE",
    "PLUGIN_CATEGORIES",
    "PLUGIN_PERMISSIONS",
    "PluginSystemStatus",
    
    # 데코레이터 및 유틸리티
    "plugin",
    "register", 
    "get_registered_plugins",
    "get_plugin_by_name"
] 