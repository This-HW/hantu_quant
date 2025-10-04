# 🚀 자동 매매 시작 가이드

한투 퀀트 시스템의 가상계좌 자동매매 기능을 활용하는 방법을 안내합니다.

## 📋 시작하기 전 준비사항

### 1. 한국투자증권 가상계좌 설정
- 한국투자증권 가상계좌 개설 완료
- `config/api_config.json`에서 가상계좌 설정 확인:
  ```json
  {
    "server": "virtual",  // ✅ 가상계좌 모드
    "app_key": "your_app_key",
    "app_secret": "your_app_secret"
  }
  ```

### 2. 텔레그램 알림 설정 (선택)
- `config/telegram_config.json` 파일 설정
- 매매 알림을 실시간으로 받을 수 있습니다

## 🎯 자동 매매 실행 방법

### 방법 1: 직접 실행 (권장)
```bash
# 자동 매매 시작
python scripts/auto_trading.py start

# 상태 확인
python scripts/auto_trading.py status

# 수동 중지
python scripts/auto_trading.py stop
```

### 방법 2: 스케줄러 통한 자동 실행
```bash
# 통합 스케줄러 시작 (자동으로 09:00에 매매 시작)
python workflows/integrated_scheduler.py start
```

## ⚙️ 매매 설정 옵션

### 기본 설정 (계좌의 10%씩 투자)
```bash
python scripts/auto_trading.py start
```

### 고급 설정 옵션
```bash
python scripts/auto_trading.py start \
  --max-positions 10 \               # 최대 보유 종목수 (기본: 10개)
  --position-method account_pct \    # 포지션 크기 방법 (account_pct, fixed, risk_based, kelly)
  --position-pct 0.10 \             # 계좌 대비 비율 (기본: 10%)
  --position-size 1000000 \         # 고정 투자금 (fixed 모드용)
  --stop-loss 0.05 \                # 손절매 비율 (기본: 5%)
  --take-profit 0.10 \              # 익절매 비율 (기본: 10%)
  --max-trades 20 \                 # 일일 최대 거래 (기본: 20건)
  --use-kelly \                     # Kelly Criterion 사용
  --kelly-multiplier 0.25           # Kelly 보수 계수 (기본: 0.25)
```

### 포지션 크기 결정 방식

1. **account_pct (권장)**: 계좌 총 자산의 일정 비율
   - 계좌가 1,000만원이면 종목당 100만원 투자
   - 손실/수익에 따라 포지션 크기 자동 조정

2. **fixed**: 고정 금액
   - 항상 동일한 금액 투자
   - 단순하지만 자금 효율성 떨어질 수 있음

3. **risk_based**: 리스크 기반 사이징
   - 손절매 거리에 따라 포지션 크기 조정
   - 동일한 리스크로 다양한 종목 투자

4. **kelly**: Kelly Criterion 적용
   - 과거 성과 기반 최적 포지션 크기 계산
   - 수학적으로 가장 효율적이지만 변동성 큼

## 📊 매매 로직

### 매수 조건
1. **AI 선별 종목**: Phase 2에서 선정된 일일 매매 종목
2. **거래량 조건**: 평균 거래량 대비 1.5배 이상
3. **가격 안정성**: 일일 변동률 30% 이하
4. **포지션 제한**: 최대 보유 종목수 이내
5. **거래 한도**: 일일 최대 거래횟수 이내

### 매도 조건
1. **손절매**: -5% 손실 시 자동 매도
2. **익절매**: +10% 수익 시 자동 매도  
3. **시간 기반**: 15:00 이후 시장가 매도
4. **리스크 관리**: 급등락 시 보호 매도

## 🕒 매매 시간표

| 시간 | 작업 | 설명 |
|------|------|------|
| 06:00 | 스크리닝 | AI가 2,875개 종목 분석 |
| 08:30 | 종목 선정 | 당일 매매 대상 10개 선정 |
| 09:00 | 매매 시작 | 자동 매수/매도 시작 |
| 15:30 | 매매 중지 | 자동 매매 종료 |
| 17:00 | 성과 분석 | 일일 결과 분석 및 알림 |

