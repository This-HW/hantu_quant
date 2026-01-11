# Technical Review & Next Phase Planning
## PostgreSQL 통합 마이그레이션

**문서 버전**: 1.0
**작성일**: 2026-01-11
**상태**: Post-Implementation Review

---

## 1. Current State Summary

### 1.1 완료된 Feature/Story 목록

| Feature | Status | Description |
|---------|--------|-------------|
| F-DB-001 | ✅ 완료 | 통합 SQLAlchemy 모델 정의 (`models.py`) |
| F-DB-002 | ✅ 완료 | 통합 DB 유틸리티 생성 (`unified_db.py`) |
| F-DB-003 | ✅ 완료 | FeedbackSystem PostgreSQL 연동 |
| F-DATA-001 | ✅ 완료 | Phase 2→3 데이터 흐름 수정 (predicted_class, model_name) |
| F-DATA-002 | ✅ 완료 | Phase 3→4 데이터 흐름 수정 (TradeHistory 필드 추가) |
| F-SCHED-001 | ✅ 완료 | 대량 작업 주말 스케줄링 |

### 1.2 전체 아키텍처 개요

```
┌─────────────────────────────────────────────────────────────────┐
│                    데이터베이스 레이어                            │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────────┐     ┌──────────────────────────────────┐  │
│  │ 메인 DB (통합)     │     │ 분산 SQLite DBs (마이그레이션 대상) │  │
│  │ PostgreSQL/SQLite │     │                                  │  │
│  │                   │     │ ├── notification_history.db     │  │
│  │ ├── stocks        │     │ ├── system_alerts.db            │  │
│  │ ├── prices        │     │ ├── learning_data.db            │  │
│  │ ├── trades        │     │ ├── error_recovery.db           │  │
│  │ ├── watchlist     │     │ ├── api_tracking.db             │  │
│  │ ├── daily_select  │     │ ├── performance_tracking.db     │  │
│  │ ├── trade_history │     │ ├── accuracy_tracking.db        │  │
│  │ ├── feedback_data │     │ ├── strategy_performance.db     │  │
│  │ └── (8개 신규)     │     │ └── model_performance.db        │  │
│  └──────────────────┘     └──────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 1.3 변경 불가한 기술적 결정 사항

| 항목 | 결정 사항 | 근거 |
|------|----------|------|
| **언어** | Python 3.9+ | 기존 코드베이스 |
| **ORM** | SQLAlchemy 2.0 | `core/database/session.py` |
| **DB 연결** | DATABASE_URL 환경변수 | `core/config/settings.py` |
| **폴백 전략** | PostgreSQL → SQLite | 운영 안정성 |
| **JSON 직렬화** | json.dumps/loads | 기존 패턴 |

### 1.4 호환성 제약 사항

1. **기존 SQLite 데이터 유지**: 마이그레이션 후에도 기존 SQLite 파일 접근 가능해야 함
2. **API 호환성**: 기존 CRUD 메서드 시그니처 유지
3. **스케줄러 호환성**: 기존 스케줄러 호출 인터페이스 유지
4. **로깅 형식**: `exc_info=True` 패턴 유지

---

## 2. Open Issues & Gaps

### 2.1 미완료 Feature/Story/Task

| ID | Type | Description | 영향도 |
|----|------|-------------|--------|
| F-DB-004 | Feature | 11개 SQLite 모듈 PostgreSQL 마이그레이션 | High |
| F-DB-005 | Feature | 데이터 마이그레이션 스크립트 | High |
| F-DB-006 | Feature | 통합 DB 트랜잭션 관리 | Medium |
| S-SYNC-001 | Story | DataSynchronizer PostgreSQL 연동 | High |
| S-ALERT-001 | Story | AlertManager PostgreSQL 연동 | Medium |
| S-NOTIF-001 | Story | NotificationHistory PostgreSQL 연동 | Medium |

### 2.2 확인된 기술적 부채

| ID | 부채 유형 | 설명 | 우선순위 |
|----|----------|------|----------|
| TD-001 | 데이터 타입 | TEXT로 저장된 날짜 (YYYYMMDD) | High |
| TD-002 | JSON 저장 | TEXT 필드에 JSON 직렬화 | Medium |
| TD-003 | 트랜잭션 | INSERT OR REPLACE 남용 | High |
| TD-004 | 연결 관리 | 모듈별 독립적 sqlite3.connect | High |
| TD-005 | 인덱스 부재 | 일부 테이블 인덱스 누락 | Medium |
| TD-006 | FK 미사용 | 외래키 제약조건 미적용 | Low |

### 2.3 구조적 리스크

1. **분산 DB 불일치**: 11개 SQLite 파일 간 데이터 정합성 보장 안됨
2. **동시성 문제**: SQLite 동시 쓰기 제한
3. **백업 분산**: 개별 .db 파일 백업 필요

### 2.4 성능 병목 지점

| 위치 | 병목 유형 | 영향 |
|------|----------|------|
| `DataSynchronizer.sync_*` | I/O | JSON 파일 읽기 + DB 쓰기 |
| `AccuracyTracker._analyze_*` | CPU | pandas read_sql + numpy polyfit |
| `StrategyReporter._calculate_*` | Memory | 대량 데이터 pandas DataFrame |
| `APICallTracker.record_*` | I/O | 고빈도 비동기 쓰기 |
| `EnhancedAdaptiveSystem.analyze_*` | I/O | 복합 JOIN 쿼리 |

---

## 3. Security & Compliance Review

### 3.1 신뢰 경계 식별

```
┌─────────────────────────────────────────────────────────────┐
│ Trust Boundary 1: 외부 API                                   │
│ ├── KIS API (한국투자증권)                                    │
│ └── Telegram API                                             │
├─────────────────────────────────────────────────────────────┤
│ Trust Boundary 2: 데이터베이스                                │
│ ├── PostgreSQL (DATABASE_URL)                                │
│ └── SQLite 로컬 파일                                          │
├─────────────────────────────────────────────────────────────┤
│ Trust Boundary 3: 파일 시스템                                 │
│ ├── data/watchlist/*.json                                    │
│ └── data/daily_selection/*.json                              │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 데이터 흐름 기준 보안 리스크

| 데이터 흐름 | 리스크 | 현재 상태 | 권장 조치 |
|------------|--------|----------|----------|
| JSON → DB | SQL Injection | 파라미터 바인딩 사용 | 유지 |
| DB → 로그 | 민감정보 노출 | `exc_info=True` 사용 | 스택트레이스 필터링 필요 |
| API 응답 → DB | 데이터 변조 | 검증 없음 | 입력 검증 추가 |
| DB 연결 문자열 | 자격증명 노출 | 환경변수 사용 | 유지 |

### 3.3 인증/인가 모델

- **DB 접근**: DATABASE_URL 환경변수 기반 인증
- **API 접근**: APP_KEY, APP_SECRET 환경변수
- **내부 모듈 간**: 인증 없음 (신뢰된 환경 가정)

### 3.4 입력 검증 현황

| 모듈 | 입력 검증 | 상태 |
|------|----------|------|
| FeedbackSystem | prediction_id 형식 검증 없음 | 추가 필요 |
| DataSynchronizer | JSON 스키마 검증 없음 | 추가 필요 |
| AccuracyTracker | 날짜 형식 검증 없음 | 추가 필요 |

### 3.5 보안 원칙 적용 가능성

| 원칙 | 적용 가능성 | 구조 변경 필요 |
|------|------------|---------------|
| 파라미터 바인딩 | ✅ 이미 적용 | No |
| 연결 풀링 | ✅ PostgreSQL에서 적용 | No |
| 최소 권한 | ⚠️ DB 사용자 권한 분리 필요 | No |
| 감사 로깅 | ⚠️ CRUD 작업 로깅 필요 | No |

---

## 4. Performance & Efficiency Analysis

### 4.1 핵심 로직 복잡도

| 함수 | 시간 복잡도 | 공간 복잡도 | 비고 |
|------|------------|------------|------|
| `sync_screening_results` | O(n) | O(n) | n = 종목 수 |
| `analyze_screening_accuracy` | O(n*m) | O(n*m) | JOIN 비용 |
| `_calculate_strategy_performance` | O(n*d) | O(n*d) | d = 거래일 수 |
| `get_api_statistics` | O(n) | O(1) | 집계 쿼리 |
| `record_api_call` (async) | O(1) | O(1) | 비동기 삽입 |

### 4.2 병렬/비동기 처리 현황

| 모듈 | 현재 방식 | 권장 변경 |
|------|----------|----------|
| APICallTracker | threading.Thread | asyncio 또는 유지 |
| DataSynchronizer | 동기 처리 | bulk_insert 적용 |
| AccuracyTracker | pandas 순차 처리 | 유지 (데이터 양 적음) |

### 4.3 구조적 최적화 가능성

| 최적화 유형 | 적용 대상 | 예상 효과 |
|------------|----------|----------|
| **배치 처리** | sync_screening_results | 50% 성능 향상 |
| **캐싱** | get_model_accuracy | 반복 쿼리 제거 |
| **인덱스** | api_calls.timestamp | 조회 성능 10x |
| **파티셔닝** | daily_strategy_returns | 대량 데이터 관리 |
| **JSONB** | TEXT JSON 필드 → JSONB | 쿼리 성능 향상 |

### 4.4 비효율 지점

1. **DataSynchronizer**: 매번 전체 JSON 파일 파싱
2. **EnhancedAdaptiveSystem**: N+1 쿼리 패턴 가능성
3. **PerformanceTracker**: 비교 분석 시 전체 데이터 로드

---

## 5. Scope for Next Phase

### Feature 1: SQLite 모듈 PostgreSQL 마이그레이션 (F-PG-001)

#### Story 1.1: 핵심 학습 모듈 마이그레이션 (S-PG-001)

| Task ID | Description | Dependencies | Priority | Urgency | Expected Impact | Test Type | Security | Performance |
|---------|-------------|--------------|----------|---------|-----------------|-----------|----------|-------------|
| T-001 | DataSynchronizer 통합 DB 연동 | unified_db.py | High | High | 구조 변경 | Integration | None | Significant |
| T-002 | EnhancedAdaptiveSystem 통합 DB 연동 | T-001 | High | High | 부분 수정 | Integration | None | Minor |
| T-003 | PerformanceTracker 통합 DB 연동 | unified_db.py | High | Medium | 구조 변경 | Integration | None | Significant |
| T-004 | AccuracyTracker 통합 DB 연동 | unified_db.py | High | Medium | 구조 변경 | Integration | None | Minor |
| T-005 | StrategyReporter 통합 DB 연동 | unified_db.py | Medium | Medium | 구조 변경 | Integration | None | Significant |

#### Story 1.2: 모니터링 모듈 마이그레이션 (S-PG-002)

| Task ID | Description | Dependencies | Priority | Urgency | Expected Impact | Test Type | Security | Performance |
|---------|-------------|--------------|----------|---------|-----------------|-----------|----------|-------------|
| T-006 | ModelPerformanceMonitor 통합 DB 연동 | unified_db.py | High | Medium | 구조 변경 | Integration | None | Minor |
| T-007 | NotificationHistoryDB 통합 DB 연동 | unified_db.py | Medium | Low | 부분 수정 | Feature | None | None |
| T-008 | SystemAlertManager 통합 DB 연동 | unified_db.py | Medium | Low | 부분 수정 | Feature | None | None |
| T-009 | APICallTracker 통합 DB 연동 | unified_db.py | Medium | Low | 구조 변경 | Integration | None | Significant |

#### Story 1.3: 복원력 모듈 마이그레이션 (S-PG-003)

| Task ID | Description | Dependencies | Priority | Urgency | Expected Impact | Test Type | Security | Performance |
|---------|-------------|--------------|----------|---------|-----------------|-----------|----------|-------------|
| T-010 | RecoveryManager 통합 DB 연동 | unified_db.py | Medium | Medium | 부분 수정 | Feature | Review Required | None |
| T-011 | AccuracyAnalyzer 통합 DB 연동 | T-001 | Low | Low | 부분 수정 | Feature | None | None |

### Feature 2: 데이터 마이그레이션 (F-PG-002)

#### Story 2.1: 마이그레이션 도구 개발 (S-MIG-001)

| Task ID | Description | Dependencies | Priority | Urgency | Expected Impact | Test Type | Security | Performance |
|---------|-------------|--------------|----------|---------|-----------------|-----------|----------|-------------|
| T-012 | 마이그레이션 스크립트 개발 | T-001~T-011 | High | Medium | 유지 | Integration | None | Significant |
| T-013 | 데이터 검증 도구 개발 | T-012 | High | Medium | 유지 | Integration | None | None |
| T-014 | 롤백 스크립트 개발 | T-012 | Medium | High | 유지 | Feature | None | None |

### Feature 3: SQLAlchemy 모델 확장 (F-PG-003)

#### Story 3.1: 누락 모델 추가 (S-MODEL-001)

| Task ID | Description | Dependencies | Priority | Urgency | Expected Impact | Test Type | Security | Performance |
|---------|-------------|--------------|----------|---------|-----------------|-----------|----------|-------------|
| T-015 | APICall 모델 추가 | None | High | High | 유지 | Feature | None | None |
| T-016 | ErrorEvent 모델 추가 | None | Medium | Medium | 유지 | Feature | None | None |
| T-017 | RecoveryRule 모델 추가 | None | Medium | Medium | 유지 | Feature | None | None |
| T-018 | StrategyPerformance 모델 추가 | None | High | Medium | 유지 | Feature | None | None |
| T-019 | MarketRegime 모델 추가 | None | Medium | Low | 유지 | Feature | None | None |
| T-020 | BacktestPrediction 모델 추가 | None | High | Medium | 유지 | Feature | None | None |
| T-021 | ActualPerformance 모델 추가 | T-020 | High | Medium | 유지 | Feature | None | None |

---

## 6. Execution Order

**Priority × Urgency 기준 실행 순서:**

| 순서 | Task ID | Description | Priority | Urgency | 비고 |
|------|---------|-------------|----------|---------|------|
| 1 | T-015 | APICall 모델 추가 | High | High | 모델 먼저 |
| 2 | T-018 | StrategyPerformance 모델 추가 | High | Medium | 모델 먼저 |
| 3 | T-020 | BacktestPrediction 모델 추가 | High | Medium | 모델 먼저 |
| 4 | T-021 | ActualPerformance 모델 추가 | High | Medium | T-020 의존 |
| 5 | T-001 | DataSynchronizer 통합 DB 연동 | High | High | 핵심 모듈 |
| 6 | T-002 | EnhancedAdaptiveSystem 통합 DB 연동 | High | High | T-001 의존 |
| 7 | T-003 | PerformanceTracker 통합 DB 연동 | High | Medium | |
| 8 | T-006 | ModelPerformanceMonitor 통합 DB 연동 | High | Medium | |
| 9 | T-004 | AccuracyTracker 통합 DB 연동 | High | Medium | |
| 10 | T-014 | 롤백 스크립트 개발 | Medium | High | 안전장치 |
| 11 | T-016 | ErrorEvent 모델 추가 | Medium | Medium | |
| 12 | T-017 | RecoveryRule 모델 추가 | Medium | Medium | |
| 13 | T-010 | RecoveryManager 통합 DB 연동 | Medium | Medium | 보안 검토 |
| 14 | T-005 | StrategyReporter 통합 DB 연동 | Medium | Medium | |
| 15 | T-019 | MarketRegime 모델 추가 | Medium | Low | |
| 16 | T-007 | NotificationHistoryDB 통합 DB 연동 | Medium | Low | |
| 17 | T-008 | SystemAlertManager 통합 DB 연동 | Medium | Low | |
| 18 | T-009 | APICallTracker 통합 DB 연동 | Medium | Low | 성능 중요 |
| 19 | T-011 | AccuracyAnalyzer 통합 DB 연동 | Low | Low | |
| 20 | T-012 | 마이그레이션 스크립트 개발 | High | Medium | 마지막 |
| 21 | T-013 | 데이터 검증 도구 개발 | High | Medium | 마지막 |

---

## 7. Design & Impact Analysis (Top Priority Tasks)

### T-001: DataSynchronizer 통합 DB 연동

**현재 구현:**
```python
class DataSynchronizer:
    def __init__(self, db_path: str = "data/learning/learning_data.db"):
        self.db_path = db_path
        with sqlite3.connect(self.db_path) as conn:
            # CREATE TABLE ...
```

**변경 필요 사항:**
- `sqlite3.connect` → `core.database.unified_db.get_session`
- `INSERT OR REPLACE` → SQLAlchemy upsert 패턴
- 4개 테이블 모델 추가 필요: `screening_history`, `selection_history`, `performance_tracking`, `learning_metrics`

**기존 아키텍처 유지 가능 여부:** ✅ 가능 (FeedbackSystem 패턴 적용)

**호환성 영향:**
- 메서드 시그니처 유지
- 반환 타입 유지
- 폴백 로직 추가

**성능 영향:**
- bulk_insert 적용 시 50% 향상 예상
- 커넥션 풀링으로 연결 오버헤드 감소

**확장성 영향:**
- PostgreSQL 복제 지원 가능
- 수평 확장 용이

---

### T-002: EnhancedAdaptiveSystem 통합 DB 연동

**현재 구현:**
- DataSynchronizer의 `learning_data.db` 읽기 전용 접근
- 복잡한 JOIN 쿼리 사용

**변경 필요 사항:**
- `sqlite3.connect` → 통합 세션 사용
- pandas `read_sql_query` → SQLAlchemy 쿼리 또는 유지

**기존 아키텍처 유지 가능 여부:** ✅ 가능

**호환성 영향:** 최소 (읽기 전용)

**성능 영향:** PostgreSQL 인덱스 활용 시 향상

---

### T-009: APICallTracker 통합 DB 연동

**현재 구현:**
```python
def _save_to_db(self, call_data):
    def save_task():
        with sqlite3.connect(self._db_path) as conn:
            cursor.execute("INSERT INTO api_calls ...")
    threading.Thread(target=save_task).start()
```

**변경 필요 사항:**
- 비동기 패턴 유지하되 연결 풀 사용
- threading → asyncio 고려 (선택적)

**기존 아키텍처 유지 가능 여부:** ⚠️ 부분 변경 필요

**성능 영향:**
- 고빈도 쓰기 → 배치 처리 또는 큐 도입 권장
- PostgreSQL 비동기 드라이버 (asyncpg) 고려

---

## 8. Scope Control Declaration

**본 문서에 정의되지 않은 Feature/Story/Task는 다음 구현 Phase 범위에 포함되지 않는다.**

### 제외 항목 (명시적)
- WatchlistManager JSON → DB 마이그레이션 (별도 Phase)
- DailyUpdater JSON → DB 마이그레이션 (별도 Phase)
- Redis 캐시 레이어 도입
- 분산 데이터베이스 구성
- 실시간 데이터 스트리밍

### 포함 조건
- 모든 Task는 위 테이블에 명시된 것만 포함
- 추가 Task 발생 시 본 문서 업데이트 후 승인 필요

---

## Appendix A: 현재 SQLite 테이블 목록

| DB 파일 | 테이블명 | 마이그레이션 대상 |
|---------|---------|-----------------|
| notification_history.db | notification_history | ✅ |
| notification_history.db | notification_stats | ✅ |
| system_alerts.db | system_alerts | ✅ |
| system_alerts.db | alert_settings | ✅ |
| system_alerts.db | alert_statistics | ✅ |
| learning_data.db | screening_history | ✅ |
| learning_data.db | selection_history | ✅ |
| learning_data.db | performance_tracking | ✅ (중복 주의) |
| learning_data.db | learning_metrics | ✅ |
| error_recovery.db | error_events | ✅ |
| error_recovery.db | recovery_rules | ✅ |
| api_tracking.db | api_calls | ✅ |
| performance_tracking.db | backtest_predictions | ✅ |
| performance_tracking.db | actual_performance | ✅ |
| performance_tracking.db | performance_comparisons | ✅ |
| performance_tracking.db | daily_tracking | ✅ |
| accuracy_tracking.db | daily_selections | ✅ (중복 주의) |
| accuracy_tracking.db | performance_tracking | ✅ (중복 주의) |
| accuracy_tracking.db | daily_accuracy | ✅ |
| strategy_performance.db | strategy_performance | ✅ |
| strategy_performance.db | strategy_comparisons | ✅ |
| strategy_performance.db | market_regimes | ✅ |
| strategy_performance.db | daily_strategy_returns | ✅ |
| model_performance.db | model_performance | ✅ |
| model_performance.db | performance_alerts | ✅ |
| model_performance.db | model_baselines | ✅ |

**총 마이그레이션 대상 테이블: 26개**

---

## Appendix B: 중복 테이블 통합 방안

| 중복 테이블 | 출처 | 통합 방안 |
|------------|------|----------|
| `performance_tracking` | learning_data.db, accuracy_tracking.db | 단일 테이블로 통합, 타입 컬럼 추가 |
| `daily_selections` | accuracy_tracking.db, models.py | models.py의 DailySelection 활용 |

---
