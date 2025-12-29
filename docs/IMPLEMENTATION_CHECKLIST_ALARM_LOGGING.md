# Implementation Phase Checklist
## 알람/모니터링/로깅 시스템 재설계

**문서 버전**: 1.0
**작성일**: 2025-12-29
**기준 문서**: `TECHNICAL_REVIEW_ALARM_LOGGING.md`

---

## 사용 방법

- [ ] 미완료 항목
- [x] 완료 항목
- [~] 부분 완료 또는 스킵 (사유 명시 필요)

각 체크박스 완료 시 날짜와 담당자를 기록할 것.

---

## Phase 1: 알림 시스템 안정화 (Critical Priority)

### Feature 1: 알림 시스템 안정화 및 통합

#### Story 1.1: Alert 클래스 버그 수정

| 상태 | Task ID | Task | 완료일 | 비고 |
|------|---------|------|--------|------|
| [ ] | T-1.1.1 | Alert 클래스에 `id: str` 필드 추가 | | |
| [ ] | T-1.1.2 | `__post_init__`에서 UUID 기반 자동 ID 생성 로직 구현 | | |
| [ ] | T-1.1.3 | MockNotifier, TelegramNotifier의 `alert.id` 참조 코드 수정 | | |

**Story 1.1 테스트 체크리스트**:
- [ ] Alert 인스턴스 생성 시 id 자동 할당 확인
- [ ] id 값이 12자리 hex 문자열인지 확인
- [ ] 두 Alert 인스턴스의 id가 서로 다른지 확인
- [ ] MockNotifier.send() 호출 시 AttributeError 발생하지 않음
- [ ] TelegramNotifier.send() 호출 시 AttributeError 발생하지 않음

---

#### Story 1.2: TelegramNotifier 통합

| 상태 | Task ID | Task | 완료일 | 비고 |
|------|---------|------|--------|------|
| [ ] | T-1.2.1 | 통합 TelegramNotifier 인터페이스 설계 문서화 | | |
| [ ] | T-1.2.2 | `core/notification/telegram_bot.py`를 표준 구현으로 확정 | | |
| [ ] | T-1.2.3 | requests 라이브러리 기반으로 HTTP 클라이언트 교체 | | |
| [ ] | T-1.2.4 | `core/utils/telegram_notifier.py` → 표준 구현 위임으로 변경 | | |
| [ ] | T-1.2.5 | `core/market_monitor/alert_manager.py` 내부 TelegramNotifier 제거 | | |
| [ ] | T-1.2.6 | `core/market_monitor/integrated_alert_manager.py` 내부 TelegramNotifier 제거 | | |
| [ ] | T-1.2.7 | 레거시 호환 `get_telegram_notifier()` 어댑터 구현 | | |

**Story 1.2 테스트 체크리스트**:
- [ ] 표준 TelegramNotifier 메시지 발송 성공
- [ ] 표준 TelegramNotifier 연결 테스트 성공
- [ ] 레거시 `get_telegram_notifier()` 호출이 표준 구현 반환
- [ ] `alert_manager.py`에서 표준 TelegramNotifier 사용 확인
- [ ] `integrated_alert_manager.py`에서 표준 TelegramNotifier 사용 확인
- [ ] 내부 중복 TelegramNotifier 클래스 완전 제거 확인

---

#### Story 1.3: 텔레그램 설정 체계 정립

