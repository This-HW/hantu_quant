# 트레이딩 설정
TRADE_AMOUNT = 1000000  # 1회 매매 금액
MAX_STOCKS = 5          # 최대 보유 종목 수
MAX_TRADES_PER_DAY = 5  # 일일 최대 거래 횟수
MAX_TRADES_PER_STOCK = 2  # 종목당 최대 거래 횟수

# 거래 시간 설정
MARKET_START_TIME = '09:00'
MARKET_END_TIME = '15:30'

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