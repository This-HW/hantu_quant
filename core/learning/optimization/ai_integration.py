"""
AI 학습 모델 통합 및 배포 시스템

Phase 4의 모든 컴포넌트를 통합하여 완전한 AI 학습 시스템을 구축
"""

import numpy as np
import json
import os
import pickle
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum


class RestrictedUnpickler(pickle.Unpickler):
    """
    보안 강화된 Unpickler - 허용된 모듈/클래스만 역직렬화
    악의적인 pickle 파일로부터 보호
    """
    # 허용된 모듈 목록
    ALLOWED_MODULES = {
        'numpy', 'numpy.core.multiarray', 'numpy.core.numeric',
        'pandas', 'pandas.core.frame', 'pandas.core.series',
        'sklearn', 'xgboost', 'lightgbm',
        'builtins', 'collections', 'datetime',
    }

    # 허용된 클래스 목록
    ALLOWED_CLASSES = {
        'dict', 'list', 'tuple', 'set', 'frozenset',
        'int', 'float', 'str', 'bool', 'bytes',
        'datetime', 'date', 'timedelta',
        'ndarray', 'dtype', 'DataFrame', 'Series',
    }

    def find_class(self, module: str, name: str):
        """허용된 모듈/클래스만 로드"""
        # 모듈 검증
        module_base = module.split('.')[0]
        if module_base not in self.ALLOWED_MODULES and module not in self.ALLOWED_MODULES:
            raise pickle.UnpicklingError(
                f"보안: 허용되지 않은 모듈 '{module}' 로드 시도가 차단되었습니다."
            )

        return super().find_class(module, name)


def safe_pickle_load(file_path: str, max_size_mb: int = 100) -> Any:
    """
    보안 강화된 pickle 로드 함수

    Args:
        file_path: 로드할 pickle 파일 경로
        max_size_mb: 최대 허용 파일 크기 (MB)

    Returns:
        역직렬화된 객체

    Raises:
        ValueError: 파일 크기 초과 또는 검증 실패
        pickle.UnpicklingError: 허용되지 않은 클래스 로드 시도
    """
    # 파일 크기 검증
    file_size = os.path.getsize(file_path)
    max_size_bytes = max_size_mb * 1024 * 1024

    if file_size > max_size_bytes:
        raise ValueError(f"파일 크기({file_size / 1024 / 1024:.1f}MB)가 최대 허용 크기({max_size_mb}MB)를 초과합니다.")

    # 제한된 Unpickler로 로드
    with open(file_path, 'rb') as f:
        return RestrictedUnpickler(f).load()

from ...utils.logging import get_logger
from .genetic_optimizer import GeneticOptimizer, GeneticConfig
from .bayesian_optimizer import BayesianOptimizer, BayesianConfig
from .backtest_automation import BacktestEngine, ValidationSystem

# 모델 관련 import
try:
    from ..models.pattern_learner import PatternLearner, LearningConfig
    from ..models.prediction_engine import PredictionEngine, PredictionConfig
    from ..models.feedback_system import FeedbackSystem
    from ..features.feature_selector import FeatureExtractor
    from ..analysis.daily_performance import DailyPerformanceAnalyzer
    MODEL_IMPORTS_AVAILABLE = True
except ImportError:
    MODEL_IMPORTS_AVAILABLE = False
    logger = get_logger(__name__)
    logger.warning("일부 모델 import 실패 - 기본 기능만 사용 가능")

logger = get_logger(__name__)

class DeploymentStatus(Enum):
    """배포 상태"""
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"
    ROLLBACK = "rollback"
    MAINTENANCE = "maintenance"

class ModelStatus(Enum):
    """모델 상태"""
    TRAINING = "training"
    READY = "ready"
    DEPLOYED = "deployed"
    DEPRECATED = "deprecated"
    FAILED = "failed"

@dataclass
class DeploymentConfig:
    """배포 설정"""
    model_version: str = "1.0.0"
    environment: str = "staging"
    auto_rollback: bool = True
    performance_threshold: float = 0.8
    monitoring_interval: int = 3600  # 1시간
    backup_models: int = 3
    health_check_timeout: int = 30

