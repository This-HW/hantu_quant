#!/usr/bin/env python3
"""
멀티 팩터 스코어링 시스템
7개 독립 팩터를 결합하여 종합 점수 계산
- 모멘텀 팩터
- 밸류 팩터
- 퀄리티 팩터
- 거래량 팩터
- 변동성 팩터
- 기술적 팩터
- 시장 강도 팩터
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from scipy import stats
import logging

from core.utils.log_utils import get_logger

logger = get_logger(__name__)


@dataclass
class FactorScores:
    """팩터별 점수"""
    stock_code: str
    stock_name: str

    # 7개 팩터 점수 (0-100)
    momentum_score: float
    value_score: float
    quality_score: float
    volume_score: float
    volatility_score: float
    technical_score: float
    market_strength_score: float

    # 종합 점수
    composite_score: float

    # Z-score (정규화된 점수)
    momentum_zscore: float
    value_zscore: float
    quality_zscore: float
    volume_zscore: float
    volatility_zscore: float
    technical_zscore: float
    market_strength_zscore: float


class MultiFactorScorer:
    """멀티 팩터 스코어링 시스템"""

    def __init__(self):
        """초기화"""
        self.logger = logger

        # 팩터 가중치 (합 = 1.0)
        self.factor_weights = {
            'momentum': 0.20,       # 모멘텀
            'value': 0.15,          # 밸류
            'quality': 0.20,        # 퀄리티
            'volume': 0.15,         # 거래량
            'volatility': 0.10,     # 변동성 (낮을수록 좋음)
            'technical': 0.15,      # 기술적
            'market_strength': 0.05 # 시장 강도
        }

    def calculate_multi_factor_scores(self, stock_data_list: List[Dict]) -> List[FactorScores]:
        """멀티 팩터 점수 계산

        Args:
            stock_data_list: 종목 데이터 리스트

        Returns:
            팩터 점수 리스트
        """
        try:
            if not stock_data_list:
                return []

            self.logger.info(f"멀티 팩터 스코어링 시작: {len(stock_data_list)}개 종목")

            # 1. 각 팩터별 원시 점수 계산
            momentum_scores = [self._calculate_momentum_factor(s) for s in stock_data_list]
            value_scores = [self._calculate_value_factor(s) for s in stock_data_list]
            quality_scores = [self._calculate_quality_factor(s) for s in stock_data_list]
            volume_scores = [self._calculate_volume_factor(s) for s in stock_data_list]
            volatility_scores = [self._calculate_volatility_factor(s) for s in stock_data_list]
            technical_scores = [self._calculate_technical_factor(s) for s in stock_data_list]
            market_strength_scores = [self._calculate_market_strength_factor(s) for s in stock_data_list]

            # 2. Z-score 정규화 (평균=0, 표준편차=1)
            momentum_zscores = self._calculate_zscores(momentum_scores)
            value_zscores = self._calculate_zscores(value_scores)
            quality_zscores = self._calculate_zscores(quality_scores)
            volume_zscores = self._calculate_zscores(volume_scores)
            volatility_zscores = self._calculate_zscores(volatility_scores)
            technical_zscores = self._calculate_zscores(technical_scores)
            market_strength_zscores = self._calculate_zscores(market_strength_scores)

            # 3. 종합 점수 계산 (가중 평균)
            results = []
            for i, stock in enumerate(stock_data_list):
                composite_zscore = (
                    momentum_zscores[i] * self.factor_weights['momentum'] +
                    value_zscores[i] * self.factor_weights['value'] +
                    quality_zscores[i] * self.factor_weights['quality'] +
                    volume_zscores[i] * self.factor_weights['volume'] +
                    volatility_zscores[i] * self.factor_weights['volatility'] +
                    technical_zscores[i] * self.factor_weights['technical'] +
                    market_strength_zscores[i] * self.factor_weights['market_strength']
                )

                # Z-score를 0-100 스케일로 변환 (평균=50, 표준편차=15)
                composite_score = 50 + composite_zscore * 15
                composite_score = np.clip(composite_score, 0, 100)

                factor_score = FactorScores(
                    stock_code=stock['stock_code'],
                    stock_name=stock['stock_name'],
                    momentum_score=momentum_scores[i],
                    value_score=value_scores[i],
                    quality_score=quality_scores[i],
                    volume_score=volume_scores[i],
                    volatility_score=volatility_scores[i],
                    technical_score=technical_scores[i],
                    market_strength_score=market_strength_scores[i],
                    composite_score=composite_score,
                    momentum_zscore=momentum_zscores[i],
                    value_zscore=value_zscores[i],
                    quality_zscore=quality_zscores[i],
                    volume_zscore=volume_zscores[i],
                    volatility_zscore=volatility_zscores[i],
                    technical_zscore=technical_zscores[i],
                    market_strength_zscore=market_strength_zscores[i]
                )

                results.append(factor_score)

            # 종합 점수 순으로 정렬
            results.sort(key=lambda x: x.composite_score, reverse=True)

            self.logger.info(f"멀티 팩터 스코어링 완료: 평균 점수 {np.mean([r.composite_score for r in results]):.1f}")
            return results

        except Exception as e:
            self.logger.error(f"멀티 팩터 스코어링 오류: {e}")
            return []

    def _calculate_momentum_factor(self, stock: Dict) -> float:
        """모멘텀 팩터 계산 (0-100)"""
        # expected_return이 높을수록 좋음
        expected_return = stock.get('expected_return', 0.0)

        # 0-20% 범위를 0-100으로 매핑
        score = (expected_return / 20.0) * 100
        return np.clip(score, 0, 100)

    def _calculate_value_factor(self, stock: Dict) -> float:
        """밸류 팩터 계산 (0-100)"""
        # price_attractiveness가 높을수록 좋음
        price_attractiveness = stock.get('price_attractiveness', 50.0)

        # 이미 0-100 범위
        return price_attractiveness

    def _calculate_quality_factor(self, stock: Dict) -> float:
        """퀄리티 팩터 계산 (0-100)"""
        # confidence가 높을수록 좋음
        confidence = stock.get('confidence', 0.5)

        # 0-1 범위를 0-100으로 매핑
        score = confidence * 100
        return score

    def _calculate_volume_factor(self, stock: Dict) -> float:
        """거래량 팩터 계산 (0-100)"""
        # volume_score가 높을수록 좋음
        volume_score = stock.get('volume_score', 50.0)

        # 이미 0-100 범위
        return volume_score

    def _calculate_volatility_factor(self, stock: Dict) -> float:
        """변동성 팩터 계산 (0-100, 낮을수록 좋음)"""
        # risk_score가 낮을수록 좋음
        risk_score = stock.get('risk_score', 50.0)

        # 역변환: 100 - risk_score
        score = 100 - risk_score
        return np.clip(score, 0, 100)

    def _calculate_technical_factor(self, stock: Dict) -> float:
        """기술적 팩터 계산 (0-100)"""
        # technical_signals 개수와 강도
        signals = stock.get('technical_signals', [])

        # 신호 개수에 따른 점수 (최대 5개 신호)
        signal_count = len(signals)
        base_score = min(signal_count / 5.0, 1.0) * 100

        return base_score

    def _calculate_market_strength_factor(self, stock: Dict) -> float:
        """시장 강도 팩터 계산 (0-100)"""
        # 섹터 모멘텀 및 시장 대비 상대 강도
        sector_momentum = stock.get('sector_momentum', 0.0)

        # -0.2 ~ +0.2 범위를 0-100으로 매핑
        score = ((sector_momentum + 0.2) / 0.4) * 100
        return np.clip(score, 0, 100)

    def _calculate_zscores(self, scores: List[float]) -> List[float]:
        """Z-score 정규화

        Args:
            scores: 원시 점수 리스트

        Returns:
            Z-score 리스트
        """
        scores_array = np.array(scores)

        # 표준편차가 0이면 모두 0 반환
        if np.std(scores_array) == 0:
            return [0.0] * len(scores)

        # Z-score 계산
        zscores = stats.zscore(scores_array)

        # 극단값 처리 (-3 ~ +3 범위로 제한)
        zscores = np.clip(zscores, -3, 3)

        return zscores.tolist()

    def get_top_stocks(self, factor_scores: List[FactorScores], n: int = 20) -> List[FactorScores]:
        """상위 N개 종목 선정

        Args:
            factor_scores: 팩터 점수 리스트
            n: 선정할 종목 수

        Returns:
            상위 N개 종목
        """
        # 이미 종합 점수 순으로 정렬되어 있음
        return factor_scores[:n]

    def filter_by_percentile(self, factor_scores: List[FactorScores], percentile: int = 90) -> List[FactorScores]:
        """백분위수 기준 필터링

        Args:
            factor_scores: 팩터 점수 리스트
            percentile: 백분위수 (예: 90 = 상위 10%)

        Returns:
            필터링된 종목 리스트
        """
        if not factor_scores:
            return []

        scores = [f.composite_score for f in factor_scores]
        threshold = np.percentile(scores, percentile)

        filtered = [f for f in factor_scores if f.composite_score >= threshold]

        self.logger.info(f"백분위수 {percentile}% 필터링: {len(filtered)}/{len(factor_scores)}개 종목")
        return filtered


def get_multi_factor_scorer() -> MultiFactorScorer:
    """싱글톤 MultiFactorScorer 인스턴스 반환"""
    if not hasattr(get_multi_factor_scorer, '_instance'):
        get_multi_factor_scorer._instance = MultiFactorScorer()
    return get_multi_factor_scorer._instance
