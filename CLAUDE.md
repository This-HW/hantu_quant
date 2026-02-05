# 한투 퀀트 (Hantu Quant) - AI 자동화 트레이딩 시스템

## 프로젝트 개요

- **이름**: Hantu Quant
- **설명**: 한국투자증권 OpenAPI 기반 AI 자동화 주식 트레이딩 시스템
- **타입**: Python 백엔드 + CLI
- **주요 언어**: Python 3.11+
- **프레임워크**: FastAPI, Schedule

---

## 작업 환경 감지

> **세션 시작 시 반드시 현재 환경을 파악하세요.**

### 환경 판단 기준

| 환경       | 판단 조건                                       | 주 용도                |
| ---------- | ----------------------------------------------- | ---------------------- |
| **로컬**   | 경로가 `/Users/grimm/`으로 시작                 | 기능 개발, 설계, CI/CD |
| **서버**   | 경로가 `/opt/hantu_quant/` 또는 `/home/ubuntu/` | 에러 픽스, 핫픽스      |
| **온라인** | claude.ai 웹 환경                               | 대규모 작업, 리서치    |

### 환경별 Git 규칙

| 환경   | 브랜치 prefix             | CI 스킵          | 비고               |
| ------ | ------------------------- | ---------------- | ------------------ |
| 로컬   | `feature/*`, `refactor/*` | X                | PR 필수            |
| 서버   | `fix/*`, `hotfix/*`       | `[skip ci]` 권장 | 서비스 재시작 필요 |
| 온라인 | `claude/*`                | X                | PR 필수            |

**상세 규칙**: `.claude/rules/git-governance.md` 참조

---

## 프로젝트 목표

### 비전

종목 스크리닝부터 매매 실행까지 전 과정을 자동화하여 체계적이고 감정에 휘둘리지 않는 퀀트 트레이딩을 구현한다.

### 핵심 기능

1. **Phase 1**: 종목 스크리닝 (전체 종목 대상 일일 분석)
2. **Phase 2**: 일일 매매 종목 선정 (감시 리스트 기반)
3. **Phase 3**: 매매 실행 (자동 주문, 리스크 관리)
4. **Phase 4**: 학습/AI (머신러닝 기반 전략 최적화)

### 비기능 요구사항

- 성능: 전체 종목 스크리닝 30분 이내
- 가용성: 장 시간 중 99% 업타임
- 보안: API 키/시크릿 보호, 인증 필수

---

## 프로젝트 구조

```
hantu_quant/
├── core/                   # 핵심 비즈니스 로직
│   ├── api/               # KIS API 클라이언트
│   ├── watchlist/         # 감시 리스트 관리
│   ├── daily_selection/   # 일일 종목 선정
│   ├── trading/           # 매매 실행
│   ├── learning/          # AI/ML 학습
│   ├── risk/              # 리스크 관리
│   └── utils/             # 유틸리티
├── api-server/            # FastAPI 서버
├── cli/                   # CLI 도구
├── workflows/             # 실행 워크플로우
│   ├── phase1_watchlist.py
│   ├── phase2_daily_selection.py
│   └── integrated_scheduler.py
├── tests/                 # 테스트
├── docs/                  # 문서
│   ├── design/            # 설계 문서
│   ├── planning/          # 기획 문서
│   └── guides/            # 가이드
├── deploy/                # 배포 설정
├── scripts/               # 유틸리티 스크립트
└── config/                # 설정
```

---

## 🚨 필수 규칙 (MUST)

> 기본 규칙(SSOT, MCP 활용, 코드 품질)은 자동 적용됩니다.

### 1. 파일/폴더 구조 규칙

**파일 생성 전 반드시 `.claude/project-structure.yaml` 확인**

```
✅ 허용:
- core/**/*.py        → 핵심 로직
- api-server/**/*.py  → API 서버
- workflows/**/*.py   → 워크플로우
- tests/**/*.py       → 테스트

❌ 금지:
- 루트에 임의 .py 파일 (main.py, setup.py 제외)
- *_old.*, *_backup.*, temp_*, tmp_*
- notes.md, TODO.md 등 산발적 문서
```

### 2. 에러 로깅 규칙

