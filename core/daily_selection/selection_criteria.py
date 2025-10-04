#!/usr/bin/env python3
"""
Phase 2: 선정 기준 관리 시스템
동적 필터링 기준 설정, 시장 상황별 기준 조정, 백테스트 기반 기준 최적화
"""

import os
import sys
import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, asdict, field
from enum import Enum
import logging
from copy import deepcopy

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.utils.log_utils import get_logger

logger = get_logger(__name__)

class MarketCondition(Enum):
    """시장 상황 열거형"""
    BULL_MARKET = "bull_market"
    BEAR_MARKET = "bear_market"
    SIDEWAYS = "sideways"
    VOLATILE = "volatile"
    RECOVERY = "recovery"

class CriteriaType(Enum):
    """기준 유형 열거형"""
    TECHNICAL = "technical"
    FUNDAMENTAL = "fundamental"
    VOLUME = "volume"
    RISK = "risk"
    SECTOR = "sector"
    MARKET_CAP = "market_cap"

@dataclass
class CriteriaRange:
    """기준 범위 데이터 클래스"""
    min_value: float
    max_value: float
    optimal_value: float
    weight: float = 1.0
    
    def is_valid(self, p_value: float) -> bool:
        """값이 유효 범위 내인지 확인"""
        return self.min_value <= p_value <= self.max_value
    
    def calculate_score(self, p_value: float) -> float:
        """값에 대한 점수 계산 (0-100)"""
        if not self.is_valid(p_value):
            return 0.0
        
        # 최적값에 가까울수록 높은 점수
        _v_distance = abs(p_value - self.optimal_value)
        _v_max_distance = max(
            abs(self.max_value - self.optimal_value),
            abs(self.min_value - self.optimal_value)
        )
        
        if _v_max_distance == 0:
            return 100.0
        
        _v_score = (1 - _v_distance / _v_max_distance) * 100
        return max(0.0, min(100.0, _v_score))

