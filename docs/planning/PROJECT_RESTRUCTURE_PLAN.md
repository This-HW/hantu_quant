# 프로젝트 재구조화 계획

## 📊 현재 상태 분석

### 문제점
1. **루트 디렉토리 혼잡** - 50+ 파일/폴더
2. **문서 파일 분산** - 15개 마크다운 문서가 루트에 산재
3. **테스트 파일 혼재** - 10개 테스트 파일이 루트에 있음
4. **스크립트 분산** - 쉘 스크립트가 루트에 있음
5. **백업 파일 노출** - Git 히스토리 백업이 루트에 있음

### 현재 루트 디렉토리 파일들
```
📄 문서 (15개):
- ALGORITHM_UPGRADE_SUMMARY.md
- CODE_REVIEW_REPORT.md
- GIT_CLEANUP_COMPLETE.md
- GIT_RESET_PLAN.md
- LICENSE
- ML_AUTO_TRIGGER_SUMMARY.md
- PHASE_INTEGRATION_COMPLETE.md
- PREDICTION_ACCURACY_IMPROVEMENT.md
- PROJECT_COLLABORATION_RULES.md
- PROJECT_SUMMARY.md
- PROJECT_VALIDATION_SUMMARY.md
- README.md (유지)
- ROADMAP.md
- SECURITY.md
- STATUS_REPORT.md
- VIRTUAL_ACCOUNT_SETUP.md

🐍 Python 파일 (10개):
- main.py (유지)
- setup.py (유지)
- test_auto_trading.py
- test_enhanced_learning_system.py
- test_enhanced_screening.py
- test_full_integration.py
- test_health_check.py
- test_integrated_monitoring.py
- test_manual_trading.py
- test_trading_debug.py

📜 쉘 스크립트 (4개):
- check_scheduler.sh
- start_production.sh
- start_scheduler.sh
- stop_all.sh

🗄️ 백업/로그 (4개):
- git_detailed_history.txt
- git_history_backup.txt
- backtest.log
- scheduler.log

📦 설정 파일 (3개):
- requirements.txt (유지)
- package.json
- package-lock.json
```

---

## 🎯 새로운 디렉토리 구조

### 루트에 유지할 파일 (최소화)
```
hantu_quant/
├── README.md                 # 프로젝트 소개
├── LICENSE                   # 라이선스
├── requirements.txt          # Python 의존성
├── setup.py                  # 패키지 설정
├── main.py                   # 메인 진입점
├── .gitignore               # Git 제외 설정
├── .env.example             # 환경 변수 예제
```

### 새로운 폴더 구조
```
hantu_quant/
│
├── 📁 docs/                  # 📚 모든 문서
│   ├── README.md            # 문서 인덱스
│   ├── guides/              # 가이드 문서
│   │   ├── SECURITY.md
│   │   ├── VIRTUAL_ACCOUNT_SETUP.md
│   │   └── PROJECT_COLLABORATION_RULES.md
│   ├── reports/             # 보고서
│   │   ├── CODE_REVIEW_REPORT.md
│   │   ├── PROJECT_VALIDATION_SUMMARY.md
│   │   └── STATUS_REPORT.md
│   ├── specs/               # 기술 스펙
│   │   ├── ALGORITHM_UPGRADE_SUMMARY.md
│   │   ├── ML_AUTO_TRIGGER_SUMMARY.md
│   │   ├── PHASE_INTEGRATION_COMPLETE.md
│   │   └── PREDICTION_ACCURACY_IMPROVEMENT.md
│   ├── planning/            # 계획 문서
│   │   ├── ROADMAP.md
│   │   └── PROJECT_SUMMARY.md
│   └── archive/             # 아카이브
│       ├── GIT_CLEANUP_COMPLETE.md
│       └── GIT_RESET_PLAN.md
│
├── 📁 scripts/               # 🛠️ 모든 스크립트
│   ├── README.md            # 스크립트 사용법
│   ├── deployment/          # 배포 스크립트
│   │   ├── start_production.sh
│   │   ├── start_scheduler.sh
│   │   ├── stop_all.sh
│   │   └── check_scheduler.sh
│   ├── setup/               # 설정 스크립트
│   │   ├── simple_telegram_setup.py
│   │   └── setup_telegram_alerts.py
│   └── utils/               # 유틸리티 스크립트
│       └── ...
│
├── 📁 tests/                 # 🧪 모든 테스트
│   ├── README.md            # 테스트 가이드
│   ├── integration/         # 통합 테스트
│   │   ├── test_auto_trading.py
│   │   ├── test_full_integration.py
│   │   ├── test_health_check.py
│   │   └── test_integrated_monitoring.py
│   ├── unit/                # 단위 테스트
│   │   └── ...
│   └── manual/              # 수동 테스트
│       ├── test_enhanced_learning_system.py
│       ├── test_enhanced_screening.py
│       ├── test_manual_trading.py
│       └── test_trading_debug.py
│
├── 📁 logs/                  # 📝 로그 파일
│   └── .gitkeep             # Git 추적용
│
├── 📁 backups/               # 💾 백업 파일
│   ├── .gitkeep
│   └── git/                 # Git 백업
│       ├── git_history_backup.txt
│       └── git_detailed_history.txt
│
├── 📁 core/                  # 💼 핵심 코드 (유지)
├── 📁 workflows/             # 🔄 워크플로우 (유지)
├── 📁 config/                # ⚙️ 설정 (유지)
├── 📁 data/                  # 💾 데이터 (유지)
└── 📁 web-interface/         # 🌐 웹 인터페이스 (유지)
```

