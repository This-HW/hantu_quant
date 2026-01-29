# 캐싱 아키텍처 설계

## 문서 정보

- **작성일**: 2026-01-28
- **작성자**: API 최적화 팀
- **버전**: 1.0
- **관련 이슈**: API 호출 최적화, 보안 강화

---

## 1. 개요

### 목표

- API 호출 50-70% 감소
- Redis 장애 시에도 서비스 가용성 유지
- 보안 강화 (pickle → JSON)
- 성능과 안정성 균형

### 핵심 요구사항

1. **고가용성**: 캐시 장애가 시스템 전체 장애로 이어지면 안 됨
2. **보안**: RCE 취약점 제거
3. **성능**: API 호출 감소로 속도 향상
4. **유지보수성**: 간단한 설정과 운영

---

## 2. 아키텍처

### 2.1. 2-Tier 캐시 구조

```
┌─────────────────┐
│   Application   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   RedisCache    │ ◄─── Primary Cache
│   (Remote)      │
└────────┬────────┘
         │ (on failure)
         ▼
┌─────────────────┐
│  MemoryCache    │ ◄─── Fallback Cache
│   (In-Process)  │
└─────────────────┘
```

### 2.2. 폴백 메커니즘

1. **RedisCache 시도**: 5초 타임아웃
2. **실패 감지**: ConnectionError, TimeoutError, RedisError
3. **자동 폴백**: MemoryCache로 전환 (로그 기록)
4. **재시도**: 다음 재시작 시 Redis 재시도

```python
try:
    # RedisCache 시도
    return redis_cache.get(key)
except (ConnectionError, TimeoutError):
    logger.warning("Redis 장애 - MemoryCache로 폴백")
    return memory_cache.get(key)
```

### 2.3. 캐시 키 생성

#### 형식

```
{prefix}:{module.function}:{args_hash}
```

#### 예시

```
price:core.api.rest_client.get_current_price:a1b2c3d4e5f6g7h8
chart:core.api.rest_client.get_daily_prices:b2c3d4e5f6g7h8i9
finance:core.api.rest_client.get_financial_info:c3d4e5f6g7h8i9j0
```

#### 해시 알고리즘

- **MD5 (이전)**: 충돌 가능성, 보안 취약
- **SHA-256 (현재)**: 충돌 방지, 보안 강화
- **길이**: 16자 (성능/보안 균형)

```python
import hashlib

def generate_key_hash(args: tuple, kwargs: dict) -> str:
    """SHA-256 기반 캐시 키 해시 생성"""
    combined = f"{args}:{sorted(kwargs.items())}"
    hash_obj = hashlib.sha256(combined.encode('utf-8'))
    return hash_obj.hexdigest()[:16]
```

---

## 3. 직렬화 전략

### 3.1. 보안 문제

#### pickle의 위험성

```python
# ❌ 위험: RCE (Remote Code Execution) 취약점
import pickle

# 악의적인 데이터로 임의 코드 실행 가능
malicious_data = pickle.dumps(MaliciousClass())
pickle.loads(malicious_data)  # 시스템 공격 가능
```

#### JSON의 안전성

```python
# ✅ 안전: JSON은 데이터만 직렬화
import json

data = {"price": 50000, "volume": 1000}
serialized = json.dumps(data)
deserialized = json.loads(serialized)  # 안전
```

### 3.2. 타입별 직렬화

| 타입             | 직렬화 방식                         |
| ---------------- | ----------------------------------- |
| 기본 타입        | JSON 기본 지원 (int, float, str 등) |
| pandas DataFrame | `.to_dict()` → JSON                 |
| numpy array      | `.tolist()` → JSON                  |
| datetime         | `.isoformat()` → ISO 8601 문자열    |
| custom object    | `.__dict__` → JSON (필요시)         |

### 3.3. 구현 예시

```python
import json
import pandas as pd
import numpy as np
from datetime import datetime

class SafeJSONEncoder(json.JSONEncoder):
    """안전한 JSON 인코더"""

    def default(self, obj):
        if isinstance(obj, pd.DataFrame):
            return obj.to_dict(orient='records')

        if isinstance(obj, np.ndarray):
            return obj.tolist()

        if isinstance(obj, datetime):
            return obj.isoformat()

        # 기타는 __dict__ 사용
        try:
            return obj.__dict__
        except AttributeError:
            return super().default(obj)

# 사용
json.dumps(data, cls=SafeJSONEncoder)
```

---

## 4. TTL 전략

### 4.1. TTL 설계 원칙

| 기준              | TTL  | 이유                         |
| ----------------- | ---- | ---------------------------- |
| **실시간성 중요** | 짧음 | 최신 데이터 필요 (현재가)    |
| **변동성 낮음**   | 중간 | 안정적 데이터 (일봉 차트)    |
| **일간 업데이트** | 길게 | 자주 변하지 않음 (재무 정보) |

