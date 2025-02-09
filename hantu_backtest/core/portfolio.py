"""
Portfolio management module for backtesting.
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional
import logging
from decimal import Decimal
from core.utils import get_logger

logger = get_logger(__name__)

class Position:
    """포지션 정보"""
    
    def __init__(self, quantity: int, avg_price: Decimal):
        """초기화
        
        Args:
            quantity: 보유 수량
            avg_price: 평균 단가
        """
        self.quantity = quantity
        self.avg_price = avg_price

class Portfolio:
    """포트폴리오 관리"""
    
    def __init__(self, initial_capital: float):
        """초기화
        
        Args:
            initial_capital: 초기 자본금
        """
        self.initial_capital = Decimal(str(initial_capital))
        self.cash = self.initial_capital
        self.positions: Dict[str, Position] = {}  # {종목코드: Position}
        self.total_value = self.initial_capital
        
    def update(self, data: pd.DataFrame):
        """포트폴리오 가치 업데이트
        
        Args:
            data: 현재 시점의 가격 데이터
        """
        stock_value = Decimal('0')
        
        # 보유 종목의 가치 계산
        for code, position in self.positions.items():
            if code in data.index:
                current_price = Decimal(str(data.loc[code, 'close']))
                stock_value += position.quantity * current_price
                
        # 총 자산가치 업데이트
        self.total_value = self.cash + stock_value
        
        logger.debug(f"포트폴리오 업데이트 - 현금: {float(self.cash):,.0f}원, "
                    f"주식: {float(stock_value):,.0f}원, "
                    f"총자산: {float(self.total_value):,.0f}원")
        
    def get_total_value(self, current_prices: Dict[str, Decimal]) -> Decimal:
        """총 자산가치 계산
        
        Args:
            current_prices: 종목별 현재가 {종목코드: 현재가}
            
        Returns:
            Decimal: 총 자산가치
        """
        stock_value = sum(
            pos.quantity * current_prices[code]
            for code, pos in self.positions.items()
            if code in current_prices
        )
        return self.cash + stock_value
        
    def can_buy(self, price: Decimal, quantity: int, commission: Decimal = Decimal('0')) -> bool:
        """매수 가능 여부 확인"""
        total_cost = price * quantity + commission
        return self.cash >= total_cost
        
    def can_sell(self, code: str, quantity: int) -> bool:
        """매도 가능 여부 확인"""
        if code not in self.positions:
            return False
        return self.positions[code].quantity >= quantity
        
    def buy(self, code: str, quantity: int, price: Decimal, commission: Decimal = Decimal('0')):
        """매수 실행"""
        total_cost = price * quantity + commission
        
        if not self.can_buy(price, quantity, commission):
            raise ValueError("매수 가능 금액이 부족합니다")
            
        # 포지션 업데이트
        if code in self.positions:
            # 기존 포지션이 있는 경우 평균단가 계산
            current_pos = self.positions[code]
            new_quantity = current_pos.quantity + quantity
            new_avg_price = (
                (current_pos.quantity * current_pos.avg_price + quantity * price) /
                new_quantity
            )
            self.positions[code] = Position(new_quantity, new_avg_price)
        else:
            # 신규 포지션
            self.positions[code] = Position(quantity, price)
            
        # 현금 차감
        self.cash -= total_cost
        
        logger.debug(f"매수 실행 - 종목: {code}, "
                    f"수량: {quantity}, 가격: {float(price):,.0f}, "
                    f"수수료: {float(commission):,.0f}")
        
    def sell(self, code: str, quantity: int, price: Decimal, commission: Decimal = Decimal('0')):
        """매도 실행"""
        if not self.can_sell(code, quantity):
            raise ValueError("매도 가능 수량이 부족합니다")
            
        # 매도 금액 계산
        total_amount = price * quantity - commission
        
        # 포지션 업데이트
        current_pos = self.positions[code]
        if current_pos.quantity == quantity:
            # 전량 매도
            del self.positions[code]
        else:
            # 일부 매도
            new_quantity = current_pos.quantity - quantity
            self.positions[code] = Position(new_quantity, current_pos.avg_price)
            
        # 현금 증가
        self.cash += total_amount
        
        logger.debug(f"매도 실행 - 종목: {code}, "
                    f"수량: {quantity}, 가격: {float(price):,.0f}, "
                    f"수수료: {float(commission):,.0f}")
        
    def get_position(self, code: str) -> Optional[Position]:
        """종목별 포지션 조회"""
        return self.positions.get(code)
        
    def get_portfolio_status(self) -> Dict:
        """포트폴리오 상태 조회"""
        return {
            'cash': float(self.cash),
            'total_value': float(self.total_value),
            'positions': {
                code: {
                    'quantity': pos.quantity,
                    'avg_price': float(pos.avg_price)
                }
                for code, pos in self.positions.items()
            }
        } 