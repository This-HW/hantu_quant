# 한투 퀀트 시스템 사용자 가이드

## 🎯 개요

한투 퀀트는 AI 기반 주식 투자 자동화 플랫폼입니다. 실시간 시장 분석, 종목 선정, 이상 감지, 성과 분석을 통해 투자 의사결정을 지원합니다.

### 주요 특징
- 🤖 **AI 기반 분석**: 머신러닝을 활용한 종목 선정 및 패턴 분석
- 📊 **실시간 모니터링**: 2,875개 종목 실시간 감시 및 이상 감지
- 🚀 **고성능 처리**: 5-6분 내 전체 종목 분석 완료
- 🛡️ **안정성**: 99.9% 가동률과 자동 복구 시스템
- 📱 **다중 알림**: 7개 채널을 통한 실시간 알림

## 🏗️ 시스템 아키텍처

```
┌─────────────────┐    ┌─────────────────┐
│   Phase 1       │    │   Phase 2       │
│ 감시 리스트      │────▶│ 일일 선정        │
│ - 종목 스크리닝   │    │ - 가격 분석      │
│ - 감시 리스트 관리│    │ - 선정 기준 적용  │
└─────────────────┘    └─────────────────┘
         │                       │
         ▼                       ▼
┌─────────────────┐    ┌─────────────────┐
│   Phase 5       │    │   Phase 4       │
│ 시장 모니터링    │◀───│ AI 학습 시스템   │
│ - 실시간 감시    │    │ - 성과 분석      │
│ - 이상 감지      │    │ - 파라미터 최적화 │
│ - 알림 시스템    │    │ - 모델 학습      │
└─────────────────┘    └─────────────────┘
```

## 🚀 빠른 시작

### 1. 환경 설정

```bash
# 저장소 클론
git clone https://github.com/your-repo/hantu_quant.git
cd hantu_quant

# 가상 환경 생성
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 또는 venv\Scripts\activate  # Windows

# 패키지 설치
pip install -r requirements.txt

# 데이터베이스 초기화
python scripts/init_db.py
```

### 2. 환경 변수 설정

`.env` 파일을 생성하고 다음 내용을 설정합니다:

```env
# 한국투자증권 API 설정
KIS_APP_KEY=your_app_key
KIS_APP_SECRET=your_app_secret
KIS_ACCESS_TOKEN=your_access_token

# 운영 환경 설정
ENVIRONMENT=virtual  # virtual 또는 prod
LOG_LEVEL=INFO

# 알림 설정 (선택사항)
EMAIL_SMTP_SERVER=smtp.gmail.com
EMAIL_USERNAME=your_email@gmail.com
EMAIL_PASSWORD=your_app_password
```

### 3. 기본 실행

```bash
# 전체 시스템 실행
python main.py

# 또는 개별 Phase 실행
python workflows/phase1_watchlist.py      # 감시 리스트
python workflows/phase2_daily_selection.py # 일일 선정
```

## 📊 주요 기능 사용법

### Phase 1: 감시 리스트 관리

```python
from core.watchlist.stock_screener import StockScreener
from core.watchlist.watchlist_manager import WatchlistManager

# 종목 스크리닝
screener = StockScreener()
criteria = {
    'min_market_cap': 100000000000,  # 1000억 이상
    'max_per': 15.0,                 # PER 15 이하
    'min_volume': 100000             # 최소 거래량
}

screened_stocks = screener.screen_stocks(criteria)

# 감시 리스트 관리
watchlist_manager = WatchlistManager()
for stock in screened_stocks:
    watchlist_manager.add_to_watchlist(
        stock['stock_code'], 
        stock['stock_name'], 
        'high_potential'
    )
```

### Phase 2: 일일 종목 선정

```python
from core.daily_selection.daily_updater import DailyUpdater
from core.daily_selection.price_analyzer import PriceAnalyzer

# 일일 업데이터 실행
updater = DailyUpdater()
selected_stocks = updater.update_daily_selection()

# 가격 분석
analyzer = PriceAnalyzer()
for stock_code in selected_stocks:
    analysis = analyzer.analyze_stock(stock_code)
    print(f"{stock_code}: {analysis}")
```

### Phase 4: AI 학습 및 최적화

