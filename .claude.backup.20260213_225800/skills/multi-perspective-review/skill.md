---
name: multi-perspective-review
description: 기획/문서를 여러 관점에서 협업 검토. 9개 관점의 전문가가 의견 교류하며 합의를 도출합니다.
model: opus
domain: common
argument-hint: [문서 경로 또는 Work ID]
allowed-tools:
  - Read
  - Glob
  - Grep
  - Task
  - Write
  - AskUserQuestion
---

# multi-perspective-review: 다관점 협업 리뷰

> Deliberation Pattern 기반 문서 검토
> 9개 관점의 전문가가 의견 교류하며 합의 도출

---

## 개요

이 스킬은 복잡한 기획/설계 문서를 여러 관점의 전문가가 협업하여 검토합니다.
단순 체크리스트가 아닌, **의견 교류**와 **합의 도출** 과정을 통해 깊이 있는 리뷰를 제공합니다.

**핵심 특징:**

- ✅ **9개 관점**: Requirements, Technical, Security, UX, Business Logic, Dependencies, Code Quality, Metrics, Data/Schema
- ✅ **3-Round Deliberation**: 초기 의견 → 상호 검토 → 합의 도출
- ✅ **충돌 해결**: 관점 간 상충 의견을 트레이드오프 분석으로 해결
- ✅ **영향도 분석**: 변경사항의 시스템 전체 영향 평가
- ✅ **최종 합의안**: Critical/Important/Nice-to-have 분류 + 액션 아이템

---

## 9개 관점 (Perspectives)

| 관점               | 역할            | 관련 에이전트         | 포커스                                    |
| ------------------ | --------------- | --------------------- | ----------------------------------------- |
| **Requirements**   | 기획자          | clarify-requirements  | P0 모호함, 엣지 케이스, 비기능 요구사항   |
| **Technical**      | 개발자          | plan-implementation   | 기술적 실현가능성, 개발 기간, 시스템 충돌 |
| **Security**       | 보안            | security-scan         | 인증/권한, 민감 데이터, 공격 벡터         |
| **UX/Flow**        | UX 디자이너     | design-user-journey   | 사용자 흐름, 상호작용, 접근성             |
| **Business Logic** | 비즈니스 분석가 | define-business-logic | 비즈니스 규칙, 도메인 로직, 정책          |
| **Dependencies**   | 아키텍트        | analyze-dependencies  | 외부 연동, 라이브러리, 시스템 간 의존성   |
| **Code Quality**   | 리뷰어          | review-code           | 코드 품질, 유지보수성, 테스트 가능성      |
| **Metrics**        | 데이터 엔지니어 | define-metrics        | 성능 지표, 모니터링, SLA                  |
| **Data/Schema**    | DB 설계자       | design-database       | 스키마 설계, 데이터 모델, 마이그레이션    |

**상세:** [references/perspectives-guide.md](references/perspectives-guide.md)

---

## 워크플로우 (3-Round Deliberation)

```
┌──────────────────────────────────────────┐
│ Round 0: Facilitation (사전 준비)        │
│   → Facilitator가 문서 분석              │
│   → 필요한 관점 식별                     │
│   → 각 관점의 초점 영역 정의             │
│   → common_context_files 출력            │
└──────────────────────────────────────────┘
                    ↓
┌──────────────────────────────────────────┐
│ Context 수집 (메인 Claude)               │
│   → facilitator 결과에서 Level 1 파일 추출│
│   → CLAUDE.md 읽기                       │
│   → planning-protocol.md 읽기            │
│   → Meta 에이전트용 Level 2 파일 별도 준비│
└──────────────────────────────────────────┘
                    ↓
┌──────────────────────────────────────────┐
│ Round 1: 초기 의견 수집 (병렬)           │
│   → 각 관점의 에이전트 동시 실행         │
│   → Level 1 Context를 prompt에 포함      │
│   → Meta 에이전트는 Level 2도 포함       │
│   → 독립적 의견 도출                     │
│   → Synthesizer가 종합 (중복/충돌 식별)  │
└──────────────────────────────────────────┘
                    ↓
┌──────────────────────────────────────────┐
│ Round 2: 상호 검토 (순차)                │
│   → Round 1 의견을 컨텍스트로 포함       │
│   → 다른 관점 의견 고려하여 재검토       │
│   → 추가 이슈 식별 및 충돌 제안          │
└──────────────────────────────────────────┘
                    ↓
┌──────────────────────────────────────────┐
│ Round 3: 합의 도출                       │
│   → Consensus-Builder가 충돌 분석        │
│   → 트레이드오프 제시                    │
│   → 합의안 도출 (필요시 사용자 질문)     │
│   → Impact-Analyzer가 영향도 분석        │
│   → Synthesizer가 최종 리포트 작성       │
└──────────────────────────────────────────┘
```

