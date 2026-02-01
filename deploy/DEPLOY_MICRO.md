# Hantu Quant - 경량 배포 가이드 (1GB RAM)

Oracle Cloud VM.Standard.E2.1.Micro (1GB RAM) 환경을 위한 배포 가이드입니다.

## 서버 스펙

| 항목    | 값                     |
| ------- | ---------------------- |
| Shape   | VM.Standard.E2.1.Micro |
| CPU     | 1 OCPU (2 vCPU)        |
| RAM     | 1GB                    |
| Storage | 47GB                   |
| OS      | Ubuntu 24.04           |

---

## 1. 초기 설정

### 빠른 설정 (스크립트)

```bash
# 프로젝트가 이미 clone 되어 있다면:
cd /opt/hantu_quant
bash deploy/setup-micro.sh
```

### 수동 설정

#### 시스템 업데이트

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl htop python3-pip python3-venv
```

### Swap 설정 (필수!)

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### 타임존 설정

```bash
sudo timedatectl set-timezone Asia/Seoul
```

---

## 2. 프로젝트 배포

### 디렉토리 생성 및 Clone

```bash
sudo mkdir -p /opt/hantu_quant
sudo chown $USER:$USER /opt/hantu_quant
cd /opt/hantu_quant
git clone https://github.com/This-HW/hantu_quant.git .
```

### 가상환경 생성

```bash
python3 -m venv venv
source venv/bin/activate
```

### 의존성 설치 (Python 3.12+ 호환)

⚠️ Python 3.12에서는 setuptools 호환성 문제로 바이너리 설치 필요:

```bash
# pip/setuptools 업그레이드
pip install --upgrade pip setuptools wheel

# 과학 패키지는 바이너리로 설치
pip install --only-binary :all: numpy pandas scipy

# 메인 requirements 설치
pip install -r requirements.txt

# API 서버 의존성 설치
pip install fastapi uvicorn python-multipart aiofiles
```

---

## 3. 환경 설정

### 3.1. .pgpass 파일 설정 (PostgreSQL 인증)

**DB 비밀번호는 환경변수 대신 .pgpass 파일로 관리합니다.**

```bash
# .pgpass 파일 생성
echo "localhost:5432:hantu_quant:hantu:PASSWORD" > ~/.pgpass

# 권한 설정 (필수!)
chmod 600 ~/.pgpass

# 권한 확인
ls -la ~/.pgpass
# 출력: -rw------- 1 ubuntu ubuntu ... .pgpass
```

**형식 설명**:

- `hostname:port:database:username:password`
- 서버 환경: `localhost:5432` (DB가 같은 머신에 있음)
- 로컬 환경: `localhost:15432` (SSH 터널 사용 시)

### 3.2. 환경변수 설정

```bash
cp .env.example .env
nano .env
```

### 필수 설정

```env
# 한국투자증권 API
APP_KEY="your_key"
APP_SECRET="your_secret"
ACCOUNT_NUMBER="your_account"
SERVER="prod"

# 텔레그램
TELEGRAM_BOT_TOKEN="your_token"
TELEGRAM_CHAT_ID="your_chat_id"

# API 서버
API_HOST="0.0.0.0"
API_PORT="8000"
API_SERVER_KEY=""  # 빈 값 = 인증 없음

# 로깅
LOG_LEVEL="INFO"
```

---

## 4. 방화벽 설정

**중요**: REJECT 규칙 앞에 추가해야 합니다!

```bash
# 현재 규칙 확인 (REJECT 위치 파악)
sudo iptables -L INPUT -n --line-numbers

# REJECT 규칙 앞 위치에 추가 (보통 5번)
sudo iptables -I INPUT 5 -m state --state NEW -p tcp --dport 8000 -j ACCEPT

# 저장
sudo netfilter-persistent save
```

**OCI Security List도 설정 필요**:

- OCI Console → Networking → VCN → Security Lists
- Ingress Rule 추가: TCP, Port 8000, Source 0.0.0.0/0

---

## 5. 서비스 테스트

```bash
cd /opt/hantu_quant
source venv/bin/activate

# API 서버 테스트
python api-server/main.py

