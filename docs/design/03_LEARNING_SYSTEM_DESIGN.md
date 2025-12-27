# 🧠 학습 시스템 설계서

> **핵심 철학**: "시장은 변하고, 전략도 진화해야 한다"
> **목표**: 시간이 지날수록 성과가 개선되는 자기 학습 시스템

---

## 1. 학습 시스템 개요

### 1.1 학습이 필요한 이유

```
┌─────────────────────────────────────────────────────────────────┐
│                    왜 학습이 필요한가?                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  정적 전략의 한계:                                               │
│  ├─ 과거 데이터에 과최적화                                       │
│  ├─ 시장 구조 변화에 적응 불가                                   │
│  ├─ 새로운 패턴 학습 불가                                        │
│  └─ 성과 저하 시 원인 파악 어려움                                │
│                                                                 │
│  학습 시스템의 장점:                                             │
│  ├─ 지속적인 성과 개선                                          │
│  ├─ 시장 변화 자동 적응                                          │
│  ├─ 실수에서 학습                                                │
│  └─ 전략 자동 최적화                                             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 학습 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         학습 시스템 아키텍처                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                        데이터 수집 계층                           │  │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐             │  │
│  │  │ 시장    │  │ 거래    │  │ 신호    │  │ 결과    │             │  │
│  │  │ 데이터  │  │ 로그    │  │ 기록    │  │ 피드백  │             │  │
│  │  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘             │  │
│  └───────┼────────────┼────────────┼────────────┼──────────────────┘  │
│          │            │            │            │                      │
│          ▼            ▼            ▼            ▼                      │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                       분석 및 학습 계층                           │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐               │  │
│  │  │   패턴      │  │   성과      │  │   실패      │               │  │
│  │  │   학습기    │  │   분석기    │  │   분석기    │               │  │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘               │  │
│  └─────────┼────────────────┼────────────────┼──────────────────────┘  │
│            │                │                │                          │
│            ▼                ▼                ▼                          │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                        적응 및 최적화 계층                        │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐               │  │
│  │  │   파라미터  │  │   가중치    │  │   전략      │               │  │
│  │  │   조정기    │  │   조정기    │  │   선택기    │               │  │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘               │  │
│  └─────────┼────────────────┼────────────────┼──────────────────────┘  │
│            │                │                │                          │
│            ▼                ▼                ▼                          │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                        실행 계층                                  │  │
│  │           업데이트된 전략 → 실시간 적용 → 결과 피드백             │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 거래 결과 학습

### 2.1 거래 로그 수집

```python
class TradeLogger:
    """
    모든 거래의 상세 정보 기록

    기록 항목:
    - 진입/청산 시점의 모든 지표
    - 신호 발생 근거
    - 시장 상황
    - 결과 및 원인 분석
    """

    def log_trade(self, trade: Trade, context: TradeContext) -> TradeLog:
        """
        거래 상세 로그 생성

        기록 항목 (학습에 활용):
        1. 진입 시점 상태
        2. 청산 시점 상태
        3. 보유 기간 중 변화
        4. 결과 및 원인
        """
        log = TradeLog(
            trade_id=trade.id,
            timestamp=datetime.now(),

            # 기본 정보
            stock_code=trade.stock_code,
            direction=trade.direction,
            entry_price=trade.entry_price,
            exit_price=trade.exit_price,
            quantity=trade.quantity,
            pnl=trade.pnl,
            pnl_pct=trade.pnl_pct,
            holding_days=trade.holding_days,

            # 진입 시점 상태
            entry_context=EntryContext(
                # 기술적 지표
                rsi=context.entry_indicators['rsi'],
                macd=context.entry_indicators['macd'],
                macd_signal=context.entry_indicators['macd_signal'],
                bb_position=context.entry_indicators['bb_position'],
                ma_trend=context.entry_indicators['ma_trend'],
                volume_ratio=context.entry_indicators['volume_ratio'],

                # 신호 정보
                signal_source=context.signal_source,  # ['LSTM', 'TA', 'SD']
                signal_strength=context.signal_strength,
                signal_confidence=context.signal_confidence,
                agreement_count=context.agreement_count,

                # 시장 상황
                market_regime=context.market_regime,
                sector_rank=context.sector_rank,
                vix_level=context.vix_level,

                # MTF 상태
                daily_trend=context.daily_trend,
                weekly_trend=context.weekly_trend,
                monthly_trend=context.monthly_trend,
            ),

            # 청산 시점 상태
            exit_context=ExitContext(
                exit_reason=trade.exit_reason,  # signal, stop_loss, take_profit, trailing, timeout
                indicators_at_exit=context.exit_indicators,
                market_regime_at_exit=context.exit_market_regime,
                max_profit_during=context.max_profit_during,
                max_loss_during=context.max_loss_during,
            ),

            # 분류 레이블 (학습용)
            labels=TradeLabels(
                is_winner=trade.pnl > 0,
                is_big_winner=trade.pnl_pct > 5,
                is_big_loser=trade.pnl_pct < -3,
                exit_optimal=self._evaluate_exit_timing(trade, context),
                entry_optimal=self._evaluate_entry_timing(trade, context),
            )
        )

        # DB에 저장
        self.db.save_trade_log(log)

        return log

    def _evaluate_exit_timing(self, trade: Trade, context: TradeContext) -> str:
        """
        청산 타이밍 평가

        분류:
        - 'optimal': 최적 타이밍 (고점/저점 근처)
        - 'early': 너무 일찍 (더 갈 수 있었음)
        - 'late': 너무 늦음 (수익 반납)
        - 'neutral': 적절함
        """
        if trade.pnl > 0:  # 수익 거래
            # 보유 중 최고점 대비 청산가
            peak_to_exit = (context.max_profit_during - trade.pnl_pct) / context.max_profit_during

            if peak_to_exit < 0.1:  # 최고점 대비 10% 이내 청산
                return 'optimal'
            elif peak_to_exit > 0.5:  # 최고점 대비 50% 이상 반납
                return 'late'
            else:
                return 'neutral'
        else:  # 손실 거래
            # 손절 적시성
            if trade.exit_reason == 'stop_loss':
                return 'neutral'  # 손절 규칙 준수
            elif context.max_loss_during < trade.pnl_pct:  # 더 큰 손실 방지
                return 'optimal'
            else:
                return 'late'