**상세:** [references/deliberation-pattern.md](references/deliberation-pattern.md)

---

## 중요 참고사항

### Context 계층화 (토큰 최적화)

**목적**: 중복 Context 제거로 토큰 46% 절감 (73K → 39K with Prompt Caching)

**동작 방식:**

1. **facilitator 실행**: Round 0에서 `common_context_files` 출력
2. **메인 Claude가 Level 1 수집**: CLAUDE.md, planning-protocol.md 읽기
3. **Task 호출 시 Level 1 포함**: 모든 관점 에이전트에게 전달
4. **Meta 에이전트는 Level 2 추가**: agent-system.md도 포함
5. **Level 3는 독립 읽기**: 각 에이전트가 필요 시 독립적으로 읽음

**효과:**

- Prompt Caching 사용 시: 73K → 39K tokens (46% 절감)
- Prompt Caching 미사용 시: 145K → 95K tokens (34% 절감)
- 중복 제거로 API 호출 최소화

---

### Task Tool 사용

이 스킬은 `Task` 도구를 사용하여 서브에이전트(facilitator, synthesizer, consensus-builder, impact-analyzer 등)를 호출합니다. **이는 메인 Claude가 스킬을 실행할 때만 사용되며, 서브에이전트 자체는 Task 도구를 사용하지 않습니다.**

**구조:**

- ✅ **스킬 (multi-perspective-review)**: Task 도구 허용 (메인 Claude가 실행)
- ❌ **서브에이전트 (facilitator, synthesizer 등)**: Task 도구 금지 (disallowedTools)

이 설계는 서브에이전트 중첩을 방지하고, 메인 Claude가 모든 워크플로우 조율을 담당하도록 합니다.

---

## 사용법

### 기본 사용

```bash
# 문서 파일 직접 지정
/multi-perspective-review docs/planning/point-system.md

# Work 시스템 사용
/multi-perspective-review W-042
```

### 옵션 (향후 확장)

```bash
# 특정 관점만 선택
/multi-perspective-review docs/api-spec.md --perspectives security,technical

# Round 1만 실행 (빠른 피드백)
/multi-perspective-review docs/feature.md --quick

# 자동 수정 제안 활성화
/multi-perspective-review docs/design.md --auto-fix
```

---

## 실행 예시

### 입력 문서

```markdown
# 포인트 시스템 추가

## 요구사항

- 사용자가 구매 시 포인트 적립
- 포인트로 결제 가능
- 포인트 유효기간 1년
```

### 실행 과정

