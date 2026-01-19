"""
성과 리포트 자동 생성 시스템

일일 성과, 전략 비교, 종합 분석 리포트를 자동으로 생성하고
시각화 차트를 포함한 포괄적인 분석 보고서를 제공하는 시스템
"""

import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
from typing import Dict, List, Any
from dataclasses import dataclass
import os

from ...utils.logging import get_logger
from .daily_performance import DailyPerformanceAnalyzer, PerformanceMetrics
from .strategy_comparison import StrategyComparator

logger = get_logger(__name__)

@dataclass 
class ReportConfig:
    """리포트 설정"""
    include_charts: bool = True
    chart_width: int = 12
    chart_height: int = 8
    chart_dpi: int = 300
    report_format: str = 'markdown'  # 'markdown', 'html', 'pdf'
    include_detailed_analysis: bool = True
    include_recommendations: bool = True
    days_to_analyze: int = 30

class PerformanceReportGenerator:
    """성과 리포트 생성기"""
    
    def __init__(self, performance_analyzer: DailyPerformanceAnalyzer,
                 strategy_comparator: StrategyComparator,
                 output_dir: str = "reports"):
        """
        초기화
        
        Args:
            performance_analyzer: 성과 분석기
            strategy_comparator: 전략 비교기
            output_dir: 리포트 출력 디렉토리
        """
        self._logger = logger
        self._performance_analyzer = performance_analyzer
        self._strategy_comparator = strategy_comparator
        self._output_dir = output_dir
        
        # 출력 디렉토리 생성
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(os.path.join(output_dir, "charts"), exist_ok=True)
        
        # 스타일 설정
        plt.style.use('seaborn-v0_8')
        sns.set_palette("husl")
        
        self._logger.info("성과 리포트 생성기 초기화 완료")
    
    def generate_comprehensive_report(self, config: ReportConfig = None) -> str:
        """종합 성과 리포트 생성"""
        if config is None:
            config = ReportConfig()
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_filename = f"comprehensive_report_{timestamp}.md"
        report_path = os.path.join(self._output_dir, report_filename)
        
        # 리포트 생성
        report_content = self._build_comprehensive_report(config)
        
        # 파일 저장
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        self._logger.info(f"종합 리포트 생성 완료: {report_path}")
        return report_path
    
    def _build_comprehensive_report(self, config: ReportConfig) -> str:
        """종합 리포트 내용 구성"""
        report_sections = []
        
        # 1. 헤더
        report_sections.append(self._generate_report_header())
        
        # 2. 요약 섹션
        report_sections.append(self._generate_executive_summary(config))
        
        # 3. 일일 성과 분석
        report_sections.append(self._generate_daily_performance_section(config))
        
        # 4. 전략 비교 분석
        report_sections.append(self._generate_strategy_comparison_section(config))
        
        # 5. 상세 분석
        if config.include_detailed_analysis:
            report_sections.append(self._generate_detailed_analysis_section(config))
        
        # 6. 시각화 차트
        if config.include_charts:
            report_sections.append(self._generate_charts_section(config))
        
        # 7. 추천사항
        if config.include_recommendations:
            report_sections.append(self._generate_recommendations_section(config))
        
        # 8. 부록
        report_sections.append(self._generate_appendix_section(config))
        
        return "\n\n".join(report_sections)
    
    def _generate_report_header(self) -> str:
        """리포트 헤더 생성"""
        now = datetime.now()
        
        return f"""# 📊 한투 퀀트 성과 분석 리포트

**생성 일시**: {now.strftime('%Y년 %m월 %d일 %H:%M:%S')}  
**리포트 유형**: 종합 성과 분석  
**분석 시스템**: Phase 4 AI 학습 시스템  

---

## 📋 목차

1. [요약](#요약)
2. [일일 성과 분석](#일일-성과-분석)
3. [전략 비교 분석](#전략-비교-분석)
4. [상세 분석](#상세-분석)
5. [시각화 차트](#시각화-차트)
6. [추천사항](#추천사항)
7. [부록](#부록)"""
    
    def _generate_executive_summary(self, config: ReportConfig) -> str:
        """요약 섹션 생성"""
        summary = self._performance_analyzer.get_performance_summary(config.days_to_analyze)
        comparison_summary = self._strategy_comparator.get_comparison_summary(config.days_to_analyze)
        
        # 핵심 지표 계산
        total_trades = summary.get('total_trades', 0)
        avg_return = summary.get('avg_return', 0)
        win_rate = summary.get('win_rate', 0)
        sharpe_ratio = summary.get('sharpe_ratio', 0)
        prediction_accuracy = summary.get('prediction_accuracy', 0)
        
        # 성과 등급 계산
        performance_grade = self._calculate_performance_grade(avg_return, win_rate, sharpe_ratio)
        
        return f"""## 📊 요약

### 🎯 핵심 성과 지표 ({config.days_to_analyze}일간)

| 지표 | 수치 | 평가 |
|------|------|------|
| **총 거래 수** | {total_trades}건 | {self._evaluate_metric('trades', total_trades)} |
| **평균 수익률** | {avg_return:.2%} | {self._evaluate_metric('return', avg_return)} |
| **승률** | {win_rate:.1%} | {self._evaluate_metric('win_rate', win_rate)} |
| **샤프 비율** | {sharpe_ratio:.2f} | {self._evaluate_metric('sharpe', sharpe_ratio)} |
| **예측 정확도** | {prediction_accuracy:.1%} | {self._evaluate_metric('accuracy', prediction_accuracy)} |

### 📈 전반적 성과 등급: **{performance_grade}**

### 🔄 전략 비교 현황

{self._format_comparison_summary(comparison_summary)}"""
    
    def _calculate_performance_grade(self, avg_return: float, win_rate: float, sharpe_ratio: float) -> str:
        """성과 등급 계산"""
        score = 0
        
        # 수익률 점수 (40%)
        if avg_return >= 0.10:      # 10% 이상
            score += 40
        elif avg_return >= 0.05:    # 5% 이상
            score += 30
        elif avg_return >= 0.02:    # 2% 이상
            score += 20
        elif avg_return >= 0:       # 0% 이상
            score += 10
        
        # 승률 점수 (35%)
        if win_rate >= 0.7:         # 70% 이상
            score += 35
        elif win_rate >= 0.6:       # 60% 이상
            score += 28
        elif win_rate >= 0.5:       # 50% 이상
            score += 21
        elif win_rate >= 0.4:       # 40% 이상
            score += 14
        
        # 샤프 비율 점수 (25%)
        if sharpe_ratio >= 2.0:     # 2.0 이상
            score += 25
        elif sharpe_ratio >= 1.5:   # 1.5 이상
            score += 20
        elif sharpe_ratio >= 1.0:   # 1.0 이상
            score += 15
        elif sharpe_ratio >= 0.5:   # 0.5 이상
            score += 10
        
        # 등급 결정
        if score >= 80:
            return "🏆 A+ (우수)"
        elif score >= 70:
            return "🥇 A (양호)"
        elif score >= 60:
            return "🥈 B+ (보통)"
        elif score >= 50:
            return "🥉 B (개선 필요)"
        else:
            return "📉 C (재검토 필요)"
    
    def _evaluate_metric(self, metric_type: str, value: float) -> str:
        """지표 평가"""
        evaluations = {
            'trades': {
                30: "매우 활발", 20: "활발", 10: "보통", 5: "저조", 0: "부족"
            },
            'return': {
                0.10: "🚀 우수", 0.05: "✅ 양호", 0.02: "📈 보통", 0: "⚠️ 주의", -999: "❌ 위험"
            },
            'win_rate': {
                0.7: "🎯 우수", 0.6: "✅ 양호", 0.5: "📊 보통", 0.4: "⚠️ 주의", 0: "❌ 부족"
            },
            'sharpe': {
                2.0: "🏆 우수", 1.5: "✅ 양호", 1.0: "📊 보통", 0.5: "⚠️ 주의", 0: "❌ 부족"
            },
            'accuracy': {
                0.8: "🧠 우수", 0.7: "✅ 양호", 0.6: "📊 보통", 0.5: "⚠️ 주의", 0: "❌ 부족"
            }
        }
        
        thresholds = evaluations.get(metric_type, {})
        for threshold in sorted(thresholds.keys(), reverse=True):
            if value >= threshold:
                return thresholds[threshold]
        
        return "❓ 미분류"
    
    def _format_comparison_summary(self, summary: Dict[str, Any]) -> str:
        """비교 요약 포맷"""
        if summary.get('no_data', False):
            return "- 📊 비교 데이터 부족: 더 많은 거래 데이터 축적 필요"
        
        return_improvement = summary.get('return_improvement', 0)
        accuracy_improvement = summary.get('accuracy_improvement', 0)
        confidence = summary.get('confidence_score', 0)
        
        status = "📈 개선" if return_improvement > 0 else "📉 하락" if return_improvement < 0 else "➡️ 유지"
        
        return f"""- **Phase 1 vs Phase 2**: {status} (수익률 {return_improvement:+.2%})
- **예측 정확도**: {accuracy_improvement:+.1%} 변화
- **분석 신뢰도**: {confidence:.1%}"""
    
    def _generate_daily_performance_section(self, config: ReportConfig) -> str:
        """일일 성과 분석 섹션"""
        summary = self._performance_analyzer.get_performance_summary(config.days_to_analyze)
        
        if summary['total_trades'] == 0:
            return """## 📈 일일 성과 분석

⚠️ 분석 기간 내 거래 데이터가 없습니다."""
        
        best_performer = summary.get('best_performer')
        worst_performer = summary.get('worst_performer')
        
        section = [
            "## 📈 일일 성과 분석",
            "",
            f"### 📊 전체 성과 ({config.days_to_analyze}일간)",
            "",
            f"- **총 거래 수**: {summary['total_trades']}건",
            f"- **평균 수익률**: {summary['avg_return']:.2%}",
            f"- **승률**: {summary['win_rate']:.1%}",
            f"- **샤프 비율**: {summary['sharpe_ratio']:.2f}",
            f"- **최대 손실**: {summary['max_drawdown']:.2%}",
            f"- **예측 정확도**: {summary['prediction_accuracy']:.1%}",
            "",
            "### 🏆 최고/최저 성과",
            ""
        ]
        
        if best_performer:
            section.extend([
                f"**🥇 최고 성과**: {best_performer.stock_name} ({best_performer.stock_code})",
                f"- 수익률: {best_performer.return_rate:.2%}",
                f"- 보유일: {best_performer.hold_days}일",
                f"- Phase: {best_performer.phase}",
                ""
            ])
        
        if worst_performer:
            section.extend([
                f"**📉 최저 성과**: {worst_performer.stock_name} ({worst_performer.stock_code})",
                f"- 수익률: {worst_performer.return_rate:.2%}",
                f"- 보유일: {worst_performer.hold_days}일", 
                f"- Phase: {worst_performer.phase}",
                ""
            ])
        
        return "\n".join(section)
    
    def _generate_strategy_comparison_section(self, config: ReportConfig) -> str:
        """전략 비교 분석 섹션"""
        try:
            comparison = self._strategy_comparator.compare_strategies(config.days_to_analyze)
            
            section = [
                "## 🔄 전략 비교 분석",
                "",
                f"**비교 기간**: {comparison.phase1_performance.period_start.strftime('%Y-%m-%d')} ~ {comparison.phase1_performance.period_end.strftime('%Y-%m-%d')}",
                f"**신뢰도**: {comparison.confidence_score:.1%}",
                "",
                "### 📊 Phase별 성과 비교",
                "",
                "| 지표 | Phase 1 | Phase 2 | 개선도 |",
                "|------|---------|---------|--------|",
                f"| 거래 수 | {comparison.phase1_performance.total_trades} | {comparison.phase2_performance.total_trades} | - |",
                f"| 평균 수익률 | {comparison.phase1_performance.avg_return:.2%} | {comparison.phase2_performance.avg_return:.2%} | {comparison.improvement_metrics['return_improvement']:+.2%} |",
                f"| 승률 | {comparison.phase1_performance.win_rate:.1%} | {comparison.phase2_performance.win_rate:.1%} | {comparison.improvement_metrics['win_rate_improvement']:+.1%} |",
                f"| 예측 정확도 | {comparison.phase1_performance.prediction_accuracy:.1%} | {comparison.phase2_performance.prediction_accuracy:.1%} | {comparison.improvement_metrics['accuracy_improvement']:+.1%} |",
                "",
                "### 🎯 주요 개선 사항",
                ""
            ]
            
            for i, recommendation in enumerate(comparison.recommendations[:5], 1):
                section.append(f"{i}. {recommendation}")
            
            return "\n".join(section)
            
        except Exception as e:
            self._logger.error(f"전략 비교 섹션 생성 실패: {e}", exc_info=True)
            return """## 🔄 전략 비교 분석

⚠️ 전략 비교 데이터를 생성할 수 없습니다. 더 많은 데이터가 필요합니다."""
    
    def _generate_detailed_analysis_section(self, config: ReportConfig) -> str:
        """상세 분석 섹션"""
        detailed_analysis = self._performance_analyzer.get_detailed_analysis(days=config.days_to_analyze)
        
        if 'error' in detailed_analysis:
            return f"""## 🔍 상세 분석

⚠️ {detailed_analysis['error']}"""
        
        overall = detailed_analysis.get('overall', {})
        phase1 = detailed_analysis.get('phase1', {})
        phase2 = detailed_analysis.get('phase2', {})
        comparison = detailed_analysis.get('comparison', {})
        
        section = [
            "## 🔍 상세 분석",
            "",
            "### 📊 전체 통계",
            f"- **거래 수**: {overall.get('count', 0)}건",
            f"- **평균 수익률**: {overall.get('avg_return', 0):.2%}",
            f"- **중위 수익률**: {overall.get('median_return', 0):.2%}",
            f"- **수익률 표준편차**: {overall.get('std_return', 0):.2%}",
            f"- **최고 수익률**: {overall.get('max_return', 0):.2%}",
            f"- **최저 수익률**: {overall.get('min_return', 0):.2%}",
            f"- **평균 보유일**: {overall.get('avg_hold_days', 0):.1f}일",
            ""
        ]
        
        if phase1.get('count', 0) > 0:
            section.extend([
                "### 🎯 Phase 1 상세",
                f"- **거래 수**: {phase1['count']}건",
                f"- **평균 수익률**: {phase1['avg_return']:.2%}",
                f"- **승률**: {phase1['win_rate']:.1%}",
                ""
            ])
        
        if phase2.get('count', 0) > 0:
            section.extend([
                "### 🚀 Phase 2 상세", 
                f"- **거래 수**: {phase2['count']}건",
                f"- **평균 수익률**: {phase2['avg_return']:.2%}",
                f"- **승률**: {phase2['win_rate']:.1%}",
                ""
            ])
        
        if comparison.get('comparison_available', False):
            section.extend([
                "### ⚖️ Phase 간 비교",
                f"- **수익률 개선**: {comparison['return_improvement']:+.2%}",
                f"- **정확도 개선**: {comparison['accuracy_improvement']:+.2%}",
                ""
            ])
        
        return "\n".join(section)
    
    def _generate_charts_section(self, config: ReportConfig) -> str:
        """차트 섹션 생성"""
        section = [
            "## 📊 시각화 차트",
            "",
            "### 📈 성과 차트",
            ""
        ]
        
        try:
            # 성과 차트 생성
            chart_paths = self._create_performance_charts(config)
            
            for chart_name, chart_path in chart_paths.items():
                section.append(f"#### {chart_name}")
                section.append(f"![{chart_name}]({chart_path})")
                section.append("")
            
        except Exception as e:
            self._logger.error(f"차트 생성 실패: {e}", exc_info=True)
            section.append("⚠️ 차트를 생성할 수 없습니다.")
        
        return "\n".join(section)
    
    def _create_performance_charts(self, config: ReportConfig) -> Dict[str, str]:
        """성과 차트 생성"""
        chart_paths = {}
        
        # 데이터 준비
        metrics = self._performance_analyzer._performance_history[-config.days_to_analyze:]
        
        if not metrics:
            return {}
        
        # 1. 일일 수익률 차트
        chart_paths['일일 수익률'] = self._create_daily_returns_chart(metrics, config)
        
        # 2. 누적 수익률 차트
        chart_paths['누적 수익률'] = self._create_cumulative_returns_chart(metrics, config)
        
        # 3. Phase별 성과 비교 차트
        chart_paths['Phase별 성과'] = self._create_phase_comparison_chart(metrics, config)
        
        # 4. 예측 정확도 차트
        chart_paths['예측 정확도'] = self._create_accuracy_chart(metrics, config)
        
        return chart_paths
    
    def _create_daily_returns_chart(self, metrics: List[PerformanceMetrics], config: ReportConfig) -> str:
        """일일 수익률 차트 생성"""
        plt.figure(figsize=(config.chart_width, config.chart_height))
        
        dates = [m.date for m in metrics]
        returns = [m.return_rate * 100 for m in metrics]  # 퍼센트 변환
        
        plt.plot(dates, returns, marker='o', linewidth=2, markersize=4)
        plt.axhline(y=0, color='red', linestyle='--', alpha=0.7)
        plt.title('일일 수익률 추이', fontsize=16, fontweight='bold')
        plt.xlabel('날짜', fontsize=12)
        plt.ylabel('수익률 (%)', fontsize=12)
        plt.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        chart_path = os.path.join(self._output_dir, "charts", "daily_returns.png")
        plt.savefig(chart_path, dpi=config.chart_dpi, bbox_inches='tight')
        plt.close()
        
        return chart_path
    
    def _create_cumulative_returns_chart(self, metrics: List[PerformanceMetrics], config: ReportConfig) -> str:
        """누적 수익률 차트 생성"""
        plt.figure(figsize=(config.chart_width, config.chart_height))
        
        dates = [m.date for m in metrics]
        cumulative_returns = []
        cumulative = 1.0
        
        for m in metrics:
            cumulative *= (1 + m.return_rate)
            cumulative_returns.append((cumulative - 1) * 100)  # 퍼센트 변환
        
        plt.plot(dates, cumulative_returns, linewidth=3, color='green')
        plt.fill_between(dates, cumulative_returns, alpha=0.3, color='green')
        plt.axhline(y=0, color='red', linestyle='--', alpha=0.7)
        plt.title('누적 수익률 추이', fontsize=16, fontweight='bold')
        plt.xlabel('날짜', fontsize=12)
        plt.ylabel('누적 수익률 (%)', fontsize=12)
        plt.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        chart_path = os.path.join(self._output_dir, "charts", "cumulative_returns.png")
        plt.savefig(chart_path, dpi=config.chart_dpi, bbox_inches='tight')
        plt.close()
        
        return chart_path
    
    def _create_phase_comparison_chart(self, metrics: List[PerformanceMetrics], config: ReportConfig) -> str:
        """Phase별 성과 비교 차트 생성"""
        plt.figure(figsize=(config.chart_width, config.chart_height))
        
        phase1_returns = [m.return_rate * 100 for m in metrics if m.phase == 'Phase 1']
        phase2_returns = [m.return_rate * 100 for m in metrics if m.phase == 'Phase 2']
        
        data = []
        labels = []
        
        if phase1_returns:
            data.append(phase1_returns)
            labels.append('Phase 1')
        
        if phase2_returns:
            data.append(phase2_returns)
            labels.append('Phase 2')
        
        if data:
            plt.boxplot(data, labels=labels)
            plt.title('Phase별 수익률 분포', fontsize=16, fontweight='bold')
            plt.ylabel('수익률 (%)', fontsize=12)
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
        
        chart_path = os.path.join(self._output_dir, "charts", "phase_comparison.png")
        plt.savefig(chart_path, dpi=config.chart_dpi, bbox_inches='tight')
        plt.close()
        
        return chart_path
    
    def _create_accuracy_chart(self, metrics: List[PerformanceMetrics], config: ReportConfig) -> str:
        """예측 정확도 차트 생성"""
        plt.figure(figsize=(config.chart_width, config.chart_height))
        
        dates = [m.date for m in metrics]
        accuracies = [m.prediction_accuracy * 100 for m in metrics]  # 퍼센트 변환
        
        plt.plot(dates, accuracies, marker='s', linewidth=2, markersize=4, color='blue')
        plt.axhline(y=50, color='red', linestyle='--', alpha=0.7, label='기준선 (50%)')
        plt.title('예측 정확도 추이', fontsize=16, fontweight='bold')
        plt.xlabel('날짜', fontsize=12)
        plt.ylabel('예측 정확도 (%)', fontsize=12)
        plt.ylim(0, 100)
        plt.grid(True, alpha=0.3)
        plt.legend()
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        chart_path = os.path.join(self._output_dir, "charts", "prediction_accuracy.png")
        plt.savefig(chart_path, dpi=config.chart_dpi, bbox_inches='tight')
        plt.close()
        
        return chart_path
    
    def _generate_recommendations_section(self, config: ReportConfig) -> str:
        """추천사항 섹션"""
        try:
            comparison = self._strategy_comparator.compare_strategies(config.days_to_analyze)
            recommendations = comparison.recommendations
            
            section = [
                "## 💡 추천사항",
                "",
                "### 🎯 핵심 개선 방향",
                ""
            ]
            
            for i, recommendation in enumerate(recommendations, 1):
                section.append(f"{i}. {recommendation}")
            
            # 일반적인 추천사항 추가
            section.extend([
                "",
                "### 📋 일반적인 개선 방안",
                "",
                "1. **데이터 품질 향상**: 더 많은 거래 데이터 축적으로 분석 정확도 개선",
                "2. **리스크 관리 강화**: 손실 제한 전략 지속적 점검 및 개선",
                "3. **모니터링 자동화**: 실시간 성과 추적 시스템 활용",
                "4. **백테스트 검증**: 새로운 전략은 충분한 백테스트 후 적용",
                "5. **정기적 리뷰**: 주간/월간 성과 리뷰를 통한 지속적 개선"
            ])
            
            return "\n".join(section)
            
        except Exception as e:
            self._logger.error(f"추천사항 섹션 생성 실패: {e}", exc_info=True)
            return """## 💡 추천사항

⚠️ 추천사항을 생성할 수 없습니다. 더 많은 데이터가 필요합니다."""
    
    def _generate_appendix_section(self, config: ReportConfig) -> str:
        """부록 섹션"""
        return f"""## 📚 부록

### 📖 용어 설명

- **수익률**: (현재가 - 매입가) / 매입가 × 100
- **승률**: 수익을 낸 거래 수 / 전체 거래 수 × 100
- **샤프 비율**: (수익률 - 무위험 수익률) / 변동성
- **최대 손실**: 최고점 대비 최대 하락률
- **예측 정확도**: 목표 수익률 대비 실제 달성도

### ⚙️ 분석 설정

- **분석 기간**: {config.days_to_analyze}일
- **차트 포함**: {'예' if config.include_charts else '아니오'}
- **상세 분석**: {'포함' if config.include_detailed_analysis else '미포함'}
- **리포트 형식**: {config.report_format}

### 📞 문의사항

분석 결과나 리포트에 대한 문의사항이 있으시면 개발팀에 연락해 주시기 바랍니다.

---

*본 리포트는 한투 퀀트 Phase 4 AI 학습 시스템에 의해 자동 생성되었습니다.*  
*생성 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*"""

# 전역 인스턴스
_report_generator = None

def get_report_generator(performance_analyzer: DailyPerformanceAnalyzer,
                        strategy_comparator: StrategyComparator) -> PerformanceReportGenerator:
    """리포트 생성기 인스턴스 반환"""
    global _report_generator
    if _report_generator is None:
        _report_generator = PerformanceReportGenerator(performance_analyzer, strategy_comparator)
    return _report_generator 