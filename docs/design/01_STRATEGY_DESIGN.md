# 🎯 전략 고도화 설계서

> **핵심 철학**: 단일 전략이 아닌, 시장 상황에 따라 학습하고 적응하는 지능형 시스템
> **목표**: 연 25%+ 수익률, MDD 10% 이내, 샤프비율 2.0 이상

---

## 1. 앙상블 전략 시스템 (Ensemble Strategy)

### 1.1 왜 앙상블인가?

단일 전략의 한계:
- 특정 시장 상황에서만 작동
- 과최적화 위험
- 드로다운 집중

앙상블의 장점:
- 다양한 시장에서 안정적 성과
- 개별 전략 실패 시 보완
- 신뢰도 높은 신호만 선별

### 1.2 앙상블 구성 요소

```
┌─────────────────────────────────────────────────────────────────┐
│                      앙상블 전략 시스템                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│   │   LSTM      │  │  기술적분석  │  │   수급분석   │            │
│   │  (딥러닝)   │  │  (TA 지표)  │  │  (거래량)   │            │
│   └──────┬──────┘  └──────┬──────┘  └──────┬──────┘            │
│          │                │                │                    │
│          ▼                ▼                ▼                    │
│   ┌─────────────────────────────────────────────────────┐      │
│   │              신호 집계기 (Signal Aggregator)          │      │
│   │  - 가중 투표 (Weighted Voting)                       │      │
│   │  - 동적 가중치 조정                                   │      │
│   │  - 신뢰도 점수 산출                                   │      │
│   └──────────────────────┬──────────────────────────────┘      │
│                          ▼                                      │
│   ┌─────────────────────────────────────────────────────┐      │
│   │              최종 신호 (Final Signal)                 │      │
│   │  - 진입/청산 결정                                     │      │
│   │  - 포지션 크기 결정                                   │      │
│   │  - 손절/익절 레벨                                     │      │
│   └─────────────────────────────────────────────────────┘      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 1.3 개별 전략 상세

#### 1.3.1 LSTM 기반 예측 (기존 구현 활용)

**입력 피처 (Feature Set):**
```python
features = {
    # 가격 기반 (5개)
    'returns_1d': '1일 수익률',
    'returns_5d': '5일 수익률',
    'returns_20d': '20일 수익률',
    'price_ma_ratio': '현재가/MA20 비율',
    'price_volatility': '가격 변동성 (20일)',

    # 기술적 지표 (7개)
    'rsi_14': 'RSI 14일',
    'macd_signal': 'MACD 시그널',
    'bb_position': '볼린저밴드 내 위치 (0~1)',
    'stoch_k': '스토캐스틱 %K',
    'cci_20': 'CCI 20일',
    'adx_14': 'ADX 추세강도',
    'obv_change': 'OBV 변화율',

    # 수급 지표 (5개)
    'volume_ratio': '거래량/평균거래량',
    'volume_trend': '거래량 추세',
    'foreign_flow': '외국인 순매수 추이',
    'institution_flow': '기관 순매수 추이',
    'program_flow': '프로그램 순매수',
}
```

**LSTM 신호 생성 로직:**
```python
def generate_lstm_signal(self, data: pd.DataFrame) -> Signal:
    """
    LSTM 모델 예측 기반 신호 생성

    예측값 해석:
    - 0.7 이상: 강한 매수 신호
    - 0.6~0.7: 약한 매수 신호
    - 0.4~0.6: 중립 (Hold)
    - 0.3~0.4: 약한 매도 신호
    - 0.3 이하: 강한 매도 신호
    """
    prediction = self.model.predict(features)
    probability = prediction['up_probability']

    if probability >= 0.7:
        return Signal(
            type=SignalType.BUY,
            strength=2.0,  # 강한 신호
            confidence=probability,
            source='LSTM'
        )
    elif probability >= 0.6:
        return Signal(
            type=SignalType.BUY,
            strength=1.0,  # 약한 신호
            confidence=probability,
            source='LSTM'
        )
    elif probability <= 0.3:
        return Signal(
            type=SignalType.SELL,
            strength=2.0,
            confidence=1 - probability,
            source='LSTM'
        )
    elif probability <= 0.4:
        return Signal(
            type=SignalType.SELL,
            strength=1.0,
            confidence=1 - probability,
            source='LSTM'
        )
    else:
        return Signal(type=SignalType.HOLD, source='LSTM')
