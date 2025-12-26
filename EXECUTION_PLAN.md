# Hantu Quant 실행 계획서

> 다른 채팅에서 바로 실행 가능한 우선순위 기반 태스크 목록

---

## 우선순위 기준

| 등급 | 기준 | 설명 |
|------|------|------|
| **P0** | 즉시 필수 | 프로덕션 운영 불가능한 치명적 문제 |
| **P1** | 높은 우선순위 | 수익에 직접 영향, 1주 내 완료 |
| **P2** | 중간 우선순위 | 시스템 개선, 2주 내 완료 |
| **P3** | 낮은 우선순위 | 장기 투자, 1개월 내 완료 |

---

## 🔴 P0: 즉시 필수 (1-3일)

### P0-1: API 재시도 로직 구현
```
파일: core/api/rest_client.py
중요도: ★★★★★
이유: API 실패 시 전체 시스템 중단 → 매매 기회 손실

작업 내용:
1. tenacity 라이브러리 추가 (requirements.txt)
2. _request() 메서드에 재시도 데코레이터 적용
3. 재시도 가능 에러: Timeout, ConnectionError, 5xx
4. 재시도 불가 에러: 4xx, 인증 실패
5. 지수 백오프: 2초, 4초, 8초 (최대 3회)

코드:
```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import requests

class KISRestClient:
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=10),
        retry=retry_if_exception_type((requests.Timeout, requests.ConnectionError)),
        before_sleep=lambda rs: logger.warning(f"API 재시도 {rs.attempt_number}/3")
    )
    def _request(self, method: str, url: str, ...) -> Dict:
        # 기존 로직 유지
```

테스트:
- 네트워크 끊김 시뮬레이션
- 타임아웃 시뮬레이션
- 3회 실패 후 최종 에러 확인
```

### P0-2: 부분 실패 허용 로직
```
파일: workflows/phase1_watchlist.py, workflows/phase2_daily_selection.py
중요도: ★★★★★
이유: 1개 종목 실패로 전체 스크리닝 중단 방지

작업 내용:
1. PartialResult 클래스 생성
2. 개별 종목 try-except 래핑
3. 성공률 90% 이상이면 계속 진행
4. 실패 종목 로깅 및 별도 저장

코드:
```python
@dataclass
class PartialResult:
    successful: List[ScreeningResult]
    failed: List[Tuple[str, str]]  # (stock_code, error_message)

    @property
    def success_rate(self) -> float:
        total = len(self.successful) + len(self.failed)
        return len(self.successful) / total if total > 0 else 0

def screen_stocks_with_partial_failure(stocks: List[str]) -> PartialResult:
    results = []
    failures = []

    for stock in stocks:
        try:
            result = screen_single_stock(stock)
            results.append(result)
        except Exception as e:
            logger.warning(f"종목 {stock} 스크리닝 실패: {e}")
            failures.append((stock, str(e)))

    return PartialResult(successful=results, failed=failures)
```
```

### P0-3: 민감 엔드포인트 인증 추가
```
파일: api-server/main.py
중요도: ★★★★★
이유: 거래 정보 무단 접근 가능 → 전략 노출 위험

작업 내용:
1. /api/watchlist, /api/daily-selections, /api/alerts에 인증 추가
2. Depends(verify_api_key) 적용

코드:
```python
@app.get("/api/watchlist", response_model=List[WatchlistItem])
async def get_watchlist(authenticated: bool = Depends(verify_api_key)):
    return REAL_WATCHLIST

@app.get("/api/daily-selections", response_model=List[DailySelection])
async def get_daily_selections(authenticated: bool = Depends(verify_api_key)):
    return REAL_DAILY_SELECTIONS

@app.get("/api/alerts", response_model=List[MarketAlert])
async def get_alerts(authenticated: bool = Depends(verify_api_key)):
    return REAL_ALERTS
```
```

---

## 🟠 P1: 수익 직결 기능 (1주)

