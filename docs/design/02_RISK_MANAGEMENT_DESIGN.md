# 🛡️ 리스크 관리 설계서

> **핵심 철학**: "돈을 잃지 않는 것이 돈을 버는 것보다 중요하다"
> **목표**: MDD 10% 이내, 일일 손실 2% 이내, 월간 손실 8% 이내

---

## 1. 포지션 사이징 시스템

### 1.1 켈리 공식 (Kelly Criterion)

```
┌─────────────────────────────────────────────────────────────────┐
│                    켈리 공식 포지션 사이징                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  기본 공식:                                                      │
│  f* = (p × b - q) / b                                          │
│                                                                 │
│  여기서:                                                         │
│  f* = 최적 베팅 비율                                            │
│  p = 승률                                                       │
│  q = 패률 (1 - p)                                              │
│  b = 손익비 (평균 이익 / 평균 손실)                             │
│                                                                 │
│  예시:                                                          │
│  승률 55%, 손익비 1.5 → f* = (0.55 × 1.5 - 0.45) / 1.5 = 25%  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 안전한 켈리 적용

```python
class KellyPositionSizer:
    """
    켈리 공식 기반 포지션 사이징

    안전 장치:
    1. Half Kelly 또는 Quarter Kelly 사용 (과투자 방지)
    2. 최대 포지션 제한 (자본의 10%)
    3. 신뢰구간 고려 (승률 불확실성)
    4. 연속 손실 시 자동 축소
    """

    def __init__(self):
        self.kelly_fraction = 0.5    # Half Kelly (50%)
        self.max_position = 0.10     # 최대 10%
        self.min_position = 0.02     # 최소 2%
        self.confidence_level = 0.95 # 95% 신뢰구간

    def calculate_position_size(self,
                               win_rate: float,
                               avg_win: float,
                               avg_loss: float,
                               capital: float,
                               trade_confidence: float = 1.0) -> PositionSize:
        """
        켈리 기반 포지션 크기 계산

        단계:
        1. 기본 켈리 계산
        2. 불확실성 조정
        3. 안전 마진 적용
        4. 제한 범위 적용
        """
        # Step 1: 기본 켈리
        payoff_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 1.5
        raw_kelly = (win_rate * payoff_ratio - (1 - win_rate)) / payoff_ratio

        # Step 2: 불확실성 조정 (샘플 크기 고려)
        adjusted_kelly = self._adjust_for_uncertainty(raw_kelly, win_rate)

        # Step 3: 안전 마진 적용 (Half Kelly)
        safe_kelly = adjusted_kelly * self.kelly_fraction

        # Step 4: 거래 신뢰도 반영
        confidence_adjusted = safe_kelly * trade_confidence

        # Step 5: 제한 범위 적용
        final_fraction = max(
            self.min_position,
            min(self.max_position, confidence_adjusted)
        )

        position_amount = capital * final_fraction

        return PositionSize(
            fraction=final_fraction,
            amount=position_amount,
            raw_kelly=raw_kelly,
            safe_kelly=safe_kelly,
            reasoning=self._generate_reasoning(
                win_rate, payoff_ratio, raw_kelly, final_fraction
            )
        )

    def _adjust_for_uncertainty(self, kelly: float, win_rate: float) -> float:
        """
        승률 추정의 불확실성 조정

        작은 샘플: 보수적 조정
        큰 샘플: 원본에 가깝게

        신뢰구간 하한 사용:
        p_lower = p - z * sqrt(p(1-p)/n)
        """
        # 최근 거래 수 (가정: 100회)
        n = 100

        # 95% 신뢰구간 하한
        import math
        z = 1.96
        std_error = math.sqrt(win_rate * (1 - win_rate) / n)
        win_rate_lower = max(0.3, win_rate - z * std_error)

        # 조정된 켈리 (하한 승률 사용)
        payoff = kelly / (win_rate - 0.5) if win_rate > 0.5 else 1.5
        adjusted = (win_rate_lower * payoff - (1 - win_rate_lower)) / payoff

        return max(0, adjusted)
