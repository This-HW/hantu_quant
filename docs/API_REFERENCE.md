# 한투 퀀트 시스템 API 레퍼런스

## 📚 개요

한투 퀀트 시스템의 주요 API들에 대한 상세 레퍼런스입니다. 각 모듈별로 클래스와 메서드를 정리하고 사용 예제를 제공합니다.

## 🏗️ 모듈 구조

```
core/
├── watchlist/          # Phase 1: 감시 리스트
├── daily_selection/    # Phase 2: 일일 선정
├── learning/           # Phase 4: AI 학습
├── market_monitor/     # Phase 5: 시장 모니터링
├── performance/        # 성능 최적화
├── resilience/         # 안정성 관리
├── di/                 # 의존성 주입
├── plugins/            # 플러그인 시스템
└── packages/           # 패키지 관리
```

---

## 📊 Phase 1: 감시 리스트 (Watchlist)

### StockScreener

종목 스크리닝을 담당하는 클래스입니다.

#### 클래스 정의
```python
class StockScreener:
    def __init__(self, data_source=None):
        """
        종목 스크리너 초기화
        
        Args:
            data_source: 데이터 소스 (선택적)
        """
```

#### 주요 메서드

##### `screen_stocks(criteria: Dict) -> List[Dict]`
지정된 기준에 따라 종목을 스크리닝합니다.

**매개변수:**
- `criteria`: 스크리닝 기준 딕셔너리
  - `min_market_cap`: 최소 시가총액
  - `max_market_cap`: 최대 시가총액
  - `min_per`: 최소 PER
  - `max_per`: 최대 PER
  - `min_volume`: 최소 거래량
  - `sector`: 업종 필터

**반환값:**
- 스크리닝된 종목 리스트

**사용 예제:**
```python
from core.watchlist.stock_screener import StockScreener

screener = StockScreener()
criteria = {
    'min_market_cap': 100000000000,  # 1000억원 이상
    'max_per': 15.0,                 # PER 15 이하
    'min_volume': 100000,            # 최소 거래량
    'sector': ['기술']               # 기술주만
}

stocks = screener.screen_stocks(criteria)
for stock in stocks:
    print(f"{stock['stock_code']}: {stock['stock_name']}")
```

##### `apply_momentum_filter(stocks: List[Dict], period: int = 20) -> List[Dict]`
모멘텀 필터를 적용합니다.

**매개변수:**
- `stocks`: 종목 리스트
- `period`: 모멘텀 계산 기간 (기본 20일)

**반환값:**
- 필터링된 종목 리스트

### WatchlistManager

감시 리스트를 관리하는 클래스입니다.

#### 클래스 정의
```python
class WatchlistManager:
    def __init__(self, db_path: str = "data/watchlist.db"):
        """
        감시 리스트 관리자 초기화
        
        Args:
            db_path: 데이터베이스 경로
        """
```

#### 주요 메서드

##### `add_stock(stock_code: str, stock_name: str, category: str = "default") -> bool`
감시 리스트에 종목을 추가합니다.

**매개변수:**
- `stock_code`: 종목 코드
- `stock_name`: 종목명
- `category`: 카테고리 (기본값: "default")

**반환값:**
- 성공 여부 (bool)

**사용 예제:**
```python
from core.watchlist.watchlist_manager import WatchlistManager

manager = WatchlistManager()
success = manager.add_stock("005930", "삼성전자", "large_cap")
if success:
    print("종목이 감시 리스트에 추가되었습니다.")
```

##### `get_stocks(category: str = None) -> List[Dict]`
감시 리스트의 종목들을 조회합니다.

**매개변수:**
- `category`: 특정 카테고리 (선택적)

**반환값:**
- 종목 리스트

---

## 📈 Phase 2: 일일 선정 (Daily Selection)

### DailyUpdater

일일 종목 선정을 담당하는 클래스입니다.