| 상태 | Task ID | Task | 완료일 | 비고 |
|------|---------|------|--------|------|
| [ ] | T-1.3.1 | `config/telegram_config.json` 스키마 정의 및 기본 파일 생성 | | |
| [ ] | T-1.3.2 | 환경 변수 폴백 지원 (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`) | | |
| [ ] | T-1.3.3 | 설정 로더 유틸리티 `load_telegram_config()` 구현 | | |
| [ ] | T-1.3.4 | 설정 검증 로직 추가 (필수 필드 체크, 에러 메시지) | | |

**Story 1.3 테스트 체크리스트**:
- [ ] `telegram_config.json` 존재 시 정상 로드
- [ ] 설정 파일 없을 때 환경 변수 폴백 동작
- [ ] 필수 필드 누락 시 명확한 에러 메시지 출력
- [ ] 잘못된 형식의 설정 파일 처리 (JSON 파싱 에러)

---

## Phase 2: 로깅 시스템 통합 (High Priority)

### Feature 2: 로깅 시스템 통합 및 개선

#### Story 2.1: 로깅 아키텍처 통합

| 상태 | Task ID | Task | 완료일 | 비고 |
|------|---------|------|--------|------|
| [ ] | T-2.1.1 | `config/logging_config.yaml` 생성 | | |
| [ ] | T-2.1.2 | 모든 로거가 중앙 설정 사용하도록 수정 | | |
| [ ] | T-2.1.3 | 로그 디렉토리 구조 통일 (`logs/app/`, `logs/trade/`, `logs/system/`) | | |
| [ ] | T-2.1.4 | 모든 로거에 로테이션 적용 확인 | | |

**Story 2.1 테스트 체크리스트**:
- [ ] `logging_config.yaml` 파싱 성공
- [ ] 앱 로그가 `logs/app/` 디렉토리에 생성
- [ ] 거래 로그가 `logs/trade/` 디렉토리에 생성
- [ ] 시스템 로그가 `logs/system/` 디렉토리에 생성
- [ ] 30일 이상 된 로그 자동 삭제 확인

---

#### Story 2.2: 구조화 로깅 확대 적용

| 상태 | Task ID | Task | 완료일 | 비고 |
|------|---------|------|--------|------|
| [ ] | T-2.2.1 | StructuredLogger 사용 가이드라인 문서 작성 | | |
| [ ] | T-2.2.2 | 핵심 모듈에 StructuredLogger 적용 | | |
| [ ] | T-2.2.3 | trace_id 자동 부여 미들웨어 구현 | | |

**Story 2.2 테스트 체크리스트**:
- [ ] StructuredLogger 출력이 JSON 형식
- [ ] trace_id가 로그에 자동 포함
- [ ] 동일 요청의 로그가 같은 trace_id 공유

---

#### Story 2.3: 알림 이력 저장 기능

| 상태 | Task ID | Task | 완료일 | 비고 |
|------|---------|------|--------|------|
| [ ] | T-2.3.1 | 알림 이력 저장 SQLite 스키마 설계 | | |
| [ ] | T-2.3.2 | NotificationManager에 이력 저장 기능 추가 | | |
| [ ] | T-2.3.3 | 알림 이력 조회 API 구현 | | |

**Story 2.3 테스트 체크리스트**:
- [ ] 알림 발송 시 DB에 이력 저장 확인
- [ ] 저장된 이력에 alert_id, timestamp, status 포함
- [ ] 이력 조회 API 정상 응답

---

## Phase 3: 모니터링 시스템 개선 (Medium Priority)

### Feature 3: 모니터링 시스템 개선

#### Story 3.1: 설정 외부화

| 상태 | Task ID | Task | 완료일 | 비고 |
|------|---------|------|--------|------|
| [ ] | T-3.1.1 | `config/monitoring_config.yaml` 생성 | | |
| [ ] | T-3.1.2 | 환경별 임계값 프로필 지원 | | |

**Story 3.1 테스트 체크리스트**:
- [ ] 설정 파일에서 CPU 임계값 로드 확인
- [ ] 설정 파일에서 메모리 임계값 로드 확인
- [ ] dev/staging/prod 프로필 전환 동작

---

#### Story 3.2: 알림 채널 확장 준비

| 상태 | Task ID | Task | 완료일 | 비고 |
|------|---------|------|--------|------|
| [ ] | T-3.2.1 | `BaseNotificationChannel` 인터페이스 정의 | | |
| [ ] | T-3.2.2 | 텔레그램 채널을 인터페이스 기반으로 리팩토링 | | |

**Story 3.2 테스트 체크리스트**:
- [ ] TelegramChannel이 BaseNotificationChannel 상속
- [ ] 인터페이스 메서드 구현 확인 (send, test_connection)

---

## Phase 4: 테스트 및 품질 보증 (High Priority)

### Feature 4: 테스트 및 품질 보증

#### Story 4.1: 알림 시스템 테스트 구축

| 상태 | Task ID | Task | 완료일 | 비고 |
|------|---------|------|--------|------|
| [ ] | T-4.1.1 | `tests/test_notification_manager.py` 작성 | | |
| [ ] | T-4.1.2 | `tests/test_telegram_notifier.py` 작성 (Mock 기반) | | |
| [ ] | T-4.1.3 | `tests/test_alert_formatter.py` 작성 | | |
| [ ] | T-4.1.4 | `tests/integration/test_notification_system.py` 작성 | | |

**Story 4.1 테스트 커버리지 목표**:
- [ ] NotificationManager 커버리지 80% 이상
- [ ] TelegramNotifier 커버리지 80% 이상
- [ ] AlertFormatter 커버리지 90% 이상
- [ ] 통합 테스트 시나리오 5개 이상

---

#### Story 4.2: 로깅 시스템 테스트 보완

| 상태 | Task ID | Task | 완료일 | 비고 |
|------|---------|------|--------|------|
| [ ] | T-4.2.1 | 로그 로테이션 동작 테스트 | | |
| [ ] | T-4.2.2 | 민감정보 필터 테스트 보완 | | |

**Story 4.2 테스트 체크리스트**:
- [ ] 로그 파일 일별 로테이션 동작 확인
- [ ] 민감정보 (API 키, 토큰) 마스킹 확인
- [ ] 민감정보 패턴 10개 이상 테스트

---

## Integration Test Checklist

### 전체 시스템 통합 테스트

| 상태 | 테스트 시나리오 | 완료일 | 비고 |
|------|---------------|--------|------|
| [ ] | 알림 발송 E2E: Alert 생성 → NotificationManager → TelegramNotifier → 텔레그램 수신 | | |
| [ ] | 설정 로드 체인: 환경변수 → config 파일 → 기본값 폴백 | | |
| [ ] | 레이트 리밋 동작: 분당 제한 초과 시 알림 스킵 확인 | | |
| [ ] | 중복 알림 방지: 동일 내용 알림 300초 내 재발송 방지 | | |
| [ ] | 로그 통합: 알림 발송 시 로그 기록, trace_id 일치 확인 | | |
| [ ] | 장애 복구: 텔레그램 API 실패 시 재시도 및 로그 기록 | | |

---

## Cleanup Checklist

### 임시 코드 / 파일 정리

| 상태 | 항목 | 완료일 | 비고 |
|------|------|--------|------|
| [ ] | 제거된 중복 TelegramNotifier 클래스 완전 삭제 확인 | | |
| [ ] | 사용하지 않는 import 문 정리 | | |
| [ ] | TODO/FIXME 주석 해결 또는 이슈 등록 | | |
| [ ] | 디버깅용 print 문 제거 | | |
| [ ] | 하드코딩된 테스트 값 제거 | | |

---

## Documentation Checklist

### 문서 업데이트

| 상태 | 문서 | 업데이트 내용 | 완료일 |
|------|------|-------------|--------|
| [ ] | `CLAUDE.md` | 알림 시스템 사용법 추가 | |
| [ ] | `README.md` | 텔레그램 설정 가이드 추가 | |
| [ ] | `config/telegram_config.json.example` | 새 스키마 반영 | |
| [ ] | `docs/NOTIFICATION_GUIDE.md` | 알림 시스템 상세 가이드 (신규) | |
| [ ] | `docs/LOGGING_GUIDE.md` | 로깅 시스템 상세 가이드 (신규) | |

---

## Git 반영 준비 Checklist

### 커밋 전 확인 사항

| 상태 | 항목 | 완료일 |
|------|------|--------|
| [ ] | 모든 단위 테스트 통과 (`pytest tests/`) | |
| [ ] | 모든 통합 테스트 통과 (`pytest tests/integration/`) | |
| [ ] | 린트 검사 통과 (있는 경우) | |
| [ ] | 타입 검사 통과 (있는 경우) | |
| [ ] | 보안 검사 통과 (`python3 scripts/security_check.py`) | |
| [ ] | 민감정보 커밋 방지 확인 (.env, credentials 등) | |

### 브랜치 및 PR

| 상태 | 항목 | 완료일 |
|------|------|--------|
| [ ] | Feature 브랜치에서 작업 | |
| [ ] | 커밋 메시지 컨벤션 준수 | |
| [ ] | PR 생성 및 리뷰 요청 | |
| [ ] | CI/CD 파이프라인 통과 | |
| [ ] | 리뷰 승인 | |
| [ ] | 메인 브랜치 머지 | |

---

## Summary Progress Tracker

### Phase별 진행률

| Phase | 완료 Task | 전체 Task | 진행률 | 상태 |
|-------|----------|----------|--------|------|
| Phase 1: 알림 시스템 안정화 | 0 | 14 | 0% | 대기 |
| Phase 2: 로깅 시스템 통합 | 0 | 10 | 0% | 대기 |
| Phase 3: 모니터링 개선 | 0 | 4 | 0% | 대기 |
| Phase 4: 테스트/품질 보증 | 0 | 6 | 0% | 대기 |
| **전체** | **0** | **34** | **0%** | **대기** |

### 주요 마일스톤

| 마일스톤 | 목표 | 상태 |
|---------|------|------|
| M1: Alert.id 버그 수정 | Critical 버그 해결 | 대기 |
| M2: TelegramNotifier 통합 | 중복 제거 완료 | 대기 |
| M3: 텔레그램 설정 체계 | 설정 로드 정상화 | 대기 |
| M4: 테스트 구축 | 테스트 커버리지 80% | 대기 |
| M5: 로깅 통합 | 중앙 설정 적용 완료 | 대기 |

---

## Sign-off

### 구현 완료 승인

| 역할 | 이름 | 서명 | 날짜 |
|------|------|------|------|
| 개발자 | | | |
| 리뷰어 | | | |
| 승인자 | | | |

---

**문서 끝**
