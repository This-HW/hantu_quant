"""
의존성 주입기 모듈

이 모듈은 의존성 주입을 위한 편의 기능들을 제공합니다.
"""

import functools
import inspect
from typing import Type, TypeVar, Callable, Any, Dict, Optional, List
from .container import ServiceContainer
from .lifetime import Lifetime

T = TypeVar('T')


class DependencyInjector:
    """의존성 주입기 클래스"""
    
    def __init__(self, container: ServiceContainer):
        self._v_container = container
    
    def inject(self, func: Callable[..., T]) -> Callable[..., T]:
        """함수에 의존성 주입 데코레이터"""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # 함수 시그니처 분석
            _v_signature = inspect.signature(func)
            _v_bound_args = _v_signature.bind_partial(*args, **kwargs)
            _v_bound_args.apply_defaults()
            
            # 의존성 주입
            for param_name, param in _v_signature.parameters.items():
                if param_name not in _v_bound_args.arguments:
                    # 타입 힌트가 있고 등록된 서비스인 경우 주입
                    if param.annotation != inspect.Parameter.empty:
                        if self._v_container.is_registered(param.annotation):
                            _v_bound_args.arguments[param_name] = self._v_container.resolve(param.annotation)
            
            return func(*_v_bound_args.args, **_v_bound_args.kwargs)
        
        return wrapper
    
    def auto_wire(self, cls: Type[T]) -> Type[T]:
        """클래스에 자동 의존성 주입 데코레이터"""
        _v_original_init = cls.__init__
        
        @functools.wraps(_v_original_init)
        def new_init(self, *args, **kwargs):
            # 생성자 시그니처 분석
            _v_signature = inspect.signature(_v_original_init)
            _v_bound_args = _v_signature.bind_partial(self, *args, **kwargs)
            _v_bound_args.apply_defaults()
            
            # 의존성 주입
            for param_name, param in _v_signature.parameters.items():
                if param_name == 'self':
                    continue
                
                if param_name not in _v_bound_args.arguments:
                    # 타입 힌트가 있고 등록된 서비스인 경우 주입
                    if param.annotation != inspect.Parameter.empty:
                        if self._v_container.is_registered(param.annotation):
                            _v_bound_args.arguments[param_name] = self._v_container.resolve(param.annotation)
            
            _v_original_init(*_v_bound_args.args, **_v_bound_args.kwargs)
        
        cls.__init__ = new_init
        return cls
    
    def resolve(self, service_type: Type[T]) -> T:
        """서비스 해결"""
        return self._v_container.resolve(service_type)
    
    def try_resolve(self, service_type: Type[T]) -> Optional[T]:
        """서비스 해결 시도"""
        return self._v_container.try_resolve(service_type)


# 전역 의존성 주입기
_global_container: Optional[ServiceContainer] = None
_global_injector: Optional[DependencyInjector] = None


def set_global_container(container: ServiceContainer):
    """전역 컨테이너 설정"""
    global _global_container, _global_injector
    _global_container = container
    _global_injector = DependencyInjector(container)


def get_global_container() -> ServiceContainer:
    """전역 컨테이너 조회"""
    global _global_container
    if _global_container is None:
        _global_container = ServiceContainer()
        set_global_container(_global_container)
    return _global_container


def get_global_injector() -> DependencyInjector:
    """전역 주입기 조회"""
    global _global_injector
    if _global_injector is None:
        _global_injector = DependencyInjector(get_global_container())
    return _global_injector


# 편의 데코레이터들
def inject(func: Callable[..., T]) -> Callable[..., T]:
    """전역 의존성 주입 데코레이터"""
    return get_global_injector().inject(func)


def auto_wire(cls: Type[T]) -> Type[T]:
    """전역 자동 의존성 주입 데코레이터"""
    return get_global_injector().auto_wire(cls)


def resolve(service_type: Type[T]) -> T:
    """전역 서비스 해결"""
    return get_global_container().resolve(service_type)


def try_resolve(service_type: Type[T]) -> Optional[T]:
    """전역 서비스 해결 시도"""
    return get_global_container().try_resolve(service_type)


def register(service_type: Type[T], 
            implementation: Type[T] = None,
            lifetime: Lifetime = Lifetime.TRANSIENT,
            dependencies: List[Type] = None,
            description: str = "",
            tags: List[str] = None) -> ServiceContainer:
    """전역 서비스 등록"""
    return get_global_container().register(
        service_type, 
        implementation, 
        lifetime, 
        dependencies, 
        description, 
        tags
    )


