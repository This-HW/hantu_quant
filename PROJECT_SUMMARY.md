# 한투 퀀트 프로젝트 요약

## 프로젝트 개요
한국투자증권 API를 활용한 단계별 자동매매 시스템 구축 프로젝트입니다.
5단계 개발 방식으로 점진적이고 안정적인 시스템을 구축합니다.

## 단계별 개발 계획

### Phase 1: 감시 리스트 구축 (core/watchlist/) ✅ 완료
- **목표**: 좋은 기업을 찾아서 매매 희망 리스트 혹은 감시 리스트에 추가
- **핵심 기능**: 기업 스크리닝, 감시 리스트 관리, 기업 평가
- **완료일**: 2025-07-09
- **구현 내용**: 
  - StockScreener: 재무/기술/모멘텀 기반 종목 스크리닝
  - WatchlistManager: 감시 리스트 CRUD 및 관리
  - EvaluationEngine: 가중치 기반 종합 평가
  - Phase1Workflow: CLI 기반 워크플로우

### Phase 2: 일일 매매 주식 선정 (core/daily_selection/)
- **목표**: 매일 감시 리스트에서 가격이 매력적인 주식을 당일 매매 리스트에 업데이트
- **핵심 기능**: 가격 분석, 일일 업데이트, 선정 기준 관리

### Phase 3: 분 단위 자동 매매 (core/intraday_trading/)
- **목표**: 당일 매매 리스트 주식들을 분 단위로 추적하며 자동 매매
- **핵심 기능**: 실시간 추적, 신호 생성, 주문 관리

### Phase 4: 학습 및 최적화 (core/learning/)
- **목표**: 일일 결과를 분석하고 학습하여 전략 개선
- **핵심 기능**: 일일 분석, 패턴 학습, 로직 최적화

### Phase 5: 시장 모니터링 (core/market_monitor/)
- **목표**: 시장 이벤트 감지 및 전략 업데이트
- **핵심 기능**: 이벤트 감지, 뉴스 분석, 시장 스캐너

## 프로젝트 구조

```
hantu_quant/
├── core/                   # 핵심 기능
│   ├── api/               # API 관련 모듈
│   ├── config/           # 설정 관련 모듈
│   ├── database/         # 데이터베이스 관련
│   ├── watchlist/        # 🆕 Phase 1: 감시 리스트 관리
│   ├── daily_selection/  # 🆕 Phase 2: 일일 매매 주식 선정
│   ├── intraday_trading/ # 🆕 Phase 3: 분 단위 트레이딩
│   ├── learning/         # 🆕 Phase 4: 학습 및 최적화
│   ├── market_monitor/   # 🆕 Phase 5: 시장 모니터링
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
├── workflows/          # 🆕 단계별 워크플로우
│   ├── phase1_watchlist.py
│   ├── phase2_daily_selection.py
│   ├── phase3_intraday_trading.py
│   ├── phase4_learning.py
│   └── phase5_monitoring.py
├── scripts/            # 실행 스크립트
├── tests/             # 테스트 코드
├── data/              # 데이터 저장소
│   ├── db/           # 데이터베이스 파일
│   ├── stock/        # 주식 데이터
│   ├── token/        # 토큰 정보
│   ├── historical/   # 과거 데이터
│   ├── watchlist/    # 🆕 감시 리스트 데이터
│   ├── daily_selection/ # 🆕 일일 선정 데이터
│   ├── intraday/     # 🆕 분 단위 데이터
│   ├── learning/     # 🆕 학습 데이터
│   └── market_events/ # 🆕 시장 이벤트 데이터
└── logs/             # 애플리케이션 로그
```

## 주요 컴포넌트

### 기존 컴포넌트
- **API 모듈**: 한국투자증권 API 연동 (core/api/kis_api.py)
- **설정 모듈**: API 설정 및 토큰 관리 (core/config/api_config.py)
- **백테스트 모듈**: 전략 백테스팅 (hantu_backtest/core)

### 새로운 컴포넌트 (단계별)