#### 클래스 정의
```python
class DailyUpdater:
    def __init__(self, watchlist_manager=None, price_analyzer=None):
        """
        일일 업데이터 초기화
        
        Args:
            watchlist_manager: 감시 리스트 관리자
            price_analyzer: 가격 분석기
        """
```

#### 주요 메서드

##### `update_daily_selection() -> List[str]`
일일 종목 선정을 실행합니다.

**반환값:**
- 선정된 종목 코드 리스트

**사용 예제:**
```python
from core.daily_selection.daily_updater import DailyUpdater

updater = DailyUpdater()
selected_stocks = updater.update_daily_selection()
print(f"오늘 선정된 종목: {selected_stocks}")
```

### PriceAnalyzer

가격 분석을 담당하는 클래스입니다.

#### 클래스 정의
```python
class PriceAnalyzer:
    def __init__(self, api_client=None):
        """
        가격 분석기 초기화
        
        Args:
            api_client: API 클라이언트
        """
```

#### 주요 메서드

##### `analyze_stock(stock_code: str, period: int = 20) -> Dict`
개별 종목을 분석합니다.

**매개변수:**
- `stock_code`: 종목 코드
- `period`: 분석 기간

**반환값:**
- 분석 결과 딕셔너리

**사용 예제:**
```python
from core.daily_selection.price_analyzer import PriceAnalyzer

analyzer = PriceAnalyzer()
result = analyzer.analyze_stock("005930")
print(f"분석 결과: {result}")
```

---

## 🤖 Phase 4: AI 학습 (Learning)

### DailyPerformanceAnalyzer

일일 성과 분석을 담당하는 클래스입니다.

#### 클래스 정의
```python
class DailyPerformanceAnalyzer:
    def __init__(self, data_dir: str = "data/performance"):
        """
        일일 성과 분석기 초기화
        
        Args:
            data_dir: 데이터 저장 디렉토리
        """
```

#### 주요 메서드

##### `analyze_daily_performance(date: str, selected_stocks: List[str], metrics: Dict) -> Dict`
일일 성과를 분석합니다.

**매개변수:**
- `date`: 분석 날짜 (YYYY-MM-DD)
- `selected_stocks`: 선정된 종목 리스트
- `metrics`: 성과 지표

**반환값:**
- 분석 결과 딕셔너리

**사용 예제:**
```python
from core.learning.analysis.daily_performance import DailyPerformanceAnalyzer

analyzer = DailyPerformanceAnalyzer()
result = analyzer.analyze_daily_performance(
    date="2024-01-17",
    selected_stocks=["005930", "000660"],
    metrics={"total_return": 0.025, "win_rate": 0.75}
)
```

### ParameterManager

파라미터 관리를 담당하는 클래스입니다.

#### 클래스 정의
```python
class ParameterManager:
    def __init__(self, data_dir: str = "data/parameters"):
        """
        파라미터 관리자 초기화
        
        Args:
            data_dir: 데이터 저장 디렉토리
        """
```

#### 주요 메서드

##### `create_random_parameter_set(strategy_name: str) -> ParameterSet`
랜덤 파라미터 세트를 생성합니다.

**매개변수:**
- `strategy_name`: 전략명

**반환값:**
- 파라미터 세트 객체

**사용 예제:**
```python
from core.learning.optimization.parameter_manager import ParameterManager

manager = ParameterManager()
params = manager.create_random_parameter_set("momentum")
print(f"생성된 파라미터: {params.parameters}")
```

---

## 🔍 Phase 5: 시장 모니터링 (Market Monitor)

### MarketMonitor

실시간 시장 모니터링을 담당하는 클래스입니다.

#### 클래스 정의
```python
class MarketMonitor:
    def __init__(self, config: MonitoringConfig = None, data_dir: str = "data/market_monitoring"):
        """
        시장 모니터 초기화
        
        Args:
            config: 모니터링 설정
            data_dir: 데이터 저장 디렉토리
        """
```

