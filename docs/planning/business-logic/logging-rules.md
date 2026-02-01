# 로그 시스템 비즈니스 규칙 정의서

## 1. 개요

- **도메인**: 로그 시스템 (Logging System)
- **버전**: 3.0 (전면 개편)
- **최종 수정**: 2026-02-01

---

## 2. 엔티티 정의

### 2.1 로그 레코드 (Log Record)

**속성**:

- `timestamp`: 로그 생성 시각 (ISO 8601)
- `level`: 로그 레벨 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `logger`: 로거 이름 (모듈 경로)
- `module`: 발생 모듈
- `function`: 발생 함수
- `line`: 발생 라인 번호
- `message`: 로그 메시지
- `trace_id`: 추적 ID (선택)
- `exception`: 예외 정보 (ERROR 이상)
- `context`: 추가 컨텍스트 데이터 (선택)

**관계**:

- `LogRecord` → `LogFile` (1:1, 저장 위치)
- `LogRecord` → `DBErrorLog` (1:0..1, ERROR 이상만)

### 2.2 로그 파일 (Log File)

**속성**:

- `path`: 파일 경로
- `format`: 파일 형식 (JSON, TEXT)
- `creation_date`: 생성일
- `rotation_policy`: 로테이션 정책
- `retention_days`: 보관 기간 (일)

**관계**:

- `LogFile` → `LogRecord` (1:N)

### 2.3 DB 에러 로그 (DB Error Log)

**속성**:

- `id`: 고유 ID
- `timestamp`: 발생 시각
- `level`: 로그 레벨 (ERROR, CRITICAL만)
- `logger`: 로거 이름
- `message`: 에러 메시지
- `exception`: 예외 정보 (전체 traceback)
- `trace_id`: 추적 ID
- `context`: 컨텍스트 JSON
- `resolved`: 해결 여부

**관계**:

- `DBErrorLog` → `LogRecord` (1:1)

---

## 3. 비즈니스 규칙

### 3.1 유효성 규칙 (Validation Rules)

#### LOG-VAL-001: 로그 레벨 검증

**조건**: 로그 생성 시
**규칙**:

```
IF level NOT IN [DEBUG, INFO, WARNING, ERROR, CRITICAL]:
  THEN raise ValueError("Invalid log level")
```

**예시**:
| 입력 | 유효성 | 결과 |
|------|--------|------|
| INFO | ✅ | 통과 |
| ERROR | ✅ | 통과 |
| TRACE | ❌ | ValueError |
| debug | ❌ | ValueError (대문자 필수) |

**예외**: 없음

---

#### LOG-VAL-002: trace_id 포맷 검증

**조건**: trace_id 설정 시
**규칙**:

```
IF trace_id is provided:
  IF NOT match(r'^[a-f0-9]{8,32}$', trace_id):
    THEN raise ValueError("Invalid trace_id format")
```

**예시**:
| trace_id | 유효성 | 결과 |
|----------|--------|------|
| 1a2b3c4d | ✅ | 통과 (8자리 hex) |
| 1a2b3c4d-5e6f-7g8h | ✅ | 통과 (UUID 형식) |
| invalid-trace | ❌ | ValueError |
| 123 | ❌ | ValueError (길이 부족) |

**예외**: `trace_id=None`인 경우 자동 생성

---

#### LOG-VAL-003: 이모티콘 사용 제한

**조건**: 로그 메시지 작성 시
**규칙**:

```
# 로그 파일/CLI
IF destination IN [log_file, cli]:
  IF emoji NOT IN [✅, ❌, ⭕]:
    THEN strip emoji from message

# Telegram
IF destination == telegram:
  # 현재 이모티콘 허용 (제한 없음)
  PASS
```

**허용 이모티콘**:

- **로그 파일/CLI**: ✅ (성공), ❌ (실패), ⭕ (진행/상태)
- **Telegram**: 🚨, 🔴, ⚠️, 💡, 🟢, 📈, 📉, ➖ 등 (기존 유지)

**예시**:
| 메시지 | 대상 | 결과 |
|--------|------|------|
| "✅ 성공" | 로그 파일 | ✅ 통과 |
| "🎉 완료" | 로그 파일 | "완료" (🎉 제거) |
| "🚨 에러" | Telegram | ✅ 통과 |

