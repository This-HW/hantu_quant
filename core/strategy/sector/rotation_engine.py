"""
섹터 로테이션 엔진 모듈

섹터 모멘텀 기반으로 자금 배분을 결정합니다.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import logging

from .sector_map import Sector, SectorMap
from .sector_analyzer import SectorAnalyzer, SectorMetrics

logger = logging.getLogger(__name__)


@dataclass
class SectorAllocation:
    """섹터 배분"""
    sector: Sector
    weight: float = 0.0  # 배분 비중 (0.0 ~ 1.0)
    rank: int = 0
    momentum_score: float = 0.0
    stocks: List[str] = field(default_factory=list)
    rationale: str = ""

    def to_dict(self) -> Dict:
        return {
            'sector': self.sector.value,
            'weight': self.weight,
            'rank': self.rank,
            'momentum_score': self.momentum_score,
            'stocks': self.stocks,
            'rationale': self.rationale,
        }


@dataclass
class RotationConfig:
    """로테이션 설정"""
    # 배분 대상 섹터 수
    top_n_sectors: int = 3

    # 배분 방식
    equal_weight: bool = False  # True면 균등 배분, False면 모멘텀 가중

    # 최소/최대 비중
    min_weight: float = 0.1
    max_weight: float = 0.5

    # 리밸런싱 임계값
    rebalance_threshold: float = 0.05  # 5% 이상 변화 시 리밸런싱

    # 섹터 필터
    min_momentum: float = 0.0  # 최소 모멘텀 점수
    min_stocks: int = 2  # 최소 종목 수


class RotationEngine:
    """
    섹터 로테이션 엔진

    섹터 모멘텀 기반으로 자금 배분을 관리합니다.
    """

    def __init__(
        self,
        sector_map: Optional[SectorMap] = None,
        analyzer: Optional[SectorAnalyzer] = None,
        config: Optional[RotationConfig] = None
    ):
        self.sector_map = sector_map or SectorMap()
        self.analyzer = analyzer or SectorAnalyzer(self.sector_map)
        self.config = config or RotationConfig()

        # 현재 배분
        self._current_allocation: Dict[Sector, SectorAllocation] = {}

        # 이전 배분 (리밸런싱 판단용)
        self._previous_allocation: Dict[Sector, SectorAllocation] = {}

        # 히스토리
        self._allocation_history: List[Dict] = []

    @property
    def current_allocation(self) -> Dict[Sector, SectorAllocation]:
        """현재 섹터 배분"""
        return self._current_allocation.copy()

    def calculate_allocation(
        self,
        stock_data: Dict[str, pd.DataFrame],
        market_data: Optional[pd.DataFrame] = None
    ) -> Dict[Sector, SectorAllocation]:
        """
        섹터 배분 계산

        Args:
            stock_data: 종목별 OHLCV 데이터
            market_data: 시장 지수 데이터

        Returns:
            {섹터: 배분} 딕셔너리
        """
        # 섹터 분석
        metrics = self.analyzer.analyze_all_sectors(stock_data, market_data)

        if not metrics:
            logger.warning("No sector metrics available")
            return {}

        # 섹터 필터링
        filtered_metrics = self._filter_sectors(metrics)

        if not filtered_metrics:
            logger.warning("No sectors passed the filter")
            return {}

        # 순위 결정
        ranked = self.analyzer.rank_sectors(filtered_metrics)

        # 상위 N개 섹터 선택
        top_sectors = ranked[:self.config.top_n_sectors]

        # 배분 계산
        if self.config.equal_weight:
            allocation = self._equal_weight_allocation(top_sectors)
        else:
            allocation = self._momentum_weight_allocation(top_sectors)

        # 현재 배분 업데이트
        self._previous_allocation = self._current_allocation.copy()
        self._current_allocation = allocation

        # 히스토리 기록
        self._record_allocation(allocation)

        return allocation

    def get_rebalance_recommendations(self) -> Dict[str, any]:
        """
        리밸런싱 권고

        Returns:
            리밸런싱 필요 여부 및 변경 사항
        """
        if not self._previous_allocation or not self._current_allocation:
            return {
                'needs_rebalance': False,
                'reason': '배분 이력 없음'
            }

        changes = []
        needs_rebalance = False

        # 현재 배분과 이전 배분 비교
        all_sectors = set(self._current_allocation.keys()) | set(self._previous_allocation.keys())

        for sector in all_sectors:
            current = self._current_allocation.get(sector)
            previous = self._previous_allocation.get(sector)

            current_weight = current.weight if current else 0.0
            previous_weight = previous.weight if previous else 0.0

            change = current_weight - previous_weight

            if abs(change) >= self.config.rebalance_threshold:
                needs_rebalance = True
                changes.append({
                    'sector': sector.value,
                    'previous_weight': previous_weight,
                    'current_weight': current_weight,
                    'change': change,
                    'action': 'INCREASE' if change > 0 else 'DECREASE'
                })

        return {
            'needs_rebalance': needs_rebalance,
            'changes': changes,
            'threshold': self.config.rebalance_threshold
        }

    def get_stock_recommendations(
        self,
        allocation: Dict[Sector, SectorAllocation],
        total_capital: float,
        stock_data: Dict[str, pd.DataFrame]
    ) -> Dict[str, Dict]:
        """
        종목별 투자 권고

        Args:
            allocation: 섹터 배분
            total_capital: 총 투자금
            stock_data: 종목별 데이터

        Returns:
            {종목코드: 권고} 딕셔너리
        """
        recommendations = {}

        for sector, alloc in allocation.items():
            sector_capital = total_capital * alloc.weight

            # 섹터 내 종목 선택
            stocks = self.sector_map.get_stocks_in_sector(sector)
            available_stocks = [s for s in stocks if s in stock_data]

            if not available_stocks:
                continue

            # 종목별 배분 (균등 또는 시가총액 가중)
            stock_weights = self._calculate_stock_weights(available_stocks)

            for stock, weight in stock_weights.items():
                stock_capital = sector_capital * weight
                current_price = stock_data[stock]['close'].iloc[-1]

                info = self.sector_map.get_stock_info(stock)

                recommendations[stock] = {
                    'name': info['name'] if info else stock,
                    'sector': sector.value,
                    'allocation': weight * alloc.weight,
                    'capital': stock_capital,
                    'current_price': current_price,
                    'shares': int(stock_capital / current_price),
                }

        return recommendations

    def _filter_sectors(
        self,
        metrics: Dict[Sector, SectorMetrics]
    ) -> Dict[Sector, SectorMetrics]:
        """섹터 필터링"""
        filtered = {}

        for sector, m in metrics.items():
            # 최소 모멘텀 점수
            if m.momentum_score < self.config.min_momentum:
                continue

            # 최소 종목 수
            if m.stock_count < self.config.min_stocks:
                continue

            filtered[sector] = m

        return filtered

    def _equal_weight_allocation(
        self,
        ranked_sectors: List[Tuple[Sector, SectorMetrics, int]]
    ) -> Dict[Sector, SectorAllocation]:
        """균등 배분"""
        allocation = {}
        n = len(ranked_sectors)

        if n == 0:
            return allocation

        weight_per_sector = 1.0 / n

        for sector, metrics, rank in ranked_sectors:
            stocks = self.sector_map.get_stocks_in_sector(sector)

            allocation[sector] = SectorAllocation(
                sector=sector,
                weight=weight_per_sector,
                rank=rank,
                momentum_score=metrics.momentum_score,
                stocks=stocks[:5],  # 상위 5개 종목
                rationale=f"균등 배분 (순위 {rank}위)"
            )

        return allocation

    def _momentum_weight_allocation(
        self,
        ranked_sectors: List[Tuple[Sector, SectorMetrics, int]]
    ) -> Dict[Sector, SectorAllocation]:
        """모멘텀 가중 배분"""
        allocation = {}

        if not ranked_sectors:
            return allocation

        # 모멘텀 점수 기반 가중치 계산
        # 음수 모멘텀도 처리하기 위해 최소값 조정
        min_score = min(m.momentum_score for _, m, _ in ranked_sectors)
        adjusted_scores = [
            m.momentum_score - min_score + 1  # 모두 양수로 만듦
            for _, m, _ in ranked_sectors
        ]
        total_score = sum(adjusted_scores)

        for i, (sector, metrics, rank) in enumerate(ranked_sectors):
            raw_weight = adjusted_scores[i] / total_score

            # 최소/최대 제한
            weight = np.clip(raw_weight, self.config.min_weight, self.config.max_weight)

            stocks = self.sector_map.get_stocks_in_sector(sector)

            allocation[sector] = SectorAllocation(
                sector=sector,
                weight=weight,
                rank=rank,
                momentum_score=metrics.momentum_score,
                stocks=stocks[:5],
                rationale=f"모멘텀 가중 (점수: {metrics.momentum_score:.1f})"
            )

        # 가중치 정규화
        total_weight = sum(a.weight for a in allocation.values())
        for alloc in allocation.values():
            alloc.weight /= total_weight

        return allocation

    def _calculate_stock_weights(
        self,
        stocks: List[str]
    ) -> Dict[str, float]:
        """종목별 비중 계산"""
        weights = {}
        total_weight = 0.0

        for stock in stocks:
            info = self.sector_map.get_stock_info(stock)
            weight = info.get('weight', 0.01) if info else 0.01
            weights[stock] = weight
            total_weight += weight

        # 정규화
        return {s: w / total_weight for s, w in weights.items()}

    def _record_allocation(self, allocation: Dict[Sector, SectorAllocation]):
        """배분 히스토리 기록"""
        record = {
            'timestamp': datetime.now().isoformat(),
            'allocation': {
                s.value: a.to_dict() for s, a in allocation.items()
            }
        }

        self._allocation_history.append(record)

        # 최근 100건만 유지
        if len(self._allocation_history) > 100:
            self._allocation_history = self._allocation_history[-100:]

    def get_allocation_summary(self) -> Dict:
        """현재 배분 요약"""
        if not self._current_allocation:
            return {'status': '배분 없음'}

        return {
            'total_sectors': len(self._current_allocation),
            'sectors': [
                {
                    'sector': s.value,
                    'weight': a.weight,
                    'rank': a.rank,
                    'momentum': a.momentum_score
                }
                for s, a in sorted(
                    self._current_allocation.items(),
                    key=lambda x: x[1].weight,
                    reverse=True
                )
            ]
        }

    def get_history(self, n: int = 10) -> List[Dict]:
        """최근 배분 히스토리"""
        return self._allocation_history[-n:]
