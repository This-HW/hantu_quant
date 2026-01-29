# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased] - 2026-01-30

### Added

- **Phase 2 실제 데이터 연동 (P0)** - 더미/랜덤 데이터를 실제 API 데이터로 교체
  - `core/api/market_data_client.py`: PyKRXClient (KOSPI/KOSDAQ/섹터 ETF), YahooFinanceClient (VIX/환율)
  - `core/api/sector_momentum_calculator.py`: 섹터 모멘텀 계산 (11개 섹터 ETF 기반)
  - 캐싱 + 재시도 로직 통합 (3회, 지수 백오프)
  - 데이터 소스 우선순위: PyKRX → KIS API → 기본값/폴백
- **Phase 2 설정 파일 확장 (P1)** - `config/phase2.yaml` 추가 섹션
  - 안전 필터, 종합 점수 가중치, 시장 적응형 선정 개수 등 중앙 집중 관리
  - API 재시도 전략 설정 (지수 백오프, 최대 재시도 횟수)
  - 병렬 처리 동시성 제어 설정
  - **레거시 필터링 기준 (legacy_filter)** - FilteringCriteria 설정 중앙화
  - **배치 우선순위 계산 (priority_calculation)** - 변동성 점수 계산 기준
  - 기본값 폴백 지원
- **API 재시도 로직 (P0)** - 지수 백오프 자동 재시도
  - Rate Limit 에러 시 자동 재시도 (최대 3회)
  - 지수 백오프 + 랜덤 지터로 충돌 방지
  - 설정 가능한 대기 시간 (base_delay, max_delay)
  - 재시도 실패 시 명확한 에러 로깅
- **단위 테스트 (P1)** - `tests/unit/daily_selection/test_daily_updater.py`
  - 종합 점수 계산 테스트 (가중치 검증 포함)
  - 시장 적응형 선정 테스트 (섹터 제한 검증)
  - 안전 필터 테스트 (경계값 검증)
  - 테스트 환경: SQLite 인메모리 DB 사용 (로컬 DB 에러 해결)
  - 15개 테스트 케이스 모두 통과

### Fixed

- **서버 크래시 루프 (CRITICAL)** - AsyncKISClient 메서드명 불일치 해결
  - 문제: hantu-scheduler.service 1632+ 재시작 (Jan 29 04:56 이후)
  - 원인: `AttributeError: 'AsyncKISClient' object has no attribute 'get_current_price'`
  - 해결: `get_current_price` → `get_price` 메서드명 수정
  - 응답 파싱: dict → PriceData dataclass로 변경
  - 서버 의존성: PyYAML>=6.0.0 설치 (ModuleNotFoundError 수정)
  - 결과: 서비스 정상 동작 (크래시 없음)
- **psycopg2 모듈 누락 (로컬 환경)** - Python 3.9 가상환경에 재설치
  - 가상환경 내 여러 Python 버전 혼재 문제 해결
  - psycopg2-binary 설치 위치 불일치 수정
  - PostgreSQL 연결 정상화
- **systemd 설정 경고 (서버)** - daemon-reload 실행
  - 서비스 파일 변경 후 reload 누락 해결
  - hantu-scheduler, hantu-api 서비스 재시작
  - 모든 서비스 정상 동작 확인
- **Phase 2 선정 로직 개선 (Phase A)** - 필터링 기준 완화 및 적응형 선정
  - 문제: 148개 감시 종목 중 0개 선정 (필터링 기준 과도)
  - 해결: 안전 필터 + 상위 N개 선정 방식으로 전환
  - 필터링 완화: risk_score < 60 (기존 43), volume_score > 5 (기존 10)
  - 시장 적응형 선정: bullish 12개, neutral 8개, bearish 5개
  - 섹터 제한: 한 섹터당 최대 3개 (포트폴리오 분산)
  - 종합 점수 체계: technical(35%) + volume(25%) + risk(25%) + confidence(15%)
- **AsyncKISClient 세션 초기화 (P0)** - 올바른 세션 관리
  - 문제: RuntimeError "세션이 초기화되지 않았습니다"
  - 해결: `async with AsyncKISClient() as api:` 패턴 사용
  - 병렬 처리 복원 (세마포어로 동시성 제어)
  - 예상 성능 개선: 2x 속도 향상 (90분 → 45분)
- **로컬 테스트 DB 연결 에러** - SQLite 인메모리 사용
  - 단위 테스트에서 PostgreSQL 연결 실패 문제 해결
  - 테스트 환경 변수 설정: `DATABASE_URL=sqlite:///:memory:`
  - Redis 의존성 제거로 테스트 독립성 확보

