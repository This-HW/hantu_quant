# Technical Review & Next Phase Planning
## Adaptive Learning System (자동 학습 및 시류 반영 시스템)

**문서 버전**: 1.0.0
**작성일**: 2024-12-29
**Phase**: Post-Implementation Technical Review & Next Phase Planning

---

## 1. Current State Summary

### 1.1 완료된 Feature / Story 목록

| Phase | Feature | 상태 | 위치 |
|-------|---------|------|------|
| Phase 1 | 감시리스트 스크리닝 | ✅ 완료 | `workflows/phase1_watchlist.py` |
| Phase 2 | 일일 종목 선정 | ✅ 완료 | `workflows/phase2_daily_selection.py` |
| Phase 3 | 자동 매매 실행 | ✅ 완료 | `core/trading/` |
| Phase 4 | AI 학습 기반 구조 | ⚠️ 부분 완료 | `core/learning/` |
| - | LSTM 예측 모델 | ✅ 완료 | `core/learning/models/lstm_predictor.py` |
| - | PPO 강화학습 에이전트 | ✅ 완료 | `core/learning/rl/ppo_agent.py` |
| - | 베이지안 최적화 프레임워크 | ✅ 완료 | `core/learning/optimization/bayesian_optimizer.py` |
| - | 피드백 수집 시스템 | ✅ 완료 | `core/learning/models/feedback_system.py` |
| - | 적응형 학습 시스템 | ⚠️ 부분 완료 | `core/learning/adaptive_learning_system.py` |
| - | 시장 상황별 기준 정의 | ⚠️ 부분 완료 | `core/daily_selection/selection_criteria.py` |

### 1.2 전체 아키텍처 개요

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Hantu Quant Architecture                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                  │
│  │   Phase 1   │───▶│   Phase 2   │───▶│   Phase 3   │                  │
│  │  Watchlist  │    │  Selection  │    │   Trading   │                  │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘                  │
│         │                  │                  │                          │
│         ▼                  ▼                  ▼                          │
│  ┌─────────────────────────────────────────────────────────────┐        │
│  │                    Database Layer                            │        │
│  │  stocks | prices | watchlist_stocks | daily_selections      │        │
│  │  trades | trade_history | indicators                         │        │
│  └─────────────────────────────────────────────────────────────┘        │
│         │                  │                  │                          │
│         └──────────────────┼──────────────────┘                          │
│                            ▼                                             │
│  ┌─────────────────────────────────────────────────────────────┐        │
│  │                   Phase 4: Learning Layer                    │        │
│  │  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐    │        │
│  │  │ FeedbackSystem│  │AdaptiveLearning│  │ Optimization  │    │        │
│  │  │   (수집)      │  │    (조정)      │  │   (최적화)    │    │        │
│  │  └───────┬───────┘  └───────┬───────┘  └───────┬───────┘    │        │
│  │          │                  │                  │             │        │
│  │          └──────────────────┴──────────────────┘             │        │
│  │                            │                                  │        │
│  │                            ▼                                  │        │
│  │          ┌─────────────────────────────────────┐             │        │
│  │          │   ❌ 연결 끊김: 자동 파이프라인 부재  │             │        │
│  │          └─────────────────────────────────────┘             │        │
│  └─────────────────────────────────────────────────────────────┘        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.3 변경 불가한 기술적 결정 사항

| 항목 | 확정된 결정 | 근거 |
|------|------------|------|
| **언어** | Python 3.9+ | 기존 코드베이스 전체 |
| **ORM** | SQLAlchemy | `core/database/models.py` 전체 구조 |
| **데이터베이스 스키마** | Stock, Price, Trade, WatchlistStock, DailySelection, TradeHistory | 기존 테이블 구조 변경 시 마이그레이션 필요 |
| **스코어링 인터페이스** | `FactorScores` dataclass, `MultiFactorScorer` 클래스 | `core/scoring/multi_factor_scorer.py` |
| **피드백 인터페이스** | `FeedbackData` dataclass, `FeedbackSystem` 클래스 | `core/learning/models/feedback_system.py` |
| **적응 파라미터 구조** | `AlgorithmParams` dataclass | `core/learning/adaptive_learning_system.py` |
| **시장 상황 Enum** | `MarketCondition` (BULL, BEAR, SIDEWAYS, VOLATILE, RECOVERY) | `core/daily_selection/selection_criteria.py` |
| **외부 의존성** | KIS API, PyTorch (선택), scikit-learn (선택), numpy, pandas | requirements.txt |

