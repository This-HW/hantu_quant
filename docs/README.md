# 📚 프로젝트 문서

한투 퀀트 트레이딩 시스템의 문서 저장소입니다.

## 📁 문서 구조

### [guides/](guides/) - 사용자 가이드
프로젝트 설정 및 사용 방법 안내
- [SECURITY.md](guides/SECURITY.md) - 보안 설정 및 best practices
- [VIRTUAL_ACCOUNT_SETUP.md](guides/VIRTUAL_ACCOUNT_SETUP.md) - 모의투자 계좌 설정 가이드
- [PROJECT_COLLABORATION_RULES.md](guides/PROJECT_COLLABORATION_RULES.md) - 프로젝트 협업 규칙

### [reports/](reports/) - 프로젝트 보고서
코드 리뷰, 검증 결과, 상태 보고서
- [CODE_REVIEW_REPORT.md](reports/CODE_REVIEW_REPORT.md) - 코드 리뷰 결과
- [PROJECT_VALIDATION_SUMMARY.md](reports/PROJECT_VALIDATION_SUMMARY.md) - 프로젝트 검증 요약
- [STATUS_REPORT.md](reports/STATUS_REPORT.md) - 현재 상태 보고서

### [specs/](specs/) - 기술 스펙
시스템 기능 및 알고리즘 상세 설명
- [ALGORITHM_UPGRADE_SUMMARY.md](specs/ALGORITHM_UPGRADE_SUMMARY.md) - 알고리즘 업그레이드 내역
- [ML_AUTO_TRIGGER_SUMMARY.md](specs/ML_AUTO_TRIGGER_SUMMARY.md) - ML 자동 트리거 시스템
- [PHASE_INTEGRATION_COMPLETE.md](specs/PHASE_INTEGRATION_COMPLETE.md) - Phase 통합 완료 보고
- [PREDICTION_ACCURACY_IMPROVEMENT.md](specs/PREDICTION_ACCURACY_IMPROVEMENT.md) - 예측 정확도 개선

### [planning/](planning/) - 계획 문서
로드맵, 프로젝트 요약, 계획 문서
- [PROJECT_SUMMARY.md](planning/PROJECT_SUMMARY.md) - 프로젝트 전체 요약
- [ROADMAP.md](planning/ROADMAP.md) - 개발 로드맵
- [PROJECT_RESTRUCTURE_PLAN.md](planning/PROJECT_RESTRUCTURE_PLAN.md) - 프로젝트 재구조화 계획

### [archive/](archive/) - 아카이브
과거 문서 및 히스토리 기록
- [GIT_CLEANUP_COMPLETE.md](archive/GIT_CLEANUP_COMPLETE.md) - Git 정리 완료 보고
- [GIT_RESET_PLAN.md](archive/GIT_RESET_PLAN.md) - Git 리셋 계획

## 📖 문서 작성 규칙

### 신규 문서 생성 시
1. **적절한 카테고리 선택**
   - 사용자 가이드 → `guides/`
   - 보고서 → `reports/`
   - 기술 스펙 → `specs/`
   - 계획 문서 → `planning/`
   - 과거 문서 → `archive/`

2. **파일명 규칙**
   - 대문자와 언더스코어 사용: `EXAMPLE_DOCUMENT.md`
   - 명확하고 설명적인 이름 사용
   - 날짜가 필요한 경우: `REPORT_20251004.md`

3. **문서 구조**
   - 제목은 명확하게 (H1)
   - 목차 포함 (복잡한 문서의 경우)
   - 작성일, 작성자, 버전 정보 포함

### 문서 관리
- 문서 업데이트 시 변경 이력 기록
- 중요 문서는 백업 유지
- 오래된 문서는 `archive/`로 이동

## 🔗 관련 링크
- [메인 README](../README.md) - 프로젝트 메인 페이지
- [테스트 가이드](../tests/README.md) - 테스트 실행 방법
- [스크립트 가이드](../scripts/README.md) - 스크립트 사용법