### P1-1: 동적 손절/익절 시스템 (ATR 기반)
```
파일: core/trading/dynamic_stop_loss.py (신규)
중요도: ★★★★☆
이유: 고정 3%/8% → 변동성 무시 → 불필요한 손절 or 큰 손실
예상 효과: 손실 20% 감소

작업 내용:
1. ATR(14일) 계산 함수
2. 손절가 = 진입가 - ATR × 2.0
3. 익절가 = 진입가 + ATR × 3.0
4. 트레일링 스탑 자동 조정
5. TradingEngine과 통합

핵심 코드:
```python
class DynamicStopLossCalculator:
    def __init__(self, atr_period: int = 14,
                 stop_multiplier: float = 2.0,
                 profit_multiplier: float = 3.0):
        self.atr_period = atr_period
        self.stop_multiplier = stop_multiplier
        self.profit_multiplier = profit_multiplier

    def calculate_atr(self, df: pd.DataFrame) -> float:
        high, low, close = df['high'], df['low'], df['close'].shift(1)
        tr = pd.concat([high - low, abs(high - close), abs(low - close)], axis=1).max(axis=1)
        return tr.rolling(self.atr_period).mean().iloc[-1]

    def get_stops(self, entry_price: int, df: pd.DataFrame) -> Dict:
        atr = self.calculate_atr(df)
        return {
            'stop_loss': int(entry_price - atr * self.stop_multiplier),
            'take_profit': int(entry_price + atr * self.profit_multiplier),
            'atr': atr
        }
```

통합 위치: core/trading/trading_engine.py의 _calculate_position_size()
```

### P1-2: 호가 불균형 분석기
```
파일: core/indicators/orderbook_analyzer.py (신규)
중요도: ★★★★☆
이유: 매수/매도 잔량 비율로 단기 방향 예측
예상 효과: 체결 정확도 30% 향상

작업 내용:
1. WebSocket H0STASP0 (호가) 데이터 파싱
2. 불균형 비율 = (매수잔량 - 매도잔량) / 총잔량
3. 신호: >0.3 강한매수, >0.1 매수, <-0.1 매도, <-0.3 강한매도
4. WebSocketClient와 연동

핵심 코드:
```python
@dataclass
class OrderBookImbalance:
    bid_volume: int
    ask_volume: int
    imbalance_ratio: float  # -1.0 ~ 1.0
    signal: str  # strong_buy, buy, neutral, sell, strong_sell
    confidence: float

class OrderBookAnalyzer:
    def analyze(self, bids: List[Tuple[int, int]],
                asks: List[Tuple[int, int]], levels: int = 10) -> OrderBookImbalance:
        bid_vol = sum(vol for _, vol in bids[:levels])
        ask_vol = sum(vol for _, vol in asks[:levels])
        total = bid_vol + ask_vol

        ratio = (bid_vol - ask_vol) / total if total > 0 else 0

        if ratio > 0.3: signal, conf = 'strong_buy', min(ratio/0.5, 1)
        elif ratio > 0.1: signal, conf = 'buy', ratio/0.3
        elif ratio < -0.3: signal, conf = 'strong_sell', min(abs(ratio)/0.5, 1)
        elif ratio < -0.1: signal, conf = 'sell', abs(ratio)/0.3
        else: signal, conf = 'neutral', 1 - abs(ratio)/0.1

        return OrderBookImbalance(bid_vol, ask_vol, ratio, signal, conf)
```

연동: core/api/websocket_client.py의 on_message() 콜백
```

### P1-3: 투자자 수급 신호
```
파일: core/indicators/investor_flow.py (신규)
중요도: ★★★★☆
이유: 기관/외국인 순매수 종목 = 상승 확률 높음
예상 효과: 신뢰도 있는 추가 매매 신호

작업 내용:
1. KIS API get_investor_flow() 활용
2. 최근 5일 외국인/기관 순매수 합계
3. 양방향 순매수 = strong_buy 신호
4. Phase 2 선정 기준에 가중치 추가

핵심 코드:
```python
class InvestorFlowAnalyzer:
    def __init__(self, kis_api):
        self.kis_api = kis_api

    def analyze(self, stock_code: str, days: int = 5) -> Dict:
        data = self.kis_api.get_investor_flow(stock_code, period=days)

        foreign_net = sum(d.get('frgn_ntby_qty', 0) for d in data)
        inst_net = sum(d.get('orgn_ntby_qty', 0) for d in data)

        foreign_trend = 'buying' if foreign_net > 1_000_000 else 'selling' if foreign_net < -1_000_000 else 'neutral'
        inst_trend = 'buying' if inst_net > 500_000 else 'selling' if inst_net < -500_000 else 'neutral'

        # 종합 신호
        buy_count = sum([foreign_trend == 'buying', inst_trend == 'buying'])
        if buy_count == 2: return {'signal': 'strong_buy', 'confidence': 0.8}
        elif buy_count == 1: return {'signal': 'buy', 'confidence': 0.6}
        # ... 나머지 로직
```

통합 위치: core/daily_selection/price_analyzer.py의 analyze() 메서드
```

