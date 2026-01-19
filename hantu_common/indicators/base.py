"""
Base class for technical indicators.
"""

from abc import ABC, abstractmethod
import pandas as pd
from typing import Union

class Indicator(ABC):
    """기술지표 기본 클래스"""
    
    def __init__(self, data: pd.DataFrame):
        """
        Args:
            data: OHLCV 데이터를 포함하는 DataFrame
                - required columns: ['open', 'high', 'low', 'close', 'volume']
        """
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        if not all(col in data.columns for col in required_columns):
            raise ValueError(f"데이터프레임에 필수 컬럼이 없습니다: {required_columns}")
            
        self.data = data.copy()
        self._validate_data()
        
    def _validate_data(self):
        """데이터 유효성 검증"""
        # 데이터 타입 검증
        numeric_columns = ['open', 'high', 'low', 'close', 'volume']
        for col in numeric_columns:
            if not pd.api.types.is_numeric_dtype(self.data[col]):
                self.data[col] = pd.to_numeric(self.data[col], errors='coerce')
                
        # 결측치 처리
        self.data = self.data.ffill().bfill()
        
    @abstractmethod
    def calculate(self) -> Union[pd.Series, pd.DataFrame]:
        """지표 계산 (하위 클래스에서 구현)"""
        pass
        
    def _typical_price(self) -> pd.Series:
        """일반적인 가격 (TP) = (고가 + 저가 + 종가) / 3"""
        return (self.data['high'] + self.data['low'] + self.data['close']) / 3
        
    def _validate_period(self, period: int):
        """기간 유효성 검증"""
        if period < 1:
            raise ValueError("기간은 1 이상이어야 합니다")
        if period > len(self.data):
            raise ValueError("기간이 데이터 길이보다 깁니다") 