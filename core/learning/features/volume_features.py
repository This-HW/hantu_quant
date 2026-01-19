"""
Phase 4 AI 학습 시스템 - 볼륨 피처 엔지니어링 모듈

볼륨 관련 피처 추출:
1. volume_price_correlation: 거래량-가격 상관관계
2. volume_price_divergence: 거래량-가격 다이버전스
3. volume_momentum_score: 거래량 모멘텀 점수
4. relative_volume_strength: 상대적 거래량 강도
5. volume_rank_percentile: 거래량 순위 백분위
6. volume_intensity: 거래량 강도
7. volume_cluster_count: 거래량 클러스터 개수
8. volume_anomaly_score: 거래량 이상치 점수
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

from core.utils.log_utils import get_logger
from hantu_common.indicators.volume import (
    VolumePriceAnalyzer, 
    RelativeVolumeStrength, 
    VolumeClusterAnalyzer
)

logger = get_logger(__name__)

@dataclass
class VolumeFeatures:
    """볼륨 피처 데이터 클래스"""
    volume_price_correlation: float = 0.0
    volume_price_divergence: float = 0.0
    volume_momentum_score: float = 0.0
    relative_volume_strength: float = 0.0
    volume_rank_percentile: float = 0.0
    volume_intensity: float = 0.0
    volume_cluster_count: float = 0.0
    volume_anomaly_score: float = 0.0
    
    def to_dict(self) -> Dict[str, float]:
        """딕셔너리 형태로 변환"""
        return {
            'volume_price_correlation': self.volume_price_correlation,
            'volume_price_divergence': self.volume_price_divergence,
            'volume_momentum_score': self.volume_momentum_score,
            'relative_volume_strength': self.relative_volume_strength,
            'volume_rank_percentile': self.volume_rank_percentile,
            'volume_intensity': self.volume_intensity,
            'volume_cluster_count': self.volume_cluster_count,
            'volume_anomaly_score': self.volume_anomaly_score
        }

class VolumeFeatureExtractor:
    """볼륨 피처 추출기"""
    
    def __init__(self):
        """볼륨 피처 추출기 초기화"""
        self._logger = logger
        self._min_data_length = 60  # 최소 필요 데이터 길이
        
    def extract_features(self, ohlcv_data: pd.DataFrame) -> VolumeFeatures:
        """
        OHLCV 데이터에서 볼륨 피처 추출
        
        Args:
            ohlcv_data: OHLCV 데이터프레임
            
        Returns:
            VolumeFeatures: 추출된 볼륨 피처
        """
        try:
            if ohlcv_data is None or len(ohlcv_data) < self._min_data_length:
                self._logger.warning(f"볼륨 피처 추출을 위한 데이터 부족: {len(ohlcv_data) if ohlcv_data is not None else 0}")
                return VolumeFeatures()
            
            # 볼륨 지표 객체 생성
            VolumePriceAnalyzer(ohlcv_data)
            relative_volume_strength = RelativeVolumeStrength(ohlcv_data)
            volume_cluster_analyzer = VolumeClusterAnalyzer(ohlcv_data)
            
            # 각 피처 계산
            features = VolumeFeatures()
            
            # 1. 거래량-가격 상관관계
            features.volume_price_correlation = self._calculate_volume_price_correlation(ohlcv_data)
            
            # 2. 거래량-가격 다이버전스
            features.volume_price_divergence = self._calculate_volume_price_divergence(ohlcv_data)
            
            # 3. 거래량 모멘텀 점수
            features.volume_momentum_score = self._calculate_volume_momentum_score(ohlcv_data)
            
            # 4. 상대적 거래량 강도
            features.relative_volume_strength = self._calculate_relative_volume_strength(relative_volume_strength)
            
            # 5. 거래량 순위 백분위
            features.volume_rank_percentile = self._calculate_volume_rank_percentile(relative_volume_strength)
            
            # 6. 거래량 강도
            features.volume_intensity = self._calculate_volume_intensity(relative_volume_strength)
            
            # 7. 거래량 클러스터 개수
            features.volume_cluster_count = self._calculate_volume_cluster_count(volume_cluster_analyzer)
            
            # 8. 거래량 이상치 점수
            features.volume_anomaly_score = self._calculate_volume_anomaly_score(volume_cluster_analyzer)
            
            self._logger.debug(f"볼륨 피처 추출 완료: {features.to_dict()}")
            return features
            
        except Exception as e:
            self._logger.error(f"볼륨 피처 추출 중 오류 발생: {e}", exc_info=True)
            return VolumeFeatures()
    
    def _calculate_volume_price_correlation(self, ohlcv_data: pd.DataFrame) -> float:
        """거래량-가격 변화 상관관계 계산
        
        Args:
            ohlcv_data: OHLCV 데이터
            
        Returns:
            float: 상관관계 (-1 ~ 1)
        """
        try:
            if len(ohlcv_data) < 20:
                return 0.0
            
            # 가격 변화율과 거래량 변화율 계산
            price_changes = ohlcv_data['close'].pct_change().tail(20)
            volume_changes = ohlcv_data['volume'].pct_change().tail(20)
            
            # 상관관계 계산
            correlation = price_changes.corr(volume_changes)
            
            # 타입 확인 및 반환
            if pd.isna(correlation):
                return 0.0
            return float(correlation)
            
        except Exception as e:
            self._logger.error(f"거래량-가격 상관관계 계산 오류: {e}", exc_info=True)
            return 0.0
    
    def _calculate_volume_price_divergence(self, ohlcv_data: pd.DataFrame) -> float:
        """거래량-가격 다이버전스 점수 계산
        
        Args:
            ohlcv_data: OHLCV 데이터
            
        Returns:
            float: 다이버전스 점수 (0-100)
        """
        try:
            if len(ohlcv_data) < 20:
                return 50.0  # 중립
            
            # 최근 10일과 이전 10일 비교
            recent_data = ohlcv_data.tail(10)
            previous_data = ohlcv_data.iloc[-20:-10]
            
            # 가격 추세 계산
            recent_price_trend = (recent_data['close'].iloc[-1] - recent_data['close'].iloc[0]) / recent_data['close'].iloc[0]
            previous_price_trend = (previous_data['close'].iloc[-1] - previous_data['close'].iloc[0]) / previous_data['close'].iloc[0]
            
            # 거래량 추세 계산
            recent_volume_trend = (recent_data['volume'].mean() - previous_data['volume'].mean()) / previous_data['volume'].mean()
            
            # 다이버전스 점수 계산
            price_direction = 1 if recent_price_trend > previous_price_trend else -1
            volume_direction = 1 if recent_volume_trend > 0 else -1
            
            if price_direction != volume_direction:
                return 75.0 if price_direction > 0 else 25.0  # bearish/bullish divergence
            else:
                return 50.0  # neutral
                
        except Exception as e:
            self._logger.error(f"거래량-가격 다이버전스 계산 오류: {e}", exc_info=True)
            return 50.0
    
    def _calculate_volume_momentum_score(self, ohlcv_data: pd.DataFrame) -> float:
        """거래량 모멘텀 점수 계산
        
        Args:
            ohlcv_data: OHLCV 데이터
            
        Returns:
            float: 모멘텀 점수 (0-100)
        """
        try:
            if len(ohlcv_data) < 20:
                return 50.0
            
            # 단기 및 장기 거래량 평균
            short_volume_avg = ohlcv_data['volume'].tail(5).mean()
            long_volume_avg = ohlcv_data['volume'].tail(20).mean()
            
            # 단기 및 장기 가격 변화율
            short_price_change = (ohlcv_data['close'].iloc[-1] - ohlcv_data['close'].iloc[-5]) / ohlcv_data['close'].iloc[-5]
            long_price_change = (ohlcv_data['close'].iloc[-1] - ohlcv_data['close'].iloc[-20]) / ohlcv_data['close'].iloc[-20]
            
            # 거래량 비율
            volume_ratio = short_volume_avg / long_volume_avg if long_volume_avg > 0 else 1.0
            
            # 모멘텀 스코어 계산
            momentum_score = (short_price_change + long_price_change) * volume_ratio
            
            # 0-100 스케일로 변환
            if momentum_score > 0.05:
                return 100.0  # strong_bullish
            elif momentum_score > 0.02:
                return 75.0   # moderate_bullish
            elif momentum_score > -0.02:
                return 50.0   # neutral
            elif momentum_score > -0.05:
                return 25.0   # moderate_bearish
            else:
                return 0.0    # strong_bearish
                
        except Exception as e:
            self._logger.error(f"거래량 모멘텀 점수 계산 오류: {e}", exc_info=True)
            return 50.0
    
    def _calculate_relative_volume_strength(self, relative_volume_strength: RelativeVolumeStrength) -> float:
        """상대적 거래량 강도 계산
        
        Args:
            relative_volume_strength: 상대적 거래량 강도 지표
            
        Returns:
            float: 상대적 거래량 강도 (0-100)
        """
        try:
            # 상대적 거래량 비율 계산
            ratios = relative_volume_strength.calculate_relative_volume_ratio()
            vs_own_avg = ratios.get('vs_own_avg', 1.0)
            
            # 0-100 스케일로 변환
            if vs_own_avg >= 3.0:
                return 100.0  # 극도로 높은 거래량
            elif vs_own_avg >= 2.0:
                return 80.0   # 매우 높은 거래량
            elif vs_own_avg >= 1.5:
                return 70.0   # 높은 거래량
            elif vs_own_avg >= 1.2:
                return 60.0   # 약간 높은 거래량
            elif vs_own_avg >= 0.8:
                return 50.0   # 평균적인 거래량
            elif vs_own_avg >= 0.5:
                return 30.0   # 낮은 거래량
            else:
                return 10.0   # 매우 낮은 거래량
                
        except Exception as e:
            self._logger.error(f"상대적 거래량 강도 계산 오류: {e}", exc_info=True)
            return 50.0
    
    def _calculate_volume_rank_percentile(self, relative_volume_strength: RelativeVolumeStrength) -> float:
        """거래량 순위 백분위 계산
        
        Args:
            relative_volume_strength: 상대적 거래량 강도 지표
            
        Returns:
            float: 거래량 순위 백분위 (0-100)
        """
        try:
            # 거래량 순위 정보 계산
            rank_info = relative_volume_strength.calculate_volume_rank()
            percentile = rank_info.get('percentile', 50.0)
            
            return percentile
            
        except Exception as e:
            self._logger.error(f"거래량 순위 백분위 계산 오류: {e}", exc_info=True)
            return 50.0
    
    def _calculate_volume_intensity(self, relative_volume_strength: RelativeVolumeStrength) -> float:
        """거래량 강도 계산
        
        Args:
            relative_volume_strength: 상대적 거래량 강도 지표
            
        Returns:
            float: 거래량 강도 (0-100)
        """
        try:
            # 거래량 강도 정보 계산
            intensity_info = relative_volume_strength.calculate_volume_intensity()
            intensity = intensity_info.get('intensity', 1.0)
            
            # 0-100 스케일로 변환
            if intensity >= 5.0:
                return 100.0
            elif intensity >= 3.0:
                return 80.0
            elif intensity >= 2.0:
                return 60.0
            elif intensity >= 1.0:
                return 40.0
            else:
                return 20.0
                
        except Exception as e:
            self._logger.error(f"거래량 강도 계산 오류: {e}", exc_info=True)
            return 40.0
    
    def _calculate_volume_cluster_count(self, volume_cluster_analyzer: VolumeClusterAnalyzer) -> float:
        """거래량 클러스터 개수 계산
        
        Args:
            volume_cluster_analyzer: 거래량 클러스터 분석기
            
        Returns:
            float: 클러스터 개수 (0-20)
        """
        try:
            # 거래량 클러스터 감지
            clusters = volume_cluster_analyzer.detect_volume_clusters()
            cluster_count = len(clusters)
            
            # 클러스터 개수를 0-20 범위로 제한
            return min(float(cluster_count), 20.0)
            
        except Exception as e:
            self._logger.error(f"거래량 클러스터 개수 계산 오류: {e}", exc_info=True)
            return 0.0
    
    def _calculate_volume_anomaly_score(self, volume_cluster_analyzer: VolumeClusterAnalyzer) -> float:
        """거래량 이상치 점수 계산
        
        Args:
            volume_cluster_analyzer: 거래량 클러스터 분석기
            
        Returns:
            float: 이상치 점수 (0-100)
        """
        try:
            # 거래량 이상치 감지
            anomalies = volume_cluster_analyzer.detect_volume_anomalies()
            
            if not anomalies:
                return 0.0
            
            # 최근 이상치 점수 계산
            recent_anomalies = [a for a in anomalies if a['index'] >= len(volume_cluster_analyzer.data) - 10]
            
            if not recent_anomalies:
                return 0.0
            
            # 이상치 강도 계산
            max_z_score = max(abs(a['z_score']) for a in recent_anomalies)
            
            # 0-100 스케일로 변환
            if max_z_score >= 3.0:
                return 100.0  # 극도 이상치
            elif max_z_score >= 2.5:
                return 80.0   # 강한 이상치
            elif max_z_score >= 2.0:
                return 60.0   # 보통 이상치
            elif max_z_score >= 1.5:
                return 40.0   # 약한 이상치
            else:
                return 20.0   # 미약한 이상치
                
        except Exception as e:
            self._logger.error(f"거래량 이상치 점수 계산 오류: {e}", exc_info=True)
            return 0.0
    
    def extract_features_from_stock_data(self, stock_data: Dict) -> VolumeFeatures:
        """
        주식 데이터에서 볼륨 피처 추출
        
        Args:
            stock_data: 주식 데이터 딕셔너리
            
        Returns:
            VolumeFeatures: 추출된 볼륨 피처
        """
        try:
            # OHLCV 데이터 생성
            ohlcv_data = self._generate_ohlcv_data(stock_data)
            
            if ohlcv_data is None:
                self._logger.warning("OHLCV 데이터 생성 실패")
                return VolumeFeatures()
                
            return self.extract_features(ohlcv_data)
            
        except Exception as e:
            self._logger.error(f"주식 데이터에서 볼륨 피처 추출 오류: {e}", exc_info=True)
            return VolumeFeatures()
    
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
            # 60일간의 임시 데이터 생성
            dates = pd.date_range(end=datetime.now().date(), periods=60, freq='D')
            prices = []
            volumes = []
            
            # 현재가 기준으로 과거 60일간 가격 시뮬레이션
            base_price = current_price * 0.92  # 시작가는 현재가의 92%
            price = base_price
            base_volume = 1800000  # 기본 거래량
            
            for i in range(60):
                # 가격 변화 시뮬레이션 (상승 추세)
                change = np.random.normal(0.003, 0.018)  # 평균 0.3% 상승, 표준편차 1.8%
                price *= (1 + change)
                prices.append(price)
                
                # 거래량 시뮬레이션 (거래량 비율 반영)
                volume_multiplier = 1.0 + (volume_ratio - 1.0) * 0.12
                volume = base_volume * volume_multiplier * np.random.uniform(0.6, 1.8)
                volumes.append(volume)
            
            # 마지막 가격을 현재가로 조정
            prices[-1] = current_price
            
            # OHLCV 데이터프레임 생성
            ohlcv_data = pd.DataFrame({
                'date': dates,
                'open': [p * 0.995 for p in prices],
                'high': [p * 1.015 for p in prices],
                'low': [p * 0.985 for p in prices],
                'close': prices,
                'volume': volumes
            })
            
            ohlcv_data.set_index('date', inplace=True)
            
            return ohlcv_data
            
        except Exception as e:
            self._logger.error(f"OHLCV 데이터 생성 오류: {e}", exc_info=True)
            return None
    
    def get_feature_names(self) -> List[str]:
        """볼륨 피처 이름 목록 반환
        
        Returns:
            List[str]: 피처 이름 리스트
        """
        return [
            'volume_price_correlation',
            'volume_price_divergence',
            'volume_momentum_score',
            'relative_volume_strength',
            'volume_rank_percentile',
            'volume_intensity',
            'volume_cluster_count',
            'volume_anomaly_score'
        ]
    
    def get_feature_descriptions(self) -> Dict[str, str]:
        """볼륨 피처 설명 반환
        
        Returns:
            Dict[str, str]: 피처 이름과 설명
        """
        return {
            'volume_price_correlation': '거래량-가격 상관관계 (-1 ~ 1)',
            'volume_price_divergence': '거래량-가격 다이버전스 점수 (0-100)',
            'volume_momentum_score': '거래량 모멘텀 점수 (0-100)',
            'relative_volume_strength': '상대적 거래량 강도 (0-100)',
            'volume_rank_percentile': '거래량 순위 백분위 (0-100)',
            'volume_intensity': '거래량 강도 (0-100)',
            'volume_cluster_count': '거래량 클러스터 개수 (0-20)',
            'volume_anomaly_score': '거래량 이상치 점수 (0-100)'
        } 