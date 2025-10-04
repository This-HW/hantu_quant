#!/usr/bin/env python3
"""
샤프 비율 최적화 포트폴리오
- 평균-분산 최적화 (Mean-Variance Optimization)
- 효율적 투자선 (Efficient Frontier) 계산
- 최대 샤프 비율 포트폴리오 선택
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from scipy.optimize import minimize
import logging

from core.utils.log_utils import get_logger
from core.portfolio.risk_parity_optimizer import PortfolioWeights

logger = get_logger(__name__)


class SharpeOptimizer:
    """샤프 비율 최적화기"""

    def __init__(self, risk_free_rate: float = 0.03):
        """초기화

        Args:
            risk_free_rate: 무위험 수익률 (기본값: 3%)
        """
        self.logger = logger
        self.risk_free_rate = risk_free_rate
        self.min_weight = 0.01  # 최소 가중치 1%
        self.max_weight = 0.25  # 최대 가중치 25%

    def optimize(self, stock_data: List[Dict], returns_data: Optional[pd.DataFrame] = None) -> PortfolioWeights:
        """샤프 비율 최적화 실행

        Args:
            stock_data: 종목 데이터 리스트
            returns_data: 과거 수익률 데이터 (옵션)

        Returns:
            최적화된 포트폴리오 가중치
        """
        try:
            n_assets = len(stock_data)

            if n_assets == 0:
                raise ValueError("종목 데이터가 없습니다")

            stock_codes = [s['stock_code'] for s in stock_data]
            self.logger.info(f"샤프 비율 최적화 시작: {n_assets}개 종목")

            # 1. 기대 수익률 벡터
            expected_returns = np.array([s.get('expected_return', 0.0) / 100.0 for s in stock_data])

            # 2. 공분산 행렬 추정
            cov_matrix = self._estimate_covariance_matrix(stock_data, returns_data)

            # 3. 제약 조건 설정
            constraints = self._get_constraints(n_assets)
            bounds = self._get_bounds(n_assets)

            # 4. 초기 가중치 (동일 가중)
            initial_weights = np.ones(n_assets) / n_assets

            # 5. 최적화 실행 (음의 샤프 비율 최소화)
            def negative_sharpe_ratio(weights):
                portfolio_return = np.dot(weights, expected_returns)
                portfolio_volatility = np.sqrt(np.dot(weights, np.dot(cov_matrix, weights)))

                if portfolio_volatility == 0:
                    return 1e10

                sharpe = (portfolio_return - self.risk_free_rate) / portfolio_volatility
                return -sharpe

            result = minimize(
                negative_sharpe_ratio,
                initial_weights,
                method='SLSQP',
                bounds=bounds,
                constraints=constraints,
                options={'maxiter': 1000, 'ftol': 1e-9}
            )

            if not result.success:
                self.logger.warning(f"최적화 실패: {result.message}, 동일 가중치 사용")
                return self._equal_weight_fallback(stock_data)

            weights = result.x

            # 6. 포트폴리오 지표 계산
            portfolio_return = np.dot(weights, expected_returns)
            portfolio_volatility = np.sqrt(np.dot(weights, np.dot(cov_matrix, weights)))
            sharpe_ratio = (portfolio_return - self.risk_free_rate) / portfolio_volatility

            # 7. 리스크 기여도 계산
            risk_contributions = self._calculate_risk_contributions(weights, cov_matrix)

            result_portfolio = PortfolioWeights(
                stock_codes=stock_codes,
                weights=weights.tolist(),
                expected_return=portfolio_return,
                expected_volatility=portfolio_volatility,
                sharpe_ratio=sharpe_ratio,
                risk_contributions=risk_contributions.tolist(),
                optimization_method="max_sharpe"
            )

            self.logger.info(f"샤프 비율 최적화 완료 - 샤프: {sharpe_ratio:.2f}, 수익률: {portfolio_return:.2%}, 변동성: {portfolio_volatility:.2%}")
            return result_portfolio

        except Exception as e:
            self.logger.error(f"샤프 비율 최적화 오류: {e}")
            return self._equal_weight_fallback(stock_data)

    def _estimate_covariance_matrix(self, stock_data: List[Dict],
                                    returns_data: Optional[pd.DataFrame]) -> np.ndarray:
        """공분산 행렬 추정"""
        n = len(stock_data)

        if returns_data is not None and not returns_data.empty:
            # 실제 데이터 기반
            cov_matrix = returns_data.cov().values
        else:
            # risk_score 및 섹터 기반 추정
            volatilities = np.array([
                0.1 + (s.get('risk_score', 50.0) / 100.0) * 0.4
                for s in stock_data
            ])

            # 상관관계 추정
            corr_matrix = np.eye(n)
            sectors = [s.get('sector', '기타') for s in stock_data]

            for i in range(n):
                for j in range(i + 1, n):
                    if sectors[i] == sectors[j]:
                        corr = 0.6  # 같은 섹터
                    else:
                        corr = 0.3  # 다른 섹터

                    corr_matrix[i, j] = corr
                    corr_matrix[j, i] = corr

            # 공분산 = 변동성 * 상관관계
            vol_matrix = np.outer(volatilities, volatilities)
            cov_matrix = vol_matrix * corr_matrix

        return cov_matrix

    def _get_constraints(self, n_assets: int) -> List[Dict]:
        """최적화 제약 조건"""
        constraints = [
            # 가중치 합 = 1
            {'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0}
        ]
        return constraints

    def _get_bounds(self, n_assets: int) -> List[Tuple[float, float]]:
        """가중치 범위"""
        return [(self.min_weight, self.max_weight) for _ in range(n_assets)]

    def _calculate_risk_contributions(self, weights: np.ndarray, cov_matrix: np.ndarray) -> np.ndarray:
        """리스크 기여도 계산"""
        portfolio_var = np.dot(weights, np.dot(cov_matrix, weights))
        marginal_risk = np.dot(cov_matrix, weights) / np.sqrt(portfolio_var)
        risk_contribution = weights * marginal_risk

        # 정규화 (퍼센트)
        risk_contribution = risk_contribution / risk_contribution.sum() * 100

        return risk_contribution

    def _equal_weight_fallback(self, stock_data: List[Dict]) -> PortfolioWeights:
        """폴백: 동일 가중치 포트폴리오"""
        n = len(stock_data)
        stock_codes = [s['stock_code'] for s in stock_data]
        weights = np.ones(n) / n

        expected_returns = np.array([s.get('expected_return', 0.0) / 100.0 for s in stock_data])
        portfolio_return = np.mean(expected_returns)
        portfolio_volatility = 0.25

        sharpe_ratio = (portfolio_return - self.risk_free_rate) / portfolio_volatility

        return PortfolioWeights(
            stock_codes=stock_codes,
            weights=weights.tolist(),
            expected_return=portfolio_return,
            expected_volatility=portfolio_volatility,
            sharpe_ratio=sharpe_ratio,
            risk_contributions=[100.0 / n] * n,
            optimization_method="equal_weight_fallback"
        )

    def calculate_efficient_frontier(self, stock_data: List[Dict],
                                     returns_data: Optional[pd.DataFrame] = None,
                                     n_points: int = 50) -> List[Dict]:
        """효율적 투자선 계산

        Args:
            stock_data: 종목 데이터
            returns_data: 과거 수익률 데이터
            n_points: 계산할 포인트 수

        Returns:
            효율적 투자선 포인트 리스트
        """
        try:
            n_assets = len(stock_data)
            expected_returns = np.array([s.get('expected_return', 0.0) / 100.0 for s in stock_data])
            cov_matrix = self._estimate_covariance_matrix(stock_data, returns_data)

            # 목표 수익률 범위
            min_return = np.min(expected_returns)
            max_return = np.max(expected_returns)
            target_returns = np.linspace(min_return, max_return, n_points)

            frontier_points = []

            for target_return in target_returns:
                # 목표 수익률 제약 조건 추가
                constraints = [
                    {'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0},
                    {'type': 'eq', 'fun': lambda w: np.dot(w, expected_returns) - target_return}
                ]

                bounds = self._get_bounds(n_assets)
                initial_weights = np.ones(n_assets) / n_assets

                # 변동성 최소화
                def portfolio_volatility(weights):
                    return np.sqrt(np.dot(weights, np.dot(cov_matrix, weights)))

                result = minimize(
                    portfolio_volatility,
                    initial_weights,
                    method='SLSQP',
                    bounds=bounds,
                    constraints=constraints,
                    options={'maxiter': 500}
                )

                if result.success:
                    weights = result.x
                    volatility = portfolio_volatility(weights)
                    sharpe = (target_return - self.risk_free_rate) / volatility

                    frontier_points.append({
                        'return': target_return,
                        'volatility': volatility,
                        'sharpe_ratio': sharpe,
                        'weights': weights.tolist()
                    })

            self.logger.info(f"효율적 투자선 계산 완료: {len(frontier_points)}개 포인트")
            return frontier_points

        except Exception as e:
            self.logger.error(f"효율적 투자선 계산 오류: {e}")
            return []


def get_sharpe_optimizer() -> SharpeOptimizer:
    """싱글톤 SharpeOptimizer 인스턴스 반환"""
    if not hasattr(get_sharpe_optimizer, '_instance'):
        get_sharpe_optimizer._instance = SharpeOptimizer()
    return get_sharpe_optimizer._instance
