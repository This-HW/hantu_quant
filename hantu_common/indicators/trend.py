"""
Trend indicators module.
"""

import pandas as pd
import numpy as np
from typing import Union, Tuple
from .base import Indicator

class MovingAverage(Indicator):
    """이동평균선 지표"""
    
    def calculate(self, period: int = 20, ma_type: str = 'sma') -> pd.Series:
        """이동평균 계산
        
        Args:
            period: 기간
            ma_type: 이동평균 유형 ('sma', 'ema', 'wma')
            
        Returns:
            pd.Series: 이동평균선
        """
        self._validate_period(period)
        
        if ma_type == 'sma':
            return self.data['close'].rolling(window=period).mean()
        elif ma_type == 'ema':
            return self.data['close'].ewm(span=period, adjust=False).mean()
        elif ma_type == 'wma':
            weights = np.arange(1, period + 1)
            return self.data['close'].rolling(window=period).apply(
                lambda x: np.sum(weights * x) / weights.sum(), raw=True
            )
        else:
            raise ValueError("지원하지 않는 이동평균 유형입니다")

class MACD(Indicator):
    """MACD (Moving Average Convergence Divergence) 지표"""
    
    def calculate(self, 
                 fast_period: int = 12,
                 slow_period: int = 26,
                 signal_period: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """MACD 계산
        
        Args:
            fast_period: 단기 EMA 기간
            slow_period: 장기 EMA 기간
            signal_period: 시그널 기간
            
        Returns:
            Tuple[pd.Series, pd.Series, pd.Series]: (MACD, Signal, Histogram)
        """
        # EMA 계산
        fast_ema = self.data['close'].ewm(span=fast_period, adjust=False).mean()
        slow_ema = self.data['close'].ewm(span=slow_period, adjust=False).mean()
        
        # MACD 라인
        macd = fast_ema - slow_ema
        
        # 시그널 라인
        signal = macd.ewm(span=signal_period, adjust=False).mean()
        
        # MACD 히스토그램
        histogram = macd - signal
        
        return macd, signal, histogram 