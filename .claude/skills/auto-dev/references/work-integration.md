# Work 시스템 통합 가이드

> auto-dev 파이프라인의 Work 시스템 자동화 상세

---

## 개요

auto-dev는 Work 시스템과 완전히 통합되어 다음을 자동화합니다:

- ✅ idea → active 상태 전환
- ✅ Phase 전환 (planning → development → validation)
- ✅ progress.md 자동 업데이트
- ✅ 완료 시 Work 병합 및 completed 이동

---

## Work Context 감지

### 1. Work 시스템 활성화 여부 확인

```bash
# docs/works/ 디렉토리 존재 여부 확인
if [ -d "docs/works/" ]; then
    echo "Work 시스템 활성화됨"
else
    echo "일반 프로젝트 (Work 시스템 없음)"
fi
```

### 2. 사용자 요청에서 Work ID 감지

```
사용자 요청 패턴:
- "/auto-dev W-042"
- "/auto-dev W-042 사용자 인증 추가"
- "W-042 구현 시작해줘"

→ Work ID: W-042 추출
```

---

## idea 상태 자동 전환

### 감지 조건

```bash
# Work 파일 위치 확인
docs/works/idea/W-042-user-authentication/W-042-user-authentication.md

# Frontmatter 확인
status: idea              # ← idea 상태!
current_phase: planning   # Planning 완료
```

### 자동 전환 실행

```bash
# active 상태로 전환
./scripts/work.sh start W-042

# 자동 수행:
# 1. active/ 폴더 생성
#    mv docs/works/idea/W-042-{slug}/ \
#       docs/works/active/W-042-{slug}/
#
# 2. Frontmatter 업데이트
#    status: idea → active
#    current_phase: planning (유지, development로 곧 전환)
#    started_at: 현재 시각
#
# 3. progress.md 초기화
#    Development Phase 시작 상태로
#
# 4. 사용자에게 알림
echo "✅ Work W-042를 active 상태로 전환했습니다"
echo "→ docs/works/active/W-042-user-authentication/"
```

---

## active 상태에서 시작

### 현재 Phase 확인

```yaml
# Frontmatter에서 현재 상태 읽기
status: active
current_phase: [planning|development|validation]
phases_completed: [...]
```

### Phase별 시작 위치

| current_phase | 시작 위치 | 설명                                |
| ------------- | --------- | ----------------------------------- |
| `planning`    | Phase 1   | Planning 완료 후 구현 시작 (일반적) |
| `development` | Phase 3   | 중단 후 재개 (구현 재개)            |
| `validation`  | Phase 5   | 검증 단계 재개                      |

### 예시: planning에서 시작

```
current_phase: planning
phases_completed: [planning]

→ Planning은 이미 완료됨
→ Development 시작해야 함
→ Phase 1 (탐색)부터 시작

Phase 1-2 완료 후 자동으로:
./scripts/work.sh next-phase W-042
→ current_phase: planning → development
```

---

## Phase 전환 자동화

### Phase 1-2 완료 후 (planning → development)

```bash
# 조건
- Phase 1: 코드베이스 탐색 완료
- Phase 2: 구현 계획 승인

# 실행
./scripts/work.sh next-phase W-042

# 결과
status: active
current_phase: planning → development
phases_completed: [planning]
updated_at: [현재 시각]

# progress.md 자동 업데이트
### Planning Phase
- [x] 코드베이스 탐색
- [x] 구현 계획

### Development Phase
- [ ] 코드 구현 (시작!)
- [ ] 테스트 작성
```

### Phase 3-4-5-6 완료 후 (development → validation)

```bash
# 조건
- Phase 3: 코드 구현 완료
- Phase 4: 테스트 작성 완료
- Phase 5: 통합 검증 통과
- Phase 6: 코드 리뷰 Approve

# 실행
./scripts/work.sh next-phase W-042

# 결과
status: active
current_phase: development → validation
phases_completed: [planning, development]
updated_at: [현재 시각]

# progress.md 자동 업데이트
### Development Phase
- [x] 코드 구현
- [x] 테스트 작성

### Validation Phase
- [x] 통합 검증
- [x] 코드 리뷰
```

---

## Work 완료 자동화

### 완료 조건

```
Phase 6 (리뷰) Approve 받음
current_phase: validation
phases_completed: [planning, development, validation]

→ 모든 Phase 완료!
```

