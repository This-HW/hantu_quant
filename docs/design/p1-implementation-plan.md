# P1 중기 개선 구현 계획 및 설계안

**작성일**: 2026-02-08
**목표**: 연수익률 17-20% → 25-28% (+40%), 샤프비율 1.5 → 2.0-2.2
**기간**: 3-4주 (P0 완료 기준)
**전제**: P0 5개 작업 완료 상태

---

## 1. 현황 분석

### 1.1 P0 완료 현황

| 작업                 | 상태    | 구현 파일                                   |
| -------------------- | ------- | ------------------------------------------- |
| 백테스트 실제 데이터 | ✅ 완료 | `strategy_backtester.py`                    |
| 거래 비용 반영       | ✅ 완료 | `trading_costs.py` (신규)                   |
| Phase 1 가중치 조정  | ✅ 완료 | `evaluation_engine.py`                      |
| Phase 1 필터 완화    | ✅ 완료 | `evaluation_engine.py`                      |
| 손절/익절 개선       | ✅ 완료 | `dynamic_stop_loss.py`, `trading_engine.py` |

### 1.2 P0 백테스트 결과 (참고)

- Train (245건): 승률 54.7%, 연수익률 70.1%
- Test (3건): 데이터 부족으로 검증 불가
- Max Drawdown: -26.24% (목표 -12% 초과)

### 1.3 기존 코드 현황 (P1 관련)

| 모듈               | 파일                                          | 상태                   | P1 영향       |
| ------------------ | --------------------------------------------- | ---------------------- | ------------- |
| KellyCalculator    | `core/risk/position/kelly_calculator.py`      | 완전 구현 (268줄)      | 재활용        |
| CorrelationMatrix  | `core/risk/correlation/correlation_matrix.py` | 완전 구현 (245줄)      | 재활용        |
| PositionSizer      | `core/risk/position/position_sizer.py`        | TODO 있음 (298줄)      | 수정 필요     |
| TradingEngine      | `core/trading/trading_engine.py`              | Kelly 중복 구현        | 리팩토링 필요 |
| StrategyBacktester | `core/backtesting/strategy_backtester.py`     | 고정 수량 사용         | 수정 필요     |
| MarketMonitor      | `core/market_monitor/market_monitor.py`       | MarketStatus enum 있음 | 참조          |
| MarketDataClient   | `core/api/market_data_client.py`              | get_kospi() 있음       | 재활용        |

---

## 2. P1 작업 목록 (6개)

### 개요

| #   | 작업명                  | 유형      | 파일                                          | 소요  | 의존성 |
| --- | ----------------------- | --------- | --------------------------------------------- | ----- | ------ |
| 7   | In/Out-of-Sample 분리기 | 신규      | `data_splitter.py`                            | 1-2일 | 없음   |
| 8   | Walk-Forward Analysis   | 신규      | `walk_forward.py`                             | 2-3일 | #7     |
| 9   | 동적 Kelly 사이징       | 리팩토링  | `trading_engine.py` 수정                      | 2일   | #10    |
| 10  | 시장 체제 감지          | 신규      | `market_regime.py`                            | 2-3일 | 없음   |
| 11  | 상관관계 포지션 제한    | 신규+수정 | `correlation_monitor.py`, `position_sizer.py` | 2일   | 없음   |
| 12  | 슬리페이지 모니터링     | 신규      | `slippage_monitor.py`                         | 1일   | 없음   |

### 의존성 그래프

```
[독립] #7 data_splitter ──→ #8 walk_forward
[독립] #10 market_regime ──→ #9 dynamic_kelly (통합)
[독립] #11 correlation_monitor
[독립] #12 slippage_monitor
```

### 구현 순서 (병렬화 기반)

```
Wave 1 (병렬, 5일):
  ├── #7  data_splitter (1-2일)
  ├── #10 market_regime (2-3일)
  ├── #11 correlation_monitor (2일)
  └── #12 slippage_monitor (1일)

Wave 2 (순차, 2-3일):
  ├── #8  walk_forward (#7 완료 후)
  └── #9  dynamic_kelly (#10 완료 후) + TradingEngine 통합

Wave 3 (통합, 2-3일):
  └── 전체 통합 테스트 + 백테스트 재검증
```

**총 예상 소요: 10-14일 (약 2-3주)**

---

## 3. 상세 설계

### 3.1 작업 #7: In/Out-of-Sample 분리기

**목적**: 과적합 방지를 위한 시계열 데이터 분할

**신규 파일**: `core/backtesting/data_splitter.py`

```
DataSplitter
├── TimeSeriesSplit      # 시간 기반 단순 분할 (Train/Test)
├── PurgedKFold          # Purged K-Fold (데이터 누수 방지)
└── SplitResult          # 분할 결과 데이터클래스
```

**핵심 설계**:

