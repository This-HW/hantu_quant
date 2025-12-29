# Implementation Phase Checklist
## Adaptive Learning System (자동 학습 및 시류 반영 시스템)

**문서 버전**: 1.0.0
**작성일**: 2024-12-29
**관련 설계 문서**: `05_ADAPTIVE_LEARNING_SYSTEM_DESIGN.md`

---

## 사용법

- [ ] 미완료
- [x] 완료
- [~] 부분 완료 / 진행 중
- [!] 블로커 / 이슈 발생

---

## Feature A: 자동 재학습 파이프라인

### Story A.1: 재학습 트리거 시스템

#### 구현

| 상태 | Task | 설명 | 파일 |
|------|------|------|------|
| [ ] | A.1.1 | `RetrainTrigger` 클래스 생성 | `core/learning/retrain/retrain_trigger.py` |
| [ ] | A.1.2 | 재학습 조건 정의 (피드백 수, 정확도, 시간) | `core/learning/retrain/retrain_trigger.py` |
| [ ] | A.1.3 | 재학습 스케줄러 통합 | `core/learning/scheduler.py` 수정 |

#### 테스트

| 상태 | 테스트 유형 | 설명 |
|------|------------|------|
| [ ] | Unit | `RetrainTrigger.should_retrain()` 조건별 테스트 |
| [ ] | Unit | 피드백 수 임계값 테스트 |
| [ ] | Unit | 정확도 하락 임계값 테스트 |
| [ ] | Integration | 스케줄러 연동 테스트 |

---

### Story A.2: 모델 재학습 실행기

#### 구현

| 상태 | Task | 설명 | 파일 |
|------|------|------|------|
| [ ] | A.2.1 | `ModelRetrainer` 클래스 생성 | `core/learning/retrain/model_retrainer.py` |
| [ ] | A.2.2 | 점진적 학습 (Incremental Learning) 구현 | `core/learning/retrain/model_retrainer.py` |
| [ ] | A.2.3 | 모델 검증 로직 (홀드아웃, 성능 비교) | `core/learning/retrain/model_retrainer.py` |
| [ ] | A.2.4 | 모델 핫스왑 구현 | `core/learning/retrain/model_swapper.py` |

#### 테스트

| 상태 | 테스트 유형 | 설명 |
|------|------------|------|
| [ ] | Unit | `ModelRetrainer.train()` 정상 동작 |
| [ ] | Unit | 점진적 학습 데이터 추가 테스트 |
| [ ] | Unit | 모델 검증 통과/실패 시나리오 |
| [ ] | Integration | 모델 핫스왑 서비스 중단 없음 확인 |

#### 보안 검토

| 상태 | 항목 |
|------|------|
| [ ] | A.2.4: 모델 파일 로드 시 `weights_only=True` 사용 |
| [ ] | A.2.4: 모델 파일 경로 검증 (path traversal 방지) |

---

### Story A.3: 재학습 모니터링

#### 구현

| 상태 | Task | 설명 | 파일 |
|------|------|------|------|
| [ ] | A.3.1 | 재학습 이력 저장 구조 | `core/learning/retrain/retrain_history.py` |
| [ ] | A.3.2 | 재학습 알림 (Telegram) | `core/learning/retrain/retrain_history.py` |

#### 테스트

| 상태 | 테스트 유형 | 설명 |
|------|------------|------|
| [ ] | Unit | 이력 저장/조회 테스트 |
| [ ] | Integration | Telegram 알림 발송 테스트 |

---

## Feature B: 동적 가중치 시스템

### Story B.1: 성과 기반 가중치 계산기

#### 구현

| 상태 | Task | 설명 | 파일 |
|------|------|------|------|
| [ ] | B.1.1 | `DynamicWeightCalculator` 클래스 생성 | `core/learning/weights/dynamic_weight_calculator.py` |
| [ ] | B.1.2 | 팩터별 기여도 분석 로직 | `core/learning/weights/dynamic_weight_calculator.py` |
| [ ] | B.1.3 | 가중치 최적화 알고리즘 (EMA) | `core/learning/weights/dynamic_weight_calculator.py` |
| [ ] | B.1.4 | 가중치 범위 제한 및 정규화 | `core/learning/weights/dynamic_weight_calculator.py` |

#### 테스트

| 상태 | 테스트 유형 | 설명 |
|------|------------|------|
| [ ] | Unit | 기여도 분석 정확성 |
| [ ] | Unit | EMA 업데이트 수렴 테스트 |
| [ ] | Unit | 가중치 범위 제한 (0.05 ~ 0.40) |
| [ ] | Unit | 가중치 합계 1.0 정규화 |

#### 보안 검토

| 상태 | 항목 |
|------|------|
| [ ] | B.1.4: 가중치 값 입력 검증 (NaN, Inf 방지) |
| [ ] | B.1.4: 외부 입력으로 가중치 조작 불가 확인 |

---

### Story B.2: 가중치 저장 및 로드

#### 구현

