# ✅ 구현 체크리스트

> 체계적인 개발 진행을 위한 상세 체크리스트

---

## Phase A: 전략 고도화 (2주)

### A-1. 앙상블 전략 시스템

#### Day 1-2: 신호 집계기
- [ ] `core/strategy/ensemble/__init__.py` 생성
- [ ] `core/strategy/ensemble/signal.py` - Signal, SignalType 정의
  - [ ] Signal 데이터클래스 (type, strength, confidence, source, metadata)
  - [ ] SignalType Enum (BUY, SELL, HOLD)
- [ ] `core/strategy/ensemble/signal_aggregator.py`
  - [ ] 가중 투표 로직
  - [ ] 최소 일치 조건 체크
  - [ ] 신뢰도 필터링
  - [ ] 최종 신호 생성
- [ ] 단위 테스트 작성

#### Day 3-4: 앙상블 엔진
- [ ] `core/strategy/ensemble/ensemble_engine.py`
  - [ ] LSTM 신호 생성기 연동
  - [ ] TA 신호 생성기 연동
  - [ ] 수급 신호 생성기 연동
  - [ ] 신호 통합 로직
- [ ] `core/strategy/ensemble/ta_scorer.py`
  - [ ] RSI 점수 계산 (-100 ~ +100)
  - [ ] MACD 점수 계산
  - [ ] 볼린저밴드 점수 계산
  - [ ] 이동평균 점수 계산
  - [ ] 종합 TA 점수 산출
- [ ] 통합 테스트

#### Day 5: 가중치 최적화
- [ ] `core/strategy/ensemble/weight_optimizer.py`
  - [ ] 성과 기반 가중치 조정
  - [ ] 최소/최대 가중치 제한
  - [ ] 급격한 변화 방지 (±10%)
  - [ ] 정규화 로직
- [ ] 백테스트 검증
  - [ ] 단일 전략 대비 성과 비교
  - [ ] 승률 개선 확인 (목표: +5%p)

### A-2. 멀티타임프레임 분석

#### Day 6-7: MTF 분석기
- [ ] `core/strategy/timeframe/__init__.py`
- [ ] `core/strategy/timeframe/mtf_analyzer.py`
  - [ ] 월봉 분석 (대세 판단)
  - [ ] 주봉 분석 (중기 추세)
  - [ ] 일봉 분석 (진입 타이밍)
  - [ ] 추세 정렬도 계산 (0~1)
- [ ] `core/strategy/timeframe/trend_aligner.py`
  - [ ] 추세 방향 판단 (BULL/BEAR/NEUTRAL)
  - [ ] 추세 강도 계산
  - [ ] 정렬 점수 산출

#### Day 8: 진입 최적화
- [ ] `core/strategy/timeframe/entry_optimizer.py`
  - [ ] 지지선 접근도 점수
  - [ ] 캔들 패턴 점수
  - [ ] 거래량 확인 점수
  - [ ] 최적 진입 가격 계산
  - [ ] 손절/익절 레벨 계산
- [ ] 백테스트 검증
  - [ ] MTF 정렬 시 vs 비정렬 시 승률 비교

### A-3. 섹터 로테이션

#### Day 9-10: 섹터 분석
- [ ] `core/strategy/sector/__init__.py`
- [ ] `core/strategy/sector/sector_map.py`
  - [ ] 한국 시장 섹터 분류 정의
  - [ ] 종목-섹터 매핑
- [ ] `core/strategy/sector/sector_analyzer.py`
  - [ ] 섹터별 수익률 계산 (1M, 3M)
  - [ ] 섹터 RSI 계산
  - [ ] 거래량 추세 분석
  - [ ] 섹터 모멘텀 점수

#### Day 11-12: 로테이션 엔진
- [ ] `core/strategy/sector/rotation_engine.py`
  - [ ] 섹터 랭킹 생성
  - [ ] 자금 배분 로직
  - [ ] 섹터 전환 감지
- [ ] `core/strategy/sector/transition_detector.py`
  - [ ] 급격한 순위 변동 감지
  - [ ] 전환 신호 생성
- [ ] 백테스트 검증

---

## Phase B: 리스크 관리 (2주)

### B-1. 켈리 포지션 사이징

