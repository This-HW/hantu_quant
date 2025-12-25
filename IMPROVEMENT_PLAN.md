# Hantu Quant 종합 개선 계획서

> 최종 목표: 알고리즘 트레이딩을 통한 수익 극대화 & 프로덕션 품질 서비스

---

## 현재 상태 요약

| 영역 | 점수 | 주요 문제 |
|------|------|----------|
| 알고리즘 수익성 | 6/10 | 고정 가중치, 시장 적응 불가, 고급 지표 미활용 |
| 시스템 아키텍처 | 5/10 | 강한 결합도, 파일 기반 데이터 공유, 싱글톤 남용 |
| 프로덕션 품질 | 4/10 | 에러 처리 미흡, 재시도 없음, 모니터링 부재 |
| 보안 | 7/10 | API 인증 부분 우회, 민감 엔드포인트 노출 |

---

## Phase 1: 기반 안정화 (1주)

### 1.1 에러 처리 & 재시도 로직 강화

**목표**: API 실패 시 자동 복구, 부분 실패 허용

#### Task 1.1.1: API 클라이언트 재시도 메커니즘
```
파일: core/api/rest_client.py
작업:
  - tenacity 라이브러리 도입
  - 지수 백오프 재시도 (최대 3회, 2^n초 대기)
  - 재시도 가능한 에러 분류 (5xx, Timeout, ConnectionError)
  - 재시도 불가 에러 분류 (4xx, 인증 실패)

코드 예시:
```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

class KISRestClient:
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((requests.Timeout, requests.ConnectionError)),
        before_sleep=lambda retry_state: logger.warning(f"재시도 {retry_state.attempt_number}/3")
    )
    def _request(self, method: str, url: str, ...) -> Dict:
        # 기존 로직
```

#### Task 1.1.2: 부분 실패 처리
```
파일: workflows/phase1_watchlist.py, workflows/phase2_daily_selection.py
작업:
  - 개별 종목 실패 시 건너뛰기 (전체 실패 X)
  - 실패 종목 별도 기록 및 나중에 재시도
  - 성공률 90% 이상이면 계속 진행

코드 예시:
```python
class PartialResult:
    successful: List[StockResult]
    failed: List[FailedStock]
    success_rate: float

def parallel_screening(stocks: List) -> PartialResult:
    results = []
    failures = []
    for stock in stocks:
        try:
            result = screen_stock(stock)
            results.append(result)
        except Exception as e:
            failures.append(FailedStock(stock, str(e)))

    return PartialResult(
        successful=results,
        failed=failures,
        success_rate=len(results) / len(stocks)
    )
```

#### Task 1.1.3: Subprocess 안전 관리
```
파일: api-server/main.py
작업:
  - 타임아웃 시 프로세스 강제 종료
  - 좀비 프로세스 정리
  - 프로세스 상태 모니터링

코드 예시:
```python
import signal

def run_with_timeout(cmd: List[str], timeout: int = 300) -> Dict:
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
        return {"success": process.returncode == 0, "output": stdout}
    except subprocess.TimeoutExpired:
        process.kill()  # 강제 종료
        process.wait()  # 정리 대기
        return {"success": False, "error": "timeout"}
```

---

### 1.2 데이터 검증 강화

**목표**: 잘못된 입력으로 인한 오류 방지

#### Task 1.2.1: Pydantic 모델 도입
```
파일: core/models/stock.py (신규)
작업:
  - 모든 입력/출력에 Pydantic 모델 적용
  - 자동 타입 변환 및 검증
  - 상세한 에러 메시지

코드 예시:
```python
from pydantic import BaseModel, Field, field_validator
import re

class StockCode(BaseModel):
    code: str = Field(..., min_length=6, max_length=6)

    @field_validator('code')
    @classmethod
    def validate_code(cls, v):
        if not re.match(r'^\d{6}$', v):
            raise ValueError(f'종목코드는 6자리 숫자여야 합니다: {v}')
        return v

class PriceData(BaseModel):
    current_price: int = Field(..., gt=0)
    volume: int = Field(..., ge=0)
    change_rate: float = Field(..., ge=-100, le=100)

class OrderRequest(BaseModel):
    stock_code: StockCode
    quantity: int = Field(..., gt=0, le=100000)
    price: int = Field(None, gt=0)  # 시장가 주문시 None
    order_type: Literal['market', 'limit']
```

#### Task 1.2.2: API 응답 검증
```
파일: core/api/kis_api.py
작업:
  - KIS API 응답을 Pydantic 모델로 파싱
  - 필수 필드 누락 시 에러
  - 비정상 값 필터링

코드 예시:
```python
class KISPriceResponse(BaseModel):
    stck_prpr: str  # 현재가
    acml_vol: str   # 누적거래량
    prdy_ctrt: str  # 전일대비율

    @property
    def current_price(self) -> int:
        return int(self.stck_prpr)

    @property
    def volume(self) -> int:
        return int(self.acml_vol)

def get_current_price(self, stock_code: str) -> PriceData:
    response = self._request(...)
    validated = KISPriceResponse(**response.get('output', {}))
    return PriceData(
        current_price=validated.current_price,
        volume=validated.volume,
        change_rate=float(validated.prdy_ctrt)
    )
```

---

### 1.3 로깅 & 모니터링 개선

**목표**: 장애 빠른 감지, 원인 분석 용이

#### Task 1.3.1: 구조화된 로깅
```
파일: core/utils/log_utils.py
작업:
  - JSON 형식 로그 추가
  - 로그 로테이션 (일별, 최대 30일)
  - 요청 ID 추적 (trace_id)

코드 예시:
```python
import json
from logging.handlers import TimedRotatingFileHandler

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "level": record.levelname,
            "module": record.module,
            "message": record.getMessage(),
            "trace_id": getattr(record, 'trace_id', None),
            "extra": getattr(record, 'extra', {})
        }
        return json.dumps(log_data, ensure_ascii=False)

def setup_logging(log_file: str, level: str = "INFO"):
    handler = TimedRotatingFileHandler(
        log_file,
        when="midnight",
        interval=1,
        backupCount=30,
        encoding='utf-8'
    )
    handler.setFormatter(JSONFormatter())
    # ...
```

#### Task 1.3.2: 헬스체크 강화
```
파일: api-server/main.py
작업:
  - 의존성 헬스체크 (DB, KIS API, WebSocket)
  - 응답 시간 측정
  - 리소스 사용량 모니터링

코드 예시:
```python
from datetime import datetime
import psutil

