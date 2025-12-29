"""
학습 리포터

Task D.3.1: 학습 모니터링 대시보드 데이터
Task D.3.2: 주간/월간 리포트 생성
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

from core.learning.retrain.retrain_history import RetrainHistory, get_retrain_history
from core.learning.weights.weight_storage import WeightStorage, get_weight_storage
from core.learning.weights.dynamic_weight_calculator import DynamicWeightCalculator, get_dynamic_weight_calculator
from core.learning.regime.regime_detector import RegimeDetector, get_regime_detector
from core.learning.regime.regime_strategy_mapper import RegimeStrategyMapper, get_regime_strategy_mapper
from core.learning.models.feedback_system import FeedbackSystem, get_feedback_system
from core.utils.log_utils import get_logger

logger = get_logger(__name__)


@dataclass
class DashboardMetrics:
    """대시보드 메트릭"""
    timestamp: str

    # 모델 성능
    model_accuracy: float
    model_precision: float
    model_recall: float

    # 가중치 상태
    current_weights: Dict[str, float]
    weight_version: Optional[str]
    last_weight_update: Optional[str]

    # 레짐 상태
    current_regime: str
    regime_confidence: float
    regime_history_7d: List[str]

    # 학습 이력
    retrain_count_30d: int
    retrain_success_rate: float
    avg_improvement: float

    # 피드백 상태
    feedback_count_7d: int
    prediction_accuracy_7d: float


@dataclass
class WeeklyReport:
    """주간 리포트"""
    report_id: str
    period_start: str
    period_end: str
    generated_at: str

    # 성능 요약
    total_predictions: int
    correct_predictions: int
    accuracy: float
    avg_return: float

    # 가중치 변화
    weight_changes: Dict[str, Dict[str, float]]

    # 레짐 분포
    regime_distribution: Dict[str, int]
    regime_transitions: int

    # 재학습 이력
    retrain_events: int
    retrain_success_rate: float

    # 주요 인사이트
    insights: List[str]

    # 권장 사항
    recommendations: List[str]


@dataclass
class MonthlyReport:
    """월간 리포트"""
    report_id: str
    period_start: str
    period_end: str
    generated_at: str

    # 종합 성능
    total_predictions: int
    accuracy: float
    precision: float
    recall: float
    f1_score: float

    # 수익률 분석
    avg_return: float
    win_rate: float
    best_performing_factor: str
    worst_performing_factor: str

    # 가중치 진화
    weight_evolution: List[Dict[str, Any]]
    optimal_weight_suggestion: Dict[str, float]

    # 레짐 분석
    dominant_regime: str
    regime_accuracy: Dict[str, float]

    # 시스템 건강
    system_uptime: float
    error_rate: float
    avg_processing_time: float

    # 상세 분석
    weekly_summaries: List[Dict[str, Any]]

    # 권장 사항
    strategic_recommendations: List[str]


class LearningReporter:
    """
    학습 리포터 (D.3.1, D.3.2)

    학습 시스템의 성능을 모니터링하고 리포트를 생성합니다.
    """

    def __init__(self, report_dir: str = "data/learning/reports"):
        """
        초기화

        Args:
            report_dir: 리포트 저장 디렉토리
        """
        self._report_dir = Path(report_dir)
        self._report_dir.mkdir(parents=True, exist_ok=True)

        self._retrain_history = get_retrain_history()
        self._weight_storage = get_weight_storage()
        self._weight_calculator = get_dynamic_weight_calculator()
        self._regime_detector = get_regime_detector()
        self._strategy_mapper = get_regime_strategy_mapper()
        self._feedback_system = get_feedback_system()

        logger.info("LearningReporter 초기화")

    def get_dashboard_metrics(self) -> DashboardMetrics:
        """
        대시보드 메트릭 조회 (D.3.1)

        Returns:
            대시보드 메트릭
        """
        now = datetime.now()

        # 가중치 상태
        active_version = self._weight_storage.get_active_version()
        current_weights = self._strategy_mapper.get_current_weights()

        # 레짐 상태
        regime_result = self._regime_detector.detect()
        current_regime = self._strategy_mapper.get_current_regime()

        # 학습 이력
        retrain_summary = self._retrain_history.get_summary()

        # 피드백 분석
        recent_feedback = self._feedback_system.get_recent_feedback(days=7)
        feedback_stats = self._feedback_system.get_stats()

        # 예측 정확도 계산
        correct_predictions = sum(
            1 for fb in recent_feedback
            if fb.actual_return is not None and
            (fb.predicted_return > 0) == (fb.actual_return > 0)
        )
        total_with_result = sum(
            1 for fb in recent_feedback
            if fb.actual_return is not None
        )
        accuracy_7d = correct_predictions / total_with_result if total_with_result > 0 else 0.0

        return DashboardMetrics(
            timestamp=now.isoformat(),
            model_accuracy=retrain_summary.get('success_rate_30d', 0.0),
            model_precision=0.0,  # TODO: 실제 계산 필요
            model_recall=0.0,     # TODO: 실제 계산 필요
            current_weights=current_weights,
            weight_version=active_version.version_id if active_version else None,
            last_weight_update=active_version.created_at if active_version else None,
            current_regime=current_regime.value if current_regime else "unknown",
            regime_confidence=regime_result.confidence,
            regime_history_7d=self._get_regime_history(7),
            retrain_count_30d=retrain_summary.get('total_retrains', 0),
            retrain_success_rate=retrain_summary.get('success_rate_30d', 0.0),
            avg_improvement=retrain_summary.get('average_improvement_30d', 0.0),
            feedback_count_7d=len(recent_feedback),
            prediction_accuracy_7d=accuracy_7d
        )

    def generate_weekly_report(self,
                              end_date: Optional[datetime] = None) -> WeeklyReport:
        """
        주간 리포트 생성 (D.3.2)

        Args:
            end_date: 종료일 (기본: 오늘)

        Returns:
            주간 리포트
        """
        if end_date is None:
            end_date = datetime.now()

        start_date = end_date - timedelta(days=7)
        report_id = f"weekly_{end_date.strftime('%Y%m%d')}"

        # 피드백 데이터 수집
        feedback_data = self._feedback_system.get_recent_feedback(days=7)

        # 예측 분석
        total_predictions = len(feedback_data)
        with_result = [fb for fb in feedback_data if fb.actual_return is not None]
        correct = sum(
            1 for fb in with_result
            if (fb.predicted_return > 0) == (fb.actual_return > 0)
        )
        accuracy = correct / len(with_result) if with_result else 0.0
        avg_return = sum(fb.actual_return for fb in with_result) / len(with_result) if with_result else 0.0

        # 가중치 변화 분석
        weight_changes = self._analyze_weight_changes(7)

        # 레짐 분석
        regime_history = self._get_regime_history(7)
        regime_dist = {}
        for r in regime_history:
            regime_dist[r] = regime_dist.get(r, 0) + 1

        # 재학습 이력
        retrain_records = self._retrain_history.get_latest_records(limit=20)
        week_retrains = [
            r for r in retrain_records
            if r.started_at >= start_date.isoformat()
        ]
        retrain_success = sum(1 for r in week_retrains if r.status == 'success')

        # 인사이트 생성
        insights = self._generate_insights(
            accuracy=accuracy,
            avg_return=avg_return,
            regime_dist=regime_dist,
            weight_changes=weight_changes
        )

        # 권장 사항 생성
        recommendations = self._generate_recommendations(
            accuracy=accuracy,
            avg_return=avg_return,
            retrain_count=len(week_retrains)
        )

        report = WeeklyReport(
            report_id=report_id,
            period_start=start_date.isoformat(),
            period_end=end_date.isoformat(),
            generated_at=datetime.now().isoformat(),
            total_predictions=total_predictions,
            correct_predictions=correct,
            accuracy=accuracy,
            avg_return=avg_return,
            weight_changes=weight_changes,
            regime_distribution=regime_dist,
            regime_transitions=self._count_regime_transitions(regime_history),
            retrain_events=len(week_retrains),
            retrain_success_rate=retrain_success / len(week_retrains) if week_retrains else 0.0,
            insights=insights,
            recommendations=recommendations
        )

        # 리포트 저장
        self._save_report('weekly', report)

        logger.info(f"주간 리포트 생성: {report_id}")
        return report

    def generate_monthly_report(self,
                               end_date: Optional[datetime] = None) -> MonthlyReport:
        """
        월간 리포트 생성 (D.3.2)

        Args:
            end_date: 종료일 (기본: 오늘)

        Returns:
            월간 리포트
        """
        if end_date is None:
            end_date = datetime.now()

        start_date = end_date - timedelta(days=30)
        report_id = f"monthly_{end_date.strftime('%Y%m')}"

        # 피드백 데이터 수집
        feedback_data = self._feedback_system.get_recent_feedback(days=30)

        # 성능 분석
        with_result = [fb for fb in feedback_data if fb.actual_return is not None]
        total = len(with_result)

        if total > 0:
            correct = sum(
                1 for fb in with_result
                if (fb.predicted_return > 0) == (fb.actual_return > 0)
            )
            accuracy = correct / total

            # 정밀도/재현율 계산
            true_pos = sum(1 for fb in with_result if fb.predicted_return > 0 and fb.actual_return > 0)
            pred_pos = sum(1 for fb in with_result if fb.predicted_return > 0)
            actual_pos = sum(1 for fb in with_result if fb.actual_return > 0)

            precision = true_pos / pred_pos if pred_pos > 0 else 0.0
            recall = true_pos / actual_pos if actual_pos > 0 else 0.0
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

            avg_return = sum(fb.actual_return for fb in with_result) / total
            win_rate = sum(1 for fb in with_result if fb.actual_return > 0) / total
        else:
            accuracy = precision = recall = f1 = avg_return = win_rate = 0.0

        # 팩터 성능 분석
        factor_performance = self._analyze_factor_performance(with_result)
        best_factor = max(factor_performance.items(), key=lambda x: x[1], default=("none", 0))[0]
        worst_factor = min(factor_performance.items(), key=lambda x: x[1], default=("none", 0))[0]

        # 가중치 진화
        weight_evolution = self._get_weight_evolution(30)
        optimal_weights = self._suggest_optimal_weights(factor_performance)

        # 레짐 분석
        regime_history = self._get_regime_history(30)
        dominant_regime = max(set(regime_history), key=regime_history.count) if regime_history else "unknown"
        regime_accuracy = self._calculate_regime_accuracy(with_result)

        # 시스템 건강 지표
        retrain_records = self._retrain_history.get_latest_records(limit=50)
        month_retrains = [
            r for r in retrain_records
            if r.started_at >= start_date.isoformat()
        ]
        error_rate = sum(1 for r in month_retrains if r.status == 'failed') / len(month_retrains) if month_retrains else 0.0

        # 주간 요약
        weekly_summaries = self._generate_weekly_summaries(start_date, end_date)

        # 전략적 권장 사항
        strategic_recommendations = self._generate_strategic_recommendations(
            accuracy=accuracy,
            factor_performance=factor_performance,
            dominant_regime=dominant_regime,
            error_rate=error_rate
        )

        report = MonthlyReport(
            report_id=report_id,
            period_start=start_date.isoformat(),
            period_end=end_date.isoformat(),
            generated_at=datetime.now().isoformat(),
            total_predictions=len(feedback_data),
            accuracy=accuracy,
            precision=precision,
            recall=recall,
            f1_score=f1,
            avg_return=avg_return,
            win_rate=win_rate,
            best_performing_factor=best_factor,
            worst_performing_factor=worst_factor,
            weight_evolution=weight_evolution,
            optimal_weight_suggestion=optimal_weights,
            dominant_regime=dominant_regime,
            regime_accuracy=regime_accuracy,
            system_uptime=1.0 - error_rate,
            error_rate=error_rate,
            avg_processing_time=0.0,  # TODO: 실제 측정 필요
            weekly_summaries=weekly_summaries,
            strategic_recommendations=strategic_recommendations
        )

        # 리포트 저장
        self._save_report('monthly', report)

        logger.info(f"월간 리포트 생성: {report_id}")
        return report

    def _get_regime_history(self, days: int) -> List[str]:
        """레짐 이력 조회"""
        # TODO: 실제 레짐 이력 저장소에서 조회
        # 현재는 현재 레짐만 반환
        current = self._strategy_mapper.get_current_regime()
        if current:
            return [current.value] * days
        return []

    def _analyze_weight_changes(self, days: int) -> Dict[str, Dict[str, float]]:
        """가중치 변화 분석"""
        versions = self._weight_storage.list_versions(limit=10)

        if len(versions) < 2:
            return {}

        latest = versions[0]
        oldest = versions[-1]

        changes = {}
        for factor in latest.weights:
            old_val = oldest.weights.get(factor, 0)
            new_val = latest.weights.get(factor, 0)
            changes[factor] = {
                'old': old_val,
                'new': new_val,
                'change': new_val - old_val
            }

        return changes

    def _count_regime_transitions(self, history: List[str]) -> int:
        """레짐 전환 횟수"""
        if len(history) < 2:
            return 0
        return sum(1 for i in range(1, len(history)) if history[i] != history[i-1])

    def _generate_insights(self,
                          accuracy: float,
                          avg_return: float,
                          regime_dist: Dict[str, int],
                          weight_changes: Dict) -> List[str]:
        """인사이트 생성"""
        insights = []

        if accuracy > 0.6:
            insights.append(f"예측 정확도 {accuracy:.1%}로 양호한 성능 유지")
        elif accuracy < 0.45:
            insights.append(f"예측 정확도 {accuracy:.1%}로 개선 필요")

        if avg_return > 0.02:
            insights.append(f"평균 수익률 {avg_return:.2%}로 긍정적 성과")
        elif avg_return < -0.02:
            insights.append(f"평균 수익률 {avg_return:.2%}로 손실 발생")

        if regime_dist:
            dominant = max(regime_dist.items(), key=lambda x: x[1])
            insights.append(f"주요 시장 레짐: {dominant[0]} ({dominant[1]}일)")

        significant_changes = [
            f for f, c in weight_changes.items()
            if abs(c.get('change', 0)) > 0.05
        ]
        if significant_changes:
            insights.append(f"주요 가중치 변화 팩터: {', '.join(significant_changes)}")

        return insights

    def _generate_recommendations(self,
                                  accuracy: float,
                                  avg_return: float,
                                  retrain_count: int) -> List[str]:
        """권장 사항 생성"""
        recommendations = []

        if accuracy < 0.5:
            recommendations.append("모델 재학습을 고려해 주세요")

        if avg_return < 0:
            recommendations.append("리스크 관리 강화를 권장합니다")

        if retrain_count == 0:
            recommendations.append("정기적인 모델 점검을 권장합니다")
        elif retrain_count > 3:
            recommendations.append("재학습 빈도가 높습니다. 안정화가 필요할 수 있습니다")

        return recommendations

    def _analyze_factor_performance(self,
                                    feedback_list: List) -> Dict[str, float]:
        """팩터별 성능 분석"""
        factor_returns = {}
        factor_counts = {}

        for fb in feedback_list:
            if not fb.factor_scores or fb.actual_return is None:
                continue

            for factor, score in fb.factor_scores.items():
                if factor not in factor_returns:
                    factor_returns[factor] = 0.0
                    factor_counts[factor] = 0

                # 팩터 점수와 실제 수익률의 상관관계
                factor_returns[factor] += score * fb.actual_return
                factor_counts[factor] += 1

        return {
            f: factor_returns[f] / factor_counts[f]
            for f in factor_returns if factor_counts[f] > 0
        }

    def _get_weight_evolution(self, days: int) -> List[Dict[str, Any]]:
        """가중치 진화 이력"""
        versions = self._weight_storage.list_versions(limit=30)

        return [
            {
                'version_id': v.version_id,
                'created_at': v.created_at,
                'weights': v.weights
            }
            for v in versions
        ]

    def _suggest_optimal_weights(self,
                                factor_performance: Dict[str, float]) -> Dict[str, float]:
        """최적 가중치 제안"""
        if not factor_performance:
            return {}

        # 성능 기반 가중치 제안
        total = sum(max(0, v) for v in factor_performance.values())
        if total == 0:
            return {f: 1/len(factor_performance) for f in factor_performance}

        return {
            f: max(0.05, min(0.4, max(0, v) / total))
            for f, v in factor_performance.items()
        }

    def _calculate_regime_accuracy(self,
                                   feedback_list: List) -> Dict[str, float]:
        """레짐별 정확도 계산"""
        regime_correct = {}
        regime_total = {}

        for fb in feedback_list:
            regime = fb.metadata.get('regime', 'unknown') if fb.metadata else 'unknown'
            if regime not in regime_correct:
                regime_correct[regime] = 0
                regime_total[regime] = 0

            regime_total[regime] += 1
            if (fb.predicted_return > 0) == (fb.actual_return > 0):
                regime_correct[regime] += 1

        return {
            r: regime_correct[r] / regime_total[r]
            for r in regime_total if regime_total[r] > 0
        }

    def _generate_weekly_summaries(self,
                                   start_date: datetime,
                                   end_date: datetime) -> List[Dict[str, Any]]:
        """주간 요약 목록 생성"""
        summaries = []
        current = start_date

        while current < end_date:
            week_end = min(current + timedelta(days=7), end_date)
            summaries.append({
                'week_start': current.isoformat(),
                'week_end': week_end.isoformat()
            })
            current = week_end

        return summaries

    def _generate_strategic_recommendations(self,
                                           accuracy: float,
                                           factor_performance: Dict[str, float],
                                           dominant_regime: str,
                                           error_rate: float) -> List[str]:
        """전략적 권장 사항"""
        recommendations = []

        if accuracy < 0.5:
            recommendations.append("전체적인 모델 아키텍처 검토 권장")

        if factor_performance:
            worst = min(factor_performance.items(), key=lambda x: x[1])
            if worst[1] < 0:
                recommendations.append(f"'{worst[0]}' 팩터 가중치 축소 또는 제거 검토")

        if error_rate > 0.1:
            recommendations.append("시스템 안정성 점검 필요")

        if dominant_regime in ['BEAR', 'VOLATILE']:
            recommendations.append("방어적 전략 유지 권장")
        elif dominant_regime == 'BULL':
            recommendations.append("모멘텀 팩터 활용 강화 고려")

        return recommendations

    def _save_report(self, report_type: str, report: Any):
        """리포트 저장"""
        try:
            report_file = self._report_dir / f"{report_type}_{report.report_id}.json"
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(asdict(report), f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"리포트 저장 실패: {e}")

    def get_saved_reports(self,
                         report_type: str = "all",
                         limit: int = 10) -> List[Dict[str, Any]]:
        """저장된 리포트 목록"""
        reports = []

        pattern = f"{report_type}_*.json" if report_type != "all" else "*.json"
        for report_file in sorted(self._report_dir.glob(pattern), reverse=True)[:limit]:
            try:
                with open(report_file, 'r', encoding='utf-8') as f:
                    reports.append(json.load(f))
            except Exception as e:
                logger.warning(f"리포트 로드 실패: {e}")

        return reports


# 싱글톤 인스턴스
_reporter_instance: Optional[LearningReporter] = None


def get_learning_reporter() -> LearningReporter:
    """LearningReporter 싱글톤 인스턴스 반환"""
    global _reporter_instance
    if _reporter_instance is None:
        _reporter_instance = LearningReporter()
    return _reporter_instance