**모든 except 블록에 반드시 `exc_info=True` 사용**

```python
# ❌ 금지
except Exception as e:
    logger.error(f"실패: {e}")

# ✅ 필수
except Exception as e:
    logger.error(f"실패: {e}", exc_info=True)
```

**공통 로거 사용**

```python
from core.utils.log_utils import get_logger
logger = get_logger(__name__)
```

### 3. 보안 규칙

- API 키/시크릿은 반드시 `.env` 파일에만 저장
- `.env` 변경 시 `.env.example` 업데이트 필수
- 커밋 전 `python3 scripts/security_check.py` 실행

### 4. 테스트 규칙

| 유형        | 위치                 | 보존           |
| ----------- | -------------------- | -------------- |
| 단위 테스트 | `tests/unit/`        | 영구           |
| 통합 테스트 | `tests/integration/` | 영구           |
| 임시 테스트 | `tests/scratch/`     | **PR 전 삭제** |

---

## 기술 스택

| 구분     | 기술                            |
| -------- | ------------------------------- |
| 언어     | Python 3.11+                    |
| API 서버 | FastAPI                         |
| 스케줄러 | Schedule, APScheduler           |
| DB       | PostgreSQL 15 (All-in-One 서버) |
| 캐시     | Redis (자동 MemoryCache 폴백)   |
| 알림     | Telegram Bot                    |
| 배포     | Docker, OCI                     |

---

## 인프라 구성

### All-in-One 서버 (158.180.87.156)

**서버와 DB가 같은 머신에 통합되어 있습니다.**

- **서버**: hantu-server (158.180.87.156)
- **구성**: API Server + Scheduler + PostgreSQL 15 + Redis 7
- **OS**: Ubuntu 24.04 (ARM64)
- **스펙**: 1 OCPU / 6GB RAM / 50GB Storage

### 환경별 DB 접속 정보

| 환경                | DATABASE_URL                                                        | 설명                         |
| ------------------- | ------------------------------------------------------------------- | ---------------------------- |
| **서버**            | `postgresql://hantu@localhost:5432/hantu_quant` (.pgpass 인증)      | 서버 내부에서 localhost 접속 |
| **로컬** (SSH 터널) | `postgresql://hantu@localhost:15432/hantu_quant` (.pgpass 인증)     | SSH 터널을 통한 접속         |
| **로컬** (직접)     | `postgresql://hantu@158.180.87.156:5432/hantu_quant` (.pgpass 인증) | 방화벽 개방 시               |

**SSH 터널 명령**:

```bash
ssh -i ~/.ssh/id_rsa -f -N -L 15432:localhost:5432 ubuntu@158.180.87.156
```

### DATABASE_URL 환경변수 우선순위

⚠️ **중요**: .env 파일에 DATABASE_URL을 설정하면 자동 감지가 무시됩니다!

`settings.py`의 자동 감지 우선순위:

1. **DATABASE_URL 환경변수** (최우선 - 자동 감지 완전히 무시!)
2. **HANTU_ENV 환경변수** (local/server/test)
3. **경로 기반 자동 감지** (`/Users/*`, `/opt/*`, `/home/ubuntu`)

**권장 설정 (로컬 개발)**:

```bash
# .env 파일에서 DATABASE_URL을 제거하거나 주석 처리 (권장)
# DATABASE_URL=...  ← 이 줄 삭제 또는 주석

# SSH 터널 시작
./scripts/db-tunnel.sh start

# 자동으로 localhost:15432 포트 사용됨 (경로 기반 감지)
```

**대안: 명시적 환경 설정**:

```bash
# .env 파일에 추가 (DATABASE_URL 대신)
HANTU_ENV=local   # 자동으로 localhost:15432 사용
```

**잘못된 예 (흔한 실수)**:

```bash
# ❌ 로컬 .env에 서버 포트 설정 → SSH 터널 미사용, 연결 실패!
DATABASE_URL=postgresql://hantu@localhost:5432/hantu_quant

# ❌ 로컬 .env에 잘못된 포트 → 자동 감지 무시됨
DATABASE_URL=postgresql://hantu@localhost:15432/hantu_quant  # 비밀번호 누락 시 실패
```

