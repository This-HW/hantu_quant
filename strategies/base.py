from abc import ABC, abstractmethod
import pandas as pd
from typing import Dict, List, Optional, Tuple

class BaseStrategy(ABC):
    """기본 트레이딩 전략 클래스"""
    
    def __init__(self, name: str):
        self.name = name
        
    @abstractmethod
    def generate_signals(self, data: pd.DataFrame) -> Tuple[bool, bool]:
        """매수/매도 신호 생성
        
        Args:
            data: OHLCV 데이터
            
        Returns:
            (buy_signal, sell_signal) 튜플
        """
        pass
        
    @abstractmethod
    def should_buy(self, data: pd.DataFrame) -> bool:
        """매수 조건 확인"""
        pass
        
    @abstractmethod
    def should_sell(self, data: pd.DataFrame, position: Dict) -> bool:
        """매도 조건 확인"""
        pass
        
    def calculate_position_size(self, price: float, available_cash: float) -> int:
        """포지션 크기 계산"""
        from core.config.trading_config import MAX_STOCK_PRICE, TRADING_AMOUNT_RATIO
        
        # 최대 투자 가능 금액 계산
        max_amount = min(MAX_STOCK_PRICE, available_cash * TRADING_AMOUNT_RATIO)
        
        # 매수 가능 수량 계산
        quantity = int(max_amount / price)
        
        return quantity
        
    def validate_trading_conditions(self, data: pd.DataFrame) -> bool:
        """거래 조건 검증"""
        from core.config.trading_config import MIN_TRADING_VOLUME
        
        # 거래량 조건 확인
        if data['Volume'].iloc[-1] < MIN_TRADING_VOLUME:
            return False
            
        # 추가적인 검증 로직
        return True 