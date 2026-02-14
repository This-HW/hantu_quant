---
name: plan-task
description: 체계적인 작업 계획 수립. 규모 판단 → 요구사항 명확화 → 사용자 여정 → 비즈니스 로직 순으로 진행합니다.
model: opus
domain: common
argument-hint: [작업 설명]
allowed-tools:
  - Read
  - Glob
  - Grep
  - Task
  - TodoWrite
  - AskUserQuestion
---

# plan-task: 체계적인 작업 계획 수립

> 규모 기반 adaptive planning pipeline
> Superpowers Brainstorm 패턴 통합

---

## 개요

이 스킬은 사용자 요청을 체계적으로 분석하여 구현 가능한 계획으로 전환합니다.

**핵심 특징:**

- ✅ **규모 기반 경로**: Small/Medium/Large에 따라 필요한 Phase만 실행
- ✅ **P0 모호함 제거**: 즉시 확인 필요한 사항만 질문
- ✅ **Work 시스템 통합**: 자동으로 Work 폴더 생성 및 관리
- ✅ **Superpowers Brainstorm**: 소크라테스식 질문으로 명확화
- ✅ **2-5분 작업 분해**: 실행 가능한 최소 단위로 분해

---

## Brainstorm: 명확화 질문 (Phase 시작 전)

**Superpowers 패턴**: 계획 수립 전 핵심 질문으로 모호함 제거

### 소크라테스식 질문

```
1. **목표 명확화**: 우리가 정확히 해결하려는 문제는 무엇인가?
2. **대안 검토**: X, Y, Z 접근 방식을 고려했는가?
3. **제약사항**: 어떤 한계와 제약이 있는가?
4. **트레이드오프**: 무엇을 최적화하고 있는가? (속도 vs 품질 vs 비용)
```

### 질문 시점

```
다음 신호 발견 시 즉시 Brainstorm 진행:

❌ "아마 ~일 것이다"
❌ "보통은 ~한다"
❌ "~해야 할 것 같다"
❌ 여러 해석이 가능한 요청

✅ 사용자에게 4가지 핵심 질문으로 명확화
✅ 답변 받은 후 Planning 진행
```

---

## 6-Phase Planning Pipeline

```
Phase 0: 규모 판단 (즉시)
    ↓
Phase 1: 코드베이스 탐색 (explore-codebase, haiku)
    ↓
Phase 2: 요구사항 명확화 (clarify-requirements, opus) ← P0 모호함 제거
    ↓
Phase 3: 사용자 여정 설계 (design-user-journey, sonnet) [Medium/Large]
    ↓
Phase 4: 비즈니스 로직 정의 (define-business-logic, sonnet) [Large]
    ↓
Phase 5: 구현 계획 수립 (plan-implementation, haiku)
    ↓
Phase 6: 다관점 리뷰 (multi-perspective-review) [Medium/Large, 자동 실행]
    ↓
Planning 완료 → Development 준비
```

### 규모별 경로

| 규모   | 실행 Phase                | 예상 시간 |
| ------ | ------------------------- | --------- |
| Small  | 0 → 1 → 2 → 5             | ~30분     |
| Medium | 0 → 1 → 2 → 3 → 5 → 6     | ~1.5시간  |
| Large  | 0 → 1 → 2 → 3 → 4 → 5 → 6 | ~2.5시간  |

---

## Work 시스템 자동화

**Work 시스템을 사용하는 경우**, 다음이 자동으로 처리됩니다:

```
✅ Work ID 생성 (W-XXX)
✅ 폴더 구조 생성 (docs/works/idea/W-XXX-{slug}/)
✅ Frontmatter 자동 작성
✅ progress.md 초기화 및 갱신
✅ decisions.md P0 결정 기록
```

**상세:** [references/work-system.md](references/work-system.md)

---

## Phase 0: 규모 판단 (즉시 실행)

다음 기준으로 작업 규모를 판단:

| 기준          | Small     | Medium     | Large     |
| ------------- | --------- | ---------- | --------- |
| 영향 범위     | 1개 모듈  | 2-3개 모듈 | 4개+ 모듈 |
| 데이터 변경   | 없음      | 기존 확장  | 새 구조   |
| 비즈니스 규칙 | 기존 내   | 경미 추가  | 핵심 변경 |
| 사용자 흐름   | 변경 없음 | 기존 수정  | 새 흐름   |

**출력:**

