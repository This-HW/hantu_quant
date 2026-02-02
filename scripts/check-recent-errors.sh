#!/bin/bash
# 최근 에러 요약 스크립트

echo "=== 최근 1시간 에러 요약 ==="
echo ""

# 로컬 로그
if [ -f "logs/$(date +%Y%m%d).log" ]; then
  echo "❌ 로컬 에러 (최근 1시간):"
  tail -5000 "logs/$(date +%Y%m%d).log" | \
    grep -E "ERROR|Exception|FATAL" | \
    cut -d' ' -f1-3,5- | \
    sort | uniq -c | sort -rn | head -10
  echo ""
fi

# 서버 로그 (SSH)
echo "❌ 서버 에러 (최근 50줄):"
ssh ubuntu@158.180.87.156 "tail -5000 /opt/hantu_quant/logs/\$(date +%Y%m%d).log 2>/dev/null | grep -E 'ERROR|Exception|FATAL' | tail -10" 2>/dev/null || echo "  (서버 접근 불가)"

echo ""
echo "전체 로그: logs/$(date +%Y%m%d).log"
