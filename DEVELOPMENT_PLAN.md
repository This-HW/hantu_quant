# 🎯 Hantu Quant 자동매매 시스템 개발 계획

> **목표**: 체계적인 퀀트 트레이딩 시스템으로 안정적인 수익 창출
> **기간**: 8주 (Phase별 2주)
> **원칙**: 실거래 전 충분한 검증, 리스크 관리 최우선

---

## 📊 현재 구현 상태

| 모듈 | 상태 | 위치 |
|------|------|------|
| Phase 1/2 스크리닝 | ✅ 완료 | `workflows/` |
| LSTM 예측 | ✅ 완료 | `core/learning/models/` |
| 기술적 지표 (13종) | ✅ 완료 | `hantu_common/indicators/` |
| ATR 동적 손절 | ✅ 완료 | `core/trading/dynamic_stop_loss.py` |
| 백테스트 엔진 | ✅ 완료 | `core/backtest/` |
| API 서버 | ✅ 완료 | `api-server/` |

---

## 🚀 개발 로드맵

### Phase A: 전략 고도화 (우선순위: 최상) - 2주

수익을 내기 위한 핵심 전략 개선. 백테스트로 검증 가능한 전략부터 구현.

#### A-1. 앙상블 전략 시스템 ⭐⭐⭐
```
core/strategy/ensemble/
├── __init__.py
├── ensemble_engine.py      # 앙상블 엔진
├── signal_aggregator.py    # 신호 집계기
├── weight_optimizer.py     # 가중치 최적화
└── confidence_scorer.py    # 신뢰도 점수
```

**구현 내용:**
- [ ] LSTM + 기술적분석 + 수급 신호 결합
- [ ] 신호 일치도 기반 진입 (3개 이상 일치시)
- [ ] 동적 가중치 조정 (최근 성과 기반)
- [ ] 신뢰도 점수 산출 (0~100)

**검증 기준:**
- 단일 전략 대비 승률 5%p 이상 향상
- MDD 20% 이내 유지

#### A-2. 멀티타임프레임 분석 ⭐⭐⭐
```
core/strategy/timeframe/
├── __init__.py
├── mtf_analyzer.py         # 멀티타임프레임 분석기
├── trend_aligner.py        # 추세 정렬 확인
└── entry_optimizer.py      # 진입점 최적화
```

**구현 내용:**
- [ ] 일봉/주봉/월봉 동시 분석
- [ ] 상위 타임프레임 추세 확인 후 하위에서 진입
- [ ] 타임프레임별 가중치 설정
- [ ] 추세 정렬도 점수화

**전략 로직:**
```
월봉: 대세 상승/하락 판단 (장기 추세)
주봉: 중기 추세 및 지지/저항 확인
일봉: 실제 진입/청산 타이밍
```

#### A-3. 섹터 로테이션 전략 ⭐⭐
```
core/strategy/sector/
├── __init__.py
├── sector_analyzer.py      # 섹터 분석기
├── rotation_engine.py      # 로테이션 엔진
├── momentum_ranker.py      # 모멘텀 순위
└── sector_map.py           # 섹터 매핑 정보
```

**구현 내용:**
- [ ] 섹터별 상대강도 계산
- [ ] 상위 3개 섹터 집중 투자
- [ ] 하위 섹터 회피 로직
- [ ] 섹터 모멘텀 점수 (RSI, 수익률 기반)

---

### Phase B: 리스크 관리 강화 (우선순위: 최상) - 2주

돈을 잃지 않는 것이 돈을 버는 것보다 중요.

#### B-1. 켈리 공식 포지션 사이징 ⭐⭐⭐
```
core/risk/position/
├── __init__.py
├── kelly_calculator.py     # 켈리 공식 계산기
├── fractional_kelly.py     # 분수 켈리 (보수적)
└── position_sizer.py       # 통합 포지션 사이저
```

**구현 내용:**
- [ ] 켈리 공식: f* = (bp - q) / b
- [ ] Half-Kelly 적용 (과다투자 방지)
- [ ] 최대 포지션 제한 (자본의 10%)
- [ ] 승률/손익비 기반 동적 조정

**공식:**
```python
kelly_fraction = (win_rate * avg_win - (1 - win_rate) * avg_loss) / avg_win
safe_kelly = kelly_fraction * 0.5  # Half Kelly
position_size = min(safe_kelly, 0.10)  # 최대 10%
```

#### B-2. 상관관계 기반 분산투자 ⭐⭐⭐
```
core/risk/correlation/
├── __init__.py
├── correlation_matrix.py   # 상관관계 행렬
├── diversification_score.py # 분산 점수
└── portfolio_optimizer.py  # 포트폴리오 최적화
```

**구현 내용:**
- [ ] 종목간 상관계수 계산 (rolling 60일)
- [ ] 상관계수 0.7 이상 종목 동시 보유 제한
- [ ] 분산투자 점수 산출
- [ ] 최소분산 포트폴리오 구성

