---
name: deploy
description: 배포 파이프라인. 검증 → 배포 → 모니터링 순서로 진행합니다.
argument-hint: [대상] [환경] (예: app staging, infra production)
allowed-tools: Read, Bash, Glob, Grep, Task
---

# 배포 실행

**즉시 실행하세요. 설명하지 말고 바로 실행합니다.**

배포 대상: $ARGUMENTS

---

## 1단계: 대상 파악

$ARGUMENTS 분석:
- `app` → 애플리케이션 배포
- `infra` → 인프라 배포
- 환경: `staging` | `production`

## 2단계: 사전 검증

### 애플리케이션 배포 시
```bash
# 빌드 확인
npm run build / go build / docker build

# 테스트 확인
npm test / pytest / go test
```

### 인프라 배포 시
```bash
# terraform plan 확인
terraform plan -out=tfplan

# 보안 검사 (있으면)
tfsec . / checkov -d .
```

## 3단계: 배포 실행

### 앱 배포
```bash
# Docker 기반
docker-compose up -d

# 또는 직접 실행
systemctl restart [서비스명]
```

### 인프라 배포
```bash
terraform apply tfplan
```

## 4단계: 배포 후 확인

```bash
# 헬스체크
curl -f http://localhost:[port]/health

# 로그 확인
journalctl -u [서비스명] -f --no-pager -n 50
```

---

## 출력 형식

### 배포 결과
| 항목 | 상태 |
|------|------|
| 대상 | [app/infra] |
| 환경 | [staging/production] |
| 결과 | [성공/실패] |

### 검증 결과
[헬스체크, 로그 확인 결과]

### 롤백 안내 (실패 시)
[롤백 방법 안내]
