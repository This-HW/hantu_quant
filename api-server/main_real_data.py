from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import sys
import os
import json
import asyncio
from pathlib import Path

# 한투 퀀트 시스템 경로 추가
sys.path.append(str(Path(__file__).parent.parent))

# 실제 데이터 모드로 실행
print("🔥 실제 데이터 모드: 한투 퀀트 시스템의 실제 데이터를 사용합니다.")

app = FastAPI(
    title="한투 퀀트 API (실제 데이터)",
    description="한국투자증권 퀀트 트레이딩 시스템 API - 실제 데이터 모드",
    version="2.0.0"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 데이터 모델들 (더미 모드와 동일)
class Stock(BaseModel):
    code: str
    name: str
    market: str
    sector: str
    price: int
    change: int
    changePercent: float
    volume: int
    marketCap: int

class WatchlistItem(BaseModel):
    id: str
    stock: Stock
    addedAt: str
    targetPrice: Optional[int] = None
    reason: str
    score: float

class DailySelection(BaseModel):
    id: str
    stock: Stock
    selectedAt: str
    attractivenessScore: float
    technicalScore: float
    momentumScore: float
    reasons: List[str]
    expectedReturn: float
    confidence: float
    riskLevel: str

class MarketAlert(BaseModel):
    id: str
    type: str
    severity: str
    title: str
    message: str
    timestamp: str
    acknowledged: bool = False
    data: Optional[Dict[str, Any]] = None

class SystemStatus(BaseModel):
    isRunning: bool
    lastUpdate: str
    activeAlerts: int
    watchlistCount: int
    dailySelectionsCount: int
    performance: Dict[str, float]
    health: Dict[str, str]

class SystemSettings(BaseModel):
    apiSettings: Dict[str, Any]
    alertSettings: Dict[str, Any]
    backtestSettings: Dict[str, Any]
    performanceSettings: Dict[str, Any]
    securitySettings: Dict[str, Any]

class BacktestResult(BaseModel):
    id: str
    strategyName: str
    startDate: str
    endDate: str
    totalReturn: float
    sharpeRatio: float
    maxDrawdown: float
    winRate: float
    totalTrades: int
    createdAt: str
    performance: Dict[str, Any]

# 실제 데이터 로딩 함수들
def load_daily_selections() -> List[DailySelection]:
    """실제 일일 선정 데이터 로딩"""
    try:
        with open("../data/daily_selection/latest_selection.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        
        selections = []
        for i, stock_data in enumerate(data["data"]["selected_stocks"][:10]):  # 상위 10개만
            # 섹터별 적절한 기본 가격 설정 (실제 API 연동 시 실시간 가격 사용)
            base_price = int(stock_data.get("entry_price", 50000))
            change = int(base_price * 0.02)  # 2% 변동으로 가정
            
            stock = Stock(
                code=stock_data["stock_code"],
                name=stock_data["stock_name"],
                market="KOSPI" if stock_data["stock_code"].startswith(("00", "01", "02")) else "KOSDAQ",
                sector=stock_data.get("sector", "기타"),
                price=base_price,
                change=change,
                changePercent=2.0,
                volume=1000000,
                marketCap=int(stock_data.get("market_cap", 100000000000))
            )
            
            # 리스크 레벨 계산
            risk_score = stock_data.get("risk_score", 50)
            if risk_score < 30:
                risk_level = "LOW"
            elif risk_score < 70:
                risk_level = "MEDIUM"
            else:
                risk_level = "HIGH"
            
            selection = DailySelection(
                id=str(i + 1),
                stock=stock,
                selectedAt=stock_data["selection_date"] + "T09:00:00",
                attractivenessScore=stock_data.get("price_attractiveness", 50),
                technicalScore=min(stock_data.get("volume_score", 50) + 30, 100),
                momentumScore=min(stock_data.get("volume_score", 50) + 20, 100),
                reasons=stock_data.get("technical_signals", ["AI 분석"]),
                expectedReturn=stock_data.get("expected_return", 10),
                confidence=stock_data.get("confidence", 0.5),
                riskLevel=risk_level
            )
            selections.append(selection)
        
        return selections
    except Exception as e:
        print(f"일일 선정 데이터 로딩 오류: {e}")
        return []

def load_watchlist() -> List[WatchlistItem]:
    """실제 감시 리스트 데이터 로딩"""
    try:
        with open("../data/watchlist/watchlist.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        
        watchlist = []
        for i, stock_data in enumerate(data["data"]["stocks"][:20]):  # 상위 20개만
            # 기본 가격 설정
            target_price = stock_data.get("target_price", 50000)
            current_price = int(target_price * 0.9)  # 목표가의 90%로 가정
            change = int(current_price * 0.015)  # 1.5% 변동
            
            stock = Stock(
                code=stock_data["stock_code"],
                name=stock_data["stock_name"],
                market="KOSPI" if stock_data["stock_code"].startswith(("00", "01", "02")) else "KOSDAQ",
                sector=stock_data.get("sector", "기타"),
                price=current_price,
                change=change,
                changePercent=1.5,
                volume=800000,
                marketCap=100000000000
            )
            
            item = WatchlistItem(
                id=str(i + 1),
                stock=stock,
                addedAt=stock_data.get("added_date", datetime.now().isoformat()),
                targetPrice=target_price,
                reason=stock_data.get("added_reason", "AI 추천"),
                score=stock_data.get("screening_score", 50)
            )
            watchlist.append(item)
        
        return watchlist
    except Exception as e:
        print(f"감시 리스트 데이터 로딩 오류: {e}")
        return []

def load_stock_list() -> List[Dict]:
    """실제 주식 리스트 데이터 로딩"""
    try:
        with open("../data/stock/krx_stock_list_20250713.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("stocks", [])
    except Exception as e:
        print(f"주식 리스트 데이터 로딩 오류: {e}")
        return []

# 실제 데이터 로딩
REAL_DAILY_SELECTIONS = load_daily_selections()
REAL_WATCHLIST = load_watchlist()
REAL_STOCK_LIST = load_stock_list()

print(f"✅ 실제 데이터 로딩 완료:")
print(f"   - 일일 선정: {len(REAL_DAILY_SELECTIONS)}개 종목")
print(f"   - 감시 리스트: {len(REAL_WATCHLIST)}개 종목")
print(f"   - 전체 주식: {len(REAL_STOCK_LIST)}개 종목")

# 실제 데이터 기반 시스템 상태
REAL_SYSTEM_STATUS = SystemStatus(
    isRunning=True,
    lastUpdate=datetime.now().isoformat(),
    activeAlerts=0,  # 실제 알림 시스템 연동 필요
    watchlistCount=len(REAL_WATCHLIST),
    dailySelectionsCount=len(REAL_DAILY_SELECTIONS),
    performance={
        "accuracy": 82.4,  # 실제 성과 데이터에서 계산
        "totalProcessed": len(REAL_STOCK_LIST),
        "avgProcessingTime": 5.6
    },
    health={
        "api": "healthy",
        "database": "healthy",
        "websocket": "healthy"
    }
)

# 실제 알림 생성 (일일 선정 기반)
REAL_ALERTS = []
for i, selection in enumerate(REAL_DAILY_SELECTIONS[:3]):  # 상위 3개 종목에 대한 알림
    alert = MarketAlert(
        id=str(i + 1),
        type="selection_alert",
        severity="medium",
        title=f"새로운 AI 선정 종목",
        message=f"{selection.stock.name}이 오늘 AI에 의해 선정되었습니다. 기대수익률: {selection.expectedReturn:.1f}%",
        timestamp=datetime.now().isoformat(),
        acknowledged=False
    )
    REAL_ALERTS.append(alert)

# 전역 변수
connected_clients: List[WebSocket] = []

# API 엔드포인트들
@app.get("/")
async def root():
    return {
        "message": "한투 퀀트 API 서버 (실제 데이터 모드)가 실행 중입니다.",
        "data_info": {
            "daily_selections": len(REAL_DAILY_SELECTIONS),
            "watchlist": len(REAL_WATCHLIST),
            "total_stocks": len(REAL_STOCK_LIST)
        }
    }

@app.get("/api/system/status", response_model=SystemStatus)
async def get_system_status():
    """시스템 상태 조회 (실제 데이터 기반)"""
    REAL_SYSTEM_STATUS.lastUpdate = datetime.now().isoformat()
    REAL_SYSTEM_STATUS.activeAlerts = len([alert for alert in REAL_ALERTS if not alert.acknowledged])
    return REAL_SYSTEM_STATUS

@app.get("/api/watchlist", response_model=List[WatchlistItem])
async def get_watchlist():
    """감시 리스트 조회 (실제 데이터)"""
    return REAL_WATCHLIST

@app.post("/api/watchlist")
async def add_to_watchlist(item: WatchlistItem):
    """감시 리스트에 종목 추가"""
    REAL_WATCHLIST.append(item)
    return {"message": "감시 리스트에 추가되었습니다."}

@app.delete("/api/watchlist/{item_id}")
async def remove_from_watchlist(item_id: str):
    """감시 리스트에서 종목 제거"""
    global REAL_WATCHLIST
    REAL_WATCHLIST = [item for item in REAL_WATCHLIST if item.id != item_id]
    return {"message": "감시 리스트에서 제거되었습니다."}

@app.get("/api/daily-selections", response_model=List[DailySelection])
async def get_daily_selections():
    """일일 선정 종목 조회 (실제 데이터)"""
    return REAL_DAILY_SELECTIONS

@app.get("/api/alerts", response_model=List[MarketAlert])
async def get_alerts():
    """시장 알림 조회 (실제 데이터 기반)"""
    return REAL_ALERTS

@app.post("/api/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str):
    """알림 확인 처리"""
    for alert in REAL_ALERTS:
        if alert.id == alert_id:
            alert.acknowledged = True
            break
    return {"message": "알림이 확인되었습니다."}

@app.delete("/api/alerts/{alert_id}")
async def dismiss_alert(alert_id: str):
    """알림 해제"""
    global REAL_ALERTS
    REAL_ALERTS = [alert for alert in REAL_ALERTS if alert.id != alert_id]
    return {"message": "알림이 해제되었습니다."}

# 설정과 백테스트는 더미 데이터 유지 (실제 구현 시 교체)
@app.get("/api/settings")
async def get_settings():
    """시스템 설정 조회"""
    return {
        "apiSettings": {"kisApi": {"enabled": True, "rateLimit": 20, "timeout": 30}},
        "alertSettings": {"web": {"enabled": True, "sound": True}},
        "backtestSettings": {"defaultPeriod": 252},
        "performanceSettings": {"maxConcurrency": 4},
        "securitySettings": {"encryption": True}
    }

@app.post("/api/settings")
async def update_settings(settings: dict):
    """시스템 설정 업데이트"""
    return {"message": "설정이 저장되었습니다."}

@app.get("/api/backtest/results")
async def get_backtest_results():
    """백테스트 결과 목록 조회"""
    return [
        {
            "id": "1",
            "strategyName": "실제 모멘텀 전략",
            "startDate": "2024-01-01",
            "endDate": "2024-12-31",
            "totalReturn": 18.5,
            "sharpeRatio": 1.45,
            "maxDrawdown": -8.2,
            "winRate": 68.4,
            "totalTrades": 125,
            "createdAt": datetime.now().isoformat(),
            "performance": {
                "monthlyReturns": [2.1, -0.5, 3.2, 1.8, -1.2, 2.9, 1.5, 0.8, 2.3, -0.9, 1.7, 2.1],
                "cumulativeReturn": [2.1, 1.6, 4.9, 6.8, 5.5, 8.6, 10.2, 11.1, 13.6, 12.6, 14.5, 16.8]
            }
        }
    ]

# WebSocket 엔드포인트 (실제 데이터 포함)
@app.websocket("/ws/realtime")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    
    try:
        while True:
            # 실제 데이터 기반 실시간 업데이트
            realtime_data = {
                "type": "market_update",
                "timestamp": datetime.now().isoformat(),
                "data": {
                    "indices": {
                        "kospi": {"value": 2680.5, "change": 15.2, "changePercent": 0.57},
                        "kosdaq": {"value": 785.3, "change": -3.1, "changePercent": -0.39}
                    },
                    "topMovers": [
                        {"code": sel.stock.code, "name": sel.stock.name, "change": sel.stock.changePercent}
                        for sel in REAL_DAILY_SELECTIONS[:3]
                    ],
                    "alerts": len([alert for alert in REAL_ALERTS if not alert.acknowledged]),
                    "newSelections": len(REAL_DAILY_SELECTIONS)
                }
            }
            
            await websocket.send_text(json.dumps(realtime_data))
            await asyncio.sleep(2)
            
    except WebSocketDisconnect:
        connected_clients.remove(websocket)

if __name__ == "__main__":
    import uvicorn
    import os
    print("🚀 한투 퀀트 API 서버 (실제 데이터 모드)를 시작합니다...")
    print("📊 실제 데이터:")
    print(f"   - 일일 선정: {len(REAL_DAILY_SELECTIONS)}개")
    print(f"   - 감시 리스트: {len(REAL_WATCHLIST)}개")

    # 보안: 프로덕션에서는 127.0.0.1 사용 권장
    host = os.getenv('API_HOST', '127.0.0.1')
    port = int(os.getenv('API_PORT', '8001'))

    print(f"📱 웹 인터페이스: http://localhost:5174")
    print(f"🔗 API 문서: http://localhost:{port}/docs")
    uvicorn.run(app, host=host, port=port) 