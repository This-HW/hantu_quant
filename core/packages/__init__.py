"""
패키지 관리 시스템

이 모듈은 한투 퀀트 프로젝트의 패키지 관리 시스템을 제공합니다.
모듈의 패키징, 배포, 설치, 버전 관리 등의 기능을 포함합니다.

주요 기능:
- 패키지 빌드 및 생성
- 로컬/원격 저장소 관리
- 패키지 설치/제거/업데이트
- 의존성 해결
- 버전 관리
"""

from pathlib import Path
from typing import Dict, List, Optional, Any, Union

# 핵심 인터페이스들
from .interfaces import (
    # 인터페이스
    IPackageInfo,
    IPackageManifest,
    IPackageBuilder,
    IPackageRepository,
    IPackageInstaller,
    IPackageDeployer,
    IVersionManager,
    IPackageManager,
    # 데이터 클래스들
    SemanticVersion,
    PackageDependency,
    PackageEntryPoint,
    # 열거형들
    PackageType,
    PackageStatus,
    VersionConstraint,
)

# 구현 클래스들
from .metadata import PackageInfo, PackageManifest
from .builder import (
    PackageBuilder,
    AssetCollector,
    DependencyResolver as BuilderDependencyResolver,
    PackageValidator,
)
from .repository import LocalRepository, PackageIndex
from .installer import PackageInstaller, InstalledPackageTracker, DependencyResolver

# 예외 클래스들
from .exceptions import (
    PackageError,
    PackageNotFoundError,
    PackageAlreadyExistsError,
    PackageAlreadyInstalledError,
    PackageNotInstalledError,
    InvalidPackageError,
    PackageCorruptedError,
    PackageDependencyError,
    UnresolvedDependencyError,
    DependencyConflictError,
    CircularDependencyError,
    IncompatibleVersionError,
    PackageBuildError,
    PackageInstallationError,
    PackageUninstallationError,
    PackageUpdateError,
    PackageValidationError,
    ManifestError,
    InvalidManifestError,
    ManifestNotFoundError,
    VersionError,
    InvalidVersionError,
    VersionNotFoundError,
    RepositoryError,
    RepositoryNotFoundError,
    RepositoryCorruptedError,
    RepositoryLockError,
    DeploymentError,
    DeploymentFailedError,
    RollbackError,
    PackageTimeoutError,
    PackageSecurityError,
    PackagePermissionError,
    PackageChecksumError,
    PackageIntegrityError,
)


# 버전 정보
__version__ = "1.0.0"
__author__ = "Hantu Quant Team"


