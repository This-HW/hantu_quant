"""
예측 엔진

패턴 학습 모델을 활용하여 실시간 예측을 수행하고
예측 결과를 관리하는 시스템
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
import json
import os

from ...utils.logging import get_logger
from .pattern_learner import PatternLearner

logger = get_logger(__name__)

class PredictionConfidence(Enum):
    """예측 신뢰도 등급"""
    VERY_HIGH = "very_high"    # 95% 이상
    HIGH = "high"              # 85% 이상
    MEDIUM = "medium"          # 70% 이상
    LOW = "low"                # 55% 이상
    VERY_LOW = "very_low"      # 55% 미만

@dataclass
class PredictionConfig:
    """예측 설정"""
    confidence_threshold: float = 0.7     # 최소 신뢰도 임계값
    probability_threshold: float = 0.6    # 성공 확률 임계값
    max_predictions_per_day: int = 20     # 일일 최대 예측 수
    enable_ensemble: bool = True          # 앙상블 예측 사용
    save_predictions: bool = True         # 예측 결과 저장
    auto_feedback: bool = True            # 자동 피드백 수집

@dataclass
class PredictionResult:
    """예측 결과"""
    prediction_id: str
    stock_code: str
    stock_name: str
    prediction_date: datetime
    success_probability: float
    confidence: float
    confidence_level: PredictionConfidence
    recommendation: str                   # BUY, HOLD, SELL
    expected_return: float
    risk_score: float
    reasoning: List[str]                  # 예측 근거
    model_contributions: Dict[str, float] # 각 모델의 기여도
    actual_result: Optional[float] = None # 실제 결과 (나중에 업데이트)
    is_validated: bool = False

class PredictionEngine:
    """예측 엔진"""
    
    def __init__(self, pattern_learner: PatternLearner,
                 config: PredictionConfig = None,
                 data_dir: str = "data/predictions"):
        """
        초기화
        
        Args:
            pattern_learner: 패턴 학습기
            config: 예측 설정
            data_dir: 예측 데이터 저장 디렉토리
        """
        self._logger = logger
        self._pattern_learner = pattern_learner
        self._config = config or PredictionConfig()
        self._data_dir = data_dir
        
        # 디렉토리 생성
        os.makedirs(data_dir, exist_ok=True)
        
        # 예측 기록
        self._predictions = []
        self._daily_prediction_count = {}
        
        # 예측 성과 추적
        self._prediction_accuracy = {}
        
        # 기존 예측 로드
        self._load_predictions()
        
        self._logger.info("예측 엔진 초기화 완료")
    
    def predict_stock(self, stock_code: str, stock_name: str = None,
                     date: datetime = None) -> Optional[PredictionResult]:
        """단일 종목 예측"""
        if date is None:
            date = datetime.now()
        
        # 일일 예측 수 제한 확인
        date_key = date.strftime('%Y-%m-%d')
        if date_key in self._daily_prediction_count:
            if self._daily_prediction_count[date_key] >= self._config.max_predictions_per_day:
                self._logger.warning(f"일일 예측 수 제한 초과: {date_key}")
                return None
        
        try:
            # 패턴 기반 예측 수행
            pattern_prediction = self._pattern_learner.predict_pattern(stock_code, date)
            
            success_probability = pattern_prediction['success_probability']
            confidence = pattern_prediction['confidence']
            
            # 신뢰도 등급 결정
            confidence_level = self._determine_confidence_level(confidence)
            
            # 최소 신뢰도 확인
            if confidence < self._config.confidence_threshold:
                self._logger.info(f"신뢰도 부족으로 예측 스킵: {stock_code} (신뢰도: {confidence:.3f})")
                return None
            
            # 추천 결정
            recommendation = self._generate_recommendation(success_probability, confidence)
            
            # 기대 수익률 계산
            expected_return = self._calculate_expected_return(success_probability, confidence)
            
            # 리스크 점수 계산
            risk_score = self._calculate_risk_score(success_probability, confidence)
            
            # 예측 근거 생성
            reasoning = self._generate_reasoning(pattern_prediction, confidence_level)
            
            # 예측 결과 생성
            prediction_result = PredictionResult(
                prediction_id=f"{stock_code}_{date.strftime('%Y%m%d_%H%M%S')}",
                stock_code=stock_code,
                stock_name=stock_name or stock_code,
                prediction_date=date,
                success_probability=success_probability,
                confidence=confidence,
                confidence_level=confidence_level,
                recommendation=recommendation,
                expected_return=expected_return,
                risk_score=risk_score,
                reasoning=reasoning,
                model_contributions=pattern_prediction.get('individual_predictions', {}),
                actual_result=None,
                is_validated=False
            )
            
            # 예측 기록
            self._predictions.append(prediction_result)
            
            # 일일 카운트 업데이트
            if date_key not in self._daily_prediction_count:
                self._daily_prediction_count[date_key] = 0
            self._daily_prediction_count[date_key] += 1
            
            # 저장
            if self._config.save_predictions:
                self._save_predictions()
            
            self._logger.info(f"예측 완료: {stock_code} - {recommendation} (확률: {success_probability:.3f}, 신뢰도: {confidence:.3f})")
            return prediction_result
            
        except Exception as e:
            self._logger.error(f"예측 실패 {stock_code}: {e}")
            return None
    
    def predict_multiple_stocks(self, stock_list: List[Tuple[str, str]],
                               date: datetime = None) -> List[PredictionResult]:
        """다중 종목 예측"""
        if date is None:
            date = datetime.now()
        
        predictions = []
        
        for stock_code, stock_name in stock_list:
            prediction = self.predict_stock(stock_code, stock_name, date)
            if prediction:
                predictions.append(prediction)
        
        # 성공 확률 순으로 정렬
        predictions.sort(key=lambda x: x.success_probability, reverse=True)
        
        self._logger.info(f"다중 종목 예측 완료: {len(predictions)}개 예측 생성")
        return predictions
    
    def _determine_confidence_level(self, confidence: float) -> PredictionConfidence:
        """신뢰도 등급 결정"""
        if confidence >= 0.95:
            return PredictionConfidence.VERY_HIGH
        elif confidence >= 0.85:
            return PredictionConfidence.HIGH
        elif confidence >= 0.70:
            return PredictionConfidence.MEDIUM
        elif confidence >= 0.55:
            return PredictionConfidence.LOW
        else:
            return PredictionConfidence.VERY_LOW
    
    def _generate_recommendation(self, success_probability: float, confidence: float) -> str:
        """투자 추천 생성"""
        # 신뢰도가 높고 성공 확률이 높으면 BUY
        if confidence >= 0.8 and success_probability >= self._config.probability_threshold:
            return "BUY"
        # 성공 확률이 낮으면 SELL
        elif success_probability <= 0.4:
            return "SELL"
        # 그 외는 HOLD
        else:
            return "HOLD"
    
    def _calculate_expected_return(self, success_probability: float, confidence: float) -> float:
        """기대 수익률 계산"""
        # 성공 시 기대 수익률 (5-15%)
        success_return = 0.05 + (success_probability - 0.5) * 0.2
        
        # 실패 시 기대 손실률 (-3% ~ -8%)
        failure_return = -0.03 - (1 - success_probability) * 0.1
        
        # 기대값 계산
        expected_return = (success_probability * success_return + 
                          (1 - success_probability) * failure_return)
        
        # 신뢰도로 조정
        expected_return *= confidence
        
        return expected_return
    
    def _calculate_risk_score(self, success_probability: float, confidence: float) -> float:
        """리스크 점수 계산 (0-1, 낮을수록 안전)"""
        # 성공 확률이 낮을수록, 신뢰도가 낮을수록 위험
        base_risk = 1 - success_probability
        confidence_risk = 1 - confidence
        
        # 가중 평균
        risk_score = base_risk * 0.7 + confidence_risk * 0.3
        
        return min(1.0, max(0.0, risk_score))
    
    def _generate_reasoning(self, pattern_prediction: Dict[str, Any], 
                          confidence_level: PredictionConfidence) -> List[str]:
        """예측 근거 생성"""
        reasoning = []
        
        success_prob = pattern_prediction['success_probability']
        individual_preds = pattern_prediction.get('individual_predictions', {})
        
        # 성공 확률 기반 근거
        if success_prob >= 0.8:
            reasoning.append("과거 데이터 분석 결과 높은 성공 확률을 보임")
        elif success_prob >= 0.6:
            reasoning.append("과거 데이터 분석 결과 중간 수준의 성공 확률을 보임")
        else:
            reasoning.append("과거 데이터 분석 결과 낮은 성공 확률을 보임")
        
        # 신뢰도 기반 근거
        if confidence_level == PredictionConfidence.VERY_HIGH:
            reasoning.append("모든 모델이 일치된 예측을 보임 (매우 높은 신뢰도)")
        elif confidence_level == PredictionConfidence.HIGH:
            reasoning.append("대부분 모델이 유사한 예측을 보임 (높은 신뢰도)")
        elif confidence_level == PredictionConfidence.MEDIUM:
            reasoning.append("모델 간 적정한 합의를 보임 (중간 신뢰도)")
        else:
            reasoning.append("모델 간 의견이 분산됨 (낮은 신뢰도)")
        
        # 개별 모델 기여도
        if individual_preds:
            best_model = max(individual_preds.items(), key=lambda x: x[1])
            reasoning.append(f"{best_model[0]} 모델이 가장 강한 긍정 신호를 보임")
        
        # 패턴 기반 근거 (실제로는 더 세부적인 패턴 분석 필요)
        reasoning.append("기술적 지표 패턴 분석 결과 반영")
        
        return reasoning
    
    def update_prediction_result(self, prediction_id: str, actual_return: float) -> bool:
        """예측 결과 업데이트"""
        try:
            for prediction in self._predictions:
                if prediction.prediction_id == prediction_id:
                    prediction.actual_result = actual_return
                    prediction.is_validated = True
                    
                    # 예측 정확도 업데이트
                    self._update_prediction_accuracy(prediction)
                    
                    # 저장
                    if self._config.save_predictions:
                        self._save_predictions()
                    
                    self._logger.info(f"예측 결과 업데이트: {prediction_id} - 실제 수익률: {actual_return:.3f}")
                    return True
            
            self._logger.warning(f"예측 ID를 찾을 수 없음: {prediction_id}")
            return False
            
        except Exception as e:
            self._logger.error(f"예측 결과 업데이트 실패: {e}")
            return False
    
    def _update_prediction_accuracy(self, prediction: PredictionResult):
        """예측 정확도 업데이트"""
        if prediction.actual_result is None:
            return
        
        # 성공 여부 판단 (실제 수익률 > 3%)
        actual_success = prediction.actual_result > 0.03
        predicted_success = prediction.success_probability > 0.5
        
        # 정확도 계산
        is_correct = actual_success == predicted_success
        
        # 모델별 정확도 업데이트
        for model_name in prediction.model_contributions.keys():
            if model_name not in self._prediction_accuracy:
                self._prediction_accuracy[model_name] = {
                    'total_predictions': 0,
                    'correct_predictions': 0,
                    'accuracy': 0.0
                }
            
            self._prediction_accuracy[model_name]['total_predictions'] += 1
            if is_correct:
                self._prediction_accuracy[model_name]['correct_predictions'] += 1
            
            # 정확도 재계산
            total = self._prediction_accuracy[model_name]['total_predictions']
            correct = self._prediction_accuracy[model_name]['correct_predictions']
            self._prediction_accuracy[model_name]['accuracy'] = correct / total if total > 0 else 0.0
    
    def get_prediction_accuracy(self) -> Dict[str, float]:
        """예측 정확도 반환"""
        return {
            model_name: metrics['accuracy']
            for model_name, metrics in self._prediction_accuracy.items()
        }
    
    def get_predictions_by_date(self, date: datetime) -> List[PredictionResult]:
        """특정 날짜의 예측 조회"""
        date_str = date.strftime('%Y-%m-%d')
        
        return [
            p for p in self._predictions
            if p.prediction_date.strftime('%Y-%m-%d') == date_str
        ]
    
    def get_recent_predictions(self, days: int = 7) -> List[PredictionResult]:
        """최근 예측 조회"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        return [
            p for p in self._predictions
            if start_date <= p.prediction_date <= end_date
        ]
    
    def get_top_recommendations(self, count: int = 10, 
                               min_confidence: float = None) -> List[PredictionResult]:
        """상위 추천 종목 조회"""
        # 최근 7일 예측 중 BUY 추천
        recent_predictions = self.get_recent_predictions(days=7)
        buy_recommendations = [
            p for p in recent_predictions
            if p.recommendation == "BUY"
        ]
        
        # 신뢰도 필터링
        if min_confidence:
            buy_recommendations = [
                p for p in buy_recommendations
                if p.confidence >= min_confidence
            ]
        
        # 성공 확률 순으로 정렬
        buy_recommendations.sort(key=lambda x: x.success_probability, reverse=True)
        
        return buy_recommendations[:count]
    
    def generate_prediction_report(self, days: int = 30) -> str:
        """예측 리포트 생성"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # 기간 내 예측 필터링
        period_predictions = [
            p for p in self._predictions
            if start_date <= p.prediction_date <= end_date
        ]
        
        if not period_predictions:
            return f"# 예측 리포트 ({days}일간)\n\n분석할 예측 데이터가 없습니다."
        
        # 검증된 예측
        validated_predictions = [p for p in period_predictions if p.is_validated]
        
        # 통계 계산
        total_predictions = len(period_predictions)
        validated_count = len(validated_predictions)
        
        # 추천별 분포
        buy_count = len([p for p in period_predictions if p.recommendation == "BUY"])
        hold_count = len([p for p in period_predictions if p.recommendation == "HOLD"])
        sell_count = len([p for p in period_predictions if p.recommendation == "SELL"])
        
        # 신뢰도별 분포
        confidence_dist = {}
        for conf_level in PredictionConfidence:
            count = len([p for p in period_predictions if p.confidence_level == conf_level])
            confidence_dist[conf_level.value] = count
        
        # 정확도 (검증된 예측만)
        accuracy_info = ""
        if validated_predictions:
            correct_predictions = 0
            for pred in validated_predictions:
                actual_success = pred.actual_result > 0.03
                predicted_success = pred.success_probability > 0.5
                if actual_success == predicted_success:
                    correct_predictions += 1
            
            accuracy = correct_predictions / validated_count
            accuracy_info = f"- **예측 정확도**: {accuracy:.1%} ({correct_predictions}/{validated_count})"
        else:
            accuracy_info = "- **예측 정확도**: 검증 데이터 부족"
        
        # 리포트 생성
        report = [
            f"# 📊 예측 엔진 리포트 ({days}일간)",
            "",
            f"**분석 기간**: {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}",
            f"**생성 일시**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## 📈 예측 통계",
            "",
            f"- **총 예측 수**: {total_predictions}개",
            f"- **검증된 예측**: {validated_count}개",
            accuracy_info,
            "",
            "## 🎯 추천 분포",
            "",
            f"- **BUY**: {buy_count}개 ({buy_count/total_predictions:.1%})",
            f"- **HOLD**: {hold_count}개 ({hold_count/total_predictions:.1%})",  
            f"- **SELL**: {sell_count}개 ({sell_count/total_predictions:.1%})",
            "",
            "## 🔍 신뢰도 분포",
            ""
        ]
        
        for conf_level, count in confidence_dist.items():
            percentage = count / total_predictions * 100
            report.append(f"- **{conf_level}**: {count}개 ({percentage:.1f}%)")
        
        # 상위 추천 종목
        top_recommendations = self.get_top_recommendations(count=5)
        if top_recommendations:
            report.extend([
                "",
                "## 🏆 상위 추천 종목",
                "",
                "| 종목코드 | 종목명 | 성공확률 | 신뢰도 | 기대수익률 |",
                "|---------|-------|----------|--------|----------|"
            ])
            
            for pred in top_recommendations:
                report.append(
                    f"| {pred.stock_code} | {pred.stock_name} | "
                    f"{pred.success_probability:.1%} | {pred.confidence:.1%} | "
                    f"{pred.expected_return:.2%} |"
                )
        
        return "\n".join(report)
    
    def _save_predictions(self):
        """예측 결과 저장"""
        try:
            predictions_data = []
            for pred in self._predictions:
                pred_dict = asdict(pred)
                pred_dict['prediction_date'] = pred.prediction_date.isoformat()
                pred_dict['confidence_level'] = pred.confidence_level.value
                predictions_data.append(pred_dict)
            
            predictions_file = os.path.join(self._data_dir, "predictions.json")
            with open(predictions_file, 'w', encoding='utf-8') as f:
                json.dump(predictions_data, f, ensure_ascii=False, indent=2, default=str)
            
            # 정확도 데이터 저장
            accuracy_file = os.path.join(self._data_dir, "prediction_accuracy.json")
            with open(accuracy_file, 'w', encoding='utf-8') as f:
                json.dump(self._prediction_accuracy, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            self._logger.error(f"예측 결과 저장 실패: {e}")
    
    def _load_predictions(self):
        """예측 결과 로드"""
        try:
            predictions_file = os.path.join(self._data_dir, "predictions.json")
            if os.path.exists(predictions_file):
                with open(predictions_file, 'r', encoding='utf-8') as f:
                    predictions_data = json.load(f)
                
                for pred_dict in predictions_data:
                    pred_dict['prediction_date'] = datetime.fromisoformat(pred_dict['prediction_date'])
                    pred_dict['confidence_level'] = PredictionConfidence(pred_dict['confidence_level'])
                    
                    prediction = PredictionResult(**pred_dict)
                    self._predictions.append(prediction)
            
            # 정확도 데이터 로드
            accuracy_file = os.path.join(self._data_dir, "prediction_accuracy.json")
            if os.path.exists(accuracy_file):
                with open(accuracy_file, 'r', encoding='utf-8') as f:
                    self._prediction_accuracy = json.load(f)
                    
            self._logger.info(f"예측 결과 로드 완료: {len(self._predictions)}개")
            
        except Exception as e:
            self._logger.error(f"예측 결과 로드 실패: {e}")

# 전역 인스턴스
_prediction_engine = None

def get_prediction_engine(pattern_learner: PatternLearner) -> PredictionEngine:
    """예측 엔진 싱글톤 인스턴스 반환"""
    global _prediction_engine
    if _prediction_engine is None:
        _prediction_engine = PredictionEngine(pattern_learner)
    return _prediction_engine 