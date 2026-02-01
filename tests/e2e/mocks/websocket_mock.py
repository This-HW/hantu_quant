"""
WebSocket Mock 서버 및 클라이언트

E2E 테스트를 위한 KIS WebSocket API 모킹
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime
from dataclasses import dataclass
import random

logger = logging.getLogger(__name__)


@dataclass
class MockWebSocketMessage:
    """모킹된 WebSocket 메시지"""

    tr_id: str
    stock_code: str
    data: Dict[str, Any]
    timestamp: str


class MockWebSocketServer:
    """테스트용 WebSocket 서버 (KIS API 시뮬레이션)"""

    def __init__(self, delay_ms: int = 0):
        """초기화

        Args:
            delay_ms: 응답 지연 시간 (밀리초)
        """
        self.delay_ms = delay_ms
        self.is_running = False
        self.subscribers: Dict[str, List[Callable]] = {}  # {종목코드: [callback 리스트]}
        self.message_queue: asyncio.Queue = asyncio.Queue()

        # 시뮬레이션 상태
        self.current_prices: Dict[str, float] = {}  # {종목코드: 현재가}
        self.base_prices: Dict[str, float] = {
            "005930": 70000,  # 삼성전자
            "000660": 120000,  # SK하이닉스
            "035720": 50000,  # 카카오
            "035420": 180000,  # NAVER
        }

        # 연결 상태
        self.connected_clients = 0
        self.disconnect_simulation = False

        logger.info(f"MockWebSocketServer 초기화 (지연: {delay_ms}ms)")

    async def start(self):
        """서버 시작"""
        self.is_running = True
        self.current_prices = self.base_prices.copy()
        logger.info("MockWebSocketServer 시작")

        # 백그라운드 가격 업데이트 시작
        asyncio.create_task(self._price_update_loop())

    async def stop(self):
        """서버 중지"""
        self.is_running = False
        logger.info("MockWebSocketServer 중지")

    async def _price_update_loop(self):
        """백그라운드 가격 업데이트 (1초마다)"""
        while self.is_running:
            try:
                # 각 종목 가격 랜덤 변동 (-1% ~ +1%)
                for stock_code in list(self.current_prices.keys()):
                    base_price = self.base_prices.get(stock_code, 50000)
                    change_pct = random.uniform(-0.01, 0.01)
                    new_price = int(base_price * (1 + change_pct))
                    self.current_prices[stock_code] = new_price

                    # 구독자에게 가격 업데이트 전송
                    if stock_code in self.subscribers:
                        await self.send_price_update(
                            stock_code=stock_code,
                            price=new_price,
                            volume=random.randint(1000, 10000),
                        )

                await asyncio.sleep(1.0)  # 1초마다 업데이트

            except Exception as e:
                logger.error(f"가격 업데이트 루프 오류: {e}", exc_info=True)

    async def send_price_update(
        self, stock_code: str, price: float, volume: int
    ):
        """실시간 체결가 업데이트 전송"""
        if self.disconnect_simulation:
            logger.warning("연결 끊김 시뮬레이션 중 - 메시지 전송 무시")
            return

        # 응답 지연 시뮬레이션
        if self.delay_ms > 0:
            await asyncio.sleep(self.delay_ms / 1000.0)

        # KIS 실시간 체결가 형식 (H0STCNT0)
        base_price = self.base_prices.get(stock_code, price)
        change_price = price - base_price
        change_pct = (change_price / base_price) * 100 if base_price > 0 else 0

        message_data = {
            "stock_code": stock_code,
            "timestamp": datetime.now().strftime("%H%M%S"),
            "current_price": int(price),
            "change": "2" if change_price > 0 else "5" if change_price < 0 else "3",
            "change_price": abs(int(change_price)),
            "change_rate": abs(change_pct),
            "volume": volume,
            "accumulated_volume": volume * 100,
            "open_price": base_price,
            "high_price": int(max(price, base_price * 1.01)),
            "low_price": int(min(price, base_price * 0.99)),
        }

        message = MockWebSocketMessage(
            tr_id="H0STCNT0",
            stock_code=stock_code,
            data=message_data,
            timestamp=datetime.now().isoformat(),
        )

        # 구독자에게 전송
        if stock_code in self.subscribers:
            for callback in self.subscribers[stock_code]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(message_data)
                    else:
                        callback(message_data)
                except Exception as e:
                    logger.error(f"콜백 실행 오류: {e}", exc_info=True)

    async def send_orderbook_update(
        self,
        stock_code: str,
        bid_prices: List[int],
        ask_prices: List[int],
    ):
        """실시간 호가 업데이트 전송"""
        if self.disconnect_simulation:
            return

        if self.delay_ms > 0:
            await asyncio.sleep(self.delay_ms / 1000.0)

        # KIS 실시간 호가 형식 (H0STASP0)
        message_data = {
            "stock_code": stock_code,
            "timestamp": datetime.now().strftime("%H%M%S"),
            "ask_prices": ask_prices[:10],  # 최대 10호가
            "bid_prices": bid_prices[:10],
            "ask_volumes": [random.randint(100, 1000) for _ in range(10)],
            "bid_volumes": [random.randint(100, 1000) for _ in range(10)],
            "total_ask_volume": sum([random.randint(100, 1000) for _ in range(10)]),
            "total_bid_volume": sum([random.randint(100, 1000) for _ in range(10)]),
        }

        message = MockWebSocketMessage(
            tr_id="H0STASP0",
            stock_code=stock_code,
            data=message_data,
            timestamp=datetime.now().isoformat(),
        )

        # 구독자에게 전송
        if stock_code in self.subscribers:
            for callback in self.subscribers[stock_code]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(message_data)
                    else:
                        callback(message_data)
                except Exception as e:
                    logger.error(f"콜백 실행 오류: {e}", exc_info=True)

    async def simulate_disconnect(self):
        """연결 끊김 시뮬레이션"""
        logger.warning("WebSocket 연결 끊김 시뮬레이션 시작")
        self.disconnect_simulation = True

    async def simulate_reconnect(self):
        """재연결 시뮬레이션"""
        logger.info("WebSocket 재연결 시뮬레이션")
        self.disconnect_simulation = False

    def set_response_delay(self, delay_ms: int):
        """응답 지연 시간 설정"""
        self.delay_ms = delay_ms
        logger.info(f"응답 지연 시간 변경: {delay_ms}ms")

    def add_subscriber(self, stock_code: str, callback: Callable):
        """구독자 추가"""
        if stock_code not in self.subscribers:
            self.subscribers[stock_code] = []

        self.subscribers[stock_code].append(callback)
        logger.debug(f"구독자 추가: {stock_code}")

    def remove_subscriber(self, stock_code: str, callback: Callable):
        """구독자 제거"""
        if stock_code in self.subscribers:
            try:
                self.subscribers[stock_code].remove(callback)
                logger.debug(f"구독자 제거: {stock_code}")
            except ValueError:
                pass


class MockKISWebSocketClient:
    """테스트용 KIS WebSocket 클라이언트

    실제 KISWebSocketClient와 동일한 인터페이스 제공
    """

    def __init__(self, mock_server: MockWebSocketServer):
        """초기화

        Args:
            mock_server: MockWebSocketServer 인스턴스
        """
        self.mock_server = mock_server
        self.approval_key = "MOCK_APPROVAL_KEY"
        self.subscribed_codes: Dict[str, List[str]] = {}  # {종목코드: [TR_ID 리스트]}
        self.callbacks: Dict[str, Callable] = {}  # {TR_ID: callback}
        self.websocket = None
        self.running = False

        logger.info("MockKISWebSocketClient 초기화")

    async def connect(self) -> bool:
        """WebSocket 연결 (모킹)"""
        try:
            if self.mock_server.disconnect_simulation:
                logger.error("연결 실패: 서버 연결 끊김 시뮬레이션 중")
                return False

            self.websocket = "MOCK_WEBSOCKET"  # 더미 연결
            self.running = True
            self.mock_server.connected_clients += 1
            logger.info("MockKISWebSocketClient 연결 성공")
            return True

        except Exception as e:
            logger.error(f"연결 실패: {e}", exc_info=True)
            return False

    async def heartbeat(self) -> bool:
        """Heartbeat (모킹)"""
        if self.mock_server.disconnect_simulation:
            return False
        return self.websocket is not None

    async def ensure_connection(self):
        """연결 확인 및 재연결"""
        ok = await self.heartbeat()
        if not ok:
            try:
                await self.close()
            except Exception:
                pass
            await self.connect()

    def add_callback(self, tr_id: str, callback: Callable):
        """콜백 함수 등록"""
        self.callbacks[tr_id] = callback
        logger.debug(f"콜백 등록: {tr_id}")

    async def subscribe(self, stock_code: str, tr_list: List[str]) -> bool:
        """종목 구독 (모킹)"""
        if not self.websocket:
            logger.error("WebSocket 미연결")
            return False

        try:
            for tr_id in tr_list:
                # Mock 서버에 구독자 등록
                if tr_id in self.callbacks:
                    callback = self.callbacks[tr_id]
                    self.mock_server.add_subscriber(stock_code, callback)

                if stock_code not in self.subscribed_codes:
                    self.subscribed_codes[stock_code] = []

                self.subscribed_codes[stock_code].append(tr_id)
                logger.info(f"구독 완료: {tr_id} - {stock_code}")

            return True

        except Exception as e:
            logger.error(f"구독 실패: {e}", exc_info=True)
            return False

    async def unsubscribe(self, stock_code: str):
        """종목 구독 해지 (모킹)"""
        if stock_code not in self.subscribed_codes:
            return

        try:
            for tr_id in self.subscribed_codes[stock_code]:
                # Mock 서버에서 구독자 제거
                if tr_id in self.callbacks:
                    callback = self.callbacks[tr_id]
                    self.mock_server.remove_subscriber(stock_code, callback)

                logger.info(f"구독 해지: {tr_id} - {stock_code}")

            del self.subscribed_codes[stock_code]

        except Exception as e:
            logger.error(f"구독 해지 실패: {e}", exc_info=True)

    async def start_streaming(self):
        """실시간 데이터 수신 시작 (모킹)"""
        if not self.websocket:
            logger.error("WebSocket 미연결")
            return

        logger.info("스트리밍 시작 (모킹)")
        # Mock 서버가 콜백을 직접 호출하므로 별도 루프 불필요

    async def close(self):
        """WebSocket 연결 종료"""
        self.running = False

        if self.websocket:
            # 모든 구독 해지
            for stock_code in list(self.subscribed_codes.keys()):
                await self.unsubscribe(stock_code)

            self.websocket = None
            self.mock_server.connected_clients -= 1
            logger.info("MockKISWebSocketClient 연결 종료")


# ===== 헬퍼 함수 =====

def create_mock_price_data(
    stock_code: str = "005930",
    base_price: float = 70000,
    change_pct: float = 0.01,
) -> Dict[str, Any]:
    """테스트용 가격 데이터 생성"""
    current_price = int(base_price * (1 + change_pct))
    change_price = current_price - base_price

    return {
        "stock_code": stock_code,
        "timestamp": datetime.now().strftime("%H%M%S"),
        "current_price": current_price,
        "change": "2" if change_price > 0 else "5" if change_price < 0 else "3",
        "change_price": abs(int(change_price)),
        "change_rate": abs(change_pct * 100),
        "volume": random.randint(1000, 10000),
        "accumulated_volume": random.randint(100000, 1000000),
        "open_price": int(base_price),
        "high_price": int(base_price * 1.02),
        "low_price": int(base_price * 0.98),
    }


def create_mock_orderbook_data(
    stock_code: str = "005930",
    base_price: float = 70000,
    spread_pct: float = 0.001,
) -> Dict[str, Any]:
    """테스트용 호가 데이터 생성"""
    spread = int(base_price * spread_pct)

    # 매도호가 (현재가 위)
    ask_prices = [int(base_price + spread * (i + 1)) for i in range(10)]

    # 매수호가 (현재가 아래)
    bid_prices = [int(base_price - spread * (i + 1)) for i in range(10)]

    return {
        "stock_code": stock_code,
        "timestamp": datetime.now().strftime("%H%M%S"),
        "ask_prices": ask_prices,
        "bid_prices": bid_prices,
        "ask_volumes": [random.randint(100, 1000) for _ in range(10)],
        "bid_volumes": [random.randint(100, 1000) for _ in range(10)],
        "total_ask_volume": sum([random.randint(100, 1000) for _ in range(10)]),
        "total_bid_volume": sum([random.randint(100, 1000) for _ in range(10)]),
    }
