# Technical Review & Next Phase Planning
## Service Entry Point Consolidation

**Document Version**: 1.0
**Review Date**: 2025-12-29
**Status**: Post-Implementation Technical Review

---

## 1. Current State Summary

### 1.1 Completed Features / Stories

| Phase | Feature | Status | Location |
|-------|---------|--------|----------|
| Phase 1 | Stock Screening | 100% | `workflows/phase1_watchlist.py`, `core/watchlist/` |
| Phase 2 | Daily Selection | 100% | `workflows/phase2_daily_selection.py`, `core/daily_selection/` |
| Phase 3 | Auto Trading | 100% | `main.py`, `core/trading/` |
| Phase 4 | AI Learning System | 100% | `core/learning/` |
| Phase 5 | Real-time Monitoring | 100% | `core/market_monitor/`, `core/monitoring/` |
| Infra | API Server | 100% | `api-server/main.py` |
| Infra | Telegram Notification | 100% | `core/utils/telegram_notifier.py` |
| Infra | Integrated Scheduler | 100% | `workflows/integrated_scheduler.py` |

### 1.2 Architecture Overview

```
                    ┌─────────────────────────────────────────┐
                    │           Entry Points (분산됨)          │
                    ├─────────────────────────────────────────┤
                    │  main.py                                │
                    │  workflows/phase1_watchlist.py          │
                    │  workflows/phase2_daily_selection.py    │
                    │  workflows/integrated_scheduler.py      │
                    │  api-server/main.py                     │
                    │  scripts/auto_trading.py                │
                    │  scripts/manage.py                      │
                    └─────────────────────────────────────────┘
                                      │
                    ┌─────────────────┴─────────────────┐
                    │           Core Modules            │
                    ├───────────────────────────────────┤
                    │  core/api/          - API Clients │
                    │  core/watchlist/    - Screening   │
                    │  core/daily_selection/ - Selection│
                    │  core/trading/      - Execution   │
                    │  core/learning/     - AI/ML       │
                    │  core/market_monitor/ - Monitor   │
                    │  core/config/       - Settings    │
                    │  core/utils/        - Utilities   │
                    └───────────────────────────────────┘
```

### 1.3 Immutable Technical Decisions

| Category | Decision | Rationale |
|----------|----------|-----------|
| Language | Python 3.11+ | ML ecosystem, async support |
| Framework | FastAPI | Async REST, OpenAPI docs |
| ORM | SQLAlchemy 2.0 | Type-safe ORM, async support |
| Scheduler | schedule + asyncio | Lightweight, native async |
| Notification | Telegram Bot API | Free, real-time, mobile |
| API | Korea Investment Securities API | Target broker |

### 1.4 Compatibility Constraints

- **KIS API Rate Limits**: 1회/초 (호가), 10회/초 (시세)
- **Database Schema**: SQLAlchemy models in `core/database/models.py` - 변경 시 migration 필수
- **Config Interface**: `.env` + `core/config/` 구조 유지
- **Telegram Config**: `config/telegram_config.json` 구조 유지

---

## 2. Open Issues & Gaps

### 2.1 Critical Issue: Fragmented Entry Points

**현재 상태**: 서비스 시작점이 7개 이상 파일에 분산됨

| Entry Point | Purpose | Command |
|-------------|---------|---------|
| `main.py` | Trading CLI | `python main.py trade/balance/find` |
| `workflows/phase1_watchlist.py` | Screening | `python workflows/phase1_watchlist.py screen` |
| `workflows/phase2_daily_selection.py` | Selection | `python workflows/phase2_daily_selection.py update` |
| `workflows/integrated_scheduler.py` | Scheduler | `python workflows/integrated_scheduler.py` |
| `api-server/main.py` | API Server | `python api-server/main.py` |
| `scripts/auto_trading.py` | Auto Trade | `python scripts/auto_trading.py` |
| `scripts/manage.py` | Management | `python scripts/manage.py` |

