#!/bin/bash
# =============================================================================
# Post-Commit Hook: 서버 환경 자동 배포 스크립트
#
# 목적: 서버에서 직접 hotfix 커밋 시 자동으로 서비스 재시작 + 텔레그램 알림
# 트리거: git commit 완료 후 (.git/hooks/post-commit)
#
# 동작:
#   1. 서버 환경 확인 (/opt/hantu_quant 경로)
#   2. 로컬 환경이면 아무 작업 안함
#   3. 서버 환경이면:
#      - 서비스 재시작 (hantu-api, hantu-scheduler)
#      - 텔레그램 알림 발송 (커밋 정보 + 재시작 결과)
#
# 환경변수 (필수):
#   - TELEGRAM_BOT_TOKEN: 텔레그램 봇 토큰
#   - TELEGRAM_CHAT_ID: 텔레그램 채팅 ID
# =============================================================================

set -euo pipefail

# ===== 설정 =====
PROJECT_DIR="$(git rev-parse --show-toplevel)"
SERVER_PATH="/opt/hantu_quant"

# ===== 1. 서버 환경 확인 =====
if [ "$PROJECT_DIR" != "$SERVER_PATH" ]; then
    # 로컬 환경에서는 아무 작업도 하지 않음
    exit 0
fi

echo "🚀 서버 환경 감지 - 자동 배포 시작"

# ===== 2. 커밋 정보 수집 =====
COMMIT_HASH=$(git rev-parse HEAD | cut -c1-8)
COMMIT_MSG=$(git log -1 --pretty=%B | head -n 1)
BRANCH=$(git rev-parse --abbrev-ref HEAD)
AUTHOR=$(git log -1 --pretty=%an)
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

echo "📋 커밋 정보:"
echo "  - Hash: $COMMIT_HASH"
echo "  - Branch: $BRANCH"
echo "  - Message: $COMMIT_MSG"
echo "  - Author: $AUTHOR"

# ===== 3. 서비스 재시작 =====
echo "🔄 서비스 재시작 중..."

RESTART_RESULT=""
RESTART_SUCCESS=true

# API 서버 재시작
if sudo systemctl restart hantu-api 2>&1; then
    echo "  ✅ hantu-api 재시작 성공"
    RESTART_RESULT+="• hantu-api: ✅ 재시작 성공\n"
else
    echo "  ❌ hantu-api 재시작 실패"
    RESTART_RESULT+="• hantu-api: ❌ 재시작 실패\n"
    RESTART_SUCCESS=false
fi

# 스케줄러 재시작
if sudo systemctl restart hantu-scheduler 2>&1; then
    echo "  ✅ hantu-scheduler 재시작 성공"
    RESTART_RESULT+="• hantu-scheduler: ✅ 재시작 성공\n"
else
    echo "  ❌ hantu-scheduler 재시작 실패"
    RESTART_RESULT+="• hantu-scheduler: ❌ 재시작 실패\n"
    RESTART_SUCCESS=false
fi

# ===== 4. 텔레그램 알림 발송 =====
echo "📱 텔레그램 알림 발송 중..."

# 환경변수 로드 (.env 파일에서)
if [ -f "$PROJECT_DIR/.env" ]; then
    export $(grep -E '^TELEGRAM_BOT_TOKEN=' "$PROJECT_DIR/.env" | xargs)
    export $(grep -E '^TELEGRAM_CHAT_ID=' "$PROJECT_DIR/.env" | xargs)
fi

# 환경변수 확인
if [ -z "${TELEGRAM_BOT_TOKEN:-}" ] || [ -z "${TELEGRAM_CHAT_ID:-}" ]; then
    echo "⚠️  텔레그램 환경변수 없음 - 알림 건너뜀"
    exit 0
fi

# 가상환경 활성화
if [ -f "$PROJECT_DIR/venv/bin/activate" ]; then
    source "$PROJECT_DIR/venv/bin/activate"
else
    echo "⚠️  가상환경 없음 - 시스템 Python 사용"
fi

# Python 스크립트로 텔레그램 알림 전송
python3 << EOF
import os
import sys
import requests
from datetime import datetime

# 환경변수 로드
bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
chat_id = os.getenv("TELEGRAM_CHAT_ID")

if not bot_token or not chat_id:
    print("⚠️  텔레그램 환경변수 없음")
    sys.exit(0)

# 재시작 결과에 따른 이모지 및 우선순위
restart_success = ${RESTART_SUCCESS}
if restart_success:
    status_emoji = "✅"
    status_text = "배포 성공"
    priority = "normal"
else:
    status_emoji = "⚠️"
    status_text = "배포 경고"
    priority = "high"

# 메시지 작성
message = f"""{status_emoji} *서버 Hotfix 배포 완료*

📅 시간: \`${TIMESTAMP}\`
🔀 브랜치: \`${BRANCH}\`
📝 커밋: \`${COMMIT_HASH}\`
👤 작성자: \`${AUTHOR}\`

💬 *커밋 메시지*:
\`\`\`
${COMMIT_MSG}
\`\`\`

🔄 *서비스 재시작 결과*:
${RESTART_RESULT}
📊 *최종 상태*: \`${status_text}\`

💡 *서비스 상태 확인*:
\`\`\`bash
sudo systemctl status hantu-api
sudo systemctl status hantu-scheduler
journalctl -u hantu-api -f
\`\`\`"""

# 텔레그램 전송
try:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown",
        "disable_notification": priority == "normal"
    }

    response = requests.post(url, json=payload, timeout=10)

    if response.status_code == 200:
        print("✅ 텔레그램 알림 전송 완료")
    else:
        print(f"❌ 텔레그램 알림 전송 실패: {response.status_code}")
        print(f"   응답: {response.text[:200]}")
except Exception as e:
    print(f"❌ 텔레그램 알림 오류: {e}")
EOF

echo "🎉 자동 배포 완료"
exit 0
