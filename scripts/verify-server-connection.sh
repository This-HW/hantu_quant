#!/bin/bash

# 서버 복구 후 연결 검증 스크립트
# 사용법: ./scripts/verify-server-connection.sh

set -euo pipefail

# 색상 정의
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# SSOT: db-tunnel.sh에서 연결 정보 추출
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DB_TUNNEL_SCRIPT="${SCRIPT_DIR}/db-tunnel.sh"

if [[ ! -f "$DB_TUNNEL_SCRIPT" ]]; then
    echo -e "${RED}❌ db-tunnel.sh를 찾을 수 없습니다: ${DB_TUNNEL_SCRIPT}${NC}"
    exit 1
fi

# db-tunnel.sh에서 변수 추출
REMOTE_HOST=$(grep '^REMOTE_HOST=' "$DB_TUNNEL_SCRIPT" | head -1 | cut -d'"' -f2)
LOCAL_PORT=$(grep '^LOCAL_PORT=' "$DB_TUNNEL_SCRIPT" | head -1 | cut -d'"' -f2)

SERVER_USER="${REMOTE_HOST%%@*}"
SERVER_IP="${REMOTE_HOST##*@}"

# 입력 검증
if ! [[ "$SERVER_IP" =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$ ]]; then
    echo -e "${RED}❌ 유효하지 않은 IP 주소: ${SERVER_IP}${NC}" >&2
    exit 1
fi
if ! [[ "$SERVER_USER" =~ ^[a-zA-Z0-9_-]+$ ]]; then
    echo -e "${RED}❌ 유효하지 않은 사용자명: ${SERVER_USER}${NC}" >&2
    exit 1
fi

echo ""
echo "=========================================="
echo "서버 연결 검증"
echo "=========================================="
echo "  Server: ${SERVER_USER}@${SERVER_IP}"
echo "  Local Port: ${LOCAL_PORT}"
echo ""

# Step 1: Ping 테스트
echo -e "${BLUE}[1/6] Ping 테스트...${NC}"
if ping -c 3 -W 5 "$SERVER_IP" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Ping 응답 정상${NC}"
else
    echo -e "${RED}❌ Ping 실패 - 서버가 응답하지 않습니다${NC}"
    echo ""
    echo "조치사항:"
    echo "1. docs/guides/server-recovery.md 참조"
    echo "2. OCI 콘솔에서 인스턴스 상태 확인"
    exit 1
fi

# Step 2: SSH 연결 테스트
echo -e "${BLUE}[2/6] SSH 연결 테스트...${NC}"
if ssh -o ConnectTimeout=10 -o BatchMode=yes "${SERVER_USER}@${SERVER_IP}" "echo 'SSH OK'" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ SSH 연결 성공${NC}"
else
    echo -e "${RED}❌ SSH 연결 실패${NC}"
    echo ""
    echo "조치사항:"
    echo "1. SSH 키 확인: ls -la ~/.ssh/id_rsa"
    echo "2. 권한 확인: chmod 600 ~/.ssh/id_rsa"
    echo "3. 서버 방화벽 확인 (포트 22)"
    exit 1
fi

# Step 3: 기존 SSH 터널 정리
echo -e "${BLUE}[3/6] 기존 SSH 터널 정리...${NC}"
pkill -f "ssh.*${LOCAL_PORT}.*${SERVER_IP}" 2>/dev/null || true
sleep 1
echo -e "${GREEN}✅ 정리 완료${NC}"

# Step 4: SSH 터널 시작
echo -e "${BLUE}[4/6] SSH 터널 시작...${NC}"
"$DB_TUNNEL_SCRIPT" start > /dev/null 2>&1
sleep 3

if "$DB_TUNNEL_SCRIPT" status 2>&1 | grep -q "Running"; then
    echo -e "${GREEN}✅ SSH 터널 시작 성공${NC}"
else
    echo -e "${RED}❌ SSH 터널 시작 실패${NC}"
    echo ""
    echo "조치사항:"
    echo "1. 로그 확인: tail -20 logs/db-tunnel.log"
    echo "2. 수동 시작: ./scripts/db-tunnel.sh start"
    exit 1
fi

# Step 5: 포트 확인
echo -e "${BLUE}[5/6] 포트 ${LOCAL_PORT} 확인...${NC}"
if nc -zv localhost "$LOCAL_PORT" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ 포트 ${LOCAL_PORT} 열림${NC}"
else
    echo -e "${RED}❌ 포트 ${LOCAL_PORT} 닫힘${NC}"
    echo ""
    echo "조치사항:"
    echo "1. SSH 터널 재시작: ./scripts/db-tunnel.sh restart"
    echo "2. 프로세스 확인: ps aux | grep ssh"
    exit 1
fi

# Step 6: DB 연결 테스트
echo -e "${BLUE}[6/6] PostgreSQL 연결 테스트...${NC}"

# 가상환경 활성화 시도
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d ".venv" ]; then
    source .venv/bin/activate
fi

if python3 scripts/diagnose-db.py 2>&1 | grep -q "Connection OK\|연결 성공"; then
    echo -e "${GREEN}✅ DB 연결 성공${NC}"
else
    echo -e "${YELLOW}⚠️  DB 연결 실패 (SSH 터널은 정상)${NC}"
    echo ""
    echo "조치사항:"
    echo "1. 서버 PostgreSQL 상태 확인"
    echo "2. ~/.pgpass 파일 확인"
    echo "3. 상세 진단: python3 scripts/diagnose-db.py"
    exit 1
fi

# 최종 성공
echo ""
echo -e "${GREEN}=========================================="
echo "✅ 모든 연결 테스트 통과!"
echo "==========================================${NC}"
echo ""
echo "서버 상태:"
echo "  - Ping: ✅ 정상"
echo "  - SSH: ✅ 정상"
echo "  - SSH Tunnel: ✅ 실행 중 (localhost:${LOCAL_PORT})"
echo "  - PostgreSQL: ✅ 연결 가능"
echo ""
