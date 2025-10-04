"""
Volume indicators module.
"""

import pandas as pd
import numpy as np
from typing import Union, Dict, List
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

class VolumePriceAnalyzer(Indicator):
    """거래량-가격 조합 분석 지표"""
    
    def calculate_volume_price_correlation(self, period: int = 20) -> float:
        """거래량-가격 변화 상관관계 계산
        
        Args:
            period: 분석 기간
            
        Returns:
            float: 상관관계 (-1 ~ 1)
        """
        if len(self.data) < period:
            return 0.0
            
        # 가격 변화율과 거래량 변화율 계산
        price_changes = self.data['close'].pct_change()
        volume_changes = self.data['volume'].pct_change()
        
        # 최근 period 기간의 상관관계 계산
        recent_price_changes = price_changes.tail(period)
        recent_volume_changes = volume_changes.tail(period)
        
        correlation = recent_price_changes.corr(recent_volume_changes)
        
        return correlation if not pd.isna(correlation) else 0.0
    
    def calculate_volume_price_divergence(self, period: int = 10) -> Dict[str, float]:
        """거래량-가격 다이버전스 분석
        
        Args:
            period: 분석 기간
            
        Returns:
            Dict: 다이버전스 분석 결과
        """
        if len(self.data) < period * 2:
            return {"divergence_score": 0.0, "signal": "neutral"}
            
        # 최근 기간과 이전 기간 비교
        recent_data = self.data.tail(period)
        previous_data = self.data.iloc[-period*2:-period]
        
        # 가격 추세 계산
        recent_price_trend = (recent_data['close'].iloc[-1] - recent_data['close'].iloc[0]) / recent_data['close'].iloc[0]
        previous_price_trend = (previous_data['close'].iloc[-1] - previous_data['close'].iloc[0]) / previous_data['close'].iloc[0]
        
        # 거래량 추세 계산
        recent_volume_trend = (recent_data['volume'].mean() - previous_data['volume'].mean()) / previous_data['volume'].mean()
        
        # 다이버전스 스코어 계산
        price_direction = 1 if recent_price_trend > previous_price_trend else -1
        volume_direction = 1 if recent_volume_trend > 0 else -1
        
        divergence_score = abs(recent_price_trend - recent_volume_trend)
        
        # 신호 판단
        if price_direction != volume_direction:
            signal = "bearish_divergence" if price_direction > 0 else "bullish_divergence"
        else:
            signal = "neutral"
        
        return {
            "divergence_score": divergence_score,
            "signal": signal,
            "price_trend": recent_price_trend,
            "volume_trend": recent_volume_trend
        }
    
    def calculate_volume_price_momentum(self, short_period: int = 5, long_period: int = 20) -> Dict[str, float]:
        """거래량-가격 모멘텀 분석
        
        Args:
            short_period: 단기 기간
            long_period: 장기 기간
            
        Returns:
            Dict: 모멘텀 분석 결과
        """
        if len(self.data) < long_period:
            return {"momentum_score": 0.0, "strength": "neutral"}
            
        # 단기 및 장기 거래량 평균
        short_volume_avg = self.data['volume'].tail(short_period).mean()
        long_volume_avg = self.data['volume'].tail(long_period).mean()
        
        # 단기 및 장기 가격 변화율
        short_price_change = (self.data['close'].iloc[-1] - self.data['close'].iloc[-short_period]) / self.data['close'].iloc[-short_period]
        long_price_change = (self.data['close'].iloc[-1] - self.data['close'].iloc[-long_period]) / self.data['close'].iloc[-long_period]
        
        # 거래량 비율
        volume_ratio = short_volume_avg / long_volume_avg if long_volume_avg > 0 else 1.0
        
        # 모멘텀 스코어 계산
        momentum_score = (short_price_change + long_price_change) * volume_ratio
        
        # 강도 판단
        if momentum_score > 0.05:
            strength = "strong_bullish"
        elif momentum_score > 0.02:
            strength = "moderate_bullish"
        elif momentum_score > -0.02:
            strength = "neutral"
        elif momentum_score > -0.05:
            strength = "moderate_bearish"
        else:
            strength = "strong_bearish"
        
        return {
            "momentum_score": momentum_score,
            "strength": strength,
            "volume_ratio": volume_ratio,
            "price_change_short": short_price_change,
            "price_change_long": long_price_change
        }
    
    def calculate(self, analysis_type: str = "comprehensive") -> Union[float, Dict]:
        """거래량-가격 분석 실행
        
        Args:
            analysis_type: 분석 유형
            
        Returns:
            Union[float, Dict]: 분석 결과
        """
        if analysis_type == "comprehensive":
            return {
                "correlation": self.calculate_volume_price_correlation(),
                "divergence": self.calculate_volume_price_divergence(),
                "momentum": self.calculate_volume_price_momentum()
            }
        elif analysis_type == "correlation":
            return self.calculate_volume_price_correlation()
        elif analysis_type == "divergence":
            return self.calculate_volume_price_divergence()
        elif analysis_type == "momentum":
            return self.calculate_volume_price_momentum()
        else:
            raise ValueError(f"지원하지 않는 분석 유형: {analysis_type}")

