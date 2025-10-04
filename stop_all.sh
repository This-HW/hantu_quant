#!/bin/bash

# 한투 퀀트 모든 서비스 중지 스크립트

echo "🛑 한투 퀀트 서비스 중지 중..."

# 웹 개발 서버 중지 (vite dev)
echo "🌐 웹 개발 서버 중지 중..."
pkill -f "vite.*dev" 2>/dev/null || true
pkill -f "node.*vite" 2>/dev/null || true

# 웹 프로덕션 서버 중지 (vite preview)
echo "🌐 웹 프로덕션 서버 중지 중..."
pkill -f "vite.*preview" 2>/dev/null || true

# 통합 스케줄러 중지
echo "📊 통합 스케줄러 중지 중..."
pkill -f "integrated_scheduler.py.*start" 2>/dev/null || true

# 스케줄러 정상 종료 시도 (텔레그램 알림 포함)
if command -v python3 &> /dev/null; then
    source .venv/bin/activate 2>/dev/null || true
    python3 workflows/integrated_scheduler.py stop 2>/dev/null || true
fi

# API 서버 중지
echo "🔧 API 서버 중지 중..."
pkill -f "uvicorn.*main:app" 2>/dev/null || true
pkill -f "fastapi" 2>/dev/null || true

# 포트 8000, 5173, 5174, 4173 사용 중인 프로세스 중지
echo "🔍 포트 정리 중..."
lsof -ti:8000 | xargs kill -9 2>/dev/null || true
lsof -ti:5173 | xargs kill -9 2>/dev/null || true
lsof -ti:5174 | xargs kill -9 2>/dev/null || true
lsof -ti:4173 | xargs kill -9 2>/dev/null || true

sleep 2

# 스케줄러 종료 확인
SCHEDULER_RUNNING=$(pgrep -f "integrated_scheduler.py.*start" | wc -l | tr -d ' ')

echo "✅ 모든 서비스 중지 완료!"
echo ""
echo "🔍 확인:"
echo "   📊 스케줄러: $SCHEDULER_RUNNING 개 프로세스"
echo "   🔧 포트 8000: $(lsof -ti:8000 | wc -l | tr -d ' ') 개 프로세스"
echo "   🌐 포트 5173: $(lsof -ti:5173 | wc -l | tr -d ' ') 개 프로세스"  
echo "   🌐 포트 5174: $(lsof -ti:5174 | wc -l | tr -d ' ') 개 프로세스"
echo "   🌐 포트 4173: $(lsof -ti:4173 | wc -l | tr -d ' ') 개 프로세스"
echo ""
echo "🚀 재시작: source start_production.sh" 