```
🔍 Round 0: Facilitator 분석
  → 복잡도: Large
  → 선택된 관점: Requirements, Technical, Security, Business Logic, Data/Schema

⚡ Round 1: 병렬 의견 수집
  ├─ Requirements: P0 모호함 3개 발견 (사용자 정의, 적립률, 사용 제한)
  ├─ Technical: 개발 3주 예상, 트랜잭션 무결성 필요
  ├─ Security: 포인트 조작 방지, 감사 로그 필수
  ├─ Business Logic: 적립률 5%, 최소/최대 사용 제한
  └─ Data/Schema: points, point_transactions 테이블 필요

📊 Synthesizer 종합
  → Critical: 2개, Important: 3개, Nice-to-have: 2개
  → 충돌: 2개 (개발 기간, Rate Limiting 우선순위)

🔄 Round 2: 상호 검토
  ├─ Technical (재검토): 보안 요구사항 반영 → 3주 확정
  ├─ Security (재검토): Rate limiting Phase 2 연기 수용
  └─ Impact-Analyzer: 3개 시스템 영향, 총 26.5일 예상

🤝 Round 3: 합의 도출
  ├─ Consensus-Builder: 충돌 2개 해결 (Phase 분할, 우선순위 조정)
  └─ 합의율: 100%

📝 최종 리포트 작성
  → Critical 2개, Important 3개 정리
  → 액션 아이템 5개
  → 권장: 조건부 승인 (트랜잭션 테스트 필수)
```

**상세 예시:** [references/examples.md](references/examples.md)

---

## 출력 형식

### 최종 리포트 구조

```markdown
# 다관점 리뷰 최종 결과

## 📋 Executive Summary

- 문서: [문서명]
- 복잡도: [Small/Medium/Large]
- 참여 관점: [N]개
- 합의 상태: [X]% 합의

---

## 🔴 Critical (즉시 수정 필요)

### 1. [이슈명]

**제기 관점:** [관점 목록]
**내용:** [상세 설명]
**영향:** [영향 범위]
**해결:** [구체적 해결책]
**합의:** ✅ 전원 합의 / ⚠️ 조건부 / ❓ 사용자 결정 필요

---

## 🟡 Important (수정 권장)

...

## 🟢 Nice-to-have (선택 사항)

...

---

## 💬 합의 과정

### 충돌 #1: [충돌 설명]

**Round 1:** [초기 의견]
**Round 2:** [재검토 의견]
**합의안:** [최종 합의]
**결과:** ✅ 해결 / ❓ 사용자 결정 대기

---

## 📊 영향도 분석

**변경 범위:**

- 시스템: [영향받는 시스템 목록]
- 파일: [예상 변경 파일 수]

**개발 기간:** [예상 시간]
**리스크:** [리스크 레벨 및 완화 방안]

---

## 🎯 다음 단계

1. [ ] [액션 아이템 1]
2. [ ] [액션 아이템 2]
       ...
```

---

## 내부 구조 (메타 에이전트)

이 스킬은 4개의 메타 에이전트를 조율합니다:

### 1. Facilitator (조율자)

- **역할**: 문서 분석, 필요 관점 식별
- **모델**: opus
- **출력**: 관점 목록 + 초점 영역

### 2. Synthesizer (종합자)

- **역할**: 의견 통합, 충돌/중복 식별
- **모델**: opus
- **출력**: Round 1 종합, Round 2 최종 리포트

### 3. Consensus-Builder (합의 도출자)

- **역할**: 충돌 분석, 트레이드오프 제시
- **모델**: opus
- **출력**: 충돌 해결안, 합의 수준

### 4. Impact-Analyzer (영향도 분석자)

- **역할**: 시스템 영향 분석, 리스크/비용 평가
- **모델**: sonnet
- **출력**: 영향받는 시스템, 개발 기간, 리스크 분류

**위치:** `agents/common/meta/`

---

## 고급 활용

### 점진적 리뷰 (Incremental Review)

```
대규모 문서를 섹션별로 나누어 리뷰:

1. /multi-perspective-review docs/design.md --section "1. 개요"
2. /multi-perspective-review docs/design.md --section "2. 아키텍처"
3. 최종 통합 리뷰
```

### 반복 리뷰 (Iterative Review)

```
Round 1 결과 → 문서 수정 → Round 2 재리뷰:

1. /multi-perspective-review docs/v1.md
2. (문서 수정)
3. /multi-perspective-review docs/v2.md --previous-review results/v1-review.md
```

### 커스텀 관점 추가