---

## 🔄 마이그레이션 계획

### Phase 1: 문서 정리 (docs/)
```bash
# 1. docs/ 폴더 구조 생성
mkdir -p docs/{guides,reports,specs,planning,archive}

# 2. 문서 이동
mv SECURITY.md docs/guides/
mv VIRTUAL_ACCOUNT_SETUP.md docs/guides/
mv PROJECT_COLLABORATION_RULES.md docs/guides/

mv CODE_REVIEW_REPORT.md docs/reports/
mv PROJECT_VALIDATION_SUMMARY.md docs/reports/
mv STATUS_REPORT.md docs/reports/

mv ALGORITHM_UPGRADE_SUMMARY.md docs/specs/
mv ML_AUTO_TRIGGER_SUMMARY.md docs/specs/
mv PHASE_INTEGRATION_COMPLETE.md docs/specs/
mv PREDICTION_ACCURACY_IMPROVEMENT.md docs/specs/

mv ROADMAP.md docs/planning/
mv PROJECT_SUMMARY.md docs/planning/

mv GIT_CLEANUP_COMPLETE.md docs/archive/
mv GIT_RESET_PLAN.md docs/archive/
```

### Phase 2: 스크립트 정리 (scripts/)
```bash
# 1. scripts/ 하위 폴더 생성
mkdir -p scripts/deployment

# 2. 쉘 스크립트 이동
mv check_scheduler.sh scripts/deployment/
mv start_production.sh scripts/deployment/
mv start_scheduler.sh scripts/deployment/
mv stop_all.sh scripts/deployment/
```

### Phase 3: 테스트 파일 정리 (tests/)
```bash
# 1. tests/ 하위 폴더 생성
mkdir -p tests/{integration,manual}

# 2. 테스트 파일 이동
mv test_auto_trading.py tests/integration/
mv test_full_integration.py tests/integration/
mv test_health_check.py tests/integration/
mv test_integrated_monitoring.py tests/integration/

mv test_enhanced_learning_system.py tests/manual/
mv test_enhanced_screening.py tests/manual/
mv test_manual_trading.py tests/manual/
mv test_trading_debug.py tests/manual/
```

### Phase 4: 백업/로그 정리
```bash
# 1. backups/ 폴더 생성
mkdir -p backups/git

# 2. 백업 파일 이동
mv git_history_backup.txt backups/git/
mv git_detailed_history.txt backups/git/

# 3. 로그 파일은 .gitignore 처리 (이미 되어 있음)
# backtest.log, scheduler.log는 logs/ 폴더로 자동 생성됨
```

### Phase 5: 웹 인터페이스 정리
```bash
# package.json, package-lock.json, node_modules는 web-interface/로 이동
mv package.json web-interface/ 2>/dev/null || true
mv package-lock.json web-interface/ 2>/dev/null || true
```

---

## 🔍 코드 참조 업데이트

