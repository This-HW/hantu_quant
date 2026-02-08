# 수익성 개선 로드맵

**작성일**: 2026-02-08
**목표**: 연수익률 8-12% → 35-40% (3단계 개선)

---

## 📋 개선 단계별 요약

| 단계          | 기간    | 작업량   | 수익률 개선 | 투자 효율  |
| ------------- | ------- | -------- | ----------- | ---------- |
| **즉시 (P0)** | 2-3주   | 5개 작업 | +8-10%p     | ⭐⭐⭐⭐⭐ |
| **중기 (P1)** | 1-2개월 | 6개 작업 | +3-4%p      | ⭐⭐⭐⭐   |
| **장기 (P2)** | 3-6개월 | 3개 작업 | +3-5%p      | ⭐⭐⭐     |

---

## 🚀 Phase P0: 즉시 개선 (2-3주)

**목표**: 연수익률 8-12% → **17-20%** (+67%)

### 작업 1: 백테스트 실제 데이터 사용

**현재 문제**:

```python
# strategy_backtester.py:236-256
if np.random.random() < 0.6:  # 랜덤 승률
    return_pct = np.random.uniform(0.03, 0.12)  # 가짜 수익률
```

**해결 방안**:

```python
def _check_exits(self, portfolio, current_date):
    for code, trade in portfolio.items():
        # 실제 가격 데이터 조회
        price_data = self.api.get_daily_price(code, current_date)
        current_price = price_data['close']

        # 실제 수익률 계산
        return_pct = (current_price - trade.entry_price) / trade.entry_price

        # 손절/익절 판단
        if return_pct <= -self.stop_loss_pct:
            # 실제 청산
            self._close_position(code, current_price, "stop_loss")
```

**담당**: Dev/fix-bugs
**파일**: `core/backtesting/strategy_backtester.py`
**소요**: 2-3일
**우선순위**: ⭐⭐⭐⭐⭐ (치명적)

---

### 작업 2: 거래 비용 반영

**현재 문제**:

- commission, slippage, 증권거래세 미반영
- 예상 연간 비용: **26%** (목표 수익률보다 큼!)

**해결 방안**:

```python
# trading_costs.py (신규 생성)
class TradingCosts:
    COMMISSION_RATE = 0.00015  # 0.015%
    TRANSACTION_TAX = 0.0023   # 0.23% (매도만)
    SLIPPAGE_RATE = 0.0005     # 0.05%

    def calculate_buy_cost(self, price, quantity):
        """매수 비용 계산"""
        gross = price * quantity
        commission = gross * self.COMMISSION_RATE
        slippage = gross * self.SLIPPAGE_RATE
        return gross + commission + slippage

    def calculate_sell_proceeds(self, price, quantity):
        """매도 수령액 계산"""
        gross = price * quantity
        commission = gross * self.COMMISSION_RATE
        tax = gross * self.TRANSACTION_TAX
        slippage = gross * self.SLIPPAGE_RATE
        return gross - commission - tax - slippage

# StrategyBacktester에 통합
self.trading_costs = TradingCosts()
net_proceeds = self.trading_costs.calculate_sell_proceeds(price, quantity)
```

**담당**: Dev/implement-code
**파일**: `core/backtesting/trading_costs.py` (신규), `strategy_backtester.py` (수정)
**소요**: 1일
**우선순위**: ⭐⭐⭐⭐⭐ (치명적)

---

### 작업 3: Phase 1 가중치 조정

**현재**:

```python
# evaluation_engine.py:22-25
fundamental: 0.4  # 재무건전성
technical: 0.3    # 기술지표
momentum: 0.2     # 모멘텀
sector: 0.1       # 섹터
```

**변경**:

```python
fundamental: 0.25  # -15%p (블루칩 편향 완화)
technical: 0.35    # +5%p (진입 타이밍 중시)
momentum: 0.30     # +10%p (단기 추세 포착)
sector: 0.10       # 유지
```

**담당**: Dev/implement-code
**파일**: `core/watchlist/evaluation_engine.py`
**소요**: 0.5일
**우선순위**: ⭐⭐⭐⭐⭐

**예상 효과**:

- 거래 기회 +50%
- 연수익률 +3-5%p

---

### 작업 4: Phase 1 필터 완화

**현재**:

```python
# evaluation_engine.py:129-195
ROE >= 20  # 상위 20-30%
PER <= 0.6  # 섹터평균 대비
PBR <= 1.0  # 저평가만
```

**변경**:

```python
ROE >= 12  # 중위수 수준
PER <= 0.8  # 성장주 포함
PBR <= 2.0  # IT/바이오 포함
debt_ratio <= 150  # 100 → 150
```

**담당**: Dev/implement-code
**파일**: `core/watchlist/evaluation_engine.py`
**소요**: 1일
**우선순위**: ⭐⭐⭐⭐

**예상 효과**:

- 감시 리스트: 50종목 → 80종목 (+60%)
- 연수익률 +2-4%p

---

### 작업 5: 손절/익절 개선

**5a. 변동성별 차등 손절**

**현재**:

```python
# trading_engine.py:50
stop_loss_pct: 0.03  # 고정 -3%
```

**변경**:

```python
def calculate_dynamic_stop(self, stock_code, entry_price):
    atr = self.get_atr(stock_code)
    atr_percent = atr / entry_price

    if atr_percent < 0.03:  # 저변동성
        stop_loss_pct = 0.03
    elif atr_percent < 0.05:  # 중간
        stop_loss_pct = 0.05
    else:  # 고변동성
        stop_loss_pct = 0.07

    return entry_price * (1 - stop_loss_pct)
```

**5b. 부분 익절 전략**

**현재**:

```python
# trading_engine.py:51-52
take_profit_pct: 0.08  # 고정 +8%
```

**변경**:

```python
def check_partial_profit(self, position):
    current_return = position.unrealized_return

    # 1차 익절: 50% @ +5%
    if current_return >= 0.05 and not position.partial_sold:
        sell_quantity = position.quantity // 2
        self._execute_sell(
            stock_code=position.stock_code,
            quantity=sell_quantity,
            reason="partial_profit_1"
        )
        position.partial_sold = True
        position.partial_profit_price = position.current_price
        return True

    # 2차 익절: 나머지 @ +10%
    if current_return >= 0.10:
        sell_quantity = position.quantity
        self._execute_sell(
            stock_code=position.stock_code,
            quantity=sell_quantity,
            reason="take_profit"
        )
        return True

    return False
```

**담당**: Dev/implement-code
**파일**: `core/trading/trading_engine.py`, `dynamic_stop_loss.py`
**소요**: 2-3일
**우선순위**: ⭐⭐⭐⭐⭐

**예상 효과**:

- 승률: 45-50% → 65% (+15%p)
- 평균 수익 +2-3%p
- 연수익률 +5-7%p

---

### 작업 6: 백테스트 재실행 및 검증

**목적**:

- 작업 1-5 완료 후 실제 성과 측정
- Out-of-Sample 검증

**방법**:

```python
# 데이터 분할
train_period = "2025-07-10" ~ "2025-12-31"  # 6개월
test_period = "2026-01-01" ~ "2026-02-03"   # 1개월

# Train에서 파라미터 최적화 (작업 3-5)
# Test에서 성과 검증
```

**담당**: validate-backtest (에이전트)
**소요**: 1일
**우선순위**: ⭐⭐⭐⭐

**통과 기준**:

- Out-of-Sample 연수익률 > 10% (거래 비용 차감 후)
- Out-of-Sample 샤프비율 > 1.0
- Train vs Test 성과 차이 < 20%

---

## 🎯 Phase P1: 중기 개선 (1-2개월)

**목표**: 연수익률 17-20% → **25-28%** (+40%)

### 작업 7: In/Out-of-Sample 분리

**현재 문제**: 전체 데이터를 하나로 사용 → 과적합 위험

**해결**:

```python
# data_splitter.py (신규)
class DataSplitter:
    def split_timeseries(self, data, train_ratio=0.7):
        """시계열 데이터 분할 (무작위 X)"""
        split_idx = int(len(data) * train_ratio)
        train = data[:split_idx]  # 시간순 앞부분
        test = data[split_idx:]   # 시간순 뒷부분
        return train, test
```

**담당**: Dev/implement-code
**파일**: `core/backtesting/data_splitter.py` (신규)
**소요**: 1일
**우선순위**: ⭐⭐⭐⭐

---

### 작업 8: Walk-Forward Analysis

**목적**: Rolling 백테스트로 파라미터 안정성 검증

**구현**:

```python
# walk_forward.py (신규)
class WalkForwardAnalyzer:
    def __init__(self, train_window=180, test_window=30):
        self.train_window = train_window  # 6개월
        self.test_window = test_window    # 1개월

    def run(self, data):
        """Rolling 백테스트"""
        results = []
        for start in range(0, len(data) - self.train_window, self.test_window):
            train = data[start:start+self.train_window]
            test = data[start+self.train_window:start+self.train_window+self.test_window]

            # 파라미터 최적화 (train)
            params = self._optimize_params(train)

            # 성과 검증 (test)
            result = self._backtest_with_params(test, params)
            results.append(result)

        return self._aggregate_results(results)
```

