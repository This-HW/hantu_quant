"""
전략별 성과 비교 시스템

Phase 1과 Phase 2의 성과를 비교하고 개선점을 분석하여
AI 학습을 위한 인사이트를 제공하는 시스템
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, asdict
import json
import os

from ...utils.logging import get_logger
from .daily_performance import PerformanceMetrics, DailyPerformanceAnalyzer

logger = get_logger(__name__)

@dataclass
class StrategyPerformance:
    """전략별 성과 정보"""
    strategy_name: str
    phase: str
    period_start: datetime
    period_end: datetime
    total_trades: int
    avg_return: float
    median_return: float
    win_rate: float
    profit_loss_ratio: float
    sharpe_ratio: float
    max_drawdown: float
    volatility: float
    best_trade: float
    worst_trade: float
    avg_hold_days: float
    prediction_accuracy: float
    risk_adjusted_return: float

@dataclass
class StrategyComparison:
    """전략 비교 결과"""
    comparison_date: datetime
    phase1_performance: StrategyPerformance
    phase2_performance: StrategyPerformance
    improvement_metrics: Dict[str, float]
    recommendations: List[str]
    confidence_score: float

class StrategyComparator:
    """전략 비교 분석기"""
    
    def __init__(self, performance_analyzer: DailyPerformanceAnalyzer, 
                 data_dir: str = "data/strategy_comparison"):
        """
        초기화
        
        Args:
            performance_analyzer: 성과 분석기
            data_dir: 전략 비교 데이터 저장 디렉토리
        """
        self._logger = logger
        self._performance_analyzer = performance_analyzer
        self._data_dir = data_dir
        self._comparison_file = os.path.join(data_dir, "strategy_comparisons.json")
        
        # 디렉토리 생성
        os.makedirs(data_dir, exist_ok=True)
        
        # 기존 비교 결과 로드
        self._comparison_history = self._load_comparison_history()
        
        self._logger.info("전략 비교 분석기 초기화 완료")
    
    def _load_comparison_history(self) -> List[StrategyComparison]:
        """전략 비교 이력 로드"""
        try:
            if os.path.exists(self._comparison_file):
                with open(self._comparison_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                comparisons = []
                for item in data:
                    # StrategyPerformance 복원
                    phase1_perf = StrategyPerformance(**item['phase1_performance'])
                    phase1_perf.period_start = datetime.fromisoformat(item['phase1_performance']['period_start'])
                    phase1_perf.period_end = datetime.fromisoformat(item['phase1_performance']['period_end'])
                    
                    phase2_perf = StrategyPerformance(**item['phase2_performance'])
                    phase2_perf.period_start = datetime.fromisoformat(item['phase2_performance']['period_start'])
                    phase2_perf.period_end = datetime.fromisoformat(item['phase2_performance']['period_end'])
                    
                    # StrategyComparison 복원
                    comparison = StrategyComparison(
                        comparison_date=datetime.fromisoformat(item['comparison_date']),
                        phase1_performance=phase1_perf,
                        phase2_performance=phase2_perf,
                        improvement_metrics=item['improvement_metrics'],
                        recommendations=item['recommendations'],
                        confidence_score=item['confidence_score']
                    )
                    comparisons.append(comparison)
                
                return comparisons
            return []
        except Exception as e:
            self._logger.error(f"전략 비교 이력 로드 실패: {e}", exc_info=True)
            return []
    
    def _save_comparison_history(self):
        """전략 비교 이력 저장"""
        try:
            data = []
            for comparison in self._comparison_history:
                item = asdict(comparison)
                item['comparison_date'] = comparison.comparison_date.isoformat()
                item['phase1_performance']['period_start'] = comparison.phase1_performance.period_start.isoformat()
                item['phase1_performance']['period_end'] = comparison.phase1_performance.period_end.isoformat()
                item['phase2_performance']['period_start'] = comparison.phase2_performance.period_start.isoformat()
                item['phase2_performance']['period_end'] = comparison.phase2_performance.period_end.isoformat()
                data.append(item)
            
            with open(self._comparison_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            self._logger.error(f"전략 비교 이력 저장 실패: {e}", exc_info=True)
    
    def compare_strategies(self, days: int = 30) -> StrategyComparison:
        """전략 비교 실행"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Phase별 성과 데이터 수집
        phase1_metrics = self._get_phase_metrics("Phase 1", start_date, end_date)
        phase2_metrics = self._get_phase_metrics("Phase 2", start_date, end_date)
        
        # 각 Phase별 성과 분석
        phase1_performance = self._analyze_strategy_performance(
            "Phase 1 Strategy", "Phase 1", phase1_metrics, start_date, end_date
        )
        
        phase2_performance = self._analyze_strategy_performance(
            "Phase 2 Strategy", "Phase 2", phase2_metrics, start_date, end_date
        )
        
        # 개선 지표 계산
        improvement_metrics = self._calculate_improvement_metrics(
            phase1_performance, phase2_performance
        )
        
        # 추천사항 생성
        recommendations = self._generate_recommendations(
            phase1_performance, phase2_performance, improvement_metrics
        )
        
        # 신뢰도 점수 계산
        confidence_score = self._calculate_confidence_score(
            phase1_performance, phase2_performance
        )
        
        # 비교 결과 생성
        comparison = StrategyComparison(
            comparison_date=datetime.now(),
            phase1_performance=phase1_performance,
            phase2_performance=phase2_performance,
            improvement_metrics=improvement_metrics,
            recommendations=recommendations,
            confidence_score=confidence_score
        )
        
        # 이력에 추가
        self._comparison_history.append(comparison)
        self._save_comparison_history()
        
        self._logger.info(f"전략 비교 완료: Phase 1 vs Phase 2 ({days}일간)")
        return comparison
    
    def _get_phase_metrics(self, phase: str, start_date: datetime, 
                          end_date: datetime) -> List[PerformanceMetrics]:
        """특정 Phase의 성과 메트릭 가져오기"""
        all_metrics = self._performance_analyzer._performance_history
        
        return [
            m for m in all_metrics
            if (m.phase == phase and 
                start_date <= m.date <= end_date)
        ]
    
    def _analyze_strategy_performance(self, strategy_name: str, phase: str,
                                    metrics: List[PerformanceMetrics],
                                    start_date: datetime, end_date: datetime) -> StrategyPerformance:
        """전략 성과 분석"""
        if not metrics:
            return StrategyPerformance(
                strategy_name=strategy_name,
                phase=phase,
                period_start=start_date,
                period_end=end_date,
                total_trades=0,
                avg_return=0.0,
                median_return=0.0,
                win_rate=0.0,
                profit_loss_ratio=0.0,
                sharpe_ratio=0.0,
                max_drawdown=0.0,
                volatility=0.0,
                best_trade=0.0,
                worst_trade=0.0,
                avg_hold_days=0.0,
                prediction_accuracy=0.0,
                risk_adjusted_return=0.0
            )
        
        returns = [m.return_rate for m in metrics]
        
        # 기본 통계
        total_trades = len(metrics)
        avg_return = float(np.mean(returns))
        median_return = float(np.median(returns))
        
        # 승률 계산
        wins = len([r for r in returns if r > 0])
        win_rate = wins / total_trades if total_trades > 0 else 0.0
        
        # 손익비 계산
        profit_trades = [r for r in returns if r > 0]
        loss_trades = [r for r in returns if r < 0]
        
        if profit_trades and loss_trades:
            avg_profit = float(np.mean(profit_trades))
            avg_loss = abs(float(np.mean(loss_trades)))
            profit_loss_ratio = avg_profit / avg_loss if avg_loss > 0 else 0.0
        else:
            profit_loss_ratio = float('inf') if profit_trades and not loss_trades else 0.0
        
        # 리스크 지표
        volatility = float(np.std(returns)) if len(returns) > 1 else 0.0
        sharpe_ratio = float(np.mean([m.sharpe_ratio for m in metrics]))
        max_drawdown = min([m.max_drawdown for m in metrics]) if metrics else 0.0
        
        # 기타 지표
        best_trade = max(returns) if returns else 0.0
        worst_trade = min(returns) if returns else 0.0
        avg_hold_days = float(np.mean([m.hold_days for m in metrics]))
        prediction_accuracy = float(np.mean([m.prediction_accuracy for m in metrics]))
        
        # 위험 조정 수익률 (샤프 비율 기반)
        risk_adjusted_return = avg_return / volatility if volatility > 0 else 0.0
        
        return StrategyPerformance(
            strategy_name=strategy_name,
            phase=phase,
            period_start=start_date,
            period_end=end_date,
            total_trades=total_trades,
            avg_return=avg_return,
            median_return=median_return,
            win_rate=win_rate,
            profit_loss_ratio=profit_loss_ratio,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            volatility=volatility,
            best_trade=best_trade,
            worst_trade=worst_trade,
            avg_hold_days=avg_hold_days,
            prediction_accuracy=prediction_accuracy,
            risk_adjusted_return=risk_adjusted_return
        )
    
    def _calculate_improvement_metrics(self, phase1: StrategyPerformance, 
                                     phase2: StrategyPerformance) -> Dict[str, float]:
        """개선 지표 계산"""
        if phase1.total_trades == 0:
            return {
                'return_improvement': phase2.avg_return,
                'win_rate_improvement': phase2.win_rate,
                'sharpe_improvement': phase2.sharpe_ratio,
                'accuracy_improvement': phase2.prediction_accuracy,
                'volatility_improvement': -phase2.volatility,
                'drawdown_improvement': -phase2.max_drawdown
            }
        
        return {
            'return_improvement': phase2.avg_return - phase1.avg_return,
            'win_rate_improvement': phase2.win_rate - phase1.win_rate,
            'sharpe_improvement': phase2.sharpe_ratio - phase1.sharpe_ratio,
            'accuracy_improvement': phase2.prediction_accuracy - phase1.prediction_accuracy,
            'volatility_improvement': phase1.volatility - phase2.volatility,  # 낮을수록 좋음
            'drawdown_improvement': phase1.max_drawdown - phase2.max_drawdown,  # 낮을수록 좋음
            'profit_loss_improvement': phase2.profit_loss_ratio - phase1.profit_loss_ratio,
            'hold_days_improvement': phase1.avg_hold_days - phase2.avg_hold_days  # 짧을수록 좋음
        }
    
    def _generate_recommendations(self, phase1: StrategyPerformance, 
                                phase2: StrategyPerformance,
                                improvements: Dict[str, float]) -> List[str]:
        """추천사항 생성"""
        recommendations = []
        
        # 수익률 개선
        if improvements['return_improvement'] > 0.05:  # 5% 이상 개선
            recommendations.append(
                f"✅ 수익률이 {improvements['return_improvement']:.2%} 개선되었습니다. "
                "Phase 2 전략의 우수성이 입증되었습니다."
            )
        elif improvements['return_improvement'] < -0.02:  # 2% 이상 악화
            recommendations.append(
                f"⚠️ 수익률이 {abs(improvements['return_improvement']):.2%} 악화되었습니다. "
                "Phase 1 전략의 장점을 Phase 2에 통합 검토가 필요합니다."
            )
        
        # 승률 개선
        if improvements['win_rate_improvement'] > 0.1:  # 10% 이상 개선
            recommendations.append(
                f"🎯 승률이 {improvements['win_rate_improvement']:.1%} 개선되었습니다. "
                "종목 선정 정확도가 향상되었습니다."
            )
        elif improvements['win_rate_improvement'] < -0.05:
            recommendations.append(
                f"🔄 승률이 {abs(improvements['win_rate_improvement']):.1%} 하락했습니다. "
                "선정 기준 재검토가 필요합니다."
            )
        
        # 예측 정확도
        if improvements['accuracy_improvement'] > 0.1:
            recommendations.append(
                f"🧠 예측 정확도가 {improvements['accuracy_improvement']:.1%} 개선되었습니다. "
                "AI 학습 효과가 나타나고 있습니다."
            )
        
        # 리스크 관리
        if improvements['volatility_improvement'] > 0.05:
            recommendations.append(
                f"📉 변동성이 {improvements['volatility_improvement']:.2%} 감소하여 "
                "리스크 관리가 개선되었습니다."
            )
        
        if improvements['drawdown_improvement'] > 0.02:
            recommendations.append(
                f"🛡️ 최대 손실이 {improvements['drawdown_improvement']:.2%} 개선되어 "
                "손실 제한이 효과적입니다."
            )
        
        # 보유 기간 최적화
        if improvements['hold_days_improvement'] > 2:
            recommendations.append(
                f"⏱️ 평균 보유 기간이 {improvements['hold_days_improvement']:.1f}일 단축되어 "
                "자본 회전율이 개선되었습니다."
            )
        
        # 전반적 성과 평가
        positive_improvements = sum(1 for v in improvements.values() if v > 0)
        total_metrics = len(improvements)
        
        if positive_improvements / total_metrics > 0.7:
            recommendations.append(
                "🚀 전반적으로 Phase 2 전략이 우수한 성과를 보이고 있습니다. "
                "현재 방향을 유지하며 추가 최적화를 진행하시기 바랍니다."
            )
        elif positive_improvements / total_metrics < 0.3:
            recommendations.append(
                "⚠️ Phase 2 전략의 성과가 기대에 미치지 못합니다. "
                "전략 재검토 및 Phase 1의 우수 요소 재도입을 검토하시기 바랍니다."
            )
        
        if not recommendations:
            recommendations.append(
                "📊 두 전략 간 유의미한 차이가 관찰되지 않습니다. "
                "더 많은 데이터 수집 후 재분석을 권장합니다."
            )
        
        return recommendations
    
    def _calculate_confidence_score(self, phase1: StrategyPerformance, 
                                  phase2: StrategyPerformance) -> float:
        """신뢰도 점수 계산"""
        # 거래 수량 기반 신뢰도
        min_trades = 10  # 최소 필요 거래 수
        trades_confidence = min(1.0, (phase1.total_trades + phase2.total_trades) / (min_trades * 2))
        
        # 기간 기반 신뢰도
        period_days = (phase1.period_end - phase1.period_start).days
        min_period = 7  # 최소 7일
        period_confidence = min(1.0, period_days / min_period)
        
        # 성과 일관성 기반 신뢰도
        if phase1.total_trades > 0 and phase2.total_trades > 0:
            # 변동성이 낮을수록 신뢰도 높음
            volatility_confidence = 1.0 - min(0.5, (phase1.volatility + phase2.volatility) / 2)
        else:
            volatility_confidence = 0.5
        
        # 전체 신뢰도 (가중 평균)
        confidence = (
            trades_confidence * 0.4 +
            period_confidence * 0.3 +
            volatility_confidence * 0.3
        )
        
        return min(1.0, max(0.0, confidence))
    
    def get_comparison_summary(self, days: int = 30) -> Dict[str, Any]:
        """비교 요약 정보"""
        recent_comparisons = [
            c for c in self._comparison_history
            if (datetime.now() - c.comparison_date).days <= days
        ]
        
        if not recent_comparisons:
            return {
                'no_data': True,
                'message': f'최근 {days}일간 비교 데이터가 없습니다.'
            }
        
        # 최신 비교 결과
        latest_comparison = max(recent_comparisons, key=lambda x: x.comparison_date)
        
        # 개선 추세 분석
        improvement_trends = self._analyze_improvement_trends(recent_comparisons)
        
        return {
            'latest_comparison_date': latest_comparison.comparison_date,
            'phase1_trades': latest_comparison.phase1_performance.total_trades,
            'phase2_trades': latest_comparison.phase2_performance.total_trades,
            'return_improvement': latest_comparison.improvement_metrics['return_improvement'],
            'win_rate_improvement': latest_comparison.improvement_metrics['win_rate_improvement'],
            'accuracy_improvement': latest_comparison.improvement_metrics['accuracy_improvement'],
            'confidence_score': latest_comparison.confidence_score,
            'key_recommendations': latest_comparison.recommendations[:3],  # 상위 3개
            'improvement_trends': improvement_trends
        }
    
    def _analyze_improvement_trends(self, comparisons: List[StrategyComparison]) -> Dict[str, str]:
        """개선 추세 분석"""
        if len(comparisons) < 2:
            return {'trend': 'insufficient_data'}
        
        # 시간순 정렬
        sorted_comparisons = sorted(comparisons, key=lambda x: x.comparison_date)
        
        # 주요 지표 추세 분석
        return_improvements = [c.improvement_metrics['return_improvement'] for c in sorted_comparisons]
        accuracy_improvements = [c.improvement_metrics['accuracy_improvement'] for c in sorted_comparisons]
        
        # 추세 방향 계산
        return_trend = 'improving' if return_improvements[-1] > return_improvements[0] else 'declining'
        accuracy_trend = 'improving' if accuracy_improvements[-1] > accuracy_improvements[0] else 'declining'
        
        return {
            'return_trend': return_trend,
            'accuracy_trend': accuracy_trend,
            'overall_trend': 'improving' if (return_trend == 'improving' and accuracy_trend == 'improving') else 'mixed'
        }
    
    def generate_comparison_report(self, comparison: StrategyComparison) -> str:
        """비교 리포트 생성"""
        report = [
            f"# 전략 비교 분석 리포트",
            "",
            f"**분석 일시**: {comparison.comparison_date.strftime('%Y-%m-%d %H:%M:%S')}",
            f"**분석 기간**: {comparison.phase1_performance.period_start.strftime('%Y-%m-%d')} ~ {comparison.phase1_performance.period_end.strftime('%Y-%m-%d')}",
            f"**신뢰도**: {comparison.confidence_score:.1%}",
            "",
            "## 📊 전략별 성과 비교",
            "",
            "| 지표 | Phase 1 | Phase 2 | 개선도 |",
            "|------|---------|---------|--------|",
            f"| 총 거래 수 | {comparison.phase1_performance.total_trades} | {comparison.phase2_performance.total_trades} | - |",
            f"| 평균 수익률 | {comparison.phase1_performance.avg_return:.2%} | {comparison.phase2_performance.avg_return:.2%} | {comparison.improvement_metrics['return_improvement']:+.2%} |",
            f"| 승률 | {comparison.phase1_performance.win_rate:.1%} | {comparison.phase2_performance.win_rate:.1%} | {comparison.improvement_metrics['win_rate_improvement']:+.1%} |",
            f"| 샤프 비율 | {comparison.phase1_performance.sharpe_ratio:.2f} | {comparison.phase2_performance.sharpe_ratio:.2f} | {comparison.improvement_metrics['sharpe_improvement']:+.2f} |",
            f"| 예측 정확도 | {comparison.phase1_performance.prediction_accuracy:.1%} | {comparison.phase2_performance.prediction_accuracy:.1%} | {comparison.improvement_metrics['accuracy_improvement']:+.1%} |",
            f"| 변동성 | {comparison.phase1_performance.volatility:.2%} | {comparison.phase2_performance.volatility:.2%} | {comparison.improvement_metrics['volatility_improvement']:+.2%} |",
            f"| 최대 손실 | {comparison.phase1_performance.max_drawdown:.2%} | {comparison.phase2_performance.max_drawdown:.2%} | {comparison.improvement_metrics['drawdown_improvement']:+.2%} |",
            "",
            "## 🎯 주요 개선 사항",
            ""
        ]
        
        for i, recommendation in enumerate(comparison.recommendations, 1):
            report.append(f"{i}. {recommendation}")
        
        report.extend([
            "",
            "## 📈 상세 분석",
            "",
            f"### Phase 1 전략 ({comparison.phase1_performance.strategy_name})",
            f"- **최고 수익률**: {comparison.phase1_performance.best_trade:.2%}",
            f"- **최저 수익률**: {comparison.phase1_performance.worst_trade:.2%}",
            f"- **평균 보유일**: {comparison.phase1_performance.avg_hold_days:.1f}일",
            f"- **손익비**: {comparison.phase1_performance.profit_loss_ratio:.2f}",
            "",
            f"### Phase 2 전략 ({comparison.phase2_performance.strategy_name})",
            f"- **최고 수익률**: {comparison.phase2_performance.best_trade:.2%}",
            f"- **최저 수익률**: {comparison.phase2_performance.worst_trade:.2%}",
            f"- **평균 보유일**: {comparison.phase2_performance.avg_hold_days:.1f}일",
            f"- **손익비**: {comparison.phase2_performance.profit_loss_ratio:.2f}",
            ""
        ])
        
        return "\n".join(report)

# 전역 인스턴스
_strategy_comparator = None

def get_strategy_comparator(performance_analyzer: DailyPerformanceAnalyzer) -> StrategyComparator:
    """전략 비교기 인스턴스 반환"""
    global _strategy_comparator
    if _strategy_comparator is None:
        _strategy_comparator = StrategyComparator(performance_analyzer)
    return _strategy_comparator 