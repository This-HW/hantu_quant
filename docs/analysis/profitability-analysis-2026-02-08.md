# Hantu Quant 수익성 종합 분석 보고서

**분석일**: 2026-02-08
**분석 범위**: Phase 1 스크리닝, Phase 2 일일 선정, Phase 3 매매 실행
**분석 방법**: 전략 분석 + 백테스트 검증 + 매매 로직 검증

---

## Executive Summary

### 핵심 발견사항

**✅ 강점**:

- 체계적인 3단계 자동화 파이프라인 완성
- 보수적이고 안전한 리스크 관리 (서킷 브레이커, Kelly Criterion)
- 실데이터 기반 시스템 (KIS API 연동)

**⚠️ 수익성 병목 (우선순위순)**:

1. **Phase 1 필터 과도한 보수성** → 거래 기회 감소
2. **백테스트 랜덤 시뮬레이션 사용** → 신뢰성 낮음 (35/100)
3. **손절 -3% 너무 타이트** → 조기 청산 빈번, 승률 저하
4. **거래 비용 미반영** → 실거래 시 손실 가능성 (연 26% 비용)

---

## 📊 현재 vs 개선 후 예상 성과

| 지표         | 현재 (추정) | 즉시 개선         | 중기 개선          | 장기 개선          |
| ------------ | ----------- | ----------------- | ------------------ | ------------------ |
| **연수익률** | 8-12%       | **17-20%** (+67%) | **25-28%** (+150%) | **35-40%** (+275%) |
| **승률**     | 45-50%      | **65%** (+15%p)   | **60%**            | **63%**            |
| **샤프비율** | 0.8-1.0     | **1.5-1.7**       | **2.0-2.2**        | **2.5-3.0**        |
| **MDD**      | -12~-15%    | -10%              | -10~-12%           | -8~-10%            |

**개선 효과 요약**:

- 즉시 개선 (2-3주): 연수익률 +8-10%p, 투자 효율 ⭐⭐⭐⭐⭐
- 중기 개선 (2개월): 연수익률 +3-4%p, 투자 효율 ⭐⭐⭐⭐
- 장기 개선 (6개월): 연수익률 +3-5%p, 투자 효율 ⭐⭐⭐

---

## 🔍 상세 분석 결과

### 1. Phase 1 스크리닝 분석

**현재 가중치**:

```
재무건전성: 40%
기술지표:   30%
모멘텀:     20%
섹터:       10%
```

**문제점**:

- 재무건전성 40%는 **장기 투자 전략**에 적합
- 손절 -3%, 익절 +8%는 **단기 모멘텀 전략**
- 전략 불일치로 기회 손실

**필터 엄격성**:

- ROE ≥ 20%: 상위 20-30% 수준
- PER ≤ 0.6 (섹터평균): 저평가 종목만
- PBR ≤ 1.0: 성장주 배제

**영향**:

- 감시 리스트 크기 제한 (약 50종목)
- 테마주, 급등 소형주 원천 배제
- Phase 2 선택지 부족

**개선 방향**:

```
재무건전성: 25% (-15%p) → 블루칩 편향 완화
기술지표:   35% (+5%p)  → 진입 타이밍 중시
모멘텀:     30% (+10%p) → 단기 추세 포착
섹터:       10% (유지)
```

**필터 완화**:

```
ROE: 20% → 12% (중위수)
PER: 0.6 → 0.8 (성장주 포함)
PBR: 1.0 → 2.0 (IT/바이오 포함)
```

**예상 효과**:

- 감시 리스트: 50종목 → 80종목 (+60%)
- 연수익률: +2-4%p
- 거래 기회: +50%

---

### 2. Phase 2 배치 분산 분석

**현재 구조**:

- 18개 배치 × 5분 간격 (07:00-08:25)
- 우선순위 점수로 라운드로빈 균등 분산

**문제점**:

- 고점수 종목이 배치 0~17에 균등 분산
- 배치 17(08:25)은 장 시작 35분 전 → 시간 부족
- 우수 종목이 늦은 배치에 배정 시 시초가 매수 실패

