---
name: daily-report
description: |
  일간 요약 리포트를 생성합니다. Work 진행 상황, 에이전트 실행 내역,
  헬스체크 결과, 주요 이벤트를 종합하여 리포트를 생성합니다.
domain: common
invoke: /daily-report
---

# /daily-report - 일간 요약 리포트

일간 활동을 요약하여 팀에게 공유할 수 있는 리포트를 생성합니다.

---

## 사용법

```bash
/daily-report              # 오늘 리포트
/daily-report yesterday    # 어제 리포트
/daily-report 2026-01-30   # 특정 날짜 리포트
```

---

## 리포트 수집 항목

### 1. Work 진행 상황

```
📊 **Work 현황** (2026-01-30)
- 완료: 2개 (W-024, W-025)
- 진행 중: 1개 (W-026)
- 대기: 3개 (W-027, W-028, W-029)
```

**수집 방법:**

- `docs/works/active/` 폴더 스캔
- `docs/works/completed/` 최근 완료 항목
- 각 Work의 progress.md 파싱

### 2. 에이전트 실행 내역

```
🤖 **에이전트 활동**
- 총 실행: 45회
- 상위 에이전트:
  - implement-code: 15회
  - verify-code: 12회
  - review-code: 8회
- 평균 실행 시간: 2.3분
```

**수집 방법:**

- `~/.claude/logs/subagents/YYYY-MM-DD.jsonl` 파싱

### 3. 헬스체크 결과

```
🏥 **시스템 상태**
- 전체 상태: ✅ 정상
- 검사 횟수: 48회 (30분 간격)
- 경고: 2건 (Slack 응답 지연)
- 에러: 0건
```

**수집 방법:**

- `logs/health/YYYY-MM-DD.log` 파싱

### 4. 스케줄/이벤트 실행

```
⏰ **자동화 실행**
- 스케줄 실행: 5회
- 이벤트 트리거: 3회
- 실패: 0건
```

**수집 방법:**

- `logs/schedules/YYYY-MM-DD.log` 파싱
- `logs/events/YYYY-MM-DD.log` 파싱

### 5. 주요 변경사항

```
📝 **코드 변경**
- 커밋: 12개
- 변경 파일: 34개
- 추가: +1,234줄 / 삭제: -567줄
```

**수집 방법:**

- `git log --since="midnight"` 명령

---

## 리포트 템플릿

```markdown
# 📊 일간 리포트 (2026-01-30)

## Work 진행 상황

| 상태    | 개수 | 목록                |
| ------- | ---- | ------------------- |
| ✅ 완료 | 2    | W-024, W-025        |
| 🔄 진행 | 1    | W-026               |
| ⏳ 대기 | 3    | W-027, W-028, W-029 |

### 완료된 Work

- **W-025: Integration 도메인** - 4개 에이전트 구현

### 진행 중인 Work

- **W-026: Automation 도메인** - Phase 5 진행 중

## 에이전트 활동

- 총 실행: 45회
- 성공률: 98%
- 주요 사용: implement-code (15), verify-code (12)

## 시스템 상태

- 헬스체크: ✅ 정상 (48/48 통과)
- 경고: 2건 (Slack 응답 지연 - 해결됨)

## 자동화 실행

- 스케줄: 5회 실행 (100% 성공)
- 이벤트: 3회 트리거 (100% 성공)

## 코드 변경

- 커밋: 12개
- 변경 파일: 34개
- 라인: +1,234 / -567

---

_리포트 생성: 2026-01-30 18:00 KST_
```

---

## 리포트 발송

### Slack 발송

```bash
/daily-report --send slack
```

notify-team 에이전트를 통해 Slack으로 발송합니다.

### 파일 저장

```bash
/daily-report --save
```

`docs/reports/daily/YYYY-MM-DD.md`에 저장합니다.

### 둘 다

```bash
/daily-report --send slack --save
```

---

## 환경변수

| 변수              | 필수 | 설명                   |
| ----------------- | ---- | ---------------------- |
| DAILY_REPORT_SEND | 선택 | 자동 발송 채널         |
| DAILY_REPORT_SAVE | 선택 | 자동 저장 여부 (true)  |
| DAILY_REPORT_TIME | 선택 | 자동 생성 시간 (18:00) |

---

## 스케줄 연동

`schedules.json`에 등록하여 매일 자동 생성:

```json
{
  "id": "daily-report",
  "cron": "0 18 * * *",
  "description": "일간 리포트 생성 및 발송",
  "action": {
    "type": "skill",
    "target": "/daily-report",
    "args": "--send slack --save"
  },
  "enabled": true
}
```

---

## 연동 에이전트

| 에이전트      | 연동 방식        |
| ------------- | ---------------- |
| notify-team   | 리포트 발송      |
| schedule-task | 정기 실행        |
| health-check  | 상태 데이터 수집 |

---

## 관련 스킬

| 스킬     | 설명                 |
| -------- | -------------------- |
| /review  | 코드 리뷰 결과 포함  |
| /test    | 테스트 결과 포함     |
| /monitor | 모니터링 데이터 포함 |
