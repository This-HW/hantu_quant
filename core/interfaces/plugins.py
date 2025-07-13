"""
플러그인 시스템 인터페이스 정의

이 모듈은 플러그인 시스템의 모든 핵심 인터페이스를 정의합니다.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Union, Callable
from dataclasses import dataclass
from enum import Enum
import asyncio


class PluginState(Enum):
    """플러그인 상태 열거형"""
    DISCOVERED = "discovered"
    LOADING = "loading"
    LOADED = "loaded"
    INITIALIZING = "initializing"
    INITIALIZED = "initialized"
    STARTING = "starting"
    ACTIVE = "active"
    STOPPING = "stopping"
    STOPPED = "stopped"
    UNLOADING = "unloading"
    UNLOADED = "unloaded"
    ERROR = "error"


@dataclass
class PluginMetadata:
    """플러그인 메타데이터"""
    name: str
    version: str
    description: str
    author: str
    category: str
    interfaces: List[str]
    dependencies: List[str]
    entry_point: str
    config_schema: Optional[Dict[str, Any]] = None
    permissions: Optional[List[str]] = None
    compatibility: Optional[Dict[str, str]] = None
    tags: Optional[List[str]] = None


class IPlugin(ABC):
    """플러그인 기본 인터페이스"""
    
    @abstractmethod
    def get_metadata(self) -> PluginMetadata:
        """플러그인 메타데이터 반환"""
        pass
    
    @abstractmethod
    async def initialize(self, config: Dict[str, Any]) -> None:
        """플러그인 초기화"""
        pass
    
    @abstractmethod
    async def start(self) -> None:
        """플러그인 시작"""
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """플러그인 중지"""
        pass
    
    @abstractmethod
    async def cleanup(self) -> None:
        """플러그인 정리"""
        pass
    
    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """플러그인 상태 반환"""
        pass


class IPluginLoader(ABC):
    """플러그인 로더 인터페이스"""
    
    @abstractmethod
    async def discover_plugins(self, plugin_dirs: List[str]) -> List[PluginMetadata]:
        """플러그인 발견"""
        pass
    
    @abstractmethod
    async def load_plugin(self, metadata: PluginMetadata) -> IPlugin:
        """플러그인 로드"""
        pass
    
    @abstractmethod
    async def unload_plugin(self, plugin: IPlugin) -> None:
        """플러그인 언로드"""
        pass
    
    @abstractmethod
    def validate_plugin(self, plugin: IPlugin) -> bool:
        """플러그인 유효성 검증"""
        pass


class IPluginRegistry(ABC):
    """플러그인 레지스트리 인터페이스"""
    
    @abstractmethod
    def register_plugin(self, plugin: IPlugin) -> None:
        """플러그인 등록"""
        pass
    
    @abstractmethod
    def unregister_plugin(self, plugin_name: str) -> None:
        """플러그인 등록 해제"""
        pass
    
    @abstractmethod
    def get_plugin(self, plugin_name: str) -> Optional[IPlugin]:
        """플러그인 조회"""
        pass
    
    @abstractmethod
    def get_all_plugins(self) -> List[IPlugin]:
        """모든 플러그인 조회"""
        pass
    
    @abstractmethod
    def get_plugins_by_category(self, category: str) -> List[IPlugin]:
        """카테고리별 플러그인 조회"""
        pass
    
    @abstractmethod
    def get_dependency_graph(self) -> Dict[str, List[str]]:
        """의존성 그래프 반환"""
        pass
    
    @abstractmethod
    def resolve_dependencies(self, plugin_name: str) -> List[str]:
        """의존성 해결 순서 반환"""
        pass


class IPluginLifecycleManager(ABC):
    """플러그인 라이프사이클 관리자 인터페이스"""
    
    @abstractmethod
    async def initialize_plugin(self, plugin: IPlugin, config: Dict[str, Any]) -> None:
        """플러그인 초기화"""
        pass
    
    @abstractmethod
    async def start_plugin(self, plugin: IPlugin) -> None:
        """플러그인 시작"""
        pass
    
    @abstractmethod
    async def stop_plugin(self, plugin: IPlugin) -> None:
        """플러그인 중지"""
        pass
    
    @abstractmethod
    async def restart_plugin(self, plugin: IPlugin) -> None:
        """플러그인 재시작"""
        pass
    
    @abstractmethod
    def get_plugin_state(self, plugin: IPlugin) -> PluginState:
        """플러그인 상태 조회"""
        pass
    
    @abstractmethod
    def set_plugin_state(self, plugin: IPlugin, state: PluginState) -> None:
        """플러그인 상태 설정"""
        pass


class IPluginSecurityManager(ABC):
    """플러그인 보안 관리자 인터페이스"""
    
    @abstractmethod
    def check_permissions(self, plugin: IPlugin, permission: str) -> bool:
        """권한 검증"""
        pass
    
    @abstractmethod
    def validate_plugin_code(self, plugin_path: str) -> bool:
        """플러그인 코드 검증"""
        pass
    
    @abstractmethod
    def create_sandbox(self, plugin: IPlugin) -> Any:
        """플러그인 샌드박스 생성"""
        pass
    
    @abstractmethod
    def destroy_sandbox(self, plugin: IPlugin) -> None:
        """플러그인 샌드박스 제거"""
        pass


class IPluginManager(ABC):
    """플러그인 매니저 인터페이스"""
    
    @abstractmethod
    async def discover_and_load_plugins(self, plugin_dirs: List[str]) -> None:
        """플러그인 발견 및 로드"""
        pass
    
    @abstractmethod
    async def load_plugin_by_name(self, plugin_name: str) -> None:
        """이름으로 플러그인 로드"""
        pass
    
    @abstractmethod
    async def unload_plugin_by_name(self, plugin_name: str) -> None:
        """이름으로 플러그인 언로드"""
        pass
    
    @abstractmethod
    async def reload_plugin_by_name(self, plugin_name: str) -> None:
        """이름으로 플러그인 재로드"""
        pass
    
    @abstractmethod
    def get_plugin_status(self, plugin_name: str) -> Dict[str, Any]:
        """플러그인 상태 조회"""
        pass
    
    @abstractmethod
    def get_all_plugin_status(self) -> Dict[str, Dict[str, Any]]:
        """모든 플러그인 상태 조회"""
        pass
    
    @abstractmethod
    def get_plugin_statistics(self) -> Dict[str, Any]:
        """플러그인 통계 조회"""
        pass
    
    @abstractmethod
    async def start_all_plugins(self) -> None:
        """모든 플러그인 시작"""
        pass
    
    @abstractmethod
    async def stop_all_plugins(self) -> None:
        """모든 플러그인 중지"""
        pass


class IPluginEventHandler(ABC):
    """플러그인 이벤트 핸들러 인터페이스"""
    
    @abstractmethod
    async def on_plugin_discovered(self, metadata: PluginMetadata) -> None:
        """플러그인 발견 시 호출"""
        pass
    
    @abstractmethod
    async def on_plugin_loaded(self, plugin: IPlugin) -> None:
        """플러그인 로드 시 호출"""
        pass
    
    @abstractmethod
    async def on_plugin_started(self, plugin: IPlugin) -> None:
        """플러그인 시작 시 호출"""
        pass
    
    @abstractmethod
    async def on_plugin_stopped(self, plugin: IPlugin) -> None:
        """플러그인 중지 시 호출"""
        pass
    
    @abstractmethod
    async def on_plugin_unloaded(self, plugin: IPlugin) -> None:
        """플러그인 언로드 시 호출"""
        pass
    
    @abstractmethod
    async def on_plugin_error(self, plugin: IPlugin, error: Exception) -> None:
        """플러그인 오류 시 호출"""
        pass 