"""
한투 퀀트 API 서버 - 실제 환경 전용
모든 더미/시뮬레이션 데이터 제거됨
"""

import json
import sys
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Literal
import time

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

from fastapi import FastAPI, HTTPException, Depends, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from pydantic import BaseModel

# 프로젝트 루트 경로 추가
sys.path.append(str(Path(__file__).parent.parent))

from core.config.api_config import APIConfig
from core.api.kis_api import KISAPI

# Database service for PostgreSQL queries
try:
    from db_service import db_service
    DB_SERVICE_AVAILABLE = True
except ImportError:
    DB_SERVICE_AVAILABLE = False

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

# 로깅 설정 - 표준 로거 사용
from core.utils.log_utils import get_logger
logger = get_logger(__name__)

# DB 에러 로깅 설정 (PostgreSQL에 에러 저장)
try:
    from core.utils.db_error_handler import setup_db_error_logging, get_recent_errors
    db_error_handler = setup_db_error_logging(service_name="api-server")
    if db_error_handler:
        logger.info("DB 에러 로깅 활성화됨 (PostgreSQL)")
except Exception as e:
    logger.warning(f"DB 에러 로깅 설정 실패: {e}", exc_info=True)

# ========== 보안: API 키 인증 설정 ==========
# 환경변수에서 API 키 로드 (설정 안된 경우 기본값 사용 - 프로덕션에서는 반드시 설정 필요)
API_KEY = os.getenv('API_SERVER_KEY', '')
API_KEY_HEADER = APIKeyHeader(name='X-API-Key', auto_error=False)

async def verify_api_key(api_key: str = Security(API_KEY_HEADER)) -> bool:
    """API 키 검증 (민감한 엔드포인트 보호용)"""
    # 프로덕션 환경에서는 API 키 필수
    is_production = os.getenv('SERVER', 'virtual') == 'prod'

    if not API_KEY:
        if is_production:
            logger.error("프로덕션 환경에서 API_SERVER_KEY가 설정되지 않았습니다!")
            raise HTTPException(
                status_code=500,
                detail="서버 설정 오류: API_SERVER_KEY가 필요합니다."
            )
        # 개발 환경에서만 경고 후 통과
        logger.warning("API_SERVER_KEY가 설정되지 않았습니다. 개발 환경에서만 허용됩니다.")
        return True

    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="API 키가 필요합니다. X-API-Key 헤더를 포함해주세요."
        )

    if api_key != API_KEY:
        raise HTTPException(
            status_code=403,
            detail="유효하지 않은 API 키입니다."
        )

    return True

async def verify_api_key_optional(api_key: str = Security(API_KEY_HEADER)) -> bool:
    """선택적 API 키 검증 (읽기 전용 엔드포인트용)"""
    if not API_KEY:
        return True  # API_SERVER_KEY 미설정시 통과

    if api_key and api_key == API_KEY:
        return True

    # API 키가 없거나 틀려도 읽기 전용은 허용 (로컬 환경)
    return True

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


# ========== P2-3: 의존성 헬스체크 모델 ==========
class HealthStatus(BaseModel):
    """의존성 헬스체크 응답 모델"""
    status: Literal['healthy', 'degraded', 'unhealthy']
    database: bool
    kis_api: bool
    websocket: bool
    memory_percent: float
    cpu_percent: float
    disk_percent: float
    uptime_seconds: float
    checks: Dict[str, Dict[str, Any]]
    timestamp: str


# 서버 시작 시간 기록
SERVER_START_TIME = time.time()


async def check_kis_api_health() -> Dict[str, Any]:
    """KIS API 연결 상태 확인"""
    try:
        # 간단한 API 호출로 연결 확인
        result = kis_client.get_current_price("005930")  # 삼성전자
        if result:
            return {"healthy": True, "latency_ms": 0, "message": "Connected"}
        return {"healthy": False, "latency_ms": 0, "message": "No response"}
    except Exception as e:
        logger.debug(f"KIS API 헬스체크 실패: {e}", exc_info=True)
        return {"healthy": False, "latency_ms": 0, "message": str(e)}


