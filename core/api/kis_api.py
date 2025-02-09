"""
Korea Investment & Securities API client module.
"""

import logging
import pandas as pd
from typing import Dict, List, Optional, Callable
import asyncio
import websockets

from .rest_client import KISRestClient
from .websocket_client import KISWebSocketClient
from core.config.api_config import APIConfig

logger = logging.getLogger(__name__)

class KISAPI(KISRestClient):
    """한국투자증권 API 클라이언트"""
    
    def __init__(self):
        """초기화"""
        self.config = APIConfig()  # 싱글톤 인스턴스
        super().__init__()
        self.ws_client = None
        
    def place_order(self, stock_code: str, order_type: int, quantity: int,
                   price: int = 0, order_division: str = "00") -> dict:
        """주문 실행"""
        return super().place_order(stock_code, order_type, quantity, price, order_division)
        
    def get_balance(self) -> dict:
        """잔고 조회"""
        return super().get_balance()
        
    def market_buy(self, stock_code: str, quantity: int) -> Optional[Dict]:
        """시장가 매수"""
        return self.place_order(stock_code, 1, quantity)
        
    def market_sell(self, stock_code: str, quantity: int) -> Optional[Dict]:
        """시장가 매도"""
        return self.place_order(stock_code, 2, quantity)
        
    def limit_buy(self, stock_code: str, quantity: int, price: int) -> Optional[Dict]:
        """지정가 매수"""
        return self.place_order(stock_code, 1, quantity, price)
        
    def limit_sell(self, stock_code: str, quantity: int, price: int) -> Optional[Dict]:
        """지정가 매도"""
        return self.place_order(stock_code, 2, quantity, price)
        
    async def connect_websocket(self) -> bool:
        """WebSocket 연결"""
        if not self.config.ensure_valid_token():
            logger.error("[connect_websocket] API 토큰이 유효하지 않습니다")
            return False
            
        self.ws_client = KISWebSocketClient(self.config.access_token)
        return await self.ws_client.connect()
        
    def add_callback(self, tr_id: str, callback: Callable):
        """실시간 데이터 수신 콜백 등록"""
        if self.ws_client:
            self.ws_client.add_callback(tr_id, callback)
            
    async def subscribe_stock(self, stock_code: str, tr_list: List[str]) -> bool:
        """종목 실시간 데이터 구독"""
        if not self.ws_client:
            logger.error("[subscribe_stock] WebSocket이 연결되지 않았습니다")
            return False
            
        return await self.ws_client.subscribe(stock_code, tr_list)
        
    async def unsubscribe_stock(self, stock_code: str):
        """종목 구독 해지"""
        if self.ws_client:
            await self.ws_client.unsubscribe(stock_code)
            
    async def start_real_time(self, stock_codes: List[str]):
        """실시간 데이터 수신 시작"""
        try:
            # WebSocket 연결
            if not await self.connect_websocket():
                raise Exception("WebSocket 연결 실패")
                
            # 종목별 실시간 데이터 구독
            for code in stock_codes:
                tr_list = [
                    'H1_', # 주식 호가
                    'S3_', # 주식 체결
                    'K3_'  # 주식 체잔
                ]
                
                if not await self.subscribe_stock(code, tr_list):
                    logger.error(f"[start_real_time] {code} 구독 실패")
                    continue
                    
                logger.info(f"[start_real_time] {code} 구독 시작")
                
            # 실시간 데이터 수신
            if self.ws_client:
                await self.ws_client.start_streaming()
                
        except Exception as e:
            logger.error(f"[start_real_time] 실시간 데이터 수신 중 오류 발생: {str(e)}")
            raise
            
    async def close(self):
        """연결 종료"""
        if self.ws_client:
            await self.ws_client.close()
            self.ws_client = None
            
    def get_stock_info(self, stock_code: str) -> Optional[Dict]:
        """종목 정보 조회"""
        try:
            if not self.config.ensure_valid_token():
                raise Exception("API 토큰이 유효하지 않습니다")
                
            # API 요청 설정
            url = f"{self.config.base_url}/uapi/domestic-stock/v1/quotations/inquire-price"
            headers = self.config.get_headers()
            
            params = {
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": stock_code
            }
            
            response = self._request("GET", url, headers=headers, params=params)
            
            if response.get('rt_cd') == '0':
                return response.get('output')
            else:
                logger.error(f"[get_stock_info] API 오류: {response.get('msg1')}")
                return None
                
        except Exception as e:
            logger.error(f"[get_stock_info] 종목 정보 조회 중 오류 발생: {str(e)}")
            return None
            
    def get_stock_history(self, stock_code: str, period: str = "D", count: int = 20) -> Optional[pd.DataFrame]:
        """과거 주가 데이터 조회
        
        Args:
            stock_code: 종목코드
            period: 기간 구분 (D: 일봉, W: 주봉, M: 월봉)
            count: 조회 건수
            
        Returns:
            DataFrame: OHLCV 데이터
        """
        try:
            if not self.config.ensure_valid_token():
                raise Exception("API 토큰이 유효하지 않습니다")
                
            # API 요청 설정
            url = f"{self.config.base_url}/uapi/domestic-stock/v1/quotations/inquire-daily-price"
            headers = self.config.get_headers()
            
            params = {
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": stock_code,
                "FID_PERIOD_DIV_CODE": period,
                "FID_ORG_ADJ_PRC": "0",  # 수정주가 여부
                "FID_INPUT_DATE_1": "",  # 조회시작일자
                "FID_INPUT_DATE_2": "",  # 조회종료일자
                "FID_INPUT_HOUR_1": "",  # 시작시간
                "FID_INPUT_HOUR_2": "",  # 종료시간
                "FID_DAY_CNT": str(count)  # 조회건수
            }
            
            response = self._request("GET", url, headers=headers, params=params)
            
            if response.get('rt_cd') == '0':
                output = response.get('output', [])
                if not output:
                    logger.warning(f"[get_stock_history] 가격 데이터가 없습니다 - {stock_code}")
                    return None
                    
                # DataFrame 생성
                df = pd.DataFrame(output)
                
                # 컬럼명 변경
                df = df.rename(columns={
                    'stck_bsop_date': 'date',  # 일자
                    'stck_oprc': 'open',  # 시가
                    'stck_hgpr': 'high',  # 고가
                    'stck_lwpr': 'low',  # 저가
                    'stck_clpr': 'close',  # 종가
                    'acml_vol': 'volume'  # 거래량
                })
                
                # 데이터 타입 변환
                numeric_columns = ['open', 'high', 'low', 'close', 'volume']
                for col in numeric_columns:
                    df[col] = pd.to_numeric(df[col])
                    
                # 날짜 타입 변환
                df['date'] = pd.to_datetime(df['date'])
                
                return df
                
            else:
                logger.error(f"[get_stock_history] API 오류: {response.get('msg1')}")
                return None
                
        except Exception as e:
            logger.error(f"[get_stock_history] 가격 데이터 조회 중 오류 발생: {str(e)}")
            return None 