### 1.4 기존 코드 및 구조와의 호환성 제약

| 제약 사항 | 영향 범위 | 대응 방안 |
|----------|----------|----------|
| `factor_weights` 딕셔너리 구조 | `MultiFactorScorer` 전체 | 기존 딕셔너리 키 유지, 동적 업데이트 레이어 추가 |
| `FeedbackSystem` 재학습 조건 | 피드백 DB 스키마 | 기존 테이블 유지, 새 컬럼/테이블 추가 |
| `AlgorithmParams` 필드 | 파라미터 저장/로드 로직 | 기존 필드 유지, 새 필드 추가 |
| `MarketCondition` enum | 시장 판단 로직 전체 | 기존 값 유지, 판단 로직만 강화 |
| JSON 기반 설정 저장 | `data/learning/*.json` | 기존 포맷 호환, 새 키 추가 |

---

## 2. Open Issues & Gaps

### 2.1 미완료 Feature / Story / Task

| 구분 | 항목 | 현재 상태 | 영향도 |
|------|------|----------|--------|
| **Feature** | 자동 재학습 파이프라인 | 미구현 | Critical |
| **Feature** | 동적 가중치 학습 시스템 | 미구현 | Critical |
| **Feature** | 시장 레짐 자동 탐지 | 부분 구현 (enum만 존재) | High |
| **Feature** | 전체 학습 루프 통합 | 미구현 | Critical |
| **Story** | 피드백 → 모델 재학습 자동화 | 미구현 | Critical |
| **Story** | 성과 기반 가중치 자동 조정 | 미구현 | Critical |
| **Story** | 시장 지표 기반 레짐 판단 | 미구현 | High |
| **Task** | 재학습 스케줄러 구현 | 미구현 | High |
| **Task** | 가중치 최적화 알고리즘 | 미구현 | High |
| **Task** | 레짐 탐지 지표 계산 | 미구현 | Medium |

### 2.2 확인된 기술적 부채

| 부채 항목 | 위치 | 심각도 | 설명 |
|----------|------|--------|------|
| 하드코딩된 가중치 | `multi_factor_scorer.py:62-70` | High | 7개 팩터 가중치가 상수로 정의됨 |
| 재학습 트리거 미자동화 | `feedback_system.py:487-527` | High | `check_retrain_needed()` 호출 후 실제 재학습 연결 없음 |
| 휴리스틱 기반 파라미터 조정 | `adaptive_learning_system.py:262-332` | Medium | 고정 규칙 기반, 학습 미적용 |
| 시장 상황 수동 지정 | `selection_criteria.py:506-515` | Medium | `get_criteria()` 호출 시 외부에서 상황 전달 필요 |
| 분산된 데이터 저장소 | 여러 JSON 파일 + DB | Low | `data/learning/`, `data/trades/` 등 분산 |

### 2.3 구조적 리스크

| 리스크 | 발생 가능성 | 영향도 | 완화 방안 |
|--------|------------|--------|----------|
| 재학습 시 서비스 중단 | Medium | High | 백그라운드 학습 + 모델 핫스왑 |
| 가중치 발산 | Low | Critical | 가중치 범위 제한, 변경률 제한 |
| 시장 레짐 오판 | Medium | High | 다중 지표 확인, 확신도 임계값 |
| 과적합 | Medium | Medium | 홀드아웃 검증, 조기 종료 |

### 2.4 성능 병목 지점

| 병목 | 복잡도 | 영향 | 최적화 방안 |
|------|--------|------|------------|
| 피드백 수집 쿼리 | O(n) | 대량 데이터 시 지연 | 인덱스 추가, 배치 처리 |
| 가중치 최적화 (Bayesian) | O(n²) | 파라미터 수 증가 시 | 차원 축소, 조기 종료 |
| 시장 지표 계산 | O(k) per indicator | 지표 수 증가 시 | 캐싱, 증분 계산 |
| 모델 재학습 | O(epoch × data) | 학습 시간 | GPU 활용, 점진적 학습 |

---

## 3. Security & Compliance Review