```

#### 1.3.2 기술적 분석 (Technical Analysis)

**복합 TA 점수 시스템:**
```python
class TechnicalAnalyzer:
    """
    다중 지표 기반 기술적 분석
    각 지표는 -100 ~ +100 점수 부여
    """

    def calculate_ta_score(self, data: pd.DataFrame) -> dict:
        scores = {}

        # 1. 추세 지표 (40% 가중치)
        scores['ma_cross'] = self._ma_cross_score(data)      # -100 ~ +100
        scores['macd'] = self._macd_score(data)              # -100 ~ +100
        scores['adx'] = self._adx_score(data)                # 0 ~ +100 (추세 강도)

        # 2. 모멘텀 지표 (30% 가중치)
        scores['rsi'] = self._rsi_score(data)                # -100 ~ +100
        scores['stochastic'] = self._stochastic_score(data)  # -100 ~ +100
        scores['cci'] = self._cci_score(data)                # -100 ~ +100

        # 3. 변동성 지표 (15% 가중치)
        scores['bollinger'] = self._bollinger_score(data)    # -100 ~ +100
        scores['atr_position'] = self._atr_score(data)       # 0 ~ +100

        # 4. 거래량 지표 (15% 가중치)
        scores['volume'] = self._volume_score(data)          # -100 ~ +100
        scores['obv'] = self._obv_score(data)                # -100 ~ +100

        return scores

    def _rsi_score(self, data: pd.DataFrame) -> float:
        """
        RSI 점수 계산

        매수 영역 (RSI < 30): +50 ~ +100
        중립 영역 (30 <= RSI <= 70): -20 ~ +20
        매도 영역 (RSI > 70): -50 ~ -100

        추가 가점:
        - RSI 다이버전스 발생 시 ±30점
        - RSI가 과매수/과매도에서 반전 시 ±20점
        """
        rsi = calculate_rsi(data['close'], period=14)
        current_rsi = rsi.iloc[-1]
        prev_rsi = rsi.iloc[-2]

        # 기본 점수
        if current_rsi < 30:
            base_score = 50 + (30 - current_rsi) * 1.67  # 50 ~ 100
        elif current_rsi > 70:
            base_score = -50 - (current_rsi - 70) * 1.67  # -50 ~ -100
        else:
            # 30~70 범위: -20 ~ +20 선형
            base_score = (50 - current_rsi) * 0.5

        # 다이버전스 체크
        divergence = self._check_divergence(data['close'], rsi)
        if divergence == 'bullish':
            base_score += 30
        elif divergence == 'bearish':
            base_score -= 30

        # 반전 신호 체크
        if prev_rsi < 30 and current_rsi > 30:  # 과매도 탈출
            base_score += 20
        elif prev_rsi > 70 and current_rsi < 70:  # 과매수 탈출
            base_score -= 20

        return max(-100, min(100, base_score))
```

**TA 신호 생성:**
```python
def generate_ta_signal(self, data: pd.DataFrame) -> Signal:
    """
    기술적 분석 기반 신호 생성

    종합 점수 해석:
    - +60 이상: 강한 매수
    - +30 ~ +60: 약한 매수
    - -30 ~ +30: 중립
    - -60 ~ -30: 약한 매도
    - -60 이하: 강한 매도
    """
    scores = self.calculate_ta_score(data)

    # 가중 평균 계산
    weighted_score = (
        (scores['ma_cross'] + scores['macd'] + scores['adx']) * 0.4 / 3 +
        (scores['rsi'] + scores['stochastic'] + scores['cci']) * 0.3 / 3 +
        (scores['bollinger'] + scores['atr_position']) * 0.15 / 2 +
        (scores['volume'] + scores['obv']) * 0.15 / 2
    ) * 100

    # 신호 변환
    if weighted_score >= 60:
        return Signal(
            type=SignalType.BUY,
            strength=2.0,
            confidence=weighted_score / 100,
            source='TA',
            metadata={'scores': scores}
        )
    elif weighted_score >= 30:
        return Signal(
            type=SignalType.BUY,
            strength=1.0,
            confidence=weighted_score / 100,
            source='TA'
        )
    # ... 생략
