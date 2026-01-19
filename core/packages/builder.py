"""
패키지 빌더 구현

이 모듈은 패키지를 빌드하는데 필요한 클래스들을 포함합니다.
소스 코드를 수집하고, 의존성을 해결하며, 패키지 파일을 생성합니다.
"""

import os
import shutil
import zipfile
import hashlib
import json
import glob
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
import datetime
import tempfile

from .interfaces import IPackageBuilder, IPackageInfo, SemanticVersion
from .metadata import PackageManifest
from .exceptions import (
    PackageBuildError, PackageValidationError
)


class AssetCollector:
    """패키지 자산 수집기"""
    
    def __init__(self, source_path: Path):
        """초기화"""
        self.source_path = source_path
        self.include_patterns: List[str] = []
        self.exclude_patterns: List[str] = []
        self.collected_files: List[str] = []
    
    def add_include_pattern(self, pattern: str) -> None:
        """포함 패턴 추가"""
        self.include_patterns.append(pattern)
    
    def add_exclude_pattern(self, pattern: str) -> None:
        """제외 패턴 추가"""
        self.exclude_patterns.append(pattern)
    
    def set_default_patterns(self) -> None:
        """기본 패턴 설정"""
        # 포함할 파일 패턴
        self.include_patterns.extend([
            "**/*.py",
            "**/*.json",
            "**/*.yml",
            "**/*.yaml",
            "**/*.txt",
            "**/*.md",
            "**/*.cfg",
            "**/*.ini"
        ])
        
        # 제외할 파일 패턴
        self.exclude_patterns.extend([
            "**/__pycache__/**",
            "**/*.pyc",
            "**/*.pyo",
            "**/*.pyd",
            "**/test_*.py",
            "**/tests/**",
            "**/.git/**",
            "**/.pytest_cache/**",
            "**/.vscode/**",
            "**/.idea/**",
            "**/node_modules/**",
            "**/.env",
            "**/Thumbs.db",
            "**/.DS_Store"
        ])
    
    def collect_files(self) -> List[str]:
        """파일 수집"""
        if not self.source_path.exists():
            raise PackageBuildError("unknown", "collect_files", 
                                   FileNotFoundError(f"Source path not found: {self.source_path}"))
        
        collected = set()
        
        # 포함 패턴으로 파일 수집
        for pattern in self.include_patterns:
            pattern_path = self.source_path / pattern
            for file_path in glob.glob(str(pattern_path), recursive=True):
                if Path(file_path).is_file():
                    rel_path = os.path.relpath(file_path, self.source_path)
                    collected.add(rel_path.replace('\\', '/'))  # 경로 구분자 통일
        
        # 제외 패턴으로 파일 제거
        for pattern in self.exclude_patterns:
            pattern_path = self.source_path / pattern
            for file_path in glob.glob(str(pattern_path), recursive=True):
                if Path(file_path).is_file():
                    rel_path = os.path.relpath(file_path, self.source_path)
                    rel_path = rel_path.replace('\\', '/')  # 경로 구분자 통일
                    collected.discard(rel_path)
        
        self.collected_files = sorted(list(collected))
        return self.collected_files
    
    def get_file_info(self, file_path: str) -> Dict[str, Any]:
        """파일 정보 조회"""
        full_path = self.source_path / file_path
        if not full_path.exists():
            return {}
        
        stat = full_path.stat()
        return {
            'path': file_path,
            'size': stat.st_size,
            'modified': datetime.datetime.fromtimestamp(stat.st_mtime).isoformat(),
            'is_binary': self._is_binary_file(full_path)
        }
    
    def _is_binary_file(self, file_path: Path) -> bool:
        """바이너리 파일 여부 확인"""
        try:
            with open(file_path, 'rb') as f:
                chunk = f.read(1024)
                return b'\0' in chunk
        except Exception:
            return True
    
    def get_total_size(self) -> int:
        """전체 파일 크기 계산"""
        total_size = 0
        for file_path in self.collected_files:
            full_path = self.source_path / file_path
            if full_path.exists():
                total_size += full_path.stat().st_size
        return total_size