### 3.1 신뢰 경계 (Trust Boundary) 식별

```
┌──────────────────────────────────────────────────────────────┐
│                    Trust Boundary 1: 외부                     │
│  ┌─────────────┐                                              │
│  │   KIS API   │ ◀─── API Key 인증 필요                       │
│  └──────┬──────┘                                              │
├─────────┼────────────────────────────────────────────────────┤
│         ▼                                                     │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │              Trust Boundary 2: 시스템 내부               │ │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐               │ │
│  │  │ Learning │  │ Scoring  │  │ Trading  │               │ │
│  │  │  System  │  │  System  │  │  System  │               │ │
│  │  └─────┬────┘  └─────┬────┘  └─────┬────┘               │ │
│  │        └─────────────┼─────────────┘                     │ │
│  │                      ▼                                    │ │
│  │  ┌──────────────────────────────────────────┐            │ │
│  │  │           Database / File Storage         │            │ │
│  │  │  (피드백 DB, 가중치 파일, 파라미터 파일)   │            │ │
│  │  └──────────────────────────────────────────┘            │ │
│  └──────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

### 3.2 데이터 흐름 기준 보안 리스크

| 데이터 흐름 | 리스크 | 현재 상태 | 권장 조치 |
|------------|--------|----------|----------|
| 가중치 파일 저장/로드 | 파일 변조 | 무검증 로드 | 체크섬 검증 추가 |
| 파라미터 JSON 저장 | 악성 JSON 인젝션 | 기본 json.load | 스키마 검증 추가 |
| 피드백 DB 쓰기 | SQL 인젝션 | SQLAlchemy ORM 사용 (안전) | 현재 상태 유지 |
| 모델 파일 로드 | 악성 pickle | PyTorch save/load | torch.load에 weights_only=True 권장 |

### 3.3 입력 검증 필요 지점

| 입력 지점 | 현재 검증 | 추가 필요 |
|----------|----------|----------|
| 가중치 값 범위 | 없음 | 0.0 - 1.0 범위 검증, 합계 1.0 검증 |
| 파라미터 값 범위 | 부분적 | 각 파라미터별 min/max 검증 |
| 시장 레짐 판단 입력 | 없음 | 지표 값 유효성 검증 |
| 피드백 데이터 | 기본 타입 체크 | 범위 검증, 이상치 탐지 |

### 3.4 로그 및 에러 처리 시 민감 정보 노출 위험

| 위치 | 현재 상태 | 리스크 | 조치 |
|------|----------|--------|------|
| `adaptive_learning_system.py` | 파라미터 값 로깅 | Low (내부 데이터) | 민감 필드 마스킹 |
| `feedback_system.py` | 예측 결과 로깅 | Low | 현재 상태 유지 |
| 오류 스택 트레이스 | 전체 출력 | Medium | 프로덕션에서 요약만 출력 |

---

## 4. Performance & Efficiency Analysis

### 4.1 핵심 로직 시간/공간 복잡도

| 로직 | 시간 복잡도 | 공간 복잡도 | 비고 |
|------|------------|------------|------|
| 가중치 로드 | O(1) | O(k) | k = 팩터 수 (7) |
| 멀티팩터 스코어 계산 | O(n × k) | O(n × k) | n = 종목 수 |
| Z-score 정규화 | O(n) | O(n) | numpy 벡터화 |
| 피드백 수집 쿼리 | O(n) | O(n) | n = 피드백 수 |
| 베이지안 최적화 1회 | O(m²) | O(m) | m = 샘플 수 |
| 시장 레짐 판단 | O(d) | O(d) | d = 지표 수 |

### 4.2 병렬 처리 필요 여부

| 작업 | 병렬화 가능 | 권장 방식 | 예상 개선 |
|------|------------|----------|----------|
| 종목별 스코어 계산 | ✅ | `concurrent.futures.ThreadPoolExecutor` | 2-4x |
| 피드백 배치 수집 | ✅ | DB 배치 쿼리 | 3-5x |
| 모델 재학습 | ✅ | GPU 활용 또는 백그라운드 프로세스 | 5-10x |
| 시장 지표 계산 | ⚠️ | 종목별 병렬 가능, 지표간 의존성 주의 | 2x |

### 4.3 캐싱 전략

| 대상 | 캐시 유형 | TTL | 무효화 조건 |
|------|----------|-----|------------|
| 현재 가중치 | 메모리 (싱글톤) | 세션 | 재학습 완료 시 |
| 시장 레짐 | 메모리 | 1시간 | 장중 지표 급변 시 |
| 피드백 통계 | 메모리 | 1일 | 일일 배치 완료 시 |
| 파라미터 설정 | 파일 + 메모리 | 영구 | 적응 완료 시 |

### 4.4 알고리즘 선택 기준

| 목적 | 선택된 알고리즘 | 대안 | 선택 근거 |
|------|----------------|------|----------|
| 가중치 최적화 | Bayesian Optimization | Grid Search, Random Search | 적은 샘플로 수렴, 기존 구현 존재 |
| 시장 레짐 탐지 | 규칙 기반 + Hidden Markov Model | k-means, SVM | 해석 가능성, 상태 전이 모델링 |
| 가중치 업데이트 | Exponential Moving Average | 단순 평균, 학습률 감쇠 | 최근 데이터 중시, 안정성 |

---

## 5. Scope for Next Phase

### Feature A: 자동 재학습 파이프라인

#### Story A.1: 재학습 트리거 시스템

| Task | Description | Dependencies | Priority | Urgency | Expected Impact | Test Type | Security Impact | Performance Impact |
|------|-------------|--------------|----------|---------|-----------------|-----------|-----------------|-------------------|
| A.1.1 | `RetrainTrigger` 클래스 생성: 재학습 조건 평가 및 트리거 | FeedbackSystem | High | High | 신규 추가 | Unit | None | Minor |
| A.1.2 | 재학습 조건 정의: 피드백 수, 정확도 하락, 시간 기반 | A.1.1 | High | High | 신규 추가 | Unit | None | None |
| A.1.3 | 재학습 스케줄러 통합: 일일/주간 체크 | A.1.1, A.1.2 | High | Medium | 부분 수정 (scheduler.py) | Integration | None | Minor |

#### Story A.2: 모델 재학습 실행기

| Task | Description | Dependencies | Priority | Urgency | Expected Impact | Test Type | Security Impact | Performance Impact |
|------|-------------|--------------|----------|---------|-----------------|-----------|-----------------|-------------------|
| A.2.1 | `ModelRetrainer` 클래스 생성: 백그라운드 재학습 실행 | RetrainTrigger | High | High | 신규 추가 | Unit | None | Significant |
| A.2.2 | 점진적 학습 (Incremental Learning) 구현 | A.2.1 | Medium | Medium | 신규 추가 | Unit | None | Minor |
| A.2.3 | 모델 검증 로직: 홀드아웃 검증, 성능 비교 | A.2.1 | High | High | 신규 추가 | Unit | None | Minor |
| A.2.4 | 모델 핫스왑: 서비스 중단 없이 모델 교체 | A.2.3 | High | Medium | 신규 추가 | Integration | Review Required | Minor |

#### Story A.3: 재학습 모니터링

| Task | Description | Dependencies | Priority | Urgency | Expected Impact | Test Type | Security Impact | Performance Impact |
|------|-------------|--------------|----------|---------|-----------------|-----------|-----------------|-------------------|
| A.3.1 | 재학습 이력 저장 테이블/파일 구조 | - | Medium | Medium | 신규 추가 | Unit | None | None |
| A.3.2 | 재학습 알림 (Telegram 연동) | A.3.1 | Low | Low | 부분 수정 | Integration | None | None |

---

### Feature B: 동적 가중치 시스템

#### Story B.1: 성과 기반 가중치 계산기

| Task | Description | Dependencies | Priority | Urgency | Expected Impact | Test Type | Security Impact | Performance Impact |
|------|-------------|--------------|----------|---------|-----------------|-----------|-----------------|-------------------|
| B.1.1 | `DynamicWeightCalculator` 클래스 생성 | FeedbackSystem | High | High | 신규 추가 | Unit | None | Minor |
| B.1.2 | 팩터별 기여도 분석 로직: 과거 N일 성과 기반 | B.1.1 | High | High | 신규 추가 | Unit | None | Minor |
| B.1.3 | 가중치 최적화 알고리즘: EMA 기반 업데이트 | B.1.2 | High | High | 신규 추가 | Unit | None | Minor |
| B.1.4 | 가중치 범위 제한 및 정규화 (합계 1.0) | B.1.3 | High | High | 신규 추가 | Unit | Review Required | None |

#### Story B.2: 가중치 저장 및 로드

| Task | Description | Dependencies | Priority | Urgency | Expected Impact | Test Type | Security Impact | Performance Impact |
|------|-------------|--------------|----------|---------|-----------------|-----------|-----------------|-------------------|
| B.2.1 | 가중치 버전 관리 시스템 | B.1.4 | Medium | Medium | 신규 추가 | Unit | None | None |
| B.2.2 | 가중치 파일 무결성 검증 (체크섬) | B.2.1 | Medium | Medium | 신규 추가 | Unit | Review Required | None |
| B.2.3 | `MultiFactorScorer` 동적 가중치 적용 수정 | B.2.1 | High | High | 구조 변경 | Integration | None | None |

#### Story B.3: 가중치 롤백 및 안전장치

| Task | Description | Dependencies | Priority | Urgency | Expected Impact | Test Type | Security Impact | Performance Impact |
|------|-------------|--------------|----------|---------|-----------------|-----------|-----------------|-------------------|
| B.3.1 | 가중치 변경 이력 관리 | B.2.1 | Medium | Medium | 신규 추가 | Unit | None | None |
| B.3.2 | 가중치 롤백 기능 | B.3.1 | Medium | Low | 신규 추가 | Unit | None | None |
| B.3.3 | 급격한 변동 방지 (변경률 제한) | B.1.3 | High | High | 신규 추가 | Unit | None | None |

---

### Feature C: 시장 레짐 탐지

#### Story C.1: 시장 지표 수집기

| Task | Description | Dependencies | Priority | Urgency | Expected Impact | Test Type | Security Impact | Performance Impact |
|------|-------------|--------------|----------|---------|-----------------|-----------|-----------------|-------------------|
| C.1.1 | `MarketIndicatorCollector` 클래스 생성 | KIS API | High | High | 신규 추가 | Unit | None | Minor |
| C.1.2 | 주요 지수 데이터 수집 (KOSPI, KOSDAQ) | C.1.1 | High | High | 신규 추가 | Integration | None | Minor |
| C.1.3 | 시장 폭 지표 계산 (등락주 비율, 신고가/신저가) | C.1.2 | Medium | Medium | 신규 추가 | Unit | None | Minor |
| C.1.4 | 변동성 지표 계산 (VIX 대용, 평균 변동성) | C.1.2 | Medium | Medium | 신규 추가 | Unit | None | Minor |

#### Story C.2: 레짐 판단 엔진

| Task | Description | Dependencies | Priority | Urgency | Expected Impact | Test Type | Security Impact | Performance Impact |
|------|-------------|--------------|----------|---------|-----------------|-----------|-----------------|-------------------|
| C.2.1 | `RegimeDetector` 클래스 생성 | C.1 전체 | High | High | 신규 추가 | Unit | None | Minor |
| C.2.2 | 규칙 기반 레짐 판단 로직 | C.2.1 | High | High | 신규 추가 | Unit | None | None |
| C.2.3 | 레짐 확신도 점수 계산 | C.2.2 | Medium | Medium | 신규 추가 | Unit | None | None |
| C.2.4 | 레짐 전환 감지 및 알림 | C.2.3 | Medium | Low | 신규 추가 | Integration | None | None |

#### Story C.3: 레짐별 전략 자동 전환

| Task | Description | Dependencies | Priority | Urgency | Expected Impact | Test Type | Security Impact | Performance Impact |
|------|-------------|--------------|----------|---------|-----------------|-----------|-----------------|-------------------|
| C.3.1 | `SelectionCriteriaManager` 자동 전환 통합 | C.2, SelectionCriteria | High | Medium | 구조 변경 | Integration | None | None |
| C.3.2 | 레짐별 가중치 프리셋 정의 | C.3.1, Feature B | Medium | Medium | 신규 추가 | Unit | None | None |

---

### Feature D: 전체 통합

#### Story D.1: 학습 파이프라인 오케스트레이터

| Task | Description | Dependencies | Priority | Urgency | Expected Impact | Test Type | Security Impact | Performance Impact |
|------|-------------|--------------|----------|---------|-----------------|-----------|-----------------|-------------------|
| D.1.1 | `LearningOrchestrator` 클래스 생성 | Feature A, B, C | High | Medium | 신규 추가 | Integration | None | Minor |
| D.1.2 | 일일 학습 루프 구현 | D.1.1 | High | Medium | 신규 추가 | Integration | None | Minor |
| D.1.3 | 주간 심층 분석 루프 구현 | D.1.2 | Medium | Low | 신규 추가 | Integration | None | Minor |

#### Story D.2: 데이터 흐름 통합

| Task | Description | Dependencies | Priority | Urgency | Expected Impact | Test Type | Security Impact | Performance Impact |
|------|-------------|--------------|----------|---------|-----------------|-----------|-----------------|-------------------|
| D.2.1 | 피드백 → 가중치 → 스코어링 파이프라인 연결 | Feature A, B | High | High | 구조 변경 | Integration | None | Minor |
| D.2.2 | 레짐 → 기준 → 선정 파이프라인 연결 | Feature C | High | Medium | 구조 변경 | Integration | None | None |

#### Story D.3: 통합 모니터링

| Task | Description | Dependencies | Priority | Urgency | Expected Impact | Test Type | Security Impact | Performance Impact |
|------|-------------|--------------|----------|---------|-----------------|-----------|-----------------|-------------------|
| D.3.1 | 학습 시스템 대시보드 메트릭 추가 | D.1, D.2 | Low | Low | 부분 수정 | Unit | None | None |
| D.3.2 | 일일 학습 리포트 생성 | D.3.1 | Low | Low | 신규 추가 | Unit | None | None |

---

## 6. Execution Order

다음 순서는 Priority × Urgency 기준이며, 보안/성능 영향이 큰 작업은 상위로 배치됨.

| 순서 | Task ID | Task 설명 | 우선순위 | 긴급도 | 비고 |
|------|---------|----------|---------|--------|------|
| 1 | B.1.4 | 가중치 범위 제한 및 정규화 | High | High | 보안 검토 필요 |
| 2 | B.3.3 | 급격한 변동 방지 (변경률 제한) | High | High | 시스템 안정성 |
| 3 | A.1.1 | RetrainTrigger 클래스 생성 | High | High | 핵심 기능 |
| 4 | A.1.2 | 재학습 조건 정의 | High | High | A.1.1 의존 |
| 5 | B.1.1 | DynamicWeightCalculator 클래스 생성 | High | High | 핵심 기능 |
| 6 | B.1.2 | 팩터별 기여도 분석 로직 | High | High | B.1.1 의존 |
| 7 | B.1.3 | 가중치 최적화 알고리즘 (EMA) | High | High | B.1.2 의존 |
| 8 | A.2.1 | ModelRetrainer 클래스 생성 | High | High | 성능 영향 |
| 9 | A.2.3 | 모델 검증 로직 | High | High | 품질 보증 |
| 10 | C.1.1 | MarketIndicatorCollector 클래스 생성 | High | High | - |
| 11 | C.1.2 | 주요 지수 데이터 수집 | High | High | C.1.1 의존 |
| 12 | C.2.1 | RegimeDetector 클래스 생성 | High | High | - |
| 13 | C.2.2 | 규칙 기반 레짐 판단 로직 | High | High | C.2.1 의존 |
| 14 | B.2.3 | MultiFactorScorer 동적 가중치 적용 | High | High | 구조 변경 |
| 15 | A.1.3 | 재학습 스케줄러 통합 | High | Medium | - |
| 16 | A.2.4 | 모델 핫스왑 | High | Medium | 보안 검토 필요 |
| 17 | C.3.1 | SelectionCriteriaManager 자동 전환 통합 | High | Medium | - |
| 18 | D.1.1 | LearningOrchestrator 클래스 생성 | High | Medium | 전체 통합 |
| 19 | D.2.1 | 피드백 → 가중치 → 스코어링 연결 | High | High | - |
| 20 | D.2.2 | 레짐 → 기준 → 선정 연결 | High | Medium | - |
| 21 | B.2.1 | 가중치 버전 관리 시스템 | Medium | Medium | - |
| 22 | B.2.2 | 가중치 파일 무결성 검증 | Medium | Medium | 보안 검토 필요 |
| 23 | A.2.2 | 점진적 학습 구현 | Medium | Medium | - |
| 24 | C.1.3 | 시장 폭 지표 계산 | Medium | Medium | - |
| 25 | C.1.4 | 변동성 지표 계산 | Medium | Medium | - |
| 26 | C.2.3 | 레짐 확신도 점수 계산 | Medium | Medium | - |
| 27 | C.3.2 | 레짐별 가중치 프리셋 정의 | Medium | Medium | - |
| 28 | B.3.1 | 가중치 변경 이력 관리 | Medium | Medium | - |
| 29 | A.3.1 | 재학습 이력 저장 구조 | Medium | Medium | - |
| 30 | D.1.2 | 일일 학습 루프 구현 | High | Medium | - |
| 31 | D.1.3 | 주간 심층 분석 루프 구현 | Medium | Low | - |
| 32 | C.2.4 | 레짐 전환 감지 및 알림 | Medium | Low | - |
| 33 | B.3.2 | 가중치 롤백 기능 | Medium | Low | - |
| 34 | A.3.2 | 재학습 알림 (Telegram) | Low | Low | - |
| 35 | D.3.1 | 대시보드 메트릭 추가 | Low | Low | - |
| 36 | D.3.2 | 일일 학습 리포트 생성 | Low | Low | - |

---

## 7. Design & Impact Analysis (Top Priority Tasks)

### Task B.1.4: 가중치 범위 제한 및 정규화

**기존 아키텍처 유지 가능 여부**: ✅ 유지 가능

**설계 방안**:
```python
# DynamicWeightCalculator 내부
def normalize_weights(self, weights: Dict[str, float]) -> Dict[str, float]:
    """가중치 정규화 및 범위 제한"""
    MIN_WEIGHT = 0.05  # 최소 5%
    MAX_WEIGHT = 0.40  # 최대 40%

    # 범위 제한
    clamped = {k: max(MIN_WEIGHT, min(MAX_WEIGHT, v)) for k, v in weights.items()}

    # 합계 1.0 정규화
    total = sum(clamped.values())
    return {k: v / total for k, v in clamped.items()}
