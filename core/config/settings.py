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
DATABASE_URL = os.getenv('DATABASE_URL', SQLITE_URL)

# 데이터베이스 타입 감지
DB_TYPE = 'postgresql' if DATABASE_URL.startswith('postgresql') else 'sqlite'

# 데이터베이스 연결 설정
DB_POOL_SIZE = int(os.getenv('DB_POOL_SIZE', '5'))
DB_MAX_OVERFLOW = int(os.getenv('DB_MAX_OVERFLOW', '10'))
DB_POOL_TIMEOUT = int(os.getenv('DB_POOL_TIMEOUT', '30'))
DB_POOL_RECYCLE = int(os.getenv('DB_POOL_RECYCLE', '1800'))

# Redis 설정 (캐시용)
REDIS_URL = os.getenv('REDIS_URL', None)

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