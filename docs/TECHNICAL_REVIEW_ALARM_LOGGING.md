# Technical Review & Next Phase Planning
## 알람/모니터링/로깅 시스템 재설계

**문서 버전**: 1.0
**작성일**: 2025-12-29
**검토 범위**: 알람, 모니터링, 텔레그램, 로깅 시스템

---

## 1. Current State Summary

### 1.1 완료된 Feature / Story 목록

| Feature | Story | 상태 | 파일 위치 |
|---------|-------|------|-----------|
| 알림 시스템 기본 구조 | Alert/AlertType/AlertLevel 정의 | ✅ 완료 | `core/notification/alert.py` |
| 알림 시스템 기본 구조 | AlertFormatter 구현 | ✅ 완료 | `core/notification/alert.py` |
| 알림 시스템 기본 구조 | NotificationManager 구현 | ✅ 완료 | `core/notification/notification_manager.py` |
| 텔레그램 연동 | TelegramNotifier (신규) 구현 | ✅ 완료 | `core/notification/telegram_bot.py` |
| 텔레그램 연동 | TelegramNotifier (레거시) 구현 | ✅ 완료 | `core/utils/telegram_notifier.py` |
| 텔레그램 연동 | 설정 템플릿 | ✅ 완료 | `config/telegram_config.json.example` |
| 로깅 시스템 | 기본 로깅 설정 | ✅ 완료 | `core/utils/log_utils.py` |
| 로깅 시스템 | JSON 구조화 로깅 | ✅ 완료 | `core/utils/log_utils.py` |
| 로깅 시스템 | TraceIdContext | ✅ 완료 | `core/utils/log_utils.py` |
| 로깅 시스템 | 민감정보 필터 | ✅ 완료 | `core/utils/log_utils.py` |
| 로깅 시스템 | 거래 로그 구조 | ✅ 완료 | `core/learning/trade_logger.py` |
| 모니터링 | MarketMonitor 기본 구현 | ✅ 완료 | `core/market_monitor/market_monitor.py` |
| 모니터링 | AnomalyDetector | ✅ 완료 | `core/market_monitor/anomaly_detector.py` |
| 모니터링 | SystemMonitor | ✅ 완료 | `core/monitoring/system_monitor.py` |

### 1.2 확정된 아키텍처 및 변경 불가 결정 사항

| 항목 | 결정 사항 | 근거 |
|------|----------|------|
| 알림 레벨 체계 | `DEBUG → INFO → WARNING → CRITICAL → EMERGENCY` | 이미 전체 시스템에서 사용 중 |
| AlertType 분류 | 거래/신호/리스크/시스템/성과/학습/시장 7개 카테고리 | 각 모듈에서 의존성 존재 |
| 로그 포맷 | JSON 구조화 로깅 (JSONFormatter) | 테스트 코드 작성됨 |
| 로그 로테이션 | 일별, 30일 보관 | 운영 요건으로 확정 |
| 레이트 리밋 | 시간당/분당/종목당 제한 | NotificationManager에 구현됨 |

---

## 2. Open Issues & Gaps

### 2.1 미완료 Story / Task

| ID | Story | 현황 | 영향도 |
|----|-------|------|--------|
| OI-001 | Alert.id 필드 누락 | MockNotifier/TelegramNotifier에서 AttributeError 발생 | 🔴 Critical |
| OI-002 | TelegramNotifier 중복 구현 | 4개의 독립적 구현 존재, 동작 불일치 | 🔴 Critical |
| OI-003 | telegram_config.json 미생성 | 실제 설정 파일 없음, 텔레그램 비활성화 | 🔴 Critical |
| OI-004 | 알림 시스템 통합 테스트 | 단위/통합 테스트 부재 | 🟠 High |
| OI-005 | 로깅 위치 분산 | logs/, logs/learning/ 분산 | 🟡 Medium |

### 2.2 기술적 부채

