"""
패키지 관리 시스템 인터페이스

이 모듈은 패키지 관리 시스템의 핵심 인터페이스들을 정의합니다.
모듈의 패키징, 배포, 설치, 버전 관리 등을 위한 인터페이스를 제공합니다.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import datetime
from pathlib import Path


class PackageType(Enum):
    """패키지 타입 정의"""
    MODULE = "module"
    PLUGIN = "plugin"
    LIBRARY = "library"
    APPLICATION = "application"
    EXTENSION = "extension"


class PackageStatus(Enum):
    """패키지 상태 정의"""
    AVAILABLE = "available"
    DOWNLOADING = "downloading"
    INSTALLING = "installing"
    INSTALLED = "installed"
    UPDATING = "updating"
    UNINSTALLING = "uninstalling"
    ERROR = "error"
    DEPRECATED = "deprecated"


class VersionConstraint(Enum):
    """버전 제약 조건 타입"""
    EXACT = "exact"          # ==1.0.0
    GREATER = "greater"      # >1.0.0
    GREATER_EQUAL = "greater_equal"  # >=1.0.0
    LESS = "less"            # <2.0.0
    LESS_EQUAL = "less_equal"        # <=2.0.0
    COMPATIBLE = "compatible"        # ~=1.0.0
    RANGE = "range"          # >=1.0.0,<2.0.0


@dataclass
class SemanticVersion:
    """Semantic Versioning (SemVer) 구현"""
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
        if not isinstance(other, SemanticVersion):
            return False
        return (self.major, self.minor, self.patch, self.pre_release) == \
               (other.major, other.minor, other.patch, other.pre_release)
    
    def __lt__(self, other) -> bool:
        if not isinstance(other, SemanticVersion):
            return NotImplemented
        
        # 메인 버전 비교
        main_self = (self.major, self.minor, self.patch)
        main_other = (other.major, other.minor, other.patch)
        
        if main_self != main_other:
            return main_self < main_other
        
        # Pre-release 비교
        if self.pre_release is None and other.pre_release is None:
            return False
        if self.pre_release is None:
            return False  # 정식 버전이 pre-release보다 높음
        if other.pre_release is None:
            return True   # pre-release가 정식 버전보다 낮음
        
        return self.pre_release < other.pre_release
    
    def is_compatible_with(self, other: 'SemanticVersion') -> bool:
        """버전 호환성 확인 (Major 버전이 같으면 호환)"""
        return self.major == other.major


@dataclass
class PackageDependency:
    """패키지 의존성 정보"""
    name: str
    version_constraint: Optional[str] = None
    constraint_type: VersionConstraint = VersionConstraint.GREATER_EQUAL
    optional: bool = False
    description: Optional[str] = None
    
    def is_satisfied_by(self, version: SemanticVersion) -> bool:
        """버전이 제약 조건을 만족하는지 확인"""
        if not self.version_constraint:
            return True
        
        # 간단한 버전 제약 확인 구현
        # 실제로는 더 복잡한 파싱이 필요
        return True  # 임시 구현


@dataclass
class PackageEntryPoint:
    """패키지 엔트리 포인트"""
    name: str
    module_path: str
    class_name: Optional[str] = None
    function_name: Optional[str] = None
    description: Optional[str] = None
    
    def get_import_path(self) -> str:
        """임포트 경로 생성"""
        if self.class_name:
            return f"{self.module_path}:{self.class_name}"
        elif self.function_name:
            return f"{self.module_path}:{self.function_name}"
        else:
            return self.module_path


class IPackageInfo(ABC):
    """패키지 정보 인터페이스"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """패키지명"""
        pass
    
    @property
    @abstractmethod
    def version(self) -> SemanticVersion:
        """패키지 버전"""
        pass
    
    @property
    @abstractmethod
    def package_type(self) -> PackageType:
        """패키지 타입"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> Optional[str]:
        """패키지 설명"""
        pass
    
    @property
    @abstractmethod
    def author(self) -> Optional[str]:
        """패키지 작성자"""
        pass
    
    @property
    @abstractmethod
    def license(self) -> Optional[str]:
        """라이선스"""
        pass
    
    @property
    @abstractmethod
    def dependencies(self) -> List[PackageDependency]:
        """의존성 목록"""
        pass
    
    @property
    @abstractmethod
    def entry_points(self) -> List[PackageEntryPoint]:
        """엔트리 포인트 목록"""
        pass
    
    @property
    @abstractmethod
    def files(self) -> List[str]:
        """패키지에 포함된 파일 목록"""
        pass
    
    @property
    @abstractmethod
    def created_at(self) -> datetime.datetime:
        """생성 시간"""
        pass
    
    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        pass


class IPackageManifest(ABC):
    """패키지 매니페스트 인터페이스"""
    
    @abstractmethod
    def get_package_info(self) -> IPackageInfo:
        """패키지 정보 조회"""
        pass
    
    @abstractmethod
    def validate(self) -> Tuple[bool, List[str]]:
        """매니페스트 유효성 검증"""
        pass
    
    @abstractmethod
    def save_to_file(self, file_path: Path) -> None:
        """파일에 저장"""
        pass
    
    @abstractmethod
    def load_from_file(self, file_path: Path) -> None:
        """파일에서 로드"""
        pass


class IPackageBuilder(ABC):
    """패키지 빌더 인터페이스"""
    
    @abstractmethod
    def set_source_path(self, path: Path) -> None:
        """소스 경로 설정"""
        pass
    
    @abstractmethod
    def set_package_info(self, package_info: IPackageInfo) -> None:
        """패키지 정보 설정"""
        pass
    
    @abstractmethod
    def collect_files(self) -> List[str]:
        """패키지에 포함될 파일 수집"""
        pass
    
    @abstractmethod
    def validate_package(self) -> Tuple[bool, List[str]]:
        """패키지 유효성 검증"""
        pass
    
    @abstractmethod
    def build(self, output_path: Path) -> Path:
        """패키지 빌드"""
        pass
    
    @abstractmethod
    def get_build_info(self) -> Dict[str, Any]:
        """빌드 정보 조회"""
        pass


