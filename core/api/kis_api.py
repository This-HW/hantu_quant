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
        
    def place_order(self, stock_code: str, order_type: str, quantity: int,
                   price: int = 0, order_division: str = "00") -> dict:
        """주문 실행"""
        return super().place_order(stock_code, order_type, quantity, price, order_division)
        
    def get_balance(self) -> dict:
        """잔고 조회"""
        return super().get_balance()

    def get_holdings(self) -> List[Dict]:
        """보유 종목 조회

        Returns:
            List[Dict]: 보유 종목 리스트. 각 종목은 다음 정보 포함:
                - stock_code: 종목코드
                - stock_name: 종목명
                - quantity: 보유수량
                - avg_price: 평균매입가
                - current_price: 현재가
                - profit_loss_rate: 손익률(%)
        """
        try:
            balance = self.get_balance()

            # get_balance()가 None을 반환하는 경우
            if not balance:
                logger.info("[get_holdings] 잔고 정보가 없습니다")
                return []

            # output2에 보유 종목 정보가 있음
            holdings_data = balance.get('output2', [])

            if not holdings_data:
                logger.info("[get_holdings] 보유 종목이 없습니다")
                return []

            holdings = []
            for item in holdings_data:
                # 수량이 0인 종목은 제외
                quantity = int(item.get('hldg_qty', 0))
                if quantity <= 0:
                    continue

                holding = {
                    'stock_code': item.get('pdno', ''),
                    'stock_name': item.get('prdt_name', ''),
                    'quantity': quantity,
                    'avg_price': int(item.get('pchs_avg_pric', 0)),
                    'current_price': int(item.get('prpr', 0)),
                    'profit_loss_rate': float(item.get('evlu_pfls_rt', 0))
                }
                holdings.append(holding)

            return holdings

        except Exception as e:
            logger.error(f"[get_holdings] 보유 종목 조회 중 오류 발생: {str(e)}")
            return []

    # 주문 상수 (KIS 표준)
    ORDER_TYPE_SELL: str = "01"  # 매도
    ORDER_TYPE_BUY: str = "02"   # 매수
    ORDER_DIVISION_LIMIT: str = "00"  # 지정가
    ORDER_DIVISION_MARKET: str = "01" # 시장가

    def market_buy(self, stock_code: str, quantity: int) -> Optional[Dict]:
        """시장가 매수"""
        return self.place_order(
            stock_code=stock_code,
            order_type=self.ORDER_TYPE_BUY,
            quantity=quantity,
            price=0,
            order_division=self.ORDER_DIVISION_MARKET,
        )
        
    def market_sell(self, stock_code: str, quantity: int) -> Optional[Dict]:
        """시장가 매도"""
        return self.place_order(
            stock_code=stock_code,
            order_type=self.ORDER_TYPE_SELL,
            quantity=quantity,
            price=0,
            order_division=self.ORDER_DIVISION_MARKET,
        )
        
    def limit_buy(self, stock_code: str, quantity: int, price: int) -> Optional[Dict]:
        """지정가 매수"""
        return self.place_order(
            stock_code=stock_code,
            order_type=self.ORDER_TYPE_BUY,
            quantity=quantity,
            price=price,
            order_division=self.ORDER_DIVISION_LIMIT,
        )
        
    def limit_sell(self, stock_code: str, quantity: int, price: int) -> Optional[Dict]:
        """지정가 매도"""
        return self.place_order(
            stock_code=stock_code,
            order_type=self.ORDER_TYPE_SELL,
            quantity=quantity,
            price=price,
            order_division=self.ORDER_DIVISION_LIMIT,
        )
        
    async def connect_websocket(self) -> bool:
        """WebSocket 연결"""
        try:
            if not self.config.ensure_valid_token():
                logger.error("[connect_websocket] API 토큰이 유효하지 않습니다")
                return False
                
            self.ws_client = KISWebSocketClient(self.config.access_token)
            return await self.ws_client.connect()
        except Exception as e:
            logger.error(f"[connect_websocket] WebSocket 연결 중 오류 발생: {str(e)}")
            return False
        
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
                logger.error("[start_real_time] WebSocket 연결 실패")
                return False
                
            # 연결 성공 후 잠시 대기 (안정화)
            await asyncio.sleep(1)
                
            # 종목별 실시간 데이터 구독
            subscription_success = False
            for code in stock_codes:
                tr_list = [
                    'H0STASP0',  # 주식 호가
                    'H0STCNT0',  # 주식 체결
                    'H0STCNI0'   # 주식 체결통보
                ]
                
                try:
                    if not await self.subscribe_stock(code, tr_list):
                        logger.error(f"[start_real_time] {code} 구독 실패")
                        continue
                        
                    logger.info(f"[start_real_time] {code} 구독 시작")
                    subscription_success = True
                except Exception as e:
                    logger.error(f"[start_real_time] {code} 구독 중 오류: {str(e)}")
                
            # 최소 하나 이상의 종목이 구독되었는지 확인
            if not subscription_success:
                logger.error("[start_real_time] 모든 종목 구독 실패")
                return False
                
            # 실시간 데이터 수신
            if self.ws_client:
                await self.ws_client.start_streaming()
                return True
            return False
                
        except Exception as e:
            logger.error(f"[start_real_time] 실시간 데이터 수신 중 오류 발생: {str(e)}")
            # 연결이 남아있다면 정리
            if self.ws_client:
                try:
                    await self.ws_client.close()
                except:
                    pass
                self.ws_client = None
            return False
            
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