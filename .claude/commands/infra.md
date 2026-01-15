---
name: infra
description: |
  인프라 작업 전체 파이프라인. 탐색 → 계획 → 구현 → 검증 → 적용
  순서로 인프라 변경을 안전하게 수행합니다.
---

# /infra - 인프라 파이프라인

인프라 변경 작업의 전체 흐름을 자동화합니다.

## 사용법
```
/infra [작업 설명]
```

## 예시
```
/infra 새로운 웹 서버 인스턴스 추가
/infra VCN에 private subnet 추가
/infra OKE 클러스터 노드 3개로 확장
```

## 파이프라인 흐름

```
1. explore-infrastructure
   └→ 현재 인프라 상태 파악

2. plan-infrastructure
   └→ 변경 계획 수립 (리스크 분석 포함)

3. write-iac
   └→ Terraform 코드 작성

4. security-compliance
   └→ 보안 검사 (tfsec, checkov)

5. verify-infrastructure
   └→ terraform plan으로 검증

6. (사용자 승인)

7. deploy
   └→ terraform apply 실행
```

## 에이전트 순서

| 단계 | 에이전트 | 역할 |
|------|----------|------|
| 1 | explore-infrastructure | 현재 상태 파악 |
| 2 | plan-infrastructure | 변경 계획 |
| 3 | write-iac | IaC 코드 작성 |
| 4 | security-compliance | 보안 검사 |
| 5 | verify-infrastructure | Plan 검증 |
| 6 | deploy | 적용 |

## 주의사항
- 프로덕션 변경은 반드시 검증 후 진행
- 롤백 계획 확인 필수
- 다운타임 예상 시 공지 필요