class RelativeVolumeStrength(Indicator):
    """상대적 거래량 강도 지표"""
    
    def __init__(self, data: pd.DataFrame, market_data: pd.DataFrame = None, sector_data: pd.DataFrame = None):
        """
        Args:
            data: 개별 종목 OHLCV 데이터
            market_data: 시장 전체 데이터 (선택적)
            sector_data: 섹터 데이터 (선택적)
        """
        super().__init__(data)
        self.market_data = market_data
        self.sector_data = sector_data
    
    def calculate_relative_volume_ratio(self, period: int = 20) -> Dict[str, float]:
        """상대적 거래량 비율 계산
        
        Args:
            period: 분석 기간
            
        Returns:
            Dict: 상대적 거래량 비율
        """
        if len(self.data) < period:
            return {"vs_own_avg": 1.0, "vs_market": 1.0, "vs_sector": 1.0}
            
        # 자기 자신의 평균 대비
        current_volume = self.data['volume'].iloc[-1]
        avg_volume = self.data['volume'].tail(period).mean()
        vs_own_avg = current_volume / avg_volume if avg_volume > 0 else 1.0
        
        # 시장 평균 대비 (데이터가 있는 경우)
        vs_market = 1.0
        if self.market_data is not None and len(self.market_data) >= period:
            market_volume_ratio = self.market_data['volume'].tail(period).mean()
            if market_volume_ratio > 0:
                vs_market = vs_own_avg / (market_volume_ratio / market_volume_ratio)
        
        # 섹터 평균 대비 (데이터가 있는 경우)
        vs_sector = 1.0
        if self.sector_data is not None and len(self.sector_data) >= period:
            sector_volume_ratio = self.sector_data['volume'].tail(period).mean()
            if sector_volume_ratio > 0:
                vs_sector = vs_own_avg / (sector_volume_ratio / sector_volume_ratio)
        
        return {
            "vs_own_avg": vs_own_avg,
            "vs_market": vs_market,
            "vs_sector": vs_sector
        }
    
    def calculate_volume_rank(self, period: int = 60) -> Dict[str, float]:
        """거래량 순위 계산
        
        Args:
            period: 분석 기간
            
        Returns:
            Dict: 거래량 순위 정보
        """
        if len(self.data) < period:
            return {"percentile": 50.0, "rank": 0.5}
            
        # 최근 period 기간의 거래량 데이터
        volumes = self.data['volume'].tail(period)
        current_volume = volumes.iloc[-1]
        
        # 백분위 계산
        percentile = (volumes < current_volume).sum() / len(volumes) * 100
        
        # 0-1 스케일 랭크
        rank = percentile / 100
        
        return {
            "percentile": percentile,
            "rank": rank,
            "current_volume": current_volume,
            "avg_volume": volumes.mean(),
            "max_volume": volumes.max(),
            "min_volume": volumes.min()
        }
    
    def calculate_volume_intensity(self, price_threshold: float = 0.02) -> Dict[str, float]:
        """거래량 강도 계산
        
        Args:
            price_threshold: 가격 변화 임계값
            
        Returns:
            Dict: 거래량 강도 정보
        """
        if len(self.data) < 2:
            return {"intensity": 0.0, "efficiency": 0.0}
            
        # 가격 변화율
        price_change = self.data['close'].pct_change().iloc[-1]
        
        # 거래량 강도 = 거래량 / 가격 변화율
        current_volume = self.data['volume'].iloc[-1]
        avg_volume = self.data['volume'].tail(20).mean()
        
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
        
        # 가격 변화가 임계값 이상인 경우에만 강도 계산
        if abs(price_change) > price_threshold:
            intensity = volume_ratio / abs(price_change)
        else:
            intensity = volume_ratio
        
        # 효율성 = 가격 변화 / 거래량 비율
        efficiency = abs(price_change) / volume_ratio if volume_ratio > 0 else 0.0
        
        return {
            "intensity": intensity,
            "efficiency": efficiency,
            "volume_ratio": volume_ratio,
            "price_change": price_change
        }
    
    def calculate(self, analysis_type: str = "comprehensive") -> Union[float, Dict]:
        """상대적 거래량 강도 분석 실행
        
        Args:
            analysis_type: 분석 유형
            
        Returns:
            Union[float, Dict]: 분석 결과
        """
        if analysis_type == "comprehensive":
            return {
                "relative_ratio": self.calculate_relative_volume_ratio(),
                "rank": self.calculate_volume_rank(),
                "intensity": self.calculate_volume_intensity()
            }
        elif analysis_type == "ratio":
            return self.calculate_relative_volume_ratio()
        elif analysis_type == "rank":
            return self.calculate_volume_rank()
        elif analysis_type == "intensity":
            return self.calculate_volume_intensity()
        else:
            raise ValueError(f"지원하지 않는 분석 유형: {analysis_type}")

