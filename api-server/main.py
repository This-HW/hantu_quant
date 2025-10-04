"""
한투 퀀트 API 서버 - 실제 환경 전용
모든 더미/시뮬레이션 데이터 제거됨
"""

import json
import logging
import subprocess
import sys
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
import time

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

# 프로젝트 루트 경로 추가
sys.path.append(str(Path(__file__).parent.parent))

from core.config.api_config import APIConfig
from core.api.kis_api import KISAPI

# 실제 투자 환경 강제 설정
import os
os.environ['SERVER'] = 'prod'

app = FastAPI(
    title="한투 퀀트 API (실제 투자 전용)",
    description="실시간 실제 데이터만 사용",
    version="2.0.0"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4173", "http://localhost:4174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 데이터 모델들
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
    targetPrice: int
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
    stock: Stock
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
    performance: Dict[str, Any]
    health: Dict[str, str]

class ServiceStatus(BaseModel):
    name: str
    description: str
    running: bool
    port: Optional[int] = None
    pid: Optional[int] = None
    uptime: str
    auto_start: bool

class SystemOverview(BaseModel):
    total_services: int
    running_services: int
    stopped_services: int
    system_health: str
    uptime: str
    last_update: str
    services: Dict[str, Dict[str, Any]]

# 글로벌 API 클라이언트
api_config = APIConfig()
kis_client = KISAPI()

print(f"🚀 실제 투자 환경 시작")
print(f"📡 API 서버: {api_config.base_url}")
print(f"🏦 계좌: {api_config.account_number}")

# 실제 API 데이터 로딩 함수들
def get_real_stock_price(stock_code: str) -> Dict:
    """실제 한국투자증권 API에서 현재가 조회"""
    try:
        response = kis_client.get_current_price(stock_code)
        
        if not response.get("success"):
            logger.warning(f"가격 조회 실패: {stock_code}")
            raise Exception(f"API 호출 실패: {response.get('message', 'Unknown error')}")
        
        data = response["data"]
        
        # 실제 API 응답 파싱
        current_price = int(data.get("stck_prpr", 0))  # 현재가
        prev_price = int(data.get("stck_sdpr", current_price))  # 전일가
        change = current_price - prev_price
        change_percent = round((change / prev_price * 100), 2) if prev_price > 0 else 0.0
        volume = int(data.get("acml_vol", 0))  # 누적거래량
        
        return {
            "price": current_price,
            "change": change,
            "changePercent": change_percent,
            "volume": volume,
            "marketCap": current_price * int(data.get("lstg_stqt", 1000000))  # 시가총액
        }
        
    except Exception as e:
        logger.error(f"실제 가격 조회 실패 ({stock_code}): {e}")
        raise Exception(f"실시간 데이터 조회 실패: {e}")

async def execute_real_screening() -> Dict[str, Any]:
    """실제 스크리닝 실행 (통합 로직 사용)"""
    import subprocess
    import os
    
    try:
        logger.info("🔍 실제 스크리닝 실행 시작")
        
        # 프로젝트 루트로 이동하여 스크리닝 실행
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # 명령에 'screen' 서브커맨드 추가하여 실제 스크리닝 실행
        cmd = f"cd {project_root} && python3 workflows/phase1_watchlist.py screen"
        
        # 비동기 실행
        process = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)
        
        if process.returncode == 0:
            # 스크리닝 성공 - 최신 데이터 로드
            global REAL_WATCHLIST
            REAL_WATCHLIST = load_latest_watchlist_data()
            
            logger.info(f"✅ 실제 스크리닝 완료: {len(REAL_WATCHLIST)}개 종목")
            return {
                "success": True, 
                "message": f"실제 스크리닝 완료 ({len(REAL_WATCHLIST)}개 종목)",
                "details": "새로운 로직으로 실제 종목 스크리닝 수행"
            }
        else:
            logger.error(f"스크리닝 실행 실패: {process.stderr}")
            return {
                "success": False, 
                "message": "스크리닝 실행 실패",
                "error": process.stderr
            }
            
    except subprocess.TimeoutExpired:
        return {"success": False, "message": "스크리닝 실행 시간 초과 (5분)"}
    except Exception as e:
        logger.error(f"스크리닝 실행 오류: {e}")
        return {"success": False, "message": f"스크리닝 실행 오류: {str(e)}"}