### Changed

- **core/daily_selection/daily_updater.py** - 시장 지표 실제 API 호출로 변경 (라인 192-223)
  - 기존: `random.uniform()` 사용
  - 신규: PyKRXClient (KOSPI/KOSDAQ) + YahooFinanceClient (VIX/환율)
  - 폴백 기본값: KOSPI=2500, KOSDAQ=850, VIX=20, USD/KRW=1300
- **core/daily_selection/price_analyzer.py** - 섹터 모멘텀 실제 계산 (라인 913-937)
  - 기존: 고정값 0.0 반환
  - 신규: SectorMomentumCalculator 사용 (선형 회귀 기반)
  - 폴백: 중립값 50.0 (기존 0.0에서 변경)
- **core/daily_selection/price_analyzer.py** - OHLC 추정 로직 제거 (라인 1229-1234)
  - 기존: close 기반 OHLC 추정 (open: close*0.995, high: close*1.015 등)
  - 신규: 분석 불가 처리 (중립값 50.0 반환)
- **deploy/DEPLOY_MICRO.md** - 문제 해결 섹션 업데이트
  - psycopg2 모듈 누락 트러블슈팅 추가
  - systemd 설정 변경 경고 해결 방법 추가
  - 진단 및 해결 절차 문서화
- **core/daily_selection/daily_updater.py** - Phase 2 선정 로직 전면 개선 (P0+P1)
  - **Config 관리**: 하드코딩 제거, `config/phase2.yaml`에서 로드
  - **FilteringCriteria.from_config()**: 클래스메서드 추가, config 기반 인스턴스 생성
  - **calculate_composite_priority()**: 변동성 점수 계산을 config 기반으로 변경
  - **\_passes_basic_filters()**: config에서 필터링 기준 로드
  - **\_calculate_composite_score()**: config에서 가중치 로드 + 가중치 합 검증 추가
  - **\_select_top_n_adaptive()**: config에서 목표 선정 수 및 섹터 제한 로드
  - **process_batch()**: AsyncKISClient 복원 + 재시도 로직 추가
  - **\_process_single_stock()**: 병렬 처리용 헬퍼 메서드 추가
  - **\_retry_with_backoff()**: 지수 백오프 재시도 헬퍼 메서드 추가
  - **\_load_config()**: 설정 파일 로드 메서드 추가
  - **\_get_default_config()**: 기본값 폴백 메서드 추가
  - 에러 로깅 개선: 16개소에 exc_info=True 추가
- **workflows/integrated_scheduler.py** - 스케줄링 코드 간소화
  - 헬스체크 스케줄링 중복 제거 (60줄 → 10줄)
  - 평일 5일 × 11개 시간대를 동적 루프로 생성
- **core/api/async_client.py** - 에러 로깅 개선
  - Rate Limit 경고에 exc_info=True 추가
- **core/daily_selection/price_analyzer.py** - Silent Exception 제거
  - 5개소의 try-except에서 logger.debug로 에러 로깅 추가
  - 예외를 무시하던 패턴을 명시적 로깅으로 변경

### Performance

- **병렬 처리 복원**: AsyncKISClient + asyncio.gather 사용
  - 동기 API → 비동기 API 전환 (2x 성능 향상 예상)
  - 세마포어로 동시 요청 수 제어 (config에서 설정 가능)
  - Rate Limit 에러 자동 재시도로 안정성 향상

### Code Quality

- **설정 중앙화 완료 (P1)**: 모든 매직 넘버를 config로 이동
  - FilteringCriteria 기본값 (price_attractiveness, volume_threshold 등 12개)
  - 변동성 계산 상수 (optimal_min, optimal_max, scale_factor 등)
  - 배치 우선순위 가중치 (technical 50%, volume 30%, volatility 20%)
- **예외 처리 개선 (P0)**: exc_info=True 누락 수정 (22개소)
  - core/daily_selection/daily_updater.py: 16개소
  - core/api/async_client.py: 1개소
  - core/daily_selection/price_analyzer.py: 5개소 (Silent Exception 제거)
  - 모든 에러/경고 로그에 스택 트레이스 포함
- **코드 중복 제거 (P2)**: integrated_scheduler.py 헬스체크 스케줄링
  - 60줄 중복 코드 → 10줄 루프로 간소화
  - 평일 5일 × 11개 시간대를 동적으로 생성
- **함수 분리 (P2)**: 긴 함수의 가독성 개선
  - distribute_stocks_to_batches: 헬퍼 메서드 추가 (222줄 → 로직 명확화)
  - \_distribute_round_robin(): 라운드로빈 분산 로직 분리
  - \_log_batch_statistics(): 통계 로깅 로직 분리
