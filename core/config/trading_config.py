"""
Trading configuration settings.
"""

# 트레이딩 설정
TRADE_AMOUNT = 1000000  # 1회 매매 금액
MAX_STOCKS = 5          # 최대 보유 종목 수
MAX_TRADES_PER_DAY = 5  # 일일 최대 거래 횟수
MAX_TRADES_PER_STOCK = 2  # 종목당 최대 거래 횟수

# 거래 시간 설정
MARKET_START_TIME = '09:00'  # 장 시작 시간
MARKET_END_TIME = '15:30'    # 장 종료 시간

# 거래 설정
MAX_RETRIES = 3              # API 호출 최대 재시도 횟수
RETRY_DELAY = 1.0           # API 호출 재시도 간격 (초)
REQUEST_TIMEOUT = 10.0      # API 요청 타임아웃 (초)

# 주문 설정
DEFAULT_ORDER_TYPE = '00'    # 기본 주문 유형 (지정가)
DEFAULT_ORDER_PRICE = 0      # 기본 주문 가격 (시장가)

# 포지션 설정
MAX_POSITION_SIZE = 100      # 최대 포지션 크기 (%)
STOP_LOSS_PCT = 2.0         # 손절 비율 (%)
TAKE_PROFIT_PCT = 5.0       # 익절 비율 (%)

# 백테스팅 설정
INITIAL_CAPITAL = 10000000  # 초기 자본금
COMMISSION_RATE = 0.00015   # 수수료율 (0.015%)

# 모멘텀 전략 설정
RSI_PERIOD = 14
RSI_BUY_THRESHOLD = 30
RSI_SELL_THRESHOLD = 70

# 거래량 설정
MIN_VOLUME = 10000
VOLUME_SURGE_RATIO = 2.0

# 트레이딩 기본 설정
MAX_STOCK_PRICE = 1_000_000  # 종목당 최대 투자금액
MIN_TRADING_AMOUNT = 100_000  # 최소 거래금액

# 수익률 설정
TARGET_PROFIT_RATE = 0.05  # 목표 수익률 (5%)
STOP_LOSS_RATE = -0.03  # 손절률 (-3%)
TRAILING_STOP_RATE = 0.02  # 트레일링 스탑 비율 (2%)

# ----- 미세 타점/리스크 파라미터 -----
# 호가 스프레드 허용(상대) 기준
MAX_RELATIVE_SPREAD = 0.005  # 0.5%
# 호가 불균형 임계 ( (Σask-Σbid)/(Σask+Σbid) )
ORDERBOOK_IMBALANCE_BUY_MIN = -0.2
ORDERBOOK_IMBALANCE_SELL_MAX = 0.2
# 업틱 비율 임계
UPTICK_RATIO_BUY_MIN = 0.6
UPTICK_RATIO_SELL_MAX = 0.4
# VWAP / 괴리 허용 범위
VWAP_DEVIATION_MAX = 0.01  # 1%

# 이동평균선 설정
MA_SHORT = 5
MA_MEDIUM = 20
MA_LONG = 60  # 장기 이동평균

# 볼린저 밴드 설정
BOLLINGER_PERIOD = 20
BOLLINGER_STD = 2

# 거래 제한 설정
MAX_BUY_COUNT_PER_DAY = 5  # 일일 최대 매수 횟수
MAX_SELL_COUNT_PER_DAY = 5  # 일일 최대 매도 횟수
TRADING_AMOUNT_RATIO = 0.2  # 계좌 잔고 대비 최대 거래 비율 