def register_singleton(service_type: Type[T],
                      implementation: Type[T] = None,
                      dependencies: List[Type] = None,
                      description: str = "",
                      tags: List[str] = None) -> ServiceContainer:
    """전역 싱글톤 서비스 등록"""
    return get_global_container().register_singleton(
        service_type, 
        implementation, 
        dependencies, 
        description, 
        tags
    )


def register_transient(service_type: Type[T],
                      implementation: Type[T] = None,
                      dependencies: List[Type] = None,
                      description: str = "",
                      tags: List[str] = None) -> ServiceContainer:
    """전역 일시적 서비스 등록"""
    return get_global_container().register_transient(
        service_type, 
        implementation, 
        dependencies, 
        description, 
        tags
    )


def register_scoped(service_type: Type[T],
                   implementation: Type[T] = None,
                   dependencies: List[Type] = None,
                   description: str = "",
                   tags: List[str] = None) -> ServiceContainer:
    """전역 스코프 서비스 등록"""
    return get_global_container().register_scoped(
        service_type, 
        implementation, 
        dependencies, 
        description, 
        tags
    )


def register_factory(service_type: Type[T],
                    factory: Callable[[ServiceContainer], T],
                    dependencies: List[Type] = None,
                    description: str = "",
                    tags: List[str] = None) -> ServiceContainer:
    """전역 팩토리 서비스 등록"""
    return get_global_container().register_factory(
        service_type, 
        factory, 
        dependencies, 
        description, 
        tags
    )


def register_instance(service_type: Type[T],
                     instance: T,
                     description: str = "",
                     tags: List[str] = None) -> ServiceContainer:
    """전역 인스턴스 등록"""
    return get_global_container().register_instance(
        service_type, 
        instance, 
        description, 
        tags
    )


# 서비스 등록 데코레이터
def service(service_type: Type = None,
           lifetime: Lifetime = Lifetime.TRANSIENT,
           dependencies: List[Type] = None,
           description: str = "",
           tags: List[str] = None):
    """서비스 등록 데코레이터"""
    def decorator(cls: Type[T]) -> Type[T]:
        _v_service_type = service_type or cls
        get_global_container().register(
            _v_service_type, 
            cls, 
            lifetime, 
            dependencies, 
            description, 
            tags
        )
        return cls
    return decorator


def singleton(service_type: Type = None,
             dependencies: List[Type] = None,
             description: str = "",
             tags: List[str] = None):
    """싱글톤 서비스 등록 데코레이터"""
    return service(service_type, Lifetime.SINGLETON, dependencies, description, tags)


def transient(service_type: Type = None,
             dependencies: List[Type] = None,
             description: str = "",
             tags: List[str] = None):
    """일시적 서비스 등록 데코레이터"""
    return service(service_type, Lifetime.TRANSIENT, dependencies, description, tags)


def scoped(service_type: Type = None,
          dependencies: List[Type] = None,
          description: str = "",
          tags: List[str] = None):
    """스코프 서비스 등록 데코레이터"""
    return service(service_type, Lifetime.SCOPED, dependencies, description, tags)


def configure_services(config_func: Callable[[ServiceContainer], None]):
    """서비스 설정 함수"""
    config_func(get_global_container())


# 유틸리티 함수들
def is_registered(service_type: Type) -> bool:
    """서비스 등록 여부 확인"""
    return get_global_container().is_registered(service_type)


def get_service_info(service_type: Type) -> Optional[Dict[str, Any]]:
    """서비스 정보 조회"""
    _v_descriptor = get_global_container().get_service_descriptor(service_type)
    if _v_descriptor:
        return {
            'service_type': _v_descriptor.service_type,
            'implementation': _v_descriptor.implementation,
            'lifetime': _v_descriptor.lifetime.get_lifetime_type().value,
            'dependencies': _v_descriptor.dependencies,
            'description': _v_descriptor.description,
            'tags': _v_descriptor.tags
        }
    return None


def get_container_stats() -> Dict[str, Any]:
    """컨테이너 통계 조회"""
    return get_global_container().get_container_stats()


def validate_container() -> List[str]:
    """컨테이너 유효성 검증"""
    return get_global_container().validate_dependencies()


def reset_container():
    """컨테이너 초기화"""
    global _global_container, _global_injector
    if _global_container:
        _global_container.dispose()
    _global_container = None
    _global_injector = None 