**담당**: Dev/implement-code
**파일**: `core/backtesting/walk_forward.py` (신규)
**소요**: 2-3일
**우선순위**: ⭐⭐⭐⭐

---

### 작업 9: 동적 Kelly 사이징

**현재 문제**: Kelly 계산 결과가 실시간 반영 안 됨

**해결**:

```python
# trading_engine.py 수정
def _calculate_position_size(self, stock_code, stock_data):
    # 항상 Kelly 계산
    kelly_result = self.kelly.calculate(
        trade_returns=self._get_recent_returns(),
        signal_strength=stock_data.get("signal_strength", 1.0)
    )

    # 기본 크기와 Kelly 결과 병합
    base_size = self.account_balance * 0.05
    kelly_size = self.account_balance * kelly_result.final_position

    # 보수적: 둘 중 작은 값
    investment_amount = min(base_size, kelly_size)

    # 신호 강도별 차등 (중기 개선)
    if stock_data.get("signal_strength", 0) > 0.8:  # 강한 신호
        kelly_multiplier = 0.40  # 40%
    elif stock_data.get("signal_strength", 0) > 0.6:
        kelly_multiplier = 0.30  # 30%
    else:
        kelly_multiplier = 0.20  # 20% (보수적)

    investment_amount = min(investment_amount, self.account_balance * kelly_multiplier)

    return investment_amount
```

**담당**: Dev/implement-code
**파일**: `core/trading/trading_engine.py`
**소요**: 2일
**우선순위**: ⭐⭐⭐⭐

**예상 효과**:

- 포트폴리오 변동성 최적화
- 장기 복리 수익률 +3-5%p

---

### 작업 10: 시장 체제 감지

**목적**: Bull/Bear/Sideways 시장별 파라미터 자동 조정

**구현**:

```python
# market_regime.py (신규)
class MarketRegimeDetector:
    def detect(self, market_data):
        """시장 체제 감지"""
        # KOSPI 최근 60일 수익률
        returns = market_data['kospi_returns'][-60:]
        volatility = np.std(returns)
        trend = np.mean(returns)

        if trend > 0.005 and volatility < 0.02:
            return "bull"  # 상승장
        elif trend < -0.005:
            return "bear"  # 하락장
        else:
            return "sideways"  # 횡보장

    def get_params(self, regime):
        """체제별 파라미터"""
        if regime == "bull":
            return {
                "stop_loss": 0.05,  # 넓은 손절
                "take_profit": 0.12,  # 높은 익절
                "position_size_multiplier": 1.2  # 공격적
            }
        elif regime == "bear":
            return {
                "stop_loss": 0.03,  # 타이트한 손절
                "take_profit": 0.06,  # 낮은 익절
                "position_size_multiplier": 0.8  # 보수적
            }
        else:  # sideways
            return {
                "stop_loss": 0.04,
                "take_profit": 0.08,
                "position_size_multiplier": 1.0
            }
```

**담당**: Dev/implement-code
**파일**: `core/market/regime_detection.py` (신규)
**소요**: 2-3일
**우선순위**: ⭐⭐⭐⭐

**예상 효과**:

- 샤프비율 +0.2-0.3
- MDD -2-3%

---

### 작업 11: 상관관계 기반 포지션 제한

**목적**: 고상관 종목 동시 보유 방지

**구현**:

```python
# correlation_monitor.py (신규)
class CorrelationMonitor:
    def calculate_portfolio_correlation(self, positions):
        """포트폴리오 평균 상관계수"""
        stock_codes = list(positions.keys())

        if len(stock_codes) < 2:
            return 0.0

        # 최근 60일 수익률 조회
        returns_matrix = []
        for code in stock_codes:
            daily_returns = self._get_daily_returns(code, period=60)
            returns_matrix.append(daily_returns)

        # 상관계수 행렬
        corr_matrix = np.corrcoef(returns_matrix)

        # 평균 상관계수 (대각선 제외)
        n = len(stock_codes)
        avg_corr = (corr_matrix.sum() - n) / (n * (n - 1))

        return avg_corr

    def check_new_position(self, new_code, existing_positions):
        """신규 종목과 기존 포트폴리오 상관관계 체크"""
        if not existing_positions:
            return True  # 첫 종목은 허용

        new_returns = self._get_daily_returns(new_code, period=60)

        high_corr_count = 0
        for code in existing_positions:
            existing_returns = self._get_daily_returns(code, period=60)
            corr = np.corrcoef(new_returns, existing_returns)[0, 1]

            if corr > 0.7:  # 70% 이상 고상관
                high_corr_count += 1

        # 고상관 종목이 2개 이상이면 거부
        if high_corr_count >= 2:
            logger.warning(
                f"신규 종목 {new_code}와 고상관 종목 {high_corr_count}개 - 매수 제한"
            )
            return False

        return True
```