### 4.2. 적용 TTL

| 데이터 유형     | TTL    | 근거                          |
| --------------- | ------ | ----------------------------- |
| **현재가**      | 5분    | 장중 가격 변동, 실시간성 필요 |
| **일봉 차트**   | 10분   | 일봉은 자주 변하지 않음       |
| **재무 정보**   | 6시간  | 분기/연간 보고서 기반         |
| **종목 리스트** | 24시간 | 일일 단위 변경                |
| **시장 지수**   | 1분    | 실시간 모니터링 필요          |

### 4.3. 동적 TTL (향후)

```python
def dynamic_ttl(data_type: str, market_status: str) -> int:
    """시장 상황에 따른 동적 TTL"""

    if market_status == "closed":
        # 장 마감 시 TTL 연장
        return {
            "price": 3600,      # 1시간
            "chart": 7200,      # 2시간
            "finance": 86400,   # 24시간
        }[data_type]

    # 장 중 기본 TTL
    return {
        "price": 300,       # 5분
        "chart": 600,       # 10분
        "finance": 21600,   # 6시간
    }[data_type]
```

---

## 5. 캐시 초기화

### 5.1. 왜 필요한가?

1. **메모리 관리**: 무한정 쌓이는 캐시 방지
2. **데이터 신선도**: 오래된 데이터 제거
3. **일관성**: 일별 초기화로 데이터 일관성 유지

### 5.2. 초기화 전략

#### 프로덕션 안전 방식 (SCAN + DELETE)

```python
def safe_cache_clear():
    """SCAN + DELETE 방식 (프로덕션 안전)"""
    cursor = 0
    deleted_count = 0

    while True:
        cursor, keys = redis.scan(
            cursor=cursor,
            match="hantu:*",  # 프로젝트 전용 키만
            count=100
        )

        if keys:
            redis.delete(*keys)
            deleted_count += len(keys)

        if cursor == 0:
            break

    logger.info(f"캐시 초기화 완료: {deleted_count}개 키 삭제")
    return deleted_count
```

#### 위험한 방식 (사용 금지)

```python
# ❌ 금지: FLUSHDB/FLUSHALL
redis.flushdb()  # 전체 DB 삭제 - 다른 앱에 영향
redis.flushall()  # 모든 DB 삭제 - 치명적
```

### 5.3. 초기화 스케줄

- **시간**: 매일 00:00 (자정)
- **이유**: 장 시작 전, 시스템 부하 최소
- **알림**: Telegram 알림 발송 (성공/실패)

```python
import schedule

schedule.every().day.at("00:00").do(safe_cache_clear)
```

---

## 6. 모니터링

### 6.1. 핵심 지표

| 지표                  | 측정 방법              | 목표    |
| --------------------- | ---------------------- | ------- |
| **Cache Hit Rate**    | hits / (hits + misses) | > 70%   |
| **Fallback Rate**     | fallback_count / total | < 5%    |
| **Avg Response Time** | sum(latencies) / count | < 50ms  |
| **Cache Size**        | redis memory usage     | < 100MB |

### 6.2. 로깅

```python
logger.info(
    "캐시 조회",
    extra={
        "key": cache_key,
        "hit": True,
        "source": "redis",  # redis or memory
        "latency_ms": 12.3
    }
)

logger.warning(
    "Redis 폴백",
    extra={
        "reason": "ConnectionError",
        "fallback_to": "memory"
    }
)
```

### 6.3. 알림

| 상황                 | 알림 레벨 | 수신자          |
| -------------------- | --------- | --------------- |
| Redis 연결 실패      | Warning   | 개발팀          |
| Cache Hit Rate < 50% | Warning   | 개발팀          |
| Fallback Rate > 10%  | Critical  | 개발팀 + 관리자 |
| 캐시 초기화 실패     | Critical  | 관리자          |

---

## 7. 성능 분석

### 7.1. 예상 효과

#### Before (캐싱 없음)

```
Phase 2 일일 선정 (300종목):
- API 호출: 300 * 3 = 900건
  - 현재가 300건
  - 차트 300건
  - 재무 300건
- 예상 시간: 900건 / 20건/초 = 45초
- Rate Limit 위험: 높음
```

#### After (캐싱 적용)

```
Phase 2 일일 선정 (300종목):
- 첫 실행: 900건 API 호출 (45초)
- 5분 내 재실행: 0건 API 호출 (< 1초)
- 캐시 적중률 70% 가정: 270건 절약
- 평균 API 호출: 270건 / 20건/초 = 13.5초
- 성능 향상: 3.3배
```

