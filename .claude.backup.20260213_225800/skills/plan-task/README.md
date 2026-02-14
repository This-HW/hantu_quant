# plan-task 스킬

> 체계적인 작업 계획 수립 스킬
> Work 시스템과 완전 통합

---

## 개요

plan-task는 5단계 파이프라인으로 체계적인 계획을 수립합니다:

```
Phase 0: 규모 판단 (Small/Medium/Large)
         ↓
Phase 1: 코드베이스 탐색 (explore-codebase)
         ↓
Phase 2: 요구사항 명확화 (clarify-requirements)
         ↓
Phase 3: 사용자 여정 설계 (design-user-journey) - Medium/Large만
         ↓
Phase 4: 비즈니스 로직 정의 (define-business-logic) - Large만
         ↓
Phase 5: 구현 계획 수립 (plan-implementation)
```

---

## Work 시스템 통합 (신규!)

**Work 시스템 프로젝트에서는 자동으로 Work 구조를 생성하고 관리합니다.**

### 신규 Work 생성

```bash
# claude-setting 프로젝트 내에서
/plan-task "사용자 인증 시스템 추가"
```

**자동으로 수행됩니다:**
1. ✅ Work ID 생성 (W-XXX)
2. ✅ 폴더 구조 생성 (`docs/works/idea/W-XXX-{slug}/`)
3. ✅ Frontmatter 생성
4. ✅ progress.md 초기화
5. ✅ decisions.md 초기화
6. ✅ Planning 결과 자동 저장
7. ✅ Phase 전환 준비

**생성되는 파일:**
```
docs/works/idea/W-XXX-user-authentication/
├── W-XXX-user-authentication.md  # Frontmatter + Planning 결과
├── progress.md                   # 자동 업데이트
└── decisions.md                  # P0 결정 자동 기록
```

### 기존 Work 계획

```bash
# 이미 생성된 Work에 대해 계획 수립
/plan-task "W-024 작업 계획"
```

**자동으로 수행됩니다:**
1. ✅ 기존 Work 파일 읽기
2. ✅ 진행 상황 파악
3. ✅ 중단 지점부터 재개
4. ✅ progress.md 업데이트
5. ✅ 새로운 결정 사항 기록

---

## 사용 방법

### 1. 기본 사용

```bash
/plan-task "기능 설명"
```

### 2. Work 시스템과 함께 (권장)

**신규 Work:**
```bash
# 1. plan-task 실행 (Work 자동 생성)
/plan-task "결제 시스템 추가"

# 2. Planning 완료 후 Phase 전환
./scripts/work.sh next-phase W-XXX

# 3. 구현 시작
/auto-dev W-XXX
```

**기존 Work:**
```bash
# 1. Work가 이미 idea 상태로 존재
ls docs/works/idea/W-024-*/

# 2. Planning 수행
/plan-task "W-024"

# 3. Phase 전환 및 구현
./scripts/work.sh next-phase W-024
/auto-dev W-024
```

---

## 규모별 Planning 경로

| 규모 | Planning 경로 | 예상 시간 |
|------|--------------|----------|
| **Small** | Phase 1-2-5 | ~30분 |
| **Medium** | Phase 1-2-3-5 | ~1시간 |
| **Large** | Phase 1-2-3-4-5 | ~2시간 |

**규모 판단 기준:**

| 기준 | Small | Medium | Large |
|------|-------|--------|-------|
| 영향 범위 | 1개 모듈 | 2-3개 모듈 | 4개+ 모듈 |
| 데이터 변경 | 없음 | 기존 확장 | 새 구조 |
| 비즈니스 규칙 | 기존 내 | 경미한 추가 | 핵심 변경 |

---

## Work Frontmatter 예시

Planning 완료 후 자동 생성되는 frontmatter:

```yaml
---
work_id: W-024
title: "결제 시스템 추가"
status: idea
current_phase: planning
phases_completed: [planning]
created_at: "2026-01-28"
updated_at: "2026-01-28T10:30:00Z"
size: large
priority: p0

# Planning 결과 요약
scope:
  - 결제 게이트웨이 연동
  - 결제 내역 관리
  - 환불 처리

requirements:
  - P0 모호함 0개 해결됨
  - 사용자 여정 정의됨
  - 비즈니스 규칙 명세됨

risks:
  - PG사 API 의존성
  - 금융 데이터 보안
  - 트랜잭션 무결성
---

# Work: 결제 시스템 추가

[Planning 상세 결과가 여기 저장됩니다]
```

---

## progress.md 자동 업데이트

각 Phase 완료 시 자동으로 갱신됩니다:

```markdown
# Progress: 결제 시스템 추가

> Work ID: W-024
> Current Phase: planning
> Last Updated: 2026-01-28T10:30:00Z

---

## 현재 진행 상황

### 완료된 작업
- [x] 규모 판단 (Large)
- [x] 코드베이스 탐색
- [x] 요구사항 명확화 (P0 모호함 8개 → 0개)
- [x] 사용자 여정 설계
- [x] 비즈니스 로직 정의 (12개 규칙)
- [x] 구현 계획 수립

### Planning Phase ✅
- ✅ P0 모호함 = 0개
- ✅ 사용자 여정 정의
- ✅ 비즈니스 규칙 명세
- ✅ 구현 계획 수립

**Planning 완료 조건:** ✅ 모두 충족

---

## 다음 작업
- [ ] Phase 전환: `./scripts/work.sh next-phase W-024`
- [ ] 구현 시작: `/auto-dev W-024`
```

---

## decisions.md 자동 기록

P0 결정 사항이 자동으로 기록됩니다:

```markdown
# Decisions: 결제 시스템 추가

> Work ID: W-024
> Last Updated: 2026-01-28T10:30:00Z

---

## 의사결정 기록

### DEC-001: 규모 판단
- **날짜**: 2026-01-28
- **결정**: Large
- **근거**: 4개 모듈 영향, 새 DB 스키마, 핵심 비즈니스 규칙 추가
- **영향**: Phase 1-2-3-4-5 전체 실행

### DEC-002: 결제 게이트웨이 선택
- **날짜**: 2026-01-28
- **질문**: "Stripe vs Toss Payments?"
- **답변**: "Toss Payments (국내 시장 특화)"
- **영향**: API 연동 방식 결정

### DEC-003: 환불 정책
- **날짜**: 2026-01-28
- **질문**: "전액 환불 가능 기간?"
- **답변**: "구매 후 7일 이내"
- **영향**: 환불 처리 로직, 상태 전이 규칙
```

---

## P0 모호함 처리

Planning 중 P0 모호함을 발견하면:

1. **즉시 질문**: AskUserQuestion으로 사용자에게 질문
2. **답변 기록**: decisions.md에 자동 기록
3. **진행 재개**: 해결된 P0 반영하여 Planning 계속

**P0 기준:**
- 데이터 무결성
- 보안
- 금융 처리
- 핵심 비즈니스 로직

---

## 일반 프로젝트 vs Work 시스템

| 기능 | 일반 프로젝트 | Work 시스템 |
|------|-------------|------------|
| 폴더 생성 | ❌ | ✅ 자동 |
| Frontmatter | ❌ | ✅ 자동 |
| progress.md | ❌ | ✅ 자동 업데이트 |
| decisions.md | ❌ | ✅ P0 자동 기록 |
| Phase 전환 | 수동 | ✅ 스크립트 지원 |

**Work 시스템 감지:**
- `docs/works/` 디렉토리 존재 → 자동 활성화
- 없으면 일반 Planning만 수행

---

## 문제 해결

### Work가 생성되지 않아요
```bash
# docs/works/ 디렉토리 확인
ls docs/works/

# 없으면 Work 시스템 미사용 프로젝트
# 수동으로 초기화:
mkdir -p docs/works/{idea,active,completed,paused}
```

### Phase 전환이 안 돼요
```bash
# work.sh 실행 권한 확인
chmod +x scripts/work.sh

# yq 설치 확인
brew install yq  # macOS
```

### Planning 결과가 저장 안 돼요
```bash
# Work 파일 확인
cat docs/works/idea/W-XXX-*/W-XXX-*.md

# Frontmatter 형식 확인
# YAML 문법 에러 가능성
```

---

## 관련 문서

- **Work 시스템**: `docs/works/README.md`
- **Phase Gate 패턴**: `docs/architecture/phase-gate-pattern.md`
- **Planning 프로토콜**: `.claude/rules/planning-protocol.md`
- **auto-dev 스킬**: `skills/common/auto-dev/README.md`

---

## 변경 이력

### 2026-01-28: Work 시스템 완전 통합
- ✅ 신규 Work 자동 생성
- ✅ Frontmatter 자동 생성
- ✅ progress.md 자동 업데이트
- ✅ decisions.md P0 자동 기록
- ✅ Phase 전환 가이드 추가

**Migration Impact:**
- 기존 일반 프로젝트: 영향 없음 (하위 호환)
- Work 시스템 프로젝트: 자동으로 Work 구조 생성

**참조**: W-023 (Anthropic 표준 채택), 이 통합은 W-023의 DEC-003에서 P1으로 식별되었습니다.
