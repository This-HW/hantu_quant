#!/bin/bash
# 서버 코드 버전 확인 스크립트

SERVER="ubuntu@158.180.87.156"
PROJECT_PATH="/opt/hantu_quant"

echo "=== 서버 Git 상태 확인 ==="
ssh -i ~/.ssh/id_rsa $SERVER << 'ENDSSH'
cd /opt/hantu_quant

echo "현재 브랜치:"
git branch --show-current

echo ""
echo "현재 커밋:"
git log -1 --oneline

echo ""
echo "로컬과 origin 비교:"
git fetch origin main
git log HEAD..origin/main --oneline || echo "✅ 최신 상태"

echo ""
echo "작업 디렉토리 상태:"
git status --short

echo ""
echo "스케줄러 상태:"
systemctl status hantu-scheduler --no-pager | head -10

echo ""
echo "마지막 배포 시간:"
stat -c '%y' venv/bin/activate 2>/dev/null || stat -f '%Sm' venv/bin/activate 2>/dev/null || echo "정보 없음"
ENDSSH
