---
name: debug
description: 에러를 분석하고 수정합니다. 에러 메시지나 로그를 입력하세요.
model: sonnet
argument-hint: [에러 메시지 또는 설명]
allowed-tools: Read, Edit, Bash, Glob, Grep, Task, WebSearch
---

# 디버깅 실행

> 4-Phase Debugging (Superpowers 패턴)
> Reproduce → Isolate → Fix → Verify

**즉시 실행하세요. 설명하지 말고 바로 실행합니다.**

에러 정보: $ARGUMENTS

---

## 파이프라인 구조

```
┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│ Phase 1      │ → │ Phase 2      │ → │ Phase 3      │ → │ Phase 4      │
│ Reproduce    │   │ Isolate      │   │ Fix          │   │ Verify       │
│ (재현)       │   │ (격리)       │   │ (수정)       │   │ (검증)       │
└──────────────┘   └──────────────┘   └──────────────┘   └──────────────┘
      │                    │                  │                  │
      └──── diagnose ──────┘        fix-bugs ─┘      verify-code ┘
           (opus)                   (sonnet)          (haiku)
```

---

## Phase 1-2: 재현 및 격리 (Reproduce + Isolate)

```
Task tool 사용:
subagent_type: diagnose
model: opus
prompt: |
  다음 에러를 진단해주세요:
  $ARGUMENTS

  ### Phase 1: Reproduce (재현)
  - 에러를 재현하는 최소 단계 식별
  - 재현 조건 및 환경 확인
  - 에러 발생 빈도 (항상/간헐적)

  ### Phase 2: Isolate (격리)
  - 에러 유형 (문법/타입/런타임/빌드/외부API)
  - 파일 위치 및 라인 번호
  - 스택 트레이스 분석
  - 루트 원인 파악
  - 영향 범위 (단일 함수/모듈/시스템 전체)

  ### 수정 방안 제안
  - 옵션 A: [빠른 수정]
  - 옵션 B: [근본 해결]
```

---

## Phase 3: 수정 (Fix)

```
Task tool 사용:
subagent_type: fix-bugs
model: sonnet
prompt: |
  [diagnose 결과 포함]

  진단 결과를 바탕으로 버그를 수정해주세요.

  수정 원칙:
  - 최소 변경 원칙
  - exc_info=True 포함 (Python 로깅)
  - 에러 핸들링 추가 (필요시)
  - 같은 패턴의 버그가 다른 곳에 없는지 확인
```

---

## Phase 4: 검증 (Verify)

```
Task tool 사용:
subagent_type: verify-code
model: haiku
prompt: |
  수정된 코드를 검증해주세요:
  [변경된 파일 목록]

  검증 항목:
  1. 에러 재현 → 해결 확인
  2. 빌드/컴파일 성공
  3. 타입 체크 통과
  4. 관련 테스트 통과
  5. 엣지 케이스 확인
```

---

## 출력 형식

### Phase 1-2: 재현 및 격리

| 항목      | 내용                       |
| --------- | -------------------------- |
| 유형      | [타입/런타임/빌드/외부API] |
| 위치      | [파일:라인]                |
| 재현 조건 | [최소 재현 단계]           |
| 루트 원인 | [원인 설명]                |
| 영향 범위 | [함수/모듈/시스템]         |

### Phase 3: 수정

[변경사항 diff 또는 설명]

### Phase 4: 검증

[테스트/빌드 통과 여부]

### 예방 권장

[재발 방지를 위한 제안]

- 테스트 추가
- 타입 강화
- 에러 핸들링 개선
