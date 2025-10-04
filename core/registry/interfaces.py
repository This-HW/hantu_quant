"""
모듈 레지스트리 시스템 인터페이스

이 모듈은 모듈 레지스트리 시스템의 핵심 인터페이스들을 정의합니다.
전체 시스템의 모듈 관리, 의존성 분석, 영향 분석 등을 위한 인터페이스를 제공합니다.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Set, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import datetime


class ModuleType(Enum):
    """모듈 타입 정의"""
    CORE = "core"
    PLUGIN = "plugin"
    WORKFLOW = "workflow"
    EXTERNAL = "external"
    COMMON = "common"


class ModuleStatus(Enum):
    """모듈 상태 정의"""
    UNREGISTERED = "unregistered"
    REGISTERED = "registered"
    INITIALIZING = "initializing"
    INITIALIZED = "initialized"
    LOADING = "loading"
    LOADED = "loaded"
    ACTIVE = "active"
    INACTIVE = "inactive"
    UNLOADING = "unloading"
    ERROR = "error"
    DEPRECATED = "deprecated"


@dataclass
class ModuleVersion:
    """모듈 버전 정보"""
    major: int
    minor: int
    patch: int
    pre_release: Optional[str] = None
    build: Optional[str] = None
    
    def __str__(self) -> str:
        version = f"{self.major}.{self.minor}.{self.patch}"
        if self.pre_release:
            version += f"-{self.pre_release}"
        if self.build:
            version += f"+{self.build}"
        return version
    
    def __eq__(self, other) -> bool:
        if not isinstance(other, ModuleVersion):
            return False
        return (self.major, self.minor, self.patch, self.pre_release, self.build) == \
               (other.major, other.minor, other.patch, other.pre_release, other.build)
    
    def __lt__(self, other) -> bool:
        if not isinstance(other, ModuleVersion):
            return NotImplemented
        return (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch)


@dataclass
class ModuleDependency:
    """모듈 의존성 정보"""
    module_name: str
    version_constraint: Optional[str] = None  # ">=1.0.0,<2.0.0"
    optional: bool = False
    description: Optional[str] = None


@dataclass
class ModuleInterface:
    """모듈이 제공하는 인터페이스 정보"""
    name: str
    version: ModuleVersion
    description: Optional[str] = None
    methods: List[str] = None
    
    def __post_init__(self):
        if self.methods is None:
            self.methods = []


@dataclass
class ModuleUsage:
    """모듈이 사용하는 인터페이스 정보"""
    interface_name: str
    required: bool = True
    description: Optional[str] = None


class IModuleMetadata(ABC):
    """모듈 메타데이터 인터페이스"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """모듈명"""
        pass
    
    @property
    @abstractmethod
    def version(self) -> ModuleVersion:
        """모듈 버전"""
        pass
    
    @property
    @abstractmethod
    def module_type(self) -> ModuleType:
        """모듈 타입"""
        pass
    
    @property
    @abstractmethod
    def status(self) -> ModuleStatus:
        """모듈 상태"""
        pass
    
    @property
    @abstractmethod
    def dependencies(self) -> List[ModuleDependency]:
        """의존성 목록"""
        pass
    
    @property
    @abstractmethod
    def provided_interfaces(self) -> List[ModuleInterface]:
        """제공하는 인터페이스 목록"""
        pass
    
    @property
    @abstractmethod
    def used_interfaces(self) -> List[ModuleUsage]:
        """사용하는 인터페이스 목록"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> Optional[str]:
        """모듈 설명"""
        pass
    
    @property
    @abstractmethod
    def author(self) -> Optional[str]:
        """모듈 작성자"""
        pass
    
    @property
    @abstractmethod
    def created_at(self) -> datetime.datetime:
        """생성 시간"""
        pass
    
    @property
    @abstractmethod
    def updated_at(self) -> datetime.datetime:
        """수정 시간"""
        pass
    
    @abstractmethod
    def update_status(self, status: ModuleStatus) -> None:
        """모듈 상태 업데이트"""
        pass
    
    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        pass
    
    @abstractmethod
    def from_dict(self, data: Dict[str, Any]) -> 'IModuleMetadata':
        """딕셔너리에서 생성"""
        pass


class IModuleRegistry(ABC):
    """모듈 레지스트리 인터페이스"""
    
    @abstractmethod
    def register_module(self, metadata: IModuleMetadata) -> bool:
        """모듈 등록"""
        pass
    
    @abstractmethod
    def unregister_module(self, module_name: str) -> bool:
        """모듈 해제"""
        pass
    
    @abstractmethod
    def get_module(self, module_name: str) -> Optional[IModuleMetadata]:
        """모듈 조회"""
        pass
    
    @abstractmethod
    def list_modules(self, module_type: Optional[ModuleType] = None, 
                    status: Optional[ModuleStatus] = None) -> List[IModuleMetadata]:
        """모듈 목록 조회"""
        pass
    
    @abstractmethod
    def has_module(self, module_name: str) -> bool:
        """모듈 존재 여부 확인"""
        pass
    
    @abstractmethod
    def update_module_status(self, module_name: str, status: ModuleStatus) -> bool:
        """모듈 상태 업데이트"""
        pass
    
    @abstractmethod
    def validate_dependencies(self, module_name: str) -> Tuple[bool, List[str]]:
        """의존성 검증"""
        pass
    
    @abstractmethod
    def get_module_graph(self) -> Dict[str, List[str]]:
        """모듈 의존성 그래프 생성"""
        pass
    
    @abstractmethod
    def clear(self) -> None:
        """레지스트리 초기화"""
        pass


