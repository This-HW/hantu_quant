"""
강화된 적응형 학습 시스템
- 데이터 동기화 시스템과 연동
- 스크리닝/선정 정확도 측정
- 가상 거래 데이터 활용
- 자동 유지보수 기능

PostgreSQL 통합 DB 지원 (T-002): use_unified_db=True로 SQLAlchemy 기반 통합 DB 사용
SQLite 폴백: 통합 DB 연결 실패 시 기존 SQLite 사용
"""

import json
import sqlite3
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from pathlib import Path


from ..utils.log_utils import get_logger
from ..data_pipeline.data_synchronizer import get_data_synchronizer
from .adaptive_learning_system import AdaptiveLearningSystem, AlgorithmParams

logger = get_logger(__name__)

@dataclass
class ScreeningAccuracy:
    """스크리닝 정확도 메트릭"""
    date: str
    total_screened: int
    passed_screening: int
    actual_positive_performance: int
    false_positive_rate: float
    true_positive_rate: float
    precision: float
    recall: float
    f1_score: float

@dataclass
class SelectionAccuracy:
    """종목 선정 정확도 메트릭"""
    date: str
    total_selected: int
    profitable_count: int
    loss_count: int
    win_rate: float
    avg_return: float
    best_return: float
    worst_return: float
    sharpe_ratio: float

@dataclass
class LearningInsight:
    """학습 인사이트"""
    insight_type: str
    description: str
    confidence: float
    actionable: bool
    suggested_action: Optional[str] = None

