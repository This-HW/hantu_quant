"""
패키지 설치자 구현

이 모듈은 패키지의 설치, 제거, 업데이트를 담당하는 시스템을 구현합니다.
"""

import shutil
import zipfile
import json
import threading
from typing import Dict, List, Optional, Set, Any
from pathlib import Path
import tempfile
import datetime

from .interfaces import (
    IPackageInstaller, IPackageRepository, IPackageInfo, 
    SemanticVersion, PackageDependency
)
from .metadata import PackageInfo
from .exceptions import (
    PackageNotFoundError, PackageAlreadyInstalledError, PackageNotInstalledError,
    PackageInstallationError, PackageUninstallationError, PackageUpdateError,
    UnresolvedDependencyError, DependencyConflictError, CircularDependencyError
)


class InstalledPackageTracker:
    """설치된 패키지 추적기"""
    
    def __init__(self, install_path: Path):
        """초기화"""
        self.install_path = install_path
        self.metadata_path = install_path / ".hantu_packages"
        self.packages_file = self.metadata_path / "installed_packages.json"
        self._lock = threading.RLock()
        self._initialize()
    
    def _initialize(self) -> None:
        """초기화"""
        self.metadata_path.mkdir(parents=True, exist_ok=True)
        if not self.packages_file.exists():
            self._save_packages_data({})
    
    def _load_packages_data(self) -> Dict[str, Any]:
        """패키지 데이터 로드"""
        try:
            with open(self.packages_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
    
    def _save_packages_data(self, data: Dict[str, Any]) -> None:
        """패키지 데이터 저장"""
        with open(self.packages_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def add_package(self, package_info: IPackageInfo, install_location: str) -> None:
        """패키지 추가"""
        with self._lock:
            data = self._load_packages_data()
            
            package_data = {
                'name': package_info.name,
                'version': str(package_info.version),
                'package_type': package_info.package_type.value,
                'install_location': install_location,
                'installed_at': datetime.datetime.now().isoformat(),
                'dependencies': [
                    {
                        'name': dep.name,
                        'version_constraint': dep.version_constraint,
                        'optional': dep.optional
                    }
                    for dep in package_info.dependencies
                ],
                'entry_points': [
                    {
                        'name': ep.name,
                        'module_path': ep.module_path,
                        'class_name': ep.class_name,
                        'function_name': ep.function_name
                    }
                    for ep in package_info.entry_points
                ],
                'metadata': package_info.to_dict()
            }
            
            data[package_info.name] = package_data
            self._save_packages_data(data)
    
    def remove_package(self, name: str) -> bool:
        """패키지 제거"""
        with self._lock:
            data = self._load_packages_data()
            if name in data:
                del data[name]
                self._save_packages_data(data)
                return True
            return False
    
    def get_package(self, name: str) -> Optional[Dict[str, Any]]:
        """패키지 정보 조회"""
        data = self._load_packages_data()
        return data.get(name)
    
    def list_packages(self) -> List[Dict[str, Any]]:
        """설치된 패키지 목록"""
        data = self._load_packages_data()
        return list(data.values())
    
    def is_package_installed(self, name: str) -> bool:
        """패키지 설치 여부 확인"""
        return self.get_package(name) is not None
    
    def get_installed_version(self, name: str) -> Optional[str]:
        """설치된 패키지 버전 조회"""
        package_data = self.get_package(name)
        return package_data['version'] if package_data else None


class DependencyResolver:
    """의존성 해결기"""
    
    def __init__(self, repository: IPackageRepository, tracker: InstalledPackageTracker):
        """초기화"""
        self.repository = repository
        self.tracker = tracker
    
    def resolve_dependencies(self, dependencies: List[PackageDependency]) -> List[IPackageInfo]:
        """의존성 해결"""
        resolved_packages = []
        resolution_order = []
        
        # 의존성 그래프 구축
        dependency_graph = self._build_dependency_graph(dependencies)
        
        # 순환 의존성 확인
        cycles = self._detect_circular_dependencies(dependency_graph)
        if cycles:
            raise CircularDependencyError(cycles[0])
        
        # 위상 정렬로 설치 순서 결정
        resolution_order = self._topological_sort(dependency_graph)
        
        # 의존성 해결
        for package_name in resolution_order:
            if not self.tracker.is_package_installed(package_name):
                package_info = self.repository.get_package_info(package_name)
                if package_info:
                    resolved_packages.append(package_info)
                else:
                    raise UnresolvedDependencyError("unknown", package_name)
        
        return resolved_packages
    
    def _build_dependency_graph(self, dependencies: List[PackageDependency]) -> Dict[str, List[str]]:
        """의존성 그래프 구축"""
        graph = {}
        visited = set()
        
        def visit(dep_name: str):
            if dep_name in visited:
                return
            visited.add(dep_name)
            
            package_info = self.repository.get_package_info(dep_name)
            if not package_info:
                return
            
            graph[dep_name] = []
            for sub_dep in package_info.dependencies:
                if not sub_dep.optional:
                    graph[dep_name].append(sub_dep.name)
                    visit(sub_dep.name)
        
        # 루트 의존성부터 시작
        for dep in dependencies:
            if not dep.optional:
                visit(dep.name)
        
        return graph
    
    def _detect_circular_dependencies(self, graph: Dict[str, List[str]]) -> List[List[str]]:
        """순환 의존성 탐지"""
        def dfs(node: str, path: List[str], visited: Set[str]) -> Optional[List[str]]:
            if node in path:
                # 순환 발견
                cycle_start = path.index(node)
                return path[cycle_start:] + [node]
            
            if node in visited:
                return None
            
            visited.add(node)
            path.append(node)
            
            for neighbor in graph.get(node, []):
                cycle = dfs(neighbor, path, visited)
                if cycle:
                    return cycle
            
            path.pop()
            return None
        
        visited = set()
        cycles = []
        
        for node in graph:
            if node not in visited:
                cycle = dfs(node, [], visited)
                if cycle:
                    cycles.append(cycle)
        
        return cycles
    
    def _topological_sort(self, graph: Dict[str, List[str]]) -> List[str]:
        """위상 정렬"""
        in_degree = {node: 0 for node in graph}
        
        # 진입 차수 계산
        for node in graph:
            for neighbor in graph[node]:
                if neighbor in in_degree:
                    in_degree[neighbor] += 1
                else:
                    in_degree[neighbor] = 1
        
        # 진입 차수가 0인 노드들부터 시작
        queue = [node for node, degree in in_degree.items() if degree == 0]
        result = []
        
        while queue:
            node = queue.pop(0)
            result.append(node)
            
            for neighbor in graph.get(node, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        return result
    
    def check_conflicts(self, package_info: IPackageInfo) -> List[str]:
        """의존성 충돌 확인"""
        conflicts = []
        
        # 현재 설치된 패키지들과 충돌 확인
        installed_packages = self.tracker.list_packages()
        
        for installed_pkg in installed_packages:
            installed_name = installed_pkg['name']
            installed_version = installed_pkg['version']
            
            # 같은 이름의 패키지가 이미 설치되어 있는지 확인
            if installed_name == package_info.name:
                if installed_version != str(package_info.version):
                    conflicts.append(
                        f"Package {installed_name} version conflict: "
                        f"installed {installed_version}, required {package_info.version}"
                    )
            
            # 의존성 버전 충돌 확인
            for dep in package_info.dependencies:
                if installed_name == dep.name:
                    # 버전 제약 조건 확인 (간단한 구현)
                    if dep.version_constraint and not self._is_version_compatible(
                        installed_version, dep.version_constraint
                    ):
                        conflicts.append(
                            f"Dependency version conflict for {dep.name}: "
                            f"installed {installed_version}, required {dep.version_constraint}"
                        )
        
        return conflicts
    
    def _is_version_compatible(self, installed_version: str, constraint: str) -> bool:
        """버전 호환성 확인"""
        # 간단한 버전 호환성 확인 (실제로는 더 복잡한 로직 필요)
        if constraint.startswith(">="):
            required_version = constraint[2:].strip()
            return installed_version >= required_version
        elif constraint.startswith("=="):
            required_version = constraint[2:].strip()
            return installed_version == required_version
        else:
            return True  # 기본적으로 호환 가능하다고 가정


class PackageInstaller(IPackageInstaller):
    """패키지 설치자 구현"""
    
    def __init__(self, repository: IPackageRepository, install_path: Path):
        """초기화"""
        self.repository = repository
        self.install_path = install_path
        self.tracker = InstalledPackageTracker(install_path)
        self.dependency_resolver = DependencyResolver(repository, self.tracker)
        self._lock = threading.RLock()
        
        # 설치 경로 생성
        self.install_path.mkdir(parents=True, exist_ok=True)
    
    def install_package(self, name: str, version: Optional[SemanticVersion] = None,
                       force: bool = False) -> bool:
        """패키지 설치"""
        with self._lock:
            try:
                # 이미 설치되어 있는지 확인
                if self.tracker.is_package_installed(name) and not force:
                    installed_version = self.tracker.get_installed_version(name)
                    raise PackageAlreadyInstalledError(name, installed_version)
                
                # 패키지 정보 조회
                package_info = self.repository.get_package_info(name, version)
                if not package_info:
                    raise PackageNotFoundError(name, str(version) if version else None)
                
                # 충돌 확인
                conflicts = self.dependency_resolver.check_conflicts(package_info)
                if conflicts and not force:
                    raise DependencyConflictError(name, conflicts)
                
                # 의존성 해결
                dependencies_to_install = self.dependency_resolver.resolve_dependencies(
                    package_info.dependencies
                )
                
                # 의존성 먼저 설치
                for dep_package in dependencies_to_install:
                    if not self.tracker.is_package_installed(dep_package.name):
                        self._install_single_package(dep_package)
                
                # 메인 패키지 설치
                self._install_single_package(package_info)
                
                return True
                
            except Exception as e:
                if isinstance(e, (PackageNotFoundError, PackageAlreadyInstalledError, 
                                DependencyConflictError, UnresolvedDependencyError)):
                    raise
                raise PackageInstallationError(name, f"Installation failed: {e}", e)
    
    def _install_single_package(self, package_info: IPackageInfo) -> None:
        """단일 패키지 설치"""
        # 패키지 파일 조회
        package_path = self.repository.get_package(package_info.name, package_info.version)
        if not package_path:
            raise PackageNotFoundError(package_info.name, str(package_info.version))
        
        # 임시 디렉토리에 압축 해제
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # 패키지 파일 압축 해제
            with zipfile.ZipFile(package_path, 'r') as zf:
                zf.extractall(temp_path)
            
            # 설치 위치 결정
            package_install_path = self.install_path / package_info.name
            
            # 기존 설치 제거 (force 설치인 경우)
            if package_install_path.exists():
                shutil.rmtree(package_install_path)
            
            # 모듈 파일들 복사
            module_source = temp_path / "module"
            if module_source.exists():
                shutil.copytree(module_source, package_install_path)
            else:
                package_install_path.mkdir(parents=True, exist_ok=True)
            
            # 설치 정보 기록
            self.tracker.add_package(package_info, str(package_install_path))
            
            # 엔트리 포인트 등록
            self._register_entry_points(package_info)
    
    def _register_entry_points(self, package_info: IPackageInfo) -> None:
        """엔트리 포인트 등록"""
        # 기존 시스템과 통합 (플러그인 시스템, DI 컨테이너 등)
        try:
            # 모듈 레지스트리에 등록
            from ..registry import ModuleRegistry
            from ..registry.metadata import ModuleMetadata
            from ..registry.interfaces import ModuleType, ModuleStatus
            
            registry = ModuleRegistry()
            
            # PackageInfo를 ModuleMetadata로 변환
            module_metadata = ModuleMetadata(
                name=package_info.name,
                version=package_info.version,
                module_type=ModuleType.PACKAGE,  # 새로운 타입 추가 필요
                description=package_info.description,
                author=package_info.author,
                dependencies=[dep.name for dep in package_info.dependencies],
                entry_points={ep.name: ep.get_import_path() for ep in package_info.entry_points}
            )
            
            registry.register_module(module_metadata)
            
        except ImportError:
            # 모듈 레지스트리가 없는 경우 건너뛰기
            pass
        except Exception as e:
            # 등록 실패는 로그만 남기고 설치는 계속 진행
            print(f"Warning: Failed to register entry points: {e}")
    
    def uninstall_package(self, name: str) -> bool:
        """패키지 제거"""
        with self._lock:
            try:
                # 설치되어 있는지 확인
                if not self.tracker.is_package_installed(name):
                    raise PackageNotInstalledError(name)
                
                # 패키지 정보 조회
                package_data = self.tracker.get_package(name)
                if not package_data:
                    raise PackageNotInstalledError(name)
                
                # 다른 패키지의 의존성 확인
                dependent_packages = self._find_dependent_packages(name)
                if dependent_packages:
                    raise PackageUninstallationError(
                        name, 
                        f"Cannot uninstall: required by {', '.join(dependent_packages)}"
                    )
                
                # 엔트리 포인트 해제
                self._unregister_entry_points(name)
                
                # 파일 제거
                install_location = Path(package_data['install_location'])
                if install_location.exists():
                    shutil.rmtree(install_location)
                
                # 설치 정보 제거
                self.tracker.remove_package(name)
                
                return True
                
            except Exception as e:
                if isinstance(e, (PackageNotInstalledError, PackageUninstallationError)):
                    raise
                raise PackageUninstallationError(name, f"Uninstallation failed: {e}", e)
    
    def _find_dependent_packages(self, package_name: str) -> List[str]:
        """의존하는 패키지들 찾기"""
        dependent_packages = []
        installed_packages = self.tracker.list_packages()
        
        for installed_pkg in installed_packages:
            if installed_pkg['name'] == package_name:
                continue
            
            for dep in installed_pkg.get('dependencies', []):
                if dep['name'] == package_name and not dep.get('optional', False):
                    dependent_packages.append(installed_pkg['name'])
                    break
        
        return dependent_packages
    
    def _unregister_entry_points(self, package_name: str) -> None:
        """엔트리 포인트 해제"""
        try:
            # 모듈 레지스트리에서 제거
            from ..registry import ModuleRegistry
            
            registry = ModuleRegistry()
            registry.unregister_module(package_name)
            
        except ImportError:
            pass
        except Exception as e:
            print(f"Warning: Failed to unregister entry points: {e}")
    
    def update_package(self, name: str, target_version: Optional[SemanticVersion] = None) -> bool:
        """패키지 업데이트"""
        with self._lock:
            try:
                # 현재 설치된 버전 확인
                if not self.tracker.is_package_installed(name):
                    raise PackageNotInstalledError(name)
                
                current_version = self.tracker.get_installed_version(name)
                
                # 대상 버전 결정
                if target_version is None:
                    # 최신 버전 찾기
                    available_versions = self.repository.get_package_versions(name)
                    if not available_versions:
                        raise PackageNotFoundError(name)
                    target_version = max(available_versions)
                
                # 동일한 버전인지 확인
                if str(target_version) == current_version:
                    return True  # 업데이트 불필요
                
                # 백업 생성
                backup_info = self._create_backup(name)
                
                try:
                    # 기존 패키지 제거 (의존성 확인 스킵)
                    package_data = self.tracker.get_package(name)
                    install_location = Path(package_data['install_location'])
                    if install_location.exists():
                        shutil.rmtree(install_location)
                    
                    self.tracker.remove_package(name)
                    
                    # 새 버전 설치
                    self.install_package(name, target_version, force=True)
                    
                    # 백업 정리
                    self._cleanup_backup(backup_info)
                    
                    return True
                    
                except Exception as e:
                    # 롤백
                    self._rollback_from_backup(backup_info)
                    raise PackageUpdateError(
                        name, current_version, str(target_version), 
                        f"Update failed: {e}", e
                    )
                
            except Exception as e:
                if isinstance(e, (PackageNotInstalledError, PackageNotFoundError, 
                                PackageUpdateError)):
                    raise
                raise PackageUpdateError(
                    name, "unknown", str(target_version) if target_version else "unknown",
                    f"Update failed: {e}", e
                )
    
    def _create_backup(self, package_name: str) -> Dict[str, Any]:
        """패키지 백업 생성"""
        package_data = self.tracker.get_package(package_name)
        backup_dir = self.install_path / ".backup" / package_name
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        # 설치 파일들 백업
        install_location = Path(package_data['install_location'])
        backup_files_dir = backup_dir / "files"
        if install_location.exists():
            shutil.copytree(install_location, backup_files_dir)
        
        # 메타데이터 백업
        backup_metadata_file = backup_dir / "metadata.json"
        with open(backup_metadata_file, 'w', encoding='utf-8') as f:
            json.dump(package_data, f, indent=2, ensure_ascii=False)
        
        return {
            'package_name': package_name,
            'backup_dir': backup_dir,
            'original_location': install_location
        }
    
    def _rollback_from_backup(self, backup_info: Dict[str, Any]) -> None:
        """백업에서 롤백"""
        backup_dir = backup_info['backup_dir']
        original_location = backup_info['original_location']
        
        # 현재 설치 제거
        if original_location.exists():
            shutil.rmtree(original_location)
        
        # 백업에서 복원
        backup_files_dir = backup_dir / "files"
        if backup_files_dir.exists():
            shutil.copytree(backup_files_dir, original_location)
        
        # 메타데이터 복원
        backup_metadata_file = backup_dir / "metadata.json"
        if backup_metadata_file.exists():
            with open(backup_metadata_file, 'r', encoding='utf-8') as f:
                package_data = json.load(f)
            
            # PackageInfo 복원
            package_info = PackageInfo.from_dict(package_data['metadata'])
            self.tracker.add_package(package_info, str(original_location))
    
    def _cleanup_backup(self, backup_info: Dict[str, Any]) -> None:
        """백업 정리"""
        backup_dir = backup_info['backup_dir']
        if backup_dir.exists():
            shutil.rmtree(backup_dir)
    
    def resolve_dependencies(self, dependencies: List[PackageDependency]) -> List[IPackageInfo]:
        """의존성 해결"""
        return self.dependency_resolver.resolve_dependencies(dependencies)
    
    def check_conflicts(self, package_info: IPackageInfo) -> List[str]:
        """의존성 충돌 확인"""
        return self.dependency_resolver.check_conflicts(package_info)
    
    def get_installed_packages(self) -> List[IPackageInfo]:
        """설치된 패키지 목록 조회"""
        installed_packages = []
        for package_data in self.tracker.list_packages():
            try:
                metadata = package_data['metadata']
                package_info = PackageInfo.from_dict(metadata)
                installed_packages.append(package_info)
            except Exception:
                continue
        return installed_packages
    
    def is_package_installed(self, name: str) -> bool:
        """패키지 설치 여부 확인"""
        return self.tracker.is_package_installed(name) 