**자동 환경 감지 동작**:

- 로컬(`/Users/*`, `/home/username`): SSH 터널 포트(`15432`) 자동 사용
- 서버(`/opt/*`, `/home/ubuntu`): localhost 포트(`5432`) 자동 사용
- 테스트: SQLite 사용

---

## 캐싱 시스템

### 개요

Redis 기반 2-Tier 캐싱으로 API 호출을 50-70% 감소시킵니다. Redis 장애 시 자동으로 MemoryCache로 폴백되어 서비스 가용성을 유지합니다.

### 캐시 TTL 전략

| 데이터 유형 | TTL   | 이유          |
| ----------- | ----- | ------------- |
| 현재가      | 5분   | 실시간성 중요 |
| 일봉 차트   | 10분  | 변동성 낮음   |
| 재무 정보   | 6시간 | 일간 업데이트 |

### 사용 예시

```python
from core.api.redis_client import cache_with_ttl

@cache_with_ttl(ttl=300, key_prefix="price")
def get_price(stock_code: str):
    # API 호출
    ...
```

### 설정

- **환경 변수**: `REDIS_URL=redis://localhost:6379/0` (선택)
- **폴백**: Redis 연결 실패 시 자동으로 MemoryCache 사용
- **초기화**: 매일 00:00 자동 캐시 초기화
- **보안**: JSON 직렬화 (pickle 대신), SHA-256 해싱

### Redis 설치 및 설정

**자동 설치 (권장)**:

```bash
# OCI 서버에서 실행
sudo ./scripts/setup-redis.sh
```

**모니터링**:

```bash
./scripts/monitor-redis.sh          # 1회 조회
./scripts/monitor-redis.sh --watch  # 실시간 (5초 갱신)
```

**롤백**:

```bash
sudo ./scripts/rollback-redis.sh
```

**상세 가이드**: `docs/guides/redis-setup.md` 참조

---

## Rate Limiting

### 멀티 윈도우 전략

| 윈도우 | 최대 요청 | 목적           |
| ------ | --------- | -------------- |
| 1초    | 5건       | 버스트 방지    |
| 1분    | 100건     | 단기 제한      |
| 1시간  | 1,500건   | 일일 할당 관리 |

### 구현 위치

- **모듈**: `core/api/async_client.py`
- **클래스**: `MultiWindowRateLimiter`
- **동시성**: asyncio.Lock으로 안전 보장

---

## 배포 규칙

### 기본 원칙

**CI/CD 자동 배포를 우선 사용하고, 수동 배포는 긴급 상황에만 사용합니다.**

### 배포 방식

| 방식          | 언제               | 프로세스                  | 소요 시간 |
| ------------- | ------------------ | ------------------------- | --------- |
| **자동 배포** | 일반적인 모든 경우 | git push → CI → Deploy    | 2-4분     |
| **수동 배포** | 긴급 핫픽스만      | 서버 접속 → 수정 → 재시작 | 즉시      |

### 자동 배포 플로우

```bash
# 1. 로컬 개발
git checkout -b feature/new-feature
# 코드 작성 및 테스트
git commit -m "feat: 새 기능 추가"
git push origin feature/new-feature

# 2. PR 생성 및 병합
# GitHub에서 PR → main 병합

# 3. CI/CD 자동 실행 (2-4분 대기)
# ✅ CI: 테스트, 린트, 보안 검사
# ✅ Deploy: git pull, 의존성 설치, 서비스 재시작
# ✅ 텔레그램 알림 전송

# 4. 완료 (수동 개입 불필요)
```

### 수동 배포 (긴급만)

```bash
# 서버 접속
ssh ubuntu@158.180.87.156

# 코드 수정
cd /opt/hantu_quant
git checkout -b hotfix/urgent
# 수정...
git commit -m "fix: 긴급 수정 [skip ci]"

# 서비스 재시작
sudo systemctl restart hantu-scheduler hantu-api

# 확인 후 push
git push origin hotfix/urgent
```

### 절대 금지

```
❌ git push + 수동 배포 (동시)
   → 배포 충돌 발생 (수동 배포 → CI/CD가 덮어씀)

✅ git push → CI/CD 대기 (권장)
✅ [skip ci] + 수동 배포 (긴급만)
```