```

#### 1.3.3 수급 분석 (Supply-Demand)

**수급 점수 시스템:**
```python
class SupplyDemandAnalyzer:
    """
    수급 기반 분석
    - 외국인/기관 동향
    - 거래량 패턴
    - 매집/분산 신호
    """

    def calculate_sd_score(self, data: pd.DataFrame) -> dict:
        scores = {}

        # 1. 기관/외국인 수급 (50% 가중치)
        scores['foreign'] = self._foreign_flow_score(data)
        scores['institution'] = self._institution_flow_score(data)

        # 2. 거래량 분석 (30% 가중치)
        scores['volume_surge'] = self._volume_surge_score(data)
        scores['volume_trend'] = self._volume_trend_score(data)

        # 3. 매집/분산 지표 (20% 가중치)
        scores['accumulation'] = self._accumulation_score(data)
        scores['distribution'] = self._distribution_score(data)

        return scores

    def _foreign_flow_score(self, data: pd.DataFrame) -> float:
        """
        외국인 순매수 분석

        5일 연속 순매수: +50점
        5일 연속 순매도: -50점
        20일 누적 매수 추세: ±30점
        대량 순매수 (상위 10%): +20점
        """
        foreign_net = data['foreign_net_buy']

        # 연속 순매수/순매도 일수
        consecutive = self._count_consecutive(foreign_net)

        # 기본 점수: 연속 일수 * 10
        base_score = consecutive * 10

        # 20일 누적 추세
        cumsum_20d = foreign_net.tail(20).sum()
        avg_volume = data['volume'].tail(20).mean()
        trend_score = (cumsum_20d / avg_volume) * 30

        # 대량 매수 체크
        if foreign_net.iloc[-1] > foreign_net.quantile(0.9):
            trend_score += 20

        return max(-100, min(100, base_score + trend_score))
```

### 1.4 신호 집계 및 최종 결정

```python
class SignalAggregator:
    """
    다중 전략 신호 집계

    집계 방식:
    1. 가중 투표 (Weighted Voting)
    2. 동적 가중치 (최근 성과 기반)
    3. 신뢰도 필터링
    """

    def __init__(self):
        # 초기 가중치 (학습으로 조정됨)
        self.weights = {
            'LSTM': 0.40,      # 딥러닝 예측
            'TA': 0.35,        # 기술적 분석
            'SD': 0.25,        # 수급 분석
        }

        # 최소 일치 조건
        self.min_agreement = 2  # 최소 2개 전략 일치
        self.min_confidence = 0.6  # 최소 신뢰도 60%

    def aggregate_signals(self, signals: List[Signal]) -> FinalSignal:
        """
        신호 집계 및 최종 결정

        결정 로직:
        1. 모든 신호가 같은 방향 → 높은 신뢰도
        2. 2개 이상 같은 방향 → 중간 신뢰도
        3. 신호 불일치 → 관망 (HOLD)
        """
        buy_signals = [s for s in signals if s.type == SignalType.BUY]
        sell_signals = [s for s in signals if s.type == SignalType.SELL]

        # 매수 신호 집계
        if len(buy_signals) >= self.min_agreement:
            weighted_confidence = sum(
                s.confidence * self.weights[s.source]
                for s in buy_signals
            ) / sum(self.weights[s.source] for s in buy_signals)

            if weighted_confidence >= self.min_confidence:
                # 신호 강도 계산 (1~3단계)
                avg_strength = sum(s.strength for s in buy_signals) / len(buy_signals)

                return FinalSignal(
                    action=Action.BUY,
                    confidence=weighted_confidence,
                    strength=self._normalize_strength(avg_strength),
                    agreement_count=len(buy_signals),
                    sources=[s.source for s in buy_signals],
                    reason=self._generate_reason(buy_signals)
                )

        # 매도 신호 집계 (동일 로직)
        # ...

        return FinalSignal(action=Action.HOLD, reason="신호 불일치 또는 신뢰도 부족")

    def _normalize_strength(self, avg_strength: float) -> int:
        """
        신호 강도 정규화 (포지션 크기 결정에 사용)

        1단계: 기본 포지션 (50%)
        2단계: 표준 포지션 (100%)
        3단계: 확대 포지션 (150%)
        """
        if avg_strength >= 1.8:
            return 3
        elif avg_strength >= 1.3:
            return 2
        else:
            return 1
