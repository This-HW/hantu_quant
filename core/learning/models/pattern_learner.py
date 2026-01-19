"""
Phase 4: AI 학습 시스템 - 패턴 학습 엔진

머신러닝을 활용한 주식 패턴 학습 및 예측 시스템
"""

import numpy as np
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass, asdict
from pathlib import Path

from core.utils.log_utils import get_logger

# Optional sklearn imports
try:
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.neural_network import MLPClassifier
    from sklearn.model_selection import train_test_split, cross_val_score, GridSearchCV
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import roc_auc_score
    import joblib

    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

logger = get_logger(__name__)


@dataclass
class PatternFeatures:
    """패턴 피처 데이터 클래스"""

    features: np.ndarray  # 17개 피처 (기울기 9개 + 볼륨 8개)
    feature_names: List[str]  # 피처 이름들
    stock_code: str
    date: str
    sector: str

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "features": self.features.tolist(),
            "feature_names": self.feature_names,
            "stock_code": self.stock_code,
            "date": self.date,
            "sector": self.sector,
        }


@dataclass
class PatternPrediction:
    """패턴 예측 결과 클래스"""

    stock_code: str
    prediction_date: str

    # 예측 결과
    success_probability: float  # 성공 확률 (0-1)
    predicted_class: int  # 0: 실패, 1: 성공
    confidence_score: float  # 신뢰도 점수

    # 예측에 사용된 피처 중요도
    feature_importance: Dict[str, float]

    # 모델 정보
    model_name: str
    model_version: str

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return asdict(self)


