# 한투 퀀트 프로젝트 컨텍스트

## 핵심 참조 파일
- PROJECT_SUMMARY.md: 프로젝트 구조와 기능 요약
- ROADMAP.md: 개발 계획 및 로드맵
- README.md: 주요 기능 및 사용 방법
- STATUS_REPORT.md: 현재 진행 상황 요약

## 주요 디렉토리
- core/: 핵심 기능 구현 
- hantu_common/: 공통 라이브러리
- hantu_backtest/: 백테스트 엔진
- scripts/: 실행 및 관리 스크립트

## 설정 관련 파일
- .env.example: 환경 변수 예시 (실제 값은 .env에 설정)
- core/config/settings.py: 기본 설정
- core/config/api_config.py: API 설정

## 보안 주의사항
- API 키와 민감정보는 항상 .env 파일에만 저장
- 토큰 파일은 data/token/ 디렉토리에 저장되며 git에 포함되지 않음
- 로깅 시 민감 정보 마스킹 필수

## 프로젝트 현황
- API 토큰 관리 개선됨 (모의/실제 투자 구분)
- 모멘텀 전략 기본 구현
- 백테스트 엔진 기본 구조 설계
- 자동 매매 기능 일부 구현

## 우선 작업 순위
1. API 인증 및 토큰 관리 안정화
2. 백테스트 엔진 완성
3. 모니터링 및 알림 시스템 구축 