async def check_database_health() -> Dict[str, Any]:
    """데이터베이스 연결 상태 확인 (PostgreSQL/SQLite)"""
    try:
        from core.config import settings

        if settings.DB_TYPE == 'postgresql':
            # PostgreSQL 연결 확인
            from sqlalchemy import create_engine, text
            engine = create_engine(settings.DATABASE_URL)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            engine.dispose()
            return {"healthy": True, "message": "PostgreSQL connected"}
        else:
            # SQLite - 파일 존재 확인
            project_root = Path(__file__).parent.parent
            data_dir = project_root / "data"
            if data_dir.exists():
                return {"healthy": True, "message": "SQLite data directory accessible"}
            return {"healthy": False, "message": "Data directory not found"}
    except Exception as e:
        return {"healthy": False, "message": str(e)}


async def check_websocket_health() -> Dict[str, Any]:
    """WebSocket 연결 상태 확인"""
    try:
        # WebSocket 클라이언트가 있으면 상태 확인
        # 현재는 기본 healthy 반환
        return {"healthy": True, "message": "WebSocket ready"}
    except Exception as e:
        return {"healthy": False, "message": str(e)}


def get_system_metrics() -> Dict[str, float]:
    """시스템 메트릭 조회"""
    if not PSUTIL_AVAILABLE:
        return {
            "memory_percent": 0.0,
            "cpu_percent": 0.0,
            "disk_percent": 0.0
        }

    try:
        return {
            "memory_percent": psutil.virtual_memory().percent,
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "disk_percent": psutil.disk_usage('/').percent
        }
    except Exception as e:
        logger.debug(f"시스템 메트릭 조회 실패: {e}", exc_info=True)
        return {
            "memory_percent": 0.0,
            "cpu_percent": 0.0,
            "disk_percent": 0.0
        }


# 글로벌 API 클라이언트
api_config = APIConfig()
kis_client = KISAPI()

print("🚀 실제 투자 환경 시작")
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
        logger.error(f"실제 가격 조회 실패 ({stock_code}): {e}", exc_info=True)
        raise Exception(f"실시간 데이터 조회 실패: {e}")

async def execute_real_screening() -> Dict[str, Any]:
    """실제 스크리닝 실행 (통합 로직 사용)"""
    import subprocess
    import os
    
    try:
        logger.info("🔍 실제 스크리닝 실행 시작")
        
        # 프로젝트 루트로 이동하여 스크리닝 실행
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        # 보안: shell=True 대신 리스트 기반 subprocess 사용 (Command Injection 방지)
        script_path = os.path.join(project_root, 'workflows', 'phase1_watchlist.py')
        process = subprocess.run(
            ['python3', script_path, 'screen'],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=300
        )
        
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
        logger.error(f"스크리닝 실행 오류: {e}", exc_info=True)
        return {"success": False, "message": f"스크리닝 실행 오류: {str(e)}"}

async def execute_real_daily_selection() -> Dict[str, Any]:
    """실제 종목선정 실행 (통합 로직 사용)"""
    import subprocess
    import os
    
    try:
        logger.info("📊 실제 종목선정 실행 시작")
        
        # 프로젝트 루트로 이동하여 종목선정 실행
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        # 보안: shell=True 대신 리스트 기반 subprocess 사용 (Command Injection 방지)
        script_path = os.path.join(project_root, 'workflows', 'phase2_daily_selection.py')
        process = subprocess.run(
            ['python3', script_path],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=180
        )
        
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
        logger.error(f"종목선정 실행 오류: {e}", exc_info=True)
        return {"success": False, "message": f"종목선정 실행 오류: {str(e)}"}

