# 보안 가이드

## 중요 보안 정책

### 민감한 정보 관리

다음 파일들은 **절대 git에 커밋되어서는 안 됩니다**:

#### 1. API 인증 정보
- `data/token/token_info_real.json` - 실제 계좌 API 토큰
- `data/token/token_info_virtual.json` - 가상 계좌 API 토큰
- `.env` - 환경 변수 (APP_KEY, APP_SECRET, ACCOUNT_NUMBER)

#### 2. 텔레그램 설정
- `config/telegram_config.json` - 봇 토큰 및 채팅 ID

#### 3. 데이터베이스 및 로그
- `core/database/stock_data.db` - 거래 데이터
- `logs/*.log` - 시스템 로그 (API 키 포함 가능)
- `data/*` - 모든 데이터 파일

### .gitignore 검증

프로젝트의 `.gitignore` 파일에 다음이 포함되어 있는지 확인:

```gitignore
# Sensitive data and tokens
data/token/
data/token/token_info_*.json
.env
examples/env_test.py
config/telegram_config.json
config/*.json

# Data directories
data/*
!data/.gitkeep

# Logs
*.log
logs/
```

### 초기 설정 방법

#### 1. 환경 변수 설정

`.env` 파일 생성 (루트 디렉토리):

```bash
# 한국투자증권 API
APP_KEY=your_app_key_here
APP_SECRET=your_app_secret_here
ACCOUNT_NUMBER=your_account_number_here

# 텔레그램 (선택사항)
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

#### 2. 텔레그램 설정

`config/telegram_config.json.example`을 복사하여 `config/telegram_config.json` 생성:

```bash
cp config/telegram_config.json.example config/telegram_config.json
```

그 후 실제 값으로 수정:

```json
{
  "telegram": {
    "bot_token": "실제_봇_토큰",
    "default_chat_ids": [
      "실제_채팅_ID"
    ]
  }
}
```

또는 자동 설정 스크립트 사용:

```bash
python scripts/simple_telegram_setup.py setup
```

### 보안 점검 체크리스트

커밋하기 전에 다음을 확인하세요:

- [ ] `git status`로 민감한 파일이 staged되지 않았는지 확인
- [ ] `git diff --cached`로 API 키나 토큰이 포함되지 않았는지 확인
- [ ] 로그 출력 시 API 키는 마스킹되는지 확인 (예: `app_key[:10]...`)
- [ ] 새로운 설정 파일은 `.gitignore`에 추가되었는지 확인

### 로그 마스킹

`core/utils/log_utils.py`에서 자동으로 다음 키워드를 마스킹합니다:

- `app_key`, `APP_KEY`
- `app_secret`, `APP_SECRET`
- `token`, `TOKEN`
- `password`, `PASSWORD`
- `account_number`, `ACCOUNT_NUMBER`

### git 히스토리에서 민감 정보 제거

만약 실수로 민감한 정보를 커밋했다면:

```bash
# 특정 파일을 git 히스토리에서 완전히 제거
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch config/telegram_config.json" \
  --prune-empty --tag-name-filter cat -- --all

# 강제 푸시 (주의: 협업 시 팀원과 협의 필요)
git push origin --force --all
```

**더 안전한 방법**: BFG Repo-Cleaner 사용

```bash
# BFG 설치
brew install bfg  # macOS

# 민감 파일 제거
bfg --delete-files telegram_config.json

# 정리
git reflog expire --expire=now --all
git gc --prune=now --aggressive
```

### 토큰 유출 시 대응

1. **즉시 토큰 무효화**
   - 한국투자증권 API: 새로운 APP_KEY/SECRET 발급
   - 텔레그램: BotFather에서 봇 토큰 재발급 (`/revoke`)

2. **git 히스토리 정리** (위 방법 사용)

3. **모든 시스템에서 새 토큰으로 업데이트**

4. **로그 파일 확인 및 정리**

### 프로덕션 환경 권장사항

1. **환경 변수 우선 사용**
   - 파일 대신 시스템 환경 변수 사용
   - Docker의 경우 secrets 사용

2. **접근 권한 제한**
   ```bash
   chmod 600 .env
   chmod 600 config/telegram_config.json
   chmod 700 data/token/
   ```

3. **정기적인 토큰 갱신**
   - API 토큰은 3개월마다 갱신
   - 텔레그램 봇 토큰은 6개월마다 점검

4. **로그 모니터링**
   - 로그에 민감 정보가 없는지 정기 점검
   - 민감 정보가 발견되면 즉시 로그 삭제

### 코드 리뷰 시 점검사항

Pull Request 리뷰 시 다음을 확인:

- 하드코딩된 API 키나 토큰이 없는지
- 새로운 민감 정보 파일이 `.gitignore`에 포함되었는지
- 로그 출력 시 마스킹이 적용되는지
- 테스트 코드에 실제 인증 정보가 사용되지 않는지

### 문의

보안 이슈 발견 시:
1. 공개 이슈로 등록하지 말 것
2. 프로젝트 관리자에게 직접 연락
3. 발견된 취약점을 악용하지 말 것

---

**마지막 업데이트**: 2025-10-04
**다음 보안 검토 예정**: 2025-11-04