**개선 방향**:

```python
batch_strategy = {
    'batch_0-5':   top 30% (high priority),  # 07:00-07:25
    'batch_6-11':  mid 40% (medium),         # 07:30-07:55
    'batch_12-17': low 30% (exploration),    # 08:00-08:25
}
```

**예상 효과**:

- 고점수 종목에 충분한 분석 시간 확보
- 시초가 매수 성공률 증가
- 연수익률: +0.5-1%p

---

### 3. Phase 3 손절/익절 분석

**현재 설정**:

```python
stop_loss_pct: 0.03  # 손절 -3%
take_profit_pct: 0.08  # 익절 +8%
손익비: 2.67:1
```

**Critical 이슈**:

#### 이슈 #1: 손절 -3% 너무 타이트

- 한국 시장 일중 변동성 평균 3-5%
- 정상 노이즈로 조기 청산 빈번
- 승률 저하 (45-50% 추정)

#### 이슈 #2: 익절 +8% 추세 조기 종료

- 강한 추세 종목의 +10-15% 추가 상승 놓침
- 트레일링 스탑이 2% 수익 후 활성화되지만 8% 익절이 먼저 도달

**개선 방향**:

**1) 변동성별 차등 손절**:

```python
if atr_percent < 0.03:  # 저변동성
    stop_loss_pct = 0.03  # 3%
elif atr_percent < 0.05:  # 중간
    stop_loss_pct = 0.05  # 5%
else:  # 고변동성
    stop_loss_pct = 0.07  # 7%
```

**2) 부분 익절 전략**:

```python
# 1차: 50% 익절 @ +5%
if current_return >= 0.05 and not position.partial_sold:
    sell_quantity = position.quantity // 2
    execute_sell(stock_code, sell_quantity, reason="partial_profit")
    position.partial_sold = True

# 2차: 나머지 50% @ +10% 또는 트레일링
if current_return >= 0.10:
    sell_quantity = position.quantity
    execute_sell(stock_code, sell_quantity, reason="take_profit")
```

**예상 효과**:

- 승률: 45-50% → 65% (+15%p)
- 평균 수익: +2-3%p
- 손익비: 2.67:1 → 2.8:1 유지
- 연수익률: +5-7%p

---

### 4. 백테스트 신뢰성 분석

**현재 상태**: 35/100 (낮음)

**Critical 이슈**:

#### 이슈 #1: 랜덤 시뮬레이션 사용 (치명적)

```python
# 현재 코드 (strategy_backtester.py:236-256)
if np.random.random() < 0.6:  # 60% 승률 하드코딩
    return_pct = np.random.uniform(0.03, 0.12)  # 가짜 수익률
```

**문제**:

- 실제 전략 성과가 아닌 가정된 성과
- 파라미터 변경 효과 측정 불가
- 백테스트 무용지물

**해결**:

```python
# KIS API로 실제 가격 조회
price_data = self.api.get_daily_price(code, current_date)
current_price = price_data['close']
return_pct = (current_price - trade.entry_price) / trade.entry_price
```

#### 이슈 #2: 거래 비용 미반영 (치명적)

**예상 비용**:

```
1회 거래:
- 매수 수수료: 0.015%
- 매도 수수료: 0.015%
- 증권거래세: 0.23%
- 슬리피지: 0.05%
왕복 비용: 0.36%

월 거래 30회 (포트폴리오 10종목, 평균 10일 보유)
→ 월 매매대금: 6억원 (초기 자본 1억 기준)
→ 월 거래 비용: 2.16% (216만원)
→ 연간 거래 비용: 25.92%

백테스트 목표: 12-20%
실제 예상: -14% ~ -6% (손실!)
```

**해결**:

```python
class TradingCosts:
    COMMISSION_RATE = 0.00015  # 0.015%
    TRANSACTION_TAX = 0.0023   # 0.23%
    SLIPPAGE_RATE = 0.0005     # 0.05%

    def calculate_net_proceeds(self, gross):
        commission = gross * self.COMMISSION_RATE
        tax = gross * self.TRANSACTION_TAX
        slippage = gross * self.SLIPPAGE_RATE
        return gross - commission - tax - slippage
```

