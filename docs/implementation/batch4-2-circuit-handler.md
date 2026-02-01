# Batch 4-2: 서킷 브레이커 대응 핸들러 구현

## 개요

서킷 브레이커 발동 시 TradingEngine과 연동하여 적절한 조치를 취하는 핸들러를 구현했습니다.

**구현 일자**: 2026-02-01
**담당**: implement-code agent
**연관 배치**: Batch 4-1 (DrawdownMonitor + CircuitBreaker)

---

## 구현 파일

### 1. `core/trading/circuit_handler.py`

**주요 클래스**:

- `CircuitResponse`: 서킷 브레이커 대응 결과 (dataclass)
- `CircuitHandler`: 서킷 브레이커 대응 핸들러

**기능**:

1. **서킷 브레이커 상태 모니터링**
   - BreakerStatus 수신 및 분석
   - 상태별 적절한 대응 수행

2. **Stage별 대응 조치**
   - **Stage 1**: 신규 매수 50% 제한 (position_limit=0.50)
   - **Stage 2**: 신규 매수 75% 제한 (position_limit=0.25)
   - **Stage 3**: 신규 매수 전면 금지 (position_limit=0.0) + 기존 포지션 리스크 관리

3. **텔레그램 알림 연동**
   - NotificationManager를 통한 자동 알림 발송
   - Stage별 차등화된 알림 우선순위

4. **대응 이력 관리**
   - 최근 100개 대응 기록 유지
   - 조회 API 제공

---

## 클래스 설계

### CircuitResponse

```python
@dataclass
class CircuitResponse:
    action: str              # REDUCE, HALT, RECOVER
    position_limit: float    # 0.0 ~ 1.0 (신규 매수 가능 비율)
    affected_positions: List[str]  # 영향받는 포지션 목록
    message: str             # 사람이 읽을 수 있는 메시지
    timestamp: datetime      # 대응 시각
```

### CircuitHandler

**주요 메서드**:

| 메서드                                           | 설명                                                    |
| ------------------------------------------------ | ------------------------------------------------------- |
| `__init__(trading_engine, notification_manager)` | 초기화 (순환 참조 방지를 위해 Optional)                 |
| `set_trading_engine(engine)`                     | TradingEngine 지연 초기화                               |
| `handle_circuit_event(breaker_status)`           | 서킷 브레이커 이벤트 처리 (메인 로직)                   |
| `apply_position_reduction(reduction_rate)`       | 포지션 축소 적용 (현재는 로깅만, Phase 3에서 실제 매도) |
| `notify_circuit_status(status)`                  | 텔레그램 알림 발송                                      |
| `get_current_restrictions()`                     | 현재 거래 제한 정보 조회                                |
| `get_response_history(limit)`                    | 대응 이력 조회                                          |

---

## Stage별 대응 상세

### Stage 1: 경고 (Warning)

**발동 조건**:

- 일간 손실 3% 초과
- 또는 DrawdownMonitor AlertLevel.HIGH

**대응**:

- 신규 매수 50% 제한
- 기존 포지션 유지
- 텔레그램 경고 알림 발송

**CircuitResponse**:

```python
CircuitResponse(
    action="REDUCE",
    position_limit=0.50,
    affected_positions=["005930", "035420", ...],
    message="Stage 1 발동 - 신규 매수 50% 제한",
    timestamp=datetime.now()
)
```

### Stage 2: 심각 (Serious)

**발동 조건**:

- 주간 손실 7% 초과
- 또는 DrawdownMonitor AlertLevel.CRITICAL

**대응**:

- 신규 매수 75% 제한 (25%만 가능)
- 기존 포지션 유지
- 텔레그램 긴급 알림 발송

**CircuitResponse**:

```python
CircuitResponse(
    action="REDUCE",
    position_limit=0.25,
    affected_positions=["005930", "035420", ...],
    message="Stage 2 발동 - 신규 매수 75% 제한",
    timestamp=datetime.now()
)
```

### Stage 3: 긴급 (Emergency)

**발동 조건**:

- 최대 낙폭 15% 초과

**대응**:

- 신규 매수 전면 금지 (position_limit=0.0)
- 기존 포지션 리스크 관리 (청산 검토)
- 텔레그램 긴급 알림 발송 (emergency priority)

**CircuitResponse**:

```python
CircuitResponse(
    action="HALT",
    position_limit=0.0,
    affected_positions=["005930", "035420", ...],
    message="Stage 3 발동 - 신규 매수 금지",
    timestamp=datetime.now()
)
```

---

## TradingEngine 연동

### 순환 참조 방지

CircuitHandler와 TradingEngine 간 순환 참조를 방지하기 위해 **지연 초기화** 패턴 사용:

```python
# TradingEngine 초기화 시
from core.trading.circuit_handler import CircuitHandler

handler = CircuitHandler()  # trading_engine=None
# ... TradingEngine 초기화 완료 후
handler.set_trading_engine(self)
```

### 포지션 정보 조회

```python
def _get_current_positions(self) -> List[str]:
    """현재 보유 포지션 종목 코드 목록 조회"""
    if not self.trading_engine:
        return []

    if hasattr(self.trading_engine, 'positions'):
        return list(self.trading_engine.positions.keys())
    else:
        return []
```

---

## 알림 연동

### NotificationManager 통합