class EnhancedAdaptiveSystem(AdaptiveLearningSystem):
    """강화된 적응형 학습 시스템

    PostgreSQL 통합 DB 지원 (T-002):
    - use_unified_db=True: SQLAlchemy 기반 통합 DB 사용
    - 통합 DB 연결 실패 시 자동으로 SQLite 폴백
    """

    def __init__(self, data_dir: str = "data/learning", use_unified_db: bool = True):
        super().__init__(data_dir)
        self.data_synchronizer = get_data_synchronizer()
        self.db_path = "data/learning/learning_data.db"
        self._unified_db_available = False

        # 통합 DB 사용 시도
        if use_unified_db:
            try:
                from ..database.unified_db import ensure_tables_exist
                ensure_tables_exist()
                self._unified_db_available = True
                self.logger.info("통합 DB 연결 성공 (PostgreSQL/SQLAlchemy)")
            except Exception as e:
                self.logger.warning(f"통합 DB 연결 실패, SQLite 폴백 사용: {e}")
                self._unified_db_available = False

        # 학습 설정
        self.evaluation_window = 10  # 평가 기간 (일)
        self.min_samples_for_learning = 30  # 학습 최소 샘플 수
        self.accuracy_threshold = 0.6  # 정확도 임계값

        # 자동 유지보수 설정
        self.max_db_records = 10000  # DB 최대 레코드 수
        self.cleanup_days = 90  # 정리 주기 (일)

        self.logger.info("강화된 적응형 학습 시스템 초기화 완료")

    def run_comprehensive_analysis(self) -> Dict[str, Any]:
        """포괄적 학습 분석 실행"""
        try:
            self.logger.info("=== 포괄적 학습 분석 시작 ===")

            # 1. 데이터 동기화
            sync_results = self.data_synchronizer.run_full_sync()

            # 2. 스크리닝 정확도 분석
            screening_accuracy = self.analyze_screening_accuracy()

            # 3. 선정 정확도 분석
            selection_accuracy = self.analyze_selection_accuracy()

            # 4. 섹터별 성과 분석
            sector_analysis = self.analyze_sector_performance_detailed()

            # 5. 시간별 성과 분석
            temporal_analysis = self.analyze_temporal_patterns()

            # 6. 학습 인사이트 생성
            insights = self.generate_learning_insights(
                screening_accuracy, selection_accuracy, sector_analysis
            )

            # 7. 파라미터 적응
            adaptation_result = self.adapt_parameters_enhanced(
                screening_accuracy, selection_accuracy, insights
            )

            # 8. 결과 정리
            analysis_result = {
                'analysis_date': datetime.now().isoformat(),
                'data_sync': sync_results,
                'screening_accuracy': screening_accuracy,
                'selection_accuracy': selection_accuracy,
                'sector_analysis': sector_analysis,
                'temporal_analysis': temporal_analysis,
                'insights': [asdict(insight) for insight in insights],
                'parameter_adaptation': adaptation_result,
                'system_health': self.check_system_health()
            }

            # 9. 결과 저장
            self._save_comprehensive_analysis(analysis_result)

            self.logger.info("포괄적 학습 분석 완료")
            return analysis_result

        except Exception as e:
            self.logger.error(f"포괄적 학습 분석 실패: {e}", exc_info=True)
            return {'error': str(e), 'status': 'failed'}

    def analyze_screening_accuracy(self, days_back: int = 30) -> Optional[ScreeningAccuracy]:
        """스크리닝 정확도 분석"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # 스크리닝 결과와 실제 성과 조인
                cutoff_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y%m%d')

                cursor.execute("""
                    SELECT
                        sh.screening_date,
                        COUNT(*) as total_screened,
                        SUM(CASE WHEN sh.passed = 1 THEN 1 ELSE 0 END) as passed_screening,
                        COUNT(pt.stock_code) as tracked_stocks,
                        SUM(CASE WHEN sh.passed = 1 AND pt.price_change_pct > 0 THEN 1 ELSE 0 END) as true_positives,
                        SUM(CASE WHEN sh.passed = 1 AND pt.price_change_pct <= 0 THEN 1 ELSE 0 END) as false_positives,
                        SUM(CASE WHEN sh.passed = 0 AND pt.price_change_pct > 0 THEN 1 ELSE 0 END) as false_negatives,
                        SUM(CASE WHEN sh.passed = 0 AND pt.price_change_pct <= 0 THEN 1 ELSE 0 END) as true_negatives
                    FROM screening_history sh
                    LEFT JOIN performance_tracking pt ON sh.stock_code = pt.stock_code
                        AND sh.screening_date = pt.tracking_date
                    WHERE sh.screening_date >= ?
                    GROUP BY sh.screening_date
                    ORDER BY sh.screening_date DESC
                """, (cutoff_date,))

                results = cursor.fetchall()

                if not results:
                    return None

                # 최신 날짜 데이터 사용
                latest = results[0]
                total_screened = latest[1]
                passed_screening = latest[2]
                true_positives = latest[4] or 0
                false_positives = latest[5] or 0
                false_negatives = latest[6] or 0
                latest[7] or 0

                # 정확도 메트릭 계산
                if passed_screening > 0:
                    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
                    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
                    f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
                    false_positive_rate = false_positives / passed_screening
                    true_positive_rate = true_positives / passed_screening
                else:
                    precision = recall = f1_score = false_positive_rate = true_positive_rate = 0

                return ScreeningAccuracy(
                    date=latest[0],
                    total_screened=total_screened,
                    passed_screening=passed_screening,
                    actual_positive_performance=true_positives,
                    false_positive_rate=false_positive_rate,
                    true_positive_rate=true_positive_rate,
                    precision=precision,
                    recall=recall,
                    f1_score=f1_score
                )

        except Exception as e:
            self.logger.error(f"스크리닝 정확도 분석 실패: {e}", exc_info=True)
            return None

    def analyze_selection_accuracy(self, days_back: int = 30) -> Optional[SelectionAccuracy]:
        """선정 정확도 분석"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cutoff_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y%m%d')

                cursor.execute("""
                    SELECT
                        sh.selection_date,
                        COUNT(*) as total_selected,
                        SUM(CASE WHEN pt.price_change_pct > 0 THEN 1 ELSE 0 END) as profitable_count,
                        SUM(CASE WHEN pt.price_change_pct <= 0 THEN 1 ELSE 0 END) as loss_count,
                        AVG(pt.price_change_pct) as avg_return,
                        MAX(pt.price_change_pct) as best_return,
                        MIN(pt.price_change_pct) as worst_return,
                        AVG(pt.max_gain) as avg_max_gain,
                        AVG(pt.max_loss) as avg_max_loss
                    FROM selection_history sh
                    JOIN performance_tracking pt ON sh.stock_code = pt.stock_code
                        AND sh.selection_date = pt.tracking_date
                    WHERE sh.selection_date >= ? AND pt.is_active = 1
                    GROUP BY sh.selection_date
                    ORDER BY sh.selection_date DESC
                """, (cutoff_date,))

                results = cursor.fetchall()

                if not results:
                    return None

                # 전체 기간 통합 계산
                total_selected = sum(row[1] for row in results)
                profitable_count = sum(row[2] for row in results)
                loss_count = sum(row[3] for row in results)

                if total_selected == 0:
                    return None

                win_rate = profitable_count / total_selected
                avg_return = np.mean([row[4] for row in results if row[4] is not None])
                best_return = max([row[5] for row in results if row[5] is not None], default=0)
                worst_return = min([row[6] for row in results if row[6] is not None], default=0)

                # 샤프 비율 계산
                returns = [row[4] for row in results if row[4] is not None]
                if len(returns) > 1:
                    return_std = np.std(returns)
                    sharpe_ratio = avg_return / return_std if return_std > 0 else 0
                else:
                    sharpe_ratio = 0

                return SelectionAccuracy(
                    date=results[0][0],
                    total_selected=total_selected,
                    profitable_count=profitable_count,
                    loss_count=loss_count,
                    win_rate=win_rate,
                    avg_return=avg_return,
                    best_return=best_return,
                    worst_return=worst_return,
                    sharpe_ratio=sharpe_ratio
                )

        except Exception as e:
            self.logger.error(f"선정 정확도 분석 실패: {e}", exc_info=True)
            return None

    def analyze_sector_performance_detailed(self) -> Dict[str, Any]:
        """상세 섹터 성과 분석"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # SQLite doesn't have STDDEV function, calculate manually
                cursor.execute("""
                    SELECT
                        sh.sector,
                        COUNT(*) as total_stocks,
                        AVG(pt.price_change_pct) as avg_performance,
                        SUM(CASE WHEN pt.price_change_pct > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as win_rate,
                        MAX(pt.price_change_pct) as best_performance,
                        MIN(pt.price_change_pct) as worst_performance
                    FROM screening_history sh
                    JOIN performance_tracking pt ON sh.stock_code = pt.stock_code
                        AND sh.screening_date = pt.tracking_date
                    WHERE pt.is_active = 1 AND sh.sector IS NOT NULL
                    GROUP BY sh.sector
                    HAVING COUNT(*) >= 3
                    ORDER BY avg_performance DESC
                """)

                sector_data = cursor.fetchall()

                if not sector_data:
                    return {'status': 'no_data'}

                sectors = {}
                for row in sector_data:
                    sector = row[0]
                    sectors[sector] = {
                        'total_stocks': row[1],
                        'avg_performance': row[2],
                        'volatility': 0,  # 계산하지 않음 (SQLite 한계)
                        'win_rate': row[3],
                        'best_performance': row[4],
                        'worst_performance': row[5],
                        'risk_adjusted_return': abs(row[2]) if row[2] else 0  # 단순화된 계산
                    }

                # 섹터 순위 매기기
                best_sectors = sorted(sectors.items(), key=lambda x: x[1]['avg_performance'], reverse=True)[:3]
                worst_sectors = sorted(sectors.items(), key=lambda x: x[1]['avg_performance'])[:3]

                return {
                    'status': 'success',
                    'total_sectors': len(sectors),
                    'sector_performance': sectors,
                    'best_sectors': [{'sector': s[0], **s[1]} for s in best_sectors],
                    'worst_sectors': [{'sector': s[0], **s[1]} for s in worst_sectors],
                    'analysis_date': datetime.now().isoformat()
                }

        except Exception as e:
            self.logger.error(f"섹터 성과 분석 실패: {e}", exc_info=True)
            return {'status': 'error', 'error': str(e)}

    def analyze_temporal_patterns(self) -> Dict[str, Any]:
        """시간별 패턴 분석"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # 요일별 성과 분석 (선정일 기준)
                cursor.execute("""
                    SELECT
                        CASE CAST(strftime('%w', date(
                            substr(sh.selection_date, 1, 4) || '-' ||
                            substr(sh.selection_date, 5, 2) || '-' ||
                            substr(sh.selection_date, 7, 2)
                        )) AS INTEGER)
                            WHEN 0 THEN 'Sunday'
                            WHEN 1 THEN 'Monday'
                            WHEN 2 THEN 'Tuesday'
                            WHEN 3 THEN 'Wednesday'
                            WHEN 4 THEN 'Thursday'
                            WHEN 5 THEN 'Friday'
                            WHEN 6 THEN 'Saturday'
                        END as day_of_week,
                        COUNT(*) as total_selections,
                        AVG(pt.price_change_pct) as avg_performance,
                        SUM(CASE WHEN pt.price_change_pct > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as win_rate
                    FROM selection_history sh
                    JOIN performance_tracking pt ON sh.stock_code = pt.stock_code
                        AND sh.selection_date = pt.tracking_date
                    WHERE pt.is_active = 1
                    GROUP BY CAST(strftime('%w', date(
                        substr(sh.selection_date, 1, 4) || '-' ||
                        substr(sh.selection_date, 5, 2) || '-' ||
                        substr(sh.selection_date, 7, 2)
                    )) AS INTEGER)
                    ORDER BY avg_performance DESC
                """)

                day_patterns = cursor.fetchall()

                # 월별 성과 분석
                cursor.execute("""
                    SELECT
                        substr(sh.selection_date, 1, 6) as year_month,
                        COUNT(*) as total_selections,
                        AVG(pt.price_change_pct) as avg_performance,
                        SUM(CASE WHEN pt.price_change_pct > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as win_rate
                    FROM selection_history sh
                    JOIN performance_tracking pt ON sh.stock_code = pt.stock_code
                        AND sh.selection_date = pt.tracking_date
                    WHERE pt.is_active = 1
                    GROUP BY substr(sh.selection_date, 1, 6)
                    ORDER BY year_month DESC
                    LIMIT 6
                """)

                month_patterns = cursor.fetchall()

                return {
                    'status': 'success',
                    'day_of_week_patterns': {
                        row[0]: {
                            'total_selections': row[1],
                            'avg_performance': row[2],
                            'win_rate': row[3]
                        } for row in day_patterns
                    },
                    'monthly_patterns': {
                        row[0]: {
                            'total_selections': row[1],
                            'avg_performance': row[2],
                            'win_rate': row[3]
                        } for row in month_patterns
                    },
                    'analysis_date': datetime.now().isoformat()
                }

        except Exception as e:
            self.logger.error(f"시간별 패턴 분석 실패: {e}", exc_info=True)
            return {'status': 'error', 'error': str(e)}

    def generate_learning_insights(
        self,
        screening_accuracy: Optional[ScreeningAccuracy],
        selection_accuracy: Optional[SelectionAccuracy],
        sector_analysis: Dict[str, Any]
    ) -> List[LearningInsight]:
        """학습 인사이트 생성"""
        insights = []

        try:
            # 스크리닝 정확도 인사이트
            if screening_accuracy:
                if screening_accuracy.precision < 0.6:
                    insights.append(LearningInsight(
                        insight_type="screening_precision",
                        description=f"스크리닝 정밀도가 낮습니다 ({screening_accuracy.precision:.1%}). 더 엄격한 기준 적용이 필요합니다.",
                        confidence=0.8,
                        actionable=True,
                        suggested_action="min_roe와 기술적 지표 가중치 증가"
                    ))

                if screening_accuracy.recall < 0.4:
                    insights.append(LearningInsight(
                        insight_type="screening_recall",
                        description=f"스크리닝 재현율이 낮습니다 ({screening_accuracy.recall:.1%}). 좋은 기회를 놓치고 있을 수 있습니다.",
                        confidence=0.7,
                        actionable=True,
                        suggested_action="선정 기준 완화 검토"
                    ))

            # 선정 정확도 인사이트
            if selection_accuracy:
                if selection_accuracy.win_rate > 0.7:
                    insights.append(LearningInsight(
                        insight_type="high_win_rate",
                        description=f"높은 승률을 보입니다 ({selection_accuracy.win_rate:.1%}). 더 공격적인 포지션 사이징을 고려할 수 있습니다.",
                        confidence=0.9,
                        actionable=True,
                        suggested_action="position_sizing_multiplier 증가"
                    ))

                if selection_accuracy.sharpe_ratio < 0.5:
                    insights.append(LearningInsight(
                        insight_type="low_sharpe_ratio",
                        description=f"샤프 비율이 낮습니다 ({selection_accuracy.sharpe_ratio:.2f}). 변동성 대비 수익이 부족합니다.",
                        confidence=0.8,
                        actionable=True,
                        suggested_action="기술적 분석 가중치 증가로 변동성 관리"
                    ))

            # 섹터 인사이트
            if sector_analysis.get('status') == 'success':
                best_sectors = sector_analysis.get('best_sectors', [])
                if best_sectors:
                    best_sector = best_sectors[0]
                    insights.append(LearningInsight(
                        insight_type="best_sector",
                        description=f"{best_sector['sector']} 섹터가 최고 성과를 보입니다 ({best_sector['avg_performance']:+.1f}%, 승률 {best_sector['win_rate']:.1f}%)",
                        confidence=0.85,
                        actionable=True,
                        suggested_action=f"{best_sector['sector']} 섹터 가중치 증가"
                    ))

            return insights

        except Exception as e:
            self.logger.error(f"학습 인사이트 생성 실패: {e}", exc_info=True)
            return []

    def adapt_parameters_enhanced(
        self,
        screening_accuracy: Optional[ScreeningAccuracy],
        selection_accuracy: Optional[SelectionAccuracy],
        insights: List[LearningInsight]
    ) -> Dict[str, Any]:
        """강화된 파라미터 적응"""
        try:
            improved_params = AlgorithmParams(**self.current_params.to_dict())
            changes_made = []

            # 인사이트 기반 적응
            for insight in insights:
                if insight.actionable and insight.suggested_action:
                    if "min_roe" in insight.suggested_action and "증가" in insight.suggested_action:
                        improved_params.min_roe *= 1.1
                        changes_made.append(f"ROE 기준 강화: {insight.description}")

                    elif "기술적" in insight.suggested_action and "증가" in insight.suggested_action:
                        improved_params.technical_weight *= 1.15
                        improved_params.momentum_weight *= 0.9
                        changes_made.append(f"기술적 분석 가중치 증가: {insight.description}")

                    elif "position_sizing_multiplier" in insight.suggested_action:
                        improved_params.position_sizing_multiplier *= 1.05
                        changes_made.append(f"포지션 사이징 증가: {insight.description}")

            # 스크리닝 정확도 기반 적응
            if screening_accuracy:
                if screening_accuracy.precision < 0.5:
                    improved_params.max_per_ratio *= 0.9
                    improved_params.min_roe *= 1.05
                    changes_made.append("스크리닝 정밀도 개선: 더 엄격한 기준 적용")

                if screening_accuracy.f1_score > 0.7:
                    improved_params.max_per_ratio *= 1.02
                    changes_made.append("우수한 스크리닝 성과: 기준 소폭 완화")

            # 선정 정확도 기반 적응
            if selection_accuracy:
                if selection_accuracy.win_rate > 0.65 and selection_accuracy.avg_return > 0.05:
                    improved_params.risk_tolerance *= 1.02
                    improved_params.position_sizing_multiplier *= 1.03
                    changes_made.append("우수한 선정 성과: 리스크 허용도 증가")

                elif selection_accuracy.win_rate < 0.45:
                    improved_params.risk_tolerance *= 0.95
                    improved_params.fundamental_weight *= 1.05
                    changes_made.append("선정 성과 부진: 보수적 조정")

            # 변경사항 적용
            if changes_made:
                self.current_params = improved_params
                self._save_current_params(improved_params)

                # 상세 적응 이력 저장
                self._save_enhanced_adaptation_history(
                    screening_accuracy, selection_accuracy, insights, improved_params, changes_made
                )

                return {
                    'status': 'adapted',
                    'changes_made': changes_made,
                    'new_params': improved_params.to_dict(),
                    'insights_applied': len([i for i in insights if i.actionable])
                }
            else:
                return {
                    'status': 'no_changes',
                    'message': '적응할 필요한 변경사항이 없음'
                }

        except Exception as e:
            self.logger.error(f"강화된 파라미터 적응 실패: {e}", exc_info=True)
            return {'status': 'error', 'error': str(e)}

    def _save_enhanced_adaptation_history(
        self,
        screening_accuracy: Optional[ScreeningAccuracy],
        selection_accuracy: Optional[SelectionAccuracy],
        insights: List[LearningInsight],
        new_params: AlgorithmParams,
        changes: List[str]
    ):
        """강화된 적응 이력 저장"""
        try:
            history_file = self.data_dir / "enhanced_adaptation_history.json"

            history_entry = {
                "date": datetime.now().isoformat(),
                "screening_accuracy": asdict(screening_accuracy) if screening_accuracy else None,
                "selection_accuracy": asdict(selection_accuracy) if selection_accuracy else None,
                "insights": [asdict(insight) for insight in insights],
                "new_params": new_params.to_dict(),
                "changes_made": changes,
                "system_version": "enhanced_v1.0"
            }

            # 기존 이력 로드
            history = []
            if history_file.exists():
                with open(history_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)

            # 새 이력 추가
            history.append(history_entry)

            # 최근 50개만 유지
            history = history[-50:]

            # 저장
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, indent=2, ensure_ascii=False)

        except Exception as e:
            self.logger.error(f"강화된 적응 이력 저장 실패: {e}", exc_info=True)

    def _save_comprehensive_analysis(self, analysis_result: Dict[str, Any]):
        """포괄적 분석 결과 저장"""
        try:
            results_file = self.data_dir / "comprehensive_analysis_results.json"

            # 기존 결과 로드
            results = []
            if results_file.exists():
                with open(results_file, 'r', encoding='utf-8') as f:
                    results = json.load(f)

            # dataclass 객체들을 dict로 변환
            serializable_result = self._make_json_serializable(analysis_result)

            # 새 결과 추가
            results.append(serializable_result)

            # 최근 30개만 유지
            results = results[-30:]

            # 저장
            with open(results_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)

        except Exception as e:
            self.logger.error(f"포괄적 분석 결과 저장 실패: {e}", exc_info=True)

    def _make_json_serializable(self, obj: Any) -> Any:
        """객체를 JSON 직렬화 가능하도록 변환"""
        if hasattr(obj, '__dict__'):
            return asdict(obj) if hasattr(obj, '__dataclass_fields__') else obj.__dict__
        elif isinstance(obj, dict):
            return {k: self._make_json_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._make_json_serializable(item) for item in obj]
        else:
            return obj

    def check_system_health(self) -> Dict[str, Any]:
        """시스템 헬스체크"""
        try:
            health = {
                'database_health': self._check_database_health(),
                'data_freshness': self._check_data_freshness(),
                'performance_metrics': self._check_performance_metrics(),
                'disk_usage': self._check_disk_usage(),
                'overall_status': 'healthy'
            }

            # 전체 상태 결정
            # 주의: stale_data는 system_monitor에서 별도로 "데이터" 카테고리 경고로 처리
            # 여기서는 학습 시스템 자체 이슈(DB, 디스크)만 포함
            issues = []
            if not health['database_health']['status']:
                issues.append('database')
            if health['disk_usage']['usage_pct'] > 90:
                issues.append('disk_space')

            if issues:
                health['overall_status'] = 'warning' if len(issues) == 1 else 'critical'
                health['issues'] = issues

            return health

        except Exception as e:
            self.logger.error(f"시스템 헬스체크 실패: {e}", exc_info=True)
            return {'overall_status': 'error', 'error': str(e)}

    # 허용된 테이블 목록 (SQL 인젝션 방지용 화이트리스트)
    ALLOWED_TABLES = frozenset(['screening_history', 'selection_history', 'performance_tracking'])

    def _check_database_health(self) -> Dict[str, Any]:
        """데이터베이스 헬스체크"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # 테이블별 레코드 수 확인 (화이트리스트 검증)
                table_counts = {}

                for table in self.ALLOWED_TABLES:
                    # 테이블명 화이트리스트 검증 (SQL 인젝션 방지)
                    if table not in self.ALLOWED_TABLES:
                        continue
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    table_counts[table] = count

                # 최신 데이터 확인
                cursor.execute("SELECT MAX(screening_date) FROM screening_history")
                latest_screening = cursor.fetchone()[0]

                return {
                    'status': True,
                    'table_counts': table_counts,
                    'latest_screening_date': latest_screening,
                    'total_records': sum(table_counts.values())
                }

        except Exception as e:
            return {'status': False, 'error': str(e)}

    def _check_data_freshness(self) -> Dict[str, Any]:
        """데이터 신선도 확인 (DB 우선, JSON 폴백)"""
        try:
            days_since = 999
            latest_date_str = None
            source = None

            # 1. DB에서 최신 스크리닝 날짜 확인 (우선)
            try:
                from core.database.session import DatabaseSession
                from core.database.models import ScreeningResult
                from sqlalchemy import func

                db = DatabaseSession()
                with db.get_session() as session:
                    latest_date = session.query(func.max(ScreeningResult.screening_date)).scalar()
                    if latest_date:
                        # date 객체를 datetime으로 변환하여 비교
                        if hasattr(latest_date, 'strftime'):
                            latest_date_str = latest_date.strftime('%Y%m%d')
                            days_since = (datetime.now().date() - latest_date).days
                            source = 'database'
            except Exception as db_error:
                self.logger.debug(f"DB 스크리닝 날짜 조회 실패 (JSON 폴백): {db_error}")

            # 2. DB에서 못 찾으면 JSON 파일 확인 (폴백)
            if source is None:
                screening_files = list(Path("data/watchlist").glob("screening_results_*.json"))
                if screening_files:
                    latest_file = max(screening_files, key=lambda x: x.stat().st_mtime)
                    latest_date_str = latest_file.name.split('_')[2][:8]  # YYYYMMDD
                    file_date = datetime.strptime(latest_date_str, '%Y%m%d')
                    days_since = (datetime.now() - file_date).days
                    source = 'json_file'

            return {
                'days_since_update': days_since,
                'latest_date': latest_date_str,
                'source': source,
                'is_fresh': days_since <= 1
            }

        except Exception as e:
            self.logger.error(f"데이터 신선도 확인 실패: {e}", exc_info=True)
            return {'days_since_update': 999, 'error': str(e)}

    def _check_performance_metrics(self) -> Dict[str, Any]:
        """성능 메트릭 확인"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # 최근 30일 성과 요약
                cursor.execute("""
                    SELECT
                        AVG(price_change_pct) as avg_return,
                        COUNT(*) as total_tracking,
                        SUM(CASE WHEN price_change_pct > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as win_rate
                    FROM performance_tracking
                    WHERE is_active = 1
                """)

                result = cursor.fetchone()

                return {
                    'avg_return': result[0] or 0,
                    'total_tracking': result[1] or 0,
                    'win_rate': result[2] or 0,
                    'performance_score': (result[2] or 0) * 0.6 + (result[0] or 0) * 40  # 간단한 점수
                }

        except Exception as e:
            return {'error': str(e)}

    def _check_disk_usage(self) -> Dict[str, Any]:
        """디스크 사용량 확인"""
        try:
            import shutil

            # 데이터 디렉토리 사용량
            data_path = Path("data")
            if data_path.exists():
                total_size = sum(f.stat().st_size for f in data_path.rglob('*') if f.is_file())
            else:
                total_size = 0

            # 전체 디스크 사용량
            total, used, free = shutil.disk_usage(data_path if data_path.exists() else ".")

            return {
                'data_size_mb': total_size / (1024 * 1024),
                'total_disk_gb': total / (1024**3),
                'used_disk_gb': used / (1024**3),
                'free_disk_gb': free / (1024**3),
                'usage_pct': (used / total) * 100
            }

        except Exception as e:
            return {'error': str(e)}

    def run_maintenance(self) -> Dict[str, Any]:
        """시스템 유지보수 실행"""
        try:
            self.logger.info("=== 시스템 유지보수 시작 ===")

            maintenance_results = {
                'start_time': datetime.now().isoformat(),
                'tasks_completed': []
            }

            # 1. 오래된 데이터 정리
            cleanup_result = self._cleanup_old_data()
            maintenance_results['tasks_completed'].append('data_cleanup')
            maintenance_results['data_cleanup'] = cleanup_result

            # 2. 데이터베이스 최적화
            db_optimize_result = self._optimize_database()
            maintenance_results['tasks_completed'].append('database_optimization')
            maintenance_results['database_optimization'] = db_optimize_result

            # 3. 로그 파일 정리
            log_cleanup_result = self._cleanup_logs()
            maintenance_results['tasks_completed'].append('log_cleanup')
            maintenance_results['log_cleanup'] = log_cleanup_result

            # 4. 데이터 무결성 검사
            integrity_result = self._check_data_integrity()
            maintenance_results['tasks_completed'].append('integrity_check')
            maintenance_results['integrity_check'] = integrity_result

            maintenance_results['end_time'] = datetime.now().isoformat()
            maintenance_results['status'] = 'completed'

            self.logger.info(f"시스템 유지보수 완료: {len(maintenance_results['tasks_completed'])}개 작업")
            return maintenance_results

        except Exception as e:
            self.logger.error(f"시스템 유지보수 실패: {e}", exc_info=True)
            return {'status': 'error', 'error': str(e)}

    def _cleanup_old_data(self) -> Dict[str, Any]:
        """오래된 데이터 정리"""
        try:
            cutoff_date = (datetime.now() - timedelta(days=self.cleanup_days)).strftime('%Y%m%d')
            deleted_count = 0

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # 오래된 성과 추적 데이터 비활성화
                cursor.execute("""
                    UPDATE performance_tracking
                    SET is_active = 0
                    WHERE tracking_date < ? AND is_active = 1
                """, (cutoff_date,))

                deleted_count += cursor.rowcount

                # 오래된 JSON 파일들 정리 (90일 이상)
                data_dirs = ['data/learning/raw_data', 'data/learning/feedback']
                for data_dir in data_dirs:
                    data_path = Path(data_dir)
                    if data_path.exists():
                        for file_path in data_path.rglob('*.json'):
                            if file_path.stat().st_mtime < (datetime.now() - timedelta(days=90)).timestamp():
                                file_path.unlink()
                                deleted_count += 1

                conn.commit()

            return {
                'status': 'completed',
                'deleted_records': deleted_count,
                'cutoff_date': cutoff_date
            }

        except Exception as e:
            return {'status': 'error', 'error': str(e)}

    def _optimize_database(self) -> Dict[str, Any]:
        """데이터베이스 최적화"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # VACUUM으로 데이터베이스 최적화
                conn.execute("VACUUM")

                # 인덱스 재구성
                conn.execute("REINDEX")

            return {'status': 'completed'}

        except Exception as e:
            return {'status': 'error', 'error': str(e)}

    def _cleanup_logs(self) -> Dict[str, Any]:
        """로그 파일 정리"""
        try:
            logs_path = Path("logs")
            cleaned_count = 0

            if logs_path.exists():
                cutoff_time = (datetime.now() - timedelta(days=30)).timestamp()

                for log_file in logs_path.glob("*.log"):
                    if log_file.stat().st_mtime < cutoff_time:
                        log_file.unlink()
                        cleaned_count += 1

            return {
                'status': 'completed',
                'cleaned_files': cleaned_count
            }

        except Exception as e:
            return {'status': 'error', 'error': str(e)}

    def _check_data_integrity(self) -> Dict[str, Any]:
        """데이터 무결성 검사"""
        try:
            issues = []

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # 중복 데이터 확인
                cursor.execute("""
                    SELECT stock_code, screening_date, COUNT(*) as cnt
                    FROM screening_history
                    GROUP BY stock_code, screening_date
                    HAVING cnt > 1
                """)

                duplicates = cursor.fetchall()
                if duplicates:
                    issues.append(f"스크리닝 데이터 중복: {len(duplicates)}건")

                # 누락된 성과 데이터 확인
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM selection_history sh
                    LEFT JOIN performance_tracking pt ON sh.stock_code = pt.stock_code
                        AND sh.selection_date = pt.tracking_date
                    WHERE pt.stock_code IS NULL
                """)

                missing_performance = cursor.fetchone()[0]
                if missing_performance > 0:
                    issues.append(f"성과 데이터 누락: {missing_performance}건")

            return {
                'status': 'completed',
                'issues_found': len(issues),
                'issues': issues
            }

        except Exception as e:
            return {'status': 'error', 'error': str(e)}

# 싱글톤 인스턴스
_enhanced_adaptive_system = None

def get_enhanced_adaptive_system() -> EnhancedAdaptiveSystem:
    """강화된 적응형 학습 시스템 싱글톤 인스턴스 반환"""
    global _enhanced_adaptive_system
    if _enhanced_adaptive_system is None:
        _enhanced_adaptive_system = EnhancedAdaptiveSystem()
    return _enhanced_adaptive_system