```

### 2.2 성과 패턴 분석

```python
class PerformancePatternAnalyzer:
    """
    거래 성과 패턴 분석

    분석 관점:
    1. 어떤 조건에서 승리하는가?
    2. 어떤 조건에서 패배하는가?
    3. 승리/패배 패턴의 공통점은?
    """

    def analyze_patterns(self, trade_logs: List[TradeLog]) -> PatternAnalysis:
        """
        거래 패턴 종합 분석
        """
        winners = [t for t in trade_logs if t.labels.is_winner]
        losers = [t for t in trade_logs if not t.labels.is_winner]

        return PatternAnalysis(
            # 승리 조건 분석
            winning_conditions=self._analyze_winning_conditions(winners),

            # 패배 조건 분석
            losing_conditions=self._analyze_losing_conditions(losers),

            # 지표별 최적 범위
            optimal_indicator_ranges=self._find_optimal_ranges(trade_logs),

            # 시장 상황별 성과
            performance_by_regime=self._analyze_by_regime(trade_logs),

            # 신호 소스별 성과
            performance_by_source=self._analyze_by_source(trade_logs),

            # 요일/시간별 성과
            performance_by_time=self._analyze_by_time(trade_logs),

            # 보유 기간별 성과
            performance_by_holding=self._analyze_by_holding_period(trade_logs),
        )

    def _analyze_winning_conditions(self, winners: List[TradeLog]) -> WinningConditions:
        """
        승리 거래의 공통 조건 분석

        학습 목표:
        - 높은 승률의 진입 조건 식별
        - 성공적인 청산 패턴 파악
        """
        if not winners:
            return WinningConditions()

        # RSI 분포
        rsi_at_entry = [t.entry_context.rsi for t in winners]
        rsi_mean = np.mean(rsi_at_entry)
        rsi_std = np.std(rsi_at_entry)

        # 신호 일치 수
        agreement_counts = [t.entry_context.agreement_count for t in winners]
        avg_agreement = np.mean(agreement_counts)

        # 시장 레짐 분포
        regime_dist = Counter([t.entry_context.market_regime for t in winners])
        best_regime = regime_dist.most_common(1)[0][0]

        # MTF 정렬
        aligned_count = sum(1 for t in winners
                          if t.entry_context.daily_trend == t.entry_context.weekly_trend)
        alignment_rate = aligned_count / len(winners)

        # 신호 소스
        source_dist = Counter([
            tuple(sorted(t.entry_context.signal_source)) for t in winners
        ])
        best_source_combo = source_dist.most_common(1)[0][0]

        return WinningConditions(
            rsi_range=(rsi_mean - rsi_std, rsi_mean + rsi_std),
            min_agreement=int(avg_agreement),
            best_regime=best_regime,
            mtf_alignment_rate=alignment_rate,
            best_source_combo=list(best_source_combo),

            # 통계
            total_winners=len(winners),
            avg_profit=np.mean([t.pnl_pct for t in winners]),
            avg_holding_days=np.mean([t.holding_days for t in winners]),
        )

    def _find_optimal_ranges(self, trade_logs: List[TradeLog]) -> dict:
        """
        지표별 최적 범위 탐색

        방법: 승률을 최대화하는 지표 범위 탐색
        """
        indicators = ['rsi', 'macd', 'bb_position', 'volume_ratio']
        optimal_ranges = {}

        for indicator in indicators:
            values = [(getattr(t.entry_context, indicator), t.labels.is_winner)
                     for t in trade_logs
                     if hasattr(t.entry_context, indicator)]

            if not values:
                continue

            # 구간별 승률 계산
            df = pd.DataFrame(values, columns=['value', 'is_winner'])
            df['bin'] = pd.qcut(df['value'], q=10, duplicates='drop')

            bin_stats = df.groupby('bin').agg({
                'is_winner': ['mean', 'count']
            })

            # 승률 60% 이상인 구간
            good_bins = bin_stats[bin_stats[('is_winner', 'mean')] >= 0.6]

            if not good_bins.empty:
                optimal_ranges[indicator] = {
                    'ranges': [(b.left, b.right) for b in good_bins.index],
                    'win_rate': good_bins[('is_winner', 'mean')].mean(),
                    'sample_size': good_bins[('is_winner', 'count')].sum()
                }

        return optimal_ranges
