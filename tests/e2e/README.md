# E2E 테스트 인프라

Phase 3 자동 매매 시스템의 End-to-End 통합 테스트 환경

---

## 개요

이 디렉토리는 실제 운영 환경과 유사한 조건에서 자동 매매 시스템 전체를 테스트하기 위한 인프라를 제공합니다.

### 주요 기능

1. **WebSocket Mock**: KIS WebSocket API 시뮬레이션
2. **TradingEngine Mock**: 가상 계좌 기반 매매 엔진 테스트
3. **데이터 스트림 생성**: 실시간 가격/호가 데이터 생성
4. **시나리오 테스트**: 매수/매도/손절/익절 시나리오 검증

---

## 디렉토리 구조

```
tests/e2e/
├── conftest.py                    # E2E 테스트 Fixtures
├── mocks/                         # Mock 모듈
│   ├── __init__.py
│   └── websocket_mock.py         # WebSocket Mock 서버/클라이언트
├── test_websocket_mock_example.py # WebSocket Mock 사용 예시
└── README.md                      # 이 파일
```

---

## 사용법

### 1. 기본 E2E 테스트 실행

```bash
# 모든 E2E 테스트 실행
pytest tests/e2e/ -v

# 특정 마커만 실행
pytest tests/e2e/ -m "e2e and not slow" -v

# WebSocket 테스트만 실행
pytest tests/e2e/ -m websocket -v
```

### 2. Fixtures 사용 예시

#### 2.1 WebSocket Mock 사용

```python
import pytest

@pytest.mark.asyncio
@pytest.mark.e2e
async def test_realtime_price_update(mock_kis_websocket_client):
    # Given: WebSocket 클라이언트 연결
    assert mock_kis_websocket_client.websocket is not None

    # When: 가격 업데이트 구독
    received_data = []

    async def callback(data):
        received_data.append(data)

    mock_kis_websocket_client.add_callback("H0STCNT0", callback)
    await mock_kis_websocket_client.subscribe("005930", ["H0STCNT0"])

    # Then: 실시간 가격 수신
    await asyncio.sleep(2)  # 백그라운드 업데이트 대기
    assert len(received_data) > 0
```

#### 2.2 TradingEngine Mock 사용

```python
@pytest.mark.asyncio
@pytest.mark.e2e
async def test_auto_trading_buy_sell(mock_trading_engine, sample_daily_selection):
    # Given: 일일 선정 종목 로드 (모킹)
    mock_trading_engine._load_daily_selection = lambda: sample_daily_selection

    # When: 자동 매매 시작
    await mock_trading_engine.start_trading()

    # Then: 포지션 생성 확인
    await asyncio.sleep(5)
    assert len(mock_trading_engine.positions) > 0
```

#### 2.3 샘플 데이터 사용

```python
@pytest.mark.e2e
def test_position_analysis(sample_positions, sample_ohlcv_data):
    # Given: 샘플 포지션과 일봉 데이터
    position = sample_positions[0]
    df = sample_ohlcv_data

    # When: 분석 수행
    from core.trading.dynamic_stop_loss import DynamicStopLossCalculator

    calculator = DynamicStopLossCalculator(atr_period=14)
    result = calculator.get_stops(position["avg_price"], df)

    # Then: 손절/익절가 계산됨
    assert result.stop_loss > 0
    assert result.take_profit > 0
```

---

## 주요 Fixtures

### WebSocket 관련

| Fixture                     | 설명                              |
| --------------------------- | --------------------------------- |
| `mock_websocket_server`     | WebSocket 모킹 서버               |
| `mock_kis_websocket_client` | 테스트용 KIS WebSocket 클라이언트 |

### TradingEngine 관련

| Fixture               | 설명                               |
| --------------------- | ---------------------------------- |
| `mock_trading_config` | 테스트용 TradingConfig (보수적)    |
| `mock_trading_engine` | 테스트용 TradingEngine (모의 투자) |

### 데이터 관련

| Fixture                  | 설명                              |
| ------------------------ | --------------------------------- |
| `sample_positions`       | 테스트용 포지션 데이터            |
| `sample_daily_selection` | 테스트용 일일 선정 종목 데이터    |
| `sample_price_stream`    | 실시간 가격 스트림 생성기         |
| `sample_ohlcv_data`      | 테스트용 OHLCV 일봉 데이터 (60일) |

### 헬퍼 관련

| Fixture                  | 설명                     |
| ------------------------ | ------------------------ |
| `create_mock_position`   | Position 객체 생성 헬퍼  |
| `mock_kis_api_responses` | KIS API 모킹 응답 데이터 |
| `test_trade_journal`     | 테스트용 매매일지        |

---

## Mock 모듈 상세

### MockWebSocketServer

KIS WebSocket API를 시뮬레이션하는 Mock 서버

**기능:**

- 실시간 가격 업데이트 자동 생성 (1초마다)
- 호가 데이터 전송
- 응답 지연 시뮬레이션
- 연결 끊김/재연결 시뮬레이션

**사용 예시:**

```python
server = MockWebSocketServer(delay_ms=100)
await server.start()

# 구독자 등록
server.add_subscriber("005930", my_callback)

# 가격 업데이트 전송
await server.send_price_update("005930", price=70000, volume=1000)

# 연결 끊김 시뮬레이션
await server.simulate_disconnect()
await server.simulate_reconnect()

await server.stop()
```

