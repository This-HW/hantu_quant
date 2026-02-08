"""
학습 안전장치 모듈

과적합 방지, 롤백 메커니즘, 학습 검증을 담당합니다.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import copy

from core.utils.log_utils import get_logger

logger = get_logger(__name__)


class ValidationCheckType(Enum):
    """검증 체크 유형"""
    MIN_SAMPLES = "min_samples"
    OVERFIT_GAP = "overfit_gap"
    SUDDEN_CHANGE = "sudden_change"
    OOS_PERFORMANCE = "oos_performance"
    CONSISTENCY = "consistency"


@dataclass
class ValidationCheck:
    """검증 체크 결과"""
    check_type: ValidationCheckType
    passed: bool
    message: str = ""
    value: float = 0.0
    threshold: float = 0.0

    def to_dict(self) -> Dict:
        return {
            'check_type': self.check_type.value,
            'passed': self.passed,
            'message': self.message,
            'value': self.value,
            'threshold': self.threshold,
        }


@dataclass
class ValidationResult:
    """검증 결과"""
    passed: bool
    checks: List[ValidationCheck] = field(default_factory=list)
    recommendation: str = "reject"
    risk_level: str = "low"

    def to_dict(self) -> Dict:
        return {
            'passed': self.passed,
            'checks': [c.to_dict() for c in self.checks],
            'recommendation': self.recommendation,
            'risk_level': self.risk_level,
        }


@dataclass
class LearningResult:
    """학습 결과"""
    success: bool = False
    learning_type: str = ""
    training_samples: int = 0
    training_score: float = 0.0
    validation_score: float = 0.0
    out_of_sample_score: float = 0.0
    improvement: float = 0.0
    before_state: Dict = field(default_factory=dict)
    after_state: Dict = field(default_factory=dict)


@dataclass
class RollbackDecision:
    """롤백 결정"""
    should_rollback: bool = False
    reason: str = ""
    target_version: str = ""
    urgency: str = "normal"

    def to_dict(self) -> Dict:
        return {
            'should_rollback': self.should_rollback,
            'reason': self.reason,
            'target_version': self.target_version,
            'urgency': self.urgency,
        }


@dataclass
class SafetyConfig:
    """안전장치 설정"""
    # 최소 샘플 수
    min_samples: int = 100

    # 과적합 감지 임계값
    overfit_gap_threshold: float = 0.1  # 학습/검증 차이 10% 이상

    # 급격한 변화 임계값
    sudden_change_threshold: float = 0.3  # 30% 이상 변화

    # OOS 성과 임계값
    oos_performance_ratio: float = 0.8  # 검증 대비 80% 미만

    # 롤백 조건
    performance_drop_threshold: float = 0.2  # 20% 이상 하락
    consecutive_loss_threshold: int = 5  # 5회 연속 손실

    # 모델 히스토리 보관 수
    max_model_history: int = 10


class OverfitPrevention:
    """
    과적합 방지 장치

    방지 메커니즘:
    1. 워크포워드 검증 필수
    2. 최소 샘플 수 요구
    3. 성과 변화 제한
    4. A/B 테스트
    """

    def __init__(self, config: Optional[SafetyConfig] = None):
        """
        Args:
            config: 안전장치 설정
        """
        self.config = config or SafetyConfig()

    def validate_learning_result(
        self,
        result: LearningResult
    ) -> ValidationResult:
        """
        학습 결과 검증

        Args:
            result: 학습 결과

        Returns:
            ValidationResult: 검증 결과
        """
        checks = []
        risk_level = "low"

        # 1. 최소 샘플 수 체크
        min_samples_check = self._check_min_samples(result)
        checks.append(min_samples_check)

        # 2. 과적합 징후 체크
        overfit_check = self._check_overfit_gap(result)
        checks.append(overfit_check)
        if not overfit_check.passed:
            risk_level = "medium"

        # 3. 급격한 변화 체크
        sudden_change_check = self._check_sudden_change(result)
        checks.append(sudden_change_check)
        if not sudden_change_check.passed:
            risk_level = "high"

        # 4. OOS 성과 체크
        oos_check = self._check_oos_performance(result)
        checks.append(oos_check)
        if not oos_check.passed:
            risk_level = "high"

        # 5. 일관성 체크
        consistency_check = self._check_consistency(result)
        checks.append(consistency_check)

        # 최종 판정
        all_passed = all(c.passed for c in checks)
        critical_passed = all(
            c.passed for c in checks
            if c.check_type in [
                ValidationCheckType.MIN_SAMPLES,
                ValidationCheckType.SUDDEN_CHANGE,
            ]
        )

        if all_passed:
            recommendation = "apply"
        elif critical_passed:
            recommendation = "apply_with_caution"
        else:
            recommendation = "reject"

        return ValidationResult(
            passed=all_passed,
            checks=checks,
            recommendation=recommendation,
            risk_level=risk_level,
        )

    def _check_min_samples(self, result: LearningResult) -> ValidationCheck:
        """최소 샘플 수 체크"""
        passed = result.training_samples >= self.config.min_samples
        return ValidationCheck(
            check_type=ValidationCheckType.MIN_SAMPLES,
            passed=passed,
            message="" if passed else f"샘플 부족: {result.training_samples} < {self.config.min_samples}",
            value=result.training_samples,
            threshold=self.config.min_samples,
        )

    def _check_overfit_gap(self, result: LearningResult) -> ValidationCheck:
        """과적합 징후 체크"""
        gap = result.training_score - result.validation_score
        passed = gap <= self.config.overfit_gap_threshold

        return ValidationCheck(
            check_type=ValidationCheckType.OVERFIT_GAP,
            passed=passed,
            message="" if passed else f"과적합 의심: 학습/검증 차이 {gap:.1%}",
            value=gap,
            threshold=self.config.overfit_gap_threshold,
        )

    def _check_sudden_change(self, result: LearningResult) -> ValidationCheck:
        """급격한 변화 체크"""
        passed = abs(result.improvement) <= self.config.sudden_change_threshold

        return ValidationCheck(
            check_type=ValidationCheckType.SUDDEN_CHANGE,
            passed=passed,
            message="" if passed else f"급격한 변화: {result.improvement:.1%}",
            value=abs(result.improvement),
            threshold=self.config.sudden_change_threshold,
        )

    def _check_oos_performance(self, result: LearningResult) -> ValidationCheck:
        """Out-of-sample 성과 체크"""
        if result.validation_score == 0:
            return ValidationCheck(
                check_type=ValidationCheckType.OOS_PERFORMANCE,
                passed=True,
                message="검증 데이터 없음",
            )

        ratio = result.out_of_sample_score / result.validation_score
        passed = ratio >= self.config.oos_performance_ratio

        return ValidationCheck(
            check_type=ValidationCheckType.OOS_PERFORMANCE,
            passed=passed,
            message="" if passed else f"OOS 성과 저조: {ratio:.1%}",
            value=ratio,
            threshold=self.config.oos_performance_ratio,
        )

    def _check_consistency(self, result: LearningResult) -> ValidationCheck:
        """일관성 체크"""
        # 상태 변화가 너무 크지 않은지 확인
        before = result.before_state
        after = result.after_state

        if not before or not after:
            return ValidationCheck(
                check_type=ValidationCheckType.CONSISTENCY,
                passed=True,
                message="상태 정보 없음",
            )

        # 가중치 변화 체크 (앙상블의 경우)
        if 'weights' in before and 'weights' in after:
            max_change = 0.0
            for key in before['weights']:
                if key in after['weights']:
                    change = abs(after['weights'][key] - before['weights'][key])
                    max_change = max(max_change, change)

            passed = max_change <= 0.2  # 20% 이내 변화
            return ValidationCheck(
                check_type=ValidationCheckType.CONSISTENCY,
                passed=passed,
                message="" if passed else f"가중치 급변: {max_change:.1%}",
                value=max_change,
                threshold=0.2,
            )

        return ValidationCheck(
            check_type=ValidationCheckType.CONSISTENCY,
            passed=True,
        )


class ModelRollback:
    """
    모델 롤백 메커니즘

    롤백 조건:
    - 새 모델 적용 후 성과 급격히 악화
    - 연속 손실 발생
    - 시스템 오류 발생
    """

    def __init__(self, config: Optional[SafetyConfig] = None):
        """
        Args:
            config: 안전장치 설정
        """
        self.config = config or SafetyConfig()
        self._model_history: List[Dict] = []
        self._current_version: str = "v0"
        self._recent_trades: List[Dict] = []

    def save_model_state(
        self,
        model_state: Any,
        version: str,
        performance: Dict
    ) -> None:
        """
        모델 상태 저장

        Args:
            model_state: 모델 상태
            version: 버전
            performance: 성과 지표
        """
        self._model_history.append({
            'version': version,
            'state': copy.deepcopy(model_state),
            'performance': performance,
            'timestamp': datetime.now(),
        })

        # 히스토리 크기 제한
        if len(self._model_history) > self.config.max_model_history:
            self._model_history = self._model_history[-self.config.max_model_history:]

        self._current_version = version
        logger.info(f"Model state saved: {version}")

    def record_trade_result(self, is_win: bool, pnl: float) -> None:
        """
        거래 결과 기록

        Args:
            is_win: 승리 여부
            pnl: 손익
        """
        self._recent_trades.append({
            'is_win': is_win,
            'pnl': pnl,
            'timestamp': datetime.now(),
        })

        # 최근 20건만 유지
        if len(self._recent_trades) > 20:
            self._recent_trades = self._recent_trades[-20:]

    def should_rollback(
        self,
        current_performance: float,
        previous_performance: float
    ) -> RollbackDecision:
        """
        롤백 필요 여부 판단

        Args:
            current_performance: 현재 성과
            previous_performance: 이전 성과

        Returns:
            RollbackDecision: 롤백 결정
        """
        # 조건 1: 성과 급락
        performance_drop = previous_performance - current_performance
        if performance_drop > self.config.performance_drop_threshold:
            return RollbackDecision(
                should_rollback=True,
                reason=f"성과 급락: {performance_drop:.1%}",
                target_version=self._get_previous_version(),
                urgency="high",
            )

        # 조건 2: 연속 손실
        consecutive_losses = self._count_consecutive_losses()
        if consecutive_losses >= self.config.consecutive_loss_threshold:
            return RollbackDecision(
                should_rollback=True,
                reason=f"연속 {consecutive_losses}회 손실",
                target_version=self._get_previous_version(),
                urgency="high",
            )

        # 조건 3: 최근 성과 급락 (최근 10건 기준)
        if len(self._recent_trades) >= 10:
            recent_wins = sum(1 for t in self._recent_trades[-10:] if t['is_win'])
            if recent_wins < 3:  # 30% 미만 승률
                return RollbackDecision(
                    should_rollback=True,
                    reason=f"최근 승률 급락: {recent_wins}/10",
                    target_version=self._get_previous_version(),
                    urgency="medium",
                )

        return RollbackDecision(should_rollback=False)

    def _count_consecutive_losses(self) -> int:
        """연속 손실 횟수"""
        count = 0
        for trade in reversed(self._recent_trades):
            if trade['is_win']:
                break
            count += 1
        return count

    def _get_previous_version(self) -> str:
        """이전 버전 조회"""
        if len(self._model_history) < 2:
            return "v0"
        return self._model_history[-2]['version']

    def rollback(self, target_version: str) -> Optional[Dict]:
        """
        모델 롤백 실행

        Args:
            target_version: 롤백할 버전

        Returns:
            Dict: 롤백된 모델 상태 (없으면 None)
        """
        for history in reversed(self._model_history):
            if history['version'] == target_version:
                self._current_version = target_version
                logger.warning(f"Model rolled back to {target_version}")
                return history['state']

        logger.error(f"Version not found: {target_version}", exc_info=True)
        return None

    def force_rollback(self, steps: int = 1) -> Optional[Dict]:
        """
        강제 롤백

        Args:
            steps: 롤백 단계 수

        Returns:
            Dict: 롤백된 모델 상태
        """
        if len(self._model_history) <= steps:
            return None

        target_idx = -(steps + 1)
        target = self._model_history[target_idx]

        self._current_version = target['version']
        logger.warning(f"Forced rollback to {target['version']}")

        return target['state']

    def get_version_history(self) -> List[Dict]:
        """버전 히스토리 조회"""
        return [
            {
                'version': h['version'],
                'performance': h['performance'],
                'timestamp': h['timestamp'].isoformat(),
            }
            for h in self._model_history
        ]

    @property
    def current_version(self) -> str:
        """현재 버전"""
        return self._current_version


class LearningSafetyManager:
    """
    학습 안전 관리자

    과적합 방지, 롤백 관리를 통합 제공합니다.
    """

    def __init__(self, config: Optional[SafetyConfig] = None):
        """
        Args:
            config: 안전장치 설정
        """
        self.config = config or SafetyConfig()
        self.overfit_prevention = OverfitPrevention(self.config)
        self.model_rollback = ModelRollback(self.config)

    def validate_and_apply(
        self,
        learning_result: LearningResult,
        model_state: Any
    ) -> Dict[str, Any]:
        """
        학습 결과 검증 및 적용

        Args:
            learning_result: 학습 결과
            model_state: 모델 상태

        Returns:
            Dict: 처리 결과
        """
        # 검증
        validation = self.overfit_prevention.validate_learning_result(learning_result)

        if validation.recommendation == "reject":
            return {
                'applied': False,
                'reason': 'validation_failed',
                'validation': validation.to_dict(),
            }

        # 현재 상태 저장
        self.model_rollback.save_model_state(
            model_state=model_state,
            version=f"v{len(self.model_rollback._model_history) + 1}",
            performance={
                'validation_score': learning_result.validation_score,
                'improvement': learning_result.improvement,
            },
        )

        return {
            'applied': True,
            'version': self.model_rollback.current_version,
            'validation': validation.to_dict(),
            'warning': validation.recommendation == "apply_with_caution",
        }

    def check_and_rollback(
        self,
        current_performance: float,
        previous_performance: float
    ) -> Dict[str, Any]:
        """
        성과 체크 및 필요시 롤백

        Args:
            current_performance: 현재 성과
            previous_performance: 이전 성과

        Returns:
            Dict: 처리 결과
        """
        decision = self.model_rollback.should_rollback(
            current_performance, previous_performance
        )

        if decision.should_rollback:
            rolled_back_state = self.model_rollback.rollback(decision.target_version)
            return {
                'rolled_back': True,
                'reason': decision.reason,
                'target_version': decision.target_version,
                'state': rolled_back_state,
            }

        return {'rolled_back': False}

    def record_trade(self, is_win: bool, pnl: float) -> None:
        """거래 결과 기록"""
        self.model_rollback.record_trade_result(is_win, pnl)

    def get_status(self) -> Dict[str, Any]:
        """상태 조회"""
        return {
            'current_version': self.model_rollback.current_version,
            'model_history_count': len(self.model_rollback._model_history),
            'recent_trades_count': len(self.model_rollback._recent_trades),
            'consecutive_losses': self.model_rollback._count_consecutive_losses(),
        }
