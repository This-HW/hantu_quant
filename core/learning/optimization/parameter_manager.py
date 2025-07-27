"""
파라미터 관리자

전략 파라미터의 정의, 관리, 검증을 담당하는 시스템
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum
import numpy as np

from ...utils.logging import get_logger

logger = get_logger(__name__)

class ParameterType(Enum):
    """파라미터 타입"""
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    CATEGORICAL = "categorical"

@dataclass
class ParameterSpace:
    """파라미터 공간 정의"""
    name: str
    param_type: ParameterType
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    categories: Optional[List[str]] = None
    default_value: Optional[Any] = None
    description: str = ""
    
    def __post_init__(self):
        """초기화 후 검증"""
        if self.param_type in [ParameterType.INTEGER, ParameterType.FLOAT]:
            if self.min_value is None or self.max_value is None:
                raise ValueError(f"수치형 파라미터 {self.name}는 min_value, max_value가 필요합니다")
        elif self.param_type == ParameterType.CATEGORICAL:
            if not self.categories:
                raise ValueError(f"범주형 파라미터 {self.name}는 categories가 필요합니다")
    
    def validate_value(self, value: Any) -> bool:
        """값 검증"""
        try:
            if self.param_type == ParameterType.INTEGER:
                return isinstance(value, int) and self.min_value <= value <= self.max_value
            elif self.param_type == ParameterType.FLOAT:
                return isinstance(value, (int, float)) and self.min_value <= value <= self.max_value
            elif self.param_type == ParameterType.BOOLEAN:
                return isinstance(value, bool)
            elif self.param_type == ParameterType.CATEGORICAL:
                return value in self.categories
            return False
        except:
            return False
    
    def generate_random_value(self) -> Any:
        """랜덤 값 생성"""
        if self.param_type == ParameterType.INTEGER:
            return np.random.randint(self.min_value, self.max_value + 1)
        elif self.param_type == ParameterType.FLOAT:
            return np.random.uniform(self.min_value, self.max_value)
        elif self.param_type == ParameterType.BOOLEAN:
            return np.random.choice([True, False])
        elif self.param_type == ParameterType.CATEGORICAL:
            return np.random.choice(self.categories)
        else:
            return self.default_value

@dataclass
class ParameterSet:
    """파라미터 세트"""
    parameters: Dict[str, Any]
    fitness_score: Optional[float] = None
    backtest_results: Optional[Dict[str, float]] = None
    created_at: Optional[datetime] = None
    validated: bool = False
    
    def __post_init__(self):
        """초기화 후 처리"""
        if self.created_at is None:
            self.created_at = datetime.now()

class ParameterManager:
    """파라미터 관리자"""
    
    def __init__(self, data_dir: str = "data/parameters"):
        """
        초기화
        
        Args:
            data_dir: 파라미터 데이터 저장 디렉토리
        """
        self._logger = logger
        self._data_dir = data_dir
        
        # 디렉토리 생성
        os.makedirs(data_dir, exist_ok=True)
        
        # 파라미터 공간 및 세트들
        self._parameter_spaces = {}
        self._parameter_sets = []
        self._best_parameters = {}
        
        # 전략별 파라미터 정의
        self._initialize_default_parameter_spaces()
        
        # 기존 데이터 로드
        self._load_parameter_data()
        
        self._logger.info("파라미터 관리자 초기화 완료")
    
    def _initialize_default_parameter_spaces(self):
        """기본 파라미터 공간 초기화"""
        # 모멘텀 전략 파라미터
        momentum_params = [
            ParameterSpace(
                name="lookback_period",
                param_type=ParameterType.INTEGER,
                min_value=5,
                max_value=30,
                default_value=20,
                description="모멘텀 계산 기간"
            ),
            ParameterSpace(
                name="momentum_threshold",
                param_type=ParameterType.FLOAT,
                min_value=0.01,
                max_value=0.10,
                default_value=0.05,
                description="모멘텀 임계값"
            ),
            ParameterSpace(
                name="volume_filter",
                param_type=ParameterType.BOOLEAN,
                default_value=True,
                description="거래량 필터 사용 여부"
            ),
            ParameterSpace(
                name="volume_threshold",
                param_type=ParameterType.FLOAT,
                min_value=0.5,
                max_value=3.0,
                default_value=1.0,
                description="거래량 임계값 (평균 대비 배수)"
            )
        ]
        
        # 위험 관리 파라미터
        risk_params = [
            ParameterSpace(
                name="stop_loss",
                param_type=ParameterType.FLOAT,
                min_value=0.02,
                max_value=0.15,
                default_value=0.05,
                description="손절 비율"
            ),
            ParameterSpace(
                name="take_profit",
                param_type=ParameterType.FLOAT,
                min_value=0.05,
                max_value=0.30,
                default_value=0.10,
                description="익절 비율"
            ),
            ParameterSpace(
                name="position_size",
                param_type=ParameterType.FLOAT,
                min_value=0.01,
                max_value=0.20,
                default_value=0.05,
                description="포지션 크기 (자본 대비 비율)"
            ),
            ParameterSpace(
                name="max_positions",
                param_type=ParameterType.INTEGER,
                min_value=5,
                max_value=50,
                default_value=20,
                description="최대 포지션 수"
            )
        ]
        
        # 기술적 지표 파라미터
        technical_params = [
            ParameterSpace(
                name="rsi_period",
                param_type=ParameterType.INTEGER,
                min_value=7,
                max_value=21,
                default_value=14,
                description="RSI 계산 기간"
            ),
            ParameterSpace(
                name="rsi_oversold",
                param_type=ParameterType.FLOAT,
                min_value=20.0,
                max_value=35.0,
                default_value=30.0,
                description="RSI 과매도 임계값"
            ),
            ParameterSpace(
                name="rsi_overbought",
                param_type=ParameterType.FLOAT,
                min_value=65.0,
                max_value=80.0,
                default_value=70.0,
                description="RSI 과매수 임계값"
            ),
            ParameterSpace(
                name="ma_short_period",
                param_type=ParameterType.INTEGER,
                min_value=5,
                max_value=20,
                default_value=10,
                description="단기 이동평균 기간"
            ),
            ParameterSpace(
                name="ma_long_period",
                param_type=ParameterType.INTEGER,
                min_value=20,
                max_value=60,
                default_value=30,
                description="장기 이동평균 기간"
            )
        ]
        
        # 전략별로 파라미터 공간 등록
        self.register_parameter_spaces("momentum_strategy", momentum_params)
        self.register_parameter_spaces("risk_management", risk_params)
        self.register_parameter_spaces("technical_indicators", technical_params)
    
    def register_parameter_spaces(self, strategy_name: str, parameter_spaces: List[ParameterSpace]):
        """파라미터 공간 등록"""
        if strategy_name not in self._parameter_spaces:
            self._parameter_spaces[strategy_name] = {}
        
        for param_space in parameter_spaces:
            self._parameter_spaces[strategy_name][param_space.name] = param_space
            
        self._logger.info(f"전략 '{strategy_name}'에 {len(parameter_spaces)}개 파라미터 공간 등록")
    
    def get_parameter_space(self, strategy_name: str, param_name: str) -> Optional[ParameterSpace]:
        """특정 파라미터 공간 조회"""
        return self._parameter_spaces.get(strategy_name, {}).get(param_name)
    
    def get_all_parameter_spaces(self, strategy_name: str) -> Dict[str, ParameterSpace]:
        """전략의 모든 파라미터 공간 조회"""
        return self._parameter_spaces.get(strategy_name, {})
    
    def create_random_parameter_set(self, strategy_name: str) -> Optional[ParameterSet]:
        """랜덤 파라미터 세트 생성"""
        if strategy_name not in self._parameter_spaces:
            self._logger.error(f"알 수 없는 전략: {strategy_name}")
            return None
        
        parameters = {}
        for param_name, param_space in self._parameter_spaces[strategy_name].items():
            parameters[param_name] = param_space.generate_random_value()
        
        parameter_set = ParameterSet(parameters=parameters)
        return parameter_set
    
    def create_parameter_set(self, strategy_name: str, parameters: Dict[str, Any]) -> Optional[ParameterSet]:
        """파라미터 세트 생성 (검증 포함)"""
        if strategy_name not in self._parameter_spaces:
            self._logger.error(f"알 수 없는 전략: {strategy_name}")
            return None
        
        # 파라미터 검증
        validated_params = {}
        for param_name, value in parameters.items():
            param_space = self.get_parameter_space(strategy_name, param_name)
            if param_space is None:
                self._logger.warning(f"알 수 없는 파라미터: {param_name}")
                continue
            
            if not param_space.validate_value(value):
                self._logger.error(f"잘못된 파라미터 값: {param_name}={value}")
                return None
            
            validated_params[param_name] = value
        
        # 누락된 필수 파라미터 기본값으로 채우기
        for param_name, param_space in self._parameter_spaces[strategy_name].items():
            if param_name not in validated_params:
                if param_space.default_value is not None:
                    validated_params[param_name] = param_space.default_value
                else:
                    validated_params[param_name] = param_space.generate_random_value()
        
        parameter_set = ParameterSet(parameters=validated_params, validated=True)
        return parameter_set
    
    def add_parameter_set(self, parameter_set: ParameterSet):
        """파라미터 세트 추가"""
        self._parameter_sets.append(parameter_set)
        
        # 최고 성능 파라미터 업데이트
        if parameter_set.fitness_score is not None:
            if not self._best_parameters or parameter_set.fitness_score > self._best_parameters.get('fitness_score', 0):
                self._best_parameters = asdict(parameter_set)
        
        self._logger.debug(f"파라미터 세트 추가 (총 {len(self._parameter_sets)}개)")
    
    def get_best_parameters(self) -> Optional[ParameterSet]:
        """최고 성능 파라미터 조회"""
        if not self._best_parameters:
            return None
        
        # Dict를 ParameterSet 객체로 변환
        best_params = self._best_parameters.copy()
        if 'created_at' in best_params and isinstance(best_params['created_at'], str):
            best_params['created_at'] = datetime.fromisoformat(best_params['created_at'])
        
        return ParameterSet(**best_params)
    
    def get_parameter_sets_by_fitness(self, top_k: int = 10) -> List[ParameterSet]:
        """적합도 순으로 파라미터 세트 조회"""
        # 적합도가 있는 세트만 필터링
        fitted_sets = [ps for ps in self._parameter_sets if ps.fitness_score is not None]
        
        # 적합도 순으로 정렬
        fitted_sets.sort(key=lambda x: x.fitness_score, reverse=True)
        
        return fitted_sets[:top_k]
    
    def get_parameter_statistics(self, strategy_name: str) -> Dict[str, Any]:
        """파라미터 통계 정보"""
        if strategy_name not in self._parameter_spaces:
            return {}
        
        # 해당 전략의 파라미터 세트만 필터링
        strategy_sets = [
            ps for ps in self._parameter_sets 
            if ps.fitness_score is not None and all(
                param in ps.parameters for param in self._parameter_spaces[strategy_name].keys()
            )
        ]
        
        if not strategy_sets:
            return {"message": "분석할 데이터가 없습니다"}
        
        statistics = {
            "total_sets": len(strategy_sets),
            "avg_fitness": np.mean([ps.fitness_score for ps in strategy_sets]),
            "best_fitness": max(ps.fitness_score for ps in strategy_sets),
            "worst_fitness": min(ps.fitness_score for ps in strategy_sets),
            "parameter_ranges": {}
        }
        
        # 파라미터별 범위 분석
        for param_name in self._parameter_spaces[strategy_name].keys():
            values = [ps.parameters.get(param_name) for ps in strategy_sets if param_name in ps.parameters]
            if values:
                if isinstance(values[0], (int, float)):
                    statistics["parameter_ranges"][param_name] = {
                        "min": min(values),
                        "max": max(values),
                        "mean": np.mean(values),
                        "std": np.std(values)
                    }
                else:
                    # 범주형 데이터의 경우 빈도 분석
                    unique_values, counts = np.unique(values, return_counts=True)
                    statistics["parameter_ranges"][param_name] = {
                        "distribution": dict(zip(unique_values, counts.tolist()))
                    }
        
        return statistics
    
    def crossover_parameters(self, parent1: ParameterSet, parent2: ParameterSet, 
                           strategy_name: str) -> Optional[ParameterSet]:
        """파라미터 교차 (유전 알고리즘용)"""
        if strategy_name not in self._parameter_spaces:
            return None
        
        child_params = {}
        param_names = list(self._parameter_spaces[strategy_name].keys())
        
        # 균등 교차: 각 파라미터를 랜덤하게 부모 중 하나에서 선택
        for param_name in param_names:
            if np.random.random() < 0.5:
                if param_name in parent1.parameters:
                    child_params[param_name] = parent1.parameters[param_name]
                else:
                    child_params[param_name] = self._parameter_spaces[strategy_name][param_name].generate_random_value()
            else:
                if param_name in parent2.parameters:
                    child_params[param_name] = parent2.parameters[param_name]
                else:
                    child_params[param_name] = self._parameter_spaces[strategy_name][param_name].generate_random_value()
        
        return ParameterSet(parameters=child_params)
    
    def mutate_parameters(self, parameter_set: ParameterSet, strategy_name: str, 
                         mutation_rate: float = 0.1) -> Optional[ParameterSet]:
        """파라미터 변이 (유전 알고리즘용)"""
        if strategy_name not in self._parameter_spaces:
            return None
        
        mutated_params = parameter_set.parameters.copy()
        
        for param_name, param_space in self._parameter_spaces[strategy_name].items():
            if np.random.random() < mutation_rate:
                if param_space.param_type in [ParameterType.INTEGER, ParameterType.FLOAT]:
                    # 가우시안 변이
                    current_value = mutated_params.get(param_name, param_space.default_value)
                    if param_space.param_type == ParameterType.INTEGER:
                        mutation_std = max(1, (param_space.max_value - param_space.min_value) * 0.1)
                        new_value = int(np.random.normal(current_value, mutation_std))
                        new_value = max(param_space.min_value, min(param_space.max_value, new_value))
                    else:  # FLOAT
                        mutation_std = (param_space.max_value - param_space.min_value) * 0.1
                        new_value = np.random.normal(current_value, mutation_std)
                        new_value = max(param_space.min_value, min(param_space.max_value, new_value))
                    
                    mutated_params[param_name] = new_value
                else:
                    # 범주형 또는 불린형은 랜덤 값으로 변경
                    mutated_params[param_name] = param_space.generate_random_value()
        
        return ParameterSet(parameters=mutated_params)
    
    def export_parameters(self, filename: str = None) -> str:
        """파라미터 데이터 내보내기"""
        if filename is None:
            filename = f"parameters_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        export_data = {
            "parameter_spaces": {},
            "parameter_sets": [],
            "best_parameters": self._best_parameters,
            "export_timestamp": datetime.now().isoformat()
        }
        
        # 파라미터 공간 직렬화
        for strategy_name, param_spaces in self._parameter_spaces.items():
            export_data["parameter_spaces"][strategy_name] = {}
            for param_name, param_space in param_spaces.items():
                space_dict = asdict(param_space)
                space_dict['param_type'] = param_space.param_type.value
                export_data["parameter_spaces"][strategy_name][param_name] = space_dict
        
        # 파라미터 세트 직렬화
        for param_set in self._parameter_sets:
            set_dict = asdict(param_set)
            if param_set.created_at:
                set_dict['created_at'] = param_set.created_at.isoformat()
            export_data["parameter_sets"].append(set_dict)
        
        # 파일 저장
        filepath = os.path.join(self._data_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2, default=str)
        
        self._logger.info(f"파라미터 데이터 내보내기 완료: {filepath}")
        return filepath
    
    def _save_parameter_data(self):
        """파라미터 데이터 저장"""
        try:
            # 파라미터 세트 저장
            sets_data = []
            for param_set in self._parameter_sets:
                set_dict = asdict(param_set)
                if param_set.created_at:
                    set_dict['created_at'] = param_set.created_at.isoformat()
                sets_data.append(set_dict)
            
            sets_file = os.path.join(self._data_dir, "parameter_sets.json")
            with open(sets_file, 'w', encoding='utf-8') as f:
                json.dump(sets_data, f, ensure_ascii=False, indent=2, default=str)
            
            # 최고 파라미터 저장
            best_file = os.path.join(self._data_dir, "best_parameters.json")
            with open(best_file, 'w', encoding='utf-8') as f:
                json.dump(self._best_parameters, f, ensure_ascii=False, indent=2, default=str)
                
        except Exception as e:
            self._logger.error(f"파라미터 데이터 저장 실패: {e}")
    
    def _load_parameter_data(self):
        """파라미터 데이터 로드"""
        try:
            # 파라미터 세트 로드
            sets_file = os.path.join(self._data_dir, "parameter_sets.json")
            if os.path.exists(sets_file):
                with open(sets_file, 'r', encoding='utf-8') as f:
                    sets_data = json.load(f)
                
                for set_dict in sets_data:
                    if 'created_at' in set_dict and set_dict['created_at']:
                        set_dict['created_at'] = datetime.fromisoformat(set_dict['created_at'])
                    param_set = ParameterSet(**set_dict)
                    self._parameter_sets.append(param_set)
            
            # 최고 파라미터 로드
            best_file = os.path.join(self._data_dir, "best_parameters.json")
            if os.path.exists(best_file):
                with open(best_file, 'r', encoding='utf-8') as f:
                    self._best_parameters = json.load(f)
                    
            self._logger.info(f"파라미터 데이터 로드 완료: {len(self._parameter_sets)}개 세트")
            
        except Exception as e:
            self._logger.error(f"파라미터 데이터 로드 실패: {e}")

# 전역 인스턴스
_parameter_manager = None

def get_parameter_manager() -> ParameterManager:
    """파라미터 관리자 싱글톤 인스턴스 반환"""
    global _parameter_manager
    if _parameter_manager is None:
        _parameter_manager = ParameterManager()
    return _parameter_manager 