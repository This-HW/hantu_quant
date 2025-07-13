# 한투 퀀트 모듈 아키텍처 설계 문서

## 📋 개요

**작성일**: 2025-01-13  
**버전**: 1.0.0  
**목적**: 확장 가능하고 유지보수가 용이한 모듈 아키텍처 설계

## 🎯 설계 목표

### 핵심 요구사항
1. **모듈 단위 교체 가능**: 시스템 영향 없이 모듈 교체
2. **독립적 모듈 개발**: 모듈 내부 수정 시 다른 모듈 영향 없음
3. **모듈 간 관계 관리**: 체계적인 의존성 및 관계 관리
4. **모듈 재사용성**: 다른 프로젝트에서 모듈 재사용 가능

### 해결 방안
- **플러그인 아키텍처**: 동적 모듈 로딩/언로딩
- **모듈 레지스트리**: 의존성 관리 및 영향 분석
- **패키지 관리 시스템**: 모듈 재사용성 및 배포 자동화
- **인터페이스 기반 설계**: 느슨한 결합 구조

## 🏗️ 아키텍처 구조

### 전체 시스템 구조
```
hantu_quant/
├── core/
│   ├── interfaces/          # 모듈 인터페이스 정의
│   │   ├── __init__.py
│   │   ├── i_module.py      # 기본 모듈 인터페이스
│   │   ├── i_screening.py   # 스크리닝 모듈 인터페이스
│   │   ├── i_analysis.py    # 분석 모듈 인터페이스
│   │   ├── i_learning.py    # 학습 모듈 인터페이스
│   │   └── i_trading.py     # 트레이딩 모듈 인터페이스
│   ├── framework/           # 프레임워크 핵심 구조
│   │   ├── __init__.py
│   │   ├── plugin_loader.py # 플러그인 로더
│   │   ├── module_registry.py # 모듈 레지스트리
│   │   ├── package_manager.py # 패키지 관리자
│   │   ├── event_bus.py     # 이벤트 버스
│   │   └── system_manager.py # 시스템 관리자
│   └── modules/             # 기본 모듈들
│       ├── __init__.py
│       ├── screening/       # 스크리닝 모듈
│       ├── analysis/        # 분석 모듈
│       ├── learning/        # 학습 모듈
│       └── trading/         # 트레이딩 모듈
├── plugins/                 # 플러그인 모듈들
│   ├── __init__.py
│   ├── fundamental_screener.py
│   ├── technical_screener.py
│   ├── price_analyzer.py
│   ├── momentum_analyzer.py
│   └── ai_learning_engine.py
├── packages/                # 패키지 저장소
│   ├── screening-1.0.0/
│   ├── analysis-1.0.0/
│   └── learning-1.0.0/
└── configs/                 # 모듈별 설정
    ├── module_configs.json
    ├── plugin_configs.json
    └── system_config.json
```

## 🔧 핵심 컴포넌트 설계

### 1. 기본 모듈 인터페이스 (IModule)

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, List

class IModule(ABC):
    """모든 모듈이 구현해야 하는 기본 인터페이스"""
    
    @abstractmethod
    def get_module_info(self) -> Dict[str, Any]:
        """모듈 정보 반환"""
        pass
    
    @abstractmethod
    def initialize(self, config: Dict[str, Any]) -> bool:
        """모듈 초기화"""
        pass
    
    @abstractmethod
    def shutdown(self) -> bool:
        """모듈 종료"""
        pass
    
    @abstractmethod
    def get_dependencies(self) -> List[str]:
        """의존성 모듈 목록 반환"""
        pass
    
    @abstractmethod
    def get_api_endpoints(self) -> Dict[str, callable]:
        """모듈 API 엔드포인트 반환"""
        pass
```

### 2. 플러그인 로더 (PluginLoader)

```python
import importlib
import pkgutil
from typing import List, Dict, Any, Optional

class PluginLoader:
    """플러그인 동적 로딩 시스템"""
    
    def __init__(self):
        self._plugins = {}
        self._plugin_instances = {}
    
    def discover_plugins(self, plugin_dir: str = "plugins") -> List[Dict]:
        """플러그인 자동 발견"""
        plugins = []
        for importer, modname, ispkg in pkgutil.iter_modules([plugin_dir]):
            try:
                module = importlib.import_module(f"{plugin_dir}.{modname}")
                if hasattr(module, 'get_plugin_class'):
                    plugin_class = module.get_plugin_class()
                    plugins.append({
                        'name': modname,
                        'class': plugin_class,
                        'module': module
                    })
            except Exception as e:
                print(f"플러그인 로드 실패: {modname} - {e}")
        return plugins
    
    def load_plugin(self, plugin_name: str, config: Dict[str, Any] = None) -> Optional[IModule]:
        """플러그인 로드"""
        if plugin_name in self._plugins:
            plugin_class = self._plugins[plugin_name]['class']
            instance = plugin_class()
            if instance.initialize(config or {}):
                self._plugin_instances[plugin_name] = instance
                return instance
        return None
    
    def unload_plugin(self, plugin_name: str) -> bool:
        """플러그인 언로드"""
        if plugin_name in self._plugin_instances:
            instance = self._plugin_instances[plugin_name]
            instance.shutdown()
            del self._plugin_instances[plugin_name]
            return True
        return False
    
    def get_plugin(self, plugin_name: str) -> Optional[IModule]:
        """플러그인 인스턴스 반환"""
        return self._plugin_instances.get(plugin_name)