```

### 1.5 동적 가중치 조정 (학습 기반)

```python
class DynamicWeightAdjuster:
    """
    전략별 성과에 따른 동적 가중치 조정

    조정 주기: 매주 (금요일 장 마감 후)
    평가 기간: 최근 4주
    """

    def __init__(self):
        self.evaluation_period = 20  # 20 거래일
        self.min_weight = 0.15       # 최소 가중치 15%
        self.max_weight = 0.50       # 최대 가중치 50%

    def adjust_weights(self, strategy_performance: dict) -> dict:
        """
        성과 기반 가중치 조정

        성과 지표:
        - 승률 (40%)
        - 평균 수익률 (30%)
        - 샤프비율 (30%)

        조정 방식:
        - 상대 성과 기반 비례 배분
        - 급격한 변화 방지 (최대 ±10%)
        """
        scores = {}

        for strategy, perf in strategy_performance.items():
            score = (
                perf['win_rate'] * 0.4 +
                self._normalize_return(perf['avg_return']) * 0.3 +
                self._normalize_sharpe(perf['sharpe_ratio']) * 0.3
            )
            scores[strategy] = max(0.1, score)  # 최소 0.1

        # 정규화
        total = sum(scores.values())
        new_weights = {k: v / total for k, v in scores.items()}

        # 급격한 변화 방지
        adjusted_weights = {}
        for strategy, new_weight in new_weights.items():
            old_weight = self.current_weights[strategy]
            change = new_weight - old_weight

            # 최대 ±10% 변화
            capped_change = max(-0.10, min(0.10, change))
            adjusted_weights[strategy] = max(
                self.min_weight,
                min(self.max_weight, old_weight + capped_change)
            )

        # 합이 1이 되도록 재정규화
        total = sum(adjusted_weights.values())
        return {k: v / total for k, v in adjusted_weights.items()}
```

---

## 2. 멀티타임프레임 분석 (MTF)

### 2.1 타임프레임별 역할

```
┌─────────────────────────────────────────────────────────────────┐
│                   멀티타임프레임 전략                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  월봉 (Monthly)                                                 │
│  ├─ 역할: 대세 판단 (Bull/Bear/Range)                          │
│  ├─ 지표: MA12, MA24, 추세선                                   │
│  └─ 결정: 매수만/매도만/양방향                                  │
│                                                                 │
│  주봉 (Weekly)                                                  │
│  ├─ 역할: 중기 추세 및 핵심 레벨                               │
│  ├─ 지표: MA5, MA20, 지지/저항선                               │
│  └─ 결정: 매수 적기/대기/청산 준비                             │
│                                                                 │
│  일봉 (Daily)                                                   │
│  ├─ 역할: 실제 진입/청산 타이밍                                │
│  ├─ 지표: 전체 기술적 지표                                      │
│  └─ 결정: 정확한 진입점, 손절/익절                             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 추세 정렬 (Trend Alignment)

