# Git 거버넌스 규칙

> Git 브랜치 전략과 환경별 작업 규칙을 정의합니다.

---

## 환경별 작업 규칙

### 환경 판단 기준

| 환경       | 판단 조건                                       | 주 용도                |
| ---------- | ----------------------------------------------- | ---------------------- |
| **로컬**   | 경로가 `/Users/grimm/`으로 시작                 | 기능 개발, 설계, CI/CD |
| **서버**   | 경로가 `/opt/hantu_quant/` 또는 `/home/ubuntu/` | 에러 픽스, 핫픽스      |
| **온라인** | claude.ai 웹 환경                               | 대규모 작업, 리서치    |

### 환경별 Git 규칙

| 환경   | 브랜치 prefix             | CI 스킵          | 비고               |
| ------ | ------------------------- | ---------------- | ------------------ |
| 로컬   | `feature/*`, `refactor/*` | ❌               | PR 필수            |
| 서버   | `fix/*`, `hotfix/*`       | `[skip ci]` 권장 | 서비스 재시작 필요 |
| 온라인 | `claude/*`                | ❌               | PR 필수            |

---

## 브랜치 전략

### Main 브랜치

```
- 항상 배포 가능한 상태 유지
- 직접 커밋 금지 (PR을 통해서만)
- Protected branch 설정 권장
```

### Feature 브랜치 (로컬 환경)

```
feature/기능명
feature/add-portfolio-optimizer
feature/improve-risk-calc

작업:
1. feature 브랜치 생성
2. 코드 작성 및 테스트
3. PR 생성
4. 리뷰 후 main 병합
```

### Fix 브랜치 (서버 환경)

```
fix/버그명
fix/trading-engine-null-check
fix/api-timeout-handling

작업:
1. 서버에서 fix 브랜치 생성
2. 에러 수정
3. [skip ci] 커밋
4. 서비스 재시작
5. 확인 후 main 병합
```

### Hotfix 브랜치 (긴급)

```
hotfix/긴급이슈
hotfix/critical-memory-leak
hotfix/trading-halt-bug

작업:
1. main에서 hotfix 브랜치 생성
2. 긴급 수정
3. [skip ci] 커밋 (선택)
4. 즉시 main 병합
5. 수동 배포 또는 CI/CD 대기
```

---

## 커밋 메시지 컨벤션

### 형식

```
<타입>: <제목>

<본문>

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

### 타입

| 타입       | 설명      | 예시                               |
| ---------- | --------- | ---------------------------------- |
| `feat`     | 새 기능   | feat: 포트폴리오 최적화 추가       |
| `fix`      | 버그 수정 | fix: trading_engine null 체크      |
| `refactor` | 리팩토링  | refactor: API 클라이언트 구조 개선 |
| `chore`    | 기타 작업 | chore: 의존성 업데이트             |
| `docs`     | 문서      | docs: 배포 가이드 업데이트         |
| `test`     | 테스트    | test: 리스크 계산 단위 테스트      |
| `perf`     | 성능 개선 | perf: 캐싱 레이어 추가             |

### CI 스킵

```bash
# 긴급 수정 시 CI 건너뛰기
git commit -m "fix: hotfix [skip ci]"
```

---

## PR (Pull Request) 규칙

### PR 필수 환경

- 로컬 환경 (feature/_, refactor/_)
- 온라인 환경 (claude/\*)

### PR 템플릿

```markdown
## 변경 내용

- [ ] 기능 추가
- [ ] 버그 수정
- [ ] 리팩토링

## 테스트

- [ ] 단위 테스트 통과
- [ ] 통합 테스트 통과
- [ ] 수동 테스트 완료

## 배포 영향

- [ ] 서비스 재시작 필요
- [ ] DB 마이그레이션 필요
- [ ] 환경변수 변경 필요
```

---

## 체크리스트

### 커밋 전

- [ ] 올바른 브랜치에서 작업 중인가?
- [ ] 테스트가 통과하는가?
- [ ] 커밋 메시지가 컨벤션을 따르는가?

### Push 전

- [ ] CI 스킵이 필요한가?
- [ ] PR이 필요한가?
- [ ] 서버 배포 영향이 있는가?

### 배포 후 (서버 환경)

- [ ] 서비스 재시작했는가?
- [ ] 서비스 정상 동작하는가?
- [ ] main에 병합했는가?