# 스케줄러 테스트
python -m workflows.integrated_scheduler start
```

---

## 6. systemd 서비스 설정

### 방법 1: 설치 스크립트 사용 (권장)

```bash
cd /opt/hantu_quant
bash deploy/install-service-micro.sh
```

스크립트 실행 후 설치할 서비스 선택:

- `1` - 스케줄러만
- `2` - API 서버만
- `3` - 둘 다

### 방법 2: 수동 설치

```bash
# 서비스 파일 복사
sudo cp deploy/hantu-api.service /etc/systemd/system/
sudo cp deploy/hantu-scheduler.service /etc/systemd/system/

# 데몬 리로드 및 활성화
sudo systemctl daemon-reload
sudo systemctl enable hantu-api hantu-scheduler
```

### 서비스 시작

```bash
sudo systemctl start hantu-api hantu-scheduler
```

### 상태 확인

```bash
sudo systemctl status hantu-api
sudo systemctl status hantu-scheduler
```

---

## 7. 관리 명령어

```bash
# 서비스 상태
sudo systemctl status hantu-api
sudo systemctl status hantu-scheduler

# 로그 확인
journalctl -u hantu-api -f
journalctl -u hantu-scheduler -f

# 재시작
sudo systemctl restart hantu-api hantu-scheduler

# 중지
sudo systemctl stop hantu-api hantu-scheduler
```

---

## 8. 메모리 모니터링

```bash
# 메모리 상태
free -h

# 프로세스별 메모리
ps aux --sort=-%mem | head

# 실시간 모니터링
htop
```

---

## 9. 문제 해결

### Python 3.12 setuptools 에러

```
AttributeError: module 'pkgutil' has no attribute 'ImpImporter'
```

**해결:**

```bash
pip install --upgrade pip setuptools wheel
pip install --only-binary :all: numpy pandas scipy
```

### 메모리 부족 (OOM Killer)

```bash
# Swap 확인
free -h

# Swap 사용량 높으면 서비스 메모리 최적화 필요
```

### API 접속 안 됨

```bash
# 방화벽 확인
sudo iptables -L -n | grep 8000

# 프로세스 확인
sudo ss -tlnp | grep 8000
```

### psycopg2 모듈 누락 (2026-01-29 해결)

**증상:**

```
WARNING - 통합 DB 초기화 실패, SQLite 폴백 사용: No module named 'psycopg2'
```

**원인:**

- 가상환경에 여러 Python 버전이 혼재 (3.9, 3.12, 3.14)
- psycopg2가 다른 Python 버전 디렉토리에만 설치됨
- 실행 중인 Python 버전과 psycopg2 설치 위치 불일치

**진단:**

```bash
# 가상환경 Python 버전 확인
venv/bin/python --version

# psycopg2 임포트 테스트
venv/bin/python -c "import psycopg2; print(psycopg2.__version__)"

# 가상환경 구조 확인
ls -la venv/lib/
```

**해결:**

```bash
# 현재 가상환경에 psycopg2 재설치
venv/bin/pip install --force-reinstall psycopg2-binary

# 설치 확인
venv/bin/python -c "import psycopg2; print('✅ 설치 성공:', psycopg2.__version__)"
```

### systemd 설정 변경 경고 (2026-01-29 해결)

**증상:**

```
Warning: The unit file, source configuration file or drop-ins of hantu-scheduler.service changed on disk. Run 'systemctl daemon-reload' to reload units.
```

**원인:**

- systemd 서비스 파일이 수정되었으나 daemon이 리로드되지 않음

**해결:**

```bash
# systemd 설정 리로드
sudo systemctl daemon-reload

# 서비스 재시작
sudo systemctl restart hantu-scheduler.service hantu-api.service

# 상태 확인
sudo systemctl status hantu-scheduler.service hantu-api.service
```

---

## 10. Auto-Fix Error Improvements (자동 에러 수정 개선)

### 개요

배포 프로세스의 안정성과 신뢰성을 향상시키기 위해 5가지 자동화 개선 사항이 구현되었습니다:

1. **배포 상태 추적** - JSON 기반 상태 관리
2. **배포 전 검증** - 메모리 및 환경변수 검증
3. **재시도 로직** - 실패 시 자동 재시도 (최대 3회)
4. **로그 순환** - 자동 압축 및 삭제
5. **알림 강화** - 3가지 새로운 텔레그램 알림

#### 배포 플로우 다이어그램

```
┌─────────────────────────────────────────────────┐
│ 1. Git Push (main 브랜치)                        │
└────────────────┬────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│ 2. GitHub Actions CI 트리거                      │
└────────────────┬────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│ 3. Pre-Deployment Checks                        │
│    ├─ Memory Check (≥800MB available)           │
│    └─ Env Validation (required vars)            │
└────────────────┬────────────────────────────────┘
                 │
        ┌────────┴────────┐
        │                 │
     PASS              FAIL
        │                 │
        ▼                 ▼