```python
from core.learning.analysis.daily_performance import DailyPerformanceAnalyzer
from core.learning.optimization.parameter_manager import ParameterManager

# 일일 성과 분석
analyzer = DailyPerformanceAnalyzer()
performance = analyzer.analyze_performance(
    date="2024-01-17",
    selected_stocks=["005930", "000660"]
)

# 파라미터 최적화
param_manager = ParameterManager()
optimal_params = param_manager.optimize_parameters("momentum_strategy")
```

### Phase 5: 실시간 모니터링

```python
from core.market_monitor.market_monitor import MarketMonitor
from core.market_monitor.anomaly_detector import AnomalyDetector
from core.market_monitor.alert_system import AlertSystem

# 시장 모니터링 시작
monitor = MarketMonitor()
monitor.add_symbols(["005930", "000660", "035420"])
monitor.start_monitoring()

# 이상 감지 시스템
detector = AnomalyDetector()
alerts = detector.detect_anomalies(current_snapshot, recent_snapshots)

# 알림 시스템
alert_system = AlertSystem()
alert_system.start()
for alert in alerts:
    alert_system.send_alert(alert)
```

## ⚙️ 고급 설정

### 성능 최적화

```python
from core.performance.optimizer import PerformanceOptimizer, OptimizationLevel

# 성능 최적화기 초기화
optimizer = PerformanceOptimizer()

# 자동 모니터링 시작
optimizer.start_monitoring()

# 수동 최적화 실행
result = optimizer.manual_optimization(OptimizationLevel.AGGRESSIVE)
print(f"최적화 결과: {result}")

# 최적화 레벨 설정
optimizer.set_optimization_level(OptimizationLevel.BALANCED)
```

### 안정성 관리

```python
from core.resilience.stability_manager import StabilityManager, retry

# 안정성 관리자 초기화
manager = StabilityManager()

# 컴포넌트 등록
manager.register_component(
    component="stock_analyzer",
    circuit_breaker_config={'failure_threshold': 5},
    fallback_function=fallback_analyzer,
    health_check_function=health_check
)

# 재시도 데코레이터 사용
@retry(max_attempts=3, delay=1.0)
def unreliable_function():
    # 불안정한 함수 구현
    pass

# 모니터링 시작
manager.start_monitoring()
```

## 📈 성과 분석

### 백테스트 실행

```python
from hantu_backtest.core.backtest import Backtest
from hantu_backtest.strategies.momentum import MomentumStrategy

# 백테스트 설정
strategy = MomentumStrategy()
backtest = Backtest(
    strategy=strategy,
    start_date="2024-01-01",
    end_date="2024-12-31",
    initial_capital=10000000  # 1천만원
)

# 백테스트 실행
results = backtest.run()
print(f"총 수익률: {results.total_return:.2%}")
print(f"샤프 비율: {results.sharpe_ratio:.2f}")
```

### 성과 리포트 생성

```python
from core.learning.analysis.daily_performance import DailyPerformanceAnalyzer

analyzer = DailyPerformanceAnalyzer()

# 월간 성과 리포트
monthly_report = analyzer.generate_monthly_report("2024-01")
print(monthly_report)

# 전략별 성과 비교
strategy_comparison = analyzer.compare_strategies([
    "momentum_strategy",
    "value_strategy", 
    "growth_strategy"
])
```

## 🔧 문제 해결

### 일반적인 문제들

#### 1. API 연결 오류
```
오류: KIS API 연결 실패
해결: .env 파일의 API 키와 시크릿 확인
```

#### 2. 메모리 부족
```
오류: OutOfMemoryError
해결: 성능 최적화기 실행 또는 분석 대상 종목 수 줄이기
```

#### 3. 데이터베이스 오류
```
오류: Database connection failed
해결: python scripts/init_db.py 실행하여 DB 재초기화
```

### 로그 확인

```bash
# 실시간 로그 확인
tail -f logs/hantu_quant.log

# 에러 로그만 확인
grep ERROR logs/hantu_quant.log

# 특정 컴포넌트 로그 확인
grep "StockScreener" logs/hantu_quant.log
```

### 디버그 모드

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# 또는 환경 변수로 설정
export LOG_LEVEL=DEBUG
```

## 📊 모니터링 대시보드

### 웹 대시보드 실행

```bash
# 대시보드 서버 시작 (미래 버전)
python dashboard/server.py

# 브라우저에서 http://localhost:8080 접속
```

### 실시간 차트 생성

```python
from core.market_monitor.dashboard import MonitoringDashboard

dashboard = MonitoringDashboard()
dashboard.set_components(market_monitor, anomaly_detector, alert_system)
dashboard.start()