```

### 1.3 동적 포지션 조정

```python
class DynamicPositionAdjuster:
    """
    시장 상황과 포트폴리오 상태에 따른 동적 조정

    조정 요인:
    1. 시장 변동성
    2. 연속 손실/이익
    3. 현재 드로다운
    4. 포트폴리오 상관관계
    """

    def adjust_position(self,
                       base_position: float,
                       market_state: MarketState,
                       portfolio_state: PortfolioState) -> float:
        """
        포지션 동적 조정

        조정 공식:
        adjusted = base × volatility_factor × streak_factor × drawdown_factor
        """
        # 1. 변동성 조정
        volatility_factor = self._volatility_adjustment(market_state.vix)

        # 2. 연속 손실/이익 조정
        streak_factor = self._streak_adjustment(portfolio_state.streak)

        # 3. 드로다운 조정
        drawdown_factor = self._drawdown_adjustment(portfolio_state.drawdown)

        # 4. 상관관계 조정
        correlation_factor = self._correlation_adjustment(
            portfolio_state.correlation_to_market
        )

        # 최종 조정
        adjusted = (base_position *
                   volatility_factor *
                   streak_factor *
                   drawdown_factor *
                   correlation_factor)

        return max(self.min_position, min(self.max_position, adjusted))

    def _volatility_adjustment(self, vix: float) -> float:
        """
        변동성 기반 조정

        VIX < 15: × 1.2 (확대)
        VIX 15-25: × 1.0 (유지)
        VIX 25-35: × 0.7 (축소)
        VIX > 35: × 0.4 (대폭 축소)
        """
        if vix < 15:
            return 1.2
        elif vix < 25:
            return 1.0
        elif vix < 35:
            return 0.7
        else:
            return 0.4

    def _streak_adjustment(self, streak: int) -> float:
        """
        연속 손실/이익 조정

        연속 이익 3회+: × 0.9 (과신 방지)
        연속 손실 3회: × 0.7
        연속 손실 5회+: × 0.5 (쿨다운)
        """
        if streak >= 3:  # 연속 이익
            return 0.9  # 과신 방지
        elif streak <= -3:
            return 0.7
        elif streak <= -5:
            return 0.5  # 쿨다운
        else:
            return 1.0

    def _drawdown_adjustment(self, drawdown: float) -> float:
        """
        현재 드로다운 기반 조정

        DD 0~3%: × 1.0
        DD 3~5%: × 0.8
        DD 5~8%: × 0.5
        DD 8~10%: × 0.3
        DD 10%+: × 0.0 (신규 진입 중단)
        """
        if drawdown <= 0.03:
            return 1.0
        elif drawdown <= 0.05:
            return 0.8
        elif drawdown <= 0.08:
            return 0.5
        elif drawdown <= 0.10:
            return 0.3
        else:
            return 0.0  # 거래 중단

    def _correlation_adjustment(self, correlation: float) -> float:
        """
        시장 상관관계 조정

        높은 상관관계 (> 0.7): 이미 시장 익스포저 많음 → 축소
        낮은 상관관계 (< 0.3): 분산 효과 → 확대 가능
        """
        if correlation > 0.7:
            return 0.8
        elif correlation < 0.3:
            return 1.1
        else:
            return 1.0
