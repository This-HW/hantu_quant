# 🛠️ 스크립트 가이드

시스템 배포, 설정, 유틸리티 스크립트 모음입니다.

## 📁 스크립트 구조

### [deployment/](deployment/) - 배포 스크립트
시스템 시작, 중지, 모니터링 스크립트

#### 주요 스크립트

**start_production.sh**
- 프로덕션 환경 전체 시작
- 통합 스케줄러 실행
```bash
./scripts/deployment/start_production.sh
```

**start_scheduler.sh**
- 통합 스케줄러만 시작
- 백그라운드 실행 지원
```bash
./scripts/deployment/start_scheduler.sh
```

**stop_all.sh**
- 실행 중인 모든 프로세스 종료
- 안전한 종료 프로세스
```bash
./scripts/deployment/stop_all.sh
```

**check_scheduler.sh**
- 스케줄러 상태 확인
- 프로세스 헬스 체크
```bash
./scripts/deployment/check_scheduler.sh
```

### [setup/](setup/) - 설정 스크립트
초기 설정 및 환경 구성 스크립트 (추후 추가 예정)

### [utils/](utils/) - 유틸리티 스크립트
보조 도구 및 헬퍼 스크립트 (추후 추가 예정)

## 🚀 사용 방법

### 기본 워크플로우

1. **시스템 시작**
   ```bash
   # 프로덕션 환경 시작
   ./scripts/deployment/start_production.sh
   ```

2. **상태 확인**
   ```bash
   # 스케줄러 상태 체크
   ./scripts/deployment/check_scheduler.sh
   ```

3. **시스템 종료**
   ```bash
   # 모든 프로세스 종료
   ./scripts/deployment/stop_all.sh
   ```

### 스크립트 실행 권한

스크립트 실행 전 권한 확인:
```bash
# 실행 권한 부여
chmod +x scripts/deployment/*.sh

# 현재 권한 확인
ls -la scripts/deployment/
```

## ⚙️ 환경 변수

스크립트 실행 시 필요한 환경 변수:

```bash
# .env 파일에 설정
APP_KEY=your_app_key
APP_SECRET=your_app_secret
ACCOUNT_NUMBER=your_account
SERVER=virtual  # 또는 prod
```

## 📝 로그 확인

스크립트 실행 로그 확인:
```bash
# 실시간 로그 확인
tail -f logs/$(date +%Y%m%d).log

# 스케줄러 로그 확인
tail -f logs/scheduler_monitor_$(date +%Y%m%d).log
```

## 🔧 문제 해결

### 스크립트 실행 안 됨
```bash
# 1. 실행 권한 확인
ls -la scripts/deployment/

# 2. 권한 부여
chmod +x scripts/deployment/*.sh

# 3. 줄바꿈 문자 확인 (Windows에서 작성한 경우)
dos2unix scripts/deployment/*.sh
```

### 프로세스가 종료되지 않음
```bash
# 강제 종료
pkill -9 -f "python.*integrated_scheduler"
```

## 📖 신규 스크립트 작성 규칙

### 1. 위치 선택
- 배포 관련 → `deployment/`
- 설정 관련 → `setup/`
- 보조 도구 → `utils/`

### 2. 파일명 규칙
- 소문자와 언더스코어 사용: `example_script.sh`
- 명확하고 설명적인 이름
- 확장자 명시: `.sh`, `.py` 등

### 3. 스크립트 템플릿

```bash
#!/bin/bash
# Script: example_script.sh
# Description: 스크립트 설명
# Usage: ./scripts/deployment/example_script.sh

set -e  # 에러 발생 시 중단

# 환경 변수 로드
source .env 2>/dev/null || true

# 스크립트 내용
echo "Starting example script..."

# 에러 처리
trap 'echo "Error occurred. Exiting..."; exit 1' ERR

# 실행 코드
# ...

echo "Script completed successfully"
```

### 4. 문서화
- 스크립트 상단에 주석으로 설명 추가
- 사용법 예제 포함
- 이 README에 새 스크립트 정보 추가

## 🔗 관련 링크
- [메인 README](../README.md) - 프로젝트 메인 페이지
- [테스트 가이드](../tests/README.md) - 테스트 실행 방법
- [문서 인덱스](../docs/README.md) - 전체 문서 목록