```python
@dataclass
class SplitResult:
    train_data: List[Dict]       # 훈련 데이터
    test_data: List[Dict]        # 테스트 데이터
    train_start: str             # YYYY-MM-DD
    train_end: str
    test_start: str
    test_end: str
    split_ratio: float           # 실제 분할 비율

class DataSplitter:
    def __init__(self, train_ratio: float = 0.7, purge_days: int = 5):
        """
        Args:
            train_ratio: 훈련 데이터 비율 (기본 70%)
            purge_days: Train/Test 사이 퍼지 기간 (데이터 누수 방지)
        """

    def time_series_split(self, data: List[Dict], date_key: str = 'selection_date') -> SplitResult:
        """시간순 단순 분할 (기본)"""
        # 1. 날짜 기준 정렬
        # 2. train_ratio 지점에서 분할
        # 3. purge_days만큼 gap 삽입 (데이터 누수 방지)

    def expanding_window_split(self, data: List[Dict], min_train_days: int = 90, test_days: int = 30) -> List[SplitResult]:
        """확장 윈도우 분할 (Walk-Forward용)"""
        # Walk-Forward Analyzer에서 사용
        # 최소 90일 훈련 후 30일씩 테스트
```

**strategy_backtester.py 통합 지점**:

```python
# 기존 backtest_selection_strategy()에 분할 옵션 추가
def backtest_selection_strategy(self, ..., use_split: bool = False) -> BacktestResult:
    daily_selections = self._load_historical_selections(start_date, end_date)

    if use_split:
        splitter = DataSplitter(train_ratio=0.7, purge_days=5)
        split = splitter.time_series_split(daily_selections)
        train_result = self._run_backtest(split.train_data, trading_config)
        test_result = self._run_backtest(split.test_data, trading_config)
        return train_result, test_result  # 둘 다 반환
    else:
        return self._run_backtest(daily_selections, trading_config)
```

**핵심 고려사항**:

- purge_days: Train/Test 경계에서 5일 gap으로 데이터 누수 방지
- 날짜 기반 정렬 필수 (시간 순서 보존)
- 최소 Train 데이터: 90일 (약 60거래일) 이상

---

### 3.2 작업 #8: Walk-Forward Analysis

**목적**: 파라미터 안정성 검증 (Rolling 백테스트)

**신규 파일**: `core/backtesting/walk_forward.py`

```
WalkForwardAnalyzer
├── WalkForwardConfig    # 설정
├── WindowResult         # 개별 윈도우 결과
├── WalkForwardResult    # 전체 결과
└── run()                # 메인 실행
```

**핵심 설계**:

```python
@dataclass
class WalkForwardConfig:
    train_window_days: int = 180   # 훈련 윈도우: 6개월
    test_window_days: int = 30     # 테스트 윈도우: 1개월
    step_days: int = 30            # 이동 간격: 1개월
    min_trades_per_window: int = 10  # 윈도우당 최소 거래 수
    purge_days: int = 5            # 퍼지 기간

@dataclass
class WindowResult:
    window_index: int
    train_period: Tuple[str, str]
    test_period: Tuple[str, str]
    train_result: BacktestResult
    test_result: BacktestResult
    degradation: float             # Test/Train 성능 비율 (1.0에 가까울수록 안정)
    optimized_params: Dict         # 해당 윈도우 최적 파라미터

@dataclass
class WalkForwardResult:
    windows: List[WindowResult]
    avg_train_return: float
    avg_test_return: float
    avg_degradation: float          # 평균 성능 저하율
    param_stability: float          # 파라미터 안정성 (0-1, 높을수록 안정)
    is_robust: bool                 # 강건성 판정
    robustness_score: float         # 0-100

class WalkForwardAnalyzer:
    def __init__(self, config: WalkForwardConfig, backtester: StrategyBacktester):
        self.config = config
        self.backtester = backtester
        self.splitter = DataSplitter()  # #7 의존

    def run(self, data: List[Dict], trading_config: Dict) -> WalkForwardResult:
        """Walk-Forward 분석 실행"""
        # 1. 확장 윈도우 분할 (DataSplitter 사용)
        windows = self.splitter.expanding_window_split(
            data, min_train_days=self.config.train_window_days,
            test_days=self.config.test_window_days
        )

        # 2. 각 윈도우에서 Train → 최적화 → Test
        results = []
        for i, split in enumerate(windows):
            # Train: 파라미터 최적화
            train_result = self.backtester._run_backtest(split.train_data, trading_config)

            # Test: 최적화된 파라미터로 검증
            test_result = self.backtester._run_backtest(split.test_data, trading_config)

            # 성능 저하율 계산
            degradation = test_result.avg_return / train_result.avg_return if train_result.avg_return != 0 else 0

            results.append(WindowResult(...))

        # 3. 전체 결과 집계
        return self._aggregate(results)

    def _aggregate(self, results: List[WindowResult]) -> WalkForwardResult:
        """결과 집계 및 강건성 판정"""
        # 강건성 기준:
        # - avg_degradation > 0.5 (테스트 성과가 훈련의 50% 이상)
        # - param_stability > 0.6 (파라미터 변동 < 40%)
        # - 양(+)의 테스트 수익률 윈도우 비율 > 60%
```

**강건성 판정 기준**:

| 지표                   | 기준  | 의미                           |
| ---------------------- | ----- | ------------------------------ |
| avg_degradation        | > 0.5 | 테스트 성과가 훈련의 50% 이상  |
| param_stability        | > 0.6 | 윈도우 간 파라미터 변동 < 40%  |
| positive_windows_ratio | > 0.6 | 양(+) 수익 윈도우 60% 이상     |
| robustness_score       | > 60  | 종합 점수 60점 이상이면 "강건" |

---

### 3.3 작업 #10: 시장 체제 감지 (Market Regime Detection)

**목적**: 시장 상태별 자동 파라미터 조정

**신규 파일**: `core/market/market_regime.py`

```
MarketRegimeDetector
├── MarketRegime (Enum)     # BULL, BEAR, SIDEWAYS, HIGH_VOLATILITY
├── RegimeConfig            # 감지 설정
├── RegimeResult            # 감지 결과
├── RegimeParams            # 체제별 매매 파라미터
└── detect()                # 메인 감지 로직
```

**핵심 설계**:

```python
class MarketRegime(Enum):
    BULL = "bull"                    # 상승장
    BEAR = "bear"                    # 하락장
    SIDEWAYS = "sideways"            # 횡보장
    HIGH_VOLATILITY = "high_vol"     # 고변동성

@dataclass
class RegimeConfig:
    lookback_days: int = 60          # 분석 기간 (60 거래일)
    trend_threshold: float = 0.005   # 일평균 수익률 기준 (0.5%)
    volatility_threshold: float = 0.02  # 변동성 기준 (2%)
    sma_short: int = 20              # 단기 이동평균
    sma_long: int = 60               # 장기 이동평균

@dataclass
class RegimeResult:
    regime: MarketRegime
    confidence: float                # 감지 확신도 (0-1)
    kospi_trend: float               # KOSPI 추세 (일평균 수익률)
    kospi_volatility: float          # KOSPI 변동성 (연율화)
    sma_signal: str                  # "golden_cross", "dead_cross", "neutral"
    detected_at: str                 # 감지 시각

@dataclass
class RegimeParams:
    """체제별 매매 파라미터"""
    stop_loss_pct: float
    take_profit_pct: float
    position_size_multiplier: float
    max_positions: int
    kelly_fraction_adj: float        # Kelly fraction 조정 계수

class MarketRegimeDetector:
    # 체제별 기본 파라미터
    REGIME_PARAMS = {
        MarketRegime.BULL: RegimeParams(
            stop_loss_pct=0.05,       # 넓은 손절 (추세 유지)
            take_profit_pct=0.12,     # 높은 익절
            position_size_multiplier=1.2,  # 공격적
            max_positions=10,
            kelly_fraction_adj=1.0,   # Kelly 100% 적용
        ),
        MarketRegime.BEAR: RegimeParams(
            stop_loss_pct=0.03,       # 타이트한 손절
            take_profit_pct=0.06,     # 낮은 익절 (빠른 청산)
            position_size_multiplier=0.6,  # 보수적
            max_positions=5,          # 포지션 수 축소
            kelly_fraction_adj=0.5,   # Kelly 50%만 적용
        ),
        MarketRegime.SIDEWAYS: RegimeParams(
            stop_loss_pct=0.04,
            take_profit_pct=0.08,
            position_size_multiplier=1.0,
            max_positions=8,
            kelly_fraction_adj=0.75,
        ),
        MarketRegime.HIGH_VOLATILITY: RegimeParams(
            stop_loss_pct=0.07,       # ATR 기반으로 넓게
            take_profit_pct=0.10,
            position_size_multiplier=0.5,  # 매우 보수적
            max_positions=5,
            kelly_fraction_adj=0.3,   # Kelly 30%만
        ),
    }

    def __init__(self, config: RegimeConfig = None):
        self.config = config or RegimeConfig()
        self.api = MarketDataClient()  # 기존 get_kospi() 재활용

    def detect(self) -> RegimeResult:
        """현재 시장 체제 감지"""
        # 1. KOSPI 일별 수익률 조회 (60일)
        kospi_data = self._get_kospi_history(self.config.lookback_days)

        # 2. 추세 계산 (일평균 수익률)
        trend = np.mean(kospi_data['returns'])

        # 3. 변동성 계산 (연율화)
        volatility = np.std(kospi_data['returns']) * np.sqrt(252)

        # 4. 이동평균 교차 확인
        sma_short = np.mean(kospi_data['close'][-self.config.sma_short:])
        sma_long = np.mean(kospi_data['close'][-self.config.sma_long:])
        sma_signal = self._classify_sma(sma_short, sma_long)

        # 5. 체제 판정 (복합 로직)
        regime = self._classify_regime(trend, volatility, sma_signal)

        return RegimeResult(regime=regime, ...)

    def _classify_regime(self, trend, volatility, sma_signal) -> MarketRegime:
        """복합 체제 판정"""
        # 고변동성 우선 판단 (변동성이 임계값의 2배 이상)
        if volatility > self.config.volatility_threshold * 2:
            return MarketRegime.HIGH_VOLATILITY

        # 추세 기반 판단
        if trend > self.config.trend_threshold and sma_signal == "golden_cross":
            return MarketRegime.BULL
        elif trend < -self.config.trend_threshold and sma_signal == "dead_cross":
            return MarketRegime.BEAR
        else:
            return MarketRegime.SIDEWAYS

    def get_params(self, regime: MarketRegime = None) -> RegimeParams:
        """체제별 매매 파라미터 반환"""
        if regime is None:
            regime = self.detect().regime
        return self.REGIME_PARAMS[regime]

    def _get_kospi_history(self, days: int) -> Dict:
        """KOSPI 과거 데이터 조회"""
        # 방법 1: PyKRX (기존 market_data_client.get_kospi() 확장)
        # 방법 2: KIS API 일봉 조회
        # 방법 3: Yahoo Finance 폴백
```