class PackageManager(IPackageManager):
    """통합 패키지 관리자"""

    def __init__(self, workspace_path: Optional[Path] = None):
        """초기화"""
        # 작업 공간 경로 설정
        if workspace_path is None:
            workspace_path = Path.cwd()

        self.workspace_path = workspace_path
        self.packages_path = workspace_path / "packages"
        self.repository_path = self.packages_path / "repository"
        self.install_path = self.packages_path / "installed"

        # 핵심 컴포넌트들
        self._repository: Optional[LocalRepository] = None
        self._installer: Optional[PackageInstaller] = None
        self._builder: Optional[PackageBuilder] = None

        # 초기화 상태
        self._initialized = False

    def initialize(self) -> None:
        """패키지 관리자 초기화"""
        if self._initialized:
            return

        try:
            # 디렉토리 생성
            self.packages_path.mkdir(parents=True, exist_ok=True)
            self.repository_path.mkdir(parents=True, exist_ok=True)
            self.install_path.mkdir(parents=True, exist_ok=True)

            # 핵심 컴포넌트 초기화
            self._repository = LocalRepository(self.repository_path)
            self._installer = PackageInstaller(self._repository, self.install_path)
            self._builder = PackageBuilder()

            self._initialized = True

        except Exception as e:
            raise PackageError(f"Failed to initialize package manager: {e}")

    def _ensure_initialized(self) -> None:
        """초기화 확인"""
        if not self._initialized:
            self.initialize()

    @property
    def repository(self) -> LocalRepository:
        """저장소 접근"""
        self._ensure_initialized()
        return self._repository

    @property
    def installer(self) -> PackageInstaller:
        """설치자 접근"""
        self._ensure_initialized()
        return self._installer

    @property
    def builder(self) -> PackageBuilder:
        """빌더 접근"""
        self._ensure_initialized()
        return self._builder

    def build_package(
        self,
        source_path: Path,
        output_path: Path,
        package_info: Optional[IPackageInfo] = None,
    ) -> Path:
        """패키지 빌드"""
        self._ensure_initialized()

        # 패키지 정보가 없으면 기본값 생성
        if package_info is None:
            package_info = self._create_default_package_info(source_path)

        # 빌더 설정
        self._builder.set_source_path(source_path)
        self._builder.set_package_info(package_info)

        # 빌드 실행
        return self._builder.build(output_path)

    def _create_default_package_info(self, source_path: Path) -> PackageInfo:
        """기본 패키지 정보 생성"""
        package_name = source_path.name

        # setup.py 또는 pyproject.toml에서 정보 읽기 시도
        setup_py = source_path / "setup.py"
        pyproject_toml = source_path / "pyproject.toml"

        if setup_py.exists():
            # setup.py에서 정보 추출 (간단한 구현)
            package_info = self._parse_setup_py(setup_py)
            if package_info:
                return package_info

        if pyproject_toml.exists():
            # pyproject.toml에서 정보 추출 (간단한 구현)
            package_info = self._parse_pyproject_toml(pyproject_toml)
            if package_info:
                return package_info

        # 기본값 생성
        return PackageInfo(
            _name=package_name,
            _version=SemanticVersion(1, 0, 0),
            _package_type=PackageType.MODULE,
            _description=f"Package for {package_name}",
            _author="Unknown",
        )

    def _parse_setup_py(self, setup_py_path: Path) -> Optional[PackageInfo]:
        """setup.py 파싱 (간단한 구현)"""
        # 실제로는 AST를 이용한 더 정교한 파싱이 필요
        try:
            with open(setup_py_path, "r", encoding="utf-8") as f:
                content = f.read()

            # 간단한 정규식 기반 파싱
            import re

            name_match = re.search(r'name\s*=\s*["\']([^"\']+)["\']', content)
            version_match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', content)
            description_match = re.search(
                r'description\s*=\s*["\']([^"\']+)["\']', content
            )
            author_match = re.search(r'author\s*=\s*["\']([^"\']+)["\']', content)

            if name_match and version_match:
                name = name_match.group(1)
                version_str = version_match.group(1)

                # 버전 파싱
                version_parts = version_str.split(".")
                major = int(version_parts[0]) if len(version_parts) > 0 else 1
                minor = int(version_parts[1]) if len(version_parts) > 1 else 0
                patch = int(version_parts[2]) if len(version_parts) > 2 else 0

                return PackageInfo(
                    _name=name,
                    _version=SemanticVersion(major, minor, patch),
                    _package_type=PackageType.MODULE,
                    _description=(
                        description_match.group(1) if description_match else None
                    ),
                    _author=author_match.group(1) if author_match else None,
                )
        except Exception:
            pass

        return None

    def _parse_pyproject_toml(self, pyproject_path: Path) -> Optional[PackageInfo]:
        """pyproject.toml 파싱 (간단한 구현)"""
        try:
            import toml

            with open(pyproject_path, "r", encoding="utf-8") as f:
                data = toml.load(f)

            project_data = data.get("project", {})
            if "name" in project_data and "version" in project_data:
                name = project_data["name"]
                version_str = project_data["version"]

                # 버전 파싱
                version_parts = version_str.split(".")
                major = int(version_parts[0]) if len(version_parts) > 0 else 1
                minor = int(version_parts[1]) if len(version_parts) > 1 else 0
                patch = int(version_parts[2]) if len(version_parts) > 2 else 0

                return PackageInfo(
                    _name=name,
                    _version=SemanticVersion(major, minor, patch),
                    _package_type=PackageType.MODULE,
                    _description=project_data.get("description"),
                    _author=project_data.get("author"),
                )
        except ImportError:
            # toml 모듈이 없는 경우
            pass
        except Exception:
            pass

        return None

    def publish_package(self, package_path: Path) -> bool:
        """패키지 퍼블리시"""
        self._ensure_initialized()

        # 패키지 파일에서 정보 추출
        package_info = self._extract_package_info(package_path)
        if not package_info:
            raise InvalidPackageError("unknown", ["Cannot extract package information"])

        # 저장소에 저장
        return self._repository.store_package(package_path, package_info)

    def _extract_package_info(self, package_path: Path) -> Optional[PackageInfo]:
        """패키지 파일에서 정보 추출"""
        try:
            import zipfile
            import json

            with zipfile.ZipFile(package_path, "r") as zf:
                # 매니페스트 읽기
                manifest_data = zf.read("manifest.json").decode("utf-8")
                manifest_dict = json.loads(manifest_data)

                # PackageInfo 복원
                package_data = manifest_dict.get("package", {})
                return PackageInfo.from_dict(package_data)

        except Exception:
            return None

    def install_package(self, name: str, version: Optional[str] = None) -> bool:
        """패키지 설치"""
        self._ensure_initialized()

        # 버전 문자열을 SemanticVersion으로 변환
        semantic_version = None
        if version:
            semantic_version = self._parse_version_string(version)

        return self._installer.install_package(name, semantic_version)

    def uninstall_package(self, name: str) -> bool:
        """패키지 제거"""
        self._ensure_initialized()
        return self._installer.uninstall_package(name)

    def update_package(self, name: str, version: Optional[str] = None) -> bool:
        """패키지 업데이트"""
        self._ensure_initialized()

        # 버전 문자열을 SemanticVersion으로 변환
        semantic_version = None
        if version:
            semantic_version = self._parse_version_string(version)

        return self._installer.update_package(name, semantic_version)

    def _parse_version_string(self, version_str: str) -> SemanticVersion:
        """버전 문자열 파싱"""
        try:
            parts = version_str.split(".")
            major = int(parts[0]) if len(parts) > 0 else 0
            minor = int(parts[1]) if len(parts) > 1 else 0
            patch = int(parts[2]) if len(parts) > 2 else 0

            # pre-release와 build 정보 처리
            pre_release = None
            build = None

            if "-" in version_str:
                base_version, rest = version_str.split("-", 1)
                if "+" in rest:
                    pre_release, build = rest.split("+", 1)
                else:
                    pre_release = rest
            elif "+" in version_str:
                base_version, build = version_str.split("+", 1)

            return SemanticVersion(major, minor, patch, pre_release, build)

        except (ValueError, IndexError):
            raise InvalidVersionError(version_str)

    def list_installed_packages(self) -> List[IPackageInfo]:
        """설치된 패키지 목록"""
        self._ensure_initialized()
        return self._installer.get_installed_packages()

    def search_packages(self, query: str) -> List[IPackageInfo]:
        """패키지 검색"""
        self._ensure_initialized()

        # 간단한 패턴 매칭 검색
        pattern = f"*{query}*"
        return self._repository.list_packages(pattern)

    def get_package_statistics(self) -> Dict[str, Any]:
        """패키지 통계 정보"""
        self._ensure_initialized()

        # 저장소 통계
        repo_stats = self._repository.get_repository_statistics()

        # 설치된 패키지 통계
        installed_packages = self.list_installed_packages()
        installed_count = len(installed_packages)

        # 패키지 타입별 통계
        installed_types = {}
        for package in installed_packages:
            package_type = package.package_type.value
            installed_types[package_type] = installed_types.get(package_type, 0) + 1

        return {
            "repository": repo_stats,
            "installed": {
                "total_packages": installed_count,
                "package_types": installed_types,
            },
            "workspace_path": str(self.workspace_path),
        }

    def cleanup(self) -> None:
        """정리 작업"""
        if self._repository:
            # 고아 파일 정리
            self._repository.cleanup_orphaned_files()

        # 임시 파일 정리
        temp_dirs = [self.packages_path / "temp", self.packages_path / ".backup"]

        for temp_dir in temp_dirs:
            if temp_dir.exists():
                import shutil

                try:
                    shutil.rmtree(temp_dir)
                except Exception:
                    pass


