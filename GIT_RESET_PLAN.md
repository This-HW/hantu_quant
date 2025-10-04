# Git 저장소 재설정 계획

## 🚨 문제 상황
- `config/telegram_config.json`에 Telegram bot token과 chat ID가 포함됨
- 원격 저장소(GitHub)에 이미 푸시됨
- 86개 커밋 히스토리에 노출됨

## ✅ 선택한 해결 방법: Git 저장소 새로 시작

### 단계별 실행 계획

#### 1단계: 백업 및 준비
```bash
# 현재 상태 백업
cd /Users/grimm/Documents/Dev/hantu_quant
cp -r .git .git.backup

# 중요 커밋 메시지 저장
git log --oneline > git_history_backup.txt
git log --pretty=format:"%H|%an|%ad|%s" > git_detailed_history.txt
```

#### 2단계: 토큰 즉시 무효화
- [x] Telegram Bot Token 재발급 필요
- [ ] BotFather에서 `/revoke` 실행
- [ ] 새 token 발급 및 설정

#### 3단계: GitHub 저장소 처리
**옵션 A: 기존 저장소 삭제 후 재생성 (추천)**
```bash
# GitHub에서 hantu_quant 저장소 완전 삭제
# GitHub UI: Settings → Danger Zone → Delete this repository

# 새 저장소 생성
# GitHub UI: New repository → hantu_quant
```

**옵션 B: 저장소 이름 변경**
```bash
# GitHub에서 hantu_quant → hantu_quant_old로 이름 변경
# 새 hantu_quant 저장소 생성
```

#### 4단계: 로컬 Git 초기화
```bash
# 현재 디렉토리에서
cd /Users/grimm/Documents/Dev/hantu_quant

# 기존 .git 제거
rm -rf .git

# 새 Git 저장소 초기화
git init
git branch -M main

# 첫 커밋 (깨끗한 상태)
git add .
git commit -m "🎉 Initial commit: AI-powered automated trading system

## 시스템 개요
- 한국투자증권 API 기반 자동 매매 시스템
- AI 예측 정확도 60-65% 목표
- 완전 자동화: 선정 → 매매 → 학습 → 백테스트

## 주요 기능
### Phase 1: 감시 리스트 스크리닝
- 병렬 처리로 2,700개 종목 분석
- 기본적/기술적 분석 기반 필터링

### Phase 2: 일일 종목 선정
- 가격 매력도 분석
- 추세 추종 필터 (방안 A)
- 멀티 전략 앙상블 (방안 C)

### Phase 3: 자동 매매
- 보수적 전략 (5% 포지션, 3% 손절)
- 계좌 기반 동적 포지션 사이징
- 실시간 모니터링

### Phase 4: 학습 및 개선
- 일일/주간/자동 ML 학습
- 성과 기반 파라미터 자동 조정
- 주간 백테스트 (매주 금요일)

## 기술 스택
- Python 3.11
- SQLite (로컬 DB)
- 한국투자증권 REST/WebSocket API
- Telegram (알림)

## 보안
- 모든 민감 정보는 환경 변수 관리
- .gitignore로 토큰 파일 보호
- 자세한 내용: SECURITY.md

## 문서
- CODE_REVIEW_REPORT.md - 코드 검증 보고서
- PROJECT_VALIDATION_SUMMARY.md - 검증 요약
- SECURITY.md - 보안 가이드
- PREDICTION_ACCURACY_IMPROVEMENT.md - 예측 정확도 개선
- PHASE_INTEGRATION_COMPLETE.md - 3단계 통합 완료

## 라이선스
Private - 개인 프로젝트"

# 원격 저장소 연결
git remote add origin https://github.com/This-HW/hantu_quant.git

# 푸시 (force push)
git push -u origin main --force
```

#### 5단계: 검증
```bash
# 원격 저장소 확인
git log --oneline
git remote -v

# GitHub에서 히스토리 확인
# commit 1개만 있어야 함
```

### 예상 소요 시간
- 백업: 1분
- Telegram token 재발급: 5분
- GitHub 저장소 재설정: 2분
- 로컬 Git 초기화: 2분
- 푸시 및 검증: 1분

**총 약 10-15분**

### 주의사항
1. **토큰 재발급 먼저** - 기존 token은 이미 노출되었으므로 무효화 필수
2. **백업 확인** - .git.backup 폴더가 정상적으로 생성되었는지 확인
3. **Force push** - 기존 히스토리를 덮어쓰므로 신중히 실행
4. **.env 파일 확인** - APP_KEY, APP_SECRET이 .env에 있는지 확인

### 롤백 방법
문제 발생 시:
```bash
# .git 복원
rm -rf .git
mv .git.backup .git

# 원격 저장소 다시 연결
git remote add origin https://github.com/This-HW/hantu_quant.git
```

---

## 🎯 실행 후 확인사항

- [ ] GitHub에 커밋 1개만 존재
- [ ] config/telegram_config.json이 히스토리에 없음
- [ ] 새 Telegram token으로 알림 정상 작동
- [ ] .env 파일에 APP_KEY, APP_SECRET 존재
- [ ] 프로그램 정상 실행

---

**작성일**: 2025-10-04
**긴급도**: 🚨 높음 (Telegram token 이미 노출됨)
