# Hantu Quant

한국투자증권 API를 이용한 퀀트 자동매매 시스템

## 프로젝트 구조
```
hantu_quant/
├── core/                   # 핵심 기능
│   ├── api/               # API 관련
│   │   ├── kis_api.py     # API 통합 클라이언트
│   │   ├── rest_client.py # REST API 클라이언트
│   │   └── websocket_client.py # WebSocket API 클라이언트
│   ├── config/            # 설정 관련
│   └── database/          # 데이터베이스 관련
├── strategies/            # 매매 전략
│   ├── base.py           # 기본 전략 클래스
│   └── momentum.py       # 모멘텀 전략
└── utils/                # 유틸리티
```

## 기능
- 실시간 시세 조회
- 자동 매매 실행
- 다양한 매매 전략 지원
- 실시간 포트폴리오 관리
- 거래 이력 관리

## 설치 방법

1. 저장소 클론
```bash
git clone https://github.com/yourusername/hantu_quant.git
cd hantu_quant
```

2. 가상환경 생성 및 활성화
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate  # Windows
```

3. 의존성 패키지 설치
```bash
pip install -r requirements.txt
```

## 환경 설정

1. `.env` 파일 생성 및 설정
```bash
# .env 파일을 생성하고 아래 내용을 채워넣으세요
# 한국투자증권 API 설정
APP_KEY="발급받은_앱키"
APP_SECRET="발급받은_시크릿키"
ACCOUNT_NUMBER="계좌번호"
ACCOUNT_PROD_CODE="01"

# 서버 설정 (virtual: 모의투자, prod: 실전투자)
SERVER=virtual

# 로깅 설정 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
LOG_LEVEL=INFO

# 데이터베이스 설정
DATABASE_URL=sqlite:///core/database/stock_data.db
```

## 실행 방법

1. 기본 실행 (모멘텀 전략 사용)
```bash
python main.py
```

2. 특정 종목 모니터링
```python
# main.py 파일에서 target_codes 리스트 수정
target_codes = [
    "005930",  # 삼성전자
    "000660",  # SK하이닉스
    # ... 추가 종목 코드
]
```

## 매매 전략 설정

1. 모멘텀 전략 파라미터 (`core/config/trading_config.py`)
```python
# 수익률 설정
TARGET_PROFIT_RATE = 0.05  # 목표 수익률 (5%)
STOP_LOSS_RATE = -0.03    # 손절률 (-3%)

# RSI 설정
RSI_PERIOD = 14           # RSI 계산 기간
RSI_OVERSOLD = 30         # RSI 과매도 기준
RSI_OVERBOUGHT = 70       # RSI 과매수 기준

# 이동평균선 설정
MA_SHORT = 5              # 단기 이동평균
MA_MEDIUM = 20           # 중기 이동평균
```

## 로그 확인

- 실행 로그: `trading.log`
- 데이터베이스: `core/database/stock_data.db`

## 주의사항

1. API 키 보안
- `.env` 파일은 절대로 Git에 커밋하지 마세요
- API 키와 시크릿은 안전하게 보관하세요

2. 모의투자 테스트
- 실전 투자 전에 반드시 모의투자로 충분한 테스트를 진행하세요
- `SERVER=virtual` 설정으로 모의투자 환경에서 테스트하세요

3. 거래 제한
- 거래량이 적은 종목은 제외하는 것이 좋습니다
- 장 시작 시간(09:00)과 종료 시간(15:30)을 확인하세요

## 문제 해결

1. WebSocket 연결 오류
- 인터넷 연결 상태 확인
- API 키와 시크릿 값 확인
- 서버 설정(virtual/prod) 확인

2. 주문 실패
- 계좌 잔고 확인
- 주문 가능 시간 확인
- 호가 단위 확인

## 라이센스
MIT License 