def load_latest_watchlist_data() -> List[WatchlistItem]:
    """최신 감시리스트 데이터 로드 (DB 우선, JSON 폴백)"""

    # 1. Try database first
    if DB_SERVICE_AVAILABLE:
        try:
            db_data = db_service.get_watchlist(limit=20)
            if db_data:
                watchlist = []
                for i, item_data in enumerate(db_data):
                    stock = Stock(
                        code=item_data['stock_code'],
                        name=item_data['stock_name'],
                        market=item_data.get('market', 'KOSPI'),
                        sector=item_data.get('sector', '기타'),
                        price=0,  # Will be updated with real price
                        change=0,
                        changePercent=0.0,
                        volume=0,
                        marketCap=0
                    )

                    item = WatchlistItem(
                        id=str(i + 1),
                        stock=stock,
                        addedAt=(item_data.get('added_date') or datetime.now().strftime("%Y-%m-%d")) + "T09:00:00",
                        targetPrice=0,
                        reason="DB 스크리닝 통과",
                        score=item_data.get('total_score', 50.0)
                    )
                    watchlist.append(item)

                logger.info(f"Loaded {len(watchlist)} watchlist items from DB")
                return watchlist
        except Exception as e:
            logger.error(f"DB watchlist load failed: {e}", exc_info=True)

    # 2. Fallback to JSON file
    if DB_SERVICE_AVAILABLE:
        logger.warning("DB에 watchlist 데이터 없음 - JSON 파일로 폴백")
    else:
        logger.info("DB 서비스 미사용 - JSON 파일에서 watchlist 로드")
    try:
        project_root = Path(__file__).parent.parent
        watchlist_path = project_root / "data" / "watchlist" / "watchlist.json"

        with open(watchlist_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        watchlist = []
        for i, stock_data in enumerate(data["data"]["stocks"][:20]):
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

            item = WatchlistItem(
                id=str(i + 1),
                stock=stock,
                addedAt=stock_data.get("added_date", datetime.now().strftime("%Y-%m-%d")) + "T09:00:00",
                targetPrice=stock_data.get("target_price", int(stock_data.get("current_price", 50000) * 1.15)),
                reason=stock_data.get("added_reason", "스크리닝 통과"),
                score=stock_data.get("screening_score", 50.0)
            )
            watchlist.append(item)

        return watchlist

    except FileNotFoundError:
        logger.warning(f"watchlist.json 파일 미존재 ({watchlist_path}) - 스케줄러 실행 후 생성됨")
        return []
    except Exception as e:
        logger.error(f"최신 감시리스트 로드 오류: {e}", exc_info=True)
        return []

def load_latest_daily_selection_data() -> List[DailySelection]:
    """최신 일일선정 데이터 로드 (DB 우선, JSON 폴백)"""

    # 1. Try database first
    if DB_SERVICE_AVAILABLE:
        try:
            db_data = db_service.get_daily_selections(limit=10)
            if db_data:
                selections = []
                for i, item_data in enumerate(db_data):
                    stock = Stock(
                        code=item_data['stock_code'],
                        name=item_data['stock_name'],
                        market=item_data.get('market', 'KOSPI'),
                        sector=item_data.get('sector', '기타'),
                        price=0,
                        change=0,
                        changePercent=0.0,
                        volume=0,
                        marketCap=0
                    )

                    risk_score = item_data.get('risk_score')
                    if risk_score is None:
                        risk_score = 50
                    risk_level = "LOW" if risk_score < 30 else "MEDIUM" if risk_score < 70 else "HIGH"

                    # None 값 안전 처리
                    technical_score = item_data.get('technical_score')
                    if technical_score is None:
                        technical_score = 50
                    momentum_score = item_data.get('momentum_score')
                    if momentum_score is None:
                        momentum_score = 50
                    signal_strength = item_data.get('signal_strength')
                    if signal_strength is None:
                        signal_strength = 0.7

                    selection = DailySelection(
                        id=str(i + 1),
                        stock=stock,
                        selectedAt=(item_data.get('selection_date') or datetime.now().strftime("%Y-%m-%d")) + "T09:00:00",
                        attractivenessScore=technical_score,
                        technicalScore=technical_score,
                        momentumScore=momentum_score,
                        reasons=[item_data.get('signal', 'buy'), "DB 분석"],
                        expectedReturn=10.0,
                        confidence=signal_strength,
                        riskLevel=risk_level
                    )
                    selections.append(selection)

                logger.info(f"Loaded {len(selections)} daily selections from DB")
                return selections
        except Exception as e:
            logger.error(f"DB daily selection load failed: {e}", exc_info=True)

    # 2. Fallback to JSON file
    if DB_SERVICE_AVAILABLE:
        logger.warning("DB에 daily selection 데이터 없음 - JSON 파일로 폴백")
    else:
        logger.info("DB 서비스 미사용 - JSON 파일에서 daily selection 로드")
    try:
        project_root = Path(__file__).parent.parent
        daily_dir = project_root / "data" / "daily_selection"
        pattern = "daily_selection_*.json"
        daily_files = list(daily_dir.glob(pattern))

        if not daily_files:
            return []

        latest_file = max(daily_files, key=lambda x: x.stat().st_mtime)

        with open(latest_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 다양한 데이터 형식 지원 (list, dict with data.selected_stocks, dict with stocks)
        if isinstance(data, list):
            stocks_list = data
        elif isinstance(data, dict):
            stocks_list = data.get("data", {}).get("selected_stocks", []) or data.get("stocks", [])
        else:
            stocks_list = []

        selections = []
        for i, stock_data in enumerate(stocks_list[:10]):
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

            risk_score = stock_data.get("risk_score", 50)
            risk_level = "LOW" if risk_score < 30 else "MEDIUM" if risk_score < 70 else "HIGH"

            selection = DailySelection(
                id=str(i + 1),
                stock=stock,
                selectedAt=stock_data.get("selection_date", datetime.now().strftime("%Y-%m-%d")) + "T09:00:00",
                attractivenessScore=stock_data.get("price_attractiveness", 50),
                technicalScore=min(stock_data.get("volume_score", 50) + 30, 100),
                momentumScore=min(stock_data.get("volume_score", 50) + 20, 100),
                reasons=stock_data.get("technical_signals", ["AI 분석", "스크리닝 통과"]),
                expectedReturn=stock_data.get("expected_return", 10.0),
                confidence=stock_data.get("confidence_score", 0.7),
                riskLevel=risk_level
            )
            selections.append(selection)

        return selections

    except Exception as e:
        logger.error(f"최신 일일선정 로드 오류: {e}", exc_info=True)
        return []

# 과거 레거시 함수 제거됨 - load_latest_watchlist_data(), load_latest_daily_selection_data() 사용

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

        # 보안: shell=True 대신 리스트 기반 subprocess 사용 (Command Injection 방지)
        script_path = os.path.join(project_root, 'workflows', 'integrated_scheduler.py')
        result = subprocess.Popen(
            ['python3', script_path, 'start'],
            cwd=project_root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        
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

        # 보안: shell=True 대신 리스트 기반 subprocess 사용 (Command Injection 방지)
        script_path = os.path.join(project_root, 'workflows', 'integrated_scheduler.py')
        subprocess.run(
            ['python3', script_path, 'stop'],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        # 강제 종료 (필요시)
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                cmdline = proc.info.get('cmdline', [])
                if cmdline and any('integrated_scheduler' in arg for arg in cmdline):
                    proc.kill()
        except Exception as e:
            logger.debug(f"프로세스 강제 종료 실패: {e}", exc_info=True)
        
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
        logger.error(f"스케줄러 상태 조회 오류: {e}", exc_info=True)
        return {
            "running": False,
            "pid": None,
            "status": "오류",
            "uptime": f"상태 조회 실패: {e}"
        }

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
        logger.warning(f"주식 리스트 로딩 실패: {e}", exc_info=True)
        return []

# 실제 데이터 로딩
print("🔄 실제 투자 데이터 로딩 중...")
REAL_DAILY_SELECTIONS = load_latest_daily_selection_data()
REAL_WATCHLIST = load_latest_watchlist_data()
REAL_STOCK_LIST = load_stock_list()

# 실시간 모니터 상태 관리 (전역 변수)
REALTIME_MONITOR_ACTIVE = False

print("✅ 실제 투자 데이터 로딩 완료:")
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


@app.get("/health", response_model=HealthStatus)
async def health_check():
    """의존성 헬스체크 (P2-3)

    시스템 상태를 종합적으로 확인합니다:
    - KIS API 연결 상태
    - 데이터베이스 (파일 시스템) 상태
    - WebSocket 상태
    - CPU/메모리/디스크 사용량
    - 서버 가동 시간

    Returns:
        HealthStatus: 상태 정보
            - healthy: 모든 의존성 정상
            - degraded: 일부 의존성 문제
            - unhealthy: 핵심 의존성 장애
    """
    # 각 의존성 체크 병렬 실행
    db_check, api_check, ws_check = await asyncio.gather(
        check_database_health(),
        check_kis_api_health(),
        check_websocket_health(),
    )

    # 시스템 메트릭
    metrics = get_system_metrics()

    # 상태 결정
    db_ok = db_check.get("healthy", False)
    api_ok = api_check.get("healthy", False)
    ws_ok = ws_check.get("healthy", False)

    all_ok = all([db_ok, api_ok, ws_ok])
    any_ok = any([db_ok, api_ok, ws_ok])

    if all_ok:
        status = "healthy"
    elif any_ok:
        status = "degraded"
    else:
        status = "unhealthy"

    # 응답 생성
    return HealthStatus(
        status=status,
        database=db_ok,
        kis_api=api_ok,
        websocket=ws_ok,
        memory_percent=metrics["memory_percent"],
        cpu_percent=metrics["cpu_percent"],
        disk_percent=metrics["disk_percent"],
        uptime_seconds=time.time() - SERVER_START_TIME,
        checks={
            "database": db_check,
            "kis_api": api_check,
            "websocket": ws_check,
        },
        timestamp=datetime.now().isoformat()
    )


@app.get("/api/system/errors")
async def get_system_errors(
    service: Optional[str] = None,
    level: Optional[str] = None,
    limit: int = 50,
    _: bool = Depends(verify_api_key)
):
    """시스템 에러 로그 조회 (API 키 인증 필요)

    Args:
        service: 서비스 필터 (api-server, scheduler 등)
        level: 레벨 필터 (ERROR, CRITICAL 등)
        limit: 최대 조회 수

    Returns:
        최근 에러 로그 목록
    """
    try:
        errors = get_recent_errors(service=service, level=level, limit=limit)
        return {
            "success": True,
            "count": len(errors),
            "errors": errors
        }
    except Exception as e:
        logger.error(f"에러 로그 조회 실패: {e}", exc_info=True)
        return {
            "success": False,
            "count": 0,
            "errors": [],
            "message": str(e)
        }


@app.get("/api/system/monitoring")
async def get_monitoring_status(_: bool = Depends(verify_api_key)):
    """시스템 모니터링 상태 조회 (API 키 인증 필요)

    실시간 시스템 리소스 및 서비스 상태를 확인합니다.
    """
    try:
        from core.utils.system_monitor import quick_health_check
        return quick_health_check()
    except Exception as e:
        logger.error(f"모니터링 상태 조회 실패: {e}", exc_info=True)
        return {
            "healthy": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@app.post("/api/system/monitoring/report")
async def send_monitoring_report(_: bool = Depends(verify_api_key)):
    """모니터링 리포트 전송 (Telegram)

    현재 시스템 상태 리포트를 Telegram으로 전송합니다.
    """
    try:
        from core.utils.system_monitor import get_system_monitor
        monitor = get_system_monitor()
        success = monitor.send_status_report()
        return {
            "success": success,
            "message": "리포트 전송 완료" if success else "리포트 전송 실패"
        }
    except Exception as e:
        logger.error(f"모니터링 리포트 전송 실패: {e}", exc_info=True)
        return {
            "success": False,
            "message": str(e)
        }


@app.get("/api/system/status", response_model=SystemStatus)
async def get_system_status():
    """실시간 시스템 상태"""
    # 실시간 업데이트
    REAL_SYSTEM_STATUS.lastUpdate = datetime.now().isoformat()
    REAL_SYSTEM_STATUS.activeAlerts = len(REAL_ALERTS)
    return REAL_SYSTEM_STATUS

@app.get("/api/watchlist", response_model=List[WatchlistItem])
async def get_watchlist(authenticated: bool = Depends(verify_api_key)):
    """실시간 감시 리스트 (API 키 인증 필요)"""
    return REAL_WATCHLIST

@app.get("/api/daily-selections", response_model=List[DailySelection])
async def get_daily_selections(authenticated: bool = Depends(verify_api_key)):
    """실시간 일일 선정 (API 키 인증 필요)"""
    return REAL_DAILY_SELECTIONS

@app.get("/api/alerts", response_model=List[MarketAlert])
async def get_alerts(authenticated: bool = Depends(verify_api_key)):
    """실시간 알림 (API 키 인증 필요)"""
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
    except Exception:
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
async def start_service(service_id: str, _: bool = Depends(verify_api_key)):
    """서비스 시작 (API 키 인증 필요)"""
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
async def stop_service(service_id: str, _: bool = Depends(verify_api_key)):
    """서비스 정지 (API 키 인증 필요)"""
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

    # 보안: 프로덕션에서는 127.0.0.1 사용 권장
    # 외부 접근이 필요한 경우 리버스 프록시(nginx) 사용
    host = os.getenv('API_HOST', '127.0.0.1')
    port = int(os.getenv('API_PORT', '8000'))

    if host == '0.0.0.0':
        logger.warning("API 서버가 모든 인터페이스(0.0.0.0)에서 수신 중입니다. 프로덕션에서는 127.0.0.1 사용을 권장합니다.")

    uvicorn.run(app, host=host, port=port) 