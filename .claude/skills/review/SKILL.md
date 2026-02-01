---
name: review
description: 현재 변경사항 또는 지정된 파일에 대한 코드 리뷰를 수행합니다.
model: opus
argument-hint: [파일 경로 또는 빈칸(git diff)]
allowed-tools: Read, Glob, Grep, Bash, Task
---

# 코드 리뷰 실행

**즉시 실행하세요. 설명하지 말고 바로 실행합니다.**

## 파이프라인 구조

```
┌──────────────┐   ┌──────────────┐   ┌───────────────┐
│ 리뷰 대상    │ → │ review-code  │ → │ security-scan │
│ 파악 (Main)  │   │ (opus)       │   │ (sonnet)      │
└──────────────┘   └──────────────┘   └───────────────┘
```

---

## 1단계: 리뷰 대상 파악

$ARGUMENTS가 있으면:

- 해당 파일/디렉토리를 읽어서 리뷰

$ARGUMENTS가 없으면:

- `git diff HEAD`로 변경사항 확인
- 변경사항이 없으면 `git diff HEAD~1`로 마지막 커밋 확인

---

## 2단계: 코드 리뷰 실행

```
Task tool 사용:
subagent_type: review-code
model: opus
prompt: |
  다음 코드를 리뷰해주세요:
  [1단계에서 확인한 코드/diff]

  리뷰 형식:
  ## 전체 평가: [A/B/C/D/F]

  ## Critical (즉시 수정 필요)
  ## Warning (권장 수정)
  ## Suggestion (개선 제안)

  ## 권장 조치
```

---

## 3단계: 보안 검토 (해당 시)

코드가 다음을 포함하면 보안 검토도 실행:

- 인증/인가, 사용자 입력, API, DB 쿼리

```
Task tool 사용:
subagent_type: security-scan
model: sonnet
prompt: |
  다음 코드의 보안 취약점을 검사해주세요:
  [대상 코드]

  검사 항목:
  - OWASP Top 10 취약점
  - 인증/인가 로직
  - 입력 검증
  - SQL 인젝션
  - XSS
```

---

## 4단계: 결과 요약

리뷰 결과를 사용자에게 요약 보고

### 리뷰 결과

| 항목       | 결과        |
| ---------- | ----------- |
| 전체 평가  | [A/B/C/D/F] |
| Critical   | [N개]       |
| Warning    | [N개]       |
| Suggestion | [N개]       |
| 보안 이슈  | [N개]       |

### 수정 필요 사항

[Critical/Warning 항목 목록]