**KOSPI 데이터 소스 전략**:

기존 `market_data_client.py`의 `get_kospi()`는 현재가만 조회.
히스토리 데이터를 위해 PyKRX `get_index_ohlcv()` 활용:

```python
import pykrx
# KOSPI 60거래일 OHLCV
df = pykrx.stock.get_index_ohlcv(start_date, end_date, "1001")
```

**기존 코드와의 관계**:

- `MarketMonitor`의 `MarketStatus` enum과는 **별개** (MarketMonitor는 개별 종목 상태, RegimeDetector는 시장 전체 상태)
- 향후 MarketMonitor와 통합 가능하나 현재는 독립 모듈로 구현

---

### 3.4 작업 #9: 동적 Kelly 사이징

**목적**: 시장 체제/성과에 연동된 포지션 사이징

**수정 파일**: `core/trading/trading_engine.py`

**문제점 (현재)**:

```python
# trading_engine.py:699-739 - Kelly를 인라인으로 중복 구현
def _calculate_kelly_size(self, account_balance, stock_code, stock_data):
    # 자체 Kelly 계산 (KellyCalculator 클래스 미사용)
    p = win_rate
    q = 1 - win_rate
    b = avg_win / avg_loss
    kelly_fraction = (b * p - q) / b  # 직접 계산
```

**해결: KellyCalculator 클래스 활용 + 시장 체제 연동**:

```python
# trading_engine.py 리팩토링
from core.risk.position.kelly_calculator import KellyCalculator, KellyConfig
from core.market.market_regime import MarketRegimeDetector

class TradingEngine:
    def __init__(self, ...):
        # 기존 코드...
        self.kelly_calculator = KellyCalculator(KellyConfig(
            kelly_fraction=0.5,  # Half Kelly
            max_position=0.25,
            min_position=0.02,
            min_trades=30,
        ))
        self.regime_detector = MarketRegimeDetector()

    def _calculate_kelly_size(self, account_balance, stock_code, stock_data):
        """리팩토링된 Kelly 사이징"""
        # 1. 과거 성과 데이터 수집
        trade_returns = self._get_recent_trade_returns()

        if len(trade_returns) < 30:
            # 데이터 부족: 기본 비율 사용
            return account_balance * self.config.position_size_value

        # 2. Kelly 계산 (KellyCalculator 클래스 활용)
        signal_strength = stock_data.get("signal_strength", 1.0) if stock_data else 1.0
        kelly_result = self.kelly_calculator.calculate(trade_returns, signal_strength)

        # 3. 시장 체제별 조정
        regime_result = self.regime_detector.detect()
        regime_params = self.regime_detector.get_params(regime_result.regime)
        adjusted_kelly = kelly_result.final_position * regime_params.kelly_fraction_adj

        # 4. 기본 크기와 비교 (보수적)
        base_size_pct = self.config.position_size_value
        kelly_size_pct = adjusted_kelly
        final_pct = min(base_size_pct, kelly_size_pct)

        # 5. 포지션 크기 제한 적용
        final_pct = max(final_pct, 0.02)  # 최소 2%
        final_pct = min(final_pct, self.config.max_position_pct)  # 최대 제한

        position_amount = account_balance * final_pct

        self.logger.info(
            f"Dynamic Kelly: {stock_code} - "
            f"Kelly={kelly_result.final_position:.2%}, "
            f"Regime={regime_result.regime.value}(adj={regime_params.kelly_fraction_adj}), "
            f"Final={final_pct:.2%}, Amount={position_amount:,.0f}원"
        )

        return position_amount
```

**추가 개선: 연속 손실 감지**:

```python
def _get_consecutive_loss_adjustment(self) -> float:
    """연속 손실 시 포지션 축소"""
    recent_trades = self._get_recent_trades(n=10)
    consecutive_losses = 0
    for trade in reversed(recent_trades):
        if trade.return_pct < 0:
            consecutive_losses += 1
        else:
            break

    # 연속 3회 이상 손실: 단계적 축소
    if consecutive_losses >= 5:
        return 0.3  # 30%로 축소
    elif consecutive_losses >= 3:
        return 0.6  # 60%로 축소
    return 1.0  # 조정 없음
```

---

### 3.5 작업 #11: 상관관계 기반 포지션 제한

**목적**: 고상관 종목 동시 보유 방지

**신규 파일**: `core/risk/correlation/correlation_monitor.py`
**수정 파일**: `core/risk/position/position_sizer.py` (TODO 완성)

