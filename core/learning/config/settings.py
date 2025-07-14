"""
Phase 4: AI 학습 시스템 - 설정 관리
AI 학습 시스템의 모든 설정을 관리
"""

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from pathlib import Path

# 기존 설정 시스템과 연동
try:
    from core.config.api_config import APIConfig
    BASE_CONFIG_AVAILABLE = True
except ImportError:
    BASE_CONFIG_AVAILABLE = False
    APIConfig = None


@dataclass
class ModelConfig:
    """머신러닝 모델 설정"""
    # Random Forest 설정
    rf_n_estimators: int = 100
    rf_max_depth: int = 10
    rf_random_state: int = 42
    rf_min_samples_split: int = 2
    rf_min_samples_leaf: int = 1
    
    # XGBoost 설정
    xgb_n_estimators: int = 200
    xgb_max_depth: int = 6
    xgb_learning_rate: float = 0.1
    xgb_random_state: int = 42
    xgb_subsample: float = 0.8
    xgb_colsample_bytree: float = 0.8
    
    # 일반 모델 설정
    test_size: float = 0.2
    validation_size: float = 0.2
    cross_validation_folds: int = 5


@dataclass
class DataConfig:
    """데이터 관련 설정"""
    # 데이터 저장 경로
    data_dir: str = "data/learning"
    features_dir: str = "data/learning/features"
    models_dir: str = "data/learning/models"
    results_dir: str = "data/learning/results"
    
    # 데이터 수집 설정
    historical_days: int = 252  # 1년간 데이터
    min_trading_days: int = 20  # 최소 거래일
    max_missing_ratio: float = 0.1  # 최대 결측치 비율
    
    # 피처 엔지니어링 설정
    feature_selection_threshold: float = 0.01  # 피처 중요도 임계값
    correlation_threshold: float = 0.95  # 상관관계 임계값
    variance_threshold: float = 0.01  # 분산 임계값


