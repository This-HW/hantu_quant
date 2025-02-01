import os
from dotenv import load_dotenv
import logging

# .env 파일 로드
load_dotenv()

# 로깅 설정
LOG_LEVEL = logging.INFO
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# API 설정
APP_KEY =  os.getenv('APP_KEY')
APP_SECRET = os.getenv('APP_SECRET')
ACCOUNT_NUMBER = os.getenv('ACCOUNT_NUMBER')
ACCOUNT_PROD_CODE = os.getenv('ACCOUNT_PROD_CODE', '01')
SERVER = os.getenv('SERVER', 'virtual')  # virtual 또는 prod

# API 엔드포인트
VIRTUAL_URL = "https://openapivts.koreainvestment.com:29443"
PROD_URL = "https://openapi.koreainvestment.com:9443"
SOCKET_VIRTUAL_URL = "wss://openapivts.koreainvestment.com:29443"
SOCKET_PROD_URL = "wss://openapi.koreainvestment.com:21000"

# WebSocket URL
VIRTUAL_WS_URL = 'ws://ops.koreainvestment.com:31000'
PROD_WS_URL = 'ws://ops.koreainvestment.com:21000'

# 데이터베이스 설정
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///stock_data.db')

# 거래 시간 설정
MARKET_START_TIME = '09:00'
MARKET_END_TIME = '15:30'

# 기타 설정
MAX_RETRIES = 3
REQUEST_TIMEOUT = 10
RATE_LIMIT_PER_SEC = 5  # 초당 최대 요청 횟수

# 로깅 설정
LOG_FILE = 'trading.log'

# API 요청 설정
REQUEST_TIMEOUT = 10
RATE_LIMIT_PER_SEC = 5  # 초당 최대 요청 횟수 