# Hantu Quant - 경량 배포 가이드 (1GB RAM)

Oracle Cloud VM.Standard.E2.1.Micro (1GB RAM) 환경을 위한 배포 가이드입니다.

## 서버 스펙

| 항목 | 값 |
|------|-----|
| Shape | VM.Standard.E2.1.Micro |
| CPU | 1 OCPU (2 vCPU) |
| RAM | 1GB |
| Storage | 47GB |
| OS | Ubuntu 24.04 |

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

---

## 10. 구성 비교

| 구성 | Docker (권장) | Native (경량) |
|------|--------------|---------------|
| RAM 요구 | 2GB+ | 1GB |
| PostgreSQL | ✅ | ❌ (SQLite) |
| Redis | ✅ | ❌ |
| 설정 난이도 | 쉬움 | 중간 |
| 격리 | 컨테이너 | 없음 |

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
