import asyncio
import logging
from datetime import datetime
from typing import Dict, List
import pandas as pd

from core.api.kis_api import KISAPI
from hantu_backtest.strategies.base import BacktestStrategy
from core.config.trading_config import (
    TRADE_AMOUNT, MAX_STOCKS,
    MAX_TRADES_PER_DAY, MAX_TRADES_PER_STOCK,
    MARKET_START_TIME, MARKET_END_TIME
)

logger = logging.getLogger(__name__)

class AutoTrader:
    """자동 매매 트레이더"""
    
    def __init__(self, api: KISAPI, strategy: BacktestStrategy):
        self.api = api
        self.strategy = strategy
        self.positions: Dict[str, Dict] = {}  # 보유 포지션
        self.buy_count = 0  # 당일 매수 횟수
        self.sell_count = 0  # 당일 매도 횟수
        
    def reset_daily_counts(self):
        """일일 거래 횟수 초기화"""
        self.buy_count = 0
        self.sell_count = 0
        
    def is_market_open(self) -> bool:
        """장 운영 시간 확인"""
        now = datetime.now().strftime('%H:%M')
        return MARKET_START_TIME <= now <= MARKET_END_TIME
        
    async def start(self, target_codes: List[str]):
        """자동 매매 시작"""
        logger.info("자동 매매를 시작합니다.")
        
        # 보유 종목 정보 초기화
        balance = self.api.get_balance()
        for code, quantity in balance.items():
            self.positions[code] = {
                'quantity': quantity,
                'entry_price': 0  # TODO: 평균 매수가 조회 필요
            }
            
        # 실시간 데이터 수신 시작
        await self.api.start_real_time(target_codes)
        
    def update_price_data(self, code: str, price_data: pd.DataFrame):
        """가격 데이터 업데이트 및 매매 신호 처리"""
        if not self.is_market_open():
            return
            
        # 매수 로직
        if (len(self.positions) < MAX_STOCKS and 
            self.buy_count < MAX_TRADES_PER_DAY and
            code not in self.positions):
            
            if self.strategy.should_buy(price_data):
                self._execute_buy(code, price_data)
                
        # 매도 로직
        elif code in self.positions and self.sell_count < MAX_TRADES_PER_STOCK:
            if self.strategy.should_sell(price_data, self.positions[code]):
                self._execute_sell(code)
                
    def _execute_buy(self, code: str, price_data: pd.DataFrame):
        """매수 실행"""
        try:
            current_price = price_data['Close'].iloc[-1]
            available_cash = float(self.api.get_balance()['예수금'])
            
            quantity = self.strategy.calculate_position_size(current_price, available_cash)
            if quantity <= 0:
                return
                
            result = self.api.market_buy(code, quantity)
            if result:
                logger.info(f"매수 주문 성공: {code} {quantity}주")
                self.positions[code] = {
                    'quantity': quantity,
                    'entry_price': current_price
                }
                self.buy_count += 1
                
        except Exception as e:
            logger.error(f"매수 실행 중 오류 발생: {e}")
            
    def _execute_sell(self, code: str):
        """매도 실행"""
        try:
            position = self.positions[code]
            result = self.api.market_sell(code, position['quantity'])
            
            if result:
                logger.info(f"매도 주문 성공: {code} {position['quantity']}주")
                del self.positions[code]
                self.sell_count += 1
                
        except Exception as e:
            logger.error(f"매도 실행 중 오류 발생: {e}")
            
    def get_trading_status(self) -> Dict:
        """거래 상태 조회"""
        return {
            'positions': self.positions,
            'buy_count': self.buy_count,
            'sell_count': self.sell_count
        } 