"""
모듈 레지스트리 구현

이 모듈은 모듈 레지스트리 시스템의 핵심 구현 클래스를 포함합니다.
"""

import threading
from typing import Dict, List, Optional, Tuple, Any, Set
from collections import defaultdict
import logging

from .interfaces import (
    IModuleRegistry, IModuleMetadata, ModuleType, ModuleStatus
)
from .exceptions import (
    ModuleAlreadyRegisteredError, ModuleNotFoundError, ModuleNotRegisteredError,
    InvalidModuleMetadataError, DependencyError, CircularDependencyError,
    UnresolvedDependencyError, RegistryLockError
)

logger = logging.getLogger(__name__)


class ModuleRegistry(IModuleRegistry):
    """모듈 레지스트리 구현 클래스"""
    
    def __init__(self):
        """초기화"""
        self._modules: Dict[str, IModuleMetadata] = {}
        self._lock = threading.RLock()
        self._listeners: Dict[str, List[callable]] = defaultdict(list)
        self._dependency_graph: Dict[str, Set[str]] = defaultdict(set)
        self._reverse_dependency_graph: Dict[str, Set[str]] = defaultdict(set)
        self._initialized = False
        
        # 통계 정보
        self._stats = {
            'total_modules': 0,
            'active_modules': 0,
            'error_modules': 0,
            'registrations': 0,
            'unregistrations': 0
        }
        
        logger.info("ModuleRegistry initialized")
    
    def register_module(self, metadata: IModuleMetadata) -> bool:
        """모듈 등록"""
        with self._lock:
            try:
                # 기존 모듈 존재 확인
                if metadata.name in self._modules:
                    raise ModuleAlreadyRegisteredError(metadata.name)
                
                # 메타데이터 검증
                self._validate_metadata(metadata)
                
                # 의존성 검증
                self._validate_dependencies(metadata)
                
                # 모듈 등록
                self._modules[metadata.name] = metadata
                metadata.update_status(ModuleStatus.REGISTERED)
                
                # 의존성 그래프 업데이트
                self._update_dependency_graph(metadata)
                
                # 통계 업데이트
                self._stats['total_modules'] += 1
                self._stats['registrations'] += 1
                
                # 이벤트 발생
                self._emit_event('module_registered', metadata)
                
                logger.info(f"Module '{metadata.name}' registered successfully")
                return True
                
            except Exception as e:
                logger.error(f"Failed to register module '{metadata.name}': {e}")
                raise
    
    def unregister_module(self, module_name: str) -> bool:
        """모듈 해제"""
        with self._lock:
            try:
                # 모듈 존재 확인
                if module_name not in self._modules:
                    raise ModuleNotFoundError(module_name)
                
                metadata = self._modules[module_name]
                
                # 의존성 확인 (다른 모듈들이 이 모듈을 의존하고 있는지)
                dependent_modules = self._get_dependent_modules(module_name)
                if dependent_modules:
                    raise DependencyError(
                        f"Cannot unregister module '{module_name}' because it's used by: {', '.join(dependent_modules)}",
                        module_name
                    )
                
                # 모듈 해제
                del self._modules[module_name]
                
                # 의존성 그래프 업데이트
                self._remove_from_dependency_graph(module_name)
                
                # 통계 업데이트
                self._stats['total_modules'] -= 1
                self._stats['unregistrations'] += 1
                
                # 이벤트 발생
                self._emit_event('module_unregistered', metadata)
                
                logger.info(f"Module '{module_name}' unregistered successfully")
                return True
                
            except Exception as e:
                logger.error(f"Failed to unregister module '{module_name}': {e}")
                raise
    
    def get_module(self, module_name: str) -> Optional[IModuleMetadata]:
        """모듈 조회"""
        with self._lock:
            return self._modules.get(module_name)
    
    def list_modules(self, module_type: Optional[ModuleType] = None, 
                    status: Optional[ModuleStatus] = None) -> List[IModuleMetadata]:
        """모듈 목록 조회"""
        with self._lock:
            modules = list(self._modules.values())
            
            # 타입 필터링
            if module_type:
                modules = [m for m in modules if m.module_type == module_type]
            
            # 상태 필터링
            if status:
                modules = [m for m in modules if m.status == status]
            
            return modules
    
    def has_module(self, module_name: str) -> bool:
        """모듈 존재 여부 확인"""
        with self._lock:
            return module_name in self._modules
    
    def update_module_status(self, module_name: str, status: ModuleStatus) -> bool:
        """모듈 상태 업데이트"""
        with self._lock:
            try:
                if module_name not in self._modules:
                    raise ModuleNotFoundError(module_name)
                
                metadata = self._modules[module_name]
                old_status = metadata.status
                metadata.update_status(status)
                
                # 통계 업데이트
                self._update_status_stats(old_status, status)
                
                # 이벤트 발생
                self._emit_event('module_status_changed', metadata, {
                    'old_status': old_status,
                    'new_status': status
                })
                
                logger.debug(f"Module '{module_name}' status updated: {old_status} -> {status}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to update module '{module_name}' status: {e}")
                raise
    
    def validate_dependencies(self, module_name: str) -> Tuple[bool, List[str]]:
        """의존성 검증"""
        with self._lock:
            try:
                if module_name not in self._modules:
                    raise ModuleNotFoundError(module_name)
                
                metadata = self._modules[module_name]
                errors = []
                
                # 각 의존성 검증
                for dependency in metadata.dependencies:
                    dep_name = dependency.module_name
                    
                    # 의존성 모듈 존재 확인
                    if dep_name not in self._modules:
                        if not dependency.optional:
                            errors.append(f"Required dependency '{dep_name}' not found")
                        continue
                    
                    # 버전 호환성 검증
                    dep_metadata = self._modules[dep_name]
                    if not self._is_version_compatible(dependency.version_constraint, 
                                                     dep_metadata.version):
                        errors.append(f"Incompatible version for '{dep_name}'")
                
                return len(errors) == 0, errors
                
            except Exception as e:
                logger.error(f"Failed to validate dependencies for '{module_name}': {e}")
                raise
    
    def get_module_graph(self) -> Dict[str, List[str]]:
        """모듈 의존성 그래프 생성"""
        with self._lock:
            graph = {}
            for module_name, dependencies in self._dependency_graph.items():
                graph[module_name] = list(dependencies)
            return graph
    
    def clear(self) -> None:
        """레지스트리 초기화"""
        with self._lock:
            self._modules.clear()
            self._dependency_graph.clear()
            self._reverse_dependency_graph.clear()
            self._stats = {
                'total_modules': 0,
                'active_modules': 0,
                'error_modules': 0,
                'registrations': 0,
                'unregistrations': 0
            }
            
            # 이벤트 발생
            self._emit_event('registry_cleared')
            
            logger.info("Module registry cleared")
    
    def get_statistics(self) -> Dict[str, Any]:
        """통계 정보 조회"""
        with self._lock:
            # 현재 상태 기반 통계 업데이트
            active_count = sum(1 for m in self._modules.values() if m.status == ModuleStatus.ACTIVE)
            error_count = sum(1 for m in self._modules.values() if m.status == ModuleStatus.ERROR)
            
            stats = self._stats.copy()
            stats['active_modules'] = active_count
            stats['error_modules'] = error_count
            
            # 타입별 통계
            type_stats = defaultdict(int)
            for module in self._modules.values():
                type_stats[module.module_type.value] += 1
            stats['modules_by_type'] = dict(type_stats)
            
            return stats
    
    def add_listener(self, event_type: str, listener: callable) -> None:
        """이벤트 리스너 추가"""
        with self._lock:
            self._listeners[event_type].append(listener)
    
    def remove_listener(self, event_type: str, listener: callable) -> None:
        """이벤트 리스너 제거"""
        with self._lock:
            if event_type in self._listeners:
                try:
                    self._listeners[event_type].remove(listener)
                except ValueError:
                    pass
    
    def _validate_metadata(self, metadata: IModuleMetadata) -> None:
        """메타데이터 검증"""
        if not metadata.name or not metadata.name.strip():
            raise InvalidModuleMetadataError(metadata.name or "Unknown", ["Module name is required"])
        
        if not metadata.version:
            raise InvalidModuleMetadataError(metadata.name, ["Module version is required"])
        
        if not metadata.module_type:
            raise InvalidModuleMetadataError(metadata.name, ["Module type is required"])
    
    def _validate_dependencies(self, metadata: IModuleMetadata) -> None:
        """의존성 검증"""
        for dependency in metadata.dependencies:
            dep_name = dependency.module_name
            
            # 자기 자신을 의존하는지 확인
            if dep_name == metadata.name:
                raise CircularDependencyError([metadata.name])
            
            # 필수 의존성이 존재하는지 확인
            if not dependency.optional and dep_name not in self._modules:
                raise UnresolvedDependencyError(metadata.name, dep_name)
        
        # 순환 의존성 검사
        self._check_circular_dependencies(metadata)
    
    def _check_circular_dependencies(self, metadata: IModuleMetadata) -> None:
        """순환 의존성 검사"""
        visited = set()
        path = []
        
        def dfs(module_name: str) -> None:
            if module_name in path:
                cycle_start = path.index(module_name)
                cycle = path[cycle_start:] + [module_name]
                raise CircularDependencyError(cycle)
            
            if module_name in visited:
                return
            
            visited.add(module_name)
            path.append(module_name)
            
            if module_name in self._modules:
                for dep in self._modules[module_name].dependencies:
                    if not dep.optional:
                        dfs(dep.module_name)
            
            path.pop()
        
        # 새로운 모듈의 의존성에서 시작
        for dependency in metadata.dependencies:
            if not dependency.optional:
                dfs(dependency.module_name)
    
    def _update_dependency_graph(self, metadata: IModuleMetadata) -> None:
        """의존성 그래프 업데이트"""
        module_name = metadata.name
        
        # 직접 의존성 추가
        dependencies = set()
        for dep in metadata.dependencies:
            dependencies.add(dep.module_name)
            self._reverse_dependency_graph[dep.module_name].add(module_name)
        
        self._dependency_graph[module_name] = dependencies
    
    def _remove_from_dependency_graph(self, module_name: str) -> None:
        """의존성 그래프에서 모듈 제거"""
        # 직접 의존성 제거
        if module_name in self._dependency_graph:
            dependencies = self._dependency_graph[module_name]
            for dep in dependencies:
                self._reverse_dependency_graph[dep].discard(module_name)
            del self._dependency_graph[module_name]
        
        # 역 의존성 제거
        if module_name in self._reverse_dependency_graph:
            dependents = self._reverse_dependency_graph[module_name]
            for dependent in dependents:
                self._dependency_graph[dependent].discard(module_name)
            del self._reverse_dependency_graph[module_name]
    
    def _get_dependent_modules(self, module_name: str) -> List[str]:
        """의존 모듈 목록 조회"""
        return list(self._reverse_dependency_graph.get(module_name, set()))
    
    def _is_version_compatible(self, constraint: Optional[str], version) -> bool:
        """버전 호환성 확인"""
        if not constraint:
            return True
        
        # 간단한 버전 제약 확인 (실제로는 더 복잡한 로직이 필요)
        # 예: ">=1.0.0,<2.0.0"
        try:
            # 여기서는 간단한 구현만 제공
            return True
        except Exception:
            return False
    
    def _update_status_stats(self, old_status: ModuleStatus, new_status: ModuleStatus) -> None:
        """상태 변경에 따른 통계 업데이트"""
        if old_status == ModuleStatus.ACTIVE and new_status != ModuleStatus.ACTIVE:
            self._stats['active_modules'] -= 1
        elif old_status != ModuleStatus.ACTIVE and new_status == ModuleStatus.ACTIVE:
            self._stats['active_modules'] += 1
        
        if old_status == ModuleStatus.ERROR and new_status != ModuleStatus.ERROR:
            self._stats['error_modules'] -= 1
        elif old_status != ModuleStatus.ERROR and new_status == ModuleStatus.ERROR:
            self._stats['error_modules'] += 1
    
    def _emit_event(self, event_type: str, metadata: Optional[IModuleMetadata] = None, 
                   extra_data: Optional[Dict[str, Any]] = None) -> None:
        """이벤트 발생"""
        listeners = self._listeners.get(event_type, [])
        for listener in listeners:
            try:
                if metadata:
                    listener(event_type, metadata, extra_data or {})
                else:
                    listener(event_type, extra_data or {})
            except Exception as e:
                logger.error(f"Error in event listener for '{event_type}': {e}")
    
    def get_modules_by_type(self, module_type: ModuleType) -> List[IModuleMetadata]:
        """타입별 모듈 조회"""
        return self.list_modules(module_type=module_type)
    
    def get_modules_by_status(self, status: ModuleStatus) -> List[IModuleMetadata]:
        """상태별 모듈 조회"""
        return self.list_modules(status=status)
    
    def get_active_modules(self) -> List[IModuleMetadata]:
        """활성 모듈 조회"""
        return self.get_modules_by_status(ModuleStatus.ACTIVE)
    
    def get_error_modules(self) -> List[IModuleMetadata]:
        """오류 모듈 조회"""
        return self.get_modules_by_status(ModuleStatus.ERROR)
    
    def find_modules_by_interface(self, interface_name: str) -> List[IModuleMetadata]:
        """인터페이스를 제공하는 모듈 조회"""
        with self._lock:
            modules = []
            for module in self._modules.values():
                if module.has_interface(interface_name):
                    modules.append(module)
            return modules
    
    def find_modules_using_interface(self, interface_name: str) -> List[IModuleMetadata]:
        """인터페이스를 사용하는 모듈 조회"""
        with self._lock:
            modules = []
            for module in self._modules.values():
                if module.uses_interface(interface_name):
                    modules.append(module)
            return modules
    
    def get_dependency_chain(self, module_name: str) -> List[str]:
        """의존성 체인 조회"""
        with self._lock:
            if module_name not in self._modules:
                return []
            
            chain = []
            visited = set()
            
            def build_chain(name: str) -> None:
                if name in visited:
                    return
                visited.add(name)
                chain.append(name)
                
                if name in self._dependency_graph:
                    for dep in self._dependency_graph[name]:
                        build_chain(dep)
            
            build_chain(module_name)
            return chain
    
    def validate_all_dependencies(self) -> Dict[str, List[str]]:
        """모든 모듈의 의존성 검증"""
        with self._lock:
            validation_results = {}
            
            for module_name in self._modules:
                try:
                    is_valid, errors = self.validate_dependencies(module_name)
                    if not is_valid:
                        validation_results[module_name] = errors
                except Exception as e:
                    validation_results[module_name] = [str(e)]
            
            return validation_results
    
    def __str__(self) -> str:
        """문자열 표현"""
        return f"ModuleRegistry(modules={len(self._modules)})"
    
    def __repr__(self) -> str:
        """상세 문자열 표현"""
        return f"ModuleRegistry(modules={len(self._modules)}, stats={self._stats})" 