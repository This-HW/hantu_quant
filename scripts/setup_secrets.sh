#!/bin/bash
# GitHub Secrets 설정 가이드 및 도우미 스크립트

echo "=========================================="
echo "  한투 퀀트 - Secrets 설정 가이드"
echo "=========================================="
echo ""

# 1. 배포 SSH 키 출력
echo "1. DEPLOY_SSH_KEY (배포용 SSH 개인키)"
echo "-------------------------------------------"
if [ -f ~/.ssh/hantu_deploy ]; then
    echo "키 파일 위치: ~/.ssh/hantu_deploy"
    echo ""
    echo "아래 내용을 GitHub Secret 'DEPLOY_SSH_KEY'에 복사하세요:"
    echo "-------------------------------------------"
    cat ~/.ssh/hantu_deploy
    echo ""
    echo "-------------------------------------------"
else
    echo "❌ 배포 키가 없습니다. 다음 명령어로 생성하세요:"
    echo "   ssh-keygen -t ed25519 -f ~/.ssh/hantu_deploy -C 'hantu-deploy'"
fi
echo ""

# 2. 기타 Secrets
echo "2. 기타 필요한 Secrets"
echo "-------------------------------------------"
echo "DEPLOY_HOST     = 134.185.104.141"
echo "DEPLOY_USER     = ubuntu"
echo "TELEGRAM_BOT_TOKEN = (BotFather에서 발급받은 토큰)"
echo "TELEGRAM_CHAT_ID   = (Telegram 채팅 ID)"
echo ""

# 3. Telegram 봇 설정 안내
echo "3. Telegram 봇 설정 방법"
echo "-------------------------------------------"
echo "1) @BotFather 에게 /newbot 명령어로 봇 생성"
echo "2) 생성된 봇 토큰 복사 (예: 123456:ABC-DEF...)"
echo "3) 생성된 봇에게 메시지 전송"
echo "4) https://api.telegram.org/bot<TOKEN>/getUpdates 접속"
echo "5) chat.id 값 확인"
echo ""

# 4. 로컬 Telegram 설정 파일 생성
echo "4. 로컬 Telegram 설정 생성"
echo "-------------------------------------------"
CONFIG_DIR="/home/user/hantu_quant/config"
if [ ! -f "$CONFIG_DIR/telegram_config.json" ]; then
    read -p "Telegram 설정을 지금 생성하시겠습니까? (y/n): " answer
    if [ "$answer" = "y" ]; then
        read -p "Bot Token: " BOT_TOKEN
        read -p "Chat ID: " CHAT_ID

        cat > "$CONFIG_DIR/telegram_config.json" << EOF
{
  "telegram": {
    "bot_token": "$BOT_TOKEN",
    "default_chat_ids": [
      "$CHAT_ID"
    ],
    "notification_settings": {
      "emergency": {"enabled": true, "sound": true},
      "high": {"enabled": true, "sound": true},
      "normal": {"enabled": true, "sound": false},
      "low": {"enabled": true, "sound": false}
    }
  }
}
EOF
        echo "✅ Telegram 설정이 생성되었습니다: $CONFIG_DIR/telegram_config.json"
    fi
else
    echo "✅ Telegram 설정 파일이 이미 존재합니다."
fi
echo ""

echo "=========================================="
echo "  GitHub에서 Settings > Secrets > Actions"
echo "  에서 위 값들을 설정하세요."
echo "=========================================="
