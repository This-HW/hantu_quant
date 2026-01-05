#!/bin/bash
#
# Oracle Cloud Micro 인스턴스 설정 스크립트 (1GB RAM)
# Docker 없이 Native Python으로 구성
# 사용법: bash deploy/setup-micro.sh
#

set -e

echo "=========================================="
echo "  Hantu Quant - Micro Instance Setup"
echo "  (1GB RAM, Native Python)"
echo "=========================================="

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 1. 시스템 업데이트
log_info "시스템 업데이트 중..."
sudo apt-get update && sudo apt-get upgrade -y

# 2. Python 3 설치
log_info "Python 설치 중..."
sudo apt-get install -y python3 python3-pip python3-venv

# 3. 필수 패키지 설치
log_info "필수 패키지 설치 중..."
sudo apt-get install -y git curl htop

# 4. 타임존 설정
log_info "타임존 설정 (Asia/Seoul)..."
sudo timedatectl set-timezone Asia/Seoul

# 5. Swap 설정 (2GB - 1GB RAM 보완)
if [ ! -f /swapfile ]; then
    log_info "Swap 파일 생성 중 (2GB)..."
    sudo fallocate -l 2G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
else
    log_info "Swap 이미 설정됨"
fi

# 6. 방화벽 설정 (Oracle Cloud iptables)
log_info "방화벽 설정 중..."
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 8000 -j ACCEPT
sudo netfilter-persistent save 2>/dev/null || {
    sudo apt-get install -y iptables-persistent
    sudo netfilter-persistent save
}

# 7. 시스템 최적화 (메모리 절약)
log_info "시스템 최적화 설정 중..."
cat << 'EOF' | sudo tee /etc/sysctl.d/99-hantu-micro.conf
# 메모리 최적화 (1GB RAM)
vm.swappiness = 60
vm.dirty_ratio = 40
vm.dirty_background_ratio = 5
vm.vfs_cache_pressure = 50

# 네트워크 최적화
net.core.somaxconn = 512
net.ipv4.tcp_max_syn_backlog = 512
EOF
sudo sysctl -p /etc/sysctl.d/99-hantu-micro.conf

# 8. 프로젝트 디렉토리 설정
log_info "프로젝트 디렉토리 설정 중..."
if [ ! -d /opt/hantu_quant ]; then
    sudo mkdir -p /opt/hantu_quant
    sudo chown $USER:$USER /opt/hantu_quant
fi

# 데이터 디렉토리
mkdir -p /opt/hantu_quant/data/db
mkdir -p /opt/hantu_quant/logs

echo ""
log_info "=========================================="
log_info "  초기 설정 완료!"
log_info "=========================================="
echo ""
log_info "다음 단계:"
echo "  1. cd /opt/hantu_quant"
echo "  2. git clone <repo> . (또는 git pull)"
echo "  3. python3 -m venv venv"
echo "  4. source venv/bin/activate"
echo "  5. pip install --only-binary :all: numpy pandas scipy"
echo "  6. pip install -r requirements.txt"
echo "  7. pip install fastapi uvicorn python-multipart aiofiles"
echo "  8. cp .env.example .env && nano .env"
echo "  9. bash deploy/install-service-micro.sh"
echo ""
log_info "메모리 확인:"
free -h
echo ""
