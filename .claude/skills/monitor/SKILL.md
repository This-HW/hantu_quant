---
name: monitor
description: 시스템 모니터링. 현재 상태를 확인하고 이상 징후를 탐지합니다.
argument-hint: [대상: app, infra, db, 또는 빈칸=전체]
allowed-tools: Read, Bash, Glob, Grep, Task
---

# 시스템 모니터링 실행

**즉시 실행하세요. 설명하지 말고 바로 실행합니다.**

대상: $ARGUMENTS (없으면 전체)

---

## 1단계: 시스템 상태 확인 (즉시 실행)

### 서비스 상태
```bash
# systemd 서비스
systemctl status [서비스명] --no-pager

# Docker 컨테이너
docker ps -a

# 프로세스 확인
ps aux | grep [프로세스명]
```

### 리소스 사용량
```bash
# CPU/메모리
top -bn1 | head -20

# 디스크
df -h

# 네트워크
netstat -tuln | grep LISTEN
```

## 2단계: 로그 확인

```bash
# 최근 에러 로그
journalctl -u [서비스명] -p err -n 20 --no-pager

# 애플리케이션 로그
tail -50 /path/to/app/logs/*.log | grep -i error
```

## 3단계: 상태 판정

| 메트릭 | 정상 | 경고 | 위험 |
|--------|------|------|------|
| CPU | <70% | 70-90% | >90% |
| Memory | <70% | 70-90% | >90% |
| Disk | <80% | 80-95% | >95% |
| Error Rate | <1% | 1-5% | >5% |

## 4단계: 이상 발견 시 대응

- 🟡 경고: 원인 분석 후 보고
- 🔴 위험: `/incident` 실행 권고

---

## 출력 형식

### 시스템 상태: [🟢 정상 / 🟡 경고 / 🔴 위험]

### 리소스 현황
| 메트릭 | 현재 | 기준 | 상태 |
|--------|------|------|------|
| CPU | [N%] | <70% | [🟢/🟡/🔴] |
| Memory | [N%] | <70% | [🟢/🟡/🔴] |
| Disk | [N%] | <80% | [🟢/🟡/🔴] |

### 서비스 상태
[서비스별 상태]

### 최근 이슈
[에러 로그 요약 또는 "없음"]

### 권장 조치
[필요한 조치 또는 "없음"]