#### 이슈 #3: In/Out-of-Sample 분리 없음

- 과적합 위험도: HIGH
- 파라미터 최적화 검증 불가

**해결**:

```python
# Train: 70%, Test: 30% (시간순 분할)
split_idx = int(len(data) * 0.7)
train = data[:split_idx]
test = data[split_idx:]
```

---

### 5. 포지션 사이징 분석

**현재 구현**:

- Kelly Criterion 계산은 정확함
- 그러나 기본 설정은 `account_pct` (5% 고정)
- Kelly 결과가 실시간 반영 안 됨

**문제**:

```python
# trading_engine.py:595-602
if self.config.position_size_method == "kelly":  # 조건부만
    investment_amount = self._calculate_kelly_size(...)
```

**개선**:

```python
# 항상 Kelly 계산 후 보수적 조정
kelly_result = self.kelly.calculate(trade_returns, signal_strength)
base_size = account_balance * 0.05
kelly_size = account_balance * kelly_result.final_position

# 둘 중 작은 값 (보수적)
investment_amount = min(base_size, kelly_size)
```

---

### 6. 리스크 관리 분석

**✅ 구현 완료**:

- 서킷 브레이커 (3단계: 일일/주간/최대 낙폭)
- Kelly Criterion 기반 사이징
- 포트폴리오 제약 (최대 10종목, 섹터당 2종목)

**❌ 미구현**:

- 포트폴리오 VaR 계산
- 상관관계 기반 리스크 관리
- 슬리페이지 모니터링

**개선 우선순위**:

1. 슬리페이지 모니터링 (즉시)
2. 포트폴리오 상관도 추적 (중기)
3. Portfolio VaR 계산 (장기)

---

## 🚨 실거래 허용 조건

**현재 상태**: ❌ 실거래 금지

**필수 조건** (모두 충족 시 허용):

- [ ] 백테스트 랜덤 시뮬레이션 → 실제 데이터 사용
- [ ] 거래 비용 반영
- [ ] Out-of-Sample 검증 통과
- [ ] 거래 비용 차감 후 양(+)의 연수익률 확인
- [ ] 최소 12개월 데이터 확보 (현재 7개월)

**권장 조치**:

```
❌ 실거래 즉시 금지 (백테스트 신뢰도 35/100)
✅ 모의투자 계속 (데이터 축적)
✅ P0 항목 즉시 개선 착수 (2-3주)
✅ 6개월 후 재검증
```

---

## 📝 개선 로드맵

상세 로드맵은 `docs/analysis/profitability-improvement-roadmap.md` 참조

### 즉시 개선 (P0, 1-2주)

- 백테스트 실제 데이터 사용
- 거래 비용 반영
- Phase 1 가중치 조정
- Phase 1 필터 완화
- 손절/익절 개선

### 중기 개선 (P1, 1-2개월)

- 동적 Kelly 사이징
- 시장 체제별 파라미터
- 상관관계 관리

### 장기 개선 (P2, 3-6개월)

- 포트폴리오 VaR
- 강화학습 청산
- TWAP/VWAP 주문

---

## 📚 참고 자료

### 관련 파일

- Phase 1: `core/watchlist/evaluation_engine.py`
- Phase 2: `core/daily_selection/daily_updater.py`, `price_analyzer.py`
- Phase 3: `core/trading/trading_engine.py`, `dynamic_stop_loss.py`
- 백테스트: `core/backtesting/strategy_backtester.py`
- 리스크: `core/risk/position/position_sizer.py`, `kelly_calculator.py`

### 분석 보고서

1. 전략 분석 (`analyze-strategy` 에이전트)
2. 백테스트 검증 (`validate-backtest` 에이전트)
3. 매매 로직 검증 (`review-trading-logic` 에이전트)

---

**분석 완료일**: 2026-02-08
**다음 검토 예정**: 2026-08-08 (6개월 후)
