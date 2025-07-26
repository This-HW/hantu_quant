"""
Phase 4 AI 학습 시스템 - 피처 선택 및 중요도 분석 모듈

전체 17개 피처를 통합하고 중요도 분석:
- 기울기 피처 9개 + 볼륨 피처 8개
- 피처 중요도 분석
- 피처 선택 최적화
- 피처 조합 평가
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass
from datetime import datetime
import logging
import json
from typing import Any

from core.utils.log_utils import get_logger
from .slope_features import SlopeFeatureExtractor, SlopeFeatures
from .volume_features import VolumeFeatureExtractor, VolumeFeatures

# Optional sklearn imports
try:
    from sklearn.feature_selection import SelectKBest, f_regression, mutual_info_regression
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.model_selection import cross_val_score
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import mean_squared_error, r2_score
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

logger = get_logger(__name__)

@dataclass
class FeatureImportance:
    """피처 중요도 정보"""
    feature_name: str
    importance_score: float
    feature_type: str  # 'slope' or 'volume'
    rank: int
    description: str

@dataclass
class FeatureSelectionResult:
    """피처 선택 결과"""
    selected_features: List[str]
    feature_importances: List[FeatureImportance]
    selection_score: float
    total_features: int
    selected_count: int
    feature_correlations: Dict[str, float]
    
    def to_dict(self) -> Dict:
        """딕셔너리 형태로 변환"""
        return {
            'selected_features': self.selected_features,
            'feature_importances': [
                {
                    'feature_name': fi.feature_name,
                    'importance_score': fi.importance_score,
                    'feature_type': fi.feature_type,
                    'rank': fi.rank,
                    'description': fi.description
                }
                for fi in self.feature_importances
            ],
            'selection_score': self.selection_score,
            'total_features': self.total_features,
            'selected_count': self.selected_count,
            'feature_correlations': self.feature_correlations
        }

@dataclass
class CombinedFeatures:
    """통합된 피처 데이터"""
    slope_features: SlopeFeatures
    volume_features: VolumeFeatures
    
    def to_dict(self) -> Dict[str, float]:
        """모든 피처를 딕셔너리로 변환"""
        combined = {}
        combined.update(self.slope_features.to_dict())
        combined.update(self.volume_features.to_dict())
        return combined
    
    def to_array(self) -> np.ndarray:
        """피처를 numpy 배열로 변환"""
        feature_dict = self.to_dict()
        return np.array(list(feature_dict.values()))
    
    def get_feature_names(self) -> List[str]:
        """피처 이름 목록 반환"""
        feature_dict = self.to_dict()
        return list(feature_dict.keys())

class FeatureSelector:
    """피처 선택 및 중요도 분석 시스템"""
    
    def __init__(self):
        """피처 선택기 초기화"""
        self._logger = logger
        self._slope_extractor = SlopeFeatureExtractor()
        self._volume_extractor = VolumeFeatureExtractor()
        self._scaler = StandardScaler()
        
        # 기본 설정
        self._max_features = 10  # 선택할 최대 피처 수
        self._correlation_threshold = 0.8  # 상관관계 임계값
        self._importance_threshold = 0.05  # 중요도 임계값
        
    def extract_all_features(self, ohlcv_data: pd.DataFrame) -> CombinedFeatures:
        """
        모든 피처 추출 (기울기 + 볼륨)
        
        Args:
            ohlcv_data: OHLCV 데이터프레임
            
        Returns:
            CombinedFeatures: 통합된 피처 데이터
        """
        try:
            # 기울기 피처 추출
            slope_features = self._slope_extractor.extract_features(ohlcv_data)
            
            # 볼륨 피처 추출
            volume_features = self._volume_extractor.extract_features(ohlcv_data)
            
            # 통합 피처 생성
            combined_features = CombinedFeatures(
                slope_features=slope_features,
                volume_features=volume_features
            )
            
            self._logger.debug(f"전체 피처 추출 완료: {len(combined_features.get_feature_names())}개")
            return combined_features
            
        except Exception as e:
            self._logger.error(f"피처 추출 오류: {e}")
            return CombinedFeatures(
                slope_features=SlopeFeatures(),
                volume_features=VolumeFeatures()
            )
    
    def extract_all_features_from_stock_data(self, stock_data: Dict) -> CombinedFeatures:
        """
        주식 데이터에서 모든 피처 추출
        
        Args:
            stock_data: 주식 데이터 딕셔너리
            
        Returns:
            CombinedFeatures: 통합된 피처 데이터
        """
        try:
            # 기울기 피처 추출
            slope_features = self._slope_extractor.extract_features_from_stock_data(stock_data)
            
            # 볼륨 피처 추출
            volume_features = self._volume_extractor.extract_features_from_stock_data(stock_data)
            
            # 통합 피처 생성
            combined_features = CombinedFeatures(
                slope_features=slope_features,
                volume_features=volume_features
            )
            
            return combined_features
            
        except Exception as e:
            self._logger.error(f"주식 데이터에서 피처 추출 오류: {e}")
            return CombinedFeatures(
                slope_features=SlopeFeatures(),
                volume_features=VolumeFeatures()
            )
    
    def analyze_feature_importance(self, 
                                 features_list: List[CombinedFeatures],
                                 targets: List[float]) -> List[FeatureImportance]:
        """
        피처 중요도 분석
        
        Args:
            features_list: 피처 데이터 리스트
            targets: 타겟 값 리스트 (예: 수익률)
            
        Returns:
            List[FeatureImportance]: 피처 중요도 리스트
        """
        try:
            if not features_list or not targets or len(features_list) != len(targets):
                self._logger.warning("피처 중요도 분석을 위한 데이터 부족")
                return []
            
            # 피처 매트릭스 생성
            feature_matrix = []
            feature_names = features_list[0].get_feature_names()
            
            for features in features_list:
                feature_matrix.append(features.to_array())
            
            X = np.array(feature_matrix)
            y = np.array(targets)
            
            # 데이터 정규화
            X_scaled = self._scaler.fit_transform(X)
            
            # RandomForest를 이용한 피처 중요도 계산
            rf_model = RandomForestRegressor(n_estimators=100, random_state=42)
            rf_model.fit(X_scaled, y)
            rf_importances = rf_model.feature_importances_
            
            # 상호 정보량 계산
            mi_scores = mutual_info_regression(X_scaled, y, random_state=42)
            
            # 피처 중요도 객체 생성
            feature_importances = []
            slope_features = self._slope_extractor.get_feature_names()
            volume_features = self._volume_extractor.get_feature_names()
            
            for i, feature_name in enumerate(feature_names):
                # 피처 타입 결정
                feature_type = 'slope' if feature_name in slope_features else 'volume'
                
                # 중요도 점수 계산 (RandomForest + 상호정보량 평균)
                importance_score = (rf_importances[i] + mi_scores[i]) / 2
                
                # 설명 가져오기
                if feature_type == 'slope':
                    descriptions = self._slope_extractor.get_feature_descriptions()
                else:
                    descriptions = self._volume_extractor.get_feature_descriptions()
                
                description = descriptions.get(feature_name, f"{feature_name} 피처")
                
                feature_importances.append(FeatureImportance(
                    feature_name=feature_name,
                    importance_score=importance_score,
                    feature_type=feature_type,
                    rank=0,  # 후에 정렬 후 설정
                    description=description
                ))
            
            # 중요도 순으로 정렬 및 순위 설정
            feature_importances.sort(key=lambda x: x.importance_score, reverse=True)
            for i, fi in enumerate(feature_importances):
                fi.rank = i + 1
            
            self._logger.info(f"피처 중요도 분석 완료: {len(feature_importances)}개 피처")
            return feature_importances
            
        except Exception as e:
            self._logger.error(f"피처 중요도 분석 오류: {e}")
            return []
    
    def select_optimal_features(self,
                              features_list: List[CombinedFeatures],
                              targets: List[float],
                              max_features: Optional[int] = None) -> FeatureSelectionResult:
        """
        최적의 피처 조합 선택
        
        Args:
            features_list: 피처 데이터 리스트
            targets: 타겟 값 리스트
            max_features: 선택할 최대 피처 수
            
        Returns:
            FeatureSelectionResult: 피처 선택 결과
        """
        try:
            if not features_list or not targets:
                self._logger.warning("피처 선택을 위한 데이터 부족")
                return FeatureSelectionResult(
                    selected_features=[],
                    feature_importances=[],
                    selection_score=0.0,
                    total_features=0,
                    selected_count=0,
                    feature_correlations={}
                )
            
            # 피처 중요도 분석
            feature_importances = self.analyze_feature_importance(features_list, targets)
            
            if not feature_importances:
                return FeatureSelectionResult(
                    selected_features=[],
                    feature_importances=[],
                    selection_score=0.0,
                    total_features=0,
                    selected_count=0,
                    feature_correlations={}
                )
            
            # 최대 피처 수 설정
            if max_features is None:
                max_features = self._max_features
            
            # 피처 매트릭스 생성
            feature_matrix = []
            feature_names = features_list[0].get_feature_names()
            
            for features in features_list:
                feature_matrix.append(features.to_array())
            
            X = np.array(feature_matrix)
            y = np.array(targets)
            
            # 상관관계 분석
            feature_correlations = self._calculate_feature_correlations(X, feature_names)
            
            # 피처 선택 수행
            selected_features = self._select_features_by_importance_and_correlation(
                feature_importances, feature_correlations, max_features
            )
            
            # 선택된 피처로 성능 평가
            selection_score = self._evaluate_feature_selection(
                X, y, feature_names, selected_features
            )
            
            result = FeatureSelectionResult(
                selected_features=selected_features,
                feature_importances=feature_importances,
                selection_score=selection_score,
                total_features=len(feature_names),
                selected_count=len(selected_features),
                feature_correlations=feature_correlations
            )
            
            self._logger.info(f"피처 선택 완료: {len(selected_features)}/{len(feature_names)} 피처 선택")
            return result
            
        except Exception as e:
            self._logger.error(f"피처 선택 오류: {e}")
            return FeatureSelectionResult(
                selected_features=[],
                feature_importances=[],
                selection_score=0.0,
                total_features=0,
                selected_count=0,
                feature_correlations={}
            )
    
    def _calculate_feature_correlations(self, X: np.ndarray, feature_names: List[str]) -> Dict[str, float]:
        """피처 간 상관관계 계산"""
        try:
            correlations = {}
            
            # 피처 간 상관관계 매트릭스 계산
            X_df = pd.DataFrame(data=X, columns=feature_names)
            corr_matrix = X_df.corr()
            
            # 각 피처의 최대 상관관계 값 저장
            for feature in feature_names:
                # 자기 자신과의 상관관계 제외
                other_correlations = corr_matrix[feature].drop(feature)
                max_correlation = other_correlations.abs().max()
                correlations[feature] = max_correlation
            
            return correlations
            
        except Exception as e:
            self._logger.error(f"피처 상관관계 계산 오류: {e}")
            return {}
    
    def _select_features_by_importance_and_correlation(self,
                                                     feature_importances: List[FeatureImportance],
                                                     feature_correlations: Dict[str, float],
                                                     max_features: int) -> List[str]:
        """중요도와 상관관계를 고려한 피처 선택"""
        try:
            selected_features = []
            
            # 중요도 순으로 정렬된 피처들을 순회
            for feature_importance in feature_importances:
                feature_name = feature_importance.feature_name
                
                # 최대 피처 수 확인
                if len(selected_features) >= max_features:
                    break
                
                # 중요도 임계값 확인
                if feature_importance.importance_score < self._importance_threshold:
                    continue
                
                # 상관관계 확인 (이미 선택된 피처와 높은 상관관계가 있는지)
                correlation_ok = True
                max_correlation = feature_correlations.get(feature_name, 0.0)
                
                if max_correlation > self._correlation_threshold:
                    # 이미 선택된 피처 중에서 유사한 피처가 있는지 확인
                    # 더 정교한 로직이 필요할 수 있음
                    correlation_ok = len(selected_features) < 3  # 초기 3개는 허용
                
                if correlation_ok:
                    selected_features.append(feature_name)
            
            return selected_features
            
        except Exception as e:
            self._logger.error(f"피처 선택 오류: {e}")
            return []
    
    def _evaluate_feature_selection(self,
                                   X: np.ndarray,
                                   y: np.ndarray,
                                   feature_names: List[str],
                                   selected_features: List[str]) -> float:
        """선택된 피처의 성능 평가"""
        try:
            if not selected_features:
                return 0.0
            
            # 선택된 피처의 인덱스 찾기
            selected_indices = [feature_names.index(f) for f in selected_features if f in feature_names]
            
            if not selected_indices:
                return 0.0
            
            # 선택된 피처만 사용
            X_selected = X[:, selected_indices]
            
            # 데이터 정규화
            X_scaled = self._scaler.fit_transform(X_selected)
            
            # RandomForest 모델로 교차 검증
            rf_model = RandomForestRegressor(n_estimators=100, random_state=42)
            cv_scores = cross_val_score(rf_model, X_scaled, y, cv=5, scoring='r2')
            
            # 평균 R² 점수 반환
            return cv_scores.mean()
            
        except Exception as e:
            self._logger.error(f"피처 선택 평가 오류: {e}")
            return 0.0
    
    def get_feature_summary(self) -> Dict[str, Any]:
        """피처 요약 정보 반환"""
        slope_features = self._slope_extractor.get_feature_names()
        volume_features = self._volume_extractor.get_feature_names()
        
        return {
            'total_features': len(slope_features) + len(volume_features),
            'slope_features': {
                'count': len(slope_features),
                'names': slope_features,
                'descriptions': self._slope_extractor.get_feature_descriptions()
            },
            'volume_features': {
                'count': len(volume_features),
                'names': volume_features,
                'descriptions': self._volume_extractor.get_feature_descriptions()
            },
            'selection_settings': {
                'max_features': self._max_features,
                'correlation_threshold': self._correlation_threshold,
                'importance_threshold': self._importance_threshold
            }
        }
    
    def save_selection_result(self, result: FeatureSelectionResult, filepath: str) -> bool:
        """피처 선택 결과를 파일에 저장"""
        try:
            result_dict = result.to_dict()
            result_dict['timestamp'] = datetime.now().isoformat()
            result_dict['feature_summary'] = self.get_feature_summary()
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(result_dict, f, ensure_ascii=False, indent=2)
            
            self._logger.info(f"피처 선택 결과 저장 완료: {filepath}")
            return True
            
        except Exception as e:
            self._logger.error(f"피처 선택 결과 저장 오류: {e}")
            return False 