### 자동 완료 실행

```bash
# Work 완료
./scripts/work.sh complete W-042

# 자동 수행:

# 1. progress.md 병합
cat docs/works/active/W-042-{slug}/progress.md >> \
    docs/works/active/W-042-{slug}/W-042-{slug}.md

# 2. decisions.md 병합
cat docs/works/active/W-042-{slug}/decisions.md >> \
    docs/works/active/W-042-{slug}/W-042-{slug}.md

# 3. Frontmatter 업데이트
status: active → completed
completed_at: [현재 시각]
phases_completed: [planning, development, validation]

# 4. 폴더 이동
mv docs/works/active/W-042-{slug}/ \
   docs/works/completed/

# 5. progress.md, decisions.md 제거
rm docs/works/completed/W-042-{slug}/progress.md
rm docs/works/completed/W-042-{slug}/decisions.md

# 6. Git 커밋 (선택)
git add docs/works/completed/W-042-{slug}/
git commit -m "chore(work): Complete W-042 - User authentication

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

### 완료 보고

```markdown
## Work 완료

- **Work ID**: W-042
- **제목**: 사용자 인증 시스템 추가
- **위치**: docs/works/completed/W-042-user-authentication.md
- **상태**: active → completed ✅
- **완료 Phase**: planning, development, validation
- **소요 시간**: [시작-종료 시각]

### 자동 수행됨

- ✅ progress.md 병합
- ✅ decisions.md 병합
- ✅ completed/ 폴더로 이동
- ✅ Git 커밋
```

---

## Work 없이 실행

### 감지

```bash
# docs/works/ 없음
[ ! -d "docs/works/" ] && echo "일반 프로젝트"

# 또는 Work ID 없음
# 사용자 요청: "/auto-dev 로그인 기능 추가"
# → Work ID 감지 안됨
```

### 동작

```
Work 시스템 관련 작업 모두 생략:
- ❌ Work 상태 전환 (start/next-phase/complete)
- ❌ progress.md 업데이트
- ❌ decisions.md 기록
- ✅ 파이프라인만 실행 (Phase 1-6)
```

---

## progress.md 자동 업데이트

### Phase 완료 시

```markdown
### Development Phase

- [x] 코드 구현 (Phase 3 완료!)
- [ ] 테스트 작성
```

### 체크포인트 기록

```markdown
## 체크포인트

| 날짜       | Phase       | 체크포인트  | 상태 |
| ---------- | ----------- | ----------- | ---- |
| 2026-01-30 | Development | 코드 구현   | ✅   |
| 2026-01-30 | Development | 테스트 작성 | ⏳   |
```

---

## decisions.md 자동 기록

### Phase 중 결정 사항 발생 시

```markdown
### DEC-005: API 엔드포인트 경로

- **날짜**: 2026-01-30
- **Phase**: Development
- **결정**: `/api/auth/login` 사용
- **근거**: RESTful 컨벤션 준수
- **영향**: 프론트엔드 API 호출부 수정 필요
```

---

## 에러 처리

### Work 시스템 오류 시

```bash
# ./scripts/work.sh 실행 실패
→ 사용자에게 에러 보고
→ 일반 프로젝트 모드로 폴백
→ 파이프라인은 계속 진행
```

### Work 파일 없음

```bash
# docs/works/active/W-042-{slug}/ 없음
→ "❌ Work W-042를 찾을 수 없습니다"
→ "docs/works/ 구조를 확인하세요"
→ 파이프라인 중단
```

---

## 체크리스트

### 파이프라인 시작 전

```
□ docs/works/ 존재 여부 확인
□ Work ID 감지
□ Work 상태 확인 (idea/active)
□ idea이면 active로 전환
□ current_phase 확인
```

### Phase 전환 시

```
□ Phase 완료 확인
□ ./scripts/work.sh next-phase 호출
□ Frontmatter 업데이트 확인
□ progress.md 갱신 확인
```

### 완료 시

```
□ 모든 Phase 완료 확인
□ ./scripts/work.sh complete 호출
□ 병합 확인
□ completed/ 이동 확인
□ Git 커밋 확인 (선택)
```

---

## 참고

- Work 시스템 전체: docs/works/README.md
- work.sh 스크립트: scripts/work.sh
- Phase Gate: docs/architecture/phase-gate-pattern.md
