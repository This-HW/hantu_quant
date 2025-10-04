"""
Phase 4: AI 학습 시스템 - 예측 엔진

학습된 모델을 사용한 실시간 예측 시스템
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import json
from dataclasses import dataclass, asdict
from pathlib import Path

from core.utils.log_utils import get_logger
from core.learning.features.feature_selector import FeatureSelector
from .pattern_learner import PatternLearner, PatternFeatures, PatternPrediction

logger = get_logger(__name__)

@dataclass
class PredictionResult:
    """예측 결과 통합 클래스"""
    stock_code: str
    stock_name: str
    prediction_date: str
    
    # 앙상블 예측 결과
    ensemble_probability: float  # 앙상블 성공 확률
    ensemble_prediction: int     # 앙상블 예측 클래스
    ensemble_confidence: float   # 앙상블 신뢰도
    
    # 개별 모델 예측들
    model_predictions: Dict[str, PatternPrediction]
    
    # 종합 평가
    recommendation: str  # 'BUY', 'HOLD', 'SELL'
    risk_level: str     # 'LOW', 'MEDIUM', 'HIGH'
    
    # 추가 정보
    sector: str
    current_price: float
    target_score: float
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        result = asdict(self)
        # 개별 모델 예측들도 딕셔너리로 변환
        result['model_predictions'] = {
            model_name: pred.to_dict() 
            for model_name, pred in self.model_predictions.items()
        }
        return result

class PredictionEngine:
    """예측 엔진 시스템"""
    
    def __init__(self, model_save_dir: str = "data/models"):
        """초기화
        
        Args:
            model_save_dir: 모델 저장 디렉토리
        """
        self._logger = logger
        self._pattern_learner = PatternLearner(model_save_dir)
        self._feature_selector = FeatureSelector()
        
        # 예측 임계값 설정
        self._prediction_thresholds = {
            'buy': 0.7,      # 70% 이상 성공 확률시 매수 추천
            'hold': 0.5,     # 50-70% 보유 추천  
            'sell': 0.3      # 30% 이하 매도 추천
        }
        
        # 리스크 레벨 기준
        self._risk_levels = {
            'low': 0.8,      # 80% 이상 신뢰도
            'medium': 0.6,   # 60-80% 신뢰도
            'high': 0.0      # 60% 이하 신뢰도
        }
        
        # 모델 가중치 (앙상블용)
        self._model_weights = {
            'random_forest': 0.3,
            'gradient_boosting': 0.3,
            'logistic_regression': 0.2,
            'mlp': 0.2
        }
        
        # 저장된 모델 로드 시도
        self._pattern_learner.load_models()
        
        self._logger.info("PredictionEngine 초기화 완료")
    
    def predict_stock_success(self, stock_data: Dict[str, Any]) -> Optional[PredictionResult]:
        """단일 종목 성공 확률 예측
        
        Args:
            stock_data: 종목 데이터 (stock_code, current_price, volume_ratio 등)
            
        Returns:
            Optional[PredictionResult]: 예측 결과
        """
        try:
            stock_code = stock_data.get('stock_code', '')
            if not stock_code:
                self._logger.error("종목 코드가 없습니다")
                return None
            
            self._logger.debug(f"종목 성공 확률 예측 시작: {stock_code}")
            
            # 1. 피처 추출
            features = self._extract_features_for_prediction(stock_data)
            if not features:
                self._logger.error(f"피처 추출 실패: {stock_code}")
                return None
            
            # 2. 모델별 예측 실행
            model_predictions = {}
            available_models = self._pattern_learner.get_model_performance()['available_models']
            
            for model_name in available_models:
                try:
                    prediction = self._pattern_learner.predict_pattern(features, model_name)
                    if prediction:
                        model_predictions[model_name] = prediction
                except Exception as e:
                    self._logger.warning(f"{model_name} 예측 실패: {e}")
            
            if not model_predictions:
                self._logger.error(f"모든 모델 예측 실패: {stock_code}")
                return None
            
            # 3. 앙상블 예측 계산
            ensemble_result = self._calculate_ensemble_prediction(model_predictions)
            
            # 4. 추천 및 리스크 레벨 결정
            recommendation = self._determine_recommendation(ensemble_result['probability'])
            risk_level = self._determine_risk_level(ensemble_result['confidence'])
            
            # 5. 결과 구성
            prediction_result = PredictionResult(
                stock_code=stock_code,
                stock_name=stock_data.get('stock_name', ''),
                prediction_date=datetime.now().strftime('%Y-%m-%d'),
                ensemble_probability=ensemble_result['probability'],
                ensemble_prediction=ensemble_result['prediction'],
                ensemble_confidence=ensemble_result['confidence'],
                model_predictions=model_predictions,
                recommendation=recommendation,
                risk_level=risk_level,
                sector=stock_data.get('sector', '기타'),
                current_price=stock_data.get('current_price', 0.0),
                target_score=stock_data.get('overall_score', 0.0)
            )
            
            self._logger.debug(f"예측 완료: {stock_code} - 성공확률 {ensemble_result['probability']:.3f}")
            return prediction_result
            
        except Exception as e:
            self._logger.error(f"종목 예측 오류: {e}")
            return None
    
    def predict_multiple_stocks(self, stocks_data: List[Dict[str, Any]]) -> List[PredictionResult]:
        """여러 종목 일괄 예측
        
        Args:
            stocks_data: 종목 데이터 리스트
            
        Returns:
            List[PredictionResult]: 예측 결과 리스트
        """
        try:
            self._logger.info(f"일괄 예측 시작: {len(stocks_data)}개 종목")
            
            results = []
            
            for stock_data in stocks_data:
                result = self.predict_stock_success(stock_data)
                if result:
                    results.append(result)
            
            # 성공 확률 기준으로 정렬
            results.sort(key=lambda x: x.ensemble_probability, reverse=True)
            
            self._logger.info(f"일괄 예측 완료: {len(results)}/{len(stocks_data)}개 성공")
            return results
            
        except Exception as e:
            self._logger.error(f"일괄 예측 오류: {e}")
            return []
    
    def get_top_predictions(self, stocks_data: List[Dict[str, Any]], 
                          top_n: int = 10, min_probability: float = 0.6) -> List[PredictionResult]:
        """상위 예측 종목 선별
        
        Args:
            stocks_data: 종목 데이터 리스트
            top_n: 선별할 상위 종목 수
            min_probability: 최소 성공 확률
            
        Returns:
            List[PredictionResult]: 상위 예측 결과
        """
        try:
            # 전체 예측 실행
            all_predictions = self.predict_multiple_stocks(stocks_data)
            
            # 최소 확률 이상인 종목만 필터링
            filtered_predictions = [
                pred for pred in all_predictions 
                if pred.ensemble_probability >= min_probability
            ]
            
            # 상위 N개 선별
            top_predictions = filtered_predictions[:top_n]
            
            self._logger.info(f"상위 종목 선별 완료: {len(top_predictions)}개 (최소확률: {min_probability:.1%})")
            return top_predictions
            
        except Exception as e:
            self._logger.error(f"상위 예측 선별 오류: {e}")
            return []
    
    def _extract_features_for_prediction(self, stock_data: Dict[str, Any]) -> Optional[PatternFeatures]:
        """예측용 피처 추출"""
        try:
            # 피처 선택기를 통해 17개 피처 추출
            combined_features = self._feature_selector.extract_all_features_from_stock_data(stock_data)
            
            # PatternFeatures 객체로 변환
            features = PatternFeatures(
                features=combined_features.to_array(),
                feature_names=combined_features.get_feature_names(),
                stock_code=stock_data.get('stock_code', ''),
                date=datetime.now().strftime('%Y-%m-%d'),
                sector=stock_data.get('sector', '기타')
            )
            
            return features
            
        except Exception as e:
            self._logger.error(f"예측용 피처 추출 오류: {e}")
            return None
    
    def _calculate_ensemble_prediction(self, model_predictions: Dict[str, PatternPrediction]) -> Dict[str, float]:
        """앙상블 예측 계산"""
        try:
            weighted_probabilities = []
            weighted_confidences = []
            predictions = []
            
            total_weight = 0.0
            
            for model_name, prediction in model_predictions.items():
                weight = self._model_weights.get(model_name, 0.25)  # 기본 가중치 0.25
                
                weighted_probabilities.append(prediction.success_probability * weight)
                weighted_confidences.append(prediction.confidence_score * weight)
                predictions.append(prediction.predicted_class)
                
                total_weight += weight
            
            # 가중치 정규화
            if total_weight > 0:
                ensemble_probability = sum(weighted_probabilities) / total_weight
                ensemble_confidence = sum(weighted_confidences) / total_weight
            else:
                ensemble_probability = np.mean([p.success_probability for p in model_predictions.values()])
                ensemble_confidence = np.mean([p.confidence_score for p in model_predictions.values()])
            
            # 앙상블 예측 클래스 (0.5 임계값)
            ensemble_prediction = 1 if ensemble_probability >= 0.5 else 0
            
            return {
                'probability': float(ensemble_probability),
                'confidence': float(ensemble_confidence),
                'prediction': int(ensemble_prediction)
            }
            
        except Exception as e:
            self._logger.error(f"앙상블 예측 계산 오류: {e}")
            return {'probability': 0.5, 'confidence': 0.5, 'prediction': 0}
    
    def _determine_recommendation(self, success_probability: float) -> str:
        """성공 확률 기반 추천 결정"""
        if success_probability >= self._prediction_thresholds['buy']:
            return 'BUY'
        elif success_probability >= self._prediction_thresholds['hold']:
            return 'HOLD'
        else:
            return 'SELL'
    
    def _determine_risk_level(self, confidence_score: float) -> str:
        """신뢰도 기반 리스크 레벨 결정"""
        if confidence_score >= self._risk_levels['low']:
            return 'LOW'
        elif confidence_score >= self._risk_levels['medium']:
            return 'MEDIUM'
        else:
            return 'HIGH'
    
    def update_prediction_thresholds(self, thresholds: Dict[str, float]):
        """예측 임계값 업데이트
        
        Args:
            thresholds: 새로운 임계값 설정
        """
        try:
            self._prediction_thresholds.update(thresholds)
            self._logger.info(f"예측 임계값 업데이트: {thresholds}")
        except Exception as e:
            self._logger.error(f"임계값 업데이트 오류: {e}")
    
    def update_model_weights(self, weights: Dict[str, float]):
        """모델 가중치 업데이트
        
        Args:
            weights: 새로운 모델 가중치
        """
        try:
            # 가중치 합이 1이 되도록 정규화
            total_weight = sum(weights.values())
            if total_weight > 0:
                normalized_weights = {k: v/total_weight for k, v in weights.items()}
                self._model_weights.update(normalized_weights)
                self._logger.info(f"모델 가중치 업데이트: {normalized_weights}")
            else:
                self._logger.error("가중치 합이 0입니다")
        except Exception as e:
            self._logger.error(f"가중치 업데이트 오류: {e}")
    
    def save_prediction_results(self, results: List[PredictionResult], filepath: str) -> bool:
        """예측 결과 저장
        
        Args:
            results: 예측 결과 리스트
            filepath: 저장 경로
            
        Returns:
            bool: 저장 성공 여부
        """
        try:
            save_data = {
                'predictions': [result.to_dict() for result in results],
                'prediction_metadata': {
                    'total_predictions': len(results),
                    'high_confidence_count': len([r for r in results if r.risk_level == 'LOW']),
                    'buy_recommendations': len([r for r in results if r.recommendation == 'BUY']),
                    'prediction_thresholds': self._prediction_thresholds,
                    'model_weights': self._model_weights,
                    'timestamp': datetime.now().isoformat()
                }
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)
            
            self._logger.info(f"예측 결과 저장 완료: {filepath}")
            return True
            
        except Exception as e:
            self._logger.error(f"예측 결과 저장 오류: {e}")
            return False
    
    def get_prediction_summary(self, results: List[PredictionResult]) -> Dict[str, Any]:
        """예측 결과 요약
        
        Args:
            results: 예측 결과 리스트
            
        Returns:
            Dict[str, Any]: 요약 정보
        """
        try:
            if not results:
                return {}
            
            # 기본 통계
            probabilities = [r.ensemble_probability for r in results]
            confidences = [r.ensemble_confidence for r in results]
            
            # 추천별 집계
            recommendation_counts = {}
            for rec in ['BUY', 'HOLD', 'SELL']:
                recommendation_counts[rec] = len([r for r in results if r.recommendation == rec])
            
            # 리스크별 집계
            risk_counts = {}
            for risk in ['LOW', 'MEDIUM', 'HIGH']:
                risk_counts[risk] = len([r for r in results if r.risk_level == risk])
            
            # 섹터별 집계
            sector_performance = {}
            for result in results:
                sector = result.sector
                if sector not in sector_performance:
                    sector_performance[sector] = {
                        'count': 0,
                        'avg_probability': 0.0,
                        'buy_count': 0
                    }
                
                sector_performance[sector]['count'] += 1
                sector_performance[sector]['avg_probability'] += result.ensemble_probability
                if result.recommendation == 'BUY':
                    sector_performance[sector]['buy_count'] += 1
            
            # 섹터별 평균 계산
            for sector_data in sector_performance.values():
                if sector_data['count'] > 0:
                    sector_data['avg_probability'] /= sector_data['count']
            
            summary = {
                'total_predictions': len(results),
                'average_probability': float(np.mean(probabilities)),
                'average_confidence': float(np.mean(confidences)),
                'max_probability': float(np.max(probabilities)),
                'min_probability': float(np.min(probabilities)),
                'recommendation_distribution': recommendation_counts,
                'risk_distribution': risk_counts,
                'sector_performance': sector_performance,
                'high_confidence_buy_count': len([
                    r for r in results 
                    if r.recommendation == 'BUY' and r.risk_level == 'LOW'
                ])
            }
            
            return summary
            
        except Exception as e:
            self._logger.error(f"예측 요약 생성 오류: {e}")
            return {} 