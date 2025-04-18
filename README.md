# Hantu Quant

한투 API를 이용한 퀀트 트레이딩 시스템

## 프로젝트 구조

```
hantu_quant/
├── core/                   # 핵심 기능
│   ├── api/               # API 관련 모듈
│   │   ├── kis_api.py    # 한국투자증권 API
│   │   ├── krx_client.py # KRX API
│   │   ├── rest_client.py # REST API 클라이언트
│   │   └── websocket_client.py # WebSocket 클라이언트
│   ├── config/           # 설정 관련 모듈
│   │   ├── settings.py   # 기본 설정
│   │   ├── api_config.py # API 설정
│   │   └── trading_config.py # 트레이딩 설정
│   ├── database/         # 데이터베이스 관련
│   │   ├── models.py     # DB 모델
│   │   ├── repository.py # 저장소 클래스
│   │   └── session.py    # DB 세션 관리
│   ├── realtime/        # 실시간 처리
│   │   ├── processor.py  # 데이터 처리기
│   │   └── handlers.py   # 이벤트 핸들러
│   └── utils/           # 유틸리티
├── hantu_backtest/      # 백테스팅 엔진
│   ├── core/            # 백테스트 핵심
│   ├── optimization/    # 전략 최적화
│   ├── strategies/      # 백테스트 전략
│   └── visualization/   # 결과 시각화
├── hantu_common/        # 공통 라이브러리
│   ├── data/           # 데이터 관리
│   ├── indicators/     # 기술적 지표
│   └── utils/          # 공통 유틸리티
├── scripts/            # 실행 스크립트
│   ├── collect_data.py # 데이터 수집
│   ├── init_db.py     # DB 초기화
│   ├── query_db.py    # DB 조회
│   └── manage.py      # 프로젝트 관리 스크립트
├── tests/             # 테스트 코드
├── data/              # 데이터 저장소
│   ├── db/           # 데이터베이스 파일
│   ├── stock/        # 주식 데이터
│   └── logs/         # 로그 파일
├── logs/             # 애플리케이션 로그
└── .ai/              # AI 협업 디렉토리
    ├── context/      # 프로젝트 컨텍스트
    ├── templates/    # 작업 템플릿
    ├── workflows/    # 작업 워크플로우
    └── history/      # 작업 히스토리
```

## 주요 기능

### 1. 실시간 트레이딩
- 한국투자증권 API를 통한 실시간 주식 거래
- WebSocket을 통한 실시간 시세 수신
- 자동 매매 전략 실행

### 2. 백테스팅
- 과거 데이터 기반 전략 테스트
- 다양한 성과 지표 계산
- 전략 최적화 및 시각화

### 3. 데이터 관리
- SQLite 데이터베이스를 통한 데이터 관리
- KRX 종목 정보 자동 수집
- 실시간/일별 주가 데이터 관리

### 4. 기술적 지표
- RSI, MACD, 볼린저 밴드 등 구현
- 커스텀 지표 추가 가능
- 실시간 지표 계산

## 설치 및 실행

1. 환경 설정
```bash
# 자동 환경 설정 (디렉토리 생성 등)
python scripts/manage.py setup

# 의존성 패키지 설치
python scripts/manage.py install

# 또는 수동 설치
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

2. 환경 변수 설정
```bash
cp .env.example .env
# .env 파일에 API 키 등 설정
```

3. 데이터베이스 초기화
```bash
python scripts/init_db.py
```

4. 실행
```bash
# 실시간 트레이딩
python main.py trade

# 계좌 잔고 조회
python main.py balance

# 조건에 맞는 종목 검색
python main.py find

# KRX 종목 목록 저장
python main.py list-stocks

# 백테스트 실행
python -m hantu_backtest.main
```

## 프로젝트 관리

프로젝트 관리를 위한 스크립트를 제공합니다:

```bash
# 환경 설정
python scripts/manage.py setup

# 의존성 패키지 설치
python scripts/manage.py install

# 데이터 백업
python scripts/manage.py backup

