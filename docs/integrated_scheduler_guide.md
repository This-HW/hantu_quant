# 통합 스케줄러 사용 가이드

## 📋 개요

**통합 스케줄러**는 Phase 1(감시 리스트 구축)과 Phase 2(일일 선정 시스템)를 자동으로 연결하여 실행하는 시스템입니다.

## 🕐 실행 스케줄

### 자동 실행 스케줄
| 작업 | 실행 시간 | 설명 |
|------|-----------|------|
| **일간 스크리닝** | 매일 06:00 | Phase 1 전체 시장 스크리닝 → 감시 리스트 업데이트 |
| **일일 업데이트** | Phase 1 완료 후 자동 실행 | Phase 2 감시 리스트 → 일일 매매 리스트 선정 |
| **마감 후 정리** | 매일 16:00 | 일일 리포트 생성 및 성과 분석 |

### 실행 순서
```
06:00 - 일간 스크리닝 시작 (Phase 1)
  ↓
06:XX - 스크리닝 완료 후 즉시 Phase 2 실행
  ↓
06:XX - 일일 업데이트 완료
  ↓
16:00 - 마감 후 정리 작업
```

## 🚀 사용법

### 1. 스케줄러 시작
```bash
python workflows/integrated_scheduler.py start
```
- 백그라운드에서 실행됩니다
- `Ctrl+C`로 중지할 수 있습니다

### 2. 스케줄러 상태 확인
```bash
python workflows/integrated_scheduler.py status
```
- 현재 실행 상태 확인
- 마지막 실행 시간 조회
- 예정된 작업 목록 확인

### 3. 즉시 실행 (테스트용)
```bash
python workflows/integrated_scheduler.py run
```
- 스케줄 무시하고 즉시 실행
- 테스트 및 디버깅 용도

### 4. 스케줄러 중지
```bash
python workflows/integrated_scheduler.py stop
```
- 실행 중인 스케줄러 중지

## 🔄 워크플로우 상세

### Phase 1: 일간 스크리닝 (06:00)
1. **전체 시장 스크리닝**
   - 3000+ 종목 분석
   - 재무/기술/모멘텀 기반 평가
   - 상위 종목 선별

2. **감시 리스트 업데이트**
   - 기존 감시 리스트와 비교
   - 신규 우량 종목 추가
   - 부실 종목 제거

3. **통계 정보 출력**
   - 감시 리스트 요약
   - 섹터별 분포
   - 점수 분포

### Phase 2: 일일 업데이트 (Phase 1 완료 후)
1. **가격 매력도 분석**
   - 감시 리스트 종목 분석
   - 기술적 지표 계산
   - 매력도 점수 산출

2. **매매 리스트 선정**
   - 필터링 기준 적용
   - 시장 상황 고려
   - 포지션 사이징

3. **결과 저장**
   - 일일 선정 결과 저장
   - 메타데이터 업데이트
   - 알림 발송

### 마감 후 정리 (16:00)
1. **일일 리포트 생성**
   - 감시 리스트 리포트
   - 성과 분석 리포트
   - 통계 정보 요약

2. **데이터 정리**
   - 임시 파일 정리
   - 로그 파일 정리
   - 백업 파일 생성

## 📊 모니터링

### 로그 확인
```bash
tail -f logs/integrated_scheduler.log
```

### 실행 결과 확인
```bash
# 감시 리스트 확인
python workflows/phase1_watchlist.py list

# 일일 선정 결과 확인
python workflows/phase2_daily_selection.py show --latest
```

## ⚠️ 주의사항

### 1. 시간 설정
- **06:00 시작**: 장 시작 전 충분한 시간 확보
- **Phase 1 → Phase 2**: 순차적 실행으로 데이터 일관성 보장
- **16:00 정리**: 장 마감 후 정리 작업

### 2. 오류 처리
- Phase 1 실패 시 Phase 2 건너뛰기
- 자동 재시도 메커니즘
- 상세한 오류 로깅

### 3. 리소스 관리
- 메모리 사용량 모니터링
- API 호출 제한 준수
- 동시 실행 방지

## 🔧 설정 변경

### 스케줄 시간 변경
`workflows/integrated_scheduler.py` 파일에서:
```python
# 일간 스크리닝 시간 변경
schedule.every().day.at("06:00").do(self._run_daily_screening)

# 마감 후 정리 시간 변경
schedule.every().day.at("16:00").do(self._run_market_close_tasks)
```

### 대기 시간 조정
Phase 1 완료 후 Phase 2 실행 전 대기 시간:
```python
time.sleep(2)  # 2초 대기 (조정 가능)
```

## 🚨 트러블슈팅

### 1. 스케줄러가 실행되지 않는 경우
```bash
# 프로세스 확인
ps aux | grep integrated_scheduler

# 로그 확인
tail -f logs/integrated_scheduler.log
```

### 2. Phase 1 실패 시
```bash
# 수동으로 Phase 1 실행
python workflows/phase1_watchlist.py screen

# 감시 리스트 상태 확인
python workflows/phase1_watchlist.py list
```

### 3. Phase 2 실패 시
```bash
# 수동으로 Phase 2 실행
python workflows/phase2_daily_selection.py update --force

# 선정 결과 확인
python workflows/phase2_daily_selection.py show --latest
```

## 📈 성과 모니터링

### 일일 성과 확인
```bash
# 오늘 선정 결과
python workflows/phase2_daily_selection.py show --latest

# 최근 7일 성과
python workflows/phase2_daily_selection.py performance --period 7
```

### 감시 리스트 품질 확인
```bash
# 감시 리스트 통계
python workflows/phase1_watchlist.py list

# 리포트 생성
python workflows/phase1_watchlist.py report
```

## 🔄 백업 및 복원

### 데이터 백업
```bash
# 감시 리스트 백업
cp data/watchlist/watchlist.json data/watchlist/watchlist_backup_$(date +%Y%m%d).json

# 일일 선정 결과 백업
cp -r data/daily_selection data/daily_selection_backup_$(date +%Y%m%d)
```

### 복원
```bash
# 감시 리스트 복원
cp data/watchlist/watchlist_backup_20240115.json data/watchlist/watchlist.json

# 일일 선정 결과 복원
cp -r data/daily_selection_backup_20240115 data/daily_selection
```

## 📞 지원

### 문제 발생 시
1. 로그 파일 확인
2. 상태 명령어로 현재 상태 확인
3. 수동 실행으로 문제 구간 파악
4. 필요 시 데이터 백업 및 복원

### 성능 최적화
- 메모리 사용량 모니터링
- 실행 시간 최적화
- API 호출 효율화

---

**마지막 업데이트**: 2025-07-10  
**버전**: 1.0.0  
**담당자**: AI Assistant 