**담당**: Dev/implement-code
**파일**: `core/risk/correlation_monitor.py` (신규)
**소요**: 2일
**우선순위**: ⭐⭐⭐

**예상 효과**:

- 분산투자 효과 향상
- 극단적 시장 변동 시 손실 완화 (-3-5%)

---

### 작업 12: 슬리페이지 모니터링

**목적**: 실제 체결가와 예상가 차이 추적

**구현**:

```python
# slippage_monitor.py (신규)
class SlippageMonitor:
    def __init__(self):
        self.slippages = []
        self.total_slippage_cost = 0.0

    def record_trade(self, expected_price, actual_price, quantity):
        """거래 기록"""
        slippage = (actual_price - expected_price) / expected_price
        slippage_amount = (actual_price - expected_price) * quantity

        self.slippages.append(slippage)
        self.total_slippage_cost += abs(slippage_amount)

        # 경고 임계값 초과 시
        if abs(slippage) > 0.01:  # 1% 초과
            logger.warning(
                f"큰 슬리페이지 발생: {slippage:.2%}, "
                f"비용: {slippage_amount:+,.0f}원"
            )

    def get_statistics(self):
        """통계"""
        if not self.slippages:
            return {}

        return {
            "avg_slippage": np.mean(self.slippages),
            "max_slippage": max(self.slippages),
            "min_slippage": min(self.slippages),
            "total_cost": self.total_slippage_cost,
            "count": len(self.slippages)
        }
```

**담당**: Dev/implement-code
**파일**: `core/monitoring/slippage_monitor.py` (신규)
**소요**: 1일
**우선순위**: ⭐⭐⭐

---

## 🚀 Phase P2: 장기 개선 (3-6개월)

**목표**: 연수익률 25-28% → **35-40%** (+40%)

### 작업 13: 포트폴리오 VaR

**목적**: 상관관계를 고려한 포트폴리오 리스크 측정

**구현**:

```python
# portfolio_var.py (신규)
def calculate_portfolio_var(positions, confidence_level=0.95):
    """
    포트폴리오 VaR 계산 (Variance-Covariance Method)
    """
    # 1. 종목별 변동성 및 비중
    weights = []
    volatilities = []

    total_value = sum(p.quantity * p.current_price for p in positions.values())

    for position in positions.values():
        weight = (position.quantity * position.current_price) / total_value
        volatility = calculate_volatility(position.stock_code, period=60)

        weights.append(weight)
        volatilities.append(volatility)

    # 2. 상관계수 행렬
    corr_matrix = calculate_correlation_matrix([p.stock_code for p in positions.values()])

    # 3. 공분산 행렬
    cov_matrix = np.outer(volatilities, volatilities) * corr_matrix

    # 4. 포트폴리오 변동성
    weights = np.array(weights)
    portfolio_vol = np.sqrt(weights @ cov_matrix @ weights)

    # 5. VaR 계산
    z_score = 1.65  # 95% 신뢰수준
    var = z_score * portfolio_vol * total_value

    return var
```

**담당**: Dev/implement-code
**파일**: `core/risk/portfolio_var.py` (신규)
**소요**: 3일
**우선순위**: ⭐⭐⭐

**예상 효과**:

- 리스크 관리 정교화
- MDD -3-5%

---

### 작업 14: 강화학습 기반 청산 전략

**목적**: 최적 청산 타이밍 학습

**구현**:

```python
# rl_exit_strategy.py (신규)
# PPO (Proximal Policy Optimization) 사용

# State: 현재 수익률, 보유 기간, RSI, MACD, 변동성
# Action: 보유/청산
# Reward: 최종 수익률

# 학습 데이터: 백테스트 결과 (수천 건 거래)
```

**담당**: Dev/implement-code + ML 전문가
**파일**: `core/learning/rl/exit_strategy.py` (신규)
**소요**: 2주
**우선순위**: ⭐⭐

**예상 효과**:

- 평균 수익 +5-7%p
- 승률 유지 또는 소폭 증가

