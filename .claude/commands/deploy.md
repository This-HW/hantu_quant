---
name: deploy
description: |
  배포 파이프라인. 애플리케이션 또는 인프라를 안전하게 배포합니다.
  검증 → 배포 → 모니터링 순서로 진행합니다.
---

# /deploy - 배포 파이프라인

안전한 배포를 위한 자동화된 흐름입니다.

## 사용법
```
/deploy [대상] [환경]
```

## 예시
```
/deploy app staging
/deploy infra production
/deploy app production --canary
```

## 파이프라인 흐름

### 애플리케이션 배포
```
1. verify-code (Dev)
   └→ 빌드/테스트 확인

2. verify-integration (Dev)
   └→ 연결 무결성 확인

3. deploy (Ops)
   └→ 배포 실행

4. monitor (Ops)
   └→ 배포 후 모니터링
```

### 인프라 배포
```
1. verify-infrastructure (Infra)
   └→ terraform plan 확인

2. security-compliance (Infra)
   └→ 보안 검사

3. deploy (Ops)
   └→ terraform apply

4. monitor (Ops)
   └→ 적용 후 모니터링
```

## 배포 전략 옵션
| 옵션 | 설명 |
|------|------|
| `--rolling` | 점진적 교체 (기본) |
| `--blue-green` | 전체 교체 |
| `--canary` | 일부만 먼저 |

## 실패 시 자동 대응
- 헬스체크 실패 → 자동 롤백
- 에러율 급증 → 알림 + 롤백 권고