### P1-4: OBV (On Balance Volume) 지표
```
파일: hantu_common/indicators/volume_indicators.py (신규)
중요도: ★★★☆☆
이유: 가격-거래량 다이버전스로 추세 전환 조기 감지
예상 효과: 추세 전환 신호 정확도 향상

작업 내용:
1. OBV 계산 (누적 거래량)
2. OBV 다이버전스 감지
3. Phase 2 기술적 신호에 추가

핵심 코드:
```python
class VolumeIndicators:
    @staticmethod
    def obv(df: pd.DataFrame) -> pd.Series:
        obv = [df['volume'].iloc[0]]
        for i in range(1, len(df)):
            if df['close'].iloc[i] > df['close'].iloc[i-1]:
                obv.append(obv[-1] + df['volume'].iloc[i])
            elif df['close'].iloc[i] < df['close'].iloc[i-1]:
                obv.append(obv[-1] - df['volume'].iloc[i])
            else:
                obv.append(obv[-1])
        return pd.Series(obv, index=df.index)

    @staticmethod
    def obv_divergence(df: pd.DataFrame, lookback: int = 20) -> str:
        obv = VolumeIndicators.obv(df)
        price_trend = df['close'].iloc[-1] - df['close'].iloc[-lookback]
        obv_trend = obv.iloc[-1] - obv.iloc[-lookback]

        if price_trend > 0 and obv_trend < 0: return 'bearish_divergence'
        if price_trend < 0 and obv_trend > 0: return 'bullish_divergence'
        return 'no_divergence'
```
```

### P1-5: 시장 상황별 적응형 설정
```
파일: core/trading/market_adaptive_risk.py (신규)
중요도: ★★★☆☆
이유: 고변동성 시장에서 동일 전략 = 큰 손실
예상 효과: 시장 상황별 최적 리스크 관리

작업 내용:
1. KOSPI 변동성 계산 (연율화)
2. 5단계 시장 상황 분류
3. 상황별 손절배수, 포지션 크기, 최대 종목수 조정

핵심 코드:
```python
class MarketAdaptiveRisk:
    CONFIGS = {
        'very_low': {'stop_mult': 1.5, 'position_factor': 1.2, 'max_pos': 15},   # VIX < 12
        'low': {'stop_mult': 1.8, 'position_factor': 1.1, 'max_pos': 12},        # 12-16
        'normal': {'stop_mult': 2.0, 'position_factor': 1.0, 'max_pos': 10},     # 16-20
        'high': {'stop_mult': 2.5, 'position_factor': 0.7, 'max_pos': 7},        # 20-30
        'very_high': {'stop_mult': 3.0, 'position_factor': 0.5, 'max_pos': 5},   # > 30
    }

    def get_market_volatility(self, kospi_df: pd.DataFrame) -> str:
        returns = kospi_df['close'].pct_change().dropna()
        vol = returns.std() * (252 ** 0.5) * 100

        if vol < 12: return 'very_low'
        elif vol < 16: return 'low'
        elif vol < 20: return 'normal'
        elif vol < 30: return 'high'
        return 'very_high'
```

통합: TradingEngine, PositionSizer에서 config 참조
```

---

## 🟡 P2: 시스템 안정화 (2주)

### P2-1: Pydantic 데이터 검증
```
파일: core/models/validators.py (신규)
중요도: ★★★☆☆
이유: 잘못된 입력으로 런타임 에러 방지

작업 내용:
1. StockCode 모델 (6자리 숫자 검증)
2. PriceData 모델 (양수, 범위 검증)
3. OrderRequest 모델 (수량, 가격 검증)
4. API 응답 파싱에 적용

핵심 코드:
```python
from pydantic import BaseModel, Field, field_validator
import re

class StockCode(BaseModel):
    code: str = Field(..., min_length=6, max_length=6)

    @field_validator('code')
    @classmethod
    def validate_code(cls, v):
        if not re.match(r'^\d{6}$', v):
            raise ValueError(f'종목코드 형식 오류: {v}')
        return v

class PriceData(BaseModel):
    current_price: int = Field(..., gt=0)
    volume: int = Field(..., ge=0)
    change_rate: float = Field(..., ge=-30, le=30)

class OrderRequest(BaseModel):
    stock_code: str
    quantity: int = Field(..., gt=0, le=100000)
    price: Optional[int] = Field(None, gt=0)
    order_type: Literal['market', 'limit']

    @field_validator('stock_code')
    @classmethod
    def validate_stock_code(cls, v):
        return StockCode(code=v).code
```
```

