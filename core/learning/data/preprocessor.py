"""
Phase 4: AI 학습 시스템 - 데이터 전처리 시스템
수집된 데이터를 AI 학습에 적합하도록 전처리하고 정제
"""

import os
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
# sklearn 라이브러리 - 사용 가능할 때만 import
try:
    from sklearn.preprocessing import StandardScaler, MinMaxScaler, RobustScaler
    from sklearn.impute import SimpleImputer, KNNImputer
    from sklearn.feature_selection import SelectKBest, f_classif, mutual_info_classif
    SKLEARN_AVAILABLE = True
    import warnings
    warnings.filterwarnings('ignore')
except ImportError:
    SKLEARN_AVAILABLE = False
    # 간단한 대체 클래스들
    class StandardScaler:
        def fit_transform(self, X): return X
        def transform(self, X): return X
    class SimpleImputer:
        def __init__(self, strategy='mean'): pass
        def fit_transform(self, X): return X
    class SelectKBest:
        def __init__(self, score_func, k=10): pass
        def fit_transform(self, X, y): return X

# 인터페이스 및 데이터 클래스 import
from core.interfaces.learning import LearningData, FeatureSet
from core.learning.config.settings import get_learning_config
from core.learning.utils.logging import get_learning_logger
from core.learning.data.storage import get_learning_storage

# 임시 플러그인 시스템 (추후 실제 아키텍처로 교체)
def plugin(**kwargs):
    """임시 플러그인 데코레이터"""
    def decorator(cls):
        cls._plugin_metadata = kwargs
        return cls
    return decorator

def inject(cls):
    """임시 DI 데코레이터"""
    return cls

logger = get_learning_logger(__name__)