class DependencyResolver:
    """의존성 해결기"""
    
    def __init__(self):
        """초기화"""
        self.resolved_dependencies: Dict[str, SemanticVersion] = {}
        self.dependency_graph: Dict[str, List[str]] = {}
    
    def add_dependency(self, name: str, version: SemanticVersion) -> None:
        """의존성 추가"""
        self.resolved_dependencies[name] = version
    
    def resolve_dependencies(self, package_info: IPackageInfo) -> Dict[str, SemanticVersion]:
        """의존성 해결"""
        resolved = {}
        
        for dependency in package_info.dependencies:
            if dependency.optional:
                continue
            
            # 간단한 의존성 해결 로직 (실제로는 더 복잡)
            if dependency.version_constraint:
                # 버전 제약 조건 파싱 및 해결
                resolved_version = self._resolve_version_constraint(
                    dependency.name, dependency.version_constraint
                )
                if resolved_version:
                    resolved[dependency.name] = resolved_version
            else:
                # 최신 버전 사용
                resolved[dependency.name] = SemanticVersion(1, 0, 0)
        
        return resolved
    
    def _resolve_version_constraint(self, package_name: str, 
                                  constraint: str) -> Optional[SemanticVersion]:
        """버전 제약 조건 해결"""
        # 간단한 구현 (실제로는 더 복잡한 파싱 필요)
        if constraint.startswith(">="):
            version_str = constraint[2:].strip()
            return self._parse_version_string(version_str)
        elif constraint.startswith("=="):
            version_str = constraint[2:].strip()
            return self._parse_version_string(version_str)
        else:
            # 기본값
            return SemanticVersion(1, 0, 0)
    
    def _parse_version_string(self, version_str: str) -> Optional[SemanticVersion]:
        """버전 문자열 파싱"""
        try:
            parts = version_str.split('.')
            major = int(parts[0]) if len(parts) > 0 else 0
            minor = int(parts[1]) if len(parts) > 1 else 0
            patch = int(parts[2]) if len(parts) > 2 else 0
            return SemanticVersion(major, minor, patch)
        except (ValueError, IndexError):
            return None
    
    def check_dependency_conflicts(self, dependencies: Dict[str, SemanticVersion]) -> List[str]:
        """의존성 충돌 확인"""
        conflicts = []
        
        # 간단한 충돌 검사 (실제로는 더 복잡)
        for name, version in dependencies.items():
            if name in self.resolved_dependencies:
                existing_version = self.resolved_dependencies[name]
                if not version.is_compatible_with(existing_version):
                    conflicts.append(
                        f"Version conflict for {name}: "
                        f"required {version}, existing {existing_version}"
                    )
        
        return conflicts


