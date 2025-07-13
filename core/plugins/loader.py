"""
플러그인 로더 구현

이 모듈은 플러그인 동적 로딩 및 발견 기능을 제공합니다.
"""

import os
import json
import importlib
import importlib.util
import inspect
import asyncio
import logging
from typing import Dict, List, Optional, Type, Any, Union
from pathlib import Path
import sys
import traceback

from core.interfaces.plugins import (
    IPluginLoader, IPlugin, PluginMetadata, PluginState
)
from core.plugins.exceptions import (
    PluginLoadError, PluginValidationError, PluginMetadataError,
    PluginInterfaceError, PluginVersionError
)
from core.plugins.base import BasePlugin
from core.plugins.events import (
    PluginDiscoveredEvent, PluginLoadingEvent, PluginLoadedEvent,
    PluginUnloadingEvent, PluginUnloadedEvent, PluginErrorEvent
)
from core.events.bus import EventBus
from core.di.injector import DependencyInjector


class PluginLoader(IPluginLoader):
    """플러그인 로더 구현"""
    
    def __init__(self, event_bus: Optional[EventBus] = None):
        """
        플러그인 로더 초기화
        
        Args:
            event_bus: 이벤트 버스 (선택적)
        """
        self._event_bus = event_bus
        self._logger = logging.getLogger(self.__class__.__name__)
        self._loaded_modules: Dict[str, Any] = {}
        self._discovered_plugins: Dict[str, PluginMetadata] = {}
        self._plugin_paths: Dict[str, str] = {}
        
        # 의존성 주입
        if not self._event_bus:
            try:
                self._event_bus = DependencyInjector.get_instance().get_service(EventBus)
            except Exception:
                pass
    
    async def discover_plugins(self, plugin_dirs: List[str]) -> List[PluginMetadata]:
        """
        플러그인 발견
        
        Args:
            plugin_dirs: 플러그인 디렉토리 목록
            
        Returns:
            발견된 플러그인 메타데이터 목록
        """
        discovered_plugins = []
        
        for plugin_dir in plugin_dirs:
            if not os.path.exists(plugin_dir):
                self._logger.warning(f"Plugin directory does not exist: {plugin_dir}")
                continue
            
            # 디렉토리 내 플러그인 발견
            plugins_in_dir = await self._discover_plugins_in_directory(plugin_dir)
            discovered_plugins.extend(plugins_in_dir)
        
        # 발견된 플러그인 저장
        for plugin_metadata in discovered_plugins:
            self._discovered_plugins[plugin_metadata.name] = plugin_metadata
        
        self._logger.info(f"Discovered {len(discovered_plugins)} plugins")
        return discovered_plugins
    
    async def _discover_plugins_in_directory(self, plugin_dir: str) -> List[PluginMetadata]:
        """
        디렉토리 내 플러그인 발견
        
        Args:
            plugin_dir: 플러그인 디렉토리
            
        Returns:
            발견된 플러그인 메타데이터 목록
        """
        discovered_plugins = []
        
        for item in os.listdir(plugin_dir):
            item_path = os.path.join(plugin_dir, item)
            
            if os.path.isdir(item_path):
                # 디렉토리인 경우 플러그인 메타데이터 파일 확인
                metadata_file = os.path.join(item_path, "plugin_info.json")
                if os.path.exists(metadata_file):
                    try:
                        plugin_metadata = await self._load_plugin_metadata(metadata_file)
                        self._plugin_paths[plugin_metadata.name] = item_path
                        discovered_plugins.append(plugin_metadata)
                        
                        # 플러그인 발견 이벤트 발생
                        await self._emit_plugin_discovered_event(plugin_metadata, item_path)
                        
                    except Exception as e:
                        self._logger.error(f"Failed to load plugin metadata from {metadata_file}: {e}")
                        continue
        
        return discovered_plugins
    
    async def _load_plugin_metadata(self, metadata_file: str) -> PluginMetadata:
        """
        플러그인 메타데이터 로드
        
        Args:
            metadata_file: 메타데이터 파일 경로
            
        Returns:
            플러그인 메타데이터
            
        Raises:
            PluginMetadataError: 메타데이터 로드 실패
        """
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata_dict = json.load(f)
            
            # 메타데이터 검증
            self._validate_metadata_dict(metadata_dict)
            
            # PluginMetadata 객체 생성
            plugin_metadata = PluginMetadata(
                name=metadata_dict["name"],
                version=metadata_dict["version"],
                description=metadata_dict.get("description", ""),
                author=metadata_dict.get("author", ""),
                category=metadata_dict.get("category", "general"),
                interfaces=metadata_dict.get("interfaces", []),
                dependencies=metadata_dict.get("dependencies", []),
                entry_point=metadata_dict["entry_point"],
                config_schema=metadata_dict.get("config_schema"),
                permissions=metadata_dict.get("permissions"),
                compatibility=metadata_dict.get("compatibility"),
                tags=metadata_dict.get("tags")
            )
            
            return plugin_metadata
            
        except FileNotFoundError:
            raise PluginMetadataError(
                f"Plugin metadata file not found: {metadata_file}",
                metadata_file=metadata_file
            )
        except json.JSONDecodeError as e:
            raise PluginMetadataError(
                f"Invalid JSON in plugin metadata file: {e}",
                metadata_file=metadata_file
            )
        except Exception as e:
            raise PluginMetadataError(
                f"Failed to load plugin metadata: {e}",
                metadata_file=metadata_file
            )
    
    def _validate_metadata_dict(self, metadata_dict: Dict[str, Any]) -> None:
        """
        메타데이터 딕셔너리 검증
        
        Args:
            metadata_dict: 메타데이터 딕셔너리
            
        Raises:
            PluginValidationError: 검증 실패
        """
        required_fields = ["name", "version", "entry_point"]
        missing_fields = [field for field in required_fields if field not in metadata_dict]
        
        if missing_fields:
            raise PluginValidationError(
                f"Missing required metadata fields: {missing_fields}",
                validation_errors=missing_fields
            )
        
        # 버전 형식 검증
        version = metadata_dict["version"]
        if not isinstance(version, str) or not version.strip():
            raise PluginValidationError(
                "Plugin version must be a non-empty string",
                validation_errors=["version"]
            )
        
        # 엔트리 포인트 형식 검증
        entry_point = metadata_dict["entry_point"]
        if not isinstance(entry_point, str) or ":" not in entry_point:
            raise PluginValidationError(
                "Plugin entry_point must be in format 'module:class'",
                validation_errors=["entry_point"]
            )
    
    async def load_plugin(self, metadata: PluginMetadata) -> IPlugin:
        """
        플러그인 로드
        
        Args:
            metadata: 플러그인 메타데이터
            
        Returns:
            로드된 플러그인 인스턴스
            
        Raises:
            PluginLoadError: 플러그인 로드 실패
        """
        plugin_name = metadata.name
        plugin_path = self._plugin_paths.get(plugin_name)
        
        if not plugin_path:
            raise PluginLoadError(
                f"Plugin path not found for {plugin_name}",
                plugin_name=plugin_name
            )
        
        try:
            # 플러그인 로딩 시작 이벤트 발생
            await self._emit_plugin_loading_event(plugin_name)
            
            # 모듈 로드
            module = await self._load_plugin_module(plugin_path, metadata)
            
            # 플러그인 클래스 인스턴스 생성
            plugin_instance = await self._create_plugin_instance(module, metadata)
            
            # 플러그인 검증
            if not self.validate_plugin(plugin_instance):
                raise PluginValidationError(
                    f"Plugin validation failed for {plugin_name}",
                    plugin_name=plugin_name
                )
            
            # 로드된 모듈 저장
            self._loaded_modules[plugin_name] = module
            
            # 플러그인 로드 완료 이벤트 발생
            await self._emit_plugin_loaded_event(plugin_name, plugin_instance)
            
            self._logger.info(f"Successfully loaded plugin: {plugin_name}")
            return plugin_instance
            
        except Exception as e:
            # 오류 이벤트 발생
            await self._emit_plugin_error_event(plugin_name, e)
            
            if isinstance(e, (PluginLoadError, PluginValidationError)):
                raise
            
            raise PluginLoadError(
                f"Failed to load plugin {plugin_name}: {str(e)}",
                plugin_name=plugin_name,
                plugin_path=plugin_path,
                original_error=e
            )
    
    async def _load_plugin_module(self, plugin_path: str, metadata: PluginMetadata) -> Any:
        """
        플러그인 모듈 로드
        
        Args:
            plugin_path: 플러그인 경로
            metadata: 플러그인 메타데이터
            
        Returns:
            로드된 모듈
        """
        module_name, class_name = metadata.entry_point.split(":", 1)
        
        # 모듈 파일 경로 구성
        module_file = os.path.join(plugin_path, f"{module_name}.py")
        
        if not os.path.exists(module_file):
            raise PluginLoadError(
                f"Plugin module file not found: {module_file}",
                plugin_name=metadata.name,
                plugin_path=plugin_path
            )
        
        try:
            # 모듈 spec 생성
            spec = importlib.util.spec_from_file_location(
                f"plugin_{metadata.name}_{module_name}",
                module_file
            )
            
            if spec is None or spec.loader is None:
                raise PluginLoadError(
                    f"Failed to create module spec for {module_file}",
                    plugin_name=metadata.name,
                    plugin_path=plugin_path
                )
            
            # 모듈 로드
            module = importlib.util.module_from_spec(spec)
            
            # 플러그인 경로를 sys.path에 추가
            if plugin_path not in sys.path:
                sys.path.insert(0, plugin_path)
            
            try:
                spec.loader.exec_module(module)
            finally:
                # sys.path에서 제거
                if plugin_path in sys.path:
                    sys.path.remove(plugin_path)
            
            return module
            
        except Exception as e:
            raise PluginLoadError(
                f"Failed to load module {module_name}: {str(e)}",
                plugin_name=metadata.name,
                plugin_path=plugin_path,
                original_error=e
            )
    
    async def _create_plugin_instance(self, module: Any, metadata: PluginMetadata) -> IPlugin:
        """
        플러그인 인스턴스 생성
        
        Args:
            module: 로드된 모듈
            metadata: 플러그인 메타데이터
            
        Returns:
            플러그인 인스턴스
        """
        module_name, class_name = metadata.entry_point.split(":", 1)
        
        # 클래스 조회
        if not hasattr(module, class_name):
            raise PluginLoadError(
                f"Plugin class {class_name} not found in module {module_name}",
                plugin_name=metadata.name
            )
        
        plugin_class = getattr(module, class_name)
        
        # 클래스 검증
        if not inspect.isclass(plugin_class):
            raise PluginLoadError(
                f"{class_name} is not a class",
                plugin_name=metadata.name
            )
        
        if not issubclass(plugin_class, BasePlugin):
            raise PluginLoadError(
                f"Plugin class {class_name} must inherit from BasePlugin",
                plugin_name=metadata.name
            )
        
        try:
            # 인스턴스 생성
            plugin_instance = plugin_class(
                name=metadata.name,
                version=metadata.version,
                description=metadata.description,
                author=metadata.author,
                category=metadata.category
            )
            
            # 인터페이스 및 의존성 설정
            plugin_instance._interfaces = metadata.interfaces.copy()
            plugin_instance._dependencies = metadata.dependencies.copy()
            
            return plugin_instance
            
        except Exception as e:
            raise PluginLoadError(
                f"Failed to create plugin instance: {str(e)}",
                plugin_name=metadata.name,
                original_error=e
            )
    
    async def unload_plugin(self, plugin: IPlugin) -> None:
        """
        플러그인 언로드
        
        Args:
            plugin: 언로드할 플러그인
            
        Raises:
            PluginUnloadError: 언로드 실패
        """
        plugin_name = plugin.name
        
        try:
            # 플러그인 언로딩 시작 이벤트 발생
            await self._emit_plugin_unloading_event(plugin_name)
            
            # 플러그인 정리
            await plugin.cleanup()
            
            # 로드된 모듈 제거
            if plugin_name in self._loaded_modules:
                del self._loaded_modules[plugin_name]
            
            # 플러그인 언로드 완료 이벤트 발생
            await self._emit_plugin_unloaded_event(plugin_name)
            
            self._logger.info(f"Successfully unloaded plugin: {plugin_name}")
            
        except Exception as e:
            # 오류 이벤트 발생
            await self._emit_plugin_error_event(plugin_name, e)
            raise
    
    def validate_plugin(self, plugin: IPlugin) -> bool:
        """
        플러그인 유효성 검증
        
        Args:
            plugin: 검증할 플러그인
            
        Returns:
            검증 결과
        """
        try:
            # 기본 인터페이스 검증
            if not isinstance(plugin, BasePlugin):
                return False
            
            # 필수 메서드 검증
            required_methods = ["get_metadata", "initialize", "start", "stop", "cleanup", "get_status"]
            for method_name in required_methods:
                if not hasattr(plugin, method_name):
                    return False
                
                method = getattr(plugin, method_name)
                if not callable(method):
                    return False
            
            # 메타데이터 검증
            metadata = plugin.get_metadata()
            if not isinstance(metadata, PluginMetadata):
                return False
            
            return True
            
        except Exception as e:
            self._logger.error(f"Plugin validation error: {e}")
            return False
    
    def get_discovered_plugins(self) -> List[PluginMetadata]:
        """발견된 플러그인 목록 반환"""
        return list(self._discovered_plugins.values())
    
    def get_plugin_path(self, plugin_name: str) -> Optional[str]:
        """플러그인 경로 반환"""
        return self._plugin_paths.get(plugin_name)
    
    def is_plugin_loaded(self, plugin_name: str) -> bool:
        """플러그인 로드 여부 확인"""
        return plugin_name in self._loaded_modules
    
    # 이벤트 발생 헬퍼 메서드들
    async def _emit_plugin_discovered_event(self, metadata: PluginMetadata, plugin_path: str):
        """플러그인 발견 이벤트 발생"""
        if self._event_bus:
            event = PluginDiscoveredEvent(
                plugin_name=metadata.name,
                plugin_metadata=metadata,
                plugin_path=plugin_path
            )
            await self._event_bus.publish(event)
    
    async def _emit_plugin_loading_event(self, plugin_name: str):
        """플러그인 로딩 시작 이벤트 발생"""
        if self._event_bus:
            event = PluginLoadingEvent(plugin_name=plugin_name)
            await self._event_bus.publish(event)
    
    async def _emit_plugin_loaded_event(self, plugin_name: str, plugin_instance: IPlugin):
        """플러그인 로드 완료 이벤트 발생"""
        if self._event_bus:
            event = PluginLoadedEvent(
                plugin_name=plugin_name,
                plugin_instance=plugin_instance
            )
            await self._event_bus.publish(event)
    
    async def _emit_plugin_unloading_event(self, plugin_name: str):
        """플러그인 언로딩 시작 이벤트 발생"""
        if self._event_bus:
            event = PluginUnloadingEvent(plugin_name=plugin_name)
            await self._event_bus.publish(event)
    
    async def _emit_plugin_unloaded_event(self, plugin_name: str):
        """플러그인 언로드 완료 이벤트 발생"""
        if self._event_bus:
            event = PluginUnloadedEvent(plugin_name=plugin_name)
            await self._event_bus.publish(event)
    
    async def _emit_plugin_error_event(self, plugin_name: str, error: Exception):
        """플러그인 오류 이벤트 발생"""
        if self._event_bus:
            event = PluginErrorEvent(
                plugin_name=plugin_name,
                error=error,
                stack_trace=traceback.format_exc()
            )
            await self._event_bus.publish(event) 