```

### 2.3 실패 분석 및 학습

```python
class FailureAnalyzer:
    """
    실패 거래 심층 분석

    목표:
    - 같은 실수 반복 방지
    - 실패 패턴 식별 및 필터링
    - 손절 개선점 도출
    """

    def analyze_failures(self, losers: List[TradeLog]) -> FailureAnalysis:
        """
        실패 거래 분석
        """
        # 실패 유형 분류
        failure_types = self._classify_failures(losers)

        # 각 유형별 분석
        analyses = {}
        for failure_type, trades in failure_types.items():
            analyses[failure_type] = self._analyze_failure_type(failure_type, trades)

        return FailureAnalysis(
            failure_distribution=failure_types,
            type_analyses=analyses,
            common_mistakes=self._find_common_mistakes(losers),
            improvement_suggestions=self._generate_improvements(analyses)
        )

    def _classify_failures(self, losers: List[TradeLog]) -> dict:
        """
        실패 유형 분류

        유형:
        1. TREND_AGAINST: 추세 역행 진입
        2. EARLY_ENTRY: 너무 이른 진입
        3. LATE_ENTRY: 너무 늦은 진입
        4. BAD_TIMING: 시장 타이밍 실패
        5. STOP_TOO_TIGHT: 손절 너무 타이트
        6. STOP_TOO_WIDE: 손절 너무 넓음
        7. WEAK_SIGNAL: 약한 신호에 진입
        """
        classified = defaultdict(list)

        for trade in losers:
            # 추세 역행 체크
            if (trade.entry_context.daily_trend != trade.entry_context.weekly_trend):
                classified['TREND_AGAINST'].append(trade)

            # 신호 강도 체크
            elif trade.entry_context.signal_confidence < 0.6:
                classified['WEAK_SIGNAL'].append(trade)

            # 신호 일치 부족
            elif trade.entry_context.agreement_count < 2:
                classified['LOW_AGREEMENT'].append(trade)

            # 손절 타이밍 분석
            elif trade.exit_reason == 'stop_loss':
                if trade.entry_context.max_loss_during > trade.pnl_pct * 1.5:
                    classified['STOP_TOO_TIGHT'].append(trade)
                else:
                    classified['MARKET_MOVED'].append(trade)

            else:
                classified['OTHER'].append(trade)

        return dict(classified)

    def _generate_improvements(self, analyses: dict) -> List[Improvement]:
        """
        개선점 도출

        각 실패 유형에 대한 구체적 개선 방안
        """
        improvements = []

        if 'TREND_AGAINST' in analyses:
            analysis = analyses['TREND_AGAINST']
            if analysis['count'] > 5:
                improvements.append(Improvement(
                    priority='high',
                    category='entry_filter',
                    action='ADD_MTF_ALIGNMENT_CHECK',
                    description="MTF 정렬 필터 추가: 일/주봉 추세 일치 시에만 진입",
                    expected_impact=f"예상 승률 개선: +{analysis['potential_win_rate_gain']:.1%}",
                    implementation="""
                    if daily_trend != weekly_trend:
                        return Signal(type=HOLD, reason='MTF_NOT_ALIGNED')
                    """
                ))

        if 'WEAK_SIGNAL' in analyses:
            analysis = analyses['WEAK_SIGNAL']
            improvements.append(Improvement(
                priority='high',
                category='signal_filter',
                action='INCREASE_CONFIDENCE_THRESHOLD',
                description="최소 신뢰도 임계값 상향: 60% → 70%",
                expected_impact=f"약 {analysis['count']}건 손실 회피 가능",
                implementation="""
                self.min_confidence = 0.70  # 기존 0.60
                """
            ))

        if 'LOW_AGREEMENT' in analyses:
            analysis = analyses['LOW_AGREEMENT']
            improvements.append(Improvement(
                priority='medium',
                category='signal_filter',
                action='REQUIRE_MORE_AGREEMENT',
                description="최소 신호 일치 수 상향: 2개 → 3개",
                expected_impact=f"거래 수 감소하나 승률 개선",
                implementation="""
                self.min_agreement = 3  # 기존 2
                """
            ))

        return sorted(improvements, key=lambda x: x.priority)