### P2-2: 구조화된 로깅 (JSON)
```
파일: core/utils/log_utils.py
중요도: ★★★☆☆
이유: 로그 분석/모니터링 시스템 통합 용이

작업 내용:
1. JSONFormatter 클래스 추가
2. TimedRotatingFileHandler (일별, 30일 보관)
3. trace_id 추가 (요청 추적)

핵심 코드:
```python
import json
from logging.handlers import TimedRotatingFileHandler

class JSONFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({
            'timestamp': datetime.now().isoformat(),
            'level': record.levelname,
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'message': record.getMessage(),
            'trace_id': getattr(record, 'trace_id', None)
        }, ensure_ascii=False)

def setup_json_logging(log_file: str):
    handler = TimedRotatingFileHandler(
        log_file, when='midnight', backupCount=30, encoding='utf-8'
    )
    handler.setFormatter(JSONFormatter())
    logging.getLogger().addHandler(handler)
```
```

### P2-3: 의존성 헬스체크
```
파일: api-server/main.py
중요도: ★★★☆☆
이유: 장애 조기 감지, 운영 안정성

작업 내용:
1. /health 엔드포인트 확장
2. DB, KIS API, WebSocket 상태 체크
3. 메모리/CPU 사용량 모니터링

핵심 코드:
```python
import psutil

class HealthStatus(BaseModel):
    status: Literal['healthy', 'degraded', 'unhealthy']
    database: bool
    kis_api: bool
    websocket: bool
    memory_percent: float
    cpu_percent: float
    uptime_seconds: float

@app.get("/health")
async def health_check() -> HealthStatus:
    db_ok = await check_db_connection()
    api_ok = await check_kis_api()
    ws_ok = check_websocket_connection()

    all_ok = all([db_ok, api_ok, ws_ok])
    any_ok = any([db_ok, api_ok, ws_ok])

    return HealthStatus(
        status='healthy' if all_ok else 'degraded' if any_ok else 'unhealthy',
        database=db_ok,
        kis_api=api_ok,
        websocket=ws_ok,
        memory_percent=psutil.virtual_memory().percent,
        cpu_percent=psutil.cpu_percent(),
        uptime_seconds=time.time() - START_TIME
    )
```
```

### P2-4: 비동기 가격 조회
```
파일: core/api/async_client.py (신규)
중요도: ★★☆☆☆
이유: 100개 종목 순차 조회 → 병렬 조회로 속도 10배↑

작업 내용:
1. aiohttp 기반 비동기 클라이언트
2. 동시 요청 제한 (세마포어 10개)
3. Phase 2에서 활용

핵심 코드:
```python
import aiohttp
import asyncio

class AsyncKISClient:
    def __init__(self, max_concurrent: int = 10):
        self.semaphore = asyncio.Semaphore(max_concurrent)

    async def get_prices_batch(self, codes: List[str]) -> Dict[str, Dict]:
        async with aiohttp.ClientSession() as session:
            tasks = [self._get_price(session, code) for code in codes]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            return {code: res for code, res in zip(codes, results)
                    if not isinstance(res, Exception)}

# 동기 코드에서 호출
def get_prices_sync(codes: List[str]) -> Dict:
    return asyncio.run(AsyncKISClient().get_prices_batch(codes))
```
```

---

## 🟢 P3: 고급 기능 (1개월)

### P3-1: LSTM 가격 예측
```
파일: core/learning/models/lstm_predictor.py (신규)
중요도: ★★☆☆☆
이유: 단기 가격 방향 예측으로 진입 타이밍 개선
예상 효과: 방향 예측 60%+ 정확도

작업 내용:
1. PyTorch LSTM 모델 구현
2. 60일 시퀀스 → 다음날 종가 예측
3. 학습/추론 파이프라인
4. 예측 기반 매매 신호 생성

의존성: torch, numpy, pandas
학습 데이터: 최소 3년 일봉 데이터
```

### P3-2: 강화학습 포지션 관리
```
파일: core/learning/rl/trading_env.py, ppo_agent.py (신규)
중요도: ★★☆☆☆
이유: 최적 매수/매도 타이밍 및 수량 자동 학습
예상 효과: 포지션 관리 최적화

작업 내용:
1. OpenAI Gym 호환 트레이딩 환경
2. 상태: 잔고, 포지션, 기술지표
3. 행동: 홀드, 매수(10/30/50%), 매도(10/30/50%), 전량청산
4. PPO 에이전트 학습

의존성: gymnasium, stable-baselines3
```

