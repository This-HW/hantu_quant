"""
분산투자 점수 모듈

포트폴리오 분산도 평가
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from dataclasses import dataclass, field

from .correlation_matrix import CorrelationMatrix, CorrelationResult
from core.utils.log_utils import get_logger

logger = get_logger(__name__)


@dataclass
class DiversificationResult:
    """분산투자 분석 결과"""
    score: float = 0.0  # 0.0 ~ 1.0 (높을수록 좋음)
    correlation_penalty: float = 0.0
    sector_concentration: float = 0.0
    effective_n: float = 0.0  # 유효 종목 수
    recommendations: List[str] = field(default_factory=list)

    @property
    def rating(self) -> str:
        """분산투자 등급"""
        if self.score >= 0.8:
            return "우수"
        elif self.score >= 0.6:
            return "양호"
        elif self.score >= 0.4:
            return "보통"
        else:
            return "미흡"

    def to_dict(self) -> Dict:
        return {
            'score': self.score,
            'rating': self.rating,
            'correlation_penalty': self.correlation_penalty,
            'sector_concentration': self.sector_concentration,
            'effective_n': self.effective_n,
            'recommendations': self.recommendations,
        }


class DiversificationScore:
    """
    분산투자 점수 계산기

    포트폴리오의 분산 정도를 평가하고 개선점을 제안합니다.
    """

    def __init__(
        self,
        correlation_matrix: Optional[CorrelationMatrix] = None,
        sector_weight_threshold: float = 0.30,
        stock_weight_threshold: float = 0.15
    ):
        """
        Args:
            correlation_matrix: 상관관계 계산기
            sector_weight_threshold: 섹터 집중도 경고 기준
            stock_weight_threshold: 종목 집중도 경고 기준
        """
        self.corr_matrix = correlation_matrix or CorrelationMatrix()
        self.sector_threshold = sector_weight_threshold
        self.stock_threshold = stock_weight_threshold

    def calculate(
        self,
        positions: Dict[str, float],
        price_data: Dict[str, pd.DataFrame],
        sector_mapping: Optional[Dict[str, str]] = None
    ) -> DiversificationResult:
        """
        분산투자 점수 계산

        Args:
            positions: {종목코드: 비중} 딕셔너리
            price_data: 가격 데이터
            sector_mapping: {종목코드: 섹터} 매핑

        Returns:
            DiversificationResult: 분산투자 분석 결과
        """
        if not positions:
            return DiversificationResult()

        recommendations = []

        # 1. 상관관계 분석
        corr_result = self.corr_matrix.calculate(price_data)
        correlation_penalty = self._calculate_correlation_penalty(
            positions, corr_result
        )

        # 2. 섹터 집중도 분석
        sector_concentration = 0.0
        if sector_mapping:
            sector_concentration = self._calculate_sector_concentration(
                positions, sector_mapping
            )
            sector_recs = self._generate_sector_recommendations(
                positions, sector_mapping
            )
            recommendations.extend(sector_recs)

        # 3. 유효 종목 수 계산
        effective_n = self._calculate_effective_n(positions, corr_result)

        # 4. 종목 집중도 체크
        concentration_recs = self._check_stock_concentration(positions)
        recommendations.extend(concentration_recs)

        # 5. 상관관계 권고
        corr_recs = self._generate_correlation_recommendations(corr_result, positions)
        recommendations.extend(corr_recs)

        # 종합 점수 계산
        score = self._calculate_final_score(
            correlation_penalty,
            sector_concentration,
            effective_n,
            len(positions)
        )

        return DiversificationResult(
            score=score,
            correlation_penalty=correlation_penalty,
            sector_concentration=sector_concentration,
            effective_n=effective_n,
            recommendations=recommendations[:5]  # 상위 5개 권고
        )

    def _calculate_correlation_penalty(
        self,
        positions: Dict[str, float],
        corr_result: CorrelationResult
    ) -> float:
        """상관관계 기반 페널티 계산"""
        if corr_result.correlation_matrix is None or corr_result.correlation_matrix.empty:
            return 0.0

        # 가중 평균 상관관계
        corr_matrix = corr_result.correlation_matrix
        stocks = list(positions.keys())
        available_stocks = [s for s in stocks if s in corr_matrix.columns]

        if len(available_stocks) < 2:
            return 0.0

        weighted_corr = 0.0
        total_weight = 0.0

        for i, stock1 in enumerate(available_stocks):
            for stock2 in available_stocks[i + 1:]:
                w1 = positions.get(stock1, 0)
                w2 = positions.get(stock2, 0)
                corr = corr_matrix.loc[stock1, stock2]

                pair_weight = w1 * w2
                weighted_corr += corr * pair_weight
                total_weight += pair_weight

        if total_weight == 0:
            return 0.0

        avg_weighted_corr = weighted_corr / total_weight

        # 높은 상관관계 = 높은 페널티
        return max(0, avg_weighted_corr)

    def _calculate_sector_concentration(
        self,
        positions: Dict[str, float],
        sector_mapping: Dict[str, str]
    ) -> float:
        """섹터 집중도 계산"""
        sector_weights = {}

        for stock, weight in positions.items():
            sector = sector_mapping.get(stock, 'OTHER')
            sector_weights[sector] = sector_weights.get(sector, 0) + weight

        if not sector_weights:
            return 0.0

        # 허핀달 지수 (집중도)
        hhi = sum(w ** 2 for w in sector_weights.values())

        return hhi

    def _calculate_effective_n(
        self,
        positions: Dict[str, float],
        corr_result: CorrelationResult
    ) -> float:
        """유효 종목 수 계산"""
        if not positions:
            return 0.0

        # 단순 유효 N (역 허핀달)
        weights = list(positions.values())
        hhi = sum(w ** 2 for w in weights)

        if hhi == 0:
            return 0.0

        simple_effective_n = 1 / hhi

        # 상관관계 보정
        if corr_result.avg_correlation > 0:
            # 높은 상관관계 = 낮은 유효 N
            correlation_factor = 1 - corr_result.avg_correlation * 0.5
            simple_effective_n *= correlation_factor

        return simple_effective_n

    def _check_stock_concentration(
        self,
        positions: Dict[str, float]
    ) -> List[str]:
        """종목 집중도 체크"""
        recommendations = []

        for stock, weight in positions.items():
            if weight > self.stock_threshold:
                recommendations.append(
                    f"{stock} 비중({weight:.1%}) 과다 - {self.stock_threshold:.0%} 이하 권장"
                )

        return recommendations

    def _generate_sector_recommendations(
        self,
        positions: Dict[str, float],
        sector_mapping: Dict[str, str]
    ) -> List[str]:
        """섹터 권고 생성"""
        recommendations = []

        sector_weights = {}
        for stock, weight in positions.items():
            sector = sector_mapping.get(stock, 'OTHER')
            sector_weights[sector] = sector_weights.get(sector, 0) + weight

        for sector, weight in sector_weights.items():
            if weight > self.sector_threshold:
                recommendations.append(
                    f"{sector} 섹터 비중({weight:.1%}) 과다 - {self.sector_threshold:.0%} 이하 권장"
                )

        return recommendations

    def _generate_correlation_recommendations(
        self,
        corr_result: CorrelationResult,
        positions: Dict[str, float]
    ) -> List[str]:
        """상관관계 권고 생성"""
        recommendations = []

        # 고상관 쌍 경고
        for stock1, stock2, corr in corr_result.high_correlation_pairs[:3]:
            if stock1 in positions and stock2 in positions:
                recommendations.append(
                    f"{stock1}-{stock2} 높은 상관관계({corr:.2f}) - 분산 효과 제한적"
                )

        # 평균 상관관계 높으면 경고
        if corr_result.avg_correlation > 0.5:
            recommendations.append(
                f"포트폴리오 평균 상관관계({corr_result.avg_correlation:.2f}) 높음 - 분산 투자 필요"
            )

        return recommendations

    def _calculate_final_score(
        self,
        correlation_penalty: float,
        sector_concentration: float,
        effective_n: float,
        total_stocks: int
    ) -> float:
        """최종 점수 계산"""
        # 상관관계 점수 (낮을수록 좋음) - 0~1 범위로 클램핑
        corr_score = np.clip(1 - correlation_penalty, 0, 1)

        # 섹터 집중도 점수 (낮을수록 좋음)
        # HHI가 1이면 완전 집중, 1/n이면 균등 분산
        if total_stocks > 0:
            min_hhi = 1 / total_stocks
            if (1 - min_hhi) > 0:
                sector_score = np.clip(
                    1 - (sector_concentration - min_hhi) / (1 - min_hhi),
                    0, 1
                )
            else:
                sector_score = 1.0  # 종목이 1개인 경우
        else:
            sector_score = 0.5

        # 유효 N 점수 (높을수록 좋음) - 0~1 범위로 클램핑
        if total_stocks > 0:
            effective_n_ratio = effective_n / total_stocks
            n_score = np.clip(effective_n_ratio, 0, 1)
        else:
            n_score = 0.0

        # 종합 점수
        score = (
            corr_score * 0.35 +
            sector_score * 0.35 +
            n_score * 0.30
        )

        # 최종 점수도 0~1 범위로 보장
        return np.clip(score, 0, 1)

    def suggest_additions(
        self,
        current_positions: Dict[str, float],
        candidate_stocks: List[str],
        price_data: Dict[str, pd.DataFrame],
        top_n: int = 3
    ) -> List[Dict]:
        """
        분산 개선을 위한 종목 추천

        Args:
            current_positions: 현재 포지션
            candidate_stocks: 후보 종목 리스트
            price_data: 가격 데이터
            top_n: 추천 종목 수

        Returns:
            추천 종목 리스트
        """
        suggestions = []

        for candidate in candidate_stocks:
            if candidate in current_positions:
                continue

            if candidate not in price_data:
                continue

            # 기존 포트폴리오와의 평균 상관계수 계산
            avg_corr = self._calculate_avg_corr_with_portfolio(
                candidate, current_positions, price_data
            )

            suggestions.append({
                'stock': candidate,
                'avg_correlation_with_portfolio': avg_corr,
                'diversification_benefit': 1 - abs(avg_corr)
            })

        # 분산 효과가 큰 순서로 정렬
        suggestions.sort(key=lambda x: x['diversification_benefit'], reverse=True)

        return suggestions[:top_n]

    def _calculate_avg_corr_with_portfolio(
        self,
        candidate: str,
        positions: Dict[str, float],
        price_data: Dict[str, pd.DataFrame]
    ) -> float:
        """후보 종목과 포트폴리오의 평균 상관계수"""
        correlations = []

        for stock in positions:
            if stock in price_data and candidate in price_data:
                corr = self.corr_matrix.get_pairwise_correlation(
                    price_data, candidate, stock
                )
                correlations.append(corr)

        if not correlations:
            return 0.0

        return np.mean(correlations)
