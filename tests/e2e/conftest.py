"""
E2E 테스트용 Pytest Fixtures

자동 매매 시스템의 E2E 테스트를 위한 통합 환경 설정
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import Dict, List, Generator, Any
from datetime import datetime, timedelta
import pytest
import pandas as pd

# 프로젝트 루트 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from core.trading.trading_engine import TradingEngine, TradingConfig, Position
from core.trading.trade_journal import TradeJournal
from core.api.kis_api import KISAPI
from core.config.api_config import APIConfig


# ===== 이벤트 루프 설정 =====

@pytest.fixture(scope="session")
def event_loop():
    """세션 범위 이벤트 루프 (async 테스트용)"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ===== 테스트 환경 설정 =====

@pytest.fixture(autouse=True)
def test_environment():
    """E2E 테스트 환경 설정 (자동 적용)"""
    # 테스트용 환경 변수 설정
    os.environ["TESTING"] = "true"
    os.environ["LOG_LEVEL"] = "DEBUG"
    os.environ["SERVER"] = "virtual"  # 가상 계좌 강제

    # 테스트 데이터 디렉토리 생성
    test_data_dir = project_root / "tests" / "e2e" / "test_data"
    test_data_dir.mkdir(parents=True, exist_ok=True)

    os.environ["TEST_DATA_DIR"] = str(test_data_dir)

    yield

    # 정리
    os.environ.pop("TESTING", None)


@pytest.fixture
def test_db_path(tmp_path) -> Path:
    """테스트용 임시 DB 경로"""
    db_path = tmp_path / "test_trading.db"
    os.environ["DB_PATH"] = str(db_path)
    yield db_path

    # 정리
    if db_path.exists():
        db_path.unlink()


# ===== 테스트용 TradingEngine =====

@pytest.fixture
def mock_trading_config() -> TradingConfig:
    """테스트용 TradingEngine 설정 (보수적)"""
    return TradingConfig(
        max_positions=3,  # 테스트용 제한
        position_size_method="fixed",
        fixed_position_size=500000,  # 50만원 고정
        stop_loss_pct=0.02,  # 2% 손절
        take_profit_pct=0.05,  # 5% 익절
        max_trades_per_day=5,  # 일일 5건 제한
        use_dynamic_stops=False,  # 고정 손절/익절
        use_trailing_stop=False,
        min_volume_ratio=1.0,
        max_price_change=0.20,
    )


@pytest.fixture
async def mock_trading_engine(mock_trading_config: TradingConfig) -> TradingEngine:
    """테스트용 TradingEngine 인스턴스 (모의 투자 모드)"""
    # 기존 싱글톤 초기화
    from core.trading.trading_engine import reset_trading_engine
    reset_trading_engine()

    # 새 인스턴스 생성
    engine = TradingEngine(mock_trading_config)

    # API 초기화 (가상 계좌)
    engine._initialize_api()

    yield engine

    # 정리: 매매 중지
    if engine.is_running:
        await engine.stop_trading("테스트 종료")


# ===== WebSocket Mock Fixture =====

@pytest.fixture
async def mock_websocket_server():
    """WebSocket 모킹 서버 (지연 주입)"""
    from tests.e2e.mocks.websocket_mock import MockWebSocketServer

    server = MockWebSocketServer(delay_ms=10)  # 10ms 지연
    await server.start()

    yield server

    await server.stop()


@pytest.fixture
async def mock_kis_websocket_client(mock_websocket_server):
    """테스트용 KIS WebSocket 클라이언트"""
    from tests.e2e.mocks.websocket_mock import MockKISWebSocketClient

    client = MockKISWebSocketClient(mock_websocket_server)
    await client.connect()

    yield client

    await client.close()


# ===== 테스트 데이터 Fixtures =====

@pytest.fixture
def sample_positions() -> List[Dict]:
    """테스트용 포지션 데이터"""
    return [
        {
            "stock_code": "005930",
            "stock_name": "삼성전자",
            "quantity": 10,
            "avg_price": 70000,
            "current_price": 72000,
            "entry_time": (datetime.now() - timedelta(hours=2)).isoformat(),
            "unrealized_pnl": 20000,
            "unrealized_return": 0.0286,
            "stop_loss": 68600,  # -2%
            "target_price": 73500,  # +5%
        },
        {
            "stock_code": "000660",
            "stock_name": "SK하이닉스",
            "quantity": 5,
            "avg_price": 120000,
            "current_price": 118000,
            "entry_time": (datetime.now() - timedelta(hours=1)).isoformat(),
            "unrealized_pnl": -10000,
            "unrealized_return": -0.0167,
            "stop_loss": 117600,  # -2%
            "target_price": 126000,  # +5%
        },
    ]


@pytest.fixture
def sample_daily_selection() -> List[Dict]:
    """테스트용 일일 선정 종목 데이터"""
    return [
        {
            "stock_code": "035720",
            "stock_name": "카카오",
            "total_score": 85.5,
            "technical_score": 82.3,
            "volume_score": 88.7,
            "entry_price": 50000,
            "target_price": 52500,
            "stop_loss": 49000,
            "signal": "buy",
            "confidence": 0.78,
            "current_price": 50200,
            "volume_ratio": 1.8,
            "change_rate": 0.02,
        },
        {
            "stock_code": "035420",
            "stock_name": "NAVER",
            "total_score": 80.2,
            "technical_score": 78.5,
            "volume_score": 82.0,
            "entry_price": 180000,
            "target_price": 189000,
            "stop_loss": 176400,
            "signal": "buy",
            "confidence": 0.72,
            "current_price": 181000,
            "volume_ratio": 1.5,
            "change_rate": 0.01,
        },
    ]


