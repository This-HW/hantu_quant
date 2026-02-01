# .pgpass 파일 인증 전환 - 서버 적용 가이드

## 개요

DB 비밀번호 관리를 환경변수에서 `.pgpass` 파일로 전환합니다.

**변경 내용:**

- 환경변수 `DB_PASSWORD` 제거
- `~/.pgpass` 파일로 비밀번호 관리
- 스크립트에서 `PGPASSWORD` 환경변수 제거

**적용 대상:**

- hantu-server (158.180.87.156)
- 로컬 환경 (/Users/grimm/)

---

## 사전 확인

### 1. 현재 DB 비밀번호 확인

```bash
# 서버에서 실행
echo $DB_PASSWORD

# 또는 .env 파일 확인
grep DB_PASSWORD /opt/hantu_quant/.env
```

비밀번호를 복사해두세요: `***REMOVED***`

---

## 서버 적용 단계

### Step 1: .pgpass 파일 생성 (서버)

```bash
# SSH 접속
ssh -i ~/.ssh/id_rsa ubuntu@158.180.87.156

# .pgpass 파일 생성
echo "localhost:5432:hantu_quant:hantu:***REMOVED***" > ~/.pgpass

# 권한 설정 (필수!)
chmod 600 ~/.pgpass

# 권한 확인
ls -la ~/.pgpass
# 출력: -rw------- 1 ubuntu ubuntu ... .pgpass
```

### Step 2: PostgreSQL 접속 테스트

```bash
# 비밀번호 입력 없이 접속되어야 함
psql -h localhost -U hantu -d hantu_quant -c "SELECT current_database(), current_user;"

# 성공 출력 예시:
#  current_database | current_user
# ------------------+--------------
#  hantu_quant      | hantu
```

### Step 3: 최신 코드 가져오기

```bash
cd /opt/hantu_quant

# 현재 상태 확인
git status

# 작업 중인 내용이 있으면 커밋 또는 stash
git stash

# 최신 코드 가져오기
git fetch origin main
git checkout main
git pull origin main

# 변경된 파일 확인
git log --oneline -5
```

### Step 4: .env 파일에서 DB_PASSWORD 제거

```bash
cd /opt/hantu_quant

# .env 파일 백업
cp .env .env.backup_$(date +%Y%m%d_%H%M)

# DB_PASSWORD 라인 제거 (주석 처리)
nano .env

# 또는 sed로 자동 처리
sed -i 's/^DB_PASSWORD=/#DB_PASSWORD=/' .env

# 확인
grep DB_PASSWORD .env
```

### Step 5: 환경변수 검증

```bash
cd /opt/hantu_quant

# 검증 실행
bash scripts/deployment/validate_env.sh

# 예상 출력:
# ✓ .pgpass: Exists with correct permissions (600)
# ✓ DB_HOST: Set
# ✓ DB_USER: Set
# ✓ DB_NAME: Set
# ...
# ✓ All required environment variables are set
# Validation: PASSED
```

### Step 6: 서비스 재시작

```bash
# 서비스 중지
sudo systemctl stop hantu-scheduler hantu-api

# 서비스 재시작
sudo systemctl restart hantu-scheduler hantu-api

# 상태 확인
sudo systemctl status hantu-scheduler hantu-api

# 로그 확인 (실시간)
journalctl -u hantu-scheduler -u hantu-api -f
```

### Step 7: DB 접속 테스트 (애플리케이션)

```bash
# Python 스크립트로 DB 접속 테스트
cd /opt/hantu_quant
source venv/bin/activate

python3 -c "
from core.config.database import get_db_engine
engine = get_db_engine()
with engine.connect() as conn:
    result = conn.execute('SELECT version()')
    print('DB 연결 성공:', result.fetchone()[0])
"
```

---

## 로컬 환경 적용 (선택)

### Step 1: .pgpass 파일 생성 (로컬)

```bash
# 이미 생성되어 있음 (/Users/grimm/.pgpass)
# 확인
ls -la ~/.pgpass

# 출력: -rw------- 1 grimm staff ... .pgpass
```

### Step 2: SSH 터널 확인

```bash
# SSH 터널 실행 (로컬 → 서버 DB)
ssh -i ~/.ssh/id_rsa -f -N -L 15432:localhost:5432 ubuntu@158.180.87.156

# 터널 상태 확인
lsof -i:15432
```

### Step 3: 로컬에서 DB 접속 테스트

```bash
# psql 설치 (Mac)
brew install postgresql@15

# 접속 테스트
psql -h localhost -p 15432 -U hantu -d hantu_quant -c "SELECT current_database();"

# 비밀번호 입력 없이 접속되어야 함
```