# 로그 파일 정리
python scripts/manage.py clean-logs

# 토큰 파일 초기화
python scripts/manage.py reset-tokens

# 테스트 실행
python scripts/manage.py test
```

## AI 협업 가이드

이 프로젝트는 AI 협업자와 효율적으로 작업하기 위한 구조를 제공합니다.

### AI 협업 디렉토리 구조

`.ai` 디렉토리는 AI 협업을 위한 다양한 자료와 템플릿을 포함합니다:
- `context/`: 프로젝트 컨텍스트 및 참조 파일 목록
- `templates/`: 작업 요청 및 응답 템플릿
- `workflows/`: 작업 유형별 워크플로우
- `history/`: 완료된 작업 히스토리

### AI 협업 명령어 체계

효율적인 AI 협업을 위한 간결한 명령어 체계를 제공합니다:

```
/init        # 기본 프로젝트 컨텍스트 로드
/api         # API 개발 작업 초기화
/strategy    # 전략 개발 작업 초기화
/trading     # 트레이딩 엔진 작업 초기화
/backtest    # 백테스트 작업 초기화
/help        # 전체 명령어 목록 표시
```

전체 명령어 목록과 상세 설명은 `.ai/templates/commands.md` 파일을 참조하세요.

### AI 협업 방법

1. **프로젝트 컨텍스트 이해**:
   ```
   /init
   ```
   또는
   ```
   AI에게: .ai/context/project_context.md 파일을 읽고 프로젝트를 이해해주세요.
   ```

2. **작업 유형별 파일 참조**:
   ```
   /api
   ```
   또는
   ```
   AI에게: .ai/context/file_references.json에서 [작업유형] 관련 파일들을 확인해주세요.
   ```

3. **워크플로우 기반 작업**:
   ```
   AI에게: .ai/workflows/[워크플로우명].md에 따라 작업을 진행해주세요.
   ```

4. **템플릿 기반 작업 요청**:
   ```
   AI에게: .ai/templates/task_request.md를 기반으로 작업 요청을 처리해주세요.
   ```

5. **작업 히스토리 기록**:
   ```
   /history [작업명]
   ```
   또는
   ```
   AI에게: 방금 완료한 작업을 .ai/history/ 디렉토리에 기록해주세요.
   ```

자세한 내용은 `.ai/README.md` 파일을 참조하세요.

## 개발 가이드

### 1. 새로운 전략 추가
- `hantu_backtest/strategies/` 디렉토리에 전략 클래스 추가
- `BacktestStrategy` 클래스를 상속받아 구현

### 2. 기술적 지표 추가
- `hantu_common/indicators/` 디렉토리에 지표 클래스 추가
- `Indicator` 기본 클래스를 상속받아 구현

### 3. 테스트 작성
- `tests/` 디렉토리에 테스트 코드 추가
- pytest를 사용한 단위 테스트 작성

## 환경 설정

### 모의투자 vs 실제투자
- 모의투자: `.env` 파일에서 `SERVER=virtual` 설정
- 실제투자: `.env` 파일에서 `SERVER=prod` 설정

### 토큰 관리
- 모의투자 토큰: `data/token/token_info_virtual.json`
- 실제투자 토큰: `data/token/token_info_real.json`

## 문제 해결

### API 토큰 오류
API 토큰 관련 오류가 발생할 경우:
```bash
# 토큰 파일 초기화 후 다시 시도
python scripts/manage.py reset-tokens
```

### 로그 확인
로그 파일을 통해 문제 분석:
```bash
tail -f logs/trading.log
```

## 의존성 패키지

- pandas==2.2.0
- numpy==1.26.3
- sqlalchemy==2.0.25
- matplotlib==3.8.2
- pyarrow==15.0.0
- 기타: requirements.txt 참조

## 프로젝트 문서

- [프로젝트 요약](PROJECT_SUMMARY.md): 구조 및 기능 요약
- [로드맵](ROADMAP.md): 개발 계획 및 로드맵

## 라이선스

MIT License 