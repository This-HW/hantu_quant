# Work 시스템 통합 가이드

> plan-task 스킬의 Work 시스템 자동화 상세 가이드

---

## 개요

plan-task는 Work 시스템과 완전히 통합되어 있습니다:

- ✅ Work ID 자동 생성 (W-XXX)
- ✅ 폴더 구조 자동 생성
- ✅ Frontmatter 자동 작성
- ✅ progress.md 자동 초기화/업데이트
- ✅ decisions.md P0 결정 자동 기록

---

## 신규 Work 생성 시

### 1. Work ID 생성

```bash
# 최신 Work ID 확인
ls -1 docs/works/idea/ | grep -oE 'W-[0-9]+' | sort -V | tail -1
# → W-042

# 다음 ID: W-043
```

### 2. 폴더 구조 생성

```
docs/works/idea/
└── W-043-user-authentication/    # W-{ID}-{slug}
    ├── W-043-user-authentication.md    # 메인 Work 파일
    ├── progress.md                      # 진행 상황
    ├── decisions.md                     # 의사결정 기록
    ├── planning-results.md              # Planning 상세 결과 (Phase 2~5)
    └── review-results.md                # 다관점 리뷰 결과 (Phase 6, Medium/Large만)
```

### 3. Work 파일 Frontmatter

```yaml
---
work_id: "W-043"
title: "사용자 인증 시스템 추가"
status: idea
current_phase: planning
phases_completed: []
size: [Small/Medium/Large]
priority: [P0/P1/P2/P3]
tags: [authentication, security, user-management]
created_at: "2026-01-30T10:30:00+09:00"
updated_at: "2026-01-30T10:30:00+09:00"
---

# 사용자 인증 시스템 추가

> Work ID: W-043
> Status: idea → planning
> Size: [판단 결과]

---

## 요구사항

[사용자 요청 내용]

---

## Planning 결과

[Phase 완료 후 여기에 결과 추가]
```

### 4. progress.md 초기화

```markdown
# Progress: 사용자 인증 시스템 추가

> Work ID: W-043
> Last Updated: 2026-01-30T10:30:00+09:00

---

## Phase 진행 상황

### Planning Phase

- [ ] 규모 판단
- [ ] 요구사항 명확화 (P0 모호함 해결)
- [ ] 사용자 여정 설계 (Medium/Large)
- [ ] 비즈니스 로직 정의 (Large)
- [ ] 구현 계획 수립

### Development Phase

- [ ] 대기 중 (Planning 완료 후)

### Validation Phase

- [ ] 대기 중 (Development 완료 후)

---

## 체크포인트

| 날짜       | Phase    | 체크포인트 | 상태 |
| ---------- | -------- | ---------- | ---- |
| 2026-01-30 | Planning | 규모 판단  | ✅   |
```

### 5. decisions.md 초기화

```markdown
# Decisions: 사용자 인증 시스템 추가

> Work ID: W-043
> Last Updated: 2026-01-30T10:30:00+09:00

---

## 의사결정 기록

### DEC-001: 규모 판단

- **날짜**: 2026-01-30
- **결정**: [Small/Medium/Large]
- **근거**: [Phase 0 판단 이유]
- **영향**: Planning 경로 결정
```

### 6. planning-results.md 초기화

```markdown
# Planning 상세 결과

> Work ID: W-043
> Last Updated: 2026-01-30T10:30:00+09:00

---

## 규모 판단 (Phase 0)

- **크기**: [Small/Medium/Large]
- **판단 근거**: [...]
- **실행 경로**: [Phase 목록]

---

## 요구사항 명확화 (Phase 2)

[clarify-requirements 에이전트 전체 결과]

---

## 사용자 여정 설계 (Phase 3) - Medium/Large만

[design-user-journey 에이전트 전체 결과]

---

## 비즈니스 로직 정의 (Phase 4) - Large만

[define-business-logic 에이전트 전체 결과]

---

## 구현 계획 수립 (Phase 5)

[plan-implementation 에이전트 전체 결과]
```

### 7. review-results.md 초기화 (Medium/Large만)

```markdown
# 다관점 리뷰 결과

> Work ID: W-043
> Last Updated: 2026-01-30T10:30:00+09:00

---

## 리뷰 메타데이터

- **실행 날짜**: 2026-01-30T14:00:00+09:00
- **규모**: [Medium/Large]
- **참여 관점**: [N]개
- **합의율**: [X]%

---

## 🔴 Critical 이슈 (즉시 해결 필요)

### 1. [이슈명]

- **제기 관점**: [관점 목록]
- **내용**: [상세 설명]
- **영향**: [영향 범위]
- **해결**: [구체적 해결책]
- **합의**: ✅ 전원 합의 / ⚠️ 조건부 / ❓ 사용자 결정 필요

---

## 🟡 Important 이슈 (수정 권장)

[...]

---

## 🟢 Nice-to-have (선택 사항)

[...]

---

## 💬 합의 과정

### 충돌 #1: [충돌 설명]

- **Round 1**: [초기 의견]
- **Round 2**: [재검토 의견]
- **합의안**: [최종 합의]
- **결과**: ✅ 해결 / ❓ 사용자 결정 대기

---

## 📊 영향도 분석

- **변경 범위**: [영향받는 시스템]
- **예상 개발 기간**: [...]
- **리스크**: [...]

---

## 🎯 최종 권고사항

- [ ] [액션 아이템 1]
- [ ] [액션 아이템 2]
- [ ] [액션 아이템 3]
```

---

## 기존 Work 계획 시

### 1. Work 파일 읽기

```bash
# Work 위치 파악
docs/works/idea/W-043-user-authentication/W-043-user-authentication.md
```