```

---

## 3. 모델 지속 학습

### 3.1 LSTM 모델 재학습

```python
class LSTMContinuousLearner:
    """
    LSTM 모델 지속 학습 시스템

    학습 전략:
    1. 정기 재학습 (주간/월간)
    2. 성과 저하 시 즉시 재학습
    3. 시장 레짐 변화 시 재학습
    """

    def __init__(self):
        self.retrain_period = 'weekly'     # 정기 재학습 주기
        self.min_new_samples = 100         # 최소 신규 샘플
        self.performance_threshold = 0.55  # 성과 임계값 (55% 미만시 재학습)
        self.lookback_days = 252           # 학습 데이터 기간 (1년)

    def should_retrain(self, current_performance: dict) -> RetrainDecision:
        """
        재학습 필요 여부 판단
        """
        reasons = []

        # 1. 정기 재학습 체크
        if self._is_scheduled_retrain_time():
            reasons.append('scheduled')

        # 2. 성과 저하 체크
        recent_accuracy = current_performance.get('recent_accuracy', 0)
        if recent_accuracy < self.performance_threshold:
            reasons.append(f'low_performance ({recent_accuracy:.1%})')

        # 3. 시장 레짐 변화 체크
        if self._detect_regime_change():
            reasons.append('regime_change')

        # 4. 신규 데이터 충분 체크
        new_samples = self._count_new_samples()
        if new_samples >= self.min_new_samples:
            reasons.append(f'sufficient_new_data ({new_samples})')

        should_retrain = len(reasons) > 0

        return RetrainDecision(
            should_retrain=should_retrain,
            reasons=reasons,
            urgency='high' if 'low_performance' in str(reasons) else 'normal'
        )

    def retrain(self, force: bool = False) -> RetrainResult:
        """
        모델 재학습 실행

        절차:
        1. 데이터 준비 (최근 1년)
        2. 피처 엔지니어링
        3. 학습/검증 분할
        4. 모델 학습
        5. 성능 검증
        6. 기존 모델과 비교
        7. 조건 충족 시 교체
        """
        # 1. 데이터 준비
        training_data = self._prepare_training_data()

        # 2. 피처 생성
        X, y = self._create_features(training_data)

        # 3. 학습/검증 분할 (시계열 분할)
        X_train, X_val, y_train, y_val = self._time_series_split(X, y)

        # 4. 모델 학습
        new_model = self._train_model(X_train, y_train)

        # 5. 검증
        val_accuracy = self._evaluate(new_model, X_val, y_val)
        old_accuracy = self._evaluate(self.current_model, X_val, y_val)

        # 6. 비교 및 교체 결정
        improvement = val_accuracy - old_accuracy

        result = RetrainResult(
            new_accuracy=val_accuracy,
            old_accuracy=old_accuracy,
            improvement=improvement,
            training_samples=len(X_train),
            validation_samples=len(X_val),
        )

        # 7. 교체 조건: 개선 또는 기존 대비 95% 이상 성능
        if improvement > 0 or val_accuracy >= old_accuracy * 0.95:
            self._replace_model(new_model)
            result.model_replaced = True
            result.replacement_reason = 'improved' if improvement > 0 else 'acceptable'
        else:
            result.model_replaced = False
            result.replacement_reason = 'not_improved'

        return result

    def _create_features(self, data: pd.DataFrame) -> Tuple[np.array, np.array]:
        """
        학습용 피처 생성

        피처 카테고리:
        1. 가격 기반 (수익률, 변동성)
        2. 기술적 지표 (RSI, MACD, BB 등)
        3. 거래량 기반 (거래량 비율, 추세)
        4. 시장 상황 (레짐, VIX)
        5. 시간 기반 (요일, 월)
        """
        features = []

        for i in range(self.sequence_length, len(data)):
            window = data.iloc[i-self.sequence_length:i]

            feature_vector = np.concatenate([
                # 가격 피처
                self._price_features(window),

                # 기술적 지표
                self._technical_features(window),

                # 거래량 피처
                self._volume_features(window),

                # 시장 피처
                self._market_features(window),
            ])

            features.append(feature_vector)

        # 레이블: 다음 N일 수익률 (양수/음수)
        labels = (data['close'].pct_change(self.prediction_horizon)
                  .shift(-self.prediction_horizon)
                  .iloc[self.sequence_length:-self.prediction_horizon] > 0).astype(int)

        return np.array(features), np.array(labels)