class PackageValidator:
    """패키지 검증기"""
    
    def __init__(self):
        """초기화"""
        self.validation_rules: List[callable] = []
        self._setup_default_rules()
    
    def _setup_default_rules(self) -> None:
        """기본 검증 규칙 설정"""
        self.validation_rules.extend([
            self._validate_package_structure,
            self._validate_entry_points,
            self._validate_dependencies,
            self._validate_python_syntax,
            self._validate_manifest
        ])
    
    def validate_package(self, package_info: IPackageInfo, 
                        source_path: Path) -> Tuple[bool, List[str]]:
        """패키지 검증"""
        errors = []
        
        for rule in self.validation_rules:
            try:
                rule_errors = rule(package_info, source_path)
                errors.extend(rule_errors)
            except Exception as e:
                errors.append(f"Validation rule failed: {e}")
        
        return len(errors) == 0, errors
    
    def _validate_package_structure(self, package_info: IPackageInfo, 
                                  source_path: Path) -> List[str]:
        """패키지 구조 검증"""
        errors = []
        
        # 필수 파일 확인
        required_files = ['__init__.py']
        for file_name in required_files:
            if not (source_path / file_name).exists():
                errors.append(f"Required file missing: {file_name}")
        
        # 패키지 파일 확인
        for file_path in package_info.files:
            full_path = source_path / file_path
            if not full_path.exists():
                errors.append(f"Listed file not found: {file_path}")
        
        return errors
    
    def _validate_entry_points(self, package_info: IPackageInfo, 
                             source_path: Path) -> List[str]:
        """엔트리 포인트 검증"""
        errors = []
        
        for entry_point in package_info.entry_points:
            module_path = entry_point.module_path.replace('.', '/')
            
            # 모듈 파일 존재 확인
            possible_paths = [
                source_path / f"{module_path}.py",
                source_path / module_path / "__init__.py"
            ]
            
            if not any(path.exists() for path in possible_paths):
                errors.append(f"Entry point module not found: {entry_point.module_path}")
        
        return errors
    
    def _validate_dependencies(self, package_info: IPackageInfo, 
                             source_path: Path) -> List[str]:
        """의존성 검증"""
        errors = []
        
        # 의존성 형식 검증
        for dependency in package_info.dependencies:
            if not dependency.name:
                errors.append("Dependency name cannot be empty")
            
            if dependency.version_constraint:
                # 버전 제약 조건 형식 검증
                if not self._is_valid_version_constraint(dependency.version_constraint):
                    errors.append(f"Invalid version constraint: {dependency.version_constraint}")
        
        return errors
    
    def _validate_python_syntax(self, package_info: IPackageInfo, 
                               source_path: Path) -> List[str]:
        """Python 구문 검증"""
        errors = []
        
        # Python 파일 구문 검사
        for file_path in package_info.files:
            if file_path.endswith('.py'):
                full_path = source_path / file_path
                if full_path.exists():
                    try:
                        with open(full_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        compile(content, str(full_path), 'exec')
                    except SyntaxError as e:
                        errors.append(f"Syntax error in {file_path}: {e}")
                    except Exception as e:
                        errors.append(f"Error reading {file_path}: {e}")
        
        return errors
    
    def _validate_manifest(self, package_info: IPackageInfo, 
                          source_path: Path) -> List[str]:
        """매니페스트 검증"""
        errors = []
        
        # 패키지 정보 필수 필드 확인
        if not package_info.name:
            errors.append("Package name is required")
        
        if not package_info.version:
            errors.append("Package version is required")
        
        # 버전 형식 확인
        if package_info.version:
            if (package_info.version.major < 0 or 
                package_info.version.minor < 0 or 
                package_info.version.patch < 0):
                errors.append("Version numbers must be non-negative")
        
        return errors
    
    def _is_valid_version_constraint(self, constraint: str) -> bool:
        """버전 제약 조건 유효성 확인"""
        # 간단한 유효성 검사
        valid_operators = ['==', '>=', '>', '<=', '<', '~=']
        return any(constraint.startswith(op) for op in valid_operators)


class PackageBuilder(IPackageBuilder):
    """패키지 빌더 구현 클래스"""
    
    def __init__(self):
        """초기화"""
        self._source_path: Optional[Path] = None
        self._package_info: Optional[IPackageInfo] = None
        self._asset_collector = None
        self._dependency_resolver = DependencyResolver()
        self._validator = PackageValidator()
        self._build_info: Dict[str, Any] = {}
        self._temp_dir: Optional[Path] = None
    
    def set_source_path(self, path: Path) -> None:
        """소스 경로 설정"""
        if not path.exists():
            raise PackageBuildError("unknown", "set_source_path", 
                                   FileNotFoundError(f"Source path not found: {path}"))
        
        self._source_path = path
        self._asset_collector = AssetCollector(path)
        self._asset_collector.set_default_patterns()
    
    def set_package_info(self, package_info: IPackageInfo) -> None:
        """패키지 정보 설정"""
        self._package_info = package_info
    
    def add_include_pattern(self, pattern: str) -> None:
        """포함 패턴 추가"""
        if self._asset_collector:
            self._asset_collector.add_include_pattern(pattern)
    
    def add_exclude_pattern(self, pattern: str) -> None:
        """제외 패턴 추가"""
        if self._asset_collector:
            self._asset_collector.add_exclude_pattern(pattern)
    
    def collect_files(self) -> List[str]:
        """패키지에 포함될 파일 수집"""
        if not self._asset_collector:
            raise PackageBuildError("unknown", "collect_files", 
                                   ValueError("Source path not set"))
        
        try:
            collected_files = self._asset_collector.collect_files()
            
            # 패키지 정보에 파일 목록 업데이트
            if self._package_info and hasattr(self._package_info, '_files'):
                self._package_info._files = collected_files
            
            return collected_files
        except Exception as e:
            raise PackageBuildError("unknown", "collect_files", e)
    
    def validate_package(self) -> Tuple[bool, List[str]]:
        """패키지 유효성 검증"""
        if not self._package_info:
            return False, ["Package info not set"]
        
        if not self._source_path:
            return False, ["Source path not set"]
        
        try:
            return self._validator.validate_package(self._package_info, self._source_path)
        except Exception as e:
            return False, [f"Validation failed: {e}"]
    
    def build(self, output_path: Path) -> Path:
        """패키지 빌드"""
        if not self._package_info:
            raise PackageBuildError("unknown", "build", ValueError("Package info not set"))
        
        if not self._source_path:
            raise PackageBuildError("unknown", "build", ValueError("Source path not set"))
        
        package_name = self._package_info.name
        
        try:
            # 1. 파일 수집
            collected_files = self.collect_files()
            
            # 2. 패키지 검증
            is_valid, validation_errors = self.validate_package()
            if not is_valid:
                raise PackageBuildError(package_name, "validation", 
                                       PackageValidationError(package_name, validation_errors))
            
            # 3. 의존성 해결
            resolved_deps = self._dependency_resolver.resolve_dependencies(self._package_info)
            dependency_conflicts = self._dependency_resolver.check_dependency_conflicts(resolved_deps)
            if dependency_conflicts:
                raise PackageBuildError(package_name, "dependency_resolution", 
                                       Exception(f"Dependency conflicts: {dependency_conflicts}"))
            
            # 4. 임시 디렉토리 생성
            self._temp_dir = Path(tempfile.mkdtemp(prefix="hantu_package_"))
            
            # 5. 패키지 파일 생성
            package_file_path = self._create_package_file(output_path, collected_files)
            
            # 6. 빌드 정보 업데이트
            self._update_build_info(collected_files, resolved_deps)
            
            return package_file_path
            
        except Exception as e:
            if isinstance(e, PackageBuildError):
                raise
            raise PackageBuildError(package_name, "build", e)
        finally:
            # 임시 디렉토리 정리
            self._cleanup_temp_dir()
    
    def _create_package_file(self, output_path: Path, files: List[str]) -> Path:
        """패키지 파일 생성"""
        package_name = self._package_info.name
        package_version = str(self._package_info.version)
        
        # 출력 파일 경로
        package_filename = f"{package_name}-{package_version}.hqp"
        package_file_path = output_path / package_filename
        
        # 출력 디렉토리 생성
        output_path.mkdir(parents=True, exist_ok=True)
        
        try:
            with zipfile.ZipFile(package_file_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                # 매니페스트 파일 추가
                manifest = PackageManifest(self._package_info)
                manifest_json = json.dumps(manifest.to_dict(), indent=2, ensure_ascii=False)
                zf.writestr('manifest.json', manifest_json)
                
                # 의존성 정보 추가
                dependencies_info = {
                    'dependencies': [
                        {
                            'name': dep.name,
                            'version_constraint': dep.version_constraint,
                            'optional': dep.optional
                        }
                        for dep in self._package_info.dependencies
                    ]
                }
                zf.writestr('dependencies.json', 
                           json.dumps(dependencies_info, indent=2, ensure_ascii=False))
                
                # 소스 파일들 추가
                for file_path in files:
                    source_file = self._source_path / file_path
                    if source_file.exists():
                        # 패키지 내 경로: module/file_path
                        archive_path = f"module/{file_path}"
                        zf.write(source_file, archive_path)
                
                # 빌드 정보 추가
                build_info = self.get_build_info()
                zf.writestr('build_info.json', 
                           json.dumps(build_info, indent=2, ensure_ascii=False))
            
            # 패키지 체크섬 계산 및 설정
            checksum = self._calculate_file_checksum(package_file_path)
            if hasattr(self._package_info, 'set_checksum'):
                self._package_info.set_checksum(checksum)
            
            # 패키지 크기 설정
            size = package_file_path.stat().st_size
            if hasattr(self._package_info, 'set_size'):
                self._package_info.set_size(size)
            
            return package_file_path
            
        except Exception:
            # 생성 실패 시 파일 삭제
            if package_file_path.exists():
                package_file_path.unlink()
            raise
    
    def _calculate_file_checksum(self, file_path: Path) -> str:
        """파일 체크섬 계산"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    def _update_build_info(self, files: List[str], dependencies: Dict[str, SemanticVersion]) -> None:
        """빌드 정보 업데이트"""
        self._build_info = {
            'build_time': datetime.datetime.now().isoformat(),
            'builder_version': '1.0.0',
            'source_path': str(self._source_path),
            'files_count': len(files),
            'total_size': self._asset_collector.get_total_size() if self._asset_collector else 0,
            'dependencies': {name: str(version) for name, version in dependencies.items()},
            'python_version': f"{os.sys.version_info.major}.{os.sys.version_info.minor}",
            'platform': os.name
        }
    
    def _cleanup_temp_dir(self) -> None:
        """임시 디렉토리 정리"""
        if self._temp_dir and self._temp_dir.exists():
            try:
                shutil.rmtree(self._temp_dir)
            except Exception:
                pass  # 정리 실패는 무시
            finally:
                self._temp_dir = None
    
    def get_build_info(self) -> Dict[str, Any]:
        """빌드 정보 조회"""
        return self._build_info.copy()
    
    def __del__(self):
        """소멸자 - 임시 디렉토리 정리"""
        self._cleanup_temp_dir() 