class HealthStatus(BaseModel):
    status: Literal['healthy', 'degraded', 'unhealthy']
    database: bool
    kis_api: bool
    websocket: bool
    memory_percent: float
    cpu_percent: float
    response_time_ms: float
    last_check: datetime

@app.get("/health")
async def health_check() -> HealthStatus:
    start = time.time()

    db_ok = await check_database()
    api_ok = await check_kis_api()
    ws_ok = await check_websocket()

    status = 'healthy'
    if not all([db_ok, api_ok, ws_ok]):
        status = 'degraded' if any([db_ok, api_ok]) else 'unhealthy'

    return HealthStatus(
        status=status,
        database=db_ok,
        kis_api=api_ok,
        websocket=ws_ok,
        memory_percent=psutil.virtual_memory().percent,
        cpu_percent=psutil.cpu_percent(),
        response_time_ms=(time.time() - start) * 1000,
        last_check=datetime.now()
    )
```

---

## Phase 2: 수익 알고리즘 강화 (2주)

### 2.1 실시간 호가 분석 시스템

**목표**: 호가 불균형으로 단기 방향 예측

#### Task 2.1.1: 호가 불균형 지표 (Order Book Imbalance)
```
파일: core/indicators/orderbook_analyzer.py (신규)
작업:
  - 실시간 호가 데이터 수집 (WebSocket H0STASP0)
  - 매수/매도 잔량 비율 계산
  - 불균형 신호 생성 (매수 우세/매도 우세)

코드 예시:
```python
from dataclasses import dataclass
from typing import List

@dataclass
class OrderBookLevel:
    price: int
    volume: int

@dataclass
class OrderBookImbalance:
    bid_volume: int      # 총 매수 잔량
    ask_volume: int      # 총 매도 잔량
    imbalance_ratio: float  # (bid - ask) / (bid + ask)
    signal: str          # 'strong_buy', 'buy', 'neutral', 'sell', 'strong_sell'
    confidence: float    # 0.0 ~ 1.0

class OrderBookAnalyzer:
    def __init__(self, levels: int = 10):
        self.levels = levels
        self.history: List[OrderBookImbalance] = []

    def analyze(self, bids: List[OrderBookLevel], asks: List[OrderBookLevel]) -> OrderBookImbalance:
        bid_vol = sum(b.volume for b in bids[:self.levels])
        ask_vol = sum(a.volume for a in asks[:self.levels])

        total = bid_vol + ask_vol
        if total == 0:
            return OrderBookImbalance(0, 0, 0.0, 'neutral', 0.0)

        ratio = (bid_vol - ask_vol) / total

        # 신호 결정
        if ratio > 0.3:
            signal = 'strong_buy'
            confidence = min(ratio / 0.5, 1.0)
        elif ratio > 0.1:
            signal = 'buy'
            confidence = ratio / 0.3
        elif ratio < -0.3:
            signal = 'strong_sell'
            confidence = min(abs(ratio) / 0.5, 1.0)
        elif ratio < -0.1:
            signal = 'sell'
            confidence = abs(ratio) / 0.3
        else:
            signal = 'neutral'
            confidence = 1.0 - abs(ratio) / 0.1

        result = OrderBookImbalance(bid_vol, ask_vol, ratio, signal, confidence)
        self.history.append(result)
        return result

    def get_trend(self, window: int = 10) -> str:
        """최근 N개 데이터의 추세"""
        if len(self.history) < window:
            return 'insufficient_data'

        recent = self.history[-window:]
        avg_ratio = sum(h.imbalance_ratio for h in recent) / window

        if avg_ratio > 0.15:
            return 'bullish'
        elif avg_ratio < -0.15:
            return 'bearish'
        return 'neutral'
```

#### Task 2.1.2: 실시간 WebSocket 통합
```
파일: core/api/websocket_client.py
작업:
  - 호가 데이터 실시간 수신
  - OrderBookAnalyzer와 연동
  - 신호 발생 시 콜백 실행

코드 예시:
```python
class KISWebSocketClient:
    def __init__(self):
        self.orderbook_analyzer = OrderBookAnalyzer()
        self.signal_callbacks: List[Callable] = []

    def on_orderbook_update(self, data: Dict):
        bids = [OrderBookLevel(int(data[f'bidp{i}']), int(data[f'bidq{i}']))
                for i in range(1, 11)]
        asks = [OrderBookLevel(int(data[f'askp{i}']), int(data[f'askq{i}']))
                for i in range(1, 11)]

        imbalance = self.orderbook_analyzer.analyze(bids, asks)

        # 강한 신호 발생 시 콜백
        if imbalance.signal in ['strong_buy', 'strong_sell'] and imbalance.confidence > 0.7:
            for callback in self.signal_callbacks:
                callback(data['stock_code'], imbalance)

    def register_signal_callback(self, callback: Callable):
        self.signal_callbacks.append(callback)
```

---

### 2.2 동적 손절/익절 시스템

**목표**: 변동성에 따른 적응형 리스크 관리

#### Task 2.2.1: ATR 기반 동적 손절가
```
파일: core/trading/dynamic_stop_loss.py (신규)
작업:
  - ATR(Average True Range) 계산
  - 변동성 기반 손절가 설정
  - 트레일링 스탑 자동 조정

코드 예시:
```python
from dataclasses import dataclass
import pandas as pd

@dataclass
class DynamicStopLoss:
    entry_price: int
    stop_loss_price: int
    take_profit_price: int
    atr_multiplier: float
    current_atr: float

class DynamicStopLossCalculator:
    def __init__(self, atr_period: int = 14, stop_multiplier: float = 2.0, profit_multiplier: float = 3.0):
        self.atr_period = atr_period
        self.stop_multiplier = stop_multiplier
        self.profit_multiplier = profit_multiplier

    def calculate_atr(self, df: pd.DataFrame) -> float:
        """ATR 계산"""
        high = df['high']
        low = df['low']
        close = df['close'].shift(1)

        tr1 = high - low
        tr2 = abs(high - close)
        tr3 = abs(low - close)

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=self.atr_period).mean().iloc[-1]

        return atr

    def calculate_stops(self, entry_price: int, df: pd.DataFrame) -> DynamicStopLoss:
        """동적 손절/익절가 계산"""
        atr = self.calculate_atr(df)

        stop_distance = int(atr * self.stop_multiplier)
        profit_distance = int(atr * self.profit_multiplier)

        return DynamicStopLoss(
            entry_price=entry_price,
            stop_loss_price=entry_price - stop_distance,
            take_profit_price=entry_price + profit_distance,
            atr_multiplier=self.stop_multiplier,
            current_atr=atr
        )

    def update_trailing_stop(self, current_price: int, highest_price: int,
                            current_stop: int, atr: float) -> int:
        """트레일링 스탑 업데이트"""
        # 최고가 갱신 시 손절가 상향
        trailing_distance = int(atr * self.stop_multiplier)
        new_stop = highest_price - trailing_distance

        # 손절가는 상향만 가능 (하향 불가)
        return max(current_stop, new_stop)
```