┌──────────────┐  ┌──────────────────────────┐
│ 4. Deploy    │  │ Update State (failed)    │
│              │  │ Send Alert (if ≥2)       │
└──────┬───────┘  │ Wait 5 min & Retry       │
       │          └──────────────────────────┘
       ▼
┌──────────────────────────────────────────────┐
│ 5. Update State (success) & Reset Failures  │
└──────────────────────────────────────────────┘
```

---

### Pre-Deployment Checks (배포 전 검증)

배포 전 시스템 상태를 검증하여 실패 가능성을 사전 차단합니다.

#### 1. 메모리 가용성 검사

**임계값**: 800MB 이상 가용 메모리 필요

```bash
# 수동 실행
bash scripts/deployment/pre_checks.sh check-memory
```

**출력 예시**:

```
[2026-01-22 14:30:00 KST] [INFO] Checking memory availability...
[2026-01-22 14:30:00 KST] [INFO] Available memory: 950 MB (Threshold: 800 MB)
[2026-01-22 14:30:00 KST] [INFO] Memory check passed: 950 MB available
```

**실패 시 동작**:

- 배포 차단
- 메모리 부족 알림 전송 (Telegram)
- 재시도 대기 (5분 + 추가 60초)

#### 2. 환경변수 검증

**필수 환경변수**:

- `DB_HOST`, `DB_USER`, `DB_NAME` (DB_PASSWORD는 .pgpass로 관리)
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`

**선택 환경변수** (경고만 표시):

- `KIS_APP_KEY`, `KIS_APP_SECRET`, `KIS_ACCOUNT_NO`
- `API_SERVER_KEY`

```bash
# 수동 실행
bash scripts/deployment/validate_env.sh
```

**출력 예시 (성공)**:

```
==========================================
Environment Variable Validation
==========================================

Checking PostgreSQL authentication...
✓ .pgpass: Exists with correct permissions (600)

Checking required variables...
✓ DB_HOST: Set
✓ DB_USER: Set
✓ DB_NAME: Set
✓ TELEGRAM_BOT_TOKEN: Set
✓ TELEGRAM_CHAT_ID: Set

Checking optional variables...
✓ KIS_APP_KEY: Set
⚠ KIS_APP_SECRET: Missing (Optional)

==========================================
✓ All required environment variables are set
Validation: PASSED
```

**실패 시 동작**:

- 배포 차단
- 누락된 변수 목록 표시
- 환경변수 검증 실패 알림 전송 (Telegram)

---

### State Management (상태 관리)

배포 상태를 JSON 파일로 추적하여 연속 실패를 감지하고 적절히 대응합니다.

#### 상태 파일 위치

```
/opt/hantu_quant/.deploy_state.json
```

#### 상태 구조

```json
{
  "consecutive_failures": 0,
  "last_success": "2026-01-22T05:30:00Z",
  "last_attempt": "2026-01-22T06:00:00Z",
  "attempts": 15,
  "last_status": "success",
  "last_reason": "Deployment succeeded on attempt 1"
}
```

#### 상태 확인

```bash
# 전체 상태 조회
bash scripts/deployment/state_manager.sh get-state

# 연속 실패 횟수만 조회
bash scripts/deployment/state_manager.sh get-failures

# 마지막 성공 시간 조회
bash scripts/deployment/state_manager.sh get-success
```

**출력 예시**:

```bash
$ bash scripts/deployment/state_manager.sh get-state
{
  "consecutive_failures": 2,
  "last_success": "2026-01-21T08:00:00Z",
  "last_attempt": "2026-01-22T06:15:00Z",
  "attempts": 18,
  "last_status": "failed",
  "last_reason": "Memory check failed"
}

$ bash scripts/deployment/state_manager.sh get-failures
2
```

#### 상태 초기화 (수동)

연속 실패 카운터를 수동으로 리셋할 수 있습니다:

```bash
# 방법 1: state_manager.sh 사용
bash scripts/deployment/state_manager.sh reset

# 방법 2: reset_state.sh 사용 (대화형)
bash scripts/deployment/reset_state.sh
```

**출력 예시**:

```
========================================
Deployment State Reset
========================================

Current State:
{
  "consecutive_failures": 3,
  "last_status": "failed",
  "last_reason": "Build failed"
}

Are you sure you want to reset the state? (y/N): y

State reset successfully

New State:
{
  "consecutive_failures": 0,
  "last_status": "reset",
  "last_reason": "Manual reset"
}
```

---

### Log Rotation (로그 순환)

디스크 공간 절약을 위해 오래된 로그를 자동으로 압축 및 삭제합니다.

#### Cron 스케줄

매일 새벽 2시 (KST)에 자동 실행:

```bash
# Cron 설정 확인
crontab -l | grep log_rotate

# 출력:
# 0 2 * * * cd /opt/hantu_quant && bash scripts/log_rotate.sh >> logs/log_rotate.log 2>&1
```

#### 정책

| 로그 나이 | 동작             |
| --------- | ---------------- |
| 7일 이하  | 유지 (압축 없음) |
| 8~30일    | gzip 압축        |
| 31일 이상 | 삭제             |

#### 수동 실행

```bash
cd /opt/hantu_quant
bash scripts/log_rotate.sh
```

**출력 예시**:

```
========================================
Log Rotation Started
========================================
Time: 2026-01-22 02:00:00 KST

Compressing logs older than 7 days...
  Compressed: logs/***REMOVED***-01-14.log → logs/***REMOVED***-01-14.log.gz
  Compressed: logs/***REMOVED***-01-13.log → logs/***REMOVED***-01-13.log.gz

Deleting logs older than 30 days...
  Deleted: logs/hantu_quant_2025-12-20.log.gz
  Deleted: logs/hantu_quant_2025-12-19.log.gz

Space saved: 45 MB

========================================
Log Rotation Completed
========================================
```

---

### Telegram Alerts (텔레그램 알림)

배포 상태를 실시간으로 모니터링하고 문제 발생 시 즉시 알림을 받습니다.

#### 새로운 알림 유형

##### 1. 배포 연속 실패 알림 (Critical)

**트리거 조건**: 연속 실패 ≥ 2회

**우선순위**:

- 2~4회 실패: High (⚠️)
- 5회 이상 실패: Critical (🚨🚨🚨)

**알림 예시**:

````
🚨 배포 연속 실패 알림

⏰ 시간: 2026-01-22 06:15:30
🔴 상태: 배포 실패
📊 연속 실패: 3회

⚠️ 조속한 확인 필요

📝 배포 정보:
• 브랜치: main
• 커밋: a1b2c3d4
• 마지막 성공: 2026-01-21T08:00:00Z
• 실패 이유: Memory check failed

🔧 조치 사항:
1. 서버 로그 확인
2. 배포 스크립트 점검
3. 환경 변수 검증
4. 의존성 확인

💡 수동 배포:
```bash
cd /opt/hantu_quant
git pull origin main
./scripts/deployment/deploy.sh
````

```

##### 2. 메모리 부족 알림 (High/Critical)

**트리거 조건**: 가용 메모리 < 800MB

**우선순위**:
- 재시도 1~2회: High (⚠️)
- 재시도 3회 이상: Critical (🚨)

**알림 예시**:
```

⚠️ 메모리 부족 알림

⏰ 시간: 2026-01-22 06:15:30
📊 메모리 사용: 650 MB / 800 MB (81.3%)
🔄 재시도: 2회

조속한 확인 필요

🔍 원인 분석:
• 대량 데이터 처리 중일 수 있음
• 메모리 누수 가능성
• 시스템 리소스 부족

🔧 권장 조치:

1. 실행 중인 프로세스 확인
2. 불필요한 프로세스 종료
3. 시스템 재시작 고려
4. 메모리 임계값 조정

💡 시스템 확인:

```bash
free -m
ps aux --sort=-%mem | head -10
systemctl status hantu-*
```

```

##### 3. 환경변수 검증 실패 알림 (Critical)

**트리거 조건**: 필수 환경변수 누락

**우선순위**: Critical (🚨)