```
프로젝트 특화 관점 추가:

1. agents/project/[프로젝트명]/custom-reviewer.md 작성
2. /multi-perspective-review docs/spec.md --add-perspective custom-reviewer
```

---

## 사용 시나리오

### 시나리오 1: 신규 기능 기획 리뷰

```
상황: 포인트 시스템 기획서 작성 완료
목표: 구현 전 다양한 관점의 검증

1. /multi-perspective-review docs/planning/point-system.md
2. Critical 이슈 확인 (P0 모호함, 보안 등)
3. 사용자에게 P0 질문 (AskUserQuestion)
4. 문서 수정 후 재리뷰
5. 합의 완료 → 구현 진행
```

### 시나리오 2: API 설계 리뷰

```
상황: RESTful API 명세 작성 완료
목표: 기술/보안/비즈니스 관점 검증

1. /multi-perspective-review docs/api/payment-api.md
2. Technical: 엔드포인트 설계 검토
3. Security: 인증/권한 체계 검토
4. Business Logic: API 비즈니스 규칙 검토
5. 충돌 해결 (예: 보안 vs 성능)
6. 최종 승인 → 구현
```

### 시나리오 3: 아키텍처 설계 리뷰

```
상황: 마이크로서비스 아키텍처 설계 완료
목표: 전체 시스템 관점 검증

1. /multi-perspective-review docs/architecture/microservices.md
2. 9개 관점 모두 참여
3. Dependencies: 서비스 간 의존성 분석
4. Impact-Analyzer: 마이그레이션 영향도 분석
5. 단계별 마이그레이션 계획 합의
6. 리스크 완화 방안 수립
```

---

## 주의사항

```
⚠️ 복잡한 문서에만 사용
   → 단순 변경은 단일 에이전트 리뷰로 충분

⚠️ Round 수행 시간
   → Round 1: 5-10분 (병렬)
   → Round 2: 10-15분 (순차)
   → Round 3: 5분 (합의)
   → 총 20-30분 예상

⚠️ 충돌이 많으면 시간 증가
   → 사전에 기획 명확화 권장

⚠️ 사용자 결정 필요 시 중단
   → AskUserQuestion 대기 중 일시 정지
```

---

## Agent Teams 모드 (실험적)

### 개요

`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` 환경 변수가 설정되면, 이 스킬은 **Agent Teams 모드**로 실행될 수 있습니다.
Agent Teams는 spawnTeam() API를 사용하여 Teammate들이 병렬로 독립 분석을 수행합니다.

### 모드 자동 선택 (CALC-001)

```
모드 점수 = scale×2 + perspective×2 + complexity×1

조건:
  점수 >= 9 → AGENT_TEAMS 모드 (자동 전환)
  점수 < 9  → SUBAGENT 모드 (기본)

사용자 오버라이드:
  --agent-teams     → 강제 Teams 모드
  --no-agent-teams  → 강제 Subagent 모드
```

### Agent Teams 실행 구조

```
Main Claude
  └─ spawnTeam()
       ├─ Lead: facilitator-teams (Opus)
       │    ├─ Round 0: 문서 분석 + Teammate 지시 (broadcast)
       │    ├─ Round 1: 독립 분석 수신 (message)
       │    ├─ Round 2: 통합 분석 (Synthesizer 역할)
       │    └─ Round 3: 합의 도출 (Consensus-Builder 역할)
       │
       └─ Teammates (각 관점별):
            ├─ clarify-requirements (Requirements)
            ├─ plan-implementation (Technical)
            ├─ security-scan (Security)
            ├─ impact-analyzer (Impact, 항상 포함)
            └─ ... (문서 유형에 따라 선정)
```

### 폴백 전략 (Teams → Subagent)

Agent Teams 모드에서 문제 발생 시, 자동으로 Subagent 모드로 전환합니다.

#### 즉시 전환 트리거