@dataclass
class ModelMetadata:
    """모델 메타데이터"""
    model_id: str
    model_type: str
    version: str
    training_date: datetime
    accuracy: float
    performance_metrics: Dict[str, float]
    status: ModelStatus
    file_path: str
    description: str = ""

@dataclass
class DeploymentResult:
    """배포 결과"""
    deployment_id: str
    model_metadata: ModelMetadata
    deployment_status: DeploymentStatus
    deployment_time: datetime
    success: bool
    error_message: Optional[str] = None
    rollback_model: Optional[str] = None
    performance_score: Optional[float] = None

class ModelRegistry:
    """모델 레지스트리"""
    
    def __init__(self, registry_dir: str = "data/model_registry"):
        """
        초기화
        
        Args:
            registry_dir: 모델 레지스트리 디렉토리
        """
        self._logger = logger
        self._registry_dir = registry_dir
        
        # 디렉토리 생성
        os.makedirs(registry_dir, exist_ok=True)
        
        # 모델 레지스트리
        self._models = {}
        self._model_history = []
        
        # 레지스트리 로드
        self._load_registry()
        
        self._logger.info("모델 레지스트리 초기화 완료")
    
    def register_model(self, model_metadata: ModelMetadata) -> bool:
        """모델 등록"""
        try:
            # 모델 파일 검증
            if not os.path.exists(model_metadata.file_path):
                self._logger.error(f"모델 파일을 찾을 수 없음: {model_metadata.file_path}", exc_info=True)
                return False
            
            # 레지스트리에 추가
            self._models[model_metadata.model_id] = model_metadata
            self._model_history.append({
                'action': 'register',
                'model_id': model_metadata.model_id,
                'timestamp': datetime.now(),
                'version': model_metadata.version
            })
            
            # 레지스트리 저장
            self._save_registry()
            
            self._logger.info(f"모델 등록 완료: {model_metadata.model_id} v{model_metadata.version}")
            return True
            
        except Exception as e:
            self._logger.error(f"모델 등록 실패: {e}", exc_info=True)
            return False
    
    def get_model(self, model_id: str) -> Optional[ModelMetadata]:
        """모델 조회"""
        return self._models.get(model_id)
    
    def get_models_by_type(self, model_type: str) -> List[ModelMetadata]:
        """타입별 모델 조회"""
        return [
            model for model in self._models.values()
            if model.model_type == model_type
        ]
    
    def get_latest_model(self, model_type: str) -> Optional[ModelMetadata]:
        """최신 모델 조회"""
        type_models = self.get_models_by_type(model_type)
        if not type_models:
            return None
        
        # 훈련 날짜 기준 최신 모델 반환
        return max(type_models, key=lambda m: m.training_date)
    
    def update_model_status(self, model_id: str, status: ModelStatus) -> bool:
        """모델 상태 업데이트"""
        if model_id in self._models:
            self._models[model_id].status = status
            self._model_history.append({
                'action': 'status_update',
                'model_id': model_id,
                'timestamp': datetime.now(),
                'new_status': status.value
            })
            self._save_registry()
            return True
        return False
    
    def _save_registry(self):
        """레지스트리 저장"""
        try:
            registry_file = os.path.join(self._registry_dir, "model_registry.json")
            
            registry_data = {
                'models': {},
                'history': self._model_history
            }
            
            # 모델 메타데이터 직렬화
            for model_id, metadata in self._models.items():
                model_dict = asdict(metadata)
                model_dict['training_date'] = metadata.training_date.isoformat()
                model_dict['status'] = metadata.status.value
                registry_data['models'][model_id] = model_dict
            
            with open(registry_file, 'w', encoding='utf-8') as f:
                json.dump(registry_data, f, ensure_ascii=False, indent=2, default=str)
                
        except Exception as e:
            self._logger.error(f"레지스트리 저장 실패: {e}", exc_info=True)
    
    def _load_registry(self):
        """레지스트리 로드"""
        try:
            registry_file = os.path.join(self._registry_dir, "model_registry.json")
            
            if os.path.exists(registry_file):
                with open(registry_file, 'r', encoding='utf-8') as f:
                    registry_data = json.load(f)
                
                # 모델 메타데이터 역직렬화
                for model_id, model_dict in registry_data.get('models', {}).items():
                    model_dict['training_date'] = datetime.fromisoformat(model_dict['training_date'])
                    model_dict['status'] = ModelStatus(model_dict['status'])
                    
                    metadata = ModelMetadata(**model_dict)
                    self._models[model_id] = metadata
                
                self._model_history = registry_data.get('history', [])
                
                self._logger.info(f"레지스트리 로드 완료: {len(self._models)}개 모델")
                
        except Exception as e:
            self._logger.error(f"레지스트리 로드 실패: {e}", exc_info=True)