@dataclass
class LearningConfig:
    """AI 학습 시스템 전체 설정"""
    
    # 기본 설정
    version: str = "1.0.0"
    debug: bool = False
    
    # 로깅 설정
    log_level: str = "INFO"
    log_dir: str = "logs/learning"
    enable_file_logging: bool = True
    
    # 성능 최적화 설정
    n_jobs: int = 4  # 병렬 처리 워커 수
    batch_size: int = 500  # 배치 크기
    memory_limit: str = "2GB"  # 메모리 제한
    
    # 모델 설정
    model: ModelConfig = field(default_factory=ModelConfig)
    
    # 데이터 설정
    data: DataConfig = field(default_factory=DataConfig)
    
    # Phase 1,2 연동 설정
    phase1_accuracy_threshold: float = 0.78  # Phase 1 정확도 임계값
    phase2_accuracy_threshold: float = 0.85  # Phase 2 정확도 임계값
    target_accuracy: float = 0.90  # 목표 정확도
    
    # 백테스트 설정
    backtest_period: int = 30  # 백테스트 기간 (일)
    performance_window: int = 5  # 성과 평가 윈도우 (일)
    
    # 최적화 설정
    optimization_trials: int = 100  # 최적화 시도 횟수
    optimization_timeout: int = 3600  # 최적화 타임아웃 (초)
    
    # 알림 설정
    enable_notifications: bool = True
    notification_threshold: float = 0.05  # 성능 변화 알림 임계값
    
    def __post_init__(self):
        """설정 후처리"""
        # 디렉토리 생성
        self._create_directories()
        
        # 기존 설정 시스템과 연동
        if BASE_CONFIG_AVAILABLE:
            self._integrate_base_config()
    
    def _create_directories(self):
        """필요한 디렉토리 생성"""
        directories = [
            self.log_dir,
            self.data.data_dir,
            self.data.features_dir,
            self.data.models_dir,
            self.data.results_dir,
        ]
        
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)
    
    def _integrate_base_config(self):
        """기존 설정 시스템과 연동"""
        if BASE_CONFIG_AVAILABLE:
            # 기존 설정에서 디버그 모드 가져오기
            try:
                # 환경변수에서 디버그 모드 확인
                debug_env = os.getenv('DEBUG', 'false').lower()
                self.debug = debug_env in ['true', '1', 'yes']
            except Exception:
                pass
    
    def to_dict(self) -> Dict[str, Any]:
        """설정을 딕셔너리로 변환"""
        return {
            'version': self.version,
            'debug': self.debug,
            'log_level': self.log_level,
            'log_dir': self.log_dir,
            'enable_file_logging': self.enable_file_logging,
            'n_jobs': self.n_jobs,
            'batch_size': self.batch_size,
            'memory_limit': self.memory_limit,
            'model': {
                'rf_n_estimators': self.model.rf_n_estimators,
                'rf_max_depth': self.model.rf_max_depth,
                'xgb_n_estimators': self.model.xgb_n_estimators,
                'xgb_max_depth': self.model.xgb_max_depth,
                'xgb_learning_rate': self.model.xgb_learning_rate,
                'test_size': self.model.test_size,
                'validation_size': self.model.validation_size,
                'cross_validation_folds': self.model.cross_validation_folds,
            },
            'data': {
                'data_dir': self.data.data_dir,
                'features_dir': self.data.features_dir,
                'models_dir': self.data.models_dir,
                'results_dir': self.data.results_dir,
                'historical_days': self.data.historical_days,
                'min_trading_days': self.data.min_trading_days,
                'max_missing_ratio': self.data.max_missing_ratio,
            },
            'phase1_accuracy_threshold': self.phase1_accuracy_threshold,
            'phase2_accuracy_threshold': self.phase2_accuracy_threshold,
            'target_accuracy': self.target_accuracy,
            'backtest_period': self.backtest_period,
            'performance_window': self.performance_window,
            'optimization_trials': self.optimization_trials,
            'optimization_timeout': self.optimization_timeout,
            'enable_notifications': self.enable_notifications,
            'notification_threshold': self.notification_threshold,
        }
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'LearningConfig':
        """딕셔너리에서 설정 객체 생성"""
        config = cls()
        
        # 기본 설정
        config.version = config_dict.get('version', config.version)
        config.debug = config_dict.get('debug', config.debug)
        config.log_level = config_dict.get('log_level', config.log_level)
        config.log_dir = config_dict.get('log_dir', config.log_dir)
        config.enable_file_logging = config_dict.get('enable_file_logging', config.enable_file_logging)
        config.n_jobs = config_dict.get('n_jobs', config.n_jobs)
        config.batch_size = config_dict.get('batch_size', config.batch_size)
        config.memory_limit = config_dict.get('memory_limit', config.memory_limit)
        
        # 모델 설정
        model_config = config_dict.get('model', {})
        config.model.rf_n_estimators = model_config.get('rf_n_estimators', config.model.rf_n_estimators)
        config.model.rf_max_depth = model_config.get('rf_max_depth', config.model.rf_max_depth)
        config.model.xgb_n_estimators = model_config.get('xgb_n_estimators', config.model.xgb_n_estimators)
        config.model.xgb_max_depth = model_config.get('xgb_max_depth', config.model.xgb_max_depth)
        config.model.xgb_learning_rate = model_config.get('xgb_learning_rate', config.model.xgb_learning_rate)
        config.model.test_size = model_config.get('test_size', config.model.test_size)
        config.model.validation_size = model_config.get('validation_size', config.model.validation_size)
        config.model.cross_validation_folds = model_config.get('cross_validation_folds', config.model.cross_validation_folds)
        
        # 데이터 설정
        data_config = config_dict.get('data', {})
        config.data.data_dir = data_config.get('data_dir', config.data.data_dir)
        config.data.features_dir = data_config.get('features_dir', config.data.features_dir)
        config.data.models_dir = data_config.get('models_dir', config.data.models_dir)
        config.data.results_dir = data_config.get('results_dir', config.data.results_dir)
        config.data.historical_days = data_config.get('historical_days', config.data.historical_days)
        config.data.min_trading_days = data_config.get('min_trading_days', config.data.min_trading_days)
        config.data.max_missing_ratio = data_config.get('max_missing_ratio', config.data.max_missing_ratio)
        
        # 기타 설정
        config.phase1_accuracy_threshold = config_dict.get('phase1_accuracy_threshold', config.phase1_accuracy_threshold)
        config.phase2_accuracy_threshold = config_dict.get('phase2_accuracy_threshold', config.phase2_accuracy_threshold)
        config.target_accuracy = config_dict.get('target_accuracy', config.target_accuracy)
        config.backtest_period = config_dict.get('backtest_period', config.backtest_period)
        config.performance_window = config_dict.get('performance_window', config.performance_window)
        config.optimization_trials = config_dict.get('optimization_trials', config.optimization_trials)
        config.optimization_timeout = config_dict.get('optimization_timeout', config.optimization_timeout)
        config.enable_notifications = config_dict.get('enable_notifications', config.enable_notifications)
        config.notification_threshold = config_dict.get('notification_threshold', config.notification_threshold)
        
        return config


# 전역 설정 관리
_global_config: Optional[LearningConfig] = None

def get_learning_config() -> LearningConfig:
    """전역 학습 설정 조회"""
    global _global_config
    if _global_config is None:
        _global_config = LearningConfig()
    return _global_config

def set_learning_config(config: LearningConfig) -> None:
    """전역 학습 설정 설정"""
    global _global_config
    _global_config = config 