```
## 규모 판단
- 규모: [Small/Medium/Large]
- 근거: [판단 이유]
- Planning 경로: [Phase 목록]
```

---

## Phase 1: 코드베이스 탐색

**Subagent**: explore-codebase (haiku)

```
Task(
  subagent_type="explore-codebase",
  model="haiku",
  description="코드베이스 구조 파악",
  prompt="""
  요청: [사용자 요청]

  다음을 파악:
  1. 프로젝트 구조 및 기술 스택
  2. 관련 파일 및 의존성
  3. 기존 코드 패턴과 컨벤션
  4. 수정이 필요한 위치
  5. 유사한 기존 구현 (참고용)
  """
)
```

**예상 결과**: 프로젝트 구조, 관련 파일, 코드 패턴, 참고 구현

---

## Phase 2: 요구사항 명확화

**Subagent**: clarify-requirements (opus)

```
Task(
  subagent_type="clarify-requirements",
  model="opus",
  description="요구사항 분석 및 P0 모호함 제거",
  prompt="""
  [사용자 요청]
  [Phase 1 탐색 결과]

  수행:
  1. 요구사항 분석 (명시적/암묵적/기술적 제약)
  2. 모호함 분류 (P0~P3)
  3. P0 모호함 발견 시 즉시 질문

  | 등급 | 기준 | 처리 |
  |------|------|------|
  | P0 | 데이터 무결성, 보안, 금융, 핵심 비즈니스 | 즉시 질문 |
  | P1 | UX 분기, 비즈니스 디테일 | 기본값 + 나중 확인 |
  | P2 | UI 디테일, 엣지케이스 | TODO 기록 |
  | P3 | 기술 선택 | 자율 판단 |
  """
)
```

**P0 모호함 발견 시**:

- AskUserQuestion으로 즉시 질문
- 답변 받은 후 재호출

**예상 결과**: 요구사항 요약, 확인된 사항, P0 모호함, P1/P2 미결정

