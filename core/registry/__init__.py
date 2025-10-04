"""
모듈 레지스트리 시스템

이 패키지는 모듈 레지스트리 시스템의 모든 구성 요소를 제공합니다.
"""

from .interfaces import (
    # 기본 데이터 클래스
    ModuleType,
    ModuleStatus,
    ModuleVersion,
    ModuleDependency,
    ModuleInterface,
    ModuleUsage,
    
    # 인터페이스
    IModuleMetadata,
    IModuleRegistry,
    IDependencyAnalyzer,
    IImpactAnalyzer,
    IModuleManager,
    IModuleScanner
)

from .exceptions import (
    # 기본 예외
    ModuleRegistryError,
    ModuleAlreadyRegisteredError,
    ModuleNotFoundError,
    ModuleNotRegisteredError,
    InvalidModuleMetadataError,
    
    # 의존성 관련 예외
    DependencyError,
    CircularDependencyError,
    UnresolvedDependencyError,
    IncompatibleVersionError,
    
    # 모듈 상태 관련 예외
    ModuleStateError,
    ModuleLoadError,
    ModuleUnloadError,
    ModuleValidationError,
    
    # 인터페이스 관련 예외
    InterfaceError,
    InterfaceNotFoundError,
    InterfaceVersionMismatchError,
    
    # 기타 예외
    ImpactAnalysisError,
    ModuleScanError,
    RegistryTimeoutError,
    RegistryLockError,
    ModuleSecurityError
)

from .metadata import ModuleMetadata
from .registry import ModuleRegistry
from .dependency import DependencyAnalyzer
from .impact import ImpactAnalyzer, ChangeType, ImpactLevel

# 편의 함수
def create_module_version(major: int, minor: int, patch: int, 
                         pre_release: str = None, build: str = None) -> ModuleVersion:
    """모듈 버전 생성 편의 함수"""
    return ModuleVersion(
        major=major,
        minor=minor,
        patch=patch,
        pre_release=pre_release,
        build=build
    )

def create_module_dependency(module_name: str, version_constraint: str = None,
                           optional: bool = False, description: str = None) -> ModuleDependency:
    """모듈 의존성 생성 편의 함수"""
    return ModuleDependency(
        module_name=module_name,
        version_constraint=version_constraint,
        optional=optional,
        description=description
    )

def create_module_interface(name: str, version: ModuleVersion, 
                          description: str = None, methods: list = None) -> ModuleInterface:
    """모듈 인터페이스 생성 편의 함수"""
    return ModuleInterface(
        name=name,
        version=version,
        description=description,
        methods=methods or []
    )

def create_module_usage(interface_name: str, required: bool = True,
                       description: str = None) -> ModuleUsage:
    """모듈 사용 정보 생성 편의 함수"""
    return ModuleUsage(
        interface_name=interface_name,
        required=required,
        description=description
    )

def create_module_metadata(name: str, version: ModuleVersion, module_type: ModuleType,
                         description: str = None, author: str = None,
                         dependencies: list = None, provided_interfaces: list = None,
                         used_interfaces: list = None) -> ModuleMetadata:
    """모듈 메타데이터 생성 편의 함수"""
    return ModuleMetadata(
        _name=name,
        _version=version,
        _module_type=module_type,
        _description=description,
        _author=author,
        _dependencies=dependencies or [],
        _provided_interfaces=provided_interfaces or [],
        _used_interfaces=used_interfaces or []
    )

# 팩토리 함수
def create_registry_system() -> tuple:
    """완전한 레지스트리 시스템 생성"""
    registry = ModuleRegistry()
    dependency_analyzer = DependencyAnalyzer(registry)
    impact_analyzer = ImpactAnalyzer(registry, dependency_analyzer)
    
    return registry, dependency_analyzer, impact_analyzer

# 버전 정보
__version__ = "1.0.0"
__author__ = "Hantu Quant Team"

# 모든 public API 내보내기
__all__ = [
    # 기본 데이터 클래스
    "ModuleType",
    "ModuleStatus", 
    "ModuleVersion",
    "ModuleDependency",
    "ModuleInterface",
    "ModuleUsage",
    
    # 인터페이스
    "IModuleMetadata",
    "IModuleRegistry",
    "IDependencyAnalyzer",
    "IImpactAnalyzer",
    "IModuleManager",
    "IModuleScanner",
    
    # 구현 클래스
    "ModuleMetadata",
    "ModuleRegistry",
    "DependencyAnalyzer",
    "ImpactAnalyzer",
    
    # 열거형
    "ChangeType",
    "ImpactLevel",
    
    # 예외 클래스
    "ModuleRegistryError",
    "ModuleAlreadyRegisteredError",
    "ModuleNotFoundError",
    "ModuleNotRegisteredError",
    "InvalidModuleMetadataError",
    "DependencyError",
    "CircularDependencyError",
    "UnresolvedDependencyError",
    "IncompatibleVersionError",
    "ModuleStateError",
    "ModuleLoadError",
    "ModuleUnloadError",
    "ModuleValidationError",
    "InterfaceError",
    "InterfaceNotFoundError",
    "InterfaceVersionMismatchError",
    "ImpactAnalysisError",
    "ModuleScanError",
    "RegistryTimeoutError",
    "RegistryLockError",
    "ModuleSecurityError",
    
    # 편의 함수
    "create_module_version",
    "create_module_dependency",
    "create_module_interface",
    "create_module_usage",
    "create_module_metadata",
    
    # 팩토리 함수
    "create_registry_system",
    
    # 버전 정보
    "__version__",
    "__author__"
] 