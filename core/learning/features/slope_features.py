"""
Phase 4 AI 학습 시스템 - 기울기 피처 엔지니어링 모듈

기울기 관련 피처 추출:
1. price_slope_5d: 5일 가격 기울기
2. price_slope_20d: 20일 가격 기울기
3. ma5_slope: 5일 이동평균 기울기
4. ma20_slope: 20일 이동평균 기울기
5. ma60_slope: 60일 이동평균 기울기
6. slope_acceleration: 기울기 가속도
7. trend_consistency: 추세 일관성
8. slope_angle: 기울기 각도
9. slope_strength_score: 기울기 강도 점수
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import logging

from core.utils.log_utils import get_logger
from hantu_common.indicators.trend import SlopeIndicator

logger = get_logger(__name__)

@dataclass
class SlopeFeatures:
    """기울기 피처 데이터 클래스"""
    price_slope_5d: float = 0.0
    price_slope_20d: float = 0.0
    ma5_slope: float = 0.0
    ma20_slope: float = 0.0
    ma60_slope: float = 0.0
    slope_acceleration: float = 0.0
    trend_consistency: float = 0.0
    slope_angle: float = 0.0
    slope_strength_score: float = 0.0
    
    def to_dict(self) -> Dict[str, float]:
        """딕셔너리 형태로 변환"""
        return {
            'price_slope_5d': self.price_slope_5d,
            'price_slope_20d': self.price_slope_20d,
            'ma5_slope': self.ma5_slope,
            'ma20_slope': self.ma20_slope,
            'ma60_slope': self.ma60_slope,
            'slope_acceleration': self.slope_acceleration,
            'trend_consistency': self.trend_consistency,
            'slope_angle': self.slope_angle,
            'slope_strength_score': self.slope_strength_score
        }

class SlopeFeatureExtractor:
    """기울기 피처 추출기"""
    
    def __init__(self):
        """기울기 피처 추출기 초기화"""
        self._logger = logger
        self._min_data_length = 70  # 최소 필요 데이터 길이
        
    def extract_features(self, ohlcv_data: pd.DataFrame) -> SlopeFeatures:
        """
        OHLCV 데이터에서 기울기 피처 추출
        
        Args:
            ohlcv_data: OHLCV 데이터프레임
            
        Returns:
            SlopeFeatures: 추출된 기울기 피처
        """
        try:
            if ohlcv_data is None or len(ohlcv_data) < self._min_data_length:
                self._logger.warning(f"기울기 피처 추출을 위한 데이터 부족: {len(ohlcv_data) if ohlcv_data is not None else 0}")
                return SlopeFeatures()
            
            # SlopeIndicator 생성
            slope_indicator = SlopeIndicator(ohlcv_data)
            
            # 각 피처 계산
            features = SlopeFeatures()
            
            # 1. 가격 기울기 피처
            features.price_slope_5d = self._calculate_price_slope(ohlcv_data, 5)
            features.price_slope_20d = self._calculate_price_slope(ohlcv_data, 20)
            
            # 2. 이동평균 기울기 피처
            features.ma5_slope = self._calculate_ma_slope(ohlcv_data, 5, 3)
            features.ma20_slope = self._calculate_ma_slope(ohlcv_data, 20, 5)
            features.ma60_slope = self._calculate_ma_slope(ohlcv_data, 60, 10)
            
            # 3. 기울기 가속도
            features.slope_acceleration = self._calculate_slope_acceleration(ohlcv_data)
            
            # 4. 추세 일관성
            features.trend_consistency = self._check_trend_consistency(ohlcv_data)
            
            # 5. 기울기 각도
            features.slope_angle = self._calculate_slope_angle(ohlcv_data)
            
            # 6. 기울기 강도 점수
            features.slope_strength_score = self._get_slope_strength_score(ohlcv_data)
            
            self._logger.debug(f"기울기 피처 추출 완료: {features.to_dict()}")
            return features
            
        except Exception as e:
            self._logger.error(f"기울기 피처 추출 중 오류 발생: {e}")
            return SlopeFeatures()
    
    def _calculate_price_slope(self, ohlcv_data: pd.DataFrame, days: int) -> float:
        """가격 기울기 계산 (선형 회귀)
        
        Args:
            ohlcv_data: OHLCV 데이터
            days: 기울기 계산 기간
            
        Returns:
            float: 정규화된 가격 기울기 (백분율)
        """
        try:
            if len(ohlcv_data) < days:
                return 0.0
                
            # 최근 가격 데이터
            recent_prices = ohlcv_data['close'].iloc[-days:]
            
            # 선형 회귀로 기울기 계산
            x = np.arange(len(recent_prices))
            slope = np.polyfit(x, recent_prices.values, 1)[0]
            
            # 정규화 (현재가 대비 백분율)
            current_price = recent_prices.iloc[-1]
            normalized_slope = (slope / current_price) * 100 if current_price != 0 else 0.0
            
            return normalized_slope
            
        except Exception as e:
            self._logger.error(f"가격 기울기 계산 오류: {e}")
            return 0.0
    
    def _calculate_ma_slope(self, ohlcv_data: pd.DataFrame, ma_period: int, slope_days: int) -> float:
        """이동평균 기울기 계산
        
        Args:
            ohlcv_data: OHLCV 데이터
            ma_period: 이동평균 기간
            slope_days: 기울기 계산 기간
            
        Returns:
            float: 정규화된 이동평균 기울기 (백분율)
        """
        try:
            if len(ohlcv_data) < ma_period + slope_days:
                return 0.0
            
            # 이동평균 계산
            ma_series = ohlcv_data['close'].rolling(window=ma_period).mean()
            ma_cleaned = ma_series.dropna()
            recent_ma = ma_cleaned.tail(slope_days)
            
            if len(recent_ma) < slope_days:
                return 0.0
            
            # 선형 회귀로 기울기 계산
            x = np.arange(len(recent_ma))
            y = np.array(recent_ma.values, dtype=float)
            slope = np.polyfit(x, y, 1)[0]
            
            # 정규화
            current_ma = recent_ma.iloc[-1]
            normalized_slope = (slope / current_ma) * 100 if current_ma != 0 else 0.0
            
            return normalized_slope
            
        except Exception as e:
            self._logger.error(f"이동평균 기울기 계산 오류: {e}")
            return 0.0
    
    def _calculate_slope_acceleration(self, ohlcv_data: pd.DataFrame) -> float:
        """기울기 가속도 계산
        
        Args:
            ohlcv_data: OHLCV 데이터
            
        Returns:
            float: 기울기 가속도 (백분율)
        """
        try:
            if len(ohlcv_data) < 15:  # 최소 15일 필요
                return 0.0
            
            # 현재 기울기 (최근 5일)
            current_slope = self._calculate_price_slope(ohlcv_data, 5)
            
            # 이전 기울기 (5일 전 기준 5일)
            previous_data = ohlcv_data.iloc[:-5]
            if len(previous_data) < 5:
                return 0.0
            
            previous_slope = self._calculate_price_slope(previous_data, 5)
            
            # 가속도 = 현재 기울기 - 이전 기울기
            acceleration = current_slope - previous_slope
            
            return acceleration
            
        except Exception as e:
            self._logger.error(f"기울기 가속도 계산 오류: {e}")
            return 0.0
    
    def _check_trend_consistency(self, ohlcv_data: pd.DataFrame) -> float:
        """추세 일관성 확인
        
        Args:
            ohlcv_data: OHLCV 데이터
            
        Returns:
            float: 추세 일관성 (0 또는 1)
        """
        try:
            if len(ohlcv_data) < 70:
                return 0.0
            
            # 각 기간별 이동평균 기울기 계산
            short_slope = self._calculate_ma_slope(ohlcv_data, 5, 3)
            medium_slope = self._calculate_ma_slope(ohlcv_data, 20, 5)
            long_slope = self._calculate_ma_slope(ohlcv_data, 60, 10)
            
            # 모든 기울기가 같은 방향인지 확인
            positive_trend = short_slope > 0 and medium_slope > 0 and long_slope > 0
            negative_trend = short_slope < 0 and medium_slope < 0 and long_slope < 0
            
            return 1.0 if (positive_trend or negative_trend) else 0.0
            
        except Exception as e:
            self._logger.error(f"추세 일관성 확인 오류: {e}")
            return 0.0
    
    def _calculate_slope_angle(self, ohlcv_data: pd.DataFrame) -> float:
        """기울기 각도 계산
        
        Args:
            ohlcv_data: OHLCV 데이터
            
        Returns:
            float: 기울기 각도 (도)
        """
        try:
            # 5일 가격 기울기를 각도로 변환
            slope = self._calculate_price_slope(ohlcv_data, 5)
            
            # 백분율을 실제 기울기로 변환
            actual_slope = slope / 100
            
            # 아크탄젠트로 각도 계산 (라디안 -> 도)
            angle = np.arctan(actual_slope) * 180 / np.pi
            
            return angle
            
        except Exception as e:
            self._logger.error(f"기울기 각도 계산 오류: {e}")
            return 0.0
    
    def _get_slope_strength_score(self, ohlcv_data: pd.DataFrame) -> float:
        """기울기 강도 점수 계산
        
        Args:
            ohlcv_data: OHLCV 데이터
            
        Returns:
            float: 기울기 강도 점수 (0-100)
        """
        try:
            # 5일 가격 기울기 기준
            slope = self._calculate_price_slope(ohlcv_data, 5)
            
            # 기울기 강도별 점수
            if slope > 1.0:
                return 100.0  # 매우 강한 상승
            elif slope > 0.5:
                return 80.0   # 강한 상승
            elif slope > 0.3:
                return 75.0   # 약한 상승
            elif slope > 0.1:
                return 60.0   # 미약한 상승
            elif slope > -0.1:
                return 50.0   # 중립
            elif slope > -0.3:
                return 40.0   # 미약한 하락
            elif slope > -0.5:
                return 25.0   # 약한 하락
            elif slope > -1.0:
                return 20.0   # 강한 하락
            else:
                return 0.0    # 매우 강한 하락
                
        except Exception as e:
            self._logger.error(f"기울기 강도 점수 계산 오류: {e}")
            return 50.0
    
    def extract_features_from_stock_data(self, stock_data: Dict) -> SlopeFeatures:
        """
        주식 데이터에서 기울기 피처 추출
        
        Args:
            stock_data: 주식 데이터 딕셔너리
            
        Returns:
            SlopeFeatures: 추출된 기울기 피처
        """
        try:
            # OHLCV 데이터 생성
            ohlcv_data = self._generate_ohlcv_data(stock_data)
            
            if ohlcv_data is None:
                self._logger.warning("OHLCV 데이터 생성 실패")
                return SlopeFeatures()
                
            return self.extract_features(ohlcv_data)
            
        except Exception as e:
            self._logger.error(f"주식 데이터에서 기울기 피처 추출 오류: {e}")
            return SlopeFeatures()
    
    def _generate_ohlcv_data(self, stock_data: Dict) -> Optional[pd.DataFrame]:
        """주식 데이터로부터 OHLCV DataFrame 생성
        
        Args:
            stock_data: 주식 데이터 딕셔너리
            
        Returns:
            Optional[pd.DataFrame]: OHLCV 데이터프레임
        """
        try:
            current_price = stock_data.get("current_price", 0.0)
            volume_ratio = stock_data.get("volume_ratio", 1.0)
            
            if current_price <= 0:
                return None
                
            # 더미 OHLCV 데이터 생성 (실제로는 API에서 가져와야 함)
            # 70일간의 임시 데이터 생성
            dates = pd.date_range(end=datetime.now().date(), periods=70, freq='D')
            prices = []
            volumes = []
            
            # 현재가 기준으로 과거 70일간 가격 시뮬레이션
            base_price = current_price * 0.90  # 시작가는 현재가의 90%
            price = base_price
            base_volume = 2000000  # 기본 거래량
            
            for i in range(70):
                # 가격 변화 시뮬레이션 (상승 추세)
                change = np.random.normal(0.004, 0.020)  # 평균 0.4% 상승, 표준편차 2.0%
                price *= (1 + change)
                prices.append(price)
                
                # 거래량 시뮬레이션
                volume_multiplier = 1.0 + (volume_ratio - 1.0) * 0.15
                volume = base_volume * volume_multiplier * np.random.uniform(0.5, 2.0)
                volumes.append(volume)
            
            # 마지막 가격을 현재가로 조정
            prices[-1] = current_price
            
            # OHLCV 데이터프레임 생성
            ohlcv_data = pd.DataFrame({
                'date': dates,
                'open': [p * 0.99 for p in prices],
                'high': [p * 1.02 for p in prices],
                'low': [p * 0.98 for p in prices],
                'close': prices,
                'volume': volumes
            })
            
            ohlcv_data.set_index('date', inplace=True)
            
            return ohlcv_data
            
        except Exception as e:
            self._logger.error(f"OHLCV 데이터 생성 오류: {e}")
            return None
    
    def get_feature_names(self) -> List[str]:
        """기울기 피처 이름 목록 반환
        
        Returns:
            List[str]: 피처 이름 리스트
        """
        return [
            'price_slope_5d',
            'price_slope_20d',
            'ma5_slope',
            'ma20_slope',
            'ma60_slope',
            'slope_acceleration',
            'trend_consistency',
            'slope_angle',
            'slope_strength_score'
        ]
    
    def get_feature_descriptions(self) -> Dict[str, str]:
        """기울기 피처 설명 반환
        
        Returns:
            Dict[str, str]: 피처 이름과 설명
        """
        return {
            'price_slope_5d': '5일 가격 기울기 (백분율)',
            'price_slope_20d': '20일 가격 기울기 (백분율)',
            'ma5_slope': '5일 이동평균 기울기 (백분율)',
            'ma20_slope': '20일 이동평균 기울기 (백분율)',
            'ma60_slope': '60일 이동평균 기울기 (백분율)',
            'slope_acceleration': '기울기 가속도 (백분율)',
            'trend_consistency': '추세 일관성 (0 또는 1)',
            'slope_angle': '기울기 각도 (도)',
            'slope_strength_score': '기울기 강도 점수 (0-100)'
        } 