```
다음 상황 발생 시 Subagent 모드로 즉시 폴백:

1. VAL-001 검증 실패
   → spawnTeam API 미지원, 환경 변수 미설정, 릴리즈 버전 미충족
   → 기존 3-Round Deliberation으로 자동 전환

2. Lead 초기화 실패 (30초 타임아웃)
   → facilitator-teams.md 로드 실패
   → 기존 facilitator.md + 개별 Meta 에이전트로 전환

3. 전원 실패 (모든 Teammate FAILED)
   → 결과물이 전혀 없는 상태
   → Subagent 모드로 전환하여 전체 리뷰 재시작
```

#### 부분 복구 (Graceful Degradation)

```
조건: 과반수 실패이지만, 2개 이상 관점 결과 존재

행동:
  1. 실패 Teammate를 FORCE_PROCEEDED로 전환
  2. 현재 결과로 CONSENSUS 진입 (축소된 합의)
  3. 최종 리포트에 누락 관점 경고 표시

리포트 추가:
  ## ⚠️ 부분 리뷰 경고
  다음 관점은 Teammate 실패로 포함되지 않았습니다:
  - [관점명]: [실패 사유]
  권장: 누락된 관점에 대해 별도 Subagent 리뷰를 실행하세요.
```

#### 사용자 결정 요청

```
조건: 결과 2개이지만 핵심 관점(Requirements, Technical) 누락

AskUserQuestion:
  A) 현재 결과로 리뷰 완료 (부분 리뷰)
  B) Subagent 모드로 전환하여 전체 리뷰 재실행
  C) 리뷰 취소
```

### 토큰 한도 (POL-002)

```
모드별 한도:
  SUBAGENT 모드:     150,000 토큰
  AGENT_TEAMS 모드:  300,000 토큰

3계층 방어:
  80% → 분석 범위 축소 (Level 3 참고 문서 스킵)
  90% → Round 3 강제 진입 (즉시 합의 도출)
  100% → 현재 결과로 정리 후 종료

환경 변수 오버라이드:
  CLAUDE_COST_LIMIT_SUBAGENT=150000
  CLAUDE_COST_LIMIT_TEAMS=300000
```

### 관련 파일

| 파일                                                                      | 역할                       |
| ------------------------------------------------------------------------- | -------------------------- |
| `agents/common/meta/facilitator-teams.md`                                 | Agent Teams Lead 에이전트  |
| `hooks/teammate-idle.py`                                                  | Teammate 5분 타임아웃 감시 |
| `hooks/pol002-monitor.py`                                                 | 토큰 사용량 3계층 방어     |
| `docs/works/active/W-032-feature-adoption-2026/state-transition-table.md` | 상태 전이표                |
| `docs/works/active/W-032-feature-adoption-2026/crash-recovery-path.md`    | 크래시 복구 경로           |

---

## 확장 가능성

### 향후 계획

```
✨ Agent Teams 모드 정식 지원
   → 실험적 플래그 제거 후 기본 모드로 전환

✨ 자동 수정 제안 (--auto-fix)
   → Critical 이슈에 대한 자동 수정 PR 생성

✨ 리뷰 히스토리 추적
   → 버전별 리뷰 결과 비교

✨ 관점별 가중치 설정
   → 보안 중요 프로젝트는 Security 의견 가중

✨ 외부 도구 연동
   → Notion, Figma, Swagger 등 직접 리뷰
```

---

## 관련 스킬

| 스킬          | 관계 | 설명                        |
| ------------- | ---- | --------------------------- |
| **plan-task** | 선행 | 작업 계획 수립 후 문서 리뷰 |
| **auto-dev**  | 후행 | 리뷰 통과 후 자동 개발      |
| **review**    | 대안 | 코드 리뷰 (구현 후)         |

---

## References

- [deliberation-pattern.md](references/deliberation-pattern.md) - 3-Round 패턴 상세
- [perspectives-guide.md](references/perspectives-guide.md) - 9개 관점 가이드
- [conflict-resolution.md](references/conflict-resolution.md) - 충돌 해결 전략
- [examples.md](references/examples.md) - 실제 리뷰 예시