#### Day 1-2: 켈리 계산기
- [ ] `core/risk/position/__init__.py`
- [ ] `core/risk/position/kelly_calculator.py`
  - [ ] 기본 켈리 공식 구현
  - [ ] 불확실성 조정 (신뢰구간)
  - [ ] Half Kelly / Quarter Kelly
  - [ ] 최대/최소 포지션 제한
- [ ] `core/risk/position/position_sizer.py`
  - [ ] 통합 포지션 사이징 인터페이스
  - [ ] 신호 강도 반영
  - [ ] 변동성 조정
- [ ] 단위 테스트

### B-2. 상관관계 분석

#### Day 3-4: 상관관계 매트릭스
- [ ] `core/risk/correlation/__init__.py`
- [ ] `core/risk/correlation/correlation_matrix.py`
  - [ ] 롤링 상관계수 계산 (60일)
  - [ ] 고상관 종목 쌍 식별
  - [ ] 평균 상관계수 산출
- [ ] `core/risk/correlation/diversification_score.py`
  - [ ] 분산투자 점수 계산
  - [ ] 섹터 집중도 체크
  - [ ] 개선 권고 생성

#### Day 5-6: 포트폴리오 최적화
- [ ] `core/risk/correlation/portfolio_optimizer.py`
  - [ ] 최소분산 포트폴리오 계산
  - [ ] 상관관계 제약 적용
  - [ ] 최적 비중 산출
- [ ] 통합 테스트

### B-3. 드로다운 관리

#### Day 7-8: 드로다운 모니터
- [ ] `core/risk/drawdown/__init__.py`
- [ ] `core/risk/drawdown/drawdown_monitor.py`
  - [ ] 일간/주간/월간 드로다운 추적
  - [ ] 고점 대비 낙폭 계산
  - [ ] 한도 초과 감지
  - [ ] 액션 결정

#### Day 9: 서킷브레이커
- [ ] `core/risk/drawdown/circuit_breaker.py`
  - [ ] 트리거 조건 정의
  - [ ] 자동 발동 로직
  - [ ] 쿨다운 기간 관리
  - [ ] 강제 해제 기능

#### Day 10: 포지션 축소
- [ ] `core/risk/drawdown/position_reducer.py`
  - [ ] 최악 성과 종목 우선 청산
  - [ ] 고상관 종목 우선 축소
  - [ ] 비례 축소
  - [ ] 청산 주문 생성
- [ ] 통합 테스트

---

## Phase C: 학습 시스템 (2주)

### C-1. 거래 학습

#### Day 1-2: 거래 로거
- [ ] `core/learning/__init__.py`
- [ ] `core/learning/trade_logger.py`
  - [ ] 거래 상세 로그 구조 정의
  - [ ] 진입/청산 시점 상태 기록
  - [ ] 시장 상황 기록
  - [ ] 결과 레이블링

#### Day 3-4: 성과 분석
- [ ] `core/learning/performance_analyzer.py`
  - [ ] 승리 조건 분석
  - [ ] 패배 조건 분석
  - [ ] 지표별 최적 범위 탐색
  - [ ] 시장 상황별 성과 분석

#### Day 5: 실패 분석
- [ ] `core/learning/failure_analyzer.py`
  - [ ] 실패 유형 분류
  - [ ] 공통 실수 패턴 식별
  - [ ] 개선점 도출
  - [ ] 필터 규칙 생성

### C-2. 모델 학습

#### Day 6-7: LSTM 재학습
- [ ] `core/learning/lstm_learner.py`
  - [ ] 재학습 조건 판단
  - [ ] 데이터 준비 파이프라인
  - [ ] 피처 생성
  - [ ] 모델 학습/검증
  - [ ] 모델 교체 로직

#### Day 8-9: 가중치 학습
- [ ] `core/learning/weight_learner.py`
  - [ ] 전략별 성과 평가
  - [ ] 점수 기반 가중치 계산
  - [ ] 레짐별 최적 가중치 탐색
  - [ ] 베이지안 최적화

#### Day 10: 파라미터 최적화
- [ ] `core/learning/param_optimizer.py`
  - [ ] 그리드 서치
  - [ ] 워크포워드 테스트
  - [ ] 최적 파라미터 저장
- [ ] 통합 테스트

### C-3. 시장 적응

#### Day 11-12: 레짐 학습
- [ ] `core/learning/regime_learner.py`
  - [ ] 레짐 분류기 학습
  - [ ] 레짐 레이블 업데이트
  - [ ] 피처 중요도 분석

