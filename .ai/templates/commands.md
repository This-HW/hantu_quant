# 한투 퀀트 프로젝트 명령어 체계

## 기본 명령어

| 명령어 | 설명 | 실행 작업 |
|--------|------|-----------|
| `/init` | 프로젝트 기본 컨텍스트 로드 | PROJECT_SUMMARY.md, ROADMAP.md, .ai/context/project_context.md 파일 읽기 |
| `/status` | 프로젝트 현재 상태 확인 | STATUS_REPORT.md 읽기 및 요약 |
| `/help` | 사용 가능한 명령어 목록 표시 | 이 명령어 체계 표시 |

## 작업 유형별 명령어

| 명령어 | 설명 | 실행 작업 |
|--------|------|-----------|
| `/api` | API 개발 작업 초기화 | core/config/settings.py, core/config/api_config.py, core/api/kis_api.py 등 관련 파일 읽기 |
| `/strategy` | 전략 개발 작업 초기화 | core/strategy/momentum.py, hantu_backtest/strategies/momentum.py 등 관련 파일 읽기 |
| `/trading` | 트레이딩 엔진 작업 초기화 | core/trading/auto_trader.py, core/realtime/processor.py 등 관련 파일 읽기 |
| `/backtest` | 백테스트 작업 초기화 | hantu_backtest/core/engine.py, hantu_backtest/strategies/base.py 등 관련 파일 읽기 |
| `/security` | 보안 관련 작업 초기화 | .env.example, core/utils/log_utils.py, core/config/api_config.py 등 관련 파일 읽기 |

## 기능별 명령어

| 명령어 | 설명 | 실행 작업 |
|--------|------|-----------|
| `/fix-token` | 토큰 관련 문제 해결 | API 인증 및 토큰 관련 파일 읽고 문제 해결 방법 제시 |
| `/add-strategy <전략명>` | 새 전략 추가 | 전략 개발 워크플로우 로드 후 새 전략 템플릿 생성 |
| `/run-test` | 테스트 실행 방법 안내 | 테스트 관련 파일 확인 및 실행 방법 제시 |
| `/check-env` | 환경 설정 확인 | .env.example 파일 읽고 환경 설정 상태 확인 |

## 문서 관리 명령어

| 명령어 | 설명 | 실행 작업 |
|--------|------|-----------|
| `/doc-api <기능명>` | API 문서 생성/업데이트 | 지정된 API 기능에 대한 문서 생성 |
| `/doc-strategy <전략명>` | 전략 문서 생성/업데이트 | 지정된 전략에 대한 문서 생성 |
| `/history <작업명>` | 작업 히스토리 생성 | .ai/history/ 디렉토리에 작업 히스토리 생성 |
| `/update-summary` | 프로젝트 요약 업데이트 | PROJECT_SUMMARY.md 파일 업데이트 제안 |

## 사용 방법

1. 새 작업 시작 시 기본 컨텍스트 로딩:
   ```
   /init
   ```

2. 작업 유형에 따라 필요한 컨텍스트 로딩:
   ```
   /api
   ```

3. 특정 기능 수행:
   ```
   /add-strategy 볼린저밴드
   ```

4. 작업 완료 후 히스토리 기록:
   ```
   /history 볼린저밴드전략구현
   ```

이 명령어 체계를 사용하면 최소한의 텍스트로 필요한 컨텍스트를 로드하고 작업을 진행할 수 있습니다. 