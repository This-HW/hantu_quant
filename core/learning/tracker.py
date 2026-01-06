"""
학습 추적 모듈

학습 결과와 모델 버전을 추적하고 관리합니다.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import json
import os

logger = logging.getLogger(__name__)


class LearningType(Enum):
    """학습 유형"""
    MODEL_RETRAIN = "model_retrain"
    WEIGHT_ADJUST = "weight_adjust"
    PARAM_OPTIMIZE = "param_optimize"
    REGIME_UPDATE = "regime_update"
    STRATEGY_CHANGE = "strategy_change"


@dataclass
class LearningRecord:
    """학습 기록"""
    id: str
    timestamp: datetime
    learning_type: LearningType

    # 변경 전/후 상태
    before_state: Dict = field(default_factory=dict)
    after_state: Dict = field(default_factory=dict)

    # 성과 지표
    before_performance: Dict = field(default_factory=dict)
    after_performance: Dict = field(default_factory=dict)
    improvement: float = 0.0

    # 메타데이터
    training_samples: int = 0
    validation_score: float = 0.0
    notes: str = ""

    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat(),
            'learning_type': self.learning_type.value,
            'before_state': self.before_state,
            'after_state': self.after_state,
            'before_performance': self.before_performance,
            'after_performance': self.after_performance,
            'improvement': self.improvement,
            'training_samples': self.training_samples,
            'validation_score': self.validation_score,
            'notes': self.notes,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'LearningRecord':
        return cls(
            id=data['id'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            learning_type=LearningType(data['learning_type']),
            before_state=data.get('before_state', {}),
            after_state=data.get('after_state', {}),
            before_performance=data.get('before_performance', {}),
            after_performance=data.get('after_performance', {}),
            improvement=data.get('improvement', 0.0),
            training_samples=data.get('training_samples', 0),
            validation_score=data.get('validation_score', 0.0),
            notes=data.get('notes', ''),
        )


@dataclass
class TypeEffectiveness:
    """학습 유형별 효과"""
    learning_type: LearningType
    total_count: int = 0
    improvement_count: int = 0
    avg_improvement: float = 0.0
    success_rate: float = 0.0
    total_impact: float = 0.0

    def to_dict(self) -> Dict:
        return {
            'learning_type': self.learning_type.value,
            'total_count': self.total_count,
            'improvement_count': self.improvement_count,
            'avg_improvement': self.avg_improvement,
            'success_rate': self.success_rate,
            'total_impact': self.total_impact,
        }


@dataclass
class LearningEffectivenessReport:
    """학습 효과 보고서"""
    report_date: datetime
    period_days: int
    effectiveness_by_type: Dict[str, TypeEffectiveness] = field(default_factory=dict)
    overall_improvement: float = 0.0
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            'report_date': self.report_date.isoformat(),
            'period_days': self.period_days,
            'effectiveness_by_type': {
                k: v.to_dict() for k, v in self.effectiveness_by_type.items()
            },
            'overall_improvement': self.overall_improvement,
            'recommendations': self.recommendations,
        }


class LearningTracker:
    """
    학습 결과 추적 및 버전 관리

    추적 항목:
    - 모델 버전
    - 파라미터 변경 이력
    - 성과 변화 추이
    """

    def __init__(self, storage_path: Optional[str] = None):
        """
        Args:
            storage_path: 저장 경로
        """
        self.storage_path = storage_path
        self._records: List[LearningRecord] = []
        self._record_counter: int = 0

    def log_learning_result(
        self,
        learning_type: LearningType,
        before_state: Dict,
        after_state: Dict,
        before_performance: Dict,
        after_performance: Dict,
        training_samples: int = 0,
        validation_score: float = 0.0,
        notes: str = ""
    ) -> LearningRecord:
        """
        학습 결과 기록

        Args:
            learning_type: 학습 유형
            before_state: 변경 전 상태
            after_state: 변경 후 상태
            before_performance: 변경 전 성과
            after_performance: 변경 후 성과
            training_samples: 학습 샘플 수
            validation_score: 검증 점수
            notes: 비고

        Returns:
            LearningRecord: 생성된 기록
        """
        self._record_counter += 1

        # 개선률 계산
        before_metric = before_performance.get('accuracy', 0) or before_performance.get('win_rate', 0)
        after_metric = after_performance.get('accuracy', 0) or after_performance.get('win_rate', 0)
        improvement = after_metric - before_metric

        record = LearningRecord(
            id=f"LR{self._record_counter:06d}",
            timestamp=datetime.now(),
            learning_type=learning_type,
            before_state=before_state,
            after_state=after_state,
            before_performance=before_performance,
            after_performance=after_performance,
            improvement=improvement,
            training_samples=training_samples,
            validation_score=validation_score,
            notes=notes,
        )

        self._records.append(record)
        self._save_record(record)

        logger.info(
            f"Learning logged: {learning_type.value} "
            f"improvement={improvement:+.2%}"
        )

        return record

    def _save_record(self, record: LearningRecord) -> None:
        """기록 저장"""
        if not self.storage_path:
            return

        try:
            os.makedirs(self.storage_path, exist_ok=True)
            file_path = os.path.join(
                self.storage_path,
                f"learning_{datetime.now().strftime('%Y%m')}.jsonl"
            )

            with open(file_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(record.to_dict(), ensure_ascii=False) + '\n')

        except Exception as e:
            logger.error(f"Failed to save learning record: {e}", exc_info=True)

    def get_learning_history(
        self,
        learning_type: Optional[LearningType] = None,
        days: int = 30
    ) -> List[LearningRecord]:
        """
        학습 이력 조회

        Args:
            learning_type: 학습 유형 필터
            days: 조회 기간 (일)

        Returns:
            List[LearningRecord]: 필터링된 기록
        """
        cutoff = datetime.now() - timedelta(days=days)
        records = [r for r in self._records if r.timestamp >= cutoff]

        if learning_type:
            records = [r for r in records if r.learning_type == learning_type]

        return records

    def analyze_learning_effectiveness(
        self,
        days: int = 90
    ) -> LearningEffectivenessReport:
        """
        학습 효과 분석

        Args:
            days: 분석 기간 (일)

        Returns:
            LearningEffectivenessReport: 효과 보고서
        """
        history = self.get_learning_history(days=days)

        # 유형별 효과 분석
        effectiveness_by_type = {}

        for ltype in LearningType:
            type_records = [r for r in history if r.learning_type == ltype]

            if not type_records:
                continue

            improvements = [r.improvement for r in type_records]
            positive_count = sum(1 for i in improvements if i > 0)

            effectiveness_by_type[ltype.value] = TypeEffectiveness(
                learning_type=ltype,
                total_count=len(type_records),
                improvement_count=positive_count,
                avg_improvement=sum(improvements) / len(improvements),
                success_rate=positive_count / len(type_records),
                total_impact=sum(improvements),
            )

        # 전체 개선율
        all_improvements = [r.improvement for r in history]
        overall_improvement = (
            sum(all_improvements) / len(all_improvements)
            if all_improvements else 0.0
        )

        # 권장 사항 생성
        recommendations = self._generate_recommendations(effectiveness_by_type)

        return LearningEffectivenessReport(
            report_date=datetime.now(),
            period_days=days,
            effectiveness_by_type=effectiveness_by_type,
            overall_improvement=overall_improvement,
            recommendations=recommendations,
        )

    def _generate_recommendations(
        self,
        effectiveness: Dict[str, TypeEffectiveness]
    ) -> List[str]:
        """권장 사항 생성"""
        recommendations = []

        for ltype, eff in effectiveness.items():
            if eff.success_rate < 0.3:
                recommendations.append(
                    f"{ltype} 학습의 성공률이 낮습니다 ({eff.success_rate:.0%}). "
                    f"학습 조건 검토 권장"
                )
            elif eff.success_rate > 0.7 and eff.total_count < 5:
                recommendations.append(
                    f"{ltype} 학습이 효과적입니다. "
                    f"학습 빈도 증가 고려"
                )

            if eff.avg_improvement < -0.05:
                recommendations.append(
                    f"{ltype} 학습이 오히려 성과를 악화시킵니다. "
                    f"학습 방식 재검토 필요"
                )

        # 전반적인 권장 사항
        if not effectiveness:
            recommendations.append("학습 데이터가 부족합니다. 더 많은 학습 실행 권장")

        return recommendations

    def get_performance_trend(
        self,
        metric: str = 'improvement',
        days: int = 30
    ) -> List[Dict]:
        """
        성과 추이 조회

        Args:
            metric: 지표 이름
            days: 조회 기간

        Returns:
            List[Dict]: 일별 성과
        """
        history = self.get_learning_history(days=days)

        # 일별 그룹화
        by_date: Dict[str, List[float]] = {}
        for record in history:
            date_key = record.timestamp.strftime('%Y-%m-%d')
            if date_key not in by_date:
                by_date[date_key] = []

            value = (
                record.improvement if metric == 'improvement'
                else record.validation_score if metric == 'validation_score'
                else 0.0
            )
            by_date[date_key].append(value)

        # 평균 계산
        return [
            {'date': date, 'value': sum(values) / len(values)}
            for date, values in sorted(by_date.items())
        ]

    def compare_versions(
        self,
        version1: str,
        version2: str
    ) -> Optional[Dict]:
        """
        버전 비교

        Args:
            version1: 버전 1
            version2: 버전 2

        Returns:
            Dict: 비교 결과
        """
        v1_records = [r for r in self._records if version1 in r.notes]
        v2_records = [r for r in self._records if version2 in r.notes]

        if not v1_records or not v2_records:
            return None

        v1_latest = v1_records[-1]
        v2_latest = v2_records[-1]

        return {
            'version1': version1,
            'version2': version2,
            'v1_performance': v1_latest.after_performance,
            'v2_performance': v2_latest.after_performance,
            'improvement': (
                v2_latest.after_performance.get('accuracy', 0) -
                v1_latest.after_performance.get('accuracy', 0)
            ),
        }

    def get_stats(self) -> Dict[str, Any]:
        """통계 정보"""
        if not self._records:
            return {
                'total_records': 0,
                'by_type': {},
            }

        by_type = {}
        for record in self._records:
            ltype = record.learning_type.value
            if ltype not in by_type:
                by_type[ltype] = 0
            by_type[ltype] += 1

        improvements = [r.improvement for r in self._records]

        return {
            'total_records': len(self._records),
            'by_type': by_type,
            'avg_improvement': sum(improvements) / len(improvements),
            'positive_rate': sum(1 for i in improvements if i > 0) / len(improvements),
            'latest_record': self._records[-1].to_dict() if self._records else None,
        }

    def load_records(self, file_path: str) -> int:
        """
        파일에서 기록 로드

        Args:
            file_path: 파일 경로

        Returns:
            int: 로드된 기록 수
        """
        loaded = 0
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    data = json.loads(line.strip())
                    record = LearningRecord.from_dict(data)
                    self._records.append(record)
                    loaded += 1
                    self._record_counter = max(
                        self._record_counter,
                        int(record.id[2:]) + 1
                    )

            logger.info(f"Loaded {loaded} learning records")

        except Exception as e:
            logger.error(f"Failed to load learning records: {e}", exc_info=True)

        return loaded

    def export_report(self, output_path: str) -> bool:
        """
        보고서 내보내기

        Args:
            output_path: 출력 경로

        Returns:
            bool: 성공 여부
        """
        try:
            report = self.analyze_learning_effectiveness()

            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)

            logger.info(f"Report exported to {output_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to export report: {e}", exc_info=True)
            return False