```python
class MultiTimeframeAnalyzer:
    """
    멀티타임프레임 분석기

    핵심 원칙:
    - 상위 타임프레임 방향으로만 거래
    - 모든 타임프레임 정렬 시 최고 신뢰도
    - 역추세 진입 절대 금지
    """

    def analyze(self, stock_code: str) -> MTFAnalysis:
        # 각 타임프레임 분석
        monthly = self._analyze_monthly(stock_code)
        weekly = self._analyze_weekly(stock_code)
        daily = self._analyze_daily(stock_code)

        # 추세 정렬도 계산
        alignment = self._calculate_alignment(monthly, weekly, daily)

        return MTFAnalysis(
            monthly_trend=monthly,
            weekly_trend=weekly,
            daily_trend=daily,
            alignment_score=alignment,
            tradeable=self._is_tradeable(alignment),
            direction=self._get_direction(monthly, weekly)
        )

    def _analyze_monthly(self, stock_code: str) -> TrendAnalysis:
        """
        월봉 분석: 대세 판단

        상승장 조건:
        - 가격 > MA12 (12개월 이동평균)
        - MA12 > MA24
        - 최근 6개월 고점 갱신

        하락장 조건:
        - 가격 < MA12
        - MA12 < MA24
        - 최근 6개월 저점 갱신
        """
        data = self.data_loader.get_monthly(stock_code, periods=36)

        ma12 = data['close'].rolling(12).mean()
        ma24 = data['close'].rolling(24).mean()

        current_price = data['close'].iloc[-1]

        # 추세 판단
        if current_price > ma12.iloc[-1] and ma12.iloc[-1] > ma24.iloc[-1]:
            trend = Trend.BULLISH
            strength = self._calculate_trend_strength(data, 'up')
        elif current_price < ma12.iloc[-1] and ma12.iloc[-1] < ma24.iloc[-1]:
            trend = Trend.BEARISH
            strength = self._calculate_trend_strength(data, 'down')
        else:
            trend = Trend.NEUTRAL
            strength = 0.5

        return TrendAnalysis(
            timeframe='monthly',
            trend=trend,
            strength=strength,
            key_levels={
                'ma12': ma12.iloc[-1],
                'ma24': ma24.iloc[-1],
                'recent_high': data['high'].tail(6).max(),
                'recent_low': data['low'].tail(6).min()
            }
        )

    def _calculate_alignment(self, monthly, weekly, daily) -> float:
        """
        추세 정렬도 계산 (0~1)

        완전 정렬 (1.0): 월/주/일 모두 같은 방향
        부분 정렬 (0.5~0.8): 2개 일치
        불일치 (0~0.5): 방향 충돌
        """
        trends = [monthly.trend, weekly.trend, daily.trend]

        if all(t == Trend.BULLISH for t in trends):
            return 1.0
        elif all(t == Trend.BEARISH for t in trends):
            return 1.0

        # 부분 일치 계산
        bullish_count = sum(1 for t in trends if t == Trend.BULLISH)
        bearish_count = sum(1 for t in trends if t == Trend.BEARISH)

        max_count = max(bullish_count, bearish_count)

        if max_count == 2:
            return 0.7
        elif max_count == 1:
            return 0.4
        else:
            return 0.5  # 모두 중립
```

### 2.3 진입 타이밍 최적화