**예외**: 민감 데이터 마스킹 우선 적용

---

#### LOG-VAL-004: 로그 메시지 길이 제한

**조건**: 로그 메시지 작성 시
**규칙**:

```
IF len(message) > 10000:
  THEN message = message[:9997] + "..."
```

**이유**: DB 저장, 텔레그램 전송 제한

**예외**: 예외 traceback은 별도 필드 저장 (길이 제한 없음)

---

### 3.2 계산 규칙 (Calculation Rules)

#### LOG-CALC-001: 로그 파일 로테이션 시점

**조건**: 로그 파일 생성 시
**규칙**:

```
rotation_time = midnight (00:00:00)
rotation_interval = 1 day
```

**계산**:

```python
# TimedRotatingFileHandler 설정
when = 'midnight'
interval = 1
backupCount = 3  # 에러/일반 모두 3일
```

**예시**:
| 현재 시각 | 다음 로테이션 |
|-----------|--------------|
| 2026-02-01 14:30 | 2026-02-02 00:00 |
| 2026-02-01 23:59 | 2026-02-02 00:00 |
| 2026-02-02 00:01 | 2026-02-03 00:00 |

**예외**: 없음

---

#### LOG-CALC-002: 로컬 파일 보관 기간

**조건**: 로컬 파일 (에러/일반 모두)
**규칙**:

```
backup_count = 3
retention_days = 3

삭제 시점 = 생성일 + 3일 + 1초
```

**계산**:

```
생성일: 2026-02-01 00:00:00
보관: 2026-02-01, 02, 03 (3일)
삭제: 2026-02-04 00:00:01
```

**예시**:
| 파일명 | 생성일 | 보관 기간 | 삭제일 |
|--------|--------|----------|--------|
| error_20260201.json | 2026-02-01 | 3일 | 2026-02-04 |
| info_20260201.log | 2026-02-01 | 3일 | 2026-02-04 |
| error_20260131.json | 2026-01-31 | 3일 | 2026-02-03 |

**예외**: 수동 백업 파일은 자동 삭제 제외

**명확화 (2026-02-01)**:

- 이전: 에러=30일, 일반=3일
- 변경: **에러/일반 모두 3일** (디스크 공간 절약)
- DB 에러 로그는 **영구 보관** (분석용)

---

#### LOG-CALC-003: DB 배치 큐 플러시 조건

**조건**: DB 에러 로그 저장 시
**규칙**:

```
IF queue_size >= 10 OR time_since_last_flush >= 5s:
  THEN flush_to_db()
```

**계산**:

```python
BATCH_SIZE = 10
FLUSH_INTERVAL = 5.0  # seconds

# 플러시 조건 (OR)
condition_1 = len(queue) >= BATCH_SIZE
condition_2 = time.time() - last_flush_time >= FLUSH_INTERVAL
should_flush = condition_1 or condition_2
```

**예시**:
| 큐 크기 | 마지막 플러시 경과 | 플러시 여부 |
|---------|-------------------|------------|
| 10 | 1초 | ✅ (크기 조건) |
| 5 | 6초 | ✅ (시간 조건) |
| 8 | 3초 | ❌ |
| 1 | 10초 | ✅ (시간 조건) |

**예외**:

- 서비스 종료 시 남은 큐 강제 플러시
- DB 연결 실패 시 재시도 큐로 이동

---

#### LOG-CALC-004: Telegram 쿨다운 시간

**조건**: Telegram 알림 전송 시
**규칙**:

```
# 같은 메시지 반복 방지
IF message_hash == last_message_hash:
  IF time_since_last_send < 300s (5분):
    THEN skip send

# Rate Limit 대응
IF telegram_rate_limited:
  cooldown = min(retry_after, 60s)
  THEN wait(cooldown)
```

**계산**:

```python
COOLDOWN_SECONDS = 300  # 5분

# 메시지 해시 비교
current_hash = hashlib.md5(message.encode()).hexdigest()
if current_hash == last_hash:
    if time.time() - last_send_time < COOLDOWN_SECONDS:
        return False  # 전송 스킵
```

