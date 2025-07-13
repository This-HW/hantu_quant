"""
의존성 주입 시스템 예외 클래스들

이 모듈은 의존성 주입 시스템에서 발생할 수 있는 예외들을 정의합니다.
"""

class DIException(Exception):
    """의존성 주입 시스템 기본 예외"""
    
    def __init__(self, message: str, service_type: str = None):
        super().__init__(message)
        self.service_type = service_type
        self.message = message
    
    def __str__(self):
        if self.service_type:
            return f"[{self.service_type}] {self.message}"
        return self.message


class ServiceNotRegisteredException(DIException):
    """서비스가 등록되지 않았을 때 발생하는 예외"""
    
    def __init__(self, service_type: str):
        super().__init__(
            f"Service '{service_type}' is not registered in the container",
            service_type
        )


class CircularDependencyException(DIException):
    """순환 의존성이 발견되었을 때 발생하는 예외"""
    
    def __init__(self, dependency_chain: list):
        self.dependency_chain = dependency_chain
        chain_str = " -> ".join(dependency_chain)
        super().__init__(
            f"Circular dependency detected: {chain_str}",
            dependency_chain[0] if dependency_chain else None
        )


class ServiceResolutionException(DIException):
    """서비스 해결 과정에서 발생하는 예외"""
    
    def __init__(self, service_type: str, inner_exception: Exception):
        self.inner_exception = inner_exception
        super().__init__(
            f"Failed to resolve service '{service_type}': {str(inner_exception)}",
            service_type
        )


class ServiceRegistrationException(DIException):
    """서비스 등록 과정에서 발생하는 예외"""
    
    def __init__(self, service_type: str, reason: str):
        super().__init__(
            f"Failed to register service '{service_type}': {reason}",
            service_type
        )


class InvalidServiceTypeException(DIException):
    """유효하지 않은 서비스 타입일 때 발생하는 예외"""
    
    def __init__(self, service_type: str):
        super().__init__(
            f"Invalid service type: '{service_type}'. Service type must be a class or interface.",
            service_type
        )


class ServiceLifetimeException(DIException):
    """서비스 생명주기 관련 예외"""
    
    def __init__(self, service_type: str, lifetime: str, reason: str):
        super().__init__(
            f"Service '{service_type}' with lifetime '{lifetime}' error: {reason}",
            service_type
        )


class DependencyInjectionError(DIException):
    """의존성 주입 과정에서 발생하는 일반적인 오류"""
    
    def __init__(self, message: str, service_type: str = None, details: dict = None):
        super().__init__(message, service_type)
        self.details = details or {}
    
    def get_details(self):
        """오류 세부 정보 반환"""
        return self.details 