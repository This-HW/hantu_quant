#!/bin/bash

# Redis 캐싱 시스템 자동 설치 스크립트
# 용도: systemd 관리 + 보안 설정 적용
# 실행: sudo ./scripts/setup-redis.sh

set -e  # 에러 시 즉시 중단

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

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
    echo "실행 방법: sudo ./scripts/setup-redis.sh"
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

# 설정 파일 경로
REDIS_CONF="/etc/redis/redis.conf"
ENV_FILE="$APP_DIR/.env"
BACKUP_DIR="/tmp/redis-backup-$(date +%Y%m%d-%H%M%S)"

echo ""
echo "=== Redis 캐싱 시스템 설치 시작 ==="
echo ""

# ============================================================
# Phase 1: 준비 작업
# ============================================================
echo "[Phase 1] 준비 작업"

# 1-1. redis-tools 설치 확인
if ! command -v redis-cli &> /dev/null; then
    log_info "redis-tools 설치 중..."
    apt-get update -qq
    apt-get install -y redis-tools
else
    log_info "redis-tools 이미 설치됨"
fi

# 1-2. Redis 서버 설치 확인
if ! command -v redis-server &> /dev/null; then
    log_info "redis-server 설치 중..."
    apt-get install -y redis-server
else
    log_info "redis-server 이미 설치됨"
fi

# 1-3. 백업 디렉토리 생성
mkdir -p "$BACKUP_DIR"
log_info "백업 디렉토리 생성: $BACKUP_DIR"

# 1-4. redis.conf 백업
if [ -f "$REDIS_CONF" ]; then
    cp "$REDIS_CONF" "$BACKUP_DIR/redis.conf.backup"
    chmod 600 "$BACKUP_DIR/redis.conf.backup"  # 보안: 소유자만 읽기
    log_info "redis.conf 백업 완료: $BACKUP_DIR/redis.conf.backup"
else
    log_error "redis.conf 파일을 찾을 수 없습니다: $REDIS_CONF"
    exit 1
fi

# 1-5. .env 백업
if [ -f "$ENV_FILE" ]; then
    cp "$ENV_FILE" "$BACKUP_DIR/.env.backup"
    chmod 600 "$BACKUP_DIR/.env.backup"  # 보안: 소유자만 읽기
    log_info ".env 백업 완료: $BACKUP_DIR/.env.backup"
else
    log_warn ".env 파일이 없습니다. 나중에 수동으로 생성하세요."
fi

# 1-6. 비밀번호 생성 (64자)
REDIS_PASSWORD=$(openssl rand -base64 48 | tr -d '\n')
log_info "비밀번호 생성 완료 (64자, .env에 저장됨)"

echo ""
# ============================================================
# Phase 2: Redis 설정 적용
# ============================================================
echo "[Phase 2] Redis 설정 적용"

# 2-1. redis.conf 수정
log_info "redis.conf 수정 중..."

# bind 설정 (localhost만 허용)
sed -i 's/^bind .*/bind 127.0.0.1/' "$REDIS_CONF"

# supervised 설정 (systemd)
if grep -q "^supervised" "$REDIS_CONF"; then
    sed -i 's/^supervised.*/supervised systemd/' "$REDIS_CONF"
else
    echo "supervised systemd" >> "$REDIS_CONF"
fi

# requirepass 추가 (이미 있으면 제거 후 추가)
sed -i '/^requirepass/d' "$REDIS_CONF"
echo "requirepass $REDIS_PASSWORD" >> "$REDIS_CONF"

# maxmemory 설정
sed -i '/^maxmemory /d' "$REDIS_CONF"
sed -i '/^maxmemory-policy/d' "$REDIS_CONF"
echo "maxmemory 256mb" >> "$REDIS_CONF"
echo "maxmemory-policy allkeys-lru" >> "$REDIS_CONF"

log_info "redis.conf 수정 완료"

# 2-2. systemd 서비스 파일 생성
SYSTEMD_FILE="/etc/systemd/system/redis-server.service"

if systemctl is-active --quiet redis-server; then
    log_info "기존 Redis 서비스 중지 중..."
    systemctl stop redis-server
fi

cat > "$SYSTEMD_FILE" <<EOF
[Unit]
Description=Redis In-Memory Data Store
After=network.target

[Service]
Type=notify
ExecStart=/usr/bin/redis-server /etc/redis/redis.conf
ExecStop=/bin/kill -s TERM \$MAINPID
Restart=always
RestartSec=5
User=redis
Group=redis

# 보안 설정
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=/var/lib/redis
ReadWritePaths=/var/log/redis

[Install]
WantedBy=multi-user.target
EOF

chmod 644 "$SYSTEMD_FILE"
log_info "systemd 서비스 파일 생성 완료"

# 2-3. systemd 재로드
systemctl daemon-reload
log_info "systemd 데몬 재로드 완료"

