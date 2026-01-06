"""
Phase 4: AI 학습 시스템 - 유전 알고리즘 최적화기

유전 알고리즘을 사용한 파라미터 자동 최적화
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any, Callable
from datetime import datetime
import random
import copy
from dataclasses import dataclass
import time

from core.utils.log_utils import get_logger
from .parameter_manager import ParameterManager, ParameterSet, OptimizationResult

logger = get_logger(__name__)

@dataclass
class GeneticConfig:
    """유전 알고리즘 설정 클래스"""
    population_size: int = 50
    generations: int = 100
    crossover_rate: float = 0.8
    mutation_rate: float = 0.1
    elite_size: int = 5
    tournament_size: int = 3
    convergence_patience: int = 20
    early_stopping: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'population_size': self.population_size,
            'generations': self.generations,
            'crossover_rate': self.crossover_rate,
            'mutation_rate': self.mutation_rate,
            'elite_size': self.elite_size,
            'tournament_size': self.tournament_size,
            'convergence_patience': self.convergence_patience,
            'early_stopping': self.early_stopping
        }

class GeneticOptimizer:
    """유전 알고리즘 최적화기"""
    
    def __init__(self, parameter_manager: ParameterManager, config: Optional[GeneticConfig] = None):
        """초기화
        
        Args:
            parameter_manager: 파라미터 관리자
            config: 유전 알고리즘 설정
        """
        self._logger = logger
        self._param_manager = parameter_manager
        self._config = config or GeneticConfig()
        
        # 최적화 상태
        self._current_generation = 0
        self._best_fitness_history = []
        self._population = []
        self._fitness_scores = []
        
        # 컨버전스 추적
        self._no_improvement_count = 0
        self._best_fitness = -np.inf
        
        self._logger.info("GeneticOptimizer 초기화 완료")
    
    def optimize(self, component: str, max_evaluations: Optional[int] = None) -> OptimizationResult:
        """유전 알고리즘 최적화 실행
        
        Args:
            component: 최적화할 컴포넌트 이름
            max_evaluations: 최대 평가 횟수
            
        Returns:
            OptimizationResult: 최적화 결과
        """
        try:
            self._logger.info(f"유전 알고리즘 최적화 시작: {component}")
            start_time = time.time()
            
            # 초기화
            self._reset_optimization_state()
            
            # 초기 집단 생성
            self._initialize_population(component)
            
            # 초기 집단 평가
            self._evaluate_population(component)
            
            all_tested_parameters = []
            total_evaluations = 0
            
            # 세대 진화
            for generation in range(self._config.generations):
                self._current_generation = generation
                
                # 선택, 교차, 돌연변이
                new_population = self._evolve_population(component)
                self._population = new_population
                
                # 새로운 집단 평가
                self._evaluate_population(component)
                
                # 통계 업데이트
                best_fitness = max(self._fitness_scores)
                self._best_fitness_history.append(best_fitness)
                
                # 모든 테스트된 파라미터 기록
                for i, individual in enumerate(self._population):
                    param_set = ParameterSet(
                        name=component,
                        parameters=individual.copy(),
                        performance_score=self._fitness_scores[i],
                        optimization_method="genetic_algorithm",
                        created_at=datetime.now().isoformat()
                    )
                    all_tested_parameters.append(param_set)
                
                total_evaluations += len(self._population)
                
                # 개선 확인
                if best_fitness > self._best_fitness:
                    self._best_fitness = best_fitness
                    self._no_improvement_count = 0
                else:
                    self._no_improvement_count += 1
                
                # 로그 출력
                if generation % 10 == 0:
                    self._logger.info(f"세대 {generation}: 최고 적합도 {best_fitness:.4f}")
                
                # 조기 종료 확인
                if (self._config.early_stopping and 
                    self._no_improvement_count >= self._config.convergence_patience):
                    self._logger.info(f"조기 종료: {self._config.convergence_patience}세대 개선 없음")
                    break
                
                # 최대 평가 횟수 확인
                if max_evaluations and total_evaluations >= max_evaluations:
                    self._logger.info(f"최대 평가 횟수 도달: {max_evaluations}")
                    break
            
            # 최적 결과 추출
            best_idx = np.argmax(self._fitness_scores)
            best_parameters = ParameterSet(
                name=component,
                parameters=self._population[best_idx].copy(),
                performance_score=self._fitness_scores[best_idx],
                optimization_method="genetic_algorithm",
                created_at=datetime.now().isoformat(),
                is_best=True
            )
            
            optimization_time = time.time() - start_time
            
            # 결과 구성
            result = OptimizationResult(
                method="genetic_algorithm",
                best_parameters=best_parameters,
                all_tested_parameters=all_tested_parameters,
                total_evaluations=total_evaluations,
                optimization_time=optimization_time,
                convergence_iteration=self._current_generation
            )
            
            self._logger.info(f"유전 알고리즘 최적화 완료: 최고 점수 {best_parameters.performance_score:.4f}")
            return result
            
        except Exception as e:
            self._logger.error(f"유전 알고리즘 최적화 오류: {e}", exc_info=True)
            # 빈 결과 반환
            return OptimizationResult(
                method="genetic_algorithm",
                best_parameters=ParameterSet(name=component, parameters={}),
                all_tested_parameters=[],
                total_evaluations=0,
                optimization_time=0.0
            )
    
    def _reset_optimization_state(self):
        """최적화 상태 리셋"""
        self._current_generation = 0
        self._best_fitness_history = []
        self._population = []
        self._fitness_scores = []
        self._no_improvement_count = 0
        self._best_fitness = -np.inf
    
    def _initialize_population(self, component: str):
        """초기 집단 생성"""
        try:
            self._population = []
            
            # 기본 파라미터 포함
            default_params = self._param_manager.get_default_parameters(component)
            if default_params:
                self._population.append(default_params)
            
            # 최적 파라미터 포함 (있다면)
            best_params = self._param_manager.get_best_parameters(component)
            if best_params:
                self._population.append(best_params.parameters)
            
            # 나머지는 랜덤 생성
            while len(self._population) < self._config.population_size:
                random_params = self._param_manager.generate_random_parameters(component)
                if random_params:
                    self._population.append(random_params)
            
            self._logger.debug(f"초기 집단 생성 완료: {len(self._population)}개 개체")
            
        except Exception as e:
            self._logger.error(f"초기 집단 생성 오류: {e}", exc_info=True)
    
    def _evaluate_population(self, component: str):
        """집단 평가"""
        try:
            self._fitness_scores = []
            
            for individual in self._population:
                score = self._param_manager.evaluate_parameters(component, individual)
                if score is not None:
                    self._fitness_scores.append(score)
                else:
                    self._fitness_scores.append(0.0)  # 실패한 경우 최저 점수
            
        except Exception as e:
            self._logger.error(f"집단 평가 오류: {e}", exc_info=True)
            self._fitness_scores = [0.0] * len(self._population)
    
    def _evolve_population(self, component: str) -> List[Dict[str, Any]]:
        """집단 진화 (선택, 교차, 돌연변이)"""
        try:
            new_population = []
            
            # 엘리트 선택 (상위 개체 보존)
            elite_indices = np.argsort(self._fitness_scores)[-self._config.elite_size:]
            for idx in elite_indices:
                new_population.append(self._population[idx].copy())
            
            # 나머지 개체 생성
            while len(new_population) < self._config.population_size:
                # 부모 선택 (토너먼트 선택)
                parent1 = self._tournament_selection()
                parent2 = self._tournament_selection()
                
                # 교차
                if random.random() < self._config.crossover_rate:
                    child1, child2 = self._crossover(component, parent1, parent2)
                else:
                    child1, child2 = parent1.copy(), parent2.copy()
                
                # 돌연변이
                if random.random() < self._config.mutation_rate:
                    child1 = self._mutate(component, child1)
                if random.random() < self._config.mutation_rate:
                    child2 = self._mutate(component, child2)
                
                new_population.extend([child1, child2])
            
            # 집단 크기 조정
            return new_population[:self._config.population_size]
            
        except Exception as e:
            self._logger.error(f"집단 진화 오류: {e}", exc_info=True)
            return self._population.copy()
    
    def _tournament_selection(self) -> Dict[str, Any]:
        """토너먼트 선택"""
        try:
            # 랜덤하게 토너먼트 참가자 선택
            tournament_indices = random.sample(
                range(len(self._population)), 
                min(self._config.tournament_size, len(self._population))
            )
            
            # 가장 적합한 개체 선택
            best_idx = max(tournament_indices, key=lambda i: self._fitness_scores[i])
            
            return self._population[best_idx].copy()
            
        except Exception as e:
            self._logger.error(f"토너먼트 선택 오류: {e}", exc_info=True)
            return random.choice(self._population).copy()
    
    def _crossover(self, component: str, parent1: Dict[str, Any], 
                  parent2: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """교차 연산"""
        try:
            child1, child2 = parent1.copy(), parent2.copy()
            
            # 파라미터별 교차
            for param_name in parent1.keys():
                if param_name in parent2 and random.random() < 0.5:
                    child1[param_name], child2[param_name] = child2[param_name], child1[param_name]
            
            return child1, child2
            
        except Exception as e:
            self._logger.error(f"교차 연산 오류: {e}", exc_info=True)
            return parent1.copy(), parent2.copy()
    
    def _mutate(self, component: str, individual: Dict[str, Any]) -> Dict[str, Any]:
        """돌연변이 연산"""
        try:
            mutated = individual.copy()
            param_space = self._param_manager.get_parameter_space(component)
            
            # 랜덤하게 하나 이상의 파라미터 변경
            params_to_mutate = random.sample(
                list(mutated.keys()), 
                max(1, int(len(mutated) * 0.3))
            )
            
            for param_name in params_to_mutate:
                if param_name not in param_space:
                    continue
                
                param_config = param_space[param_name]
                param_type = param_config.get('type')
                
                if param_type == 'int':
                    low, high = param_config['range']
                    mutated[param_name] = random.randint(low, high)
                
                elif param_type == 'float':
                    low, high = param_config['range']
                    # 현재 값 기준으로 가우시안 변형
                    current_val = mutated[param_name]
                    std = (high - low) * 0.1  # 표준편차는 범위의 10%
                    new_val = np.random.normal(current_val, std)
                    mutated[param_name] = np.clip(new_val, low, high)
                
                elif param_type == 'choice':
                    choices = param_config['choices']
                    mutated[param_name] = random.choice(choices)
            
            return mutated
            
        except Exception as e:
            self._logger.error(f"돌연변이 연산 오류: {e}", exc_info=True)
            return individual.copy()
    
    def get_optimization_progress(self) -> Dict[str, Any]:
        """최적화 진행 상황 조회
        
        Returns:
            Dict[str, Any]: 진행 상황 정보
        """
        return {
            'current_generation': self._current_generation,
            'total_generations': self._config.generations,
            'population_size': len(self._population),
            'best_fitness_history': self._best_fitness_history.copy(),
            'current_best_fitness': max(self._fitness_scores) if self._fitness_scores else 0.0,
            'no_improvement_count': self._no_improvement_count,
            'convergence_patience': self._config.convergence_patience,
            'config': self._config.to_dict()
        }
    
    def update_config(self, config: GeneticConfig):
        """설정 업데이트
        
        Args:
            config: 새로운 설정
        """
        self._config = config
        self._logger.info("유전 알고리즘 설정 업데이트 완료")
    
    def get_population_diversity(self) -> float:
        """집단 다양성 계산
        
        Returns:
            float: 다양성 점수 (0-1)
        """
        try:
            if not self._population or len(self._population) < 2:
                return 0.0
            
            # 파라미터별 표준편차 계산
            diversity_scores = []
            
            param_names = list(self._population[0].keys())
            
            for param_name in param_names:
                values = [individual.get(param_name, 0) for individual in self._population]
                
                # 숫자형 파라미터의 경우 표준편차 계산
                if all(isinstance(v, (int, float)) for v in values):
                    if len(set(values)) > 1:
                        std = np.std(values)
                        mean_val = np.mean(values)
                        if mean_val != 0:
                            cv = std / abs(mean_val)  # 변동계수
                            diversity_scores.append(min(cv, 1.0))
                else:
                    # 범주형 파라미터의 경우 고유값 비율
                    unique_ratio = len(set(values)) / len(values)
                    diversity_scores.append(unique_ratio)
            
            return np.mean(diversity_scores) if diversity_scores else 0.0
            
        except Exception as e:
            self._logger.error(f"집단 다양성 계산 오류: {e}", exc_info=True)
            return 0.0 