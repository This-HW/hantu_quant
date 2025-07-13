"""
서비스 레지스트리 모듈

이 모듈은 서비스 등록과 관리를 위한 중앙 집중식 레지스트리를 제공합니다.
"""

from typing import Type, Dict, List, Optional, Callable, Any, Set
import threading
from dataclasses import dataclass
from .lifetime import ServiceLifetime, Lifetime, create_lifetime, LifetimeManager
from .exceptions import (
    ServiceRegistrationException, 
    ServiceNotRegisteredException,
    CircularDependencyException,
    InvalidServiceTypeException
)


@dataclass
class ServiceDescriptor:
    """서비스 설명자"""
    service_type: Type
    implementation: Type
    lifetime: ServiceLifetime
    dependencies: List[Type]
    description: str = ""
    tags: List[str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []


class ServiceRegistry:
    """서비스 레지스트리 클래스"""
    
    def __init__(self):
        self._v_services: Dict[Type, ServiceDescriptor] = {}
        self._v_factories: Dict[Type, Callable] = {}
        self._v_lifetime_manager = LifetimeManager()
        self._v_lock = threading.RLock()
        self._v_dependency_graph: Dict[Type, Set[Type]] = {}
        self._v_service_tags: Dict[str, Set[Type]] = {}
    
    def register(self, 
                service_type: Type, 
                implementation: Type = None,
                lifetime: Lifetime = Lifetime.TRANSIENT,
                dependencies: List[Type] = None,
                description: str = "",
                tags: List[str] = None) -> 'ServiceRegistry':
        """서비스 등록"""
        with self._v_lock:
            # 구현체가 지정되지 않으면 서비스 타입 자체를 구현체로 사용
            if implementation is None:
                implementation = service_type
            
            # 서비스 타입 유효성 검증
            if not self._is_valid_service_type(service_type):
                raise InvalidServiceTypeException(str(service_type))
            
            # 순환 의존성 검사
            if dependencies:
                self._check_circular_dependency(service_type, dependencies)
            
            try:
                # 생명주기 생성
                _v_service_lifetime = create_lifetime(service_type, implementation, lifetime)
                
                # 서비스 설명자 생성
                _v_descriptor = ServiceDescriptor(
                    service_type=service_type,
                    implementation=implementation,
                    lifetime=_v_service_lifetime,
                    dependencies=dependencies or [],
                    description=description,
                    tags=tags or []
                )
                
                # 서비스 등록
                self._v_services[service_type] = _v_descriptor
                self._v_lifetime_manager.add_lifetime(service_type, _v_service_lifetime)
                
                # 의존성 그래프 업데이트
                self._v_dependency_graph[service_type] = set(dependencies or [])
                
                # 태그 인덱스 업데이트
                self._update_tag_index(service_type, tags or [])
                
                return self
                
            except Exception as e:
                raise ServiceRegistrationException(
                    str(service_type),
                    f"Failed to register service: {str(e)}"
                )
    
    def register_factory(self, 
                        service_type: Type, 
                        factory: Callable,
                        dependencies: List[Type] = None,
                        description: str = "",
                        tags: List[str] = None) -> 'ServiceRegistry':
        """팩토리 함수로 서비스 등록"""
        with self._v_lock:
            if not self._is_valid_service_type(service_type):
                raise InvalidServiceTypeException(str(service_type))
            
            if dependencies:
                self._check_circular_dependency(service_type, dependencies)
            
            try:
                # 팩토리 생명주기 생성
                from .lifetime import FactoryLifetime
                _v_factory_lifetime = FactoryLifetime(service_type, factory)
                
                # 서비스 설명자 생성
                _v_descriptor = ServiceDescriptor(
                    service_type=service_type,
                    implementation=None,
                    lifetime=_v_factory_lifetime,
                    dependencies=dependencies or [],
                    description=description,
                    tags=tags or []
                )
                
                # 서비스 등록
                self._v_services[service_type] = _v_descriptor
                self._v_factories[service_type] = factory
                self._v_lifetime_manager.add_lifetime(service_type, _v_factory_lifetime)
                
                # 의존성 그래프 업데이트
                self._v_dependency_graph[service_type] = set(dependencies or [])
                
                # 태그 인덱스 업데이트
                self._update_tag_index(service_type, tags or [])
                
                return self
                
            except Exception as e:
                raise ServiceRegistrationException(
                    str(service_type),
                    f"Failed to register factory: {str(e)}"
                )
    
    def register_singleton(self,
                          service_type: Type,
                          implementation: Type = None,
                          dependencies: List[Type] = None,
                          description: str = "",
                          tags: List[str] = None) -> 'ServiceRegistry':
        """싱글톤 서비스 등록"""
        return self.register(
            service_type, 
            implementation, 
            Lifetime.SINGLETON, 
            dependencies, 
            description, 
            tags
        )
    
    def register_transient(self,
                          service_type: Type,
                          implementation: Type = None,
                          dependencies: List[Type] = None,
                          description: str = "",
                          tags: List[str] = None) -> 'ServiceRegistry':
        """일시적 서비스 등록"""
        return self.register(
            service_type, 
            implementation, 
            Lifetime.TRANSIENT, 
            dependencies, 
            description, 
            tags
        )
    
    def register_scoped(self,
                       service_type: Type,
                       implementation: Type = None,
                       dependencies: List[Type] = None,
                       description: str = "",
                       tags: List[str] = None) -> 'ServiceRegistry':
        """스코프 서비스 등록"""
        return self.register(
            service_type, 
            implementation, 
            Lifetime.SCOPED, 
            dependencies, 
            description, 
            tags
        )
    
    def unregister(self, service_type: Type) -> bool:
        """서비스 등록 해제"""
        with self._v_lock:
            if service_type in self._v_services:
                _v_descriptor = self._v_services[service_type]
                
                # 생명주기 정리
                self._v_lifetime_manager.remove_lifetime(service_type)
                
                # 서비스 제거
                del self._v_services[service_type]
                
                # 팩토리 제거
                if service_type in self._v_factories:
                    del self._v_factories[service_type]
                
                # 의존성 그래프 제거
                if service_type in self._v_dependency_graph:
                    del self._v_dependency_graph[service_type]
                
                # 태그 인덱스 제거
                self._remove_from_tag_index(service_type, _v_descriptor.tags)
                
                return True
            return False
    
    def is_registered(self, service_type: Type) -> bool:
        """서비스 등록 여부 확인"""
        return service_type in self._v_services
    
    def get_service_descriptor(self, service_type: Type) -> Optional[ServiceDescriptor]:
        """서비스 설명자 조회"""
        return self._v_services.get(service_type)
    
    def get_all_services(self) -> Dict[Type, ServiceDescriptor]:
        """모든 서비스 조회"""
        return self._v_services.copy()
    
    def get_services_by_tag(self, tag: str) -> List[Type]:
        """태그별 서비스 조회"""
        return list(self._v_service_tags.get(tag, set()))
    
    def get_service_dependencies(self, service_type: Type) -> List[Type]:
        """서비스 의존성 조회"""
        return list(self._v_dependency_graph.get(service_type, set()))
    
    def get_dependency_chain(self, service_type: Type) -> List[Type]:
        """의존성 체인 조회"""
        _v_chain = []
        _v_visited = set()
        
        def _build_chain(svc_type: Type):
            if svc_type in _v_visited:
                return
            _v_visited.add(svc_type)
            _v_chain.append(svc_type)
            
            for dep in self._v_dependency_graph.get(svc_type, set()):
                _build_chain(dep)
        
        _build_chain(service_type)
        return _v_chain
    
    def validate_dependencies(self) -> List[str]:
        """의존성 유효성 검증"""
        _v_errors = []
        
        for service_type, dependencies in self._v_dependency_graph.items():
            for dependency in dependencies:
                if not self.is_registered(dependency):
                    _v_errors.append(
                        f"Service '{service_type}' depends on unregistered service '{dependency}'"
                    )
        
        return _v_errors
    
    def get_lifecycle_stats(self) -> Dict[str, int]:
        """생명주기 통계 조회"""
        return self._v_lifetime_manager.get_lifetime_stats()
    
    def dispose(self):
        """레지스트리 정리"""
        with self._v_lock:
            self._v_lifetime_manager.dispose_all()
            self._v_services.clear()
            self._v_factories.clear()
            self._v_dependency_graph.clear()
            self._v_service_tags.clear()
    
    def _is_valid_service_type(self, service_type: Type) -> bool:
        """서비스 타입 유효성 검증"""
        return isinstance(service_type, type) or hasattr(service_type, '__abstractmethods__')
    
    def _check_circular_dependency(self, service_type: Type, dependencies: List[Type]):
        """순환 의존성 검사"""
        def _has_circular_dependency(current_type: Type, visited: Set[Type], path: List[Type]) -> bool:
            if current_type in visited:
                # 순환 의존성 발견
                _v_cycle_start = path.index(current_type)
                _v_cycle = path[_v_cycle_start:] + [current_type]
                raise CircularDependencyException([str(t) for t in _v_cycle])
            
            visited.add(current_type)
            path.append(current_type)
            
            for dep in self._v_dependency_graph.get(current_type, set()):
                if _has_circular_dependency(dep, visited.copy(), path.copy()):
                    return True
            
            return False
        
        for dependency in dependencies:
            if dependency == service_type:
                raise CircularDependencyException([str(service_type), str(dependency)])
            
            _has_circular_dependency(dependency, set(), [service_type])
    
    def _update_tag_index(self, service_type: Type, tags: List[str]):
        """태그 인덱스 업데이트"""
        for tag in tags:
            if tag not in self._v_service_tags:
                self._v_service_tags[tag] = set()
            self._v_service_tags[tag].add(service_type)
    
    def _remove_from_tag_index(self, service_type: Type, tags: List[str]):
        """태그 인덱스에서 제거"""
        for tag in tags:
            if tag in self._v_service_tags:
                self._v_service_tags[tag].discard(service_type)
                if not self._v_service_tags[tag]:
                    del self._v_service_tags[tag]
    
    def __str__(self) -> str:
        return f"ServiceRegistry(services={len(self._v_services)})"
    
    def __repr__(self) -> str:
        return self.__str__() 