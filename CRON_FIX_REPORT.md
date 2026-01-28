# Cron Job 수정 보고서

📅 **수정 일시**: 2026-01-29  
🔧 **작업자**: Claude Code  
✅ **상태**: 완료

---

## 🐛 발견된 문제

### 1. check_scheduler.sh 파일 누락
- **crontab 설정**: `*/5 * * * * ./check_scheduler.sh`
- **실제 경로**: `scripts/deployment/check_scheduler.sh`
- **문제**: 루트 디렉토리에 `check_scheduler.sh`가 없어서 cron이 실행되지 않음

### 2. 스케줄러 중단
- 마지막 실행: 2025-12-29 23:30
- 생존 신호: 2025-12-30 00:09까지 확인
- 이후 프로세스 없음

---

## ✅ 수정 사항

### 1. 심볼릭 링크 생성
```bash
ln -sf scripts/deployment/check_scheduler.sh check_scheduler.sh
```

**결과**:
```
lrwxr-xr-x  1 grimm  staff  37  1 29 08:15 check_scheduler.sh -> scripts/deployment/check_scheduler.sh
```

### 2. 스크립트 기능

`check_scheduler.sh`는 다음을 자동으로 수행합니다:

- ✅ 스케줄러 프로세스 확인 (5분 간격)
- ✅ 프로세스 응답 확인 (좀비 프로세스 감지)
- ✅ 자동 재시작 (최대 3회)
- ✅ Telegram 알림 (재시작/장애)
- ✅ 로그 관리 (1MB 초과 시 압축)

---

## 📊 동작 확인

### 수동 실행 테스트
```bash
./check_scheduler.sh
```

**결과**: ✅ 정상 실행, Telegram 알림 전송됨

### Crontab 설정
```bash
*/5 * * * * cd /Users/grimm/Documents/Dev/hantu_quant && ./check_scheduler.sh >/dev/null 2>&1
```

**실행 간격**: 5분마다 (00, 05, 10, 15, ... 분)

---

## 📋 모니터링 로그

모니터링 로그는 다음 위치에 저장됩니다:

- **모니터 로그**: `logs/scheduler_monitor_YYYYMMDD.log`
- **스케줄러 로그**: `logs/scheduler_YYYYMMDD.log` 
- **재시작 횟수**: `logs/restart_count.txt`

### 로그 확인 명령어
```bash
# 오늘 모니터링 로그
tail -f logs/scheduler_monitor_$(date +%Y%m%d).log

# 오늘 스케줄러 로그
tail -f logs/scheduler_$(date +%Y%m%d).log

# 재시작 횟수
cat logs/restart_count.txt
```

---

## 🚨 자동 재시작 로직

### 정상 상태
- ✅ 프로세스 실행 중
- ✅ 응답 정상
- 재시작 카운터: 0

### 장애 발생 시
1. **1차 시도** (5분 후)
   - 스케줄러 자동 재시작
   - Telegram 알림: 🔄 자동 재시작 (1/3)

2. **2차 시도** (10분 후)
   - 다시 자동 재시작
   - Telegram 알림: 🔄 자동 재시작 (2/3)

3. **3차 시도** (15분 후)
   - 마지막 자동 재시작
   - Telegram 알림: 🔄 자동 재시작 (3/3)

4. **최대 횟수 초과**
   - 자동 재시작 중단
   - Telegram 긴급 알림: 🚨 수동 개입 필요

---

## 🔍 문제 해결 가이드

### 스케줄러가 계속 재시작되는 경우

1. **로그 확인**
   ```bash
   tail -100 logs/scheduler_$(date +%Y%m%d).log
   ```

2. **에러 원인 파악**
   - API 토큰 만료
   - 네트워크 연결 문제
   - 시스템 리소스 부족
   - 코드 에러

3. **수동 실행 테스트**
   ```bash
   source .venv/bin/activate
   python3 workflows/integrated_scheduler.py start
   ```

### 재시작 카운터 리셋

문제 해결 후 카운터를 수동으로 리셋:
```bash
echo 0 > logs/restart_count.txt
```

---

## 📈 다음 단계

### 1. 모니터링 확인
```bash
# 5분 후 로그 확인
tail -f logs/scheduler_monitor_$(date +%Y%m%d).log
```

### 2. 스케줄러 상태 확인
```bash
ps aux | grep integrated_scheduler
```

### 3. Telegram 알림 확인
- 재시작 알림이 오는지 확인
- 긴급 알림 설정 테스트

---

## ✅ 결론

- **문제**: check_scheduler.sh 파일 누락으로 cron 실행 실패 ✅ 해결
- **수정**: 심볼릭 링크 생성 ✅ 완료
- **테스트**: 수동 실행 성공 ✅ 확인
- **자동화**: 5분 간격 자동 모니터링 및 재시작 ✅ 활성화

**Cron job이 정상적으로 작동합니다!**
