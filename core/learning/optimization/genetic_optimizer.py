"""
유전 알고리즘 최적화기

유전 알고리즘을 사용하여 전략 파라미터를 최적화하는 시스템
"""

import numpy as np
import json
import os
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any, Callable
from dataclasses import dataclass, asdict
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor, as_completed

from ...utils.logging import get_logger
from .parameter_manager import ParameterManager, ParameterSet

logger = get_logger(__name__)

@dataclass
class GeneticConfig:
    """유전 알고리즘 설정"""
    population_size: int = 50          # 개체 수
    max_generations: int = 100         # 최대 세대 수
    crossover_rate: float = 0.8        # 교차 확률
    mutation_rate: float = 0.1         # 변이 확률
    elite_rate: float = 0.1            # 엘리트 비율
    tournament_size: int = 3           # 토너먼트 선택 크기
    convergence_threshold: float = 1e-6 # 수렴 임계값
    early_stopping_generations: int = 20 # 조기 종료 세대 수
    parallel_evaluation: bool = True    # 병렬 평가 사용
    max_workers: int = 4               # 병렬 작업자 수

@dataclass
class OptimizationResult:
    """최적화 결과"""
    best_parameters: ParameterSet
    best_fitness: float
    generation: int
    total_generations: int
    fitness_history: List[float]
    convergence_achieved: bool
    optimization_time: float
    final_population: List[ParameterSet]

