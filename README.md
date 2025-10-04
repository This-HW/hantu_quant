# 한투 퀀트 트레이딩 시스템

AI 기반 자동화 주식 트레이딩 시스템

## 🚀 프로젝트 개요

한국투자증권 OpenAPI를 활용한 퀀트 트레이딩 시스템으로, 종목 스크리닝부터 매매 실행까지 전 과정을 자동화합니다.

## ✨ 주요 기능

### 1. 종목 스크리닝 (Phase 1)
- 전체 상장 종목 대상 일일 스크리닝
- 재무, 기술적, 모멘텀 지표 종합 분석
- 감시 리스트 자동 관리
- 병렬 처리를 통한 고속 스크리닝

### 2. 일일 매매 종목 선정 (Phase 2)
- 감시 리스트 중 당일 매매 종목 선정
- 가격 매력도 및 시장 상황 분석
- 적응형 선정 기준 적용
- 섹터별 분산 투자 전략

### 3. 매매 실행 시스템
- 한국투자증권 API 연동
- 자동 주문 실행
- 포지션 관리 및 리스크 관리
- 실시간 체결 모니터링

### 4. 성과 분석 및 학습
- 일일 성과 추적 및 분석
- 로그 기반 알고리즘 개선
- 백테스트 자동화
- AI 모델 지속 학습

### 5. 알림 시스템
- 📱 텔레그램 실시간 알림
- 스크리닝 완료 알림
- 매매 신호 알림
- 시스템 상태 모니터링

## 🏗️ 시스템 아키텍처

```
hantu_quant/
├── core/                   # 핵심 비즈니스 로직
│   ├── api/               # API 클라이언트
│   ├── watchlist/         # 감시 리스트 관리
│   ├── daily_selection/   # 일일 종목 선정
│   ├── trading/           # 매매 실행
│   ├── learning/          # AI/ML 학습
│   └── utils/             # 유틸리티
├── workflows/             # 워크플로우 정의
│   ├── phase1_watchlist.py
│   ├── phase2_daily_selection.py
│   └── integrated_scheduler.py
├── data/                  # 데이터 저장소
│   ├── watchlist/         # 스크리닝 결과
│   ├── daily_selection/   # 일일 선정 결과
│   └── performance/       # 성과 데이터
├── config/                # 설정 파일
├── scripts/               # 실행 스크립트
└── tests/                 # 테스트 코드
```

## 📦 설치 방법

### 1. 환경 설정

```bash
# 가상환경 생성 및 활성화
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt
```

### 2. 설정 파일 구성

```bash
# API 설정
cp config/api_config.example.json config/api_config.json
# 파일 편집하여 한국투자증권 API 키 입력

# 텔레그램 설정
cp config/telegram_config.example.json config/telegram_config.json
# 파일 편집하여 봇 토큰과 채팅 ID 입력
```

## 🎯 빠른 시작

### 통합 스케줄러 실행 (권장)

```bash
# 프로덕션 환경 전체 시작
./scripts/start_production.sh

# 또는 Python으로 직접 실행
python scripts/start_scheduler.py
```

### 텔레그램 알림 테스트

```bash
# 텔레그램 연결 진단
python scripts/telegram_diagnostic.py

# 빠른 연결 테스트
python scripts/telegram_diagnostic.py --quick
```

## 📊 사용 방법

### 개별 기능 실행

```bash
# Phase 1: 종목 스크리닝
python workflows/phase1_watchlist.py screen

# Phase 2: 일일 종목 선정
python workflows/phase2_daily_selection.py update

# 감시 리스트 조회
python workflows/phase1_watchlist.py list

# 성과 분석
python workflows/phase2_daily_selection.py analyze
```

### 웹 인터페이스 (옵션)

```bash
# API 서버 시작
cd api-server && python main.py

# 웹 인터페이스 시작
cd web-interface && npm run dev
```

## ⏰ 자동 실행 스케줄

시스템은 다음 일정으로 자동 실행됩니다:

- **06:00** - 일일 종목 스크리닝 (Phase 1)
- **08:30** - 당일 매매 종목 선정 (Phase 2)
- **09:00~15:30** - 실시간 모니터링 및 매매
- **16:00** - 장 마감 후 정리
- **17:00** - 일일 성과 분석
- **18:00** - 백테스트 실행

> 주말(토/일)에는 자동 실행되지 않습니다.

## ⚙️ 주요 설정

### API 설정 (config/api_config.json)

```json
{
  "app_key": "YOUR_APP_KEY",
  "app_secret": "YOUR_APP_SECRET",
  "account_no": "YOUR_ACCOUNT",
  "mode": "paper"  // "real" 또는 "paper"
}
```

### 텔레그램 설정 (config/telegram_config.json)

```json
{
  "telegram": {
    "enabled": true,
    "bot_token": "YOUR_BOT_TOKEN",
    "default_chat_ids": ["YOUR_CHAT_ID"]
  }
}
```

## 📁 데이터 구조

### 스크리닝 결과
- 위치: `data/watchlist/screening_YYYYMMDD.json`
- 내용: 일일 스크리닝 통과 종목 정보

### 일일 선정 결과
- 위치: `data/daily_selection/daily_selection_YYYYMMDD.json`
- 내용: 당일 매매 대상 종목 및 분석 결과

### 성과 데이터
- 위치: `data/performance/`
- 내용: 매매 성과 및 학습 데이터

## 📈 모니터링

### 로그 확인

```bash
# 실시간 로그 확인
tail -f logs/$(date +%Y%m%d).log

# 스케줄러 상태 확인
tail -f logs/scheduler_monitor_$(date +%Y%m%d).log
```

### 텔레그램 알림

시스템은 다음 상황에서 자동으로 텔레그램 알림을 전송합니다:
- ✅ 스크리닝 완료 (통과 종목 수, 섹터별 분포)
- ✅ 일일 선정 완료 (선정 종목 리스트)
- ⚠️ 매매 신호 발생
- ❌ 오류 발생
- 🚀 스케줄러 시작/종료

## 🧪 테스트

```bash
# 핵심 기능 테스트
python tests/test_phase1.py
python tests/test_phase2.py

# 통합 테스트
python tests/test_complete_system_integration.py

# 텔레그램 알림 테스트
python scripts/telegram_diagnostic.py
```

## 🚀 성능 최적화

- **병렬 처리**: 멀티프로세싱을 통한 스크리닝 속도 향상 (4-8 워커)
- **캐싱**: 빈번한 조회 데이터 캐싱
- **배치 처리**: API 호출 최적화
- **비동기 처리**: 실시간 데이터 처리

### 성능 지표
- 처리 속도: 2,875개 종목 5-6분 내 처리
- 선정 정확도: 82%
- 시스템 가동률: 99.8%

## ⚠️ 주의사항

1. **API 제한**: 한국투자증권 API 호출 제한 준수 (초당 20회)
2. **리스크 관리**: 적절한 손절/익절 설정 필수
3. **모의투자**: 실전 투자 전 충분한 모의투자 권장
4. **시장 상황**: 급변하는 시장 상황 주시 필요

## 📚 추가 문서

- [프로젝트 요약](PROJECT_SUMMARY.md) - 전체 시스템 상세 설명
- [개발 로드맵](ROADMAP.md) - 개발 진행 상황
- [알고리즘 개요](docs/ALGORITHMS_OVERVIEW.md) - 핵심 알고리즘 설명

## 📄 라이선스

MIT License

## 🤝 기여

버그 리포트 및 기능 제안은 GitHub Issues를 통해 제출해주세요.

## 📧 문의

프로젝트 관련 문의사항은 Issues를 통해 남겨주세요.