#!/usr/bin/env python3
"""
리스크 패리티 포트폴리오 최적화
- 각 자산의 리스크 기여도를 균등하게 배분
- 변동성 기반 가중치 조정
- 상관관계 고려한 분산 최소화
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional
from dataclasses import dataclass

from core.utils.log_utils import get_logger

logger = get_logger(__name__)


@dataclass
class PortfolioWeights:
    """포트폴리오 가중치 결과"""
    stock_codes: List[str]
    weights: List[float]
    expected_return: float
    expected_volatility: float
    sharpe_ratio: float
    risk_contributions: List[float]
    optimization_method: str


class RiskParityOptimizer:
    """리스크 패리티 최적화기"""

    def __init__(self):
        """초기화"""
        self.logger = logger
        self.min_weight = 0.01  # 최소 가중치 1%
        self.max_weight = 0.25  # 최대 가중치 25%

    def optimize(self, stock_data: List[Dict], returns_data: Optional[pd.DataFrame] = None) -> PortfolioWeights:
        """리스크 패리티 최적화 실행

        Args:
            stock_data: 종목 데이터 리스트 (risk_score, expected_return 포함)
            returns_data: 과거 수익률 데이터 (옵션)

        Returns:
            최적화된 포트폴리오 가중치
        """
        try:
            n_assets = len(stock_data)

            if n_assets == 0:
                raise ValueError("종목 데이터가 없습니다")

            stock_codes = [s['stock_code'] for s in stock_data]
            self.logger.info(f"리스크 패리티 최적화 시작: {n_assets}개 종목")

            # 1. 변동성 추정
            volatilities = self._estimate_volatilities(stock_data, returns_data)

            # 2. 상관관계 행렬 추정
            correlation_matrix = self._estimate_correlation_matrix(stock_data, returns_data)

            # 3. 공분산 행렬 계산
            cov_matrix = self._calculate_covariance_matrix(volatilities, correlation_matrix)

            # 4. 리스크 패리티 가중치 계산
            weights = self._calculate_risk_parity_weights(cov_matrix)

            # 5. 제약 조건 적용
            weights = self._apply_constraints(weights)

            # 6. 기대 수익률 계산
            expected_returns = np.array([s.get('expected_return', 0.0) / 100.0 for s in stock_data])
            portfolio_return = np.dot(weights, expected_returns)

            # 7. 포트폴리오 변동성 계산
            portfolio_volatility = np.sqrt(np.dot(weights, np.dot(cov_matrix, weights)))

            # 8. 샤프 비율 계산 (무위험 수익률 = 3%)
            risk_free_rate = 0.03
            sharpe_ratio = (portfolio_return - risk_free_rate) / portfolio_volatility if portfolio_volatility > 0 else 0

            # 9. 리스크 기여도 계산
            risk_contributions = self._calculate_risk_contributions(weights, cov_matrix)

            result = PortfolioWeights(
                stock_codes=stock_codes,
                weights=weights.tolist(),
                expected_return=portfolio_return,
                expected_volatility=portfolio_volatility,
                sharpe_ratio=sharpe_ratio,
                risk_contributions=risk_contributions.tolist(),
                optimization_method="risk_parity"
            )

            self.logger.info(f"리스크 패리티 최적화 완료 - 샤프비율: {sharpe_ratio:.2f}")
            return result

        except Exception as e:
            self.logger.error(f"리스크 패리티 최적화 오류: {e}", exc_info=True)
            # 폴백: 동일 가중치
            return self._equal_weight_fallback(stock_data)

    def _estimate_volatilities(self, stock_data: List[Dict], returns_data: Optional[pd.DataFrame]) -> np.ndarray:
        """변동성 추정

        Args:
            stock_data: 종목 데이터
            returns_data: 과거 수익률 데이터

        Returns:
            변동성 배열
        """
        if returns_data is not None and not returns_data.empty:
            # 실제 데이터 기반 변동성 계산
            volatilities = returns_data.std().values
        else:
            # risk_score 기반 변동성 추정
            # risk_score가 높을수록 변동성이 높음 (0-100 → 0.1-0.5)
            volatilities = np.array([
                0.1 + (s.get('risk_score', 50.0) / 100.0) * 0.4
                for s in stock_data
            ])

        return volatilities

    def _estimate_correlation_matrix(self, stock_data: List[Dict],
                                     returns_data: Optional[pd.DataFrame]) -> np.ndarray:
        """상관관계 행렬 추정

        Args:
            stock_data: 종목 데이터
            returns_data: 과거 수익률 데이터

        Returns:
            상관관계 행렬
        """
        n = len(stock_data)

        if returns_data is not None and not returns_data.empty:
            # 실제 데이터 기반 상관관계 계산
            corr_matrix = returns_data.corr().values
        else:
            # 섹터 기반 상관관계 추정
            corr_matrix = np.eye(n)
            sectors = [s.get('sector', '기타') for s in stock_data]

            for i in range(n):
                for j in range(i + 1, n):
                    if sectors[i] == sectors[j]:
                        # 같은 섹터: 상관관계 0.6
                        corr = 0.6
                    else:
                        # 다른 섹터: 상관관계 0.3
                        corr = 0.3

                    corr_matrix[i, j] = corr
                    corr_matrix[j, i] = corr

        return corr_matrix

    def _calculate_covariance_matrix(self, volatilities: np.ndarray,
                                     correlation_matrix: np.ndarray) -> np.ndarray:
        """공분산 행렬 계산

        Args:
            volatilities: 변동성 배열
            correlation_matrix: 상관관계 행렬

        Returns:
            공분산 행렬
        """
        # Cov(i,j) = σ_i * σ_j * ρ_ij
        vol_matrix = np.outer(volatilities, volatilities)
        cov_matrix = vol_matrix * correlation_matrix

        return cov_matrix

    def _calculate_risk_parity_weights(self, cov_matrix: np.ndarray, max_iter: int = 1000) -> np.ndarray:
        """리스크 패리티 가중치 계산 (반복 최적화)

        Args:
            cov_matrix: 공분산 행렬
            max_iter: 최대 반복 횟수

        Returns:
            최적 가중치
        """
        n = cov_matrix.shape[0]

        # 초기 가중치: 역변동성 가중
        volatilities = np.sqrt(np.diag(cov_matrix))
        inv_vol = 1 / volatilities
        weights = inv_vol / inv_vol.sum()

        # 반복 최적화
        for iteration in range(max_iter):
            # 리스크 기여도 계산
            portfolio_var = np.dot(weights, np.dot(cov_matrix, weights))
            marginal_risk = np.dot(cov_matrix, weights) / np.sqrt(portfolio_var)
            risk_contribution = weights * marginal_risk

            # 목표 리스크 기여도 (균등 분산)
            target_rc = portfolio_var / n

            # 가중치 업데이트
            adjustment = target_rc / risk_contribution
            weights = weights * adjustment
            weights = weights / weights.sum()

            # 수렴 확인
            rc_diff = np.std(risk_contribution)
            if rc_diff < 1e-6:
                self.logger.debug(f"리스크 패리티 수렴: {iteration + 1}회 반복")
                break

        return weights

    def _apply_constraints(self, weights: np.ndarray) -> np.ndarray:
        """제약 조건 적용

        Args:
            weights: 원본 가중치

        Returns:
            제약 조건 적용된 가중치
        """
        # 최소/최대 가중치 제약
        weights = np.clip(weights, self.min_weight, self.max_weight)

        # 합이 1이 되도록 정규화
        weights = weights / weights.sum()

        return weights

    def _calculate_risk_contributions(self, weights: np.ndarray, cov_matrix: np.ndarray) -> np.ndarray:
        """리스크 기여도 계산

        Args:
            weights: 가중치
            cov_matrix: 공분산 행렬

        Returns:
            각 자산의 리스크 기여도
        """
        portfolio_var = np.dot(weights, np.dot(cov_matrix, weights))
        marginal_risk = np.dot(cov_matrix, weights) / np.sqrt(portfolio_var)
        risk_contribution = weights * marginal_risk

        # 정규화 (퍼센트)
        risk_contribution = risk_contribution / risk_contribution.sum() * 100

        return risk_contribution

    def _equal_weight_fallback(self, stock_data: List[Dict]) -> PortfolioWeights:
        """폴백: 동일 가중치 포트폴리오

        Args:
            stock_data: 종목 데이터

        Returns:
            동일 가중 포트폴리오
        """
        n = len(stock_data)
        stock_codes = [s['stock_code'] for s in stock_data]
        weights = np.ones(n) / n

        expected_returns = np.array([s.get('expected_return', 0.0) / 100.0 for s in stock_data])
        portfolio_return = np.mean(expected_returns)
        portfolio_volatility = 0.25  # 추정값

        sharpe_ratio = (portfolio_return - 0.03) / portfolio_volatility if portfolio_volatility > 0 else 0

        return PortfolioWeights(
            stock_codes=stock_codes,
            weights=weights.tolist(),
            expected_return=portfolio_return,
            expected_volatility=portfolio_volatility,
            sharpe_ratio=sharpe_ratio,
            risk_contributions=[100.0 / n] * n,
            optimization_method="equal_weight_fallback"
        )


def get_risk_parity_optimizer() -> RiskParityOptimizer:
    """싱글톤 RiskParityOptimizer 인스턴스 반환"""
    if not hasattr(get_risk_parity_optimizer, '_instance'):
        get_risk_parity_optimizer._instance = RiskParityOptimizer()
    return get_risk_parity_optimizer._instance