**예시**:
| 메시지 | 마지막 전송 경과 | 전송 여부 |
|--------|------------------|----------|
| "에러 A" | 2분 | ❌ (쿨다운) |
| "에러 A" | 6분 | ✅ |
| "에러 B" | 1분 | ✅ (다른 메시지) |

**예외**:

- `priority=critical`인 경우 쿨다운 무시
- 서로 다른 메시지는 쿨다운 적용 안함

---

### 3.3 상태 전이 규칙 (State Transition Rules)

#### LOG-STATE-001: 로그 핸들러 상태 전이

**상태 목록**:
| 상태 | 코드 | 설명 |
|------|------|------|
| 초기화 | INIT | 핸들러 생성 |
| 활성 | ACTIVE | 로그 수신 중 |
| 플러시 중 | FLUSHING | 버퍼 비우는 중 |
| 에러 | ERROR | 핸들러 오류 |
| 종료 | CLOSED | 핸들러 종료 |

**전이 규칙**:

```
INIT → ACTIVE        (핸들러 시작)
ACTIVE → FLUSHING    (플러시 조건 충족)
FLUSHING → ACTIVE    (플러시 완료)
ACTIVE → ERROR       (핸들러 오류)
ERROR → ACTIVE       (오류 복구)
ACTIVE → CLOSED      (서비스 종료)
ERROR → CLOSED       (오류 상태에서 종료)
```

**전이 다이어그램**:

```
[INIT] ──시작──→ [ACTIVE] ──플러시──→ [FLUSHING]
                    ↑            ↓
                    └─── 완료 ──┘
                    │
              ┌─── 오류 ──→ [ERROR]
              │              │
              └──── 복구 ────┘
              │
         ┌─ 종료 ──→ [CLOSED]
```

**제약 조건**:

- CLOSED 상태에서는 상태 변경 불가
- 역방향 전이 불가 (CLOSED → ACTIVE 불가)

---

#### LOG-STATE-002: DB 배치 큐 상태 전이

**상태 목록**:
| 상태 | 코드 | 설명 |
|------|------|------|
| 대기 | IDLE | 큐 비어있음 |
| 적재 | QUEUING | 로그 수집 중 |
| 플러시 | FLUSHING | DB 저장 중 |
| 재시도 | RETRY | DB 오류 재시도 |
| 완료 | COMPLETE | 플러시 완료 |

**전이 규칙**:

```
IDLE → QUEUING       (첫 로그 추가)
QUEUING → FLUSHING   (플러시 조건 충족)
FLUSHING → COMPLETE  (DB 저장 성공)
FLUSHING → RETRY     (DB 저장 실패)
RETRY → FLUSHING     (재시도)
RETRY → COMPLETE     (재시도 포기)
COMPLETE → IDLE      (큐 초기화)
```

**전이 다이어그램**:

```
[IDLE] ──로그 추가──→ [QUEUING]
                        │
                    플러시 조건
                        │
                        ▼
                   [FLUSHING] ──성공──→ [COMPLETE] ──→ [IDLE]
                        │
                    실패 ▼
                   [RETRY] ──재시도 3회──→ [COMPLETE]
                        │
                        └─── 재시도 ──┘
```

**제약 조건**:

- RETRY 최대 3회
- 재시도 간격: 1초, 2초, 4초 (exponential backoff)
- 재시도 실패 시 COMPLETE 처리 후 로그 손실 기록

---

#### LOG-STATE-003: 에러 로그 해결 상태

**상태 목록**:
| 상태 | 코드 | 설명 |
|------|------|------|
| 미해결 | UNRESOLVED | 새 에러 |
| 진행 중 | IN_PROGRESS | 조사 중 |
| 해결 | RESOLVED | 해결 완료 |
| 무시 | IGNORED | 무시 처리 |

**전이 규칙**:

```
UNRESOLVED → IN_PROGRESS  (조사 시작)
IN_PROGRESS → RESOLVED    (해결)
IN_PROGRESS → IGNORED     (무시 결정)
RESOLVED → UNRESOLVED     (재발)
```