```python
class EntryOptimizer:
    """
    멀티타임프레임 기반 진입점 최적화

    원칙:
    - 상위 TF에서 방향 확인
    - 중위 TF에서 지지/저항 확인
    - 하위 TF에서 정확한 진입점
    """

    def find_entry(self, mtf_analysis: MTFAnalysis) -> EntryPoint:
        """
        최적 진입점 탐색

        매수 진입 조건:
        1. 월봉 상승 추세
        2. 주봉이 지지선 근처에서 반등 신호
        3. 일봉에서 캔들 패턴 + 거래량 확인

        진입 점수 (0~100):
        - 추세 정렬도: 30점
        - 지지선 접근: 25점
        - 캔들 패턴: 25점
        - 거래량 확인: 20점
        """
        if not mtf_analysis.tradeable:
            return EntryPoint(valid=False, reason="추세 정렬 부족")

        direction = mtf_analysis.direction

        # 점수 계산
        alignment_score = mtf_analysis.alignment_score * 30
        support_score = self._score_support_proximity(
            mtf_analysis.weekly_trend.key_levels,
            mtf_analysis.daily_trend.current_price,
            direction
        ) * 25
        pattern_score = self._score_candle_pattern(
            mtf_analysis.daily_trend.data,
            direction
        ) * 25
        volume_score = self._score_volume_confirmation(
            mtf_analysis.daily_trend.data
        ) * 20

        total_score = alignment_score + support_score + pattern_score + volume_score

        if total_score >= 70:
            return EntryPoint(
                valid=True,
                direction=direction,
                score=total_score,
                entry_price=self._calculate_entry_price(mtf_analysis),
                stop_loss=self._calculate_stop_loss(mtf_analysis),
                take_profit=self._calculate_take_profit(mtf_analysis)
            )

        return EntryPoint(valid=False, reason=f"진입 점수 부족 ({total_score:.0f}/70)")
```

---

## 3. 섹터 로테이션 전략

### 3.1 섹터 모멘텀 랭킹

```python
class SectorRotationEngine:
    """
    섹터 로테이션 엔진

    핵심 원칙:
    - 강한 섹터에 집중 투자
    - 약한 섹터 회피
    - 섹터 모멘텀 전환 시 빠른 대응
    """

    # 한국 주식시장 섹터 분류
    SECTORS = {
        'IT': ['005930', '000660', '035720', ...],         # 삼성전자, SK하이닉스 등
        'Bio': ['207940', '068270', '091990', ...],        # 삼성바이오 등
        'Battery': ['373220', '006400', '051910', ...],    # LG에너지 등
        'Finance': ['105560', '055550', '086790', ...],    # KB금융 등
        'Chemical': ['051910', '010950', '011170', ...],   # LG화학 등
        'Auto': ['005380', '000270', '012330', ...],       # 현대차 등
        'Retail': ['004170', '139480', '069960', ...],     # 신세계 등
        'Steel': ['005490', '004020', '001230', ...],      # POSCO 등
    }

    def rank_sectors(self) -> List[SectorRank]:
        """
        섹터 모멘텀 랭킹

        평가 지표:
        - 1개월 수익률 (30%)
        - 3개월 수익률 (30%)
        - 상대강도 (RSI 20일) (20%)
        - 거래량 추세 (20%)
        """
        rankings = []

        for sector_name, stocks in self.SECTORS.items():
            # 섹터 평균 계산
            sector_data = self._get_sector_aggregate(stocks)

            # 점수 계산
            return_1m = sector_data['close'].pct_change(20).iloc[-1]
            return_3m = sector_data['close'].pct_change(60).iloc[-1]
            rsi = self._calculate_rsi(sector_data['close'], 20)
            volume_trend = self._calculate_volume_trend(sector_data)

            score = (
                self._normalize_return(return_1m) * 0.30 +
                self._normalize_return(return_3m) * 0.30 +
                (rsi / 100) * 0.20 +
                volume_trend * 0.20
            ) * 100

            rankings.append(SectorRank(
                sector=sector_name,
                score=score,
                return_1m=return_1m,
                return_3m=return_3m,
                rsi=rsi,
                trend=self._determine_trend(score)
            ))

        return sorted(rankings, key=lambda x: x.score, reverse=True)

    def get_allocation(self, rankings: List[SectorRank]) -> dict:
        """
        섹터별 자금 배분

        배분 전략:
        - 상위 3개 섹터: 70% (각 20~25%)
        - 중위 3개 섹터: 25% (각 7~10%)
        - 하위 2개 섹터: 5% 또는 회피

        동적 조정:
        - 섹터 점수 > 70: 최대 배분
        - 섹터 점수 40~70: 표준 배분
        - 섹터 점수 < 40: 최소 배분 또는 회피
        """
        allocation = {}

        top_3 = rankings[:3]
        mid_3 = rankings[3:6]
        bottom_2 = rankings[6:]

        # 상위 섹터
        for i, sector in enumerate(top_3):
            if sector.score >= 70:
                allocation[sector.sector] = 0.25 - (i * 0.02)  # 25%, 23%, 21%
            else:
                allocation[sector.sector] = 0.20 - (i * 0.02)

        # 중위 섹터
        for i, sector in enumerate(mid_3):
            if sector.score >= 40:
                allocation[sector.sector] = 0.10 - (i * 0.02)
            else:
                allocation[sector.sector] = 0.05

        # 하위 섹터
        for sector in bottom_2:
            allocation[sector.sector] = 0.0  # 회피

        # 정규화
        total = sum(allocation.values())
        return {k: v / total for k, v in allocation.items()}
```

