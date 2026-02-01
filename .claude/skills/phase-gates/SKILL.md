---
name: phase-gates
description: Phase 전환 자동화 및 게이트 검증. Planning, Development, Validation 단계 간 전환 조건 검증.
model: sonnet
allowed-tools: Read, Bash
---

# Phase Gate 스킬

Phase 간 전환 시 품질 게이트를 자동으로 검증합니다.

---

## Phase 구조

```
Phase 1: Planning
  ├─ clarify-requirements
  ├─ design-user-journey (Medium/Large만)
  └─ define-business-logic (Large만)
      │
      ▼ [Gate 1: P0 = 0]
      │
Phase 2: Development
  ├─ plan-implementation
  ├─ implement-code
  └─ write-tests
      │
      ▼ [Gate 2: 빌드 성공 + 테스트 통과]
      │
Phase 3: Validation
  ├─ verify-code
  ├─ verify-integration
  ├─ review-code
  └─ security-scan (필요시)
      │
      ▼ [Gate 3: Must Fix = 0]
      │
    ✅ COMPLETE
```

---

## Gate 1: Planning → Development

### 필수 조건

| 조건            | 검증 방법                 | 실패 시        |
| --------------- | ------------------------- | -------------- |
| P0 모호함 = 0   | clarify output의 p0_count | clarify 재호출 |
| 요구사항 문서화 | output 존재 확인          | clarify 재호출 |
| 구현 계획 존재  | plan-implementation 완료  | plan 호출      |

### 검증 로직

```yaml
gate_1:
  conditions:
    - field: clarify_output.p0_count
      operator: equals
      value: 0
    - field: clarify_output.status
      operator: in
      value: [complete, ready_for_planning]

  on_fail:
    action: delegate
    target: clarify-requirements
    message: "P0 모호함 해결 필요"

  on_pass:
    action: proceed
    target: plan-implementation
```

---

## Gate 2: Development → Validation

### 필수 조건

| 조건             | 검증 방법          | 실패 시       |
| ---------------- | ------------------ | ------------- |
| 빌드 성공        | verify-code output | fix-bugs 호출 |
| 타입 체크 통과   | mypy/tsc 결과      | fix-bugs 호출 |
| 린트 통과        | ruff/eslint 결과   | fix-bugs 호출 |
| 기본 테스트 통과 | pytest/jest 결과   | fix-bugs 호출 |

### 검증 로직

```yaml
gate_2:
  conditions:
    - field: verify_output.build_status
      operator: equals
      value: success
    - field: verify_output.type_check
      operator: equals
      value: pass
    - field: verify_output.lint
      operator: equals
      value: pass

  on_fail:
    action: delegate
    target: fix-bugs
    context: verify_output.errors
    then: self # Gate 2 재검증

  on_pass:
    action: proceed
    parallel:
      - review-code
      - security-scan # 선택적
```

---

## Gate 3: Validation → Complete

### 필수 조건

| 조건                   | 검증 방법       | 실패 시            |
| ---------------------- | --------------- | ------------------ |
| 리뷰 승인              | review output   | fix-bugs 후 재리뷰 |
| Must Fix = 0           | must_fix_count  | fix-bugs 후 재리뷰 |
| Critical 보안 이슈 = 0 | security output | fix-bugs 후 재스캔 |

### 검증 로직

```yaml
gate_3:
  conditions:
    - field: review_output.decision
      operator: equals
      value: approve
    - field: review_output.must_fix_count
      operator: equals
      value: 0
    - field: security_output.critical_count
      operator: equals
      value: 0
      optional: true # 보안 스캔 실행 안 했으면 무시

  on_fail:
    action: delegate
    target: fix-bugs
    context:
      - review_output.must_fix_items
      - security_output.critical_items
    then: gate_2 # Development → Validation 재실행

  on_pass:
    action: complete
    summary: true
```

---

## 사용 방법

메인 Claude가 Phase 전환 시 이 스킬의 조건을 확인합니다.

### 예시: Planning → Development 전환

```
1. clarify-requirements 완료
2. Gate 1 검증:
   - p0_count == 0? → ✅ 통과
   - status == complete? → ✅ 통과
3. plan-implementation 호출
```

### 예시: Development → Validation 전환

```
1. implement-code 완료
2. verify-code 실행
3. Gate 2 검증:
   - build_status == success? → ❌ 실패
4. fix-bugs 호출 (에러 컨텍스트 전달)
5. Gate 2 재검증
```

---

## 우회 조건

긴급한 경우 사용자가 Gate를 우회할 수 있습니다:

```yaml
bypass:
  requires: explicit_user_approval
  log: true
  warning: "품질 게이트가 우회되었습니다. 리스크를 감수합니다."
```

**우회 트리거:**

- 사용자가 "gate 우회" 또는 "강제 진행" 요청
- hotfix 상황에서 빠른 배포 필요

---

## 메트릭

| Gate   | 평균 통과율 | 평균 재시도 | 병목 원인       |
| ------ | ----------- | ----------- | --------------- |
| Gate 1 | 85%         | 1.2회       | P0 모호함       |
| Gate 2 | 70%         | 1.8회       | 타입 에러, 린트 |
| Gate 3 | 90%         | 1.1회       | Must Fix 이슈   |

---

## 관련 에이전트

| Phase       | 에이전트                                                         |
| ----------- | ---------------------------------------------------------------- |
| Planning    | clarify-requirements, design-user-journey, define-business-logic |
| Development | plan-implementation, implement-code, write-tests, fix-bugs       |
| Validation  | verify-code, verify-integration, review-code, security-scan      |

---

## 참고

- Phase Gate 패턴 상세: docs/architecture/phase-gate-pattern.md
- 에이전트 선택: docs/architecture/agent-selection-pattern.md
- 병렬화 설계: .claude/design/phase-parallelization.md