#### B-3. 드로다운 관리 시스템 ⭐⭐⭐
```
core/risk/drawdown/
├── __init__.py
├── drawdown_monitor.py     # 낙폭 모니터링
├── position_reducer.py     # 포지션 축소기
└── circuit_breaker.py      # 서킷브레이커
```

**구현 내용:**
- [ ] 실시간 드로다운 추적
- [ ] 단계별 포지션 축소 규칙:
  - DD 5%: 신규 진입 중단
  - DD 10%: 포지션 50% 축소
  - DD 15%: 전량 청산, 거래 중단
- [ ] 일일/주간 손실 한도 설정
- [ ] 연속 손실 시 쿨다운 기간

---

### Phase C: 데이터 & 인프라 (우선순위: 상) - 1주

안정적인 데이터 파이프라인과 모니터링 시스템.

#### C-1. 데이터 파이프라인 강화
```
core/data/
├── __init__.py
├── data_pipeline.py        # 데이터 파이프라인
├── data_validator.py       # 데이터 검증
├── cache_manager.py        # 캐시 관리
└── data_sync.py            # 데이터 동기화
```

**구현 내용:**
- [ ] 일별 OHLCV 자동 수집 (장 마감 후)
- [ ] 데이터 품질 검증 (결측치, 이상치)
- [ ] Redis/SQLite 캐싱
- [ ] 과거 데이터 백필

#### C-2. 실시간 모니터링 대시보드
```
core/monitoring/
├── __init__.py
├── dashboard.py            # 대시보드
├── metrics_collector.py    # 지표 수집
└── health_checker.py       # 상태 체크
```

**구현 내용:**
- [ ] 포트폴리오 현황 실시간 표시
- [ ] 전략별 성과 모니터링
- [ ] 시스템 상태 체크
- [ ] 웹 기반 대시보드 (Streamlit/Gradio)

---

### Phase D: 알림 & 자동화 (우선순위: 상) - 1주

실시간 알림으로 중요 이벤트 즉시 파악.

#### D-1. 텔레그램 알림 시스템 ⭐⭐
```
core/notification/
├── __init__.py
├── telegram_bot.py         # 텔레그램 봇
├── slack_webhook.py        # 슬랙 웹훅
├── alert_manager.py        # 알림 관리자
└── message_formatter.py    # 메시지 포맷터
```

**알림 유형:**
- [ ] 매수/매도 신호 발생
- [ ] 포지션 진입/청산 완료
- [ ] 손절/익절 도달
- [ ] 일일 수익 보고서
- [ ] 시스템 오류/경고

**메시지 예시:**
```
🟢 매수 신호
종목: 삼성전자 (005930)
가격: 71,500원
신뢰도: 85%
전략: 앙상블 (LSTM+RSI+거래량)
손절가: 69,400원 (-2.9%)
목표가: 77,800원 (+8.8%)
```

#### D-2. 스케줄러 & 자동 실행
```
core/scheduler/
├── __init__.py
├── job_scheduler.py        # 작업 스케줄러
├── market_calendar.py      # 시장 캘린더
└── task_runner.py          # 태스크 실행기
```

**스케줄:**
```
08:30 - 장 전 분석 (종목 스크리닝)
09:00 - 장 시작 모니터링
15:20 - 장 마감 전 정리
15:40 - 일일 리포트 생성
18:00 - 데이터 업데이트
```

---

### Phase E: 종이거래 시스템 (우선순위: 상) - 1주

실거래 전 필수 검증 단계.

#### E-1. 페이퍼 트레이딩 엔진
```
core/paper_trading/
├── __init__.py
├── paper_engine.py         # 페이퍼 트레이딩 엔진
├── virtual_broker.py       # 가상 브로커
├── order_simulator.py      # 주문 시뮬레이터
├── slippage_model.py       # 슬리피지 모델
└── paper_portfolio.py      # 가상 포트폴리오
```

**구현 내용:**
- [ ] 실시간 시세로 가상 거래
- [ ] 실제 슬리피지/수수료 반영
- [ ] 체결 지연 시뮬레이션
- [ ] 일일/주간 성과 리포트

**검증 기준 (2주간):**
- 총 수익률 > 0%
- MDD < 10%
- 승률 > 50%
- 샤프비율 > 1.0

---

### Phase F: 고급 기능 (우선순위: 중) - 1주

수익 극대화를 위한 추가 기능.

#### F-1. 마켓 레짐 감지
```
core/market/
├── __init__.py
├── regime_detector.py      # 레짐 감지기
├── volatility_regime.py    # 변동성 레짐
└── trend_regime.py         # 추세 레짐
```

**레짐 분류:**
- 강세장 (Bull): 공격적 전략
- 약세장 (Bear): 방어적 전략
- 횡보장 (Range): 평균회귀 전략
- 고변동성: 포지션 축소

#### F-2. 실행 알고리즘
```
core/execution/
├── __init__.py
├── twap.py                 # 시간가중평균가격
├── vwap.py                 # 거래량가중평균가격
└── smart_router.py         # 스마트 라우팅
```

