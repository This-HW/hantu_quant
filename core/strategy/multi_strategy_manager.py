#!/usr/bin/env python3
"""
멀티 전략 관리 시스템
시장 상황에 따라 최적 전략 자동 선택
"""

from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Optional
import pandas as pd

from core.utils.log_utils import get_logger

logger = get_logger(__name__)


class StrategyType(Enum):
    """전략 유형"""
    TREND_FOLLOWING = "trend_following"  # 추세 추종
    MEAN_REVERSION = "mean_reversion"    # 평균 회귀 (역추세)
    MOMENTUM = "momentum"                 # 모멘텀
    VALUE = "value"                       # 가치 투자
    BREAKOUT = "breakout"                 # 돌파 전략


class MarketRegime(Enum):
    """시장 체제"""
    BULL_TRENDING = "bull_trending"      # 강한 상승 추세
    BULL_VOLATILE = "bull_volatile"      # 변동성 높은 상승
    BEAR_TRENDING = "bear_trending"      # 강한 하락 추세
    BEAR_VOLATILE = "bear_volatile"      # 변동성 높은 하락
    SIDEWAYS_LOW_VOL = "sideways_low_vol"  # 횡보 (낮은 변동성)
    SIDEWAYS_HIGH_VOL = "sideways_high_vol"  # 횡보 (높은 변동성)


@dataclass
class StrategyConfig:
    """전략 설정"""
    strategy_type: StrategyType
    name: str
    description: str
    optimal_regimes: List[MarketRegime]  # 최적 시장 환경
    weight_multiplier: float = 1.0  # 가중치 배수

    # 선정 기준
    min_price_attractiveness: float = 70.0
    min_technical_score: float = 60.0
    max_risk_score: float = 35.0
    min_confidence: float = 0.6

    # 매매 설정
    stop_loss_pct: float = 0.05
    take_profit_pct: float = 0.10
    max_holding_days: int = 10


