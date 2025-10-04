"""
패키지 메타데이터 구현

이 모듈은 패키지 메타데이터와 매니페스트의 구현 클래스들을 포함합니다.
"""

import json
import datetime
import hashlib
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from pathlib import Path

from .interfaces import (
    IPackageInfo, IPackageManifest, PackageType, SemanticVersion,
    PackageDependency, PackageEntryPoint
)
from .exceptions import (
    InvalidPackageError, InvalidManifestError, ManifestNotFoundError
)


@dataclass
class PackageInfo(IPackageInfo):
    """패키지 정보 구현 클래스"""
    
    _name: str
    _version: SemanticVersion
    _package_type: PackageType
    _description: Optional[str] = None
    _author: Optional[str] = None
    _license: Optional[str] = None
    _homepage: Optional[str] = None
    _repository: Optional[str] = None
    _dependencies: List[PackageDependency] = field(default_factory=list)
    _entry_points: List[PackageEntryPoint] = field(default_factory=list)
    _files: List[str] = field(default_factory=list)
    _created_at: Optional[datetime.datetime] = None
    _keywords: List[str] = field(default_factory=list)
    _python_requires: Optional[str] = None
    _checksum: Optional[str] = None
    _size: Optional[int] = None
    
    def __post_init__(self):
        """초기화 후 처리"""
        if self._created_at is None:
            self._created_at = datetime.datetime.now()
        
        # 메타데이터 검증
        self._validate()
    
    def _validate(self) -> None:
        """메타데이터 검증"""
        errors = []
        
        # 필수 필드 검증
        if not self._name or not self._name.strip():
            errors.append("Package name is required")
        
        if not isinstance(self._version, SemanticVersion):
            errors.append("Package version must be a SemanticVersion instance")
        
        if not isinstance(self._package_type, PackageType):
            errors.append("Package type must be a PackageType instance")
        
        # 패키지명 형식 검증 (소문자, 하이픈, 언더스코어만 허용)
        if self._name and not self._name.replace('-', '').replace('_', '').isalnum():
            errors.append("Package name must contain only alphanumeric characters, hyphens, and underscores")
        
        # 의존성 검증
        for dep in self._dependencies:
            if not isinstance(dep, PackageDependency):
                errors.append(f"Invalid dependency: {dep}")
        
        # 엔트리 포인트 검증
        for entry_point in self._entry_points:
            if not isinstance(entry_point, PackageEntryPoint):
                errors.append(f"Invalid entry point: {entry_point}")
        
        if errors:
            raise InvalidPackageError(self._name, errors)
    
    @property
    def name(self) -> str:
        """패키지명"""
        return self._name
    
    @property
    def version(self) -> SemanticVersion:
        """패키지 버전"""
        return self._version
    
    @property
    def package_type(self) -> PackageType:
        """패키지 타입"""
        return self._package_type
    
    @property
    def description(self) -> Optional[str]:
        """패키지 설명"""
        return self._description
    
    @property
    def author(self) -> Optional[str]:
        """패키지 작성자"""
        return self._author
    
    @property
    def license(self) -> Optional[str]:
        """라이선스"""
        return self._license
    
    @property
    def homepage(self) -> Optional[str]:
        """홈페이지"""
        return self._homepage
    
    @property
    def repository(self) -> Optional[str]:
        """저장소 URL"""
        return self._repository
    
    @property
    def dependencies(self) -> List[PackageDependency]:
        """의존성 목록"""
        return self._dependencies.copy()
    
    @property
    def entry_points(self) -> List[PackageEntryPoint]:
        """엔트리 포인트 목록"""
        return self._entry_points.copy()
    
    @property
    def files(self) -> List[str]:
        """패키지에 포함된 파일 목록"""
        return self._files.copy()
    
    @property
    def created_at(self) -> datetime.datetime:
        """생성 시간"""
        return self._created_at
    
    @property
    def keywords(self) -> List[str]:
        """키워드 목록"""
        return self._keywords.copy()
    
    @property
    def python_requires(self) -> Optional[str]:
        """필요한 Python 버전"""
        return self._python_requires
    
    @property
    def checksum(self) -> Optional[str]:
        """패키지 체크섬"""
        return self._checksum
    
    @property
    def size(self) -> Optional[int]:
        """패키지 크기 (바이트)"""
        return self._size
    
    def add_dependency(self, dependency: PackageDependency) -> None:
        """의존성 추가"""
        if dependency not in self._dependencies:
            self._dependencies.append(dependency)
    
    def remove_dependency(self, name: str) -> bool:
        """의존성 제거"""
        for i, dep in enumerate(self._dependencies):
            if dep.name == name:
                self._dependencies.pop(i)
                return True
        return False
    
    def add_entry_point(self, entry_point: PackageEntryPoint) -> None:
        """엔트리 포인트 추가"""
        if entry_point not in self._entry_points:
            self._entry_points.append(entry_point)
    
    def remove_entry_point(self, name: str) -> bool:
        """엔트리 포인트 제거"""
        for i, ep in enumerate(self._entry_points):
            if ep.name == name:
                self._entry_points.pop(i)
                return True
        return False
    
    def add_file(self, file_path: str) -> None:
        """파일 추가"""
        if file_path not in self._files:
            self._files.append(file_path)
    
    def remove_file(self, file_path: str) -> bool:
        """파일 제거"""
        if file_path in self._files:
            self._files.remove(file_path)
            return True
        return False
    
    def add_keyword(self, keyword: str) -> None:
        """키워드 추가"""
        if keyword not in self._keywords:
            self._keywords.append(keyword)
    
    def remove_keyword(self, keyword: str) -> bool:
        """키워드 제거"""
        if keyword in self._keywords:
            self._keywords.remove(keyword)
            return True
        return False
    
    def set_checksum(self, checksum: str) -> None:
        """체크섬 설정"""
        self._checksum = checksum
    
    def set_size(self, size: int) -> None:
        """크기 설정"""
        self._size = size
    
    def has_dependency(self, name: str) -> bool:
        """의존성 존재 여부 확인"""
        return any(dep.name == name for dep in self._dependencies)
    
    def get_dependency(self, name: str) -> Optional[PackageDependency]:
        """의존성 조회"""
        for dep in self._dependencies:
            if dep.name == name:
                return dep
        return None
    
    def has_entry_point(self, name: str) -> bool:
        """엔트리 포인트 존재 여부 확인"""
        return any(ep.name == name for ep in self._entry_points)
    
    def get_entry_point(self, name: str) -> Optional[PackageEntryPoint]:
        """엔트리 포인트 조회"""
        for ep in self._entry_points:
            if ep.name == name:
                return ep
        return None
    
    def is_compatible_with_python(self, python_version: str) -> bool:
        """Python 버전 호환성 확인"""
        if not self._python_requires:
            return True
        
        # 간단한 호환성 확인 (실제로는 더 복잡한 파싱 필요)
        return True  # 임시 구현
    
    def calculate_checksum(self, data: bytes) -> str:
        """데이터의 체크섬 계산"""
        return hashlib.sha256(data).hexdigest()
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            'name': self._name,
            'version': {
                'major': self._version.major,
                'minor': self._version.minor,
                'patch': self._version.patch,
                'pre_release': self._version.pre_release,
                'build': self._version.build
            },
            'package_type': self._package_type.value,
            'description': self._description,
            'author': self._author,
            'license': self._license,
            'homepage': self._homepage,
            'repository': self._repository,
            'dependencies': [
                {
                    'name': dep.name,
                    'version_constraint': dep.version_constraint,
                    'constraint_type': dep.constraint_type.value,
                    'optional': dep.optional,
                    'description': dep.description
                }
                for dep in self._dependencies
            ],
            'entry_points': [
                {
                    'name': ep.name,
                    'module_path': ep.module_path,
                    'class_name': ep.class_name,
                    'function_name': ep.function_name,
                    'description': ep.description
                }
                for ep in self._entry_points
            ],
            'files': self._files,
            'created_at': self._created_at.isoformat() if self._created_at else None,
            'keywords': self._keywords,
            'python_requires': self._python_requires,
            'checksum': self._checksum,
            'size': self._size
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PackageInfo':
        """딕셔너리에서 생성"""
        # 버전 정보 파싱
        version_data = data.get('version', {})
        version = SemanticVersion(
            major=version_data.get('major', 0),
            minor=version_data.get('minor', 0),
            patch=version_data.get('patch', 0),
            pre_release=version_data.get('pre_release'),
            build=version_data.get('build')
        )
        
        # 패키지 타입 파싱
        package_type = PackageType(data.get('package_type', PackageType.MODULE.value))
        
        # 의존성 파싱
        dependencies = []
        for dep_data in data.get('dependencies', []):
            from .interfaces import VersionConstraint
            dependencies.append(PackageDependency(
                name=dep_data['name'],
                version_constraint=dep_data.get('version_constraint'),
                constraint_type=VersionConstraint(dep_data.get('constraint_type', 'greater_equal')),
                optional=dep_data.get('optional', False),
                description=dep_data.get('description')
            ))
        
        # 엔트리 포인트 파싱
        entry_points = []
        for ep_data in data.get('entry_points', []):
            entry_points.append(PackageEntryPoint(
                name=ep_data['name'],
                module_path=ep_data['module_path'],
                class_name=ep_data.get('class_name'),
                function_name=ep_data.get('function_name'),
                description=ep_data.get('description')
            ))
        
        # 생성 시간 파싱
        created_at = None
        if data.get('created_at'):
            created_at = datetime.datetime.fromisoformat(data['created_at'])
        
        # PackageInfo 객체 생성
        package_info = cls(
            _name=data['name'],
            _version=version,
            _package_type=package_type,
            _description=data.get('description'),
            _author=data.get('author'),
            _license=data.get('license'),
            _homepage=data.get('homepage'),
            _repository=data.get('repository'),
            _dependencies=dependencies,
            _entry_points=entry_points,
            _files=data.get('files', []),
            _created_at=created_at,
            _keywords=data.get('keywords', []),
            _python_requires=data.get('python_requires'),
            _checksum=data.get('checksum'),
            _size=data.get('size')
        )
        
        return package_info
    
    def to_json(self) -> str:
        """JSON 문자열로 변환"""
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'PackageInfo':
        """JSON 문자열에서 생성"""
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    def __str__(self) -> str:
        """문자열 표현"""
        return f"PackageInfo(name='{self._name}', version={self._version}, type={self._package_type.value})"
    
    def __repr__(self) -> str:
        """상세 문자열 표현"""
        return (
            f"PackageInfo(name='{self._name}', version={self._version}, "
            f"type={self._package_type.value}, dependencies={len(self._dependencies)})"
        )
    
    def __eq__(self, other) -> bool:
        """동등성 비교"""
        if not isinstance(other, PackageInfo):
            return False
        return (
            self._name == other._name and
            self._version == other._version and
            self._package_type == other._package_type
        )
    
    def __hash__(self) -> int:
        """해시 값 계산"""
        return hash((self._name, str(self._version), self._package_type.value))