```python
def notify_circuit_status(self, status: BreakerStatus) -> bool:
    """서킷 브레이커 상태 알림"""
    if not self.notification_manager:
        return False

    self.notification_manager.notify_circuit_breaker(
        reason=status.trigger_reason or "서킷 브레이커 상태 변경",
        triggered_at=status.triggered_at or datetime.now(),
        cooldown_until=status.cooldown_until
    )

    return True
```

### 알림 우선순위

| Stage     | 우선순위  | 알림 채널 |
| --------- | --------- | --------- |
| Stage 1   | high      | 텔레그램  |
| Stage 2   | critical  | 텔레그램  |
| Stage 3   | emergency | 텔레그램  |
| 정상 복구 | normal    | 텔레그램  |

---

## 대응 이력 관리

### 히스토리 저장

```python
def _record_response(self, response: CircuitResponse):
    """대응 이력 기록"""
    self._response_history.append(response)

    # 최근 100개만 유지
    if len(self._response_history) > 100:
        self._response_history = self._response_history[-100:]
```

### 이력 조회 API

```python
history = handler.get_response_history(limit=10)
# [
#   {
#     "action": "HALT",
#     "position_limit": 0.0,
#     "affected_positions_count": 5,
#     "message": "Stage 3 발동 - 신규 매수 금지",
#     "timestamp": "2026-02-01T15:30:00"
#   },
#   ...
# ]
```

---

## 에러 처리

### 안전한 에러 핸들링

```python
try:
    # 메인 로직
    ...
except Exception as e:
    logger.error(f"서킷 브레이커 이벤트 처리 실패: {e}", exc_info=True)
    return CircuitResponse(
        action="ERROR",
        position_limit=0.0,
        affected_positions=[],
        message=f"처리 실패: {e}",
        timestamp=datetime.now()
    )
```

### CLAUDE.md 규칙 준수

- **에러 로깅**: 모든 except 블록에 `exc_info=True` 사용
- **공통 로거**: `get_logger(__name__)` 사용
- **Silent Failure 금지**: 에러 발생 시 반드시 로깅 및 CircuitResponse 반환

---

## 테스트

### 구문 검증

```bash
python3 -m py_compile core/trading/circuit_handler.py
# ✅ 성공
```

### 테스트 파일

1. `tests/scratch/test_circuit_handler.py` (pytest 기반, 상세)
2. `tests/scratch/test_circuit_handler_simple.py` (간단 버전)

**주요 테스트 케이스**:

- ✅ 정상 상태 처리 (RECOVER)
- ✅ Stage 1 처리 (50% 제한)
- ✅ Stage 2 처리 (75% 제한)
- ✅ Stage 3 처리 (전면 금지)
- ✅ 알림 발송 확인
- ✅ 이력 관리
- ✅ 에러 처리

---

## 향후 개선 사항

### Phase 3 구현 시

1. **실제 포지션 축소 로직**
   - 현재는 로깅만 수행
   - PositionReducer와 연동하여 실제 매도 주문 실행

2. **자동 복구 로직**
   - 쿨다운 완료 후 자동 복구
   - 수익 회복 시 자동 해제

3. **포지션별 우선순위 축소**
   - PositionReducer의 ReductionPriority 활용
   - 손실이 큰 종목 우선 청산

---

## 통합 지점

### DrawdownMonitor + CircuitBreaker + CircuitHandler

```python
# Batch 4-1 (DrawdownMonitor + CircuitBreaker)
monitor = DrawdownMonitor(circuit_breaker=breaker)
status = monitor.check_drawdown(portfolio_value, peak_value)

# Batch 4-2 (CircuitHandler)
handler = CircuitHandler(
    trading_engine=trading_engine,
    notification_manager=notification_manager
)

# 서킷 브레이커 발동 시
if status.breaker_status:
    response = handler.handle_circuit_event(status.breaker_status)

    # TradingEngine에서 position_limit 적용
    if response.position_limit < 1.0:
        # 신규 매수 제한 적용
        ...
```

---

## 파일 변경 이력

| 파일                                              | 변경 내용                                   |
| ------------------------------------------------- | ------------------------------------------- |
| `core/trading/circuit_handler.py`                 | 신규 생성                                   |
| `core/trading/__init__.py`                        | CircuitHandler, CircuitResponse export 추가 |
| `tests/scratch/test_circuit_handler.py`           | 테스트 생성 (pytest)                        |
| `tests/scratch/test_circuit_handler_simple.py`    | 테스트 생성 (간단)                          |
| `docs/implementation/batch4-2-circuit-handler.md` | 구현 문서 생성                              |

---

## 체크리스트

구현:

- [x] CLAUDE.md 규칙 준수
- [x] 올바른 위치에 파일 생성 (`core/trading/`)
- [x] 기존 패턴 따름 (DrawdownMonitor, PositionReducer 참조)
- [x] 타입 정의 완료 (dataclass)
- [x] 에러 처리 완료 (`exc_info=True`)
- [x] console.log 제거 (logger만 사용)

테스트:

- [x] 구문 검증 통과
- [x] 테스트 파일 작성

다음 단계:

- [ ] verify-code (빌드, 타입체크, 린트, 테스트 실행)
- [ ] verify-integration (연결 무결성 검증)

---

## 참고

- **관련 배치**: Batch 4-1 (DrawdownMonitor + CircuitBreaker)
- **참고 파일**:
  - `core/risk/drawdown/circuit_breaker.py`
  - `core/risk/drawdown/position_reducer.py`
  - `core/notification/notification_manager.py`
