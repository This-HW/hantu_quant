import logging
from typing import Dict, List, Optional, Callable
from .rest_client import KISRestClient
from .websocket_client import KISWebSocketClient

logger = logging.getLogger(__name__)

class KISAPI(KISRestClient):
    """한국투자증권 API 통합 클라이언트"""
    
    def __init__(self):
        """초기화"""
        super().__init__()  # 부모 클래스 초기화 (토큰 발급 포함)
        
        # WebSocket 클라이언트 초기화 (토큰 정보 전달)
        if self.token_info and self.token_info.get('access_token'):
            self.ws_client = KISWebSocketClient(self.token_info['access_token'])
        else:
            logger.error("[__init__] WebSocket 클라이언트 초기화 실패: 토큰 정보가 없습니다")
            raise Exception("WebSocket 클라이언트 초기화 실패")
        
    # REST API 메서드들
    def place_order(self, stock_code: str, order_type: int, quantity: int,
                   price: int = 0, order_division: str = "00") -> dict:
        """주문 실행"""
        return super().place_order(stock_code, order_type, quantity, price, order_division)
        
    def get_balance(self) -> dict:
        """계좌 잔고 조회"""
        return super().get_balance()
        
    def market_buy(self, stock_code: str, quantity: int) -> Optional[Dict]:
        """시장가 매수"""
        return self.place_order(stock_code, 2, quantity, 0, "01")
        
    def market_sell(self, stock_code: str, quantity: int) -> Optional[Dict]:
        """시장가 매도"""
        return self.place_order(stock_code, 1, quantity, 0, "01")
        
    def limit_buy(self, stock_code: str, quantity: int, price: int) -> Optional[Dict]:
        """지정가 매수"""
        return self.place_order(stock_code, 2, quantity, price, "00")
        
    def limit_sell(self, stock_code: str, quantity: int, price: int) -> Optional[Dict]:
        """지정가 매도"""
        return self.place_order(stock_code, 1, quantity, price, "00")
        
    # WebSocket API 메서드들
    async def connect_websocket(self) -> bool:
        """WebSocket 연결"""
        return await self.ws_client.connect()
        
    def add_callback(self, tr_id: str, callback: Callable):
        """실시간 데이터 콜백 함수 등록"""
        self.ws_client.add_callback(tr_id, callback)
        
    async def subscribe_stock(self, stock_code: str, tr_list: List[str]) -> bool:
        """종목 실시간 데이터 구독"""
        return await self.ws_client.subscribe(stock_code, tr_list)
        
    async def unsubscribe_stock(self, stock_code: str):
        """종목 구독 해지"""
        await self.ws_client.unsubscribe(stock_code)
        
    async def start_real_time(self, stock_codes: List[str]):
        """실시간 데이터 수신 시작"""
        if not await self.connect_websocket():
            return
            
        # 기본 TR 목록 설정
        tr_list = [
            "H0STCNT0",  # 체결 통보
            "H0STASP0",  # 호가
            "H0STCNT1"   # 체결
        ]
        
        # 종목별 구독 신청
        for code in stock_codes:
            await self.subscribe_stock(code, tr_list)
            
        # 스트리밍 시작
        await self.ws_client.start_streaming()
        
    async def close(self):
        """연결 종료"""
        await self.ws_client.close() 