---
name: auto-dev
description: 자동화된 개발 파이프라인 실행. 탐색 → 계획 → 구현 → 검증 → 리뷰 순으로 진행합니다.
model: sonnet
domain: common
argument-hint: [작업 설명]
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, Task, WebSearch, WebFetch, TodoWrite, AskUserQuestion
---

# 자동 개발 파이프라인 실행

> 6-Phase automated development pipeline
> TDD Red-Green-Refactor 통합

**즉시 실행하세요. 설명하지 말고 바로 실행합니다.**

사용자 요청: $ARGUMENTS

---

## 파이프라인 구조

```
Phase 0: Planning 확인
    ↓
Phase 1: explore-codebase (haiku)
    ↓
Phase 2: development-review (병렬 3개) ← 신규!
    ├─ plan-implementation (sonnet)
    ├─ review-code (opus)
    └─ analyze-dependencies (sonnet)
    ↓
Phase 3: implement-code (sonnet)
    ↓
Phase 4: test-and-verify (병렬 3개) ← 확장!
    ├─ write-tests (sonnet+TDD)
    ├─ verify-code (haiku)
    └─ security-scan (sonnet)
    ↓
Phase 5: review-code (opus) - 최종 리뷰
    ↓
Phase 6: 완료 보고
```

**중요**: 각 단계 완료 후 결과를 확인하고 다음 단계 에이전트를 직접 호출해야 합니다.
Subagent는 다른 subagent를 호출할 수 없으므로 Main Claude가 순차적으로 오케스트레이션합니다.

**병렬 실행**: Phase 2와 Phase 4는 병렬 실행으로 시간을 단축합니다.
**fail-fast**: Phase 4에서 하나라도 실패하면 즉시 중단하고 수정합니다.

---

## Work 시스템 통합

**이 프로젝트는 Work 시스템을 사용합니다.**

```
✅ idea → active 자동 전환
✅ Phase 전환 자동화 (planning → development → validation)
✅ progress.md 자동 업데이트
✅ 완료 시 completed/ 이동
```

**상세:** [references/work-integration.md](references/work-integration.md)

---

## Phase 0: Planning 결과 확인

**이 프로젝트가 Work 시스템을 사용하고 plan-task 결과가 있는지 확인합니다.**

```bash
# Work 폴더 확인
ls docs/works/active/ | grep "W-[0-9]"
ls docs/works/idea/ | grep "W-[0-9]"

# plan-task 결과 파일 확인
# - planning-completed.md
# - decisions.md, user-journey.md, business-rules.md 등
```

**결과에 따른 분기:**

1. **plan-task 결과 있음** (planning 완료)
   - Phase 2에서 **Development 관점만** 수행
   - Planning 관점 리뷰는 이미 완료됨 → 스킵

2. **plan-task 결과 없음** (planning 미완료)
   - Phase 2에서 **모든 관점** 수행
   - Planning + Development 관점 모두 필요

**Work Phase 전환:**

```bash
# planning → development 전환 (해당 시)
./scripts/work.sh next-phase W-XXX
```

---

## Phase 1: 코드베이스 탐색 (즉시 실행)

```
Task tool 사용:
subagent_type: explore-codebase
model: haiku
prompt: |
  사용자 요청: [요청 내용]

  다음을 파악해주세요:
  1. 관련 파일 및 디렉토리
  2. 기존 코드 패턴과 컨벤션
  3. 의존성 관계
  4. 수정이 필요한 위치
  5. CLAUDE.md와 project-structure.yaml 규칙 확인
```

**탐색 완료 후**: 결과를 확인하고 Phase 2로 진행

---

## Phase 2: 개발 계획 및 사전 분석 (병렬)

**3가지 관점을 병렬로 분석합니다. 각 에이전트를 동시에 호출하세요.**

### 2a. 기술 계획 (plan-implementation)

```
Task tool 사용:
subagent_type: plan-implementation
model: sonnet
prompt: |
  [Phase 1 탐색 결과 요약 포함]

  다음 구현 계획을 수립해주세요:
  1. 작업 분해 (2-5분 단위 - Superpowers 패턴)
  2. 파일별 변경 내용
  3. 구현 순서와 의존성
  4. **의존성 그래프** (조건부 병렬화용) ← 신규!
     - 파일 간 의존성 명시
     - 독립적으로 구현 가능한 파일 그룹 식별
  5. 리스크 분석
```

### 2b. 품질 검토 (review-code)

