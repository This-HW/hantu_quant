# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased] - 2026-01-29

### Added

- **Phase 2 설정 파일 (P1)** - `config/phase2.yaml` 추가
  - 안전 필터, 종합 점수 가중치, 시장 적응형 선정 개수 등 중앙 집중 관리
  - API 재시도 전략 설정 (지수 백오프, 최대 재시도 횟수)
  - 병렬 처리 동시성 제어 설정
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

- **deploy/DEPLOY_MICRO.md** - 문제 해결 섹션 업데이트
  - psycopg2 모듈 누락 트러블슈팅 추가
  - systemd 설정 변경 경고 해결 방법 추가
  - 진단 및 해결 절차 문서화
- **core/daily_selection/daily_updater.py** - Phase 2 선정 로직 전면 개선 (P0+P1)
  - **Config 관리**: 하드코딩 제거, `config/phase2.yaml`에서 로드
  - **\_passes_basic_filters()**: config에서 필터링 기준 로드
  - **\_calculate_composite_score()**: config에서 가중치 로드 + 가중치 합 검증 추가
  - **\_select_top_n_adaptive()**: config에서 목표 선정 수 및 섹터 제한 로드
  - **process_batch()**: AsyncKISClient 복원 + 재시도 로직 추가
  - **\_process_single_stock()**: 병렬 처리용 헬퍼 메서드 추가
  - **\_retry_with_backoff()**: 지수 백오프 재시도 헬퍼 메서드 추가
  - **\_load_config()**: 설정 파일 로드 메서드 추가
  - **\_get_default_config()**: 기본값 폴백 메서드 추가

### Performance

- **병렬 처리 복원**: AsyncKISClient + asyncio.gather 사용
  - 동기 API → 비동기 API 전환 (2x 성능 향상 예상)
  - 세마포어로 동시 요청 수 제어 (config에서 설정 가능)
  - Rate Limit 에러 자동 재시도로 안정성 향상

### Code Quality

- **설정 중앙화**: 하드코딩 제거 (60, 5, 12/8/5 등)
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

- **Added**: `redis>=5.0.0` (requirements.txt에 기존재)

---

## [이전 버전]

이전 변경 이력은 별도 관리되지 않았습니다.