@dataclass
class SelectionCriteria:
    """선정 기준 데이터 클래스"""
    # 기본 정보
    name: str
    description: str
    market_condition: MarketCondition
    created_date: str
    version: str = "1.0.0"
    
    # 기술적 분석 기준 (보수적 버전: 더욱 엄격한 필터링)
    price_attractiveness: CriteriaRange = field(default_factory=lambda: CriteriaRange(80.0, 100.0, 90.0, 0.35))  # 75→80 (상위 20%만)
    technical_score: CriteriaRange = field(default_factory=lambda: CriteriaRange(70.0, 100.0, 85.0, 0.35))  # 60→70 (기술적 우위)
    volume_score: CriteriaRange = field(default_factory=lambda: CriteriaRange(60.0, 100.0, 80.0, 0.15))  # 50→60 (거래량 안정성)
    pattern_score: CriteriaRange = field(default_factory=lambda: CriteriaRange(50.0, 100.0, 75.0, 0.15))  # 40→50 (패턴 신뢰도)

    # 리스크 관리 기준 (보수적: 리스크 최소화)
    risk_score: CriteriaRange = field(default_factory=lambda: CriteriaRange(0.0, 25.0, 15.0, 0.4))  # 35→25 (더 낮은 리스크)
    volatility: CriteriaRange = field(default_factory=lambda: CriteriaRange(0.1, 0.3, 0.18, 0.25))  # 0.4→0.3 (변동성 제한)
    confidence: CriteriaRange = field(default_factory=lambda: CriteriaRange(0.75, 1.0, 0.85, 0.25))  # 0.65→0.75 (높은 신뢰도)
    max_drawdown: CriteriaRange = field(default_factory=lambda: CriteriaRange(0.0, 0.10, 0.05, 0.1))  # 0.15→0.10 (손실 제한)
    
    # 펀더멘털 기준
    market_cap: CriteriaRange = field(default_factory=lambda: CriteriaRange(500000000000, 1000000000000000, 5000000000000, 0.1))
    per_ratio: CriteriaRange = field(default_factory=lambda: CriteriaRange(0.0, 25.0, 15.0, 0.2))
    pbr_ratio: CriteriaRange = field(default_factory=lambda: CriteriaRange(0.0, 3.0, 1.5, 0.2))
    roe: CriteriaRange = field(default_factory=lambda: CriteriaRange(10.0, 50.0, 20.0, 0.3))
    debt_ratio: CriteriaRange = field(default_factory=lambda: CriteriaRange(0.0, 60.0, 30.0, 0.2))
    
    # 포트폴리오 관리 기준 (보수적: 분산 투자 + 작은 포지션)
    max_stocks: int = 10  # 12→10 (더 집중된 포트폴리오)
    max_sector_stocks: int = 2  # 섹터별 최대 2종목 유지
    max_position_size: float = 0.08  # 0.12→0.08 (종목당 8% 이하)
    min_position_size: float = 0.04  # 0.03→0.04 (최소 4%)
    rebalance_threshold: float = 0.05

    # 보수적 추가: 강화된 필터
    min_relative_strength: float = 0.75  # 0.7→0.75 (시장 대비 상위 25%)
    min_momentum_score: float = 70.0  # 60→70 (강한 모멘텀만)
    min_trend_strength: float = 0.7  # 추세 강도 (새로 추가)
    avoid_reversal_only: bool = True  # 역추세 전략만 사용 금지
    
    # 섹터 가중치
    sector_weights: Dict[str, float] = field(default_factory=lambda: {
        "기술": 0.3,
        "금융": 0.2,
        "제조": 0.2,
        "소비재": 0.15,
        "헬스케어": 0.1,
        "기타": 0.05
    })
    
    def to_dict(self) -> Dict:
        """딕셔너리로 변환"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, p_data: Dict) -> 'SelectionCriteria':
        """딕셔너리에서 생성"""
        # 중첩된 CriteriaRange 객체들을 올바르게 변환
        _v_criteria = cls(**p_data)
        
        # CriteriaRange 필드들을 올바르게 변환
        for field_name, field_value in p_data.items():
            if isinstance(field_value, dict) and 'min_value' in field_value:
                setattr(_v_criteria, field_name, CriteriaRange(**field_value))
        
        return _v_criteria

@dataclass
class CriteriaPerformance:
    """기준 성과 데이터 클래스"""
    criteria_name: str
    test_period: str
    total_trades: int
    win_rate: float
    avg_return: float
    max_drawdown: float
    sharpe_ratio: float
    sortino_ratio: float
    profit_factor: float
    
    # 섹터별 성과
    sector_performance: Dict[str, Dict] = field(default_factory=dict)
    
    # 월별 성과
    monthly_returns: List[float] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        """딕셔너리로 변환"""
        return asdict(self)

class CriteriaOptimizer:
    """기준 최적화 클래스"""
    
    def __init__(self):
        """초기화"""
        self._v_optimization_history = []
    
    def optimize_criteria(self, p_base_criteria: SelectionCriteria, 
                         p_historical_data: List[Dict],
                         p_optimization_periods: int = 12) -> SelectionCriteria:
        """기준 최적화 실행
        
        Args:
            p_base_criteria: 기본 기준
            p_historical_data: 과거 데이터
            p_optimization_periods: 최적화 기간 (개월)
            
        Returns:
            최적화된 기준
        """
        try:
            logger.info("기준 최적화 시작")
            
            # 최적화 파라미터 설정
            _v_param_ranges = self._define_optimization_ranges()
            
            # 유전 알고리즘 기반 최적화
            _v_best_criteria = self._genetic_algorithm_optimization(
                p_base_criteria, p_historical_data, _v_param_ranges
            )
            
            # 최적화 결과 검증
            _v_performance = self._evaluate_criteria_performance(_v_best_criteria, p_historical_data)
            
            logger.info(f"최적화 완료 - 승률: {_v_performance.win_rate:.2%}, 샤프비율: {_v_performance.sharpe_ratio:.2f}")
            
            return _v_best_criteria
            
        except Exception as e:
            logger.error(f"기준 최적화 오류: {e}")
            return p_base_criteria
    
    def _define_optimization_ranges(self) -> Dict[str, Tuple[float, float]]:
        """최적화 파라미터 범위 정의
        
        Returns:
            파라미터별 (최소값, 최대값) 딕셔너리
        """
        return {
            "price_attractiveness_min": (50.0, 80.0),
            "price_attractiveness_optimal": (70.0, 90.0),
            "technical_score_min": (40.0, 70.0),
            "technical_score_optimal": (60.0, 85.0),
            "volume_score_min": (30.0, 60.0),
            "volume_score_optimal": (50.0, 80.0),
            "risk_score_max": (30.0, 60.0),
            "confidence_min": (0.3, 0.7),
            "max_stocks": (10, 25),
            "max_sector_stocks": (2, 5)
        }
    
    def _genetic_algorithm_optimization(self, p_base_criteria: SelectionCriteria,
                                      p_historical_data: List[Dict],
                                      p_param_ranges: Dict) -> SelectionCriteria:
        """유전 알고리즘 기반 최적화
        
        Args:
            p_base_criteria: 기본 기준
            p_historical_data: 과거 데이터
            p_param_ranges: 파라미터 범위
            
        Returns:
            최적화된 기준
        """
        _v_population_size = 20
        _v_generations = 10
        _v_mutation_rate = 0.1
        
        # 초기 개체군 생성
        _v_population = self._create_initial_population(p_base_criteria, p_param_ranges, _v_population_size)
        
        for generation in range(_v_generations):
            # 적합도 평가
            _v_fitness_scores = []
            for individual in _v_population:
                _v_performance = self._evaluate_criteria_performance(individual, p_historical_data)
                _v_fitness = self._calculate_fitness(_v_performance)
                _v_fitness_scores.append(_v_fitness)
            
            # 선택, 교배, 돌연변이
            _v_population = self._evolve_population(_v_population, _v_fitness_scores, _v_mutation_rate)
            
            logger.info(f"세대 {generation + 1}: 최고 적합도 {max(_v_fitness_scores):.3f}")
        
        # 최고 개체 반환
        _v_best_index = np.argmax(_v_fitness_scores)
        return _v_population[_v_best_index]
    
    def _create_initial_population(self, p_base_criteria: SelectionCriteria,
                                 p_param_ranges: Dict, p_size: int) -> List[SelectionCriteria]:
        """초기 개체군 생성"""
        _v_population = []
        
        for _ in range(p_size):
            _v_individual = deepcopy(p_base_criteria)
            
            # 파라미터 랜덤 설정
            for param_name, (min_val, max_val) in p_param_ranges.items():
                if param_name == "price_attractiveness_min":
                    _v_individual.price_attractiveness.min_value = np.random.uniform(min_val, max_val)
                elif param_name == "price_attractiveness_optimal":
                    _v_individual.price_attractiveness.optimal_value = np.random.uniform(min_val, max_val)
                elif param_name == "technical_score_min":
                    _v_individual.technical_score.min_value = np.random.uniform(min_val, max_val)
                elif param_name == "technical_score_optimal":
                    _v_individual.technical_score.optimal_value = np.random.uniform(min_val, max_val)
                elif param_name == "volume_score_min":
                    _v_individual.volume_score.min_value = np.random.uniform(min_val, max_val)
                elif param_name == "volume_score_optimal":
                    _v_individual.volume_score.optimal_value = np.random.uniform(min_val, max_val)
                elif param_name == "risk_score_max":
                    _v_individual.risk_score.max_value = np.random.uniform(min_val, max_val)
                elif param_name == "confidence_min":
                    _v_individual.confidence.min_value = np.random.uniform(min_val, max_val)
                elif param_name == "max_stocks":
                    _v_individual.max_stocks = int(np.random.uniform(min_val, max_val))
                elif param_name == "max_sector_stocks":
                    _v_individual.max_sector_stocks = int(np.random.uniform(min_val, max_val))
            
            _v_population.append(_v_individual)
        
        return _v_population
    
    def _evaluate_criteria_performance(self, p_criteria: SelectionCriteria,
                                     p_historical_data: List[Dict]) -> CriteriaPerformance:
        """기준 성과 평가
        
        Args:
            p_criteria: 평가할 기준
            p_historical_data: 과거 데이터
            
        Returns:
            성과 평가 결과
        """
        # 더미 성과 계산 (실제로는 백테스트 실행)
        _v_total_trades = len(p_historical_data)
        _v_win_rate = 0.6 + np.random.normal(0, 0.1)  # 60% 기준 ±10%
        _v_avg_return = 0.08 + np.random.normal(0, 0.02)  # 8% 기준 ±2%
        _v_max_drawdown = 0.15 + np.random.normal(0, 0.05)  # 15% 기준 ±5%
        _v_sharpe_ratio = 1.2 + np.random.normal(0, 0.3)  # 1.2 기준 ±0.3
        
        return CriteriaPerformance(
            criteria_name=p_criteria.name,
            test_period="12M",
            total_trades=_v_total_trades,
            win_rate=max(0.0, min(1.0, _v_win_rate)),
            avg_return=_v_avg_return,
            max_drawdown=max(0.0, _v_max_drawdown),
            sharpe_ratio=_v_sharpe_ratio,
            sortino_ratio=_v_sharpe_ratio * 1.2,
            profit_factor=2.0 + np.random.normal(0, 0.5)
        )
    
    def _calculate_fitness(self, p_performance: CriteriaPerformance) -> float:
        """적합도 계산
        
        Args:
            p_performance: 성과 데이터
            
        Returns:
            적합도 점수
        """
        # 가중 점수 계산
        _v_fitness = (
            p_performance.win_rate * 0.3 +
            min(p_performance.avg_return, 0.5) * 0.3 +  # 최대 50% 제한
            max(0, 2.0 - p_performance.max_drawdown) * 0.2 +  # 드로우다운 페널티
            min(p_performance.sharpe_ratio, 3.0) / 3.0 * 0.2  # 샤프비율 정규화
        )
        
        return max(0.0, _v_fitness)
    
    def _evolve_population(self, p_population: List[SelectionCriteria],
                         p_fitness_scores: List[float], p_mutation_rate: float) -> List[SelectionCriteria]:
        """개체군 진화
        
        Args:
            p_population: 현재 개체군
            p_fitness_scores: 적합도 점수
            p_mutation_rate: 돌연변이 확률
            
        Returns:
            새로운 개체군
        """
        _v_new_population = []
        
        # 엘리트 선택 (상위 20% 보존)
        _v_elite_count = int(len(p_population) * 0.2)
        _v_elite_indices = np.argsort(p_fitness_scores)[-_v_elite_count:]
        
        for idx in _v_elite_indices:
            _v_new_population.append(deepcopy(p_population[idx]))
        
        # 나머지는 선택, 교배, 돌연변이로 생성
        while len(_v_new_population) < len(p_population):
            # 토너먼트 선택
            _v_parent1 = self._tournament_selection(p_population, p_fitness_scores)
            _v_parent2 = self._tournament_selection(p_population, p_fitness_scores)
            
            # 교배
            _v_child = self._crossover(_v_parent1, _v_parent2)
            
            # 돌연변이
            if np.random.random() < p_mutation_rate:
                _v_child = self._mutate(_v_child)
            
            _v_new_population.append(_v_child)
        
        return _v_new_population
    
    def _tournament_selection(self, p_population: List[SelectionCriteria],
                            p_fitness_scores: List[float], p_tournament_size: int = 3) -> SelectionCriteria:
        """토너먼트 선택"""
        _v_tournament_indices = np.random.choice(len(p_population), p_tournament_size, replace=False)
        _v_tournament_fitness = [p_fitness_scores[i] for i in _v_tournament_indices]
        _v_winner_idx = _v_tournament_indices[np.argmax(_v_tournament_fitness)]
        
        return deepcopy(p_population[_v_winner_idx])
    
    def _crossover(self, p_parent1: SelectionCriteria, p_parent2: SelectionCriteria) -> SelectionCriteria:
        """교배 연산"""
        _v_child = deepcopy(p_parent1)
        
        # 50% 확률로 부모2의 특성 상속
        if np.random.random() < 0.5:
            _v_child.price_attractiveness = deepcopy(p_parent2.price_attractiveness)
        if np.random.random() < 0.5:
            _v_child.technical_score = deepcopy(p_parent2.technical_score)
        if np.random.random() < 0.5:
            _v_child.volume_score = deepcopy(p_parent2.volume_score)
        if np.random.random() < 0.5:
            _v_child.risk_score = deepcopy(p_parent2.risk_score)
        if np.random.random() < 0.5:
            _v_child.confidence = deepcopy(p_parent2.confidence)
        
        return _v_child
    
    def _mutate(self, p_individual: SelectionCriteria) -> SelectionCriteria:
        """돌연변이 연산"""
        _v_mutated = deepcopy(p_individual)
        
        # 10% 확률로 각 파라미터 변경
        if np.random.random() < 0.1:
            _v_mutated.price_attractiveness.optimal_value += np.random.normal(0, 5)
            _v_mutated.price_attractiveness.optimal_value = max(60, min(95, _v_mutated.price_attractiveness.optimal_value))
        
        if np.random.random() < 0.1:
            _v_mutated.technical_score.optimal_value += np.random.normal(0, 5)
            _v_mutated.technical_score.optimal_value = max(50, min(90, _v_mutated.technical_score.optimal_value))
        
        if np.random.random() < 0.1:
            _v_mutated.confidence.min_value += np.random.normal(0, 0.1)
            _v_mutated.confidence.min_value = max(0.3, min(0.8, _v_mutated.confidence.min_value))
        
        return _v_mutated

class SelectionCriteriaManager:
    """선정 기준 관리 메인 클래스"""
    
    def __init__(self, p_criteria_dir: str = "data/criteria"):
        """초기화
        
        Args:
            p_criteria_dir: 기준 저장 디렉토리
        """
        self._v_criteria_dir = p_criteria_dir
        self._v_current_criteria = {}  # 시장 상황별 현재 기준
        self._v_optimizer = CriteriaOptimizer()
        
        # 디렉토리 생성
        os.makedirs(p_criteria_dir, exist_ok=True)
        
        # 기본 기준 로드
        self._load_default_criteria()
        
        logger.info("선정 기준 관리자 초기화 완료")
    
    def _load_default_criteria(self):
        """기본 기준 로드"""
        # 시장 상황별 기본 기준 생성
        for market_condition in MarketCondition:
            _v_criteria = self._create_default_criteria(market_condition)
            self._v_current_criteria[market_condition] = _v_criteria
    
    def _create_default_criteria(self, p_market_condition: MarketCondition) -> SelectionCriteria:
        """시장 상황별 기본 기준 생성
        
        Args:
            p_market_condition: 시장 상황
            
        Returns:
            기본 선정 기준
        """
        _v_base_criteria = SelectionCriteria(
            name=f"기본기준_{p_market_condition.value}",
            description=f"{p_market_condition.value} 시장 상황용 기본 선정 기준",
            market_condition=p_market_condition,
            created_date=datetime.now().strftime("%Y-%m-%d")
        )
        
        # 시장 상황별 기준 조정
        if p_market_condition == MarketCondition.BULL_MARKET:
            # 상승장: 기준 완화, 성장성 중시
            _v_base_criteria.price_attractiveness = CriteriaRange(60.0, 100.0, 75.0, 0.4)
            _v_base_criteria.risk_score = CriteriaRange(0.0, 60.0, 35.0, 0.25)
            _v_base_criteria.max_stocks = 20
            _v_base_criteria.max_sector_stocks = 4
            
        elif p_market_condition == MarketCondition.BEAR_MARKET:
            # 하락장: 기준 강화, 안정성 중시
            _v_base_criteria.price_attractiveness = CriteriaRange(75.0, 100.0, 85.0, 0.5)
            _v_base_criteria.risk_score = CriteriaRange(0.0, 35.0, 20.0, 0.4)
            _v_base_criteria.confidence = CriteriaRange(0.6, 1.0, 0.8, 0.4)
            _v_base_criteria.max_stocks = 10
            _v_base_criteria.max_sector_stocks = 2
            
        elif p_market_condition == MarketCondition.VOLATILE:
            # 변동성 장: 리스크 관리 강화
            _v_base_criteria.volatility = CriteriaRange(0.1, 0.3, 0.2, 0.3)
            _v_base_criteria.risk_score = CriteriaRange(0.0, 40.0, 25.0, 0.35)
            _v_base_criteria.max_position_size = 0.1
            _v_base_criteria.max_stocks = 12
            
        elif p_market_condition == MarketCondition.RECOVERY:
            # 회복장: 모멘텀 중시
            _v_base_criteria.technical_score = CriteriaRange(60.0, 100.0, 80.0, 0.4)
            _v_base_criteria.volume_score = CriteriaRange(50.0, 100.0, 75.0, 0.3)
            _v_base_criteria.max_stocks = 18
            
        return _v_base_criteria
    
    def get_criteria(self, p_market_condition: MarketCondition) -> SelectionCriteria:
        """시장 상황별 기준 조회
        
        Args:
            p_market_condition: 시장 상황
            
        Returns:
            선정 기준
        """
        return self._v_current_criteria.get(p_market_condition, self._v_current_criteria[MarketCondition.SIDEWAYS])
    
    def update_criteria(self, p_market_condition: MarketCondition, p_criteria: SelectionCriteria):
        """기준 업데이트
        
        Args:
            p_market_condition: 시장 상황
            p_criteria: 새로운 기준
        """
        self._v_current_criteria[p_market_condition] = p_criteria
        self._save_criteria(p_market_condition, p_criteria)
        
        logger.info(f"기준 업데이트 완료: {p_market_condition.value}")
    
    def optimize_criteria(self, p_market_condition: MarketCondition,
                         p_historical_data: List[Dict]) -> SelectionCriteria:
        """기준 최적화
        
        Args:
            p_market_condition: 시장 상황
            p_historical_data: 과거 데이터
            
        Returns:
            최적화된 기준
        """
        _v_current_criteria = self.get_criteria(p_market_condition)
        _v_optimized_criteria = self._v_optimizer.optimize_criteria(_v_current_criteria, p_historical_data)
        
        # 최적화된 기준으로 업데이트
        _v_optimized_criteria.name = f"최적화기준_{p_market_condition.value}_{datetime.now().strftime('%Y%m%d')}"
        _v_optimized_criteria.created_date = datetime.now().strftime("%Y-%m-%d")
        
        self.update_criteria(p_market_condition, _v_optimized_criteria)
        
        return _v_optimized_criteria
    
    def evaluate_criteria_performance(self, p_market_condition: MarketCondition,
                                    p_historical_data: List[Dict]) -> CriteriaPerformance:
        """기준 성과 평가
        
        Args:
            p_market_condition: 시장 상황
            p_historical_data: 과거 데이터
            
        Returns:
            성과 평가 결과
        """
        _v_criteria = self.get_criteria(p_market_condition)
        return self._v_optimizer._evaluate_criteria_performance(_v_criteria, p_historical_data)
    
    def _save_criteria(self, p_market_condition: MarketCondition, p_criteria: SelectionCriteria):
        """기준 저장
        
        Args:
            p_market_condition: 시장 상황
            p_criteria: 저장할 기준
        """
        try:
            _v_filename = f"criteria_{p_market_condition.value}.json"
            _v_filepath = os.path.join(self._v_criteria_dir, _v_filename)
            
            with open(_v_filepath, 'w', encoding='utf-8') as f:
                json.dump(p_criteria.to_dict(), f, ensure_ascii=False, indent=2)
            
            logger.info(f"기준 저장 완료: {_v_filepath}")
            
        except Exception as e:
            logger.error(f"기준 저장 실패: {e}")
    
    def load_criteria(self, p_market_condition: MarketCondition) -> Optional[SelectionCriteria]:
        """기준 로드
        
        Args:
            p_market_condition: 시장 상황
            
        Returns:
            로드된 기준 (실패 시 None)
        """
        try:
            _v_filename = f"criteria_{p_market_condition.value}.json"
            _v_filepath = os.path.join(self._v_criteria_dir, _v_filename)
            
            if not os.path.exists(_v_filepath):
                return None
            
            with open(_v_filepath, 'r', encoding='utf-8') as f:
                _v_data = json.load(f)
            
            return SelectionCriteria.from_dict(_v_data)
            
        except Exception as e:
            logger.error(f"기준 로드 실패: {e}")
            return None
    
    def get_all_criteria(self) -> Dict[MarketCondition, SelectionCriteria]:
        """모든 기준 조회
        
        Returns:
            시장 상황별 기준 딕셔너리
        """
        return self._v_current_criteria.copy()
    
    def create_custom_criteria(self, p_name: str, p_description: str,
                             p_market_condition: MarketCondition,
                             p_custom_params: Dict[str, Any]) -> SelectionCriteria:
        """사용자 정의 기준 생성
        
        Args:
            p_name: 기준 이름
            p_description: 기준 설명
            p_market_condition: 시장 상황
            p_custom_params: 사용자 정의 파라미터
            
        Returns:
            사용자 정의 기준
        """
        _v_base_criteria = self._create_default_criteria(p_market_condition)
        _v_base_criteria.name = p_name
        _v_base_criteria.description = p_description
        
        # 사용자 정의 파라미터 적용
        for param_name, param_value in p_custom_params.items():
            if hasattr(_v_base_criteria, param_name):
                setattr(_v_base_criteria, param_name, param_value)
        
        return _v_base_criteria
    
    def compare_criteria_performance(self, p_criteria_list: List[SelectionCriteria],
                                   p_historical_data: List[Dict]) -> List[CriteriaPerformance]:
        """기준 성과 비교
        
        Args:
            p_criteria_list: 비교할 기준 리스트
            p_historical_data: 과거 데이터
            
        Returns:
            성과 비교 결과 리스트
        """
        _v_performance_list = []
        
        for criteria in p_criteria_list:
            _v_performance = self._v_optimizer._evaluate_criteria_performance(criteria, p_historical_data)
            _v_performance_list.append(_v_performance)
        
        return _v_performance_list
    
    def get_criteria_summary(self) -> Dict[str, Any]:
        """기준 요약 정보 조회
        
        Returns:
            기준 요약 정보
        """
        _v_summary = {
            "total_criteria": len(self._v_current_criteria),
            "market_conditions": [condition.value for condition in self._v_current_criteria.keys()],
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "criteria_details": {}
        }
        
        for condition, criteria in self._v_current_criteria.items():
            _v_summary["criteria_details"][condition.value] = {
                "name": criteria.name,
                "max_stocks": criteria.max_stocks,
                "price_attractiveness_min": criteria.price_attractiveness.min_value,
                "risk_score_max": criteria.risk_score.max_value,
                "confidence_min": criteria.confidence.min_value
            }
        
        return _v_summary

if __name__ == "__main__":
    # 테스트 실행
    manager = SelectionCriteriaManager()
    
    # 기본 기준 조회
    bull_criteria = manager.get_criteria(MarketCondition.BULL_MARKET)
    print(f"상승장 기준: {bull_criteria.name}")
    print(f"최대 종목 수: {bull_criteria.max_stocks}")
    print(f"가격 매력도 최소값: {bull_criteria.price_attractiveness.min_value}")
    
    # 사용자 정의 기준 생성
    custom_criteria = manager.create_custom_criteria(
        "보수적_기준",
        "리스크를 최소화한 보수적 선정 기준",
        MarketCondition.SIDEWAYS,
        {
            "max_stocks": 8,
            "max_sector_stocks": 2,
            "max_position_size": 0.1
        }
    )
    
    print(f"\n사용자 정의 기준: {custom_criteria.name}")
    print(f"최대 종목 수: {custom_criteria.max_stocks}")
    print(f"최대 포지션 크기: {custom_criteria.max_position_size}")
    
    # 기준 요약 조회
    summary = manager.get_criteria_summary()
    print(f"\n기준 요약:")
    print(f"총 기준 수: {summary['total_criteria']}")
    print(f"시장 상황: {summary['market_conditions']}") 