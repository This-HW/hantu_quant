---
description: 자동화된 개발 파이프라인 실행. 탐색 → 계획 → 구현 → 검증 → 리뷰 순으로 진행합니다.
argument-hint: [작업 설명]
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, Task, WebSearch, WebFetch
---

# 자동화된 개발 파이프라인

사용자 요청: $ARGUMENTS

---

## 실행 순서

다음 순서로 subagent들을 활용하여 작업을 완료하세요:

### Phase 1: 탐색
`explore-codebase` subagent를 사용하여:
- 프로젝트 구조 분석
- 관련 파일 식별
- 기존 패턴 파악

### Phase 2: 계획
`plan-implementation` subagent를 사용하여:
- 구현 전략 수립
- 작업 분해 (병렬 가능한 것 식별)
- 리스크 분석

**중요**: 계획 완료 후 사용자에게 승인을 요청하세요.

### Phase 3: 구현
승인 후 `implement-code` subagent를 사용하여:
- 계획에 따라 코드 작성
- 기존 컨벤션 준수
- 에러 처리 포함

### Phase 4: 검증
`verify-code` subagent를 사용하여:
- 린트 검사
- 타입 체크
- 테스트 실행
- 빌드 확인

**실패 시**: `debug-issues` subagent로 문제 해결 후 재검증

### Phase 5: 리뷰
`review-code` subagent를 사용하여:
- 코드 품질 검토
- 보안 검토 (필요시 `security-scan` 사용)
- 개선 권장사항

---

## 완료 보고

모든 단계 완료 후 다음을 보고하세요:

1. **변경 요약**: 생성/수정/삭제된 파일
2. **주요 구현 내용**: 핵심 변경사항
3. **테스트 결과**: 검증 상태
4. **추가 작업**: 후속 작업이 필요하면 명시
