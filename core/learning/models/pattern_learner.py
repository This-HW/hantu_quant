"""
패턴 학습 엔진

과거 성과 데이터에서 성공/실패 패턴을 추출하고
머신러닝 모델을 훈련하여 예측 정확도를 향상시키는 시스템
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.neural_network import MLPClassifier
from sklearn.model_selection import train_test_split, cross_val_score, GridSearchCV
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
import joblib
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, asdict

from ...utils.logging import get_logger
from ..features.feature_selector import FeatureExtractor
from ..analysis.daily_performance import DailyPerformanceAnalyzer, PerformanceMetrics

logger = get_logger(__name__)

@dataclass
class LearningConfig:
    """학습 설정"""
    target_accuracy: float = 0.9           # 목표 정확도
    min_samples: int = 100                 # 최소 학습 샘플 수
    test_size: float = 0.2                 # 테스트 데이터 비율
    cv_folds: int = 5                      # 교차 검증 폴드 수
    feature_selection: bool = True         # 피처 선택 사용 여부
    ensemble_voting: str = 'soft'          # 앙상블 투표 방식
    auto_retrain: bool = True              # 자동 재훈련 여부
    retrain_threshold: float = 0.05        # 재훈련 임계값 (정확도 하락)
    save_models: bool = True               # 모델 저장 여부

@dataclass
class PatternModel:
    """패턴 모델 정보"""
    model_id: str
    model_type: str
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    feature_importance: Dict[str, float]
    training_date: datetime
    sample_count: int
    is_active: bool

class PatternLearner:
    """패턴 학습기"""
    
    def __init__(self, feature_extractor: FeatureExtractor,
                 performance_analyzer: DailyPerformanceAnalyzer,
                 config: LearningConfig = None,
                 model_dir: str = "data/models"):
        """
        초기화
        
        Args:
            feature_extractor: 피처 추출기
            performance_analyzer: 성과 분석기
            config: 학습 설정
            model_dir: 모델 저장 디렉토리
        """
        self._logger = logger
        self._feature_extractor = feature_extractor
        self._performance_analyzer = performance_analyzer
        self._config = config or LearningConfig()
        self._model_dir = model_dir
        
        # 디렉토리 생성
        os.makedirs(model_dir, exist_ok=True)
        
        # 모델 초기화
        self._models = {}
        self._scalers = {}
        self._feature_names = []
        self._target_encoder = LabelEncoder()
        
        # 모델 정의
        self._model_configs = {
            'random_forest': {
                'model': RandomForestClassifier,
                'params': {
                    'n_estimators': [100, 200, 300],
                    'max_depth': [10, 20, None],
                    'min_samples_split': [2, 5, 10],
                    'min_samples_leaf': [1, 2, 4]
                }
            },
            'gradient_boosting': {
                'model': GradientBoostingClassifier,
                'params': {
                    'n_estimators': [100, 200],
                    'learning_rate': [0.05, 0.1, 0.15],
                    'max_depth': [3, 5, 7]
                }
            },
            'logistic_regression': {
                'model': LogisticRegression,
                'params': {
                    'C': [0.1, 1.0, 10.0],
                    'solver': ['liblinear', 'lbfgs'],
                    'max_iter': [1000]
                }
            },
            'neural_network': {
                'model': MLPClassifier,
                'params': {
                    'hidden_layer_sizes': [(50,), (100,), (50, 25)],
                    'activation': ['relu', 'tanh'],
                    'learning_rate': ['constant', 'adaptive'],
                    'max_iter': [1000]
                }
            }
        }
        
        # 모델 성과 기록
        self._model_performance = []
        
        self._logger.info("패턴 학습기 초기화 완료")
    
    def prepare_training_data(self, days: int = 90) -> Tuple[np.ndarray, np.ndarray]:
        """학습 데이터 준비"""
        self._logger.info(f"학습 데이터 준비 시작 ({days}일간)")
        
        # 성과 데이터 가져오기
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        performance_metrics = [
            m for m in self._performance_analyzer._performance_history
            if start_date <= m.date <= end_date
        ]
        
        if len(performance_metrics) < self._config.min_samples:
            raise ValueError(f"학습에 필요한 최소 샘플 수 부족: {len(performance_metrics)} < {self._config.min_samples}")
        
        # 피처와 타겟 준비
        features_list = []
        targets = []
        
        for metric in performance_metrics:
            try:
                # 피처 추출 (종목 코드 기반)
                features = self._extract_features_for_stock(metric.stock_code, metric.date)
                if features is not None:
                    features_list.append(features)
                    
                    # 타겟 라벨: 성공(1) vs 실패(0)
                    # 성공 기준: 수익률 > 3% 그리고 예측 정확도 > 0.7
                    is_success = (metric.return_rate > 0.03 and 
                                metric.prediction_accuracy > 0.7)
                    targets.append('success' if is_success else 'failure')
                    
            except Exception as e:
                self._logger.warning(f"피처 추출 실패 {metric.stock_code}: {e}")
                continue
        
        if len(features_list) < self._config.min_samples:
            raise ValueError(f"유효한 학습 샘플 부족: {len(features_list)} < {self._config.min_samples}")
        
        # numpy 배열로 변환
        X = np.array(features_list)
        y = np.array(targets)
        
        # 피처 이름 저장
        if not self._feature_names:
            self._feature_names = [f"feature_{i}" for i in range(X.shape[1])]
        
        # 타겟 인코딩
        y_encoded = self._target_encoder.fit_transform(y)
        
        self._logger.info(f"학습 데이터 준비 완료: {X.shape[0]}개 샘플, {X.shape[1]}개 피처")
        return X, y_encoded
    
    def _extract_features_for_stock(self, stock_code: str, date: datetime) -> Optional[np.ndarray]:
        """종목별 피처 추출"""
        try:
            # 모의 OHLCV 데이터 생성 (실제로는 API에서 가져와야 함)
            mock_ohlcv = self._generate_mock_ohlcv(stock_code, date)
            
            # 기존 피처 추출기 활용
            slope_features = self._feature_extractor._calculate_slope_features(mock_ohlcv)
            volume_features = self._feature_extractor._calculate_volume_features(mock_ohlcv)
            
            # 피처 결합
            all_features = []
            all_features.extend(slope_features.values())
            all_features.extend(volume_features.values())
            
            return np.array(all_features)
            
        except Exception as e:
            self._logger.error(f"피처 추출 실패 {stock_code}: {e}")
            return None
    
    def _generate_mock_ohlcv(self, stock_code: str, date: datetime) -> pd.DataFrame:
        """모의 OHLCV 데이터 생성 (실제로는 API에서 가져와야 함)"""
        # 20일간 데이터 생성
        dates = pd.date_range(end=date, periods=20, freq='D')
        
        # 주식별 기본 가격 설정
        base_prices = {
            '005930': 65000,  # 삼성전자
            '000660': 120000, # SK하이닉스
            '035420': 180000, # NAVER
        }
        
        base_price = base_prices.get(stock_code, 50000)
        
        # 랜덤워크로 가격 생성
        np.random.seed(hash(stock_code + str(date.date())) % 2**32)
        returns = np.random.normal(0, 0.02, len(dates))  # 일일 2% 변동성
        
        prices = [base_price]
        for ret in returns[1:]:
            prices.append(prices[-1] * (1 + ret))
        
        # OHLCV 데이터 생성
        ohlcv_data = []
        for i, (dt, close) in enumerate(zip(dates, prices)):
            high = close * (1 + abs(np.random.normal(0, 0.01)))
            low = close * (1 - abs(np.random.normal(0, 0.01)))
            open_price = prices[i-1] if i > 0 else close
            volume = np.random.randint(100000, 1000000)
            
            ohlcv_data.append({
                'Date': dt,
                'Open': open_price,
                'High': high,
                'Low': low,
                'Close': close,
                'Volume': volume
            })
        
        return pd.DataFrame(ohlcv_data)
    
    def train_models(self, X: np.ndarray, y: np.ndarray) -> Dict[str, PatternModel]:
        """모델 훈련"""
        self._logger.info("모델 훈련 시작")
        
        # 데이터 분할
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=self._config.test_size, random_state=42, stratify=y
        )
        
        # 피처 스케일링
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        
        self._scalers['main'] = scaler
        
        trained_models = {}
        
        for model_name, model_config in self._model_configs.items():
            self._logger.info(f"{model_name} 모델 훈련 중...")
            
            try:
                # 모델 생성
                model_class = model_config['model']
                
                # 그리드 서치로 최적 하이퍼파라미터 찾기
                grid_search = GridSearchCV(
                    model_class(random_state=42),
                    model_config['params'],
                    cv=self._config.cv_folds,
                    scoring='accuracy',
                    n_jobs=-1
                )
                
                # 모델에 따라 다른 데이터 사용
                if model_name in ['logistic_regression', 'neural_network']:
                    grid_search.fit(X_train_scaled, y_train)
                    X_test_final = X_test_scaled
                else:
                    grid_search.fit(X_train, y_train)
                    X_test_final = X_test
                
                # 최적 모델로 예측
                best_model = grid_search.best_estimator_
                y_pred = best_model.predict(X_test_final)
                
                # 성과 지표 계산
                accuracy = accuracy_score(y_test, y_pred)
                precision = precision_score(y_test, y_pred, average='weighted')
                recall = recall_score(y_test, y_pred, average='weighted')
                f1 = f1_score(y_test, y_pred, average='weighted')
                
                # 피처 중요도
                feature_importance = {}
                if hasattr(best_model, 'feature_importances_'):
                    for i, importance in enumerate(best_model.feature_importances_):
                        feature_importance[f"feature_{i}"] = float(importance)
                elif hasattr(best_model, 'coef_'):
                    for i, coef in enumerate(best_model.coef_[0]):
                        feature_importance[f"feature_{i}"] = float(abs(coef))
                
                # 모델 정보 생성
                pattern_model = PatternModel(
                    model_id=f"{model_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    model_type=model_name,
                    accuracy=accuracy,
                    precision=precision,
                    recall=recall,
                    f1_score=f1,
                    feature_importance=feature_importance,
                    training_date=datetime.now(),
                    sample_count=len(X_train),
                    is_active=accuracy >= self._config.target_accuracy * 0.8  # 80% 이상이면 활성화
                )
                
                # 모델 저장
                self._models[model_name] = best_model
                trained_models[model_name] = pattern_model
                
                # 파일로 저장
                if self._config.save_models:
                    model_path = os.path.join(self._model_dir, f"{model_name}_model.pkl")
                    joblib.dump(best_model, model_path)
                
                self._logger.info(f"{model_name} 훈련 완료 - 정확도: {accuracy:.3f}")
                
            except Exception as e:
                self._logger.error(f"{model_name} 훈련 실패: {e}")
                continue
        
        # 모델 성과 기록
        self._model_performance.append({
            'timestamp': datetime.now(),
            'models': trained_models
        })
        
        # 메타데이터 저장
        self._save_metadata(trained_models)
        
        self._logger.info(f"모델 훈련 완료: {len(trained_models)}개 모델")
        return trained_models
    
    def _save_metadata(self, models: Dict[str, PatternModel]):
        """모델 메타데이터 저장"""
        metadata = {
            'timestamp': datetime.now().isoformat(),
            'config': asdict(self._config),
            'models': {name: asdict(model) for name, model in models.items()},
            'feature_names': self._feature_names
        }
        
        metadata_path = os.path.join(self._model_dir, "models_metadata.json")
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2, default=str)
    
    def load_models(self) -> bool:
        """저장된 모델 로드"""
        try:
            metadata_path = os.path.join(self._model_dir, "models_metadata.json")
            if not os.path.exists(metadata_path):
                return False
            
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            self._feature_names = metadata.get('feature_names', [])
            
            # 모델 파일 로드
            for model_name in metadata['models'].keys():
                model_path = os.path.join(self._model_dir, f"{model_name}_model.pkl")
                if os.path.exists(model_path):
                    self._models[model_name] = joblib.load(model_path)
            
            # 스케일러 로드
            scaler_path = os.path.join(self._model_dir, "scaler.pkl")
            if os.path.exists(scaler_path):
                self._scalers['main'] = joblib.load(scaler_path)
            
            self._logger.info(f"저장된 모델 로드 완료: {len(self._models)}개")
            return True
            
        except Exception as e:
            self._logger.error(f"모델 로드 실패: {e}")
            return False
    
    def predict_pattern(self, stock_code: str, date: datetime = None) -> Dict[str, float]:
        """패턴 기반 예측"""
        if date is None:
            date = datetime.now()
        
        if not self._models:
            raise ValueError("훈련된 모델이 없습니다. 먼저 train_models()를 실행하세요.")
        
        # 피처 추출
        features = self._extract_features_for_stock(stock_code, date)
        if features is None:
            return {'success_probability': 0.5, 'confidence': 0.0}
        
        # 예측 수행
        predictions = {}
        
        for model_name, model in self._models.items():
            try:
                # 스케일링 (필요한 경우)
                if model_name in ['logistic_regression', 'neural_network'] and 'main' in self._scalers:
                    features_scaled = self._scalers['main'].transform(features.reshape(1, -1))
                    features_input = features_scaled
                else:
                    features_input = features.reshape(1, -1)
                
                # 예측 확률
                if hasattr(model, 'predict_proba'):
                    proba = model.predict_proba(features_input)[0]
                    # success 클래스의 확률 (클래스 1)
                    success_prob = proba[1] if len(proba) > 1 else proba[0]
                else:
                    # 분류 결과만 있는 경우
                    pred = model.predict(features_input)[0]
                    success_prob = 1.0 if pred == 1 else 0.0
                
                predictions[model_name] = success_prob
                
            except Exception as e:
                self._logger.warning(f"{model_name} 예측 실패: {e}")
                continue
        
        if not predictions:
            return {'success_probability': 0.5, 'confidence': 0.0}
        
        # 앙상블 예측 (평균)
        ensemble_prob = np.mean(list(predictions.values()))
        
        # 신뢰도 계산 (예측값들의 표준편차가 낮을수록 높은 신뢰도)
        confidence = 1.0 - np.std(list(predictions.values()))
        confidence = max(0.0, min(1.0, confidence))
        
        return {
            'success_probability': float(ensemble_prob),
            'confidence': float(confidence),
            'individual_predictions': predictions
        }
    
    def evaluate_models(self, X: np.ndarray, y: np.ndarray) -> Dict[str, Dict[str, float]]:
        """모델 평가"""
        evaluation_results = {}
        
        for model_name, model in self._models.items():
            try:
                # 스케일링 (필요한 경우)
                if model_name in ['logistic_regression', 'neural_network'] and 'main' in self._scalers:
                    X_scaled = self._scalers['main'].transform(X)
                    X_input = X_scaled
                else:
                    X_input = X
                
                # 교차 검증
                cv_scores = cross_val_score(model, X_input, y, cv=self._config.cv_folds)
                
                # 예측
                y_pred = model.predict(X_input)
                
                evaluation_results[model_name] = {
                    'accuracy': accuracy_score(y, y_pred),
                    'precision': precision_score(y, y_pred, average='weighted'),
                    'recall': recall_score(y, y_pred, average='weighted'),
                    'f1_score': f1_score(y, y_pred, average='weighted'),
                    'cv_mean': cv_scores.mean(),
                    'cv_std': cv_scores.std()
                }
                
            except Exception as e:
                self._logger.error(f"{model_name} 평가 실패: {e}")
                continue
        
        return evaluation_results
    
    def get_feature_importance(self) -> Dict[str, Dict[str, float]]:
        """피처 중요도 반환"""
        importance_results = {}
        
        for model_name, model in self._models.items():
            if hasattr(model, 'feature_importances_'):
                importance_results[model_name] = {
                    f"feature_{i}": float(importance) 
                    for i, importance in enumerate(model.feature_importances_)
                }
            elif hasattr(model, 'coef_'):
                importance_results[model_name] = {
                    f"feature_{i}": float(abs(coef)) 
                    for i, coef in enumerate(model.coef_[0])
                }
        
        return importance_results
    
    def retrain_if_needed(self) -> bool:
        """필요시 재훈련"""
        if not self._config.auto_retrain:
            return False
        
        try:
            # 최근 데이터로 성능 확인
            X, y = self.prepare_training_data(days=30)
            current_performance = self.evaluate_models(X, y)
            
            # 성능 하락 체크
            needs_retrain = False
            for model_name, metrics in current_performance.items():
                if metrics['accuracy'] < self._config.target_accuracy - self._config.retrain_threshold:
                    needs_retrain = True
                    self._logger.warning(f"{model_name} 성능 하락 감지: {metrics['accuracy']:.3f}")
            
            if needs_retrain:
                self._logger.info("모델 재훈련 시작")
                X_full, y_full = self.prepare_training_data(days=90)
                self.train_models(X_full, y_full)
                return True
            
            return False
            
        except Exception as e:
            self._logger.error(f"재훈련 확인 실패: {e}")
            return False
    
    def get_learning_summary(self) -> Dict[str, Any]:
        """학습 요약 정보"""
        if not self._models:
            return {'error': '훈련된 모델이 없습니다'}
        
        summary = {
            'total_models': len(self._models),
            'active_models': len([m for m in self._models.keys()]),
            'feature_count': len(self._feature_names),
            'last_training': None,
            'model_performance': {}
        }
        
        # 최근 성과 기록
        if self._model_performance:
            latest_performance = self._model_performance[-1]
            summary['last_training'] = latest_performance['timestamp']
            
            for model_name, pattern_model in latest_performance['models'].items():
                summary['model_performance'][model_name] = {
                    'accuracy': pattern_model.accuracy,
                    'precision': pattern_model.precision,
                    'recall': pattern_model.recall,
                    'f1_score': pattern_model.f1_score,
                    'is_active': pattern_model.is_active
                }
        
        return summary

# 전역 인스턴스
_pattern_learner = None

def get_pattern_learner(feature_extractor, performance_analyzer) -> PatternLearner:
    """패턴 학습기 싱글톤 인스턴스 반환"""
    global _pattern_learner
    if _pattern_learner is None:
        _pattern_learner = PatternLearner(feature_extractor, performance_analyzer)
    return _pattern_learner 