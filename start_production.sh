#!/bin/bash

# 한투 퀀트 프로덕션 환경 전체 시스템 시작 스크립트

echo "🚀 한투 퀀트 프로덕션 환경 시작"
echo "================================="

# 가상환경 활성화
if [ -d ".venv" ]; then
    echo "✅ 가상환경 활성화 중..."
    source .venv/bin/activate
else
    echo "❌ 가상환경을 찾을 수 없습니다"
    exit 1
fi

# 환경 변수 설정 (프로덕션)
export SERVER=prod
export PYTHONPATH=".:$PYTHONPATH"

echo "📊 환경 설정:"
echo "   - SERVER: $SERVER (실제투자)"
echo "   - PYTHONPATH: $PYTHONPATH"

# 1. 기존 프로세스 정리 (중복 실행 방지)
echo ""
echo "🧹 기존 프로세스 정리 중..."
pkill -f "uvicorn.*main:app" 2>/dev/null || true
pkill -f "vite.*preview" 2>/dev/null || true
pkill -f "integrated_scheduler.py.*start" 2>/dev/null || true
sleep 2

# 2. API 서버 시작 (백그라운드)
echo ""
echo "🔧 API 서버 시작 중..."
cd api-server
nohup uvicorn main:app --host 0.0.0.0 --port 8000 --reload > ../logs/api_server.log 2>&1 &
API_PID=$!
cd ..

# API 서버 시작 확인
sleep 3
if kill -0 $API_PID 2>/dev/null; then
    echo "✅ API 서버 시작됨 (PID: $API_PID)"
    echo "   - URL: http://localhost:8000"
    echo "   - API 문서: http://localhost:8000/docs"
else
    echo "❌ API 서버 시작 실패"
    echo "📋 로그 확인: cat logs/api_server.log"
    exit 1
fi

# 3. 웹 인터페이스 프로덕션 빌드 및 실행
echo ""
echo "🌐 웹 인터페이스 프로덕션 모드 시작 중..."
cd web-interface

# 프로덕션 빌드
echo "🔨 프로덕션 빌드 중..."
npm run build

# 프로덕션 서버 시작 (preview 모드)
echo "🚀 프로덕션 웹 서버 시작 중..."
nohup npm run preview > ../logs/web_server.log 2>&1 &
WEB_PID=$!
cd ..

# 웹 서버 시작 확인
sleep 3
if kill -0 $WEB_PID 2>/dev/null; then
    echo "✅ 웹 서버 시작됨 (PID: $WEB_PID)"
    echo "   - URL: http://localhost:4173"
else
    echo "❌ 웹 서버 시작 실패"
    echo "📋 로그 확인: cat logs/web_server.log"
fi

# 4. 통합 스케줄러 시작 (단일 인스턴스 보장)
echo ""
echo "📊 통합 스케줄러 시작 중..."

# 스케줄러 백그라운드 시작
echo "🚀 스케줄러 백그라운드 실행 중..."
nohup python3 workflows/integrated_scheduler.py start > logs/scheduler.log 2>&1 &
SCHEDULER_PID=$!

# 스케줄러 시작 확인 (5초 대기)
sleep 5
SCHEDULER_STATUS=$(python3 workflows/integrated_scheduler.py status 2>/dev/null | grep -c "실행 중" || echo "0")

if [ "$SCHEDULER_STATUS" -gt 0 ]; then
    echo "✅ 스케줄러 시작됨 (PID: $SCHEDULER_PID)"
    echo "   - 일간 스크리닝: 매일 06:00"
    echo "   - 일일 업데이트: Phase 1 완료 후 자동"
    echo "   - 시장 마감 정리: 매일 16:00"
else
    echo "❌ 스케줄러 시작 실패"
    echo "📋 로그 확인: cat logs/scheduler.log"
    echo "   수동 시작: python3 workflows/integrated_scheduler.py start"
fi

echo ""
echo "🎉 프로덕션 환경 시작 완료!"
echo ""
echo "📋 접속 정보:"
echo "   🌐 웹 인터페이스: http://localhost:4173"
echo "   🔧 API 서버: http://localhost:8000"
echo "   📖 API 문서: http://localhost:8000/docs"
echo ""
echo "📊 프로세스 상태:"
echo "   API 서버 PID: $API_PID"
echo "   웹 서버 PID: $WEB_PID"
echo "   스케줄러 PID: $SCHEDULER_PID"
echo ""
echo "🔍 로그 모니터링:"
echo "   tail -f logs/api_server.log"
echo "   tail -f logs/web_server.log"
echo "   tail -f logs/scheduler.log"
echo ""
echo "🛑 중지 명령:"
echo "   kill $API_PID $WEB_PID $SCHEDULER_PID"
echo "   또는: ./stop_all.sh"
echo ""
echo "⚡ 이제 실제 투자 데이터를 사용하는 프로덕션 환경입니다!" 