```

**기존 코드 영향**:
- `MultiFactorScorer.factor_weights` 직접 수정 안 함
- 새로운 레이어에서 동적 가중치 제공

**성능 영향**: 없음 (O(k) 상수 시간)

**확장성 영향**: 팩터 추가 시 자동 대응

---

### Task A.1.1: RetrainTrigger 클래스 생성

**기존 아키텍처 유지 가능 여부**: ✅ 유지 가능

**설계 방안**:
```python
# core/learning/retrain/retrain_trigger.py
class RetrainTrigger:
    def __init__(self, feedback_system: FeedbackSystem):
        self._feedback_system = feedback_system
        self._config = RetrainConfig()

    def should_retrain(self) -> Tuple[bool, List[str]]:
        """재학습 필요 여부 판단"""
        reasons = []

        # 1. 피드백 수 체크
        summary = self._feedback_system.get_feedback_summary(30)
        if summary['processed_feedback'] >= self._config.min_feedback_count:
            reasons.append('sufficient_feedback')

        # 2. 정확도 하락 체크
        performance = self._feedback_system.evaluate_model_performance()
        if performance.get('accuracy', 1.0) < self._config.accuracy_threshold:
            reasons.append('accuracy_drop')

        # 3. 시간 기반 체크
        if self._days_since_last_train() > self._config.max_days_without_retrain:
            reasons.append('time_based')

        return len(reasons) > 0, reasons