```

---

## 2. 상관관계 기반 분산투자

### 2.1 상관관계 매트릭스

```python
class CorrelationAnalyzer:
    """
    포트폴리오 상관관계 분석

    목표:
    - 진정한 분산투자 달성
    - 상관관계 0.5 이하 종목으로 구성
    - 섹터/스타일 분산
    """

    def __init__(self):
        self.lookback_period = 60        # 60일 롤링 상관계수
        self.max_correlation = 0.70      # 최대 허용 상관계수
        self.target_correlation = 0.40   # 목표 평균 상관계수

    def calculate_correlation_matrix(self,
                                    stock_codes: List[str],
                                    returns: pd.DataFrame) -> pd.DataFrame:
        """
        종목간 상관계수 행렬 계산

        Returns:
            상관계수 매트릭스 (DataFrame)
        """
        # 일간 수익률 기준 상관계수
        corr_matrix = returns[stock_codes].corr()

        return corr_matrix

    def check_diversification(self,
                             portfolio: Portfolio) -> DiversificationReport:
        """
        분산투자 검증

        체크 항목:
        1. 종목간 상관관계
        2. 섹터 집중도
        3. 스타일 집중도 (성장/가치)
        4. 시가총액 분포
        """
        stock_codes = list(portfolio.holdings.keys())
        returns = self._get_returns(stock_codes)

        # 상관계수 매트릭스
        corr_matrix = self.calculate_correlation_matrix(stock_codes, returns)

        # 평균 상관계수 (대각선 제외)
        n = len(stock_codes)
        if n > 1:
            avg_correlation = (corr_matrix.sum().sum() - n) / (n * (n - 1))
        else:
            avg_correlation = 0

        # 고상관 종목 쌍 찾기
        high_corr_pairs = []
        for i in range(n):
            for j in range(i + 1, n):
                if corr_matrix.iloc[i, j] > self.max_correlation:
                    high_corr_pairs.append({
                        'stock1': stock_codes[i],
                        'stock2': stock_codes[j],
                        'correlation': corr_matrix.iloc[i, j]
                    })

        # 섹터 집중도
        sector_concentration = self._calculate_sector_concentration(portfolio)

        # 분산 점수 (0~100)
        diversification_score = self._calculate_div_score(
            avg_correlation, len(high_corr_pairs), sector_concentration
        )

        return DiversificationReport(
            avg_correlation=avg_correlation,
            high_corr_pairs=high_corr_pairs,
            sector_concentration=sector_concentration,
            diversification_score=diversification_score,
            recommendations=self._generate_recommendations(
                high_corr_pairs, sector_concentration
            )
        )

    def _calculate_div_score(self,
                            avg_corr: float,
                            high_corr_count: int,
                            sector_conc: float) -> float:
        """
        분산투자 점수 계산

        구성:
        - 평균 상관계수: 40점 (낮을수록 좋음)
        - 고상관 종목 수: 30점 (적을수록 좋음)
        - 섹터 분산: 30점 (분산될수록 좋음)
        """
        # 평균 상관계수 점수 (0.3 이하: 40점, 0.7 이상: 0점)
        corr_score = max(0, 40 * (1 - (avg_corr - 0.3) / 0.4))

        # 고상관 종목 점수 (0개: 30점, 5개 이상: 0점)
        pair_score = max(0, 30 * (1 - high_corr_count / 5))

        # 섹터 분산 점수 (HHI 기반)
        sector_score = 30 * (1 - sector_conc)

        return corr_score + pair_score + sector_score
```

### 2.2 포트폴리오 최적화

```python
class PortfolioOptimizer:
    """
    상관관계 기반 포트폴리오 최적화

    최적화 목표:
    1. 목표 수익률 달성
    2. 변동성 최소화
    3. 상관관계 제약 충족
    """

    def optimize(self,
                candidates: List[str],
                expected_returns: pd.Series,
                covariance: pd.DataFrame,
                constraints: dict) -> OptimalPortfolio:
        """
        최소분산 포트폴리오 최적화

        제약 조건:
        - 개별 종목 최대 비중: 15%
        - 섹터 최대 비중: 30%
        - 최소 종목 수: 5개
        - 최대 종목 수: 15개
        """
        from scipy.optimize import minimize

        n = len(candidates)

        # 목적 함수: 포트폴리오 변동성 최소화
        def portfolio_volatility(weights):
            return np.sqrt(weights @ covariance @ weights)

        # 제약 조건
        constraints_list = [
            {'type': 'eq', 'fun': lambda w: np.sum(w) - 1},  # 합 = 1
        ]

        # 개별 종목 제한
        bounds = [(0, constraints.get('max_weight', 0.15)) for _ in range(n)]

        # 초기값
        x0 = np.array([1/n] * n)

        # 최적화 실행
        result = minimize(
            portfolio_volatility,
            x0,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints_list
        )

        optimal_weights = result.x

        # 결과 생성
        return OptimalPortfolio(
            weights={candidates[i]: optimal_weights[i]
                    for i in range(n) if optimal_weights[i] > 0.01},
            expected_return=expected_returns @ optimal_weights,
            volatility=portfolio_volatility(optimal_weights),
            sharpe_ratio=self._calculate_sharpe(
                expected_returns @ optimal_weights,
                portfolio_volatility(optimal_weights)
            )
        )

    def check_correlation_constraint(self,
                                    weights: np.array,
                                    corr_matrix: pd.DataFrame) -> bool:
        """
        상관관계 제약 충족 확인

        규칙:
        - 상관계수 > 0.7인 종목 쌍의 합산 비중 < 20%
        """
        n = len(weights)

        for i in range(n):
            for j in range(i + 1, n):
                if corr_matrix.iloc[i, j] > 0.7:
                    if weights[i] + weights[j] > 0.20:
                        return False

        return True
