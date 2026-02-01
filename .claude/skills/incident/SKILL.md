---
name: incident
description: 인시던트 대응 파이프라인. 복구 최우선으로 대응 → 복구 → 분석 순으로 진행합니다.
model: sonnet
argument-hint: [상황 설명]
allowed-tools: Read, Bash, Glob, Grep, Task, WebSearch
---

# 인시던트 대응 실행

**즉시 실행하세요. 복구가 먼저입니다!**

상황: $ARGUMENTS

---

## 파이프라인 구조

```
┌──────────────────┐   ┌──────────────┐   ┌──────────────┐
│ respond-incident │ → │ rollback     │ → │ monitor      │
│ (sonnet)         │   │ (sonnet)     │   │ (haiku)      │
└──────────────────┘   └──────────────┘   └──────────────┘
        │                    │                   │
        ▼                    ▼                   ▼
   즉각 대응            복구 실행          안정화 확인
                                                 │
                                          ┌──────────────┐
                                          │ postmortem   │
                                          │ (opus)       │
                                          └──────────────┘
```

---

## 1단계: 인시던트 대응 시작

```
Task tool 사용:
subagent_type: respond-incident
model: sonnet
prompt: |
  인시던트가 발생했습니다: $ARGUMENTS

  즉시 다음을 수행해주세요:

  ### 심각도 판단
  | 심각도 | 증상 | 대응 |
  |--------|------|------|
  | **SEV1** | 서비스 전체 다운 | 즉시 롤백 |
  | **SEV2** | 주요 기능 장애 | 15분 내 복구 |
  | **SEV3** | 부분 기능 저하 | 1시간 내 대응 |

  ### 상황 파악
  - 서비스 상태 확인
  - 최근 로그 확인
  - 에러 로그 확인
```

---

## 2단계: 롤백 (SEV1/SEV2)

```
Task tool 사용:
subagent_type: rollback
model: sonnet
prompt: |
  [인시던트 상황 포함]

  롤백을 수행해주세요:
  - 이전 버전으로 복구
  - 롤백 방법 선택 (git/docker/k8s)
  - 롤백 후 헬스체크
```

---

## 3단계: 안정화 모니터링

```
Task tool 사용:
subagent_type: monitor
model: haiku
prompt: |
  복구 후 안정화를 확인해주세요.

  확인 항목:
  - 헬스체크 상태
  - 에러율 추이 (5분간)
  - 리소스 사용량
  - 사용자 요청 처리 정상 여부
```

---

## 4단계: 사후 분석 (안정화 후)

```
Task tool 사용:
subagent_type: postmortem
model: opus
prompt: |
  [인시던트 전체 타임라인 포함]

  Postmortem 문서를 작성해주세요:
  1. 인시던트 타임라인
  2. 근본 원인 분석 (5 Whys)
  3. 영향 범위
  4. 대응 내역
  5. 재발 방지 대책
  6. 액션 아이템
```

---

## 출력 형식

### 인시던트 요약

| 항목      | 내용       |
| --------- | ---------- |
| 심각도    | SEV[1/2/3] |
| 증상      | [증상]     |
| 원인      | [원인]     |
| 복구 시간 | [N분]      |

### 대응 내역

[수행한 조치들]

### 후속 조치

[필요한 작업]
