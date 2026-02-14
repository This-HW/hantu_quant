---
name: infra
description: 인프라 작업 파이프라인. 탐색 → 계획 → 구현 → 검증 → 적용 순서로 진행합니다.
argument-hint: [작업 설명]
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, Task
---

# 인프라 작업 실행

**즉시 실행하세요. 설명하지 말고 바로 실행합니다.**

작업 요청: $ARGUMENTS

---

## 1단계: 현재 상태 파악 (즉시 실행)

```bash
# OCI 리소스 확인
oci compute instance list --compartment-id $COMPARTMENT_ID

# 또는 Terraform 상태 확인
terraform state list
terraform show
```

## 2단계: 변경 계획 수립

### 변경 내용
[무엇을 변경하는지]

### 리스크 분석
| 리스크 | 영향 | 대응 |
|--------|------|------|
| [예상 리스크] | [영향 범위] | [대응책] |

### 롤백 계획
[실패 시 복구 방법]

## 3단계: IaC 코드 작성/수정

```hcl
# Terraform 코드 예시
resource "oci_core_instance" "example" {
  # 설정...
}
```

## 4단계: 검증

```bash
# 문법 검사
terraform fmt -check
terraform validate

# 보안 검사 (있으면)
tfsec .

# Plan 확인
terraform plan -out=tfplan
```

## 5단계: 사용자 승인 요청

Plan 결과 보여주고 승인 요청 (AskUserQuestion)

## 6단계: 적용 (승인 후)

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