**알림 예시**:
```

🚨 환경변수 검증 실패

⏰ 시간: 2026-01-22 06:15:30
🔴 상태: 필수 환경변수 누락
📊 누락 개수: 2개

⚠️⚠️⚠️ 배포 차단됨 ⚠️⚠️⚠️

📝 누락된 환경변수:
• TELEGRAM_BOT_TOKEN

📦 데이터베이스 인증:
• .pgpass 파일 확인 필요

📦 데이터베이스 설정:

```bash
DB_HOST=localhost
DB_PORT=5432
DB_USER=hantu_user
DB_PASSWORD=your_password
DB_NAME=hantu_quant
```

🔧 조치 방법:

1. 서버 접속

   ```bash
   ssh ubuntu@서버IP
   cd /opt/hantu_quant
   ```

2. 환경변수 설정

   ```bash
   nano .env
   # 누락된 변수 추가
   ```

3. 검증 및 재배포
   ```bash
   ./scripts/deployment/validate_env.sh
   ./scripts/deployment/deploy.sh
   ```

````

#### 알림 설정

환경변수로 설정:

```bash
# .env 파일
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
````

---

### Troubleshooting (문제 해결)

#### 메모리 부족 이슈

**증상**:

- 배포 실패 (메모리 체크 실패)
- 메모리 부족 알림 수신
- OOM Killer 발동

**진단**:

```bash
# 1. 현재 메모리 상태 확인
free -m

# 2. 메모리 사용 프로세스 확인
ps aux --sort=-%mem | head -10

# 3. Swap 사용량 확인
swapon --show
```

**해결 방법**:

1. **임시 조치**: 메모리 정리

   ```bash
   # 캐시 정리
   sudo sync && sudo sysctl -w vm.drop_caches=3

   # 불필요한 프로세스 종료
   sudo systemctl stop hantu-api  # 임시로 API 서버 중지
   ```

2. **영구 조치**: Swap 증설

   ```bash
   # 기존 swap 확인
   free -h

   # Swap 크기 증가 (2GB → 4GB)
   sudo swapoff /swapfile
   sudo fallocate -l 4G /swapfile
   sudo mkswap /swapfile
   sudo swapon /swapfile
   ```

3. **근본 해결**: 메모리 최적화
   - 스크리닝 배치 크기 축소
   - 불필요한 데이터 캐싱 제거
   - 서버 업그레이드 고려 (2GB+ RAM)

#### 연속 배포 실패

**증상**:

- 배포 연속 실패 알림 수신
- `consecutive_failures ≥ 2`

**진단**:

```bash
# 1. 배포 상태 확인
bash scripts/deployment/state_manager.sh get-state

# 2. 최근 로그 확인
journalctl -u hantu-scheduler -n 50

# 3. 환경변수 검증
bash scripts/deployment/validate_env.sh
```

**해결 방법**:

1. **로그 분석**: 실패 원인 파악

   ```bash
   # CI/CD 로그 확인
   gh run list --limit 5
   gh run view [run-id] --log
   ```

2. **상태 초기화**: 문제 해결 후

   ```bash
   # 상태 리셋
   bash scripts/deployment/reset_state.sh

   # 수동 배포
   git pull origin main
   bash scripts/deployment/pre_checks.sh check-all
   # 문제 없으면 배포 진행
   ```

3. **환경 복구**:

   ```bash
   # 환경변수 재설정
   nano .env

   # 의존성 재설치
   source venv/bin/activate
   pip install -r requirements.txt
   ```

#### 환경변수 문제

**증상**:

- 환경변수 검증 실패
- 서비스 시작 실패

**진단**:

```bash
# 환경변수 검증
bash scripts/deployment/validate_env.sh

# .env 파일 존재 확인
ls -la /opt/hantu_quant/.env

# 권한 확인
stat /opt/hantu_quant/.env
```

**해결 방법**:

1. **.pgpass 파일 설정**:

   ```bash
   # .pgpass 파일 생성
   echo "localhost:5432:hantu_quant:hantu:PASSWORD" > ~/.pgpass
   chmod 600 ~/.pgpass
   ```

2. **.env 파일 생성**:

   ```bash
   cd /opt/hantu_quant
   cp .env.example .env
   nano .env  # 실제 값 입력
   ```