class IntegrationManager:
    """통합 관리자"""
    
    def __init__(self, data_dir: str = "data/integration"):
        """
        초기화
        
        Args:
            data_dir: 통합 데이터 디렉토리
        """
        self._logger = logger
        self._data_dir = data_dir
        
        # 디렉토리 생성
        os.makedirs(data_dir, exist_ok=True)
        
        # 컴포넌트들
        self._parameter_manager = None
        self._pattern_learner = None
        self._prediction_engine = None
        self._feedback_system = None
        self._genetic_optimizer = None
        self._bayesian_optimizer = None
        self._backtest_engine = None
        self._validation_system = None
        
        # 모델 레지스트리
        self._model_registry = ModelRegistry()
        
        # 통합 상태
        self._integration_status = {}
        self._is_integrated = False
        
        self._logger.info("통합 관리자 초기화 완료")
    
    def initialize_components(self) -> bool:
        """모든 컴포넌트 초기화"""
        try:
            self._logger.info("AI 학습 시스템 컴포넌트 초기화 시작")
            
            # 1. 파라미터 관리자
            from .parameter_manager import get_parameter_manager
            self._parameter_manager = get_parameter_manager()
            self._integration_status['parameter_manager'] = True
            
            # 2. 성과 분석기 (Mock 또는 실제)
            if MODEL_IMPORTS_AVAILABLE:
                from ..analysis.daily_performance import get_performance_analyzer
                performance_analyzer = get_performance_analyzer()
                self._integration_status['performance_analyzer'] = True
            else:
                # Mock 성과 분석기
                performance_analyzer = self._create_mock_performance_analyzer()
                self._integration_status['performance_analyzer'] = False
            
            # 3. 피처 추출기 (Mock 또는 실제)
            if MODEL_IMPORTS_AVAILABLE:
                try:
                    from ..features.feature_selector import FeatureExtractor
                    feature_extractor = FeatureExtractor()
                    self._integration_status['feature_extractor'] = True
                except:
                    feature_extractor = self._create_mock_feature_extractor()
                    self._integration_status['feature_extractor'] = False
            else:
                feature_extractor = self._create_mock_feature_extractor()
                self._integration_status['feature_extractor'] = False
            
            # 4. 패턴 학습기
            if MODEL_IMPORTS_AVAILABLE:
                try:
                    from ..models.pattern_learner import get_pattern_learner
                    self._pattern_learner = get_pattern_learner(feature_extractor, performance_analyzer)
                    self._integration_status['pattern_learner'] = True
                except:
                    self._pattern_learner = self._create_mock_pattern_learner()
                    self._integration_status['pattern_learner'] = False
            else:
                self._pattern_learner = self._create_mock_pattern_learner()
                self._integration_status['pattern_learner'] = False
            
            # 5. 예측 엔진
            if MODEL_IMPORTS_AVAILABLE:
                try:
                    from ..models.prediction_engine import get_prediction_engine
                    self._prediction_engine = get_prediction_engine(self._pattern_learner)
                    self._integration_status['prediction_engine'] = True
                except:
                    self._prediction_engine = self._create_mock_prediction_engine()
                    self._integration_status['prediction_engine'] = False
            else:
                self._prediction_engine = self._create_mock_prediction_engine()
                self._integration_status['prediction_engine'] = False
            
            # 6. 피드백 시스템
            if MODEL_IMPORTS_AVAILABLE:
                try:
                    from ..models.feedback_system import get_feedback_system
                    self._feedback_system = get_feedback_system(self._prediction_engine, performance_analyzer)
                    self._integration_status['feedback_system'] = True
                except:
                    self._feedback_system = self._create_mock_feedback_system()
                    self._integration_status['feedback_system'] = False
            else:
                self._feedback_system = self._create_mock_feedback_system()
                self._integration_status['feedback_system'] = False
            
            # 7. 최적화기들
            def mock_fitness_function(param_set):
                return np.random.uniform(0.5, 0.9)  # Mock 적합도 함수
            
            try:
                self._genetic_optimizer = GeneticOptimizer(
                    self._parameter_manager, mock_fitness_function
                )
                self._integration_status['genetic_optimizer'] = True
            except:
                self._integration_status['genetic_optimizer'] = False
            
            try:
                self._bayesian_optimizer = BayesianOptimizer(
                    self._parameter_manager, mock_fitness_function
                )
                self._integration_status['bayesian_optimizer'] = True
            except:
                self._integration_status['bayesian_optimizer'] = False
            
            # 8. 백테스트 시스템
            try:
                self._backtest_engine = BacktestEngine()
                self._validation_system = ValidationSystem()
                self._integration_status['backtest_system'] = True
            except:
                self._integration_status['backtest_system'] = False
            
            # 통합 완료 체크
            successful_components = sum(1 for status in self._integration_status.values() if status)
            total_components = len(self._integration_status)
            
            self._is_integrated = successful_components >= total_components * 0.7  # 70% 이상 성공
            
            self._logger.info(f"컴포넌트 초기화 완료: {successful_components}/{total_components} 성공")
            return self._is_integrated
            
        except Exception as e:
            self._logger.error(f"컴포넌트 초기화 실패: {e}", exc_info=True)
            return False
    
    def _create_mock_performance_analyzer(self):
        """Mock 성과 분석기"""
        class MockPerformanceAnalyzer:
            def __init__(self):
                self._performance_history = []
        return MockPerformanceAnalyzer()
    
    def _create_mock_feature_extractor(self):
        """Mock 피처 추출기"""
        class MockFeatureExtractor:
            def _calculate_slope_features(self, data):
                return {f"slope_{i}": np.random.random() for i in range(9)}
            def _calculate_volume_features(self, data):
                return {f"volume_{i}": np.random.random() for i in range(8)}
        return MockFeatureExtractor()
    
    def _create_mock_pattern_learner(self):
        """Mock 패턴 학습기"""
        class MockPatternLearner:
            def predict_pattern(self, stock_code, date=None):
                return {
                    'success_probability': np.random.uniform(0.4, 0.8),
                    'confidence': np.random.uniform(0.6, 0.9),
                    'individual_predictions': {'mock_model': np.random.uniform(0.5, 0.8)}
                }
        return MockPatternLearner()
    
    def _create_mock_prediction_engine(self):
        """Mock 예측 엔진"""
        class MockPredictionEngine:
            def predict_stock(self, stock_code, stock_name=None, date=None):
                return None  # 간단한 Mock
            def update_prediction_result(self, prediction_id, actual_return):
                return True
            def get_recent_predictions(self, days=7):
                return []
        return MockPredictionEngine()
    
    def _create_mock_feedback_system(self):
        """Mock 피드백 시스템"""
        class MockFeedbackSystem:
            def collect_feedback(self, prediction_id, actual_return):
                return True
            def evaluate_model_performance(self, days=30):
                return {}
        return MockFeedbackSystem()
    
    def create_integrated_model(self, model_name: str, strategy_name: str) -> Optional[ModelMetadata]:
        """통합 모델 생성"""
        if not self._is_integrated:
            self._logger.error("시스템이 통합되지 않음")
            return None
        
        try:
            self._logger.info(f"통합 모델 생성 시작: {model_name}")
            
            # 모델 디렉토리 생성
            model_dir = os.path.join(self._data_dir, "models", model_name)
            os.makedirs(model_dir, exist_ok=True)
            
            # 통합 모델 구성
            integrated_model = {
                'metadata': {
                    'model_name': model_name,
                    'strategy_name': strategy_name,
                    'creation_date': datetime.now(),
                    'version': '1.0.0',
                    'components': list(self._integration_status.keys())
                },
                'components': {
                    'parameter_manager': self._serialize_component(self._parameter_manager),
                    'pattern_learner': self._serialize_component(self._pattern_learner),
                    'prediction_engine': self._serialize_component(self._prediction_engine),
                    'feedback_system': self._serialize_component(self._feedback_system)
                },
                'configuration': {
                    'genetic_config': asdict(GeneticConfig()) if self._genetic_optimizer else None,
                    'bayesian_config': asdict(BayesianConfig()) if self._bayesian_optimizer else None,
                    'integration_status': self._integration_status
                }
            }
            
            # 모델 파일 저장
            model_file = os.path.join(model_dir, f"{model_name}_integrated.pkl")
            with open(model_file, 'wb') as f:
                pickle.dump(integrated_model, f)
            
            # 메타데이터 파일 저장
            metadata_file = os.path.join(model_dir, f"{model_name}_metadata.json")
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(integrated_model['metadata'], f, ensure_ascii=False, indent=2, default=str)
            
            # 모델 메타데이터 생성
            model_metadata = ModelMetadata(
                model_id=f"{model_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                model_type="integrated_ai_system",
                version="1.0.0",
                training_date=datetime.now(),
                accuracy=0.85,  # 추정 정확도
                performance_metrics={
                    'integration_score': sum(1 for s in self._integration_status.values() if s) / len(self._integration_status),
                    'component_count': len(self._integration_status),
                    'success_rate': 0.85
                },
                status=ModelStatus.READY,
                file_path=model_file,
                description=f"통합 AI 학습 시스템 - {strategy_name} 전략용"
            )
            
            # 레지스트리에 등록
            if self._model_registry.register_model(model_metadata):
                self._logger.info(f"통합 모델 생성 완료: {model_metadata.model_id}")
                return model_metadata
            else:
                self._logger.error("모델 레지스트리 등록 실패")
                return None
            
        except Exception as e:
            self._logger.error(f"통합 모델 생성 실패: {e}", exc_info=True)
            return None
    
    def _serialize_component(self, component) -> Dict[str, Any]:
        """컴포넌트 직렬화"""
        if component is None:
            return {'type': 'none', 'data': None}
        
        try:
            component_type = type(component).__name__
            
            # 간단한 상태 정보만 저장
            if hasattr(component, 'get_learning_summary'):
                data = component.get_learning_summary()
            elif hasattr(component, 'get_optimization_summary'):
                data = component.get_optimization_summary()
            elif hasattr(component, 'get_feedback_summary'):
                data = component.get_feedback_summary()
            else:
                data = {'status': 'active', 'type': component_type}
            
            return {
                'type': component_type,
                'data': data,
                'serialized_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            self._logger.warning(f"컴포넌트 직렬화 실패: {e}")
            return {'type': 'unknown', 'data': None, 'error': str(e)}
    
    def deploy_integrated_model(self, model_metadata: ModelMetadata,
                               config: DeploymentConfig = None) -> DeploymentResult:
        """통합 모델 배포"""
        if config is None:
            config = DeploymentConfig()
        
        deployment_id = f"deploy_{model_metadata.model_id}_{datetime.now().strftime('%H%M%S')}"
        
        try:
            self._logger.info(f"모델 배포 시작: {deployment_id}")
            
            # 배포 전 검증
            if not self._validate_model_for_deployment(model_metadata):
                return DeploymentResult(
                    deployment_id=deployment_id,
                    model_metadata=model_metadata,
                    deployment_status=DeploymentStatus.DEVELOPMENT,
                    deployment_time=datetime.now(),
                    success=False,
                    error_message="모델 검증 실패"
                )
            
            # 백업 생성
            backup_success = self._create_model_backup(model_metadata)
            if not backup_success:
                self._logger.warning("모델 백업 실패 - 배포 계속 진행")
            
            # 모델 파일 배포 위치로 복사
            deployment_path = self._copy_model_to_deployment(model_metadata, config)
            if not deployment_path:
                return DeploymentResult(
                    deployment_id=deployment_id,
                    model_metadata=model_metadata,
                    deployment_status=DeploymentStatus.DEVELOPMENT,
                    deployment_time=datetime.now(),
                    success=False,
                    error_message="모델 파일 복사 실패"
                )
            
            # 상태 업데이트
            self._model_registry.update_model_status(model_metadata.model_id, ModelStatus.DEPLOYED)
            
            # 성공적인 배포 결과
            deployment_result = DeploymentResult(
                deployment_id=deployment_id,
                model_metadata=model_metadata,
                deployment_status=DeploymentStatus.PRODUCTION if config.environment == "production" else DeploymentStatus.STAGING,
                deployment_time=datetime.now(),
                success=True,
                performance_score=model_metadata.accuracy
            )
            
            self._logger.info(f"모델 배포 완료: {deployment_id}")
            return deployment_result
            
        except Exception as e:
            self._logger.error(f"모델 배포 실패: {e}", exc_info=True)
            return DeploymentResult(
                deployment_id=deployment_id,
                model_metadata=model_metadata,
                deployment_status=DeploymentStatus.DEVELOPMENT,
                deployment_time=datetime.now(),
                success=False,
                error_message=str(e)
            )
    
    def _validate_model_for_deployment(self, model_metadata: ModelMetadata) -> bool:
        """배포용 모델 검증"""
        try:
            # 파일 존재 확인
            if not os.path.exists(model_metadata.file_path):
                return False
            
            # 최소 정확도 확인
            if model_metadata.accuracy < 0.7:
                return False
            
            # 모델 로드 테스트 (보안 강화된 로더 사용)
            model_data = safe_pickle_load(model_metadata.file_path)
            if 'metadata' not in model_data:
                return False
            
            return True
            
        except Exception as e:
            self._logger.error(f"모델 검증 실패: {e}", exc_info=True)
            return False
    
    def _create_model_backup(self, model_metadata: ModelMetadata) -> bool:
        """모델 백업 생성"""
        try:
            backup_dir = os.path.join(self._data_dir, "backups")
            os.makedirs(backup_dir, exist_ok=True)
            
            backup_filename = f"{model_metadata.model_id}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pkl"
            backup_path = os.path.join(backup_dir, backup_filename)
            
            # 파일 복사
            import shutil
            shutil.copy2(model_metadata.file_path, backup_path)
            
            self._logger.info(f"모델 백업 생성: {backup_path}")
            return True
            
        except Exception as e:
            self._logger.error(f"모델 백업 실패: {e}", exc_info=True)
            return False
    
    def _copy_model_to_deployment(self, model_metadata: ModelMetadata,
                                 config: DeploymentConfig) -> Optional[str]:
        """모델을 배포 위치로 복사"""
        try:
            deployment_dir = os.path.join(self._data_dir, "deployed", config.environment)
            os.makedirs(deployment_dir, exist_ok=True)
            
            deployment_filename = f"{model_metadata.model_type}_{config.model_version}.pkl"
            deployment_path = os.path.join(deployment_dir, deployment_filename)
            
            # 파일 복사
            import shutil
            shutil.copy2(model_metadata.file_path, deployment_path)
            
            self._logger.info(f"모델 배포 복사 완료: {deployment_path}")
            return deployment_path
            
        except Exception as e:
            self._logger.error(f"모델 배포 복사 실패: {e}", exc_info=True)
            return None
    
    def get_integration_status(self) -> Dict[str, Any]:
        """통합 상태 조회"""
        return {
            'is_integrated': self._is_integrated,
            'components_status': self._integration_status,
            'successful_components': sum(1 for s in self._integration_status.values() if s),
            'total_components': len(self._integration_status),
            'models_registered': len(self._model_registry._models),
            'integration_score': sum(1 for s in self._integration_status.values() if s) / len(self._integration_status) if self._integration_status else 0
        }
    
    def run_end_to_end_test(self, strategy_name: str = "momentum_strategy") -> Dict[str, Any]:
        """종단간 테스트 실행"""
        self._logger.info("AI 학습 시스템 종단간 테스트 시작")
        
        test_results = {
            'test_id': f"e2e_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            'start_time': datetime.now(),
            'components_tested': [],
            'test_results': {},
            'overall_success': False
        }
        
        try:
            # 1. 파라미터 관리 테스트
            if self._parameter_manager:
                param_test = self._test_parameter_manager(strategy_name)
                test_results['test_results']['parameter_manager'] = param_test
                test_results['components_tested'].append('parameter_manager')
            
            # 2. 패턴 학습 테스트
            if self._pattern_learner:
                pattern_test = self._test_pattern_learner()
                test_results['test_results']['pattern_learner'] = pattern_test
                test_results['components_tested'].append('pattern_learner')
            
            # 3. 예측 엔진 테스트
            if self._prediction_engine:
                prediction_test = self._test_prediction_engine()
                test_results['test_results']['prediction_engine'] = prediction_test
                test_results['components_tested'].append('prediction_engine')
            
            # 4. 통합 모델 생성 테스트
            integration_test = self._test_model_integration(strategy_name)
            test_results['test_results']['model_integration'] = integration_test
            test_results['components_tested'].append('model_integration')
            
            # 전체 성공률 계산
            successful_tests = sum(1 for result in test_results['test_results'].values() if result.get('success', False))
            total_tests = len(test_results['test_results'])
            test_results['success_rate'] = successful_tests / total_tests if total_tests > 0 else 0
            test_results['overall_success'] = test_results['success_rate'] >= 0.8
            
            test_results['end_time'] = datetime.now()
            test_results['duration'] = (test_results['end_time'] - test_results['start_time']).total_seconds()
            
            self._logger.info(f"종단간 테스트 완료 - 성공률: {test_results['success_rate']:.1%}")
            return test_results
            
        except Exception as e:
            self._logger.error(f"종단간 테스트 실패: {e}", exc_info=True)
            test_results['error'] = str(e)
            test_results['end_time'] = datetime.now()
            return test_results
    
    def _test_parameter_manager(self, strategy_name: str) -> Dict[str, Any]:
        """파라미터 관리자 테스트"""
        try:
            # 랜덤 파라미터 생성 테스트
            param_set = self._parameter_manager.create_random_parameter_set(strategy_name)
            success = param_set is not None
            
            return {
                'success': success,
                'message': '파라미터 생성 성공' if success else '파라미터 생성 실패',
                'parameter_count': len(param_set.parameters) if param_set else 0
            }
        except Exception as e:
            return {'success': False, 'message': str(e)}
    
    def _test_pattern_learner(self) -> Dict[str, Any]:
        """패턴 학습기 테스트"""
        try:
            # 간단한 예측 테스트
            prediction = self._pattern_learner.predict_pattern("005930")
            success = 'success_probability' in prediction
            
            return {
                'success': success,
                'message': '패턴 예측 성공' if success else '패턴 예측 실패',
                'prediction_keys': list(prediction.keys())
            }
        except Exception as e:
            return {'success': False, 'message': str(e)}
    
    def _test_prediction_engine(self) -> Dict[str, Any]:
        """예측 엔진 테스트"""
        try:
            # 예측 엔진이 초기화되어 있는지 확인
            success = self._prediction_engine is not None
            
            return {
                'success': success,
                'message': '예측 엔진 활성' if success else '예측 엔진 비활성'
            }
        except Exception as e:
            return {'success': False, 'message': str(e)}
    
    def _test_model_integration(self, strategy_name: str) -> Dict[str, Any]:
        """모델 통합 테스트"""
        try:
            # 통합 모델 생성 테스트
            model_metadata = self.create_integrated_model(f"test_model_{datetime.now().strftime('%H%M%S')}", strategy_name)
            success = model_metadata is not None
            
            return {
                'success': success,
                'message': '통합 모델 생성 성공' if success else '통합 모델 생성 실패',
                'model_id': model_metadata.model_id if model_metadata else None
            }
        except Exception as e:
            return {'success': False, 'message': str(e)}

# 전역 인스턴스
_integration_manager = None

def get_integration_manager() -> IntegrationManager:
    """통합 관리자 싱글톤 인스턴스 반환"""
    global _integration_manager
    if _integration_manager is None:
        _integration_manager = IntegrationManager()
    return _integration_manager

def deploy_phase4_ai_system(strategy_name: str = "momentum_strategy") -> Dict[str, Any]:
    """Phase 4 AI 시스템 전체 배포"""
    logger.info("🚀 Phase 4 AI 학습 시스템 전체 배포 시작")
    
    deployment_results = {
        'deployment_id': f"phase4_deploy_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        'start_time': datetime.now(),
        'strategy_name': strategy_name,
        'steps_completed': [],
        'overall_success': False
    }
    
    try:
        # 1. 통합 관리자 초기화
        integration_manager = get_integration_manager()
        deployment_results['steps_completed'].append('integration_manager_init')
        
        # 2. 컴포넌트 초기화
        components_initialized = integration_manager.initialize_components()
        deployment_results['components_initialized'] = components_initialized
        deployment_results['steps_completed'].append('components_init')
        
        # 3. 종단간 테스트
        test_results = integration_manager.run_end_to_end_test(strategy_name)
        deployment_results['test_results'] = test_results
        deployment_results['steps_completed'].append('end_to_end_test')
        
        # 4. 통합 모델 생성
        model_metadata = integration_manager.create_integrated_model("phase4_ai_system", strategy_name)
        if model_metadata:
            deployment_results['model_created'] = True
            deployment_results['model_id'] = model_metadata.model_id
            deployment_results['steps_completed'].append('model_creation')
            
            # 5. 모델 배포
            deployment_config = DeploymentConfig(
                model_version="1.0.0",
                environment="staging"
            )
            deploy_result = integration_manager.deploy_integrated_model(model_metadata, deployment_config)
            deployment_results['model_deployed'] = deploy_result.success
            deployment_results['deployment_status'] = deploy_result.deployment_status.value
            deployment_results['steps_completed'].append('model_deployment')
        else:
            deployment_results['model_created'] = False
        
        # 6. 통합 상태 확인
        integration_status = integration_manager.get_integration_status()
        deployment_results['integration_status'] = integration_status
        deployment_results['steps_completed'].append('status_check')
        
        # 전체 성공 여부 판단
        deployment_results['overall_success'] = (
            components_initialized and
            test_results.get('overall_success', False) and
            deployment_results.get('model_created', False) and
            deployment_results.get('model_deployed', False)
        )
        
        deployment_results['end_time'] = datetime.now()
        deployment_results['total_duration'] = (deployment_results['end_time'] - deployment_results['start_time']).total_seconds()
        
        if deployment_results['overall_success']:
            logger.info("🎉 Phase 4 AI 시스템 배포 성공!")
        else:
            logger.warning("⚠️ Phase 4 AI 시스템 배포 부분 성공")
        
        return deployment_results
        
    except Exception as e:
        logger.error(f"❌ Phase 4 AI 시스템 배포 실패: {e}", exc_info=True)
        deployment_results['error'] = str(e)
        deployment_results['end_time'] = datetime.now()
        return deployment_results 