#### 주요 메서드

##### `add_symbols(symbols: List[str]) -> None`
모니터링 대상 종목을 추가합니다.

**매개변수:**
- `symbols`: 종목 코드 리스트

**사용 예제:**
```python
from core.market_monitor.market_monitor import MarketMonitor

monitor = MarketMonitor()
monitor.add_symbols(["005930", "000660", "035420"])
monitor.start_monitoring()
```

##### `get_current_snapshot() -> MarketSnapshot`
현재 시장 스냅샷을 조회합니다.

**반환값:**
- 시장 스냅샷 객체

### AnomalyDetector

이상 감지를 담당하는 클래스입니다.

#### 클래스 정의
```python
class AnomalyDetector:
    def __init__(self, config: AnomalyConfig = None, data_dir: str = "data/anomaly_detection"):
        """
        이상 감지기 초기화
        
        Args:
            config: 이상 감지 설정
            data_dir: 데이터 저장 디렉토리
        """
```

#### 주요 메서드

##### `detect_anomalies(current_snapshot: MarketSnapshot, recent_snapshots: List[MarketSnapshot]) -> List[AnomalyAlert]`
이상 상황을 감지합니다.

**매개변수:**
- `current_snapshot`: 현재 스냅샷
- `recent_snapshots`: 최근 스냅샷들

**반환값:**
- 이상 알림 리스트

**사용 예제:**
```python
from core.market_monitor.anomaly_detector import AnomalyDetector

detector = AnomalyDetector()
alerts = detector.detect_anomalies(current_snapshot, recent_snapshots)
for alert in alerts:
    print(f"이상 감지: {alert.title}")
```

---

## ⚡ 성능 최적화 (Performance)

### PerformanceOptimizer

시스템 성능 최적화를 담당하는 클래스입니다.

#### 클래스 정의
```python
class PerformanceOptimizer:
    def __init__(self, data_dir: str = "data/performance"):
        """
        성능 최적화기 초기화
        
        Args:
            data_dir: 데이터 저장 디렉토리
        """
```

#### 주요 메서드

##### `manual_optimization(level: OptimizationLevel = None) -> Dict`
수동 최적화를 실행합니다.

**매개변수:**
- `level`: 최적화 레벨

**반환값:**
- 최적화 결과 딕셔너리

**사용 예제:**
```python
from core.performance.optimizer import PerformanceOptimizer, OptimizationLevel

optimizer = PerformanceOptimizer()
result = optimizer.manual_optimization(OptimizationLevel.AGGRESSIVE)
print(f"최적화 결과: {result['overall_success']}")
```

---

## 🛡️ 안정성 관리 (Resilience)

### StabilityManager

시스템 안정성을 관리하는 클래스입니다.

#### 클래스 정의
```python
class StabilityManager:
    def __init__(self, data_dir: str = "data/stability"):
        """
        안정성 관리자 초기화
        
        Args:
            data_dir: 데이터 저장 디렉토리
        """
```

#### 주요 메서드

##### `register_component(component: str, **config) -> None`
컴포넌트를 등록합니다.

**매개변수:**
- `component`: 컴포넌트명
- `circuit_breaker_config`: 회로 차단기 설정
- `fallback_function`: 대체 함수
- `health_check_function`: 헬스 체크 함수

**사용 예제:**
```python
from core.resilience.stability_manager import StabilityManager

manager = StabilityManager()
manager.register_component(
    component="api_client",
    circuit_breaker_config={'failure_threshold': 5},
    fallback_function=fallback_api_call,
    health_check_function=check_api_health
)
```

### 데코레이터

#### `@retry(max_attempts=3, delay=1.0, backoff=2.0)`
함수에 재시도 로직을 추가합니다.

**매개변수:**
- `max_attempts`: 최대 시도 횟수
- `delay`: 초기 지연 시간
- `backoff`: 지연 시간 배수