**상세:** [references/phase-guides.md#phase-2](references/phase-guides.md#phase-2-요구사항-명확화-필수)

---

## Phase 3: 사용자 여정 설계 (Medium/Large)

**Subagent**: design-user-journey (sonnet)

```
Task(
  subagent_type="design-user-journey",
  model="sonnet",
  description="사용자 흐름 및 상태 설계",
  prompt="""
  [사용자 요청]
  [Phase 2 요구사항]

  수행:
  1. 사용자 여정 정의 (진입점 → 주요 흐름 → 대안 흐름 → 종료점)
  2. 상태 다이어그램
  3. 에러 처리 전략
  """
)
```

**예상 결과**: 사용자 여정, 상태 다이어그램, 에러 처리

**상세:** [references/phase-guides.md#phase-3](references/phase-guides.md#phase-3-사용자-여정-설계-mediumlarge)

---

## Phase 4: 비즈니스 로직 정의 (Large)

**Subagent**: define-business-logic (sonnet)

```
Task(
  subagent_type="define-business-logic",
  model="sonnet",
  description="비즈니스 규칙 명세화",
  prompt="""
  [사용자 요청]
  [Phase 2 요구사항]
  [Phase 3 사용자 여정]

  수행:
  1. 비즈니스 규칙 식별 (VAL/CALC/STATE/AUTH/POL)
  2. 규칙 명세화 (ID, 조건, 결과, 예외, 예시)
  """
)
```

**예상 결과**: 비즈니스 규칙 목록, 규칙 상세 명세

**상세:** [references/phase-guides.md#phase-4](references/phase-guides.md#phase-4-비즈니스-로직-정의-large)

---

## Phase 5: 구현 계획 수립

**Subagent**: plan-implementation (haiku)

```
Task(
  subagent_type="plan-implementation",
  model="haiku",
  description="구체적 구현 작업 계획",
  prompt="""
  [사용자 요청]
  [Phase 2~4 결과]

  수행:
  1. 목표 요약
  2. 기술적 결정 (프레임워크, 패턴, 구조)
  3. 작업 분해 (2-5분 단위, 배치별 병렬화)
  4. 파일 변경 예상
  5. 리스크 분석
  """
)
```

**2-5분 작업 분해 원칙** (Superpowers):

```
❌ 나쁜 예: "인증 시스템 구현"

✅ 좋은 예:
- [ ] User 타입 정의 (src/types/user.ts)
- [ ] 로그인 API (src/api/auth.ts)
- [ ] JWT 유틸 (src/utils/jwt.ts)
- [ ] 로그인 폼 (src/components/LoginForm.tsx)
- [ ] 상태 관리 (src/store/auth.ts)
```

**예상 결과**: 목표, 기술적 결정, 작업 분해, 파일 변경, 리스크

**상세:** [references/phase-guides.md#phase-5](references/phase-guides.md#phase-5-구현-계획-수립-필수)

---

## Phase 6: 다관점 리뷰 (규모별 자동 실행)

**실행 조건**: Phase 5 완료 후 규모에 따라 자동 실행

**실행 방식:**

- **Medium/Large**: Phase 5 완료 즉시 자동으로 multi-perspective-review 스킬 호출
- **Small**: 리뷰 생략, 사용자가 명시적으로 요청한 경우에만 실행

**리뷰 대상**: Phase 2~5의 종합 Planning 결과 (planning-results.md)

### 규모별 리뷰 전략

| 규모   | 리뷰 실행                 | 관점 수 | 실행 방식      |
| ------ | ------------------------- | ------- | -------------- |
| Small  | 생략                      | 0       | 수동 요청 시만 |
| Medium | 4개 핵심 관점             | 4       | 자동 실행      |
| Large  | 전체 관점 + 비즈니스 로직 | 9       | 자동 실행      |

### Medium 규모 (4개 핵심 관점)

```
실행 관점:
1. Requirements (clarify-requirements) - 요구사항 명확성
2. Technical (plan-implementation) - 기술적 실현가능성
3. Security (security-scan) - 보안 취약점
4. Business Logic (define-business-logic) - 비즈니스 규칙 검증

이유: Medium 규모에서도 비즈니스 규칙 검증이 중요한 경우가 많음
```

### Large 규모 (9개 전체 관점)

```
실행 관점:
1. Requirements (clarify-requirements)
2. Technical (plan-implementation)
3. Security (security-scan)
4. UX/Flow (design-user-journey)
5. Business Logic (define-business-logic)
6. Dependencies (analyze-dependencies)
7. Code Quality (review-code)
8. Metrics (define-metrics)
9. Data/Schema (design-database)

이유: 복잡한 시스템 변경은 모든 관점의 검증 필요
```

### 자동 리뷰 실행

**Medium/Large 규모에서 Phase 5 완료 후:**

```python
# 의사 코드
if size == "Medium":
    perspectives = ["requirements", "technical", "security", "business_logic"]
elif size == "Large":
    perspectives = ["requirements", "technical", "security", "ux_flow",
                     "business_logic", "dependencies", "code_quality",
                     "metrics", "data_schema"]
else:  # Small
    perspectives = []  # 리뷰 생략

if perspectives:
    # Planning 결과 문서를 Work 폴더에 저장
    planning_doc = save_planning_results()

    # multi-perspective-review 스킬 호출
    result = run_skill("multi-perspective-review", planning_doc)

    # 리뷰 결과를 Work 폴더에 저장
    save_review_results(result)
```

### Agent Teams 모드 자동 선택 (W-032)

**Large 규모에서 CALC-001 점수 >= 9인 경우, Agent Teams 모드로 자동 전환:**

```python
# CALC-001 모드 자동 선택
mode_score = scale * 2 + perspective * 2 + complexity * 1

if mode_score >= 9:
    # Agent Teams 모드: facilitator-teams.md (Lead) + Teammate 병렬
    # 환경변수: CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 필요
    result = run_skill("multi-perspective-review", planning_doc, mode="agent_teams")
else:
    # Subagent 모드: facilitator → 병렬 Task → synthesizer → consensus-builder
    result = run_skill("multi-perspective-review", planning_doc, mode="subagent")
```

**모드별 차이:**

| 항목      | Subagent 모드                 | Agent Teams 모드          |
| --------- | ----------------------------- | ------------------------- |
| 토큰 한도 | 150K (POL-002)                | 300K (POL-002)            |
| 관점 수   | 4-9개                         | 4-9개                     |
| 실행 방식 | 순차 Task 호출                | 병렬 Teammate             |
| 합의 도출 | consensus-builder (별도 Task) | Lead가 직접 수행          |
| 폴백      | -                             | Subagent 모드로 자동 전환 |

**상세:** `skills/common/multi-perspective-review/skill.md` (Agent Teams 섹션)

### 리뷰 결과 저장

**Work 시스템 파일 구조 확장:**

```
docs/works/idea/W-XXX-{slug}/
├── W-XXX-{slug}.md          # 메인 Work 파일
├── progress.md               # 진행 상황
├── decisions.md              # P0 결정 사항
├── planning-results.md       # Phase 2~5 Planning 결과 (신규)
└── review-results.md         # Phase 6 다관점 리뷰 결과 (신규)
```

**planning-results.md 형식:**

```markdown
# Planning 결과

## 규모

- 크기: [Small/Medium/Large]
- 판단 근거: [...]

## 요구사항 (Phase 2)

[clarify-requirements 결과]

## 사용자 여정 (Phase 3, Medium/Large만)

[design-user-journey 결과]

## 비즈니스 로직 (Phase 4, Large만)

[define-business-logic 결과]

## 구현 계획 (Phase 5)

[plan-implementation 결과]
```

**review-results.md 형식:**

```markdown
# 다관점 리뷰 결과

## 리뷰 메타데이터

- 실행 날짜: [...]
- 규모: [Medium/Large]
- 참여 관점: [N]개
- 합의율: [X]%

## Critical 이슈 (즉시 해결 필요)

[...]

## Important 이슈 (권장)

[...]

## Nice-to-have (선택)

[...]

## 최종 권고사항

- [ ] [액션 아이템 1]
- [ ] [액션 아이템 2]
```

---

## Planning 완료 체크리스트

### 기본 (모든 규모)

```
□ 규모 판단 완료
□ P0 모호함 = 0개
□ 요구사항 명확히 정의됨
□ 구현 계획 수립됨
□ 리스크 식별됨
```

### Medium/Large

```
□ 사용자 여정 설계됨
□ 주요 상태 전이 명세됨
□ 에러 처리 전략 수립됨
```

### Large

```
□ 비즈니스 규칙 명세됨
□ 규칙 간 관계 정의됨
□ 예외 처리 명세됨
```

### Work 시스템 (해당 시)

```
□ Work 폴더 생성됨
□ Frontmatter 작성됨
□ progress.md 갱신됨
□ decisions.md 기록됨
□ planning-results.md 저장됨 (Phase 2~5 결과)
□ phases_completed: [planning] 업데이트됨
```

### 다관점 리뷰 (Medium/Large만)

```
□ 규모별 관점 선택됨 (Medium: 4개, Large: 9개)
□ multi-perspective-review 실행됨
□ Critical/Important 이슈 식별됨
□ review-results.md 저장됨
□ 최종 권고사항 확인됨
```

---

## Planning 완료 출력

````
# Planning 완료 보고서

## 1. Work 정보 (Work 시스템 사용 시)
- Work ID: W-XXX
- 위치: docs/works/idea/W-XXX-{slug}/
- 상태: planning 완료 → development 준비

## 2. 규모 및 경로
- 규모: [Small/Medium/Large]
- 실행 Phase: [목록]

## 3. 요구사항 요약
[Phase 2 핵심 요구사항]

## 4. 사용자 여정 (해당시)
[Phase 3 핵심 흐름]

## 5. 비즈니스 규칙 (해당시)
[Phase 4 핵심 규칙]

## 6. 구현 계획
[Phase 5 작업 분해 및 파일 변경]

## 7. 다관점 리뷰 결과 (Medium/Large만)
- 리뷰 실행: [예/아니오]
- 관점 수: [N]개
- Critical 이슈: [N]개
- Important 이슈: [N]개
- 최종 권고: [요약]

## 8. 미결정 사항 (P1/P2)
[나중에 결정할 항목]

## 9. 다음 단계

**Work 시스템:**
```bash
# Phase 전환
./scripts/work.sh next-phase W-XXX

# 또는 직접 구현
/auto-dev W-XXX
````

**일반 프로젝트:**

- `/auto-dev [작업]` 또는 "진행해줘"

```

---

## 상세 참조

| 주제 | 문서 |
|------|------|
| Work 시스템 자동화 | [references/work-system.md](references/work-system.md) |
| Phase별 상세 가이드 | [references/phase-guides.md](references/phase-guides.md) |
| Superpowers 패턴 | docs/research/superpowers-analysis.md |
| Planning 협업 프로토콜 | .claude/rules/planning-protocol.md |
| Agent 시스템 | .claude/rules/agent-system.md |

---

## 관련 스킬

| 다음 단계 | 스킬 |
|----------|------|
| 구현 시작 | `/auto-dev` |
| 리뷰 | `/review` |
| 테스트 | `/test` |
```