```

### 3. 모듈 레지스트리 (ModuleRegistry)

```python
class ModuleRegistry:
    """모듈 등록 및 관계 관리"""
    
    def __init__(self):
        self._modules = {}
        self._dependencies = {}
        self._relationships = {}
    
    def register_module(self, module: IModule):
        """모듈 등록"""
        info = module.get_module_info()
        module_name = info['name']
        
        self._modules[module_name] = {
            'instance': module,
            'info': info,
            'status': 'registered'
        }
        
        # 의존성 정보 저장
        dependencies = module.get_dependencies()
        self._dependencies[module_name] = dependencies
        
        # 관계 매트릭스 업데이트
        self._update_relationships(module_name, dependencies)
    
    def get_startup_order(self) -> List[str]:
        """모듈 시작 순서 계산 (위상 정렬)"""
        order = []
        visited = set()
        temp_visited = set()
        
        def dfs(module_name):
            if module_name in temp_visited:
                raise ValueError(f"순환 의존성 발견: {module_name}")
            if module_name in visited:
                return
            
            temp_visited.add(module_name)
            
            # 의존성 모듈들을 먼저 방문
            for dep in self._dependencies.get(module_name, []):
                dfs(dep)
            
            temp_visited.remove(module_name)
            visited.add(module_name)
            order.append(module_name)
        
        for module_name in self._modules:
            if module_name not in visited:
                dfs(module_name)
        
        return order
    
    def get_impact_analysis(self, module_name: str) -> Dict:
        """모듈 변경 시 영향 분석"""
        if module_name not in self._relationships:
            return {'direct_impact': [], 'indirect_impact': []}
        
        direct_impact = list(self._relationships[module_name]['depended_by'])
        indirect_impact = set()
        
        # 간접 영향 계산
        def collect_indirect(current_module):
            for dependent in self._relationships.get(current_module, {}).get('depended_by', []):
                if dependent not in direct_impact:
                    indirect_impact.add(dependent)
                    collect_indirect(dependent)
        
        for dep in direct_impact:
            collect_indirect(dep)
        
        return {
            'direct_impact': direct_impact,
            'indirect_impact': list(indirect_impact)
        }
```

### 4. 패키지 관리자 (PackageManager)

```python
class PackageManager:
    """모듈 패키지 관리 시스템"""
    
    def __init__(self):
        self._packages = {}
        self._package_registry = {}
    
    def create_package(self, module_name: str, version: str, dependencies: List[str] = None) -> str:
        """모듈을 패키지로 생성"""
        package_info = {
            'name': module_name,
            'version': version,
            'dependencies': dependencies or [],
            'config_schema': self._extract_config_schema(module_name),
            'api_docs': self._generate_api_docs(module_name),
            'examples': self._generate_examples(module_name)
        }
        
        package_key = f"{module_name}:{version}"
        self._packages[package_key] = package_info
        
        # 패키지 파일 생성
        self._create_package_files(module_name, version, package_info)
        
        return package_key
    
    def install_package(self, package_name: str, version: str = "latest") -> bool:
        """패키지 설치"""
        # 실제 구현에서는 pip install 실행
        print(f"패키지 설치: {package_name}:{version}")
        return True
    
    def list_packages(self) -> List[Dict]:
        """사용 가능한 패키지 목록"""
        return [
            {
                'name': info['name'],
                'version': info['version'],
                'description': f"Hantu Quant {info['name']} module"
            }
            for info in self._packages.values()
        ]
```

### 5. 이벤트 버스 (EventBus)

```python
class EventBus:
    """이벤트 발행/구독 시스템"""
    
    def __init__(self):
        self._subscribers = {}
    
    def subscribe(self, event_type: str, callback):
        """이벤트 구독"""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)
    
    def publish(self, event_type: str, data):
        """이벤트 발행"""
        if event_type in self._subscribers:
            for callback in self._subscribers[event_type]:
                callback(data)
    
    def unsubscribe(self, event_type: str, callback):
        """이벤트 구독 해제"""
        if event_type in self._subscribers:
            self._subscribers[event_type].remove(callback)