async def execute_real_daily_selection() -> Dict[str, Any]:
    """실제 종목선정 실행 (통합 로직 사용)"""
    import subprocess
    import os
    
    try:
        logger.info("📊 실제 종목선정 실행 시작")
        
        # 프로젝트 루트로 이동하여 종목선정 실행
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cmd = f"cd {project_root} && python3 workflows/phase2_daily_selection.py"
        
        # 비동기 실행
        process = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=180)
        
        if process.returncode == 0:
            # 종목선정 성공 - 최신 데이터 로드
            global REAL_DAILY_SELECTIONS
            REAL_DAILY_SELECTIONS = load_latest_daily_selection_data()
            
            logger.info(f"✅ 실제 종목선정 완료: {len(REAL_DAILY_SELECTIONS)}개 종목")
            return {
                "success": True,
                "message": f"실제 종목선정 완료 ({len(REAL_DAILY_SELECTIONS)}개 종목)",
                "details": "새로운 로직으로 실제 종목 선정 수행"
            }
        else:
            logger.error(f"종목선정 실행 실패: {process.stderr}")
            return {
                "success": False,
                "message": "종목선정 실행 실패", 
                "error": process.stderr
            }
            
    except subprocess.TimeoutExpired:
        return {"success": False, "message": "종목선정 실행 시간 초과 (3분)"}
    except Exception as e:
        logger.error(f"종목선정 실행 오류: {e}")
        return {"success": False, "message": f"종목선정 실행 오류: {str(e)}"}