**문제점**:
1. 사용자가 어떤 명령을 실행해야 하는지 혼란
2. 프로세스 관리가 개별적으로 필요
3. 로그 파일이 분산됨
4. 환경 초기화 코드가 중복됨

### 2.2 Incomplete Tasks

| Task | Status | Blocker |
|------|--------|---------|
| Unified CLI Entry Point | Not Started | Design needed |
| Process Manager | Not Started | Design needed |
| Service Status Dashboard | Partial | CLI version only |

### 2.3 Technical Debt

| Item | Location | Impact |
|------|----------|--------|
| Duplicate sys.path manipulation | 모든 entry point 파일 | Maintainability |
| Inconsistent logging setup | 각 entry point마다 다름 | Debugging |
| Hardcoded target_codes | `main.py:131-137` | Flexibility |
| Multiple Telegram config loaders | `integrated_scheduler.py`, `telegram_notifier.py` | DRY violation |

### 2.4 Structural Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Process orphaning | Medium | High | Process manager 도입 |
| Log file corruption (concurrent write) | Low | Medium | Centralized logging |
| Config drift between services | Medium | Medium | Single config loader |

### 2.5 Performance Bottlenecks

| Area | Complexity | I/O | Scaling Risk |
|------|------------|-----|--------------|
| Stock screening | O(n) per stock | Network (KIS API) | Rate limit bound |
| Daily selection | O(n * m) indicators | Network + CPU | Memory bound for large portfolios |
| Scheduler loop | O(1) | None | Stable |

---

## 3. Security & Compliance Review

### 3.1 Trust Boundaries

```
┌──────────────────────────────────────────────────────────┐
│                    INTERNAL (Trusted)                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │
│  │   main.py   │  │  workflows/ │  │   core/     │       │
│  └─────────────┘  └─────────────┘  └─────────────┘       │
│                                                          │
│  ┌─────────────────────────────────────────────────┐     │
│  │              api-server/main.py                 │     │
│  │         (X-API-Key Header Required)             │     │
│  └─────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────┘
                           │
          ─────────────────┼───────────────── Trust Boundary
                           │
┌──────────────────────────────────────────────────────────┐
│                   EXTERNAL (Untrusted)                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │
│  │   Web UI    │  │  KIS API    │  │  Telegram   │       │
│  └─────────────┘  └─────────────┘  └─────────────┘       │
└──────────────────────────────────────────────────────────┘
```

### 3.2 Data Flow Security Risks

| Flow | Risk | Current Mitigation | Status |
|------|------|-------------------|--------|
| .env → Process | Credential exposure | `.env` not in git, sensitive filter in logs | OK |
| API Server → Client | Unauthorized access | X-API-Key header, CORS | OK |
| Telegram → User | Message interception | HTTPS, bot token | OK |
| KIS API → System | Token exposure | Memory only, no disk write | OK |

### 3.3 Authentication Model

- **API Server**: `X-API-Key` header (static key from `API_SERVER_KEY` env)
- **KIS API**: OAuth 2.0 (APP_KEY + APP_SECRET → Access Token)
- **Telegram**: Bot Token (static)

### 3.4 Input Validation Points

| Entry | Validation | Status |
|-------|------------|--------|
| CLI arguments | argparse type checking | OK |
| API endpoints | Pydantic models | OK |
| Stock codes | Regex validation in `validators.py` | OK |
| Config files | Schema validation | Partial - JSON schema 없음 |

### 3.5 Sensitive Data Exposure Risks

| Location | Risk | Recommendation |
|----------|------|----------------|
| `api-server/main.py:59` | API_KEY in memory | OK (no logging) |
| Error handlers | Stack trace in logs | Filtered via `add_sensitive_filter` |
| Telegram notifications | Trade details visible | OK (intended behavior) |

### 3.6 Security Principles (Architecture-Compatible)

