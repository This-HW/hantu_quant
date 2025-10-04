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

class SlopeIndicator(Indicator):
    """기울기(미분값) 지표 - 가격 및 이동평균의 기울기 계산"""
    
    def calculate_ma_slope(self, period: int = 20, days: int = 5) -> float:
        """이동평균 기울기 계산
        
        Args:
            period: 이동평균 기간
            days: 기울기 계산 기간
            
        Returns:
            float: 정규화된 기울기 (백분율)
        """
        self._validate_period(period)
        
        if len(self.data) < period + days:
            return 0.0
            
        # 이동평균 계산
        ma = self.data['close'].rolling(window=period).mean()
        
        # 기울기 계산을 위한 최근 데이터
        recent_ma = ma.dropna()[-days:]
        
        if len(recent_ma) < days:
            return 0.0
            
        # 선형 회귀로 기울기 계산
        x = np.arange(len(recent_ma))
        slope = np.polyfit(x, recent_ma.values, 1)[0]
        
        # 정규화 (현재 이동평균 대비 백분율)
        current_ma = recent_ma.iloc[-1]
        normalized_slope = (slope / current_ma) * 100 if current_ma != 0 else 0.0
        
        return normalized_slope
    
    def calculate_price_slope(self, days: int = 5) -> float:
        """가격 기울기 계산 (선형 회귀)
        
        Args:
            days: 기울기 계산 기간
            
        Returns:
            float: 정규화된 가격 기울기 (백분율)
        """
        if len(self.data) < days:
            return 0.0
            
        # 최근 가격 데이터
        recent_prices = self.data['close'].iloc[-days:]
        
        # 선형 회귀로 기울기 계산
        x = np.arange(len(recent_prices))
        slope = np.polyfit(x, recent_prices.values, 1)[0]
        
        # 정규화 (현재가 대비 백분율)
        current_price = recent_prices.iloc[-1]
        normalized_slope = (slope / current_price) * 100 if current_price != 0 else 0.0
        
        return normalized_slope
    
    def calculate_volume_slope(self, days: int = 5) -> float:
        """거래량 기울기 계산
        
        Args:
            days: 기울기 계산 기간
            
        Returns:
            float: 정규화된 거래량 기울기 (백분율)
        """
        if len(self.data) < days:
            return 0.0
            
        # 최근 거래량 데이터
        recent_volumes = self.data['volume'].iloc[-days:]
        
        # 선형 회귀로 기울기 계산
        x = np.arange(len(recent_volumes))
        slope = np.polyfit(x, recent_volumes.values, 1)[0]
        
        # 정규화 (현재 거래량 대비 백분율)
        current_volume = recent_volumes.iloc[-1]
        normalized_slope = (slope / current_volume) * 100 if current_volume != 0 else 0.0
        
        return normalized_slope
    
    def calculate_slope_acceleration(self, days: int = 5) -> float:
        """기울기 가속도 계산 (기울기의 변화율)
        
        Args:
            days: 기울기 계산 기간
            
        Returns:
            float: 기울기 가속도
        """
        if len(self.data) < days * 2:
            return 0.0
            
        # 현재 기울기와 이전 기울기 계산
        current_slope = self.calculate_price_slope(days)
        
        # 이전 기간의 기울기 계산을 위해 데이터 슬라이싱
        previous_data = self.data.iloc[:-days]
        if len(previous_data) < days:
            return 0.0
            
        # 임시 SlopeIndicator 생성하여 이전 기울기 계산
        temp_indicator = SlopeIndicator(previous_data)
        previous_slope = temp_indicator.calculate_price_slope(days)
        
        # 가속도 = 현재 기울기 - 이전 기울기
        acceleration = current_slope - previous_slope
        
        return acceleration
    
    def check_trend_consistency(self, short_period: int = 5, 
                              medium_period: int = 20, 
                              long_period: int = 60) -> bool:
        """추세 일관성 확인 (단기-중기-장기 기울기 방향 일치)
        
        Args:
            short_period: 단기 이동평균 기간
            medium_period: 중기 이동평균 기간
            long_period: 장기 이동평균 기간
            
        Returns:
            bool: 추세 일관성 여부
        """
        if len(self.data) < long_period + 10:
            return False
            
        # 각 기간별 기울기 계산
        short_slope = self.calculate_ma_slope(short_period, 3)
        medium_slope = self.calculate_ma_slope(medium_period, 5)
        long_slope = self.calculate_ma_slope(long_period, 10)
        
        # 모든 기울기가 같은 방향인지 확인
        # 상승 추세: 모든 기울기가 양수
        # 하락 추세: 모든 기울기가 음수
        positive_trend = short_slope > 0 and medium_slope > 0 and long_slope > 0
        negative_trend = short_slope < 0 and medium_slope < 0 and long_slope < 0
        
        return positive_trend or negative_trend
    
    def calculate_slope_angle(self, days: int = 5) -> float:
        """기울기를 각도로 변환
        
        Args:
            days: 기울기 계산 기간
            
        Returns:
            float: 기울기 각도 (도)
        """
        slope = self.calculate_price_slope(days)
        
        # 기울기를 각도로 변환 (아크탄젠트 사용)
        # slope는 이미 백분율이므로 100으로 나누어 실제 기울기로 변환
        actual_slope = slope / 100
        angle = np.arctan(actual_slope) * 180 / np.pi
        
        return angle
    
    def get_slope_strength(self, days: int = 5) -> str:
        """기울기 강도 분류
        
        Args:
            days: 기울기 계산 기간
            
        Returns:
            str: 기울기 강도 ('strong_up', 'weak_up', 'neutral', 'weak_down', 'strong_down')
        """
        slope = self.calculate_price_slope(days)
        
        if slope > 1.0:
            return 'strong_up'
        elif slope > 0.3:
            return 'weak_up'
        elif slope > -0.3:
            return 'neutral'
        elif slope > -1.0:
            return 'weak_down'
        else:
            return 'strong_down'
    
    def calculate_combined_slope_score(self) -> float:
        """종합 기울기 점수 계산 (0-100점)
        
        Returns:
            float: 종합 기울기 점수
        """
        score = 0.0
        
        # 1. 가격 기울기 점수 (40점)
        price_slope = self.calculate_price_slope(5)
        if price_slope > 0.5:
            score += 40
        elif price_slope > 0.2:
            score += 30
        elif price_slope > 0:
            score += 20
        elif price_slope > -0.2:
            score += 10
        # 음수면 0점
        
        # 2. 이동평균 기울기 점수 (30점)
        ma20_slope = self.calculate_ma_slope(20, 5)
        if ma20_slope > 0.3:
            score += 30
        elif ma20_slope > 0.1:
            score += 20
        elif ma20_slope > 0:
            score += 10
        
        # 3. 추세 일관성 점수 (20점)
        if self.check_trend_consistency():
            score += 20
        
        # 4. 기울기 가속도 점수 (10점)
        acceleration = self.calculate_slope_acceleration()
        if acceleration > 0.2:
            score += 10
        elif acceleration > 0:
            score += 5
        
        return min(score, 100.0)
    
    def calculate(self, analysis_type: str = 'comprehensive') -> Union[float, dict]:
        """기울기 지표 계산
        
        Args:
            analysis_type: 분석 유형 ('comprehensive', 'price', 'ma', 'volume')
            
        Returns:
            Union[float, dict]: 선택된 분석 결과
        """
        if analysis_type == 'comprehensive':
            return {
                'price_slope_5d': self.calculate_price_slope(5),
                'price_slope_20d': self.calculate_price_slope(20),
                'ma5_slope': self.calculate_ma_slope(5, 3),
                'ma20_slope': self.calculate_ma_slope(20, 5),
                'ma60_slope': self.calculate_ma_slope(60, 10),
                'volume_slope': self.calculate_volume_slope(5),
                'slope_acceleration': self.calculate_slope_acceleration(),
                'trend_consistency': self.check_trend_consistency(),
                'slope_angle': self.calculate_slope_angle(),
                'slope_strength': self.get_slope_strength(),
                'combined_score': self.calculate_combined_slope_score()
            }
        elif analysis_type == 'price':
            return self.calculate_price_slope(5)
        elif analysis_type == 'ma':
            return self.calculate_ma_slope(20, 5)
        elif analysis_type == 'volume':
            return self.calculate_volume_slope(5)
        else:
            raise ValueError(f"지원하지 않는 분석 유형: {analysis_type}") 