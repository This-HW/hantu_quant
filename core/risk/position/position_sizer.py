"""
포지션 사이징 모듈

다양한 요소를 고려한 통합 포지션 크기 결정
"""

import numpy as np
from typing import Dict, Optional, List
from dataclasses import dataclass
import logging

from .kelly_calculator import KellyCalculator, KellyResult

logger = logging.getLogger(__name__)


@dataclass
class SizingConfig:
    """포지션 사이징 설정"""
    # 계좌 리스크 한도
    account_risk_per_trade: float = 0.02  # 거래당 계좌 리스크 2%
    max_portfolio_risk: float = 0.10  # 전체 포트폴리오 리스크 10%

    # 포지션 제한
    max_single_position: float = 0.20  # 단일 종목 최대 20%
    max_sector_exposure: float = 0.40  # 섹터 최대 40%

    # ATR 기반 사이징
    use_atr_sizing: bool = True
    atr_multiplier: float = 2.0  # 손절 거리 = ATR * multiplier

    # 변동성 조정
    use_volatility_scaling: bool = True
    target_volatility: float = 0.15  # 목표 연간 변동성 15%

    # 신호 강도 반영
    use_signal_strength: bool = True


@dataclass
class PositionSize:
    """포지션 크기 결과"""
    position_pct: float = 0.0  # 포트폴리오 비중 (%)
    shares: int = 0  # 주식 수
    amount: float = 0.0  # 투자 금액
    stop_loss: float = 0.0  # 손절가
    risk_amount: float = 0.0  # 리스크 금액
    method: str = ""  # 사용된 방법

    kelly_result: Optional[KellyResult] = None

    def to_dict(self) -> Dict:
        return {
            'position_pct': self.position_pct,
            'shares': self.shares,
            'amount': self.amount,
            'stop_loss': self.stop_loss,
            'risk_amount': self.risk_amount,
            'method': self.method,
        }


