#!/bin/bash

# 한투 퀀트 통합 스케줄러 시작 스크립트

echo "🚀 한투 퀀트 통합 스케줄러 시작 중..."

# 가상환경 활성화 (필요시)
source .venv/bin/activate

# 환경 변수 정렬 (프로덕션과 동일하게 적용)
export SERVER=prod
export PYTHONPATH=".:$PYTHONPATH"

# 로그 디렉토리 보장
mkdir -p logs

# 기존 스케줄러 프로세스 확인 및 종료
if pgrep -f "integrated_scheduler.py.*start" > /dev/null; then
    echo "⚠️ 기존 스케줄러 프로세스를 종료합니다..."
    pkill -f "integrated_scheduler.py.*start"
    sleep 2
fi

# 스케줄러 시작
echo "🔄 스케줄러 시작 중..."
nohup python3 workflows/integrated_scheduler.py start > logs/scheduler_$(date +%Y%m%d).log 2>&1 &

SCHEDULER_PID=$!
echo "📝 스케줄러 PID: $SCHEDULER_PID"

# 잠시 대기 후 상태 확인
sleep 3

if ps -p $SCHEDULER_PID > /dev/null; then
    echo "✅ 스케줄러가 성공적으로 시작되었습니다!"
    echo "📊 상태 확인: python3 workflows/integrated_scheduler.py status"
    echo "📱 텔레그램 알림이 활성화되어 있습니다."
    echo ""
    echo "📅 스케줄:"
    echo "   ├─ 일간 스크리닝: 매일 06:00"
    echo "   ├─ 일일 업데이트: 스크리닝 완료 후 자동"
    echo "   └─ 마감 후 정리: 매일 16:00"
    echo ""
    echo "🔍 로그 모니터링: tail -f logs/scheduler_$(date +%Y%m%d).log"
else
    echo "❌ 스케줄러 시작 실패!"
    echo "📋 로그 확인: cat logs/scheduler_$(date +%Y%m%d).log"
    exit 1
fi 