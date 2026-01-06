"""
LSTM 지속 학습 모듈

LSTM 모델의 지속적인 재학습 및 성과 모니터링을 담당합니다.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import numpy as np

logger = logging.getLogger(__name__)


class RetrainUrgency(Enum):
    """재학습 긴급도"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class RetrainDecision:
    """재학습 결정"""
    should_retrain: bool = False
    reasons: List[str] = field(default_factory=list)
    urgency: RetrainUrgency = RetrainUrgency.NORMAL

    def to_dict(self) -> Dict:
        return {
            'should_retrain': self.should_retrain,
            'reasons': self.reasons,
            'urgency': self.urgency.value,
        }


@dataclass
class RetrainResult:
    """재학습 결과"""
    success: bool = False
    new_accuracy: float = 0.0
    old_accuracy: float = 0.0
    improvement: float = 0.0
    training_samples: int = 0
    validation_samples: int = 0
    model_replaced: bool = False
    replacement_reason: str = ""
    training_time: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            'success': self.success,
            'new_accuracy': self.new_accuracy,
            'old_accuracy': self.old_accuracy,
            'improvement': self.improvement,
            'training_samples': self.training_samples,
            'validation_samples': self.validation_samples,
            'model_replaced': self.model_replaced,
            'replacement_reason': self.replacement_reason,
            'training_time': self.training_time,
            'timestamp': self.timestamp.isoformat(),
        }


@dataclass
class ModelMetrics:
    """모델 성과 지표"""
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    profit_factor: float = 0.0
    sharpe_ratio: float = 0.0
    sample_count: int = 0

    def to_dict(self) -> Dict:
        return {
            'accuracy': self.accuracy,
            'precision': self.precision,
            'recall': self.recall,
            'f1_score': self.f1_score,
            'profit_factor': self.profit_factor,
            'sharpe_ratio': self.sharpe_ratio,
            'sample_count': self.sample_count,
        }


@dataclass
class LearnerConfig:
    """학습기 설정"""
    # 재학습 주기
    retrain_period: str = 'weekly'  # daily, weekly, monthly

    # 최소 신규 샘플
    min_new_samples: int = 100

    # 성과 임계값 (이하 시 재학습)
    performance_threshold: float = 0.55

    # 학습 데이터 기간 (일)
    lookback_days: int = 252

    # 시퀀스 길이
    sequence_length: int = 20

    # 예측 기간
    prediction_horizon: int = 5

    # 모델 교체 조건
    min_improvement: float = 0.0  # 개선 필요 없음 (95% 이상이면 교체)
    min_replacement_ratio: float = 0.95  # 기존 대비 최소 비율


