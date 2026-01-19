"""
Momentum strategy for backtesting.
"""

import pandas as pd
import numpy as np
from decimal import Decimal
from datetime import datetime
from pathlib import Path

from .base import BacktestStrategy
from hantu_common.indicators import MovingAverage
from core.utils import get_logger
from ..core.portfolio import Portfolio

logger = get_logger(__name__)

class MomentumStrategy(BacktestStrategy):
    """모멘텀 전략"""
    
    def __init__(self, rsi_period: int = 14, rsi_upper: float = 70, rsi_lower: float = 30,
                 ma_short: int = 5, ma_long: int = 20):
        """
        초기화

        Args:
            rsi_period (int, optional): RSI 계산 기간. 기본값 14.
            rsi_upper (float, optional): RSI 상단 기준값. 기본값 70.
            rsi_lower (float, optional): RSI 하단 기준값. 기본값 30.
            ma_short (int, optional): 단기 이동평균 기간. 기본값 5.
            ma_long (int, optional): 장기 이동평균 기간. 기본값 20.
        """
        super().__init__(name="모멘텀 전략")
        self.rsi_period = rsi_period
        self.rsi_upper = rsi_upper
        self.rsi_lower = rsi_lower
        self.ma_short = ma_short
        self.ma_long = ma_long
        
        # 데이터 저장 경로
        self.data_dir = Path(__file__).parent.parent / 'data' / 'historical'
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
    def initialize_portfolio(self, initial_capital: float):
        """
        포트폴리오 초기화

        Args:
            initial_capital (float): 초기 자본금
        """
        self.portfolio = Portfolio(initial_capital)
        logger.info(f"포트폴리오 초기화 완료 (초기자본: {initial_capital:,.0f}원)")

    def load_data(self, start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """과거 데이터 로드
        
        Args:
            start_date: 시작일
            end_date: 종료일
            
        Returns:
            pd.DataFrame: OHLCV 데이터
        """
        try:
            # 테스트 데이터 생성
            dates = pd.date_range(start=start_date, end=end_date, freq='D')
            base_price = 100
            
            data = pd.DataFrame({
                'open': [base_price + np.random.normal(0, 2) for _ in range(len(dates))],
                'high': [base_price + np.random.normal(2, 2) for _ in range(len(dates))],
                'low': [base_price + np.random.normal(-2, 2) for _ in range(len(dates))],
                'close': [base_price + np.random.normal(0, 2) for _ in range(len(dates))],
                'volume': [np.random.randint(1000, 10000) for _ in range(len(dates))]
            }, index=dates)
            
            # 데이터 정리
            data = data.sort_index()
            
            # 고가/저가 조정
            data['high'] = data[['open', 'high', 'close']].max(axis=1)
            data['low'] = data[['open', 'low', 'close']].min(axis=1)
            
            logger.info(f"[load_data] 데이터 로드 완료 - {len(data)}개 데이터")
            return data
            
        except Exception as e:
            logger.error(f"[load_data] 데이터 로드 중 오류 발생: {str(e)}")
            raise

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """매매 신호 생성

        Args:
            data: 주가 데이터

        Returns:
            pd.DataFrame: 매매 신호가 포함된 데이터프레임
        """
        try:
            # 데이터 길이 체크
            if len(data) < max(self.rsi_period, self.ma_short, self.ma_long):
                logger.warning(f"데이터 길이({len(data)})가 필요한 최소 길이보다 짧습니다.")
                return pd.DataFrame()

            # RSI 계산
            rsi = self._calculate_rsi(data['close'])
            
            # 이동평균 계산
            ma_short = MovingAverage(data).calculate(self.ma_short)
            ma_long = MovingAverage(data).calculate(self.ma_long)

            # 매매 신호 초기화
            signals = pd.DataFrame(index=data.index)
            signals['signal'] = 0

            # 매수 조건: RSI < 30이고 단기 이동평균이 장기 이동평균을 상향 돌파
            buy_condition = (
                (rsi < 30) & 
                (ma_short > ma_long) & 
                (ma_short.shift(1) <= ma_long.shift(1))
            )
            signals.loc[buy_condition, 'signal'] = 1

            # 매도 조건: RSI > 70이고 단기 이동평균이 장기 이동평균을 하향 돌파
            sell_condition = (
                (rsi > 70) & 
                (ma_short < ma_long) & 
                (ma_short.shift(1) >= ma_long.shift(1))
            )
            signals.loc[sell_condition, 'signal'] = -1

            logger.info(f"매매 신호 생성 완료 - 매수: {len(buy_condition[buy_condition])}건, 매도: {len(sell_condition[sell_condition])}건")
            return signals

        except Exception as e:
            logger.error(f"매매 신호 생성 중 오류 발생: {str(e)}")
            return pd.DataFrame()

    def execute_trade(self, code: str, action: str, price: Decimal, quantity: int):
        """
        거래 실행

        Args:
            code (str): 종목 코드
            action (str): 매매 구분 ('buy' 또는 'sell')
            price (Decimal): 거래 가격
            quantity (int): 거래 수량
        """
        try:
            if action == 'buy':
                self.portfolio.buy(code, quantity, price, commission=0)
                logger.info(f"매수 실행: {code} {quantity}주 @ {price:,.0f}원")
            elif action == 'sell':
                self.portfolio.sell(code, quantity, price, commission=0)
                logger.info(f"매도 실행: {code} {quantity}주 @ {price:,.0f}원")
                
        except Exception as e:
            logger.error(f"[execute_trade] 거래 실행 중 오류 발생: {str(e)}")

    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """RSI 계산"""
        # 가격 변화
        delta = prices.diff()
        
        # 상승/하락 구분
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        
        # 초기 평균 계산
        avg_gain = gain.rolling(window=period, min_periods=period).mean()
        avg_loss = loss.rolling(window=period, min_periods=period).mean()
        
        # RSI 계산
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        # NaN 값을 50으로 대체 (중립)
        rsi = rsi.fillna(50)
        
        return rsi 