**상세 규칙**: `.claude/rules/deployment.md` 참조

---

## 배치 분산 처리 (Phase 2)

### 스케줄

- **Phase 1**: 06:00 - 전체 종목 스크리닝 (감시 리스트 생성)
- **Phase 2**: 07:00-08:30 - 18개 배치, 5분 간격
  - 배치 0: 07:00
  - 배치 1: 07:05
  - ...
  - 배치 17: 08:25

### 우선순위 점수

- **Technical Score**: 50% (기술적 지표)
- **Volume Score**: 30% (거래량 추세)
- **Volatility Score**: 20% (변동성)

### 배치 분산 방식

1. 감시 리스트 종목에 우선순위 점수 계산
2. 점수 기준 내림차순 정렬
3. 라운드로빈으로 18개 배치에 균등 분산
4. 각 배치는 5분 간격으로 실행

### 구현 위치

- **모듈**: `core/daily_selection/daily_updater.py`
- **함수**: `distribute_to_batches()`, `calculate_priority_score()`
- **스케줄러**: `workflows/integrated_scheduler.py`

---

## 주요 명령어

```bash
# CLI 설치
pip install -e .

# 서비스 시작
hantu start all          # 전체 서비스
hantu start scheduler    # 스케줄러만
hantu start api          # API 서버만

# 분석 실행
hantu screen             # 종목 스크리닝
hantu select             # 일일 선정

# 트레이딩
hantu trade balance      # 잔고 조회
hantu trade positions    # 포지션 조회
hantu monitor            # 실시간 모니터링 (1회)
hantu monitor --live     # 실시간 모니터링 (5초 갱신)

# 시스템
hantu status             # 서비스 상태
hantu health             # 헬스 체크
hantu logs -f            # 로그 보기

# 보안 검사
python3 scripts/security_check.py --fix

# DB 연결 (로컬 개발 시)
./scripts/db-tunnel.sh start    # SSH 터널 시작
./scripts/db-tunnel.sh status   # 터널 상태 확인
./scripts/db-tunnel.sh stop     # 터널 중지
python scripts/diagnose-db.py   # DB 연결 진단
```

---

## 환경 변수