- **적용 가능**: Rate limiting on API server, Log rotation, Config validation
- **구조 변경 필요 없음**: 현재 아키텍처로 충분

---

## 4. Performance & Efficiency Analysis

### 4.1 Time Complexity by Component

| Component | Operation | Complexity | Notes |
|-----------|-----------|------------|-------|
| StockScreener | screen_all | O(n) | n = 2,875 stocks |
| PriceAnalyzer | analyze_stock | O(k) | k = indicator count (~10) |
| WatchlistManager | add/remove | O(1) | dict-based |
| IntegratedScheduler | tick | O(s) | s = scheduled jobs (~15) |

### 4.2 Space Complexity

| Component | Memory Usage | Growth Pattern |
|-----------|--------------|----------------|
| Stock data cache | ~50MB | Linear with stock count |
| Price history (60 days) | ~200MB | Linear with watchlist size |
| ML models | ~100MB | Fixed (model size) |

### 4.3 Parallel/Async Processing

| Component | Current | Optimal |
|-----------|---------|---------|
| Phase 1 screening | 4-8 workers | OK (configurable) |
| Phase 2 analysis | 4-8 workers | OK (configurable) |
| API Server | async (uvicorn) | OK |
| Scheduler | single thread + async | OK for current scale |

### 4.4 Caching Opportunities

| Data | Current | Recommendation |
|------|---------|----------------|
| Stock list | File cache | OK |
| Price data | API call per request | Redis cache 가능 (optional) |
| Indicator calc | Recalculate | In-memory LRU cache 가능 |

### 4.5 Inefficiency Points

| Location | Issue | Impact |
|----------|-------|--------|
| 각 entry point의 초기화 | Import overhead 중복 | Startup ~2-3s per process |
| Telegram config 다중 로드 | File I/O 중복 | Minor |

---

## 5. Scope for Next Phase

### Feature 1: Unified Service Management System

#### Story 1.1: Unified CLI Entry Point

**Task 1.1.1**: Create `hantu` CLI command structure
- **Description**: `hantu [command] [subcommand]` 형태의 통합 CLI 생성
- **Dependencies**: None
- **Priority**: High
- **Urgency**: High
- **Expected Impact**: 구조 변경 (신규 파일 추가, 기존 파일 유지)
- **Required Test Type**: Feature Test
- **Security Impact**: None
- **Performance Impact**: Minor (startup 최적화)

**Task 1.1.2**: Implement service subcommands
- **Description**: `hantu start [service]`, `hantu stop [service]`, `hantu status` 구현
- **Dependencies**: Task 1.1.1
- **Priority**: High
- **Urgency**: High
- **Expected Impact**: 신규 기능 추가
- **Required Test Type**: Integration Test
- **Security Impact**: None
- **Performance Impact**: None

**Task 1.1.3**: Migrate existing commands
- **Description**: 기존 `main.py`, `workflows/*.py` 명령들을 통합 CLI로 연결
- **Dependencies**: Task 1.1.2
- **Priority**: Medium
- **Urgency**: Medium
- **Expected Impact**: 부분 수정 (기존 파일 wrapper 추가)
- **Required Test Type**: Integration Test
- **Security Impact**: None
- **Performance Impact**: None

#### Story 1.2: Process Manager

**Task 1.2.1**: Design process registry
- **Description**: 실행 중인 서비스 프로세스 추적을 위한 PID 파일 및 상태 관리
- **Dependencies**: Task 1.1.1
- **Priority**: High
- **Urgency**: Medium
- **Expected Impact**: 신규 기능 추가
- **Required Test Type**: Story Test
- **Security Impact**: Review Required (PID file permissions)
- **Performance Impact**: None

**Task 1.2.2**: Implement graceful shutdown
- **Description**: SIGTERM/SIGINT 핸들러 통합 및 graceful shutdown 구현
- **Dependencies**: Task 1.2.1
- **Priority**: High
- **Urgency**: Medium
- **Expected Impact**: 부분 수정
- **Required Test Type**: Integration Test
- **Security Impact**: None
- **Performance Impact**: Minor