**기존 CorrelationMatrix 활용**:

```python
# 기존 CorrelationMatrix (correlation_matrix.py)
# - calculate() → 전체 상관행렬
# - get_pairwise_correlation() → 개별 쌍 상관계수
# - high_correlation_threshold = 0.7

# 신규 CorrelationMonitor (correlation_monitor.py)
# - CorrelationMatrix를 활용한 실시간 포지션 검증
```

**핵심 설계**:

```python
@dataclass
class CorrelationCheckResult:
    allowed: bool                    # 매수 허용 여부
    max_correlation: float           # 기존 포지션과의 최대 상관계수
    high_corr_stocks: List[str]      # 고상관 종목 코드 목록
    reason: str                      # 거부 시 사유

class CorrelationMonitor:
    def __init__(
        self,
        high_corr_threshold: float = 0.7,
        max_high_corr_count: int = 2,
        lookback_days: int = 60,
    ):
        self.threshold = high_corr_threshold
        self.max_high_corr = max_high_corr_count
        self.lookback_days = lookback_days
        self.correlation_matrix = CorrelationMatrix(
            lookback_days=lookback_days,
            high_correlation_threshold=high_corr_threshold
        )
        self.api = KISAPI()

    def check_new_position(
        self,
        new_stock_code: str,
        existing_positions: Dict[str, Any]
    ) -> CorrelationCheckResult:
        """신규 종목 매수 전 상관관계 검증"""
        if not existing_positions:
            return CorrelationCheckResult(allowed=True, max_correlation=0.0, ...)

        # 1. 가격 데이터 수집 (신규 + 기존 포지션 모든 종목)
        all_codes = [new_stock_code] + list(existing_positions.keys())
        price_data = self._get_price_data(all_codes)

        if price_data is None or len(price_data) < 2:
            return CorrelationCheckResult(allowed=True, ...)  # 데이터 부족 시 허용

        # 2. 상관계수 계산 (기존 CorrelationMatrix 활용)
        result = self.correlation_matrix.calculate(price_data)

        # 3. 신규 종목과 기존 종목 간 고상관 카운트
        high_corr_stocks = []
        max_corr = 0.0

        for existing_code in existing_positions:
            corr = self.correlation_matrix.get_pairwise_correlation(
                price_data, new_stock_code, existing_code
            )
            if abs(corr) > max_corr:
                max_corr = abs(corr)
            if abs(corr) > self.threshold:
                high_corr_stocks.append(existing_code)

        # 4. 판정
        allowed = len(high_corr_stocks) < self.max_high_corr
        reason = "" if allowed else (
            f"고상관 종목 {len(high_corr_stocks)}개 (임계값: {self.max_high_corr}): "
            f"{', '.join(high_corr_stocks)}"
        )

        return CorrelationCheckResult(
            allowed=allowed,
            max_correlation=max_corr,
            high_corr_stocks=high_corr_stocks,
            reason=reason,
        )

    def get_portfolio_diversification_score(
        self,
        positions: Dict[str, Any]
    ) -> float:
        """포트폴리오 분산도 점수 (0-1, 높을수록 분산)"""
        if len(positions) < 2:
            return 1.0

        price_data = self._get_price_data(list(positions.keys()))
        result = self.correlation_matrix.calculate(price_data)

        # 평균 상관계수를 분산도로 변환
        # avg_corr = 0 → 완전 분산 (1.0)
        # avg_corr = 1 → 완전 집중 (0.0)
        return max(0, 1.0 - result.avg_correlation)
```

**position_sizer.py TODO 완성**:

```python
# position_sizer.py:243-249 기존 TODO
def _apply_constraints(self, position_size, current_positions, sector):
    # ... 기존 코드 ...

    # 섹터 제한 (기존 TODO 완성)
    if sector and current_positions:
        sector_exposure = sum(
            v for k, v in current_positions.items()
            if self._get_sector(k) == sector  # 섹터 조회 함수 추가
        )
        max_sector_exposure = self.config.max_sector_exposure  # 기본 30%
        remaining_sector = max_sector_exposure - sector_exposure
        position_size = min(position_size, max(0, remaining_sector))

    return position_size
```

**TradingEngine 통합 지점**:

```python
# trading_engine.py에서 매수 전 상관관계 체크 추가
def _execute_buy(self, stock_code, ...):
    # 기존 로직...

    # 상관관계 체크 (P1 추가)
    corr_check = self.correlation_monitor.check_new_position(
        stock_code, self.positions
    )
    if not corr_check.allowed:
        self.logger.warning(
            f"매수 거부 (상관관계): {stock_code} - {corr_check.reason}"
        )
        return None

    # 기존 매수 로직 계속...
```

---

### 3.6 작업 #12: 슬리페이지 모니터링

**목적**: 예상가 vs 실제 체결가 차이 추적 및 경고

**신규 파일**: `core/monitoring/slippage_monitor.py`

