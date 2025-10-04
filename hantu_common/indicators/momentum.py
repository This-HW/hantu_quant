"""
Momentum indicators module.
"""

import pandas as pd
import numpy as np
from typing import Union, Tuple, Optional
from .base import Indicator

class RSI(Indicator):
    """RSI (Relative Strength Index) 지표"""
    
    def calculate(self, period: int = 14) -> pd.Series:
        """RSI 계산
        
        Args:
            period: RSI 계산 기간
            
        Returns:
            pd.Series: RSI 값
        """
        self._validate_period(period)
        
        # 가격 변화
        delta = self.data['close'].diff()
        
        # 상승/하락 구분
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        
        # 평균 계산
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        
        # RSI 계산
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi

    def get_latest(self, period: int = 14) -> Optional[float]:
        """최신 RSI 값 반환
        
        Args:
            period: RSI 계산 기간
            
        Returns:
            Optional[float]: 최신 RSI 값
        """
        try:
            rsi = self.calculate(period)
            return rsi.iloc[-1]
        except Exception:
            return None

class MomentumScore:
    """모멘텀 점수 계산"""
    
    def __init__(self, data: pd.DataFrame):
        """
        Args:
            data: OHLCV 데이터를 포함하는 DataFrame
        """
        self.data = data
        self.rsi = RSI(data)
        
    def calculate(self,
                 rsi_period: int = 14,
                 rsi_buy_threshold: int = 30,
                 ma_short_period: int = 5,
                 ma_medium_period: int = 20,
                 volume_surge_ratio: float = 2.0) -> float:
        """모멘텀 점수 계산 (0-100점)
        
        Args:
            rsi_period: RSI 계산 기간
            rsi_buy_threshold: RSI 매수 임계값
            ma_short_period: 단기 이동평균 기간
            ma_medium_period: 중기 이동평균 기간
            volume_surge_ratio: 거래량 급증 비율
            
        Returns:
            float: 모멘텀 점수
        """
        score = 0
        
        # RSI 점수 (40점)
        rsi_value = self.rsi.get_latest(rsi_period)
        if rsi_value is not None:
            if rsi_value <= rsi_buy_threshold:  # 과매도 구간
                score += 40
            elif rsi_value <= 45:  # 매수 고려 구간
                score += 20
        
        # 이동평균 점수 (30점)
        ma_short = self.data['close'].rolling(window=ma_short_period).mean()
        ma_medium = self.data['close'].rolling(window=ma_medium_period).mean()
        
        if (ma_short.iloc[-1] > ma_medium.iloc[-1] and  # 골든크로스
            ma_short.iloc[-2] <= ma_medium.iloc[-2]):
            score += 30
        elif ma_short.iloc[-1] > ma_medium.iloc[-1]:  # 단순 상승추세
            score += 15
        
        # 거래량 점수 (30점)
        volume_ratio = (self.data['volume'].iloc[-1] / 
                       self.data['volume'].rolling(window=20).mean().iloc[-1])
        
        if volume_ratio >= volume_surge_ratio:
            score += 30
        elif volume_ratio >= 1.5:
            score += 15
        
        return score

class Stochastic(Indicator):
    """스토캐스틱 지표"""
    
    def calculate(self, 
                 k_period: int = 14,
                 d_period: int = 3,
                 smooth_k: int = 3) -> Tuple[pd.Series, pd.Series]:
        """스토캐스틱 계산
        
        Args:
            k_period: K값 기간
            d_period: D값 기간
            smooth_k: K값 평활화 기간
            
        Returns:
            Tuple[pd.Series, pd.Series]: (K%, D%)
        """
        self._validate_period(k_period)
        
        # 최저가/최고가 계산
        low_min = self.data['low'].rolling(window=k_period).min()
        high_max = self.data['high'].rolling(window=k_period).max()
        
        # Fast %K 계산
        fast_k = 100 * (self.data['close'] - low_min) / (high_max - low_min)
        
        # Slow %K 계산 (Fast %K의 이동평균)
        slow_k = fast_k.rolling(window=smooth_k).mean()
        
        # Slow %D 계산 (Slow %K의 이동평균)
        slow_d = slow_k.rolling(window=d_period).mean()
        
        return slow_k, slow_d 