| ID | 부채 항목 | 상세 설명 | 영향 범위 |
|----|----------|----------|----------|
| TD-001 | **TelegramNotifier 중복 구현** | 4개 파일에 각각 TelegramNotifier 클래스 존재:<br>1. `core/notification/telegram_bot.py` (urllib 기반)<br>2. `core/utils/telegram_notifier.py` (requests 기반, 싱글톤)<br>3. `core/market_monitor/alert_manager.py` (내부 클래스)<br>4. `core/market_monitor/integrated_alert_manager.py` (내부 클래스) | 유지보수 복잡성 증가, 동작 불일치 |
| TD-002 | **레거시/신규 시스템 혼용** | NotificationManager (신규)와 get_telegram_notifier() (레거시) 동시 존재 | 어느 것을 사용해야 하는지 불명확 |
| TD-003 | **하드코딩된 설정값** | SystemMonitor 임계값 (CPU 80%, 메모리 85%, 디스크 90%) 하드코딩 | 운영 환경별 설정 불가 |
| TD-004 | **Email/SMS/Slack 미구현** | AlertSystem에서 정의만 하고 구현 없음 | 다중 채널 알림 불가 |
| TD-005 | **StructuredLogger 미사용** | 정의만 있고 실제 사용하는 코드 없음 | 구조화 로깅 활용 불가 |

### 2.3 성능 병목 또는 구조적 리스크

| ID | 리스크 | 설명 | 잠재적 영향 |
|----|--------|------|------------|
| SR-001 | **텔레그램 API 단일 실패점** | 재시도 로직은 있으나 폴백 채널 없음 | 네트워크 장애 시 모든 알림 실패 |
| SR-002 | **동기 HTTP 요청** | `core/notification/telegram_bot.py`에서 urllib 동기 요청 사용 | 고부하 시 응답 지연 |
| SR-003 | **로그 파일 무한 증가** | 일부 로그에 로테이션 미적용 | 디스크 공간 고갈 가능성 |
| SR-004 | **알림 이력 미저장** | 발송된 알림 기록 없음 | 디버깅/감사 불가 |

---

## 3. Scope for Next Phase

### Feature 1: 알림 시스템 안정화 및 통합

#### Story 1.1: Alert 클래스 버그 수정

| Task | Description | Dependencies | Priority | Urgency | Expected Impact | Required Test |
|------|-------------|--------------|----------|---------|-----------------|---------------|
| T-1.1.1 | Alert 클래스에 `id` 필드 추가 (UUID 기반) | 없음 | High | High | 부분 수정 | Story |
| T-1.1.2 | `__post_init__`에서 자동 ID 생성 로직 구현 | T-1.1.1 | High | High | 부분 수정 | Story |
| T-1.1.3 | MockNotifier, TelegramNotifier의 alert.id 참조 코드 수정 | T-1.1.1 | High | High | 부분 수정 | Story |

#### Story 1.2: TelegramNotifier 통합

| Task | Description | Dependencies | Priority | Urgency | Expected Impact | Required Test |
|------|-------------|--------------|----------|---------|-----------------|---------------|
| T-1.2.1 | 통합 TelegramNotifier 인터페이스 설계 | 없음 | High | High | 구조 변경 | Story |
| T-1.2.2 | `core/notification/telegram_bot.py`를 표준 구현으로 확정 | T-1.2.1 | High | High | 유지 | Story |
| T-1.2.3 | requests 라이브러리 기반으로 HTTP 클라이언트 교체 | T-1.2.2 | Medium | Medium | 부분 수정 | Story |
| T-1.2.4 | `core/utils/telegram_notifier.py` 레거시 코드를 표준 구현으로 래핑 | T-1.2.2 | High | Medium | 구조 변경 | Integration |
| T-1.2.5 | `core/market_monitor/alert_manager.py` 내부 TelegramNotifier 제거, 표준 사용 | T-1.2.2 | High | Medium | 구조 변경 | Integration |
| T-1.2.6 | `core/market_monitor/integrated_alert_manager.py` 내부 TelegramNotifier 제거 | T-1.2.2 | High | Medium | 구조 변경 | Integration |
| T-1.2.7 | 레거시 호환성 유지를 위한 `get_telegram_notifier()` 어댑터 구현 | T-1.2.4 | Medium | Low | 부분 수정 | Story |

