# Hantu Quant - Oracle Cloud 배포 가이드

## 리소스 사용량 (여유있는 구성)

| 서비스 | CPU | RAM | 용도 |
|--------|-----|-----|------|
| PostgreSQL | 0.5 | 512MB | 데이터베이스 |
| Redis | 0.25 | 256MB | 캐시 |
| scheduler | 0.5 | 512MB | 자동 스크리닝 |
| api | 0.5 | 512MB | REST API |
| **합계** | **1.75** | **~2GB** | |

> 4코어/24GB 중 약 8% 사용 → 다른 프로젝트 2-3개 여유

---

## 1. Oracle Cloud VM 생성

### 1.1 계정 생성
1. https://cloud.oracle.com 접속
2. 무료 계정 생성 (신용카드 필요하지만 과금 안 됨)
3. 홈 리전 선택 (서울/도쿄/싱가포르 권장)

### 1.2 VM 인스턴스 생성
1. Compute → Instances → Create Instance
2. 설정:
   - **Image**: Oracle Linux 8 또는 Ubuntu 22.04
   - **Shape**: VM.Standard.A1.Flex (ARM)
   - **OCPU**: 1 (나중에 늘릴 수 있음)
   - **Memory**: 6GB (나중에 늘릴 수 있음)
   - **Boot volume**: 50GB
3. SSH 키 추가 (다운로드 또는 기존 키 업로드)
4. Create 클릭

### 1.3 네트워크 설정
1. 인스턴스 상세 → Attached VNICs → Subnet
2. Security Lists → Ingress Rules 추가:
   - Source: 0.0.0.0/0
   - Port: 8000 (API용, 필요시)

---

## 2. 서버 초기 설정

### 2.1 SSH 접속
```bash
ssh -i <your-key.pem> ubuntu@<public-ip>
```

### 2.2 자동 설정 스크립트 실행
```bash
# 원격 스크립트 실행 (프로젝트 업로드 후)
bash deploy/setup-oracle.sh

# 또는 수동으로
sudo apt update && sudo apt upgrade -y
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
```

### 2.3 재로그인
```bash
exit
ssh -i <your-key.pem> ubuntu@<public-ip>
```

---

## 3. 프로젝트 배포

### 3.1 코드 배포
```bash
cd /opt/hantu_quant

# 방법 1: Git clone
git clone https://github.com/This-HW/hantu_quant.git .

# 방법 2: SCP 업로드
scp -r -i <key.pem> ./hantu_quant/* ubuntu@<ip>:/opt/hantu_quant/
```

### 3.2 환경 설정
```bash
cp .env.example .env
nano .env  # API 키 등 설정
```

필수 설정:
```env
# 한국투자증권 API
APP_KEY="한국투자증권 API 키"
APP_SECRET="한국투자증권 API 시크릿"
ACCOUNT_NUMBER="계좌번호"
SERVER="virtual"  # 또는 "prod"

# 텔레그램 알림
TELEGRAM_BOT_TOKEN="텔레그램 봇 토큰"
TELEGRAM_CHAT_ID="채팅 ID"

# 데이터베이스 (보안을 위해 반드시 변경!)
DB_USER="hantu"
DB_PASSWORD="your_strong_password_here"
DB_NAME="hantu_quant"
```

### 3.3 Docker 빌드 및 실행
```bash
# 전체 서비스 실행 (PostgreSQL + Redis + Scheduler + API)
docker compose up -d

# 로그 확인
docker compose logs -f

# 개별 서비스 로그
docker compose logs -f scheduler
docker compose logs -f postgres
```

---

## 4. 자동 시작 설정 (systemd)

```bash
# 서비스 설치
bash deploy/install-service.sh

# 서비스 시작
sudo systemctl start hantu

# 상태 확인
sudo systemctl status hantu
```

서버 재부팅 시 자동으로 시작됨.

---

## 5. 관리 명령어

### Docker 명령어
```bash
# 상태 확인
docker compose ps

# 로그 확인
docker compose logs -f scheduler
docker compose logs -f api

# 재시작
docker compose restart

# 중지
docker compose down

# 업데이트
git pull
docker compose up -d --build
```

### systemd 명령어
```bash
sudo systemctl start hantu
sudo systemctl stop hantu
sudo systemctl restart hantu
sudo systemctl status hantu
journalctl -u hantu -f  # 로그
```

---

## 6. 모니터링

### 리소스 사용량 확인
```bash
# Docker 리소스
docker stats

# 시스템 전체
htop
free -h
df -h
```

### 헬스체크
```bash
# API 헬스체크
curl http://localhost:8000/health

# PostgreSQL 상태
docker compose exec postgres pg_isready

# Redis 상태
docker compose exec redis redis-cli ping

# 스케줄러 프로세스 확인
docker compose exec scheduler pgrep -f integrated_scheduler
```

### 데이터베이스 접속
```bash
# PostgreSQL CLI 접속
docker compose exec postgres psql -U hantu -d hantu_quant

# 테이블 확인
\dt

# 종료
\q
```

---

## 7. 문제 해결

### 컨테이너가 재시작 반복
```bash
# 로그 확인
docker compose logs scheduler --tail=100

# 메모리 부족 확인
docker stats
free -h
```

### Out of Capacity 에러 (VM 생성 시)
- 다른 리전 시도 (도쿄, 싱가포르)
- 시간대 변경 후 재시도 (새벽 시간)
- Shape을 VM.Standard.E2.1.Micro로 변경 시도

### Idle 인스턴스 경고
```bash
# cron으로 주기적 활동 생성
crontab -e
# 추가:
*/10 * * * * curl -s http://localhost:8000/health > /dev/null 2>&1
```

---

## 8. 비용

| 항목 | 비용 |
|------|------|
| VM (Always Free) | $0 |
| Storage 50GB | $0 (200GB까지 무료) |
| Network 10TB | $0 |
| **총 월 비용** | **$0** |

---

## 요약

```bash
# 1. VM 생성 후 SSH 접속
ssh ubuntu@<ip>

# 2. 초기 설정
bash deploy/setup-oracle.sh
exit && ssh ubuntu@<ip>

# 3. 코드 배포
cd /opt/hantu_quant
git clone <repo> .
cp .env.example .env && nano .env

# 4. 실행
docker compose up -d

# 5. 자동 시작 설정
bash deploy/install-service.sh
sudo systemctl enable hantu
```
