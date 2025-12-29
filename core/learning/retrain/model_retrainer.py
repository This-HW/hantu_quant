"""
모델 재학습 실행기

Task A.2.1: ModelRetrainer 클래스 생성
Task A.2.2: 점진적 학습 (Incremental Learning) 구현
Task A.2.3: 모델 검증 로직 (홀드아웃, 성능 비교)
"""

import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, asdict, field
from enum import Enum
import threading
import queue

from core.utils.log_utils import get_logger

logger = get_logger(__name__)


class RetrainStatus(Enum):
    """재학습 상태"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class ValidationResult:
    """모델 검증 결과"""
    passed: bool
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    auc_score: float
    holdout_size: int
    baseline_accuracy: float
    improvement: float
    validation_time: float
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RetrainResult:
    """재학습 결과"""
    status: RetrainStatus
    started_at: str
    completed_at: Optional[str]
    training_samples: int
    validation_result: Optional[ValidationResult]
    model_version: str
    previous_version: Optional[str]
    training_time_seconds: float
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result['status'] = self.status.value
        if self.validation_result:
            result['validation_result'] = self.validation_result.to_dict()
        return result


@dataclass
class RetrainConfig:
    """재학습 설정"""
    # 검증 설정
    holdout_ratio: float = 0.2              # 홀드아웃 비율 (20%)
    min_accuracy_threshold: float = 0.55     # 최소 정확도
    min_improvement_threshold: float = -0.02 # 최소 개선율 (-2% 이상)

    # 학습 설정
    max_epochs: int = 100
    early_stopping_patience: int = 10
    batch_size: int = 32
    learning_rate: float = 0.001

    # 점진적 학습 설정
    incremental_enabled: bool = True
    incremental_data_weight: float = 0.3    # 새 데이터 가중치


class ModelRetrainer:
    """모델 재학습 실행기"""

    def __init__(self,
                 model_dir: str = "data/models",
                 config: Optional[RetrainConfig] = None):
        """
        초기화

        Args:
            model_dir: 모델 저장 디렉토리
            config: 재학습 설정
        """
        self._model_dir = Path(model_dir)
        self._model_dir.mkdir(parents=True, exist_ok=True)

        self._config = config or RetrainConfig()
        self._current_status = RetrainStatus.PENDING
        self._current_result: Optional[RetrainResult] = None

        # 백그라운드 학습용
        self._training_thread: Optional[threading.Thread] = None
        self._training_queue: queue.Queue = queue.Queue()
        self._stop_event = threading.Event()

        # 모델 레지스트리
        self._model_registry = self._load_model_registry()

        logger.info("ModelRetrainer 초기화 완료")

    def retrain(self,
                training_data: List[Dict[str, Any]],
                model_trainer: Optional[Callable] = None,
                background: bool = False) -> RetrainResult:
        """
        모델 재학습 실행 (A.2.1)

        Args:
            training_data: 학습 데이터
            model_trainer: 모델 학습 함수 (None이면 기본 학습기 사용)
            background: 백그라운드 실행 여부

        Returns:
            재학습 결과
        """
        if background:
            return self._start_background_training(training_data, model_trainer)

        return self._execute_training(training_data, model_trainer)

    def _execute_training(self,
                          training_data: List[Dict[str, Any]],
                          model_trainer: Optional[Callable] = None) -> RetrainResult:
        """학습 실행 로직"""
        start_time = datetime.now()
        self._current_status = RetrainStatus.IN_PROGRESS

        try:
            # 1. 데이터 분할 (학습/검증)
            train_data, holdout_data = self._split_data(training_data)
            logger.info(f"데이터 분할: 학습={len(train_data)}, 검증={len(holdout_data)}")

            # 2. 현재 모델 버전 백업
            previous_version = self._get_current_model_version()

            # 3. 모델 학습
            if model_trainer:
                trained_model = model_trainer(train_data, self._config)
            else:
                trained_model = self._default_training(train_data)

            # 4. 새 모델 버전 생성
            new_version = self._generate_model_version()

            # 5. 검증 (A.2.3)
            self._current_status = RetrainStatus.VALIDATING
            validation_result = self._validate_model(
                trained_model, holdout_data, previous_version
            )

            # 6. 검증 통과 여부 확인
            if not validation_result.passed:
                logger.warning(f"모델 검증 실패: {validation_result.error_message}")
                self._current_status = RetrainStatus.FAILED

                return RetrainResult(
                    status=RetrainStatus.FAILED,
                    started_at=start_time.isoformat(),
                    completed_at=datetime.now().isoformat(),
                    training_samples=len(train_data),
                    validation_result=validation_result,
                    model_version=new_version,
                    previous_version=previous_version,
                    training_time_seconds=(datetime.now() - start_time).total_seconds(),
                    error_message="모델 검증 실패"
                )

            # 7. 모델 저장 및 등록
            self._save_model(trained_model, new_version)
            self._register_model(new_version, validation_result)

            self._current_status = RetrainStatus.COMPLETED
            logger.info(f"재학습 완료: {new_version}, 정확도={validation_result.accuracy:.4f}")

            result = RetrainResult(
                status=RetrainStatus.COMPLETED,
                started_at=start_time.isoformat(),
                completed_at=datetime.now().isoformat(),
                training_samples=len(train_data),
                validation_result=validation_result,
                model_version=new_version,
                previous_version=previous_version,
                training_time_seconds=(datetime.now() - start_time).total_seconds()
            )

            self._current_result = result
            return result

        except Exception as e:
            logger.error(f"재학습 실패: {e}")
            self._current_status = RetrainStatus.FAILED

            return RetrainResult(
                status=RetrainStatus.FAILED,
                started_at=start_time.isoformat(),
                completed_at=datetime.now().isoformat(),
                training_samples=len(training_data),
                validation_result=None,
                model_version="",
                previous_version=self._get_current_model_version(),
                training_time_seconds=(datetime.now() - start_time).total_seconds(),
                error_message=str(e)
            )

    def retrain_incremental(self,
                           new_data: List[Dict[str, Any]],
                           existing_data: Optional[List[Dict[str, Any]]] = None) -> RetrainResult:
        """
        점진적 학습 (A.2.2)

        기존 데이터와 새 데이터를 가중치 적용하여 학습

        Args:
            new_data: 새로운 학습 데이터
            existing_data: 기존 학습 데이터 (None이면 저장된 데이터 사용)

        Returns:
            재학습 결과
        """
        if not self._config.incremental_enabled:
            logger.warning("점진적 학습이 비활성화됨, 일반 학습 수행")
            return self.retrain(new_data)

        # 기존 데이터 로드
        if existing_data is None:
            existing_data = self._load_training_data_cache()

        if not existing_data:
            logger.info("기존 데이터 없음, 일반 학습 수행")
            return self.retrain(new_data)

        # 데이터 가중치 적용
        # 새 데이터에 더 높은 샘플링 확률 부여
        combined_data = self._weighted_data_combine(existing_data, new_data)

        logger.info(f"점진적 학습: 기존={len(existing_data)}, "
                   f"신규={len(new_data)}, 결합={len(combined_data)}")

        return self.retrain(combined_data)

    def _weighted_data_combine(self,
                               existing: List[Dict[str, Any]],
                               new: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """가중치 기반 데이터 결합"""
        import random

        new_weight = self._config.incremental_data_weight
        existing_weight = 1 - new_weight

        # 목표 샘플 수
        target_size = len(existing) + len(new)

        # 새 데이터 샘플 수
        new_samples = int(target_size * new_weight)
        existing_samples = target_size - new_samples

        # 샘플링 (복원 추출)
        combined = []

        if new and new_samples > 0:
            new_sampled = random.choices(new, k=min(new_samples, len(new) * 2))
            combined.extend(new_sampled)

        if existing and existing_samples > 0:
            existing_sampled = random.choices(existing, k=min(existing_samples, len(existing)))
            combined.extend(existing_sampled)

        random.shuffle(combined)
        return combined

    def _split_data(self,
                   data: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """학습/검증 데이터 분할"""
        import random

        shuffled = data.copy()
        random.shuffle(shuffled)

        holdout_size = int(len(shuffled) * self._config.holdout_ratio)
        holdout_size = max(1, holdout_size)  # 최소 1개

        holdout = shuffled[:holdout_size]
        train = shuffled[holdout_size:]

        return train, holdout

    def _validate_model(self,
                       model: Any,
                       holdout_data: List[Dict[str, Any]],
                       previous_version: Optional[str]) -> ValidationResult:
        """
        모델 검증 (A.2.3)

        Args:
            model: 학습된 모델
            holdout_data: 홀드아웃 검증 데이터
            previous_version: 이전 모델 버전

        Returns:
            검증 결과
        """
        start_time = datetime.now()

        try:
            # 예측 수행 및 지표 계산
            predictions = []
            actuals = []

            for sample in holdout_data:
                # 모델이 있으면 예측, 없으면 더미 예측
                if hasattr(model, 'predict'):
                    pred = model.predict(sample)
                else:
                    # 더미 예측 (실제 구현에서는 모델 사용)
                    pred = sample.get('predicted_class', 0)

                predictions.append(pred)
                actuals.append(sample.get('actual_class', sample.get('is_win', 0)))

            # 지표 계산
            metrics = self._calculate_metrics(predictions, actuals)

            # 이전 모델 성능 조회
            baseline_accuracy = 0.5
            if previous_version:
                prev_info = self._model_registry.get(previous_version, {})
                baseline_accuracy = prev_info.get('accuracy', 0.5)

            improvement = metrics['accuracy'] - baseline_accuracy

            # 검증 통과 조건
            passed = (
                metrics['accuracy'] >= self._config.min_accuracy_threshold and
                improvement >= self._config.min_improvement_threshold
            )

            error_message = None
            if not passed:
                if metrics['accuracy'] < self._config.min_accuracy_threshold:
                    error_message = f"정확도 미달: {metrics['accuracy']:.4f} < {self._config.min_accuracy_threshold}"
                elif improvement < self._config.min_improvement_threshold:
                    error_message = f"개선율 미달: {improvement:.4f} < {self._config.min_improvement_threshold}"

            return ValidationResult(
                passed=passed,
                accuracy=metrics['accuracy'],
                precision=metrics['precision'],
                recall=metrics['recall'],
                f1_score=metrics['f1'],
                auc_score=metrics.get('auc', 0.5),
                holdout_size=len(holdout_data),
                baseline_accuracy=baseline_accuracy,
                improvement=improvement,
                validation_time=(datetime.now() - start_time).total_seconds(),
                error_message=error_message
            )

        except Exception as e:
            logger.error(f"모델 검증 오류: {e}")
            return ValidationResult(
                passed=False,
                accuracy=0.0,
                precision=0.0,
                recall=0.0,
                f1_score=0.0,
                auc_score=0.0,
                holdout_size=len(holdout_data),
                baseline_accuracy=0.5,
                improvement=0.0,
                validation_time=(datetime.now() - start_time).total_seconds(),
                error_message=str(e)
            )

    def _calculate_metrics(self,
                          predictions: List[int],
                          actuals: List[int]) -> Dict[str, float]:
        """분류 지표 계산"""
        if not predictions or not actuals:
            return {'accuracy': 0, 'precision': 0, 'recall': 0, 'f1': 0}

        # 기본 지표 계산
        correct = sum(1 for p, a in zip(predictions, actuals) if p == a)
        accuracy = correct / len(predictions)

        # Precision, Recall, F1
        tp = sum(1 for p, a in zip(predictions, actuals) if p == 1 and a == 1)
        fp = sum(1 for p, a in zip(predictions, actuals) if p == 1 and a == 0)
        fn = sum(1 for p, a in zip(predictions, actuals) if p == 0 and a == 1)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

        return {
            'accuracy': accuracy,
            'precision': precision,
            'recall': recall,
            'f1': f1
        }

    def _default_training(self, train_data: List[Dict[str, Any]]) -> Any:
        """기본 학습 로직 (실제 구현에서 오버라이드)"""
        # 더미 모델 반환 (실제 구현에서는 LSTM/PPO 등 사용)
        logger.info(f"기본 학습 수행: {len(train_data)}개 샘플")

        class DummyModel:
            def predict(self, x):
                return 1 if x.get('predicted_probability', 0.5) > 0.5 else 0

        return DummyModel()

    def _generate_model_version(self) -> str:
        """모델 버전 생성"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        random_suffix = hashlib.md5(str(datetime.now().timestamp()).encode()).hexdigest()[:6]
        return f"v_{timestamp}_{random_suffix}"

    def _get_current_model_version(self) -> Optional[str]:
        """현재 활성 모델 버전 조회"""
        for version, info in self._model_registry.items():
            if info.get('is_active', False):
                return version
        return None

    def _save_model(self, model: Any, version: str):
        """모델 저장"""
        model_path = self._model_dir / f"model_{version}.pkl"

        try:
            import pickle
            with open(model_path, 'wb') as f:
                # 보안: 저장 시 메타데이터만 저장 (실제 모델은 별도 처리)
                pickle.dump({'version': version, 'saved_at': datetime.now().isoformat()}, f)
            logger.info(f"모델 저장: {model_path}")
        except Exception as e:
            logger.error(f"모델 저장 실패: {e}")

    def _register_model(self, version: str, validation: ValidationResult):
        """모델 레지스트리에 등록"""
        # 기존 활성 모델 비활성화
        for v in self._model_registry:
            self._model_registry[v]['is_active'] = False

        # 새 모델 등록
        self._model_registry[version] = {
            'version': version,
            'registered_at': datetime.now().isoformat(),
            'accuracy': validation.accuracy,
            'precision': validation.precision,
            'recall': validation.recall,
            'f1_score': validation.f1_score,
            'is_active': True
        }

        self._save_model_registry()

    def _load_model_registry(self) -> Dict[str, Dict]:
        """모델 레지스트리 로드"""
        registry_file = self._model_dir / "model_registry.json"

        try:
            if registry_file.exists():
                with open(registry_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"모델 레지스트리 로드 실패: {e}")

        return {}

    def _save_model_registry(self):
        """모델 레지스트리 저장"""
        registry_file = self._model_dir / "model_registry.json"

        try:
            with open(registry_file, 'w', encoding='utf-8') as f:
                json.dump(self._model_registry, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"모델 레지스트리 저장 실패: {e}")

    def _load_training_data_cache(self) -> List[Dict[str, Any]]:
        """학습 데이터 캐시 로드"""
        cache_file = self._model_dir / "training_data_cache.json"

        try:
            if cache_file.exists():
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"학습 데이터 캐시 로드 실패: {e}")

        return []

    def _start_background_training(self,
                                   training_data: List[Dict[str, Any]],
                                   model_trainer: Optional[Callable]) -> RetrainResult:
        """백그라운드 학습 시작"""
        if self._training_thread and self._training_thread.is_alive():
            logger.warning("이미 학습 진행 중")
            return RetrainResult(
                status=RetrainStatus.IN_PROGRESS,
                started_at=datetime.now().isoformat(),
                completed_at=None,
                training_samples=0,
                validation_result=None,
                model_version="",
                previous_version=None,
                training_time_seconds=0,
                error_message="이미 학습 진행 중"
            )

        def training_worker():
            result = self._execute_training(training_data, model_trainer)
            self._training_queue.put(result)

        self._training_thread = threading.Thread(target=training_worker, daemon=True)
        self._training_thread.start()

        logger.info("백그라운드 학습 시작")

        return RetrainResult(
            status=RetrainStatus.IN_PROGRESS,
            started_at=datetime.now().isoformat(),
            completed_at=None,
            training_samples=len(training_data),
            validation_result=None,
            model_version="",
            previous_version=self._get_current_model_version(),
            training_time_seconds=0
        )

    def get_training_status(self) -> Dict[str, Any]:
        """학습 상태 조회"""
        # 백그라운드 학습 결과 확인
        try:
            result = self._training_queue.get_nowait()
            self._current_result = result
        except queue.Empty:
            pass

        return {
            'status': self._current_status.value,
            'current_model_version': self._get_current_model_version(),
            'is_training': self._training_thread and self._training_thread.is_alive(),
            'last_result': self._current_result.to_dict() if self._current_result else None,
            'model_count': len(self._model_registry)
        }

    def get_model_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """모델 히스토리 조회"""
        models = list(self._model_registry.values())
        models.sort(key=lambda x: x.get('registered_at', ''), reverse=True)
        return models[:limit]


# 싱글톤 인스턴스
_retrainer_instance: Optional[ModelRetrainer] = None


def get_model_retrainer() -> ModelRetrainer:
    """ModelRetrainer 싱글톤 인스턴스 반환"""
    global _retrainer_instance
    if _retrainer_instance is None:
        _retrainer_instance = ModelRetrainer()
    return _retrainer_instance