**사용 예제:**
```python
from core.resilience.stability_manager import retry

@retry(max_attempts=3, delay=1.0)
def unstable_api_call():
    # 불안정한 API 호출
    pass
```

---

## 🔌 플러그인 시스템 (Plugins)

### PluginRegistry

플러그인을 등록하고 관리하는 클래스입니다.

#### 클래스 정의
```python
class PluginRegistry:
    def __init__(self):
        """플러그인 레지스트리 초기화"""
```

#### 주요 메서드

##### `register_plugin(plugin: BasePlugin) -> bool`
플러그인을 등록합니다.

**매개변수:**
- `plugin`: 플러그인 인스턴스

**반환값:**
- 등록 성공 여부

**사용 예제:**
```python
from core.plugins.registry import PluginRegistry
from my_plugin import CustomAnalyzer

registry = PluginRegistry()
plugin = CustomAnalyzer()
success = registry.register_plugin(plugin)
```

---

## 📦 패키지 관리 (Packages)

### PackageManager

패키지를 관리하는 클래스입니다.

#### 클래스 정의
```python
class PackageManager:
    def __init__(self, repository_path: str = "data/packages"):
        """
        패키지 관리자 초기화
        
        Args:
            repository_path: 패키지 저장소 경로
        """
```

#### 주요 메서드

##### `install_package(package_path: str) -> bool`
패키지를 설치합니다.

**매개변수:**
- `package_path`: 패키지 파일 경로

**반환값:**
- 설치 성공 여부

**사용 예제:**
```python
from core.packages.installer import PackageInstaller

installer = PackageInstaller()
success = installer.install_package("my_strategy.hqp")
```

---

## 🎯 의존성 주입 (DI)

### DIContainer

의존성 주입 컨테이너입니다.

#### 클래스 정의
```python
class DIContainer:
    def __init__(self):
        """의존성 주입 컨테이너 초기화"""
```

#### 주요 메서드

##### `register(interface: type, implementation: type, lifetime: Lifetime = Lifetime.TRANSIENT) -> None`
서비스를 등록합니다.

**매개변수:**
- `interface`: 인터페이스 타입
- `implementation`: 구현 타입  
- `lifetime`: 생명주기

**사용 예제:**
```python
from core.di.container import DIContainer, Lifetime

container = DIContainer()
container.register(IStockScreener, StockScreener, Lifetime.SINGLETON)
```

##### `resolve(service_type: type) -> object`
서비스를 해결합니다.

**매개변수:**
- `service_type`: 서비스 타입

**반환값:**
- 서비스 인스턴스

---

## 📊 데이터 모델

### 공통 데이터 타입

#### StockInfo
```python
@dataclass
class StockInfo:
    stock_code: str
    stock_name: str
    market_cap: float
    sector: str
    per: float
    pbr: float
    current_price: float
    volume: int
```

#### MarketSnapshot
```python
@dataclass  
class MarketSnapshot:
    timestamp: datetime
    market_status: MarketStatus
    kospi_index: float
    kosdaq_index: float
    total_trading_value: float
    stock_snapshots: List[StockSnapshot]
```

#### PerformanceMetrics
```python
@dataclass
class PerformanceMetrics:
    total_return: float
    win_rate: float
    max_drawdown: float
    sharpe_ratio: float
    volatility: float
```

---

## 🔧 설정 관리

### 환경 변수

시스템에서 사용하는 주요 환경 변수들:

```env
# API 설정
KIS_APP_KEY=your_app_key
KIS_APP_SECRET=your_app_secret
KIS_ACCESS_TOKEN=your_access_token

# 환경 설정
ENVIRONMENT=virtual  # virtual, prod
LOG_LEVEL=INFO       # DEBUG, INFO, WARNING, ERROR

# 데이터베이스
DB_PATH=data/hantu_quant.db

# 성능 설정
MAX_WORKERS=4
BATCH_SIZE=500
CACHE_SIZE=1000

# 알림 설정
EMAIL_ENABLED=true
SLACK_WEBHOOK_URL=https://hooks.slack.com/...
```