```

---

## 3. 드로다운 관리 시스템

### 3.1 실시간 드로다운 모니터링

```python
class DrawdownMonitor:
    """
    실시간 드로다운 모니터링 및 대응

    모니터링 레벨:
    - 일간 드로다운
    - 주간 드로다운
    - 월간 드로다운
    - 고점 대비 드로다운 (MDD)
    """

    def __init__(self):
        # 한도 설정
        self.limits = {
            'daily': 0.02,      # 일일 2%
            'weekly': 0.05,     # 주간 5%
            'monthly': 0.08,    # 월간 8%
            'total': 0.15,      # 전체 MDD 15%
        }

        # 단계별 대응
        self.response_levels = {
            0.03: 'warning',    # 3%: 경고
            0.05: 'reduce',     # 5%: 포지션 축소
            0.08: 'halt_new',   # 8%: 신규 진입 중단
            0.10: 'close_half', # 10%: 절반 청산
            0.12: 'close_all',  # 12%: 전량 청산
        }

    def update(self, current_equity: float) -> DrawdownStatus:
        """
        드로다운 상태 업데이트

        Returns:
            현재 드로다운 상태 및 필요한 액션
        """
        # 각 기간별 드로다운 계산
        daily_dd = self._calculate_daily_drawdown(current_equity)
        weekly_dd = self._calculate_weekly_drawdown(current_equity)
        monthly_dd = self._calculate_monthly_drawdown(current_equity)
        total_dd = self._calculate_total_drawdown(current_equity)

        # 최악의 드로다운 기준으로 대응 결정
        max_dd = max(daily_dd, weekly_dd / 2.5, monthly_dd / 4, total_dd)

        action = self._determine_action(max_dd, total_dd)

        return DrawdownStatus(
            daily=daily_dd,
            weekly=weekly_dd,
            monthly=monthly_dd,
            total=total_dd,
            action=action,
            limits_breached=self._check_limits(daily_dd, weekly_dd, monthly_dd, total_dd)
        )

    def _determine_action(self, max_dd: float, total_dd: float) -> Action:
        """
        드로다운 수준에 따른 액션 결정

        단계별 대응:
        1. 경고 (3%): 알림 발송
        2. 축소 (5%): 신규 포지션 50%로 축소
        3. 진입 중단 (8%): 신규 진입 금지
        4. 절반 청산 (10%): 전체 포지션 50% 청산
        5. 전량 청산 (12%): 모든 포지션 청산
        """
        for threshold, action in sorted(self.response_levels.items(), reverse=True):
            if max_dd >= threshold:
                return Action(
                    type=action,
                    severity=self._get_severity(action),
                    message=self._get_message(action, max_dd),
                    auto_execute=action in ['close_all', 'close_half']
                )

        return Action(type='normal', severity='low')