#### Task 2.2.2: 시장 상황별 멀티플라이어 조정
```
파일: core/trading/market_adaptive_risk.py (신규)
작업:
  - 시장 변동성 지수 계산 (VIX 대용)
  - 상황별 손절/익절 배수 자동 조정
  - 위험 시장에서 보수적, 안정 시장에서 공격적

코드 예시:
```python
from enum import Enum

class MarketVolatility(Enum):
    VERY_LOW = 'very_low'      # VIX < 12
    LOW = 'low'                # 12 <= VIX < 16
    NORMAL = 'normal'          # 16 <= VIX < 20
    HIGH = 'high'              # 20 <= VIX < 30
    VERY_HIGH = 'very_high'    # VIX >= 30

class MarketAdaptiveRisk:
    # 시장 상황별 설정
    VOLATILITY_CONFIG = {
        MarketVolatility.VERY_LOW: {
            'stop_multiplier': 1.5,
            'profit_multiplier': 4.0,
            'position_size_factor': 1.2,
            'max_positions': 15
        },
        MarketVolatility.LOW: {
            'stop_multiplier': 1.8,
            'profit_multiplier': 3.5,
            'position_size_factor': 1.1,
            'max_positions': 12
        },
        MarketVolatility.NORMAL: {
            'stop_multiplier': 2.0,
            'profit_multiplier': 3.0,
            'position_size_factor': 1.0,
            'max_positions': 10
        },
        MarketVolatility.HIGH: {
            'stop_multiplier': 2.5,
            'profit_multiplier': 2.5,
            'position_size_factor': 0.7,
            'max_positions': 7
        },
        MarketVolatility.VERY_HIGH: {
            'stop_multiplier': 3.0,
            'profit_multiplier': 2.0,
            'position_size_factor': 0.5,
            'max_positions': 5
        }
    }

    def __init__(self):
        self.current_volatility = MarketVolatility.NORMAL

    def calculate_market_volatility(self, kospi_df: pd.DataFrame) -> MarketVolatility:
        """KOSPI 200 기반 변동성 계산"""
        returns = kospi_df['close'].pct_change().dropna()
        volatility = returns.std() * (252 ** 0.5) * 100  # 연율화

        if volatility < 12:
            return MarketVolatility.VERY_LOW
        elif volatility < 16:
            return MarketVolatility.LOW
        elif volatility < 20:
            return MarketVolatility.NORMAL
        elif volatility < 30:
            return MarketVolatility.HIGH
        else:
            return MarketVolatility.VERY_HIGH

    def get_config(self) -> Dict:
        return self.VOLATILITY_CONFIG[self.current_volatility]
```

---

### 2.3 고급 기술 지표 추가

**목표**: 더 정확한 매매 신호 생성

#### Task 2.3.1: OBV (On Balance Volume)
```
파일: hantu_common/indicators/volume_indicators.py (신규)
작업:
  - OBV 계산 및 추세 분석
  - 가격-거래량 다이버전스 감지
  - 누적 거래량 모멘텀

코드 예시:
```python
import pandas as pd
import numpy as np

class VolumeIndicators:
    @staticmethod
    def obv(df: pd.DataFrame) -> pd.Series:
        """On Balance Volume 계산"""
        obv = pd.Series(index=df.index, dtype=float)
        obv.iloc[0] = df['volume'].iloc[0]

        for i in range(1, len(df)):
            if df['close'].iloc[i] > df['close'].iloc[i-1]:
                obv.iloc[i] = obv.iloc[i-1] + df['volume'].iloc[i]
            elif df['close'].iloc[i] < df['close'].iloc[i-1]:
                obv.iloc[i] = obv.iloc[i-1] - df['volume'].iloc[i]
            else:
                obv.iloc[i] = obv.iloc[i-1]

        return obv

    @staticmethod
    def obv_divergence(df: pd.DataFrame, lookback: int = 20) -> str:
        """OBV 다이버전스 감지"""
        obv = VolumeIndicators.obv(df)

        price_trend = df['close'].iloc[-1] - df['close'].iloc[-lookback]
        obv_trend = obv.iloc[-1] - obv.iloc[-lookback]

        # 가격 상승 + OBV 하락 = 약세 다이버전스 (매도 신호)
        if price_trend > 0 and obv_trend < 0:
            return 'bearish_divergence'

        # 가격 하락 + OBV 상승 = 강세 다이버전스 (매수 신호)
        if price_trend < 0 and obv_trend > 0:
            return 'bullish_divergence'

        return 'no_divergence'

    @staticmethod
    def volume_price_trend(df: pd.DataFrame) -> pd.Series:
        """Volume Price Trend (VPT)"""
        vpt = pd.Series(index=df.index, dtype=float)
        vpt.iloc[0] = 0

        for i in range(1, len(df)):
            price_change = (df['close'].iloc[i] - df['close'].iloc[i-1]) / df['close'].iloc[i-1]
            vpt.iloc[i] = vpt.iloc[i-1] + df['volume'].iloc[i] * price_change

        return vpt

    @staticmethod
    def mfi(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Money Flow Index (거래량 가중 RSI)"""
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        money_flow = typical_price * df['volume']

        positive_flow = pd.Series(0.0, index=df.index)
        negative_flow = pd.Series(0.0, index=df.index)

        for i in range(1, len(df)):
            if typical_price.iloc[i] > typical_price.iloc[i-1]:
                positive_flow.iloc[i] = money_flow.iloc[i]
            else:
                negative_flow.iloc[i] = money_flow.iloc[i]

        positive_sum = positive_flow.rolling(window=period).sum()
        negative_sum = negative_flow.rolling(window=period).sum()

        money_ratio = positive_sum / negative_sum.replace(0, np.nan)
        mfi = 100 - (100 / (1 + money_ratio))

        return mfi
```