| 상태 | Task | 설명 | 파일 |
|------|------|------|------|
| [ ] | B.2.1 | 가중치 버전 관리 시스템 | `core/learning/weights/weight_storage.py` |
| [ ] | B.2.2 | 가중치 파일 무결성 검증 (체크섬) | `core/learning/weights/weight_storage.py` |
| [ ] | B.2.3 | `MultiFactorScorer` 동적 가중치 적용 | `core/scoring/multi_factor_scorer.py` 수정 |

#### 테스트

| 상태 | 테스트 유형 | 설명 |
|------|------------|------|
| [ ] | Unit | 버전 관리 저장/로드 |
| [ ] | Unit | 체크섬 검증 성공/실패 시나리오 |
| [ ] | Integration | `MultiFactorScorer` 동적 가중치 적용 확인 |
| [ ] | Integration | 기존 호출 방식 하위 호환성 확인 |

#### 보안 검토

| 상태 | 항목 |
|------|------|
| [ ] | B.2.2: SHA-256 이상 해시 알고리즘 사용 |
| [ ] | B.2.2: 체크섬 불일치 시 기본 가중치 폴백 |

---

### Story B.3: 가중치 롤백 및 안전장치

#### 구현

| 상태 | Task | 설명 | 파일 |
|------|------|------|------|
| [ ] | B.3.1 | 가중치 변경 이력 관리 | `core/learning/weights/weight_safety.py` |
| [ ] | B.3.2 | 가중치 롤백 기능 | `core/learning/weights/weight_safety.py` |
| [ ] | B.3.3 | 급격한 변동 방지 (변경률 제한) | `core/learning/weights/weight_safety.py` |

#### 테스트

| 상태 | 테스트 유형 | 설명 |
|------|------------|------|
| [ ] | Unit | 이력 저장/조회 |
| [ ] | Unit | 롤백 기능 정상 동작 |
| [ ] | Unit | 변경률 제한 (예: 1회 최대 ±5%) |

---

## Feature C: 시장 레짐 탐지

### Story C.1: 시장 지표 수집기

#### 구현

| 상태 | Task | 설명 | 파일 |
|------|------|------|------|
| [ ] | C.1.1 | `MarketIndicatorCollector` 클래스 생성 | `core/learning/regime/market_indicator_collector.py` |
| [ ] | C.1.2 | 주요 지수 데이터 수집 (KOSPI, KOSDAQ) | `core/learning/regime/market_indicator_collector.py` |
| [ ] | C.1.3 | 시장 폭 지표 계산 | `core/learning/regime/market_indicator_collector.py` |
| [ ] | C.1.4 | 변동성 지표 계산 | `core/learning/regime/market_indicator_collector.py` |

#### 테스트

| 상태 | 테스트 유형 | 설명 |
|------|------------|------|
| [ ] | Unit | 지표 계산 정확성 |
| [ ] | Integration | KIS API 연동 테스트 |
| [ ] | Unit | API 실패 시 폴백 처리 |

---

### Story C.2: 레짐 판단 엔진

#### 구현

| 상태 | Task | 설명 | 파일 |
|------|------|------|------|
| [ ] | C.2.1 | `RegimeDetector` 클래스 생성 | `core/learning/regime/regime_detector.py` |
| [ ] | C.2.2 | 규칙 기반 레짐 판단 로직 | `core/learning/regime/regime_detector.py` |
| [ ] | C.2.3 | 레짐 확신도 점수 계산 | `core/learning/regime/regime_detector.py` |
| [ ] | C.2.4 | 레짐 전환 감지 및 알림 | `core/learning/regime/regime_detector.py` |

#### 테스트

| 상태 | 테스트 유형 | 설명 |
|------|------------|------|
| [ ] | Unit | 각 레짐별 판단 로직 (BULL, BEAR, SIDEWAYS, VOLATILE, RECOVERY) |
| [ ] | Unit | 확신도 점수 범위 (0.0 ~ 1.0) |
| [ ] | Unit | 레짐 전환 감지 테스트 |
| [ ] | Integration | 알림 발송 테스트 |

---

### Story C.3: 레짐별 전략 자동 전환

#### 구현

| 상태 | Task | 설명 | 파일 |
|------|------|------|------|
| [ ] | C.3.1 | `SelectionCriteriaManager` 자동 전환 통합 | `core/daily_selection/selection_criteria.py` 수정 |
| [ ] | C.3.2 | 레짐별 가중치 프리셋 정의 | `core/learning/regime/regime_strategy_mapper.py` |

#### 테스트

| 상태 | 테스트 유형 | 설명 |
|------|------------|------|
| [ ] | Integration | 레짐 변경 시 기준 자동 전환 |
| [ ] | Unit | 프리셋별 가중치 정합성 |

---

## Feature D: 전체 통합

### Story D.1: 학습 파이프라인 오케스트레이터

#### 구현