**Task 1.2.3**: Health check integration
- **Description**: 각 서비스의 health check endpoint/method 통합
- **Dependencies**: Task 1.2.1
- **Priority**: Medium
- **Urgency**: Low
- **Expected Impact**: 부분 수정
- **Required Test Type**: Integration Test
- **Security Impact**: None
- **Performance Impact**: None

#### Story 1.3: Configuration Consolidation

**Task 1.3.1**: Create unified config loader
- **Description**: 환경변수, JSON, YAML 설정을 통합 로드하는 단일 모듈
- **Dependencies**: None
- **Priority**: Medium
- **Urgency**: Medium
- **Expected Impact**: 부분 수정
- **Required Test Type**: Story Test
- **Security Impact**: Review Required (credential handling)
- **Performance Impact**: Minor (startup 최적화)

**Task 1.3.2**: Implement config validation
- **Description**: JSON Schema 기반 설정 파일 검증
- **Dependencies**: Task 1.3.1
- **Priority**: Medium
- **Urgency**: Low
- **Expected Impact**: 신규 기능 추가
- **Required Test Type**: Story Test
- **Security Impact**: Review Required
- **Performance Impact**: None

### Feature 2: Logging Consolidation

#### Story 2.1: Centralized Logging

**Task 2.1.1**: Implement centralized log manager
- **Description**: 모든 서비스가 공유하는 로그 매니저 구현
- **Dependencies**: None
- **Priority**: Medium
- **Urgency**: Low
- **Expected Impact**: 부분 수정
- **Required Test Type**: Story Test
- **Security Impact**: None
- **Performance Impact**: Minor

**Task 2.1.2**: Add structured logging format
- **Description**: JSON 형식의 구조화된 로그 포맷 적용
- **Dependencies**: Task 2.1.1
- **Priority**: Low
- **Urgency**: Low
- **Expected Impact**: 부분 수정
- **Required Test Type**: Story Test
- **Security Impact**: None
- **Performance Impact**: None

---

## 6. Execution Order

| Order | Task ID | Task Name | Priority | Urgency | Security | Performance |
|-------|---------|-----------|----------|---------|----------|-------------|
| 1 | 1.1.1 | Create `hantu` CLI command structure | High | High | None | Minor |
| 2 | 1.1.2 | Implement service subcommands | High | High | None | None |
| 3 | 1.2.1 | Design process registry | High | Medium | Review | None |
| 4 | 1.3.1 | Create unified config loader | Medium | Medium | Review | Minor |
| 5 | 1.2.2 | Implement graceful shutdown | High | Medium | None | Minor |
| 6 | 1.1.3 | Migrate existing commands | Medium | Medium | None | None |
| 7 | 1.3.2 | Implement config validation | Medium | Low | Review | None |
| 8 | 1.2.3 | Health check integration | Medium | Low | None | None |
| 9 | 2.1.1 | Implement centralized log manager | Medium | Low | None | Minor |
| 10 | 2.1.2 | Add structured logging format | Low | Low | None | None |

---

## 7. Design & Impact Analysis (Top Priority Tasks)

### Task 1.1.1: Create `hantu` CLI command structure

**Architecture Compatibility**: 유지 가능

**Proposed Structure**:
```
hantu/
├── cli/
│   ├── __init__.py
│   ├── main.py          # Click/Typer based CLI
│   ├── commands/
│   │   ├── start.py     # hantu start [service]
│   │   ├── stop.py      # hantu stop [service]
│   │   ├── status.py    # hantu status
│   │   ├── trade.py     # hantu trade [subcommand]
│   │   ├── screen.py    # hantu screen [options]
│   │   └── select.py    # hantu select [options]
```

