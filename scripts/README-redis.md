# Redis 캐싱 시스템 설치 스크립트

이 디렉토리에는 Redis 캐싱 시스템 자동 설치 및 관리를 위한 스크립트가 포함되어 있습니다.

---

## 스크립트 목록

### 1. setup-redis.sh

**용도**: Redis 자동 설치 및 systemd 설정

**실행**:

```bash
sudo ./scripts/setup-redis.sh
```

**주요 작업**:

- redis-server, redis-tools 설치
- 비밀번호 자동 생성 (openssl rand -base64 48)
- redis.conf 수정 (bind, requirepass, maxmemory)
- systemd 서비스 파일 생성
- .env 파일에 REDIS_URL 추가
- 애플리케이션 서비스 재시작

**백업**:

- `/tmp/redis-backup-YYYYMMDD-HHMMSS/` 디렉토리에 자동 백업

---

### 2. rollback-redis.sh

**용도**: Redis 설정 롤백 (setup-redis.sh 취소)

**실행**:

```bash
sudo ./scripts/rollback-redis.sh
```

**주요 작업**:

- .env에서 REDIS_URL 제거
- redis.conf 원복 (백업에서 복구)
- Redis 서비스 중지 및 비활성화
- 애플리케이션 서비스 재시작
- MemoryCache 폴백 확인

---

### 3. monitor-redis.sh

**용도**: Redis 실시간 모니터링

**실행**:

```bash
# 1회 조회
./scripts/monitor-redis.sh

# 실시간 모니터링 (5초 갱신)
./scripts/monitor-redis.sh --watch
```

**표시 정보**:

- Redis 서비스 상태
- 메모리 사용량 (사용률, 제한)
- 캐시 통계 (히트율, 총 키 개수)
- 캐시 키 목록 (최근 10개)
- 애플리케이션 연결 상태

---

## 사용 예시

### 신규 설치

```bash
# 1. 서버 접속
ssh ubuntu@158.180.87.156

# 2. 프로젝트 디렉토리 이동
cd /opt/hantu_quant

# 3. 설치
sudo ./scripts/setup-redis.sh

# 4. 모니터링
./scripts/monitor-redis.sh --watch
```

### 롤백

```bash
# 1. 롤백 실행
sudo ./scripts/rollback-redis.sh

# 2. MemoryCache 폴백 확인
journalctl -u hantu-api -n 100 | grep -i cache
```

---

## 상세 가이드

전체 설치 가이드 및 트러블슈팅은 다음 문서를 참조하세요:

**[docs/guides/redis-setup.md](../docs/guides/redis-setup.md)**

---

## 주의사항

1. **Root 권한 필요**: setup-redis.sh, rollback-redis.sh는 sudo로 실행
2. **환경 감지**: 스크립트는 자동으로 환경 감지 (server/dev)
3. **백업 확인**: 설치 후 백업 디렉토리 경로 기록
4. **로그 확인**: 설치 후 반드시 애플리케이션 로그 확인

---

## 트러블슈팅

### 설치 실패

```bash
# 로그 확인
journalctl -u redis-server -n 50

# 수동 재시작
sudo systemctl restart redis-server

# 롤백
sudo ./scripts/rollback-redis.sh
```

### 연결 실패

```bash
# .env 확인
cat /opt/hantu_quant/.env | grep REDIS_URL

# Redis 연결 테스트
redis-cli -a $(grep REDIS_URL .env | sed 's/.*:\([^@]*\)@.*/\1/') PING

# 애플리케이션 재시작
sudo systemctl restart hantu-api hantu-scheduler
```

---

## 버전

- **1.0.0** (2026-02-06): 최초 작성
