"""
포트폴리오 최적화 모듈

상관관계 기반 최소 분산 포트폴리오 계산
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from core.utils.log_utils import get_logger

logger = get_logger(__name__)


@dataclass
class OptimizationResult:
    """최적화 결과"""
    weights: Dict[str, float] = field(default_factory=dict)
    expected_return: float = 0.0
    expected_volatility: float = 0.0
    sharpe_ratio: float = 0.0
    diversification_ratio: float = 0.0
    method: str = ""

    def to_dict(self) -> Dict:
        return {
            'weights': self.weights,
            'expected_return': self.expected_return,
            'expected_volatility': self.expected_volatility,
            'sharpe_ratio': self.sharpe_ratio,
            'diversification_ratio': self.diversification_ratio,
            'method': self.method,
        }


class PortfolioOptimizer:
    """
    포트폴리오 최적화기

    상관관계를 고려하여 최적 비중을 계산합니다.
    """

    def __init__(
        self,
        risk_free_rate: float = 0.03,
        max_weight: float = 0.25,
        min_weight: float = 0.02
    ):
        """
        Args:
            risk_free_rate: 무위험 수익률 (연간)
            max_weight: 최대 종목 비중
            min_weight: 최소 종목 비중
        """
        self.risk_free_rate = risk_free_rate
        self.max_weight = max_weight
        self.min_weight = min_weight

    def optimize_min_variance(
        self,
        price_data: Dict[str, pd.DataFrame],
        lookback_days: int = 252
    ) -> OptimizationResult:
        """
        최소 분산 포트폴리오 계산

        Args:
            price_data: 가격 데이터
            lookback_days: 계산 기간

        Returns:
            OptimizationResult: 최적화 결과
        """
        returns_df, cov_matrix = self._prepare_data(price_data, lookback_days)

        if returns_df.empty:
            return OptimizationResult(method='min_variance_failed')

        n = len(returns_df.columns)
        stocks = returns_df.columns.tolist()

        # 최소 분산 포트폴리오 (분석적 해)
        try:
            cov_inv = np.linalg.inv(cov_matrix.values)
            ones = np.ones(n)

            # w = (Σ^-1 * 1) / (1' * Σ^-1 * 1)
            weights = cov_inv @ ones / (ones @ cov_inv @ ones)

            # 제약 조건 적용
            weights = self._apply_constraints(weights)

            weights_dict = {stocks[i]: weights[i] for i in range(n)}

            # 성과 지표 계산
            expected_return = returns_df.mean() @ weights * 252
            expected_vol = np.sqrt(weights @ cov_matrix.values @ weights) * np.sqrt(252)
            sharpe = (expected_return - self.risk_free_rate) / expected_vol if expected_vol > 0 else 0

            return OptimizationResult(
                weights=weights_dict,
                expected_return=expected_return,
                expected_volatility=expected_vol,
                sharpe_ratio=sharpe,
                method='min_variance'
            )

        except Exception as e:
            logger.error(f"Min variance optimization failed: {e}", exc_info=True)
            return self._equal_weight_fallback(stocks)

    def optimize_max_sharpe(
        self,
        price_data: Dict[str, pd.DataFrame],
        lookback_days: int = 252
    ) -> OptimizationResult:
        """
        최대 샤프 비율 포트폴리오 (근사 해)

        수치 최적화 없이 간단한 방법 사용
        """
        returns_df, cov_matrix = self._prepare_data(price_data, lookback_days)

        if returns_df.empty:
            return OptimizationResult(method='max_sharpe_failed')

        stocks = returns_df.columns.tolist()
        n = len(stocks)

        # 각 종목의 샤프 비율 계산
        stock_sharpes = {}
        for stock in stocks:
            mean_return = returns_df[stock].mean() * 252
            volatility = returns_df[stock].std() * np.sqrt(252)
            sharpe = (mean_return - self.risk_free_rate) / volatility if volatility > 0 else 0
            stock_sharpes[stock] = max(0, sharpe)  # 음수 샤프는 0으로

        # 샤프 비율 기반 가중치
        total_sharpe = sum(stock_sharpes.values())
        if total_sharpe == 0:
            return self._equal_weight_fallback(stocks)

        weights = np.array([stock_sharpes[s] / total_sharpe for s in stocks])
        weights = self._apply_constraints(weights)

        weights_dict = {stocks[i]: weights[i] for i in range(n)}

        # 성과 지표
        expected_return = returns_df.mean() @ weights * 252
        expected_vol = np.sqrt(weights @ cov_matrix.values @ weights) * np.sqrt(252)
        sharpe = (expected_return - self.risk_free_rate) / expected_vol if expected_vol > 0 else 0

        return OptimizationResult(
            weights=weights_dict,
            expected_return=expected_return,
            expected_volatility=expected_vol,
            sharpe_ratio=sharpe,
            method='max_sharpe_approx'
        )

    def optimize_risk_parity(
        self,
        price_data: Dict[str, pd.DataFrame],
        lookback_days: int = 252
    ) -> OptimizationResult:
        """
        리스크 패리티 포트폴리오

        각 종목의 리스크 기여도가 동일하도록 배분
        """
        returns_df, cov_matrix = self._prepare_data(price_data, lookback_days)

        if returns_df.empty:
            return OptimizationResult(method='risk_parity_failed')

        stocks = returns_df.columns.tolist()
        n = len(stocks)

        # 개별 변동성 역수 가중치 (근사)
        volatilities = returns_df.std().values
        inv_vol = 1 / (volatilities + 1e-10)
        weights = inv_vol / inv_vol.sum()

        weights = self._apply_constraints(weights)
        weights_dict = {stocks[i]: weights[i] for i in range(n)}

        # 성과 지표
        expected_return = returns_df.mean() @ weights * 252
        expected_vol = np.sqrt(weights @ cov_matrix.values @ weights) * np.sqrt(252)
        sharpe = (expected_return - self.risk_free_rate) / expected_vol if expected_vol > 0 else 0

        return OptimizationResult(
            weights=weights_dict,
            expected_return=expected_return,
            expected_volatility=expected_vol,
            sharpe_ratio=sharpe,
            method='risk_parity'
        )

    def optimize_with_constraints(
        self,
        price_data: Dict[str, pd.DataFrame],
        target_return: Optional[float] = None,
        max_correlation: float = 0.7,
        lookback_days: int = 252
    ) -> OptimizationResult:
        """
        제약 조건을 고려한 최적화

        Args:
            price_data: 가격 데이터
            target_return: 목표 수익률 (None이면 무시)
            max_correlation: 최대 허용 상관관계
            lookback_days: 계산 기간
        """
        returns_df, cov_matrix = self._prepare_data(price_data, lookback_days)

        if returns_df.empty:
            return OptimizationResult(method='constrained_failed')

        stocks = returns_df.columns.tolist()
        corr_matrix = returns_df.corr()

        # 고상관 종목 쌍 필터링
        filtered_stocks = self._filter_high_correlation(
            stocks, corr_matrix, max_correlation
        )

        if len(filtered_stocks) < 2:
            return self._equal_weight_fallback(stocks)

        # 필터링된 종목으로 최적화
        filtered_returns = returns_df[filtered_stocks]
        filtered_cov = filtered_returns.cov()

        # 최소 분산 최적화
        n = len(filtered_stocks)
        try:
            cov_inv = np.linalg.inv(filtered_cov.values)
            ones = np.ones(n)
            weights = cov_inv @ ones / (ones @ cov_inv @ ones)
            weights = self._apply_constraints(weights)
        except Exception:
            weights = np.ones(n) / n

        weights_dict = {filtered_stocks[i]: weights[i] for i in range(n)}

        # 제외된 종목은 0
        for stock in stocks:
            if stock not in weights_dict:
                weights_dict[stock] = 0.0

        # 성과 지표
        full_weights = np.array([weights_dict.get(s, 0) for s in stocks])
        expected_return = returns_df.mean() @ full_weights * 252
        expected_vol = np.sqrt(full_weights @ cov_matrix.values @ full_weights) * np.sqrt(252)
        sharpe = (expected_return - self.risk_free_rate) / expected_vol if expected_vol > 0 else 0

        return OptimizationResult(
            weights=weights_dict,
            expected_return=expected_return,
            expected_volatility=expected_vol,
            sharpe_ratio=sharpe,
            method='constrained'
        )

    def _prepare_data(
        self,
        price_data: Dict[str, pd.DataFrame],
        lookback_days: int
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """데이터 준비"""
        returns = {}

        for stock, data in price_data.items():
            if len(data) >= lookback_days:
                stock_returns = data['close'].pct_change().dropna().tail(lookback_days)
                returns[stock] = stock_returns

        if len(returns) < 2:
            return pd.DataFrame(), pd.DataFrame()

        returns_df = pd.DataFrame(returns).dropna()
        cov_matrix = returns_df.cov()

        return returns_df, cov_matrix

    def _apply_constraints(self, weights: np.ndarray) -> np.ndarray:
        """비중 제약 적용"""
        # 음수 제거
        weights = np.maximum(weights, 0)

        # 최대/최소 제한
        weights = np.clip(weights, self.min_weight, self.max_weight)

        # 정규화
        if weights.sum() > 0:
            weights = weights / weights.sum()
        else:
            weights = np.ones(len(weights)) / len(weights)

        return weights

    def _equal_weight_fallback(self, stocks: List[str]) -> OptimizationResult:
        """균등 배분 폴백"""
        n = len(stocks)
        weights = {stock: 1.0 / n for stock in stocks}

        return OptimizationResult(
            weights=weights,
            method='equal_weight_fallback'
        )

    def _filter_high_correlation(
        self,
        stocks: List[str],
        corr_matrix: pd.DataFrame,
        max_corr: float
    ) -> List[str]:
        """고상관 종목 필터링 (그리디)"""
        selected = [stocks[0]]

        for stock in stocks[1:]:
            # 기존 선택 종목들과의 상관관계 확인
            max_correlation = max(
                abs(corr_matrix.loc[stock, s])
                for s in selected
            )

            if max_correlation <= max_corr:
                selected.append(stock)

        return selected

    def compare_methods(
        self,
        price_data: Dict[str, pd.DataFrame],
        lookback_days: int = 252
    ) -> Dict[str, OptimizationResult]:
        """여러 방법 비교"""
        results = {
            'min_variance': self.optimize_min_variance(price_data, lookback_days),
            'max_sharpe': self.optimize_max_sharpe(price_data, lookback_days),
            'risk_parity': self.optimize_risk_parity(price_data, lookback_days),
        }

        return results