class PositionSizer:
    """
    통합 포지션 사이징

    켈리, ATR, 변동성 등 다양한 요소를 결합하여
    최적 포지션 크기를 결정합니다.
    """

    def __init__(
        self,
        config: Optional[SizingConfig] = None,
        kelly_calculator: Optional[KellyCalculator] = None
    ):
        self.config = config or SizingConfig()
        self.kelly = kelly_calculator or KellyCalculator()

    def calculate_position(
        self,
        portfolio_value: float,
        entry_price: float,
        stop_loss: float,
        atr: float = 0.0,
        volatility: float = 0.15,
        signal_strength: float = 1.0,
        trade_returns: Optional[List[float]] = None,
        current_positions: Optional[Dict[str, float]] = None,
        sector: Optional[str] = None
    ) -> PositionSize:
        """
        종합 포지션 크기 계산

        Args:
            portfolio_value: 포트폴리오 가치
            entry_price: 진입 가격
            stop_loss: 손절가
            atr: ATR (변동성 지표)
            volatility: 연간 변동성
            signal_strength: 신호 강도 (0.0 ~ 2.0)
            trade_returns: 과거 거래 수익률
            current_positions: 현재 보유 포지션 {종목: 비중}
            sector: 종목의 섹터

        Returns:
            PositionSize: 포지션 크기 결과
        """
        methods_used = []

        # 1. 기본 리스크 기반 사이징
        risk_based_size = self._calculate_risk_based_size(
            portfolio_value, entry_price, stop_loss
        )
        methods_used.append('risk')

        # 2. ATR 기반 사이징 (옵션)
        atr_based_size = 1.0
        if self.config.use_atr_sizing and atr > 0:
            atr_based_size = self._calculate_atr_based_size(
                portfolio_value, entry_price, atr
            )
            methods_used.append('atr')

        # 3. 변동성 조정 (옵션)
        volatility_multiplier = 1.0
        if self.config.use_volatility_scaling and volatility > 0:
            volatility_multiplier = self._calculate_volatility_multiplier(volatility)
            methods_used.append('vol')

        # 4. 켈리 기반 사이징 (과거 데이터 있을 때)
        kelly_result = None
        kelly_multiplier = 1.0
        if trade_returns and len(trade_returns) >= 30:
            kelly_result = self.kelly.calculate(trade_returns, signal_strength)
            if kelly_result.final_position > 0:
                kelly_multiplier = kelly_result.final_position / 0.10  # 기본 10% 대비
                methods_used.append('kelly')

        # 5. 신호 강도 반영
        signal_multiplier = 1.0
        if self.config.use_signal_strength:
            signal_multiplier = min(2.0, max(0.5, signal_strength))
            methods_used.append('signal')

        # 종합 포지션 크기 계산
        base_size = risk_based_size
        adjusted_size = base_size * atr_based_size * volatility_multiplier * kelly_multiplier * signal_multiplier

        # 제한 적용
        final_size = self._apply_constraints(
            adjusted_size,
            current_positions,
            sector
        )

        # 최종 계산
        amount = portfolio_value * final_size
        shares = int(amount / entry_price) if entry_price > 0 else 0
        actual_amount = shares * entry_price
        actual_pct = actual_amount / portfolio_value if portfolio_value > 0 else 0

        # 리스크 금액
        risk_per_share = entry_price - stop_loss
        risk_amount = shares * abs(risk_per_share)

        return PositionSize(
            position_pct=actual_pct,
            shares=shares,
            amount=actual_amount,
            stop_loss=stop_loss,
            risk_amount=risk_amount,
            method='+'.join(methods_used),
            kelly_result=kelly_result
        )

    def _calculate_risk_based_size(
        self,
        portfolio_value: float,
        entry_price: float,
        stop_loss: float
    ) -> float:
        """리스크 기반 포지션 크기"""
        if entry_price <= 0 or stop_loss <= 0:
            return 0.0

        # 주당 리스크
        risk_per_share = abs(entry_price - stop_loss)
        risk_pct = risk_per_share / entry_price

        if risk_pct <= 0:
            return 0.0

        # 계좌 리스크 / 주당 리스크 비율
        position_size = self.config.account_risk_per_trade / risk_pct

        return min(position_size, self.config.max_single_position)

    def _calculate_atr_based_size(
        self,
        portfolio_value: float,
        entry_price: float,
        atr: float
    ) -> float:
        """ATR 기반 포지션 조정 계수"""
        # 정규화된 ATR (가격 대비)
        normalized_atr = atr / entry_price

        # 높은 ATR = 작은 포지션
        if normalized_atr > 0.05:  # 변동성 높음
            return 0.5
        elif normalized_atr > 0.03:
            return 0.75
        else:
            return 1.0

    def _calculate_volatility_multiplier(self, volatility: float) -> float:
        """변동성 조정 계수"""
        if volatility <= 0:
            return 1.0

        # 목표 변동성 대비 비율
        ratio = self.config.target_volatility / volatility

        # 제한 적용 (0.5 ~ 2.0)
        return np.clip(ratio, 0.5, 2.0)

    def _apply_constraints(
        self,
        position_size: float,
        current_positions: Optional[Dict[str, float]],
        sector: Optional[str]
    ) -> float:
        """제약 조건 적용"""
        # 단일 종목 제한
        position_size = min(position_size, self.config.max_single_position)

        # 포트폴리오 리스크 제한
        if current_positions:
            current_total = sum(current_positions.values())
            remaining = self.config.max_portfolio_risk - current_total
            position_size = min(position_size, max(0, remaining))

            # 섹터 제한
            if sector:
                sum(
                    v for k, v in current_positions.items()
                    # 섹터 체크 로직 필요
                )
                # TODO: 섹터 정보 기반 제한

        # 최소 포지션
        if position_size < 0.01:  # 1% 미만이면 투자하지 않음
            return 0.0

        return position_size

    def calculate_stop_loss(
        self,
        entry_price: float,
        atr: float,
        method: str = 'atr'
    ) -> float:
        """손절가 계산"""
        if method == 'atr' and atr > 0:
            return entry_price - (atr * self.config.atr_multiplier)
        elif method == 'percent':
            return entry_price * 0.95  # 5% 손절
        else:
            return entry_price * 0.93  # 기본 7% 손절

    def calculate_take_profit(
        self,
        entry_price: float,
        stop_loss: float,
        risk_reward_ratio: float = 2.0
    ) -> float:
        """익절가 계산"""
        risk = entry_price - stop_loss
        profit_target = risk * risk_reward_ratio
        return entry_price + profit_target

    def get_position_summary(
        self,
        positions: Dict[str, PositionSize]
    ) -> Dict:
        """포지션 요약"""
        total_amount = sum(p.amount for p in positions.values())
        total_risk = sum(p.risk_amount for p in positions.values())

        return {
            'position_count': len(positions),
            'total_amount': total_amount,
            'total_risk': total_risk,
            'avg_position': total_amount / len(positions) if positions else 0,
            'risk_per_position': total_risk / len(positions) if positions else 0,
            'positions': {k: v.to_dict() for k, v in positions.items()}
        }
