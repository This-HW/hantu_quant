---
name: infra
description: 인프라 작업 파이프라인. 탐색 → 계획 → 구현 → 검증 → 적용 순서로 진행합니다.
argument-hint: [작업 설명]
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, Task, AskUserQuestion
---

# 인프라 작업 실행

**즉시 실행하세요. 설명하지 말고 바로 실행합니다.**

작업 요청: $ARGUMENTS

---

## 파이프라인 구조

```
┌──────────────────┐   ┌──────────────────┐   ┌──────────────┐
│ explore-         │ → │ plan-            │ → │ write-iac    │
│ infrastructure   │   │ infrastructure   │   │ (sonnet)     │
│ (haiku)          │   │ (sonnet)         │   │              │
└──────────────────┘   └──────────────────┘   └──────────────┘
                                                     │
┌──────────────────┐   ┌──────────────────┐          │
│ verify-          │ ← │ security-        │ ←────────┘
│ infrastructure   │   │ compliance       │
│ (haiku)          │   │ (sonnet)         │
└──────────────────┘   └──────────────────┘
```

---

## 1단계: 인프라 탐색

```
Task tool 사용:
subagent_type: explore-infrastructure
model: haiku
prompt: |
  현재 인프라 상태를 파악해주세요.

  탐색 항목:
  - 클라우드 리소스 현황 (OCI/AWS/GCP)
  - Terraform 상태 (terraform state list)
  - 기존 IaC 코드 구조
  - 의존성 관계
```

---

## 2단계: 변경 계획 수립

```
Task tool 사용:
subagent_type: plan-infrastructure
model: sonnet
prompt: |
  [탐색 결과 포함]
  작업 요청: $ARGUMENTS

  다음을 수립해주세요:
  - 변경 내용 상세
  - 리스크 분석 (영향 범위, 대응책)
  - 롤백 계획
  - 작업 순서
```

---

## 3단계: IaC 코드 작성

```
Task tool 사용:
subagent_type: write-iac
model: sonnet
prompt: |
  [계획 결과 포함]

  Terraform/Pulumi 코드를 작성해주세요.

  코드 작성 원칙:
  - 모듈화된 구조
  - 변수화된 설정
  - 적절한 태깅
  - 주석 포함
```

---

## 4단계: 보안 검사

```
Task tool 사용:
subagent_type: security-compliance
model: sonnet
prompt: |
  [작성된 IaC 코드 포함]

  보안 검사를 수행해주세요:
  - tfsec 분석
  - checkov 검사
  - 정책 준수 확인
  - 취약점 식별
```

---

## 5단계: 검증

```
Task tool 사용:
subagent_type: verify-infrastructure
model: haiku
prompt: |
  [IaC 코드 포함]

  인프라 코드를 검증해주세요:
  - terraform fmt -check
  - terraform validate
  - terraform plan -out=tfplan
  - Plan 결과 분석
```

---

## 6단계: 사용자 승인 요청

Plan 결과 보여주고 AskUserQuestion으로 승인 요청

---

## 7단계: 적용 (승인 후)

```bash
terraform apply tfplan
```

---

## 출력 형식

### 변경 계획

[추가/수정/삭제될 리소스 목록]

### 검증 결과

[Plan 결과 요약]

### 적용 결과

[성공/실패 및 상세]
