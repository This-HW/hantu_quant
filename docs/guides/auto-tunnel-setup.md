# SSH 터널 자동 시작 설정 가이드

## 개요

로컬 개발 환경에서 hantu_quant 프로젝트 디렉토리로 이동할 때마다 SSH 터널을 자동으로 시작합니다.

## 설정 방법

### 1. zsh 사용자 (macOS 기본)

`~/.zshrc` 파일에 다음 추가:

```bash
# Hantu Quant SSH Tunnel Auto-Start
if [[ "$PWD" == *"hantu_quant"* ]]; then
    # 터널이 실행 중이 아니면 시작
    if ! lsof -i :15432 >/dev/null 2>&1; then
        echo "Starting SSH tunnel for Hantu Quant..."
        ~/Documents/Dev/hantu_quant/scripts/db-tunnel.sh start >/dev/null 2>&1 &
    fi
fi
```

### 2. bash 사용자

`~/.bash_profile` 파일에 다음 추가:

```bash
# Hantu Quant SSH Tunnel Auto-Start
if [[ "$PWD" == *"hantu_quant"* ]]; then
    # 터널이 실행 중이 아니면 시작
    if ! lsof -i :15432 >/dev/null 2>&1; then
        echo "Starting SSH tunnel for Hantu Quant..."
        ~/Documents/Dev/hantu_quant/scripts/db-tunnel.sh start >/dev/null 2>&1 &
    fi
fi
```

### 3. 설정 적용

```bash
# zsh 사용자
source ~/.zshrc

# bash 사용자
source ~/.bash_profile
```

## 동작 방식

1. **디렉토리 진입 시 자동 실행**
   - `cd ~/Documents/Dev/hantu_quant` 실행 시 자동으로 터널 시작
   - 프로젝트 하위 디렉토리로 이동해도 동작

2. **중복 실행 방지**
   - 15432 포트가 이미 사용 중이면 스킵
   - 로그 파일: `logs/auto-tunnel.log`

3. **백그라운드 실행**
   - 터미널 블로킹 없이 백그라운드에서 실행
   - 출력은 로그 파일로 리다이렉트

## 수동 제어

자동 시작이 활성화되어도 수동 제어 가능:

```bash
# 터널 상태 확인
./scripts/db-tunnel.sh status

# 터널 중지
./scripts/db-tunnel.sh stop

# 터널 재시작
./scripts/db-tunnel.sh restart
```

## 트러블슈팅

### 터널이 자동으로 시작되지 않음

```bash
# 1. 로그 확인
cat logs/auto-tunnel.log

# 2. 수동 실행 테스트
./scripts/db-tunnel.sh start

# 3. SSH 키 확인
ls -la ~/.ssh/id_rsa
```

### 프로젝트가 아닌 곳에서도 실행됨

- 조건문 확인: `[[ "$PWD" == *"hantu_quant"* ]]`
- 프로젝트 경로가 정확한지 확인

### 터미널 시작이 느려짐

- 백그라운드 실행 확인: `&` 기호 확인
- 출력 리다이렉트 확인: `>/dev/null 2>&1`

## 권장 설정

### Option 1: 간단한 버전 (추천)

위의 기본 설정 사용 (zsh/bash 직접 설정)

### Option 2: 스크립트 버전

`auto-start-tunnel.sh` 스크립트 사용:

```bash
# ~/.zshrc 또는 ~/.bash_profile에 추가
if [[ "$PWD" == *"hantu_quant"* ]]; then
    ~/Documents/Dev/hantu_quant/scripts/auto-start-tunnel.sh
fi
```

**장점**: 로그 관리 자동화
**단점**: 스크립트 파일 의존성

## 제거 방법

자동 시작을 비활성화하려면:

1. `~/.zshrc` 또는 `~/.bash_profile` 열기
2. Hantu Quant 관련 설정 삭제
3. `source ~/.zshrc` 또는 `source ~/.bash_profile` 실행

## 참고

- 서버 환경에서는 이 설정 불필요 (서버는 localhost 직접 연결)
- 원격 서버 주소 변경 시 `scripts/db-tunnel.sh` 업데이트 필요
