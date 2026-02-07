#!/bin/bash
# Hantu Quant SSH Tunnel 자동 시작 스크립트
# ~/.zshrc 또는 ~/.bash_profile에서 호출하여 사용

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TUNNEL_SCRIPT="$SCRIPT_DIR/db-tunnel.sh"
LOG_FILE="$PROJECT_ROOT/logs/auto-tunnel.log"

# 로그 디렉토리 생성
mkdir -p "$PROJECT_ROOT/logs"

# 현재 디렉토리가 hantu_quant 프로젝트인지 확인
if [[ "$PWD" == *"hantu_quant"* ]]; then
    # SSH 터널이 이미 실행 중인지 확인
    if lsof -i :15432 >/dev/null 2>&1; then
        # 이미 실행 중
        exit 0
    fi

    # 터널 시작 (백그라운드, 출력 리다이렉트)
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Auto-starting SSH tunnel..." >> "$LOG_FILE"
    "$TUNNEL_SCRIPT" start >> "$LOG_FILE" 2>&1

    if [ $? -eq 0 ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] SSH tunnel started successfully" >> "$LOG_FILE"
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Failed to start SSH tunnel" >> "$LOG_FILE"
    fi
fi
