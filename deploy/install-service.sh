#!/bin/bash
#
# systemd 서비스 설치 스크립트
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_FILE="$SCRIPT_DIR/hantu.service"
PROJECT_DIR="/opt/hantu_quant"

echo "Hantu Quant systemd 서비스 설치"
echo "================================"

# 프로젝트 디렉토리 확인
if [ ! -d "$PROJECT_DIR" ]; then
    echo "Error: $PROJECT_DIR 디렉토리가 없습니다."
    exit 1
fi

# docker-compose.yml 확인
if [ ! -f "$PROJECT_DIR/docker-compose.yml" ]; then
    echo "Error: docker-compose.yml이 없습니다."
    exit 1
fi

# 서비스 파일 복사
echo "서비스 파일 설치 중..."
sudo cp "$SERVICE_FILE" /etc/systemd/system/hantu.service

# systemd 데몬 리로드
echo "systemd 리로드 중..."
sudo systemctl daemon-reload

# 서비스 활성화
echo "서비스 활성화 중..."
sudo systemctl enable hantu.service

echo ""
echo "설치 완료!"
echo ""
echo "사용 가능한 명령어:"
echo "  sudo systemctl start hantu    # 시작"
echo "  sudo systemctl stop hantu     # 중지"
echo "  sudo systemctl restart hantu  # 재시작"
echo "  sudo systemctl status hantu   # 상태 확인"
echo "  journalctl -u hantu -f        # 로그 확인"
echo ""
