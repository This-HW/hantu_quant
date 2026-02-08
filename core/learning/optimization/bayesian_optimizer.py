"""
베이지안 최적화기

베이지안 최적화를 사용하여 전략 파라미터를 효율적으로 최적화하는 시스템
"""

import numpy as np
import json
import os
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any, Callable
from dataclasses import dataclass, asdict
import warnings

from ...utils.logging import get_logger
from .parameter_manager import (
    ParameterManager,
    ParameterSet,
    ParameterSpace,
    ParameterType,
)

logger = get_logger(__name__)

# sklearn 사용 (없으면 간단한 대안 구현)
try:
    from sklearn.gaussian_process import GaussianProcessRegressor
    from sklearn.gaussian_process.kernels import Matern

    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.warning(
        "scikit-learn이나 scipy가 설치되지 않음. 간단한 베이지안 최적화 구현을 사용합니다."
    )


@dataclass
class BayesianConfig:
    """베이지안 최적화 설정"""

    max_iterations: int = 50  # 최대 반복 수
    initial_samples: int = 10  # 초기 랜덤 샘플 수
    acquisition_function: str = "ei"  # 획득 함수 ("ei", "ucb", "pi")
    xi: float = 0.01  # 탐험-활용 균형 파라미터
    alpha: float = 1e-6  # 가우시안 프로세스 노이즈
    n_restarts_optimizer: int = 5  # 획득 함수 최적화 재시작 수
    convergence_threshold: float = 1e-6  # 수렴 임계값
    early_stopping_iterations: int = 10  # 조기 종료 반복 수


@dataclass
class OptimizationHistory:
    """최적화 기록"""

    iteration: int
    parameters: Dict[str, Any]
    fitness_score: float
    acquisition_value: float
    timestamp: datetime


