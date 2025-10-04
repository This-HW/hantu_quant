#!/bin/bash

# 한투 퀀트 스케줄러 자동 재시작 시스템 설정 스크립트

echo "🚀 한투 퀀트 스케줄러 자동 재시작 시스템 설정"
echo "=============================================="

# 현재 디렉토리 확인
CURRENT_DIR=$(pwd)
if [[ ! -f "check_scheduler.sh" ]]; then
    echo "❌ check_scheduler.sh 파일을 찾을 수 없습니다. 프로젝트 루트에서 실행해주세요."
    exit 1
fi

# logs 디렉토리 생성
mkdir -p logs
echo "✅ logs 디렉토리 생성 완료"

# check_scheduler.sh 실행 권한 부여
chmod +x check_scheduler.sh
chmod +x start_scheduler.sh
echo "✅ 스크립트 실행 권한 설정 완료"

# 현재 cron 설정 백업
crontab -l > logs/crontab_backup_$(date +%Y%m%d_%H%M%S).txt 2>/dev/null || echo "# 새 crontab" > logs/crontab_backup_$(date +%Y%m%d_%H%M%S).txt
echo "💾 기존 crontab 백업 완료"

# 새 cron 작업 추가
CRON_ENTRY="*/5 * * * * cd $CURRENT_DIR && ./check_scheduler.sh >/dev/null 2>&1"

# 기존 cron에서 한투 퀀트 관련 항목 제거
(crontab -l 2>/dev/null | grep -v "check_scheduler.sh") | crontab -

# 새 cron 작업 추가
(crontab -l 2>/dev/null; echo "$CRON_ENTRY") | crontab -

echo "⏰ Cron 작업 추가 완료:"
echo "   - 스케줄러 모니터링: 5분마다 실행"
echo "   - 자동 재시작: 최대 3회 시도"
echo "   - 로그 위치: logs/scheduler_monitor_*.log"

# 설정 확인
echo ""
echo "📋 현재 Cron 설정:"
crontab -l | grep -E "(check_scheduler|한투|hantu)" || echo "   (관련 항목 없음)"

echo ""
echo "🔧 수동 테스트:"
echo "   bash check_scheduler.sh"

echo ""
echo "📊 상태 확인:"
echo "   python3 workflows/integrated_scheduler.py status"

echo ""
echo "📱 텔레그램 설정 확인:"
echo "   cat config/telegram_config.json"

# 초기 테스트 실행
echo ""
echo "🧪 초기 테스트 실행 중..."
if bash check_scheduler.sh; then
    echo "✅ 자동 재시작 시스템 테스트 성공"
else
    echo "⚠️ 자동 재시작 시스템 테스트 실패 - 로그 확인 필요"
fi

echo ""
echo "🎉 자동 재시작 시스템 설정 완료!"
echo ""
echo "📋 주요 기능:"
echo "   ✅ 5분마다 스케줄러 상태 자동 확인"
echo "   ✅ Crash 감지 시 자동 재시작 (최대 3회)"
echo "   ✅ 텔레그램 자동 알림 (설정된 경우)"
echo "   ✅ 로그 파일 자동 관리"
echo "   ✅ 긴급 상황 시 수동 개입 알림"
echo ""
echo "⚠️ 참고사항:"
echo "   - 재시작 카운터는 logs/restart_count.txt에 저장"
echo "   - 정상 작동 시 카운터 자동 리셋"
echo "   - 최대 재시작 횟수 초과 시 수동 개입 필요"
echo ""
echo "🔍 로그 모니터링:"
echo "   tail -f logs/scheduler_monitor_$(date +%Y%m%d).log" 