#### Task 2.3.2: VWAP (Volume Weighted Average Price)
```
파일: hantu_common/indicators/vwap.py (신규)
작업:
  - 일중 VWAP 계산
  - VWAP 밴드 (표준편차 기반)
  - VWAP 대비 현재가 위치

코드 예시:
```python
class VWAPIndicator:
    def __init__(self):
        self.cumulative_volume = 0
        self.cumulative_vp = 0  # volume * price
        self.prices = []

    def calculate_intraday_vwap(self, df: pd.DataFrame) -> pd.Series:
        """일중 VWAP 계산"""
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        vwap = (typical_price * df['volume']).cumsum() / df['volume'].cumsum()
        return vwap

    def vwap_bands(self, df: pd.DataFrame, std_dev: float = 2.0) -> Dict[str, pd.Series]:
        """VWAP 밴드 계산"""
        vwap = self.calculate_intraday_vwap(df)
        typical_price = (df['high'] + df['low'] + df['close']) / 3

        # 누적 표준편차
        squared_diff = ((typical_price - vwap) ** 2 * df['volume']).cumsum()
        variance = squared_diff / df['volume'].cumsum()
        std = variance ** 0.5

        return {
            'vwap': vwap,
            'upper_band': vwap + std_dev * std,
            'lower_band': vwap - std_dev * std
        }

    def get_signal(self, current_price: float, vwap: float,
                   upper_band: float, lower_band: float) -> str:
        """VWAP 기반 신호"""
        if current_price < lower_band:
            return 'oversold'  # 매수 기회
        elif current_price > upper_band:
            return 'overbought'  # 매도 기회
        elif current_price < vwap:
            return 'below_vwap'  # 약세
        else:
            return 'above_vwap'  # 강세
```

---

### 2.4 투자자 수급 분석

**목표**: 기관/외국인 매매 동향 활용

#### Task 2.4.1: 수급 데이터 수집 및 분석
```
파일: core/indicators/investor_flow.py (신규)
작업:
  - KIS API investor_flow 활용
  - 기관/외국인 순매수 추적
  - 수급 기반 매매 신호

코드 예시:
```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class InvestorFlow:
    date: str
    foreign_buy: int
    foreign_sell: int
    foreign_net: int
    institution_buy: int
    institution_sell: int
    institution_net: int
    retail_net: int

@dataclass
class FlowSignal:
    signal: str  # 'strong_buy', 'buy', 'neutral', 'sell', 'strong_sell'
    foreign_trend: str
    institution_trend: str
    confidence: float
    description: str

class InvestorFlowAnalyzer:
    def __init__(self, kis_api):
        self.kis_api = kis_api

    def get_flow(self, stock_code: str, days: int = 20) -> List[InvestorFlow]:
        """수급 데이터 조회"""
        data = self.kis_api.get_investor_flow(stock_code, period=days)
        return [InvestorFlow(**d) for d in data]

    def analyze(self, flows: List[InvestorFlow]) -> FlowSignal:
        """수급 분석"""
        recent = flows[-5:]  # 최근 5일

        foreign_total = sum(f.foreign_net for f in recent)
        institution_total = sum(f.institution_net for f in recent)

        # 외국인 추세
        if foreign_total > 0:
            foreign_trend = 'buying' if foreign_total > 1_000_000_000 else 'slightly_buying'
        else:
            foreign_trend = 'selling' if foreign_total < -1_000_000_000 else 'slightly_selling'

        # 기관 추세
        if institution_total > 0:
            institution_trend = 'buying' if institution_total > 500_000_000 else 'slightly_buying'
        else:
            institution_trend = 'selling' if institution_total < -500_000_000 else 'slightly_selling'

        # 종합 신호
        buy_signals = sum([
            foreign_trend in ['buying', 'slightly_buying'],
            institution_trend in ['buying', 'slightly_buying']
        ])
        sell_signals = sum([
            foreign_trend in ['selling', 'slightly_selling'],
            institution_trend in ['selling', 'slightly_selling']
        ])

        if buy_signals == 2:
            signal = 'strong_buy'
            confidence = 0.8
        elif buy_signals == 1 and sell_signals == 0:
            signal = 'buy'
            confidence = 0.6
        elif sell_signals == 2:
            signal = 'strong_sell'
            confidence = 0.8
        elif sell_signals == 1 and buy_signals == 0:
            signal = 'sell'
            confidence = 0.6
        else:
            signal = 'neutral'
            confidence = 0.5

        return FlowSignal(
            signal=signal,
            foreign_trend=foreign_trend,
            institution_trend=institution_trend,
            confidence=confidence,
            description=f"외국인 {foreign_trend}, 기관 {institution_trend}"
        )
```

---

## Phase 3: 아키텍처 개선 (2주)

### 3.1 의존성 주입 패턴 도입

**목표**: 테스트 용이성, 결합도 감소

#### Task 3.1.1: DI 컨테이너 구현
```
파일: core/di/container.py (신규)
작업:
  - 의존성 주입 컨테이너
  - 싱글톤 vs 트랜지언트 관리
  - 테스트 시 Mock 교체 용이

코드 예시:
```python
from typing import Type, TypeVar, Dict, Callable
from functools import wraps

T = TypeVar('T')

class DIContainer:
    _instance = None
    _singletons: Dict[Type, object] = {}
    _factories: Dict[Type, Callable] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def register_singleton(self, interface: Type[T], implementation: Type[T] = None):
        """싱글톤 등록"""
        impl = implementation or interface
        self._factories[interface] = lambda: self._get_or_create_singleton(impl)

    def register_transient(self, interface: Type[T], implementation: Type[T] = None):
        """매번 새 인스턴스 등록"""
        impl = implementation or interface
        self._factories[interface] = lambda: impl()

    def register_factory(self, interface: Type[T], factory: Callable[[], T]):
        """팩토리 함수 등록"""
        self._factories[interface] = factory

    def resolve(self, interface: Type[T]) -> T:
        """의존성 해결"""
        if interface not in self._factories:
            raise ValueError(f"등록되지 않은 타입: {interface}")
        return self._factories[interface]()

    def _get_or_create_singleton(self, impl: Type[T]) -> T:
        if impl not in self._singletons:
            self._singletons[impl] = impl()
        return self._singletons[impl]

    def clear(self):
        """테스트용: 모든 등록 초기화"""
        self._singletons.clear()
        self._factories.clear()

# 글로벌 컨테이너
container = DIContainer()

