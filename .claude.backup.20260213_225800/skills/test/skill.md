---
name: test
description: 테스트를 실행하고 결과를 분석합니다.
model: sonnet
domain: common
argument-hint: [테스트 경로 또는 빈칸(전체)]
allowed-tools: Read, Bash, Glob, Grep, Task
---

# 테스트 실행

**즉시 실행하세요. 설명하지 말고 바로 실행합니다.**

대상: $ARGUMENTS

---

## 파이프라인 구조

```
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│ 테스트 실행  │ → │ verify-code  │ → │ fix-bugs     │
│ (Bash)       │   │ (haiku)      │   │ (sonnet)     │
└──────────────┘   └──────────────┘   └──────────────┘
                         │                    │
                         ▼                    │
                   실패 분석 필요 ─────────────┘
```

---

## 1단계: 프로젝트 타입 감지 및 테스트 실행

프로젝트에 맞는 테스트 명령 실행:

```bash
# Python 프로젝트
pytest $ARGUMENTS -v --tb=short

# Node.js 프로젝트
npm test $ARGUMENTS

# Go 프로젝트
go test $ARGUMENTS ./...

# Rust 프로젝트
cargo test $ARGUMENTS
```

---

## 2단계: 결과 검증

```
Task tool 사용:
subagent_type: verify-code
model: haiku
prompt: |
  테스트 결과를 분석해주세요:
  [테스트 실행 출력]

  분석 내용:
  - 총 테스트 수, 통과/실패/스킵 수
  - 커버리지 (있으면)
  - 실패한 테스트 목록 및 원인 분석
```

---

## 3단계: 실패 시 버그 수정

실패가 있으면 fix-bugs 에이전트로 수정:

```
Task tool 사용:
subagent_type: fix-bugs
model: sonnet
prompt: |
  다음 테스트 실패를 수정해주세요:
  [실패한 테스트 출력]

  각 실패에 대해:
  1. 실패한 테스트명
  2. 에러 메시지
  3. 예상 vs 실제 값
  4. 코드 수정
```

---

## 출력 형식

### 테스트 결과

| 항목      | 결과 |
| --------- | ---- |
| 총 테스트 | N개  |
| 통과      | N개  |
| 실패      | N개  |
| 스킵      | N개  |

### 실패 상세 (있으면)

[테스트별 원인과 수정 방안]

### 수정 결과 (실패 시)

[fix-bugs 에이전트 적용 결과]