| 변수                  | 설명                                          | 기본값        | 필수 여부 |
| --------------------- | --------------------------------------------- | ------------- | --------- |
| `APP_KEY`             | 한투 API 앱 키                                | -             | ✅        |
| `APP_SECRET`          | 한투 API 시크릿                               | -             | ✅        |
| `ACCOUNT_NUMBER`      | 계좌 번호 (8자리)                             | -             | ✅        |
| `ACCOUNT_PROD_CODE`   | 계좌 상품 코드 (01=종합, 02=위탁)             | `01`          | ⭕ (선택) |
| `SERVER`              | 서버 모드 (virtual=모의투자, prod=실전)       | `virtual`     | ⭕ (선택) |
| `API_SERVER_KEY`      | API 서버 인증 키                              | -             | ⭕ (prod) |
| `TELEGRAM_BOT_TOKEN`  | 텔레그램 봇 토큰                              | -             | ✅        |
| `TELEGRAM_CHAT_ID`    | 텔레그램 채팅 ID                              | -             | ✅        |
| `DATABASE_URL`        | PostgreSQL 연결 URL                           | (자동 감지)   | ⭕ (자동) |
| `HANTU_ENV`           | 환경 명시 (local/server/test)                 | (경로 기반)   | ⭕ (선택) |
| `REDIS_URL`           | Redis 연결 URL (예: redis://localhost:6379/0) | (MemoryCache) | ⭕ (선택) |
| `LOG_LEVEL`           | 로그 레벨 (DEBUG/INFO/WARNING/ERROR)          | `INFO`        | ⭕ (선택) |
| `TRADING_PROD_ENABLE` | 실전 거래 허용 (true/false)                   | `false`       | ⭕ (선택) |
| `DB_POOL_SIZE`        | DB 연결 풀 크기                               | `5`           | ⭕ (선택) |
| `DB_MAX_OVERFLOW`     | DB 연결 풀 최대 오버플로우                    | `10`          | ⭕ (선택) |
| `DB_POOL_TIMEOUT`     | DB 연결 풀 타임아웃 (초)                      | `30`          | ⭕ (선택) |
| `DB_POOL_RECYCLE`     | DB 연결 재사용 시간 (초)                      | `1800` (30분) | ⭕ (선택) |

**참고**:

- **DATABASE_URL 자동 설정 (강력 권장)**:
  - ⚠️ `.env` 파일에 `DATABASE_URL`을 설정하면 자동 감지가 **완전히 무시됩니다**
  - 권장: `.env`에서 `DATABASE_URL` 제거 후 자동 감지 사용
  - 로컬: SSH 터널 포트 (`localhost:15432`) 자동 사용
  - 서버: 내부 포트 (`localhost:5432`) 자동 사용
  - 상세: "인프라 구성 > DATABASE_URL 환경변수 우선순위" 섹션 참조
- **DB 비밀번호 인증**: `~/.pgpass` 파일 사용 (환경변수 불필요)
  - 형식: `hostname:port:database:username:password`
  - 권한: `chmod 600 ~/.pgpass`
  - 예시: `localhost:15432:hantu_quant:hantu:PASSWORD` (로컬)
  - 예시: `localhost:5432:hantu_quant:hantu:PASSWORD` (서버)
- `REDIS_URL` 미설정 시 자동으로 MemoryCache 사용
- Redis 연결 실패 시에도 MemoryCache로 폴백되어 서비스 정상 동작

### DATABASE_URL 트러블슈팅

**문제: 로컬에서 PostgreSQL 연결 실패 (포트 5432 접근 시도)**

```bash
# 원인: .env 파일에 DATABASE_URL 설정 → 자동 감지 무시됨
# 해결:
1. .env 파일 열기
2. DATABASE_URL 라인 제거 또는 주석 처리
3. SSH 터널 확인: ./scripts/db-tunnel.sh status
4. 재시도: python scripts/diagnose-db.py
```

**문제: "비밀번호 인증 실패"**

```bash
# 원인: .pgpass 파일 누락 또는 권한 문제
# 해결:
1. ~/.pgpass 파일 생성/수정
   echo "localhost:15432:hantu_quant:hantu:YOUR_PASSWORD" >> ~/.pgpass
2. 권한 설정
   chmod 600 ~/.pgpass
```

---

## 점수 기준

### Phase 1: 종목 스크리닝 (100점)

- 재무건전성 (30%): ROE, PER, PBR, 부채비율
- 기술적 지표 (40%): 이평선, MACD, RSI
- 모멘텀 (30%): 거래량/가격 추세

### Phase 2: 일일 선정 (100점)

- 기술적 점수 (40%): 이평선, MACD, RSI, 스토캐스틱, CCI
- 가격 매력도 (30%): 지지선 근접도
- 시장 상황 (20%): 섹터 동향
- 리스크 점수 (10%): 변동성, VaR

---

## 현재 구현 진행상황

### 1. 실데이터 연동 구현 (상태: 완료)

**현재 상태**: 모든 분석이 실제 데이터로 동작
**구현 완료**:

- KIS API 통한 실데이터 조회 완료
- 캐싱 및 요청 제한 처리
- 데이터 검증 및 정제

```python
# 사용 예시
from core.api.kis_api import KISAPI

kis = KISAPI()
real_data = kis.get_daily_prices(stock_code, period=60)
```

### 2. 기술적 지표 계산 구현 (완료)

**구현 완료 지표**:

- RSI (Relative Strength Index)
- MACD (Moving Average Convergence Divergence)
- 볼린저 밴드 (Bollinger Bands)
- 스토캐스틱 오실레이터 (%K, %D)
- CCI (Commodity Channel Index)
- ATR (Average True Range)

**구현 위치**: `core/daily_selection/price_analyzer.py`

### 3. 리스크 관리 시스템 (완료)

**구현 완료**:

- 역사적 변동성 계산 (연율화)
- VaR (Value at Risk) 파라메트릭 방법
- ATR 기반 손절가 계산
- 통합 리스크 점수 (변동성, 시가총액, 유동성, 섹터)

**향후 개선 예정**:

- CVaR (Conditional VaR)
- Copula 기반 상관관계 분석
- 동적 포지션 사이징

### 4. ML/AI 모델 학습 (진행중)

**계획된 모델**:

1. **LSTM**: 시계열 가격 예측
2. **XGBoost**: 종목 선정 분류
3. **Random Forest**: 특성 중요도 분석
4. **앙상블**: 최종 의사결정

**구현 위치**: `core/learning/models/` (구조만 완료)

### 5. 머신러닝 학습 파이프라인

**현재 상태**: 실제 데이터 기반
**구현 예정**:

- 일별 성과 데이터 수집
- 특성/레이블 데이터셋 생성
- 모델 학습 및 평가 자동화

### 6. 실시간 모니터링 예시

```python
# 스케줄러 예시
scheduler.every().day.at("08:30").do(run_daily_selection)

watch_list.monitor_real_time(
    price_change_threshold=0.05,  # 5% 변동
    volume_surge_threshold=2.0    # 2배 거래량
)
```

---

## 목표 지표

| 지표        | 현재 목표 | 장기 목표 |
| ----------- | --------- | --------- |
| 연수익률    | 12%       | 20%+      |
| 샤프 비율   | 1.2       | 1.8+      |
| 최대 손실폭 | -8%       | -12%      |
| 승률        | 58%       | 65%+      |

---

## Deployment & Maintenance Documentation Rules

### 필수 문서화 항목

배포 또는 인프라 변경 시 반드시 아래 문서를 업데이트하세요:

#### 1. `deploy/SERVERS.md` - 서버 정보

업데이트 시점: 서버 생성/변경/삭제 시

- 서버 IP 주소 (Public/Private)
- 인스턴스 OCID
- 서버 스펙 (CPU, RAM, Storage)
- 용도 및 설치된 서비스
- SSH 접속 정보

#### 2. `deploy/DEPLOY_MICRO.md` - 배포 가이드

업데이트 시점: 배포 절차 변경 시

- 의존성 설치 방법
- 환경 설정 방법
- 트러블슈팅 가이드

#### 3. `CHANGELOG.md` - 변경 이력 (필요시 생성)

업데이트 시점: 주요 버전 릴리즈 시

- 버전별 변경 내용
- Breaking changes
- 마이그레이션 가이드

### 배포 체크리스트

```markdown
배포 전:
[ ] 코드 변경사항 테스트 완료
[ ] requirements.txt 의존성 확인
[ ] .env.example 업데이트 (새 환경변수 추가 시)

배포 후:
[ ] deploy/SERVERS.md 업데이트
[ ] 서버 동작 확인
[ ] 로그 확인 (journalctl -u hantu-\* -f)
```

### 버전 정보 기록

Python 패키지 버전 이슈 발생 시 `deploy/DEPLOY_MICRO.md`의 "문제 해결" 섹션에 기록:

- 에러 메시지
- 해결 방법
- 영향받는 Python/OS 버전

---

## 에러 로깅 상세 가이드

### 컨텍스트 정보 포함 (중요한 함수)

```python
except Exception as e:
    logger.error(
        f"주문 실행 실패: {e}",
        exc_info=True,
        extra={
            'stock_code': stock_code,
            'order_type': order_type,
            'quantity': quantity,
        }
    )
```

### 에러 수준 구분

| 수준               | 용도                     | 예시                    |
| ------------------ | ------------------------ | ----------------------- |
| `logger.error()`   | 기능 실패, 복구 필요     | 주문 실패, DB 연결 실패 |
| `logger.warning()` | 잠재적 문제, 동작은 계속 | 재시도 성공, 폴백 사용  |
| `logger.info()`    | 중요 이벤트              | 주문 체결, 스케줄 시작  |
| `logger.debug()`   | 디버깅용 상세 정보       | 변수 값, 중간 결과      |

### Silent Failure 금지

```python
# ❌ 금지 - 에러 무시
except Exception:
    pass

# ❌ 금지 - 로깅 없이 반환
except Exception as e:
    return None

# ✅ 올바른 예
except Exception as e:
    logger.error(f"처리 실패: {e}", exc_info=True)
    return None  # 또는 raise
```

### DB 에러 로깅 (중요 서비스)

```python
# 스케줄러, API 서버 등 중요 서비스에서는 DB 에러 로깅 활성화
from core.utils.db_error_handler import setup_db_error_logging
db_error_handler = setup_db_error_logging(service_name="서비스명")
```

### 에러 로깅 체크리스트

새 코드 작성 시:

- [ ] 모든 `except` 블록에 `exc_info=True` 추가
- [ ] `get_logger(__name__)` 사용
- [ ] 에러 메시지에 실패 원인 포함
- [ ] 중요 함수는 컨텍스트 정보 추가
- [ ] Silent failure 없음 확인

---

## 이모티콘 사용 정책

### 로그 파일 및 CLI

**허용되는 이모티콘 (3종만)**:

- ✅ (성공)
- ❌ (실패)
- ⭕ (진행/상태)

**금지**: 위 3종을 제외한 모든 이모티콘

### Telegram 알림

**현재 이모티콘 유지** (가독성 우선):

- 🚨 (critical)
- 🔴 (emergency)
- ⚠️ (high)
- 💡, 🟢, 📈, 📉, ➖ 등

**상세 규칙**: `docs/planning/business-logic/logging-rules.md` 참조

---

## Telegram Circuit Breaker

네트워크 장애 시 불필요한 재시도를 방지하고 시스템 안정성을 높이기 위해 Circuit Breaker 패턴을 적용합니다.

### 동작 방식

| 상태   | 조건                   | 동작                       |
| ------ | ---------------------- | -------------------------- |
| Closed | 정상 상태              | 모든 요청 처리             |
| Open   | 연속 5회 실패          | 요청 즉시 거부 (5분간)     |
| Reset  | Open 상태에서 5분 경과 | Closed로 복귀, 재시도 허용 |

### 설정값

- **임계값**: 연속 5회 실패 시 차단 (`_circuit_breaker_threshold = 5`)
- **리셋 시간**: 5분 (300초) 후 재시도 (`_circuit_breaker_reset_time = 300`)

### 구현 위치

- **모듈**: `core/notification/telegram_bot.py`
- **테스트**: `tests/unit/notification/test_telegram_circuit_breaker.py`

### 로그 확인

```bash
# Circuit Breaker 관련 로그 확인
grep "Circuit breaker" logs/*.log
grep "consecutive_failures" logs/*.log
```

---

## 로그 보관 정책

### 로컬 파일 보관 기간

**모든 로그 파일: 3일**

| 파일 유형 | 위치                              | 보관 기간 | 삭제 방식 |
| --------- | --------------------------------- | --------- | --------- |
| 에러 로그 | `logs/errors/error_YYYYMMDD.json` | 3일       | 자동 삭제 |
| 일반 로그 | `logs/info/info_YYYYMMDD.log`     | 3일       | 자동 삭제 |

**변경 이유**:

- 디스크 공간 절약 (OCI 50GB 제한)
- 최근 3일 로그만으로 충분한 디버깅 가능
- 장기 분석용 데이터는 DB에 영구 보관

### DB 에러 로그

**영구 보관** (삭제 안함)

- 테이블: `error_logs`
- 용도: 장기 분석, 패턴 분석, 통계
- 접근: `hantu logs --db` 또는 SQL 직접 쿼리

**상세 규칙**: `docs/planning/business-logic/logging-rules.md` 참조

---

## 참고 문서

### 개발 가이드

- [CLI 레퍼런스](docs/CLI_REFERENCE.md)
- [API 레퍼런스](docs/API_REFERENCE.md)
- [환경 변수 설정 가이드](docs/guides/env-setup.md) - **.env 설정 및 DATABASE_URL 트러블슈팅**
- [Redis 설치 가이드](docs/guides/redis-setup.md) - **캐싱 시스템 자동 설치 및 모니터링**

### 배포 및 인프라

- [배포 규칙](.claude/rules/deployment.md) - **CI/CD 자동 배포 우선**
- [Git 거버넌스](.claude/rules/git-governance.md) - 브랜치 전략
- [배포 가이드](deploy/DEPLOY_MICRO.md) - 수동 배포 참고용
- [서버 정보](deploy/SERVERS.md)
