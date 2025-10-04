# 알고리즘 개요 (Phase1/Phase2/Trading/Sell)

본 문서는 현재 시스템 각 단계(스크리닝/일일선정/매매/피드백)에서 적용 중인 핵심 알고리즘과 데이터 흐름을 요약합니다.

## Phase 1 · 스크리닝(감시리스트)

- 입력: 전체 종목 기본정보/지표(내부 스코어 집계 결과)
- 통과 기준 (완화 정책 반영)
  - 펀더멘털/테크니컬/모멘텀 중 2/3 ≥ 45.0
  - 총점 ≥ 60.0
- 산출: 통과 종목 리스트(섹터 포함), watchlist.json 동기화
- 텔레그램: “스크리닝 완료” 단일 소스 메시지 전송
- 파티션 저장: `data/watchlist/screening_YYYYMMDD.json`
- 이력: `data/watchlist/history.json`(종목별 선정 일수/날짜)

## Phase 2 · 일일 선정(매매 리스트)

- 입력: 당일 파티션(`screening_YYYYMMDD.json`)에 포함된 종목만 후보로 사용
- 분석: `PriceAnalyzer`가 가격매력도, 거래량, 패턴 점수 산출
- 필터/선정:
  - 가격매력도/리스크/신뢰도/유동성 필터
  - 섹터별 상한(`sector_limit`)
  - 총량 제한 없음(`total_limit=0`)
- 산출: `data/daily_selection/daily_selection_YYYYMMDD.json`(+ latest_selection.json)
- 텔레그램: “일일 업데이트 완료” 메시지 전송

## Trading · 매수/매도 로직

- 매수
  - 사전 가드: 상대스프레드 ≤ 임계, 업틱비율 ≥ 임계, VWAP 괴리 ≤ 임계
  - 시그널: 모멘텀/체결/호가 특성 반영(확장 중)
- 매도(SellEngine)
  - 손절: 고정 손절
  - 이익실현: 목표가 도달 시 부분청산(동적 비율)
  - 트레일링: ATR 기반 추적 손절
  - 기술적: RSI 과매수, MACD 약세, 볼린저 이탈/반전
  - 시장상황: 호가 불균형/수급(투자자/회원사) 반영 프레임워크
  - TradeJournal 연계: 시그널/주문 기록 → 일일 요약 → 피드백

## Feedback · 성과/학습

- 마감(16:00): TradeJournal 일일 요약 → DailyPerformanceAnalyzer.ingest_trade_summary
- 라벨링(신규): DailyPerformanceAnalyzer
  - 스크리닝일 기준: 1/7/14/30/60/90/120/365일 수익률 라벨
  - 일일선정일 기준: 0/1/2/3/7/14일 수익률 라벨
  - 구현: pykrx 종가 조회로 미래 시점 종가 대비 수익률 계산

## 스케줄링

- 월~금: 06:00 스크리닝 → 성공 시 즉시 일일선정
- 월~금: 16:00 마감/요약 반영
- 토/일: 비실행

## 데이터 표준 경로

- 스크리닝 파티션: `data/watchlist/screening_YYYYMMDD.json`
- 감시리스트 이력: `data/watchlist/history.json`
- 일일선정: `data/daily_selection/daily_selection_YYYYMMDD.json`
- 학습 라벨: `data/learning/labels/*.json`