### 2. 현재 상태 확인

```yaml
# Frontmatter 확인
status: idea # idea 상태여야 함
current_phase: planning # planning이어야 함
```

### 3. 진행 상황 확인

```bash
# progress.md 읽기
cat docs/works/idea/W-043-user-authentication/progress.md

# 체크포인트 확인
- 어디까지 진행되었는가?
- 어느 Phase에서 중단되었는가?
- 중단된 지점부터 재개
```

---

## Planning 진행 중 업데이트

### Phase 완료 후 업데이트

**1. progress.md 업데이트**

```markdown
### Planning Phase

- [x] 규모 판단
- [x] 요구사항 명확화 (P0 모호함 해결)
- [ ] 사용자 여정 설계 (Medium/Large)
- [ ] 비즈니스 로직 정의 (Large)
- [ ] 구현 계획 수립

---

## 체크포인트

| 날짜       | Phase    | 체크포인트      | 상태 |
| ---------- | -------- | --------------- | ---- |
| 2026-01-30 | Planning | 규모 판단       | ✅   |
| 2026-01-30 | Planning | 요구사항 명확화 | ✅   |
```

**2. decisions.md 업데이트**

P0 결정 사항 기록:

```markdown
### DEC-002: 인증 방식

- **날짜**: 2026-01-30
- **질문**: JWT vs Session 기반 인증?
- **결정**: JWT 기반 인증
- **근거**: 마이크로서비스 아키텍처에 적합
- **영향**: 토큰 관리, 리프레시 로직 필요
```

**3. Work 파일에 결과 추가**

```markdown
## Planning 결과

### 요구사항 명확화 (Phase 2)

[Phase 2 결과 전체 내용]

### 사용자 여정 설계 (Phase 3)

[Phase 3 결과 전체 내용]
```

---

## Planning 완료 시

### 1. Frontmatter 업데이트

```yaml
---
work_id: "W-043"
title: "사용자 인증 시스템 추가"
status: idea
current_phase: planning # 유지
phases_completed: [planning] # ← 추가
size: Large
priority: P0
tags: [authentication, security, user-management]
created_at: "2026-01-30T10:30:00+09:00"
updated_at: "2026-01-30T14:20:00+09:00" # ← 갱신
---
```

### 2. progress.md 업데이트

```markdown
### Planning Phase

- [x] 규모 판단
- [x] 요구사항 명확화 (P0 모호함 해결)
- [x] 사용자 여정 설계
- [x] 비즈니스 로직 정의
- [x] 구현 계획 수립

### Development Phase

- [ ] ⏳ 준비됨 (Phase 전환 대기)
```

### 3. Work 파일에 최종 결과 저장

```markdown
## Planning 결과

### 규모 판단

- 규모: Large
- 근거: 4개 모듈 영향, 새 데이터 구조, 핵심 보안 규칙

### 요구사항 명확화

[Phase 2 전체 결과]

### 사용자 여정

[Phase 3 전체 결과]

### 비즈니스 규칙

[Phase 4 전체 결과]

### 구현 계획

[Phase 5 전체 결과]
```

### 4. 상태 전환 안내

```bash
# 사용자에게 다음 명령 제시:

# Option 1: Phase 전환
./scripts/work.sh next-phase W-043

# Option 2: 직접 Development 시작
/auto-dev W-043
```

---

## 자동화 체크리스트

### 신규 Work 생성 시

```
□ Work ID 생성 (W-XXX)
□ slug 생성 (kebab-case)
□ 폴더 생성 (docs/works/idea/W-XXX-{slug}/)
□ Work 파일 생성 (W-XXX-{slug}.md)
□ Frontmatter 작성 (모든 필드)
□ progress.md 초기화
□ decisions.md 초기화
□ planning-results.md 초기화
□ review-results.md 초기화 (Medium/Large만)
```

### Planning 진행 중

```
□ 각 Phase 완료 시 progress.md 갱신
□ P0 결정 시 decisions.md 기록
□ Phase 2~5 결과를 planning-results.md에 저장
□ Work 파일에 결과 추가
□ Frontmatter updated_at 갱신
```

### Planning 완료 시

```
□ phases_completed: [planning] 업데이트
□ progress.md → Planning ✅
□ progress.md → Development ⏳ 준비
□ planning-results.md 최종 저장
□ Phase 6 다관점 리뷰 실행 (Medium/Large)
□ review-results.md 저장 (리뷰 실행 시)
□ Work 파일 최종 저장
□ 사용자에게 다음 단계 안내
```

---

## 파일 위치 규칙

```
docs/works/
├── idea/                    # Planning 중
│   └── W-XXX-{slug}/
│       ├── W-XXX-{slug}.md      # 메인 파일
│       ├── progress.md          # 진행 상황
│       ├── decisions.md         # 의사결정
│       ├── planning-results.md  # Planning 상세 결과 (Phase 2~5)
│       └── review-results.md    # 다관점 리뷰 결과 (Phase 6, Medium/Large만)
│
├── active/                  # Development 중
│   └── W-XXX-{slug}/
│
└── completed/               # 완료
    └── W-XXX-{slug}/
```

**Phase 전환 시 폴더 이동:**

```bash
# Planning 완료 → Development 시작
mv docs/works/idea/W-043-user-authentication \
   docs/works/active/
```

---

## 관련 도구

| 도구              | 용도                      |
| ----------------- | ------------------------- |
| `scripts/work.sh` | Work 상태 관리            |
| `/plan-task`      | Planning 자동화 (이 스킬) |
| `/auto-dev`       | Development 자동화        |

---

## 참고

- 전체 Work 시스템: docs/works/README.md
- Phase 전환 규칙: docs/architecture/phase-gate-pattern.md
