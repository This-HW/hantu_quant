"""
모듈 레지스트리 시스템 예외 클래스

이 모듈은 모듈 레지스트리 시스템에서 발생할 수 있는 다양한 예외들을 정의합니다.
"""

from typing import List, Optional


class ModuleRegistryError(Exception):
    """모듈 레지스트리 기본 예외 클래스"""
    
    def __init__(self, message: str, module_name: Optional[str] = None):
        super().__init__(message)
        self.module_name = module_name
        self.message = message
    
    def __str__(self):
        if self.module_name:
            return f"Module '{self.module_name}': {self.message}"
        return self.message


class ModuleAlreadyRegisteredError(ModuleRegistryError):
    """이미 등록된 모듈 예외"""
    
    def __init__(self, module_name: str):
        super().__init__(f"Module '{module_name}' is already registered", module_name)


class ModuleNotFoundError(ModuleRegistryError):
    """모듈을 찾을 수 없는 예외"""
    
    def __init__(self, module_name: str):
        super().__init__(f"Module '{module_name}' not found", module_name)


class ModuleNotRegisteredError(ModuleRegistryError):
    """모듈이 등록되지 않은 예외"""
    
    def __init__(self, module_name: str):
        super().__init__(f"Module '{module_name}' is not registered", module_name)


class InvalidModuleMetadataError(ModuleRegistryError):
    """잘못된 모듈 메타데이터 예외"""
    
    def __init__(self, module_name: str, errors: List[str]):
        error_msg = f"Invalid metadata for module '{module_name}': {', '.join(errors)}"
        super().__init__(error_msg, module_name)
        self.errors = errors


class DependencyError(ModuleRegistryError):
    """의존성 관련 예외"""
    
    def __init__(self, message: str, module_name: Optional[str] = None, 
                 dependency_name: Optional[str] = None):
        super().__init__(message, module_name)
        self.dependency_name = dependency_name


class CircularDependencyError(DependencyError):
    """순환 의존성 예외"""
    
    def __init__(self, cycle: List[str]):
        cycle_str = " -> ".join(cycle + [cycle[0]])
        super().__init__(f"Circular dependency detected: {cycle_str}")
        self.cycle = cycle


class UnresolvedDependencyError(DependencyError):
    """해결되지 않은 의존성 예외"""
    
    def __init__(self, module_name: str, dependency_name: str):
        super().__init__(
            f"Unresolved dependency: {dependency_name}",
            module_name,
            dependency_name
        )


class IncompatibleVersionError(DependencyError):
    """호환되지 않는 버전 예외"""
    
    def __init__(self, module_name: str, dependency_name: str, 
                 required_version: str, available_version: str):
        super().__init__(
            f"Incompatible version for {dependency_name}: "
            f"required {required_version}, available {available_version}",
            module_name,
            dependency_name
        )
        self.required_version = required_version
        self.available_version = available_version


class ModuleStateError(ModuleRegistryError):
    """모듈 상태 관련 예외"""
    
    def __init__(self, module_name: str, current_state: str, 
                 expected_state: str, operation: str):
        super().__init__(
            f"Cannot {operation} module '{module_name}' in state '{current_state}'. "
            f"Expected state: '{expected_state}'",
            module_name
        )
        self.current_state = current_state
        self.expected_state = expected_state
        self.operation = operation


class ModuleLoadError(ModuleRegistryError):
    """모듈 로드 실패 예외"""
    
    def __init__(self, module_name: str, error: Exception):
        super().__init__(f"Failed to load module '{module_name}': {error}", module_name)
        self.original_error = error


class ModuleUnloadError(ModuleRegistryError):
    """모듈 언로드 실패 예외"""
    
    def __init__(self, module_name: str, error: Exception):
        super().__init__(f"Failed to unload module '{module_name}': {error}", module_name)
        self.original_error = error


class ModuleValidationError(ModuleRegistryError):
    """모듈 검증 실패 예외"""
    
    def __init__(self, module_name: str, validation_errors: List[str]):
        error_msg = f"Module '{module_name}' failed validation: {', '.join(validation_errors)}"
        super().__init__(error_msg, module_name)
        self.validation_errors = validation_errors


class InterfaceError(ModuleRegistryError):
    """인터페이스 관련 예외"""
    
    def __init__(self, message: str, module_name: Optional[str] = None, 
                 interface_name: Optional[str] = None):
        super().__init__(message, module_name)
        self.interface_name = interface_name


class InterfaceNotFoundError(InterfaceError):
    """인터페이스를 찾을 수 없는 예외"""
    
    def __init__(self, interface_name: str, module_name: Optional[str] = None):
        super().__init__(
            f"Interface '{interface_name}' not found",
            module_name,
            interface_name
        )


class InterfaceVersionMismatchError(InterfaceError):
    """인터페이스 버전 불일치 예외"""
    
    def __init__(self, interface_name: str, required_version: str, 
                 available_version: str, module_name: Optional[str] = None):
        super().__init__(
            f"Interface '{interface_name}' version mismatch: "
            f"required {required_version}, available {available_version}",
            module_name,
            interface_name
        )
        self.required_version = required_version
        self.available_version = available_version


class ImpactAnalysisError(ModuleRegistryError):
    """영향 분석 관련 예외"""
    
    def __init__(self, message: str, module_name: Optional[str] = None, 
                 change_type: Optional[str] = None):
        super().__init__(message, module_name)
        self.change_type = change_type


class ModuleScanError(ModuleRegistryError):
    """모듈 스캔 관련 예외"""
    
    def __init__(self, path: str, error: Exception):
        super().__init__(f"Failed to scan module at '{path}': {error}")
        self.path = path
        self.original_error = error


class RegistryTimeoutError(ModuleRegistryError):
    """레지스트리 작업 타임아웃 예외"""
    
    def __init__(self, operation: str, timeout: float):
        super().__init__(f"Registry operation '{operation}' timed out after {timeout} seconds")
        self.operation = operation
        self.timeout = timeout


class RegistryLockError(ModuleRegistryError):
    """레지스트리 락 관련 예외"""
    
    def __init__(self, message: str, lock_type: str = "unknown"):
        super().__init__(message)
        self.lock_type = lock_type


class ModuleSecurityError(ModuleRegistryError):
    """모듈 보안 관련 예외"""
    
    def __init__(self, module_name: str, security_issue: str):
        super().__init__(f"Security issue in module '{module_name}': {security_issue}", module_name)
        self.security_issue = security_issue 