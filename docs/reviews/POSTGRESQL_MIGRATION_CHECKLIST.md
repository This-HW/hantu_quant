# Implementation Phase Checklist
## PostgreSQL 통합 마이그레이션

**문서 버전**: 1.0
**작성일**: 2026-01-11
**기준 문서**: POSTGRESQL_MIGRATION_REVIEW.md

---

## Feature 1: SQLite 모듈 PostgreSQL 마이그레이션 (F-PG-001)

### Story 1.1: 핵심 학습 모듈 마이그레이션 (S-PG-001)

#### T-001: DataSynchronizer 통합 DB 연동
- [ ] `__init__` 메서드에 `use_unified_db` 파라미터 추가
- [ ] 통합 DB 연결 시도 및 폴백 로직 구현
- [ ] `sync_screening_results()` SQLAlchemy 버전 구현
- [ ] `sync_selection_results()` SQLAlchemy 버전 구현
- [ ] `update_performance_tracking()` SQLAlchemy 버전 구현
- [ ] `calculate_learning_metrics()` SQLAlchemy 버전 구현
- [ ] 기존 SQLite 버전 폴백으로 유지
- [ ] 단위 테스트 작성 및 통과
- [ ] 통합 테스트 작성 및 통과

#### T-002: EnhancedAdaptiveSystem 통합 DB 연동
- [ ] 통합 DB 세션 사용으로 변경
- [ ] `analyze_screening_accuracy()` 쿼리 업데이트
- [ ] `analyze_selection_accuracy()` 쿼리 업데이트
- [ ] `analyze_sector_performance_detailed()` 쿼리 업데이트
- [ ] `analyze_temporal_patterns()` 쿼리 업데이트
- [ ] pandas read_sql_query 호환성 확인
- [ ] 단위 테스트 작성 및 통과

#### T-003: PerformanceTracker 통합 DB 연동
- [ ] `__init__` 메서드에 `use_unified_db` 파라미터 추가
- [ ] 통합 DB 연결 시도 및 폴백 로직 구현
- [ ] `record_backtest_prediction()` SQLAlchemy 버전 구현
- [ ] `record_actual_performance()` SQLAlchemy 버전 구현
- [ ] `_save_comparison_result()` SQLAlchemy 버전 구현
- [ ] `get_tracking_summary()` SQLAlchemy 버전 구현
- [ ] 외래키 관계 설정 확인
- [ ] 단위 테스트 작성 및 통과
- [ ] 통합 테스트 작성 및 통과

#### T-004: AccuracyTracker 통합 DB 연동
- [ ] `__init__` 메서드에 `use_unified_db` 파라미터 추가
- [ ] `record_daily_selection()` SQLAlchemy 버전 구현
- [ ] `_update_performance_data()` SQLAlchemy 버전 구현
- [ ] `_save_accuracy_result()` SQLAlchemy 버전 구현
- [ ] `_analyze_accuracy_for_date()` SQLAlchemy 버전 구현
- [ ] `get_recent_accuracy()` SQLAlchemy 버전 구현
- [ ] 중복 테이블 통합 처리 (daily_selections, performance_tracking)
- [ ] 단위 테스트 작성 및 통과

#### T-005: StrategyReporter 통합 DB 연동
- [ ] `__init__` 메서드에 `use_unified_db` 파라미터 추가
- [ ] `record_daily_strategy_return()` SQLAlchemy 버전 구현
- [ ] `_save_strategy_performance()` SQLAlchemy 버전 구현
- [ ] `_save_strategy_comparison()` SQLAlchemy 버전 구현
- [ ] `_calculate_strategy_performance()` SQLAlchemy 버전 구현
- [ ] `get_strategy_performance_history()` SQLAlchemy 버전 구현
- [ ] 단위 테스트 작성 및 통과

---

### Story 1.2: 모니터링 모듈 마이그레이션 (S-PG-002)

#### T-006: ModelPerformanceMonitor 통합 DB 연동
- [ ] `__init__` 메서드에 `use_unified_db` 파라미터 추가
- [ ] `_save_performance_metrics()` SQLAlchemy 버전 구현
- [ ] `_save_alert()` SQLAlchemy 버전 구현
- [ ] `_save_baseline()` SQLAlchemy 버전 구현
- [ ] `_get_recent_performance()` SQLAlchemy 버전 구현
- [ ] `_load_baseline()` SQLAlchemy 버전 구현
- [ ] 단위 테스트 작성 및 통과

#### T-007: NotificationHistoryDB 통합 DB 연동
- [ ] `__init__` 메서드에 `use_unified_db` 파라미터 추가
- [ ] `save()` SQLAlchemy 버전 구현
- [ ] `get_by_id()`, `get_by_alert_id()` SQLAlchemy 버전 구현
- [ ] `get_recent()`, `get_failed()` SQLAlchemy 버전 구현
- [ ] `_update_stats()` SQLAlchemy 버전 구현 (UPSERT)
- [ ] `cleanup_old()` SQLAlchemy 버전 구현
- [ ] 단위 테스트 작성 및 통과