```

### 3.2 앙상블 가중치 학습

```python
class EnsembleWeightLearner:
    """
    앙상블 가중치 자동 학습

    학습 방법:
    1. 최근 성과 기반 조정
    2. 시장 상황별 최적 가중치
    3. 베이지안 최적화
    """

    def __init__(self):
        self.evaluation_window = 20  # 평가 기간 (20 거래일)
        self.min_weight = 0.15       # 최소 가중치
        self.max_weight = 0.50       # 최대 가중치
        self.learning_rate = 0.1     # 학습률

    def learn_weights(self,
                     strategy_signals: Dict[str, List[Signal]],
                     actual_results: List[TradeResult]) -> Dict[str, float]:
        """
        전략별 최적 가중치 학습

        방법: 각 전략의 신호 정확도 기반 가중치 조정
        """
        # 각 전략 성과 평가
        strategy_performance = {}

        for strategy_name, signals in strategy_signals.items():
            # 신호와 실제 결과 매칭
            matches = self._match_signals_to_results(signals, actual_results)

            # 정확도 계산
            accuracy = self._calculate_accuracy(matches)
            profit_factor = self._calculate_profit_factor(matches)
            sharpe = self._calculate_sharpe(matches)

            # 종합 점수
            score = (accuracy * 0.4 + profit_factor * 0.3 + sharpe * 0.3)
            strategy_performance[strategy_name] = score

        # 점수 기반 가중치 계산
        total_score = sum(strategy_performance.values())
        raw_weights = {k: v / total_score for k, v in strategy_performance.items()}

        # 제한 범위 적용
        adjusted_weights = {}
        for strategy, weight in raw_weights.items():
            adjusted = max(self.min_weight, min(self.max_weight, weight))
            adjusted_weights[strategy] = adjusted

        # 정규화
        total = sum(adjusted_weights.values())
        final_weights = {k: v / total for k, v in adjusted_weights.items()}

        return final_weights

    def learn_regime_specific_weights(self,
                                     historical_data: Dict,
                                     regimes: List[MarketRegime]) -> Dict:
        """
        시장 레짐별 최적 가중치 학습

        각 레짐에서 어떤 전략이 잘 작동하는지 학습
        """
        regime_weights = {}

        for regime in set(regimes):
            # 해당 레짐 기간 데이터 필터링
            regime_data = self._filter_by_regime(historical_data, regime)

            if len(regime_data) < 50:  # 최소 샘플
                continue

            # 해당 레짐에서 최적 가중치 탐색
            optimal_weights = self._optimize_weights_for_regime(regime_data)
            regime_weights[regime] = optimal_weights

        return regime_weights

    def _optimize_weights_for_regime(self, regime_data: Dict) -> Dict[str, float]:
        """
        베이지안 최적화로 특정 레짐 최적 가중치 탐색
        """
        from scipy.optimize import minimize

        strategies = list(regime_data['signals'].keys())
        n = len(strategies)

        def objective(weights):
            # 가중 신호 생성
            combined_signals = self._combine_signals(
                regime_data['signals'],
                dict(zip(strategies, weights))
            )

            # 백테스트 성과
            performance = self._quick_backtest(combined_signals, regime_data['prices'])

            # 최대화 → 최소화 변환
            return -performance['sharpe_ratio']

        # 제약: 합 = 1
        constraints = {'type': 'eq', 'fun': lambda w: sum(w) - 1}
        bounds = [(self.min_weight, self.max_weight) for _ in range(n)]

        # 초기값
        x0 = [1/n] * n

        result = minimize(objective, x0, method='SLSQP',
                         bounds=bounds, constraints=constraints)

        return dict(zip(strategies, result.x))
```

### 3.3 지표 파라미터 자동 최적화

```python
class IndicatorParameterOptimizer:
    """
    기술적 지표 파라미터 자동 최적화

    최적화 대상:
    - RSI 기간, 과매수/과매도 레벨
    - MACD 파라미터
    - 이동평균 기간
    - 볼린저밴드 파라미터
    """

    def optimize_parameters(self,
                           historical_data: pd.DataFrame,
                           indicator: str,
                           param_ranges: dict) -> OptimizedParams:
        """
        그리드 서치 + 워크포워드로 파라미터 최적화
        """
        best_params = None
        best_score = -np.inf

        # 그리드 생성
        param_grid = self._create_grid(param_ranges)

        for params in param_grid:
            # 워크포워드 검증
            scores = self._walk_forward_test(
                historical_data, indicator, params
            )

            avg_score = np.mean(scores)

            if avg_score > best_score:
                best_score = avg_score
                best_params = params

        return OptimizedParams(
            indicator=indicator,
            parameters=best_params,
            score=best_score,
            validation_method='walk_forward'
        )

    def _walk_forward_test(self,
                          data: pd.DataFrame,
                          indicator: str,
                          params: dict,
                          n_splits: int = 5) -> List[float]:
        """
        워크포워드 테스트

        과최적화 방지를 위한 롤링 검증
        """
        scores = []
        split_size = len(data) // (n_splits + 1)

        for i in range(n_splits):
            # 학습 기간: 처음 ~ i+1 구간
            train_end = (i + 1) * split_size
            train_data = data.iloc[:train_end]

            # 검증 기간: i+1 ~ i+2 구간
            test_start = train_end
            test_end = (i + 2) * split_size
            test_data = data.iloc[test_start:test_end]

            # 해당 파라미터로 지표 계산 및 성과 측정
            score = self._evaluate_indicator(
                test_data, indicator, params
            )
            scores.append(score)

        return scores