### 3.2 섹터 전환 감지

```python
class SectorTransitionDetector:
    """
    섹터 모멘텀 전환 감지

    전환 신호:
    - 급격한 순위 변동 (3단계 이상)
    - 상대강도 급등/급락
    - 거래량 이상 급증
    """

    def detect_transition(self,
                         current_rankings: List[SectorRank],
                         previous_rankings: List[SectorRank]) -> List[Transition]:
        """
        섹터 전환 신호 감지

        반환:
        - 신규 강세 섹터
        - 약화 섹터
        - 전환 신뢰도
        """
        transitions = []

        for curr in current_rankings:
            # 이전 순위 찾기
            prev = next((p for p in previous_rankings if p.sector == curr.sector), None)
            if not prev:
                continue

            rank_change = prev.rank - curr.rank  # 양수면 순위 상승
            score_change = curr.score - prev.score

            # 강세 전환
            if rank_change >= 3 and score_change > 10:
                transitions.append(Transition(
                    sector=curr.sector,
                    type=TransitionType.EMERGING_STRONG,
                    confidence=min(1.0, score_change / 30),
                    action="배분 확대"
                ))

            # 약세 전환
            elif rank_change <= -3 and score_change < -10:
                transitions.append(Transition(
                    sector=curr.sector,
                    type=TransitionType.WEAKENING,
                    confidence=min(1.0, abs(score_change) / 30),
                    action="배분 축소"
                ))

        return transitions
```

---

## 4. 전략 전환 로직

### 4.1 언제 전략을 바꿀 것인가?

```python
class StrategySelector:
    """
    시장 상황에 따른 전략 선택

    시장 레짐별 최적 전략:
    - 강세장 (Bull): 모멘텀 + 추세추종
    - 약세장 (Bear): 방어적 + 현금 비중 확대
    - 횡보장 (Range): 평균회귀 + 옵션 전략
    - 고변동성: 포지션 축소 + 넓은 손절
    """

    STRATEGY_MAP = {
        MarketRegime.BULL: {
            'primary': 'momentum',
            'secondary': 'trend_following',
            'position_size': 1.2,      # 120% 포지션
            'stop_loss_mult': 1.5,     # ATR 1.5배
            'sector_focus': 'growth',
        },
        MarketRegime.BEAR: {
            'primary': 'defensive',
            'secondary': 'mean_reversion',
            'position_size': 0.5,      # 50% 포지션
            'stop_loss_mult': 1.0,     # ATR 1.0배 (타이트)
            'sector_focus': 'defensive',
            'cash_target': 0.50,       # 50% 현금
        },
        MarketRegime.RANGE: {
            'primary': 'mean_reversion',
            'secondary': 'momentum',
            'position_size': 0.8,
            'stop_loss_mult': 1.2,
            'sector_focus': 'balanced',
        },
        MarketRegime.HIGH_VOLATILITY: {
            'primary': 'defensive',
            'secondary': None,
            'position_size': 0.3,      # 30% 포지션
            'stop_loss_mult': 2.5,     # 넓은 손절
            'cash_target': 0.70,       # 70% 현금
        }
    }

    def select_strategy(self, market_analysis: MarketAnalysis) -> StrategyConfig:
        """
        현재 시장 상황에 맞는 전략 선택

        전략 전환 조건:
        - 레짐 전환 확인 (3일 연속 같은 레짐)
        - 급격한 전환 방지 (점진적 조정)
        - 전환 비용 고려
        """
        current_regime = market_analysis.regime
        regime_confidence = market_analysis.confidence

        # 레짐 확신도가 낮으면 보수적 접근
        if regime_confidence < 0.7:
            # 혼합 전략
            return self._blend_strategies(
                self.STRATEGY_MAP[current_regime],
                self.STRATEGY_MAP[MarketRegime.RANGE],
                ratio=regime_confidence
            )

        return StrategyConfig(**self.STRATEGY_MAP[current_regime])
```