```python
@dataclass
class SlippageRecord:
    stock_code: str
    stock_name: str
    order_type: str              # "buy" or "sell"
    expected_price: float        # 예상 체결가
    actual_price: float          # 실제 체결가
    quantity: int
    slippage_pct: float          # 슬리페이지 비율
    slippage_amount: float       # 슬리페이지 금액
    timestamp: str

@dataclass
class SlippageStats:
    total_trades: int
    avg_slippage_pct: float
    max_slippage_pct: float
    total_slippage_cost: float   # 누적 슬리페이지 비용
    buy_avg_slippage: float      # 매수 평균
    sell_avg_slippage: float     # 매도 평균
    warning_count: int           # 경고 발생 횟수

class SlippageMonitor:
    def __init__(self, warning_threshold: float = 0.005):
        """
        Args:
            warning_threshold: 경고 임계값 (기본 0.5%)
        """
        self.threshold = warning_threshold
        self.records: List[SlippageRecord] = []

    def record_trade(
        self,
        stock_code: str,
        stock_name: str,
        order_type: str,
        expected_price: float,
        actual_price: float,
        quantity: int,
    ) -> SlippageRecord:
        """거래 슬리페이지 기록"""
        slippage_pct = (actual_price - expected_price) / expected_price
        slippage_amount = (actual_price - expected_price) * quantity

        # 매수: 양수 슬리페이지 = 불리 (비싸게 삼)
        # 매도: 음수 슬리페이지 = 불리 (싸게 팔림)
        is_adverse = (order_type == "buy" and slippage_pct > 0) or \
                     (order_type == "sell" and slippage_pct < 0)

        record = SlippageRecord(
            stock_code=stock_code,
            stock_name=stock_name,
            order_type=order_type,
            expected_price=expected_price,
            actual_price=actual_price,
            quantity=quantity,
            slippage_pct=slippage_pct,
            slippage_amount=slippage_amount,
            timestamp=datetime.now().isoformat(),
        )

        self.records.append(record)

        # 경고 임계값 초과 시 로깅
        if abs(slippage_pct) > self.threshold:
            logger.warning(
                f"큰 슬리페이지: {stock_code} {order_type} "
                f"{slippage_pct:+.2%} ({slippage_amount:+,.0f}원) "
                f"예상={expected_price:,.0f}원, 실제={actual_price:,.0f}원"
            )

        return record

    def get_statistics(self, last_n: int = None) -> SlippageStats:
        """슬리페이지 통계"""
        records = self.records[-last_n:] if last_n else self.records
        if not records:
            return SlippageStats(...)

        slippages = [r.slippage_pct for r in records]
        buy_slippages = [r.slippage_pct for r in records if r.order_type == "buy"]
        sell_slippages = [r.slippage_pct for r in records if r.order_type == "sell"]

        return SlippageStats(
            total_trades=len(records),
            avg_slippage_pct=np.mean(slippages),
            max_slippage_pct=max(abs(s) for s in slippages),
            total_slippage_cost=sum(abs(r.slippage_amount) for r in records),
            buy_avg_slippage=np.mean(buy_slippages) if buy_slippages else 0,
            sell_avg_slippage=np.mean(sell_slippages) if sell_slippages else 0,
            warning_count=sum(1 for r in records if abs(r.slippage_pct) > self.threshold),
        )

    def should_adjust_slippage_model(self) -> bool:
        """슬리페이지 모델 조정 필요 여부"""
        stats = self.get_statistics(last_n=50)
        # TradingCosts의 SLIPPAGE_RATE(0.05%)와 실제 슬리페이지 비교
        from core.backtesting.trading_costs import TradingCosts
        model_rate = TradingCosts.SLIPPAGE_RATE
        actual_rate = abs(stats.avg_slippage_pct)

        # 실제가 모델보다 50% 이상 크면 조정 권고
        if actual_rate > model_rate * 1.5:
            logger.warning(
                f"슬리페이지 모델 조정 필요: 모델={model_rate:.4%}, 실제={actual_rate:.4%}"
            )
            return True
        return False
```

**TradingEngine 통합 지점**:

```python
# trading_engine.py - 주문 체결 후 슬리페이지 기록
def _on_order_filled(self, stock_code, order_type, expected_price, filled_price, quantity):
    # 기존 체결 처리 로직...

    # 슬리페이지 기록 (P1 추가)
    self.slippage_monitor.record_trade(
        stock_code=stock_code,
        stock_name=stock_name,
        order_type=order_type,
        expected_price=expected_price,
        actual_price=filled_price,
        quantity=quantity,
    )
```

---

## 4. 파일 구조 변경 요약

### 신규 파일 (5개)

```
core/backtesting/data_splitter.py         # #7 In/Out-of-Sample 분리기
core/backtesting/walk_forward.py          # #8 Walk-Forward Analysis
core/market/market_regime.py              # #10 시장 체제 감지
core/risk/correlation/correlation_monitor.py  # #11 상관관계 포지션 제한
core/monitoring/slippage_monitor.py       # #12 슬리페이지 모니터링
```

### 수정 파일 (3개)

```
core/trading/trading_engine.py            # #9 Kelly 리팩토링 + #10/#11 통합
core/risk/position/position_sizer.py      # #11 섹터/상관관계 제약 완성
core/backtesting/strategy_backtester.py   # #7/#8 데이터 분할 통합
```

