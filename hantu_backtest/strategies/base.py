"""
Base strategy class for backtesting.
"""

from abc import ABC, abstractmethod
import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class BacktestStrategy(ABC):
    """백테스팅용 기본 전략 클래스"""
    
    def __init__(self, name: str):
        """
        Args:
            name: 전략 이름
        """
        self.name = name
        
    @abstractmethod
    def load_data(self, start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """과거 데이터 로드
        
        Args:
            start_date: 시작일
            end_date: 종료일
            
        Returns:
            pd.DataFrame: OHLCV 데이터
        """
        pass
        
    @abstractmethod
    def generate_signals(self, data: pd.DataFrame) -> List[Dict]:
        """매매 신호 생성
        
        Args:
            data: OHLCV 데이터
            
        Returns:
            List[Dict]: 매매 신호 목록
            [
                {
                    'code': 종목코드,
                    'type': 'buy' or 'sell',
                    'quantity': 수량
                },
                ...
            ]
        """
        pass
        
    def calculate_position_size(self, 
                              price: float,
                              available_cash: float,
                              risk_ratio: float = 0.02) -> int:
        """포지션 크기 계산
        
        Args:
            price: 현재가
            available_cash: 사용 가능 현금
            risk_ratio: 위험 비율 (기본값: 2%)
            
        Returns:
            int: 매수/매도 수량
        """
        if price <= 0 or available_cash <= 0:
            return 0
            
        position_amount = available_cash * risk_ratio
        quantity = int(position_amount / price)
        
        return max(quantity, 0)
        
    def validate_trading_conditions(self, data: pd.DataFrame) -> bool:
        """거래 조건 검증
        
        Args:
            data: OHLCV 데이터
            
        Returns:
            bool: 거래 가능 여부
        """
        if data is None or data.empty:
            return False
            
        # 거래량 조건
        if 'volume' in data.columns and data['volume'].iloc[-1] <= 0:
            return False
            
        return True 