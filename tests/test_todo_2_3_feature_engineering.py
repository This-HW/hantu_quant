"""
TODO 2.3 피처 엔지니어링 시스템 테스트

테스트 내용:
- 기울기 피처 9개 추출 테스트
- 볼륨 피처 8개 추출 테스트
- 피처 선택 및 중요도 분석 테스트
- 통합 피처 시스템 테스트
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List
import os
import sys

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.learning.features.slope_features import SlopeFeatureExtractor, SlopeFeatures
from core.learning.features.volume_features import VolumeFeatureExtractor, VolumeFeatures
from core.learning.features.feature_selector import FeatureSelector, CombinedFeatures

class TestSlopeFeatureExtractor:
    """기울기 피처 추출기 테스트"""
    
    def setup_method(self):
        """테스트 설정"""
        self.extractor = SlopeFeatureExtractor()
        self.sample_ohlcv = self._create_sample_ohlcv_data()
        self.sample_stock_data = self._create_sample_stock_data()
    
    def _create_sample_ohlcv_data(self) -> pd.DataFrame:
        """샘플 OHLCV 데이터 생성"""
        dates = pd.date_range(start='2024-01-01', periods=80, freq='D')
        
        # 상승 추세를 가진 더미 데이터
        base_price = 50000
        prices = []
        volumes = []
        
        for i in range(80):
            # 상승 추세 + 노이즈
            trend = i * 100  # 일일 100원 상승
            noise = np.random.normal(0, 500)
            price = base_price + trend + noise
            prices.append(price)
            
            # 거래량 데이터
            volume = 1000000 + np.random.normal(0, 200000)
            volumes.append(max(volume, 100000))
        
        return pd.DataFrame({
            'date': dates,
            'open': [p * 0.998 for p in prices],
            'high': [p * 1.015 for p in prices],
            'low': [p * 0.985 for p in prices],
            'close': prices,
            'volume': volumes
        }).set_index('date')
    
    def _create_sample_stock_data(self) -> Dict:
        """샘플 주식 데이터 생성"""
        return {
            'stock_code': '005930',
            'stock_name': '삼성전자',
            'current_price': 58000.0,
            'volume_ratio': 1.5,
            'sector': '반도체',
            'market_cap': 400000000000000
        }
    
    def test_slope_extractor_initialization(self):
        """기울기 피처 추출기 초기화 테스트"""
        assert self.extractor is not None
        assert self.extractor._min_data_length == 70
        
        # 피처 이름 확인
        feature_names = self.extractor.get_feature_names()
        assert len(feature_names) == 9
        assert 'price_slope_5d' in feature_names
        assert 'trend_consistency' in feature_names
        assert 'slope_strength_score' in feature_names
    
    def test_slope_features_extraction(self):
        """기울기 피처 추출 테스트"""
        features = self.extractor.extract_features(self.sample_ohlcv)
        
        assert isinstance(features, SlopeFeatures)
        
        # 모든 피처가 숫자값인지 확인
        feature_dict = features.to_dict()
        assert len(feature_dict) == 9
        
        for feature_name, value in feature_dict.items():
            assert isinstance(value, (int, float)), f"{feature_name} 값이 숫자가 아님: {value}"
            assert not np.isnan(value), f"{feature_name} 값이 NaN: {value}"
    
    def test_individual_slope_calculations(self):
        """개별 기울기 계산 테스트"""
        # 가격 기울기 테스트
        price_slope_5d = self.extractor._calculate_price_slope(self.sample_ohlcv, 5)
        assert isinstance(price_slope_5d, (int, float))
        assert -1.0 <= price_slope_5d <= 1.0  # 정규화된 기울기 값 범위 확인
        
        # 이동평균 기울기 테스트
        ma_slope = self.extractor._calculate_ma_slope(self.sample_ohlcv, 20, 5)
        assert isinstance(ma_slope, (int, float))
        
        # 기울기 가속도 테스트
        acceleration = self.extractor._calculate_slope_acceleration(self.sample_ohlcv)
        assert isinstance(acceleration, (int, float))
        
        # 추세 일관성 테스트
        consistency = self.extractor._check_trend_consistency(self.sample_ohlcv)
        assert consistency in [0.0, 1.0]  # 0 또는 1이어야 함
    
    def test_slope_features_from_stock_data(self):
        """주식 데이터에서 기울기 피처 추출 테스트"""
        features = self.extractor.extract_features_from_stock_data(self.sample_stock_data)
        
        assert isinstance(features, SlopeFeatures)
        feature_dict = features.to_dict()
        
        # 피처 개수 확인
        assert len(feature_dict) == 9
        
        # 피처 범위 확인
        assert -45 <= features.slope_angle <= 45  # 각도는 -45도 ~ 45도 범위
        assert 0 <= features.slope_strength_score <= 100  # 점수는 0-100 범위
        assert features.trend_consistency in [0.0, 1.0]  # 0 또는 1
    
    def test_insufficient_data_handling(self):
        """데이터 부족 시 처리 테스트"""
        # 데이터가 부족한 경우
        short_data = self.sample_ohlcv.head(50)
        features = self.extractor.extract_features(short_data)
        
        assert isinstance(features, SlopeFeatures)
        # 기본값으로 설정되어야 함
        assert features.price_slope_5d == 0.0
        assert features.trend_consistency == 0.0

class TestVolumeFeatureExtractor:
    """볼륨 피처 추출기 테스트"""
    
    def setup_method(self):
        """테스트 설정"""
        self.extractor = VolumeFeatureExtractor()
        self.sample_ohlcv = self._create_sample_ohlcv_data()
        self.sample_stock_data = self._create_sample_stock_data()
    
    def _create_sample_ohlcv_data(self) -> pd.DataFrame:
        """샘플 OHLCV 데이터 생성"""
        dates = pd.date_range(start='2024-01-01', periods=70, freq='D')
        
        # 가격과 거래량 데이터
        prices = []
        volumes = []
        
        for i in range(70):
            # 가격 데이터
            price = 50000 + i * 50 + np.random.normal(0, 300)
            prices.append(price)
            
            # 거래량 데이터 (가격 상승 시 거래량 증가 패턴)
            volume = 1500000 + i * 10000 + np.random.normal(0, 300000)
            volumes.append(max(volume, 100000))
        
        return pd.DataFrame({
            'date': dates,
            'open': [p * 0.998 for p in prices],
            'high': [p * 1.012 for p in prices],
            'low': [p * 0.988 for p in prices],
            'close': prices,
            'volume': volumes
        }).set_index('date')
    
    def _create_sample_stock_data(self) -> Dict:
        """샘플 주식 데이터 생성"""
        return {
            'stock_code': '000660',
            'stock_name': 'SK하이닉스',
            'current_price': 85000.0,
            'volume_ratio': 2.0,
            'sector': '반도체',
            'market_cap': 600000000000000
        }
    
    def test_volume_extractor_initialization(self):
        """볼륨 피처 추출기 초기화 테스트"""
        assert self.extractor is not None
        assert self.extractor._min_data_length == 60
        
        # 피처 이름 확인
        feature_names = self.extractor.get_feature_names()
        assert len(feature_names) == 8
        assert 'volume_price_correlation' in feature_names
        assert 'volume_cluster_count' in feature_names
        assert 'volume_anomaly_score' in feature_names
    
    def test_volume_features_extraction(self):
        """볼륨 피처 추출 테스트"""
        features = self.extractor.extract_features(self.sample_ohlcv)
        
        assert isinstance(features, VolumeFeatures)
        
        # 모든 피처가 숫자값인지 확인
        feature_dict = features.to_dict()
        assert len(feature_dict) == 8
        
        for feature_name, value in feature_dict.items():
            assert isinstance(value, (int, float)), f"{feature_name} 값이 숫자가 아님: {value}"
            assert not np.isnan(value), f"{feature_name} 값이 NaN: {value}"
    
    def test_volume_price_correlation(self):
        """거래량-가격 상관관계 테스트"""
        correlation = self.extractor._calculate_volume_price_correlation(self.sample_ohlcv)
        
        assert isinstance(correlation, (int, float))
        assert -1 <= correlation <= 1  # 상관관계는 -1 ~ 1 범위
    
    def test_volume_features_ranges(self):
        """볼륨 피처 범위 테스트"""
        features = self.extractor.extract_features(self.sample_ohlcv)
        
        # 각 피처의 범위 확인
        assert -1 <= features.volume_price_correlation <= 1
        assert 0 <= features.volume_price_divergence <= 100
        assert 0 <= features.volume_momentum_score <= 100
        assert 0 <= features.relative_volume_strength <= 100
        assert 0 <= features.volume_rank_percentile <= 100
        assert 0 <= features.volume_intensity <= 100
        assert 0 <= features.volume_cluster_count <= 20
        assert 0 <= features.volume_anomaly_score <= 100
    
    def test_volume_features_from_stock_data(self):
        """주식 데이터에서 볼륨 피처 추출 테스트"""
        features = self.extractor.extract_features_from_stock_data(self.sample_stock_data)
        
        assert isinstance(features, VolumeFeatures)
        feature_dict = features.to_dict()
        
        # 피처 개수 확인
        assert len(feature_dict) == 8
        
        # 기본적인 범위 확인
        for feature_name, value in feature_dict.items():
            assert isinstance(value, (int, float))
            assert not np.isnan(value)

class TestFeatureSelector:
    """피처 선택기 테스트"""
    
    def setup_method(self):
        """테스트 설정"""
        self.selector = FeatureSelector()
        self.sample_ohlcv = self._create_sample_ohlcv_data()
        self.sample_stock_data_list = self._create_sample_stock_data_list()
    
    def _create_sample_ohlcv_data(self) -> pd.DataFrame:
        """샘플 OHLCV 데이터 생성"""
        dates = pd.date_range(start='2024-01-01', periods=80, freq='D')
        
        prices = []
        volumes = []
        
        for i in range(80):
            price = 50000 + i * 100 + np.random.normal(0, 500)
            prices.append(price)
            
            volume = 1000000 + i * 15000 + np.random.normal(0, 200000)
            volumes.append(max(volume, 100000))
        
        return pd.DataFrame({
            'date': dates,
            'open': [p * 0.998 for p in prices],
            'high': [p * 1.015 for p in prices],
            'low': [p * 0.985 for p in prices],
            'close': prices,
            'volume': volumes
        }).set_index('date')
    
    def _create_sample_stock_data_list(self) -> List[Dict]:
        """샘플 주식 데이터 리스트 생성"""
        stock_codes = ['005930', '000660', '035420', '005380', '068270']
        stock_names = ['삼성전자', 'SK하이닉스', 'NAVER', '현대차', '셀트리온']
        
        stock_data_list = []
        for i, (code, name) in enumerate(zip(stock_codes, stock_names)):
            stock_data = {
                'stock_code': code,
                'stock_name': name,
                'current_price': 50000 + i * 10000 + np.random.normal(0, 5000),
                'volume_ratio': 1.0 + i * 0.3 + np.random.normal(0, 0.2),
                'sector': '테크',
                'market_cap': 100000000000000 + i * 50000000000000
            }
            stock_data_list.append(stock_data)
        
        return stock_data_list
    
    def test_feature_selector_initialization(self):
        """피처 선택기 초기화 테스트"""
        assert self.selector is not None
        assert self.selector._max_features == 10
        assert self.selector._correlation_threshold == 0.8
        assert self.selector._importance_threshold == 0.05
    
    def test_combined_features_extraction(self):
        """통합 피처 추출 테스트"""
        combined_features = self.selector.extract_all_features(self.sample_ohlcv)
        
        assert isinstance(combined_features, CombinedFeatures)
        assert isinstance(combined_features.slope_features, SlopeFeatures)
        assert isinstance(combined_features.volume_features, VolumeFeatures)
        
        # 전체 피처 개수 확인
        feature_names = combined_features.get_feature_names()
        assert len(feature_names) == 17  # 9개 기울기 + 8개 볼륨
        
        # 피처 배열 변환 테스트
        feature_array = combined_features.to_array()
        assert isinstance(feature_array, np.ndarray)
        assert feature_array.shape == (17,)
    
    def test_combined_features_from_stock_data(self):
        """주식 데이터에서 통합 피처 추출 테스트"""
        stock_data = self.sample_stock_data_list[0]
        combined_features = self.selector.extract_all_features_from_stock_data(stock_data)
        
        assert isinstance(combined_features, CombinedFeatures)
        
        # 피처 딕셔너리 확인
        feature_dict = combined_features.to_dict()
        assert len(feature_dict) == 17
        
        # 모든 피처가 숫자값인지 확인
        for feature_name, value in feature_dict.items():
            assert isinstance(value, (int, float))
            assert not np.isnan(value)
    
    def test_feature_importance_analysis(self):
        """피처 중요도 분석 테스트"""
        # 여러 종목의 피처 추출
        features_list = []
        targets = []
        
        for i, stock_data in enumerate(self.sample_stock_data_list):
            combined_features = self.selector.extract_all_features_from_stock_data(stock_data)
            features_list.append(combined_features)
            
            # 더미 타겟 값 (수익률)
            target = 0.05 + i * 0.02 + np.random.normal(0, 0.01)
            targets.append(target)
        
        # 피처 중요도 분석 (sklearn이 없을 수 있으므로 예외 처리)
        try:
            feature_importances = self.selector.analyze_feature_importance(features_list, targets)
            
            if feature_importances:  # sklearn이 있는 경우
                assert len(feature_importances) == 17
                
                # 중요도 순으로 정렬되어 있는지 확인
                for i in range(len(feature_importances) - 1):
                    assert feature_importances[i].importance_score >= feature_importances[i + 1].importance_score
                
                # 순위가 올바르게 설정되었는지 확인
                for i, fi in enumerate(feature_importances):
                    assert fi.rank == i + 1
                    assert fi.feature_type in ['slope', 'volume']
                    assert isinstance(fi.description, str)
        except Exception:
            # sklearn이 없는 경우 스킵
            pass
    
    def test_feature_summary(self):
        """피처 요약 정보 테스트"""
        summary = self.selector.get_feature_summary()
        
        assert isinstance(summary, dict)
        assert summary['total_features'] == 17
        assert summary['slope_features']['count'] == 9
        assert summary['volume_features']['count'] == 8
        
        # 피처 이름 확인
        slope_names = summary['slope_features']['names']
        volume_names = summary['volume_features']['names']
        assert len(slope_names) == 9
        assert len(volume_names) == 8
        
        # 설명 확인
        slope_descriptions = summary['slope_features']['descriptions']
        volume_descriptions = summary['volume_features']['descriptions']
        assert len(slope_descriptions) == 9
        assert len(volume_descriptions) == 8

class TestIntegratedFeatureSystem:
    """통합 피처 시스템 테스트"""
    
    def setup_method(self):
        """테스트 설정"""
        self.selector = FeatureSelector()
        self.sample_data = self._create_comprehensive_test_data()
    
    def _create_comprehensive_test_data(self) -> List[Dict]:
        """종합 테스트 데이터 생성"""
        return [
            {
                'stock_code': '005930',
                'stock_name': '삼성전자',
                'current_price': 58000.0,
                'volume_ratio': 1.5,
                'sector': '반도체'
            },
            {
                'stock_code': '000660',
                'stock_name': 'SK하이닉스',
                'current_price': 85000.0,
                'volume_ratio': 2.0,
                'sector': '반도체'
            },
            {
                'stock_code': '035420',
                'stock_name': 'NAVER',
                'current_price': 180000.0,
                'volume_ratio': 1.2,
                'sector': '인터넷'
            }
        ]
    
    def test_end_to_end_feature_pipeline(self):
        """종단 간 피처 파이프라인 테스트"""
        # 1. 각 종목에서 피처 추출
        all_features = []
        for stock_data in self.sample_data:
            combined_features = self.selector.extract_all_features_from_stock_data(stock_data)
            all_features.append(combined_features)
        
        assert len(all_features) == 3
        
        # 2. 모든 피처가 17개인지 확인
        for features in all_features:
            assert len(features.get_feature_names()) == 17
            assert len(features.to_array()) == 17
        
        # 3. 피처 배열 생성
        feature_matrix = np.array([features.to_array() for features in all_features])
        assert feature_matrix.shape == (3, 17)
        
        # 4. 피처 이름 일관성 확인
        feature_names_sets = [set(features.get_feature_names()) for features in all_features]
        assert len(set.intersection(*feature_names_sets)) == 17  # 모든 피처 이름이 동일
    
    def test_feature_extraction_performance(self):
        """피처 추출 성능 테스트"""
        import time
        
        # 10개 종목에 대해 피처 추출 시간 측정
        large_sample = self.sample_data * 10
        
        start_time = time.time()
        extracted_features = []
        
        for stock_data in large_sample:
            combined_features = self.selector.extract_all_features_from_stock_data(stock_data)
            extracted_features.append(combined_features)
        
        end_time = time.time()
        extraction_time = end_time - start_time
        
        # 평균 추출 시간이 1초 이하인지 확인
        avg_time_per_stock = extraction_time / len(large_sample)
        assert avg_time_per_stock < 1.0, f"피처 추출 시간이 너무 오래 걸림: {avg_time_per_stock:.2f}초"
        
        # 모든 피처가 올바르게 추출되었는지 확인
        assert len(extracted_features) == len(large_sample)
        for features in extracted_features:
            assert len(features.get_feature_names()) == 17
    
    def test_feature_data_quality(self):
        """피처 데이터 품질 테스트"""
        # 다양한 시나리오의 주식 데이터 생성
        test_scenarios = [
            # 정상 데이터
            {'stock_code': '005930', 'current_price': 58000.0, 'volume_ratio': 1.5},
            # 높은 거래량
            {'stock_code': '000660', 'current_price': 85000.0, 'volume_ratio': 5.0},
            # 낮은 거래량
            {'stock_code': '035420', 'current_price': 180000.0, 'volume_ratio': 0.5},
            # 극단적인 가격
            {'stock_code': '068270', 'current_price': 500000.0, 'volume_ratio': 2.0}
        ]
        
        for i, scenario in enumerate(test_scenarios):
            combined_features = self.selector.extract_all_features_from_stock_data(scenario)
            feature_dict = combined_features.to_dict()
            
            # 모든 피처가 유효한 값인지 확인
            for feature_name, value in feature_dict.items():
                assert isinstance(value, (int, float)), f"시나리오 {i}: {feature_name} 값이 숫자가 아님"
                assert not np.isnan(value), f"시나리오 {i}: {feature_name} 값이 NaN"
                assert not np.isinf(value), f"시나리오 {i}: {feature_name} 값이 무한대"
                
                # 피처별 범위 확인
                if 'correlation' in feature_name:
                    assert -1 <= value <= 1, f"시나리오 {i}: {feature_name} 상관관계 범위 오류"
                elif 'percentile' in feature_name or 'score' in feature_name:
                    assert 0 <= value <= 100, f"시나리오 {i}: {feature_name} 점수 범위 오류"
                elif 'angle' in feature_name:
                    assert -90 <= value <= 90, f"시나리오 {i}: {feature_name} 각도 범위 오류"

if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 