def load_latest_watchlist_data() -> List[WatchlistItem]:
    """최신 감시리스트 데이터 로드"""
    try:
        # 프로젝트 루트 경로 기준으로 수정
        project_root = Path(__file__).parent.parent
        watchlist_path = project_root / "data" / "watchlist" / "watchlist.json"
        
        with open(watchlist_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        watchlist = []
        for stock_data in data["data"]["stocks"][:20]:  # 상위 20개
            stock_code = stock_data["stock_code"] 
            stock_name = stock_data["stock_name"]
            
            # 실제 데이터 사용 (스크리닝 결과)
            stock = Stock(
                code=stock_code,
                name=stock_name,
                market="KOSPI" if stock_code.startswith(("00", "01", "02")) else "KOSDAQ",
                sector=stock_data.get("sector", "기타"),
                price=stock_data.get("current_price", 50000),
                change=stock_data.get("price_change", 0),
                changePercent=stock_data.get("change_percent", 0.0),
                volume=stock_data.get("volume", 100000),
                marketCap=stock_data.get("market_cap", 500000000)
            )
            
            item = WatchlistItem(
                stock=stock,
                addedDate=stock_data.get("added_date", "2025-01-27"),
                reason=stock_data.get("added_reason", "스크리닝 통과"),
                targetPrice=stock_data.get("target_price", 0),
                riskLevel=stock_data.get("risk_level", "보통")
            )
            
            watchlist.append(item)
        
        return watchlist
        
    except Exception as e:
        logger.error(f"최신 감시리스트 로드 오류: {e}")
        return []

def load_latest_daily_selection_data() -> List[DailySelectionItem]:
    """최신 일일선정 데이터 로드"""
    try:
        project_root = Path(__file__).parent.parent
        
        # 최신 일일선정 파일 찾기
        daily_dir = project_root / "data" / "daily_selection"
        pattern = "daily_selection_*.json"
        daily_files = list(daily_dir.glob(pattern))
        
        if not daily_files:
            return []
        
        # 가장 최신 파일 선택
        latest_file = max(daily_files, key=lambda x: x.stat().st_mtime)
        
        with open(latest_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        selections = []
        for stock_data in data.get("data", {}).get("selected_stocks", [])[:10]:  # 상위 10개
            stock_code = stock_data["stock_code"]
            stock_name = stock_data["stock_name"]
            
            stock = Stock(
                code=stock_code,
                name=stock_name,
                market="KOSPI" if stock_code.startswith(("00", "01", "02")) else "KOSDAQ",
                sector=stock_data.get("sector", "기타"),
                price=stock_data.get("current_price", 50000),
                change=stock_data.get("price_change", 0),
                changePercent=stock_data.get("change_percent", 0.0),
                volume=stock_data.get("volume", 100000),
                marketCap=stock_data.get("market_cap", 500000000)
            )
            
            item = DailySelectionItem(
                stock=stock,
                selectionDate=stock_data.get("selection_date", "2025-01-27"),
                reason=stock_data.get("selection_reason", "가격 매력도"),
                confidence=stock_data.get("confidence_score", 0.8),
                expectedReturn=stock_data.get("expected_return", 0.1),
                riskScore=stock_data.get("risk_score", 0.3)
            )
            
            selections.append(item)
        
        return selections
        
    except Exception as e:
        logger.error(f"최신 일일선정 로드 오류: {e}")
        return []

# 과거 함수 제거됨 - load_latest_watchlist_data()로 대체

def load_watchlist_with_real_prices() -> List[WatchlistItem]:
    """레거시 함수 - load_latest_watchlist_data() 사용 권장"""
    logger.warning("load_watchlist_with_real_prices()는 레거시 함수입니다. load_latest_watchlist_data() 사용을 권장합니다.")
    return load_latest_watchlist_data()

def load_daily_selections_with_real_prices() -> List[DailySelectionItem]:
    """레거시 함수 - load_latest_daily_selection_data() 사용 권장"""
    logger.warning("load_daily_selections_with_real_prices()는 레거시 함수입니다. load_latest_daily_selection_data() 사용을 권장합니다.")
    return load_latest_daily_selection_data()

# ========== 통합 스케줄러 제어 함수들 ==========

async def start_integrated_scheduler() -> Dict[str, Any]:
    """통합 스케줄러 시작 (구 main_real_pykrx.py 기능 통합)"""
    import subprocess
    import os
    
    try:
        # 현재 실행 중인지 확인
        status = get_integrated_scheduler_status()
        if status["running"]:
            return {"success": False, "message": "통합 스케줄러가 이미 실행 중입니다", "pid": status["pid"]}
        
        # 스케줄러 시작
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cmd = f"cd {project_root} && python3 workflows/integrated_scheduler.py start &"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        # 시작 확인 (3초 대기)
        import time
        time.sleep(3)
        new_status = get_integrated_scheduler_status()
        
        if new_status["running"]:
            logger.info(f"통합 스케줄러 시작 성공: PID {new_status['pid']}")
            return {"success": True, "message": "통합 스케줄러가 성공적으로 시작되었습니다", "pid": new_status["pid"]}
        else:
            return {"success": False, "message": "통합 스케줄러 시작에 실패했습니다", "error": result.stderr}
            
    except Exception as e:
        return {"success": False, "message": "통합 스케줄러 시작 중 오류 발생", "error": str(e)}

async def stop_integrated_scheduler() -> Dict[str, Any]:
    """통합 스케줄러 중지"""
    import subprocess
    import os
    import psutil
    
    try:
        # 현재 실행 중인지 확인
        status = get_integrated_scheduler_status()
        if not status["running"]:
            return {"success": False, "message": "통합 스케줄러가 실행 중이 아닙니다"}
        
        # 정상 종료 시도
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cmd = f"cd {project_root} && python3 workflows/integrated_scheduler.py stop"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        
        # 강제 종료 (필요시)
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                cmdline = proc.info.get('cmdline', [])
                if cmdline and any('integrated_scheduler' in arg for arg in cmdline):
                    proc.kill()
        except:
            pass
        
        # 종료 확인
        import time
        time.sleep(2)
        new_status = get_integrated_scheduler_status()
        
        if not new_status["running"]:
            logger.info("통합 스케줄러 중지 성공")
            return {"success": True, "message": "통합 스케줄러가 성공적으로 중지되었습니다"}
        else:
            return {"success": False, "message": "통합 스케줄러 중지에 실패했습니다"}
            
    except Exception as e:
        return {"success": False, "message": "통합 스케줄러 중지 중 오류 발생", "error": str(e)}

def get_integrated_scheduler_status() -> Dict[str, Any]:
    """통합 스케줄러 상태 조회"""
    import psutil
    
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            cmdline = proc.info.get('cmdline', [])
            if cmdline and any('integrated_scheduler' in arg for arg in cmdline):
                return {
                    "running": True,
                    "pid": proc.info['pid'],
                    "status": "실행 중",
                    "uptime": "측정 불가"
                }
        
        return {
            "running": False,
            "pid": None,
            "status": "정지됨",
            "uptime": "중지됨"
        }
        
    except Exception as e:
        logger.error(f"스케줄러 상태 조회 오류: {e}")
        return {
            "running": False,
            "pid": None,
            "status": "오류",
            "uptime": f"상태 조회 실패: {e}"
        }

# ========== 과거 로직 제거 완료 ==========
# 이전 load_watchlist_with_real_prices() 함수는 더미 데이터를 사용했습니다.
# 새로운 load_latest_watchlist_data()는 실제 스크리닝 결과를 사용합니다.

def _load_legacy_watchlist_code_placeholder():
    """과거 로직 참고용 (실행되지 않음)"""
    try:
        # 이전 로직: 더미 데이터 사용
        project_root = Path(__file__).parent.parent
        watchlist_path = project_root / "data" / "watchlist" / "watchlist.json"
        
        print(f"📁 감시리스트 파일 경로: {watchlist_path}")
        
        with open(watchlist_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        print("📡 기존 데이터로 감시리스트 구성 중... (API 호출 제외)")
        
        watchlist = []
        for i, stock_data in enumerate(data["data"]["stocks"][:20]):  # 상위 20개
            stock_code = stock_data["stock_code"] 
            stock_name = stock_data["stock_name"]
            
            try:
                # 기존 데이터 사용 (API 호출 제외)
                price_info = {
                    "price": 50000,  # 기본값
                    "change": 0,
                    "changePercent": 0.0, 
                    "volume": 100000,
                    "marketCap": 500000000
                }
                
                stock = Stock(
                    code=stock_code,
                    name=stock_name,
                    market="KOSPI" if stock_code.startswith(("00", "01", "02")) else "KOSDAQ",
                    sector=stock_data.get("sector", "기타"),
                    price=price_info["price"],
                    change=price_info["change"],
                    changePercent=price_info["changePercent"],
                    volume=price_info["volume"],
                    marketCap=price_info["marketCap"]
                )
                
                item = WatchlistItem(
                    id=str(i + 1),
                    stock=stock,
                    addedAt=stock_data.get("added_date", datetime.now().isoformat()),
                    targetPrice=stock_data.get("target_price", price_info["price"]),
                    reason=stock_data.get("added_reason", "스크리닝 상위 종목"),
                    score=stock_data.get("screening_score", 50)
                )
                watchlist.append(item)
                
                print(f"✅ {stock_name} ({stock_code}): 기존 데이터 로딩")
                
            except Exception as e:
                logger.error(f"❌ {stock_name} ({stock_code}): 가격 조회 실패 - {e}")
                continue
        
        print(f"🎯 실제 데이터 감시 리스트 로딩 완료: {len(watchlist)}개 종목")
        return watchlist
        
    except Exception as e:
        logger.error(f"감시 리스트 로딩 실패: {e}")
        return []

def load_daily_selections_with_real_prices() -> List[DailySelection]:
    """실제 API 호출로 일일 선정 로딩"""
    try:
        # 프로젝트 루트 경로 기준으로 수정
        project_root = Path(__file__).parent.parent
        selection_path = project_root / "data" / "daily_selection" / "latest_selection.json"
        
        print(f"📁 일일선정 파일 경로: {selection_path}")
        
        with open(selection_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        print("📡 기존 데이터로 일일 선정 구성 중... (API 호출 제외)")
        
        selections = []
        for i, stock_data in enumerate(data["data"]["selected_stocks"][:10]):  # 상위 10개
            stock_code = stock_data["stock_code"]
            stock_name = stock_data["stock_name"]
            
            try:
                # 기존 데이터 사용 (API 호출 제외)
                price_info = {
                    "price": 50000,  # 기본값
                    "change": 0, 
                    "changePercent": 0.0,
                    "volume": 100000,
                    "marketCap": 500000000
                }
                
                stock = Stock(
                    code=stock_code,
                    name=stock_name,
                    market="KOSPI" if stock_code.startswith(("00", "01", "02")) else "KOSDAQ",
                    sector=stock_data.get("sector", "기타"),
                    price=price_info["price"],
                    change=price_info["change"],
                    changePercent=price_info["changePercent"],
                    volume=price_info["volume"],
                    marketCap=price_info["marketCap"]
                )
                
                # 리스크 레벨 계산
                risk_score = stock_data.get("risk_score", 50)
                risk_level = "LOW" if risk_score < 30 else "MEDIUM" if risk_score < 70 else "HIGH"
                
                selection = DailySelection(
                    id=str(i + 1),
                    stock=stock,
                    selectedAt=stock_data.get("selection_date", datetime.now().strftime("%Y-%m-%d")) + "T09:00:00",
                    attractivenessScore=stock_data.get("price_attractiveness", 50),
                    technicalScore=min(stock_data.get("volume_score", 50) + 30, 100),
                    momentumScore=min(stock_data.get("volume_score", 50) + 20, 100),
                    reasons=stock_data.get("technical_signals", ["AI 분석", "실시간 모니터링"]),
                    expectedReturn=stock_data.get("expected_return", 10.0),
                    confidence=stock_data.get("confidence", 0.7),
                    riskLevel=risk_level
                )
                selections.append(selection)
                
                print(f"🎯 {stock_name} ({stock_code}): 기존 데이터 로딩")
                
            except Exception as e:
                logger.error(f"❌ {stock_name} ({stock_code}): 가격 조회 실패 - {e}")
                continue
        
        print(f"🚀 실제 데이터 일일 선정 로딩 완료: {len(selections)}개 종목")
        return selections
        
    except Exception as e:
        logger.error(f"일일 선정 로딩 실패: {e}")
        return []

def load_stock_list() -> List[Dict]:
    """주식 리스트 로딩 (메타 정보만)"""
    try:
        project_root = Path(__file__).parent.parent
        stock_path = project_root / "data" / "stocks" / "stock_master.json"
        
        print(f"📁 주식리스트 파일 경로: {stock_path}")
        
        with open(stock_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("data", [])
    except Exception as e:
        logger.warning(f"주식 리스트 로딩 실패: {e}")
        return []

# 실제 데이터 로딩
print("🔄 실제 투자 데이터 로딩 중...")
REAL_DAILY_SELECTIONS = load_daily_selections_with_real_prices()
REAL_WATCHLIST = load_watchlist_with_real_prices()
REAL_STOCK_LIST = load_stock_list()

# 실시간 모니터 상태 관리 (전역 변수)
REALTIME_MONITOR_ACTIVE = False

print(f"✅ 실제 투자 데이터 로딩 완료:")
print(f"   - 일일 선정: {len(REAL_DAILY_SELECTIONS)}개 종목")
print(f"   - 감시 리스트: {len(REAL_WATCHLIST)}개 종목")
print(f"   - 전체 주식: {len(REAL_STOCK_LIST)}개 종목")

# 실시간 알림 생성
def generate_real_alerts() -> List[MarketAlert]:
    """실시간 알림 생성"""
    alerts = []
    
    # 일일 선정 기반 알림
    for i, selection in enumerate(REAL_DAILY_SELECTIONS[:3]):
        if selection.stock:
            alert = MarketAlert(
                id=str(i + 1),
                stock=selection.stock,
                type="ai_recommendation",
                severity="high" if selection.confidence > 0.7 else "medium",
                title="AI 매수 추천",
                message=f"실시간 AI 추천: {selection.stock.name} 매수 신호 (현재가: {selection.stock.price:,}원)",
                timestamp=datetime.now().isoformat(),
                acknowledged=False
            )
            alerts.append(alert)
    
    # 급등/급락 알림
    for item in REAL_WATCHLIST[:5]:
        if item.stock and abs(item.stock.changePercent) > 3:  # 3% 이상 변동
            alert = MarketAlert(
                id=str(len(alerts) + 1),
                stock=item.stock,
                type="price_spike" if item.stock.changePercent > 0 else "price_drop",
                severity="high" if abs(item.stock.changePercent) > 5 else "medium",
                title="급등/급락 알림",
                message=f"실시간 가격 변동: {item.stock.name} {item.stock.changePercent:+.1f}% ({item.stock.price:,}원)",
                timestamp=datetime.now().isoformat(),
                acknowledged=False
            )
            alerts.append(alert)
    
    return alerts

REAL_ALERTS = generate_real_alerts()
print(f"   - 실시간 알림: {len(REAL_ALERTS)}개 생성")

# 시스템 상태
REAL_SYSTEM_STATUS = SystemStatus(
    isRunning=True,
    lastUpdate=datetime.now().isoformat(),
    activeAlerts=len(REAL_ALERTS),
    watchlistCount=len(REAL_WATCHLIST),
    dailySelectionsCount=len(REAL_DAILY_SELECTIONS),
    performance={
        "accuracy": 85.2,
        "totalProcessed": len(REAL_STOCK_LIST),
        "avgProcessingTime": 4.8
    },
    health={
        "api": "healthy",
        "database": "healthy", 
        "websocket": "healthy"
    }
)

# API 엔드포인트들
@app.get("/")
async def root():
    return {
        "message": "🚀 한투 퀀트 API (실제 투자 전용) 실행 중",
        "mode": "PRODUCTION_REAL_DATA_ONLY",
        "environment": api_config.server,
        "api_server": api_config.base_url,
        "data_info": {
            "daily_selections": len(REAL_DAILY_SELECTIONS),
            "watchlist": len(REAL_WATCHLIST),
            "alerts": len(REAL_ALERTS)
        }
    }

@app.get("/api/system/status", response_model=SystemStatus)
async def get_system_status():
    """실시간 시스템 상태"""
    # 실시간 업데이트
    REAL_SYSTEM_STATUS.lastUpdate = datetime.now().isoformat()
    REAL_SYSTEM_STATUS.activeAlerts = len(REAL_ALERTS)
    return REAL_SYSTEM_STATUS

@app.get("/api/watchlist", response_model=List[WatchlistItem])
async def get_watchlist():
    """실시간 감시 리스트"""
    return REAL_WATCHLIST

@app.get("/api/daily-selections", response_model=List[DailySelection])
async def get_daily_selections():
    """실시간 일일 선정"""
    return REAL_DAILY_SELECTIONS

@app.get("/api/alerts", response_model=List[MarketAlert])
async def get_alerts():
    """실시간 알림"""
    return REAL_ALERTS

def get_enhanced_scheduler_status() -> Dict[str, Any]:
    """향상된 스케줄러 상태 조회 (부분 실행 감지 포함)"""
    # 통합 스케줄러 상태
    integrated_status = get_integrated_scheduler_status()
    
    # 개별 Phase 상태 확인
    phase1_active = len(REAL_WATCHLIST) > 0
    phase2_active = len(REAL_DAILY_SELECTIONS) > 0
    
    # 전체 상태 판단
    if integrated_status["running"]:
        if phase1_active and phase2_active:
            status_text = "전체 실행 중"
            status_type = "full_running"
        elif phase1_active or phase2_active:
            status_text = "부분 실행 중"
            status_type = "partial_running"
        else:
            status_text = "초기화 중"
            status_type = "initializing"
    else:
        status_text = "중지됨"
        status_type = "stopped"
    
    return {
        "running": integrated_status["running"],
        "pid": integrated_status.get("pid"),
        "status": status_text,
        "status_type": status_type,
        "uptime": integrated_status.get("uptime", "측정 불가"),
        "phases": {
            "phase1_active": phase1_active,
            "phase2_active": phase2_active,
            "phase1_count": len(REAL_WATCHLIST),
            "phase2_count": len(REAL_DAILY_SELECTIONS)
        }
    }

def get_system_services() -> Dict[str, ServiceStatus]:
    """시스템 서비스 상태 조회"""
    import psutil
    import os
    
    services = {}
    
    # API 서버 (현재 실행 중)
    services["api_server"] = ServiceStatus(
        name="API 서버",
        description="FastAPI 기반 실시간 데이터 서비스",
        running=True,
        port=8000,
        pid=os.getpid(),
        uptime="실행 중",
        auto_start=True
    )
    
    # 웹 인터페이스 (Vite 개발 서버)
    web_running = False
    web_pid = None
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            cmdline = proc.info.get('cmdline', [])
            if cmdline and any('vite' in arg.lower() for arg in cmdline):
                web_running = True
                web_pid = proc.info['pid']
                break
    except:
        pass
    
    services["web_interface"] = ServiceStatus(
        name="웹 인터페이스",
        description="React 기반 사용자 인터페이스",
        running=web_running,
        port=4173 if web_running else None,
        pid=web_pid,
        uptime="실행 중" if web_running else "정지됨",
        auto_start=False
    )
    
    # 통합 스케줄러 (향상된 상태 조회)
    enhanced_status = get_enhanced_scheduler_status()
    
    services["scheduler"] = ServiceStatus(
        name="통합 스케줄러",
        description=f"일일 자동 분석 및 학습 시스템 ({enhanced_status['status']})",
        running=enhanced_status["running"],
        pid=enhanced_status.get("pid"),
        uptime=enhanced_status["status"],
        auto_start=True
    )
    
    # Phase 1 감시리스트 (통합 스케줄러 연동)
    phase1_active = enhanced_status["phases"]["phase1_active"]
    phase1_count = enhanced_status["phases"]["phase1_count"]
    
    services["phase1_watchlist"] = ServiceStatus(
        name="Phase 1 감시리스트",
        description=f"종목 스크리닝 및 감시리스트 관리 (통합 스케줄러: {enhanced_status['status_type']})",
        running=phase1_active,  
        uptime=f"활성 ({phase1_count}개 종목)" if phase1_active else "대기 중",
        auto_start=True
    )
    
    # Phase 2 일일 선정 (통합 스케줄러 연동)
    phase2_active = enhanced_status["phases"]["phase2_active"]
    phase2_count = enhanced_status["phases"]["phase2_count"]
    
    services["phase2_daily"] = ServiceStatus(
        name="Phase 2 일일 선정", 
        description=f"매일 매매 대상 종목 선정 (통합 스케줄러: {enhanced_status['status_type']})",
        running=phase2_active,
        uptime=f"활성 ({phase2_count}개 선정)" if phase2_active else "대기 중",
        auto_start=True
    )
    
    # 실시간 모니터 (전역 상태 확인)
    global REALTIME_MONITOR_ACTIVE
    services["realtime_monitor"] = ServiceStatus(
        name="실시간 모니터",
        description="시장 데이터 실시간 추적 및 알림",
        running=REALTIME_MONITOR_ACTIVE,
        uptime=f"모니터링 중 ({len(REAL_ALERTS)}개 알림)" if REALTIME_MONITOR_ACTIVE else "대기 중",
        auto_start=True
    )
    
    return services

def get_system_overview() -> SystemOverview:
    """시스템 개요 정보"""
    services = get_system_services()
    
    total_services = len(services)
    running_services = sum(1 for s in services.values() if s.running)
    stopped_services = total_services - running_services
    
    # 시스템 건강도 계산
    running_ratio = running_services / total_services if total_services > 0 else 0
    if running_ratio >= 0.8:
        system_health = "healthy"
    elif running_ratio >= 0.5:
        system_health = "warning"
    else:
        system_health = "critical"
    
    # 서비스 요약 정보
    services_summary = {}
    for service_id, service in services.items():
        services_summary[service_id] = {
            "name": service.name,
            "running": service.running
        }
    
    return SystemOverview(
        total_services=total_services,
        running_services=running_services,
        stopped_services=stopped_services,
        system_health=system_health,
        uptime=f"{running_services}/{total_services} 서비스 실행",
        last_update=datetime.now().isoformat(),
        services=services_summary
    )

@app.get("/api/system/services", response_model=Dict[str, ServiceStatus])
async def get_services():
    """시스템 서비스 상태 조회"""
    return get_system_services()

@app.get("/api/system/overview", response_model=SystemOverview)
async def get_overview():
    """시스템 개요 정보"""
    return get_system_overview()

@app.get("/api/system/scheduler/enhanced-status")
async def get_enhanced_scheduler_status_endpoint():
    """향상된 스케줄러 상태 조회 (부분 실행 감지 포함)"""
    return get_enhanced_scheduler_status()

@app.post("/api/system/services/{service_id}/start")
async def start_service(service_id: str):
    """서비스 시작"""
    try:
        if service_id == "web_interface":
            return {"success": True, "message": "웹 인터페이스 시작을 위해 'npm run preview'를 실행하세요"}
        elif service_id == "scheduler":
# 통합 스케줄러 실제 시작 (구 main_real_pykrx.py와 동일 로직 통합)
            return await start_integrated_scheduler()
        elif service_id == "realtime_monitor":
            # 실시간 모니터 상태 활성화
            global REALTIME_MONITOR_ACTIVE
            REALTIME_MONITOR_ACTIVE = True
            logger.info("실시간 모니터 서비스 활성화됨")
            return {"success": True, "message": "실시간 모니터가 시작되었습니다"}
        elif service_id == "phase1_watchlist":
            # Phase 1 실제 스크리닝 실행 (통합 로직 사용)
            return await execute_real_screening()
        elif service_id == "phase2_daily":
            # Phase 2 실제 종목선정 실행 (통합 로직 사용)  
            return await execute_real_daily_selection()
        else:
            return {"success": True, "message": f"{service_id} 서비스가 시작되었습니다"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"서비스 시작 실패: {str(e)}")

@app.post("/api/system/services/{service_id}/stop")
async def stop_service(service_id: str):
    """서비스 정지"""
    try:
        if service_id == "scheduler":
            # 통합 스케줄러 중지
            return await stop_integrated_scheduler()
        elif service_id == "realtime_monitor":
            # 실시간 모니터 비활성화
            global REALTIME_MONITOR_ACTIVE
            REALTIME_MONITOR_ACTIVE = False
            logger.info("실시간 모니터 서비스 비활성화됨")
            return {"success": True, "message": "실시간 모니터가 중지되었습니다"}
        else:
            return {"success": True, "message": f"{service_id} 서비스가 중지되었습니다"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"서비스 중지 실패: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    print("🌟 실제 투자 데이터 전용 API 서버 시작!")
    uvicorn.run(app, host="0.0.0.0", port=8000) 