```

### 3.2 서킷브레이커

```python
class CircuitBreaker:
    """
    자동 거래 중단 시스템 (서킷브레이커)

    트리거 조건:
    1. 일일 손실 한도 초과
    2. 연속 손실 횟수 초과
    3. 시스템 오류
    4. 시장 급변동
    """

    def __init__(self):
        self.triggers = {
            'daily_loss': 0.02,          # 일일 2% 손실
            'consecutive_losses': 5,      # 연속 5회 손실
            'error_count': 3,            # 3회 오류
            'market_volatility': 0.05,   # 시장 5% 급변동
        }

        self.cooldown_periods = {
            'daily_loss': timedelta(hours=24),
            'consecutive_losses': timedelta(hours=48),
            'error_count': timedelta(hours=1),
            'market_volatility': timedelta(hours=4),
        }

        self.is_active = False
        self.trigger_time = None
        self.trigger_reason = None

    def check_and_trigger(self, state: SystemState) -> CircuitBreakerStatus:
        """
        서킷브레이커 조건 확인 및 발동

        Returns:
            서킷브레이커 상태
        """
        # 이미 활성화된 경우
        if self.is_active:
            if self._should_reset():
                self._reset()
            else:
                return CircuitBreakerStatus(
                    active=True,
                    reason=self.trigger_reason,
                    time_remaining=self._get_remaining_time()
                )

        # 트리거 조건 확인
        # 1. 일일 손실
        if state.daily_pnl <= -self.triggers['daily_loss']:
            return self._activate('daily_loss', f"일일 손실 {state.daily_pnl:.1%}")

        # 2. 연속 손실
        if state.consecutive_losses >= self.triggers['consecutive_losses']:
            return self._activate('consecutive_losses',
                                f"연속 {state.consecutive_losses}회 손실")

        # 3. 시스템 오류
        if state.error_count >= self.triggers['error_count']:
            return self._activate('error_count', f"시스템 오류 {state.error_count}회")

        # 4. 시장 급변동
        if abs(state.market_change) >= self.triggers['market_volatility']:
            return self._activate('market_volatility',
                                f"시장 급변동 {state.market_change:.1%}")

        return CircuitBreakerStatus(active=False)

    def _activate(self, reason: str, message: str) -> CircuitBreakerStatus:
        """
        서킷브레이커 활성화
        """
        self.is_active = True
        self.trigger_time = datetime.now()
        self.trigger_reason = reason

        # 알림 발송
        self._send_alert(f"🚨 서킷브레이커 발동: {message}")

        # 모든 주문 취소
        self._cancel_all_orders()

        return CircuitBreakerStatus(
            active=True,
            reason=reason,
            message=message,
            cooldown=self.cooldown_periods[reason]
        )

    def force_reset(self, admin_key: str) -> bool:
        """
        관리자 강제 리셋 (비밀키 필요)
        """
        if admin_key == os.environ.get('CIRCUIT_BREAKER_KEY'):
            self._reset()
            self._send_alert("⚠️ 서킷브레이커 관리자에 의해 해제됨")
            return True
        return False
```

### 3.3 단계별 포지션 축소

```python
class PositionReducer:
    """
    드로다운 수준에 따른 단계별 포지션 축소

    축소 전략:
    1. 최악 성과 종목부터 청산
    2. 상관관계 높은 종목 우선 축소
    3. 유동성 고려 (거래량 낮은 종목 먼저)
    """

    def reduce_positions(self,
                        portfolio: Portfolio,
                        reduction_rate: float,
                        method: str = 'worst_first') -> List[Order]:
        """
        포지션 축소 주문 생성

        Args:
            portfolio: 현재 포트폴리오
            reduction_rate: 축소 비율 (예: 0.5 = 50% 축소)
            method: 축소 방법
                - 'worst_first': 최악 성과 종목부터
                - 'pro_rata': 비례 축소
                - 'correlation': 고상관 종목 우선

        Returns:
            청산 주문 리스트
        """
        orders = []

        if method == 'worst_first':
            # 수익률 기준 정렬 (낮은 순)
            sorted_holdings = sorted(
                portfolio.holdings.items(),
                key=lambda x: x[1].unrealized_pnl_pct
            )

            target_reduction = portfolio.total_value * reduction_rate
            reduced_amount = 0

            for stock_code, holding in sorted_holdings:
                if reduced_amount >= target_reduction:
                    break

                # 전체 청산
                order = self._create_sell_order(stock_code, holding.quantity)
                orders.append(order)
                reduced_amount += holding.market_value

        elif method == 'pro_rata':
            # 비례 축소
            for stock_code, holding in portfolio.holdings.items():
                reduce_qty = int(holding.quantity * reduction_rate)
                if reduce_qty > 0:
                    orders.append(self._create_sell_order(stock_code, reduce_qty))

        elif method == 'correlation':
            # 고상관 종목 우선 축소
            orders = self._reduce_by_correlation(portfolio, reduction_rate)

        return orders

    def _reduce_by_correlation(self,
                              portfolio: Portfolio,
                              reduction_rate: float) -> List[Order]:
        """
        상관관계 기반 축소

        로직:
        1. 포트폴리오 상관관계 매트릭스 계산
        2. 평균 상관관계가 높은 종목 식별
        3. 해당 종목 우선 축소
        """
        stock_codes = list(portfolio.holdings.keys())
        corr_matrix = self.correlation_analyzer.calculate_correlation_matrix(stock_codes)

        # 각 종목의 평균 상관관계 계산
        avg_correlations = {}
        for code in stock_codes:
            others = [c for c in stock_codes if c != code]
            avg_corr = corr_matrix.loc[code, others].mean()
            avg_correlations[code] = avg_corr

        # 상관관계 높은 순 정렬
        sorted_by_corr = sorted(avg_correlations.items(), key=lambda x: x[1], reverse=True)

        orders = []
        target_reduction = portfolio.total_value * reduction_rate
        reduced_amount = 0

        for stock_code, _ in sorted_by_corr:
            if reduced_amount >= target_reduction:
                break

            holding = portfolio.holdings[stock_code]
            order = self._create_sell_order(stock_code, holding.quantity)
            orders.append(order)
            reduced_amount += holding.market_value

        return orders