---

## 롤백 절차 (문제 발생 시)

### 서버에서 롤백

```bash
cd /opt/hantu_quant

# .env 파일 복원
cp .env.backup_YYYYMMDD_HHMM .env

# .pgpass 삭제
rm ~/.pgpass

# 서비스 재시작
sudo systemctl restart hantu-scheduler hantu-api

# 이전 코드로 복원 (필요시)
git fetch origin main
git reset --hard origin/main~1
```

---

## 확인 체크리스트

### 서버 적용 후 확인

- [ ] ~/.pgpass 파일이 600 권한으로 생성됨
- [ ] psql 명령으로 비밀번호 입력 없이 접속 가능
- [ ] scripts/deployment/validate_env.sh 통과
- [ ] hantu-scheduler 서비스 정상 실행 중
- [ ] hantu-api 서비스 정상 실행 중
- [ ] journalctl 로그에 DB 연결 에러 없음
- [ ] 애플리케이션에서 DB 접속 성공

### 로컬 적용 후 확인

- [ ] ~/.pgpass 파일이 600 권한으로 생성됨
- [ ] SSH 터널 실행 중
- [ ] psql -p 15432 접속 가능
- [ ] Python 애플리케이션에서 DB 접속 가능

---

## 문제 해결

### 문제 1: psql 접속 시 비밀번호 요청

**원인:** .pgpass 파일이 없거나 권한이 잘못됨

**해결:**

```bash
# 파일 존재 확인
ls -la ~/.pgpass

# 권한 확인 및 수정
chmod 600 ~/.pgpass

# 파일 내용 확인 (형식 검증)
cat ~/.pgpass
# 출력: localhost:5432:hantu_quant:hantu:***REMOVED***
```

### 문제 2: validate_env.sh 실패

**원인:** .pgpass 파일 권한이 600이 아님

**해결:**

```bash
chmod 600 ~/.pgpass
bash scripts/deployment/validate_env.sh
```

### 문제 3: 서비스 시작 실패

**원인:** .env 파일 손상 또는 필수 환경변수 누락

**해결:**

```bash
# .env 파일 복원
cp .env.backup_YYYYMMDD_HHMM .env

# 필수 환경변수 확인
grep -E '(DB_HOST|DB_USER|DB_NAME|TELEGRAM)' .env

# 서비스 재시작
sudo systemctl restart hantu-scheduler hantu-api
```

### 문제 4: "PGPASSWORD deprecated" 경고

**원인:** 일부 스크립트에서 아직 PGPASSWORD 환경변수 사용 중

**해결:**

```bash
# 해당 스크립트에서 PGPASSWORD 제거
# 예: scripts/auto-fix-errors.sh의 88번, 162번 라인
grep -rn "PGPASSWORD" /opt/hantu_quant/scripts/

# 각 파일에서 PGPASSWORD="$DB_PASS" 제거
```

---

## 참고 자료

- [PostgreSQL .pgpass 공식 문서](https://www.postgresql.org/docs/15/libpq-pgpass.html)
- [CLAUDE.md - 환경 변수 섹션](../CLAUDE.md#환경-변수)
- [SERVERS.md - DB 인증 방법](./SERVERS.md#db-인증-방법)
- [DEPLOY_MICRO.md - 환경 설정](./DEPLOY_MICRO.md#3-환경-설정)

---

## 보안 고려사항

### .pgpass 파일 보안

1. **권한 필수:** 600 (소유자만 읽기/쓰기)
2. **위치 고정:** ~/.pgpass (홈 디렉토리)
3. **Git 제외:** .gitignore에 포함되어 있음
4. **백업 주의:** 백업 시 권한 유지 필수

### 환경변수 vs .pgpass 비교

| 항목                 | 환경변수       | .pgpass         |
| -------------------- | -------------- | --------------- |
| 프로세스 노출        | ❌ 노출됨      | ✅ 노출 안 됨   |
| 로그 기록            | ❌ 기록될 수 O | ✅ 기록 안 됨   |
| 권한 제어            | ⚠️ 약함        | ✅ 강함 (600)   |
| 다중 DB 지원         | ❌ 어려움      | ✅ 여러 줄 가능 |
| PostgreSQL 공식 지원 | ❌             | ✅              |

---

## 적용 일정

- **계획일:** 2026-02-01
- **적용 대상:**
  - 로컬 환경: 즉시 적용 완료
  - 서버 환경: 사용자 확인 후 적용
- **롤백 가능 기간:** 1주일