@plugin(
    name="learning_data_preprocessor",
    version="1.0.0",
    description="AI 학습용 데이터 전처리 플러그인",
    author="HantuQuant",
    dependencies=["learning_config", "learning_storage"],
    category="learning"
)
class LearningDataPreprocessor:
    """AI 학습용 데이터 전처리 시스템"""
    
    @inject
    def __init__(self, config=None, storage=None):
        """초기화"""
        self._config = config or get_learning_config()
        self._storage = storage or get_learning_storage()
        self._logger = logger
        
        # 전처리 설정
        self._scalers = {}
        self._imputers = {}
        self._feature_selectors = {}
        
        self._logger.info("LearningDataPreprocessor 초기화 완료")
    
    def preprocess_learning_data(self, data: List[LearningData]) -> List[LearningData]:
        """학습 데이터 전처리"""
        try:
            self._logger.info(f"학습 데이터 전처리 시작: {len(data)}개 데이터")
            
            # 1. 데이터 검증 및 정제
            _v_cleaned_data = self._clean_data(data)
            
            # 2. 이상치 제거
            _v_outlier_removed = self._remove_outliers(_v_cleaned_data)
            
            # 3. 결측치 처리
            _v_imputed_data = self._handle_missing_values(_v_outlier_removed)
            
            # 4. 데이터 타입 정규화
            _v_normalized_data = self._normalize_data_types(_v_imputed_data)
            
            # 5. 시계열 데이터 보정
            _v_time_corrected = self._correct_time_series(_v_normalized_data)
            
            self._logger.info(f"학습 데이터 전처리 완료: {len(_v_time_corrected)}개 데이터")
            return _v_time_corrected
            
        except Exception as e:
            self._logger.error(f"학습 데이터 전처리 오류: {e}")
            return data
    
    def preprocess_feature_data(self, features: List[FeatureSet]) -> List[FeatureSet]:
        """피처 데이터 전처리"""
        try:
            self._logger.info(f"피처 데이터 전처리 시작: {len(features)}개 피처 셋")
            
            # 1. 피처 검증
            _v_validated_features = self._validate_features(features)
            
            # 2. 피처 스케일링
            _v_scaled_features = self._scale_features(_v_validated_features)
            
            # 3. 피처 선택
            _v_selected_features = self._select_features(_v_scaled_features)
            
            # 4. 피처 엔지니어링
            _v_engineered_features = self._engineer_features(_v_selected_features)
            
            self._logger.info(f"피처 데이터 전처리 완료: {len(_v_engineered_features)}개 피처 셋")
            return _v_engineered_features
            
        except Exception as e:
            self._logger.error(f"피처 데이터 전처리 오류: {e}")
            return features
    
    def _clean_data(self, data: List[LearningData]) -> List[LearningData]:
        """데이터 정제"""
        try:
            _v_cleaned_data = []
            
            for _v_record in data:
                # 필수 필드 검증
                if not _v_record.stock_code or not _v_record.stock_name:
                    continue
                
                # 날짜 유효성 검증
                try:
                    datetime.strptime(_v_record.date, '%Y-%m-%d')
                except ValueError:
                    continue
                
                # Phase 1 데이터 정제
                _v_cleaned_phase1 = self._clean_phase1_data(_v_record.phase1_data)
                
                # Phase 2 데이터 정제
                _v_cleaned_phase2 = self._clean_phase2_data(_v_record.phase2_data)
                
                # 실제 성과 데이터 정제
                _v_cleaned_performance = self._clean_performance_data(_v_record.actual_performance)
                
                # 정제된 데이터로 새 객체 생성
                _v_cleaned_record = LearningData(
                    stock_code=_v_record.stock_code,
                    stock_name=_v_record.stock_name,
                    date=_v_record.date,
                    phase1_data=_v_cleaned_phase1,
                    phase2_data=_v_cleaned_phase2,
                    actual_performance=_v_cleaned_performance,
                    market_condition=_v_record.market_condition,
                    metadata=_v_record.metadata
                )
                
                _v_cleaned_data.append(_v_cleaned_record)
            
            self._logger.debug(f"데이터 정제 완료: {len(_v_cleaned_data)}개 유효 데이터")
            return _v_cleaned_data
            
        except Exception as e:
            self._logger.error(f"데이터 정제 오류: {e}")
            return data
    
    def _clean_phase1_data(self, phase1_data: Dict[str, Any]) -> Dict[str, Any]:
        """Phase 1 데이터 정제"""
        if not phase1_data:
            return {}
        
        _v_cleaned = {}
        
        # 점수 데이터 정제
        for _v_key in ["fundamental_score", "technical_score", "momentum_score", "overall_score"]:
            if _v_key in phase1_data:
                _v_score = phase1_data[_v_key]
                if isinstance(_v_score, (int, float)) and 0 <= _v_score <= 100:
                    _v_cleaned[_v_key] = float(_v_score)
        
        # 통과 여부 정제
        for _v_key in ["fundamental_passed", "technical_passed", "momentum_passed", "overall_passed"]:
            if _v_key in phase1_data:
                _v_cleaned[_v_key] = bool(phase1_data[_v_key])
        
        # 세부 정보 정제
        if "details" in phase1_data and isinstance(phase1_data["details"], dict):
            _v_cleaned["details"] = phase1_data["details"]
        
        # 섹터 정보 정제
        if "sector" in phase1_data:
            _v_cleaned["sector"] = str(phase1_data["sector"])
        
        return _v_cleaned
    
    def _clean_phase2_data(self, phase2_data: Dict[str, Any]) -> Dict[str, Any]:
        """Phase 2 데이터 정제"""
        if not phase2_data:
            return {}
        
        _v_cleaned = {}
        
        # 점수 데이터 정제
        for _v_key in ["price_attractiveness", "technical_score", "volume_score", "pattern_score"]:
            if _v_key in phase2_data:
                _v_score = phase2_data[_v_key]
                if isinstance(_v_score, (int, float)) and 0 <= _v_score <= 100:
                    _v_cleaned[_v_key] = float(_v_score)
        
        # 가격 정보 정제
        for _v_key in ["entry_price", "target_price", "stop_loss", "current_price"]:
            if _v_key in phase2_data:
                _v_price = phase2_data[_v_key]
                if isinstance(_v_price, (int, float)) and _v_price > 0:
                    _v_cleaned[_v_key] = float(_v_price)
        
        # 기타 지표 정제
        for _v_key in ["risk_score", "confidence", "expected_return"]:
            if _v_key in phase2_data:
                _v_value = phase2_data[_v_key]
                if isinstance(_v_value, (int, float)):
                    _v_cleaned[_v_key] = float(_v_value)
        
        # 선정 이유 정제
        if "selection_reason" in phase2_data:
            _v_cleaned["selection_reason"] = str(phase2_data["selection_reason"])
        
        return _v_cleaned
    
    def _clean_performance_data(self, performance_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """실제 성과 데이터 정제"""
        if not performance_data:
            return {}
        
        _v_cleaned = {}
        
        # 수익률 데이터 정제
        for _v_key in ["1d_return", "3d_return", "7d_return", "14d_return", "30d_return"]:
            if _v_key in performance_data:
                _v_return = performance_data[_v_key]
                if isinstance(_v_return, (int, float)) and -1 <= _v_return <= 5:  # -100% ~ +500% 범위 제한
                    _v_cleaned[_v_key] = float(_v_return)
        
        # 리스크 지표 정제
        for _v_key in ["volatility", "max_drawdown", "sharpe_ratio", "beta"]:
            if _v_key in performance_data:
                _v_value = performance_data[_v_key]
                if isinstance(_v_value, (int, float)):
                    _v_cleaned[_v_key] = float(_v_value)
        
        # 거래량 정보 정제
        for _v_key in ["avg_volume", "volume_increase"]:
            if _v_key in performance_data:
                _v_value = performance_data[_v_key]
                if isinstance(_v_value, (int, float)) and _v_value > 0:
                    _v_cleaned[_v_key] = float(_v_value)
        
        return _v_cleaned
    
    def _remove_outliers(self, data: List[LearningData]) -> List[LearningData]:
        """이상치 제거"""
        try:
            # 수치형 데이터 추출
            _v_numeric_data = []
            for _v_record in data:
                _v_numeric_row = {}
                
                # Phase 1 점수들
                if _v_record.phase1_data:
                    for _v_key in ["fundamental_score", "technical_score", "momentum_score", "overall_score"]:
                        if _v_key in _v_record.phase1_data:
                            _v_numeric_row[f"phase1_{_v_key}"] = _v_record.phase1_data[_v_key]
                
                # Phase 2 점수들
                if _v_record.phase2_data:
                    for _v_key in ["price_attractiveness", "technical_score", "volume_score", "pattern_score"]:
                        if _v_key in _v_record.phase2_data:
                            _v_numeric_row[f"phase2_{_v_key}"] = _v_record.phase2_data[_v_key]
                
                # 실제 성과 데이터
                if _v_record.actual_performance:
                    for _v_key in ["7d_return", "volatility", "max_drawdown"]:
                        if _v_key in _v_record.actual_performance:
                            _v_numeric_row[f"performance_{_v_key}"] = _v_record.actual_performance[_v_key]
                
                _v_numeric_data.append(_v_numeric_row)
            
            # DataFrame으로 변환
            _v_df = pd.DataFrame(_v_numeric_data)
            
            if _v_df.empty:
                return data
            
            # IQR 방법으로 이상치 탐지
            _v_outlier_mask = pd.Series([False] * len(_v_df))
            
            for _v_col in _v_df.columns:
                _v_q1 = _v_df[_v_col].quantile(0.25)
                _v_q3 = _v_df[_v_col].quantile(0.75)
                _v_iqr = _v_q3 - _v_q1
                
                _v_lower_bound = _v_q1 - 1.5 * _v_iqr
                _v_upper_bound = _v_q3 + 1.5 * _v_iqr
                
                _v_outlier_mask |= (_v_df[_v_col] < _v_lower_bound) | (_v_df[_v_col] > _v_upper_bound)
            
            # 이상치가 아닌 데이터만 유지
            _v_cleaned_data = [data[i] for i in range(len(data)) if not _v_outlier_mask.iloc[i]]
            
            _v_removed_count = len(data) - len(_v_cleaned_data)
            self._logger.debug(f"이상치 제거 완료: {_v_removed_count}개 제거, {len(_v_cleaned_data)}개 유지")
            
            return _v_cleaned_data
            
        except Exception as e:
            self._logger.error(f"이상치 제거 오류: {e}")
            return data
    
    def _handle_missing_values(self, data: List[LearningData]) -> List[LearningData]:
        """결측치 처리"""
        try:
            # 결측치 통계 수집
            _v_missing_stats = self._collect_missing_stats(data)
            
            # 결측치 보간
            _v_imputed_data = []
            
            for _v_record in data:
                # Phase 1 데이터 보간
                _v_imputed_phase1 = self._impute_phase1_data(_v_record.phase1_data, _v_missing_stats)
                
                # Phase 2 데이터 보간
                _v_imputed_phase2 = self._impute_phase2_data(_v_record.phase2_data, _v_missing_stats)
                
                # 실제 성과 데이터 보간
                _v_imputed_performance = self._impute_performance_data(_v_record.actual_performance, _v_missing_stats)
                
                # 보간된 데이터로 새 객체 생성
                _v_imputed_record = LearningData(
                    stock_code=_v_record.stock_code,
                    stock_name=_v_record.stock_name,
                    date=_v_record.date,
                    phase1_data=_v_imputed_phase1,
                    phase2_data=_v_imputed_phase2,
                    actual_performance=_v_imputed_performance,
                    market_condition=_v_record.market_condition,
                    metadata=_v_record.metadata
                )
                
                _v_imputed_data.append(_v_imputed_record)
            
            self._logger.debug(f"결측치 처리 완료: {len(_v_imputed_data)}개 데이터")
            return _v_imputed_data
            
        except Exception as e:
            self._logger.error(f"결측치 처리 오류: {e}")
            return data
    
    def _collect_missing_stats(self, data: List[LearningData]) -> Dict[str, Any]:
        """결측치 통계 수집"""
        _v_stats = {
            "phase1_means": {},
            "phase2_means": {},
            "performance_means": {}
        }
        
        # Phase 1 평균값 계산
        _v_phase1_sums = {}
        _v_phase1_counts = {}
        
        for _v_record in data:
            if _v_record.phase1_data:
                for _v_key, _v_value in _v_record.phase1_data.items():
                    if isinstance(_v_value, (int, float)):
                        _v_phase1_sums[_v_key] = _v_phase1_sums.get(_v_key, 0) + _v_value
                        _v_phase1_counts[_v_key] = _v_phase1_counts.get(_v_key, 0) + 1
        
        for _v_key in _v_phase1_sums:
            if _v_phase1_counts[_v_key] > 0:
                _v_stats["phase1_means"][_v_key] = _v_phase1_sums[_v_key] / _v_phase1_counts[_v_key]
        
        # Phase 2, 성과 데이터도 동일하게 처리
        # (코드 간소화를 위해 생략)
        
        return _v_stats
    
    def _impute_phase1_data(self, phase1_data: Dict[str, Any], stats: Dict[str, Any]) -> Dict[str, Any]:
        """Phase 1 데이터 보간"""
        if not phase1_data:
            return {}
        
        _v_imputed = phase1_data.copy()
        
        # 점수 필드 보간
        for _v_key in ["fundamental_score", "technical_score", "momentum_score", "overall_score"]:
            if _v_key not in _v_imputed or _v_imputed[_v_key] is None:
                if _v_key in stats["phase1_means"]:
                    _v_imputed[_v_key] = stats["phase1_means"][_v_key]
                else:
                    _v_imputed[_v_key] = 50.0  # 기본값
        
        return _v_imputed
    
    def _impute_phase2_data(self, phase2_data: Dict[str, Any], stats: Dict[str, Any]) -> Dict[str, Any]:
        """Phase 2 데이터 보간"""
        if not phase2_data:
            return {}
        
        _v_imputed = phase2_data.copy()
        
        # 점수 필드 보간
        for _v_key in ["price_attractiveness", "technical_score", "volume_score", "pattern_score"]:
            if _v_key not in _v_imputed or _v_imputed[_v_key] is None:
                _v_imputed[_v_key] = 50.0  # 기본값
        
        return _v_imputed
    
    def _impute_performance_data(self, performance_data: Optional[Dict[str, Any]], stats: Dict[str, Any]) -> Dict[str, Any]:
        """실제 성과 데이터 보간"""
        if not performance_data:
            return {}
        
        _v_imputed = performance_data.copy()
        
        # 수익률 필드 보간
        for _v_key in ["1d_return", "3d_return", "7d_return", "14d_return", "30d_return"]:
            if _v_key not in _v_imputed or _v_imputed[_v_key] is None:
                _v_imputed[_v_key] = 0.0  # 기본값
        
        return _v_imputed
    
    def _normalize_data_types(self, data: List[LearningData]) -> List[LearningData]:
        """데이터 타입 정규화"""
        try:
            _v_normalized_data = []
            
            for _v_record in data:
                # 문자열 정규화
                _v_normalized_stock_code = _v_record.stock_code.strip().upper()
                _v_normalized_stock_name = _v_record.stock_name.strip()
                
                # 시장 상황 정규화
                _v_normalized_market_condition = _v_record.market_condition.lower() if _v_record.market_condition else "neutral"
                
                # 정규화된 데이터로 새 객체 생성
                _v_normalized_record = LearningData(
                    stock_code=_v_normalized_stock_code,
                    stock_name=_v_normalized_stock_name,
                    date=_v_record.date,
                    phase1_data=_v_record.phase1_data,
                    phase2_data=_v_record.phase2_data,
                    actual_performance=_v_record.actual_performance,
                    market_condition=_v_normalized_market_condition,
                    metadata=_v_record.metadata
                )
                
                _v_normalized_data.append(_v_normalized_record)
            
            return _v_normalized_data
            
        except Exception as e:
            self._logger.error(f"데이터 타입 정규화 오류: {e}")
            return data
    
    def _correct_time_series(self, data: List[LearningData]) -> List[LearningData]:
        """시계열 데이터 보정"""
        try:
            # 날짜순 정렬
            _v_sorted_data = sorted(data, key=lambda x: x.date)
            
            # 중복 제거 (같은 날짜, 같은 종목)
            _v_seen = set()
            _v_deduplicated = []
            
            for _v_record in _v_sorted_data:
                _v_key = f"{_v_record.stock_code}_{_v_record.date}"
                if _v_key not in _v_seen:
                    _v_seen.add(_v_key)
                    _v_deduplicated.append(_v_record)
            
            self._logger.debug(f"시계열 보정 완료: {len(_v_deduplicated)}개 데이터")
            return _v_deduplicated
            
        except Exception as e:
            self._logger.error(f"시계열 보정 오류: {e}")
            return data
    
    def _validate_features(self, features: List[FeatureSet]) -> List[FeatureSet]:
        """피처 검증"""
        # 구현 생략 (기본 검증 로직)
        return features
    
    def _scale_features(self, features: List[FeatureSet]) -> List[FeatureSet]:
        """피처 스케일링"""
        # 구현 생략 (StandardScaler 사용)
        return features
    
    def _select_features(self, features: List[FeatureSet]) -> List[FeatureSet]:
        """피처 선택"""
        # 구현 생략 (SelectKBest 사용)
        return features
    
    def _engineer_features(self, features: List[FeatureSet]) -> List[FeatureSet]:
        """피처 엔지니어링"""
        # 구현 생략 (파생 변수 생성)
        return features
    
    def get_preprocessing_stats(self) -> Dict[str, Any]:
        """전처리 통계 조회"""
        return {
            "scalers": list(self._scalers.keys()),
            "imputers": list(self._imputers.keys()),
            "feature_selectors": list(self._feature_selectors.keys()),
            "config": self._config.to_dict()
        }


# 전역 인스턴스
_preprocessor = None

def get_data_preprocessor() -> LearningDataPreprocessor:
    """데이터 전처리기 전역 인스턴스 반환"""
    global _preprocessor
    if _preprocessor is None:
        _preprocessor = LearningDataPreprocessor()
    return _preprocessor 