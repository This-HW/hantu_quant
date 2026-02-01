---
name: deploy
description: 배포 파이프라인. 검증 → 배포 → 모니터링 순서로 진행합니다.
model: sonnet
argument-hint: [대상] [환경] (예: app staging, infra production)
allowed-tools: Read, Bash, Glob, Grep, Task
---

# 배포 실행

**즉시 실행하세요. 설명하지 말고 바로 실행합니다.**

배포 대상: $ARGUMENTS

---

## 파이프라인 구조

```
┌─────────────────┐   ┌──────────────┐   ┌──────────────┐
│ verify-code     │ → │ deploy       │ → │ monitor      │
│ (haiku)         │   │ (sonnet)     │   │ (haiku)      │
└─────────────────┘   └──────────────┘   └──────────────┘
        │                    │                   │
        ▼                    ▼                   ▼
   사전 검증 통과       배포 실행         배포 후 확인
        │                    │                   │
        └────────────────────┴───────────────────┘
                             │
                      실패 시 rollback
```

---

## 1단계: 대상 파악

$ARGUMENTS 분석:

- `app` → 애플리케이션 배포
- `infra` → 인프라 배포
- 환경: `staging` | `production`

---

## 2단계: 사전 검증

```
Task tool 사용:
subagent_type: verify-code
model: haiku
prompt: |
  배포 전 검증을 수행해주세요.

  ### 애플리케이션 배포 시
  - 빌드 확인: npm run build / go build / docker build
  - 테스트 확인: npm test / pytest / go test

  ### 인프라 배포 시
  - terraform plan 확인
  - 보안 검사 (tfsec / checkov)

  배포 가능 여부를 판단해주세요.
```

---

## 3단계: 배포 실행

```
Task tool 사용:
subagent_type: deploy
model: sonnet
prompt: |
  다음 배포를 실행해주세요:
  - 대상: [app/infra]
  - 환경: [staging/production]

  배포 전략:
  - Blue-Green / Canary / Rolling 중 선택
  - 롤백 계획 수립

  ### 앱 배포
  - Docker 기반: docker-compose up -d
  - 또는 직접 실행: systemctl restart [서비스명]

  ### 인프라 배포
  - terraform apply tfplan
```

---

## 4단계: 배포 후 모니터링

```
Task tool 사용:
subagent_type: monitor
model: haiku
prompt: |
  배포 후 상태를 확인해주세요.

  검증 항목:
  - 헬스체크: curl -f http://localhost:[port]/health
  - 로그 확인: 에러 로그 모니터링
  - 리소스 사용량: CPU, Memory 확인

  이상 징후 발견 시 롤백 권고
```

---

## 5단계: 롤백 (실패 시)

```
Task tool 사용:
subagent_type: rollback
model: sonnet
prompt: |
  배포 실패로 롤백을 수행해주세요.

  - 이전 버전으로 복구
  - 롤백 후 헬스체크
  - 원인 분석 요청
```

---

## 출력 형식

### 배포 결과

| 항목 | 상태                 |
| ---- | -------------------- |
| 대상 | [app/infra]          |
| 환경 | [staging/production] |
| 결과 | [성공/실패]          |

### 검증 결과

[헬스체크, 로그 확인 결과]

### 롤백 안내 (실패 시)

[롤백 방법 안내]
