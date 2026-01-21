# Git Hooks 스크립트

이 디렉토리는 Git 커밋 시 자동으로 실행되는 Hook 스크립트를 포함합니다.

## 설치 방법

```bash
./scripts/install_hooks.sh
```

## 포함된 Hook

### 1. post-commit-deploy.sh (서버 자동 배포)

**목적**: 서버 환경에서 hotfix 커밋 시 자동으로 서비스를 재시작하고 텔레그램 알림을 발송합니다.

**동작 조건**:

- 프로젝트 경로가 `/opt/hantu_quant`인 경우에만 실행
- 로컬 환경에서는 아무 작업도 하지 않음

**수행 작업**:

1. 커밋 정보 수집 (hash, branch, message, author)
2. 서비스 재시작
   - `sudo systemctl restart hantu-api`
   - `sudo systemctl restart hantu-scheduler`
3. 텔레그램 알림 발송
   - 커밋 정보 포함
   - 재시작 결과 포함
   - 실패 시 경고 우선순위로 전송

**필수 환경변수**:

- `TELEGRAM_BOT_TOKEN`: 텔레그램 봇 토큰
- `TELEGRAM_CHAT_ID`: 텔레그램 채팅 ID

**텔레그램 알림 형식**:

```
✅ 서버 Hotfix 배포 완료

📅 시간: 2026-01-22 08:00:00
🔀 브랜치: fix/critical-bug
📝 커밋: a1b2c3d4
👤 작성자: Developer

💬 커밋 메시지:
fix: 긴급 버그 수정

🔄 서비스 재시작 결과:
• hantu-api: ✅ 재시작 성공
• hantu-scheduler: ✅ 재시작 성공

📊 최종 상태: 배포 성공
```

## 테스트

### 로컬에서 테스트 (실제 배포 안함)

```bash
# 프로젝트 루트에서
./scripts/hooks/post-commit-deploy.sh

# 출력: (아무것도 실행되지 않음)
```

### 서버에서 테스트

```bash
# 서버 접속
ssh ubuntu@서버IP

# 프로젝트 디렉토리로 이동
cd /opt/hantu_quant

# 코드 수정 후 커밋
git add .
git commit -m "fix: 긴급 버그 수정"

# post-commit hook이 자동 실행됨
# 1. 서비스 재시작
# 2. 텔레그램 알림 발송
```

## 트러블슈팅

### 텔레그램 알림이 전송되지 않는 경우

1. 환경변수 확인

   ```bash
   cat .env | grep TELEGRAM
   ```

2. 환경변수 설정
   ```bash
   nano .env
   # 다음 추가:
   # TELEGRAM_BOT_TOKEN=your_bot_token
   # TELEGRAM_CHAT_ID=your_chat_id
   ```

### 서비스 재시작 실패

1. 서비스 상태 확인

   ```bash
   sudo systemctl status hantu-api
   sudo systemctl status hantu-scheduler
   ```

2. 로그 확인

   ```bash
   journalctl -u hantu-api -n 50
   journalctl -u hantu-scheduler -n 50
   ```

3. 수동 재시작
   ```bash
   sudo systemctl restart hantu-api hantu-scheduler
   ```

## Hook 비활성화

```bash
# pre-commit + post-commit 모두 제거
rm .git/hooks/pre-commit .git/hooks/post-commit

# post-commit만 제거
rm .git/hooks/post-commit
```

## 참고

- `post-commit-deploy.sh`는 서버 환경에서만 실행됩니다.
- 로컬 환경에서는 커밋 후 아무 작업도 하지 않습니다.
- 재시작 실패 시에도 텔레그램 알림은 발송됩니다.