### 7.2. 메모리 사용량

#### 예상 메모리

```
1종목당 데이터 크기:
- 현재가: ~500 bytes
- 차트 (60일): ~15 KB
- 재무 정보: ~2 KB

총 17.5 KB / 종목

전체 감시 리스트 (300종목):
- Redis: 17.5 KB * 300 = 5.25 MB
- MemoryCache (폴백): 5.25 MB
- 총: ~10 MB (충분히 작음)
```

---

## 8. 배포 가이드

### 8.1. Redis 설치 (선택)

#### Docker 방식 (권장)

```bash
docker run -d \
  --name hantu-redis \
  -p 6379:6379 \
  -v hantu-redis-data:/data \
  redis:7-alpine \
  redis-server --appendonly yes
```

#### 직접 설치

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install redis-server

# macOS
brew install redis

# 시작
sudo systemctl start redis  # Linux
brew services start redis   # macOS
```

### 8.2. 환경 변수 설정

```bash
# .env 파일
REDIS_URL=redis://localhost:6379/0

# 비밀번호 사용 시
REDIS_URL=redis://:password@localhost:6379/0

# Redis 미사용 시 (MemoryCache만 사용)
# REDIS_URL을 설정하지 않음
```

### 8.3. 연결 테스트

```bash
# Redis CLI로 연결 확인
redis-cli ping  # 응답: PONG

# Python에서 테스트
python -c "
from core.api.redis_client import cache
cache.set('test', 'hello', ttl=60)
print(cache.get('test'))
"
```

### 8.4. 배포 체크리스트

- [ ] Redis 설치/실행 확인
- [ ] REDIS_URL 환경 변수 설정
- [ ] 연결 테스트 성공
- [ ] 로그 확인 (폴백 발생 여부)
- [ ] 캐시 초기화 스케줄 등록 확인
- [ ] Telegram 알림 설정

---

## 9. 트러블슈팅

### 9.1. Redis 연결 실패

**증상**: "Redis 장애 - MemoryCache로 폴백" 로그

**원인**:

- Redis 서버 미실행
- REDIS_URL 잘못 설정
- 방화벽/네트워크 문제

**해결**:

```bash
# Redis 상태 확인
sudo systemctl status redis  # Linux
brew services list | grep redis  # macOS

# Redis 재시작
sudo systemctl restart redis  # Linux
brew services restart redis  # macOS

# 포트 확인
lsof -i:6379
```

### 9.2. 캐시 적중률 낮음

**증상**: Cache Hit Rate < 50%

**원인**:

- TTL이 너무 짧음
- 캐시 키 중복 없음 (매번 다른 인자)
- 메모리 부족으로 조기 eviction

**해결**:

```python
# TTL 조정
@cache_with_ttl(ttl=600, key_prefix="price")  # 10분으로 연장

# 캐시 키 생성 로직 확인
logger.debug(f"Generated cache key: {key}")
```

### 9.3. 직렬화 오류

**증상**: JSONDecodeError, TypeError

**원인**:

- JSON으로 직렬화 불가능한 타입
- 순환 참조

**해결**:

```python
# SafeJSONEncoder 확장
class SafeJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        # 문제되는 타입 추가 처리
        if isinstance(obj, MyCustomClass):
            return obj.to_dict()

        return super().default(obj)
```

---

## 10. 향후 개선 사항

### 10.1. 단기 (1-3개월)

- [ ] 캐시 통계 대시보드 구축
- [ ] 동적 TTL 적용
- [ ] Redis Cluster 구성 (고가용성)

### 10.2. 중기 (3-6개월)

- [ ] 분산 캐시 (Redis Sentinel)
- [ ] 캐시 warming (사전 로딩)
- [ ] 캐시 invalidation 전략

### 10.3. 장기 (6개월+)

- [ ] CDN 통합 (정적 데이터)
- [ ] Edge caching
- [ ] AI 기반 캐시 예측

---

## 11. 참고 자료

### 내부 문서

- `core/api/redis_client.py`: 캐시 구현
- `CHANGELOG.md`: 변경 이력
- `CLAUDE.md`: 프로젝트 설정

### 외부 리소스

- [Redis Documentation](https://redis.io/docs/)
- [Python JSON Encoder](https://docs.python.org/3/library/json.html)
- [OWASP: Deserialization Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Deserialization_Cheat_Sheet.html)
- [Redis Best Practices](https://redis.io/docs/manual/patterns/)

---

## 변경 이력

| 날짜       | 버전 | 변경 내용                 | 작성자        |
| ---------- | ---- | ------------------------- | ------------- |
| 2026-01-28 | 1.0  | 초안 작성 (캐싱 아키텍처) | API 최적화 팀 |