# 2-4. Redis 서비스 시작
systemctl start redis-server
sleep 2

if systemctl is-active --quiet redis-server; then
    log_info "Redis 서비스 시작 완료"
else
    log_error "Redis 서비스 시작 실패"
    journalctl -u redis-server -n 20 --no-pager
    exit 1
fi

# 2-5. 자동 시작 설정
systemctl enable redis-server
log_info "자동 시작 설정 완료"

echo ""
# ============================================================
# Phase 3: 애플리케이션 연동
# ============================================================
echo "[Phase 3] 애플리케이션 연동"

# 3-1. .env 파일 업데이트
if [ -f "$ENV_FILE" ]; then
    # 기존 REDIS_URL 제거
    sed -i '/^REDIS_URL=/d' "$ENV_FILE"

    # 새 REDIS_URL 추가
    echo "" >> "$ENV_FILE"
    echo "# Redis 캐싱 시스템 (자동 생성 - $(date))" >> "$ENV_FILE"
    echo "REDIS_URL=redis://:$REDIS_PASSWORD@localhost:6379/0" >> "$ENV_FILE"

    # 권한 설정 (보안)
    chmod 600 "$ENV_FILE"

    log_info ".env 파일 업데이트 완료"
else
    log_warn ".env 파일이 없습니다. 수동으로 다음 내용을 추가하세요:"
    echo "REDIS_URL=redis://:$REDIS_PASSWORD@localhost:6379/0"
fi

# 3-2. 애플리케이션 서비스 재시작 (서버 환경만)
if [ "$ENV_TYPE" == "server" ]; then
    if systemctl is-active --quiet hantu-api; then
        log_info "hantu-api 재시작 중..."
        systemctl restart hantu-api
        sleep 2
        log_info "hantu-api 재시작 완료"
    else
        log_warn "hantu-api 서비스가 실행 중이 아닙니다."
    fi

    if systemctl is-active --quiet hantu-scheduler; then
        log_info "hantu-scheduler 재시작 중..."
        systemctl restart hantu-scheduler
        sleep 2
        log_info "hantu-scheduler 재시작 완료"
    else
        log_warn "hantu-scheduler 서비스가 실행 중이 아닙니다."
    fi
else
    log_info "dev 환경이므로 서비스 재시작 생략"
fi

echo ""
# ============================================================
# 검증
# ============================================================
echo "[검증]"

# 검증 1: Redis 서비스 상태
if systemctl is-active --quiet redis-server; then
    log_info "Redis 서비스: Active (running)"
else
    log_error "Redis 서비스: Inactive"
    exit 1
fi

# 검증 2: Redis 연결 테스트
if REDISCLI_AUTH="$REDIS_PASSWORD" redis-cli PING 2>/dev/null | grep -q PONG; then
    log_info "Redis 연결: PONG (성공)"
else
    log_error "Redis 연결: 실패"
    exit 1
fi

# 검증 3: 바인딩 확인
if netstat -tlnp 2>/dev/null | grep -q "127.0.0.1:6379" || ss -tlnp 2>/dev/null | grep -q "127.0.0.1:6379"; then
    log_info "바인딩: 127.0.0.1:6379 (localhost만 허용)"
else
    log_warn "바인딩 확인 실패 (netstat/ss 명령어 없음)"
fi

# 검증 4: 메모리 설정 확인
MAXMEMORY=$(REDISCLI_AUTH="$REDIS_PASSWORD" redis-cli CONFIG GET maxmemory 2>/dev/null | tail -1)
if [ "$MAXMEMORY" == "268435456" ]; then  # 256MB = 268435456 bytes
    log_info "메모리 제한: 256MB (설정됨)"
else
    log_warn "메모리 제한: $MAXMEMORY bytes (확인 필요)"
fi

# 검증 5: 애플리케이션 로그 확인 (서버 환경만)
if [ "$ENV_TYPE" == "server" ]; then
    if journalctl -u hantu-api -n 20 --since "1 minute ago" 2>/dev/null | grep -qi "redis"; then
        log_info "애플리케이션 로그에서 Redis 연결 확인됨"
    else
        log_warn "애플리케이션 로그에서 Redis 연결 확인 안 됨 (수동 확인 필요)"
    fi
fi

echo ""
echo "=== 설치 완료 ==="
echo ""
echo "Redis 설정:"
echo "  - 주소: localhost:6379"
echo "  - 비밀번호: .env 파일에 저장됨 (REDIS_URL)"
echo "  - 메모리 제한: 256MB (LRU 정책)"
echo "  - 자동 시작: 활성화"
echo ""
echo "백업 위치: $BACKUP_DIR"
echo ""
echo "다음 단계:"
echo "  1. 모니터링: ./scripts/monitor-redis.sh"
echo "  2. 로그 확인: journalctl -u redis-server -f"
echo "  3. 롤백 (필요시): sudo ./scripts/rollback-redis.sh"
echo ""
