# Git 거버넌스 규칙

> 로컬, 서버, 온라인 환경에서의 Git 작업 규칙을 정의합니다.

---

## 환경 감지

Claude Code는 작업 시작 시 현재 환경을 파악해야 합니다.

### 환경 판단 기준

| 환경       | 판단 조건                                              |
| ---------- | ------------------------------------------------------ |
| **로컬**   | 경로가 `/Users/grimm/`으로 시작                        |
| **서버**   | 경로가 `/opt/hantu_quant/` 또는 `/home/ubuntu/`로 시작 |
| **온라인** | claude.ai 웹 환경 (GitHub 연동)                        |

### 환경 확인 명령

```bash
# 현재 경로 확인
pwd

# 호스트명 확인
hostname
```

---

## 환경별 역할

| 환경       | 주 용도                        | 특징                |
| ---------- | ------------------------------ | ------------------- |
| **로컬**   | 기능 개발, 설계, 인프라, CI/CD | 전체 개발 환경      |
| **서버**   | 에러 픽스, 핫픽스              | 로컬 로그 접근 가능 |
| **온라인** | 대규모 작업, 리서치 기반 개발  | GitHub 직접 연동    |

---

## 브랜치 전략

### 브랜치 네이밍 컨벤션

| prefix       | 용도                      | 주 사용 환경 |
| ------------ | ------------------------- | ------------ |
| `feature/*`  | 새 기능 개발              | 로컬, 온라인 |
| `fix/*`      | 버그 수정                 | 서버, 로컬   |
| `hotfix/*`   | 긴급 수정 (프로덕션 이슈) | 서버         |
| `refactor/*` | 코드 리팩토링             | 로컬, 온라인 |
| `docs/*`     | 문서 작업                 | 모든 환경    |
| `claude/*`   | 온라인 Claude Code 작업   | 온라인       |

### 브랜치 생성 규칙

```
main (보호됨 - 직접 push 지양)
  │
  ├── feature/* ──── 로컬/온라인 → PR → 머지
  ├── fix/* ──────── 서버/로컬 → PR or 직접 머지
  ├── hotfix/* ───── 서버 → 빠른 머지
  └── claude/* ───── 온라인 → PR → 머지
```

---

## 환경별 Git 워크플로우

### 로컬 환경

```bash
# 1. 작업 시작 전
git pull origin main

# 2. 브랜치 생성
git checkout -b feature/기능명

# 3. 작업 및 커밋
git add .
git commit -m "feat: 기능 설명"

# 4. Push 및 PR
git push -u origin feature/기능명
gh pr create --title "제목" --body "설명"

# 5. PR 머지 후 자동 배포
```

### 서버 환경

```bash
# 1. 작업 시작 전
git pull origin main

# 2. 브랜치 생성
git checkout -b fix/에러명

# 3. 에러 수정 및 커밋 ([skip ci] 포함)
git add .
git commit -m "fix: 에러 수정 [skip ci]"

# 4. Push
git push -u origin fix/에러명

# 5. 서비스 재시작 (이미 서버에 적용됨)
sudo systemctl restart hantu-api hantu-scheduler

# 6. PR 생성 (선택) 또는 직접 머지
gh pr create --title "fix: 에러 수정" --body "서버 로그 기반 수정"
```

### 온라인 환경

```
1. GitHub 연동된 상태에서 작업
2. claude/* 브랜치로 자동 생성
3. PR 생성 → 리뷰 → 머지
4. 머지 시 자동 배포
```

---

## CI/CD 규칙

### CI 스킵 조건

| 상황                         | `[skip ci]` 사용 |
| ---------------------------- | :--------------: |
| 서버 에러 픽스 (이미 적용됨) |        O         |
| 문서만 수정                  |     O (선택)     |
| 로컬 기능 개발               |        X         |
| 온라인 대규모 작업           |        X         |

### 커밋 메시지에 스킵 태그

```bash
# 다음 중 하나 포함 시 CI 스킵
[skip ci]
[ci skip]
[no ci]
```

---

## 충돌 방지 규칙

### 작업 시작 전 필수

```bash
git fetch origin
git status
# 로컬 변경사항 없으면 pull
git pull origin main
```

### 동시 작업 시

1. 서로 다른 파일/모듈 작업
2. 같은 파일 수정 필요 시 → 한쪽 먼저 머지 후 진행
3. 충돌 발생 시 → 수동 해결 후 커밋

### 머지 순서 권장

```
긴급도: hotfix > fix > feature
```

---

## 환경별 자동 행동

### 로컬 환경 감지 시

```
- 브랜치: feature/* 또는 refactor/* 권장
- CI: 정상 실행
- PR: 필수
```

### 서버 환경 감지 시

```
- 브랜치: fix/* 또는 hotfix/* 권장
- CI: [skip ci] 권장
- 서비스 재시작 안내
```

### 온라인 환경 감지 시

```
- 브랜치: claude/* (자동)
- CI: 정상 실행
- PR: 필수
```

---

## 체크리스트

### Git 작업 전

- [ ] 현재 환경 확인 (로컬/서버/온라인)
- [ ] `git pull origin main` 실행
- [ ] 적절한 브랜치 생성

### Git 작업 후

- [ ] 의미 있는 커밋 메시지 작성
- [ ] 서버 환경이면 `[skip ci]` 고려
- [ ] Push 및 PR 생성 (필요시)
- [ ] 서버면 서비스 재시작

---

## 관련 파일

- `.github/workflows/ci.yml` - CI 스킵 조건 정의
- `.github/workflows/deploy.yml` - 배포 워크플로우
- `deploy/SERVERS.md` - 서버 정보
