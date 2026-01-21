"""
플러그인 데코레이터 모듈

플러그인 등록 및 메타데이터 관리를 위한 데코레이터들을 제공합니다.
"""

import functools
from typing import Type, Dict, Any, Optional
from dataclasses import dataclass

from core.interfaces.plugins import PluginMetadata, IPlugin


@dataclass
class PluginConfig:
    """플러그인 설정"""
    name: Optional[str] = None
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    dependencies: Optional[list] = None
    auto_register: bool = True
    priority: int = 0
    category: str = "trading"


# 전역 플러그인 레지스트리
_plugin_registry: Dict[str, Type[IPlugin]] = {}


def plugin(name: Optional[str] = None,
           version: str = "1.0.0",
           description: str = "",
           author: str = "",
           dependencies: Optional[list] = None,
           auto_register: bool = True,
           priority: int = 0,
           category: str = "trading"):
    """
    클래스를 플러그인으로 등록하는 데코레이터

    Args:
        name: 플러그인 이름 (None이면 클래스명 사용)
        version: 플러그인 버전
        description: 플러그인 설명
        author: 플러그인 작성자
        dependencies: 의존성 목록
        auto_register: 자동 등록 여부
        priority: 우선순위 (낮을수록 먼저 로드)
        category: 플러그인 카테고리 (기본값: "trading")

    Returns:
        데코레이터 함수

    Example:
        @plugin(name="MyPlugin", version="1.0.0", category="analysis")
        class MyPlugin(BasePlugin):
            pass
    """
    def decorator(cls: Type[IPlugin]) -> Type[IPlugin]:
        # 플러그인 이름 결정
        plugin_name = name if name is not None else cls.__name__

        # 의존성 리스트 초기화
        if dependencies is None:
            deps = []
        else:
            deps = dependencies.copy()

        # 메타데이터 생성
        metadata = PluginMetadata(
            name=plugin_name,
            version=version,
            description=description,
            author=author,
            category=category,
            interfaces=[cls.__name__],  # 클래스 이름을 인터페이스로 사용
            dependencies=deps,
            entry_point=f"{cls.__module__}:{cls.__name__}"  # 모듈:클래스 형식
        )

        # 클래스에 메타데이터 추가
        setattr(cls, '_plugin_metadata', metadata)
        setattr(cls, '_plugin_config', PluginConfig(
            name=plugin_name,
            version=version,
            description=description,
            author=author,
            dependencies=deps,
            auto_register=auto_register,
            priority=priority,
            category=category
        ))

        # 플러그인 인터페이스 체크
        if not hasattr(cls, 'initialize'):
            raise TypeError(f"Plugin {plugin_name} must implement initialize() method")

        # 자동 등록
        if auto_register:
            _plugin_registry[plugin_name] = cls

        # 클래스에 플러그인 메서드 추가
        original_init = cls.__init__

        @functools.wraps(original_init)
        def new_init(self, *args, **kwargs):
            # 원본 __init__ 호출
            original_init(self, *args, **kwargs)

            # 플러그인 속성 설정
            if not hasattr(self, '_metadata'):
                self._metadata = metadata
            if not hasattr(self, '_config'):
                self._config = PluginConfig(
                    name=plugin_name,
                    version=version,
                    description=description,
                    author=author,
                    dependencies=deps,
                    auto_register=auto_register,
                    priority=priority,
                    category=category
                )

        cls.__init__ = new_init

        # get_metadata 메서드 추가 (없는 경우)
        if not hasattr(cls, 'get_metadata'):
            def get_metadata(self) -> PluginMetadata:
                return self._metadata
            cls.get_metadata = get_metadata

        return cls

    return decorator


def get_registered_plugins() -> Dict[str, Type[IPlugin]]:
    """등록된 모든 플러그인 반환"""
    return _plugin_registry.copy()


def get_plugin_by_name(name: str) -> Optional[Type[IPlugin]]:
    """이름으로 플러그인 조회"""
    return _plugin_registry.get(name)


def register_plugin(name: str, plugin_class: Type[IPlugin]) -> None:
    """플러그인 수동 등록"""
    _plugin_registry[name] = plugin_class


def unregister_plugin(name: str) -> bool:
    """플러그인 등록 해제"""
    if name in _plugin_registry:
        del _plugin_registry[name]
        return True
    return False


def clear_registry() -> None:
    """플러그인 레지스트리 초기화"""
    _plugin_registry.clear()


def is_plugin_registered(name: str) -> bool:
    """플러그인 등록 여부 확인"""
    return name in _plugin_registry


def get_plugin_count() -> int:
    """등록된 플러그인 수 반환"""
    return len(_plugin_registry)


def list_plugin_names() -> list:
    """등록된 플러그인 이름 목록 반환"""
    return list(_plugin_registry.keys())


def validate_plugin(plugin_class: Type[IPlugin]) -> bool:
    """플러그인 클래스 유효성 검증"""
    try:
        # 필수 메서드 확인
        required_methods = ['initialize', 'get_metadata']
        for method in required_methods:
            if not hasattr(plugin_class, method):
                return False

        # 메타데이터 확인
        if hasattr(plugin_class, '_plugin_metadata'):
            metadata = getattr(plugin_class, '_plugin_metadata')
            if not isinstance(metadata, PluginMetadata):
                return False

        return True
    except Exception:
        return False


def get_plugin_info(name: str) -> Optional[Dict[str, Any]]:
    """플러그인 정보 조회"""
    plugin_class = get_plugin_by_name(name)
    if not plugin_class:
        return None

    info = {
        'name': name,
        'class': plugin_class.__name__,
        'module': plugin_class.__module__,
    }

    if hasattr(plugin_class, '_plugin_metadata'):
        metadata = getattr(plugin_class, '_plugin_metadata')
        info.update({
            'version': metadata.version,
            'description': metadata.description,
            'author': metadata.author,
            'category': metadata.category,
            'dependencies': metadata.dependencies
        })

    if hasattr(plugin_class, '_plugin_config'):
        config = getattr(plugin_class, '_plugin_config')
        info.update({
            'auto_register': config.auto_register,
            'priority': config.priority
        })

    return info


# 별칭
register = plugin  # plugin 데코레이터의 별칭
