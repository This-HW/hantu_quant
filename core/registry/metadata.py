"""
모듈 메타데이터 구현

이 모듈은 모듈 레지스트리 시스템의 메타데이터 구현 클래스들을 포함합니다.
"""

import json
import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from .interfaces import (
    IModuleMetadata, ModuleType, ModuleStatus, ModuleVersion,
    ModuleDependency, ModuleInterface, ModuleUsage
)
from .exceptions import InvalidModuleMetadataError


@dataclass
class ModuleMetadata(IModuleMetadata):
    """모듈 메타데이터 구현 클래스"""
    
    _name: str
    _version: ModuleVersion
    _module_type: ModuleType
    _status: ModuleStatus = ModuleStatus.UNREGISTERED
    _dependencies: List[ModuleDependency] = field(default_factory=list)
    _provided_interfaces: List[ModuleInterface] = field(default_factory=list)
    _used_interfaces: List[ModuleUsage] = field(default_factory=list)
    _description: Optional[str] = None
    _author: Optional[str] = None
    _created_at: Optional[datetime.datetime] = None
    _updated_at: Optional[datetime.datetime] = None
    _tags: List[str] = field(default_factory=list)
    _config: Dict[str, Any] = field(default_factory=dict)
    _file_path: Optional[str] = None
    _package_path: Optional[str] = None
    
    def __post_init__(self):
        """초기화 후 처리"""
        if self._created_at is None:
            self._created_at = datetime.datetime.now()
        if self._updated_at is None:
            self._updated_at = datetime.datetime.now()
        
        # 메타데이터 검증
        self._validate()
    
    def _validate(self) -> None:
        """메타데이터 검증"""
        errors = []
        
        # 필수 필드 검증
        if not self._name or not self._name.strip():
            errors.append("Module name is required")
        
        if not isinstance(self._version, ModuleVersion):
            errors.append("Module version must be a ModuleVersion instance")
        
        if not isinstance(self._module_type, ModuleType):
            errors.append("Module type must be a ModuleType instance")
        
        if not isinstance(self._status, ModuleStatus):
            errors.append("Module status must be a ModuleStatus instance")
        
        # 의존성 검증
        for dep in self._dependencies:
            if not isinstance(dep, ModuleDependency):
                errors.append(f"Invalid dependency: {dep}")
            elif not dep.module_name or not dep.module_name.strip():
                errors.append("Dependency module name is required")
        
        # 인터페이스 검증
        for interface in self._provided_interfaces:
            if not isinstance(interface, ModuleInterface):
                errors.append(f"Invalid interface: {interface}")
            elif not interface.name or not interface.name.strip():
                errors.append("Interface name is required")
        
        # 사용 인터페이스 검증
        for usage in self._used_interfaces:
            if not isinstance(usage, ModuleUsage):
                errors.append(f"Invalid interface usage: {usage}")
            elif not usage.interface_name or not usage.interface_name.strip():
                errors.append("Interface name is required for usage")
        
        if errors:
            raise InvalidModuleMetadataError(self._name, errors)
    
    @property
    def name(self) -> str:
        """모듈명"""
        return self._name
    
    @property
    def version(self) -> ModuleVersion:
        """모듈 버전"""
        return self._version
    
    @property
    def module_type(self) -> ModuleType:
        """모듈 타입"""
        return self._module_type
    
    @property
    def status(self) -> ModuleStatus:
        """모듈 상태"""
        return self._status
    
    @property
    def dependencies(self) -> List[ModuleDependency]:
        """의존성 목록"""
        return self._dependencies.copy()
    
    @property
    def provided_interfaces(self) -> List[ModuleInterface]:
        """제공하는 인터페이스 목록"""
        return self._provided_interfaces.copy()
    
    @property
    def used_interfaces(self) -> List[ModuleUsage]:
        """사용하는 인터페이스 목록"""
        return self._used_interfaces.copy()
    
    @property
    def description(self) -> Optional[str]:
        """모듈 설명"""
        return self._description
    
    @property
    def author(self) -> Optional[str]:
        """모듈 작성자"""
        return self._author
    
    @property
    def created_at(self) -> datetime.datetime:
        """생성 시간"""
        return self._created_at
    
    @property
    def updated_at(self) -> datetime.datetime:
        """수정 시간"""
        return self._updated_at
    
    @property
    def tags(self) -> List[str]:
        """태그 목록"""
        return self._tags.copy()
    
    @property
    def config(self) -> Dict[str, Any]:
        """설정 정보"""
        return self._config.copy()
    
    @property
    def file_path(self) -> Optional[str]:
        """파일 경로"""
        return self._file_path
    
    @property
    def package_path(self) -> Optional[str]:
        """패키지 경로"""
        return self._package_path
    
    def update_status(self, status: ModuleStatus) -> None:
        """모듈 상태 업데이트"""
        self._status = status
        self._updated_at = datetime.datetime.now()
    
    def add_dependency(self, dependency: ModuleDependency) -> None:
        """의존성 추가"""
        if dependency not in self._dependencies:
            self._dependencies.append(dependency)
            self._updated_at = datetime.datetime.now()
    
    def remove_dependency(self, module_name: str) -> bool:
        """의존성 제거"""
        for i, dep in enumerate(self._dependencies):
            if dep.module_name == module_name:
                self._dependencies.pop(i)
                self._updated_at = datetime.datetime.now()
                return True
        return False
    
    def add_interface(self, interface: ModuleInterface) -> None:
        """인터페이스 추가"""
        if interface not in self._provided_interfaces:
            self._provided_interfaces.append(interface)
            self._updated_at = datetime.datetime.now()
    
    def remove_interface(self, interface_name: str) -> bool:
        """인터페이스 제거"""
        for i, interface in enumerate(self._provided_interfaces):
            if interface.name == interface_name:
                self._provided_interfaces.pop(i)
                self._updated_at = datetime.datetime.now()
                return True
        return False
    
    def add_interface_usage(self, usage: ModuleUsage) -> None:
        """인터페이스 사용 추가"""
        if usage not in self._used_interfaces:
            self._used_interfaces.append(usage)
            self._updated_at = datetime.datetime.now()
    
    def remove_interface_usage(self, interface_name: str) -> bool:
        """인터페이스 사용 제거"""
        for i, usage in enumerate(self._used_interfaces):
            if usage.interface_name == interface_name:
                self._used_interfaces.pop(i)
                self._updated_at = datetime.datetime.now()
                return True
        return False
    
    def add_tag(self, tag: str) -> None:
        """태그 추가"""
        if tag not in self._tags:
            self._tags.append(tag)
            self._updated_at = datetime.datetime.now()
    
    def remove_tag(self, tag: str) -> bool:
        """태그 제거"""
        if tag in self._tags:
            self._tags.remove(tag)
            self._updated_at = datetime.datetime.now()
            return True
        return False
    
    def update_config(self, config: Dict[str, Any]) -> None:
        """설정 정보 업데이트"""
        self._config.update(config)
        self._updated_at = datetime.datetime.now()
    
    def set_file_path(self, file_path: str) -> None:
        """파일 경로 설정"""
        self._file_path = file_path
        self._updated_at = datetime.datetime.now()
    
    def set_package_path(self, package_path: str) -> None:
        """패키지 경로 설정"""
        self._package_path = package_path
        self._updated_at = datetime.datetime.now()
    
    def has_dependency(self, module_name: str) -> bool:
        """의존성 존재 여부 확인"""
        return any(dep.module_name == module_name for dep in self._dependencies)
    
    def has_interface(self, interface_name: str) -> bool:
        """인터페이스 제공 여부 확인"""
        return any(interface.name == interface_name for interface in self._provided_interfaces)
    
    def uses_interface(self, interface_name: str) -> bool:
        """인터페이스 사용 여부 확인"""
        return any(usage.interface_name == interface_name for usage in self._used_interfaces)
    
    def has_tag(self, tag: str) -> bool:
        """태그 존재 여부 확인"""
        return tag in self._tags
    
    def is_compatible_with(self, other: 'ModuleMetadata') -> bool:
        """다른 모듈과의 호환성 확인"""
        # 버전 호환성 확인
        if self._version.major != other._version.major:
            return False
        
        # 타입 호환성 확인
        if self._module_type != other._module_type:
            return False
        
        return True
    
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
            'module_type': self._module_type.value,
            'status': self._status.value,
            'dependencies': [
                {
                    'module_name': dep.module_name,
                    'version_constraint': dep.version_constraint,
                    'optional': dep.optional,
                    'description': dep.description
                }
                for dep in self._dependencies
            ],
            'provided_interfaces': [
                {
                    'name': interface.name,
                    'version': {
                        'major': interface.version.major,
                        'minor': interface.version.minor,
                        'patch': interface.version.patch,
                        'pre_release': interface.version.pre_release,
                        'build': interface.version.build
                    },
                    'description': interface.description,
                    'methods': interface.methods
                }
                for interface in self._provided_interfaces
            ],
            'used_interfaces': [
                {
                    'interface_name': usage.interface_name,
                    'required': usage.required,
                    'description': usage.description
                }
                for usage in self._used_interfaces
            ],
            'description': self._description,
            'author': self._author,
            'created_at': self._created_at.isoformat() if self._created_at else None,
            'updated_at': self._updated_at.isoformat() if self._updated_at else None,
            'tags': self._tags,
            'config': self._config,
            'file_path': self._file_path,
            'package_path': self._package_path
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ModuleMetadata':
        """딕셔너리에서 생성"""
        # 버전 정보 파싱
        version_data = data.get('version', {})
        version = ModuleVersion(
            major=version_data.get('major', 0),
            minor=version_data.get('minor', 0),
            patch=version_data.get('patch', 0),
            pre_release=version_data.get('pre_release'),
            build=version_data.get('build')
        )
        
        # 모듈 타입 파싱
        module_type = ModuleType(data.get('module_type', ModuleType.CORE.value))
        
        # 모듈 상태 파싱
        status = ModuleStatus(data.get('status', ModuleStatus.UNREGISTERED.value))
        
        # 의존성 파싱
        dependencies = []
        for dep_data in data.get('dependencies', []):
            dependencies.append(ModuleDependency(
                module_name=dep_data['module_name'],
                version_constraint=dep_data.get('version_constraint'),
                optional=dep_data.get('optional', False),
                description=dep_data.get('description')
            ))
        
        # 제공 인터페이스 파싱
        provided_interfaces = []
        for interface_data in data.get('provided_interfaces', []):
            interface_version_data = interface_data.get('version', {})
            interface_version = ModuleVersion(
                major=interface_version_data.get('major', 0),
                minor=interface_version_data.get('minor', 0),
                patch=interface_version_data.get('patch', 0),
                pre_release=interface_version_data.get('pre_release'),
                build=interface_version_data.get('build')
            )
            provided_interfaces.append(ModuleInterface(
                name=interface_data['name'],
                version=interface_version,
                description=interface_data.get('description'),
                methods=interface_data.get('methods', [])
            ))
        
        # 사용 인터페이스 파싱
        used_interfaces = []
        for usage_data in data.get('used_interfaces', []):
            used_interfaces.append(ModuleUsage(
                interface_name=usage_data['interface_name'],
                required=usage_data.get('required', True),
                description=usage_data.get('description')
            ))
        
        # 시간 정보 파싱
        created_at = None
        if data.get('created_at'):
            created_at = datetime.datetime.fromisoformat(data['created_at'])
        
        updated_at = None
        if data.get('updated_at'):
            updated_at = datetime.datetime.fromisoformat(data['updated_at'])
        
        # 메타데이터 객체 생성
        metadata = cls(
            _name=data['name'],
            _version=version,
            _module_type=module_type,
            _status=status,
            _dependencies=dependencies,
            _provided_interfaces=provided_interfaces,
            _used_interfaces=used_interfaces,
            _description=data.get('description'),
            _author=data.get('author'),
            _created_at=created_at,
            _updated_at=updated_at,
            _tags=data.get('tags', []),
            _config=data.get('config', {}),
            _file_path=data.get('file_path'),
            _package_path=data.get('package_path')
        )
        
        return metadata
    
    def to_json(self) -> str:
        """JSON 문자열로 변환"""
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'ModuleMetadata':
        """JSON 문자열에서 생성"""
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    def __str__(self) -> str:
        """문자열 표현"""
        return f"ModuleMetadata(name='{self._name}', version={self._version}, type={self._module_type.value})"
    
    def __repr__(self) -> str:
        """상세 문자열 표현"""
        return (
            f"ModuleMetadata(name='{self._name}', version={self._version}, "
            f"type={self._module_type.value}, status={self._status.value})"
        )
    
    def __eq__(self, other) -> bool:
        """동등성 비교"""
        if not isinstance(other, ModuleMetadata):
            return False
        return (
            self._name == other._name and
            self._version == other._version and
            self._module_type == other._module_type
        )
    
    def __hash__(self) -> int:
        """해시 값 계산"""
        return hash((self._name, str(self._version), self._module_type.value)) 