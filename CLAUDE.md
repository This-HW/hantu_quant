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

| 구분     | 기술                             |
| -------- | -------------------------------- |
| 언어     | Python 3.11+                     |
| API 서버 | FastAPI                          |
| 스케줄러 | Schedule, APScheduler            |
| DB       | SQLite (로컬), PostgreSQL (운영) |
| 알림     | Telegram Bot                     |
| 배포     | Docker, OCI                      |

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

# 시스템
hantu status             # 서비스 상태
hantu health             # 헬스 체크
hantu logs -f            # 로그 보기

# 보안 검사
python3 scripts/security_check.py --fix
```

---

## 환경 변수

| 변수                 | 설명             |
| -------------------- | ---------------- |
| `KIS_APP_KEY`        | 한투 API 앱 키   |
| `KIS_APP_SECRET`     | 한투 API 시크릿  |
| `KIS_ACCOUNT_NO`     | 계좌 번호        |
| `API_SERVER_KEY`     | API 서버 인증 키 |
| `TELEGRAM_BOT_TOKEN` | 텔레그램 봇 토큰 |
| `TELEGRAM_CHAT_ID`   | 텔레그램 채팅 ID |

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

## 참고 문서

- [CLI 레퍼런스](docs/CLI_REFERENCE.md)
- [API 레퍼런스](docs/API_REFERENCE.md)
- [배포 가이드](deploy/DEPLOY_MICRO.md)
- [서버 정보](deploy/SERVERS.md)