class IDependencyAnalyzer(ABC):
    """의존성 분석 엔진 인터페이스"""
    
    @abstractmethod
    def analyze_dependencies(self, module_name: str) -> Dict[str, Any]:
        """의존성 분석"""
        pass
    
    @abstractmethod
    def detect_circular_dependencies(self) -> List[List[str]]:
        """순환 의존성 탐지"""
        pass
    
    @abstractmethod
    def resolve_dependency_order(self, modules: List[str]) -> List[str]:
        """의존성 순서 해결 (위상 정렬)"""
        pass
    
    @abstractmethod
    def validate_dependency_versions(self, module_name: str) -> Tuple[bool, List[str]]:
        """의존성 버전 검증"""
        pass
    
    @abstractmethod
    def get_dependency_tree(self, module_name: str) -> Dict[str, Any]:
        """의존성 트리 생성"""
        pass
    
    @abstractmethod
    def get_reverse_dependencies(self, module_name: str) -> List[str]:
        """역 의존성 조회 (해당 모듈을 의존하는 모듈들)"""
        pass
    
    @abstractmethod
    def calculate_dependency_depth(self, module_name: str) -> int:
        """의존성 깊이 계산"""
        pass


class IImpactAnalyzer(ABC):
    """영향 분석 엔진 인터페이스"""
    
    @abstractmethod
    def analyze_impact(self, module_name: str, change_type: str) -> Dict[str, Any]:
        """영향 분석"""
        pass
    
    @abstractmethod
    def get_dependent_modules(self, module_name: str) -> List[str]:
        """의존 모듈 목록 (해당 모듈을 의존하는 모듈들)"""
        pass
    
    @abstractmethod
    def get_affected_modules(self, module_name: str, change_type: str) -> List[str]:
        """영향 받는 모듈 목록"""
        pass
    
    @abstractmethod
    def calculate_change_impact(self, module_name: str, change_type: str) -> float:
        """변경 영향도 계산 (0.0 ~ 1.0)"""
        pass
    
    @abstractmethod
    def generate_impact_report(self, module_name: str, change_type: str) -> Dict[str, Any]:
        """영향 분석 보고서 생성"""
        pass
    
    @abstractmethod
    def predict_breaking_changes(self, module_name: str, change_type: str) -> List[str]:
        """호환성 문제 예측"""
        pass
    
    @abstractmethod
    def calculate_risk_score(self, module_name: str, change_type: str) -> float:
        """변경 위험도 계산 (0.0 ~ 1.0)"""
        pass


class IModuleManager(ABC):
    """모듈 관리자 인터페이스"""
    
    @abstractmethod
    def initialize(self) -> None:
        """모듈 관리자 초기화"""
        pass
    
    @abstractmethod
    def load_module(self, module_name: str) -> bool:
        """모듈 로드"""
        pass
    
    @abstractmethod
    def unload_module(self, module_name: str) -> bool:
        """모듈 언로드"""
        pass
    
    @abstractmethod
    def reload_module(self, module_name: str) -> bool:
        """모듈 리로드"""
        pass
    
    @abstractmethod
    def validate_module_state(self, module_name: str) -> Tuple[bool, str]:
        """모듈 상태 검증"""
        pass
    
    @abstractmethod
    def monitor_module_health(self) -> Dict[str, Any]:
        """모듈 상태 모니터링"""
        pass
    
    @abstractmethod
    def auto_discover_modules(self) -> List[str]:
        """모듈 자동 발견"""
        pass
    
    @abstractmethod
    def get_module_statistics(self) -> Dict[str, Any]:
        """모듈 통계 정보"""
        pass
    
    @abstractmethod
    def shutdown(self) -> None:
        """모듈 관리자 종료"""
        pass


class IModuleScanner(ABC):
    """모듈 스캐너 인터페이스"""
    
    @abstractmethod
    def scan_directory(self, directory: str) -> List[IModuleMetadata]:
        """디렉토리 내 모듈 스캔"""
        pass
    
    @abstractmethod
    def scan_module_file(self, file_path: str) -> Optional[IModuleMetadata]:
        """모듈 파일 스캔"""
        pass
    
    @abstractmethod
    def extract_dependencies(self, file_path: str) -> List[ModuleDependency]:
        """파일에서 의존성 추출"""
        pass
    
    @abstractmethod
    def extract_interfaces(self, file_path: str) -> List[ModuleInterface]:
        """파일에서 인터페이스 추출"""
        pass
    
    @abstractmethod
    def validate_module_structure(self, module_path: str) -> Tuple[bool, List[str]]:
        """모듈 구조 검증"""
        pass 