class PackageManifest(IPackageManifest):
    """패키지 매니페스트 구현 클래스"""
    
    def __init__(self, package_info: Optional[PackageInfo] = None):
        """초기화"""
        self._package_info = package_info
        self._metadata: Dict[str, Any] = {}
        self._version = "1.0"  # 매니페스트 포맷 버전
    
    def get_package_info(self) -> IPackageInfo:
        """패키지 정보 조회"""
        if not self._package_info:
            raise InvalidManifestError("unknown", ["Package info not set"])
        return self._package_info
    
    def set_package_info(self, package_info: PackageInfo) -> None:
        """패키지 정보 설정"""
        self._package_info = package_info
    
    def add_metadata(self, key: str, value: Any) -> None:
        """메타데이터 추가"""
        self._metadata[key] = value
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """메타데이터 조회"""
        return self._metadata.get(key, default)
    
    def validate(self) -> Tuple[bool, List[str]]:
        """매니페스트 유효성 검증"""
        errors = []
        
        # 패키지 정보 존재 확인
        if not self._package_info:
            errors.append("Package info is required")
            return False, errors
        
        # 필수 필드 확인
        if not self._package_info.name:
            errors.append("Package name is required")
        
        if not self._package_info.version:
            errors.append("Package version is required")
        
        # 엔트리 포인트 유효성 확인
        for entry_point in self._package_info.entry_points:
            if not entry_point.module_path:
                errors.append(f"Entry point '{entry_point.name}' missing module path")
        
        # 의존성 유효성 확인
        for dependency in self._package_info.dependencies:
            if not dependency.name:
                errors.append("Dependency name is required")
        
        return len(errors) == 0, errors
    
    def save_to_file(self, file_path: Path) -> None:
        """파일에 저장"""
        if not self._package_info:
            raise InvalidManifestError("unknown", ["Package info not set"])
        
        # 매니페스트 데이터 생성
        manifest_data = {
            'manifest_version': self._version,
            'package': self._package_info.to_dict(),
            'metadata': self._metadata,
            'created_at': datetime.datetime.now().isoformat()
        }
        
        # 파일에 저장
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(manifest_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            raise InvalidManifestError(
                self._package_info.name if self._package_info else "unknown",
                [f"Failed to save manifest: {e}"],
                str(file_path)
            )
    
    def load_from_file(self, file_path: Path) -> None:
        """파일에서 로드"""
        if not file_path.exists():
            raise ManifestNotFoundError(str(file_path))
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                manifest_data = json.load(f)
            
            # 매니페스트 버전 확인
            self._version = manifest_data.get('manifest_version', '1.0')
            
            # 패키지 정보 로드
            package_data = manifest_data.get('package', {})
            self._package_info = PackageInfo.from_dict(package_data)
            
            # 메타데이터 로드
            self._metadata = manifest_data.get('metadata', {})
            
        except json.JSONDecodeError as e:
            raise InvalidManifestError(
                "unknown",
                [f"Invalid JSON format: {e}"],
                str(file_path)
            )
        except Exception as e:
            raise InvalidManifestError(
                "unknown",
                [f"Failed to load manifest: {e}"],
                str(file_path)
            )
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        if not self._package_info:
            raise InvalidManifestError("unknown", ["Package info not set"])
        
        return {
            'manifest_version': self._version,
            'package': self._package_info.to_dict(),
            'metadata': self._metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PackageManifest':
        """딕셔너리에서 생성"""
        manifest = cls()
        manifest._version = data.get('manifest_version', '1.0')
        
        # 패키지 정보 로드
        package_data = data.get('package', {})
        manifest._package_info = PackageInfo.from_dict(package_data)
        
        # 메타데이터 로드
        manifest._metadata = data.get('metadata', {})
        
        return manifest
    
    def __str__(self) -> str:
        """문자열 표현"""
        package_name = self._package_info.name if self._package_info else "unknown"
        return f"PackageManifest(package='{package_name}', version={self._version})"
    
    def __repr__(self) -> str:
        """상세 문자열 표현"""
        package_name = self._package_info.name if self._package_info else "unknown"
        return f"PackageManifest(package='{package_name}', manifest_version={self._version})" 