```

---

## 4. 손절/익절 관리

### 4.1 동적 손절 시스템

```python
class DynamicStopLossManager:
    """
    ATR 기반 동적 손절/익절 관리

    기존 구현 (core/trading/dynamic_stop_loss.py) 확장
    """

    def __init__(self):
        self.base_atr_multiplier = 2.0    # 기본 ATR 배수
        self.profit_multiplier = 3.0       # 익절 배수
        self.trailing_activation = 0.02    # 트레일링 활성화 (2% 수익)
        self.trailing_multiplier = 1.5     # 트레일링 ATR 배수

    def calculate_stops(self,
                       entry_price: float,
                       data: pd.DataFrame,
                       market_regime: MarketRegime) -> StopLevels:
        """
        시장 상황별 손절/익절 계산

        레짐별 조정:
        - 강세장: ATR × 2.5 (넓은 손절)
        - 약세장: ATR × 1.5 (타이트한 손절)
        - 고변동성: ATR × 3.0 (매우 넓은 손절)
        """
        atr = self._calculate_atr(data)

        # 레짐별 배수 조정
        regime_multipliers = {
            MarketRegime.BULL: {'stop': 2.5, 'profit': 4.0},
            MarketRegime.BEAR: {'stop': 1.5, 'profit': 2.0},
            MarketRegime.RANGE: {'stop': 2.0, 'profit': 3.0},
            MarketRegime.HIGH_VOLATILITY: {'stop': 3.0, 'profit': 4.5},
        }

        mult = regime_multipliers.get(market_regime, {'stop': 2.0, 'profit': 3.0})

        stop_loss = entry_price - (atr * mult['stop'])
        take_profit = entry_price + (atr * mult['profit'])

        # 최소/최대 손절 비율 제한
        stop_pct = (entry_price - stop_loss) / entry_price
        if stop_pct < 0.02:  # 최소 2%
            stop_loss = entry_price * 0.98
        elif stop_pct > 0.08:  # 최대 8%
            stop_loss = entry_price * 0.92

        return StopLevels(
            stop_loss=stop_loss,
            take_profit=take_profit,
            atr=atr,
            risk_reward_ratio=(take_profit - entry_price) / (entry_price - stop_loss)
        )

    def update_trailing_stop(self,
                            position: Position,
                            current_price: float) -> float:
        """
        트레일링 스탑 업데이트

        로직:
        1. 수익이 활성화 임계값 도달 시 트레일링 시작
        2. 신고가 갱신 시 손절가 상향 조정
        3. 손절가는 내려가지 않음
        """
        profit_pct = (current_price - position.entry_price) / position.entry_price

        # 트레일링 활성화 체크
        if profit_pct < self.trailing_activation:
            return position.stop_loss  # 기존 손절 유지

        # 신고가 갱신 시
        if current_price > position.highest_price:
            new_trailing = current_price - (position.atr * self.trailing_multiplier)

            # 손절가는 올라가기만 함
            if new_trailing > position.stop_loss:
                return new_trailing

        return position.stop_loss
```

### 4.2 시간 기반 청산

```python
class TimeBasedExitManager:
    """
    시간 기반 청산 관리

    청산 조건:
    1. 최대 보유 기간 초과
    2. 목표 미달성 지연
    3. 이벤트 전 청산 (실적 발표 등)
    """

    def __init__(self):
        self.max_holding_days = 20         # 최대 20일 보유
        self.stagnant_threshold = 0.02     # 2% 미만 변동
        self.stagnant_days = 10            # 10일간 정체 시

    def check_time_exit(self, position: Position) -> TimeExitSignal:
        """
        시간 기반 청산 신호 확인
        """
        holding_days = (datetime.now() - position.entry_date).days

        # 1. 최대 보유 기간
        if holding_days >= self.max_holding_days:
            return TimeExitSignal(
                should_exit=True,
                reason='max_holding_period',
                message=f"최대 보유 기간 {self.max_holding_days}일 초과"
            )

        # 2. 정체 상태
        if self._is_stagnant(position, self.stagnant_days, self.stagnant_threshold):
            return TimeExitSignal(
                should_exit=True,
                reason='stagnant',
                message=f"{self.stagnant_days}일간 {self.stagnant_threshold:.0%} 미만 변동"
            )

        # 3. 이벤트 임박
        event = self._check_upcoming_event(position.stock_code)
        if event and event.days_until <= 2:
            return TimeExitSignal(
                should_exit=True,
                reason='upcoming_event',
                message=f"이벤트 임박: {event.name} (D-{event.days_until})"
            )

        return TimeExitSignal(should_exit=False)