class LSTMContinuousLearner:
    """
    LSTM 모델 지속 학습 시스템

    정기적인 재학습과 성과 모니터링을 통해 모델을 최신 상태로 유지합니다.
    """

    def __init__(self, config: Optional[LearnerConfig] = None):
        """
        Args:
            config: 학습기 설정
        """
        self.config = config or LearnerConfig()

        # 현재 모델 (외부에서 주입)
        self.current_model = None
        self.model_version: str = "v0"

        # 성과 추적
        self._performance_history: List[ModelMetrics] = []
        self._last_retrain: Optional[datetime] = None
        self._new_samples_count: int = 0

        # 레짐 변화 감지
        self._last_regime: Optional[str] = None

    def set_model(self, model: Any, version: str = "v1") -> None:
        """
        현재 모델 설정

        Args:
            model: LSTM 모델
            version: 모델 버전
        """
        self.current_model = model
        self.model_version = version
        logger.info(f"Model set: {version}")

    def record_sample(self) -> None:
        """새 샘플 기록"""
        self._new_samples_count += 1

    def should_retrain(self, current_performance: Dict) -> RetrainDecision:
        """
        재학습 필요 여부 판단

        Args:
            current_performance: 현재 성과 지표

        Returns:
            RetrainDecision: 재학습 결정
        """
        reasons = []
        urgency = RetrainUrgency.NORMAL

        # 1. 정기 재학습 체크
        if self._is_scheduled_retrain_time():
            reasons.append('scheduled')

        # 2. 성과 저하 체크
        recent_accuracy = current_performance.get('recent_accuracy', 0.55)
        if recent_accuracy < self.config.performance_threshold:
            reasons.append(f'low_performance ({recent_accuracy:.1%})')
            urgency = RetrainUrgency.HIGH

        # 3. 시장 레짐 변화 체크
        current_regime = current_performance.get('market_regime')
        if self._detect_regime_change(current_regime):
            reasons.append('regime_change')
            if urgency != RetrainUrgency.HIGH:
                urgency = RetrainUrgency.NORMAL

        # 4. 신규 데이터 충분 체크
        if self._new_samples_count >= self.config.min_new_samples:
            reasons.append(f'sufficient_new_data ({self._new_samples_count})')

        # 5. 연속 손실 체크
        consecutive_losses = current_performance.get('consecutive_losses', 0)
        if consecutive_losses >= 5:
            reasons.append(f'consecutive_losses ({consecutive_losses})')
            urgency = RetrainUrgency.CRITICAL

        should_retrain = len(reasons) > 0

        return RetrainDecision(
            should_retrain=should_retrain,
            reasons=reasons,
            urgency=urgency,
        )

    def _is_scheduled_retrain_time(self) -> bool:
        """정기 재학습 시간 여부"""
        if not self._last_retrain:
            return True

        now = datetime.now()
        elapsed = now - self._last_retrain

        if self.config.retrain_period == 'daily':
            return elapsed >= timedelta(hours=24)
        elif self.config.retrain_period == 'weekly':
            return elapsed >= timedelta(days=7)
        elif self.config.retrain_period == 'monthly':
            return elapsed >= timedelta(days=30)

        return False

    def _detect_regime_change(self, current_regime: Optional[str]) -> bool:
        """레짐 변화 감지"""
        if current_regime is None:
            return False

        if self._last_regime is None:
            self._last_regime = current_regime
            return False

        changed = current_regime != self._last_regime
        self._last_regime = current_regime

        return changed

    def retrain(
        self,
        training_data: Dict,
        force: bool = False
    ) -> RetrainResult:
        """
        모델 재학습 실행

        Args:
            training_data: 학습 데이터
            force: 강제 재학습 여부

        Returns:
            RetrainResult: 재학습 결과
        """
        import time
        start_time = time.time()

        try:
            # 1. 데이터 준비
            X, y = self._create_features(training_data)

            if len(X) < self.config.min_new_samples:
                logger.warning(f"Insufficient data: {len(X)} samples")
                return RetrainResult(
                    success=False,
                    replacement_reason="insufficient_data",
                )

            # 2. 학습/검증 분할 (시계열)
            X_train, X_val, y_train, y_val = self._time_series_split(X, y)

            # 3. 모델 학습
            new_model = self._train_model(X_train, y_train)

            # 4. 검증
            new_accuracy = self._evaluate(new_model, X_val, y_val)
            old_accuracy = (
                self._evaluate(self.current_model, X_val, y_val)
                if self.current_model else 0.0
            )

            # 5. 비교 및 교체 결정
            improvement = new_accuracy - old_accuracy

            training_time = time.time() - start_time

            result = RetrainResult(
                success=True,
                new_accuracy=new_accuracy,
                old_accuracy=old_accuracy,
                improvement=improvement,
                training_samples=len(X_train),
                validation_samples=len(X_val),
                training_time=training_time,
            )

            # 6. 교체 조건 확인
            should_replace = (
                improvement > self.config.min_improvement or
                new_accuracy >= old_accuracy * self.config.min_replacement_ratio
            )

            if should_replace or force:
                self._replace_model(new_model)
                result.model_replaced = True
                result.replacement_reason = (
                    'improved' if improvement > 0 else
                    'acceptable' if not force else 'forced'
                )
                logger.info(
                    f"Model replaced: {old_accuracy:.2%} → {new_accuracy:.2%} "
                    f"({improvement:+.2%})"
                )
            else:
                result.model_replaced = False
                result.replacement_reason = 'not_improved'
                logger.info(
                    f"Model not replaced: new={new_accuracy:.2%}, "
                    f"old={old_accuracy:.2%}"
                )

            # 성과 기록
            self._performance_history.append(ModelMetrics(
                accuracy=new_accuracy if result.model_replaced else old_accuracy,
                sample_count=len(X_train),
            ))

            # 카운터 리셋
            self._new_samples_count = 0
            self._last_retrain = datetime.now()

            return result

        except Exception as e:
            logger.error(f"Retrain failed: {e}", exc_info=True)
            return RetrainResult(
                success=False,
                replacement_reason=f"error: {str(e)}",
                training_time=time.time() - start_time,
            )

    def _create_features(
        self,
        data: Dict
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        학습용 피처 생성

        Args:
            data: 원시 데이터

        Returns:
            Tuple[np.ndarray, np.ndarray]: (피처, 레이블)
        """
        # 데이터 추출
        prices = data.get('prices', [])
        volumes = data.get('volumes', [])
        indicators = data.get('indicators', {})

        if len(prices) < self.config.sequence_length + self.config.prediction_horizon:
            return np.array([]), np.array([])

        features = []
        labels = []

        for i in range(self.config.sequence_length, len(prices) - self.config.prediction_horizon):
            # 시퀀스 데이터
            price_seq = prices[i - self.config.sequence_length:i]
            vol_seq = volumes[i - self.config.sequence_length:i] if volumes else [1.0] * self.config.sequence_length

            # 수익률 계산
            returns = np.diff(price_seq) / price_seq[:-1]

            # 피처 벡터 구성
            feature_vector = []

            # 가격 기반 피처
            feature_vector.extend([
                np.mean(returns),
                np.std(returns),
                returns[-1],  # 최근 수익률
                (price_seq[-1] - price_seq[0]) / price_seq[0],  # 기간 수익률
            ])

            # 거래량 피처
            vol_mean = np.mean(vol_seq)
            feature_vector.extend([
                vol_seq[-1] / vol_mean if vol_mean > 0 else 1.0,
            ])

            # 지표 피처
            for ind_name, ind_values in indicators.items():
                if i < len(ind_values):
                    feature_vector.append(ind_values[i])

            features.append(feature_vector)

            # 레이블: 미래 수익률 방향
            future_return = (prices[i + self.config.prediction_horizon] - prices[i]) / prices[i]
            labels.append(1 if future_return > 0 else 0)

        return np.array(features), np.array(labels)

    def _time_series_split(
        self,
        X: np.ndarray,
        y: np.ndarray,
        test_ratio: float = 0.2
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """시계열 분할 (셔플 없음)"""
        split_idx = int(len(X) * (1 - test_ratio))

        return (
            X[:split_idx],
            X[split_idx:],
            y[:split_idx],
            y[split_idx:],
        )

    def _train_model(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray
    ) -> Any:
        """
        모델 학습

        실제 구현에서는 LSTM 모델을 학습합니다.
        여기서는 간단한 로지스틱 회귀로 대체합니다.
        """
        try:
            from sklearn.linear_model import LogisticRegression
            from sklearn.preprocessing import StandardScaler

            # 스케일링
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X_train)

            # 모델 학습
            model = LogisticRegression(max_iter=1000, random_state=42)
            model.fit(X_scaled, y_train)

            # 스케일러와 모델을 함께 반환
            return {'model': model, 'scaler': scaler}

        except ImportError:
            logger.warning("sklearn not available, using dummy model")
            return {'dummy': True}

    def _evaluate(
        self,
        model: Any,
        X_val: np.ndarray,
        y_val: np.ndarray
    ) -> float:
        """모델 평가"""
        if model is None or len(X_val) == 0:
            return 0.0

        if isinstance(model, dict) and 'dummy' in model:
            return 0.5

        try:
            scaler = model.get('scaler')
            clf = model.get('model')

            if scaler is None or clf is None:
                return 0.5

            X_scaled = scaler.transform(X_val)
            accuracy = clf.score(X_scaled, y_val)

            return accuracy

        except Exception as e:
            logger.error(f"Evaluation failed: {e}", exc_info=True)
            return 0.0

    def _replace_model(self, new_model: Any) -> None:
        """모델 교체"""
        self.current_model = new_model
        self.model_version = f"v{len(self._performance_history) + 1}"

    def predict(
        self,
        features: np.ndarray
    ) -> Tuple[int, float]:
        """
        예측 수행

        Args:
            features: 입력 피처

        Returns:
            Tuple[int, float]: (예측값, 확률)
        """
        if self.current_model is None:
            return 0, 0.5

        if isinstance(self.current_model, dict) and 'dummy' in self.current_model:
            return 0, 0.5

        try:
            scaler = self.current_model.get('scaler')
            clf = self.current_model.get('model')

            if scaler is None or clf is None:
                return 0, 0.5

            X_scaled = scaler.transform(features.reshape(1, -1))
            prediction = clf.predict(X_scaled)[0]
            probability = clf.predict_proba(X_scaled)[0].max()

            return int(prediction), float(probability)

        except Exception as e:
            logger.error(f"Prediction failed: {e}", exc_info=True)
            return 0, 0.5

    def get_stats(self) -> Dict[str, Any]:
        """통계 정보"""
        return {
            'model_version': self.model_version,
            'last_retrain': self._last_retrain.isoformat() if self._last_retrain else None,
            'new_samples': self._new_samples_count,
            'performance_history_length': len(self._performance_history),
            'current_accuracy': (
                self._performance_history[-1].accuracy
                if self._performance_history else 0.0
            ),
            'config': {
                'retrain_period': self.config.retrain_period,
                'min_new_samples': self.config.min_new_samples,
                'performance_threshold': self.config.performance_threshold,
            },
        }

    def get_performance_trend(self, n_recent: int = 10) -> List[float]:
        """최근 성과 추이"""
        recent = self._performance_history[-n_recent:]
        return [m.accuracy for m in recent]