@pytest.fixture
def sample_price_stream() -> Generator[Dict, None, None]:
    """테스트용 가격 스트림 생성기"""
    base_prices = {
        "005930": 70000,  # 삼성전자
        "000660": 120000,  # SK하이닉스
        "035720": 50000,  # 카카오
        "035420": 180000,  # NAVER
    }

    import random

    while True:
        for stock_code, base_price in base_prices.items():
            # -1% ~ +1% 변동
            change_pct = random.uniform(-0.01, 0.01)
            current_price = int(base_price * (1 + change_pct))
            volume = random.randint(1000, 10000)

            yield {
                "stock_code": stock_code,
                "timestamp": datetime.now().strftime("%H%M%S"),
                "current_price": current_price,
                "change": "2" if change_pct > 0 else "5" if change_pct < 0 else "3",
                "change_price": int(base_price * abs(change_pct)),
                "change_rate": change_pct * 100,
                "volume": volume,
                "accumulated_volume": volume * 100,
                "open_price": base_price,
                "high_price": int(base_price * 1.01),
                "low_price": int(base_price * 0.99),
            }


@pytest.fixture
def sample_ohlcv_data() -> pd.DataFrame:
    """테스트용 OHLCV 일봉 데이터 (60일)"""
    dates = pd.date_range(end=datetime.now(), periods=60, freq="D")

    # 간단한 랜덤워크 가격 생성
    import numpy as np
    np.random.seed(42)

    base_price = 50000
    returns = np.random.normal(0.001, 0.02, 60)  # 일일 수익률 평균 0.1%, 표준편차 2%
    prices = base_price * (1 + returns).cumprod()

    # OHLC 생성
    highs = prices * (1 + np.random.uniform(0, 0.02, 60))
    lows = prices * (1 - np.random.uniform(0, 0.02, 60))
    opens = prices * (1 + np.random.uniform(-0.01, 0.01, 60))
    closes = prices
    volumes = np.random.randint(100000, 1000000, 60)

    df = pd.DataFrame(
        {
            "date": dates,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
        }
    )

    return df


# ===== Trade Journal Fixture =====

@pytest.fixture
def test_trade_journal(tmp_path) -> TradeJournal:
    """테스트용 매매일지"""
    journal_dir = tmp_path / "trade_journal"
    journal_dir.mkdir(parents=True, exist_ok=True)

    journal = TradeJournal(log_dir=str(journal_dir))

    yield journal


# ===== 시나리오 헬퍼 Fixtures =====

@pytest.fixture
def create_mock_position():
    """Position 객체 생성 헬퍼"""

    def _create(
        stock_code: str = "005930",
        stock_name: str = "삼성전자",
        quantity: int = 10,
        avg_price: float = 70000,
        current_price: float = 72000,
    ) -> Position:
        return Position(
            stock_code=stock_code,
            stock_name=stock_name,
            quantity=quantity,
            avg_price=avg_price,
            current_price=current_price,
            entry_time=datetime.now().isoformat(),
            unrealized_pnl=(current_price - avg_price) * quantity,
            unrealized_return=(current_price - avg_price) / avg_price,
            stop_loss=avg_price * 0.98,
            target_price=avg_price * 1.05,
        )

    return _create


@pytest.fixture
def mock_kis_api_responses() -> Dict[str, Any]:
    """KIS API 모킹 응답 데이터"""
    return {
        "balance": {
            "total_eval_amount": 100000000,  # 1억
            "deposit": 50000000,  # 5천만원 현금
            "total_profit_loss": 0,
            "positions": {},
        },
        "current_price": {
            "stock_code": "005930",
            "current_price": 70000,
            "change_rate": 1.5,
            "volume": 10000000,
        },
        "order_success": {
            "success": True,
            "order_id": "TEST_ORDER_001",
            "message": "주문 접수 완료",
        },
        "order_failure": {
            "success": False,
            "order_id": "",
            "message": "주문 실패: 잔고 부족",
        },
    }


# ===== 테스트 격리 Fixture =====

@pytest.fixture(autouse=True)
def cleanup_after_test():
    """각 테스트 후 정리 (자동 적용)"""
    yield

    # TradingEngine 싱글톤 초기화
    from core.trading.trading_engine import reset_trading_engine
    reset_trading_engine()

    # 이벤트 루프 정리
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.stop()
    except RuntimeError:
        pass


# ===== Marker 정의 =====

def pytest_configure(config):
    """E2E 테스트 마커 등록"""
    config.addinivalue_line(
        "markers", "e2e: E2E 통합 테스트 (느림, 외부 의존성 필요)"
    )
    config.addinivalue_line(
        "markers", "websocket: WebSocket 실시간 테스트"
    )
    config.addinivalue_line(
        "markers", "slow: 느린 테스트 (30초 이상)"
    )