- **더미 데이터 경고 (P2)**: 개발/테스트용 더미 데이터 명시
  - \_generate_dummy_price_data(): DEPRECATED 주석 + 경고 로그
  - \_get_sector_momentum(): 더미 데이터 사용 경고
  - \_generate_ohlcv_data(): 더미 데이터 사용 경고
  - 실제 API 데이터로 교체 필요성 명확화
- **이모지 제거 (P2)**: CLAUDE.md 규칙 준수
  - workflows/integrated_scheduler.py: 60개소 이모지 제거
  - core 모듈 6개 파일: 20개소 이모지 제거
  - 로그 메시지에서 모든 이모지 제거 (80개소 총)
- **가중치 검증**: 종합 점수 계산 시 가중치 합 검증
- **테스트 커버리지**: 핵심 로직 단위 테스트 추가 (15개)
- **에러 처리**: API 재시도 로직으로 안정성 향상

---

## [0.8.0] - 2026-01-28

### Added

- **Redis 캐싱 시스템** - API 호출 최적화를 위한 2-Tier 캐시 구조
  - 자동 폴백: Redis 장애 시 MemoryCache로 자동 전환
  - TTL 전략: 현재가 5분, 일봉 차트 10분, 재무 정보 6시간
  - 데코레이터 지원: `@cache_with_ttl` 간편 사용
  - 보안 강화: pickle 대신 JSON 직렬화 사용
- **멀티 윈도우 Rate Limiting** - 3-Tier 요청 제한 시스템
  - 1초 5건: 버스트 방지
  - 1분 100건: 단기 제한
  - 1시간 1,500건: 일일 할당 관리
- **Phase 2 배치 분산 처리** - 감시 리스트 종목 분산 분석
  - 18개 배치, 5분 간격 실행 (07:00-08:30)
  - 복합 우선순위 점수: Technical 50% + Volume 30% + Volatility 20%
  - 라운드로빈 균등 분산
- **자정 캐시 초기화** - 매일 00:00 자동 캐시 정리
  - SCAN + DELETE 방식 (프로덕션 안전)
  - Telegram 알림 발송
- **새 모듈**: `core/api/redis_client.py` (612줄)
  - RedisCache, MemoryCache, CacheManager 클래스
  - 자동 폴백 메커니즘
  - SHA-256 기반 캐시 키 생성

### Changed

- **core/api/rest_client.py** - 캐싱 적용 (3개 메서드)
  - `get_current_price()`: 5분 TTL
  - `get_daily_prices()`: 10분 TTL
  - `get_financial_info()`: 6시간 TTL
- **core/api/async_client.py** - Rate Limiting 개선
  - 단일 윈도우 → 멀티 윈도우 (1s/1m/1h)
  - 동시성 안전 보장 (asyncio.Lock)
- **core/daily_selection/daily_updater.py** - 배치 분산 로직
  - 우선순위 점수 계산 추가
  - 18개 배치로 균등 분산
  - 배치별 실행 시간 관리
- **workflows/integrated_scheduler.py** - 스케줄 추가
  - 00:00: 캐시 초기화
  - 07:00-08:30: Phase 2 배치 실행 (18개, 5분 간격)

### Security

- **pickle 직렬화 제거** - RCE 취약점 해결
  - 모든 캐시 데이터를 JSON으로 직렬화
  - pandas DataFrame/numpy array 안전 변환
- **MD5 → SHA-256 해싱** - 충돌 공격 방지
  - 캐시 키 생성 시 SHA-256 사용
  - 16자 해시 사용 (성능/보안 균형)
- **Redis URL 마스킹** - 비밀번호 보호
  - 로그 출력 시 비밀번호 자동 마스킹

### Fixed

- **core/daily_selection/daily_updater.py**
  - 존재하지 않는 `AsyncKISAPI` → `AsyncKISClient`로 수정
  - 존재하지 않는 `RedisClient` → `cache` 인스턴스로 수정

### Performance

- API 호출 50-70% 감소 (캐싱)
- 배치 분산으로 KIS API Rate Limit 준수
- 멀티 윈도우 Rate Limiting으로 안정성 향상

### Dependencies

- **Added**: `yfinance>=0.2.0` (VIX, USD/KRW 환율 조회)
- **Added**: `scipy>=1.10.0` (선형 회귀 계산)
- **Note**: `pykrx>=1.0.0` (이미 설치됨, KOSPI/KOSDAQ/섹터 ETF)

---

## [이전 버전]

이전 변경 이력은 별도 관리되지 않았습니다.