### 4.2 전략 전환 비용 관리

```python
class StrategyTransitionManager:
    """
    전략 전환 시 비용 최소화

    고려 사항:
    - 거래 비용 (수수료, 슬리피지)
    - 시장 충격
    - 포지션 청산 손실
    """

    def plan_transition(self,
                       current_portfolio: Portfolio,
                       target_strategy: StrategyConfig) -> TransitionPlan:
        """
        전략 전환 계획 수립

        전환 방식:
        1. 즉시 전환: 긴급 상황 (MDD 10% 이상)
        2. 점진적 전환: 일반 상황 (3~5일에 걸쳐)
        3. 만기 전환: 기존 포지션 청산 후 신규 진입
        """
        transition_urgency = self._calculate_urgency(current_portfolio)

        if transition_urgency == Urgency.IMMEDIATE:
            # 즉시 전환: 모든 포지션 청산 후 재진입
            return TransitionPlan(
                method='immediate',
                steps=[
                    Step(day=0, action='close_all'),
                    Step(day=1, action='rebalance_to_target')
                ],
                estimated_cost=self._estimate_immediate_cost(current_portfolio)
            )

        elif transition_urgency == Urgency.GRADUAL:
            # 점진적 전환: 일별 20%씩 조정
            steps = []
            for day in range(5):
                steps.append(Step(
                    day=day,
                    action='adjust_20_percent',
                    target_allocation=self._interpolate_allocation(
                        current_portfolio.allocation,
                        target_strategy.allocation,
                        (day + 1) / 5
                    )
                ))

            return TransitionPlan(
                method='gradual',
                steps=steps,
                estimated_cost=self._estimate_gradual_cost(current_portfolio)
            )
```

---

## 5. 구현 우선순위

### Phase A-1: 앙상블 기반 (Week 1-2)

```python
# 구현 순서
1. core/strategy/ensemble/__init__.py
2. core/strategy/ensemble/signal_aggregator.py    # 신호 집계
3. core/strategy/ensemble/ensemble_engine.py      # 앙상블 엔진
4. core/strategy/ensemble/weight_optimizer.py     # 가중치 최적화

# 테스트
- 단위 테스트: 각 컴포넌트
- 통합 테스트: 전체 파이프라인
- 백테스트: 과거 1년 데이터
```

### Phase A-2: 멀티타임프레임 (Week 2)

```python
# 구현 순서
1. core/strategy/timeframe/__init__.py
2. core/strategy/timeframe/mtf_analyzer.py        # MTF 분석
3. core/strategy/timeframe/trend_aligner.py       # 추세 정렬
4. core/strategy/timeframe/entry_optimizer.py     # 진입 최적화

# 검증
- 추세 정렬 정확도 > 80%
- 진입 타이밍 승률 > 55%
```

### Phase A-3: 섹터 로테이션 (Week 2-3)

```python
# 구현 순서
1. core/strategy/sector/__init__.py
2. core/strategy/sector/sector_analyzer.py        # 섹터 분석
3. core/strategy/sector/rotation_engine.py        # 로테이션 엔진
4. core/strategy/sector/transition_detector.py    # 전환 감지

# 검증
- 섹터 모멘텀 예측 정확도 > 70%
- 로테이션 대비 벤치마크 초과 수익
```

---

*다음 문서: `02_RISK_MANAGEMENT_DESIGN.md` - 리스크 관리 설계*
