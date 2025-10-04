"""전략 기본 클래스"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any
import pandas as pd
from decimal import Decimal

from core.utils import get_logger
from .portfolio import Portfolio

logger = get_logger(__name__)

class Strategy(ABC):
    """전략 기본 클래스"""

    def __init__(self):
        """초기화"""
        self.portfolio = None

    @abstractmethod
    def initialize_portfolio(self, initial_capital: float):
        """
        포트폴리오 초기화

        Args:
            initial_capital (float): 초기 자본금
        """
        pass

    @abstractmethod
    def generate_signals(self, data: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        매매 신호 생성

        Args:
            data (pd.DataFrame): 주가 데이터

        Returns:
            List[Dict[str, Any]]: 매매 신호 목록
        """
        pass

    @abstractmethod
    def execute_trade(self, code: str, action: str, price: Decimal, quantity: int):
        """
        거래 실행

        Args:
            code (str): 종목 코드
            action (str): 매매 구분 ('buy' 또는 'sell')
            price (Decimal): 거래 가격
            quantity (int): 거래 수량
        """
        pass 