## 💰 리스크 관리

### 기본 설정
- **최대 포지션**: 10개 종목 (분산 투자)
- **포지션 크기**: 계좌 자산의 10%씩 (동적 조정)
- **일일 한도**: 최대 20건 거래 (과다 거래 방지)
- **손절매**: 5% 손실 시 자동 매도
- **총 위험도**: 계좌 대비 2% 이하
- **Kelly Criterion**: 과거 성과 기반 최적 포지션 사이징

### 안전 장치
- **가상계좌 전용**: 실제 손실 없음
- **실시간 모니터링**: 매매 현황 실시간 추적
- **긴급 중지**: Ctrl+C로 즉시 중지 가능
- **텔레그램 알림**: 모든 매매 내역 실시간 알림

## 📱 실시간 모니터링

### 텔레그램 알림 메시지
```
📈 자동 매수 체결
종목: 삼성전자 (005930)
수량: 14주
가격: 71,000원
투자금: 994,000원
목표가: 78,100원 (+10.0%)
손절가: 67,450원 (-5.0%)
```

### 상태 확인 명령어
```bash
# 실시간 상태 확인
python scripts/auto_trading.py status
```

## 🔧 문제 해결

### 자주 발생하는 문제

1. **API 토큰 오류**
   ```
   해결: config/api_config.json의 app_key, app_secret 확인
   ```

2. **일일 선정 파일 없음**
   ```
   해결: 먼저 스크리닝(Phase 1)과 선정(Phase 2) 실행
   python workflows/phase1_watchlist.py
   python workflows/phase2_daily_selection.py
   ```

3. **장 시간 외 실행**
   ```
   해결: 09:00~15:30 (평일)에만 매매 실행됨
   ```

4. **매매 중지 방법**
   ```bash
   # 즉시 중지
   python scripts/auto_trading.py stop
   
   # 또는 Ctrl+C (실행 중인 터미널에서)
   ```

## 📈 성과 확인

### 일일 성과 리포트
- 매일 17:00에 자동 생성
- 실현 손익 (매도한 종목)
- 평가 손익 (보유 종목)
- 종합 성과 분석

### 매매 일지 확인
```bash
# 매매 기록 확인
ls data/trades/
cat data/trades/trade_journal_20250911.json
```

## ⚠️ 주의사항

1. **가상계좌 확인**: 반드시 `"server": "virtual"` 설정 확인
2. **투자금 관리**: 가상계좌 잔고 충분히 확보
3. **시스템 점검**: 정전, 네트워크 장애 대비
4. **수수료 고려**: 실제 매매 시 수수료 발생
5. **시장 휴장일**: 주말, 공휴일에는 매매 없음

## 🚀 고급 설정

### 커스텀 매매 설정
```python
# scripts/auto_trading.py 수정
config = TradingConfig(
    max_positions=15,        # 종목수 증가
    position_size=500000,    # 종목당 50만원
    stop_loss_pct=0.03,      # 3% 손절
    take_profit_pct=0.15,    # 15% 익절
    max_trades_per_day=30    # 일일 30건
)
```

### 백그라운드 실행
```bash
# nohup으로 백그라운드 실행
nohup python scripts/auto_trading.py start > auto_trading.log 2>&1 &

# 프로세스 확인
ps aux | grep auto_trading.py
```

## 💡 Tips

1. **시작 전 테스트**: 소액으로 먼저 테스트
2. **로그 확인**: `logs/` 폴더에서 상세 로그 확인
3. **정기 점검**: 주간 성과 리뷰 및 설정 조정
4. **시장 분석**: 급변동 시기에는 수동 조정 고려

---

## 🆘 지원

문제 발생 시:
1. 로그 파일 확인: `logs/auto_trading_YYYYMMDD.log`
2. 텔레그램 알림 확인
3. GitHub Issues에 문의

**⚡ 내일부터 AI가 선별한 종목으로 자동매매를 시작하세요!**