```

**기존 코드 영향**:
- `FeedbackSystem` 그대로 사용 (의존성만 주입)
- `check_retrain_needed()` 메서드 대체 또는 래핑

**성능 영향**: Minor (피드백 쿼리 1회)

---

### Task C.2.2: 규칙 기반 레짐 판단 로직

**기존 아키텍처 유지 가능 여부**: ✅ 유지 가능

**설계 방안**:
```python
# core/learning/regime/regime_detector.py
class RegimeDetector:
    def detect_regime(self, indicators: MarketIndicators) -> Tuple[MarketCondition, float]:
        """시장 레짐 판단 및 확신도 반환"""

        # 규칙 기반 점수 계산
        scores = {
            MarketCondition.BULL_MARKET: self._calculate_bull_score(indicators),
            MarketCondition.BEAR_MARKET: self._calculate_bear_score(indicators),
            MarketCondition.SIDEWAYS: self._calculate_sideways_score(indicators),
            MarketCondition.VOLATILE: self._calculate_volatile_score(indicators),
            MarketCondition.RECOVERY: self._calculate_recovery_score(indicators),
        }

        # 최고 점수 레짐 선택
        best_regime = max(scores, key=scores.get)
        confidence = scores[best_regime] / sum(scores.values())

        return best_regime, confidence

    def _calculate_bull_score(self, ind: MarketIndicators) -> float:
        score = 0.0
        if ind.kospi_20d_return > 0.05: score += 30  # 20일 수익률 > 5%
        if ind.advance_decline_ratio > 1.5: score += 25  # 등락비 > 1.5
        if ind.above_ma200_ratio > 0.6: score += 25  # 200일선 위 종목 > 60%
        if ind.new_high_low_ratio > 2: score += 20  # 신고가/신저가 비율 > 2
        return score