class BayesianOptimizer:
    """베이지안 최적화기"""

    def __init__(
        self,
        parameter_manager: ParameterManager,
        fitness_function: Callable[[ParameterSet], float],
        config: BayesianConfig = None,
        data_dir: str = "data/bayesian_optimization",
    ):
        """
        초기화

        Args:
            parameter_manager: 파라미터 관리자
            fitness_function: 적합도 평가 함수
            config: 베이지안 최적화 설정
            data_dir: 최적화 데이터 저장 디렉토리
        """
        self._logger = logger
        self._parameter_manager = parameter_manager
        self._fitness_function = fitness_function
        self._config = config or BayesianConfig()
        self._data_dir = data_dir

        # 디렉토리 생성
        os.makedirs(data_dir, exist_ok=True)

        # 최적화 기록
        self._optimization_history = []
        self._X_samples = []  # 샘플 파라미터들
        self._y_samples = []  # 적합도 값들

        # 가우시안 프로세스 모델
        if SKLEARN_AVAILABLE:
            self._gp_model = GaussianProcessRegressor(
                kernel=Matern(length_scale=1.0, nu=2.5),
                alpha=self._config.alpha,
                n_restarts_optimizer=self._config.n_restarts_optimizer,
                random_state=42,
            )
        else:
            self._gp_model = None

        # 최적화 상태
        self._best_parameters = None
        self._best_fitness = float("-inf")
        self._current_iteration = 0

        self._logger.info("베이지안 최적화기 초기화 완료")

    def optimize(
        self, strategy_name: str, target_fitness: float = None
    ) -> Dict[str, Any]:
        """
        파라미터 최적화 수행

        Args:
            strategy_name: 최적화할 전략명
            target_fitness: 목표 적합도 (달성시 조기 종료)

        Returns:
            Dict: 최적화 결과
        """
        start_time = datetime.now()
        self._logger.info(f"베이지안 최적화 시작: {strategy_name}")

        # 파라미터 공간 가져오기
        param_spaces = self._parameter_manager.get_all_parameter_spaces(strategy_name)
        if not param_spaces:
            raise ValueError(
                f"전략 '{strategy_name}'의 파라미터 공간을 찾을 수 없습니다"
            )

        # 초기화
        self._optimization_history = []
        self._X_samples = []
        self._y_samples = []
        self._best_parameters = None
        self._best_fitness = float("-inf")
        self._current_iteration = 0

        # 파라미터 공간을 수치형으로 변환
        param_bounds, param_info = self._prepare_parameter_space(param_spaces)

        # 초기 샘플링
        self._initial_sampling(strategy_name, param_bounds, param_info)

        convergence_counter = 0
        convergence_achieved = False

        # 베이지안 최적화 반복
        for iteration in range(
            self._config.initial_samples, self._config.max_iterations
        ):
            self._current_iteration = iteration

            # 가우시안 프로세스 모델 학습
            if not self._train_gp_model():
                self._logger.warning(
                    "가우시안 프로세스 모델 학습 실패, 랜덤 샘플링으로 대체"
                )
                next_params = self._random_sampling(
                    strategy_name, param_bounds, param_info
                )
            else:
                # 획득 함수로 다음 샘플 찾기
                next_params = self._acquire_next_sample(param_bounds, param_info)

            if next_params is None:
                self._logger.warning("다음 샘플 획득 실패, 랜덤 샘플링으로 대체")
                next_params = self._random_sampling(
                    strategy_name, param_bounds, param_info
                )

            # 파라미터 세트 생성 및 평가
            param_set = self._parameter_manager.create_parameter_set(
                strategy_name, next_params
            )
            if param_set is None:
                self._logger.warning("파라미터 세트 생성 실패, 건너뜀")
                continue

            try:
                fitness_score = self._fitness_function(param_set)
                param_set.fitness_score = fitness_score
            except Exception as e:
                self._logger.error(f"적합도 평가 실패: {e}", exc_info=True)
                fitness_score = 0.0
                param_set.fitness_score = fitness_score

            # 샘플 추가
            param_vector = self._params_to_vector(next_params, param_info)
            self._X_samples.append(param_vector)
            self._y_samples.append(fitness_score)

            # 최고 성능 업데이트
            if fitness_score > self._best_fitness:
                self._best_fitness = fitness_score
                self._best_parameters = param_set
                self._parameter_manager.add_parameter_set(param_set)
                convergence_counter = 0
            else:
                convergence_counter += 1

            # 기록 저장
            history_entry = OptimizationHistory(
                iteration=iteration,
                parameters=next_params,
                fitness_score=fitness_score,
                acquisition_value=0.0,  # 실제로는 획득 함수 값
                timestamp=datetime.now(),
            )
            self._optimization_history.append(history_entry)

            self._logger.info(
                f"반복 {iteration}: 적합도={fitness_score:.6f}, 최고={self._best_fitness:.6f}"
            )

            # 목표 적합도 달성 체크
            if target_fitness and fitness_score >= target_fitness:
                self._logger.info(
                    f"목표 적합도 달성: {fitness_score:.6f} >= {target_fitness:.6f}"
                )
                convergence_achieved = True
                break

            # 조기 수렴 체크
            if convergence_counter >= self._config.early_stopping_iterations:
                self._logger.info(
                    f"조기 수렴 감지: {convergence_counter}회 반복 동안 개선 없음"
                )
                convergence_achieved = True
                break

        # 최적화 완료
        end_time = datetime.now()
        optimization_time = (end_time - start_time).total_seconds()

        # 결과 생성
        result = {
            "strategy_name": strategy_name,
            "best_parameters": (
                asdict(self._best_parameters) if self._best_parameters else None
            ),
            "best_fitness": self._best_fitness,
            "total_iterations": self._current_iteration + 1,
            "convergence_achieved": convergence_achieved,
            "optimization_time": optimization_time,
            "optimization_history": [asdict(h) for h in self._optimization_history],
            "config": asdict(self._config),
        }

        # 결과 저장
        self._save_optimization_results(result, strategy_name)

        self._logger.info(
            f"베이지안 최적화 완료: {optimization_time:.2f}초, 최고 적합도: {self._best_fitness:.6f}"
        )
        return result

    def _prepare_parameter_space(
        self, param_spaces: Dict[str, ParameterSpace]
    ) -> Tuple[List[Tuple[float, float]], Dict]:
        """파라미터 공간을 수치형으로 변환"""
        param_bounds = []
        param_info = {"names": [], "types": [], "categories": {}, "original_bounds": {}}

        for param_name, param_space in param_spaces.items():
            param_info["names"].append(param_name)
            param_info["types"].append(param_space.param_type)

            if param_space.param_type == ParameterType.INTEGER:
                param_bounds.append(
                    (
                        float(param_space.min_value or 0),
                        float(param_space.max_value or 100),
                    )
                )
                param_info["original_bounds"][param_name] = (
                    param_space.min_value,
                    param_space.max_value,
                )
            elif param_space.param_type == ParameterType.FLOAT:
                param_bounds.append(
                    (
                        float(param_space.min_value or 0.0),
                        float(param_space.max_value or 1.0),
                    )
                )
                param_info["original_bounds"][param_name] = (
                    param_space.min_value,
                    param_space.max_value,
                )
            elif param_space.param_type == ParameterType.BOOLEAN:
                param_bounds.append((0.0, 1.0))
            elif param_space.param_type == ParameterType.CATEGORICAL:
                param_bounds.append((0.0, float(len(param_space.categories or []) - 1)))
                param_info["categories"][param_name] = param_space.categories or []

        return param_bounds, param_info

    def _initial_sampling(
        self,
        strategy_name: str,
        param_bounds: List[Tuple[float, float]],
        param_info: Dict,
    ):
        """초기 샘플링"""
        self._logger.info(f"초기 샘플링 시작: {self._config.initial_samples}개 샘플")

        for i in range(self._config.initial_samples):
            # 기존 좋은 파라미터가 있다면 일부 포함
            if i == 0:
                best_params = self._parameter_manager.get_best_parameters()
                if best_params:
                    param_vector = self._params_to_vector(
                        best_params.parameters, param_info
                    )
                    fitness_score = best_params.fitness_score or 0.0
                else:
                    # 랜덤 샘플링
                    params = self._random_sampling(
                        strategy_name, param_bounds, param_info
                    )
                    param_set = self._parameter_manager.create_parameter_set(
                        strategy_name, params
                    )
                    if param_set:
                        try:
                            fitness_score = self._fitness_function(param_set)
                            param_set.fitness_score = fitness_score
                        except Exception as e:
                            self._logger.error(
                                f"초기 샘플 평가 실패: {e}", exc_info=True
                            )
                            fitness_score = 0.0
                        param_vector = self._params_to_vector(params, param_info)
                    else:
                        continue
            else:
                # 랜덤 샘플링
                params = self._random_sampling(strategy_name, param_bounds, param_info)
                param_set = self._parameter_manager.create_parameter_set(
                    strategy_name, params
                )
                if param_set:
                    try:
                        fitness_score = self._fitness_function(param_set)
                        param_set.fitness_score = fitness_score
                    except Exception as e:
                        self._logger.error(f"초기 샘플 평가 실패: {e}", exc_info=True)
                        fitness_score = 0.0
                    param_vector = self._params_to_vector(params, param_info)
                else:
                    continue

            # 샘플 추가
            self._X_samples.append(param_vector)
            self._y_samples.append(fitness_score)

            # 최고 성능 업데이트
            if fitness_score > self._best_fitness:
                self._best_fitness = fitness_score
                self._best_parameters = param_set

            self._logger.debug(f"초기 샘플 {i+1}: 적합도={fitness_score:.6f}")

    def _random_sampling(
        self,
        strategy_name: str,
        param_bounds: List[Tuple[float, float]],
        param_info: Dict,
    ) -> Dict[str, Any]:
        """랜덤 샘플링"""
        params = {}

        for i, param_name in enumerate(param_info["names"]):
            param_type = param_info["types"][i]
            min_val, max_val = param_bounds[i]

            if param_type == ParameterType.INTEGER:
                original_min, original_max = param_info["original_bounds"][param_name]
                params[param_name] = np.random.randint(original_min, original_max + 1)
            elif param_type == ParameterType.FLOAT:
                params[param_name] = np.random.uniform(min_val, max_val)
            elif param_type == ParameterType.BOOLEAN:
                params[param_name] = np.random.choice([True, False])
            elif param_type == ParameterType.CATEGORICAL:
                categories = param_info["categories"][param_name]
                params[param_name] = np.random.choice(categories)

        return params

    def _train_gp_model(self) -> bool:
        """가우시안 프로세스 모델 학습"""
        if not SKLEARN_AVAILABLE or len(self._X_samples) < 2:
            return False

        try:
            X = np.array(self._X_samples)
            y = np.array(self._y_samples)

            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                self._gp_model.fit(X, y)

            return True
        except Exception as e:
            self._logger.error(f"가우시안 프로세스 모델 학습 실패: {e}", exc_info=True)
            return False

    def _acquire_next_sample(
        self, param_bounds: List[Tuple[float, float]], param_info: Dict
    ) -> Optional[Dict[str, Any]]:
        """획득 함수로 다음 샘플 찾기"""
        if not SKLEARN_AVAILABLE or self._gp_model is None:
            return None

        try:
            # 간단한 그리드 서치로 획득 함수 최적화
            best_acq_value = float("-inf")
            best_params = None

            # 각 차원마다 몇 개 후보 생성
            n_candidates = 1000
            candidates = []

            for _ in range(n_candidates):
                candidate = []
                for min_val, max_val in param_bounds:
                    candidate.append(np.random.uniform(min_val, max_val))
                candidates.append(candidate)

            candidates = np.array(candidates)

            # 획득 함수 계산
            if self._config.acquisition_function == "ei":
                acquisition_values = self._expected_improvement(candidates)
            elif self._config.acquisition_function == "ucb":
                acquisition_values = self._upper_confidence_bound(candidates)
            else:  # "pi"
                acquisition_values = self._probability_of_improvement(candidates)

            # 최고 획득 함수 값을 가진 후보 선택
            best_idx = np.argmax(acquisition_values)
            best_candidate = candidates[best_idx]

            # 벡터를 파라미터로 변환
            best_params = self._vector_to_params(best_candidate, param_info)

            return best_params

        except Exception as e:
            self._logger.error(f"획득 함수 최적화 실패: {e}", exc_info=True)
            return None

    def _expected_improvement(self, X: np.ndarray) -> np.ndarray:
        """기대 개선 (Expected Improvement) 계산"""
        try:
            mu, std = self._gp_model.predict(X, return_std=True)

            # 현재 최고값
            f_best = np.max(self._y_samples)

            # 기대 개선 계산
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                improvement = mu - f_best - self._config.xi
                Z = improvement / (std + 1e-9)

                # 정규분포 CDF와 PDF 근사
                ei = improvement * self._norm_cdf(Z) + std * self._norm_pdf(Z)

            return ei

        except Exception as e:
            self._logger.error(f"기대 개선 계산 실패: {e}", exc_info=True)
            return np.zeros(len(X))

    def _upper_confidence_bound(self, X: np.ndarray) -> np.ndarray:
        """상한 신뢰 구간 (Upper Confidence Bound) 계산"""
        try:
            mu, std = self._gp_model.predict(X, return_std=True)

            # UCB = 평균 + kappa * 표준편차
            kappa = 2.0  # 탐험-활용 균형 파라미터
            ucb = mu + kappa * std

            return ucb

        except Exception as e:
            self._logger.error(f"상한 신뢰 구간 계산 실패: {e}", exc_info=True)
            return np.zeros(len(X))

    def _probability_of_improvement(self, X: np.ndarray) -> np.ndarray:
        """개선 확률 (Probability of Improvement) 계산"""
        try:
            mu, std = self._gp_model.predict(X, return_std=True)

            # 현재 최고값
            f_best = np.max(self._y_samples)

            # 개선 확률 계산
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                improvement = mu - f_best - self._config.xi
                Z = improvement / (std + 1e-9)
                pi = self._norm_cdf(Z)

            return pi

        except Exception as e:
            self._logger.error(f"개선 확률 계산 실패: {e}", exc_info=True)
            return np.zeros(len(X))

    def _norm_cdf(self, x: np.ndarray) -> np.ndarray:
        """정규분포 누적분포함수 근사"""
        return 0.5 * (1 + np.tanh(np.sqrt(2 / np.pi) * (x + 0.044715 * x**3)))

    def _norm_pdf(self, x: np.ndarray) -> np.ndarray:
        """정규분포 확률밀도함수"""
        return np.exp(-0.5 * x**2) / np.sqrt(2 * np.pi)

    def _params_to_vector(
        self, params: Dict[str, Any], param_info: Dict
    ) -> List[float]:
        """파라미터를 벡터로 변환"""
        vector = []

        for i, param_name in enumerate(param_info["names"]):
            param_type = param_info["types"][i]
            value = params.get(param_name, 0)

            if param_type == ParameterType.INTEGER:
                vector.append(float(value))
            elif param_type == ParameterType.FLOAT:
                vector.append(float(value))
            elif param_type == ParameterType.BOOLEAN:
                vector.append(1.0 if value else 0.0)
            elif param_type == ParameterType.CATEGORICAL:
                categories = param_info["categories"][param_name]
                try:
                    idx = categories.index(value)
                    vector.append(float(idx))
                except ValueError:
                    vector.append(0.0)

        return vector

    def _vector_to_params(self, vector: np.ndarray, param_info: Dict) -> Dict[str, Any]:
        """벡터를 파라미터로 변환"""
        params = {}

        for i, param_name in enumerate(param_info["names"]):
            param_type = param_info["types"][i]
            value = vector[i]

            if param_type == ParameterType.INTEGER:
                original_min, original_max = param_info["original_bounds"][param_name]
                params[param_name] = int(
                    np.clip(np.round(value), original_min, original_max)
                )
            elif param_type == ParameterType.FLOAT:
                params[param_name] = float(value)
            elif param_type == ParameterType.BOOLEAN:
                params[param_name] = value >= 0.5
            elif param_type == ParameterType.CATEGORICAL:
                categories = param_info["categories"][param_name]
                idx = int(np.clip(np.round(value), 0, len(categories) - 1))
                params[param_name] = categories[idx]

        return params

    def get_optimization_summary(self) -> Dict[str, Any]:
        """최적화 요약 정보"""
        if not self._optimization_history:
            return {"message": "최적화 기록이 없습니다"}

        fitness_history = [h.fitness_score for h in self._optimization_history]

        summary = {
            "total_iterations": len(self._optimization_history),
            "best_fitness": self._best_fitness,
            "average_fitness": np.mean(fitness_history),
            "fitness_improvement": (
                self._best_fitness - fitness_history[0]
                if len(fitness_history) > 1
                else 0
            ),
            "best_parameters": (
                asdict(self._best_parameters) if self._best_parameters else None
            ),
            "sklearn_available": SKLEARN_AVAILABLE,
            "config": asdict(self._config),
        }

        return summary

    def _save_optimization_results(self, result: Dict[str, Any], strategy_name: str):
        """최적화 결과 저장"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"bayesian_optimization_{strategy_name}_{timestamp}.json"
            filepath = os.path.join(self._data_dir, filename)

            # datetime 객체들을 문자열로 변환
            result_copy = result.copy()
            for i, history in enumerate(result_copy["optimization_history"]):
                if "timestamp" in history and hasattr(
                    history["timestamp"], "isoformat"
                ):
                    result_copy["optimization_history"][i]["timestamp"] = history[
                        "timestamp"
                    ].isoformat()

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(result_copy, f, ensure_ascii=False, indent=2, default=str)

            self._logger.info(f"베이지안 최적화 결과 저장: {filepath}")

        except Exception as e:
            self._logger.error(f"최적화 결과 저장 실패: {e}", exc_info=True)


# 전역 인스턴스
_bayesian_optimizer = None


def get_bayesian_optimizer(
    parameter_manager: ParameterManager,
    fitness_function: Callable[[ParameterSet], float],
) -> BayesianOptimizer:
    """베이지안 최적화기 싱글톤 인스턴스 반환"""
    global _bayesian_optimizer
    if _bayesian_optimizer is None:
        _bayesian_optimizer = BayesianOptimizer(parameter_manager, fitness_function)
    return _bayesian_optimizer