# 데코레이터
def inject(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        # 타입 힌트 기반 자동 주입
        import inspect
        sig = inspect.signature(func)
        for param_name, param in sig.parameters.items():
            if param_name not in kwargs and param.annotation != inspect.Parameter.empty:
                try:
                    kwargs[param_name] = container.resolve(param.annotation)
                except ValueError:
                    pass
        return func(*args, **kwargs)
    return wrapper
```

#### Task 3.1.2: 서비스 등록 및 사용
```
파일: core/di/services.py (신규)
작업:
  - 모든 서비스 등록
  - 인터페이스 정의
  - 구현체 바인딩

코드 예시:
```python
from abc import ABC, abstractmethod
from core.di.container import container

# 인터페이스 정의
class IStockAPI(ABC):
    @abstractmethod
    def get_current_price(self, stock_code: str) -> Dict: pass

    @abstractmethod
    def get_daily_prices(self, stock_code: str, period: int) -> pd.DataFrame: pass

class IStockScreener(ABC):
    @abstractmethod
    def screen(self, stocks: List[str]) -> List[ScreeningResult]: pass

class IOrderExecutor(ABC):
    @abstractmethod
    def buy(self, stock_code: str, quantity: int, price: int = None) -> OrderResult: pass

    @abstractmethod
    def sell(self, stock_code: str, quantity: int, price: int = None) -> OrderResult: pass

# 서비스 등록
def register_services():
    from core.api.kis_api import KISAPI
    from core.watchlist.stock_screener import StockScreener
    from core.trading.order_executor import OrderExecutor

    container.register_singleton(IStockAPI, KISAPI)
    container.register_singleton(IStockScreener, StockScreener)
    container.register_transient(IOrderExecutor, OrderExecutor)

# 사용 예시
class TradingEngine:
    def __init__(self, api: IStockAPI = None, screener: IStockScreener = None):
        self.api = api or container.resolve(IStockAPI)
        self.screener = screener or container.resolve(IStockScreener)
```

---

### 3.2 데이터베이스 마이그레이션

**목표**: JSON 파일 → SQLite/PostgreSQL

#### Task 3.2.1: 데이터 모델 정의
```
파일: core/database/models.py
작업:
  - SQLAlchemy 모델 확장
  - 관계 정의
  - 인덱스 최적화

코드 예시:
```python
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from core.database.session import Base

class WatchlistStock(Base):
    __tablename__ = 'watchlist_stocks'

    id = Column(Integer, primary_key=True)
    stock_code = Column(String(6), unique=True, nullable=False, index=True)
    stock_name = Column(String(100), nullable=False)
    market = Column(String(10))  # KOSPI, KOSDAQ
    sector = Column(String(50))

    # 스크리닝 점수
    fundamental_score = Column(Float)
    technical_score = Column(Float)
    momentum_score = Column(Float)
    total_score = Column(Float, index=True)

    # 메타데이터
    added_date = Column(DateTime, default=datetime.now)
    last_updated = Column(DateTime, onupdate=datetime.now)
    is_active = Column(Integer, default=1)

    # 관계
    daily_selections = relationship("DailySelection", back_populates="stock")

    __table_args__ = (
        Index('idx_watchlist_score_active', 'total_score', 'is_active'),
    )

class DailySelection(Base):
    __tablename__ = 'daily_selections'

    id = Column(Integer, primary_key=True)
    stock_id = Column(Integer, ForeignKey('watchlist_stocks.id'), nullable=False)
    selection_date = Column(DateTime, nullable=False, index=True)

    # 가격 정보
    entry_price = Column(Integer)
    current_price = Column(Integer)

    # 분석 결과
    attractiveness_score = Column(Float)
    risk_score = Column(Float)
    signal_count = Column(Integer)

    # 매매 기준
    stop_loss_price = Column(Integer)
    take_profit_price = Column(Integer)
    position_size = Column(Float)

    # 상태
    status = Column(String(20), default='pending')  # pending, bought, sold, cancelled

    # 관계
    stock = relationship("WatchlistStock", back_populates="daily_selections")

    __table_args__ = (
        Index('idx_selection_date_status', 'selection_date', 'status'),
    )

class TradeHistory(Base):
    __tablename__ = 'trade_history'

    id = Column(Integer, primary_key=True)
    stock_code = Column(String(6), nullable=False, index=True)
    trade_type = Column(String(10))  # buy, sell
    quantity = Column(Integer)
    price = Column(Integer)
    total_amount = Column(Integer)
    commission = Column(Integer)

    # 성과
    profit_loss = Column(Integer)
    profit_loss_rate = Column(Float)

    # 타임스탬프
    order_time = Column(DateTime)
    execution_time = Column(DateTime, index=True)

    # 전략 정보
    strategy_name = Column(String(50))
    signal_source = Column(String(100))
```

#### Task 3.2.2: Repository 패턴 구현
```
파일: core/database/repositories.py
작업:
  - CRUD 작업 추상화
  - 트랜잭션 관리
  - 쿼리 최적화

코드 예시:
```python
from typing import List, Optional
from sqlalchemy.orm import Session
from contextlib import contextmanager

class BaseRepository:
    def __init__(self, session: Session):
        self.session = session

    @contextmanager
    def transaction(self):
        try:
            yield
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

class WatchlistRepository(BaseRepository):
    def add_stock(self, stock: WatchlistStock) -> WatchlistStock:
        with self.transaction():
            self.session.add(stock)
            self.session.flush()
            return stock

    def get_by_code(self, stock_code: str) -> Optional[WatchlistStock]:
        return self.session.query(WatchlistStock)\
            .filter(WatchlistStock.stock_code == stock_code)\
            .filter(WatchlistStock.is_active == 1)\
            .first()

    def get_top_stocks(self, limit: int = 100) -> List[WatchlistStock]:
        return self.session.query(WatchlistStock)\
            .filter(WatchlistStock.is_active == 1)\
            .order_by(WatchlistStock.total_score.desc())\
            .limit(limit)\
            .all()

    def update_scores(self, stock_code: str, scores: Dict[str, float]) -> bool:
        with self.transaction():
            stock = self.get_by_code(stock_code)
            if not stock:
                return False

            stock.fundamental_score = scores.get('fundamental', stock.fundamental_score)
            stock.technical_score = scores.get('technical', stock.technical_score)
            stock.momentum_score = scores.get('momentum', stock.momentum_score)
            stock.total_score = scores.get('total', stock.total_score)
            stock.last_updated = datetime.now()

            return True

    def bulk_upsert(self, stocks: List[WatchlistStock]) -> int:
        """대량 삽입/업데이트"""
        with self.transaction():
            count = 0
            for stock_data in stocks:
                existing = self.get_by_code(stock_data.stock_code)
                if existing:
                    # 업데이트
                    for key, value in stock_data.__dict__.items():
                        if not key.startswith('_') and value is not None:
                            setattr(existing, key, value)
                else:
                    # 삽입
                    self.session.add(stock_data)
                count += 1
            return count
```

---

### 3.3 비동기 처리 도입

**목표**: I/O 바운드 작업 병렬화

#### Task 3.3.1: 비동기 API 클라이언트
```
파일: core/api/async_client.py (신규)
작업:
  - aiohttp 기반 비동기 클라이언트
  - 동시 요청 제한 (세마포어)
  - 비동기 재시도

코드 예시:
```python
import aiohttp
import asyncio
from typing import List, Dict

class AsyncKISClient:
    def __init__(self, max_concurrent: int = 10):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.session: aiohttp.ClientSession = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, *args):
        await self.session.close()

    async def _request(self, method: str, url: str, **kwargs) -> Dict:
        async with self.semaphore:
            async with self.session.request(method, url, **kwargs) as response:
                return await response.json()

    async def get_current_prices(self, stock_codes: List[str]) -> Dict[str, Dict]:
        """여러 종목 현재가 동시 조회"""
        tasks = [
            self._get_price(code) for code in stock_codes
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        return {
            code: result for code, result in zip(stock_codes, results)
            if not isinstance(result, Exception)
        }

    async def _get_price(self, stock_code: str) -> Dict:
        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-price"
        params = {"FID_INPUT_ISCD": stock_code}
        return await self._request("GET", url, params=params)

# 사용 예시
async def fetch_all_prices(stock_codes: List[str]) -> Dict:
    async with AsyncKISClient(max_concurrent=10) as client:
        return await client.get_current_prices(stock_codes)

# 동기 코드에서 호출
def get_prices_sync(stock_codes: List[str]) -> Dict:
    return asyncio.run(fetch_all_prices(stock_codes))
```

---

## Phase 4: AI/ML 강화 (3주)

### 4.1 LSTM 가격 예측 모델

**목표**: 단기 가격 방향 예측

#### Task 4.1.1: LSTM 모델 구현
```
파일: core/learning/models/lstm_predictor.py (신규)
작업:
  - PyTorch 기반 LSTM 모델
  - 시퀀스 데이터 전처리
  - 학습/추론 파이프라인

코드 예시:
```python
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
import numpy as np

class StockDataset(Dataset):
    def __init__(self, data: np.ndarray, seq_length: int = 60):
        self.data = data
        self.seq_length = seq_length

    def __len__(self):
        return len(self.data) - self.seq_length

    def __getitem__(self, idx):
        x = self.data[idx:idx + self.seq_length]
        y = self.data[idx + self.seq_length, 0]  # 다음날 종가
        return torch.FloatTensor(x), torch.FloatTensor([y])

class LSTMPredictor(nn.Module):
    def __init__(self, input_size: int = 5, hidden_size: int = 128,
                 num_layers: int = 2, dropout: float = 0.2):
        super().__init__()

        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            dropout=dropout,
            batch_first=True
        )

        self.fc = nn.Sequential(
            nn.Linear(hidden_size, 64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, 1)
        )

    def forward(self, x):
        lstm_out, _ = self.lstm(x)
        last_output = lstm_out[:, -1, :]
        return self.fc(last_output)

class LSTMTrainer:
    def __init__(self, model: LSTMPredictor, learning_rate: float = 0.001):
        self.model = model
        self.optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
        self.criterion = nn.MSELoss()
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model.to(self.device)

    def train(self, train_loader: DataLoader, epochs: int = 100) -> List[float]:
        losses = []
        self.model.train()

        for epoch in range(epochs):
            epoch_loss = 0
            for x_batch, y_batch in train_loader:
                x_batch = x_batch.to(self.device)
                y_batch = y_batch.to(self.device)

                self.optimizer.zero_grad()
                predictions = self.model(x_batch)
                loss = self.criterion(predictions, y_batch)
                loss.backward()
                self.optimizer.step()

                epoch_loss += loss.item()

            avg_loss = epoch_loss / len(train_loader)
            losses.append(avg_loss)

            if (epoch + 1) % 10 == 0:
                print(f"Epoch {epoch+1}/{epochs}, Loss: {avg_loss:.6f}")

        return losses

    def predict(self, x: np.ndarray) -> float:
        self.model.eval()
        with torch.no_grad():
            x_tensor = torch.FloatTensor(x).unsqueeze(0).to(self.device)
            prediction = self.model(x_tensor)
            return prediction.item()
```

#### Task 4.1.2: 예측 기반 신호 생성
```
파일: core/learning/models/prediction_signal.py (신규)
작업:
  - 예측값 기반 매매 신호
  - 신뢰도 계산
  - 백테스트 검증

코드 예시:
```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class PredictionSignal:
    predicted_price: float
    current_price: float
    predicted_change: float  # 예측 변화율 (%)
    signal: str  # 'buy', 'sell', 'hold'
    confidence: float  # 0.0 ~ 1.0
    model_accuracy: float  # 모델의 최근 정확도

class PredictionSignalGenerator:
    def __init__(self, lstm_model: LSTMPredictor, buy_threshold: float = 2.0,
                 sell_threshold: float = -2.0):
        self.model = lstm_model
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold
        self.recent_predictions: List[Tuple[float, float]] = []  # (예측, 실제)

    def generate_signal(self, features: np.ndarray, current_price: float) -> PredictionSignal:
        predicted_price = self.model.predict(features)
        predicted_change = (predicted_price - current_price) / current_price * 100

        # 신호 결정
        if predicted_change > self.buy_threshold:
            signal = 'buy'
            confidence = min(predicted_change / (self.buy_threshold * 2), 1.0)
        elif predicted_change < self.sell_threshold:
            signal = 'sell'
            confidence = min(abs(predicted_change) / (abs(self.sell_threshold) * 2), 1.0)
        else:
            signal = 'hold'
            confidence = 1.0 - abs(predicted_change) / self.buy_threshold

        return PredictionSignal(
            predicted_price=predicted_price,
            current_price=current_price,
            predicted_change=predicted_change,
            signal=signal,
            confidence=confidence,
            model_accuracy=self._calculate_accuracy()
        )

    def update_accuracy(self, predicted: float, actual: float):
        self.recent_predictions.append((predicted, actual))
        if len(self.recent_predictions) > 100:
            self.recent_predictions.pop(0)

    def _calculate_accuracy(self) -> float:
        if len(self.recent_predictions) < 10:
            return 0.5  # 데이터 부족

        correct = 0
        for pred, actual in self.recent_predictions:
            pred_direction = 1 if pred > 0 else -1
            actual_direction = 1 if actual > 0 else -1
            if pred_direction == actual_direction:
                correct += 1

        return correct / len(self.recent_predictions)
```

---

### 4.2 강화학습 포지션 관리

**목표**: 최적 매수/매도 타이밍 및 수량 학습

#### Task 4.2.1: 트레이딩 환경 구현
```
파일: core/learning/rl/trading_env.py (신규)
작업:
  - OpenAI Gym 호환 환경
  - 상태/행동/보상 정의
  - 시뮬레이션 로직

코드 예시:
```python
import gymnasium as gym
from gymnasium import spaces
import numpy as np

class TradingEnv(gym.Env):
    def __init__(self, df: pd.DataFrame, initial_balance: float = 10_000_000,
                 commission: float = 0.00015):
        super().__init__()

        self.df = df
        self.initial_balance = initial_balance
        self.commission = commission

        # 상태: [잔고 비율, 포지션 비율, RSI, MACD, 변화율, ...]
        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf, shape=(10,), dtype=np.float32
        )

        # 행동: [0=홀드, 1=매수10%, 2=매수30%, 3=매수50%, 4=매도10%, 5=매도30%, 6=매도50%, 7=전량매도]
        self.action_space = spaces.Discrete(8)

        self.reset()

    def reset(self, seed=None):
        super().reset(seed=seed)

        self.current_step = 0
        self.balance = self.initial_balance
        self.shares = 0
        self.total_value = self.initial_balance
        self.trades = []

        return self._get_observation(), {}

    def step(self, action):
        current_price = self.df.iloc[self.current_step]['close']

        # 행동 실행
        reward = self._execute_action(action, current_price)

        # 다음 스텝
        self.current_step += 1
        done = self.current_step >= len(self.df) - 1

        # 포트폴리오 가치 업데이트
        if not done:
            next_price = self.df.iloc[self.current_step]['close']
            self.total_value = self.balance + self.shares * next_price

        return self._get_observation(), reward, done, False, {}

    def _execute_action(self, action, price) -> float:
        prev_value = self.total_value

        if action == 0:  # 홀드
            pass
        elif action in [1, 2, 3]:  # 매수
            buy_ratio = {1: 0.1, 2: 0.3, 3: 0.5}[action]
            amount = self.balance * buy_ratio
            shares_to_buy = int(amount / price)
            cost = shares_to_buy * price * (1 + self.commission)

            if cost <= self.balance and shares_to_buy > 0:
                self.balance -= cost
                self.shares += shares_to_buy
                self.trades.append(('buy', price, shares_to_buy))

        elif action in [4, 5, 6]:  # 부분 매도
            sell_ratio = {4: 0.1, 5: 0.3, 6: 0.5}[action]
            shares_to_sell = int(self.shares * sell_ratio)

            if shares_to_sell > 0:
                proceeds = shares_to_sell * price * (1 - self.commission)
                self.balance += proceeds
                self.shares -= shares_to_sell
                self.trades.append(('sell', price, shares_to_sell))

        elif action == 7:  # 전량 매도
            if self.shares > 0:
                proceeds = self.shares * price * (1 - self.commission)
                self.balance += proceeds
                self.trades.append(('sell', price, self.shares))
                self.shares = 0

        # 현재 가치 계산
        self.total_value = self.balance + self.shares * price

        # 보상: 가치 변화율
        reward = (self.total_value - prev_value) / prev_value * 100

        return reward

    def _get_observation(self) -> np.ndarray:
        row = self.df.iloc[self.current_step]
        current_price = row['close']

        return np.array([
            self.balance / self.initial_balance,  # 잔고 비율
            (self.shares * current_price) / self.total_value if self.total_value > 0 else 0,  # 포지션 비율
            row.get('rsi', 50) / 100,  # RSI 정규화
            row.get('macd', 0) / 1000,  # MACD 정규화
            row.get('change_rate', 0) / 10,  # 변화율 정규화
            row.get('volume_ratio', 1),  # 거래량 비율
            row.get('bb_position', 0.5),  # 볼린저밴드 위치
            self.total_value / self.initial_balance - 1,  # 수익률
            len(self.trades) / 100,  # 거래 횟수 정규화
            self.current_step / len(self.df)  # 진행률
        ], dtype=np.float32)
```

#### Task 4.2.2: PPO 에이전트 학습
```
파일: core/learning/rl/ppo_agent.py (신규)
작업:
  - Stable-Baselines3 PPO 활용
  - 학습 및 평가
  - 모델 저장/로드

코드 예시:
```python
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv
from stable_baselines3.common.callbacks import EvalCallback

class TradingAgent:
    def __init__(self, env: TradingEnv):
        self.env = DummyVecEnv([lambda: env])
        self.model = PPO(
            "MlpPolicy",
            self.env,
            learning_rate=3e-4,
            n_steps=2048,
            batch_size=64,
            n_epochs=10,
            gamma=0.99,
            verbose=1
        )

    def train(self, total_timesteps: int = 100000, eval_env: TradingEnv = None):
        callbacks = []

        if eval_env:
            eval_callback = EvalCallback(
                DummyVecEnv([lambda: eval_env]),
                best_model_save_path="./models/",
                log_path="./logs/",
                eval_freq=5000,
                deterministic=True
            )
            callbacks.append(eval_callback)

        self.model.learn(total_timesteps=total_timesteps, callback=callbacks)

    def predict(self, observation: np.ndarray) -> int:
        action, _ = self.model.predict(observation, deterministic=True)
        return int(action)

    def save(self, path: str):
        self.model.save(path)

    @classmethod
    def load(cls, path: str, env: TradingEnv):
        agent = cls(env)
        agent.model = PPO.load(path, env=agent.env)
        return agent
```

---

## Phase 5: 선물/해외주식 확장 (2주)

### 5.1 선물 헤징 시스템

**목표**: 포트폴리오 하락 리스크 헤지

#### Task 5.1.1: 코스피200 선물 연동
```
파일: core/hedging/futures_hedger.py (신규)
작업:
  - KIS 선물 API 연동
  - 베타 기반 헤지 비율 계산
  - 자동 헤지 포지션 관리

코드 예시:
```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class HedgePosition:
    futures_code: str  # 예: "101S12"
    contracts: int
    entry_price: float
    hedge_ratio: float
    portfolio_value: float

class FuturesHedger:
    def __init__(self, kis_api):
        self.kis_api = kis_api
        self.current_hedge: Optional[HedgePosition] = None
        self.contract_multiplier = 250000  # 코스피200 선물 1계약 = 지수 × 25만원

    def calculate_hedge_ratio(self, portfolio_beta: float,
                              portfolio_value: float,
                              futures_price: float) -> int:
        """헤지에 필요한 선물 계약 수 계산"""
        # 헤지 비율 = 포트폴리오 가치 × 베타 / (선물가격 × 승수)
        hedge_value = portfolio_value * portfolio_beta
        contracts = int(hedge_value / (futures_price * self.contract_multiplier))
        return max(1, contracts)  # 최소 1계약

    def calculate_portfolio_beta(self, holdings: List[Dict]) -> float:
        """포트폴리오 베타 계산"""
        total_value = sum(h['value'] for h in holdings)
        weighted_beta = sum(
            h['value'] / total_value * h.get('beta', 1.0)
            for h in holdings
        )
        return weighted_beta

    def open_hedge(self, portfolio_value: float, portfolio_beta: float) -> HedgePosition:
        """헤지 포지션 오픈"""
        # 선물 현재가 조회
        futures_price = self.kis_api.get_futures_price("101")  # 근월물

        contracts = self.calculate_hedge_ratio(portfolio_beta, portfolio_value, futures_price)

        # 선물 매도 주문 (헤지)
        order_result = self.kis_api.sell_futures("101", contracts)

        if order_result['success']:
            self.current_hedge = HedgePosition(
                futures_code="101",
                contracts=contracts,
                entry_price=futures_price,
                hedge_ratio=portfolio_beta,
                portfolio_value=portfolio_value
            )
            return self.current_hedge

        raise Exception(f"헤지 주문 실패: {order_result}")

    def close_hedge(self) -> Dict:
        """헤지 포지션 청산"""
        if not self.current_hedge:
            return {"success": False, "message": "활성 헤지 없음"}

        # 선물 매수로 청산
        order_result = self.kis_api.buy_futures(
            self.current_hedge.futures_code,
            self.current_hedge.contracts
        )

        if order_result['success']:
            current_price = order_result['price']
            profit = (self.current_hedge.entry_price - current_price) * \
                     self.current_hedge.contracts * self.contract_multiplier

            self.current_hedge = None
            return {"success": True, "profit": profit}

        return order_result

    def should_hedge(self, market_condition: str, portfolio_value: float) -> bool:
        """헤지 필요 여부 판단"""
        # 고변동성 또는 약세장에서 헤지
        if market_condition in ['high_volatility', 'very_high_volatility', 'bear']:
            return True

        # 포트폴리오 규모가 클 때 헤지
        if portfolio_value > 50_000_000:  # 5천만원 이상
            return True

        return False
```

### 5.2 해외주식 분산 투자

**목표**: 글로벌 분산으로 변동성 감소

#### Task 5.2.1: 미국 주식 트레이딩
```
파일: core/overseas/us_trader.py (신규)
작업:
  - KIS 해외주식 API 연동
  - 환율 자동 계산
  - 미국 장 시간 스케줄링

코드 예시:
```python
from datetime import datetime, time
import pytz

class USStockTrader:
    US_MARKET_OPEN = time(9, 30)   # EST
    US_MARKET_CLOSE = time(16, 0)  # EST

    def __init__(self, kis_api):
        self.kis_api = kis_api
        self.est_tz = pytz.timezone('US/Eastern')
        self.kst_tz = pytz.timezone('Asia/Seoul')

    def is_market_open(self) -> bool:
        """미국 장 개장 여부"""
        now_est = datetime.now(self.est_tz).time()
        return self.US_MARKET_OPEN <= now_est <= self.US_MARKET_CLOSE

    def get_exchange_rate(self) -> float:
        """현재 USD/KRW 환율"""
        return self.kis_api.get_exchange_rate("USD")

    def get_us_stock_price(self, symbol: str) -> Dict:
        """미국 주식 현재가 조회"""
        return self.kis_api.get_overseas_price(
            exchange="NAS" if symbol in self.NASDAQ_SYMBOLS else "NYS",
            symbol=symbol
        )

    def buy_us_stock(self, symbol: str, quantity: int,
                    order_type: str = 'limit', price: float = None) -> Dict:
        """미국 주식 매수"""
        if not self.is_market_open():
            return {"success": False, "message": "미국 장 마감"}

        exchange = "NAS" if self._is_nasdaq(symbol) else "NYS"

        return self.kis_api.place_overseas_order(
            exchange=exchange,
            symbol=symbol,
            side="buy",
            quantity=quantity,
            order_type=order_type,
            price=price
        )

    def get_diversified_portfolio(self) -> List[Dict]:
        """추천 분산 포트폴리오"""
        return [
            {"symbol": "QQQ", "weight": 0.3, "description": "나스닥100 ETF"},
            {"symbol": "SPY", "weight": 0.3, "description": "S&P500 ETF"},
            {"symbol": "VGK", "weight": 0.2, "description": "유럽 ETF"},
            {"symbol": "EEM", "weight": 0.2, "description": "신흥국 ETF"},
        ]
```

---

## 구현 일정 요약

| Phase | 기간 | 핵심 작업 | 예상 효과 |
|-------|------|----------|----------|
| **Phase 1** | 1주 | 에러 처리, 데이터 검증, 로깅 | 안정성 50%↑ |
| **Phase 2** | 2주 | 호가 분석, 동적 손절, 고급 지표 | 수익률 10-15%↑ |
| **Phase 3** | 2주 | DI 패턴, DB 마이그레이션, 비동기 | 유지보수성 ↑ |
| **Phase 4** | 3주 | LSTM 예측, 강화학습 | 예측 정확도 60%+ |
| **Phase 5** | 2주 | 선물 헤징, 해외주식 | MDD 30%↓ |

---

## 성과 목표

| 지표 | 현재 | Phase 1-2 후 | Phase 3-5 후 |
|------|------|-------------|-------------|
| 연수익률 | 12% | 18% | **25%+** |
| 샤프비율 | 1.2 | 1.5 | **2.0+** |
| 최대낙폭 | -8% | -6% | **-4%** |
| 승률 | 58% | 63% | **68%+** |
| 시스템 가용성 | 85% | 95% | **99%+** |

---

## 다음 단계

1. 이 계획서 검토 및 승인
2. Phase 1 즉시 착수
3. 주간 진행 상황 리뷰

---

*작성일: 2025-12-25*
*버전: 1.0*