| 상태 | Task | 설명 | 파일 |
|------|------|------|------|
| [ ] | D.1.1 | `LearningOrchestrator` 클래스 생성 | `core/learning/orchestrator/learning_orchestrator.py` |
| [ ] | D.1.2 | 일일 학습 루프 구현 | `core/learning/orchestrator/learning_orchestrator.py` |
| [ ] | D.1.3 | 주간 심층 분석 루프 구현 | `core/learning/orchestrator/learning_orchestrator.py` |

#### 테스트

| 상태 | 테스트 유형 | 설명 |
|------|------------|------|
| [ ] | Integration | 일일 루프 전체 흐름 |
| [ ] | Integration | 주간 루프 전체 흐름 |
| [ ] | Unit | 각 컴포넌트 호출 순서 |

---

### Story D.2: 데이터 흐름 통합

#### 구현

| 상태 | Task | 설명 | 파일 |
|------|------|------|------|
| [ ] | D.2.1 | 피드백 → 가중치 → 스코어링 연결 | `core/learning/orchestrator/pipeline_connector.py` |
| [ ] | D.2.2 | 레짐 → 기준 → 선정 연결 | `core/learning/orchestrator/pipeline_connector.py` |

#### 테스트

| 상태 | 테스트 유형 | 설명 |
|------|------------|------|
| [ ] | Integration | 피드백 수집 → 가중치 업데이트 → 스코어 반영 E2E |
| [ ] | Integration | 레짐 탐지 → 기준 전환 → 선정 결과 반영 E2E |

---

### Story D.3: 통합 모니터링

#### 구현

| 상태 | Task | 설명 | 파일 |
|------|------|------|------|
| [ ] | D.3.1 | 학습 시스템 대시보드 메트릭 | `core/learning/orchestrator/learning_reporter.py` |
| [ ] | D.3.2 | 일일 학습 리포트 생성 | `core/learning/orchestrator/learning_reporter.py` |

#### 테스트

| 상태 | 테스트 유형 | 설명 |
|------|------------|------|
| [ ] | Unit | 메트릭 수집 정확성 |
| [ ] | Unit | 리포트 생성 포맷 |

---

## 공통 체크리스트

### 보안 설계 반영

| 상태 | 항목 |
|------|------|
| [ ] | 모든 파일 로드에 경로 검증 적용 |
| [ ] | 가중치 파일 체크섬 검증 구현 |
| [ ] | 모델 파일 로드 시 안전 옵션 사용 |
| [ ] | 로그에 민감 정보 마스킹 |

### 성능 및 효율성 설계 반영

| 상태 | 항목 |
|------|------|
| [ ] | 피드백 쿼리 배치 처리 |
| [ ] | 가중치 싱글톤 캐싱 |
| [ ] | 시장 지표 1시간 캐싱 |
| [ ] | 모델 재학습 백그라운드 실행 |

### 임시 코드 / 파일 정리

| 상태 | 항목 |
|------|------|
| [ ] | TODO 주석 해결 또는 이슈 생성 |
| [ ] | 디버그용 print 문 제거 |
| [ ] | 테스트용 하드코딩 값 설정 파일로 이동 |
| [ ] | 사용하지 않는 import 제거 |

### 문서 업데이트

| 상태 | 항목 |
|------|------|
| [ ] | `CLAUDE.md` 학습 시스템 섹션 추가 |
| [ ] | `docs/API_REFERENCE.md` 새 API 문서화 |
| [ ] | `docs/ALGORITHMS_OVERVIEW.md` 동적 가중치 설명 추가 |
| [ ] | 인라인 docstring 작성 |

### Git 반영 및 PR 준비

| 상태 | 항목 |
|------|------|
| [ ] | 기능별 커밋 분리 |
| [ ] | 커밋 메시지 컨벤션 준수 |
| [ ] | PR 설명 작성 |
| [ ] | 리뷰어 지정 |

---

## 최종 검증

### Feature 완료 기준

| Feature | 구현 | Unit Test | Integration Test | 문서 | 완료 |
|---------|------|-----------|------------------|------|------|
| A. 자동 재학습 파이프라인 | [ ] | [ ] | [ ] | [ ] | [ ] |
| B. 동적 가중치 시스템 | [ ] | [ ] | [ ] | [ ] | [ ] |
| C. 시장 레짐 탐지 | [ ] | [ ] | [ ] | [ ] | [ ] |
| D. 전체 통합 | [ ] | [ ] | [ ] | [ ] | [ ] |

### 전체 시스템 테스트

| 상태 | 테스트 시나리오 |
|------|----------------|
| [ ] | 시스템 시작 → 레짐 탐지 → 기준 자동 적용 |
| [ ] | 피드백 축적 → 재학습 트리거 → 가중치 업데이트 |
| [ ] | 시장 급변 → 레짐 전환 → 전략 자동 조정 |
| [ ] | 가중치 이상 감지 → 자동 롤백 |
| [ ] | 1주일 시뮬레이션 무중단 운영 |

---

## 서명

| 역할 | 담당자 | 확인일 |
|------|--------|--------|
| 설계 검토 | | |
| 구현 완료 | | |
| 테스트 완료 | | |
| 최종 승인 | | |

---

**문서 끝**
