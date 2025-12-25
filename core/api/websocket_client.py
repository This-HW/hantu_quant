"""
한국투자증권 WebSocket API 클라이언트

보안 강화 정책에 따라 REST API 토큰 대신
별도의 WebSocket 접속키(approval_key)를 사용
"""

import json
import logging
import asyncio
import websockets
from typing import Dict, Optional, Callable, List
from core.config.settings import (
    APP_KEY, APP_SECRET, ACCOUNT_NUMBER,
    SERVER, SOCKET_VIRTUAL_URL, SOCKET_PROD_URL
)
from core.config.api_config import APIConfig

logger = logging.getLogger(__name__)


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
            logger.error(f"WebSocket 연결 실패: {str(e)}")
            return False

    async def heartbeat(self) -> bool:
        """간단한 heartbeat (서버 스펙에 맞춰 향후 개선)"""
        try:
            if not self.websocket:
                return False
            # websockets 라이브러리 내부 ping 사용 가능
            await self.websocket.ping()
            return True
        except Exception:
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
            logger.error(f"구독 요청 실패: {e}")
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
            logger.error(f"구독 해지 실패: {e}")
            
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
                    logger.error(f"WebSocket 연결이 종료되었습니다. 코드: {e.code}, 사유: {e.reason}")
                    success = await self._reconnect()
                    if not success:
                        logger.error("재연결 실패로 스트리밍을 종료합니다.")
                        break
                except json.JSONDecodeError as e:
                    logger.error(f"JSON 디코딩 오류: {e}")
                    continue
                except Exception as e:
                    logger.error(f"스트리밍 중 예상치 못한 오류: {str(e)}")
                    await asyncio.sleep(1)  # 짧은 대기 후 계속
                    
        except Exception as e:
            logger.error(f"스트리밍 중 심각한 오류 발생: {str(e)}")
            self.running = False
            
    async def _handle_message(self, message: str):
        """수신된 메시지 처리"""
        try:
            data = json.loads(message)
            tr_id = data.get("header", {}).get("tr_id", "")
            
            if tr_id in self.callbacks:
                await self.callbacks[tr_id](data["body"])
            else:
                logger.warning(f"등록되지 않은 TR_ID: {tr_id}")
                
        except Exception as e:
            logger.error(f"메시지 처리 중 오류 발생: {e}")
            
    async def _reconnect(self):
        """WebSocket 재연결"""
        logger.info("WebSocket 재연결 시도...")
        
        max_retries = 5
        retry_count = 0
        
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
                logger.error(f"재연결 실패 ({retry_count}/{max_retries}): {str(e)}")
                await asyncio.sleep(min(5 * retry_count, 30))  # 지수 백오프, 최대 30초
        
        if retry_count >= max_retries:
            logger.error(f"최대 재시도 횟수({max_retries})를 초과했습니다. 재연결 중단.")
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