**구현 내용:**
- [ ] TWAP: 시간 분할 주문
- [ ] VWAP: 거래량 기반 분할
- [ ] 시장충격 최소화

#### F-3. Walk-Forward 분석
```
core/validation/
├── __init__.py
├── walk_forward.py         # 워크포워드 분석
├── cross_validator.py      # 교차 검증
└── robustness_test.py      # 강건성 테스트
```

**구현 내용:**
- [ ] 롤링 윈도우 최적화
- [ ] Out-of-sample 테스트
- [ ] 과최적화 방지

---

## 📅 주간 개발 일정

### Week 1-2: Phase A (전략 고도화)
| 일차 | 작업 | 산출물 |
|------|------|--------|
| 1-2 | 앙상블 전략 설계 & 구현 | `ensemble_engine.py` |
| 3 | 신호 집계 & 가중치 | `signal_aggregator.py` |
| 4-5 | 멀티타임프레임 분석 | `mtf_analyzer.py` |
| 6-7 | 섹터 로테이션 | `sector_analyzer.py` |
| 8-10 | 백테스트 검증 & 튜닝 | 성과 리포트 |

### Week 3-4: Phase B (리스크 관리)
| 일차 | 작업 | 산출물 |
|------|------|--------|
| 1-2 | 켈리 공식 구현 | `kelly_calculator.py` |
| 3-4 | 상관관계 분석 | `correlation_matrix.py` |
| 5-6 | 드로다운 관리 | `drawdown_monitor.py` |
| 7-8 | 서킷브레이커 | `circuit_breaker.py` |
| 9-10 | 통합 테스트 | 리스크 대시보드 |

### Week 5: Phase C+D (인프라 & 알림)
| 일차 | 작업 | 산출물 |
|------|------|--------|
| 1-2 | 데이터 파이프라인 | `data_pipeline.py` |
| 3 | 텔레그램 봇 | `telegram_bot.py` |
| 4 | 스케줄러 | `job_scheduler.py` |
| 5 | 모니터링 대시보드 | `dashboard.py` |

### Week 6: Phase E (종이거래)
| 일차 | 작업 | 산출물 |
|------|------|--------|
| 1-2 | 페이퍼 트레이딩 엔진 | `paper_engine.py` |
| 3 | 가상 브로커 | `virtual_broker.py` |
| 4-5 | 2주 검증 시작 | 일일 리포트 |

### Week 7-8: Phase F + 검증
| 일차 | 작업 | 산출물 |
|------|------|--------|
| 1-3 | 마켓 레짐 감지 | `regime_detector.py` |
| 4-5 | 실행 알고리즘 | `twap.py`, `vwap.py` |
| 6-10 | 종합 검증 & 최적화 | 최종 리포트 |

---

## ✅ 실거래 전 체크리스트

### 필수 조건
- [ ] 백테스트 연환산 수익률 > 15%
- [ ] 백테스트 MDD < 15%
- [ ] 백테스트 샤프비율 > 1.5
- [ ] 페이퍼 트레이딩 2주 이상 양수 수익
- [ ] 페이퍼 vs 백테스트 괴리율 < 30%

### 시스템 안정성
- [ ] 알림 시스템 정상 작동
- [ ] 데이터 파이프라인 안정성 확인
- [ ] 서킷브레이커 테스트 완료
- [ ] 비상 청산 기능 테스트

### 리스크 설정
- [ ] 일일 손실 한도 설정 (2%)
- [ ] 주간 손실 한도 설정 (5%)
- [ ] 최대 포지션 수 설정 (5~10개)
- [ ] 단일 종목 한도 설정 (10%)

---

## 📈 목표 성과 지표

| 지표 | 최소 목표 | 이상적 목표 |
|------|----------|------------|
| 연환산 수익률 | 15% | 25%+ |
| 최대 낙폭 (MDD) | < 15% | < 10% |
| 샤프 비율 | > 1.5 | > 2.0 |
| 소르티노 비율 | > 2.0 | > 2.5 |
| 승률 | > 50% | > 60% |
| 손익비 | > 1.5 | > 2.0 |
| 월간 승률 | > 60% | > 75% |

---

## 🔧 기술 스택

| 영역 | 기술 |
|------|------|
| 언어 | Python 3.11+ |
| 데이터 | Pandas, NumPy |
| ML | PyTorch, Scikit-learn |
| 백테스트 | 자체 엔진 (core/backtest) |
| API | FastAPI |
| DB | SQLite, Redis |
| 알림 | Telegram Bot API |
| 시각화 | Matplotlib, Plotly |
| 스케줄링 | APScheduler |

---

## 📝 개발 원칙

1. **테스트 우선**: 모든 전략은 백테스트로 검증
2. **점진적 확장**: 작은 자본으로 시작, 검증 후 확대
3. **리스크 최우선**: 수익보다 손실 관리가 중요
4. **단순함 유지**: 복잡한 전략보다 검증된 단순 전략
5. **기록 철저**: 모든 거래와 의사결정 로깅

---

*마지막 업데이트: 2024-12-27*
