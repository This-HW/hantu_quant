# Technical Review & Next Phase Planning
## Learning System Post-Implementation Review

**Review Date**: 2026-01-10
**Review Scope**: core/learning/* (AI 학습 시스템)
**Document Version**: 1.0

---

## 1. Current State Summary

### 1.1 완료된 Feature / Story 목록

| Phase | Feature | Status | Location |
|-------|---------|--------|----------|
| Phase 4.A | 재학습 트리거 시스템 | ✅ 완료 | `core/learning/retrain/` |
| Phase 4.A | 모델 재학습 실행기 | ✅ 완료 | `core/learning/retrain/model_retrainer.py` |
| Phase 4.A | 재학습 히스토리 관리 | ✅ 완료 | `core/learning/retrain/retrain_history.py` |
| Phase 4.B | 동적 가중치 계산기 | ✅ 완료 | `core/learning/weights/` |
| Phase 4.B | 가중치 안전 장치 | ✅ 완료 | `core/learning/weights/weight_safety.py` |
| Phase 4.C | 레짐 탐지기 | ✅ 완료 | `core/learning/regime/regime_detector.py` |
| Phase 4.C | 레짐 전략 매퍼 | ✅ 완료 | `core/learning/regime/regime_strategy_mapper.py` |
| Phase 4.D | 학습 오케스트레이터 | ✅ 완료 | `core/learning/orchestrator/` |
| Phase 4.D | 학습 스케줄러 | ✅ 완료 | `core/learning/scheduler.py` |
| Phase 4.E | 피드백 시스템 | ✅ 완료 | `core/learning/models/feedback_system.py` |
| Phase 4.E | LSTM 예측기 | ✅ 완료 | `core/learning/models/lstm_predictor.py` |
| Phase 4.E | 패턴 학습기 | ✅ 완료 | `core/learning/models/pattern_learner.py` |

### 1.2 전체 아키텍처 개요

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        INTEGRATED SCHEDULER                                  │
│                   (workflows/integrated_scheduler.py)                        │
├─────────────────────────────────────────────────────────────────────────────┤
│  Daily 17:00    │  Daily 18:30        │  Fri 20:00      │  Sat 22:00        │
│  Performance    │  Adaptive Learning  │  Weekly Backtest│  Weekly Deep      │
│  Analysis       │                     │                 │  Learning         │
└────────┬────────┴─────────┬───────────┴────────┬────────┴─────────┬─────────┘
         │                  │                    │                  │
         ▼                  ▼                    ▼                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       LEARNING ORCHESTRATOR                                  │
│                (core/learning/orchestrator/learning_orchestrator.py)         │
├───────────────────┬───────────────────┬───────────────────┬─────────────────┤
│   Regime Check    │   Retrain Check   │  Weight Update    │ Performance Eval│
└────────┬──────────┴─────────┬─────────┴─────────┬─────────┴────────┬────────┘
         │                    │                   │                  │
         ▼                    ▼                   ▼                  ▼
┌────────────────┐  ┌─────────────────┐  ┌───────────────┐  ┌────────────────┐
│ RegimeDetector │  │ RetrainTrigger  │  │DynamicWeight  │  │ RetrainHistory │
│ RegimeMapper   │  │ ModelRetrainer  │  │Calculator     │  │                │
└────────────────┘  └─────────────────┘  └───────────────┘  └────────────────┘
         │                    │                   │
         └────────────────────┴───────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │ FeedbackSystem  │
                    │  (SQLite DB)    │
                    └─────────────────┘
```

### 1.3 변경 불가한 기술적 결정 사항

#### 언어 / 프레임워크
- **Python 3.9+**: 전체 프로젝트 언어
- **SQLite**: 피드백/성능 데이터 저장소 (단일 서버 운영)
- **PyTorch**: LSTM 모델 구현
- **scikit-learn**: 패턴 학습기 (RandomForest, XGBoost)
- **schedule**: 작업 스케줄링

#### 데이터 모델 (DB Schema)

**feedback_data 테이블** (`core/learning/models/feedback_system.py:91-108`):
```sql
CREATE TABLE feedback_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prediction_id TEXT UNIQUE NOT NULL,
    stock_code TEXT NOT NULL,
    prediction_date TEXT NOT NULL,
    predicted_probability REAL NOT NULL,
    predicted_class INTEGER NOT NULL,
    model_name TEXT NOT NULL,
    actual_return_7d REAL,
    actual_class INTEGER,
    prediction_error REAL,
    absolute_error REAL,
    feedback_date TEXT,
    is_processed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

#### 인터페이스 계약

**FeedbackData 클래스** (`feedback_system.py:22-48`):
```python
@dataclass
class FeedbackData:
    prediction_id: str
    stock_code: str
    prediction_date: str
    predicted_probability: float
    predicted_class: int
    model_name: str
    actual_return_7d: Optional[float] = None
    actual_class: Optional[int] = None
    prediction_error: Optional[float] = None
    absolute_error: Optional[float] = None
    feedback_date: Optional[str] = None
    is_processed: bool = False
```

**RetrainTrigger.should_retrain() 기대 입력** (`retrain_trigger.py`):
```python
def should_retrain(
    feedback_stats: Dict[str, Any],  # 'processed_feedback', 'new_feedback_since_last_train'
    model_performance: Dict[str, float]  # 'accuracy', 'win_rate', 'sharpe_ratio'
) -> TriggerResult
```

#### 외부 시스템 의존성
- **KIS API**: 실시간 주가/거래 데이터
- **pykrx**: 과거 주가 데이터
- **Telegram Bot API**: 알림 발송

### 1.4 기존 코드 및 구조와의 호환성 제약 사항

1. **싱글톤 패턴**: 모든 주요 컴포넌트가 싱글톤으로 구현됨
   - `get_feedback_system()`, `get_model_retrainer()`, `get_regime_detector()` 등
   - 변경 시 전역 상태 영향 고려 필요

2. **스케줄 의존성**: `integrated_scheduler.py`와 `scheduler.py` 이중 스케줄링
   - 두 파일 모두 수정 시 동기화 필요

3. **데이터 흐름 의존성**:
   - Phase 1/2 → FeedbackSystem → LearningOrchestrator → Weight/Model 업데이트
   - 파이프라인 중간 변경 시 하위 의존성 검증 필요

---

## 2. Open Issues & Gaps

### 2.1 확인된 버그 (Critical)

#### Bug-001: FeedbackSystem.get_recent_feedback() 컬럼명 불일치
**Location**: `core/learning/models/feedback_system.py:606-614`

```python
# 현재 코드 (잘못됨)
cursor.execute("""
    SELECT stock_code, prediction_date, predicted_value,
           actual_value, prediction_type, model_name, ...
""")

# 실제 DB 스키마
# predicted_value → predicted_probability
# actual_value → actual_return_7d
# prediction_type → 존재하지 않음
```

**영향**: SQL 오류로 피드백 조회 실패 → 가중치 업데이트/재학습 불가

---

#### Bug-002: LearningOrchestrator 피드백 데이터 접근 오류
**Location**: `core/learning/orchestrator/learning_orchestrator.py:281-287`

```python
# 현재 코드 (잘못됨)
for fb in recent_feedback:
    performance_data.append({
        'stock_code': fb.stock_code,        # fb는 dict, 속성 접근 불가
        'pnl_ratio': fb.actual_return or 0, # actual_return 키 없음
        'return': fb.actual_return or 0
    })
    factor_scores.append(fb.factor_scores or {})  # factor_scores 키 없음
```

**문제점**:
1. `get_recent_feedback()`은 `List[Dict]` 반환, 속성 접근(`.stock_code`) 불가
2. 반환 딕셔너리에 `actual_return`, `factor_scores` 키 없음

**영향**: 가중치 업데이트 시 AttributeError/KeyError 발생

---

#### Bug-003: RetrainTrigger에 전달되는 model_performance 불완전
**Location**: `core/learning/orchestrator/learning_orchestrator.py:333-346`

```python
# 현재 반환값
return {
    'accuracy': success_rate,
    'improvement': improvement,
    'recent_performance': success_rate
}
# 누락: 'win_rate', 'sharpe_ratio'
```

**영향**: RetrainTrigger가 `win_rate < 0.45` 또는 `sharpe_ratio < 0.5` 조건 체크 불가

---

### 2.2 미완료 Feature / Task

| ID | Feature/Task | Status | Priority |
|----|--------------|--------|----------|
| T-001 | factor_scores 저장/조회 기능 | 미구현 | High |
| T-002 | PipelineConnector Phase 1/2 통합 | 부분 구현 | High |
| T-003 | RL Agent (PPO) 실제 학습 연동 | 스텁만 존재 | Medium |
| T-004 | Bayesian Optimizer 활성화 | 코드 존재, 미연동 | Medium |

### 2.3 구조적 리스크

#### Risk-001: 이중 스케줄링 시스템
- `integrated_scheduler.py`: 토요일 22:00 주간 학습
- `scheduler.py`: 금요일 17:00 가중치 조정
- **문제**: 두 시스템 간 조율 없음, 중복 실행 또는 누락 가능

#### Risk-002: 스케줄 순서 역전
- 금요일 17:00: 가중치 조정 (먼저 실행)
- 금요일 20:00: 주간 백테스트 (나중 실행)
- **문제**: 백테스트 결과가 가중치 조정에 반영되지 않음

### 2.4 성능 병목 지점

| 위치 | 복잡도 | 병목 유형 | 설명 |
|------|--------|-----------|------|
| `feedback_system.py:371-458` | O(n) | I/O | 모델 평가 시 전체 피드백 스캔 |
| `model_retrainer.py:264-292` | O(n*m) | CPU | 가중치 결합 시 중복 샘플링 |
| `regime_detector.py` | O(API calls) | Network | 시장 지표 수집 시 다중 API 호출 |

---

## 3. Security & Compliance Review

### 3.1 신뢰 경계 식별

```
┌─────────────────────────────────────────────────────────────────┐
│                    Trust Boundary 1: External APIs              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │  KIS API    │  │   pykrx    │  │  Telegram   │              │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘              │
└─────────┼────────────────┼────────────────┼────────────────────┘
          │                │                │
          ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Trust Boundary 2: Application                │
│                                                                 │
│    [Feedback System] ──▶ [SQLite DB] ──▶ [Learning Modules]    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 보안 리스크

| 위치 | 리스크 | 심각도 | 현재 상태 |
|------|--------|--------|-----------|
| `feedback_system.py:606-614` | SQL Injection 가능성 | Low | 파라미터 바인딩 사용 중 ✅ |
| `model_retrainer.py:448-459` | Pickle 역직렬화 | Medium | 내부 데이터만 처리 (제한적 위험) |
| `scheduler.py` | 무한 루프 DoS | Low | daemon=True로 제한됨 ✅ |

### 3.3 로그 민감 정보 노출

| 파일 | 라인 | 위험 | 조치 필요 |
|------|------|------|-----------|
| `feedback_system.py:453` | 정확도 로깅 | None | - |
| `learning_orchestrator.py:378` | task_id 로깅 | None | - |

**평가**: 현재 로깅에서 민감 정보(API 키, 계좌 정보) 노출 없음

### 3.4 구조 변경 필요 보안 요구사항

**없음** - 현재 아키텍처 내에서 보안 요구사항 충족 가능

---

## 4. Performance & Efficiency Analysis

### 4.1 핵심 로직 복잡도

| 함수 | 시간 복잡도 | 공간 복잡도 | 호출 빈도 |
|------|-------------|-------------|-----------|
| `FeedbackSystem.evaluate_model_performance()` | O(n) | O(n) | Daily |
| `ModelRetrainer._weighted_data_combine()` | O(n+m) | O(n+m) | Weekly |
| `DynamicWeightCalculator.update_from_performance()` | O(n*f) | O(f) | Daily |
| `RegimeDetector.detect()` | O(1) | O(1) | Daily |

*n: 피드백 수, m: 새 데이터 수, f: 팩터 수 (7개 고정)*

### 4.2 병렬/비동기 처리 필요 여부

| 작업 | 현재 방식 | 권장 방식 | 이유 |
|------|-----------|-----------|------|
| 모델 재학습 | 동기 (background=False) | 비동기 | 학습 중 다른 작업 블로킹 |
| API 데이터 수집 | 순차 호출 | 병렬 호출 | 네트워크 대기 시간 감소 |
| 피드백 DB 쓰기 | 건별 INSERT | 배치 INSERT | I/O 감소 |

### 4.3 구조적 최적화 가능성

1. **피드백 조회 캐싱**: 동일 기간 다중 조회 시 캐싱 적용 가능
2. **모델 평가 배치화**: 일일 1회 전체 평가 대신 증분 평가 가능
3. **DB 인덱스 추가**: `prediction_date` + `is_processed` 복합 인덱스 권장

### 4.4 알고리즘 선택 기준 및 제약

| 선택 | 근거 | 제약 |
|------|------|------|
| LSTM 60일 시퀀스 | 한국 주식시장 분기 사이클 반영 | 메모리 제약으로 확장 어려움 |
| EMA α=0.3 | 최근 성과 30% 반영, 안정성 유지 | 급격한 시장 변화 대응 지연 |
| Holdout 20% | 표준 검증 비율 | 데이터 적을 시 검증 신뢰도 저하 |

---

## 5. Scope for Next Phase

### Feature 1: 피드백 시스템 데이터 일관성 수정

#### Story 1.1: get_recent_feedback() SQL 쿼리 수정

| Task | Description | Dependencies | Priority | Urgency | Expected Impact | Test Type | Security | Performance |
|------|-------------|--------------|----------|---------|-----------------|-----------|----------|-------------|
| 1.1.1 | `get_recent_feedback()` SELECT 컬럼명을 DB 스키마와 일치하도록 수정 | None | High | High | 부분 수정 | Story | None | None |
| 1.1.2 | 반환 딕셔너리 키를 `FeedbackData` 필드명과 일치시킴 | 1.1.1 | High | High | 부분 수정 | Story | None | None |
| 1.1.3 | 단위 테스트 작성: 피드백 조회 정상 동작 검증 | 1.1.2 | High | Medium | 유지 | Story | None | None |

#### Story 1.2: factor_scores 저장/조회 기능 추가

| Task | Description | Dependencies | Priority | Urgency | Expected Impact | Test Type | Security | Performance |
|------|-------------|--------------|----------|---------|-----------------|-----------|----------|-------------|
| 1.2.1 | `feedback_data` 테이블에 `factor_scores` TEXT 컬럼 추가 (JSON 직렬화) | 1.1 완료 | High | High | 구조 변경 | Integration | None | Minor |
| 1.2.2 | `record_predictions()`에 factor_scores 저장 로직 추가 | 1.2.1 | High | High | 부분 수정 | Story | None | None |
| 1.2.3 | `get_recent_feedback()`에서 factor_scores 역직렬화 추가 | 1.2.2 | High | High | 부분 수정 | Story | None | None |
| 1.2.4 | 마이그레이션 스크립트 작성 (기존 데이터 호환) | 1.2.1 | Medium | Medium | 유지 | Integration | None | None |

---

### Feature 2: 오케스트레이터 파라미터 전달 수정

#### Story 2.1: 피드백 데이터 접근 방식 수정

| Task | Description | Dependencies | Priority | Urgency | Expected Impact | Test Type | Security | Performance |
|------|-------------|--------------|----------|---------|-----------------|-----------|----------|-------------|
| 2.1.1 | `_run_weight_update_check()`에서 딕셔너리 키 접근으로 변경 (`fb['stock_code']`) | 1.1 완료 | High | High | 부분 수정 | Story | None | None |
| 2.1.2 | `actual_return` → `actual_return_7d` 키 이름 수정 | 2.1.1 | High | High | 부분 수정 | Story | None | None |
| 2.1.3 | factor_scores 기본값 처리 (`fb.get('factor_scores', {})`) | 1.2 완료 | High | High | 부분 수정 | Story | None | None |

#### Story 2.2: model_performance 반환값 보완

| Task | Description | Dependencies | Priority | Urgency | Expected Impact | Test Type | Security | Performance |
|------|-------------|--------------|----------|---------|-----------------|-----------|----------|-------------|
| 2.2.1 | `_get_model_performance()`에 `win_rate` 계산 및 반환 추가 | None | High | High | 부분 수정 | Story | None | None |
| 2.2.2 | `_get_model_performance()`에 `sharpe_ratio` 계산 및 반환 추가 | 2.2.1 | High | High | 부분 수정 | Story | None | Minor |
| 2.2.3 | RetrainTrigger 연동 테스트 작성 | 2.2.2 | High | Medium | 유지 | Integration | None | None |

---

### Feature 3: 스케줄 순서 최적화

#### Story 3.1: 금요일 스케줄 순서 조정

| Task | Description | Dependencies | Priority | Urgency | Expected Impact | Test Type | Security | Performance |
|------|-------------|--------------|----------|---------|-----------------|-----------|----------|-------------|
| 3.1.1 | `integrated_scheduler.py` 백테스트 시간을 16:00으로 변경 | None | Medium | Medium | 부분 수정 | Integration | None | None |
| 3.1.2 | 백테스트 → 가중치 조정 의존성 명시 (주석 추가) | 3.1.1 | Low | Low | 유지 | Story | None | None |

---

### Feature 4: 모델 재학습 데이터 형식 통일

#### Story 4.1: 학습 데이터 변환 계층 추가

| Task | Description | Dependencies | Priority | Urgency | Expected Impact | Test Type | Security | Performance |
|------|-------------|--------------|----------|---------|-----------------|-----------|----------|-------------|
| 4.1.1 | `_execute_model_retrain()`에 피드백→학습데이터 변환 함수 추가 | 1.1 완료 | High | Medium | 부분 수정 | Story | None | None |
| 4.1.2 | 변환 함수에서 `predicted_class`, `actual_class` 필드 매핑 | 4.1.1 | High | Medium | 부분 수정 | Story | None | None |
| 4.1.3 | ModelRetrainer 입력 검증 로직 추가 | 4.1.2 | Medium | Low | 부분 수정 | Story | None | None |

---

## 6. Execution Order

Priority × Urgency 기준 실행 순서:

| 순서 | Task ID | Task 설명 | Priority | Urgency | 비고 |
|------|---------|-----------|----------|---------|------|
| 1 | 1.1.1 | get_recent_feedback() SQL 컬럼명 수정 | High | High | 핵심 버그 수정 |
| 2 | 1.1.2 | 반환 딕셔너리 키 일치 | High | High | 1.1.1 의존 |
| 3 | 2.1.1 | 딕셔너리 키 접근 방식 수정 | High | High | 1.1 의존 |
| 4 | 2.1.2 | actual_return 키 이름 수정 | High | High | 2.1.1 의존 |
| 5 | 2.2.1 | win_rate 반환 추가 | High | High | 독립 작업 |
| 6 | 2.2.2 | sharpe_ratio 반환 추가 | High | High | 2.2.1 의존 |
| 7 | 1.2.1 | factor_scores 컬럼 추가 | High | High | DB 스키마 변경 |
| 8 | 1.2.2 | factor_scores 저장 로직 | High | High | 1.2.1 의존 |
| 9 | 1.2.3 | factor_scores 조회 로직 | High | High | 1.2.2 의존 |
| 10 | 2.1.3 | factor_scores 기본값 처리 | High | High | 1.2 의존 |
| 11 | 4.1.1 | 학습 데이터 변환 함수 | High | Medium | 1.1 의존 |
| 12 | 4.1.2 | 필드 매핑 구현 | High | Medium | 4.1.1 의존 |
| 13 | 1.1.3 | 피드백 조회 테스트 | High | Medium | 1.1.2 의존 |
| 14 | 2.2.3 | RetrainTrigger 연동 테스트 | High | Medium | 2.2.2 의존 |
| 15 | 1.2.4 | 마이그레이션 스크립트 | Medium | Medium | 1.2.1 의존 |
| 16 | 3.1.1 | 백테스트 시간 변경 | Medium | Medium | 독립 작업 |
| 17 | 4.1.3 | 입력 검증 로직 | Medium | Low | 4.1.2 의존 |
| 18 | 3.1.2 | 의존성 주석 추가 | Low | Low | 3.1.1 의존 |

---

## 7. Design & Impact Analysis (Top Priority Tasks)

### Task 1.1.1: get_recent_feedback() SQL 컬럼명 수정

#### 기존 아키텍처 유지 가능 여부
**가능** - SQL 쿼리 문자열만 수정, 메서드 시그니처 및 반환 타입 유지

#### 변경 범위
- **파일**: `core/learning/models/feedback_system.py`
- **라인**: 606-614
- **변경 내용**: SELECT 절의 `predicted_value` → `predicted_probability`, `actual_value` → `actual_return_7d`, `prediction_type` 제거

#### 기존 코드 호환성 영향
- 호출자(`LearningOrchestrator`)가 기대하는 딕셔너리 키가 변경됨
- Task 2.1.1, 2.1.2와 함께 적용 필수

#### 성능 영향
**None** - 쿼리 컬럼 수 동일

#### 확장성 영향
**None**

#### 운영/유지보수 영향
- DB 스키마와 코드 일치로 유지보수성 향상

---

### Task 1.2.1: factor_scores 컬럼 추가

#### 기존 아키텍처 유지 가능 여부
**부분 변경 필요** - DB 스키마 확장

#### 변경 범위
- **파일**: `core/learning/models/feedback_system.py`
- **라인**: 91-108 (테이블 생성)
- **변경 내용**: `factor_scores TEXT` 컬럼 추가

#### 기존 코드 호환성 영향
- 기존 데이터 유지됨 (ALTER TABLE ADD COLUMN)
- 기존 INSERT 문에 새 컬럼 추가 필요

#### 성능 영향
**Minor** - JSON 직렬화/역직렬화 오버헤드 (무시 가능 수준)

#### 확장성 영향
- 팩터 수 증가 시 JSON 크기 증가 (현재 7개 팩터, 약 200bytes)

#### 운영/유지보수 영향
- 마이그레이션 스크립트 실행 필요 (일회성)

---

### Task 2.2.1-2: win_rate, sharpe_ratio 반환 추가

#### 기존 아키텍처 유지 가능 여부
**가능** - 반환 딕셔너리에 키 추가

#### 변경 범위
- **파일**: `core/learning/orchestrator/learning_orchestrator.py`
- **라인**: 333-346
- **변경 내용**: RetrainHistory에서 win_rate 조회, 수익률 데이터로 sharpe_ratio 계산

#### 기존 코드 호환성 영향
- 반환 딕셔너리 확장, 기존 키 유지
- RetrainTrigger가 이미 해당 키 기대 중 (누락 시 기본값 사용)

#### 성능 영향
**Minor** - sharpe_ratio 계산 추가 (O(n), n=30일 데이터)

#### 확장성 영향
**None**

#### 운영/유지보수 영향
- 재학습 트리거 조건 정상 동작으로 시스템 안정성 향상

---

## 8. Scope Control Declaration

**본 문서에 정의되지 않은 Feature / Story / Task는 다음 구현 Phase 범위에 포함되지 않는다.**

### 명시적 범위 외 항목

| 항목 | 상태 | 이유 |
|------|------|------|
| RL Agent (PPO) 학습 연동 | 범위 외 | 현재 Phase는 버그 수정 우선 |
| Bayesian Optimizer 활성화 | 범위 외 | 기본 학습 파이프라인 안정화 후 진행 |
| 새로운 팩터 추가 | 범위 외 | 기존 7개 팩터 유지 |
| 분산 학습 인프라 | 범위 외 | 현재 단일 서버 구조 유지 |
| LSTM 아키텍처 변경 | 범위 외 | 검증된 현재 구조 유지 |

---

## Appendix: 파일 참조 맵

| 파일 경로 | 주요 클래스/함수 | 관련 Task |
|-----------|------------------|-----------|
| `core/learning/models/feedback_system.py` | `FeedbackSystem.get_recent_feedback()` | 1.1.1, 1.1.2, 1.2.3 |
| `core/learning/models/feedback_system.py` | `FeedbackSystem.record_predictions()` | 1.2.2 |
| `core/learning/models/feedback_system.py` | `_init_database()` | 1.2.1 |
| `core/learning/orchestrator/learning_orchestrator.py` | `_run_weight_update_check()` | 2.1.1, 2.1.2, 2.1.3 |
| `core/learning/orchestrator/learning_orchestrator.py` | `_get_model_performance()` | 2.2.1, 2.2.2 |
| `core/learning/orchestrator/learning_orchestrator.py` | `_execute_model_retrain()` | 4.1.1, 4.1.2 |
| `workflows/integrated_scheduler.py` | `_run_weekly_backtest()` | 3.1.1 |
| `core/learning/retrain/model_retrainer.py` | `ModelRetrainer.retrain()` | 4.1.3 |
