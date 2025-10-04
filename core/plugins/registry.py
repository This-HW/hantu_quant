"""
플러그인 레지스트리 구현

이 모듈은 플러그인 등록, 관리, 의존성 처리 기능을 제공합니다.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Set, Any, Tuple
from collections import defaultdict, deque
import threading

from core.interfaces.plugins import (
    IPluginRegistry, IPlugin, PluginMetadata, PluginState
)
from core.plugins.exceptions import (
    PluginAlreadyExistsError, PluginNotFoundError, PluginDependencyError,
    PluginException
)
from core.plugins.events import (
    PluginRegistryEvent, PluginDependencyEvent, PluginErrorEvent
)
from core.events.bus import EventBus
from core.di.injector import DependencyInjector


class PluginRegistry(IPluginRegistry):
    """플러그인 레지스트리 구현"""
    
    def __init__(self, event_bus: Optional[EventBus] = None):
        """
        플러그인 레지스트리 초기화
        
        Args:
            event_bus: 이벤트 버스 (선택적)
        """
        self._event_bus = event_bus
        self._logger = logging.getLogger(self.__class__.__name__)
        
        # 플러그인 저장소
        self._plugins: Dict[str, IPlugin] = {}
        self._plugins_by_category: Dict[str, List[IPlugin]] = defaultdict(list)
        self._plugin_metadata: Dict[str, PluginMetadata] = {}
        
        # 의존성 관리
        self._dependency_graph: Dict[str, Set[str]] = defaultdict(set)
        self._reverse_dependency_graph: Dict[str, Set[str]] = defaultdict(set)
        
        # 스레드 안전성
        self._lock = threading.RLock()
        
        # 레지스트리 통계
        self._registration_count = 0
        self._last_registration_time = None
        
        # 의존성 주입
        if not self._event_bus:
            try:
                self._event_bus = DependencyInjector.get_instance().get_service(EventBus)
            except Exception:
                pass
    
    def register_plugin(self, plugin: IPlugin) -> None:
        """
        플러그인 등록
        
        Args:
            plugin: 등록할 플러그인
            
        Raises:
            PluginAlreadyExistsError: 플러그인이 이미 존재함
        """
        plugin_name = plugin.name
        
        with self._lock:
            # 중복 등록 확인
            if plugin_name in self._plugins:
                raise PluginAlreadyExistsError(plugin_name)
            
            try:
                # 플러그인 메타데이터 조회
                metadata = plugin.get_metadata()
                
                # 의존성 검증
                self._validate_dependencies(plugin_name, metadata.dependencies)
                
                # 플러그인 등록
                self._plugins[plugin_name] = plugin
                self._plugin_metadata[plugin_name] = metadata
                
                # 카테고리별 등록
                self._plugins_by_category[metadata.category].append(plugin)
                
                # 의존성 그래프 업데이트
                self._update_dependency_graph(plugin_name, metadata.dependencies)
                
                # 등록 통계 업데이트
                self._registration_count += 1
                from datetime import datetime
                self._last_registration_time = datetime.now()
                
                self._logger.info(f"Successfully registered plugin: {plugin_name}")
                
                # 등록 이벤트 발생
                asyncio.create_task(self._emit_plugin_registered_event(plugin_name))
                
            except Exception as e:
                # 등록 실패 시 정리
                self._cleanup_failed_registration(plugin_name)
                
                # 오류 이벤트 발생
                asyncio.create_task(self._emit_plugin_error_event(plugin_name, e))
                
                raise
    
    def unregister_plugin(self, plugin_name: str) -> None:
        """
        플러그인 등록 해제
        
        Args:
            plugin_name: 해제할 플러그인 이름
            
        Raises:
            PluginNotFoundError: 플러그인을 찾을 수 없음
            PluginDependencyError: 의존성 플러그인이 존재함
        """
        with self._lock:
            # 플러그인 존재 확인
            if plugin_name not in self._plugins:
                raise PluginNotFoundError(plugin_name)
            
            try:
                # 의존성 확인 (다른 플러그인이 이 플러그인에 의존하는지)
                dependents = self._reverse_dependency_graph.get(plugin_name, set())
                if dependents:
                    raise PluginDependencyError(
                        f"Cannot unregister plugin {plugin_name}: "
                        f"plugins {list(dependents)} depend on it",
                        plugin_name=plugin_name
                    )
                
                # 플러그인 정보 조회
                plugin = self._plugins[plugin_name]
                metadata = self._plugin_metadata[plugin_name]
                
                # 플러그인 제거
                del self._plugins[plugin_name]
                del self._plugin_metadata[plugin_name]
                
                # 카테고리에서 제거
                if plugin in self._plugins_by_category[metadata.category]:
                    self._plugins_by_category[metadata.category].remove(plugin)
                
                # 의존성 그래프에서 제거
                self._remove_from_dependency_graph(plugin_name)
                
                self._logger.info(f"Successfully unregistered plugin: {plugin_name}")
                
                # 등록 해제 이벤트 발생
                asyncio.create_task(self._emit_plugin_unregistered_event(plugin_name))
                
            except Exception as e:
                # 오류 이벤트 발생
                asyncio.create_task(self._emit_plugin_error_event(plugin_name, e))
                raise
    
    def get_plugin(self, plugin_name: str) -> Optional[IPlugin]:
        """
        플러그인 조회
        
        Args:
            plugin_name: 플러그인 이름
            
        Returns:
            플러그인 인스턴스 (없으면 None)
        """
        with self._lock:
            return self._plugins.get(plugin_name)
    
    def get_all_plugins(self) -> List[IPlugin]:
        """
        모든 플러그인 조회
        
        Returns:
            모든 플러그인 목록
        """
        with self._lock:
            return list(self._plugins.values())
    
    def get_plugins_by_category(self, category: str) -> List[IPlugin]:
        """
        카테고리별 플러그인 조회
        
        Args:
            category: 플러그인 카테고리
            
        Returns:
            해당 카테고리의 플러그인 목록
        """
        with self._lock:
            return self._plugins_by_category.get(category, []).copy()
    
    def get_dependency_graph(self) -> Dict[str, List[str]]:
        """
        의존성 그래프 반환
        
        Returns:
            의존성 그래프 (딕셔너리)
        """
        with self._lock:
            return {
                plugin_name: list(dependencies)
                for plugin_name, dependencies in self._dependency_graph.items()
            }
    
    def resolve_dependencies(self, plugin_name: str) -> List[str]:
        """
        의존성 해결 순서 반환
        
        Args:
            plugin_name: 대상 플러그인 이름
            
        Returns:
            의존성 해결 순서 (로딩 순서)
            
        Raises:
            PluginNotFoundError: 플러그인을 찾을 수 없음
            PluginDependencyError: 의존성 해결 실패
        """
        with self._lock:
            if plugin_name not in self._plugins:
                raise PluginNotFoundError(plugin_name)
            
            try:
                # 토폴로지 정렬을 통한 의존성 해결
                return self._topological_sort(plugin_name)
                
            except Exception as e:
                raise PluginDependencyError(
                    f"Failed to resolve dependencies for {plugin_name}: {str(e)}",
                    plugin_name=plugin_name
                )
    
    def get_plugin_metadata(self, plugin_name: str) -> Optional[PluginMetadata]:
        """
        플러그인 메타데이터 조회
        
        Args:
            plugin_name: 플러그인 이름
            
        Returns:
            플러그인 메타데이터 (없으면 None)
        """
        with self._lock:
            return self._plugin_metadata.get(plugin_name)
    
    def get_all_plugin_names(self) -> List[str]:
        """모든 플러그인 이름 목록 반환"""
        with self._lock:
            return list(self._plugins.keys())
    
    def get_plugin_count(self) -> int:
        """등록된 플러그인 수 반환"""
        with self._lock:
            return len(self._plugins)
    
    def get_categories(self) -> List[str]:
        """등록된 플러그인 카테고리 목록 반환"""
        with self._lock:
            return list(self._plugins_by_category.keys())
    
    def is_plugin_registered(self, plugin_name: str) -> bool:
        """플러그인 등록 여부 확인"""
        with self._lock:
            return plugin_name in self._plugins
    
    def get_registry_statistics(self) -> Dict[str, Any]:
        """레지스트리 통계 반환"""
        with self._lock:
            return {
                "total_plugins": len(self._plugins),
                "categories": len(self._plugins_by_category),
                "registration_count": self._registration_count,
                "last_registration_time": self._last_registration_time.isoformat() if self._last_registration_time else None,
                "plugins_by_category": {
                    category: len(plugins)
                    for category, plugins in self._plugins_by_category.items()
                },
                "dependency_graph_size": len(self._dependency_graph)
            }
    
    def _validate_dependencies(self, plugin_name: str, dependencies: List[str]) -> None:
        """
        의존성 검증
        
        Args:
            plugin_name: 플러그인 이름
            dependencies: 의존성 목록
            
        Raises:
            PluginDependencyError: 의존성 검증 실패
        """
        missing_dependencies = []
        
        for dependency in dependencies:
            if dependency not in self._plugins:
                missing_dependencies.append(dependency)
        
        if missing_dependencies:
            raise PluginDependencyError(
                f"Missing dependencies for plugin {plugin_name}: {missing_dependencies}",
                plugin_name=plugin_name,
                missing_dependencies=missing_dependencies
            )
        
        # 순환 의존성 검사
        if self._would_create_circular_dependency(plugin_name, dependencies):
            raise PluginDependencyError(
                f"Circular dependency detected for plugin {plugin_name}",
                plugin_name=plugin_name,
                circular_dependencies=dependencies
            )
    
    def _would_create_circular_dependency(self, plugin_name: str, dependencies: List[str]) -> bool:
        """
        순환 의존성 생성 여부 확인
        
        Args:
            plugin_name: 플러그인 이름
            dependencies: 의존성 목록
            
        Returns:
            순환 의존성 생성 여부
        """
        # 임시 의존성 그래프 생성
        temp_graph = self._dependency_graph.copy()
        temp_graph[plugin_name] = set(dependencies)
        
        # DFS를 통한 순환 검사
        visited = set()
        rec_stack = set()
        
        def has_cycle(node: str) -> bool:
            if node in rec_stack:
                return True
            if node in visited:
                return False
            
            visited.add(node)
            rec_stack.add(node)
            
            for neighbor in temp_graph.get(node, []):
                if has_cycle(neighbor):
                    return True
            
            rec_stack.remove(node)
            return False
        
        return has_cycle(plugin_name)
    
    def _update_dependency_graph(self, plugin_name: str, dependencies: List[str]) -> None:
        """
        의존성 그래프 업데이트
        
        Args:
            plugin_name: 플러그인 이름
            dependencies: 의존성 목록
        """
        # 정방향 그래프 업데이트
        self._dependency_graph[plugin_name] = set(dependencies)
        
        # 역방향 그래프 업데이트
        for dependency in dependencies:
            self._reverse_dependency_graph[dependency].add(plugin_name)
    
    def _remove_from_dependency_graph(self, plugin_name: str) -> None:
        """
        의존성 그래프에서 플러그인 제거
        
        Args:
            plugin_name: 제거할 플러그인 이름
        """
        # 정방향 그래프에서 제거
        dependencies = self._dependency_graph.pop(plugin_name, set())
        
        # 역방향 그래프에서 제거
        for dependency in dependencies:
            self._reverse_dependency_graph[dependency].discard(plugin_name)
        
        # 다른 플러그인의 의존성에서도 제거
        for other_plugin, deps in self._dependency_graph.items():
            deps.discard(plugin_name)
        
        # 역방향 그래프에서 완전히 제거
        del self._reverse_dependency_graph[plugin_name]
    
    def _topological_sort(self, target_plugin: str) -> List[str]:
        """
        토폴로지 정렬을 통한 의존성 해결
        
        Args:
            target_plugin: 대상 플러그인
            
        Returns:
            정렬된 의존성 순서
        """
        # 대상 플러그인과 모든 의존성 수집
        all_plugins = set()
        queue = deque([target_plugin])
        
        while queue:
            current = queue.popleft()
            if current in all_plugins:
                continue
                
            all_plugins.add(current)
            dependencies = self._dependency_graph.get(current, set())
            queue.extend(dependencies)
        
        # 인접 리스트 구성 (대상 플러그인과 의존성만)
        graph = {}
        in_degree = {}
        
        for plugin in all_plugins:
            graph[plugin] = []
            in_degree[plugin] = 0
        
        for plugin in all_plugins:
            dependencies = self._dependency_graph.get(plugin, set())
            for dep in dependencies:
                if dep in all_plugins:
                    graph[dep].append(plugin)
                    in_degree[plugin] += 1
        
        # 토폴로지 정렬
        queue = deque([plugin for plugin in all_plugins if in_degree[plugin] == 0])
        result = []
        
        while queue:
            current = queue.popleft()
            result.append(current)
            
            for neighbor in graph[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        # 순환 의존성 검사
        if len(result) != len(all_plugins):
            raise PluginDependencyError(
                f"Circular dependency detected for plugin {target_plugin}",
                plugin_name=target_plugin
            )
        
        return result
    
    def _cleanup_failed_registration(self, plugin_name: str) -> None:
        """
        실패한 등록 정리
        
        Args:
            plugin_name: 정리할 플러그인 이름
        """
        try:
            if plugin_name in self._plugins:
                del self._plugins[plugin_name]
            
            if plugin_name in self._plugin_metadata:
                del self._plugin_metadata[plugin_name]
            
            # 카테고리에서 제거
            for category_plugins in self._plugins_by_category.values():
                category_plugins[:] = [p for p in category_plugins if p.name != plugin_name]
            
            # 의존성 그래프에서 제거
            if plugin_name in self._dependency_graph:
                del self._dependency_graph[plugin_name]
            
        except Exception as e:
            self._logger.warning(f"Failed to cleanup failed registration for {plugin_name}: {e}")
    
    # 이벤트 발생 헬퍼 메서드들
    async def _emit_plugin_registered_event(self, plugin_name: str):
        """플러그인 등록 이벤트 발생"""
        if self._event_bus:
            event = PluginRegistryEvent(
                plugin_name=plugin_name,
                registry_action="registered",
                registry_stats=self.get_registry_statistics()
            )
            await self._event_bus.publish(event)
    
    async def _emit_plugin_unregistered_event(self, plugin_name: str):
        """플러그인 등록 해제 이벤트 발생"""
        if self._event_bus:
            event = PluginRegistryEvent(
                plugin_name=plugin_name,
                registry_action="unregistered",
                registry_stats=self.get_registry_statistics()
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
    
    async def _emit_dependency_resolved_event(self, plugin_name: str, dependencies: List[str]):
        """의존성 해결 이벤트 발생"""
        if self._event_bus:
            event = PluginDependencyEvent(
                plugin_name=plugin_name,
                dependency_action="resolved",
                dependencies=dependencies
            )
            await self._event_bus.publish(event) 