"""
서비스 생명주기 관리 모듈

이 모듈은 서비스 인스턴스의 생명주기를 관리하는 클래스들을 정의합니다.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Type, Optional, Callable
from enum import Enum
import threading
import weakref
from .exceptions import ServiceLifetimeException


class Lifetime(Enum):
    """서비스 생명주기 타입"""
    SINGLETON = "singleton"     # 싱글톤 - 하나의 인스턴스만 생성
    TRANSIENT = "transient"     # 일시적 - 요청할 때마다 새 인스턴스 생성
    SCOPED = "scoped"           # 스코프 - 스코프 내에서는 같은 인스턴스


class ServiceLifetime(ABC):
    """서비스 생명주기 기본 클래스"""
    
    def __init__(self, service_type: Type, implementation: Type):
        self.service_type = service_type
        self.implementation = implementation
        self._v_lock = threading.Lock()
    
    @abstractmethod
    def get_instance(self, container, **kwargs) -> Any:
        """인스턴스 반환"""
        pass
    
    @abstractmethod
    def dispose(self):
        """리소스 정리"""
        pass
    
    @abstractmethod
    def get_lifetime_type(self) -> Lifetime:
        """생명주기 타입 반환"""
        pass


class SingletonLifetime(ServiceLifetime):
    """싱글톤 생명주기 관리"""
    
    def __init__(self, service_type: Type, implementation: Type):
        super().__init__(service_type, implementation)
        self._v_instance = None
        self._v_is_disposed = False
    
    def get_instance(self, container, **kwargs) -> Any:
        """싱글톤 인스턴스 반환"""
        if self._v_is_disposed:
            raise ServiceLifetimeException(
                str(self.service_type),
                "singleton",
                "Service has been disposed"
            )
        
        if self._v_instance is None:
            with self._v_lock:
                if self._v_instance is None:
                    try:
                        self._v_instance = container._create_instance(self.implementation, **kwargs)
                    except Exception as e:
                        raise ServiceLifetimeException(
                            str(self.service_type),
                            "singleton",
                            f"Failed to create singleton instance: {str(e)}"
                        )
        
        return self._v_instance
    
    def dispose(self):
        """싱글톤 인스턴스 정리"""
        with self._v_lock:
            if self._v_instance is not None:
                # 인스턴스가 dispose 메서드를 가지고 있으면 호출
                if hasattr(self._v_instance, 'dispose'):
                    try:
                        self._v_instance.dispose()
                    except Exception:
                        pass  # 정리 중 오류는 무시
                self._v_instance = None
            self._v_is_disposed = True
    
    def get_lifetime_type(self) -> Lifetime:
        return Lifetime.SINGLETON


class TransientLifetime(ServiceLifetime):
    """일시적 생명주기 관리"""
    
    def __init__(self, service_type: Type, implementation: Type):
        super().__init__(service_type, implementation)
        self._v_instances = weakref.WeakSet()
    
    def get_instance(self, container, **kwargs) -> Any:
        """새로운 인스턴스 반환"""
        try:
            _v_instance = container._create_instance(self.implementation, **kwargs)
            self._v_instances.add(_v_instance)
            return _v_instance
        except Exception as e:
            raise ServiceLifetimeException(
                str(self.service_type),
                "transient",
                f"Failed to create transient instance: {str(e)}"
            )
    
    def dispose(self):
        """일시적 인스턴스들 정리"""
        for _v_instance in list(self._v_instances):
            if hasattr(_v_instance, 'dispose'):
                try:
                    _v_instance.dispose()
                except Exception:
                    pass  # 정리 중 오류는 무시
        self._v_instances.clear()
    
    def get_lifetime_type(self) -> Lifetime:
        return Lifetime.TRANSIENT


class ScopedLifetime(ServiceLifetime):
    """스코프 생명주기 관리"""
    
    def __init__(self, service_type: Type, implementation: Type):
        super().__init__(service_type, implementation)
        # 스레드별로 스코프를 분리
        self._v_local = threading.local()
    
    def get_instance(self, container, **kwargs) -> Any:
        """스코프 내 인스턴스 반환"""
        if not hasattr(self._v_local, 'instances'):
            self._v_local.instances = {}
        
        _v_scope_key = id(container.get_current_scope())
        
        if _v_scope_key not in self._v_local.instances:
            try:
                _v_instance = container._create_instance(self.implementation, **kwargs)
                self._v_local.instances[_v_scope_key] = _v_instance
            except Exception as e:
                raise ServiceLifetimeException(
                    str(self.service_type),
                    "scoped",
                    f"Failed to create scoped instance: {str(e)}"
                )
        
        return self._v_local.instances[_v_scope_key]
    
    def dispose(self):
        """스코프 인스턴스들 정리"""
        if hasattr(self._v_local, 'instances'):
            for _v_instance in self._v_local.instances.values():
                if hasattr(_v_instance, 'dispose'):
                    try:
                        _v_instance.dispose()
                    except Exception:
                        pass  # 정리 중 오류는 무시
            self._v_local.instances.clear()
    
    def dispose_scope(self, scope_id: int):
        """특정 스코프 정리"""
        if hasattr(self._v_local, 'instances') and scope_id in self._v_local.instances:
            _v_instance = self._v_local.instances[scope_id]
            if hasattr(_v_instance, 'dispose'):
                try:
                    _v_instance.dispose()
                except Exception:
                    pass  # 정리 중 오류는 무시
            del self._v_local.instances[scope_id]
    
    def get_lifetime_type(self) -> Lifetime:
        return Lifetime.SCOPED


class FactoryLifetime(ServiceLifetime):
    """팩토리 생명주기 관리"""
    
    def __init__(self, service_type: Type, factory: Callable):
        super().__init__(service_type, None)
        self._v_factory = factory
    
    def get_instance(self, container, **kwargs) -> Any:
        """팩토리를 통해 인스턴스 반환"""
        try:
            return self._v_factory(container, **kwargs)
        except Exception as e:
            raise ServiceLifetimeException(
                str(self.service_type),
                "factory",
                f"Failed to create factory instance: {str(e)}"
            )
    
    def dispose(self):
        """팩토리 정리"""
        self._v_factory = None
    
    def get_lifetime_type(self) -> Lifetime:
        return Lifetime.TRANSIENT  # 팩토리는 기본적으로 일시적


class LifetimeManager:
    """생명주기 관리자"""
    
    def __init__(self):
        self._v_lifetimes: Dict[Type, ServiceLifetime] = {}
        self._v_lock = threading.Lock()
    
    def add_lifetime(self, service_type: Type, lifetime: ServiceLifetime):
        """생명주기 추가"""
        with self._v_lock:
            self._v_lifetimes[service_type] = lifetime
    
    def get_lifetime(self, service_type: Type) -> Optional[ServiceLifetime]:
        """생명주기 조회"""
        return self._v_lifetimes.get(service_type)
    
    def remove_lifetime(self, service_type: Type) -> bool:
        """생명주기 제거"""
        with self._v_lock:
            if service_type in self._v_lifetimes:
                _v_lifetime = self._v_lifetimes[service_type]
                _v_lifetime.dispose()
                del self._v_lifetimes[service_type]
                return True
        return False
    
    def dispose_all(self):
        """모든 생명주기 정리"""
        with self._v_lock:
            for _v_lifetime in self._v_lifetimes.values():
                _v_lifetime.dispose()
            self._v_lifetimes.clear()
    
    def get_all_lifetimes(self) -> Dict[Type, ServiceLifetime]:
        """모든 생명주기 조회"""
        return self._v_lifetimes.copy()
    
    def get_lifetime_stats(self) -> Dict[str, int]:
        """생명주기 통계 조회"""
        _v_stats = {}
        for _v_lifetime in self._v_lifetimes.values():
            _v_lifetime_type = _v_lifetime.get_lifetime_type().value
            _v_stats[_v_lifetime_type] = _v_stats.get(_v_lifetime_type, 0) + 1
        return _v_stats


def create_lifetime(service_type: Type, implementation: Type, lifetime_type: Lifetime) -> ServiceLifetime:
    """생명주기 생성 팩토리 함수"""
    if lifetime_type == Lifetime.SINGLETON:
        return SingletonLifetime(service_type, implementation)
    elif lifetime_type == Lifetime.TRANSIENT:
        return TransientLifetime(service_type, implementation)
    elif lifetime_type == Lifetime.SCOPED:
        return ScopedLifetime(service_type, implementation)
    else:
        raise ServiceLifetimeException(
            str(service_type),
            str(lifetime_type),
            f"Unsupported lifetime type: {lifetime_type}"
        ) 