```

---

## 5. 통합 리스크 대시보드

### 5.1 리스크 메트릭스 종합

```python
class RiskDashboard:
    """
    통합 리스크 모니터링 대시보드

    모니터링 항목:
    1. 포트폴리오 VaR/CVaR
    2. 개별 종목 리스크
    3. 섹터 익스포저
    4. 상관관계 리스크
    5. 유동성 리스크
    """

    def generate_report(self, portfolio: Portfolio) -> RiskReport:
        """
        종합 리스크 리포트 생성
        """
        return RiskReport(
            # VaR/CVaR
            var_95=self._calculate_var(portfolio, 0.95),
            var_99=self._calculate_var(portfolio, 0.99),
            cvar_95=self._calculate_cvar(portfolio, 0.95),

            # 드로다운
            current_drawdown=self._get_current_drawdown(portfolio),
            max_drawdown=self._get_max_drawdown(portfolio),

            # 포지션 리스크
            position_concentration=self._check_concentration(portfolio),
            sector_exposure=self._check_sector_exposure(portfolio),

            # 상관관계
            avg_correlation=self._get_avg_correlation(portfolio),
            high_corr_pairs=self._find_high_corr_pairs(portfolio),

            # 유동성
            illiquid_positions=self._find_illiquid(portfolio),

            # 종합 점수
            risk_score=self._calculate_risk_score(portfolio),

            # 권고사항
            recommendations=self._generate_recommendations(portfolio)
        )

    def _calculate_risk_score(self, portfolio: Portfolio) -> float:
        """
        종합 리스크 점수 (0~100, 낮을수록 안전)

        구성:
        - VaR 점수: 25%
        - 드로다운 점수: 25%
        - 집중도 점수: 20%
        - 상관관계 점수: 15%
        - 유동성 점수: 15%
        """
        var_score = min(100, self._calculate_var(portfolio, 0.95) * 1000)
        dd_score = min(100, abs(self._get_current_drawdown(portfolio)) * 500)
        conc_score = self._concentration_score(portfolio)
        corr_score = self._correlation_score(portfolio)
        liq_score = self._liquidity_score(portfolio)

        total = (
            var_score * 0.25 +
            dd_score * 0.25 +
            conc_score * 0.20 +
            corr_score * 0.15 +
            liq_score * 0.15
        )

        return total
```

---

## 6. 구현 우선순위

### Phase B-1: 켈리 포지션 사이징 (Day 1-2)

```python
# 구현 순서
1. core/risk/position/__init__.py
2. core/risk/position/kelly_calculator.py
3. core/risk/position/position_sizer.py

# 테스트
- 켈리 공식 정확성
- 안전 마진 적용
- 극단값 처리
```

### Phase B-2: 상관관계 분석 (Day 3-4)

```python
# 구현 순서
1. core/risk/correlation/__init__.py
2. core/risk/correlation/correlation_matrix.py
3. core/risk/correlation/portfolio_optimizer.py

# 검증
- 상관계수 계산 정확성
- 최적화 알고리즘 수렴
```

### Phase B-3: 드로다운 관리 (Day 5-8)

```python
# 구현 순서
1. core/risk/drawdown/__init__.py
2. core/risk/drawdown/drawdown_monitor.py
3. core/risk/drawdown/circuit_breaker.py
4. core/risk/drawdown/position_reducer.py

# 검증
- 실시간 모니터링
- 서킷브레이커 발동
- 자동 포지션 축소
```

---

*다음 문서: `03_LEARNING_SYSTEM_DESIGN.md` - 학습 시스템 설계*
