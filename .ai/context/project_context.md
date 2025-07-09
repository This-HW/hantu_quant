# 한투 퀀트 프로젝트 컨텍스트

## 프로젝트 개요
한국투자증권 API를 활용한 단계별 자동매매 시스템 구축 프로젝트입니다.
5단계 개발 방식으로 점진적이고 안정적인 시스템을 구축합니다.

## 핵심 참조 파일
- PROJECT_SUMMARY.md: 프로젝트 구조와 기능 요약
- ROADMAP.md: 개발 계획 및 로드맵
- README.md: 주요 기능 및 사용 방법
- STATUS_REPORT.md: 현재 진행 상황 요약
- .cursor/rules/project_phases.md: 단계별 개발 규칙
- .cursor/rules/development_guidelines.md: 개발 가이드라인

## 단계별 개발 계획

### Phase 1: 감시 리스트 구축 (core/watchlist/) - 현재 진행 중
**목표**: 좋은 기업을 찾아서 매매 희망 리스트 혹은 감시 리스트에 추가하기
**핵심 모듈**: stock_screener.py, watchlist_manager.py, evaluation_engine.py

### Phase 2: 일일 매매 주식 선정 (core/daily_selection/)
**목표**: 매일 감시 리스트에서 가격이 매력적인 주식을 당일 매매 리스트에 업데이트
**핵심 모듈**: price_analyzer.py, daily_updater.py, selection_criteria.py

### Phase 3: 분 단위 자동 매매 (core/intraday_trading/)
**목표**: 당일 매매 리스트 주식들을 분 단위로 추적하며 자동 매매
**핵심 모듈**: minute_tracker.py, signal_generator.py, order_manager.py

### Phase 4: 학습 및 최적화 (core/learning/)
**목표**: 일일 결과를 분석하고 학습하여 전략 개선
**핵심 모듈**: daily_analyzer.py, pattern_learner.py, logic_optimizer.py

### Phase 5: 시장 모니터링 (core/market_monitor/)
**목표**: 시장 이벤트 감지 및 전략 업데이트
**핵심 모듈**: event_detector.py, news_analyzer.py, market_scanner.py

## 주요 디렉토리 구조
```
core/
├── api/                  # API 관련 모듈
├── config/              # 설정 관련 모듈
├── watchlist/           # Phase 1: 감시 리스트 관리
├── daily_selection/     # Phase 2: 일일 매매 주식 선정
├── intraday_trading/    # Phase 3: 분 단위 트레이딩
├── learning/            # Phase 4: 학습 및 최적화
├── market_monitor/      # Phase 5: 시장 모니터링
├── realtime/           # 실시간 처리
├── strategy/           # 전략 구현
├── trading/            # 트레이딩 모듈
└── utils/              # 유틸리티

data/
├── watchlist/          # 감시 리스트 데이터
├── daily_selection/    # 일일 선정 데이터
├── intraday/          # 분 단위 데이터
├── learning/          # 학습 데이터
├── market_events/     # 시장 이벤트 데이터
├── stock/             # 주식 데이터
├── token/             # 토큰 정보
└── historical/        # 과거 데이터

workflows/              # 단계별 워크플로우
├── phase1_watchlist.py
├── phase2_daily_selection.py
├── phase3_intraday_trading.py
├── phase4_learning.py
└── phase5_monitoring.py
```

## 설정 관련 파일
- .env.example: 환경 변수 예시 (실제 값은 .env에 설정)
- core/config/settings.py: 기본 설정
- core/config/api_config.py: API 설정

## 보안 주의사항
- API 키와 민감정보는 항상 .env 파일에만 저장
- 토큰 파일은 data/token/ 디렉토리에 저장되며 git에 포함되지 않음
- 로깅 시 민감 정보 마스킹 필수
- 파라미터 변수에는 'p_' 접두사, 내부 변수에는 '_v_' 접두사 사용

## 개발 원칙

### 단계별 개발 규칙
1. 각 단계는 이전 단계가 완료된 후 시작
2. 모든 기능은 모의투자 환경에서 충분히 테스트
3. 단계별 완료 기준을 만족해야 다음 단계 진행
4. 코드 변경 시 관련 문서 업데이트

### 코딩 표준
- 모든 클래스와 함수에 docstring 필수
- 타입 힌트 사용 권장
- 로깅을 통한 디버깅 정보 제공
- 예외 처리 필수
- core.utils.log_utils.get_logger 사용

### 데이터 관리
- 각 단계별 데이터는 해당 data/ 하위 폴더에 저장
- JSON 형태로 구조화된 데이터 저장
- 버전 관리 및 메타데이터 포함
- 민감 정보는 절대 하드코딩 금지

### 테스트 전략
- 각 모듈별 단위 테스트 작성
- 통합 테스트를 통한 단계별 검증
- 모의투자 환경에서 충분한 테스트 후 실제 적용

## 프로젝트 현황
- ✅ 기본 인프라 구축 완료
- ✅ API 연동 및 토큰 관리 안정화
- ✅ 프로젝트 구조 재설계 완료
- ✅ 개발 가이드라인 수립
- 🔄 Phase 1 개발 준비 중

## 현재 우선 작업 순위
1. Phase 1: 감시 리스트 구축
   - 기업 스크리닝 로직 구현
   - 감시 리스트 관리 시스템 구축
   - 기업 평가 엔진 개발

2. Phase 2: 일일 매매 주식 선정
   - 가격 매력도 분석 시스템
   - 일일 업데이트 스케줄러
   - 선정 기준 관리

3. Phase 3: 분 단위 자동 매매
   - 실시간 데이터 처리
   - 매매 신호 생성
   - 자동 주문 실행

## 필수 확인사항
- 모든 작업은 모의투자 환경에서 테스트
- API 호출 제한 준수
- 리스크 관리 로직 필수 구현
- 정기적인 성과 검토 및 전략 조정

## AI 협업 지침
1. 작업 시작 시 해당 Phase의 .cursor/rules/ 파일 확인
2. 단계별 완료 기준 준수
3. 코딩 표준 및 네이밍 규칙 적용
4. 모든 변경사항은 관련 문서에 반영
5. 테스트 코드 작성 필수 