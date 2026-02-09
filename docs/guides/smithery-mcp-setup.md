# Smithery MCP API 설정 가이드

> kis-code-assistant-mcp가 재시작될 때마다 인증을 요구하는 문제 해결

---

## 문제 상황

- `/mcp` 명령 실행 시 매번 인증 필요
- MCP 서버 재시작 시 세션 초기화
- 원인: 인증 토큰이 메모리에만 저장되고 영구 저장소에 저장되지 않음

---

## 해결 방법

### 로컬 환경 설정

#### 방법 1: 자동 스크립트 사용 (권장)

```bash
# 프로젝트 루트에서 실행
./scripts/setup-smithery-env.sh
```

실행 후 Claude Code를 재시작하세요.

#### 방법 2: 수동 설정

`.env` 파일에 직접 추가:

```bash
echo "" >> .env
echo "# Smithery.ai MCP API Key" >> .env
echo "SMITHERY_API_KEY=d9e6136a-ca80-4f6f-8387-eb00980831b2" >> .env
```

현재 셸에 적용:

```bash
export SMITHERY_API_KEY=d9e6136a-ca80-4f6f-8387-eb00980831b2
# 또는
source .env
```

---

### 서버 환경 설정 (자동 배포)

#### GitHub Secrets 설정

1. GitHub 저장소 → **Settings** → **Secrets and variables** → **Actions**
2. **New repository secret** 클릭
3. 다음 정보 입력:
   - **Name**: `SMITHERY_API_KEY`
   - **Secret**: `d9e6136a-ca80-4f6f-8387-eb00980831b2`
4. **Add secret** 클릭

#### 배포 시 자동 적용

GitHub Secrets 설정 후 다음 배포부터 자동으로 서버 `.env`에 추가됩니다:

```bash
# 로컬에서 push
git push origin main

# CI/CD가 자동으로:
# 1. 서버 .env에 SMITHERY_API_KEY 추가/업데이트
# 2. systemd 서비스 재시작 (자동으로 .env 로드)
```

---

### 수동 서버 설정 (긴급 시)

서버에 직접 SSH 접속하여 설정:

```bash
# 서버 접속
ssh ubuntu@158.180.87.156

# Production 환경
cd /opt/hantu_quant
echo "" >> .env
echo "# Smithery.ai MCP API Key" >> .env
echo "SMITHERY_API_KEY=d9e6136a-ca80-4f6f-8387-eb00980831b2" >> .env

# Dev 환경 (있는 경우)
cd /home/ubuntu/hantu_quant_dev
echo "" >> .env
echo "# Smithery.ai MCP API Key" >> .env
echo "SMITHERY_API_KEY=d9e6136a-ca80-4f6f-8387-eb00980831b2" >> .env

# 서비스 재시작 (환경 변수 로드)
sudo systemctl restart hantu-scheduler
sudo systemctl restart hantu-api
```

---

## 검증

### 로컬 검증

```bash
# 환경 변수 확인
echo $SMITHERY_API_KEY

# 출력: d9e6136a-ca80-4f6f-8387-eb00980831b2
```

Claude Code를 재시작하고 `/mcp` 명령 실행 시 인증 없이 바로 연결되어야 합니다.

### 서버 검증

```bash
# 서버에서
source .env
echo $SMITHERY_API_KEY

# systemd 서비스가 환경 변수를 로드하는지 확인
sudo systemctl show hantu-scheduler --property=Environment
sudo systemctl show hantu-api --property=Environment
```

---

## 동작 원리

### 로컬 환경

```
.env 파일
  ↓
export SMITHERY_API_KEY=...
  ↓
.claude/settings.json
  ↓ ${SMITHERY_API_KEY} 참조
mcp-proxy가 Smithery.ai 서버 인증
  ↓
세션 유지 (재시작 시에도 .env에서 재로드)
```

### 서버 환경

```
GitHub Secrets
  ↓
CI/CD 배포 (deploy.yml)
  ↓
서버 .env 파일 업데이트
  ↓
systemd EnvironmentFile 로드
  ↓
서비스 시작 시 자동으로 환경 변수 설정
```

---

## 트러블슈팅

### 여전히 인증을 요구하는 경우

1. **환경 변수 확인**:

   ```bash
   echo $SMITHERY_API_KEY
   ```

2. **Claude Code 재시작**:
   - 환경 변수 변경 후 반드시 재시작 필요

3. **settings.json 확인**:

   ```bash
   cat .claude/settings.json | grep -A 5 kis-code-assistant
   ```

   출력에 `"SMITHERY_API_KEY": "${SMITHERY_API_KEY}"` 포함되어 있어야 함

4. **.env 파일 확인**:
   ```bash
   grep SMITHERY_API_KEY .env
   ```

### 서버에서 MCP 서버 연결 실패

서버 환경에서는 MCP 서버가 필요하지 않을 수 있습니다. MCP는 주로 로컬 개발 환경에서 사용됩니다.

만약 서버에서도 필요하다면:

- Claude Code가 서버에 설치되어 있는지 확인
- systemd 서비스에서 MCP 서버를 사용하는지 확인

---

## 참고

- **API 키 보안**: .env 파일은 .gitignore에 포함되어 있어 Git에 커밋되지 않음
- **GitHub Secrets**: 암호화되어 저장되며 로그에 노출되지 않음
- **환경 변수 우선순위**: 시스템 환경 변수 > .env 파일
- **서비스 재시작**: .env 변경 시 systemd 서비스 재시작 필요

---

## 관련 파일

- `.claude/settings.json` - MCP 서버 설정
- `.env` - 환경 변수 저장
- `scripts/setup-smithery-env.sh` - 자동 설정 스크립트
- `.github/workflows/deploy.yml` - CI/CD 배포 스크립트
- `deploy/hantu-scheduler.service` - 스케줄러 systemd 설정
- `deploy/hantu-api.service` - API 서버 systemd 설정
