#!/bin/bash
# 최근 에러 요약 스크립트

echo "=== 최근 1시간 에러 요약 ==="
echo ""

# SSOT: db-tunnel.sh에서 호스트 정보 가져오기
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REMOTE_HOST=$(grep '^REMOTE_HOST=' "${SCRIPT_DIR}/db-tunnel.sh" 2>/dev/null | cut -d'"' -f2)

if [ -z "$REMOTE_HOST" ]; then
    echo "⚠️ SSOT 소스에서 REMOTE_HOST 추출 실패. 기본값 사용." >&2
    REMOTE_HOST="ubuntu@158.180.87.156"
fi

# 로컬 로그
if [ -f "logs/$(date +%Y%m%d).log" ]; then
  echo "❌ 로컬 에러 (최근 1시간):"
  tail -5000 "logs/$(date +%Y%m%d).log" | \
    grep -E "ERROR|Exception|FATAL" | \
    cut -d' ' -f1-3,5- | \
    sort | uniq -c | sort -rn | head -10
  echo ""
fi

# 서버 로그 (SSH) - REMOTE_HOST 변수 사용
echo "❌ 서버 에러 (최근 50줄):"
ssh "$REMOTE_HOST" "tail -5000 /opt/hantu_quant/logs/\$(date +%Y%m%d).log 2>/dev/null | grep -E 'ERROR|Exception|FATAL' | tail -10" 2>/dev/null || echo "  (서버 접근 불가)"

echo ""
echo "전체 로그: logs/$(date +%Y%m%d).log"
