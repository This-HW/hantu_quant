# 환경 변수 설정 가이드

## .env 파일 설정

### 중요: DATABASE_URL 설정

⚠️ **DATABASE_URL을 .env 파일에 설정하면 자동 환경 감지가 완전히 무시됩니다!**

#### 권장 설정 (로컬 개발)

```bash
# .env.example을 복사하여 .env 생성
cp .env.example .env

# DATABASE_URL 라인을 찾아서 주석 처리 또는 삭제
# DATABASE_URL=postgresql://...  ← 이 라인 제거!
```

**.env.example의 DATABASE_URL 섹션**:

```bash
# DATABASE_URL - PostgreSQL 연결 문자열
# ⚠️ 이 값을 설정하면 settings.py의 자동 감지를 오버라이드합니다!
# 권장: 이 항목을 제거하고 자동 감지 사용 (HANTU_ENV 또는 경로 기반)
#
# 자동 감지 동작:
# - 로컬 (/Users/*, /home/username): localhost:15432 (SSH 터널)
# - 서버 (/opt/*, /home/ubuntu): localhost:5432 (직접 연결)
#
# 수동 설정이 필요한 경우에만 아래 주석 해제:
# DATABASE_URL=postgresql://hantu@localhost:15432/hantu_quant
```

### DATABASE_URL 우선순위

1. **DATABASE_URL 환경변수** (최고 우선) - 설정 시 자동 감지 완전히 무시
2. **HANTU_ENV 환경변수** - `local`, `server`, `test` 값으로 수동 지정
3. **경로 기반 자동 감지** - 프로젝트 경로로 환경 자동 판별
4. **기본값** - 알 수 없는 경로는 로컬 설정 사용

### 환경별 설정 예시

#### 1. 로컬 개발 (권장)

```bash
# .env 파일
# DATABASE_URL 라인 제거 (자동 감지 사용)

# SSH 터널 시작
./scripts/db-tunnel.sh start

# 확인
python scripts/diagnose-db.py
# → localhost:15432 자동 사용됨
```

#### 2. 로컬 개발 (명시적 환경 설정)

```bash
# .env 파일
HANTU_ENV=local  # localhost:15432 사용

# SSH 터널 시작
./scripts/db-tunnel.sh start
```

#### 3. 서버 환경

```bash
# .env 파일 (서버)
# DATABASE_URL 라인 제거 (자동 감지 사용)

# 또는 명시적 설정
HANTU_ENV=server  # localhost:5432 사용
```

#### 4. 테스트 환경

```bash
# .env 파일 (테스트)
HANTU_ENV=test  # SQLite 사용
```

### 잘못된 설정 예시

#### ❌ 잘못된 예 1: 로컬에서 서버 포트 사용

```bash
# .env 파일 (로컬)
DATABASE_URL=postgresql://hantu@localhost:5432/hantu_quant

# 문제: SSH 터널(15432)이 아닌 5432 포트로 접근 시도
# 결과: 연결 실패 (서버가 원격이므로 직접 5432 접근 불가)
```

#### ❌ 잘못된 예 2: 비밀번호 하드코딩

```bash
# .env 파일
DATABASE_URL=postgresql://hantu:PASSWORD@localhost:15432/hantu_quant

# 문제:
# 1. 비밀번호가 .env에 노출됨 (보안 위험)
# 2. 자동 감지가 무시됨
# 3. .pgpass 파일 사용이 권장됨
```

#### ❌ 잘못된 예 3: .env.example 그대로 사용

```bash
# .env 파일을 생성하지 않고 .env.example을 그대로 사용
cp .env.example .env
# → DATABASE_URL 라인이 활성화되어 자동 감지 무시됨
```

### 올바른 설정 예시

#### ✅ 올바른 예 1: 자동 감지 사용 (권장)

```bash
# .env 파일에 DATABASE_URL 없음 (또는 주석 처리)
# DATABASE_URL=...

# ~/.pgpass 파일 설정
echo "localhost:15432:hantu_quant:hantu:YOUR_PASSWORD" >> ~/.pgpass
chmod 600 ~/.pgpass

# SSH 터널 시작
./scripts/db-tunnel.sh start

# 자동으로 올바른 포트 감지됨
```

#### ✅ 올바른 예 2: HANTU_ENV 사용

```bash
# .env 파일
HANTU_ENV=local

# ~/.pgpass 파일 설정 (동일)
echo "localhost:15432:hantu_quant:hantu:YOUR_PASSWORD" >> ~/.pgpass
chmod 600 ~/.pgpass
```

## 비밀번호 관리

### .pgpass 파일 설정

**위치**: `~/.pgpass`

**형식**:

```
hostname:port:database:username:password
```

**로컬 개발 설정**:

```bash
# .pgpass 파일 생성/수정
cat >> ~/.pgpass << EOF
localhost:15432:hantu_quant:hantu:YOUR_PASSWORD
EOF

# 권한 설정 (필수)
chmod 600 ~/.pgpass
```

**서버 설정**:

```bash
# 서버 .pgpass
cat >> ~/.pgpass << EOF
localhost:5432:hantu_quant:hantu:YOUR_PASSWORD
EOF

chmod 600 ~/.pgpass
```

### 보안 주의사항

1. **절대 금지**: DATABASE_URL에 비밀번호 하드코딩
2. **권장**: .pgpass 파일 사용 (권한 600 필수)
3. **금지**: .env 파일을 Git에 커밋
4. **필수**: .env.example만 커밋 (비밀번호 없이)

## 트러블슈팅

### 문제 1: 로컬에서 연결 실패 (포트 5432)

**증상**:

```
psycopg2.OperationalError: could not connect to server: Connection refused
	Is the server running on host "localhost" (127.0.0.1) and accepting
	TCP/IP connections on port 5432?
```

**원인**: .env 파일에 잘못된 DATABASE_URL 설정

**해결**:

```bash
# 1. .env 파일 확인
cat .env | grep DATABASE_URL

# 2. DATABASE_URL 라인 제거 또는 주석
vim .env
# DATABASE_URL=...  ← 주석 처리

# 3. SSH 터널 확인
./scripts/db-tunnel.sh status

# 4. 재시도
python scripts/diagnose-db.py
```

### 문제 2: 비밀번호 인증 실패

**증상**:

```
psycopg2.OperationalError: FATAL: password authentication failed for user "hantu"
```

**원인**: .pgpass 파일 누락 또는 권한 문제

**해결**:

```bash
# 1. .pgpass 파일 생성
echo "localhost:15432:hantu_quant:hantu:YOUR_PASSWORD" >> ~/.pgpass

# 2. 권한 설정 (필수!)
chmod 600 ~/.pgpass

# 3. 확인
ls -la ~/.pgpass
# -rw------- 1 user group ... .pgpass

# 4. 재시도
python scripts/diagnose-db.py
```

### 문제 3: SSH 터널 미실행

**증상**:

```
psycopg2.OperationalError: could not connect to server: Connection refused
	Is the server running on host "localhost" and accepting
	TCP/IP connections on port 15432?
```

**원인**: SSH 터널이 실행되지 않음

**해결**:

```bash
# 1. 터널 상태 확인
./scripts/db-tunnel.sh status

# 2. 터널 시작
./scripts/db-tunnel.sh start

# 3. 재시도
python scripts/diagnose-db.py
```

## 환경 변수 전체 목록

### 필수 환경 변수

| 변수                 | 설명                                    | 예시                |
| -------------------- | --------------------------------------- | ------------------- |
| `APP_KEY`            | 한투 API 앱 키                          | `PSxxxxx...`        |
| `APP_SECRET`         | 한투 API 시크릿                         | `xxxxx...`          |
| `ACCOUNT_NUMBER`     | 계좌 번호 (8자리)                       | `12345678`          |
| `ACCOUNT_PROD_CODE`  | 계좌 상품 코드 (01=종합, 02=위탁)       | `01`                |
| `SERVER`             | 서버 모드 (virtual=모의투자, prod=실전) | `virtual`           |
| `API_SERVER_KEY`     | API 서버 인증 키                        | `your-secret-key`   |
| `TELEGRAM_BOT_TOKEN` | 텔레그램 봇 토큰                        | `1234567890:ABC...` |
| `TELEGRAM_CHAT_ID`   | 텔레그램 채팅 ID                        | `123456789`         |

### 선택적 환경 변수

| 변수           | 설명                                 | 기본값                     |
| -------------- | ------------------------------------ | -------------------------- |
| `DATABASE_URL` | PostgreSQL 연결 URL (자동 감지 권장) | (자동 감지)                |
| `HANTU_ENV`    | 환경 명시 (local/server/test)        | (경로 기반 자동 감지)      |
| `REDIS_URL`    | Redis 연결 URL                       | `redis://localhost:6379/0` |

## 체크리스트

### 로컬 개발 환경 설정

- [ ] .env.example을 .env로 복사
- [ ] .env에서 DATABASE_URL 라인 제거 또는 주석
- [ ] .pgpass 파일 생성 (localhost:15432 포트)
- [ ] .pgpass 권한 설정 (chmod 600)
- [ ] SSH 터널 시작 (./scripts/db-tunnel.sh start)
- [ ] 연결 테스트 (python scripts/diagnose-db.py)

### 서버 환경 설정

- [ ] .env 파일 생성
- [ ] .env에서 DATABASE_URL 라인 제거 또는 주석
- [ ] .pgpass 파일 생성 (localhost:5432 포트)
- [ ] .pgpass 권한 설정 (chmod 600)
- [ ] 연결 테스트

## 참고 문서

- [CLAUDE.md - 인프라 구성](../../CLAUDE.md#인프라-구성)
- [CLAUDE.md - 환경 변수](../../CLAUDE.md#환경-변수)
- [scripts/diagnose-db.py](../../scripts/diagnose-db.py) - DB 연결 진단 도구
- [scripts/db-tunnel.sh](../../scripts/db-tunnel.sh) - SSH 터널 관리