**전이 다이어그램**:

```
[UNRESOLVED] ──조사──→ [IN_PROGRESS] ──해결──→ [RESOLVED]
      ↑                      │
      └───── 재발 ───────────┘
                             │
                          무시 ▼
                        [IGNORED]
```

**제약 조건**:

- IGNORED 상태는 변경 불가 (영구)
- RESOLVED → UNRESOLVED는 같은 trace_id 재발 시만 허용

---

### 3.4 권한 규칙 (Authorization Rules)

#### LOG-AUTH-001: 로그 파일 접근 권한

**역할 정의**:
| 역할 | 코드 | 설명 |
|------|------|------|
| 시스템 | SYSTEM | 시스템 프로세스 |
| 관리자 | ADMIN | 시스템 관리자 |
| 개발자 | DEVELOPER | 개발자 |
| 모니터링 | MONITOR | 모니터링 도구 |

**권한 매트릭스**:
| 리소스 | SYSTEM | ADMIN | DEVELOPER | MONITOR |
|--------|--------|-------|----------|---------|
| logs/errors/_.json | RW | R | R | R |
| logs/info/_.log | RW | R | R | R |
| DB error_logs | CRW | CRUD | R | R |
| 로그 삭제 | - | D | - | - |

**규칙**:

```python
def can_access(user, resource, action):
    if user.role == SYSTEM:
        return action in ['READ', 'WRITE']
    elif user.role == ADMIN:
        return True  # 전체 권한
    elif user.role == DEVELOPER:
        return action == 'READ'
    elif user.role == MONITOR:
        return action == 'READ'
    return False
```

**예외**:

- 민감 데이터 마스킹 우선 적용 (모든 역할)
- ADMIN도 시스템 로그 파일 직접 수정 불가 (WRITE는 시스템만)

---

### 3.5 정책 규칙 (Policy Rules)

#### LOG-POL-001: 레벨별 출력 정책

**조건**: 로그 레벨에 따라 출력 위치 결정
**규칙**:

```
IF level >= ERROR:
  - 로컬 JSON 파일 (logs/errors/error_YYYYMMDD.json)
  - DB 배치 큐 추가
  - stderr 출력 (systemd journal)
  - Telegram 알림 (조건부)
ELSE IF level >= INFO:
  - 로컬 텍스트 파일 (logs/info/info_YYYYMMDD.log)
  - stdout 출력 (프로덕션: null, 개발: 콘솔)
ELSE (DEBUG):
  - 로컬 텍스트 파일 (개발 환경만)
  - 프로덕션: 비활성화
```

**예시**:

```python
# ERROR 이상
logger.error("DB 연결 실패", exc_info=True)
# → logs/errors/error_20260201.json (JSON)
# → DB error_logs 테이블
# → stderr (journalctl -u hantu-scheduler)
# → Telegram (priority=emergency)

# INFO/WARNING
logger.info("스케줄러 시작")
# → logs/info/info_20260201.log (텍스트)
# → stdout (개발 환경만)

# DEBUG
logger.debug("변수 x=%s", x)
# → logs/info/info_20260201.log (개발 환경만)
# → 프로덕션: 무시
```

**예외**: 핸들러 오류 시 stderr 폴백

---

#### LOG-POL-002: 민감 데이터 마스킹 정책

**조건**: 로그 메시지에 민감 정보 포함 시
**규칙**:

```
민감 필드 목록:
- app_key, APP_KEY
- app_secret, APP_SECRET
- access_token, ACCESS_TOKEN
- refresh_token, REFRESH_TOKEN
- account_number, ACCOUNT_NUMBER
- password, PASSWORD
- token, auth, key, secret

마스킹 패턴:
1. JSON: "field": "value" → "field": "***MASKED***"
2. 변수: field=value → field=***MASKED***
```

**예시**:
| 원본 | 마스킹 후 |
|------|----------|
| `"access_token": "abc123"` | `"access_token": "***MASKED***"` |
| `app_key=xyz789` | `app_key=***MASKED***` |
| `password='secret'` | `password=***MASKED***` |

**예외**:

- trace_id는 마스킹 제외 (추적용)
- 에러 메시지의 타입명은 마스킹 제외

