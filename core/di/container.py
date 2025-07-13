"""
서비스 컨테이너 모듈

이 모듈은 의존성 주입 시스템의 핵심인 서비스 컨테이너를 구현합니다.
"""

import inspect
from typing import Type, TypeVar, Dict, List, Optional, Any, Set, Callable, Union
import threading
from contextlib import contextmanager
from .registry import ServiceRegistry, ServiceDescriptor
from .lifetime import Lifetime
from .exceptions import (
    ServiceNotRegisteredException,
    ServiceResolutionException,
    CircularDependencyException,
    DependencyInjectionError
)

T = TypeVar('T')


class ServiceScope:
    """서비스 스코프 클래스"""
    
    def __init__(self, parent_scope: Optional['ServiceScope'] = None):
        self._v_parent_scope = parent_scope
        self._v_services: Dict[Type, Any] = {}
        self._v_lock = threading.Lock()
        self._v_is_disposed = False
    
    def get_service(self, service_type: Type) -> Optional[Any]:
        """스코프 내 서비스 조회"""
        with self._v_lock:
            if self._v_is_disposed:
                return None
            
            # 현재 스코프에서 찾기
            if service_type in self._v_services:
                return self._v_services[service_type]
            
            # 부모 스코프에서 찾기
            if self._v_parent_scope:
                return self._v_parent_scope.get_service(service_type)
            
            return None
    
    def set_service(self, service_type: Type, instance: Any):
        """스코프 내 서비스 설정"""
        with self._v_lock:
            if not self._v_is_disposed:
                self._v_services[service_type] = instance
    
    def dispose(self):
        """스코프 정리"""
        with self._v_lock:
            for instance in self._v_services.values():
                if hasattr(instance, 'dispose'):
                    try:
                        instance.dispose()
                    except Exception:
                        pass  # 정리 중 오류는 무시
            self._v_services.clear()
            self._v_is_disposed = True
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.dispose()


