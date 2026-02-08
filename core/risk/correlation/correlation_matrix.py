"""
상관관계 매트릭스 모듈

종목 간 상관관계 분석
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from dataclasses import dataclass, field

from core.utils.log_utils import get_logger

logger = get_logger(__name__)


@dataclass
class CorrelationResult:
    """상관관계 분석 결과"""
    correlation_matrix: pd.DataFrame = None
    avg_correlation: float = 0.0
    high_correlation_pairs: List[Tuple[str, str, float]] = field(default_factory=list)
    low_correlation_pairs: List[Tuple[str, str, float]] = field(default_factory=list)
    cluster_count: int = 0

    def to_dict(self) -> Dict:
        return {
            'avg_correlation': self.avg_correlation,
            'high_correlation_pairs': [
                {'stock1': p[0], 'stock2': p[1], 'correlation': p[2]}
                for p in self.high_correlation_pairs[:5]
            ],
            'low_correlation_pairs': [
                {'stock1': p[0], 'stock2': p[1], 'correlation': p[2]}
                for p in self.low_correlation_pairs[:5]
            ],
            'cluster_count': self.cluster_count,
        }


class CorrelationMatrix:
    """
    상관관계 매트릭스

    종목 간 가격 움직임의 상관관계를 분석합니다.
    """

    def __init__(
        self,
        lookback_days: int = 60,
        high_correlation_threshold: float = 0.7,
        low_correlation_threshold: float = 0.3
    ):
        """
        Args:
            lookback_days: 상관관계 계산 기간
            high_correlation_threshold: 고상관 기준
            low_correlation_threshold: 저상관 기준
        """
        self.lookback_days = lookback_days
        self.high_threshold = high_correlation_threshold
        self.low_threshold = low_correlation_threshold

    def calculate(
        self,
        price_data: Dict[str, pd.DataFrame]
    ) -> CorrelationResult:
        """
        상관관계 매트릭스 계산

        Args:
            price_data: {종목코드: OHLCV DataFrame}

        Returns:
            CorrelationResult: 상관관계 분석 결과
        """
        if len(price_data) < 2:
            return CorrelationResult()

        # 수익률 DataFrame 구성
        returns_df = self._build_returns_df(price_data)

        if returns_df.empty or len(returns_df.columns) < 2:
            return CorrelationResult()

        # 상관관계 계산
        corr_matrix = returns_df.corr()

        # 평균 상관계수
        avg_corr = self._calculate_avg_correlation(corr_matrix)

        # 고상관/저상관 쌍 식별
        high_pairs = self._find_high_correlation_pairs(corr_matrix)
        low_pairs = self._find_low_correlation_pairs(corr_matrix)

        # 클러스터 수 추정
        cluster_count = self._estimate_clusters(corr_matrix)

        return CorrelationResult(
            correlation_matrix=corr_matrix,
            avg_correlation=avg_corr,
            high_correlation_pairs=high_pairs,
            low_correlation_pairs=low_pairs,
            cluster_count=cluster_count
        )

    def calculate_rolling(
        self,
        price_data: Dict[str, pd.DataFrame],
        window: int = 20
    ) -> pd.DataFrame:
        """
        롤링 상관관계 계산

        Args:
            price_data: 가격 데이터
            window: 롤링 윈도우

        Returns:
            롤링 평균 상관관계 시계열
        """
        returns_df = self._build_returns_df(price_data)

        if returns_df.empty:
            return pd.DataFrame()

        # 각 시점의 평균 상관계수 계산
        rolling_corrs = []

        for i in range(window, len(returns_df)):
            window_returns = returns_df.iloc[i - window:i]
            corr = window_returns.corr()
            avg_corr = self._calculate_avg_correlation(corr)
            rolling_corrs.append({
                'date': returns_df.index[i],
                'avg_correlation': avg_corr
            })

        return pd.DataFrame(rolling_corrs).set_index('date')

    def get_pairwise_correlation(
        self,
        price_data: Dict[str, pd.DataFrame],
        stock1: str,
        stock2: str
    ) -> float:
        """두 종목 간 상관계수"""
        if stock1 not in price_data or stock2 not in price_data:
            return 0.0

        returns1 = price_data[stock1]['close'].pct_change().dropna().tail(self.lookback_days)
        returns2 = price_data[stock2]['close'].pct_change().dropna().tail(self.lookback_days)

        # 인덱스 정렬
        aligned = pd.DataFrame({
            'stock1': returns1,
            'stock2': returns2
        }).dropna()

        if len(aligned) < 10:
            return 0.0

        return aligned['stock1'].corr(aligned['stock2'])

    def _build_returns_df(self, price_data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """수익률 DataFrame 구성"""
        returns = {}

        for stock, data in price_data.items():
            if len(data) >= self.lookback_days:
                stock_returns = data['close'].pct_change().dropna().tail(self.lookback_days)
                returns[stock] = stock_returns

        if not returns:
            return pd.DataFrame()

        returns_df = pd.DataFrame(returns)
        return returns_df.dropna()

    def _calculate_avg_correlation(self, corr_matrix: pd.DataFrame) -> float:
        """평균 상관계수 계산 (대각선 제외)"""
        if corr_matrix.empty:
            return 0.0

        # 상삼각 행렬의 값만 추출
        mask = np.triu(np.ones_like(corr_matrix, dtype=bool), k=1)
        upper_triangle = corr_matrix.where(mask)
        values = upper_triangle.values.flatten()
        values = values[~np.isnan(values)]

        if len(values) == 0:
            return 0.0

        return float(np.mean(values))

    def _find_high_correlation_pairs(
        self,
        corr_matrix: pd.DataFrame
    ) -> List[Tuple[str, str, float]]:
        """고상관 쌍 찾기"""
        pairs = []
        stocks = corr_matrix.columns.tolist()

        for i, stock1 in enumerate(stocks):
            for stock2 in stocks[i + 1:]:
                corr = corr_matrix.loc[stock1, stock2]
                if abs(corr) >= self.high_threshold:
                    pairs.append((stock1, stock2, corr))

        return sorted(pairs, key=lambda x: abs(x[2]), reverse=True)

    def _find_low_correlation_pairs(
        self,
        corr_matrix: pd.DataFrame
    ) -> List[Tuple[str, str, float]]:
        """저상관 쌍 찾기"""
        pairs = []
        stocks = corr_matrix.columns.tolist()

        for i, stock1 in enumerate(stocks):
            for stock2 in stocks[i + 1:]:
                corr = corr_matrix.loc[stock1, stock2]
                if abs(corr) <= self.low_threshold:
                    pairs.append((stock1, stock2, corr))

        return sorted(pairs, key=lambda x: abs(x[2]))

    def _estimate_clusters(self, corr_matrix: pd.DataFrame) -> int:
        """클러스터 수 추정 (간단한 방법)"""
        if corr_matrix.empty:
            return 0

        # 평균 상관계수 기반 대략적인 클러스터 수 추정
        avg_corr = self._calculate_avg_correlation(corr_matrix)

        n = len(corr_matrix)

        if avg_corr > 0.7:
            return 1  # 모두 높은 상관관계
        elif avg_corr > 0.5:
            return max(1, n // 4)
        elif avg_corr > 0.3:
            return max(1, n // 3)
        else:
            return max(1, n // 2)
