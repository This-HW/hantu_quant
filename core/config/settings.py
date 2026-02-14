"""
Configuration management module.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
import logging

# .env 파일 로드
load_dotenv()

# 프로젝트 디렉토리 설정
ROOT_DIR = Path(__file__).parent.parent.parent
DATA_DIR = ROOT_DIR / 'data'

# 데이터 디렉토리 구조
DB_DIR = DATA_DIR / 'db'
STOCK_DIR = DATA_DIR / 'stock'
TOKEN_DIR = DATA_DIR / 'token'
HISTORICAL_DIR = DATA_DIR / 'historical'
METADATA_DIR = DATA_DIR / 'metadata'
LOG_DIR = ROOT_DIR / 'logs'

# 데이터베이스 설정
# 환경변수 DATABASE_URL이 있으면 사용 (PostgreSQL 등)
# 없으면 기본 SQLite 사용 (로컬 개발용)
DB_FILENAME = 'stock_data.db'
DB_PATH = DB_DIR / DB_FILENAME
SQLITE_URL = f"sqlite:///{DB_PATH.absolute()}"

# 환경 자동 감지
def _get_default_database_url():
    """환경별 기본 DATABASE_URL 반환

    주의: .pgpass 파일 기반 인증 사용
    Password authentication uses ~/.pgpass file:
    - 로컬: localhost:15432:hantu_quant:hantu:PASSWORD
    - 서버: localhost:5432:hantu_quant:hantu:PASSWORD
    """
    # 로거 설정 (사이클 참조 방지를 위해 지연 import)
    from core.utils.log_utils import get_logger
    logger = get_logger(__name__)

    # 1. 환경변수 HANTU_ENV 우선 체크 (local, server, test)
    env_override = os.getenv('HANTU_ENV', '').lower()
    if env_override == 'local':
        logger.debug("환경 감지: HANTU_ENV=local (환경변수 우선)")
        return "postgresql://hantu@localhost:15432/hantu_quant"
    elif env_override == 'server':
        logger.debug("환경 감지: HANTU_ENV=server (환경변수 우선)")
        return "postgresql://hantu@localhost:5432/hantu_quant"
    elif env_override == 'test':
        logger.debug("환경 감지: HANTU_ENV=test (환경변수 우선)")
        return SQLITE_URL

    # 2. 경로 기반 자동 감지
    root_path = str(ROOT_DIR)

    # 로컬 환경 패턴
    # macOS: /Users/{username}
    # Linux 개발 환경: /home/{username} (단, 서버 경로 /home/ubuntu 제외)
    is_local = (
        root_path.startswith("/Users/") or
        (root_path.startswith("/home/") and
         not root_path.startswith("/home/ubuntu"))
    )

    # 서버 환경 패턴
    is_server = (
        root_path.startswith("/opt/hantu_quant") or
        root_path.startswith("/opt/") or
        root_path.startswith("/home/ubuntu") or
        root_path.startswith("/srv/")
    )

    if is_local:
        logger.debug(f"환경 감지: 로컬 (경로: {root_path})")
        logger.debug("SSH 터널 필요: ./scripts/db-tunnel.sh start")
        return "postgresql://hantu@localhost:15432/hantu_quant"
    elif is_server:
        logger.debug(f"환경 감지: 서버 (경로: {root_path})")
        return "postgresql://hantu@localhost:5432/hantu_quant"
    else:
        # 알 수 없는 환경: 경고 후 로컬 설정 사용
        logger.warning(f"알 수 없는 환경 (경로: {root_path}). 로컬 설정 사용 (SSH 터널 포트)")
        return "postgresql://hantu@localhost:15432/hantu_quant"

# DATABASE_URL 설정
DATABASE_URL = os.getenv('DATABASE_URL', _get_default_database_url())

# 데이터베이스 타입 감지
DB_TYPE = 'postgresql' if DATABASE_URL.startswith('postgresql') else 'sqlite'

# DATABASE_URL 로깅 (비밀번호 마스킹)
try:
    from core.utils.log_utils import get_logger
    import re
    logger = get_logger(__name__)

    # 비밀번호 마스킹 (예: postgresql://user:password@host:port/db → postgresql://user:***@host:port/db)
    masked_url = re.sub(r'://([^:]+):([^@]+)@', r'://\1:***@', DATABASE_URL)
    logger.info(f"데이터베이스 연결: {masked_url} (타입: {DB_TYPE})")
except Exception as e:
    # 로깅 실패는 무시 (설정 초기화 중에는 로거가 없을 수 있음)
    pass

# 데이터베이스 연결 설정
DB_POOL_SIZE = int(os.getenv('DB_POOL_SIZE', '5'))
DB_MAX_OVERFLOW = int(os.getenv('DB_MAX_OVERFLOW', '10'))
DB_POOL_TIMEOUT = int(os.getenv('DB_POOL_TIMEOUT', '30'))
DB_POOL_RECYCLE = int(os.getenv('DB_POOL_RECYCLE', '1800'))

# Redis 설정 (캐시용)
REDIS_URL = os.getenv('REDIS_URL', None)

# Redis 모니터링 임계값 설정
REDIS_MEMORY_WARNING_THRESHOLD = float(os.getenv('REDIS_MEMORY_WARNING_THRESHOLD', '0.7'))  # 70%
REDIS_MEMORY_CRITICAL_THRESHOLD = float(os.getenv('REDIS_MEMORY_CRITICAL_THRESHOLD', '0.8'))  # 80%
REDIS_HIT_RATE_WARNING_THRESHOLD = float(os.getenv('REDIS_HIT_RATE_WARNING_THRESHOLD', '0.5'))  # 50%
REDIS_HIT_RATE_CRITICAL_THRESHOLD = float(os.getenv('REDIS_HIT_RATE_CRITICAL_THRESHOLD', '0.4'))  # 40%
REDIS_LATENCY_WARNING_MS = int(os.getenv('REDIS_LATENCY_WARNING_MS', '50'))  # 50ms
REDIS_LATENCY_CRITICAL_MS = int(os.getenv('REDIS_LATENCY_CRITICAL_MS', '100'))  # 100ms

# API 설정
APP_KEY = os.getenv('APP_KEY')
APP_SECRET = os.getenv('APP_SECRET')
ACCOUNT_NUMBER = os.getenv('ACCOUNT_NUMBER')
ACCOUNT_PROD_CODE = os.getenv('ACCOUNT_PROD_CODE', '01')

# 서버 환경 설정
# - virtual: 모의투자 (개발 및 테스트용)
# - prod: 실제투자 (실전 투자용)
SERVER = os.getenv('SERVER', 'virtual')

# API 엔드포인트
VIRTUAL_URL = "https://openapivts.koreainvestment.com:29443"     # 모의투자 서버
PROD_URL = "https://openapi.koreainvestment.com:9443"            # 실제투자 서버
SOCKET_VIRTUAL_URL = "wss://openapivts.koreainvestment.com:29443/websocket"  # 모의투자 WebSocket
SOCKET_PROD_URL = "wss://openapi.koreainvestment.com:21000/websocket"        # 실제투자 WebSocket

# API 요청 설정
REQUEST_TIMEOUT = 10
RATE_LIMIT_PER_SEC = 2  # 초당 최대 요청 횟수 (Rate Limit 에러 방지를 위해 2건으로 제한)

# 거래 시간 설정
MARKET_START_TIME = '09:00'
MARKET_END_TIME = '15:30'

# 로깅 설정
LOG_LEVEL = logging.getLevelName(os.getenv('LOG_LEVEL', 'INFO'))
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# 기타 설정
MAX_RETRIES = 3

# 거래 안전 가드 (실제투자 보호)
# - TRADING_PROD_ENABLE=true 일 때만 실제투자 주문 허용
TRADING_PROD_ENABLE = os.getenv('TRADING_PROD_ENABLE', 'false').lower() == 'true'

# Telegram 알림 설정
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

def create_directories():
    """필요한 디렉토리 생성"""
    directories = [
        DATA_DIR,
        DB_DIR,
        STOCK_DIR,
        TOKEN_DIR,
        HISTORICAL_DIR,
        METADATA_DIR,
        LOG_DIR
    ]
    
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)

# 시작 시 디렉토리 생성
create_directories()

# Settings 인스턴스 생성 (import 편의성을 위해)
class Settings:
    """설정 관리 클래스"""
    def __init__(self):
        """프로젝트 설정을 인스턴스로 제공"""
        # Redis 모니터링 임계값
        self.REDIS_MEMORY_WARNING_THRESHOLD = REDIS_MEMORY_WARNING_THRESHOLD
        self.REDIS_MEMORY_CRITICAL_THRESHOLD = REDIS_MEMORY_CRITICAL_THRESHOLD
        self.REDIS_HIT_RATE_WARNING_THRESHOLD = REDIS_HIT_RATE_WARNING_THRESHOLD
        self.REDIS_HIT_RATE_CRITICAL_THRESHOLD = REDIS_HIT_RATE_CRITICAL_THRESHOLD
        self.REDIS_LATENCY_WARNING_MS = REDIS_LATENCY_WARNING_MS
        self.REDIS_LATENCY_CRITICAL_MS = REDIS_LATENCY_CRITICAL_MS

settings = Settings() 