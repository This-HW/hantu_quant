#!/bin/bash
#
# Micro 인스턴스용 systemd 서비스 설치 스크립트
# Native Python 배포용
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="/opt/hantu_quant"

echo "========================================"
echo "  Hantu Quant - Micro Instance Services"
echo "========================================"

# 색상 정의
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

# 프로젝트 디렉토리 확인
if [ ! -d "$PROJECT_DIR" ]; then
    echo "Error: $PROJECT_DIR 디렉토리가 없습니다."
    exit 1
fi

# venv 확인
if [ ! -d "$PROJECT_DIR/venv" ]; then
    echo "Error: Python venv가 없습니다. 먼저 설정하세요."
    exit 1
fi

# 서비스 설치 함수
install_service() {
    local service_name=$1
    local service_file="$SCRIPT_DIR/${service_name}.service"

    if [ ! -f "$service_file" ]; then
        log_warn "$service_file 파일이 없습니다. 건너뜁니다."
        return
    fi

    log_info "$service_name 서비스 설치 중..."
    sudo cp "$service_file" /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable "$service_name"
}

# 서비스 선택
echo ""
echo "설치할 서비스를 선택하세요:"
echo "  1) hantu-scheduler (스케줄러만)"
echo "  2) hantu-api (API 서버만)"
echo "  3) 둘 다 설치"
echo ""
read -p "선택 [1-3]: " choice

case $choice in
    1)
        install_service "hantu-scheduler"
        ;;
    2)
        install_service "hantu-api"
        ;;
    3)
        install_service "hantu-scheduler"
        install_service "hantu-api"
        ;;
    *)
        echo "잘못된 선택입니다."
        exit 1
        ;;
esac

echo ""
log_info "========================================"
log_info "  설치 완료!"
log_info "========================================"
echo ""
echo "사용 가능한 명령어:"
echo ""
echo "  # 스케줄러"
echo "  sudo systemctl start hantu-scheduler"
echo "  sudo systemctl stop hantu-scheduler"
echo "  sudo systemctl status hantu-scheduler"
echo "  journalctl -u hantu-scheduler -f"
echo ""
echo "  # API 서버"
echo "  sudo systemctl start hantu-api"
echo "  sudo systemctl stop hantu-api"
echo "  sudo systemctl status hantu-api"
echo "  journalctl -u hantu-api -f"
echo ""
echo "  # 모든 서비스 시작"
echo "  sudo systemctl start hantu-scheduler hantu-api"
echo ""
