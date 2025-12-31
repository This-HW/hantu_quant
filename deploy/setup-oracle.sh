#!/bin/bash
#
# Oracle Cloud 서버 초기 설정 스크립트
# 사용법: curl -fsSL <url> | bash
#

set -e

echo "=========================================="
echo "  Hantu Quant - Oracle Cloud Setup"
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

# 2. Docker 설치
if ! command -v docker &> /dev/null; then
    log_info "Docker 설치 중..."
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker $USER
    log_warn "Docker 그룹 적용을 위해 재로그인 필요"
else
    log_info "Docker 이미 설치됨"
fi

# 3. Docker Compose 설치 (v2)
if ! docker compose version &> /dev/null; then
    log_info "Docker Compose 설치 중..."
    sudo apt-get install -y docker-compose-plugin
else
    log_info "Docker Compose 이미 설치됨"
fi

# 4. Git 설치
if ! command -v git &> /dev/null; then
    log_info "Git 설치 중..."
    sudo apt-get install -y git
fi

# 5. 프로젝트 디렉토리 생성
log_info "프로젝트 디렉토리 설정 중..."
sudo mkdir -p /opt/hantu_quant
sudo chown $USER:$USER /opt/hantu_quant

# 6. 타임존 설정
log_info "타임존 설정 (Asia/Seoul)..."
sudo timedatectl set-timezone Asia/Seoul

# 7. 방화벽 설정 (Oracle Cloud iptables)
log_info "방화벽 설정 중..."
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 8000 -j ACCEPT
sudo netfilter-persistent save 2>/dev/null || true

# 8. Swap 설정 (메모리 부족 대비)
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

# 9. 시스템 최적화
log_info "시스템 최적화 설정 중..."
cat << 'EOF' | sudo tee /etc/sysctl.d/99-hantu.conf
# 네트워크 최적화
net.core.somaxconn = 1024
net.ipv4.tcp_max_syn_backlog = 1024

# 메모리 최적화
vm.swappiness = 10
vm.dirty_ratio = 60
vm.dirty_background_ratio = 2
EOF
sudo sysctl -p /etc/sysctl.d/99-hantu.conf

echo ""
log_info "=========================================="
log_info "  초기 설정 완료!"
log_info "=========================================="
echo ""
log_info "다음 단계:"
echo "  1. 재로그인 (Docker 그룹 적용)"
echo "  2. cd /opt/hantu_quant"
echo "  3. git clone <your-repo> ."
echo "  4. cp .env.example .env && nano .env"
echo "  5. docker compose up -d"
echo ""