#### Phase 1 컴포넌트
- `core/watchlist/stock_screener.py`: 기업 스크리닝 로직
- `core/watchlist/watchlist_manager.py`: 감시 리스트 관리
- `core/watchlist/evaluation_engine.py`: 기업 평가 엔진

#### Phase 2 컴포넌트
- `core/daily_selection/price_analyzer.py`: 가격 매력도 분석
- `core/daily_selection/daily_updater.py`: 일일 매매 리스트 업데이트
- `core/daily_selection/selection_criteria.py`: 선정 기준 관리

#### Phase 3 컴포넌트
- `core/intraday_trading/minute_tracker.py`: 분 단위 추적
- `core/intraday_trading/signal_generator.py`: 매매 신호 생성
- `core/intraday_trading/order_manager.py`: 주문 관리

#### Phase 4 컴포넌트
- `core/learning/daily_analyzer.py`: 일일 분석
- `core/learning/pattern_learner.py`: 패턴 학습
- `core/learning/logic_optimizer.py`: 로직 최적화

#### Phase 5 컴포넌트
- `core/market_monitor/event_detector.py`: 이벤트 감지
- `core/market_monitor/news_analyzer.py`: 뉴스 분석
- `core/market_monitor/market_scanner.py`: 시장 스캐너

## 설정 요약

### 환경 설정
- `.env` 파일에 API 키 및 계정 정보 설정
- 모의투자 vs 실제투자 환경 구분 (`SERVER` 설정)

### 토큰 관리
- 모의투자: `data/token/token_info_virtual.json`
- 실제투자: `data/token/token_info_real.json`

### 데이터 관리
- 각 단계별 데이터는 `data/` 하위 전용 폴더에 저장
- JSON 형태로 구조화된 데이터 저장
- 버전 관리 및 메타데이터 포함

## 주요 기능 (기존)

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

## 새로운 기능 (단계별 구현 예정)

### Phase 1: 감시 리스트 관리 ✅ 완료
```bash
python workflows/phase1_watchlist.py screen                    # 전체 스크리닝 실행
python workflows/phase1_watchlist.py screen --stocks 005930    # 특정 종목 스크리닝
python workflows/phase1_watchlist.py list                      # 감시 리스트 조회
python workflows/phase1_watchlist.py add 005930 70000 50000    # 종목 추가
python workflows/phase1_watchlist.py remove 005930            # 종목 제거
python workflows/phase1_watchlist.py report                    # 리포트 생성
```

### Phase 2: 일일 매매 리스트
```bash
python workflows/phase2_daily_selection.py --update  # 일일 업데이트
python workflows/phase2_daily_selection.py --analyze # 가격 분석
```

### Phase 3: 분 단위 트레이딩
```bash
python workflows/phase3_intraday_trading.py --start  # 자동 매매 시작
python workflows/phase3_intraday_trading.py --stop   # 자동 매매 중지
```

### Phase 4: 학습 및 최적화
```bash
python workflows/phase4_learning.py --analyze  # 일일 분석
python workflows/phase4_learning.py --optimize # 전략 최적화
```

### Phase 5: 시장 모니터링
```bash
python workflows/phase5_monitoring.py --scan   # 시장 스캔
python workflows/phase5_monitoring.py --events # 이벤트 감지
```

## 개발 원칙

### 단계별 개발
1. 각 단계는 이전 단계 완료 후 시작
2. 모든 기능은 모의투자 환경에서 충분히 테스트
3. 단계별 완료 기준을 만족해야 다음 단계 진행

### 보안 및 안정성
- API 호출 제한 준수
- 토큰 갱신 로직 안정화
- 오류 처리 및 재시도 메커니즘
- 실시간 모니터링 및 알림

### 코드 품질
- 모든 모듈에 단위 테스트 작성
- 코드 리뷰 및 문서화
- 로깅 및 모니터링 시스템 구축

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

## 현재 상태
- ✅ 기본 인프라 구축 완료
- ✅ API 연동 및 토큰 관리 안정화
- ✅ 프로젝트 구조 재설계 완료
- 🔄 Phase 1 개발 준비 중 