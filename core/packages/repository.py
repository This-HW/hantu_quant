"""
패키지 저장소 구현

이 모듈은 패키지를 저장하고 관리하는 저장소 시스템을 구현합니다.
로컬 저장소와 원격 저장소를 지원합니다.
"""

import json
import shutil
import sqlite3
import threading
from typing import Dict, List, Optional, Any
from pathlib import Path
import datetime
import fnmatch

from .interfaces import IPackageRepository, IPackageInfo, SemanticVersion
from .metadata import PackageInfo, PackageManifest
from .exceptions import (
    RepositoryError, RepositoryNotFoundError, RepositoryCorruptedError,
    PackageNotFoundError, PackageAlreadyExistsError, RepositoryLockError
)


class PackageIndex:
    """패키지 인덱스 관리"""
    
    def __init__(self, index_path: Path):
        """초기화"""
        self.index_path = index_path
        self.db_path = index_path / "packages.db"
        self._lock = threading.RLock()
        self._initialize_database()
    
    def _initialize_database(self) -> None:
        """데이터베이스 초기화"""
        self.index_path.mkdir(parents=True, exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS packages (
                    name TEXT NOT NULL,
                    version TEXT NOT NULL,
                    package_type TEXT NOT NULL,
                    description TEXT,
                    author TEXT,
                    license TEXT,
                    homepage TEXT,
                    repository TEXT,
                    file_path TEXT NOT NULL,
                    checksum TEXT,
                    size INTEGER,
                    created_at TEXT NOT NULL,
                    keywords TEXT,
                    python_requires TEXT,
                    metadata TEXT,
                    PRIMARY KEY (name, version)
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS dependencies (
                    package_name TEXT NOT NULL,
                    package_version TEXT NOT NULL,
                    dependency_name TEXT NOT NULL,
                    version_constraint TEXT,
                    constraint_type TEXT,
                    optional BOOLEAN DEFAULT FALSE,
                    FOREIGN KEY (package_name, package_version) 
                        REFERENCES packages (name, version)
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS entry_points (
                    package_name TEXT NOT NULL,
                    package_version TEXT NOT NULL,
                    name TEXT NOT NULL,
                    module_path TEXT NOT NULL,
                    class_name TEXT,
                    function_name TEXT,
                    description TEXT,
                    FOREIGN KEY (package_name, package_version) 
                        REFERENCES packages (name, version)
                )
            """)
            
            conn.commit()
    
    def add_package(self, package_info: IPackageInfo, file_path: str) -> None:
        """패키지 추가"""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                try:
                    # 패키지 기본 정보 삽입
                    conn.execute("""
                        INSERT INTO packages (
                            name, version, package_type, description, author, license,
                            homepage, repository, file_path, checksum, size, created_at,
                            keywords, python_requires, metadata
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        package_info.name,
                        str(package_info.version),
                        package_info.package_type.value,
                        package_info.description,
                        package_info.author,
                        package_info.license,
                        getattr(package_info, 'homepage', None),
                        getattr(package_info, 'repository', None),
                        file_path,
                        getattr(package_info, 'checksum', None),
                        getattr(package_info, 'size', None),
                        package_info.created_at.isoformat(),
                        json.dumps(getattr(package_info, 'keywords', [])),
                        getattr(package_info, 'python_requires', None),
                        json.dumps(package_info.to_dict())
                    ))
                    
                    # 의존성 정보 삽입
                    for dep in package_info.dependencies:
                        conn.execute("""
                            INSERT INTO dependencies (
                                package_name, package_version, dependency_name,
                                version_constraint, constraint_type, optional
                            ) VALUES (?, ?, ?, ?, ?, ?)
                        """, (
                            package_info.name,
                            str(package_info.version),
                            dep.name,
                            dep.version_constraint,
                            dep.constraint_type.value,
                            dep.optional
                        ))
                    
                    # 엔트리 포인트 정보 삽입
                    for ep in package_info.entry_points:
                        conn.execute("""
                            INSERT INTO entry_points (
                                package_name, package_version, name, module_path,
                                class_name, function_name, description
                            ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (
                            package_info.name,
                            str(package_info.version),
                            ep.name,
                            ep.module_path,
                            ep.class_name,
                            ep.function_name,
                            ep.description
                        ))
                    
                    conn.commit()
                    
                except sqlite3.IntegrityError:
                    raise PackageAlreadyExistsError(package_info.name, str(package_info.version))
    
    def remove_package(self, name: str, version: Optional[str] = None) -> bool:
        """패키지 제거"""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                if version:
                    # 특정 버전 제거
                    cursor = conn.execute(
                        "DELETE FROM packages WHERE name = ? AND version = ?",
                        (name, version)
                    )
                    affected = cursor.rowcount
                    
                    # 관련 의존성 및 엔트리 포인트 제거
                    conn.execute(
                        "DELETE FROM dependencies WHERE package_name = ? AND package_version = ?",
                        (name, version)
                    )
                    conn.execute(
                        "DELETE FROM entry_points WHERE package_name = ? AND package_version = ?",
                        (name, version)
                    )
                else:
                    # 모든 버전 제거
                    cursor = conn.execute("DELETE FROM packages WHERE name = ?", (name,))
                    affected = cursor.rowcount
                    
                    # 관련 의존성 및 엔트리 포인트 제거
                    conn.execute("DELETE FROM dependencies WHERE package_name = ?", (name,))
                    conn.execute("DELETE FROM entry_points WHERE package_name = ?", (name,))
                
                conn.commit()
                return affected > 0
    
    def get_package(self, name: str, version: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """패키지 정보 조회"""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                if version:
                    cursor = conn.execute(
                        "SELECT * FROM packages WHERE name = ? AND version = ?",
                        (name, version)
                    )
                else:
                    # 최신 버전 조회
                    cursor = conn.execute(
                        "SELECT * FROM packages WHERE name = ? ORDER BY version DESC LIMIT 1",
                        (name,)
                    )
                
                row = cursor.fetchone()
                if row:
                    return dict(row)
                return None
    
    def list_packages(self, name_pattern: Optional[str] = None) -> List[Dict[str, Any]]:
        """패키지 목록 조회"""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                if name_pattern:
                    # LIKE 패턴 사용
                    pattern = name_pattern.replace('*', '%').replace('?', '_')
                    cursor = conn.execute(
                        "SELECT * FROM packages WHERE name LIKE ? ORDER BY name, version DESC",
                        (pattern,)
                    )
                else:
                    cursor = conn.execute(
                        "SELECT * FROM packages ORDER BY name, version DESC"
                    )
                
                return [dict(row) for row in cursor.fetchall()]
    
    def get_package_versions(self, name: str) -> List[str]:
        """패키지 버전 목록 조회"""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT version FROM packages WHERE name = ? ORDER BY version DESC",
                    (name,)
                )
                return [row[0] for row in cursor.fetchall()]
    
    def package_exists(self, name: str, version: Optional[str] = None) -> bool:
        """패키지 존재 여부 확인"""
        return self.get_package(name, version) is not None
    
    def rebuild_index(self) -> None:
        """인덱스 재구축"""
        with self._lock:
            # 기존 데이터베이스 백업
            backup_path = self.db_path.with_suffix('.db.bak')
            if self.db_path.exists():
                shutil.copy2(self.db_path, backup_path)
            
            try:
                # 새 데이터베이스 생성
                if self.db_path.exists():
                    self.db_path.unlink()
                self._initialize_database()
                
            except Exception as e:
                # 복구
                if backup_path.exists():
                    shutil.copy2(backup_path, self.db_path)
                raise RepositoryCorruptedError(str(self.index_path), f"Index rebuild failed: {e}")
            finally:
                # 백업 파일 정리
                if backup_path.exists():
                    backup_path.unlink()


class LocalRepository(IPackageRepository):
    """로컬 패키지 저장소"""
    
    def __init__(self, repository_path: Path):
        """초기화"""
        self.repository_path = repository_path
        self.packages_path = repository_path / "packages"
        self.index = PackageIndex(repository_path / "index")
        self._lock = threading.RLock()
        self._initialize_repository()
    
    def _initialize_repository(self) -> None:
        """저장소 초기화"""
        try:
            self.repository_path.mkdir(parents=True, exist_ok=True)
            self.packages_path.mkdir(parents=True, exist_ok=True)
            
            # 저장소 메타데이터 파일 생성
            metadata_file = self.repository_path / "repository.json"
            if not metadata_file.exists():
                metadata = {
                    "repository_version": "1.0",
                    "created_at": datetime.datetime.now().isoformat(),
                    "type": "local",
                    "description": "Local package repository"
                }
                with open(metadata_file, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, indent=2, ensure_ascii=False)
                    
        except Exception as e:
            raise RepositoryError(f"Failed to initialize repository: {e}", str(self.repository_path))
    
    def store_package(self, package_path: Path, package_info: IPackageInfo) -> bool:
        """패키지 저장"""
        if not package_path.exists():
            raise PackageNotFoundError(package_info.name, str(package_info.version))
        
        with self._lock:
            try:
                # 저장 경로 결정
                package_name = package_info.name
                package_version = str(package_info.version)
                
                # 패키지 디렉토리 생성
                package_dir = self.packages_path / package_name
                package_dir.mkdir(parents=True, exist_ok=True)
                
                # 패키지 파일 복사
                target_filename = f"{package_name}-{package_version}.hqp"
                target_path = package_dir / target_filename
                
                if target_path.exists():
                    raise PackageAlreadyExistsError(package_name, package_version)
                
                shutil.copy2(package_path, target_path)
                
                # 인덱스에 추가
                relative_path = str(target_path.relative_to(self.repository_path))
                self.index.add_package(package_info, relative_path)
                
                return True
                
            except Exception as e:
                if isinstance(e, (PackageNotFoundError, PackageAlreadyExistsError)):
                    raise
                raise RepositoryError(f"Failed to store package: {e}", str(self.repository_path))
    
    def get_package(self, name: str, version: Optional[SemanticVersion] = None) -> Optional[Path]:
        """패키지 조회"""
        version_str = str(version) if version else None
        
        with self._lock:
            package_data = self.index.get_package(name, version_str)
            if not package_data:
                return None
            
            package_path = self.repository_path / package_data['file_path']
            if package_path.exists():
                return package_path
            
            # 파일이 없으면 인덱스에서 제거
            self.index.remove_package(name, version_str)
            return None
    
    def list_packages(self, name_pattern: Optional[str] = None) -> List[IPackageInfo]:
        """패키지 목록 조회"""
        with self._lock:
            packages_data = self.index.list_packages(name_pattern)
            packages = []
            
            for package_data in packages_data:
                try:
                    # 메타데이터에서 PackageInfo 복원
                    metadata = json.loads(package_data['metadata'])
                    package_info = PackageInfo.from_dict(metadata)
                    packages.append(package_info)
                except Exception:
                    # 손상된 메타데이터는 건너뛰기
                    continue
            
            return packages
    
    def get_package_versions(self, name: str) -> List[SemanticVersion]:
        """패키지 버전 목록 조회"""
        with self._lock:
            version_strings = self.index.get_package_versions(name)
            versions = []
            
            for version_str in version_strings:
                try:
                    # 버전 문자열 파싱
                    parts = version_str.split('.')
                    major = int(parts[0]) if len(parts) > 0 else 0
                    minor = int(parts[1]) if len(parts) > 1 else 0
                    patch = int(parts[2]) if len(parts) > 2 else 0
                    
                    # pre-release와 build 정보 처리 (간단한 구현)
                    pre_release = None
                    build = None
                    if '-' in version_str:
                        base_version, rest = version_str.split('-', 1)
                        if '+' in rest:
                            pre_release, build = rest.split('+', 1)
                        else:
                            pre_release = rest
                    elif '+' in version_str:
                        base_version, build = version_str.split('+', 1)
                    
                    versions.append(SemanticVersion(major, minor, patch, pre_release, build))
                except (ValueError, IndexError):
                    # 잘못된 버전 형식은 건너뛰기
                    continue
            
            return versions
    
    def remove_package(self, name: str, version: Optional[SemanticVersion] = None) -> bool:
        """패키지 제거"""
        version_str = str(version) if version else None
        
        with self._lock:
            try:
                # 패키지 파일 경로 조회
                if version_str:
                    package_data = self.index.get_package(name, version_str)
                    if package_data:
                        package_path = self.repository_path / package_data['file_path']
                        if package_path.exists():
                            package_path.unlink()
                else:
                    # 모든 버전 제거
                    versions = self.index.get_package_versions(name)
                    for ver in versions:
                        package_data = self.index.get_package(name, ver)
                        if package_data:
                            package_path = self.repository_path / package_data['file_path']
                            if package_path.exists():
                                package_path.unlink()
                
                # 인덱스에서 제거
                return self.index.remove_package(name, version_str)
                
            except Exception as e:
                raise RepositoryError(f"Failed to remove package: {e}", str(self.repository_path))
    
    def package_exists(self, name: str, version: Optional[SemanticVersion] = None) -> bool:
        """패키지 존재 여부 확인"""
        version_str = str(version) if version else None
        return self.index.package_exists(name, version_str)
    
    def get_package_info(self, name: str, version: Optional[SemanticVersion] = None) -> Optional[IPackageInfo]:
        """패키지 정보 조회"""
        version_str = str(version) if version else None
        
        with self._lock:
            package_data = self.index.get_package(name, version_str)
            if not package_data:
                return None
            
            try:
                # 메타데이터에서 PackageInfo 복원
                metadata = json.loads(package_data['metadata'])
                return PackageInfo.from_dict(metadata)
            except Exception:
                return None
    
    def rebuild_index(self) -> None:
        """인덱스 재구축"""
        with self._lock:
            try:
                # 인덱스 재구축
                self.index.rebuild_index()
                
                # 실제 파일들을 스캔하여 인덱스 재구성
                self._scan_and_rebuild_index()
                
            except Exception as e:
                raise RepositoryCorruptedError(
                    str(self.repository_path), 
                    f"Index rebuild failed: {e}"
                )
    
    def _scan_and_rebuild_index(self) -> None:
        """실제 파일을 스캔하여 인덱스 재구성"""
        for package_file in self.packages_path.rglob("*.hqp"):
            try:
                # 패키지 파일에서 매니페스트 읽기
                import zipfile
                with zipfile.ZipFile(package_file, 'r') as zf:
                    manifest_data = zf.read('manifest.json').decode('utf-8')
                    manifest_dict = json.loads(manifest_data)
                    
                    # PackageInfo 생성
                    package_data = manifest_dict.get('package', {})
                    package_info = PackageInfo.from_dict(package_data)
                    
                    # 인덱스에 추가
                    relative_path = str(package_file.relative_to(self.repository_path))
                    self.index.add_package(package_info, relative_path)
                    
            except Exception:
                # 손상된 패키지 파일은 건너뛰기
                continue
    
    def get_repository_statistics(self) -> Dict[str, Any]:
        """저장소 통계 정보"""
        with self._lock:
            packages = self.list_packages()
            total_size = 0
            package_types = {}
            
            for package in packages:
                if hasattr(package, 'size') and package.size:
                    total_size += package.size
                
                package_type = package.package_type.value
                package_types[package_type] = package_types.get(package_type, 0) + 1
            
            return {
                'total_packages': len(packages),
                'total_size': total_size,
                'package_types': package_types,
                'repository_path': str(self.repository_path),
                'last_updated': datetime.datetime.now().isoformat()
            }
    
    def cleanup_orphaned_files(self) -> int:
        """고아 파일 정리"""
        with self._lock:
            cleaned_count = 0
            
            # 인덱스에 있는 파일들 목록
            indexed_files = set()
            packages = self.index.list_packages()
            for package_data in packages:
                indexed_files.add(package_data['file_path'])
            
            # 실제 파일들 확인
            for package_file in self.packages_path.rglob("*.hqp"):
                relative_path = str(package_file.relative_to(self.repository_path))
                if relative_path not in indexed_files:
                    # 고아 파일 삭제
                    package_file.unlink()
                    cleaned_count += 1
            
            return cleaned_count 