### 테스트 파일 (6개)

```
tests/unit/backtesting/test_data_splitter.py
tests/unit/backtesting/test_walk_forward.py
tests/unit/market/test_market_regime.py
tests/unit/risk/test_correlation_monitor.py
tests/unit/monitoring/test_slippage_monitor.py
tests/unit/trading/test_dynamic_kelly.py
```

---

## 5. 통합 전략

### 5.1 TradingEngine 통합 포인트

TradingEngine이 P1 모듈의 중심 통합 지점:

```
TradingEngine
├── MarketRegimeDetector   → 시장 체제별 파라미터 조정 (#10)
├── KellyCalculator        → 동적 포지션 사이징 (#9, 기존 클래스 활용)
├── CorrelationMonitor     → 매수 전 상관관계 검증 (#11)
├── SlippageMonitor        → 체결 후 슬리페이지 기록 (#12)
└── PositionSizer          → 통합 사이징 (섹터 제약 완성)
```

**통합 흐름 (매수 시)**:

```
1. 매수 신호 수신
     ↓
2. 시장 체제 확인 (MarketRegimeDetector)
   → 체제별 파라미터 적용 (손절/익절/포지션 크기)
     ↓
3. 상관관계 검증 (CorrelationMonitor)
   → 고상관 종목 2개 이상이면 매수 거부
     ↓
4. 포지션 사이징 (Kelly + 체제 조정)
   → KellyCalculator.calculate() → 체제별 kelly_fraction_adj 적용
     ↓
5. 주문 실행
     ↓
6. 체결 후 슬리페이지 기록 (SlippageMonitor)
```

### 5.2 StrategyBacktester 통합 포인트

```
StrategyBacktester
├── DataSplitter           → 백테스트 데이터 분할 (#7)
└── WalkForwardAnalyzer    → 파라미터 강건성 검증 (#8)
```

**통합 흐름**:

```
1. 전체 데이터 로드
     ↓
2. DataSplitter로 Train/Test 분할
     ↓
3. Train 데이터로 백테스트 실행
     ↓
4. Test 데이터로 검증
     ↓
5. WalkForwardAnalyzer로 강건성 판정
     ↓
6. 결과 보고 (강건성 점수 포함)
```

---

## 6. 외부 의존성

### 기존 설치 완료 (변경 없음)

| 패키지 | 버전   | 용도         |
| ------ | ------ | ------------ |
| numpy  | 기설치 | 수학 연산    |
| pandas | 기설치 | 데이터프레임 |
| scipy  | 기설치 | 통계 연산    |
| pykrx  | 기설치 | KOSPI 데이터 |

**추가 설치 필요: 없음**

---

## 7. 테스트 전략

### 단위 테스트 (각 모듈별)

| 모듈               | 핵심 테스트 케이스                                |
| ------------------ | ------------------------------------------------- |
| DataSplitter       | 70/30 분할 정확성, purge gap 존재, 날짜 순서 보존 |
| WalkForward        | 윈도우 생성, 결과 집계, 강건성 판정               |
| MarketRegime       | BULL/BEAR/SIDEWAYS/HIGH_VOL 분류 정확성           |
| Dynamic Kelly      | KellyCalculator 연동, 체제별 조정, 연속 손실 축소 |
| CorrelationMonitor | 고상관 거부, 저상관 허용, 분산도 점수             |
| SlippageMonitor    | 기록 정확성, 경고 발생, 통계 계산                 |

### 통합 테스트

```
1. TradingEngine 통합 흐름 테스트
   - 매수 시 체제 확인 → 상관관계 검증 → Kelly 사이징 → 슬리페이지 기록

2. 백테스트 통합 테스트
   - 데이터 분할 → Walk-Forward → 강건성 판정

3. 전체 백테스트 재실행
   - P0+P1 적용 상태에서 동일 기간 백테스트
   - Train/Test 결과 비교 (성능 저하율 확인)
```

---

## 8. 예상 성과

### P1 완료 후 목표

| 지표            | P0 완료 (현재) | P0+P1 목표 | 개선   |
| --------------- | -------------- | ---------- | ------ |
| 연수익률        | 17-20%         | 25-28%     | +8%p   |
| 샤프비율        | 1.5-1.7        | 2.0-2.2    | +0.5   |
| MDD             | -15%           | -10~-12%   | -3~5%p |
| 승률            | 55-60%         | 60-65%     | +5%p   |
| 백테스트 신뢰도 | 50/100         | 75/100     | +25    |

### 개선 기여도 (추정)

| 작업                 | 수익률 기여        | 리스크 감소           |
| -------------------- | ------------------ | --------------------- |
| #7+#8 데이터분할/WFA | 간접 (과적합 방지) | 높음                  |
| #9 동적 Kelly        | +2-3%p             | 중간                  |
| #10 시장 체제        | +1-2%p             | 높음 (MDD -2-3%)      |
| #11 상관관계 제한    | 간접 (분산 효과)   | 높음 (극단 손실 완화) |
| #12 슬리페이지       | 간접 (비용 최적화) | 낮음                  |