class PatternLearner:
    """패턴 학습 엔진"""

    def __init__(self, model_save_dir: str = "data/models"):
        """초기화

        Args:
            model_save_dir: 모델 저장 디렉토리
        """
        self._logger = logger
        self._model_save_dir = Path(model_save_dir)
        self._model_save_dir.mkdir(parents=True, exist_ok=True)

        # 지원 모델들
        self._models = {}
        self._scalers = {}
        self._label_encoders = {}

        if SKLEARN_AVAILABLE:
            self._initialize_models()
        else:
            self._logger.warning("sklearn이 설치되지 않아 제한된 기능만 사용 가능")

        self._logger.info("PatternLearner 초기화 완료")

    def _initialize_models(self):
        """머신러닝 모델들 초기화"""
        try:
            # Random Forest Classifier
            self._models["random_forest"] = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                min_samples_split=5,
                min_samples_leaf=2,
                random_state=42,
                n_jobs=-1,
            )

            # Gradient Boosting Classifier
            self._models["gradient_boosting"] = GradientBoostingClassifier(
                n_estimators=100, learning_rate=0.1, max_depth=6, random_state=42
            )

            # Logistic Regression
            self._models["logistic_regression"] = LogisticRegression(
                max_iter=1000, random_state=42
            )

            # Multi-Layer Perceptron
            self._models["mlp"] = MLPClassifier(
                hidden_layer_sizes=(50, 25),
                max_iter=500,
                random_state=42,
                early_stopping=True,
                validation_fraction=0.1,
            )

            # 각 모델별 스케일러 초기화
            for model_name in self._models.keys():
                self._scalers[model_name] = StandardScaler()

            self._logger.info(f"머신러닝 모델 초기화 완료: {len(self._models)}개 모델")

        except Exception as e:
            self._logger.error(f"모델 초기화 오류: {e}", exc_info=True)

    def train_models(
        self,
        training_data: List[PatternFeatures],
        labels: List[int],
        test_size: float = 0.2,
    ) -> Dict[str, Any]:
        """모델 학습

        Args:
            training_data: 학습용 패턴 피처 데이터
            labels: 성공/실패 라벨 (0: 실패, 1: 성공)
            test_size: 테스트 데이터 비율

        Returns:
            Dict[str, Any]: 학습 결과
        """
        try:
            if not SKLEARN_AVAILABLE:
                self._logger.error("sklearn이 설치되지 않아 모델 학습 불가")
                return {}

            self._logger.info(f"모델 학습 시작: {len(training_data)}개 학습 데이터")

            # 데이터 준비
            X = np.array([data.features for data in training_data])
            y = np.array(labels)
            feature_names = training_data[0].feature_names if training_data else []

            # 데이터 검증
            if len(X) == 0 or len(y) == 0:
                self._logger.error("학습 데이터가 없습니다")
                return {}

            if len(X) != len(y):
                self._logger.error("피처와 라벨 수가 일치하지 않습니다")
                return {}

            # 학습/테스트 분할
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=test_size, random_state=42, stratify=y
            )

            training_results = {}

            # 각 모델별 학습
            for model_name, model in self._models.items():
                try:
                    self._logger.info(f"{model_name} 모델 학습 시작...")

                    # 데이터 스케일링
                    scaler = self._scalers[model_name]
                    X_train_scaled = scaler.fit_transform(X_train)
                    X_test_scaled = scaler.transform(X_test)

                    # 모델 학습
                    model.fit(X_train_scaled, y_train)

                    # 예측 및 평가
                    model.predict(X_test_scaled)
                    y_pred_proba = model.predict_proba(X_test_scaled)[:, 1]

                    # 성능 지표 계산
                    accuracy = model.score(X_test_scaled, y_test)
                    auc_score = (
                        roc_auc_score(y_test, y_pred_proba)
                        if len(set(y_test)) > 1
                        else 0.5
                    )

                    # 교차 검증
                    cv_scores = cross_val_score(model, X_train_scaled, y_train, cv=5)

                    # 피처 중요도 (가능한 경우)
                    feature_importance = {}
                    if hasattr(model, "feature_importances_"):
                        importance_scores = model.feature_importances_
                        feature_importance = dict(zip(feature_names, importance_scores))
                    elif hasattr(model, "coef_"):
                        # 로지스틱 회귀의 경우 계수의 절댓값 사용
                        importance_scores = abs(model.coef_[0])
                        feature_importance = dict(zip(feature_names, importance_scores))

                    # 결과 저장
                    training_results[model_name] = {
                        "accuracy": float(accuracy),
                        "auc_score": float(auc_score),
                        "cv_mean": float(cv_scores.mean()),
                        "cv_std": float(cv_scores.std()),
                        "feature_importance": feature_importance,
                        "training_samples": len(X_train),
                        "test_samples": len(X_test),
                        "positive_ratio": float(np.mean(y_train)),
                    }

                    self._logger.info(
                        f"{model_name} 학습 완료 - 정확도: {accuracy:.3f}, AUC: {auc_score:.3f}"
                    )

                except Exception as e:
                    self._logger.error(f"{model_name} 학습 오류: {e}", exc_info=True)
                    training_results[model_name] = {"error": str(e)}

            # 모델 저장
            self._save_models()

            # 전체 결과
            overall_results = {
                "training_completed": True,
                "total_samples": len(X),
                "training_samples": len(X_train),
                "test_samples": len(X_test),
                "feature_count": X.shape[1],
                "positive_ratio": float(np.mean(y)),
                "models": training_results,
                "timestamp": datetime.now().isoformat(),
            }

            self._logger.info(f"모델 학습 완료: {len(training_results)}개 모델")
            return overall_results

        except Exception as e:
            self._logger.error(f"모델 학습 오류: {e}", exc_info=True)
            return {"error": str(e)}

    def predict_pattern(
        self, features: PatternFeatures, model_name: str = "random_forest"
    ) -> Optional[PatternPrediction]:
        """패턴 예측

        Args:
            features: 예측할 피처 데이터
            model_name: 사용할 모델명

        Returns:
            Optional[PatternPrediction]: 예측 결과
        """
        try:
            if not SKLEARN_AVAILABLE:
                self._logger.error("sklearn이 설치되지 않아 예측 불가")
                return None

            if model_name not in self._models:
                self._logger.error(f"존재하지 않는 모델: {model_name}", exc_info=True)
                return None

            model = self._models[model_name]
            scaler = self._scalers[model_name]

            # 피처 준비
            X = features.features.reshape(1, -1)
            X_scaled = scaler.transform(X)

            # 예측 실행
            predicted_class = model.predict(X_scaled)[0]
            success_probability = model.predict_proba(X_scaled)[0][1]

            # 신뢰도 계산 (확률값 기반)
            confidence_score = max(success_probability, 1 - success_probability)

            # 피처 중요도
            feature_importance = {}
            if hasattr(model, "feature_importances_"):
                importance_scores = model.feature_importances_
                feature_importance = dict(
                    zip(features.feature_names, importance_scores)
                )

            prediction = PatternPrediction(
                stock_code=features.stock_code,
                prediction_date=datetime.now().strftime("%Y-%m-%d"),
                success_probability=float(success_probability),
                predicted_class=int(predicted_class),
                confidence_score=float(confidence_score),
                feature_importance=feature_importance,
                model_name=model_name,
                model_version="1.0",
            )

            self._logger.debug(
                f"패턴 예측 완료: {features.stock_code} - 성공확률 {success_probability:.3f}"
            )
            return prediction

        except Exception as e:
            self._logger.error(f"패턴 예측 오류: {e}", exc_info=True)
            return None

    def predict_batch(
        self, features_list: List[PatternFeatures], model_name: str = "random_forest"
    ) -> List[PatternPrediction]:
        """배치 예측

        Args:
            features_list: 예측할 피처 데이터 리스트
            model_name: 사용할 모델명

        Returns:
            List[PatternPrediction]: 예측 결과 리스트
        """
        try:
            predictions = []

            for features in features_list:
                prediction = self.predict_pattern(features, model_name)
                if prediction:
                    predictions.append(prediction)

            self._logger.info(
                f"배치 예측 완료: {len(predictions)}/{len(features_list)}개"
            )
            return predictions

        except Exception as e:
            self._logger.error(f"배치 예측 오류: {e}", exc_info=True)
            return []

    def optimize_hyperparameters(
        self,
        training_data: List[PatternFeatures],
        labels: List[int],
        model_name: str = "random_forest",
    ) -> Dict[str, Any]:
        """하이퍼파라미터 최적화

        Args:
            training_data: 학습 데이터
            labels: 라벨 데이터
            model_name: 최적화할 모델명

        Returns:
            Dict[str, Any]: 최적화 결과
        """
        try:
            if not SKLEARN_AVAILABLE:
                self._logger.error("sklearn이 설치되지 않아 최적화 불가")
                return {}

            self._logger.info(f"{model_name} 하이퍼파라미터 최적화 시작...")

            X = np.array([data.features for data in training_data])
            y = np.array(labels)

            # 데이터 스케일링
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)

            # 모델별 파라미터 그리드
            param_grids = {
                "random_forest": {
                    "n_estimators": [50, 100, 200],
                    "max_depth": [5, 10, 15],
                    "min_samples_split": [2, 5, 10],
                },
                "gradient_boosting": {
                    "n_estimators": [50, 100, 150],
                    "learning_rate": [0.05, 0.1, 0.2],
                    "max_depth": [3, 6, 9],
                },
                "logistic_regression": {
                    "C": [0.1, 1.0, 10.0],
                    "penalty": ["l2", "l1"],
                    "solver": ["liblinear", "saga"],
                },
            }

            if model_name not in param_grids:
                self._logger.error(f"지원하지 않는 모델: {model_name}", exc_info=True)
                return {}

            # 그리드 서치 실행
            base_model = self._models[model_name]
            grid_search = GridSearchCV(
                base_model,
                param_grids[model_name],
                cv=5,
                scoring="roc_auc",
                n_jobs=-1,
                verbose=1,
            )

            grid_search.fit(X_scaled, y)

            # 최적 모델로 업데이트
            self._models[model_name] = grid_search.best_estimator_

            optimization_results = {
                "model_name": model_name,
                "best_params": grid_search.best_params_,
                "best_score": float(grid_search.best_score_),
                "optimization_completed": True,
                "timestamp": datetime.now().isoformat(),
            }

            self._logger.info(
                f"{model_name} 최적화 완료 - 최고 점수: {grid_search.best_score_:.3f}"
            )
            return optimization_results

        except Exception as e:
            self._logger.error(f"하이퍼파라미터 최적화 오류: {e}", exc_info=True)
            return {"error": str(e)}

    def _save_models(self):
        """모델 저장"""
        try:
            if not SKLEARN_AVAILABLE:
                return

            for model_name, model in self._models.items():
                # 모델 저장
                model_path = self._model_save_dir / f"{model_name}_model.pkl"
                joblib.dump(model, model_path)

                # 스케일러 저장
                scaler_path = self._model_save_dir / f"{model_name}_scaler.pkl"
                joblib.dump(self._scalers[model_name], scaler_path)

            self._logger.info(f"모델 저장 완료: {len(self._models)}개")

        except Exception as e:
            self._logger.error(f"모델 저장 오류: {e}", exc_info=True)

    def load_models(self):
        """저장된 모델 로드"""
        try:
            if not SKLEARN_AVAILABLE:
                return False

            loaded_count = 0

            for model_name in list(self._models.keys()):
                model_path = self._model_save_dir / f"{model_name}_model.pkl"
                scaler_path = self._model_save_dir / f"{model_name}_scaler.pkl"

                if model_path.exists() and scaler_path.exists():
                    self._models[model_name] = joblib.load(model_path)
                    self._scalers[model_name] = joblib.load(scaler_path)
                    loaded_count += 1

            if loaded_count > 0:
                self._logger.info(f"모델 로드 완료: {loaded_count}개")
                return True
            else:
                self._logger.warning("로드할 모델이 없습니다")
                return False

        except Exception as e:
            self._logger.error(f"모델 로드 오류: {e}", exc_info=True)
            return False

    def get_model_performance(self) -> Dict[str, Any]:
        """모델 성능 정보 반환"""
        try:
            performance_info = {
                "available_models": list(self._models.keys()),
                "sklearn_available": SKLEARN_AVAILABLE,
                "models_trained": len(
                    [m for m in self._models.values() if hasattr(m, "n_features_in_")]
                ),
                "model_save_dir": str(self._model_save_dir),
            }

            return performance_info

        except Exception as e:
            self._logger.error(f"모델 성능 정보 조회 오류: {e}", exc_info=True)
            return {}