### 영향받는 파일들 검색
```bash
# 스크립트 참조 검색
grep -r "start_production.sh" --include="*.py" --include="*.md" .
grep -r "stop_all.sh" --include="*.py" --include="*.md" .

# 테스트 파일 참조 검색
grep -r "test_auto_trading" --include="*.py" --include="*.md" .
grep -r "test_full_integration" --include="*.py" --include="*.md" .

# 문서 참조 검색
grep -r "SECURITY.md" --include="*.py" --include="*.md" .
grep -r "README.md" --include="*.py" --include="*.md" .
```

### 업데이트 필요한 파일들
1. **README.md** - 문서 링크 업데이트
2. **docs/README.md** - 문서 인덱스 생성
3. **scripts/README.md** - 스크립트 가이드 생성
4. **tests/README.md** - 테스트 가이드 생성
5. **.cursor/rules/** - 프로젝트 구조 규칙 업데이트
6. **.ai/context/** - AI 컨텍스트 업데이트

---

## 📋 프로젝트 구조 규칙

### 1. 루트 디렉토리 규칙
- **최소화 원칙**: 필수 파일만 유지
- **허용되는 파일**:
  - `README.md` - 프로젝트 소개
  - `LICENSE` - 라이선스
  - `requirements.txt` - Python 의존성
  - `setup.py` - 패키지 설정
  - `main.py` - 메인 진입점
  - `.gitignore` - Git 제외
  - `.env.example` - 환경 변수 예제

### 2. 문서 관리 규칙 (docs/)
- **가이드** (`docs/guides/`) - 사용자 가이드, 설정 가이드
- **보고서** (`docs/reports/`) - 코드 리뷰, 검증 보고서
- **스펙** (`docs/specs/`) - 기술 스펙, 구현 상세
- **계획** (`docs/planning/`) - 로드맵, 요약
- **아카이브** (`docs/archive/`) - 과거 문서

### 3. 스크립트 관리 규칙 (scripts/)
- **배포** (`scripts/deployment/`) - 배포 관련 스크립트
- **설정** (`scripts/setup/`) - 초기 설정 스크립트
- **유틸리티** (`scripts/utils/`) - 보조 스크립트

### 4. 테스트 관리 규칙 (tests/)
- **통합 테스트** (`tests/integration/`) - 전체 시스템 테스트
- **단위 테스트** (`tests/unit/`) - 개별 모듈 테스트
- **수동 테스트** (`tests/manual/`) - 디버그, 수동 확인용

### 5. 신규 파일 생성 규칙
- **문서**: 항상 `docs/` 하위에 카테고리별 배치
- **스크립트**: 항상 `scripts/` 하위에 용도별 배치
- **테스트**: 항상 `tests/` 하위에 타입별 배치
- **코드**: `core/`, `workflows/` 등 기존 구조 유지
- **백업**: `backups/` 폴더 사용

---

## ✅ 마이그레이션 체크리스트

### Phase 1: 문서 정리
- [ ] docs/ 폴더 구조 생성
- [ ] 문서 파일 이동
- [ ] docs/README.md 생성
- [ ] 링크 업데이트

### Phase 2: 스크립트 정리
- [ ] scripts/deployment/ 생성
- [ ] 쉘 스크립트 이동
- [ ] scripts/README.md 업데이트
- [ ] 실행 권한 확인

### Phase 3: 테스트 정리
- [ ] tests/integration/, tests/manual/ 생성
- [ ] 테스트 파일 이동
- [ ] import 경로 수정
- [ ] tests/README.md 생성

### Phase 4: 백업 정리
- [ ] backups/git/ 생성
- [ ] 백업 파일 이동
- [ ] .gitignore 확인

### Phase 5: 웹 인터페이스 정리
- [ ] package.json 이동 (필요시)
- [ ] node_modules 확인

### Phase 6: 검증
- [ ] 모든 테스트 실행 성공
- [ ] 프로그램 정상 실행
- [ ] 문서 링크 정상 작동
- [ ] Git 커밋 및 푸시

---

## 🎯 예상 효과

### Before (현재)
```
루트 파일: 50+개
문서 위치: 분산됨
테스트 위치: 루트에 혼재
관리 난이도: 높음
```

### After (재구조화 후)
```
루트 파일: 7개 (필수만)
문서 위치: docs/ 하위 카테고리별 정리
테스트 위치: tests/ 하위 타입별 정리
관리 난이도: 낮음
신규 파일 규칙: 명확함
```

---

**작성일**: 2025-10-04
**예상 소요 시간**: 30-45분
**위험도**: 낮음 (백업 완료 + 단계별 검증)