```

---

## 4. 시장 적응 학습

### 4.1 시장 레짐 감지 학습

```python
class RegimeDetectorLearner:
    """
    시장 레짐 감지 모델 학습

    레짐 분류:
    - BULL: 상승장
    - BEAR: 하락장
    - RANGE: 횡보장
    - HIGH_VOL: 고변동성
    """

    def __init__(self):
        self.features = [
            'market_return_20d',    # 20일 시장 수익률
            'market_volatility',     # 변동성
            'trend_strength',        # 추세 강도 (ADX)
            'breadth',              # 시장 폭 (상승 종목 비율)
            'vix_level',            # VIX
            'volume_trend',         # 거래량 추세
        ]

    def train_regime_classifier(self,
                               market_data: pd.DataFrame,
                               labeled_regimes: pd.Series) -> RegimeClassifier:
        """
        레짐 분류기 학습

        모델: Random Forest (해석 가능성)
        """
        # 피처 생성
        X = self._create_regime_features(market_data)
        y = labeled_regimes

        # 학습/검증 분할
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, shuffle=False  # 시계열이므로 셔플 X
        )

        # 모델 학습
        model = RandomForestClassifier(
            n_estimators=100,
            max_depth=5,  # 과적합 방지
            min_samples_leaf=20
        )
        model.fit(X_train, y_train)

        # 평가
        accuracy = model.score(X_test, y_test)

        # 피처 중요도
        feature_importance = dict(zip(self.features, model.feature_importances_))

        return RegimeClassifier(
            model=model,
            accuracy=accuracy,
            feature_importance=feature_importance
        )

    def update_regime_labels(self,
                            market_data: pd.DataFrame,
                            actual_performance: pd.DataFrame) -> pd.Series:
        """
        실제 성과 기반 레짐 레이블 업데이트

        성과가 좋았던 기간의 레짐을 "맞는 레짐"으로 학습
        """
        # 현재 레짐 예측
        predicted_regimes = self.current_model.predict(market_data)

        # 실제 성과와 비교
        for i, regime in enumerate(predicted_regimes):
            expected_strategy = self.regime_strategies[regime]
            actual_return = actual_performance.iloc[i]

            # 성과가 기대에 못 미치면 레짐 재분류 고려
            if actual_return < expected_strategy['min_return']:
                # 다른 레짐이었을 가능성 체크
                alternative_regime = self._find_better_regime(
                    market_data.iloc[i], actual_return
                )
                if alternative_regime:
                    predicted_regimes[i] = alternative_regime

        return predicted_regimes
```

### 4.2 전략 자동 선택 학습

```python
class StrategySelector:
    """
    시장 상황에 따른 전략 자동 선택

    학습 목표:
    - 어떤 시장에서 어떤 전략이 최적인지 학습
    - 전략 전환 타이밍 학습
    """

    def __init__(self):
        self.strategies = {
            'momentum': MomentumStrategy(),
            'mean_reversion': MeanReversionStrategy(),
            'trend_following': TrendFollowingStrategy(),
            'defensive': DefensiveStrategy(),
        }

        # 전략별 적합 레짐 (초기값, 학습으로 업데이트)
        self.strategy_regime_fit = {
            'momentum': [MarketRegime.BULL],
            'mean_reversion': [MarketRegime.RANGE],
            'trend_following': [MarketRegime.BULL, MarketRegime.BEAR],
            'defensive': [MarketRegime.BEAR, MarketRegime.HIGH_VOL],
        }

    def learn_strategy_selection(self,
                                historical_regimes: List[MarketRegime],
                                strategy_performances: Dict[str, Dict]) -> None:
        """
        레짐별 최적 전략 학습

        각 레짐에서 각 전략의 성과 분석 후 매핑 업데이트
        """
        regime_strategy_scores = defaultdict(dict)

        for regime in set(historical_regimes):
            for strategy_name, perf in strategy_performances.items():
                # 해당 레짐 기간의 전략 성과
                regime_perf = self._filter_performance_by_regime(
                    perf, historical_regimes, regime
                )

                if len(regime_perf) < 10:  # 최소 샘플
                    continue

                # 성과 점수
                score = (
                    regime_perf['sharpe_ratio'] * 0.4 +
                    regime_perf['win_rate'] * 0.3 +
                    (1 - abs(regime_perf['max_drawdown'])) * 0.3
                )

                regime_strategy_scores[regime][strategy_name] = score

        # 레짐별 최적 전략 업데이트
        for regime, scores in regime_strategy_scores.items():
            if not scores:
                continue

            # 점수 기준 정렬
            sorted_strategies = sorted(scores.items(), key=lambda x: x[1], reverse=True)

            # 상위 2개 전략을 해당 레짐에 매핑
            best_strategies = [s[0] for s in sorted_strategies[:2]]

            # 매핑 업데이트
            self.strategy_regime_fit = self._update_regime_mapping(
                self.strategy_regime_fit, regime, best_strategies
            )

    def select_strategy(self, current_regime: MarketRegime) -> str:
        """
        현재 레짐에 최적인 전략 선택
        """
        # 해당 레짐에 적합한 전략들
        suitable_strategies = []
        for strategy, regimes in self.strategy_regime_fit.items():
            if current_regime in regimes:
                suitable_strategies.append(strategy)

        if not suitable_strategies:
            return 'defensive'  # 기본값

        # 최근 성과가 가장 좋은 전략 선택
        best_strategy = max(
            suitable_strategies,
            key=lambda s: self._get_recent_performance(s)
        )

        return best_strategy