class GeneticOptimizer:
    """유전 알고리즘 최적화기"""
    
    def __init__(self, parameter_manager: ParameterManager,
                 fitness_function: Callable[[ParameterSet], float],
                 config: GeneticConfig = None,
                 data_dir: str = "data/optimization"):
        """
        초기화
        
        Args:
            parameter_manager: 파라미터 관리자
            fitness_function: 적합도 평가 함수
            config: 유전 알고리즘 설정
            data_dir: 최적화 데이터 저장 디렉토리
        """
        self._logger = logger
        self._parameter_manager = parameter_manager
        self._fitness_function = fitness_function
        self._config = config or GeneticConfig()
        self._data_dir = data_dir
        
        # 디렉토리 생성
        os.makedirs(data_dir, exist_ok=True)
        
        # 최적화 기록
        self._optimization_history = []
        
        # 현재 최적화 상태
        self._current_generation = 0
        self._population = []
        self._fitness_history = []
        self._best_individual = None
        self._best_fitness = float('-inf')
        
        self._logger.info("유전 알고리즘 최적화기 초기화 완료")
    
    def optimize(self, strategy_name: str, target_fitness: float = None) -> OptimizationResult:
        """
        파라미터 최적화 수행
        
        Args:
            strategy_name: 최적화할 전략명
            target_fitness: 목표 적합도 (달성시 조기 종료)
        
        Returns:
            OptimizationResult: 최적화 결과
        """
        start_time = datetime.now()
        self._logger.info(f"유전 알고리즘 최적화 시작: {strategy_name}")
        
        # 초기화
        self._current_generation = 0
        self._fitness_history = []
        self._best_individual = None
        self._best_fitness = float('-inf')
        
        # 초기 개체군 생성
        self._population = self._initialize_population(strategy_name)
        if not self._population:
            raise ValueError(f"초기 개체군 생성 실패: {strategy_name}")
        
        # 초기 개체군 평가
        self._evaluate_population()
        
        convergence_counter = 0
        convergence_achieved = False
        
        # 진화 과정
        for generation in range(self._config.max_generations):
            self._current_generation = generation
            
            # 새로운 세대 생성
            new_population = self._create_new_generation(strategy_name)
            
            # 개체군 교체
            self._population = new_population
            
            # 개체군 평가
            self._evaluate_population()
            
            # 진행 상황 로깅
            current_best = max(ind.fitness_score for ind in self._population if ind.fitness_score is not None)
            avg_fitness = np.mean([ind.fitness_score for ind in self._population if ind.fitness_score is not None])
            
            self._logger.info(f"세대 {generation}: 최고={current_best:.6f}, 평균={avg_fitness:.6f}")
            
            # 목표 적합도 달성 체크
            if target_fitness and current_best >= target_fitness:
                self._logger.info(f"목표 적합도 달성: {current_best:.6f} >= {target_fitness:.6f}")
                convergence_achieved = True
                break
            
            # 수렴 체크
            if len(self._fitness_history) > 1:
                improvement = abs(self._fitness_history[-1] - self._fitness_history[-2])
                if improvement < self._config.convergence_threshold:
                    convergence_counter += 1
                else:
                    convergence_counter = 0
                
                if convergence_counter >= self._config.early_stopping_generations:
                    self._logger.info(f"조기 수렴 감지: {convergence_counter}세대 동안 개선 없음")
                    convergence_achieved = True
                    break
        
        # 최적화 완료
        end_time = datetime.now()
        optimization_time = (end_time - start_time).total_seconds()
        
        # 결과 생성
        result = OptimizationResult(
            best_parameters=self._best_individual,
            best_fitness=self._best_fitness,
            generation=self._current_generation,
            total_generations=self._config.max_generations,
            fitness_history=self._fitness_history.copy(),
            convergence_achieved=convergence_achieved,
            optimization_time=optimization_time,
            final_population=self._population.copy()
        )
        
        # 최적화 기록 저장
        self._optimization_history.append(result)
        self._save_optimization_results(result, strategy_name)
        
        self._logger.info(f"유전 알고리즘 최적화 완료: {optimization_time:.2f}초, 최고 적합도: {self._best_fitness:.6f}")
        return result
    
    def _initialize_population(self, strategy_name: str) -> List[ParameterSet]:
        """초기 개체군 생성"""
        population = []
        
        # 기존 최고 파라미터가 있다면 포함
        best_params = self._parameter_manager.get_best_parameters()
        if best_params:
            population.append(best_params)
            self._logger.info("기존 최고 파라미터를 초기 개체군에 포함")
        
        # 기존 상위 파라미터들 포함
        top_parameters = self._parameter_manager.get_parameter_sets_by_fitness(
            top_k=min(10, self._config.population_size // 4)
        )
        population.extend(top_parameters)
        
        # 나머지는 랜덤 생성
        while len(population) < self._config.population_size:
            random_params = self._parameter_manager.create_random_parameter_set(strategy_name)
            if random_params:
                population.append(random_params)
        
        # 개체군 크기 조정
        population = population[:self._config.population_size]
        
        self._logger.info(f"초기 개체군 생성 완료: {len(population)}개 개체")
        return population
    
    def _evaluate_population(self):
        """개체군 평가"""
        if self._config.parallel_evaluation:
            self._evaluate_population_parallel()
        else:
            self._evaluate_population_sequential()
        
        # 최고 개체 업데이트
        for individual in self._population:
            if individual.fitness_score is not None and individual.fitness_score > self._best_fitness:
                self._best_fitness = individual.fitness_score
                self._best_individual = individual
                
                # 파라미터 매니저에도 등록
                self._parameter_manager.add_parameter_set(individual)
        
        # 적합도 기록
        if self._population:
            current_best = max(ind.fitness_score for ind in self._population if ind.fitness_score is not None)
            self._fitness_history.append(current_best)
    
    def _evaluate_population_sequential(self):
        """순차 개체군 평가"""
        for individual in self._population:
            if individual.fitness_score is None:
                try:
                    individual.fitness_score = self._fitness_function(individual)
                except Exception as e:
                    self._logger.error(f"적합도 평가 실패: {e}")
                    individual.fitness_score = 0.0
    
    def _evaluate_population_parallel(self):
        """병렬 개체군 평가"""
        unevaluated_individuals = [ind for ind in self._population if ind.fitness_score is None]
        
        if not unevaluated_individuals:
            return
        
        try:
            with ProcessPoolExecutor(max_workers=self._config.max_workers) as executor:
                # 평가 작업 제출
                future_to_individual = {
                    executor.submit(self._fitness_function, individual): individual
                    for individual in unevaluated_individuals
                }
                
                # 결과 수집
                for future in as_completed(future_to_individual):
                    individual = future_to_individual[future]
                    try:
                        individual.fitness_score = future.result()
                    except Exception as e:
                        self._logger.error(f"병렬 적합도 평가 실패: {e}")
                        individual.fitness_score = 0.0
                        
        except Exception as e:
            self._logger.warning(f"병렬 평가 실패, 순차 평가로 전환: {e}")
            self._evaluate_population_sequential()
    
    def _create_new_generation(self, strategy_name: str) -> List[ParameterSet]:
        """새로운 세대 생성"""
        new_population = []
        
        # 엘리트 선택
        elite_count = int(self._config.population_size * self._config.elite_rate)
        elites = self._select_elites(elite_count)
        new_population.extend(elites)
        
        # 교차와 변이로 나머지 개체 생성
        while len(new_population) < self._config.population_size:
            # 부모 선택
            parent1 = self._tournament_selection()
            parent2 = self._tournament_selection()
            
            # 교차
            if np.random.random() < self._config.crossover_rate:
                child = self._parameter_manager.crossover_parameters(parent1, parent2, strategy_name)
                if child is None:
                    child = self._parameter_manager.create_random_parameter_set(strategy_name)
            else:
                child = parent1 if np.random.random() < 0.5 else parent2
            
            # 변이
            if np.random.random() < self._config.mutation_rate:
                child = self._parameter_manager.mutate_parameters(child, strategy_name, self._config.mutation_rate)
                if child is None:
                    child = self._parameter_manager.create_random_parameter_set(strategy_name)
            
            # 적합도 초기화 (재평가 필요)
            child.fitness_score = None
            new_population.append(child)
        
        return new_population[:self._config.population_size]
    
    def _select_elites(self, count: int) -> List[ParameterSet]:
        """엘리트 선택"""
        # 적합도 순으로 정렬
        sorted_population = sorted(
            [ind for ind in self._population if ind.fitness_score is not None],
            key=lambda x: x.fitness_score,
            reverse=True
        )
        
        return sorted_population[:count]
    
    def _tournament_selection(self) -> ParameterSet:
        """토너먼트 선택"""
        # 평가된 개체들만 선택 대상
        evaluated_population = [ind for ind in self._population if ind.fitness_score is not None]
        
        if len(evaluated_population) < self._config.tournament_size:
            tournament_size = len(evaluated_population)
        else:
            tournament_size = self._config.tournament_size
        
        # 토너먼트 참가자 랜덤 선택
        tournament_participants = np.random.choice(
            evaluated_population, 
            size=tournament_size, 
            replace=False
        )
        
        # 토너먼트 승자 선택 (최고 적합도)
        winner = max(tournament_participants, key=lambda x: x.fitness_score)
        return winner
    
    def get_optimization_summary(self) -> Dict[str, Any]:
        """최적화 요약 정보"""
        if not self._optimization_history:
            return {"message": "최적화 기록이 없습니다"}
        
        latest_result = self._optimization_history[-1]
        
        summary = {
            "total_optimizations": len(self._optimization_history),
            "latest_optimization": {
                "best_fitness": latest_result.best_fitness,
                "generations_completed": latest_result.generation + 1,
                "convergence_achieved": latest_result.convergence_achieved,
                "optimization_time": latest_result.optimization_time,
                "improvement_over_generations": latest_result.fitness_history[-1] - latest_result.fitness_history[0] if len(latest_result.fitness_history) > 1 else 0
            },
            "best_parameters": asdict(latest_result.best_parameters) if latest_result.best_parameters else None,
            "configuration": asdict(self._config)
        }
        
        return summary
    
    def plot_fitness_evolution(self, save_path: str = None) -> str:
        """적합도 진화 그래프 생성"""
        try:
            import matplotlib.pyplot as plt
            
            if not self._fitness_history:
                return "그래프를 생성할 적합도 기록이 없습니다"
            
            plt.figure(figsize=(10, 6))
            plt.plot(self._fitness_history, 'b-', linewidth=2, label='최고 적합도')
            plt.xlabel('세대')
            plt.ylabel('적합도')
            plt.title('유전 알고리즘 적합도 진화')
            plt.grid(True, alpha=0.3)
            plt.legend()
            
            # 저장
            if save_path is None:
                save_path = os.path.join(self._data_dir, f"fitness_evolution_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            plt.close()
            
            self._logger.info(f"적합도 진화 그래프 저장: {save_path}")
            return save_path
            
        except ImportError:
            return "matplotlib이 설치되지 않아 그래프를 생성할 수 없습니다"
        except Exception as e:
            self._logger.error(f"그래프 생성 실패: {e}")
            return f"그래프 생성 실패: {e}"
    
    def _save_optimization_results(self, result: OptimizationResult, strategy_name: str):
        """최적화 결과 저장"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # 결과 데이터 직렬화
            result_data = {
                "strategy_name": strategy_name,
                "timestamp": timestamp,
                "best_fitness": result.best_fitness,
                "generation": result.generation,
                "total_generations": result.total_generations,
                "convergence_achieved": result.convergence_achieved,
                "optimization_time": result.optimization_time,
                "fitness_history": result.fitness_history,
                "config": asdict(self._config)
            }
            
            # 최고 파라미터 추가
            if result.best_parameters:
                result_data["best_parameters"] = asdict(result.best_parameters)
                if result.best_parameters.created_at:
                    result_data["best_parameters"]["created_at"] = result.best_parameters.created_at.isoformat()
            
            # 최종 개체군 (상위 10개만)
            top_individuals = sorted(
                [ind for ind in result.final_population if ind.fitness_score is not None],
                key=lambda x: x.fitness_score,
                reverse=True
            )[:10]
            
            result_data["top_final_population"] = []
            for individual in top_individuals:
                ind_data = asdict(individual)
                if individual.created_at:
                    ind_data["created_at"] = individual.created_at.isoformat()
                result_data["top_final_population"].append(ind_data)
            
            # 파일 저장
            filename = f"optimization_{strategy_name}_{timestamp}.json"
            filepath = os.path.join(self._data_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(result_data, f, ensure_ascii=False, indent=2, default=str)
            
            self._logger.info(f"최적화 결과 저장: {filepath}")
            
        except Exception as e:
            self._logger.error(f"최적화 결과 저장 실패: {e}")

# 전역 인스턴스
_genetic_optimizer = None

def get_genetic_optimizer(parameter_manager: ParameterManager, 
                         fitness_function: Callable[[ParameterSet], float]) -> GeneticOptimizer:
    """유전 알고리즘 최적화기 싱글톤 인스턴스 반환"""
    global _genetic_optimizer
    if _genetic_optimizer is None:
        _genetic_optimizer = GeneticOptimizer(parameter_manager, fitness_function)
    return _genetic_optimizer 