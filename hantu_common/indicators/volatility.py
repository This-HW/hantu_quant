"""
Volatility indicators module.
"""

import pandas as pd
import numpy as np
from typing import Tuple
from .base import Indicator

class BollingerBands(Indicator):
    """볼린저 밴드 지표"""
    
    def calculate(self, 
                 period: int = 20,
                 num_std: float = 2.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """볼린저 밴드 계산
        
        Args:
            period: 이동평균 기간
            num_std: 표준편차 승수
            
        Returns:
            Tuple[pd.Series, pd.Series, pd.Series]: (Upper Band, Middle Band, Lower Band)
        """
        self._validate_period(period)
        
        # 중간 밴드 (단순 이동평균)
        middle_band = self.data['close'].rolling(window=period).mean()
        
        # 표준편차 계산
        rolling_std = self.data['close'].rolling(window=period).std()
        
        # 상단/하단 밴드
        upper_band = middle_band + (rolling_std * num_std)
        lower_band = middle_band - (rolling_std * num_std)
        
        return upper_band, middle_band, lower_band

class ATR(Indicator):
    """ATR (Average True Range) 지표"""
    
    def calculate(self, period: int = 14) -> pd.Series:
        """ATR 계산
        
        Args:
            period: ATR 계산 기간
            
        Returns:
            pd.Series: ATR 값
        """
        self._validate_period(period)
        
        # True Range 계산
        high_low = self.data['high'] - self.data['low']
        high_close = np.abs(self.data['high'] - self.data['close'].shift())
        low_close = np.abs(self.data['low'] - self.data['close'].shift())
        
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        
        # ATR 계산 (지수이동평균 사용)
        atr = true_range.ewm(span=period, adjust=False).mean()
        
        return atr 