class MultiStrategyManager:
    """멀티 전략 관리자"""

    def __init__(self):
        self.logger = logger
        self.strategies = self._initialize_strategies()
        self.current_regime = None
        self.strategy_weights = {}

    def _initialize_strategies(self) -> Dict[StrategyType, StrategyConfig]:
        """전략 초기화"""
        return {
            StrategyType.TREND_FOLLOWING: StrategyConfig(
                strategy_type=StrategyType.TREND_FOLLOWING,
                name="추세 추종",
                description="강한 상승 추세 종목 매수",
                optimal_regimes=[MarketRegime.BULL_TRENDING, MarketRegime.BULL_VOLATILE],
                weight_multiplier=1.5,
                min_price_attractiveness=80.0,
                min_technical_score=70.0,
                max_risk_score=25.0,
                min_confidence=0.75,
                stop_loss_pct=0.03,
                take_profit_pct=0.08,
                max_holding_days=10
            ),

            StrategyType.MEAN_REVERSION: StrategyConfig(
                strategy_type=StrategyType.MEAN_REVERSION,
                name="평균 회귀",
                description="과매도 구간 반등 매수",
                optimal_regimes=[MarketRegime.SIDEWAYS_LOW_VOL, MarketRegime.SIDEWAYS_HIGH_VOL],
                weight_multiplier=1.0,
                min_price_attractiveness=75.0,
                min_technical_score=65.0,
                max_risk_score=30.0,
                min_confidence=0.65,
                stop_loss_pct=0.04,
                take_profit_pct=0.06,
                max_holding_days=5
            ),

            StrategyType.MOMENTUM: StrategyConfig(
                strategy_type=StrategyType.MOMENTUM,
                name="모멘텀",
                description="강한 모멘텀 종목 매수",
                optimal_regimes=[MarketRegime.BULL_TRENDING, MarketRegime.BULL_VOLATILE],
                weight_multiplier=1.3,
                min_price_attractiveness=85.0,
                min_technical_score=75.0,
                max_risk_score=30.0,
                min_confidence=0.70,
                stop_loss_pct=0.04,
                take_profit_pct=0.12,
                max_holding_days=15
            ),
        }

    def detect_market_regime(self, market_index_data: pd.DataFrame) -> MarketRegime:
        """시장 체제 감지

        Args:
            market_index_data: 시장 지수 데이터 (KOSPI)

        Returns:
            MarketRegime: 현재 시장 체제
        """
        try:
            # 1. 추세 판단 (MA20 기준)
            current_price = market_index_data['close'].iloc[-1]
            ma20 = market_index_data['close'].rolling(window=20).mean().iloc[-1]
            ma60 = market_index_data['close'].rolling(window=60).mean().iloc[-1]

            is_uptrend = current_price > ma20 > ma60
            is_downtrend = current_price < ma20 < ma60

            # 2. 변동성 판단 (ATR)
            high_low = market_index_data['high'] - market_index_data['low']
            atr = high_low.rolling(window=14).mean().iloc[-1]
            avg_atr = high_low.rolling(window=60).mean().iloc[-1]

            is_high_vol = atr > avg_atr * 1.2

            # 3. 체제 결정
            if is_uptrend:
                regime = MarketRegime.BULL_VOLATILE if is_high_vol else MarketRegime.BULL_TRENDING
            elif is_downtrend:
                regime = MarketRegime.BEAR_VOLATILE if is_high_vol else MarketRegime.BEAR_TRENDING
            else:
                regime = MarketRegime.SIDEWAYS_HIGH_VOL if is_high_vol else MarketRegime.SIDEWAYS_LOW_VOL

            self.current_regime = regime
            self.logger.info(f"시장 체제 감지: {regime.value}")

            return regime

        except Exception as e:
            self.logger.error(f"시장 체제 감지 실패: {e}", exc_info=True)
            return MarketRegime.SIDEWAYS_LOW_VOL

    def calculate_strategy_weights(self, regime: Optional[MarketRegime] = None) -> Dict[StrategyType, float]:
        """시장 체제에 따른 전략별 가중치 계산

        Args:
            regime: 시장 체제 (None이면 현재 체제 사용)

        Returns:
            Dict: 전략별 가중치 (합계 = 1.0)
        """
        if regime is None:
            regime = self.current_regime

        if regime is None:
            # 기본 균등 배분
            return {st: 1.0 / len(self.strategies) for st in self.strategies.keys()}

        weights = {}
        total_weight = 0.0

        for strategy_type, config in self.strategies.items():
            # 최적 체제에 속하면 가중치 증가
            if regime in config.optimal_regimes:
                weight = config.weight_multiplier
            else:
                weight = 0.3  # 비최적 환경에서는 가중치 감소

            weights[strategy_type] = weight
            total_weight += weight

        # 정규화 (합계 = 1.0)
        if total_weight > 0:
            weights = {st: w / total_weight for st, w in weights.items()}

        self.strategy_weights = weights
        self.logger.info(f"전략별 가중치: {weights}")

        return weights

    def select_strategy(self, market_index_data: pd.DataFrame) -> StrategyConfig:
        """현재 시장에 최적인 전략 선택

        Args:
            market_index_data: 시장 지수 데이터

        Returns:
            StrategyConfig: 선택된 전략 설정
        """
        # 1. 시장 체제 감지
        regime = self.detect_market_regime(market_index_data)

        # 2. 전략 가중치 계산
        weights = self.calculate_strategy_weights(regime)

        # 3. 가장 높은 가중치의 전략 선택
        best_strategy = max(weights.items(), key=lambda x: x[1])
        selected = self.strategies[best_strategy[0]]

        self.logger.info(f"선택된 전략: {selected.name} (가중치: {best_strategy[1]:.2%})")

        return selected

    def get_ensemble_stocks(
        self,
        candidate_stocks: List[Dict],
        market_index_data: pd.DataFrame,
        max_stocks: int = 10
    ) -> List[Dict]:
        """앙상블 방식으로 종목 선정

        여러 전략의 결과를 조합하여 최종 선정

        Args:
            candidate_stocks: 후보 종목 리스트
            market_index_data: 시장 지수 데이터
            max_stocks: 최대 선정 종목 수

        Returns:
            List[Dict]: 최종 선정 종목
        """
        # 1. 시장 체제 감지 및 가중치 계산
        regime = self.detect_market_regime(market_index_data)
        weights = self.calculate_strategy_weights(regime)

        # 2. 각 전략별로 종목 평가
        stock_scores = {}

        for stock in candidate_stocks:
            code = stock['stock_code']
            total_score = 0.0

            for strategy_type, weight in weights.items():
                config = self.strategies[strategy_type]

                # 전략별 기준 충족 여부 평가
                score = self._evaluate_stock_for_strategy(stock, config)
                total_score += score * weight

            stock_scores[code] = total_score
            stock['ensemble_score'] = total_score

        # 3. 점수 기준 정렬
        sorted_stocks = sorted(
            candidate_stocks,
            key=lambda x: x.get('ensemble_score', 0),
            reverse=True
        )

        # 4. 상위 종목 선정
        selected = sorted_stocks[:max_stocks]

        self.logger.info(f"앙상블 선정: {len(candidate_stocks)}개 → {len(selected)}개")

        return selected

    def _evaluate_stock_for_strategy(self, stock: Dict, config: StrategyConfig) -> float:
        """전략별 종목 평가 점수 (0-100)

        Args:
            stock: 종목 정보
            config: 전략 설정

        Returns:
            float: 평가 점수
        """
        score = 0.0
        max_score = 100.0

        # 1. 가격 매력도 (30%)
        price_attr = stock.get('price_attractiveness', 0)
        if price_attr >= config.min_price_attractiveness:
            score += (price_attr / 100) * 30

        # 2. 기술적 점수 (30%)
        tech_score = stock.get('technical_score', 0)
        if tech_score >= config.min_technical_score:
            score += (tech_score / 100) * 30

        # 3. 리스크 점수 (20% - 낮을수록 좋음)
        risk = stock.get('risk_score', 100)
        if risk <= config.max_risk_score:
            risk_score = (1 - risk / 100) * 20
            score += risk_score

        # 4. 신뢰도 (20%)
        confidence = stock.get('confidence', 0)
        if confidence >= config.min_confidence:
            score += (confidence * 20)

        return min(score, max_score)


def get_multi_strategy_manager() -> MultiStrategyManager:
    """MultiStrategyManager 싱글톤 인스턴스"""
    if not hasattr(get_multi_strategy_manager, '_instance'):
        get_multi_strategy_manager._instance = MultiStrategyManager()
    return get_multi_strategy_manager._instance