### P3-3: 선물 헤징 시스템
```
파일: core/hedging/futures_hedger.py (신규)
중요도: ★★☆☆☆
이유: 포트폴리오 하락 시 선물로 손실 보전
예상 효과: MDD 50% 감소

작업 내용:
1. KIS 선물 API 연동
2. 포트폴리오 베타 계산
3. 헤지 비율 및 계약 수 계산
4. 자동 헤지 오픈/클로즈
```

### P3-4: 해외주식 분산
```
파일: core/overseas/us_trader.py (신규)
중요도: ★☆☆☆☆
이유: 글로벌 분산으로 변동성 감소

작업 내용:
1. KIS 해외주식 API 연동
2. 미국 장 시간 스케줄링
3. 환율 자동 계산
4. ETF 기반 분산 포트폴리오
```

### P3-5: DB 마이그레이션
```
파일: core/database/models.py, repositories.py
중요도: ★★☆☆☆
이유: JSON 파일 → DB로 데이터 일관성/동시성 개선

작업 내용:
1. WatchlistStock, DailySelection, TradeHistory 모델
2. Repository 패턴 구현
3. 기존 JSON 데이터 마이그레이션
4. 트랜잭션 관리
```

---

## 실행 순서 요약

```
Week 1 (P0 + P1 일부)
├── Day 1-2: P0-1 API 재시도 + P0-2 부분 실패 허용
├── Day 3: P0-3 엔드포인트 인증
├── Day 4-5: P1-1 동적 손절/익절
└── Day 6-7: P1-2 호가 불균형

Week 2 (P1 완료)
├── Day 1-2: P1-3 투자자 수급
├── Day 3-4: P1-4 OBV 지표
└── Day 5-7: P1-5 시장 적응형 설정

Week 3-4 (P2)
├── P2-1 Pydantic 검증
├── P2-2 JSON 로깅
├── P2-3 헬스체크
└── P2-4 비동기 클라이언트

Month 2 (P3)
├── P3-1 LSTM 예측
├── P3-2 강화학습
├── P3-3 선물 헤징
├── P3-4 해외주식
└── P3-5 DB 마이그레이션
```

---

## 각 태스크 실행 방법

### 새 채팅에서 시작할 때 프롬프트 예시:

**P0-1 실행:**
```
hantu_quant 프로젝트에서 P0-1 태스크를 실행해줘.

파일: core/api/rest_client.py
작업: tenacity 라이브러리로 API 재시도 로직 구현
- 지수 백오프 (2초, 4초, 8초)
- 최대 3회 재시도
- Timeout, ConnectionError만 재시도
- 4xx 에러는 재시도 안함

requirements.txt에 tenacity 추가도 해줘.
```

**P1-1 실행:**
```
hantu_quant 프로젝트에서 P1-1 태스크를 실행해줘.

파일: core/trading/dynamic_stop_loss.py (신규 생성)
작업: ATR 기반 동적 손절/익절 시스템 구현
- ATR(14일) 계산
- 손절가 = 진입가 - ATR × 2.0
- 익절가 = 진입가 + ATR × 3.0
- 트레일링 스탑 기능

완료 후 core/trading/trading_engine.py에 통합해줘.
```

**P1-2 실행:**
```
hantu_quant 프로젝트에서 P1-2 태스크를 실행해줘.

파일: core/indicators/orderbook_analyzer.py (신규 생성)
작업: 호가 불균형 분석기 구현
- 매수/매도 잔량 비율 계산
- 신호: strong_buy, buy, neutral, sell, strong_sell
- WebSocketClient와 연동

core/api/websocket_client.py에서 호가 데이터 수신 시 분석기 호출하도록 수정해줘.
```

---

## 예상 결과

| 단계 완료 | 연수익률 | 샤프비율 | MDD | 시스템 안정성 |
|----------|----------|----------|-----|--------------|
| 현재 | 12% | 1.2 | -8% | 85% |
| P0 완료 | 12% | 1.2 | -8% | **95%** |
| P1 완료 | **18%** | **1.6** | **-5%** | 95% |
| P2 완료 | 18% | 1.6 | -5% | **99%** |
| P3 완료 | **25%** | **2.0** | **-4%** | 99% |

---

## 의존성 추가 (requirements.txt)

```
# P0
tenacity>=8.2.0

# P2
pydantic>=2.0.0
psutil>=5.9.0
aiohttp>=3.9.0

# P3 (선택)
torch>=2.0.0
gymnasium>=0.29.0
stable-baselines3>=2.0.0
```

---

*작성일: 2025-12-26*
*버전: 1.0*
