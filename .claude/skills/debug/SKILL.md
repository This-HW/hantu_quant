---
name: debug
description: 에러를 분석하고 수정합니다. 에러 메시지나 로그를 입력하세요.
argument-hint: [에러 메시지 또는 설명]
allowed-tools: Read, Edit, Bash, Glob, Grep, Task, WebSearch
---

# 디버깅 실행

**즉시 실행하세요. 설명하지 말고 바로 실행합니다.**

에러 정보: $ARGUMENTS

---

## 파이프라인 구조

```
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│ diagnose     │ → │ fix-bugs     │ → │ verify-code  │
│ (opus)       │   │ (sonnet)     │   │ (haiku)      │
└──────────────┘   └──────────────┘   └──────────────┘
```

---

## 1단계: 에러 진단

```
Task tool 사용:
subagent_type: diagnose
model: opus
prompt: |
  다음 에러를 진단해주세요:
  $ARGUMENTS

  분석 내용:
  - 에러 유형 (문법/타입/런타임/빌드)
  - 파일 위치 및 라인 번호
  - 스택 트레이스 분석
  - 루트 원인 파악
  - 수정 방안 제안
```

---

## 2단계: 버그 수정

```
Task tool 사용:
subagent_type: fix-bugs
model: sonnet
prompt: |
  [diagnose 결과 포함]

  진단 결과를 바탕으로 버그를 수정해주세요.

  수정 원칙:
  - 최소 변경 원칙
  - exc_info=True 포함 (Python)
  - 에러 핸들링 추가 (필요시)
```

---

## 3단계: 수정 검증

```
Task tool 사용:
subagent_type: verify-code
model: haiku
prompt: |
  수정된 코드를 검증해주세요:
  [변경된 파일 목록]

  검증 항목:
  1. 빌드/컴파일 성공
  2. 타입 체크 통과
  3. 관련 테스트 통과
```

---

## 출력 형식

### 에러 분석

| 항목      | 내용                       |
| --------- | -------------------------- |
| 유형      | [타입/런타임/빌드/외부API] |
| 위치      | [파일:라인]                |
| 루트 원인 | [원인 설명]                |

### 수정 내용

[변경사항 diff 또는 설명]

### 검증 결과

[테스트/빌드 통과 여부]

### 예방 권장

[재발 방지를 위한 제안]