```

---

## 5. 학습 주기 및 자동화

### 5.1 학습 스케줄

```python
class LearningScheduler:
    """
    학습 작업 스케줄 관리

    스케줄:
    - 실시간: 거래 로그 수집
    - 일간: 당일 성과 분석
    - 주간: 가중치 조정, 파라미터 미세 조정
    - 월간: 모델 재학습, 전략 재평가
    - 분기: 전체 시스템 리뷰
    """

    def __init__(self):
        self.schedule = {
            'realtime': [
                {'task': 'log_trade', 'trigger': 'on_trade'},
                {'task': 'update_metrics', 'trigger': 'on_price_update'},
            ],
            'daily': [
                {'task': 'daily_performance_analysis', 'time': '16:00'},
                {'task': 'failure_analysis', 'time': '16:30'},
                {'task': 'update_regime', 'time': '17:00'},
            ],
            'weekly': [
                {'task': 'adjust_ensemble_weights', 'day': 'friday', 'time': '17:00'},
                {'task': 'optimize_indicator_params', 'day': 'saturday', 'time': '10:00'},
                {'task': 'sector_rotation_update', 'day': 'sunday', 'time': '18:00'},
            ],
            'monthly': [
                {'task': 'retrain_lstm', 'day': 1, 'time': '06:00'},
                {'task': 'strategy_performance_review', 'day': 1, 'time': '10:00'},
                {'task': 'regime_classifier_update', 'day': 15, 'time': '06:00'},
            ],
            'quarterly': [
                {'task': 'full_system_review', 'month': [1, 4, 7, 10], 'day': 1},
                {'task': 'backtest_all_strategies', 'month': [1, 4, 7, 10], 'day': 2},
            ]
        }

    def run_scheduled_tasks(self):
        """
        스케줄된 학습 작업 실행
        """
        current_time = datetime.now()

        # 일간 작업
        for task in self.schedule['daily']:
            if self._should_run(task, current_time):
                self._execute_task(task['task'])

        # 주간 작업
        for task in self.schedule['weekly']:
            if self._should_run_weekly(task, current_time):
                self._execute_task(task['task'])

        # 월간 작업
        for task in self.schedule['monthly']:
            if self._should_run_monthly(task, current_time):
                self._execute_task(task['task'])
```

### 5.2 학습 결과 추적

```python
class LearningTracker:
    """
    학습 결과 추적 및 버전 관리

    추적 항목:
    - 모델 버전
    - 파라미터 변경 이력
    - 성과 변화 추이
    """

    def __init__(self):
        self.db = LearningDatabase()

    def log_learning_result(self, result: LearningResult) -> None:
        """
        학습 결과 기록
        """
        record = LearningRecord(
            timestamp=datetime.now(),
            learning_type=result.type,  # 'model_retrain', 'weight_adjust', etc.

            # 변경 전/후 상태
            before_state=result.before_state,
            after_state=result.after_state,

            # 성과 지표
            before_performance=result.before_performance,
            after_performance=result.after_performance,
            improvement=result.improvement,

            # 메타데이터
            training_samples=result.training_samples,
            validation_score=result.validation_score,
            notes=result.notes
        )

        self.db.save(record)

    def get_learning_history(self,
                            learning_type: str = None,
                            days: int = 30) -> List[LearningRecord]:
        """
        학습 이력 조회
        """
        return self.db.query(
            learning_type=learning_type,
            since=datetime.now() - timedelta(days=days)
        )

    def analyze_learning_effectiveness(self) -> LearningEffectivenessReport:
        """
        학습 효과 분석

        질문:
        - 학습 후 성과가 개선되었는가?
        - 어떤 유형의 학습이 가장 효과적인가?
        - 학습 주기는 적절한가?
        """
        history = self.get_learning_history(days=90)

        return LearningEffectivenessReport(
            # 학습 유형별 효과
            effectiveness_by_type={
                learning_type: self._analyze_type_effectiveness(
                    [r for r in history if r.learning_type == learning_type]
                )
                for learning_type in set(r.learning_type for r in history)
            },

            # 전체 개선율
            overall_improvement=self._calculate_overall_improvement(history),

            # 권장 사항
            recommendations=self._generate_recommendations(history)
        )