```

## 📊 모듈 분류 및 인터페이스

### 스크리닝 모듈 (IScreeningModule)
```python
class IScreeningModule(IModule):
    @abstractmethod
    def screen_stocks(self, stock_list: List[str]) -> List[Dict]:
        """종목 스크리닝 실행"""
        pass
    
    @abstractmethod
    def get_screening_criteria(self) -> Dict:
        """스크리닝 기준 반환"""
        pass
    
    @abstractmethod
    def update_screening_criteria(self, criteria: Dict) -> bool:
        """스크리닝 기준 업데이트"""
        pass
```

### 분석 모듈 (IAnalysisModule)
```python
class IAnalysisModule(IModule):
    @abstractmethod
    def analyze_stock(self, stock_data: Dict) -> Dict:
        """종목 분석 실행"""
        pass
    
    @abstractmethod
    def analyze_multiple_stocks(self, stock_list: List[Dict]) -> List[Dict]:
        """복수 종목 분석"""
        pass
    
    @abstractmethod
    def get_analysis_indicators(self) -> List[str]:
        """분석 지표 목록 반환"""
        pass
```

### 학습 모듈 (ILearningModule)
```python
class ILearningModule(IModule):
    @abstractmethod
    def train_model(self, training_data: List[Dict]) -> bool:
        """모델 훈련"""
        pass
    
    @abstractmethod
    def predict(self, input_data: Dict) -> Dict:
        """예측 실행"""
        pass
    
    @abstractmethod
    def evaluate_model(self, test_data: List[Dict]) -> Dict:
        """모델 성능 평가"""
        pass
```

## 🔄 모듈 생명주기 관리

### 모듈 상태
- **registered**: 등록됨
- **initializing**: 초기화 중
- **active**: 활성화됨
- **error**: 오류 발생
- **shutting_down**: 종료 중
- **shutdown**: 종료됨

### 생명주기 이벤트
- **module_registered**: 모듈 등록
- **module_initialized**: 모듈 초기화 완료
- **module_activated**: 모듈 활성화
- **module_error**: 모듈 오류
- **module_shutdown**: 모듈 종료

## 📈 성능 및 확장성 고려사항

### 성능 최적화
1. **지연 로딩**: 필요할 때만 모듈 로드
2. **모듈 캐싱**: 인스턴스 재사용
3. **비동기 처리**: 병렬 모듈 초기화
4. **메모리 관리**: 사용하지 않는 모듈 언로드

### 확장성 설계
1. **수평적 확장**: 새로운 모듈 타입 추가
2. **수직적 확장**: 기존 모듈 기능 확장
3. **마이크로서비스**: 모듈별 독립적 배포
4. **클라우드 네이티브**: 컨테이너 기반 배포

## 🛡️ 보안 및 안정성

### 보안 고려사항
1. **모듈 검증**: 디지털 서명 확인
2. **권한 관리**: 모듈별 접근 권한 제어
3. **샌드박스**: 격리된 실행 환경
4. **감사 로그**: 모듈 활동 추적

### 안정성 보장
1. **오류 격리**: 모듈 오류가 시스템에 영향 없음
2. **복구 메커니즘**: 자동 재시작 및 복구
3. **백업 시스템**: 모듈 설정 및 데이터 백업
4. **모니터링**: 실시간 모듈 상태 추적

## 📝 개발 가이드라인

### 새로운 모듈 개발 시 준수사항
1. **인터페이스 구현**: 해당 모듈 타입 인터페이스 필수 구현
2. **설정 외부화**: 하드코딩 금지, 설정 파일 사용
3. **로깅 표준**: 통합 로깅 시스템 사용
4. **테스트 코드**: 단위 테스트 필수 작성
5. **문서화**: API 문서 및 사용 예시 제공

### 모듈 배포 프로세스
1. **개발 완료**: 기능 구현 및 테스트
2. **패키지 생성**: PackageManager로 패키지 생성
3. **품질 검증**: 자동화된 테스트 실행
4. **배포**: 패키지 저장소에 업로드
5. **배포 확인**: 실제 환경에서 동작 확인

## 🎯 마이그레이션 계획

### 기존 모듈 리팩토링 순서
1. **TODO 1.9**: 인터페이스 정의 및 프레임워크 구축
2. **TODO 1.10**: 플러그인 시스템 구현
3. **TODO 1.11**: 모듈 레지스트리 구현
4. **TODO 1.12**: 패키지 관리 시스템 구현
5. **TODO 1.13**: 기존 Phase 1,2 모듈 리팩토링

### 리팩토링 전략
- **점진적 마이그레이션**: 모듈별 단계적 변경
- **하위 호환성 보장**: 기존 API 유지
- **테스트 우선**: 리팩토링 전 테스트 코드 작성
- **문서 업데이트**: 변경 사항 문서화

---

이 설계를 통해 **완전한 모듈 단위 교체**, **독립적 개발**, **체계적 관계 관리**, **완전한 재사용성**을 달성할 수 있습니다. 