# 편의 함수들
def create_package_manager(
    workspace_path: Optional[Union[str, Path]] = None
) -> PackageManager:
    """패키지 관리자 생성"""
    if isinstance(workspace_path, str):
        workspace_path = Path(workspace_path)

    manager = PackageManager(workspace_path)
    manager.initialize()
    return manager


def create_package_info(
    name: str,
    version: str,
    package_type: str = "module",
    description: str = None,
    author: str = None,
) -> PackageInfo:
    """패키지 정보 생성"""
    # 버전 파싱
    version_parts = version.split(".")
    major = int(version_parts[0]) if len(version_parts) > 0 else 1
    minor = int(version_parts[1]) if len(version_parts) > 1 else 0
    patch = int(version_parts[2]) if len(version_parts) > 2 else 0

    semantic_version = SemanticVersion(major, minor, patch)

    # 패키지 타입 변환
    try:
        pkg_type = PackageType(package_type.lower())
    except ValueError:
        pkg_type = PackageType.MODULE

    return PackageInfo(
        _name=name,
        _version=semantic_version,
        _package_type=pkg_type,
        _description=description,
        _author=author,
    )


def build_package(
    source_path: Union[str, Path],
    output_path: Union[str, Path],
    package_info: Optional[IPackageInfo] = None,
) -> Path:
    """패키지 빌드 편의 함수"""
    if isinstance(source_path, str):
        source_path = Path(source_path)
    if isinstance(output_path, str):
        output_path = Path(output_path)

    manager = create_package_manager()
    return manager.build_package(source_path, output_path, package_info)