```

---

## 6. 학습 안전장치

### 6.1 과적합 방지

```python
class OverfitPrevention:
    """
    학습 과적합 방지 장치

    방지 메커니즘:
    1. 워크포워드 검증 필수
    2. 최소 샘플 수 요구
    3. 성과 변화 제한
    4. A/B 테스트
    """

    def validate_learning_result(self, result: LearningResult) -> ValidationResult:
        """
        학습 결과 검증
        """
        checks = []

        # 1. 최소 샘플 수
        if result.training_samples < 100:
            checks.append(ValidationCheck(
                passed=False,
                check='min_samples',
                message=f"샘플 부족: {result.training_samples} < 100"
            ))
        else:
            checks.append(ValidationCheck(passed=True, check='min_samples'))

        # 2. 과적합 징후 (학습/검증 성과 차이)
        train_val_gap = result.training_score - result.validation_score
        if train_val_gap > 0.1:  # 10% 이상 차이
            checks.append(ValidationCheck(
                passed=False,
                check='overfit_gap',
                message=f"과적합 의심: 학습/검증 차이 {train_val_gap:.1%}"
            ))
        else:
            checks.append(ValidationCheck(passed=True, check='overfit_gap'))

        # 3. 급격한 변화
        if abs(result.improvement) > 0.3:  # 30% 이상 변화
            checks.append(ValidationCheck(
                passed=False,
                check='sudden_change',
                message=f"급격한 변화: {result.improvement:.1%}"
            ))
        else:
            checks.append(ValidationCheck(passed=True, check='sudden_change'))

        # 4. Out-of-sample 성과
        if result.out_of_sample_score < result.validation_score * 0.8:
            checks.append(ValidationCheck(
                passed=False,
                check='oos_performance',
                message="Out-of-sample 성과 저조"
            ))
        else:
            checks.append(ValidationCheck(passed=True, check='oos_performance'))

        all_passed = all(c.passed for c in checks)

        return ValidationResult(
            passed=all_passed,
            checks=checks,
            recommendation='apply' if all_passed else 'reject'
        )
```

### 6.2 롤백 메커니즘

```python
class ModelRollback:
    """
    학습 실패 시 롤백 메커니즘

    롤백 조건:
    - 새 모델 적용 후 성과 급격히 악화
    - 연속 3회 이상 손실
    - 시스템 오류 발생
    """

    def __init__(self):
        self.model_history = []  # 모델 버전 히스토리
        self.performance_window = 10  # 성과 평가 기간

    def should_rollback(self,
                       current_model_performance: float,
                       previous_model_performance: float) -> RollbackDecision:
        """
        롤백 필요 여부 판단
        """
        performance_drop = previous_model_performance - current_model_performance

        # 조건 1: 성과 급락 (20% 이상)
        if performance_drop > 0.2:
            return RollbackDecision(
                should_rollback=True,
                reason=f"성과 급락: {performance_drop:.1%}",
                target_version=self._get_previous_version()
            )

        # 조건 2: 연속 손실
        recent_trades = self._get_recent_trades(self.performance_window)
        consecutive_losses = self._count_consecutive_losses(recent_trades)

        if consecutive_losses >= 5:
            return RollbackDecision(
                should_rollback=True,
                reason=f"연속 {consecutive_losses}회 손실",
                target_version=self._get_previous_version()
            )

        return RollbackDecision(should_rollback=False)

    def rollback(self, target_version: str) -> bool:
        """
        이전 모델로 롤백
        """
        previous_model = self._load_model_version(target_version)

        if previous_model is None:
            return False

        # 현재 모델 백업
        self._backup_current_model()

        # 롤백 실행
        self.current_model = previous_model

        # 알림
        self._send_rollback_notification(target_version)

        return True
```

---

## 7. 구현 우선순위

### Phase 1: 거래 학습 (Week 1)
```
1. core/learning/trade_logger.py        - 거래 로그 수집
2. core/learning/performance_analyzer.py - 성과 패턴 분석
3. core/learning/failure_analyzer.py    - 실패 분석
```

### Phase 2: 모델 학습 (Week 2)
```
1. core/learning/lstm_learner.py        - LSTM 재학습
2. core/learning/weight_learner.py      - 앙상블 가중치 학습
3. core/learning/param_optimizer.py     - 파라미터 최적화
```

### Phase 3: 시장 적응 (Week 3)
```
1. core/learning/regime_learner.py      - 레짐 감지 학습
2. core/learning/strategy_selector.py   - 전략 선택 학습
```

### Phase 4: 자동화 (Week 4)
```
1. core/learning/scheduler.py           - 학습 스케줄러
2. core/learning/tracker.py             - 학습 추적
3. core/learning/safety.py              - 안전장치
```

---

*다음 문서: `04_IMPLEMENTATION_CHECKLIST.md` - 구현 체크리스트*