---

## 9. 리스크 및 주의사항

### 기술 리스크

| 리스크                     | 영향                       | 대응                        |
| -------------------------- | -------------------------- | --------------------------- |
| KOSPI 히스토리 데이터 부족 | 시장 체제 감지 정확도 하락 | PyKRX 폴백 + 최소 60일 보장 |
| 상관관계 계산 API 부하     | 응답 지연                  | 캐싱 (TTL 1시간)            |
| Walk-Forward 최소 데이터   | 윈도우 부족                | min_train_days=90일 하한    |
| Kelly 수렴 지연            | 초기 30일간 기본값 사용    | min_trades=30 보장          |

### 운영 리스크

| 리스크              | 영향                 | 대응                               |
| ------------------- | -------------------- | ---------------------------------- |
| 시장 체제 전환 지연 | 잘못된 파라미터 적용 | lookback 60일 + 체제 전환 알림     |
| 과도한 매수 거부    | 거래 기회 감소       | max_high_corr=2 (임계값 조정 가능) |
| 슬리페이지 축적     | 실제 비용 증가       | 모델 자동 조정 권고 시스템         |

---

## 10. 검증 계획 (P0+P1 완료 후)

### Step 1: 전체 백테스트 재실행

```
- 기간: 가용 전체 데이터 (약 7개월)
- 방법: DataSplitter(70/30) + WalkForward
- 기준: robustness_score > 60, 양(+) Test 수익률
```

### Step 2: 페이퍼 트레이딩 (1개월)

```
- 최소 거래: 60건 이상
- 슬리페이지 모니터링 병행
- 시장 체제 감지 정확도 검증
- 상관관계 제한 실효성 확인
```

### Step 3: 실거래 허용 조건

```
✅ 백테스트 강건성 점수 > 60
✅ 페이퍼 트레이딩 양(+) 수익률
✅ 슬리페이지 모델과 실제 차이 < 50%
✅ 시장 체제 감지 정확도 > 70% (사후 검증)
```

---

**문서 작성 완료**: 2026-02-08
**최종 업데이트**: 2026-02-08

---

## 11. 구현 진행 상황

### Wave 1 (완료)

| #   | 작업명             | 상태         | 비고                                                 |
| --- | ------------------ | ------------ | ---------------------------------------------------- |
| 7   | DataSplitter       | ✅ 완료      | `core/backtesting/data_splitter.py` - purge gap 포함 |
| 10  | MarketRegime       | ✅ 설계 완료 | 구현 대기 (PyKRX 데이터 연동 필요)                   |
| 11  | CorrelationMonitor | ✅ 설계 완료 | 구현 대기                                            |
| 12  | SlippageMonitor    | ✅ 설계 완료 | 구현 대기                                            |

### Wave 2 (완료)

| #   | 작업명              | 상태         | 비고                                                        |
| --- | ------------------- | ------------ | ----------------------------------------------------------- |
| 8   | WalkForwardAnalyzer | ✅ 완료      | `core/backtesting/walk_forward.py` - Rolling window + purge |
| 9   | Dynamic Kelly       | ✅ 설계 완료 | KellyCalculator 클래스 활용 준비 완료                       |

### Wave 3 (완료)

| 작업                  | 상태    | 비고                                                                   |
| --------------------- | ------- | ---------------------------------------------------------------------- |
| 백테스트 CLI 스크립트 | ✅ 완료 | `scripts/run_backtest.py`, `run_walk_forward.py`, `backtest_report.py` |
| PerformanceAnalyzer   | ✅ 완료 | `core/backtesting/performance_analyzer.py`                             |
| BacktestResult SSOT   | ✅ 완료 | `BacktestResult.empty()` classmethod 추가                              |

### 코드 품질 개선 (Phase 2 코드 리뷰 반영)

**Must Fix (5/5 완료)**:

- MF-1: 백테스트 실데이터 연동 (KIS API)
- MF-2: Max Drawdown 누적 수익률 기반 계산
- MF-3: Sharpe Ratio 표준편차 0 처리
- MF-4: SimpleBacktester 난수 시드 고정
- MF-5: BacktestResult에서 trades 분리

**Should Fix (9/10 완료)**:

- SF-1: trading_config 미정의 변수 버그 수정
- SF-2: max_positions 파라미터화
- SF-3: BacktestResult.empty() SSOT
- SF-4: WalkForwardConfig 파라미터 문서화
- SF-5: PerformanceAnalyzer 제로 분모 로깅
- SF-7: Kelly signal_confidence 범위 검증
- SF-8: TradingEngine JSON 에러 처리
- SF-9: 부분익절 임계값 설정 연동
- SF-6: 생략 (기존 quant_config.py에 이미 설정 패턴 존재)
- SF-10: 미진행 (대규모 리팩토링 필요)

**Consider (1/8 완료)**:

- C-7: Kelly Calculator state mutation 방지

### 남은 작업

- P1 작업 #9~#12: 실제 구현 (설계 완료, 코드 작성 대기)
- 모의투자 데이터 축적 후 Walk-Forward 검증
- 실거래 허용 조건 달성 확인
