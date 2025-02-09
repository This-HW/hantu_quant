"""
Volume indicators module.
"""

import pandas as pd
import numpy as np
from typing import Union, Dict
from .base import Indicator

class OBV(Indicator):
    """OBV (On Balance Volume) 지표"""
    
    def calculate(self) -> pd.Series:
        """OBV 계산
        
        Returns:
            pd.Series: OBV 값
        """
        # 가격 변화
        price_change = self.data['close'].diff()
        
        # OBV 계산
        obv = pd.Series(index=self.data.index, dtype=float)
        obv.iloc[0] = 0
        
        # 가격 변화에 따른 거래량 가감
        obv[price_change > 0] = self.data['volume'][price_change > 0]
        obv[price_change < 0] = -self.data['volume'][price_change < 0]
        obv[price_change == 0] = 0
        
        return obv.cumsum()

class VolumeProfile(Indicator):
    """거래량 프로파일 지표"""
    
    def calculate(self, price_levels: int = 50) -> Dict[str, pd.Series]:
        """거래량 프로파일 계산
        
        Args:
            price_levels: 가격 구간 수
            
        Returns:
            Dict[str, pd.Series]: 
                - volume_by_price: 가격대별 거래량
                - poc: Point of Control (최대 거래량 가격)
                - value_area: Value Area (거래량 68% 구간)
        """
        # 가격 구간 설정
        price_min = self.data['low'].min()
        price_max = self.data['high'].max()
        price_step = (price_max - price_min) / price_levels
        
        # 가격 구간별 거래량 계산
        volume_by_price = pd.Series(0.0, index=np.arange(price_min, price_max, price_step))
        
        for i in range(len(self.data)):
            # 해당 봉의 거래 구간에 거래량 분배
            low = self.data['low'].iloc[i]
            high = self.data['high'].iloc[i]
            volume = self.data['volume'].iloc[i]
            
            # 거래가 발생한 가격 구간 찾기
            price_range = np.arange(low, high, price_step)
            if len(price_range) > 0:
                volume_per_level = volume / len(price_range)
                for price in price_range:
                    if price in volume_by_price.index:
                        volume_by_price[price] += volume_per_level
        
        # Point of Control (최대 거래량 가격)
        poc = volume_by_price.idxmax()
        
        # Value Area (전체 거래량의 68% 구간)
        total_volume = volume_by_price.sum()
        sorted_volumes = volume_by_price.sort_values(ascending=False)
        cumsum_volumes = sorted_volumes.cumsum()
        value_area = sorted_volumes[cumsum_volumes <= total_volume * 0.68]
        
        return {
            'volume_by_price': volume_by_price,
            'poc': poc,
            'value_area': value_area
        } 