### MockKISWebSocketClient

실제 `KISWebSocketClient`와 동일한 인터페이스를 제공하는 Mock 클라이언트

**기능:**

- 종목 구독/해지
- 실시간 데이터 수신
- Heartbeat
- 재연결

**사용 예시:**

```python
client = MockKISWebSocketClient(mock_server)
await client.connect()

# 콜백 등록
client.add_callback("H0STCNT0", price_callback)

# 종목 구독
await client.subscribe("005930", ["H0STCNT0"])

# 실시간 데이터 수신 (백그라운드)
# mock_server가 자동으로 콜백 호출

await client.close()
```

---

## 테스트 시나리오 예시

### 시나리오 1: 매수 → 익절

```python
@pytest.mark.asyncio
@pytest.mark.e2e
async def test_buy_then_take_profit(mock_trading_engine):
    # 1. 매수
    stock_data = {
        "stock_code": "005930",
        "stock_name": "삼성전자",
        "current_price": 70000,
        "volume_ratio": 2.0,
        "change_rate": 0.03,
    }

    await mock_trading_engine._execute_buy_order(stock_data)
    assert "005930" in mock_trading_engine.positions

    # 2. 가격 상승 (익절가 도달)
    position = mock_trading_engine.positions["005930"]
    position.current_price = position.target_price + 100
    position.unrealized_return = 0.06  # 6% 수익

    # 3. 매도 신호 확인
    should_sell, reason = mock_trading_engine._should_sell(position)
    assert should_sell
    assert reason == "take_profit"

    # 4. 매도 실행
    await mock_trading_engine._execute_sell_order(position, reason)
    assert "005930" not in mock_trading_engine.positions
```

### 시나리오 2: 매수 → 손절

```python
@pytest.mark.asyncio
@pytest.mark.e2e
async def test_buy_then_stop_loss(mock_trading_engine):
    # 1. 매수
    stock_data = {
        "stock_code": "000660",
        "stock_name": "SK하이닉스",
        "current_price": 120000,
        "volume_ratio": 1.5,
        "change_rate": 0.01,
    }

    await mock_trading_engine._execute_buy_order(stock_data)

    # 2. 가격 하락 (손절가 도달)
    position = mock_trading_engine.positions["000660"]
    position.current_price = position.stop_loss - 100
    position.unrealized_return = -0.025  # -2.5% 손실

    # 3. 매도 신호 확인
    should_sell, reason = mock_trading_engine._should_sell(position)
    assert should_sell
    assert reason == "stop_loss"

    # 4. 매도 실행
    await mock_trading_engine._execute_sell_order(position, reason)
    assert "000660" not in mock_trading_engine.positions
```

---

## 테스트 마커

E2E 테스트는 다음 마커를 사용합니다:

| 마커                     | 설명                                |
| ------------------------ | ----------------------------------- |
| `@pytest.mark.e2e`       | E2E 통합 테스트 (느림, 외부 의존성) |
| `@pytest.mark.websocket` | WebSocket 실시간 테스트             |
| `@pytest.mark.slow`      | 느린 테스트 (30초 이상)             |

**마커 사용 예시:**

```python
@pytest.mark.e2e
@pytest.mark.websocket
@pytest.mark.slow
async def test_long_running_websocket():
    # 30초 이상 실행되는 WebSocket 테스트
    ...
```

---

## 주의사항

### 1. 테스트 격리

각 테스트는 독립적으로 실행되어야 합니다.

- `cleanup_after_test` fixture가 자동으로 테스트 후 정리
- TradingEngine 싱글톤 초기화
- 이벤트 루프 정리

### 2. 비동기 테스트

WebSocket 테스트는 반드시 `@pytest.mark.asyncio` 사용:

```python
@pytest.mark.asyncio
async def test_websocket():
    ...
```

### 3. 가상 계좌 강제

E2E 테스트는 자동으로 가상 계좌 모드로 실행됩니다:

```python
os.environ["SERVER"] = "virtual"
```

### 4. 외부 의존성

E2E 테스트는 외부 서비스를 모킹하므로 인터넷 연결 불필요:

- KIS API → Mock
- WebSocket → Mock
- DB → In-memory SQLite

---

## 확장 가이드

### 새 Mock 추가

1. `tests/e2e/mocks/` 디렉토리에 모듈 추가
2. `tests/e2e/conftest.py`에 fixture 추가
3. `tests/e2e/mocks/__init__.py`에 export 추가

**예시:**

```python
# tests/e2e/mocks/rest_api_mock.py
class MockKISRestAPI:
    def get_balance(self):
        return {"total_eval_amount": 100000000}

    def place_order(self, **kwargs):
        return {"success": True, "order_id": "TEST_001"}

# tests/e2e/conftest.py
@pytest.fixture
def mock_kis_rest_api():
    return MockKISRestAPI()
```

### 새 시나리오 추가

1. `tests/e2e/scenarios/` 디렉토리 생성 (선택)
2. 시나리오별 테스트 파일 작성
3. fixture 조합으로 복잡한 시나리오 구성

---

## 참고 문서

- [TradingEngine 구현](../../core/trading/trading_engine.py)
- [KISWebSocketClient 구현](../../core/api/websocket_client.py)
- [Phase 3 설계](../../docs/design/phase3/)
- [테스트 가이드](../README.md)