def install_package(
    name: str,
    version: Optional[str] = None,
    workspace_path: Optional[Union[str, Path]] = None,
) -> bool:
    """패키지 설치 편의 함수"""
    manager = create_package_manager(workspace_path)
    return manager.install_package(name, version)


def uninstall_package(
    name: str, workspace_path: Optional[Union[str, Path]] = None
) -> bool:
    """패키지 제거 편의 함수"""
    manager = create_package_manager(workspace_path)
    return manager.uninstall_package(name)


def list_packages(
    workspace_path: Optional[Union[str, Path]] = None
) -> List[IPackageInfo]:
    """패키지 목록 조회 편의 함수"""
    manager = create_package_manager(workspace_path)
    return manager.list_installed_packages()


# 전역 패키지 관리자 (싱글톤 패턴)
_global_manager: Optional[PackageManager] = None


def get_global_manager() -> PackageManager:
    """전역 패키지 관리자 조회"""
    global _global_manager
    if _global_manager is None:
        _global_manager = create_package_manager()
    return _global_manager


def set_global_workspace(workspace_path: Union[str, Path]) -> None:
    """전역 작업 공간 설정"""
    global _global_manager
    if isinstance(workspace_path, str):
        workspace_path = Path(workspace_path)
    _global_manager = create_package_manager(workspace_path)


# 모듈 종료 시 정리
import atexit  # noqa: E402


def _cleanup_at_exit():
    """모듈 종료 시 정리 작업"""
    global _global_manager
    if _global_manager:
        try:
            _global_manager.cleanup()
        except Exception:
            pass


atexit.register(_cleanup_at_exit)


# __all__ 정의
__all__ = [
    # 클래스들
    "PackageManager",
    "PackageInfo",
    "PackageManifest",
    "SemanticVersion",
    "PackageDependency",
    "PackageEntryPoint",
    "PackageBuilder",
    "LocalRepository",
    "PackageInstaller",
    # 열거형들
    "PackageType",
    "PackageStatus",
    "VersionConstraint",
    # 편의 함수들
    "create_package_manager",
    "create_package_info",
    "build_package",
    "install_package",
    "uninstall_package",
    "list_packages",
    "get_global_manager",
    "set_global_workspace",
    # 예외 클래스들
    "PackageError",
    "PackageNotFoundError",
    "PackageAlreadyExistsError",
    "PackageInstallationError",
    "PackageUninstallationError",
    "DependencyConflictError",
    "InvalidPackageError",
    "IPackageManifest",
    "PackageTimeoutError",
    "PackageSecurityError",
    "PackagePermissionError",
    "PackageChecksumError",
    "PackageIntegrityError",
    # 상수들
    "__version__",
    "__author__",
]
