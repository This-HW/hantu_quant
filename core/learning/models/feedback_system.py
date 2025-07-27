"""
피드백 시스템

예측 결과와 실제 성과를 비교하여 모델의 성능을 분석하고
지속적인 학습 개선을 위한 피드백을 제공하는 시스템
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
from .prediction_engine import PredictionEngine, PredictionResult
from ..analysis.daily_performance import DailyPerformanceAnalyzer, PerformanceMetrics

logger = get_logger(__name__)

class ModelPerformanceLevel(Enum):
    """모델 성능 등급"""
    EXCELLENT = "excellent"    # 90% 이상
    GOOD = "good"             # 80% 이상
    AVERAGE = "average"       # 70% 이상
    POOR = "poor"             # 60% 이상
    CRITICAL = "critical"     # 60% 미만

@dataclass
class FeedbackData:
    """피드백 데이터"""
    feedback_id: str
    prediction_id: str
    stock_code: str
    predicted_success_prob: float
    actual_return: float
    prediction_accuracy: float     # 이 예측의 정확도
    error_magnitude: float         # 예측 오차 크기
    feedback_date: datetime
    model_contributions: Dict[str, float]
    learning_insights: List[str]   # 학습 인사이트

@dataclass
class ModelPerformance:
    """모델 성능 평가"""
    model_name: str
    evaluation_period: int         # 평가 기간 (일)
    total_predictions: int
    correct_predictions: int
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    avg_confidence: float
    avg_error_magnitude: float
    performance_level: ModelPerformanceLevel
    trend: str                     # improving, stable, declining
    recommendations: List[str]     # 개선 추천사항

class FeedbackSystem:
    """피드백 시스템"""
    
    def __init__(self, prediction_engine: PredictionEngine,
                 performance_analyzer: DailyPerformanceAnalyzer,
                 data_dir: str = "data/feedback"):
        """
        초기화
        
        Args:
            prediction_engine: 예측 엔진
            performance_analyzer: 성과 분석기
            data_dir: 피드백 데이터 저장 디렉토리
        """
        self._logger = logger
        self._prediction_engine = prediction_engine
        self._performance_analyzer = performance_analyzer
        self._data_dir = data_dir
        
        # 디렉토리 생성
        os.makedirs(data_dir, exist_ok=True)
        
        # 피드백 데이터
        self._feedback_data = []
        self._model_performance_history = []
        
        # 성능 임계값
        self._performance_thresholds = {
            'excellent': 0.9,
            'good': 0.8,
            'average': 0.7,
            'poor': 0.6
        }
        
        # 기존 데이터 로드
        self._load_feedback_data()
        
        self._logger.info("피드백 시스템 초기화 완료")
    
    def collect_feedback(self, prediction_id: str, actual_return: float) -> bool:
        """피드백 수집"""
        try:
            # 예측 결과 찾기
            prediction = self._find_prediction(prediction_id)
            if not prediction:
                self._logger.warning(f"예측을 찾을 수 없음: {prediction_id}")
                return False
            
            # 예측 정확도 계산
            predicted_success = prediction.success_probability > 0.5
            actual_success = actual_return > 0.03  # 3% 이상을 성공으로 정의
            prediction_accuracy = 1.0 if predicted_success == actual_success else 0.0
            
            # 오차 크기 계산
            # 예측된 성공 확률과 실제 성공 여부의 차이
            actual_prob = 1.0 if actual_success else 0.0
            error_magnitude = abs(prediction.success_probability - actual_prob)
            
            # 학습 인사이트 생성
            learning_insights = self._generate_learning_insights(
                prediction, actual_return, prediction_accuracy
            )
            
            # 피드백 데이터 생성
            feedback_data = FeedbackData(
                feedback_id=f"fb_{prediction_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                prediction_id=prediction_id,
                stock_code=prediction.stock_code,
                predicted_success_prob=prediction.success_probability,
                actual_return=actual_return,
                prediction_accuracy=prediction_accuracy,
                error_magnitude=error_magnitude,
                feedback_date=datetime.now(),
                model_contributions=prediction.model_contributions,
                learning_insights=learning_insights
            )
            
            # 피드백 기록
            self._feedback_data.append(feedback_data)
            
            # 예측 엔진에 실제 결과 업데이트
            self._prediction_engine.update_prediction_result(prediction_id, actual_return)
            
            # 저장
            self._save_feedback_data()
            
            self._logger.info(f"피드백 수집 완료: {prediction_id} - 정확도: {prediction_accuracy:.1f}")
            return True
            
        except Exception as e:
            self._logger.error(f"피드백 수집 실패: {e}")
            return False
    
    def _find_prediction(self, prediction_id: str) -> Optional[PredictionResult]:
        """예측 결과 찾기"""
        recent_predictions = self._prediction_engine.get_recent_predictions(days=30)
        
        for prediction in recent_predictions:
            if prediction.prediction_id == prediction_id:
                return prediction
        
        return None
    
    def _generate_learning_insights(self, prediction: PredictionResult,
                                  actual_return: float, accuracy: float) -> List[str]:
        """학습 인사이트 생성"""
        insights = []
        
        # 정확도 기반 인사이트
        if accuracy == 1.0:
            insights.append("예측이 정확했음 - 현재 모델 성능 양호")
            
            if prediction.confidence >= 0.8:
                insights.append("높은 신뢰도로 정확한 예측 - 모델 신뢰성 확인")
            else:
                insights.append("낮은 신뢰도임에도 정확한 예측 - 신뢰도 계산 방식 검토 필요")
        else:
            insights.append("예측이 부정확했음 - 모델 개선 필요")
            
            if prediction.confidence >= 0.8:
                insights.append("높은 신뢰도로 잘못된 예측 - 모델 재훈련 고려")
            else:
                insights.append("낮은 신뢰도로 잘못된 예측 - 신뢰도 임계값 상향 조정 검토")
        
        # 수익률 기반 인사이트
        if actual_return > 0.1:  # 10% 이상
            insights.append("실제 높은 수익률 달성 - 유사 패턴 강화 학습 필요")
        elif actual_return < -0.05:  # -5% 이하
            insights.append("실제 손실 발생 - 위험 패턴 식별 및 회피 학습 필요")
        
        # 예측 근거 검증
        if "높은 성공 확률" in " ".join(prediction.reasoning) and actual_return < 0:
            insights.append("높은 성공 확률 예측이 실패 - 성공 패턴 재검토 필요")
        
        # 모델별 기여도 분석
        if prediction.model_contributions:
            best_contributing_model = max(prediction.model_contributions.items(), key=lambda x: x[1])
            if accuracy == 0.0:
                insights.append(f"{best_contributing_model[0]} 모델의 성능 검토 필요")
            else:
                insights.append(f"{best_contributing_model[0]} 모델의 우수 성능 확인")
        
        return insights
    
    def evaluate_model_performance(self, days: int = 30) -> Dict[str, ModelPerformance]:
        """모델 성능 평가"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # 기간 내 피드백 데이터 필터링
        period_feedback = [
            fb for fb in self._feedback_data
            if start_date <= fb.feedback_date <= end_date
        ]
        
        if not period_feedback:
            self._logger.warning("평가할 피드백 데이터가 없습니다")
            return {}
        
        # 모델별 성능 평가
        model_performances = {}
        
        # 모든 모델 이름 수집
        all_models = set()
        for fb in period_feedback:
            all_models.update(fb.model_contributions.keys())
        
        for model_name in all_models:
            model_feedback = [
                fb for fb in period_feedback
                if model_name in fb.model_contributions
            ]
            
            if not model_feedback:
                continue
            
            # 성능 지표 계산
            total_predictions = len(model_feedback)
            correct_predictions = sum(1 for fb in model_feedback if fb.prediction_accuracy == 1.0)
            accuracy = correct_predictions / total_predictions if total_predictions > 0 else 0.0
            
            # 신뢰도 및 오차 평균
            avg_confidence = np.mean([
                fb.model_contributions[model_name] for fb in model_feedback
            ])
            avg_error_magnitude = np.mean([fb.error_magnitude for fb in model_feedback])
            
            # 정밀도, 재현율, F1 스코어 계산
            true_positives = sum(1 for fb in model_feedback 
                               if fb.predicted_success_prob > 0.5 and fb.actual_return > 0.03)
            false_positives = sum(1 for fb in model_feedback 
                                if fb.predicted_success_prob > 0.5 and fb.actual_return <= 0.03)
            false_negatives = sum(1 for fb in model_feedback 
                                if fb.predicted_success_prob <= 0.5 and fb.actual_return > 0.03)
            
            precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0
            recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0.0
            f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
            
            # 성능 등급 결정
            performance_level = self._determine_performance_level(accuracy)
            
            # 트렌드 분석
            trend = self._analyze_performance_trend(model_name, days)
            
            # 추천사항 생성
            recommendations = self._generate_model_recommendations(
                model_name, accuracy, precision, recall, avg_error_magnitude
            )
            
            # 모델 성능 객체 생성
            model_performances[model_name] = ModelPerformance(
                model_name=model_name,
                evaluation_period=days,
                total_predictions=total_predictions,
                correct_predictions=correct_predictions,
                accuracy=accuracy,
                precision=precision,
                recall=recall,
                f1_score=f1_score,
                avg_confidence=avg_confidence,
                avg_error_magnitude=avg_error_magnitude,
                performance_level=performance_level,
                trend=trend,
                recommendations=recommendations
            )
        
        # 성능 기록 저장
        self._model_performance_history.append({
            'evaluation_date': datetime.now(),
            'period_days': days,
            'performances': model_performances
        })
        
        self._logger.info(f"모델 성능 평가 완료: {len(model_performances)}개 모델")
        return model_performances
    
    def _determine_performance_level(self, accuracy: float) -> ModelPerformanceLevel:
        """성능 등급 결정"""
        if accuracy >= self._performance_thresholds['excellent']:
            return ModelPerformanceLevel.EXCELLENT
        elif accuracy >= self._performance_thresholds['good']:
            return ModelPerformanceLevel.GOOD
        elif accuracy >= self._performance_thresholds['average']:
            return ModelPerformanceLevel.AVERAGE
        elif accuracy >= self._performance_thresholds['poor']:
            return ModelPerformanceLevel.POOR
        else:
            return ModelPerformanceLevel.CRITICAL
    
    def _analyze_performance_trend(self, model_name: str, current_days: int) -> str:
        """성능 트렌드 분석"""
        if len(self._model_performance_history) < 2:
            return "stable"  # 비교할 이전 데이터 부족
        
        # 최근 2개 평가 결과 비교
        recent_performances = self._model_performance_history[-2:]
        
        current_accuracy = None
        previous_accuracy = None
        
        for perf_record in recent_performances:
            if model_name in perf_record['performances']:
                if current_accuracy is None:
                    previous_accuracy = perf_record['performances'][model_name].accuracy
                else:
                    current_accuracy = perf_record['performances'][model_name].accuracy
        
        if current_accuracy is None or previous_accuracy is None:
            return "stable"
        
        # 트렌드 판단
        diff = current_accuracy - previous_accuracy
        if diff > 0.05:  # 5% 이상 향상
            return "improving"
        elif diff < -0.05:  # 5% 이상 하락
            return "declining"
        else:
            return "stable"
    
    def _generate_model_recommendations(self, model_name: str, accuracy: float,
                                      precision: float, recall: float,
                                      avg_error: float) -> List[str]:
        """모델 개선 추천사항 생성"""
        recommendations = []
        
        # 정확도 기반 추천
        if accuracy < 0.7:
            recommendations.append("모델 재훈련 필요 - 정확도가 70% 미만")
            recommendations.append("더 많은 학습 데이터 수집 검토")
            recommendations.append("하이퍼파라미터 재조정 고려")
        elif accuracy < 0.8:
            recommendations.append("모델 파인튜닝 검토 - 정확도 개선 여지 있음")
        
        # 정밀도/재현율 기반 추천
        if precision < 0.6:
            recommendations.append("거짓 양성 감소 필요 - 예측 임계값 상향 조정 검토")
        
        if recall < 0.6:
            recommendations.append("거짓 음성 감소 필요 - 예측 민감도 향상 필요")
        
        # 오차 크기 기반 추천
        if avg_error > 0.3:
            recommendations.append("예측 오차가 큼 - 피처 엔지니어링 재검토")
            recommendations.append("모델 복잡도 조정 고려")
        
        # 모델별 특화 추천
        if model_name == "neural_network" and accuracy < 0.75:
            recommendations.append("신경망 구조 재설계 검토")
            recommendations.append("드롭아웃 비율 조정 고려")
        elif model_name == "random_forest" and accuracy < 0.75:
            recommendations.append("트리 개수 및 깊이 조정 검토")
            recommendations.append("피처 중요도 기반 피처 선택 재검토")
        
        if not recommendations:
            recommendations.append("현재 성능 양호 - 정기적 모니터링 유지")
        
        return recommendations
    
    def get_feedback_summary(self, days: int = 30) -> Dict[str, Any]:
        """피드백 요약 정보"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        period_feedback = [
            fb for fb in self._feedback_data
            if start_date <= fb.feedback_date <= end_date
        ]
        
        if not period_feedback:
            return {'no_data': True, 'message': f'최근 {days}일간 피드백 데이터가 없습니다.'}
        
        # 통계 계산
        total_feedback = len(period_feedback)
        correct_predictions = sum(1 for fb in period_feedback if fb.prediction_accuracy == 1.0)
        overall_accuracy = correct_predictions / total_feedback
        avg_error = np.mean([fb.error_magnitude for fb in period_feedback])
        
        # 성공/실패 분포
        actual_successes = sum(1 for fb in period_feedback if fb.actual_return > 0.03)
        predicted_successes = sum(1 for fb in period_feedback if fb.predicted_success_prob > 0.5)
        
        return {
            'period_days': days,
            'total_feedback': total_feedback,
            'overall_accuracy': overall_accuracy,
            'correct_predictions': correct_predictions,
            'average_error_magnitude': avg_error,
            'actual_success_rate': actual_successes / total_feedback,
            'predicted_success_rate': predicted_successes / total_feedback,
            'prediction_vs_reality_gap': abs(predicted_successes - actual_successes) / total_feedback
        }
    
    def generate_feedback_report(self, days: int = 30) -> str:
        """피드백 리포트 생성"""
        # 피드백 요약
        summary = self.get_feedback_summary(days)
        
        if summary.get('no_data', False):
            return f"# 피드백 시스템 리포트 ({days}일간)\n\n{summary['message']}"
        
        # 모델 성능 평가
        model_performances = self.evaluate_model_performance(days)
        
        # 리포트 생성
        report = [
            f"# 🔄 피드백 시스템 리포트 ({days}일간)",
            "",
            f"**분석 기간**: {(datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')} ~ {datetime.now().strftime('%Y-%m-%d')}",
            f"**생성 일시**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## 📊 전체 피드백 요약",
            "",
            f"- **총 피드백 수**: {summary['total_feedback']}개",
            f"- **전체 정확도**: {summary['overall_accuracy']:.1%}",
            f"- **정확한 예측**: {summary['correct_predictions']}개",
            f"- **평균 예측 오차**: {summary['average_error_magnitude']:.3f}",
            f"- **실제 성공률**: {summary['actual_success_rate']:.1%}",
            f"- **예측 성공률**: {summary['predicted_success_rate']:.1%}",
            "",
            "## 🤖 모델별 성능 평가",
            ""
        ]
        
        if model_performances:
            report.extend([
                "| 모델명 | 정확도 | 정밀도 | 재현율 | F1점수 | 성능등급 | 트렌드 |",
                "|-------|--------|--------|--------|--------|----------|--------|"
            ])
            
            for model_name, performance in model_performances.items():
                report.append(
                    f"| {model_name} | {performance.accuracy:.1%} | "
                    f"{performance.precision:.1%} | {performance.recall:.1%} | "
                    f"{performance.f1_score:.3f} | {performance.performance_level.value} | "
                    f"{performance.trend} |"
                )
            
            # 개선 추천사항
            report.extend([
                "",
                "## 💡 모델 개선 추천사항",
                ""
            ])
            
            for model_name, performance in model_performances.items():
                if performance.recommendations:
                    report.append(f"### {model_name}")
                    for rec in performance.recommendations:
                        report.append(f"- {rec}")
                    report.append("")
        
        return "\n".join(report)
    
    def _save_feedback_data(self):
        """피드백 데이터 저장"""
        try:
            # 피드백 데이터 저장
            feedback_data = []
            for fb in self._feedback_data:
                fb_dict = asdict(fb)
                fb_dict['feedback_date'] = fb.feedback_date.isoformat()
                feedback_data.append(fb_dict)
            
            feedback_file = os.path.join(self._data_dir, "feedback_data.json")
            with open(feedback_file, 'w', encoding='utf-8') as f:
                json.dump(feedback_data, f, ensure_ascii=False, indent=2, default=str)
            
            # 성능 기록 저장
            performance_file = os.path.join(self._data_dir, "model_performance_history.json")
            with open(performance_file, 'w', encoding='utf-8') as f:
                json.dump(self._model_performance_history, f, ensure_ascii=False, indent=2, default=str)
                
        except Exception as e:
            self._logger.error(f"피드백 데이터 저장 실패: {e}")
    
    def _load_feedback_data(self):
        """피드백 데이터 로드"""
        try:
            # 피드백 데이터 로드
            feedback_file = os.path.join(self._data_dir, "feedback_data.json")
            if os.path.exists(feedback_file):
                with open(feedback_file, 'r', encoding='utf-8') as f:
                    feedback_data = json.load(f)
                
                for fb_dict in feedback_data:
                    fb_dict['feedback_date'] = datetime.fromisoformat(fb_dict['feedback_date'])
                    feedback = FeedbackData(**fb_dict)
                    self._feedback_data.append(feedback)
            
            # 성능 기록 로드
            performance_file = os.path.join(self._data_dir, "model_performance_history.json")
            if os.path.exists(performance_file):
                with open(performance_file, 'r', encoding='utf-8') as f:
                    self._model_performance_history = json.load(f)
                    
            self._logger.info(f"피드백 데이터 로드 완료: {len(self._feedback_data)}개")
            
        except Exception as e:
            self._logger.error(f"피드백 데이터 로드 실패: {e}")

# 전역 인스턴스
_feedback_system = None

def get_feedback_system(prediction_engine: PredictionEngine,
                       performance_analyzer: DailyPerformanceAnalyzer) -> FeedbackSystem:
    """피드백 시스템 싱글톤 인스턴스 반환"""
    global _feedback_system
    if _feedback_system is None:
        _feedback_system = FeedbackSystem(prediction_engine, performance_analyzer)
    return _feedback_system 