---

#### LOG-POL-003: 에러 로그 알림 정책

**조건**: 에러 로그 발생 시 Telegram 알림 여부 결정
**규칙**:

```
# 알림 조건 (AND)
IF level >= ERROR:
  IF consecutive_errors >= 3 OR priority == CRITICAL:
    IF time_since_last_alert >= 300s (5분):
      THEN send_telegram_alert(priority)
```

**우선순위별 정책**:
| 우선순위 | 조건 | 알림 주기 | 소리 |
|---------|------|----------|------|
| critical | 즉시 | 즉시 | 🔊 |
| emergency | 연속 3회 | 즉시 | 🔊 |
| high | 연속 5회 | 5분 | 🔊 |
| normal | - | 알림 안함 | - |

**예시**:

```python
# Case 1: DB 연결 실패 (critical)
logger.error("PostgreSQL 연결 실패", exc_info=True)
# → Telegram 즉시 전송 (🚨)

# Case 2: API 타임아웃 (일반 에러)
logger.error("API 타임아웃", exc_info=True)
# 1회: Telegram 전송 안함
# 2회: Telegram 전송 안함
# 3회: Telegram 전송 (⚠️)

# Case 3: 유효성 검증 실패 (경미)
logger.error("입력값 검증 실패: %s", value)
# → Telegram 전송 안함 (로그만)
```

**예외**:

- 서비스 시작/종료는 `priority=high`로 강제 전송
- 배포 연속 실패는 `priority=critical`로 강제 전송

---

#### LOG-POL-004: 로컬 파일 삭제 정책

**조건**: 로그 파일 로테이션 시
**규칙**:

```
# 자동 삭제 (TimedRotatingFileHandler)
IF file_age > retention_days:
  THEN delete_file()

# 수동 백업 보호
IF file_name contains "backup" OR "manual":
  THEN skip delete
```

**삭제 정책**:
| 파일 유형 | 보관 기간 | 자동 삭제 | 수동 보호 |
|----------|----------|----------|----------|
| error*\*.json | 3일 | ✅ | ❌ |
| info*_.log | 3일 | ✅ | ❌ |
| _\_backup._ | - | ❌ | ✅ |
| _\_manual.\* | - | ❌ | ✅ |

**예시**:

```
# 자동 삭제 대상
logs/errors/error_20260128.json  # 4일 전
logs/info/info_20260129.log      # 4일 전

# 삭제 제외
logs/errors/error_20260131_backup.json  # backup 포함
logs/errors/critical_manual.json        # manual 포함
```

**예외**:

- DB 에러 로그는 영구 보관 (삭제 안함)
- 디스크 공간 부족 시 경고 (자동 삭제 안함)

---

## 4. 용어 정의 (Glossary)

| 용어                | 정의                                                      |
| ------------------- | --------------------------------------------------------- |
| **로그 레벨**       | 로그의 중요도 (DEBUG < INFO < WARNING < ERROR < CRITICAL) |
| **trace_id**        | 요청 추적을 위한 고유 식별자 (8-32자리 hex)               |
| **로테이션**        | 로그 파일을 일자별로 분리하는 과정 (midnight)             |
| **배치 큐**         | DB 저장 전 로그를 임시 보관하는 메모리 버퍼 (최대 10개)   |
| **플러시**          | 배치 큐의 로그를 DB에 저장하는 작업                       |
| **쿨다운**          | 중복 알림 방지를 위한 대기 시간 (5분)                     |
| **민감 데이터**     | 인증 토큰, 비밀번호 등 보호가 필요한 정보                 |
| **마스킹**          | 민감 데이터를 `***MASKED***`로 치환                       |
| **systemd journal** | Linux systemd 로그 시스템 (journalctl로 조회)             |
| **stderr**          | 표준 에러 출력 스트림 (systemd journal로 전달)            |
| **stdout**          | 표준 출력 스트림 (개발 환경: 콘솔, 프로덕션: /dev/null)   |

---

## 5. 규칙 요약

### 비즈니스 규칙 목록