```
Task tool 사용:
subagent_type: review-code
model: opus
prompt: |
  [Phase 1 탐색 결과 포함]

  개발 계획 관점에서 기존 코드베이스를 검토해주세요:
  1. 변경 예정 영역의 코드 품질
  2. 개선이 필요한 부분
  3. 리팩토링 기회
  4. 잠재적 문제점 (기술 부채, 안티패턴)
```

### 2c. 의존성 분석 (analyze-dependencies)

```
Task tool 사용:
subagent_type: analyze-dependencies
model: sonnet
prompt: |
  [Phase 1 탐색 결과 포함]

  의존성 관점에서 분석해주세요:
  1. 외부 라이브러리 의존성
  2. 내부 모듈 의존성
  3. 버전 호환성
  4. 의존성 충돌 가능성
```

**Phase 2 완료 후**:

1. **3가지 관점의 결과를 종합**
   - 기술 계획 + 품질 검토 + 의존성 분석 통합
   - 종합된 개발 계획 수립

2. **작업 목록 생성**
   - TodoWrite로 Task 항목 생성
   - 의존성 그래프 기반으로 병렬 가능 작업 표시

3. **사용자 승인 요청** (필요 시)
   - AskUserQuestion으로 계획 승인

4. **Phase 3로 진행**

**Work 시스템**: `./scripts/work.sh next-phase W-XXX` (planning → development)

---

## Phase 3: 코드 구현 (조건부 병렬화)

**의존성 그래프를 기반으로 구현 순서를 결정합니다.**

### 의존성 그래프 분석

Phase 2a의 의존성 그래프를 사용하여:

1. **위상 정렬** (Topological Sort)
   - 의존성 순서대로 레벨 분류
   - 각 레벨 내 파일은 독립적

2. **레벨별 병렬 구현**
   - Level 0: 의존성 없는 파일 (병렬)
   - Level 1: Level 0에 의존하는 파일 (병렬)
   - Level 2: Level 1에 의존하는 파일 (병렬)
   - ...

### 순차 구현 (의존성 그래프 없는 경우)

```
Task tool 사용:
subagent_type: implement-code
model: sonnet
prompt: |
  [Phase 2 계획 내용 포함]

  위 계획에 따라 코드를 구현해주세요.

  필수 확인:
  - CLAUDE.md 규칙 준수
  - 기존 패턴 따르기
  - 에러 처리 포함

  완료 후 변경된 파일 목록과 주요 구현 내용을 보고해주세요.
```

### 병렬 구현 (의존성 그래프 있는 경우)

**예시: 3개 파일이 독립적인 경우**

```
# Level 0 파일들을 병렬로 구현
Task(subagent_type="implement-code", model="sonnet", prompt="[파일 A 구현]")
Task(subagent_type="implement-code", model="sonnet", prompt="[파일 B 구현]")
Task(subagent_type="implement-code", model="sonnet", prompt="[파일 C 구현]")

# Level 0 완료 대기
# Level 1 파일들 병렬 구현
Task(subagent_type="implement-code", model="sonnet", prompt="[파일 D 구현]")
...
```

**주의**: 병렬 구현 시 파일 충돌에 주의하세요. 독립적인 파일만 병렬로 구현합니다.

**구현 완료 후**: 결과를 확인하고 Phase 4로 진행

---

## Phase 4: 검증 및 테스트 (병렬)

**fail-fast 전략으로 3가지 검증을 병렬 실행합니다. 하나라도 실패 시 즉시 중단합니다.**

### 4a. 테스트 작성 및 실행 (write-tests)

```
Task tool 사용:
subagent_type: write-tests
model: sonnet
prompt: |
  TDD Red-Green-Refactor 사이클로 테스트를 작성해주세요.

  ### 1. Red (실패하는 테스트 작성)
  - 단위 테스트 (핵심 로직)
  - 경계값 테스트
  - 에러 케이스 테스트
  - 통합 테스트 (필요시)

  ### 2. Green (최소 구현으로 통과)
  - 테스트 실행 결과 확인
  - 모든 테스트 통과 확인

  ### 3. Refactor (개선)
  - 코드 중복 제거
  - 가독성 개선
  - 테스트 여전히 통과 확인

  ⚠️ 각 단계에서 커밋 지점 표시
```

### 4b. 코드 검증 (verify-code)

