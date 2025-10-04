"""
Phase 4: AI 학습 시스템 - 파라미터 관리 시스템

다양한 최적화 알고리즘을 통합 관리하는 파라미터 매니저
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any, Union
from datetime import datetime, timedelta
import json
import pickle
from dataclasses import dataclass, asdict
from pathlib import Path
import copy

from core.utils.log_utils import get_logger

logger = get_logger(__name__)

@dataclass
class ParameterSet:
    """파라미터 세트 클래스"""
    name: str
    parameters: Dict[str, Any]
    
    # 성능 지표
    performance_score: Optional[float] = None
    accuracy: Optional[float] = None
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1_score: Optional[float] = None
    
    # 메타데이터
    optimization_method: Optional[str] = None
    created_at: Optional[str] = None
    is_best: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return asdict(self)

@dataclass
class OptimizationResult:
    """최적화 결과 클래스"""
    method: str
    best_parameters: ParameterSet
    all_tested_parameters: List[ParameterSet]
    
    # 최적화 통계
    total_evaluations: int
    optimization_time: float
    convergence_iteration: Optional[int] = None
    
    # 성능 개선
    improvement_rate: Optional[float] = None
    baseline_score: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            'method': self.method,
            'best_parameters': self.best_parameters.to_dict(),
            'all_tested_parameters': [p.to_dict() for p in self.all_tested_parameters],
            'total_evaluations': self.total_evaluations,
            'optimization_time': self.optimization_time,
            'convergence_iteration': self.convergence_iteration,
            'improvement_rate': self.improvement_rate,
            'baseline_score': self.baseline_score
        }

class ParameterManager:
    """파라미터 관리 시스템"""
    
    def __init__(self, config_dir: str = "data/optimization"):
        """초기화
        
        Args:
            config_dir: 설정 저장 디렉토리
        """
        self._logger = logger
        self._config_dir = Path(config_dir)
        self._config_dir.mkdir(parents=True, exist_ok=True)
        
        # 파라미터 공간 정의
        self._parameter_spaces = self._initialize_parameter_spaces()
        
        # 최적화 히스토리
        self._optimization_history = []
        
        # 현재 최적 파라미터
        self._current_best_parameters = {}
        
        # 기본 평가 함수
        self._evaluation_function = None
        
        self._logger.info("ParameterManager 초기화 완료")
    
    def _initialize_parameter_spaces(self) -> Dict[str, Dict]:
        """파라미터 공간 초기화"""
        return {
            # Random Forest 파라미터
            'random_forest': {
                'n_estimators': {'type': 'int', 'range': [50, 500], 'default': 100},
                'max_depth': {'type': 'int', 'range': [3, 20], 'default': 10},
                'min_samples_split': {'type': 'int', 'range': [2, 20], 'default': 5},
                'min_samples_leaf': {'type': 'int', 'range': [1, 10], 'default': 2},
                'max_features': {'type': 'choice', 'choices': ['sqrt', 'log2', None], 'default': 'sqrt'}
            },
            
            # Gradient Boosting 파라미터
            'gradient_boosting': {
                'n_estimators': {'type': 'int', 'range': [50, 300], 'default': 100},
                'learning_rate': {'type': 'float', 'range': [0.01, 0.3], 'default': 0.1},
                'max_depth': {'type': 'int', 'range': [3, 15], 'default': 6},
                'subsample': {'type': 'float', 'range': [0.6, 1.0], 'default': 1.0},
                'max_features': {'type': 'choice', 'choices': ['sqrt', 'log2', None], 'default': 'sqrt'}
            },
            
            # Logistic Regression 파라미터
            'logistic_regression': {
                'C': {'type': 'float', 'range': [0.001, 100.0], 'default': 1.0},
                'penalty': {'type': 'choice', 'choices': ['l1', 'l2', 'elasticnet'], 'default': 'l2'},
                'solver': {'type': 'choice', 'choices': ['liblinear', 'saga', 'lbfgs'], 'default': 'lbfgs'},
                'max_iter': {'type': 'int', 'range': [100, 2000], 'default': 1000}
            },
            
            # MLP 파라미터
            'mlp': {
                'hidden_layer_sizes': {'type': 'choice', 'choices': [(50,), (100,), (50, 25), (100, 50)], 'default': (50, 25)},
                'learning_rate_init': {'type': 'float', 'range': [0.0001, 0.01], 'default': 0.001},
                'alpha': {'type': 'float', 'range': [0.0001, 0.01], 'default': 0.0001},
                'max_iter': {'type': 'int', 'range': [200, 1000], 'default': 500}
            },
            
            # 피처 선택 파라미터
            'feature_selection': {
                'k_best': {'type': 'int', 'range': [5, 17], 'default': 10},
                'correlation_threshold': {'type': 'float', 'range': [0.5, 0.95], 'default': 0.8},
                'variance_threshold': {'type': 'float', 'range': [0.0, 0.1], 'default': 0.01}
            },
            
            # 데이터 전처리 파라미터
            'preprocessing': {
                'scaler_type': {'type': 'choice', 'choices': ['standard', 'minmax', 'robust'], 'default': 'standard'},
                'outlier_method': {'type': 'choice', 'choices': ['iqr', 'zscore', 'isolation'], 'default': 'iqr'},
                'outlier_threshold': {'type': 'float', 'range': [1.5, 3.0], 'default': 2.0}
            }
        }
    
    def set_evaluation_function(self, eval_func):
        """평가 함수 설정
        
        Args:
            eval_func: 파라미터를 받아 성능 점수를 반환하는 함수
        """
        self._evaluation_function = eval_func
        self._logger.info("평가 함수 설정 완료")
    
    def get_parameter_space(self, component: str) -> Dict[str, Dict]:
        """파라미터 공간 조회
        
        Args:
            component: 컴포넌트 이름
            
        Returns:
            Dict[str, Dict]: 파라미터 공간 정의
        """
        return self._parameter_spaces.get(component, {})
    
    def generate_random_parameters(self, component: str) -> Dict[str, Any]:
        """랜덤 파라미터 생성
        
        Args:
            component: 컴포넌트 이름
            
        Returns:
            Dict[str, Any]: 랜덤 파라미터
        """
        try:
            space = self.get_parameter_space(component)
            if not space:
                return {}
            
            random_params = {}
            
            for param_name, param_config in space.items():
                param_type = param_config.get('type')
                
                if param_type == 'int':
                    low, high = param_config['range']
                    random_params[param_name] = np.random.randint(low, high + 1)
                
                elif param_type == 'float':
                    low, high = param_config['range']
                    random_params[param_name] = np.random.uniform(low, high)
                
                elif param_type == 'choice':
                    choices = param_config['choices']
                    random_params[param_name] = np.random.choice(choices)
            
            return random_params
            
        except Exception as e:
            self._logger.error(f"랜덤 파라미터 생성 오류: {e}")
            return {}
    
    def get_default_parameters(self, component: str) -> Dict[str, Any]:
        """기본 파라미터 조회
        
        Args:
            component: 컴포넌트 이름
            
        Returns:
            Dict[str, Any]: 기본 파라미터
        """
        try:
            space = self.get_parameter_space(component)
            if not space:
                return {}
            
            default_params = {}
            
            for param_name, param_config in space.items():
                default_params[param_name] = param_config.get('default')
            
            return default_params
            
        except Exception as e:
            self._logger.error(f"기본 파라미터 조회 오류: {e}")
            return {}
    
    def validate_parameters(self, component: str, parameters: Dict[str, Any]) -> bool:
        """파라미터 유효성 검증
        
        Args:
            component: 컴포넌트 이름
            parameters: 검증할 파라미터
            
        Returns:
            bool: 유효성 검증 결과
        """
        try:
            space = self.get_parameter_space(component)
            if not space:
                return False
            
            for param_name, param_value in parameters.items():
                if param_name not in space:
                    self._logger.warning(f"알 수 없는 파라미터: {param_name}")
                    continue
                
                param_config = space[param_name]
                param_type = param_config.get('type')
                
                if param_type == 'int':
                    if not isinstance(param_value, int):
                        return False
                    low, high = param_config['range']
                    if not (low <= param_value <= high):
                        return False
                
                elif param_type == 'float':
                    if not isinstance(param_value, (int, float)):
                        return False
                    low, high = param_config['range']
                    if not (low <= param_value <= high):
                        return False
                
                elif param_type == 'choice':
                    choices = param_config['choices']
                    if param_value not in choices:
                        return False
            
            return True
            
        except Exception as e:
            self._logger.error(f"파라미터 검증 오류: {e}")
            return False
    
    def evaluate_parameters(self, component: str, parameters: Dict[str, Any]) -> Optional[float]:
        """파라미터 평가
        
        Args:
            component: 컴포넌트 이름
            parameters: 평가할 파라미터
            
        Returns:
            Optional[float]: 성능 점수
        """
        try:
            if not self._evaluation_function:
                self._logger.error("평가 함수가 설정되지 않았습니다")
                return None
            
            if not self.validate_parameters(component, parameters):
                self._logger.error("파라미터 유효성 검증 실패")
                return None
            
            # 평가 함수 호출
            score = self._evaluation_function(component, parameters)
            
            return float(score) if score is not None else None
            
        except Exception as e:
            self._logger.error(f"파라미터 평가 오류: {e}")
            return None
    
    def save_optimization_result(self, result: OptimizationResult):
        """최적화 결과 저장
        
        Args:
            result: 최적화 결과
        """
        try:
            # 히스토리에 추가
            self._optimization_history.append(result)
            
            # 현재 최적 파라미터 업데이트
            component = result.best_parameters.name
            self._current_best_parameters[component] = result.best_parameters
            
            # 파일로 저장
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"optimization_{result.method}_{timestamp}.json"
            filepath = self._config_dir / filename
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
            
            # 현재 최적 파라미터 저장
            best_params_file = self._config_dir / "best_parameters.json"
            best_params_data = {
                component: params.to_dict() 
                for component, params in self._current_best_parameters.items()
            }
            
            with open(best_params_file, 'w', encoding='utf-8') as f:
                json.dump(best_params_data, f, ensure_ascii=False, indent=2)
            
            self._logger.info(f"최적화 결과 저장 완료: {filepath}")
            
        except Exception as e:
            self._logger.error(f"최적화 결과 저장 오류: {e}")
    
    def load_best_parameters(self) -> Dict[str, ParameterSet]:
        """저장된 최적 파라미터 로드
        
        Returns:
            Dict[str, ParameterSet]: 컴포넌트별 최적 파라미터
        """
        try:
            best_params_file = self._config_dir / "best_parameters.json"
            
            if not best_params_file.exists():
                self._logger.info("저장된 최적 파라미터가 없습니다")
                return {}
            
            with open(best_params_file, 'r', encoding='utf-8') as f:
                best_params_data = json.load(f)
            
            loaded_params = {}
            
            for component, params_dict in best_params_data.items():
                parameter_set = ParameterSet(
                    name=params_dict['name'],
                    parameters=params_dict['parameters'],
                    performance_score=params_dict.get('performance_score'),
                    accuracy=params_dict.get('accuracy'),
                    precision=params_dict.get('precision'),
                    recall=params_dict.get('recall'),
                    f1_score=params_dict.get('f1_score'),
                    optimization_method=params_dict.get('optimization_method'),
                    created_at=params_dict.get('created_at'),
                    is_best=params_dict.get('is_best', False)
                )
                
                loaded_params[component] = parameter_set
            
            self._current_best_parameters = loaded_params
            
            self._logger.info(f"최적 파라미터 로드 완료: {len(loaded_params)}개 컴포넌트")
            return loaded_params
            
        except Exception as e:
            self._logger.error(f"최적 파라미터 로드 오류: {e}")
            return {}
    
    def get_best_parameters(self, component: str) -> Optional[ParameterSet]:
        """최적 파라미터 조회
        
        Args:
            component: 컴포넌트 이름
            
        Returns:
            Optional[ParameterSet]: 최적 파라미터
        """
        return self._current_best_parameters.get(component)
    
    def compare_parameters(self, component: str, params1: Dict[str, Any], 
                          params2: Dict[str, Any]) -> Dict[str, Any]:
        """파라미터 비교
        
        Args:
            component: 컴포넌트 이름
            params1: 첫 번째 파라미터
            params2: 두 번째 파라미터
            
        Returns:
            Dict[str, Any]: 비교 결과
        """
        try:
            # 두 파라미터 평가
            score1 = self.evaluate_parameters(component, params1)
            score2 = self.evaluate_parameters(component, params2)
            
            comparison = {
                'component': component,
                'params1': params1,
                'params2': params2,
                'score1': score1,
                'score2': score2,
                'better_params': None,
                'improvement': 0.0
            }
            
            if score1 is not None and score2 is not None:
                if score1 > score2:
                    comparison['better_params'] = 'params1'
                    comparison['improvement'] = score1 - score2
                elif score2 > score1:
                    comparison['better_params'] = 'params2'
                    comparison['improvement'] = score2 - score1
                else:
                    comparison['better_params'] = 'equal'
            
            return comparison
            
        except Exception as e:
            self._logger.error(f"파라미터 비교 오류: {e}")
            return {}
    
    def get_optimization_history(self) -> List[OptimizationResult]:
        """최적화 히스토리 조회
        
        Returns:
            List[OptimizationResult]: 최적화 히스토리
        """
        return self._optimization_history.copy()
    
    def get_parameter_statistics(self, component: str) -> Dict[str, Any]:
        """파라미터 통계 정보
        
        Args:
            component: 컴포넌트 이름
            
        Returns:
            Dict[str, Any]: 통계 정보
        """
        try:
            space = self.get_parameter_space(component)
            default_params = self.get_default_parameters(component)
            best_params = self.get_best_parameters(component)
            
            stats = {
                'component': component,
                'parameter_count': len(space),
                'parameter_names': list(space.keys()),
                'has_default': len(default_params) > 0,
                'has_optimized': best_params is not None,
                'parameter_types': {
                    name: config['type'] 
                    for name, config in space.items()
                },
                'optimization_attempts': len([
                    result for result in self._optimization_history 
                    if result.best_parameters.name == component
                ])
            }
            
            if best_params:
                stats['best_score'] = best_params.performance_score
                stats['optimization_method'] = best_params.optimization_method
            
            return stats
            
        except Exception as e:
            self._logger.error(f"파라미터 통계 조회 오류: {e}")
            return {} 