#### T-008: SystemAlertManager 통합 DB 연동
- [ ] `__init__` 메서드에 `use_unified_db` 파라미터 추가
- [ ] `_save_alert()` SQLAlchemy 버전 구현
- [ ] `_update_statistics()` SQLAlchemy 버전 구현
- [ ] `get_alert_statistics()` SQLAlchemy 버전 구현
- [ ] 단위 테스트 작성 및 통과

#### T-009: APICallTracker 통합 DB 연동
- [ ] `__init__` 메서드에 `use_unified_db` 파라미터 추가
- [ ] 비동기 쓰기 패턴 유지하면서 통합 DB 연동
- [ ] `record_api_call()` SQLAlchemy 버전 구현
- [ ] `get_api_statistics()` SQLAlchemy 버전 구현
- [ ] `get_recent_calls()` SQLAlchemy 버전 구현
- [ ] `generate_traffic_report()` SQLAlchemy 버전 구현
- [ ] 고빈도 쓰기 성능 테스트
- [ ] 단위 테스트 작성 및 통과
- [ ] 통합 테스트 작성 및 통과 (성능 검증)

---

### Story 1.3: 복원력 모듈 마이그레이션 (S-PG-003)

#### T-010: RecoveryManager 통합 DB 연동
- [ ] `__init__` 메서드에 `use_unified_db` 파라미터 추가
- [ ] `_save_error_event()` SQLAlchemy 버전 구현
- [ ] `_save_recovery_rule()` SQLAlchemy 버전 구현
- [ ] `get_error_statistics()` SQLAlchemy 버전 구현
- [ ] 보안 검토: 에러 메시지 내 민감정보 마스킹
- [ ] 단위 테스트 작성 및 통과

#### T-011: AccuracyAnalyzer 통합 DB 연동
- [ ] 통합 DB 세션 사용으로 변경
- [ ] `_get_performance_data()` SQLAlchemy 버전 구현
- [ ] `compare_periods()` SQLAlchemy 버전 구현
- [ ] `get_accuracy_trend()` SQLAlchemy 버전 구현
- [ ] 단위 테스트 작성 및 통과

---

## Feature 2: 데이터 마이그레이션 (F-PG-002)

### Story 2.1: 마이그레이션 도구 개발 (S-MIG-001)

#### T-012: 마이그레이션 스크립트 개발
- [ ] `scripts/migrate_sqlite_to_postgres.py` 생성
- [ ] 모든 SQLite 테이블 데이터 읽기 구현
- [ ] PostgreSQL 테이블에 bulk insert 구현
- [ ] 진행률 표시 구현
- [ ] 에러 핸들링 및 재시도 로직 구현
- [ ] dry-run 모드 구현
- [ ] 통합 테스트 작성 및 통과

#### T-013: 데이터 검증 도구 개발
- [ ] `scripts/validate_migration.py` 생성
- [ ] 레코드 수 비교 검증
- [ ] 샘플 데이터 무결성 검증
- [ ] 외래키 관계 검증
- [ ] 인덱스 존재 여부 검증
- [ ] 검증 결과 리포트 생성

#### T-014: 롤백 스크립트 개발
- [ ] `scripts/rollback_postgres_migration.py` 생성
- [ ] PostgreSQL 테이블 데이터 삭제 구현
- [ ] SQLite 폴백 활성화 플래그 설정
- [ ] 롤백 로그 기록
- [ ] 통합 테스트 작성 및 통과

---

## Feature 3: SQLAlchemy 모델 확장 (F-PG-003)

### Story 3.1: 누락 모델 추가 (S-MODEL-001)

#### T-015: APICall 모델 추가
- [ ] `core/database/models.py`에 APICall 클래스 추가
- [ ] 컬럼 정의: timestamp, endpoint, method, response_time, status_code 등
- [ ] 인덱스 정의: timestamp, endpoint, success
- [ ] `to_dict()` 메서드 구현
- [ ] 단위 테스트 작성 및 통과

#### T-016: ErrorEvent 모델 추가
- [ ] `core/database/models.py`에 ErrorEvent 클래스 추가
- [ ] 컬럼 정의: timestamp, error_type, severity, message, stack_trace 등
- [ ] 인덱스 정의: timestamp, error_type, severity
- [ ] `to_dict()` 메서드 구현
- [ ] 단위 테스트 작성 및 통과

#### T-017: RecoveryRule 모델 추가
- [ ] `core/database/models.py`에 RecoveryRule 클래스 추가
- [ ] 컬럼 정의: name, error_pattern, recovery_actions, max_attempts 등
- [ ] 단위 테스트 작성 및 통과

