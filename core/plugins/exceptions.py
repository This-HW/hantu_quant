"""
플러그인 시스템 예외 클래스 정의

이 모듈은 플러그인 시스템에서 발생할 수 있는 모든 예외를 정의합니다.
"""

from typing import Optional, List, Any, Dict


class PluginException(Exception):
    """플러그인 관련 기본 예외"""
    
    def __init__(self, message: str, plugin_name: Optional[str] = None, 
                 error_code: Optional[str] = None):
        super().__init__(message)
        self.plugin_name = plugin_name
        self.error_code = error_code
        self.message = message
    
    def __str__(self) -> str:
        if self.plugin_name:
            return f"Plugin '{self.plugin_name}': {self.message}"
        return self.message


class PluginLoadError(PluginException):
    """플러그인 로딩 오류"""
    
    def __init__(self, message: str, plugin_name: Optional[str] = None, 
                 plugin_path: Optional[str] = None, original_error: Optional[Exception] = None):
        super().__init__(message, plugin_name, "LOAD_ERROR")
        self.plugin_path = plugin_path
        self.original_error = original_error


class PluginInitializationError(PluginException):
    """플러그인 초기화 오류"""
    
    def __init__(self, message: str, plugin_name: Optional[str] = None, 
                 original_error: Optional[Exception] = None):
        super().__init__(message, plugin_name, "INIT_ERROR")
        self.original_error = original_error


class PluginStartError(PluginException):
    """플러그인 시작 오류"""
    
    def __init__(self, message: str, plugin_name: Optional[str] = None, 
                 original_error: Optional[Exception] = None):
        super().__init__(message, plugin_name, "START_ERROR")
        self.original_error = original_error


class PluginStopError(PluginException):
    """플러그인 중지 오류"""
    
    def __init__(self, message: str, plugin_name: Optional[str] = None, 
                 original_error: Optional[Exception] = None):
        super().__init__(message, plugin_name, "STOP_ERROR")
        self.original_error = original_error


class PluginUnloadError(PluginException):
    """플러그인 언로드 오류"""
    
    def __init__(self, message: str, plugin_name: Optional[str] = None, 
                 original_error: Optional[Exception] = None):
        super().__init__(message, plugin_name, "UNLOAD_ERROR")
        self.original_error = original_error


class PluginDependencyError(PluginException):
    """플러그인 의존성 오류"""
    
    def __init__(self, message: str, plugin_name: Optional[str] = None, 
                 missing_dependencies: Optional[List[str]] = None, 
                 circular_dependencies: Optional[List[str]] = None):
        super().__init__(message, plugin_name, "DEPENDENCY_ERROR")
        self.missing_dependencies = missing_dependencies or []
        self.circular_dependencies = circular_dependencies or []


class PluginValidationError(PluginException):
    """플러그인 유효성 검증 오류"""
    
    def __init__(self, message: str, plugin_name: Optional[str] = None, 
                 validation_errors: Optional[List[str]] = None):
        super().__init__(message, plugin_name, "VALIDATION_ERROR")
        self.validation_errors = validation_errors or []


class PluginSecurityError(PluginException):
    """플러그인 보안 오류"""
    
    def __init__(self, message: str, plugin_name: Optional[str] = None, 
                 permission: Optional[str] = None):
        super().__init__(message, plugin_name, "SECURITY_ERROR")
        self.permission = permission


class PluginVersionError(PluginException):
    """플러그인 버전 호환성 오류"""
    
    def __init__(self, message: str, plugin_name: Optional[str] = None, 
                 required_version: Optional[str] = None, 
                 current_version: Optional[str] = None):
        super().__init__(message, plugin_name, "VERSION_ERROR")
        self.required_version = required_version
        self.current_version = current_version


class PluginNotFoundError(PluginException):
    """플러그인을 찾을 수 없음"""
    
    def __init__(self, plugin_name: str):
        message = f"Plugin '{plugin_name}' not found"
        super().__init__(message, plugin_name, "NOT_FOUND")


class PluginAlreadyExistsError(PluginException):
    """플러그인이 이미 존재함"""
    
    def __init__(self, plugin_name: str):
        message = f"Plugin '{plugin_name}' already exists"
        super().__init__(message, plugin_name, "ALREADY_EXISTS")


class PluginStateError(PluginException):
    """플러그인 상태 오류"""
    
    def __init__(self, message: str, plugin_name: Optional[str] = None, 
                 current_state: Optional[str] = None, 
                 expected_state: Optional[str] = None):
        super().__init__(message, plugin_name, "STATE_ERROR")
        self.current_state = current_state
        self.expected_state = expected_state


class PluginTimeoutError(PluginException):
    """플러그인 작업 타임아웃"""
    
    def __init__(self, message: str, plugin_name: Optional[str] = None, 
                 timeout_seconds: Optional[float] = None):
        super().__init__(message, plugin_name, "TIMEOUT_ERROR")
        self.timeout_seconds = timeout_seconds


class PluginConfigurationError(PluginException):
    """플러그인 설정 오류"""
    
    def __init__(self, message: str, plugin_name: Optional[str] = None, 
                 config_key: Optional[str] = None):
        super().__init__(message, plugin_name, "CONFIG_ERROR")
        self.config_key = config_key


class PluginMetadataError(PluginException):
    """플러그인 메타데이터 오류"""
    
    def __init__(self, message: str, plugin_name: Optional[str] = None, 
                 metadata_file: Optional[str] = None):
        super().__init__(message, plugin_name, "METADATA_ERROR")
        self.metadata_file = metadata_file


class PluginInterfaceError(PluginException):
    """플러그인 인터페이스 오류"""
    
    def __init__(self, message: str, plugin_name: Optional[str] = None, 
                 interface_name: Optional[str] = None, 
                 method_name: Optional[str] = None):
        super().__init__(message, plugin_name, "INTERFACE_ERROR")
        self.interface_name = interface_name
        self.method_name = method_name


class PluginRuntimeError(PluginException):
    """플러그인 런타임 오류"""
    
    def __init__(self, message: str, plugin_name: Optional[str] = None, 
                 original_error: Optional[Exception] = None, 
                 context: Optional[Dict[str, Any]] = None):
        super().__init__(message, plugin_name, "RUNTIME_ERROR")
        self.original_error = original_error
        self.context = context or {}


class PluginResourceError(PluginException):
    """플러그인 리소스 오류"""
    
    def __init__(self, message: str, plugin_name: Optional[str] = None, 
                 resource_type: Optional[str] = None, 
                 resource_name: Optional[str] = None):
        super().__init__(message, plugin_name, "RESOURCE_ERROR")
        self.resource_type = resource_type
        self.resource_name = resource_name


# 편의 함수들
def format_plugin_error(error: Exception, plugin_name: Optional[str] = None) -> str:
    """플러그인 오류 메시지 포맷팅"""
    if isinstance(error, PluginException):
        return str(error)
    
    if plugin_name:
        return f"Plugin '{plugin_name}': {str(error)}"
    return str(error)


def is_plugin_error(error: Exception) -> bool:
    """플러그인 관련 오류인지 확인"""
    return isinstance(error, PluginException)


def get_error_code(error: Exception) -> Optional[str]:
    """오류 코드 추출"""
    if isinstance(error, PluginException):
        return error.error_code
    return None 