```
Task tool 사용:
subagent_type: verify-code
model: haiku
prompt: |
  구현된 코드를 검증해주세요.

  검증 항목:
  1. 빌드/컴파일 테스트
  2. 타입 체크 (mypy/tsc)
  3. 린트 검사 (ruff/eslint)
  4. Import/Export 정합성
  5. 함수 시그니처와 호출부 일치
  6. API 계약 준수
  7. 파일 경로 참조 유효성

  끊어진 연결이 있으면 상세히 보고해주세요.
```

### 4c. 보안 스캔 (security-scan)

```
Task tool 사용:
subagent_type: security-scan
model: sonnet
prompt: |
  보안 관점에서 코드를 스캔해주세요:

  1. 취약점 패턴 검사
     - SQL Injection
     - XSS
     - CSRF
     - Command Injection

  2. 민감 정보 노출 체크
     - 하드코딩된 비밀번호/토큰
     - API 키 노출
     - 개인정보 로깅

  3. 인증/권한 검증
     - 인증 우회 가능성
     - 권한 상승 가능성

  4. 입력 검증 확인
     - 사용자 입력 검증
     - 파일 업로드 검증
```

**Phase 4 완료 후**:

- ✅ **모두 통과** → Phase 5로 진행
- ❌ **하나라도 실패** → fix-bugs 에이전트로 수정 후 Phase 4 재실행
- ⚠️ **fail-fast**: 첫 번째 실패 감지 시 나머지 중단하고 즉시 수정

---

## Phase 5: 최종 리뷰 (review-code)

```
Task tool 사용:
subagent_type: review-code
model: opus
prompt: |
  구현 완료된 코드를 최종 리뷰해주세요.

  리뷰 관점:
  1. 정확성 - 의도대로 동작하는가?
  2. 가독성 - 이해하기 쉬운가?
  3. 유지보수성 - 변경하기 쉬운가?
  4. 보안 - 취약점이 없는가?
  5. 성능 - 병목이 없는가?

  Must Fix / Should Fix / Consider 로 분류해서 피드백해주세요.
```

**리뷰 결과에 따라**:

- ✅ Approve → Phase 6으로 진행
- 🔄 Request Changes → fix-bugs 에이전트로 수정 후 재리뷰

**Work 시스템**:

```bash
# Phase 3-4 구현/검증 완료, Phase 5 리뷰 완료 → validation 전환
./scripts/work.sh next-phase W-XXX  # development → validation

# Phase 6 완료 보고 후 → Work 완료
./scripts/work.sh complete W-XXX  # validation → completed
```

---

## Phase 6: 완료 보고

모든 단계 완료 후 다음을 보고:

### Work 정보 (Work 시스템 사용 시)

- **Work ID**: W-XXX
- **위치**: completed/W-XXX-{slug}.md
- **상태**: active → completed ✅
- **완료된 Phase**: planning, development, validation
- **실제 소요 시간**: [기록]

### 변경 요약

| 파일         | 유형           | 설명      |
| ------------ | -------------- | --------- |
| path/to/file | 생성/수정/삭제 | 변경 내용 |

### 주요 구현 내용

[핵심 변경사항]

### 검증 결과

- 빌드: ✅/❌
- 테스트: ✅/❌
- 린트: ✅/❌
- 통합: ✅/❌
- 리뷰: ✅ Approve / 🔄 Request Changes
- **Work 완료**: ✅ (Work 시스템 사용 시)

### 후속 작업

[추가로 필요한 작업이 있으면]

### 다음 단계

**일반 프로젝트:**

- 코드 커밋 및 푸시
- PR 생성 (필요시)

**Work 시스템 프로젝트:**

- ✅ 자동 완료됨 (`./scripts/work.sh complete W-XXX`)
- ✅ progress.md, decisions.md 병합됨
- ✅ completed/W-XXX-{slug}.md 생성됨
- 필요시 다음 Work 시작

---

## 에러 수정이 필요한 경우

```
Task tool 사용:
subagent_type: fix-bugs
model: sonnet
prompt: |
  다음 문제를 수정해주세요:

  [에러 내용 또는 리뷰 피드백]

  수정 후 변경 내용을 보고해주세요.
```

---

## 중단 조건

다음 상황에서는 중단하고 사용자에게 질문:

- 요구사항이 모호할 때
- 큰 아키텍처 변경이 필요할 때
- 보안 관련 결정이 필요할 때
- P0 모호함 발견 시 (데이터/결제/인증 관련)

---

## 관련 스킬

| 상황      | 스킬         |
| --------- | ------------ |
| 계획 필요 | `/plan-task` |
| 리뷰만    | `/review`    |
| 테스트만  | `/test`      |
| 디버깅    | `/debug`     |