```

**기존 코드 영향**:
- `MarketCondition` enum 그대로 사용
- `SelectionCriteriaManager.get_criteria()` 호출 시 자동 판단 결과 전달

**성능 영향**: Minor (지표 계산 O(k))

---

### Task B.2.3: MultiFactorScorer 동적 가중치 적용

**기존 아키텍처 유지 가능 여부**: ⚠️ 부분 수정 필요

**변경 범위**:
- `MultiFactorScorer.__init__()`: 가중치 소스 주입
- `calculate_multi_factor_scores()`: 동적 가중치 사용

**설계 방안**:
```python
class MultiFactorScorer:
    def __init__(self, weight_provider: Optional[WeightProvider] = None):
        self._weight_provider = weight_provider

        # 기본 가중치 (폴백용)
        self._default_weights = {
            'momentum': 0.20,
            'value': 0.15,
            'quality': 0.20,
            'volume': 0.15,
            'volatility': 0.10,
            'technical': 0.15,
            'market_strength': 0.05
        }

    @property
    def factor_weights(self) -> Dict[str, float]:
        if self._weight_provider:
            return self._weight_provider.get_weights()
        return self._default_weights
```

**호환성 영향**:
- 기존 `MultiFactorScorer()` 호출 시 기본 가중치 사용 (하위 호환)
- 새로운 `MultiFactorScorer(weight_provider)` 호출 시 동적 가중치 사용

**성능 영향**: 없음

---

## 8. Scope Control Declaration

**본 문서에 정의되지 않은 Feature / Story / Task는 다음 구현 Phase 범위에 포함되지 않는다.**

포함되지 않는 항목 예시:
- 새로운 ML 모델 아키텍처 개발 (LSTM 외)
- 실시간 학습 (Online Learning)
- 분산 학습 시스템
- 외부 데이터 소스 통합 (뉴스, SNS)
- UI/대시보드 전면 개편

---

## 부록: 파일 구조 예상

```
core/learning/
├── retrain/                      # Feature A
│   ├── __init__.py
│   ├── retrain_trigger.py        # A.1.1, A.1.2
│   ├── model_retrainer.py        # A.2.1, A.2.2, A.2.3
│   ├── model_swapper.py          # A.2.4
│   └── retrain_history.py        # A.3.1
│
├── weights/                      # Feature B
│   ├── __init__.py
│   ├── dynamic_weight_calculator.py  # B.1.1 ~ B.1.4
│   ├── weight_provider.py        # B.2.3 인터페이스
│   ├── weight_storage.py         # B.2.1, B.2.2
│   └── weight_safety.py          # B.3.1 ~ B.3.3
│
├── regime/                       # Feature C
│   ├── __init__.py
│   ├── market_indicator_collector.py  # C.1.1 ~ C.1.4
│   ├── regime_detector.py        # C.2.1 ~ C.2.4
│   └── regime_strategy_mapper.py # C.3.1, C.3.2
│
└── orchestrator/                 # Feature D
    ├── __init__.py
    ├── learning_orchestrator.py  # D.1.1 ~ D.1.3
    ├── pipeline_connector.py     # D.2.1, D.2.2
    └── learning_reporter.py      # D.3.1, D.3.2
```

---

**문서 끝**
