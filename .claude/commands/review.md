---
description: 현재 변경사항 또는 지정된 파일에 대한 코드 리뷰를 수행합니다.
argument-hint: [파일 경로 또는 빈칸(git diff)]
allowed-tools: Read, Glob, Grep, Bash, Task
---

# 코드 리뷰

대상: $ARGUMENTS

---

## 리뷰 대상 확인

인자가 없으면 최근 git 변경사항을 리뷰합니다:
```bash
git diff HEAD
```

인자가 있으면 해당 파일/디렉토리를 리뷰합니다.

---

## 실행

### 1단계: 코드 리뷰
`review-code` subagent를 사용하여:
- 코드 품질 검토
- 베스트 프랙티스 확인
- 개선점 식별

### 2단계: 보안 검토 (선택)
변경이 다음을 포함하면 `security-scan` subagent도 실행:
- 인증/인가 관련 코드
- 사용자 입력 처리
- API 엔드포인트
- 데이터베이스 쿼리

---

## 출력 형식

### 리뷰 요약
- 검토 범위: [파일 수, 라인 수]
- 전체 평가: [A/B/C/D/F]

### 피드백
[Critical → Warning → Suggestion 순으로]

### 권장 조치
[우선순위순 개선사항]
