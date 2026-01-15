---
description: 자동화된 개발 파이프라인 실행. 탐색 → 계획 → 구현 → 검증 → 리뷰 순으로 진행합니다.
argument-hint: [작업 설명]
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, Task, WebSearch, WebFetch, TodoWrite, AskUserQuestion
---

# 자동 개발 파이프라인 실행

**즉시 실행하세요. 설명하지 말고 바로 실행합니다.**

사용자 요청: $ARGUMENTS

---

## 파이프라인 구조

```
┌─────────┐   ┌─────────┐   ┌─────────┐   ┌───────────┐   ┌──────────┐   ┌─────────┐
│ 탐색    │ → │ 계획    │ → │ 구현    │ → │ 코드 검증 │ → │ 통합 검증│ → │ 리뷰    │
│ Explore │   │ Plan    │   │ general │   │ general   │   │ general  │   │ general │
└─────────┘   └─────────┘   └─────────┘   └───────────┘   └──────────┘   └─────────┘
```

**중요**: 각 단계 완료 후 결과를 확인하고 다음 단계 에이전트를 직접 호출해야 합니다.
Subagent는 다른 subagent를 호출할 수 없으므로 Main Claude가 순차적으로 오케스트레이션합니다.

---

## Phase 1: 탐색 (즉시 실행)

```
Task tool 사용:
subagent_type: Explore
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

## Phase 2: 계획

```
Task tool 사용:
subagent_type: Plan
prompt: |
  [탐색 결과 요약 포함]

  다음 구현 계획을 수립해주세요:
  1. 작업 분해 (단계별)
  2. 파일별 변경 내용
  3. 구현 순서와 의존성
  4. 리스크 분석
```

**계획 완료 후**:
- TodoWrite로 작업 목록 생성
- AskUserQuestion으로 사용자 승인 요청
- 승인 후 Phase 3로 진행

---

## Phase 3: 구현

```
Task tool 사용:
subagent_type: general-purpose
prompt: |
  [계획 내용 포함]

  위 계획에 따라 코드를 구현해주세요.

  필수 확인:
  - CLAUDE.md 규칙 준수
  - 기존 패턴 따르기
  - 에러 처리 포함

  완료 후 변경된 파일 목록과 주요 구현 내용을 보고해주세요.
```

**구현 완료 후**: 결과를 확인하고 Phase 4로 진행

---

## Phase 4: 코드 검증

```
Task tool 사용:
subagent_type: general-purpose
prompt: |
  방금 구현된 코드를 검증해주세요.

  검증 항목:
  1. 빌드/컴파일 테스트
  2. 타입 체크 (mypy/tsc)
  3. 린트 검사 (ruff/eslint)
  4. 단위 테스트 실행

  에러 발생 시 상세 내용과 수정 방안을 제시해주세요.
```

**검증 결과에 따라**:
- ✅ 통과 → Phase 5로 진행
- ❌ 실패 → 에러 수정 후 재검증

---

## Phase 5: 통합 검증

```
Task tool 사용:
subagent_type: general-purpose
prompt: |
  구현된 코드의 통합 무결성을 검증해주세요.

  검증 항목:
  1. Import/Export 정합성
  2. 함수 시그니처와 호출부 일치
  3. API 계약 준수
  4. 파일 경로 참조 유효성

  끊어진 연결이 있으면 상세히 보고해주세요.
```

**검증 결과에 따라**:
- ✅ 통과 → Phase 6으로 진행
- ❌ 실패 → 연결 수정 후 재검증

---

## Phase 6: 코드 리뷰

```
Task tool 사용:
subagent_type: general-purpose
prompt: |
  구현 완료된 코드를 리뷰해주세요.

  리뷰 관점:
  1. 정확성 - 의도대로 동작하는가?
  2. 가독성 - 이해하기 쉬운가?
  3. 유지보수성 - 변경하기 쉬운가?
  4. 보안 - 취약점이 없는가?

  Must Fix / Should Fix / Consider 로 분류해서 피드백해주세요.
```

---

## Phase 7: 완료 보고

모든 단계 완료 후 다음을 보고:

### 변경 요약
| 파일 | 유형 | 설명 |
|------|------|------|
| path/to/file | 생성/수정/삭제 | 변경 내용 |

### 주요 구현 내용
[핵심 변경사항]

### 검증 결과
- 빌드: ✅/❌
- 테스트: ✅/❌
- 린트: ✅/❌
- 통합: ✅/❌
- 리뷰: ✅ Approve / 🔄 Request Changes

### 후속 작업
[추가로 필요한 작업이 있으면]

---

## 중단 조건

다음 상황에서는 중단하고 사용자에게 질문:
- 요구사항이 모호할 때
- 큰 아키텍처 변경이 필요할 때
- 보안 관련 결정이 필요할 때
- P0 모호함 발견 시 (데이터/결제/인증 관련)
