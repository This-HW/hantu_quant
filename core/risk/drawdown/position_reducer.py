"""
포지션 축소 모듈

드로다운 시 포지션 정리 계획 생성
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from core.utils.log_utils import get_logger

logger = get_logger(__name__)


class ReductionPriority(Enum):
    """축소 우선순위"""
    WORST_PERFORMER = "worst_performer"  # 최악 성과
    HIGH_CORRELATION = "high_correlation"  # 높은 상관관계
    HIGH_VOLATILITY = "high_volatility"  # 높은 변동성
    PROPORTIONAL = "proportional"  # 비례 축소


@dataclass
class PositionInfo:
    """포지션 정보"""
    stock_code: str
    current_value: float
    current_weight: float
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    correlation_score: float = 0.0  # 평균 상관관계
    volatility: float = 0.0
    sector: str = ""


@dataclass
class ReductionOrder:
    """축소 주문"""
    stock_code: str
    action: str = "SELL"
    quantity: int = 0
    target_value: float = 0.0
    priority: int = 0
    reason: str = ""


@dataclass
class ReductionPlan:
    """축소 계획"""
    total_reduction_pct: float = 0.0
    orders: List[ReductionOrder] = field(default_factory=list)
    estimated_proceeds: float = 0.0
    remaining_value: float = 0.0
    strategy: ReductionPriority = ReductionPriority.PROPORTIONAL

    def to_dict(self) -> Dict:
        return {
            'total_reduction_pct': self.total_reduction_pct,
            'orders': [
                {
                    'stock_code': o.stock_code,
                    'action': o.action,
                    'quantity': o.quantity,
                    'target_value': o.target_value,
                    'priority': o.priority,
                    'reason': o.reason
                }
                for o in self.orders
            ],
            'estimated_proceeds': self.estimated_proceeds,
            'remaining_value': self.remaining_value,
            'strategy': self.strategy.value,
        }


class PositionReducer:
    """
    포지션 축소기

    드로다운 상황에서 최적의 포지션 정리 계획을 생성합니다.
    """

    def __init__(
        self,
        min_position_value: float = 100000,  # 최소 유지 포지션
        max_single_order_pct: float = 0.30  # 한 번에 최대 30% 축소
    ):
        self.min_position_value = min_position_value
        self.max_single_order_pct = max_single_order_pct

    def create_reduction_plan(
        self,
        positions: Dict[str, PositionInfo],
        target_reduction_pct: float,
        strategy: ReductionPriority = ReductionPriority.WORST_PERFORMER,
        correlation_matrix: Optional[pd.DataFrame] = None
    ) -> ReductionPlan:
        """
        축소 계획 생성

        Args:
            positions: 현재 포지션 정보
            target_reduction_pct: 목표 축소 비율 (0.0 ~ 1.0)
            strategy: 축소 전략
            correlation_matrix: 상관관계 매트릭스

        Returns:
            ReductionPlan: 축소 계획
        """
        if not positions or target_reduction_pct <= 0:
            return ReductionPlan()

        # 총 포트폴리오 가치
        total_value = sum(p.current_value for p in positions.values())
        target_reduction_value = total_value * target_reduction_pct

        # 상관관계 점수 업데이트
        if correlation_matrix is not None:
            positions = self._update_correlation_scores(positions, correlation_matrix)

        # 우선순위 정렬
        sorted_positions = self._sort_by_priority(positions, strategy)

        # 축소 주문 생성
        orders = []
        remaining_reduction = target_reduction_value
        priority = 1

        for stock_code, position in sorted_positions:
            if remaining_reduction <= 0:
                break

            # 최소 유지 포지션 체크
            if position.current_value <= self.min_position_value:
                continue

            # 축소 가능 금액
            available_for_reduction = max(
                0,
                position.current_value - self.min_position_value
            )

            # 이번 주문 축소 금액
            reduction_amount = min(
                remaining_reduction,
                available_for_reduction,
                position.current_value * self.max_single_order_pct
            )

            if reduction_amount > 0:
                # 주문 생성
                order = ReductionOrder(
                    stock_code=stock_code,
                    action="SELL",
                    target_value=reduction_amount,
                    priority=priority,
                    reason=self._get_reduction_reason(position, strategy)
                )
                orders.append(order)

                remaining_reduction -= reduction_amount
                priority += 1

        # 계획 생성
        estimated_proceeds = sum(o.target_value for o in orders)

        return ReductionPlan(
            total_reduction_pct=target_reduction_pct,
            orders=orders,
            estimated_proceeds=estimated_proceeds,
            remaining_value=total_value - estimated_proceeds,
            strategy=strategy
        )

    def create_emergency_liquidation(
        self,
        positions: Dict[str, PositionInfo]
    ) -> ReductionPlan:
        """
        긴급 청산 계획

        모든 포지션 청산 (서킷브레이커 Stage 3)
        """
        orders = []
        total_value = 0

        for priority, (stock_code, position) in enumerate(positions.items(), 1):
            orders.append(ReductionOrder(
                stock_code=stock_code,
                action="SELL",
                target_value=position.current_value,
                priority=priority,
                reason="긴급 청산"
            ))
            total_value += position.current_value

        return ReductionPlan(
            total_reduction_pct=1.0,
            orders=orders,
            estimated_proceeds=total_value,
            remaining_value=0,
            strategy=ReductionPriority.PROPORTIONAL
        )

    def _sort_by_priority(
        self,
        positions: Dict[str, PositionInfo],
        strategy: ReductionPriority
    ) -> List[Tuple[str, PositionInfo]]:
        """우선순위 정렬"""
        position_list = list(positions.items())

        if strategy == ReductionPriority.WORST_PERFORMER:
            # 미실현 손익 오름차순 (손실 큰 것 우선)
            position_list.sort(key=lambda x: x[1].unrealized_pnl_pct)

        elif strategy == ReductionPriority.HIGH_CORRELATION:
            # 상관관계 내림차순 (상관관계 높은 것 우선)
            position_list.sort(key=lambda x: x[1].correlation_score, reverse=True)

        elif strategy == ReductionPriority.HIGH_VOLATILITY:
            # 변동성 내림차순 (변동성 높은 것 우선)
            position_list.sort(key=lambda x: x[1].volatility, reverse=True)

        elif strategy == ReductionPriority.PROPORTIONAL:
            # 비중 내림차순 (비중 큰 것 우선)
            position_list.sort(key=lambda x: x[1].current_weight, reverse=True)

        return position_list

    def _update_correlation_scores(
        self,
        positions: Dict[str, PositionInfo],
        correlation_matrix: pd.DataFrame
    ) -> Dict[str, PositionInfo]:
        """상관관계 점수 업데이트"""
        stocks = list(positions.keys())
        available_stocks = [s for s in stocks if s in correlation_matrix.columns]

        for stock in available_stocks:
            # 다른 종목들과의 평균 상관관계
            correlations = []
            for other in available_stocks:
                if other != stock:
                    corr = correlation_matrix.loc[stock, other]
                    correlations.append(abs(corr))

            if correlations:
                positions[stock].correlation_score = np.mean(correlations)

        return positions

    def _get_reduction_reason(
        self,
        position: PositionInfo,
        strategy: ReductionPriority
    ) -> str:
        """축소 이유 생성"""
        if strategy == ReductionPriority.WORST_PERFORMER:
            return f"손실: {position.unrealized_pnl_pct:.1%}"
        elif strategy == ReductionPriority.HIGH_CORRELATION:
            return f"상관관계: {position.correlation_score:.2f}"
        elif strategy == ReductionPriority.HIGH_VOLATILITY:
            return f"변동성: {position.volatility:.1%}"
        else:
            return f"비중 축소: {position.current_weight:.1%}"

    def simulate_reduction(
        self,
        plan: ReductionPlan,
        positions: Dict[str, PositionInfo],
        prices: Dict[str, float]
    ) -> Dict:
        """
        축소 시뮬레이션

        Args:
            plan: 축소 계획
            positions: 현재 포지션
            prices: 현재 가격

        Returns:
            시뮬레이션 결과
        """
        simulated_positions = {k: v.current_value for k, v in positions.items()}
        total_proceeds = 0
        executed_orders = []

        for order in plan.orders:
            stock = order.stock_code
            if stock not in simulated_positions:
                continue

            # 실제 청산 금액 (가격 변동 고려)
            current_price = prices.get(stock, 0)
            if current_price > 0:
                shares_to_sell = int(order.target_value / current_price)
                actual_proceeds = shares_to_sell * current_price

                simulated_positions[stock] -= actual_proceeds
                total_proceeds += actual_proceeds

                executed_orders.append({
                    'stock_code': stock,
                    'shares': shares_to_sell,
                    'proceeds': actual_proceeds
                })

        remaining_value = sum(simulated_positions.values())

        return {
            'executed_orders': executed_orders,
            'total_proceeds': total_proceeds,
            'remaining_value': remaining_value,
            'reduction_achieved': total_proceeds / sum(p.current_value for p in positions.values())
        }

    def get_reduction_recommendation(
        self,
        positions: Dict[str, PositionInfo],
        current_drawdown: float,
        max_allowed_drawdown: float = 0.15
    ) -> Dict:
        """
        축소 권고

        Args:
            positions: 현재 포지션
            current_drawdown: 현재 드로다운
            max_allowed_drawdown: 허용 최대 드로다운

        Returns:
            권고 사항
        """
        if current_drawdown < max_allowed_drawdown * 0.5:
            return {
                'action': 'NONE',
                'reduction_pct': 0,
                'reason': '드로다운 안전 범위 내'
            }

        elif current_drawdown < max_allowed_drawdown * 0.7:
            return {
                'action': 'MONITOR',
                'reduction_pct': 0,
                'reason': '주의 필요 - 모니터링 강화'
            }

        elif current_drawdown < max_allowed_drawdown:
            reduction_needed = (current_drawdown / max_allowed_drawdown - 0.7) * 0.5
            return {
                'action': 'REDUCE',
                'reduction_pct': reduction_needed,
                'reason': f'{reduction_needed:.0%} 포지션 축소 권고',
                'strategy': ReductionPriority.WORST_PERFORMER
            }

        else:
            return {
                'action': 'EMERGENCY',
                'reduction_pct': 0.5,
                'reason': '긴급 50% 포지션 축소 필요',
                'strategy': ReductionPriority.WORST_PERFORMER
            }
