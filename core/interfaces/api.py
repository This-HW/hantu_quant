"""
API 관련 인터페이스 정의

이 모듈은 외부 API와의 통신을 위한 인터페이스들을 정의합니다.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Callable
import pandas as pd


class IAPIClient(ABC):
    """API 클라이언트 인터페이스"""
    
    @abstractmethod
    def place_order(self, stock_code: str, order_type: int, quantity: int,
                   price: int = 0, order_division: str = "00") -> Dict:
        """주문 실행"""
        pass
    
    @abstractmethod
    def get_balance(self) -> Dict:
        """잔고 조회"""
        pass
    
    @abstractmethod
    def market_buy(self, stock_code: str, quantity: int) -> Optional[Dict]:
        """시장가 매수"""
        pass
    
    @abstractmethod
    def market_sell(self, stock_code: str, quantity: int) -> Optional[Dict]:
        """시장가 매도"""
        pass
    
    @abstractmethod
    def limit_buy(self, stock_code: str, quantity: int, price: int) -> Optional[Dict]:
        """지정가 매수"""
        pass
    
    @abstractmethod
    def limit_sell(self, stock_code: str, quantity: int, price: int) -> Optional[Dict]:
        """지정가 매도"""
        pass
    
    @abstractmethod
    def get_stock_info(self, stock_code: str) -> Optional[Dict]:
        """종목 정보 조회"""
        pass
    
    @abstractmethod
    def get_stock_history(self, stock_code: str, period: str = "D", count: int = 20) -> Optional[pd.DataFrame]:
        """주가 히스토리 조회"""
        pass


class IDataProvider(ABC):
    """데이터 제공자 인터페이스"""
    
    @abstractmethod
    def get_stock_data(self, stock_code: str) -> Optional[Dict]:
        """종목 데이터 조회"""
        pass
    
    @abstractmethod
    def get_market_data(self, market_type: str = "KOSPI") -> Optional[Dict]:
        """시장 데이터 조회"""
        pass
    
    @abstractmethod
    def get_financial_data(self, stock_code: str) -> Optional[Dict]:
        """재무 데이터 조회"""
        pass
    
    @abstractmethod
    def get_sector_data(self, sector: str) -> Optional[Dict]:
        """섹터 데이터 조회"""
        pass
    
    @abstractmethod
    def get_price_history(self, stock_code: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        """가격 히스토리 조회"""
        pass


class IWebSocketClient(ABC):
    """WebSocket 클라이언트 인터페이스"""
    
    @abstractmethod
    async def connect(self) -> bool:
        """WebSocket 연결"""
        pass
    
    @abstractmethod
    async def disconnect(self):
        """WebSocket 연결 해제"""
        pass
    
    @abstractmethod
    def add_callback(self, tr_id: str, callback: Callable):
        """콜백 함수 추가"""
        pass
    
    @abstractmethod
    async def subscribe_stock(self, stock_code: str, tr_list: List[str]) -> bool:
        """종목 실시간 데이터 구독"""
        pass
    
    @abstractmethod
    async def unsubscribe_stock(self, stock_code: str):
        """종목 실시간 데이터 구독 해제"""
        pass
    
    @abstractmethod
    async def start_real_time(self, stock_codes: List[str]):
        """실시간 데이터 수신 시작"""
        pass
    
    @abstractmethod
    async def close(self):
        """WebSocket 클라이언트 종료"""
        pass


class ITokenManager(ABC):
    """토큰 관리자 인터페이스"""
    
    @abstractmethod
    def get_access_token(self) -> Optional[str]:
        """액세스 토큰 조회"""
        pass
    
    @abstractmethod
    def refresh_token(self) -> bool:
        """토큰 갱신"""
        pass
    
    @abstractmethod
    def is_token_valid(self) -> bool:
        """토큰 유효성 확인"""
        pass
    
    @abstractmethod
    def save_token(self, token: Dict) -> bool:
        """토큰 저장"""
        pass
    
    @abstractmethod
    def load_token(self) -> Optional[Dict]:
        """토큰 로드"""
        pass 