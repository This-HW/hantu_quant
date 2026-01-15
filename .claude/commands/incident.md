---
name: incident
description: 인시던트 대응 파이프라인. 복구 최우선으로 대응 → 복구 → 분석 순으로 진행합니다.
argument-hint: [상황 설명]
allowed-tools: Read, Bash, Glob, Grep, Task, WebSearch
---

# 인시던트 대응 실행

**즉시 실행하세요. 복구가 먼저입니다!**

상황: $ARGUMENTS

---

## 1단계: 심각도 판단 (즉시)

| 심각도 | 증상 | 대응 |
|--------|------|------|
| **SEV1** | 서비스 전체 다운 | 즉시 롤백 |
| **SEV2** | 주요 기능 장애 | 15분 내 복구 |
| **SEV3** | 부분 기능 저하 | 1시간 내 대응 |

## 2단계: 상황 파악

```bash
# 서비스 상태 확인
systemctl status [서비스명]

# 최근 로그 확인
journalctl -u [서비스명] -n 100 --no-pager | tail -50

# 에러 로그 확인
grep -i error /path/to/logs/*.log | tail -20
```

## 3단계: 즉각 대응

### SEV1/SEV2: 롤백 우선
```bash
# 이전 버전으로 롤백
git checkout [이전커밋]
docker-compose up -d

# 또는 systemctl로 이전 버전 실행
```

### SEV3: 원인별 대응
- 리소스 부족 → 스케일업/재시작
- 외부 서비스 장애 → 폴백 활성화
- 코드 버그 → 핫픽스

## 4단계: 안정화 확인

```bash
# 헬스체크
curl -f http://localhost:[port]/health

# 에러율 확인 (5분간)
grep -c ERROR /path/to/logs/*.log
```

## 5단계: 사후 분석 (안정화 후)

안정화 확인 후:
1. 근본 원인 분석
2. 타임라인 정리
3. 재발 방지 대책

---

## 출력 형식

### 인시던트 요약
| 항목 | 내용 |
|------|------|
| 심각도 | SEV[1/2/3] |
| 증상 | [증상] |
| 원인 | [원인] |
| 복구 시간 | [N분] |

### 대응 내역
[수행한 조치들]

### 후속 조치
[필요한 작업]
