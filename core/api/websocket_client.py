"""
한국투자증권 WebSocket API 클라이언트

보안 강화 정책에 따라 REST API 토큰 대신
별도의 WebSocket 접속키(approval_key)를 사용
"""

import json
import asyncio
import websockets
from typing import Dict, Optional, Callable, List
from core.config.settings import (
    SERVER, SOCKET_VIRTUAL_URL, SOCKET_PROD_URL
)
from core.config.api_config import APIConfig
from core.utils.log_utils import get_logger

logger = get_logger(__name__)


class KISWebSocketClient:
    """한국투자증권 WebSocket API 클라이언트

    한투 보안 강화 정책에 따라 WebSocket 연결 시
    REST API access_token 대신 별도의 approval_key 사용
    """

    def __init__(self, approval_key: Optional[str] = None):
        """초기화

        Args:
            approval_key: WebSocket 접속키 (None이면 자동 발급)
        """
        self.config = APIConfig()

        # WebSocket 접속키 설정 (REST 토큰과 별도)
        if approval_key:
            self.approval_key = approval_key
        else:
            # APIConfig에서 접속키 발급/로드
            self.approval_key = self.config.get_ws_approval_key()

        self.ws_url = SOCKET_PROD_URL if SERVER == 'prod' else SOCKET_VIRTUAL_URL
        self.subscribed_codes: Dict[str, List[str]] = {}  # {종목코드: [TR_ID 리스트]}
        self.callbacks: Dict[str, Callable] = {}  # {TR_ID: callback 함수}
        self.websocket = None
        self.running = False

    @classmethod
    def from_access_token(cls, access_token: str) -> 'KISWebSocketClient':
        """기존 access_token 방식 호환용 팩토리 메서드 (deprecated)

        Args:
            access_token: REST API 토큰

        Returns:
            KISWebSocketClient 인스턴스

        Note:
            이 방식은 deprecated입니다. 새 코드에서는 approval_key 사용을 권장합니다.
        """
        logger.warning(
            "[KISWebSocketClient] access_token 방식은 deprecated입니다. "
            "approval_key 사용을 권장합니다."
        )
        instance = cls.__new__(cls)
        instance.approval_key = access_token  # 호환성을 위해 access_token 사용
        instance.config = APIConfig()
        instance.ws_url = SOCKET_PROD_URL if SERVER == 'prod' else SOCKET_VIRTUAL_URL
        instance.subscribed_codes = {}
        instance.callbacks = {}
        instance.websocket = None
        instance.running = False
        return instance
        
    def add_callback(self, tr_id: str, callback: Callable):
        """실시간 데이터 수신 시 호출할 콜백 함수 등록"""
        self.callbacks[tr_id] = callback
        
    async def connect(self):
        """WebSocket 연결"""
        try:
            logger.info(f"WebSocket 연결 시도: {self.ws_url}")
            self.websocket = await websockets.connect(self.ws_url, ping_interval=30)
            self.running = True
            logger.info("WebSocket 연결 성공")
            return True
        except Exception as e:
            logger.error(f"WebSocket 연결 실패: {str(e)}", exc_info=True)
            return False

    async def heartbeat(self) -> bool:
        """간단한 heartbeat (서버 스펙에 맞춰 향후 개선)"""
        try:
            if not self.websocket:
                return False
            # websockets 라이브러리 내부 ping 사용 가능
            await self.websocket.ping()
            return True
        except Exception as e:
            logger.warning(
                f"Heartbeat 실패: {e}",
                exc_info=True,
                extra={
                    "websocket_open": self.websocket is not None,
                    "running": self.running,
                },
            )
            return False

    async def ensure_connection(self):
        ok = await self.heartbeat()
        if not ok:
            try:
                await self.close()
            except Exception:
                pass
            await self.connect()
            
    async def subscribe(self, stock_code: str, tr_list: List[str]):
        """종목 실시간 데이터 구독"""
        if not self.websocket:
            logger.error("WebSocket이 연결되지 않았습니다.")
            return False

        # 접속키 확인
        if not self.approval_key:
            logger.error("WebSocket 접속키가 없습니다. 접속키 발급이 필요합니다.")
            self.approval_key = self.config.get_ws_approval_key()
            if not self.approval_key:
                return False

        try:
            for tr_id in tr_list:
                message = {
                    "header": {
                        "approval_key": self.approval_key,  # REST 토큰 대신 접속키 사용
                        "custtype": "P",
                        "tr_type": "1",
                        "content-type": "utf-8"
                    },
                    "body": {
                        "tr_id": tr_id,
                        "tr_key": stock_code
                    }
                }

                await self.websocket.send(json.dumps(message))
                logger.info(f"구독 요청 전송: {tr_id} - {stock_code}")

                if stock_code not in self.subscribed_codes:
                    self.subscribed_codes[stock_code] = []
                self.subscribed_codes[stock_code].append(tr_id)

                await asyncio.sleep(0.5)  # API 호출 제한 준수

            return True

        except Exception as e:
            logger.error(f"구독 요청 실패: {e}", exc_info=True)
            return False
            
    async def unsubscribe(self, stock_code: str):
        """종목 구독 해지"""
        if not self.websocket or stock_code not in self.subscribed_codes:
            return

        try:
            for tr_id in self.subscribed_codes[stock_code]:
                message = {
                    "header": {
                        "approval_key": self.approval_key,  # REST 토큰 대신 접속키 사용
                        "custtype": "P",
                        "tr_type": "2",  # 구독 해지
                        "content-type": "utf-8"
                    },
                    "body": {
                        "tr_id": tr_id,
                        "tr_key": stock_code
                    }
                }

                await self.websocket.send(json.dumps(message))
                logger.info(f"구독 해지 요청: {tr_id} - {stock_code}")

            del self.subscribed_codes[stock_code]

        except Exception as e:
            logger.error(f"구독 해지 실패: {e}", exc_info=True)
            
    async def start_streaming(self):
        """실시간 데이터 수신 시작"""
        if not self.websocket:
            logger.error("WebSocket이 연결되지 않았습니다.")
            return
            
        try:
            while self.running:
                try:
                    data = await self.websocket.recv()
                    await self._handle_message(data)
                except websockets.exceptions.ConnectionClosed as e:
                    logger.error(f"WebSocket 연결이 종료되었습니다. 코드: {e.code}, 사유: {e.reason}", exc_info=True)
                    success = await self._reconnect()
                    if not success:
                        logger.error("재연결 실패로 스트리밍을 종료합니다.")
                        break
                except json.JSONDecodeError as e:
                    logger.error(f"JSON 디코딩 오류: {e}", exc_info=True)
                    continue
                except Exception as e:
                    logger.error(f"스트리밍 중 예상치 못한 오류: {str(e)}", exc_info=True)
                    await asyncio.sleep(1)  # 짧은 대기 후 계속
                    
        except Exception as e:
            logger.error(f"스트리밍 중 심각한 오류 발생: {str(e)}", exc_info=True)
            self.running = False
            
    async def _handle_message(self, message: str):
        """수신된 메시지 처리

        Args:
            message: WebSocket으로부터 수신된 원본 메시지
        """
        try:
            # JSON 파싱
            data = json.loads(message)

            # 헤더 정보 추출
            header = data.get("header", {})
            body = data.get("body", {})
            tr_id = header.get("tr_id", "")

            # 메시지 타입 확인
            if not tr_id:
                logger.warning(f"TR_ID가 없는 메시지: {message[:100]}")
                return

            # KIS 실시간 데이터는 body가 파이프(|) 구분 문자열
            if isinstance(body, str) and "|" in body:
                normalized_data = self._normalize_kis_message(tr_id, body)
                if not normalized_data:
                    logger.warning(f"메시지 정규화 실패: {tr_id}")
                    return
            else:
                # 이미 dict 형태이거나 일반 메시지
                normalized_data = body

            # 등록된 콜백 호출
            if tr_id in self.callbacks:
                callback = self.callbacks[tr_id]
                if asyncio.iscoroutinefunction(callback):
                    await callback(normalized_data)
                else:
                    callback(normalized_data)
            else:
                logger.debug(f"등록되지 않은 TR_ID: {tr_id}")

        except json.JSONDecodeError as e:
            logger.error(f"JSON 디코딩 실패: {e}, 원본: {message[:100]}", exc_info=True)
        except Exception as e:
            logger.error(f"메시지 처리 중 오류 발생: {e}", exc_info=True)

    def _normalize_kis_message(self, tr_id: str, body: str) -> Optional[Dict]:
        """KIS WebSocket 메시지 정규화

        KIS WebSocket 실시간 데이터는 파이프(|) 구분자로 전달됩니다.
        이를 파싱하여 dict 형태로 변환합니다.

        Args:
            tr_id: 거래 ID (H0STCNT0=체결가, H0STASP0=호가)
            body: 파이프 구분 메시지 본문

        Returns:
            정규화된 딕셔너리 또는 None (실패 시)
        """
        try:
            fields = body.split("|")

            # TR_ID별 필드 매핑
            if tr_id == "H0STCNT0":
                # 실시간 체결가
                if len(fields) < 20:
                    logger.warning(f"체결가 메시지 필드 부족: {len(fields)}개")
                    return None

                return {
                    "stock_code": fields[0],        # 종목코드
                    "timestamp": fields[1],         # 체결시간 (HHMMSS)
                    "current_price": int(fields[2]) if fields[2] else 0,  # 현재가
                    "change": fields[3],            # 전일대비부호 (1:상한, 2:상승, 3:보합, 4:하한, 5:하락)
                    "change_price": int(fields[4]) if fields[4] else 0,   # 전일대비
                    "change_rate": float(fields[5]) if fields[5] else 0.0,  # 등락율
                    "volume": int(fields[9]) if fields[9] else 0,           # 체결량
                    "accumulated_volume": int(fields[12]) if fields[12] else 0,  # 누적 거래량
                    "open_price": int(fields[16]) if fields[16] else 0,    # 시가
                    "high_price": int(fields[17]) if fields[17] else 0,    # 고가
                    "low_price": int(fields[18]) if fields[18] else 0,     # 저가
                }

            elif tr_id == "H0STASP0":
                # 실시간 호가
                if len(fields) < 60:
                    logger.warning(f"호가 메시지 필드 부족: {len(fields)}개")
                    return None

                return {
                    "stock_code": fields[0],
                    "timestamp": fields[1],
                    "ask_prices": [int(fields[i]) if fields[i] else 0 for i in range(3, 13)],    # 매도호가 10개
                    "bid_prices": [int(fields[i]) if fields[i] else 0 for i in range(13, 23)],   # 매수호가 10개
                    "ask_volumes": [int(fields[i]) if fields[i] else 0 for i in range(23, 33)],  # 매도잔량 10개
                    "bid_volumes": [int(fields[i]) if fields[i] else 0 for i in range(33, 43)],  # 매수잔량 10개
                    "total_ask_volume": int(fields[43]) if fields[43] else 0,  # 총 매도잔량
                    "total_bid_volume": int(fields[44]) if fields[44] else 0,  # 총 매수잔량
                }

            else:
                # 알 수 없는 TR_ID
                logger.warning(f"알 수 없는 TR_ID: {tr_id}")
                return {"raw": body}

        except (IndexError, ValueError) as e:
            logger.error(f"메시지 파싱 오류 ({tr_id}): {e}, 본문: {body[:100]}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"메시지 정규화 중 예상치 못한 오류: {e}", exc_info=True)
            return None
            
    async def _reconnect(self):
        """WebSocket 재연결 (지수 백오프 적용)"""
        logger.info("WebSocket 재연결 시도...")

        max_retries = 5
        retry_count = 0
        # 지수 백오프: 1, 2, 4, 8, 16초
        retry_delays = [1, 2, 4, 8, 16]

        while not self.websocket and retry_count < max_retries:
            try:
                retry_count += 1
                logger.info(f"재연결 시도 {retry_count}/{max_retries}")

                if await self.connect():
                    # 기존 구독 정보 복구
                    for stock_code, tr_list in self.subscribed_codes.items():
                        await self.subscribe(stock_code, tr_list)

                    logger.info("WebSocket 재연결 성공")
                    return True

            except Exception as e:
                delay = retry_delays[min(retry_count - 1, len(retry_delays) - 1)]
                logger.error(
                    f"재연결 실패 ({retry_count}/{max_retries}): {e}",
                    exc_info=True,
                    extra={
                        "retry_count": retry_count,
                        "max_retries": max_retries,
                        "next_delay": delay if retry_count < max_retries else None,
                    },
                )
                if retry_count < max_retries:
                    logger.info(f"{delay}초 후 재시도")
                    await asyncio.sleep(delay)

        if retry_count >= max_retries:
            logger.error(
                f"최대 재시도 횟수({max_retries})를 초과했습니다. 재연결 중단.",
                exc_info=True,
                extra={
                    "total_retries": retry_count,
                    "total_wait_time": sum(retry_delays[:max_retries - 1]),
                },
            )
            self.running = False
            return False
            
    async def close(self):
        """WebSocket 연결 종료"""
        self.running = False
        if self.websocket:
            # 모든 구독 해지
            for stock_code in list(self.subscribed_codes.keys()):
                await self.unsubscribe(stock_code)
            await self.websocket.close()
            self.websocket = None 