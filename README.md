# Hantu Quant

한투 API를 이용한 퀀트 트레이딩 시스템

## 프로젝트 구조

```
hantu_quant/
├── core/                   # 핵심 기능
│   ├── api/               # API 관련 모듈
│   │   ├── kis_api.py    # 한국투자증권 API
│   │   ├── krx_client.py # KRX API
│   │   ├── rest_client.py # REST API 클라이언트
│   │   └── websocket_client.py # WebSocket 클라이언트
│   ├── config/           # 설정 관련 모듈
│   │   ├── settings.py   # 기본 설정
│   │   ├── api_config.py # API 설정
│   │   └── trading_config.py # 트레이딩 설정
│   ├── database/         # 데이터베이스 관련
│   │   ├── models.py     # DB 모델
│   │   ├── repository.py # 저장소 클래스
│   │   └── session.py    # DB 세션 관리
│   ├── realtime/        # 실시간 처리
│   │   ├── processor.py  # 데이터 처리기
│   │   └── handlers.py   # 이벤트 핸들러
│   └── utils/           # 유틸리티
├── hantu_backtest/      # 백테스팅 엔진
│   ├── core/            # 백테스트 핵심
│   ├── optimization/    # 전략 최적화
│   ├── strategies/      # 백테스트 전략
│   └── visualization/   # 결과 시각화
├── hantu_common/        # 공통 라이브러리
│   ├── data/           # 데이터 관리
│   ├── indicators/     # 기술적 지표
│   └── utils/          # 공통 유틸리티
├── scripts/            # 실행 스크립트
│   ├── collect_data.py # 데이터 수집
│   ├── init_db.py     # DB 초기화
│   └── query_db.py    # DB 조회
├── tests/             # 테스트 코드
├── data/              # 데이터 저장소
│   ├── db/           # 데이터베이스 파일
│   ├── stock/        # 주식 데이터
│   └── logs/         # 로그 파일
└── logs/             # 애플리케이션 로그
```

## 주요 기능

### 1. 실시간 트레이딩
- 한국투자증권 API를 통한 실시간 주식 거래
- WebSocket을 통한 실시간 시세 수신
- 자동 매매 전략 실행

### 2. 백테스팅
- 과거 데이터 기반 전략 테스트
- 다양한 성과 지표 계산
- 전략 최적화 및 시각화

### 3. 데이터 관리
- SQLite 데이터베이스를 통한 데이터 관리
- KRX 종목 정보 자동 수집
- 실시간/일별 주가 데이터 관리

### 4. 기술적 지표
- RSI, MACD, 볼린저 밴드 등 구현
- 커스텀 지표 추가 가능
- 실시간 지표 계산

## 설치 및 실행

1. 환경 설정
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

2. 환경 변수 설정
```bash
cp .env.example .env
# .env 파일에 API 키 등 설정
```

3. 데이터베이스 초기화
```bash
python scripts/init_db.py
```

4. 실행
```bash
# 실시간 트레이딩
python main.py trade

# 백테스트 실행
python -m hantu_backtest.main
```

## 개발 가이드

### 1. 새로운 전략 추가
- `hantu_backtest/strategies/` 디렉토리에 전략 클래스 추가
- `BacktestStrategy` 클래스를 상속받아 구현

### 2. 기술적 지표 추가
- `hantu_common/indicators/` 디렉토리에 지표 클래스 추가
- `Indicator` 기본 클래스를 상속받아 구현

### 3. 테스트 작성
- `tests/` 디렉토리에 테스트 코드 추가
- pytest를 사용한 단위 테스트 작성

## 의존성 패키지

- pandas==2.2.0
- numpy==1.26.3
- sqlalchemy==2.0.25
- matplotlib==3.8.2
- pyarrow==15.0.0
- 기타: requirements.txt 참조

## 라이선스

MIT License 