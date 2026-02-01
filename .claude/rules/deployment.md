# 배포 규칙

> 자동화된 배포를 우선하고, 수동 배포는 긴급 상황에만 사용합니다.

---

## 핵심 원칙

### 1. CI/CD 우선 원칙

```
✅ 기본 배포 방식: GitHub Actions 자동 배포
❌ 수동 배포: 긴급 상황 외 금지
```

### 2. 배포 충돌 방지

```
❌ 금지: git push + 수동 배포 (중복)
✅ 허용: git push → CI/CD 대기
✅ 허용: [skip ci] + 수동 배포 (긴급)
```

---

## 배포 방식

### 방식 1: 자동 배포 (기본)

**언제 사용:**

- 로컬에서 개발 완료
- 정상적인 기능 추가/수정
- 긴급하지 않은 모든 배포

**프로세스:**

```bash
# 1. 로컬에서 개발
git checkout -b feature/new-feature
# 코드 작성...
git add -A
git commit -m "feat: 새 기능 추가"

# 2. Push (CI/CD 자동 트리거)
git push origin feature/new-feature

# 3. PR 생성 및 병합
# GitHub에서 PR 생성 → 리뷰 → main 병합

# 4. CI/CD 자동 실행
# ✅ CI: 테스트, 린트, 보안 검사
# ✅ Deploy: 서버 배포, 서비스 재시작
# ✅ Notification: 텔레그램 알림

# 5. 배포 완료 대기 (2-3분)
# 텔레그램으로 "✅ 배포 성공" 알림 수신
```

**소요 시간:**

- CI: 1-2분
- Deploy: 1-2분
- 총: **2-4분**

**장점:**

- 자동 테스트 실행
- 배포 상태 추적
- 롤백 가능
- 알림 자동 전송

---

### 방식 2: 수동 배포 (긴급)

**언제 사용:**

- 서버에서 긴급 에러 수정
- CI/CD 장애 시
- 즉시 배포 필요한 핫픽스

**프로세스:**

```bash
# 1. 서버 접속
ssh ubuntu@158.180.87.156

# 2. 핫픽스 브랜치 생성
cd /opt/hantu_quant
git checkout -b hotfix/urgent-fix

# 3. 코드 수정
nano core/trading/trading_engine.py

# 4. 커밋 (CI 스킵)
git add -A
git commit -m "fix: 긴급 에러 수정 [skip ci]"

# 5. 서비스 재시작
sudo systemctl restart hantu-scheduler hantu-api

# 6. 확인
sudo systemctl status hantu-scheduler hantu-api

# 7. Push 및 병합
git push origin hotfix/urgent-fix
# GitHub에서 main에 병합
```

**주의사항:**

```
⚠️ [skip ci]로 CI를 건너뛰면:
- 자동 테스트 미실행
- 자동 배포 미실행
- 수동으로 서비스 재시작 필수
```

---

## 배포 플로우 다이어그램

### 자동 배포 (권장)

```
┌──────────────┐
│ git push     │
│ origin main  │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ GitHub       │
│ Actions CI   │ (1-2분)
└──────┬───────┘
       │
    SUCCESS
       │
       ▼
┌──────────────────────┐
│ GitHub Actions       │
│ Deploy Workflow      │
│ • git pull           │
│ • pip install        │ (1-2분)
│ • service restart    │
└──────┬───────────────┘
       │
       ▼
┌──────────────┐
│ Telegram     │
│ 알림 전송    │
└──────────────┘
```

### 수동 배포 (긴급)

```
┌──────────────┐
│ SSH 접속     │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ 코드 수정    │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ git commit   │
│ [skip ci]    │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ service      │
│ restart      │ (수동)
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ 수동 확인    │
└──────────────┘
```

---

## 배포 후 확인

### 자동 배포 후

```bash
# 1. 텔레그램 알림 확인
# "✅ 배포 성공" 메시지 수신

# 2. 서버 상태 확인 (선택)
ssh ubuntu@158.180.87.156
sudo systemctl status hantu-scheduler hantu-api
```

### 수동 배포 후

```bash
# 1. 서비스 상태 (필수)
sudo systemctl status hantu-scheduler hantu-api

# 2. 로그 확인 (필수)
journalctl -u hantu-scheduler -f
journalctl -u hantu-api -f

# 3. 헬스 체크 (필수)
curl http://localhost:8000/health
```

---

## 트러블슈팅

### 문제: 자동 배포가 안됨

**원인:**

```
1. CI 실패 → Deploy 트리거 안됨
2. GitHub Actions Secrets 미설정
3. [skip ci] 플래그 사용
```

**해결:**

```bash
# 1. CI 로그 확인
gh run list --limit 5
gh run view [run-id] --log

# 2. Secrets 확인 (GitHub Settings)
DEPLOY_HOST
DEPLOY_USER
DEPLOY_SSH_KEY
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID

# 3. [skip ci] 제거 후 재푸시
```

### 문제: 수동 배포 후 자동 배포가 덮어씀

**원인:**

```
git push 했는데 수동 배포도 함
→ 수동 배포 (즉시) → CI/CD 배포 (2-3분 후) → 덮어씀
```

**해결:**

```
방법 1: [skip ci] 사용
git commit -m "fix: hotfix [skip ci]"

방법 2: 수동 배포 후 push 안하기 (비권장)

방법 3: CI/CD만 사용 (권장)
```

---

## 배포 체크리스트

### 일반 배포 (로컬 환경)

```
□ feature/* 브랜치 생성
□ 코드 작성 및 테스트
□ git push origin feature/*
□ PR 생성
□ CI 통과 확인
□ PR 병합
□ Deploy 워크플로우 대기 (2-3분)
□ 텔레그램 알림 확인
```

### 긴급 배포 (서버 환경)

```
□ hotfix/* 브랜치 생성
□ 서버에서 코드 수정
□ git commit -m "fix: ... [skip ci]"
□ sudo systemctl restart hantu-*
□ 서비스 상태 확인
□ git push origin hotfix/*
□ main 병합
```

---

## 절대 금지 사항

```
❌ git push + 수동 배포 (동시)
❌ main 브랜치 직접 커밋 (서버 제외)
❌ CI 실패 무시하고 배포
❌ 배포 후 서비스 확인 안함
❌ [skip ci] 남발
```

---

## 관련 파일

| 파일                              | 설명                 |
| --------------------------------- | -------------------- |
| `.github/workflows/deploy.yml`    | 자동 배포 워크플로우 |
| `deploy/DEPLOY_MICRO.md`          | 배포 가이드 (참고용) |
| `.claude/rules/git-governance.md` | Git 브랜치 규칙      |
| `scripts/deployment/deploy.sh`    | 배포 스크립트        |
