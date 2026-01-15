---
description: 테스트를 실행하고 결과를 분석합니다.
argument-hint: [테스트 경로 또는 빈칸(전체)]
allowed-tools: Read, Bash, Glob, Grep, Task
---

# 테스트 실행

**즉시 실행하세요. 설명하지 말고 바로 실행합니다.**

대상: $ARGUMENTS

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

## 2단계: 결과 분석

### 모두 통과 시
결과 요약:
- 총 테스트 수
- 실행 시간
- 커버리지 (있으면)

### 실패 있을 시
각 실패에 대해:
1. 실패한 테스트명
2. 에러 메시지
3. 예상 vs 실제 값
4. 수정 제안

## 3단계: 실패 시 자동 분석

실패가 있으면 Task tool로 분석:
```
subagent_type: general-purpose
prompt: |
  테스트 실패 분석:
  [실패한 테스트 출력]

  원인 파악 및 수정 방안 제시
```

---

## 출력 형식

### 테스트 결과
| 항목 | 결과 |
|------|------|
| 총 테스트 | N개 |
| 통과 | N개 |
| 실패 | N개 |
| 스킵 | N개 |

### 실패 상세 (있으면)
[테스트별 원인과 수정 방안]