class ServiceContainer:
    """서비스 컨테이너 클래스"""
    
    def __init__(self):
        self._v_registry = ServiceRegistry()
        self._v_lock = threading.RLock()
        self._v_resolution_stack: Set[Type] = set()
        self._v_current_scope = ServiceScope()
        self._v_scope_stack: List[ServiceScope] = [self._v_current_scope]
        self._v_is_disposed = False
    
    def register(self, 
                service_type: Type[T], 
                implementation: Type[T] = None,
                lifetime: Lifetime = Lifetime.TRANSIENT,
                dependencies: List[Type] = None,
                description: str = "",
                tags: List[str] = None) -> 'ServiceContainer':
        """서비스 등록"""
        self._v_registry.register(
            service_type, 
            implementation, 
            lifetime, 
            dependencies, 
            description, 
            tags
        )
        return self
    
    def register_singleton(self,
                          service_type: Type[T],
                          implementation: Type[T] = None,
                          dependencies: List[Type] = None,
                          description: str = "",
                          tags: List[str] = None) -> 'ServiceContainer':
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
                          service_type: Type[T],
                          implementation: Type[T] = None,
                          dependencies: List[Type] = None,
                          description: str = "",
                          tags: List[str] = None) -> 'ServiceContainer':
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
                       service_type: Type[T],
                       implementation: Type[T] = None,
                       dependencies: List[Type] = None,
                       description: str = "",
                       tags: List[str] = None) -> 'ServiceContainer':
        """스코프 서비스 등록"""
        return self.register(
            service_type, 
            implementation, 
            Lifetime.SCOPED, 
            dependencies, 
            description, 
            tags
        )
    
    def register_factory(self,
                        service_type: Type[T],
                        factory: Callable[['ServiceContainer'], T],
                        dependencies: List[Type] = None,
                        description: str = "",
                        tags: List[str] = None) -> 'ServiceContainer':
        """팩토리 함수로 서비스 등록"""
        self._v_registry.register_factory(
            service_type, 
            factory, 
            dependencies, 
            description, 
            tags
        )
        return self
    
    def register_instance(self,
                         service_type: Type[T],
                         instance: T,
                         description: str = "",
                         tags: List[str] = None) -> 'ServiceContainer':
        """인스턴스 직접 등록"""
        def _instance_factory(container: 'ServiceContainer') -> T:
            return instance
        
        return self.register_factory(
            service_type, 
            _instance_factory, 
            description=description, 
            tags=tags
        )
    
    def resolve(self, service_type: Type[T]) -> T:
        """서비스 해결"""
        if self._v_is_disposed:
            raise DependencyInjectionError("Container has been disposed")
        
        with self._v_lock:
            # 순환 의존성 검사
            if service_type in self._v_resolution_stack:
                _v_cycle = list(self._v_resolution_stack) + [service_type]
                raise CircularDependencyException([str(t) for t in _v_cycle])
            
            # 서비스 등록 확인
            if not self._v_registry.is_registered(service_type):
                raise ServiceNotRegisteredException(str(service_type))
            
            try:
                self._v_resolution_stack.add(service_type)
                return self._resolve_service(service_type)
            finally:
                self._v_resolution_stack.discard(service_type)
    
    def resolve_all(self, service_type: Type[T]) -> List[T]:
        """태그된 모든 서비스 해결"""
        _v_instances = []
        _v_descriptors = self._v_registry.get_all_services()
        
        for descriptor in _v_descriptors.values():
            if descriptor.service_type == service_type:
                _v_instances.append(self.resolve(service_type))
        
        return _v_instances
    
    def try_resolve(self, service_type: Type[T]) -> Optional[T]:
        """서비스 해결 시도 (실패 시 None 반환)"""
        try:
            return self.resolve(service_type)
        except Exception:
            return None
    
    def is_registered(self, service_type: Type) -> bool:
        """서비스 등록 여부 확인"""
        return self._v_registry.is_registered(service_type)
    
    def get_service_descriptor(self, service_type: Type) -> Optional[ServiceDescriptor]:
        """서비스 설명자 조회"""
        return self._v_registry.get_service_descriptor(service_type)
    
    def get_all_services(self) -> Dict[Type, ServiceDescriptor]:
        """모든 서비스 조회"""
        return self._v_registry.get_all_services()
    
    def get_services_by_tag(self, tag: str) -> List[Type]:
        """태그별 서비스 조회"""
        return self._v_registry.get_services_by_tag(tag)
    
    def unregister(self, service_type: Type) -> bool:
        """서비스 등록 해제"""
        return self._v_registry.unregister(service_type)
    
    def validate_dependencies(self) -> List[str]:
        """의존성 유효성 검증"""
        return self._v_registry.validate_dependencies()
    
    @contextmanager
    def create_scope(self):
        """새로운 스코프 생성"""
        _v_new_scope = ServiceScope(self._v_current_scope)
        self._v_scope_stack.append(_v_new_scope)
        _v_old_scope = self._v_current_scope
        self._v_current_scope = _v_new_scope
        
        try:
            yield _v_new_scope
        finally:
            self._v_current_scope = _v_old_scope
            self._v_scope_stack.pop()
            _v_new_scope.dispose()
    
    def get_current_scope(self) -> ServiceScope:
        """현재 스코프 조회"""
        return self._v_current_scope
    
    def dispose(self):
        """컨테이너 정리"""
        with self._v_lock:
            if not self._v_is_disposed:
                # 모든 스코프 정리
                for scope in self._v_scope_stack:
                    scope.dispose()
                self._v_scope_stack.clear()
                
                # 레지스트리 정리
                self._v_registry.dispose()
                
                self._v_is_disposed = True
    
    def _resolve_service(self, service_type: Type) -> Any:
        """서비스 해결 내부 메서드"""
        _v_descriptor = self._v_registry.get_service_descriptor(service_type)
        if not _v_descriptor:
            raise ServiceNotRegisteredException(str(service_type))
        
        try:
            return _v_descriptor.lifetime.get_instance(self)
        except Exception as e:
            raise ServiceResolutionException(str(service_type), e)
    
    def _create_instance(self, implementation: Type, **kwargs) -> Any:
        """인스턴스 생성 내부 메서드"""
        if implementation is None:
            raise DependencyInjectionError("Implementation cannot be None")
        
        # 생성자 의존성 해결
        _v_constructor_args = self._resolve_constructor_dependencies(implementation)
        
        try:
            return implementation(**_v_constructor_args, **kwargs)
        except Exception as e:
            raise DependencyInjectionError(
                f"Failed to create instance of {implementation}: {str(e)}",
                str(implementation)
            )
    
    def _resolve_constructor_dependencies(self, implementation: Type) -> Dict[str, Any]:
        """생성자 의존성 해결"""
        _v_constructor_args = {}
        
        # 생성자 시그니처 분석
        try:
            _v_signature = inspect.signature(implementation.__init__)
            _v_parameters = _v_signature.parameters
            
            for param_name, param in _v_parameters.items():
                if param_name == 'self':
                    continue
                
                # 타입 힌트가 있는 경우 의존성 주입
                if param.annotation != inspect.Parameter.empty:
                    if self.is_registered(param.annotation):
                        _v_constructor_args[param_name] = self.resolve(param.annotation)
                    elif param.default == inspect.Parameter.empty:
                        # 필수 파라미터인데 등록되지 않은 경우
                        raise DependencyInjectionError(
                            f"Required dependency '{param.annotation}' for parameter '{param_name}' is not registered",
                            str(implementation)
                        )
                
        except Exception as e:
            if not isinstance(e, DependencyInjectionError):
                raise DependencyInjectionError(
                    f"Failed to resolve constructor dependencies for {implementation}: {str(e)}",
                    str(implementation)
                )
            raise
        
        return _v_constructor_args
    
    def get_container_stats(self) -> Dict[str, Any]:
        """컨테이너 통계 조회"""
        return {
            'registered_services': len(self._v_registry.get_all_services()),
            'lifecycle_stats': self._v_registry.get_lifecycle_stats(),
            'active_scopes': len(self._v_scope_stack),
            'dependency_errors': len(self.validate_dependencies())
        }
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.dispose()
    
    def __str__(self) -> str:
        return f"ServiceContainer(services={len(self._v_registry.get_all_services())})"
    
    def __repr__(self) -> str:
        return self.__str__() 