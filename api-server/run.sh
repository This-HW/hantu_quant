#!/bin/bash

# 한투 퀀트 API 서버 실행 스크립트

echo "🚀 한투 퀀트 API 서버 시작"

# 가상환경 활성화 (선택사항)
if [ -d "../.venv" ]; then
    echo "가상환경 활성화 중..."
    source ../.venv/bin/activate
fi

# 의존성 설치
echo "의존성 설치 중..."
pip install -r requirements.txt

# 환경 변수 설정
export PYTHONPATH="../:$PYTHONPATH"

# FastAPI 서버 실행
echo "FastAPI 서버 실행 중..."
echo "- URL: http://localhost:8000"
echo "- API 문서: http://localhost:8000/docs"
echo "- WebSocket: ws://localhost:8000/ws"
echo ""

uvicorn main:app --host 0.0.0.0 --port 8000 --reload 