---

### 작업 15: TWAP/VWAP 주문

**목적**: 대량 주문 시 시장 충격 최소화

**구현**:

```python
# smart_order.py (신규)
class TWAPOrder:
    def split_order(self, total_quantity, time_window):
        """TWAP: Time-Weighted Average Price"""
        num_slices = time_window // 5  # 5분 간격
        quantity_per_slice = total_quantity // num_slices

        orders = []
        for i in range(num_slices):
            order_time = start_time + timedelta(minutes=5*i)
            orders.append({
                "time": order_time,
                "quantity": quantity_per_slice,
                "type": "limit"
            })

        return orders

class VWAPOrder:
    def split_order(self, total_quantity, volume_profile):
        """VWAP: Volume-Weighted Average Price"""
        # 거래량 프로파일 기반 분할
        ...
```

**담당**: Dev/implement-code
**파일**: `core/trading/smart_order.py` (신규)
**소요**: 1주
**우선순위**: ⭐⭐

**예상 효과**:

- 슬리페이지 -0.3-0.5%
- 대량 거래 시 유리한 체결가

---

## 📊 체크리스트

### P0 완료 조건

- [x] 백테스트 실제 데이터 사용 (MF-1: KIS API 실데이터 연동)
- [x] 거래 비용 반영 (MF-2: TradingCosts 모듈 구현)
- [x] Phase 1 가중치 조정 (완료)
- [x] Phase 1 필터 완화 (완료)
- [x] 손절/익절 개선 (MF-4: 변동성별 손절 + 부분 익절)
- [ ] 백테스트 재실행 (Out-of-Sample 검증 통과) - 모의투자 데이터 축적 후 진행

### P1 완료 조건 (코드 구현 완료, 실데이터 검증 대기)

- [x] In/Out-of-Sample 분리 (#7: DataSplitter + purge gap)
- [x] Walk-Forward Analysis (#8: WalkForwardAnalyzer)
- [ ] 동적 Kelly 사이징 (#9: TradingEngine 통합 대기)
- [ ] 시장 체제 감지 (#10: MarketRegimeDetector 구현 대기)
- [ ] 상관관계 기반 포지션 제한 (#11: CorrelationMonitor 구현 대기)
- [ ] 슬리페이지 모니터링 (#12: SlippageMonitor 구현 대기)

### P1 코드 품질 개선 (Should Fix / Consider)

- [x] SF-1: strategy_backtester.py trading_config 미정의 버그 수정
- [x] SF-2: strategy_backtester.py max_positions 파라미터화
- [x] SF-3: BacktestResult.empty() SSOT classmethod 추가
- [x] SF-4: WalkForwardConfig 파라미터 문서화
- [x] SF-5: PerformanceAnalyzer 제로 분모 로깅 강화
- [x] SF-7: Kelly Calculator signal_confidence 범위 검증
- [x] SF-8: TradingEngine JSON 로드 에러 처리 강화
- [x] SF-9: TradingEngine 부분익절 임계값 설정 연동
- [x] C-7: Kelly Calculator state mutation 방지 (임시 인스턴스 패턴)

### P2 완료 조건

- [ ] 포트폴리오 VaR
- [ ] 강화학습 청산 전략
- [ ] TWAP/VWAP 주문

---

## 📈 예상 성과 추이

| 시점                | 연수익률 | 승률   | 샤프비율 | MDD      |
| ------------------- | -------- | ------ | -------- | -------- |
| **현재**            | 8-12%    | 45-50% | 0.8-1.0  | -12~-15% |
| **P0 완료 (3주)**   | 17-20%   | 65%    | 1.5-1.7  | -10%     |
| **P1 완료 (2개월)** | 25-28%   | 60%    | 2.0-2.2  | -10~-12% |
| **P2 완료 (6개월)** | 35-40%   | 63%    | 2.5-3.0  | -8~-10%  |

---

## 🎯 마일스톤

| 날짜           | 마일스톤 | 산출물                                       |
| -------------- | -------- | -------------------------------------------- |
| **2026-02-22** | P0 완료  | 백테스트 신뢰도 80/100, 연수익률 17-20% 검증 |
| **2026-04-08** | P1 완료  | Walk-Forward 검증 통과, 연수익률 25-28% 검증 |
| **2026-08-08** | P2 완료  | RL 모델 운영, 연수익률 35-40% 검증           |

---

**작성자**: Claude (analyze-strategy + validate-backtest + review-trading-logic)
**다음 검토**: P0 완료 후 (2026-02-22)
