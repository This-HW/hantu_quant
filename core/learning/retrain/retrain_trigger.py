"""
재학습 트리거 시스템

Task A.1.1: RetrainTrigger 클래스 생성
Task A.1.2: 재학습 조건 정의 (피드백 수, 정확도, 시간)
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, asdict, field
from enum import Enum

from core.utils.log_utils import get_logger

logger = get_logger(__name__)


class RetrainReason(Enum):
    """재학습 사유"""
    SUFFICIENT_FEEDBACK = "sufficient_feedback"       # 충분한 피드백 축적
    ACCURACY_DROP = "accuracy_drop"                   # 정확도 하락
    TIME_BASED = "time_based"                         # 시간 기반 (정기 재학습)
    PERFORMANCE_DEGRADATION = "performance_degradation"  # 성능 저하
    MANUAL_REQUEST = "manual_request"                 # 수동 요청
    REGIME_CHANGE = "regime_change"                   # 시장 레짐 변경


@dataclass
class RetrainConfig:
    """재학습 트리거 설정"""
    # 피드백 기반 조건
    min_feedback_count: int = 100              # 최소 피드백 수
    min_new_feedback_count: int = 50           # 마지막 학습 이후 최소 새 피드백

    # 정확도 기반 조건
    accuracy_threshold: float = 0.55           # 최소 정확도 (이하 시 재학습)
    accuracy_drop_threshold: float = 0.10      # 정확도 하락폭 (이상 시 재학습)

    # 시간 기반 조건
    max_days_without_retrain: int = 30         # 최대 재학습 없이 경과 가능 일수
    min_days_between_retrain: int = 7          # 최소 재학습 간격 (일)

    # 성능 기반 조건
    min_win_rate: float = 0.45                 # 최소 승률 (이하 시 재학습)
    min_sharpe_ratio: float = 0.5              # 최소 샤프 비율

    # 안전 장치
    max_retrain_per_week: int = 2              # 주당 최대 재학습 횟수
    cooldown_hours: int = 24                   # 재학습 후 쿨다운 시간

    def validate(self) -> Tuple[bool, List[str]]:
        """설정 유효성 검증"""
        errors = []

        if self.min_feedback_count < 10:
            errors.append("min_feedback_count는 10 이상이어야 함")
        if not 0 < self.accuracy_threshold < 1:
            errors.append("accuracy_threshold는 0~1 사이여야 함")
        if self.max_days_without_retrain < 7:
            errors.append("max_days_without_retrain는 7일 이상이어야 함")
        if self.min_days_between_retrain < 1:
            errors.append("min_days_between_retrain는 1일 이상이어야 함")

        return len(errors) == 0, errors


@dataclass
class TriggerCheckResult:
    """트리거 체크 결과"""
    should_retrain: bool
    reasons: List[RetrainReason]
    details: Dict[str, Any]
    checked_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result['reasons'] = [r.value for r in self.reasons]
        return result


class RetrainTrigger:
    """재학습 트리거 시스템"""

    def __init__(self,
                 config: Optional[RetrainConfig] = None,
                 state_dir: str = "data/learning/retrain"):
        """
        초기화

        Args:
            config: 재학습 트리거 설정
            state_dir: 상태 저장 디렉토리
        """
        self._config = config or RetrainConfig()
        is_valid, errors = self._config.validate()
        if not is_valid:
            raise ValueError(f"유효하지 않은 설정: {errors}")

        self._state_dir = Path(state_dir)
        self._state_dir.mkdir(parents=True, exist_ok=True)

        self._state = self._load_state()
        logger.info("RetrainTrigger 초기화 완료")

    def should_retrain(self,
                       feedback_stats: Optional[Dict[str, Any]] = None,
                       model_performance: Optional[Dict[str, Any]] = None,
                       force: bool = False) -> TriggerCheckResult:
        """
        재학습 필요 여부 판단 (A.1.1)

        Args:
            feedback_stats: 피드백 통계 (FeedbackSystem에서 제공)
            model_performance: 모델 성능 지표
            force: 강제 재학습 여부

        Returns:
            트리거 체크 결과
        """
        reasons: List[RetrainReason] = []
        details: Dict[str, Any] = {}

        # 강제 재학습
        if force:
            reasons.append(RetrainReason.MANUAL_REQUEST)
            details['force'] = True
            return TriggerCheckResult(
                should_retrain=True,
                reasons=reasons,
                details=details
            )

        # 쿨다운 체크
        if self._is_in_cooldown():
            details['cooldown'] = True
            details['cooldown_remaining'] = self._get_cooldown_remaining()
            return TriggerCheckResult(
                should_retrain=False,
                reasons=[],
                details=details
            )

        # 주간 재학습 횟수 제한 체크
        if self._exceeded_weekly_limit():
            details['weekly_limit_exceeded'] = True
            return TriggerCheckResult(
                should_retrain=False,
                reasons=[],
                details=details
            )

        # 조건별 체크
        self._check_feedback_conditions(feedback_stats, reasons, details)
        self._check_accuracy_conditions(model_performance, reasons, details)
        self._check_time_conditions(reasons, details)
        self._check_performance_conditions(model_performance, reasons, details)

        should_retrain = len(reasons) > 0

        if should_retrain:
            logger.info(f"재학습 트리거 활성화: {[r.value for r in reasons]}")
        else:
            logger.debug("재학습 조건 미충족")

        return TriggerCheckResult(
            should_retrain=should_retrain,
            reasons=reasons,
            details=details
        )

    def _check_feedback_conditions(self,
                                   feedback_stats: Optional[Dict[str, Any]],
                                   reasons: List[RetrainReason],
                                   details: Dict[str, Any]):
        """피드백 기반 조건 체크 (A.1.2)"""
        if not feedback_stats:
            details['feedback_check'] = 'no_data'
            return

        total_feedback = feedback_stats.get('processed_feedback', 0)
        new_feedback = feedback_stats.get('new_feedback_since_last_train',
                                          feedback_stats.get('processed_feedback', 0))

        details['total_feedback'] = total_feedback
        details['new_feedback'] = new_feedback
        details['min_feedback_required'] = self._config.min_feedback_count
        details['min_new_feedback_required'] = self._config.min_new_feedback_count

        # 충분한 피드백 축적 확인
        if (total_feedback >= self._config.min_feedback_count and
            new_feedback >= self._config.min_new_feedback_count):
            reasons.append(RetrainReason.SUFFICIENT_FEEDBACK)
            details['feedback_condition_met'] = True
        else:
            details['feedback_condition_met'] = False

    def _check_accuracy_conditions(self,
                                   model_performance: Optional[Dict[str, Any]],
                                   reasons: List[RetrainReason],
                                   details: Dict[str, Any]):
        """정확도 기반 조건 체크 (A.1.2)"""
        if not model_performance:
            details['accuracy_check'] = 'no_data'
            return

        current_accuracy = model_performance.get('accuracy', 1.0)
        baseline_accuracy = self._state.get('baseline_accuracy', 0.7)

        details['current_accuracy'] = current_accuracy
        details['baseline_accuracy'] = baseline_accuracy
        details['accuracy_threshold'] = self._config.accuracy_threshold

        # 절대 정확도 체크
        if current_accuracy < self._config.accuracy_threshold:
            reasons.append(RetrainReason.ACCURACY_DROP)
            details['accuracy_below_threshold'] = True
        else:
            details['accuracy_below_threshold'] = False

        # 상대적 정확도 하락 체크
        accuracy_drop = baseline_accuracy - current_accuracy
        details['accuracy_drop'] = accuracy_drop
        details['accuracy_drop_threshold'] = self._config.accuracy_drop_threshold

        if accuracy_drop > self._config.accuracy_drop_threshold:
            if RetrainReason.ACCURACY_DROP not in reasons:
                reasons.append(RetrainReason.ACCURACY_DROP)
            details['significant_accuracy_drop'] = True
        else:
            details['significant_accuracy_drop'] = False

    def _check_time_conditions(self,
                               reasons: List[RetrainReason],
                               details: Dict[str, Any]):
        """시간 기반 조건 체크 (A.1.2)"""
        last_retrain = self._state.get('last_retrain_date')

        if not last_retrain:
            details['time_check'] = 'no_previous_train'
            # 첫 학습이면 시간 조건 만족
            reasons.append(RetrainReason.TIME_BASED)
            return

        try:
            last_retrain_dt = datetime.fromisoformat(last_retrain)
            days_since_retrain = (datetime.now() - last_retrain_dt).days

            details['days_since_last_retrain'] = days_since_retrain
            details['max_days_allowed'] = self._config.max_days_without_retrain

            if days_since_retrain >= self._config.max_days_without_retrain:
                reasons.append(RetrainReason.TIME_BASED)
                details['time_condition_met'] = True
            else:
                details['time_condition_met'] = False

        except (ValueError, TypeError) as e:
            logger.warning(f"마지막 재학습 날짜 파싱 실패: {e}")
            details['time_check'] = 'parse_error'

    def _check_performance_conditions(self,
                                      model_performance: Optional[Dict[str, Any]],
                                      reasons: List[RetrainReason],
                                      details: Dict[str, Any]):
        """성능 기반 조건 체크 (A.1.2)"""
        if not model_performance:
            details['performance_check'] = 'no_data'
            return

        win_rate = model_performance.get('win_rate', 1.0)
        sharpe_ratio = model_performance.get('sharpe_ratio', 1.0)

        details['current_win_rate'] = win_rate
        details['min_win_rate'] = self._config.min_win_rate
        details['current_sharpe_ratio'] = sharpe_ratio
        details['min_sharpe_ratio'] = self._config.min_sharpe_ratio

        performance_degraded = False

        if win_rate < self._config.min_win_rate:
            performance_degraded = True
            details['win_rate_below_threshold'] = True
        else:
            details['win_rate_below_threshold'] = False

        if sharpe_ratio < self._config.min_sharpe_ratio:
            performance_degraded = True
            details['sharpe_below_threshold'] = True
        else:
            details['sharpe_below_threshold'] = False

        if performance_degraded:
            reasons.append(RetrainReason.PERFORMANCE_DEGRADATION)

    def _is_in_cooldown(self) -> bool:
        """쿨다운 상태 확인"""
        last_retrain = self._state.get('last_retrain_date')
        if not last_retrain:
            return False

        try:
            last_retrain_dt = datetime.fromisoformat(last_retrain)
            cooldown_end = last_retrain_dt + timedelta(hours=self._config.cooldown_hours)
            return datetime.now() < cooldown_end
        except (ValueError, TypeError):
            return False

    def _get_cooldown_remaining(self) -> Optional[float]:
        """쿨다운 남은 시간(시간 단위) 반환"""
        last_retrain = self._state.get('last_retrain_date')
        if not last_retrain:
            return None

        try:
            last_retrain_dt = datetime.fromisoformat(last_retrain)
            cooldown_end = last_retrain_dt + timedelta(hours=self._config.cooldown_hours)
            remaining = cooldown_end - datetime.now()
            return max(0, remaining.total_seconds() / 3600)
        except (ValueError, TypeError):
            return None

    def _exceeded_weekly_limit(self) -> bool:
        """주간 재학습 횟수 제한 초과 확인"""
        retrain_dates = self._state.get('retrain_dates', [])
        one_week_ago = datetime.now() - timedelta(days=7)

        weekly_count = 0
        for date_str in retrain_dates:
            try:
                dt = datetime.fromisoformat(date_str)
                if dt > one_week_ago:
                    weekly_count += 1
            except (ValueError, TypeError):
                continue

        return weekly_count >= self._config.max_retrain_per_week

    def record_retrain(self, accuracy: float = 0.0):
        """
        재학습 완료 기록

        Args:
            accuracy: 재학습 후 모델 정확도
        """
        now = datetime.now().isoformat()

        self._state['last_retrain_date'] = now
        self._state['baseline_accuracy'] = accuracy

        # 재학습 날짜 이력 관리
        retrain_dates = self._state.get('retrain_dates', [])
        retrain_dates.append(now)

        # 최근 30일치만 유지
        one_month_ago = (datetime.now() - timedelta(days=30)).isoformat()
        retrain_dates = [d for d in retrain_dates if d > one_month_ago]
        self._state['retrain_dates'] = retrain_dates

        self._save_state()
        logger.info(f"재학습 완료 기록: accuracy={accuracy}")

    def get_status(self) -> Dict[str, Any]:
        """현재 트리거 상태 조회"""
        return {
            'last_retrain_date': self._state.get('last_retrain_date'),
            'baseline_accuracy': self._state.get('baseline_accuracy'),
            'retrain_count_this_week': self._get_weekly_retrain_count(),
            'in_cooldown': self._is_in_cooldown(),
            'cooldown_remaining_hours': self._get_cooldown_remaining(),
            'config': asdict(self._config)
        }

    def _get_weekly_retrain_count(self) -> int:
        """이번 주 재학습 횟수"""
        retrain_dates = self._state.get('retrain_dates', [])
        one_week_ago = datetime.now() - timedelta(days=7)

        count = 0
        for date_str in retrain_dates:
            try:
                dt = datetime.fromisoformat(date_str)
                if dt > one_week_ago:
                    count += 1
            except (ValueError, TypeError):
                continue
        return count

    def _load_state(self) -> Dict[str, Any]:
        """상태 파일 로드"""
        state_file = self._state_dir / "trigger_state.json"

        try:
            if state_file.exists():
                with open(state_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"트리거 상태 로드 실패: {e}")

        return {}

    def _save_state(self):
        """상태 파일 저장"""
        state_file = self._state_dir / "trigger_state.json"

        try:
            with open(state_file, 'w', encoding='utf-8') as f:
                json.dump(self._state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"트리거 상태 저장 실패: {e}")


# 싱글톤 인스턴스
_retrain_trigger_instance: Optional[RetrainTrigger] = None


def get_retrain_trigger() -> RetrainTrigger:
    """RetrainTrigger 싱글톤 인스턴스 반환"""
    global _retrain_trigger_instance
    if _retrain_trigger_instance is None:
        _retrain_trigger_instance = RetrainTrigger()
    return _retrain_trigger_instance
