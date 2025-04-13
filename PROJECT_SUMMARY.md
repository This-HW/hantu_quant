# 한투 퀀트 프로젝트 요약

## 프로젝트 구조

```
hantu_quant/
├── core/                   # 핵심 기능
│   ├── api/               # API 관련 모듈
│   ├── config/           # 설정 관련 모듈
│   ├── database/         # 데이터베이스 관련
│   ├── realtime/        # 실시간 처리
│   ├── strategy/        # 전략 구현
│   ├── trading/         # 트레이딩 모듈
│   └── utils/           # 유틸리티
├── hantu_backtest/      # 백테스팅 엔진
│   ├── core/            # 백테스트 핵심
│   ├── optimization/    # 전략 최적화
│   ├── strategies/      # 백테스트 전략
│   └── visualization/   # 결과 시각화
├── hantu_common/        # 공통 라이브러리
│   ├── data/           # 데이터 관리
│   ├── indicators/     # 기술적 지표
│   ├── models/         # 데이터 모델
│   └── utils/          # 공통 유틸리티
├── scripts/            # 실행 스크립트
├── tests/             # 테스트 코드
├── data/              # 데이터 저장소
│   ├── db/           # 데이터베이스 파일
│   ├── stock/        # 주식 데이터
│   ├── token/        # 토큰 정보
│   └── historical/   # 과거 데이터
└── logs/             # 애플리케이션 로그
```

## 주요 컴포넌트

### API 모듈
- 한국투자증권 API 연동 (core/api/kis_api.py)
- 한국거래소(KRX) 연동 (core/api/krx_client.py)
- WebSocket 실시간 데이터 (core/api/websocket_client.py)

### 전략 모듈
- 모멘텀 전략 (hantu_backtest/strategies/momentum.py)
- 볼린저 밴드 전략 (계획)
- 커스텀 전략 추가 가능

### 거래 모듈
- 자동 매매 (core/trading/auto_trader.py)
- 실시간 시세 처리 (core/realtime/processor.py)

### 백테스트 모듈
- 전략 백테스팅 (hantu_backtest/core)
- 최적화 및 시각화 (hantu_backtest/optimization, hantu_backtest/visualization)

## 설정 요약

### 환경 설정
- `.env` 파일에 API 키 및 계정 정보 설정
- 모의투자 vs 실제투자 환경 구분 (`SERVER` 설정)

### 토큰 관리
- 모의투자: `data/token/token_info_virtual.json`
- 실제투자: `data/token/token_info_real.json`

## 주요 기능

### 자동 매매
```bash
python main.py trade
```

### 잔고 조회
```bash
python main.py balance
```

### 종목 검색
```bash
python main.py find
```

### KRX 종목 목록 저장
```bash
python main.py list-stocks
```

### 백테스트 실행
```bash
python -m hantu_backtest.main
```

## 알려진 이슈 및 해결책

### API 토큰 인증 오류
- 문제: 토큰 갱신 실패 (403 오류)
- 해결: 
  1. 토큰 파일 삭제 후 재시도
  2. API 키 확인 및 갱신
  3. 서버 상태 확인

### 전략 실행 오류
- 문제: `MomentumStrategy` 초기화 시 API 객체 누락
- 해결: `strategy = MomentumStrategy(api)` 형태로 API 객체 전달 