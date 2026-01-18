# Model Selection Guide

## 모델 특성

| 모델 | 강점 | 약점 | 비용 |
|------|------|------|------|
| `opus` | 복잡한 추론, 아키텍처, 심층 분석 | 느림, 비쌈 | 높음 |
| `sonnet` | 균형잡힌 성능, 코딩 최적화 | 중간 | 중간 |
| `haiku` | 빠른 실행, 단순 작업 | 복잡한 추론 약함 | 낮음 |
| `inherit` | 부모 대화 모델 사용 | - | 가변 |

## 작업별 권장 모델

### Opus 권장 (11개 유형)

**전략적 사고가 필요한 작업:**
- 요구사항 분석 (clarify-requirements)
- 사용자 여정 설계 (design-user-journey)
- 비즈니스 로직 정의 (define-business-logic)
- 구현 계획 (plan-implementation)
- 리팩토링 계획 (plan-refactor)
- 인프라 계획 (plan-infrastructure)
- 코드 리뷰 (review-code)
- 보안 스캔 (security-scan)
- 보안 컴플라이언스 (security-compliance)
- 장애 진단 (diagnose)
- 사후 분석 (postmortem)

### Sonnet 권장 (9개 유형)

**코드 작성/수정 작업:**
- 코드 구현 (implement-code)
- 버그 수정 (fix-bugs)
- 테스트 작성 (write-tests)
- IaC 작성 (write-iac)
- 컨테이너 설정 (setup-containers)
- CI/CD 설정 (configure-cicd)
- 배포 (deploy)
- 인시던트 대응 (respond-incident)
- 외부 조사 (research-external)

### Haiku 권장 (11개 유형)

**빠른 실행/단순 작업:**
- 코드베이스 탐색 (explore-codebase)
- 인프라 탐색 (explore-infrastructure)
- 코드 검증 (verify-code)
- 통합 검증 (verify-integration)
- 인프라 검증 (verify-infrastructure)
- 구조 강제 (enforce-structure)
- 의존성 분석 (analyze-dependencies)
- 모니터링 (monitor)
- 스케일링 (scale)
- 롤백 (rollback)
- 문서 동기화 (sync-docs)

## 결정 플로우차트

```
작업이 복잡한 추론을 필요로 하는가?
├── Yes → 아키텍처/전략 결정인가?
│         ├── Yes → opus
│         └── No → 코드 구현/수정인가?
│                   ├── Yes → sonnet
│                   └── No → opus
└── No → 단순 탐색/검증인가?
          ├── Yes → haiku
          └── No → 일관성이 중요한가?
                    ├── Yes → inherit
                    └── No → sonnet
```

## 비용 최적화 팁

1. **탐색 작업은 haiku**: 파일 검색, 패턴 매칭 등
2. **구현은 sonnet**: 코드 작성, 수정
3. **중요 결정은 opus**: 아키텍처, 보안, 리뷰
4. **일관성 필요시 inherit**: 대화 흐름 유지