#### Story 1.3: 텔레그램 설정 체계 정립

| Task | Description | Dependencies | Priority | Urgency | Expected Impact | Required Test |
|------|-------------|--------------|----------|---------|-----------------|---------------|
| T-1.3.1 | `telegram_config.json` 스키마 정의 및 문서화 | 없음 | High | High | 유지 | Story |
| T-1.3.2 | 환경 변수 폴백 지원 (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`) | T-1.3.1 | High | High | 부분 수정 | Story |
| T-1.3.3 | 설정 로더 유틸리티 구현 (`load_telegram_config()`) | T-1.3.1, T-1.3.2 | High | Medium | 부분 수정 | Story |
| T-1.3.4 | 설정 검증 로직 추가 (필수 필드 체크) | T-1.3.3 | Medium | Medium | 부분 수정 | Story |

### Feature 2: 로깅 시스템 통합 및 개선

#### Story 2.1: 로깅 아키텍처 통합

| Task | Description | Dependencies | Priority | Urgency | Expected Impact | Required Test |
|------|-------------|--------------|----------|---------|-----------------|---------------|
| T-2.1.1 | 통합 로깅 설정 파일 생성 (`logging_config.yaml`) | 없음 | High | Medium | 구조 변경 | Story |
| T-2.1.2 | 모든 로거가 중앙 설정을 사용하도록 수정 | T-2.1.1 | High | Medium | 구조 변경 | Integration |
| T-2.1.3 | 로그 디렉토리 구조 통일 (`logs/app/`, `logs/trade/`, `logs/system/`) | T-2.1.1 | Medium | Low | 구조 변경 | Story |
| T-2.1.4 | 모든 로거에 로테이션 적용 확인 | T-2.1.2 | Medium | Medium | 유지 | Story |

#### Story 2.2: 구조화 로깅 확대 적용

| Task | Description | Dependencies | Priority | Urgency | Expected Impact | Required Test |
|------|-------------|--------------|----------|---------|-----------------|---------------|
| T-2.2.1 | StructuredLogger 사용 가이드라인 작성 | 없음 | Medium | Low | 유지 | Feature |
| T-2.2.2 | 핵심 모듈(trading, notification)에 StructuredLogger 적용 | T-2.2.1 | Medium | Low | 부분 수정 | Story |
| T-2.2.3 | trace_id를 모든 요청에 자동 부여하는 미들웨어 구현 | T-2.2.1 | Medium | Low | 부분 수정 | Story |

#### Story 2.3: 알림 이력 저장 기능

| Task | Description | Dependencies | Priority | Urgency | Expected Impact | Required Test |
|------|-------------|--------------|----------|---------|-----------------|---------------|
| T-2.3.1 | 알림 이력 저장 스키마 설계 (SQLite) | 없음 | Medium | Medium | 구조 변경 | Story |
| T-2.3.2 | NotificationManager에 이력 저장 기능 추가 | T-2.3.1 | Medium | Medium | 부분 수정 | Story |
| T-2.3.3 | 알림 이력 조회 API 구현 | T-2.3.2 | Low | Low | 부분 수정 | Story |

### Feature 3: 모니터링 시스템 개선

#### Story 3.1: 설정 외부화

| Task | Description | Dependencies | Priority | Urgency | Expected Impact | Required Test |
|------|-------------|--------------|----------|---------|-----------------|---------------|
| T-3.1.1 | SystemMonitor 임계값 설정 파일화 (`monitoring_config.yaml`) | 없음 | Medium | Medium | 부분 수정 | Story |
| T-3.1.2 | 환경별 임계값 프로필 지원 (dev/staging/prod) | T-3.1.1 | Low | Low | 부분 수정 | Story |

#### Story 3.2: 알림 채널 확장 준비

| Task | Description | Dependencies | Priority | Urgency | Expected Impact | Required Test |
|------|-------------|--------------|----------|---------|-----------------|---------------|
| T-3.2.1 | 알림 채널 인터페이스 정의 (`BaseNotificationChannel`) | 없음 | Low | Low | 구조 변경 | Story |
| T-3.2.2 | 텔레그램 채널을 인터페이스 기반으로 리팩토링 | T-3.2.1, Story 1.2 | Low | Low | 부분 수정 | Story |

### Feature 4: 테스트 및 품질 보증

#### Story 4.1: 알림 시스템 테스트 구축

| Task | Description | Dependencies | Priority | Urgency | Expected Impact | Required Test |
|------|-------------|--------------|----------|---------|-----------------|---------------|
| T-4.1.1 | NotificationManager 단위 테스트 작성 | Story 1.1 | High | High | 유지 | Story |
| T-4.1.2 | TelegramNotifier Mock 기반 단위 테스트 작성 | Story 1.2 | High | High | 유지 | Story |
| T-4.1.3 | AlertFormatter 단위 테스트 작성 | 없음 | Medium | Medium | 유지 | Story |
| T-4.1.4 | 알림 시스템 통합 테스트 작성 | T-4.1.1, T-4.1.2 | High | Medium | 유지 | Integration |

#### Story 4.2: 로깅 시스템 테스트 보완

| Task | Description | Dependencies | Priority | Urgency | Expected Impact | Required Test |
|------|-------------|--------------|----------|---------|-----------------|---------------|
| T-4.2.1 | 로그 로테이션 동작 테스트 | Story 2.1 | Medium | Low | 유지 | Story |
| T-4.2.2 | 민감정보 필터 테스트 보완 | 없음 | Medium | Medium | 유지 | Story |

---

## 4. Execution Order

**Priority × Urgency 기준 실행 순서**

| 순서 | Task ID | Task 설명 | Priority | Urgency | 예상 소요 |
|------|---------|----------|----------|---------|----------|
| 1 | T-1.1.1 | Alert.id 필드 추가 | High | High | 소 |
| 2 | T-1.1.2 | 자동 ID 생성 로직 | High | High | 소 |
| 3 | T-1.1.3 | alert.id 참조 코드 수정 | High | High | 소 |
| 4 | T-1.3.1 | telegram_config.json 스키마 정의 | High | High | 소 |
| 5 | T-1.3.2 | 환경 변수 폴백 지원 | High | High | 소 |
| 6 | T-1.2.1 | 통합 TelegramNotifier 인터페이스 설계 | High | High | 중 |
| 7 | T-1.2.2 | 표준 구현 확정 | High | High | 소 |
| 8 | T-4.1.1 | NotificationManager 단위 테스트 | High | High | 중 |
| 9 | T-4.1.2 | TelegramNotifier 단위 테스트 | High | High | 중 |
| 10 | T-1.3.3 | 설정 로더 유틸리티 | High | Medium | 소 |
| 11 | T-1.2.4 | 레거시 코드 래핑 | High | Medium | 중 |
| 12 | T-1.2.5 | alert_manager.py 정리 | High | Medium | 중 |
| 13 | T-1.2.6 | integrated_alert_manager.py 정리 | High | Medium | 중 |
| 14 | T-4.1.4 | 알림 시스템 통합 테스트 | High | Medium | 대 |
| 15 | T-2.1.1 | 통합 로깅 설정 파일 | High | Medium | 중 |
| 16 | T-2.1.2 | 중앙 설정 사용 수정 | High | Medium | 대 |
| 17 | T-1.2.3 | HTTP 클라이언트 교체 | Medium | Medium | 중 |
| 18 | T-1.3.4 | 설정 검증 로직 | Medium | Medium | 소 |
| 19 | T-2.1.4 | 로테이션 적용 확인 | Medium | Medium | 소 |
| 20 | T-4.1.3 | AlertFormatter 단위 테스트 | Medium | Medium | 소 |
| 21 | T-4.2.2 | 민감정보 필터 테스트 | Medium | Medium | 소 |
| 22 | T-2.3.1 | 알림 이력 스키마 설계 | Medium | Medium | 중 |
| 23 | T-2.3.2 | 이력 저장 기능 | Medium | Medium | 중 |
| 24 | T-3.1.1 | 모니터링 설정 외부화 | Medium | Medium | 중 |
| 25 | T-1.2.7 | 레거시 어댑터 | Medium | Low | 소 |
| 26 | T-2.1.3 | 로그 디렉토리 통일 | Medium | Low | 소 |
| 27 | T-2.2.1 | StructuredLogger 가이드 | Medium | Low | 소 |
| 28 | T-2.2.2 | StructuredLogger 적용 | Medium | Low | 중 |
| 29 | T-2.2.3 | trace_id 미들웨어 | Medium | Low | 중 |
| 30 | T-4.2.1 | 로테이션 테스트 | Medium | Low | 소 |
| 31 | T-3.1.2 | 환경별 프로필 | Low | Low | 소 |
| 32 | T-2.3.3 | 이력 조회 API | Low | Low | 소 |
| 33 | T-3.2.1 | 채널 인터페이스 정의 | Low | Low | 중 |
| 34 | T-3.2.2 | 인터페이스 리팩토링 | Low | Low | 중 |

---

## 5. Design & Impact Analysis (Top Priority)

### 5.1 Alert.id 필드 추가 (T-1.1.1 ~ T-1.1.3)

**기존 아키텍처 유지 여부**: ✅ 유지
**변경 범위**: `core/notification/alert.py`, `core/notification/notifier.py`

**변경 내용**:
```
Alert 클래스에 id: str 필드 추가
__post_init__에서 uuid.uuid4().hex[:12] 자동 생성
```

**기술적 근거**:
- Alert 인스턴스마다 고유 식별자 필요
- 중복 알림 방지, 이력 추적에 필수
- UUID 앞 12자리로 충분한 고유성 확보

**영향 분석**:
- 성능: 무시할 수준 (UUID 생성 비용 낮음)
- 확장성: 향후 분산 환경에서도 충돌 가능성 낮음
- 운영: 기존 코드와 완전 호환

### 5.2 TelegramNotifier 통합 (T-1.2.1 ~ T-1.2.7)

**기존 아키텍처 유지 여부**: ⚠️ 부분 변경
**변경 범위**: 4개 파일의 TelegramNotifier → 1개로 통합

**변경 내용**:
```
표준: core/notification/telegram_bot.py
제거: core/market_monitor/alert_manager.py 내부 클래스
제거: core/market_monitor/integrated_alert_manager.py 내부 클래스
래핑: core/utils/telegram_notifier.py → 표준 구현 위임
```

**기술적 근거**:
- 단일 책임 원칙 (SRP) 준수
- 유지보수 복잡성 감소
- 동작 일관성 보장

**영향 분석**:
- 성능: 개선 (중복 코드 제거)
- 확장성: 향상 (단일 진입점)
- 운영: 마이그레이션 기간 필요 (레거시 어댑터로 완화)

### 5.3 로깅 시스템 통합 (T-2.1.1 ~ T-2.1.4)

**기존 아키텍처 유지 여부**: ⚠️ 부분 변경
**변경 범위**: 로깅 설정 중앙화

**변경 내용**:
```
logging_config.yaml 생성
모든 모듈에서 중앙 설정 참조
로그 디렉토리 구조 통일
```

**기술적 근거**:
- 설정 일관성 확보
- 운영 환경별 설정 용이
- 로그 분석 효율성 향상

**영향 분석**:
- 성능: 무관
- 확장성: 향상 (환경별 설정 가능)
- 운영: 초기 마이그레이션 필요, 이후 관리 용이

---

## 6. Scope Control Declaration

### 6.1 범위 내 포함 항목

위 문서에 정의된 **Feature 1 ~ 4**와 해당 **Story/Task**만 다음 구현 Phase 범위에 포함된다.

### 6.2 범위 외 제외 항목

다음 항목은 **명시적으로 제외**되며, 별도 Phase에서 다룬다:

| 제외 항목 | 제외 사유 |
|----------|----------|
| Email/SMS/Slack 채널 구현 | 텔레그램 안정화 우선 |
| 실시간 대시보드 UI 개발 | 백엔드 안정화 후 진행 |
| AI 기반 이상 탐지 고도화 | 기본 기능 안정화 후 진행 |
| 메트릭 시계열 DB 도입 | 운영 데이터 축적 후 검토 |
| 분산 로깅 시스템 (ELK 등) | 현재 규모에서 불필요 |

### 6.3 변경 통제

- 위 문서에 정의되지 않은 Feature/Story/Task는 다음 구현 Phase 범위에 포함되지 않는다.
- 범위 변경이 필요한 경우, 본 문서를 갱신하고 "설계 확정" 선언 전에 검토를 거쳐야 한다.

---

## Appendix A: 파일별 변경 영향 매트릭스

| 파일 경로 | 변경 유형 | 관련 Task |
|----------|----------|----------|
| `core/notification/alert.py` | 수정 | T-1.1.1, T-1.1.2 |
| `core/notification/notifier.py` | 수정 | T-1.1.3 |
| `core/notification/telegram_bot.py` | 수정 | T-1.2.2, T-1.2.3 |
| `core/utils/telegram_notifier.py` | 수정 | T-1.2.4, T-1.2.7 |
| `core/market_monitor/alert_manager.py` | 수정 | T-1.2.5 |
| `core/market_monitor/integrated_alert_manager.py` | 수정 | T-1.2.6 |
| `config/telegram_config.json` | 신규 | T-1.3.1 |
| `core/notification/config_loader.py` | 신규 | T-1.3.3 |
| `config/logging_config.yaml` | 신규 | T-2.1.1 |
| `config/monitoring_config.yaml` | 신규 | T-3.1.1 |
| `tests/test_notification_manager.py` | 신규 | T-4.1.1 |
| `tests/test_telegram_notifier.py` | 신규 | T-4.1.2 |
| `tests/test_alert_formatter.py` | 신규 | T-4.1.3 |
| `tests/integration/test_notification_system.py` | 신규 | T-4.1.4 |

---

## Appendix B: 의존성 다이어그램

```
                    ┌─────────────────────────┐
                    │   NotificationManager   │
                    │   (통합 관리자)          │
                    └───────────┬─────────────┘
                                │
            ┌───────────────────┼───────────────────┐
            │                   │                   │
            v                   v                   v
    ┌───────────────┐   ┌───────────────┐   ┌───────────────┐
    │TelegramNotifier│   │ MockNotifier  │   │ (Future)      │
    │   (표준)       │   │  (테스트용)   │   │ Email/Slack   │
    └───────────────┘   └───────────────┘   └───────────────┘
            │
            v
    ┌───────────────┐
    │ Alert         │
    │ (id 필드 추가)│
    └───────────────┘
            │
            v
    ┌───────────────┐
    │AlertFormatter │
    └───────────────┘


    ┌─────────────────────────────────────────┐
    │          Logging Architecture           │
    ├─────────────────────────────────────────┤
    │  logging_config.yaml (중앙 설정)        │
    │         │                               │
    │         v                               │
    │  ┌─────────────┐  ┌─────────────┐      │
    │  │ app logger  │  │trade logger │      │
    │  └──────┬──────┘  └──────┬──────┘      │
    │         │                │              │
    │         v                v              │
    │    logs/app/        logs/trade/         │
    └─────────────────────────────────────────┘
```

---

**문서 끝**