class VolumeClusterAnalyzer(Indicator):
    """거래량 클러스터링 분석 지표"""
    
    def detect_volume_clusters(self, min_cluster_size: int = 3, volume_threshold: float = 1.5) -> List[Dict]:
        """거래량 클러스터 감지
        
        Args:
            min_cluster_size: 최소 클러스터 크기
            volume_threshold: 거래량 임계값 (평균 대비 배수)
            
        Returns:
            List[Dict]: 감지된 클러스터 정보
        """
        if len(self.data) < min_cluster_size * 2:
            return []
            
        # 거래량 평균 계산
        avg_volume = self.data['volume'].mean()
        
        # 임계값 이상의 거래량 지점 찾기
        high_volume_points = self.data['volume'] > (avg_volume * volume_threshold)
        
        # 연속된 고거래량 구간 찾기
        clusters = []
        cluster_start = None
        
        for i, is_high in enumerate(high_volume_points):
            if is_high and cluster_start is None:
                cluster_start = i
            elif not is_high and cluster_start is not None:
                cluster_end = i - 1
                cluster_size = cluster_end - cluster_start + 1
                
                if cluster_size >= min_cluster_size:
                    cluster_data = self.data.iloc[cluster_start:cluster_end+1]
                    clusters.append({
                        "start_index": cluster_start,
                        "end_index": cluster_end,
                        "size": cluster_size,
                        "avg_volume": cluster_data['volume'].mean(),
                        "max_volume": cluster_data['volume'].max(),
                        "price_start": cluster_data['close'].iloc[0],
                        "price_end": cluster_data['close'].iloc[-1],
                        "price_change": (cluster_data['close'].iloc[-1] - cluster_data['close'].iloc[0]) / cluster_data['close'].iloc[0]
                    })
                
                cluster_start = None
        
        return clusters
    
    def analyze_volume_distribution(self, bins: int = 10) -> Dict[str, np.ndarray]:
        """거래량 분포 분석
        
        Args:
            bins: 히스토그램 구간 수
            
        Returns:
            Dict: 분포 분석 결과
        """
        volumes = self.data['volume'].values
        
        # 히스토그램 계산
        hist, bin_edges = np.histogram(volumes, bins=bins)
        
        # 통계 정보
        stats = {
            "histogram": hist,
            "bin_edges": bin_edges,
            "mean": np.mean(volumes),
            "std": np.std(volumes),
            "median": np.median(volumes),
            "skewness": self._calculate_skewness(volumes),
            "kurtosis": self._calculate_kurtosis(volumes)
        }
        
        return stats
    
    def _calculate_skewness(self, data: np.ndarray) -> float:
        """왜도 계산"""
        mean = np.mean(data)
        std = np.std(data)
        if std == 0:
            return 0.0
        return np.mean(((data - mean) / std) ** 3)
    
    def _calculate_kurtosis(self, data: np.ndarray) -> float:
        """첨도 계산"""
        mean = np.mean(data)
        std = np.std(data)
        if std == 0:
            return 0.0
        return np.mean(((data - mean) / std) ** 4) - 3
    
    def detect_volume_anomalies(self, threshold: float = 3.0) -> List[Dict]:
        """거래량 이상치 감지
        
        Args:
            threshold: 이상치 임계값 (표준편차 배수)
            
        Returns:
            List[Dict]: 감지된 이상치 정보
        """
        volumes = self.data['volume']
        mean_volume = volumes.mean()
        std_volume = volumes.std()
        
        if std_volume == 0:
            return []
        
        # Z-score 계산
        z_scores = (volumes - mean_volume) / std_volume
        
        # 이상치 감지
        anomalies = []
        for i, z_score in enumerate(z_scores):
            if abs(z_score) > threshold:
                anomalies.append({
                    "index": i,
                    "date": self.data.index[i] if hasattr(self.data, 'index') else i,
                    "volume": volumes.iloc[i],
                    "z_score": z_score,
                    "price": self.data['close'].iloc[i],
                    "anomaly_type": "high" if z_score > 0 else "low"
                })
        
        return anomalies
    
    def calculate(self, analysis_type: str = "comprehensive") -> Union[List, Dict]:
        """거래량 클러스터 분석 실행
        
        Args:
            analysis_type: 분석 유형
            
        Returns:
            Union[List, Dict]: 분석 결과
        """
        if analysis_type == "comprehensive":
            return {
                "clusters": self.detect_volume_clusters(),
                "distribution": self.analyze_volume_distribution(),
                "anomalies": self.detect_volume_anomalies()
            }
        elif analysis_type == "clusters":
            return self.detect_volume_clusters()
        elif analysis_type == "distribution":
            return self.analyze_volume_distribution()
        elif analysis_type == "anomalies":
            return self.detect_volume_anomalies()
        else:
            raise ValueError(f"지원하지 않는 분석 유형: {analysis_type}") 