| ID                | 유형  | 설명                                          |
| ----------------- | ----- | --------------------------------------------- |
| **LOG-VAL-001**   | VAL   | 로그 레벨 검증 (5개 레벨만 허용)              |
| **LOG-VAL-002**   | VAL   | trace_id 포맷 검증 (8-32자리 hex)             |
| **LOG-VAL-003**   | VAL   | 이모티콘 사용 제한 (로그: ✅❌⭕만)           |
| **LOG-VAL-004**   | VAL   | 로그 메시지 길이 제한 (10,000자)              |
| **LOG-CALC-001**  | CALC  | 로그 파일 로테이션 시점 (midnight)            |
| **LOG-CALC-002**  | CALC  | 로컬 파일 보관 기간 (3일)                     |
| **LOG-CALC-003**  | CALC  | DB 배치 큐 플러시 조건 (10개 또는 5초)        |
| **LOG-CALC-004**  | CALC  | Telegram 쿨다운 시간 (5분)                    |
| **LOG-STATE-001** | STATE | 로그 핸들러 상태 전이 (INIT→ACTIVE→CLOSED)    |
| **LOG-STATE-002** | STATE | DB 배치 큐 상태 전이 (IDLE→QUEUING→FLUSHING)  |
| **LOG-STATE-003** | STATE | 에러 로그 해결 상태 (UNRESOLVED→RESOLVED)     |
| **LOG-AUTH-001**  | AUTH  | 로그 파일 접근 권한 (역할별)                  |
| **LOG-POL-001**   | POL   | 레벨별 출력 정책 (ERROR→JSON+DB, INFO→텍스트) |
| **LOG-POL-002**   | POL   | 민감 데이터 마스킹 정책                       |
| **LOG-POL-003**   | POL   | 에러 로그 알림 정책 (우선순위별)              |
| **LOG-POL-004**   | POL   | 로컬 파일 삭제 정책 (3일 후 자동 삭제)        |

---

## 6. 핵심 결정 사항

### 6.1 로컬 파일 보관 기간 (명확화: 2026-02-01)

**이전**:

- 에러 로그: 30일
- 일반 로그: 3일

**변경**:

- **에러/일반 모두 3일** (backupCount=3)
- DB 에러 로그: **영구 보관**

**이유**:

- 디스크 공간 절약 (OCI 50GB 제한)
- 분석용 데이터는 DB에 영구 보관
- 최근 3일 로그만으로 충분한 디버깅 가능

### 6.2 이모티콘 정책

**로그 파일/CLI**:

- 허용: ✅ (성공), ❌ (실패), ⭕ (진행/상태)
- 금지: 모든 기타 이모티콘

**Telegram**:

- 현재 이모티콘 유지 (가독성 우선)
- 우선순위별 이모티콘: 🚨 (critical), 🔴 (emergency), ⚠️ (high)

### 6.3 systemd 출력 정책

**프로덕션 환경**:

- stdout → `/dev/null` (일반 로그 무시)
- stderr → `journalctl -u hantu-*` (에러만 기록)

**개발 환경**:

- stdout → 콘솔 (실시간 모니터링)
- stderr → 콘솔 + journalctl

---

## 7. 마이그레이션 주의사항

### 7.1 기존 로그 처리

**규칙**: 기존 로그 파일 **전체 삭제**

**대상**:

- `logs/app/*.log`
- `logs/trade/*.log`
- `logs/system/*.log`
- `logs/error/*.log`

**제외**:

- 수동 백업 파일 (`*_backup.*`, `*_manual.*`)

### 7.2 호환성

**이전 버전과 호환 불가**:

- 로그 디렉토리 구조 변경 (`logs/errors/`, `logs/info/`)
- JSON 형식 변경 (에러 로그만 JSON)
- trace_id 필수 (기존: 선택)

**마이그레이션 스크립트**:

- `scripts/migrate_logs_v3.sh` (예정)

---

## 8. 관련 문서

- **사용자 여정**: `docs/planning/user-journey/logging-system-journey.md`
- **요구사항**: `docs/planning/requirements/logging-system-requirements.md`
- **구현 계획**: `docs/dev/logging-implementation-plan.md` (예정)
- **API 설계**: `docs/design/logging-api.md` (예정)