#### Day 13-14: 전략 선택
- [ ] `core/learning/strategy_selector.py`
  - [ ] 레짐-전략 매핑 학습
  - [ ] 전략 전환 타이밍 학습
  - [ ] 최적 전략 선택 로직

---

## Phase D: 알림 & 자동화 (1주)

### D-1. 텔레그램 알림

#### Day 1-2: 봇 구현
- [ ] `core/notification/__init__.py`
- [ ] `core/notification/telegram_bot.py`
  - [ ] 봇 초기화
  - [ ] 메시지 전송 함수
  - [ ] 메시지 포맷터
  - [ ] 이미지/차트 전송

#### Day 3: 알림 관리자
- [ ] `core/notification/alert_manager.py`
  - [ ] 알림 유형 정의
  - [ ] 알림 우선순위
  - [ ] 중복 알림 방지
  - [ ] 알림 이력 관리

### D-2. 스케줄러

#### Day 4-5: 작업 스케줄러
- [ ] `core/scheduler/__init__.py`
- [ ] `core/scheduler/job_scheduler.py`
  - [ ] 일간 작업 스케줄
  - [ ] 주간 작업 스케줄
  - [ ] 월간 작업 스케줄
  - [ ] 작업 실행 로직
- [ ] `core/scheduler/market_calendar.py`
  - [ ] 휴장일 체크
  - [ ] 거래 시간 체크

---

## Phase E: 페이퍼 트레이딩 (1주)

### E-1. 페이퍼 엔진

#### Day 1-3: 가상 브로커
- [ ] `core/paper_trading/__init__.py`
- [ ] `core/paper_trading/virtual_broker.py`
  - [ ] 가상 주문 처리
  - [ ] 체결 시뮬레이션
  - [ ] 슬리피지 적용
- [ ] `core/paper_trading/paper_portfolio.py`
  - [ ] 가상 포지션 관리
  - [ ] 실시간 손익 추적

#### Day 4-5: 페이퍼 엔진
- [ ] `core/paper_trading/paper_engine.py`
  - [ ] 실시간 시세 연동
  - [ ] 신호 처리
  - [ ] 주문 실행
  - [ ] 일일 리포트

---

## Phase F: 검증 & 최적화 (1주)

### F-1. 종합 검증

#### Day 1-2: 워크포워드 분석
- [ ] `core/validation/__init__.py`
- [ ] `core/validation/walk_forward.py`
  - [ ] 롤링 윈도우 최적화
  - [ ] Out-of-sample 테스트
  - [ ] 성과 안정성 분석

#### Day 3-4: 강건성 테스트
- [ ] `core/validation/robustness_test.py`
  - [ ] 파라미터 민감도 분석
  - [ ] 몬테카를로 시뮬레이션
  - [ ] 스트레스 테스트

### F-2. 통합 테스트

#### Day 5-7: 전체 시스템 테스트
- [ ] 전략 → 신호 → 리스크 → 실행 파이프라인 테스트
- [ ] 학습 → 적응 → 개선 사이클 테스트
- [ ] 알림 → 모니터링 테스트
- [ ] 페이퍼 트레이딩 2주 검증 시작

---

## 최종 검증 체크리스트

### 백테스트 기준
- [ ] 연환산 수익률 > 15%
- [ ] 최대 낙폭 (MDD) < 15%
- [ ] 샤프 비율 > 1.5
- [ ] 승률 > 50%
- [ ] 손익비 > 1.5

### 시스템 안정성
- [ ] 모든 단위 테스트 통과
- [ ] 통합 테스트 통과
- [ ] 에러 핸들링 완료
- [ ] 로깅 시스템 작동
- [ ] 알림 시스템 작동

### 문서화
- [ ] API 문서
- [ ] 사용자 가이드
- [ ] 운영 매뉴얼
- [ ] 트러블슈팅 가이드

---

## 일일 개발 루틴

```
09:00 - 어제 작업 리뷰
09:30 - 오늘 작업 계획
10:00 - 핵심 개발
12:00 - 점심
13:00 - 테스트 작성 & 실행
15:00 - 코드 리뷰 & 리팩토링
16:00 - 문서화
17:00 - 다음날 준비
```

---

*마지막 업데이트: 2024-12-27*