3. **누락된 변수 추가**:

   ```bash
   # .env 파일 수정
   nano .env

   # 필수 변수 확인 (validate_env.sh 참조)
   DB_HOST=localhost
   TELEGRAM_BOT_TOKEN=your_token
   TELEGRAM_CHAT_ID=your_chat_id
   ```

4. **서비스 재시작**:
   ```bash
   sudo systemctl restart hantu-scheduler hantu-api
   sudo systemctl status hantu-scheduler hantu-api
   ```

#### 상태 파일 손상

**증상**:

- `jq` 파싱 에러
- 상태 조회 실패

**진단**:

```bash
# 상태 파일 확인
cat /opt/hantu_quant/.deploy_state.json

# JSON 유효성 검증
jq . /opt/hantu_quant/.deploy_state.json
```

**해결 방법**:

1. **상태 파일 재생성**:

   ```bash
   # 백업
   mv /opt/hantu_quant/.deploy_state.json /opt/hantu_quant/.deploy_state.json.bak

   # 재초기화
   bash scripts/deployment/state_manager.sh init
   ```

2. **수동 복구** (백업이 있는 경우):

   ```bash
   # 백업에서 복원
   cp /opt/hantu_quant/.deploy_state.json.bak /opt/hantu_quant/.deploy_state.json

   # 검증
   jq . /opt/hantu_quant/.deploy_state.json
   ```

---

### Testing (테스트)

배포 개선 사항을 로컬에서 테스트할 수 있습니다.

#### 테스트 위치

```
tests/deployment/
├── test_state_manager.sh        # 상태 관리 단위 테스트
├── test_validate_env.sh          # 환경변수 검증 단위 테스트
└── test_integration_deploy.sh    # 배포 플로우 통합 테스트
```

#### 테스트 실행

```bash
cd /Users/grimm/Documents/Dev/hantu_quant

# 1. 상태 관리 테스트 (6개 테스트)
bash tests/deployment/test_state_manager.sh

# 2. 환경변수 검증 테스트 (6개 테스트)
bash tests/deployment/test_validate_env.sh

# 3. 통합 테스트 (8개 시나리오)
bash tests/deployment/test_integration_deploy.sh

# 전체 테스트 실행
for test in tests/deployment/test_*.sh; do
    echo "Running: $test"
    bash "$test"
    echo ""
done
```

#### 예상 출력

**성공 시**:

```
==========================================
State Manager Unit Tests
==========================================

Test state file: /tmp/test_state_manager_12345.json

✓ PASS: test_init_state
✓ PASS: test_update_state_success
✓ PASS: test_update_state_failed
✓ PASS: test_get_consecutive_failures
✓ PASS: test_reset_state
✓ PASS: test_get_attempts

==========================================
Test Summary
==========================================
Total:  6
Passed: 6
Failed: 0

✓ All tests passed!
```

#### 테스트 커버리지

| 테스트 파일                | 커버리지                          |
| -------------------------- | --------------------------------- |
| test_state_manager.sh      | 상태 초기화, 업데이트, 조회, 리셋 |
| test_validate_env.sh       | 필수/선택 변수 검증, 에러 처리    |
| test_integration_deploy.sh | 전체 배포 플로우, 재시도, 알림    |

**테스트 시나리오 (통합 테스트)**:

1. State file initialization
2. Pre-deployment checks (env validation)
3. Deployment success handling
4. Deployment failure handling
5. Retry logic with multiple attempts
6. Alert triggering at ≥2 failures
7. State reset on success
8. State persistence

---

## 11. 구성 비교

| 구성        | Docker (권장) | Native (경량) |
| ----------- | ------------- | ------------- |
| RAM 요구    | 2GB+          | 1GB           |
| PostgreSQL  | ✅            | ❌ (SQLite)   |
| Redis       | ✅            | ❌            |
| 설정 난이도 | 쉬움          | 중간          |
| 격리        | 컨테이너      | 없음          |

---

## 체크리스트

```
[ ] 시스템 업데이트
[ ] Swap 2GB 설정
[ ] 타임존 Asia/Seoul
[ ] 프로젝트 Clone
[ ] 가상환경 생성
[ ] 바이너리 패키지 설치 (numpy, pandas, scipy)
[ ] requirements.txt 설치
[ ] api-server 의존성 설치
[ ] .env 설정
[ ] 방화벽 8000 포트
[ ] systemd 서비스 등록
[ ] 서비스 시작 확인
```
