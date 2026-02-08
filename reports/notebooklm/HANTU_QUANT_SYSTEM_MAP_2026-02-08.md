# hantu_quant System Map (NotebookLM Import)

작성일: 2026-02-08
목적: NotebookLM에서 프로젝트 구조/실행 흐름/핵심 모듈을 빠르게 이해하기 위한 코드 맵

## 1) End-to-End 실행 흐름

1. Phase 1 스크리닝
- 엔트리: `workflows/phase1_watchlist.py`
- 핵심: `core/watchlist/stock_screener.py`, `core/watchlist/evaluation_engine.py`, `core/watchlist/watchlist_manager.py`
- 출력: `data/watchlist/screening_YYYYMMDD.json`, `data/watchlist/watchlist.json`

2. Phase 2 일일 선정
- 엔트리: `workflows/phase2_daily_selection.py`
- 핵심: `core/daily_selection/daily_updater.py`, `core/daily_selection/price_analyzer.py`, `core/daily_selection/selection_criteria.py`
- 출력: `data/daily_selection/daily_selection_YYYYMMDD.json`, `data/daily_selection/latest_selection.json`

3. 자동 매매/트레이딩
- 엔트리: `scripts/auto_trading.py`
- 핵심: `core/trading/trading_engine.py`, `core/trading/sell_engine.py`, `core/trading/validators.py`
- 리스크: `core/risk/position/position_sizer.py`, `core/risk/position/kelly_calculator.py`, `core/risk/drawdown/circuit_breaker.py`

4. 성과/학습
- 핵심: `core/learning/analysis/*`, `core/learning/models/*`, `core/learning/optimization/*`, `core/learning/backtest/*`
- 라벨/성과 반영: `core/learning/analysis/daily_performance.py`, `core/learning/trade_logger.py`

5. 통합 스케줄링/운영
- 엔트리: `workflows/integrated_scheduler.py`
- 스케줄러 패키지: `workflows/scheduler/*`
- 서비스 스크립트: `scripts/deployment/*`, `deploy/*.service`

## 2) 운영 인터페이스

- CLI: `cli/main.py`, `cli/commands/*`
- API 서버: `api-server/main.py`, `api-server/main_real_data.py`
- 웹 UI: `web-interface/src/*`

## 3) 데이터/상태 저장

- 워크플로우 결과: `workflows/data/*`, `data/watchlist/*`, `data/daily_selection/*`
- 학습 데이터: `data/learning/*`
- 리포트: `reports/*`, `docs/reports/*`
- 설정: `config/*.yaml`, `config/*.json`, `.env`

## 4) 테스트 체계

- 단위/통합: `tests/unit/*`, `tests/integration/*`
- 보안/배포 스크립트 테스트: `tests/security/*`, `tests/deployment/*`
- 백테스트/리스크/학습: `tests/backtest/*`, `tests/risk/*`, `tests/learning/*`

## 5) 핵심 설계 포인트

- 모듈화: `core/interfaces/*`, `core/plugins/*`, `core/di/*`
- 신뢰성: `core/resilience/*`, `core/monitoring/*`
- 이벤트 기반: `core/events/*`
- 확장성: 플러그인/레지스트리/패키지 시스템 (`core/registry/*`, `core/packages/*`)

## 6) 현재 문서/코드 간 해석 주의

- 문서상 "완료" 상태와 실제 코드 세부 구현은 시점 차이가 있을 수 있음
- 수익성/백테스트 관련 최신 판단은 아래 문서를 우선 참조
  - `docs/analysis/profitability-analysis-2026-02-08.md`
  - `docs/analysis/profitability-improvement-roadmap.md`

