#!/bin/bash
# 배포 검증 스크립트

SERVER="ubuntu@158.180.87.156"

echo "=== 배포 검증 ==="
ssh -i ~/.ssh/id_rsa $SERVER << 'ENDSSH'
echo "1. Production Repo:"
cd /opt/hantu_quant
echo "   커밋: $(git log -1 --oneline)"

echo ""
echo "2. Dev Repo:"
cd /home/ubuntu/hantu_quant_dev
echo "   커밋: $(git log -1 --oneline)"

echo ""
echo "3. 두 레포 비교:"
PROD_SHA=$(cd /opt/hantu_quant && git rev-parse HEAD)
DEV_SHA=$(cd /home/ubuntu/hantu_quant_dev && git rev-parse HEAD)

if [ "$PROD_SHA" = "$DEV_SHA" ]; then
    echo "   ✅ 동기화됨!"
else
    echo "   ❌ 불일치"
    echo "   Production: ${PROD_SHA:0:7}"
    echo "   Dev: ${DEV_SHA:0:7}"
fi
ENDSSH