### 설정 파일

#### monitoring_config.json
```json
{
    "update_interval": 30,
    "max_symbols": 100,
    "price_change_threshold": 0.05,
    "volume_change_threshold": 2.0,
    "enable_alerts": true
}
```

#### optimization_config.json
```json
{
    "optimization_level": "balanced",
    "auto_optimization": true,
    "memory_threshold": 80.0,
    "cpu_threshold": 85.0
}
```

---

## 🚨 예외 처리

### 공통 예외

#### `HantuQuantException`
시스템의 기본 예외 클래스입니다.

#### `APIConnectionError`
API 연결 오류 시 발생합니다.

#### `DataValidationError`
데이터 검증 실패 시 발생합니다.

#### `OptimizationError`
최적화 과정에서 오류 발생 시 발생합니다.

### 예외 처리 예제

```python
from core.exceptions import APIConnectionError, DataValidationError

try:
    result = api_client.get_stock_data("005930")
except APIConnectionError as e:
    logger.error(f"API 연결 실패: {e}")
    # 대체 방법 실행
except DataValidationError as e:
    logger.warning(f"데이터 검증 실패: {e}")
    # 데이터 정제 후 재시도
```

---

## 📝 로깅

### 로거 사용법

```python
from core.utils.logging import get_logger

logger = get_logger(__name__)

# 다양한 로그 레벨
logger.debug("디버그 정보")
logger.info("일반 정보")
logger.warning("경고")
logger.error("오류")
logger.critical("심각한 오류")

# 구조화된 로깅
logger.info("종목 분석 완료", extra={
    "stock_code": "005930",
    "analysis_time": 2.5,
    "result": "buy"
})
```

### 로그 필터링

민감한 정보는 자동으로 마스킹됩니다:

```python
# API 키, 토큰 등이 자동으로 마스킹됨
logger.info(f"API 호출: {api_key}")  # "API 호출: ***masked***"
```

---

## 🧪 테스트 지원

### Mock 데이터 생성

```python
from tests.utils import create_mock_stock_data, create_mock_market_snapshot

# Mock 종목 데이터 생성
mock_stocks = create_mock_stock_data(count=10)

# Mock 시장 스냅샷 생성
mock_snapshot = create_mock_market_snapshot()
```

### 테스트 유틸리티

```python
from tests.utils import assert_performance_improved, assert_no_errors

# 성과 개선 검증
assert_performance_improved(before_metrics, after_metrics)

# 오류 없음 검증
assert_no_errors(system_logs)
```

---

## 📊 성능 메트릭

### 시스템 메트릭

- `processing_time`: 처리 시간 (초)
- `memory_usage`: 메모리 사용량 (MB)
- `cpu_usage`: CPU 사용률 (%)
- `api_call_count`: API 호출 횟수
- `error_rate`: 오류율 (%)

### 투자 메트릭

- `total_return`: 총 수익률
- `win_rate`: 승률
- `sharpe_ratio`: 샤프 비율
- `max_drawdown`: 최대 손실
- `volatility`: 변동성

---

## 🔄 버전 관리

### API 버전

현재 API 버전: `v1.0.0`

### 호환성

- Python 3.9+
- 모든 주요 운영체제 지원
- 한국투자증권 API v1.0 호환

---

## 📞 지원

API 관련 문의나 버그 리포트는 다음을 통해 연락주세요:

- 📧 이메일: api-support@hantu-quant.com
- 🐛 버그 리포트: GitHub Issues
- 📖 추가 문서: [개발자 위키](https://github.com/hantu-quant/wiki)

---

**마지막 업데이트**: 2024-01-17
**API 버전**: v1.0.0 