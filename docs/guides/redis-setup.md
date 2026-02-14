# Redis 캐싱 시스템 설치 가이드

> 이 문서는 OCI 서버에 Redis를 설치하고 systemd로 관리하는 방법을 설명합니다.

---

## 목차

1. [개요](#개요)
2. [사전 준비](#사전-준비)
3. [자동 설치 (권장)](#자동-설치-권장)
4. [수동 설치](#수동-설치)
5. [검증](#검증)
6. [모니터링](#모니터링)
7. [롤백](#롤백)
8. [트러블슈팅](#트러블슈팅)

---

## 개요

### 설치 내용

- **Redis 서버**: 메모리 캐싱 (1GB 제한)
- **systemd 관리**: 자동 시작 및 재시작
- **보안 설정**: localhost 바인딩, 비밀번호 인증
- **애플리케이션 연동**: hantu-api, hantu-scheduler

### 아키텍처

```
┌─────────────────────────────────────────┐
│  OCI 서버 (158.180.87.156)             │
│                                         │
│  ┌───────────────┐   ┌──────────────┐  │
│  │  hantu-api    │   │  hantu-      │  │
│  │  hantu-       │──>│  scheduler   │  │
│  │  scheduler    │   └──────────────┘  │
│  └───────┬───────┘                     │
│          │ REDIS_URL                   │
│          │ (localhost:6379)            │
│          ▼                              │
│  ┌───────────────┐                     │
│  │  Redis        │                     │
│  │  (systemd)    │                     │
│  │  - 1GB      │                     │
│  │  - LRU 정책   │                     │
│  └───────────────┘                     │
└─────────────────────────────────────────┘
```

---

## 사전 준비

### 1. 서버 접속

```bash
# 로컬에서 서버 접속
ssh ubuntu@158.180.87.156
```

### 2. 환경 확인

```bash
# 작업 디렉토리 확인
pwd
# 출력: /opt/hantu_quant (운영)
# 또는: /home/ubuntu/hantu_quant_dev (개발)

# Redis 실행 확인
systemctl status redis-server
# 또는
ps aux | grep redis
```

### 3. 백업 (권장)

```bash
# .env 백업
cp .env .env.backup

# redis.conf 백업 (있다면)
sudo cp /etc/redis/redis.conf /etc/redis/redis.conf.backup
```

---

## 자동 설치 (권장)

### 단일 명령어 설치

```bash
# 1. 서버 접속
ssh ubuntu@158.180.87.156

# 2. 프로젝트 디렉토리 이동
cd /opt/hantu_quant

# 3. 스크립트 실행
sudo ./scripts/setup-redis.sh
```

### 설치 과정

스크립트는 다음 작업을 자동으로 수행합니다:

#### Phase 1: 준비 작업

- redis-tools, redis-server 설치
- 백업 디렉토리 생성 (`/tmp/redis-backup-YYYYMMDD-HHMMSS`)
- redis.conf, .env 백업
- 비밀번호 자동 생성 (openssl rand -base64 48)

#### Phase 2: Redis 설정 적용

- redis.conf 수정:
  - `bind 127.0.0.1` (localhost만 허용)
  - `requirepass [자동생성비밀번호]`
  - `maxmemory 1gb`
  - `maxmemory-policy allkeys-lru`
  - `supervised systemd`
- systemd 서비스 파일 생성
- Redis 서비스 시작 및 자동시작 활성화

#### Phase 3: 애플리케이션 연동

- .env 파일에 REDIS_URL 추가
- hantu-api, hantu-scheduler 재시작 (운영 환경만)

#### 검증

- Redis 서비스 상태 확인
- PING 테스트
- 바인딩 확인
- 메모리 설정 확인
- 애플리케이션 로그 확인

### 예상 출력

```
=== Redis 캐싱 시스템 설치 시작 ===

[Phase 1] 준비 작업
✅ redis-tools 이미 설치됨
✅ redis-server 이미 설치됨
✅ 백업 디렉토리 생성: /tmp/redis-backup-20260206-100000
✅ redis.conf 백업 완료: /tmp/redis-backup-20260206-100000/redis.conf.backup
✅ .env 백업 완료: /tmp/redis-backup-20260206-100000/.env.backup
✅ 비밀번호 생성 완료: ****************

[Phase 2] Redis 설정 적용
✅ redis.conf 수정 완료
✅ systemd 서비스 파일 생성 완료
✅ systemd 데몬 재로드 완료
✅ Redis 서비스 시작 완료
✅ 자동 시작 설정 완료

[Phase 3] 애플리케이션 연동
✅ .env 파일 업데이트 완료
✅ hantu-api 재시작 중...
✅ hantu-api 재시작 완료
✅ hantu-scheduler 재시작 중...
✅ hantu-scheduler 재시작 완료

[검증]
✅ Redis 서비스: Active (running)
✅ Redis 연결: PONG (성공)
✅ 바인딩: 127.0.0.1:6379 (localhost만 허용)
✅ 메모리 제한: 1GB (설정됨)
✅ 애플리케이션 로그에서 Redis 연결 확인됨

=== 설치 완료 ===

Redis 설정:
  - 주소: localhost:6379
  - 비밀번호: .env 파일에 저장됨 (REDIS_URL)
  - 메모리 제한: 1GB (LRU 정책)
  - 자동 시작: 활성화

백업 위치: /tmp/redis-backup-20260206-100000

다음 단계:
  1. 모니터링: ./scripts/monitor-redis.sh
  2. 로그 확인: journalctl -u redis-server -f
  3. 롤백 (필요시): sudo ./scripts/rollback-redis.sh
```

---

## 수동 설치

자동 스크립트를 사용할 수 없는 경우 수동 설치 방법:

### 1. Redis 설치

```bash
sudo apt-get update
sudo apt-get install -y redis-server redis-tools
```

### 2. redis.conf 수정

```bash
sudo vim /etc/redis/redis.conf

# 다음 내용 수정/추가:
bind 127.0.0.1
supervised systemd
requirepass YOUR_STRONG_PASSWORD
maxmemory 1gb
maxmemory-policy allkeys-lru
```

### 3. systemd 서비스 설정

```bash
sudo vim /etc/systemd/system/redis-server.service
```

```ini
[Unit]
Description=Redis In-Memory Data Store
After=network.target

[Service]
Type=notify
ExecStart=/usr/bin/redis-server /etc/redis/redis.conf
ExecStop=/bin/kill -s TERM $MAINPID
Restart=always
RestartSec=5
User=redis
Group=redis

[Install]
WantedBy=multi-user.target
```

### 4. 서비스 시작

```bash
sudo systemctl daemon-reload
sudo systemctl start redis-server
sudo systemctl enable redis-server
```

### 5. .env 파일 업데이트

```bash
vim /opt/hantu_quant/.env

# 다음 라인 추가:
REDIS_URL=redis://:YOUR_STRONG_PASSWORD@localhost:6379/0
```

### 6. 애플리케이션 재시작

```bash
sudo systemctl restart hantu-api
sudo systemctl restart hantu-scheduler
```

---

## 검증

### 1. Redis 서비스 상태

```bash
# 서비스 상태
sudo systemctl status redis-server

# 예상 출력:
# ● redis-server.service - Redis In-Memory Data Store
#    Loaded: loaded (/etc/systemd/system/redis-server.service; enabled)
#    Active: active (running)
```

### 2. Redis 연결 테스트

```bash
# PING 테스트 (비밀번호 필요)
# 보안: REDISCLI_AUTH 환경변수 사용 (프로세스 목록에 노출 방지)
REDISCLI_AUTH="YOUR_PASSWORD" redis-cli PING

# 예상 출력: PONG
```

### 3. 메모리 설정 확인

```bash
# maxmemory 확인
REDISCLI_AUTH="YOUR_PASSWORD" redis-cli CONFIG GET maxmemory

# 예상 출력:
# 1) "maxmemory"
# 2) "268435456"  (1GB = 268435456 bytes)
```

### 4. 바인딩 확인

```bash
# 포트 확인
netstat -tlnp | grep 6379
# 또는
ss -tlnp | grep 6379

# 예상 출력:
# tcp 0 0 127.0.0.1:6379 0.0.0.0:* LISTEN 1234/redis-server
```

### 5. 애플리케이션 로그

```bash
# API 로그
journalctl -u hantu-api -n 50 | grep -i redis

# Scheduler 로그
journalctl -u hantu-scheduler -n 50 | grep -i redis

# 예상 출력: Redis 연결 성공 로그
```

---

## 모니터링

### 실시간 모니터링 대시보드

```bash
# 1회 조회
./scripts/monitor-redis.sh

# 5초 갱신 (실시간)
./scripts/monitor-redis.sh --watch
```

### 출력 예시

```
╔════════════════════════════════════════════════════════════╗
║           Redis 캐싱 시스템 모니터링 대시보드              ║
╚════════════════════════════════════════════════════════════╝

[환경 정보]
  환경: server
  앱 디렉토리: /opt/hantu_quant
  업데이트: 2026-02-06 10:30:45

[1. Redis 서비스 상태]
  상태: ✅ Active (running)
  시작 시간: Thu 2026-02-06 10:00:00 UTC
  자동 시작: ✅ Enabled

[2. Redis 연결 상태]
  연결: ✅ PONG
  연결된 클라이언트: 2
  바인딩: 127.0.0.1:6379

[3. 메모리 사용량]
  사용 중: 12.5M
  최대 사용: 15.3M
  제한: 1GB
  정책: allkeys-lru
  사용률: 5%

[4. 캐시 통계]
  총 키 개수: 127
  캐시 히트: 4523
  캐시 미스: 892
  히트율: 83%

[5. 캐시 키 목록 (최근 10개)]
  - price:005930 (TTL: 245초)
  - chart:daily:005930 (TTL: 512초)
  - watchlist:latest (TTL: 3421초)
  ...

[6. 애플리케이션 연결 상태]
  hantu-api: ✅ Redis 사용 중
  hantu-scheduler: ✅ Redis 사용 중

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
실시간 모니터링 중... (5초 갱신, Ctrl+C로 종료)
```

### 프로그래밍 방식 모니터링 (Python API)

코드에서 Redis 상태를 확인하고 메트릭을 수집할 수 있습니다.

#### 헬스 체크

```python
from core.monitoring.redis_health import check_redis_health, get_redis_status

# 간편 헬스 체크
result = check_redis_health()
# {'status': 'OK', 'metrics': RedisMetricsData, 'alert_message': None, 'timestamp': '...'}

# 타입 안전 상태 조회 (RedisStatusDict)
status = get_redis_status()
# {'available': True, 'fallback_mode': False, 'status': 'OK',
#  'memory_usage': 12.5, 'hit_rate': 83.0, 'total_keys': 127, 'latency_ms': 0.5}
```

#### 워크플로우 통합

```python
from core.monitoring.redis_health import check_redis_before_workflow

# Phase 1/2 실행 전 자동 헬스 체크 (로깅 전용, 워크플로우를 차단하지 않음)
check_redis_before_workflow("Phase 1 - Screening")
```

#### 메트릭 수집 및 DB 저장

```python
from core.monitoring.redis_health import collect_and_save_metrics

# 주기적 호출 (스케줄러에서 사용)
success = collect_and_save_metrics()  # redis_metrics 테이블에 저장
```

#### 공개 접근자 API

```python
from core.api.redis_client import get_redis_client, get_memory_cache

# Redis 클라이언트 접근 (모니터링 등 내부 용도)
client = get_redis_client()  # Optional[redis.Redis]

# MemoryCache 접근 (폴백 상태 확인)
cache = get_memory_cache()   # MemoryCache
```

#### 알림 임계값

| 지표          | 경고 (WARNING) | 위험 (CRITICAL) |
| ------------- | -------------- | --------------- |
| 메모리 사용률 | 70%            | 80%             |
| 캐시 히트율   | 50% 미만       | 40% 미만        |
| 응답 지연     | 50ms           | 100ms           |

#### DB 테이블

메트릭은 `redis_metrics` 테이블에 자동 저장됩니다:

| 컬럼                   | 타입     | 설명                  |
| ---------------------- | -------- | --------------------- |
| `timestamp`            | DateTime | 수집 시간             |
| `is_available`         | Boolean  | Redis 가용 여부       |
| `memory_usage_percent` | Float    | 메모리 사용률 (%)     |
| `hit_rate_percent`     | Float    | 캐시 히트율 (%)       |
| `total_keys`           | Integer  | 총 키 개수            |
| `latency_ms`           | Float    | 응답 지연 (ms)        |
| `fallback_in_use`      | Boolean  | MemoryCache 폴백 여부 |

### 수동 모니터링

```bash
# 서비스 상태
sudo systemctl status redis-server

# 비밀번호 환경변수 설정 (세션 유지)
export REDISCLI_AUTH="YOUR_PASSWORD"

# 메모리 사용량
redis-cli INFO memory

# 캐시 통계
redis-cli INFO stats

# 연결된 클라이언트
redis-cli CLIENT LIST

# 모든 키 목록 (주의: 프로덕션에서는 SCAN 사용)
redis-cli --scan
```

> **보안 팁**: `redis-cli -a PASSWORD` 대신 `REDISCLI_AUTH` 환경변수를 사용하세요.
> `-a` 옵션은 `ps aux`에서 비밀번호가 노출됩니다.

---

## 롤백

설치 후 문제가 발생하면 롤백할 수 있습니다.

### 자동 롤백

```bash
sudo ./scripts/rollback-redis.sh
```

#### 롤백 작업

1. .env에서 REDIS_URL 제거
2. redis.conf 백업에서 복구 (또는 초기화)
3. Redis 서비스 중지 및 비활성화
4. 애플리케이션 서비스 재시작
5. MemoryCache 폴백 확인

### 수동 롤백

```bash
# 1. .env 수정
vim /opt/hantu_quant/.env
# REDIS_URL 라인 삭제

# 2. Redis 서비스 중지
sudo systemctl stop redis-server
sudo systemctl disable redis-server

# 3. 애플리케이션 재시작
sudo systemctl restart hantu-api
sudo systemctl restart hantu-scheduler

# 4. MemoryCache 폴백 확인
journalctl -u hantu-api -n 100 | grep -i cache
```

### 완전 제거

```bash
# Redis 패키지 제거
sudo apt-get remove --purge redis-server redis-tools

# 설정 파일 제거
sudo rm -rf /etc/redis

# systemd 서비스 파일 제거
sudo rm /etc/systemd/system/redis-server.service
sudo systemctl daemon-reload
```

---

## 트러블슈팅

### 문제 1: Redis 서비스 시작 실패

**증상**:

```bash
sudo systemctl status redis-server
# Active: failed
```

**원인 및 해결**:

1. **포트 충돌** (다른 Redis 인스턴스가 실행 중)

   ```bash
   # 기존 프로세스 확인
   ps aux | grep redis

   # 기존 프로세스 종료
   sudo pkill redis-server

   # 재시작
   sudo systemctl start redis-server
   ```

2. **설정 파일 오류**

   ```bash
   # 설정 파일 검증
   redis-server /etc/redis/redis.conf --test-memory 1

   # 로그 확인
   journalctl -u redis-server -n 50
   ```

3. **권한 문제**

   ```bash
   # redis 사용자/그룹 확인
   id redis

   # 디렉토리 권한 설정
   sudo chown -R redis:redis /var/lib/redis
   sudo chown -R redis:redis /var/log/redis
   ```

### 문제 2: 애플리케이션이 Redis에 연결 안 됨

**증상**:

```bash
journalctl -u hantu-api -n 50 | grep -i redis
# "Redis 연결 실패" 또는 "MemoryCache 폴백" 로그
```

**원인 및 해결**:

1. **.env 파일 확인**

   ```bash
   cat /opt/hantu_quant/.env | grep REDIS_URL

   # REDIS_URL 형식 확인:
   # redis://:PASSWORD@localhost:6379/0
   ```

2. **비밀번호 불일치**

   ```bash
   # redis.conf에서 requirepass 확인
   sudo grep "requirepass" /etc/redis/redis.conf

   # .env의 비밀번호와 일치하는지 확인
   ```

3. **서비스 재시작**
   ```bash
   sudo systemctl restart hantu-api
   sudo systemctl restart hantu-scheduler
   ```

### 문제 3: 메모리 부족 (Evicted keys 증가)

**증상**:

```bash
REDISCLI_AUTH="PASSWORD" redis-cli INFO stats | grep evicted_keys
# evicted_keys:1523  (0이 아님)
```

**원인 및 해결**:

1. **메모리 제한 증가** (1GB → 512MB)

   ```bash
   sudo vim /etc/redis/redis.conf

   # maxmemory 1gb → maxmemory 512mb

   sudo systemctl restart redis-server
   ```

2. **TTL 조정** (캐시 만료 시간 단축)

   ```python
   # core/api/redis_client.py
   @cache_with_ttl(ttl=180)  # 5분 → 3분으로 단축
   ```

3. **불필요한 키 삭제**
   ```bash
   # 만료 시간이 긴 키 확인
   export REDISCLI_AUTH="PASSWORD"
   redis-cli --scan | while read key; do
       TTL=$(redis-cli TTL "$key")
       echo "$key: $TTL"
   done | sort -t: -k2 -n
   ```

### 문제 4: 캐시 히트율 낮음 (<50%)

**증상**:

```bash
./scripts/monitor-redis.sh
# 히트율: 35%
```

**원인 및 해결**:

1. **TTL 너무 짧음** (만료 전에 삭제됨)

   ```python
   # TTL 증가
   @cache_with_ttl(ttl=600)  # 5분 → 10분
   ```

2. **동일 데이터 반복 조회 부족**
   - 스케줄러 간격 조정
   - API 호출 패턴 분석

3. **캐시 키 설계 개선**
   ```python
   # 잘못된 예: 매번 다른 키
   cache_key = f"data:{timestamp}"
   # 올바른 예: 재사용 가능한 키
   cache_key = f"data:{stock_code}:{date}"
   ```

### 문제 5: 모니터링 스크립트 실행 안 됨

**증상**:

```bash
./scripts/monitor-redis.sh
# 에러: redis-cli: command not found
```

**원인 및 해결**:

```bash
# redis-tools 설치
sudo apt-get install -y redis-tools

# 권한 확인
chmod +x ./scripts/monitor-redis.sh
```

---

## 참고 자료

### 관련 문서

- [CLAUDE.md - 캐싱 시스템](../../CLAUDE.md#캐싱-시스템)
- [redis_client.py](../../core/api/redis_client.py) - Python 클라이언트 구현
- [redis_health.py](../../core/monitoring/redis_health.py) - 헬스 체크 유틸리티 (공개 API)
- [redis_monitor.py](../../core/monitoring/redis_monitor.py) - 메트릭 수집 및 DB 저장

### 외부 링크

- [Redis 공식 문서](https://redis.io/docs/)
- [Redis 설정 가이드](https://redis.io/docs/management/config/)
- [systemd 서비스 관리](https://www.freedesktop.org/software/systemd/man/systemctl.html)

### 스크립트 소스

- `scripts/setup-redis.sh` - 자동 설치 스크립트
- `scripts/rollback-redis.sh` - 롤백 스크립트
- `scripts/monitor-redis.sh` - 모니터링 스크립트

---

## 버전 이력

| 버전  | 날짜       | 변경 내용                                                                  |
| ----- | ---------- | -------------------------------------------------------------------------- |
| 1.1.0 | 2026-02-14 | 프로그래밍 모니터링 API 섹션 추가, 메모리 1GB 반영, 공개 접근자 API 문서화 |
| 1.0.0 | 2026-02-06 | 최초 작성 (자동 설치 추가)                                                 |

---

## 문의

설치 중 문제가 발생하면:

1. 로그 확인: `journalctl -u redis-server -n 100`
2. 모니터링: `./scripts/monitor-redis.sh`
3. 롤백: `sudo ./scripts/rollback-redis.sh`
