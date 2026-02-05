#!/bin/bash

# Redis 설정 롤백 스크립트
# 용도: setup-redis.sh로 적용한 변경사항 원복
# 실행: sudo ./scripts/rollback-redis.sh

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 로그 함수
log_info() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warn() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# root 권한 확인
if [ "$EUID" -ne 0 ]; then
    log_error "이 스크립트는 sudo로 실행해야 합니다."
    echo "실행 방법: sudo ./scripts/rollback-redis.sh"
    exit 1
fi

# 환경 감지
if [[ "$PWD" == /opt/hantu_quant* ]]; then
    ENV_TYPE="server"
    APP_DIR="/opt/hantu_quant"
elif [[ "$PWD" == /home/ubuntu/hantu_quant* ]]; then
    ENV_TYPE="dev"
    APP_DIR="/home/ubuntu/hantu_quant_dev"
else
    log_error "알 수 없는 환경입니다. /opt/hantu_quant 또는 /home/ubuntu/hantu_quant_dev에서 실행하세요."
    exit 1
fi

log_info "환경: $ENV_TYPE"
log_info "앱 디렉토리: $APP_DIR"

echo ""
echo "=== Redis 설정 롤백 시작 ==="
echo ""

# 백업 파일 찾기
BACKUP_DIR=$(find /tmp -maxdepth 1 -type d -name "redis-backup-*" | sort -r | head -1)

if [ -z "$BACKUP_DIR" ]; then
    log_warn "백업 디렉토리를 찾을 수 없습니다."
    echo "수동 롤백을 진행합니다..."
    MANUAL_ROLLBACK=true
else
    log_info "백업 디렉토리: $BACKUP_DIR"
    MANUAL_ROLLBACK=false
fi

# ============================================================
# Step 1: .env 파일에서 REDIS_URL 제거
# ============================================================
echo "[Step 1] .env 파일 복구"

ENV_FILE="$APP_DIR/.env"

if [ -f "$ENV_FILE" ]; then
    # REDIS_URL 라인 제거
    sed -i '/^REDIS_URL=/d' "$ENV_FILE"
    sed -i '/# Redis 캐싱 시스템/d' "$ENV_FILE"

    log_info ".env 파일에서 REDIS_URL 제거 완료"
else
    log_warn ".env 파일이 없습니다."
fi

echo ""
# ============================================================
# Step 2: redis.conf 원복
# ============================================================
echo "[Step 2] redis.conf 복구"

REDIS_CONF="/etc/redis/redis.conf"

if [ "$MANUAL_ROLLBACK" = false ] && [ -f "$BACKUP_DIR/redis.conf.backup" ]; then
    # 백업에서 복구
    cp "$BACKUP_DIR/redis.conf.backup" "$REDIS_CONF"
    log_info "redis.conf 백업에서 복구 완료"
else
    # 수동 복구
    log_warn "백업 파일이 없습니다. 수동으로 redis.conf 초기화 중..."

    # requirepass 제거
    sed -i '/^requirepass/d' "$REDIS_CONF"

    # maxmemory 제거
    sed -i '/^maxmemory /d' "$REDIS_CONF"
    sed -i '/^maxmemory-policy/d' "$REDIS_CONF"

    # bind 기본값 복구 (보안: localhost 유지)
    sed -i 's/^bind .*/bind 127.0.0.1/' "$REDIS_CONF"

    # supervised 기본값 복구 (Ubuntu 기본값: systemd)
    sed -i 's/^supervised.*/supervised systemd/' "$REDIS_CONF"

    log_info "redis.conf 수동 초기화 완료"
fi

echo ""
# ============================================================
# Step 3: systemd 서비스 중지 및 삭제
# ============================================================
echo "[Step 3] systemd 서비스 정리"

# Redis 서비스 중지
if systemctl is-active --quiet redis-server; then
    systemctl stop redis-server
    log_info "Redis 서비스 중지 완료"
fi

# 자동 시작 비활성화
if systemctl is-enabled --quiet redis-server 2>/dev/null; then
    systemctl disable redis-server
    log_info "자동 시작 비활성화 완료"
fi

# systemd 서비스 파일 삭제 (선택)
# SYSTEMD_FILE="/etc/systemd/system/redis-server.service"
# if [ -f "$SYSTEMD_FILE" ]; then
#     rm "$SYSTEMD_FILE"
#     systemctl daemon-reload
#     log_info "systemd 서비스 파일 삭제 완료"
# fi

log_warn "systemd 서비스 파일은 유지됩니다. 완전 삭제 시 수동으로 제거하세요."

echo ""
# ============================================================
# Step 4: 애플리케이션 서비스 재시작
# ============================================================
echo "[Step 4] 애플리케이션 서비스 재시작"

if [ "$ENV_TYPE" == "server" ]; then
    if systemctl is-active --quiet hantu-api; then
        systemctl restart hantu-api
        sleep 2
        log_info "hantu-api 재시작 완료"
    fi

    if systemctl is-active --quiet hantu-scheduler; then
        systemctl restart hantu-scheduler
        sleep 2
        log_info "hantu-scheduler 재시작 완료"
    fi
else
    log_info "dev 환경이므로 서비스 재시작 생략"
fi

echo ""
# ============================================================
# Step 5: 검증
# ============================================================
echo "[검증]"

# Redis 서비스 상태
if systemctl is-active --quiet redis-server; then
    log_warn "Redis 서비스가 아직 실행 중입니다."
else
    log_info "Redis 서비스: 중지됨"
fi

# .env 파일 확인
if grep -q "REDIS_URL" "$ENV_FILE" 2>/dev/null; then
    log_warn ".env에 REDIS_URL이 여전히 존재합니다."
else
    log_info ".env에서 REDIS_URL 제거 확인"
fi

# MemoryCache 폴백 확인
if [ "$ENV_TYPE" == "server" ]; then
    log_info "애플리케이션 로그 확인 중..."

    if journalctl -u hantu-api -n 50 --since "1 minute ago" 2>/dev/null | grep -qi "MemoryCache"; then
        log_info "MemoryCache 폴백 확인됨"
    else
        log_warn "MemoryCache 폴백 확인 안 됨 (수동 확인 필요)"
        echo "로그 확인: journalctl -u hantu-api -n 100 | grep -i cache"
    fi
fi

echo ""
echo "=== 롤백 완료 ==="
echo ""
echo "다음 단계:"
echo "  1. 애플리케이션 로그 확인: journalctl -u hantu-api -f"
echo "  2. MemoryCache 동작 확인: hantu logs -n 100 | grep Cache"
echo "  3. Redis 서비스 완전 제거 (선택):"
echo "     sudo apt-get remove --purge redis-server"
echo "     sudo rm /etc/systemd/system/redis-server.service"
echo "     sudo systemctl daemon-reload"
echo ""

if [ "$MANUAL_ROLLBACK" = false ]; then
    echo "백업 파일 위치: $BACKUP_DIR"
    echo "백업 파일 삭제: rm -rf $BACKUP_DIR"
    echo ""
fi