class IPackageRepository(ABC):
    """패키지 저장소 인터페이스"""
    
    @abstractmethod
    def store_package(self, package_path: Path, package_info: IPackageInfo) -> bool:
        """패키지 저장"""
        pass
    
    @abstractmethod
    def get_package(self, name: str, version: Optional[SemanticVersion] = None) -> Optional[Path]:
        """패키지 조회"""
        pass
    
    @abstractmethod
    def list_packages(self, name_pattern: Optional[str] = None) -> List[IPackageInfo]:
        """패키지 목록 조회"""
        pass
    
    @abstractmethod
    def get_package_versions(self, name: str) -> List[SemanticVersion]:
        """패키지 버전 목록 조회"""
        pass
    
    @abstractmethod
    def remove_package(self, name: str, version: Optional[SemanticVersion] = None) -> bool:
        """패키지 제거"""
        pass
    
    @abstractmethod
    def package_exists(self, name: str, version: Optional[SemanticVersion] = None) -> bool:
        """패키지 존재 여부 확인"""
        pass
    
    @abstractmethod
    def get_package_info(self, name: str, version: Optional[SemanticVersion] = None) -> Optional[IPackageInfo]:
        """패키지 정보 조회"""
        pass
    
    @abstractmethod
    def rebuild_index(self) -> None:
        """인덱스 재구축"""
        pass


class IPackageInstaller(ABC):
    """패키지 설치자 인터페이스"""
    
    @abstractmethod
    def install_package(self, name: str, version: Optional[SemanticVersion] = None,
                       force: bool = False) -> bool:
        """패키지 설치"""
        pass
    
    @abstractmethod
    def uninstall_package(self, name: str) -> bool:
        """패키지 제거"""
        pass
    
    @abstractmethod
    def update_package(self, name: str, target_version: Optional[SemanticVersion] = None) -> bool:
        """패키지 업데이트"""
        pass
    
    @abstractmethod
    def resolve_dependencies(self, dependencies: List[PackageDependency]) -> List[IPackageInfo]:
        """의존성 해결"""
        pass
    
    @abstractmethod
    def check_conflicts(self, package_info: IPackageInfo) -> List[str]:
        """의존성 충돌 확인"""
        pass
    
    @abstractmethod
    def get_installed_packages(self) -> List[IPackageInfo]:
        """설치된 패키지 목록 조회"""
        pass
    
    @abstractmethod
    def is_package_installed(self, name: str) -> bool:
        """패키지 설치 여부 확인"""
        pass


class IPackageDeployer(ABC):
    """패키지 배포자 인터페이스"""
    
    @abstractmethod
    def deploy_package(self, package_path: Path, target: str) -> bool:
        """패키지 배포"""
        pass
    
    @abstractmethod
    def create_release(self, package_info: IPackageInfo, release_notes: str) -> str:
        """릴리스 생성"""
        pass
    
    @abstractmethod
    def tag_version(self, version: SemanticVersion) -> bool:
        """버전 태깅"""
        pass
    
    @abstractmethod
    def rollback_deployment(self, deployment_id: str) -> bool:
        """배포 롤백"""
        pass
    
    @abstractmethod
    def get_deployment_status(self, deployment_id: str) -> Dict[str, Any]:
        """배포 상태 조회"""
        pass


class IVersionManager(ABC):
    """버전 관리자 인터페이스"""
    
    @abstractmethod
    def bump_version(self, current_version: SemanticVersion, 
                    bump_type: str) -> SemanticVersion:
        """버전 증가"""
        pass
    
    @abstractmethod
    def parse_version(self, version_string: str) -> SemanticVersion:
        """버전 문자열 파싱"""
        pass
    
    @abstractmethod
    def format_version(self, version: SemanticVersion) -> str:
        """버전 포맷팅"""
        pass
    
    @abstractmethod
    def is_version_compatible(self, version1: SemanticVersion, 
                            version2: SemanticVersion) -> bool:
        """버전 호환성 확인"""
        pass
    
    @abstractmethod
    def find_latest_version(self, versions: List[SemanticVersion],
                          constraint: Optional[str] = None) -> Optional[SemanticVersion]:
        """최신 버전 찾기"""
        pass


class IPackageManager(ABC):
    """패키지 관리자 통합 인터페이스"""
    
    @abstractmethod
    def initialize(self) -> None:
        """패키지 관리자 초기화"""
        pass
    
    @abstractmethod
    def build_package(self, source_path: Path, output_path: Path) -> Path:
        """패키지 빌드"""
        pass
    
    @abstractmethod
    def publish_package(self, package_path: Path) -> bool:
        """패키지 퍼블리시"""
        pass
    
    @abstractmethod
    def install_package(self, name: str, version: Optional[str] = None) -> bool:
        """패키지 설치"""
        pass
    
    @abstractmethod
    def uninstall_package(self, name: str) -> bool:
        """패키지 제거"""
        pass
    
    @abstractmethod
    def list_installed_packages(self) -> List[IPackageInfo]:
        """설치된 패키지 목록"""
        pass
    
    @abstractmethod
    def search_packages(self, query: str) -> List[IPackageInfo]:
        """패키지 검색"""
        pass
    
    @abstractmethod
    def get_package_statistics(self) -> Dict[str, Any]:
        """패키지 통계 정보"""
        pass
    
    @abstractmethod
    def cleanup(self) -> None:
        """정리 작업"""
        pass 