#### T-018: StrategyPerformance 모델 추가
- [ ] `core/database/models.py`에 StrategyPerformance 클래스 추가
- [ ] 컬럼 정의: strategy_name, date, total_return, sharpe_ratio 등
- [ ] JSON 필드: monthly_returns, quarterly_returns
- [ ] 인덱스 정의: strategy_name, date
- [ ] `to_dict()` 메서드 구현
- [ ] 단위 테스트 작성 및 통과

#### T-019: MarketRegime 모델 추가
- [ ] `core/database/models.py`에 MarketRegime 클래스 추가
- [ ] 컬럼 정의: date, regime_type, market_return, volatility, confidence
- [ ] 단위 테스트 작성 및 통과

#### T-020: BacktestPrediction 모델 추가
- [ ] `core/database/models.py`에 BacktestPrediction 클래스 추가
- [ ] 컬럼 정의: prediction_id, strategy_name, prediction_date 등
- [ ] JSON 필드: target_stocks, predicted_returns, predicted_weights
- [ ] 인덱스 정의: prediction_id, strategy_name, prediction_date
- [ ] `to_dict()` 메서드 구현
- [ ] 단위 테스트 작성 및 통과

#### T-021: ActualPerformance 모델 추가
- [ ] `core/database/models.py`에 ActualPerformance 클래스 추가
- [ ] BacktestPrediction과 외래키 관계 설정
- [ ] 컬럼 정의: performance_id, prediction_id, execution_date 등
- [ ] JSON 필드: executed_stocks, actual_returns, actual_weights
- [ ] 단위 테스트 작성 및 통과

---

## 공통 검증 체크리스트

### 보안 설계 반영 여부
- [ ] 모든 쿼리에 파라미터 바인딩 사용
- [ ] DATABASE_URL 환경변수 사용 확인
- [ ] 에러 로그에 민감정보 마스킹 적용
- [ ] SQL Injection 취약점 검사 완료

### 성능 및 효율성 설계 반영 여부
- [ ] 필요한 인덱스 모두 생성
- [ ] bulk insert 패턴 적용 (sync_* 메서드)
- [ ] 연결 풀링 활성화 확인
- [ ] 대량 데이터 조회 시 LIMIT 적용

### 임시 코드/파일 정리 여부
- [ ] 디버그 print 문 제거
- [ ] TODO 코멘트 해결 또는 이슈 등록
- [ ] 미사용 import 제거
- [ ] 미사용 변수 제거

### 문서 업데이트 여부
- [ ] CLAUDE.md 데이터베이스 섹션 업데이트
- [ ] deploy/SERVERS.md DB 설정 정보 업데이트
- [ ] deploy/DEPLOY_MICRO.md 마이그레이션 가이드 추가
- [ ] API 문서 업데이트 (있는 경우)

### Git 반영 및 PR 준비 완료 여부
- [ ] 의미 있는 커밋 메시지 작성
- [ ] 커밋당 하나의 논리적 변경
- [ ] PR 설명에 변경 사항 요약
- [ ] PR 설명에 테스트 방법 명시
- [ ] 코드 리뷰 요청

---

## 마이그레이션 완료 검증 체크리스트

### 데이터 무결성 검증
- [ ] 모든 SQLite 테이블 레코드 수 일치 확인
- [ ] 샘플 데이터 내용 일치 확인
- [ ] NULL 값 처리 일치 확인
- [ ] 날짜/시간 변환 정확성 확인
- [ ] JSON 필드 파싱 정확성 확인

### 기능 검증
- [ ] 스크리닝 워크플로우 정상 동작
- [ ] 일일 선정 워크플로우 정상 동작
- [ ] 매매 엔진 정상 동작
- [ ] 학습 시스템 정상 동작
- [ ] 모니터링 시스템 정상 동작
- [ ] 알림 시스템 정상 동작

### 성능 검증
- [ ] 응답 시간 기준치 이하 확인
- [ ] 메모리 사용량 기준치 이하 확인
- [ ] 동시 연결 처리 확인
- [ ] 대량 데이터 처리 시간 확인

### 롤백 준비
- [ ] 롤백 스크립트 테스트 완료
- [ ] 롤백 절차 문서화 완료
- [ ] 롤백 담당자 지정

---

## 최종 승인

| 항목 | 담당자 | 완료일 | 서명 |
|------|-------|-------|------|
| 기능 검증 완료 | | | |
| 보안 검토 완료 | | | |
| 성능 검토 완료 | | | |
| 문서 업데이트 완료 | | | |
| 롤백 준비 완료 | | | |

---

**참고**: 모든 체크 항목이 완료되어야 다음 Phase로 이동할 수 있습니다.