**Existing Code Impact**:
- `main.py`: 유지 (CLI에서 import하여 호출)
- `workflows/*.py`: 유지 (CLI에서 import하여 호출)
- `api-server/main.py`: 유지 (별도 프로세스로 관리)

**Performance Impact**:
- 초기화 코드 중복 제거로 startup time ~1-2s 단축 예상

**Scalability Impact**: None (CLI layer만 추가)

**Maintenance Impact**:
- 단일 진입점으로 문서화 용이
- 명령어 일관성 향상

### Task 1.2.1: Design process registry

**Architecture Compatibility**: 유지 가능

**Proposed Design**:
```python
# /var/run/hantu/ or ~/.hantu/run/
# scheduler.pid, api.pid, etc.

class ProcessRegistry:
    def register(service_name: str, pid: int) -> None
    def unregister(service_name: str) -> None
    def get_status(service_name: str) -> ProcessStatus
    def list_all() -> Dict[str, ProcessStatus]
```

**Security Considerations**:
- PID 파일 권한: 0600 (owner only)
- Lock file을 통한 다중 인스턴스 방지

**Existing Code Impact**:
- 기존 코드 변경 없음
- 새로운 wrapper layer 추가

### Task 1.3.1: Create unified config loader

**Architecture Compatibility**: 유지 가능

**Proposed Design**:
```python
# core/config/loader.py
class ConfigLoader:
    @staticmethod
    def load() -> Config:
        # 1. Load .env
        # 2. Load config/*.yaml
        # 3. Load config/*.json
        # 4. Merge and validate
        return Config(...)
```

**Security Considerations**:
- Credential masking in logs 유지
- Config 객체에 credential getter method 분리

**Existing Code Impact**:
- `core/config/api_config.py`: 리팩토링 (loader 사용)
- `integrated_scheduler.py`: Telegram config 로딩 제거

---

## 8. Scope Control Declaration

본 문서에 정의되지 않은 Feature / Story / Task는 다음 구현 Phase 범위에 포함되지 않는다.

**명시적 제외 항목**:
- Redis 캐싱 시스템 도입
- Kubernetes/Docker 배포 구성
- Web UI 개선
- ML 모델 추가/변경
- 새로운 기술 지표 추가
- 백테스트 시스템 확장

**향후 Phase 검토 대상**:
- Multi-broker support
- Cloud deployment
- Real-time dashboard enhancement

---

## Appendix A: Proposed CLI Commands

```bash
# Service Management
hantu start scheduler     # 통합 스케줄러 시작
hantu start api           # API 서버 시작
hantu start all           # 모든 서비스 시작
hantu stop scheduler      # 스케줄러 중지
hantu stop api            # API 서버 중지
hantu stop all            # 모든 서비스 중지
hantu status              # 전체 서비스 상태 확인
hantu status scheduler    # 특정 서비스 상태 확인

# Trading Operations
hantu trade start         # 자동 매매 시작
hantu trade stop          # 자동 매매 중지
hantu trade balance       # 잔고 조회
hantu trade positions     # 보유 종목 조회

# Screening & Selection
hantu screen              # Phase 1 스크리닝 실행
hantu screen --parallel 8 # 병렬 워커 수 지정
hantu select              # Phase 2 일일 선정 실행
hantu select --analyze    # 분석 모드

# Utilities
hantu logs                # 로그 확인
hantu logs -f             # 로그 실시간 확인
hantu config check        # 설정 검증
hantu health              # 시스템 헬스체크
```

---

## Appendix B: Current vs Target Execution Model

### Current (분산)
```bash
# Terminal 1
python workflows/integrated_scheduler.py

# Terminal 2
python api-server/main.py

# Terminal 3 (필요시)
python main.py trade
```

### Target (통합)
```bash
# Single command to start all
hantu start all

# Or individual services
hantu start scheduler
hantu start api

# Monitor
hantu status
```

---

**Document End**
