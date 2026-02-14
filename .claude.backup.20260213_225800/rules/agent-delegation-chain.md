# 에이전트 자동 위임 체인 규칙

> 이 규칙은 메인 Claude가 서브에이전트 결과를 받은 후 자동으로 다음 에이전트를 호출하도록 합니다.

---

## 핵심 원칙

**서브에이전트는 다른 서브에이전트를 호출할 수 없습니다.**
따라서 메인 Claude가 위임 체인을 직접 관리해야 합니다.

---

## 위임 신호 감지

서브에이전트 결과에서 **DELEGATION_SIGNAL** 블록을 감지하면 자동으로 다음 행동을 수행합니다.

### 표준 신호 형식

```
---DELEGATION_SIGNAL---
TYPE: [신호 유형]
TARGET: [대상 에이전트 - 해당 시]
REASON: [이유]
CONTEXT: [전달할 컨텍스트]
---END_SIGNAL---
```

### 신호 유형별 행동

| TYPE | 행동 |
|------|------|
| `NEED_USER_INPUT` | AskUserQuestion으로 사용자에게 QUESTIONS 항목 질문 |
| `NEED_CLARIFICATION` | clarify-requirements 에이전트 선택/호출 |
| `DELEGATE_TO` | TARGET 에이전트 선택/호출 (CONTEXT 전달) |
| `JOURNEY_COMPLETE` | define-business-logic 또는 plan-implementation으로 진행 |
| `BUSINESS_LOGIC_COMPLETE` | plan-implementation으로 진행 |
| `PLANNING_COMPLETE` | 사용자에게 결과 보고, 구현 준비 완료 |

### 레거시 패턴 (하위 호환)

```
1. "→ Planning/clarify-requirements" 또는 "clarify-requirements 필요"
2. "→ Planning/design-user-journey" 또는 "사용자 여정 설계 필요"
3. "→ Planning/define-business-logic" 또는 "비즈니스 규칙 정의 필요"
4. "→ Dev/plan-implementation" 또는 "구현 계획 필요"
5. "P0 모호함" + "사용자 확인 필요"
```

---

## 자동 위임 행동

### 패턴 1: P0 모호함 발견

```
에이전트 결과에 "P0 모호함" + 질문 목록이 있으면:
1. 사용자에게 AskUserQuestion으로 질문
2. 답변 받은 후 동일 에이전트 재호출 (또는 다음 에이전트)
```

### 패턴 2: 다른 Planning 에이전트 필요

```
에이전트 결과에 "→ Planning/[에이전트명]" 패턴이 있으면:
1. 현재 결과를 컨텍스트로 포함
2. 해당 에이전트를 Task로 호출
3. 결과 종합
```

### 패턴 3: Dev 위임 준비 완료

```
에이전트 결과에 "구현 준비 완료" 또는 "→ Dev/plan-implementation" 있으면:
1. Planning 결과를 요약
2. Dev/plan-implementation 에이전트 호출
3. 구현 계획 수립
```

---

## 위임 체인 예시

### Large 규모 작업 체인

```
사용자 요청: "포인트 시스템 추가해줘"
     │
     ▼
[Plan 에이전트] → P0 모호함 8개 발견
     │
     ▼
[메인 Claude] → AskUserQuestion으로 P0 질문
     │
     ▼
[사용자 답변] → P0 해결됨
     │
     ▼
[메인 Claude] → design-user-journey 호출 (자동)
     │
     ▼
[design-user-journey] → 여정 설계 완료, 비즈니스 규칙 필요
     │
     ▼
[메인 Claude] → define-business-logic 호출 (자동)
     │
     ▼
[define-business-logic] → 규칙 정의 완료
     │
     ▼
[메인 Claude] → 결과 종합 → 사용자에게 보고
```

---

## 메인 Claude 행동 규칙

### 서브에이전트 결과 수신 후

1. **위임 신호 스캔**: 결과에서 위임 패턴 탐지
2. **P0 확인**: P0 모호함이 있으면 사용자 질문 우선
3. **자동 연계**: 위임 대상이 명시되어 있으면 자동 호출
4. **결과 종합**: 체인 완료 후 사용자에게 요약 보고

### 자동 호출 시 컨텍스트 전달

```
Task 호출 시 prompt에 포함할 내용:
1. 원래 사용자 요청
2. 이전 에이전트 결과 요약
3. 해결된 P0 항목 (있으면)
4. 현재 에이전트에게 요청하는 구체적 작업
```

---

## 위임 중단 조건

다음 경우 자동 위임을 중단하고 사용자에게 보고:

1. **P0 미해결**: 사용자 답변이 필요한 P0가 남아있음
2. **순환 감지**: 동일 에이전트가 2회 이상 호출됨
3. **명시적 완료**: "Planning 완료" 또는 "구현 준비 완료" 신호
4. **오류 발생**: 에이전트 실행 실패

---

## 구현 참고

이 규칙은 메인 Claude의 행동을 가이드합니다.
실제 구현은 메인 Claude가 에이전트 결과를 분석하고 판단합니다.

### 권장 패턴

```python
# 의사 코드
result = call_agent("Plan", user_request)

while has_delegation_signal(result):
    if has_p0_ambiguity(result):
        answer = ask_user(extract_p0_questions(result))
        result = call_agent("Plan", user_request + answer)

    elif needs_journey_design(result):
        result = call_agent("design-user-journey", summarize(result))

    elif needs_business_logic(result):
        result = call_agent("define-business-logic", summarize(result))

    elif ready_for_implementation(result):
        result = call_agent("plan-implementation", summarize(result))
        break

report_to_user(result)
```
