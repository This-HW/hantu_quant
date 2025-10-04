#!/bin/bash

# 한투 퀀트 스케줄러 자동 재시작 모니터링 스크립트
# cron으로 5분마다 실행하여 스케줄러 상태 확인 및 자동 재시작

LOG_FILE="logs/scheduler_monitor_$(date +%Y%m%d).log"
SCHEDULER_LOG="logs/scheduler_$(date +%Y%m%d).log"
MAX_RESTART_COUNT=3
RESTART_COUNT_FILE="logs/restart_count.txt"

# 로그 함수
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOG_FILE"
}

# 재시작 카운터 읽기
get_restart_count() {
    if [[ -f "$RESTART_COUNT_FILE" ]]; then
        cat "$RESTART_COUNT_FILE"
    else
        echo 0
    fi
}

# 재시작 카운터 업데이트
update_restart_count() {
    echo "$1" > "$RESTART_COUNT_FILE"
}

# 재시작 카운터 리셋 (성공적 실행 시)
reset_restart_count() {
    echo 0 > "$RESTART_COUNT_FILE"
}

log_message "🔍 스케줄러 상태 확인 시작"

# 가상환경 활성화
if [[ -f ".venv/bin/activate" ]]; then
    source .venv/bin/activate
    log_message "✅ 가상환경 활성화 완료"
else
    log_message "⚠️ 가상환경을 찾을 수 없습니다"
fi

# 스케줄러 프로세스 확인
SCHEDULER_PID=$(pgrep -f "integrated_scheduler.py start")

if [[ -n "$SCHEDULER_PID" ]]; then
    log_message "✅ 스케줄러 실행 중 (PID: $SCHEDULER_PID)"
    
    # 프로세스가 응답하는지 확인 (kill -0으로 테스트)
    if kill -0 "$SCHEDULER_PID" 2>/dev/null; then
        log_message "💓 스케줄러 프로세스 정상 응답"
        reset_restart_count
        
        # 추가 상태 확인 (옵션)
        if python3 workflows/integrated_scheduler.py status > /dev/null 2>&1; then
            log_message "📊 스케줄러 상태 정상"
        else
            log_message "⚠️ 스케줄러 상태 확인 실패, 하지만 프로세스는 실행 중"
        fi
    else
        log_message "❌ 스케줄러 프로세스 응답 없음 (좀비 프로세스 가능성)"
        # 좀비 프로세스 종료
        pkill -f "integrated_scheduler.py start"
        SCHEDULER_PID=""
    fi
else
    log_message "❌ 스케줄러 프로세스 없음"
fi

# 스케줄러가 실행되지 않는 경우 재시작 시도
if [[ -z "$SCHEDULER_PID" ]]; then
    CURRENT_RESTART_COUNT=$(get_restart_count)
    
    if [[ $CURRENT_RESTART_COUNT -lt $MAX_RESTART_COUNT ]]; then
        NEW_COUNT=$((CURRENT_RESTART_COUNT + 1))
        update_restart_count $NEW_COUNT
        
        log_message "🔄 스케줄러 자동 재시작 시도 ($NEW_COUNT/$MAX_RESTART_COUNT)"
        
        # 기존 프로세스 완전 정리
        pkill -f "integrated_scheduler.py" 2>/dev/null
        sleep 2
        
        # 스케줄러 재시작
        nohup python3 workflows/integrated_scheduler.py start > "$SCHEDULER_LOG" 2>&1 &
        NEW_PID=$!
        
        # 재시작 확인
        sleep 5
        if kill -0 "$NEW_PID" 2>/dev/null; then
            log_message "✅ 스케줄러 재시작 성공 (PID: $NEW_PID)"
            
            # 텔레그램 알림 전송 (있는 경우)
            if command -v python3 >/dev/null 2>&1; then
                python3 -c "
try:
    from core.utils.telegram_notifier import get_telegram_notifier
    notifier = get_telegram_notifier()
    if notifier.is_enabled():
        message = f'🔄 **한투 퀀트 스케줄러 자동 재시작**\n\n⏰ 시간: $(date)\n🆔 PID: $NEW_PID\n🔢 재시작 횟수: $NEW_COUNT/$MAX_RESTART_COUNT\n\n✅ 시스템이 정상적으로 복구되었습니다.'
        notifier.send_message(message, 'high')
        print('텔레그램 알림 전송됨')
except Exception as e:
    print(f'텔레그램 알림 실패: {e}')
" 2>/dev/null || true
            fi
        else
            log_message "❌ 스케줄러 재시작 실패"
        fi
    else
        log_message "🚨 최대 재시작 횟수 초과 ($CURRENT_RESTART_COUNT/$MAX_RESTART_COUNT) - 수동 개입 필요"
        
        # 긴급 텔레그램 알림
        if command -v python3 >/dev/null 2>&1; then
            python3 -c "
try:
    from core.utils.telegram_notifier import get_telegram_notifier
    notifier = get_telegram_notifier()
    if notifier.is_enabled():
        message = f'🚨 **한투 퀀트 스케줄러 장애**\n\n⏰ 시간: $(date)\n❌ 상태: 최대 재시작 횟수 초과\n🔢 시도 횟수: $CURRENT_RESTART_COUNT/$MAX_RESTART_COUNT\n\n⚠️ **즉시 수동 개입이 필요합니다!**\n\n📋 확인 사항:\n• 시스템 리소스 상태\n• 로그 파일 확인\n• 네트워크 연결 상태\n• API 토큰 유효성'
        notifier.send_message(message, 'emergency')
        print('긴급 텔레그램 알림 전송됨')
except Exception as e:
    print(f'긴급 텔레그램 알림 실패: {e}')
" 2>/dev/null || true
        fi
    fi
fi

log_message "🏁 스케줄러 모니터링 완료"

# 로그 파일 크기 관리 (1MB 초과 시 압축)
if [[ -f "$LOG_FILE" ]] && [[ $(stat -f%z "$LOG_FILE" 2>/dev/null || stat -c%s "$LOG_FILE" 2>/dev/null) -gt 1048576 ]]; then
    gzip "$LOG_FILE"
    log_message "📦 로그 파일 압축 완료"
fi 