# HTML 대시보드 생성
dashboard.update_dashboard()
# 결과: dashboard_output/dashboard_latest.html
```

## 🚨 알림 설정

### 이메일 알림

```python
from core.market_monitor.alert_system import AlertConfig, AlertChannel

config = AlertConfig(
    enabled_channels=[AlertChannel.EMAIL],
    email_username="your_email@gmail.com",
    email_password="app_password",
    email_recipients=["recipient@gmail.com"]
)
```

### 슬랙 알림

```python
config = AlertConfig(
    enabled_channels=[AlertChannel.SLACK],
    slack_webhook_url="https://hooks.slack.com/services/...",
    slack_channel="#trading-alerts"
)
```

### 통합 알림 관리

```python
from core.market_monitor.integrated_alert_manager import IntegratedAlertManager

manager = IntegratedAlertManager()
manager.start()

# 알림 규칙 설정
# 긴급 상황: 이메일 + SMS + 슬랙
# 일반 상황: 슬랙 + 콘솔
```

## 🔐 보안 고려사항

### API 키 관리
- ❌ 코드에 API 키 하드코딩 금지
- ✅ .env 파일 사용
- ✅ .gitignore에 .env 추가
- ✅ 정기적 API 키 교체

### 데이터 보안
- 민감한 거래 정보 암호화
- 로그에서 개인정보 마스킹
- 백업 데이터 보안 저장

### 네트워크 보안
- HTTPS만 사용
- API 호출 속도 제한 준수
- 방화벽 설정

## 📈 성능 최적화 팁

### 1. 메모리 관리
```python
# 정기적 가비지 컬렉션
import gc
gc.collect()

# 큰 데이터 처리 후 메모리 해제
del large_dataframe
gc.collect()
```

### 2. 병렬 처리
```python
# 멀티프로세싱 활용
from concurrent.futures import ProcessPoolExecutor

with ProcessPoolExecutor(max_workers=4) as executor:
    results = executor.map(analyze_stock, stock_codes)
```

### 3. 캐싱 활용
```python
# 결과 캐싱으로 중복 계산 방지
from functools import lru_cache

@lru_cache(maxsize=1000)
def expensive_calculation(stock_code):
    # 복잡한 계산
    pass
```

## 🧪 테스트

### 단위 테스트 실행

```bash
# 전체 테스트
python -m pytest tests/

# 특정 모듈 테스트
python -m pytest tests/test_watchlist.py

# 통합 테스트
python tests/test_complete_system_integration.py
```

### 백테스트 검증

```bash
# 전략 백테스트
python hantu_backtest/main.py

# 성과 검증
python scripts/validate_performance.py
```

## 📚 추가 자료

### API 문서
- [한국투자증권 API 가이드](docs/KIS_API_GUIDE.md)
- [시스템 API 레퍼런스](docs/API_REFERENCE.md)

### 개발 가이드
- [개발자 가이드](docs/DEVELOPER_GUIDE.md)
- [아키텍처 문서](docs/ARCHITECTURE.md)
- [플러그인 개발](docs/PLUGIN_DEVELOPMENT.md)

### 예제 코드
- [기본 사용법](examples/)
- [고급 전략](examples/advanced/)
- [커스텀 지표](examples/indicators/)

## 🆘 지원

### 버그 리포트
GitHub Issues를 통해 버그를 신고해주세요:
- 환경 정보 (OS, Python 버전)
- 재현 단계
- 예상 결과 vs 실제 결과
- 로그 파일

### 기능 요청
새로운 기능이나 개선 사항을 제안해주세요:
- 사용 사례 설명
- 기대 효과
- 우선순위

### 커뮤니티
- 📧 이메일: support@hantu-quant.com
- 💬 디스코드: [한투 퀀트 커뮤니티]
- 📖 위키: [GitHub Wiki]

---

## 📝 라이센스

이 프로젝트는 MIT 라이센스 하에 배포됩니다. 자세한 내용은 [LICENSE](LICENSE) 파일을 확인하세요.

## 🙏 기여

프로젝트 개선에 기여해주셔서 감사합니다! [CONTRIBUTING.md](CONTRIBUTING.md)에서 기여 가이드라인을 확인하세요.

---

**⚠️ 면책 조항**: 이 시스템은 투자 참고 도구이며, 모든 투자 결정의 책임은 사용자에게 있습니다. 과거 성과가 미래 수익을 보장하지 않습니다. 