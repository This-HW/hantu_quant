"""
가상 포트폴리오 모듈

페이퍼 트레이딩용 가상 자산 관리를 담당합니다.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


@dataclass
class PortfolioConfig:
    """포트폴리오 설정"""
    # 초기 자본
    initial_capital: float = 10_000_000  # 1000만원

    # 수수료
    commission_rate: float = 0.00015  # 0.015%
    tax_rate: float = 0.0023         # 0.23% (매도 시)
    min_commission: float = 0        # 최소 수수료

    # 제한
    max_position_pct: float = 0.20   # 최대 단일 포지션 비중 20%
    max_positions: int = 20          # 최대 보유 종목 수

    # 슬리피지 (시뮬레이션)
    slippage_pct: float = 0.001      # 0.1%


@dataclass
class Holding:
    """보유 종목"""
    stock_code: str
    stock_name: str
    quantity: int
    avg_price: float
    current_price: float = 0.0
    first_buy_date: datetime = field(default_factory=datetime.now)

    @property
    def market_value(self) -> float:
        """시장 가치"""
        return self.quantity * self.current_price

    @property
    def cost_basis(self) -> float:
        """매입 원가"""
        return self.quantity * self.avg_price

    @property
    def unrealized_pnl(self) -> float:
        """미실현 손익"""
        return self.market_value - self.cost_basis

    @property
    def unrealized_pnl_pct(self) -> float:
        """미실현 손익률"""
        if self.cost_basis == 0:
            return 0.0
        return (self.unrealized_pnl / self.cost_basis) * 100

    def to_dict(self) -> Dict:
        return {
            'stock_code': self.stock_code,
            'stock_name': self.stock_name,
            'quantity': self.quantity,
            'avg_price': self.avg_price,
            'current_price': self.current_price,
            'market_value': self.market_value,
            'cost_basis': self.cost_basis,
            'unrealized_pnl': self.unrealized_pnl,
            'unrealized_pnl_pct': self.unrealized_pnl_pct,
            'first_buy_date': self.first_buy_date.isoformat(),
        }


@dataclass
class PortfolioSnapshot:
    """포트폴리오 스냅샷"""
    timestamp: datetime
    cash: float
    holdings_value: float
    total_value: float
    realized_pnl: float
    unrealized_pnl: float
    total_pnl: float
    total_pnl_pct: float
    num_positions: int

    def to_dict(self) -> Dict:
        return {
            'timestamp': self.timestamp.isoformat(),
            'cash': self.cash,
            'holdings_value': self.holdings_value,
            'total_value': self.total_value,
            'realized_pnl': self.realized_pnl,
            'unrealized_pnl': self.unrealized_pnl,
            'total_pnl': self.total_pnl,
            'total_pnl_pct': self.total_pnl_pct,
            'num_positions': self.num_positions,
        }


class VirtualPortfolio:
    """
    가상 포트폴리오

    페이퍼 트레이딩용 자산 관리 시스템입니다.
    """

    def __init__(self, config: Optional[PortfolioConfig] = None):
        """
        Args:
            config: 포트폴리오 설정
        """
        self.config = config or PortfolioConfig()

        # 자금
        self._cash: float = self.config.initial_capital
        self._initial_capital: float = self.config.initial_capital

        # 보유 종목
        self._holdings: Dict[str, Holding] = {}

        # 실현 손익
        self._realized_pnl: float = 0.0

        # 히스토리
        self._snapshots: List[PortfolioSnapshot] = []
        self._transaction_count: int = 0

    @property
    def cash(self) -> float:
        """현금"""
        return self._cash

    @property
    def holdings_value(self) -> float:
        """보유 종목 가치"""
        return sum(h.market_value for h in self._holdings.values())

    @property
    def total_value(self) -> float:
        """총 자산"""
        return self._cash + self.holdings_value

    @property
    def unrealized_pnl(self) -> float:
        """미실현 손익"""
        return sum(h.unrealized_pnl for h in self._holdings.values())

    @property
    def total_pnl(self) -> float:
        """총 손익"""
        return self._realized_pnl + self.unrealized_pnl

    @property
    def total_pnl_pct(self) -> float:
        """총 수익률"""
        if self._initial_capital == 0:
            return 0.0
        return (self.total_value - self._initial_capital) / self._initial_capital * 100

    def buy(
        self,
        stock_code: str,
        stock_name: str,
        price: float,
        quantity: int
    ) -> Dict[str, Any]:
        """
        매수 실행

        Args:
            stock_code: 종목 코드
            stock_name: 종목명
            price: 가격
            quantity: 수량

        Returns:
            Dict: 실행 결과
        """
        # 슬리피지 적용
        exec_price = price * (1 + self.config.slippage_pct)

        # 금액 계산
        gross_amount = exec_price * quantity
        commission = max(
            gross_amount * self.config.commission_rate,
            self.config.min_commission
        )
        total_cost = gross_amount + commission

        # 자금 체크
        if total_cost > self._cash:
            return {
                'success': False,
                'error': 'Insufficient cash',
                'required': total_cost,
                'available': self._cash,
            }

        # 포지션 제한 체크
        if stock_code not in self._holdings:
            if len(self._holdings) >= self.config.max_positions:
                return {
                    'success': False,
                    'error': 'Max positions reached',
                    'max_positions': self.config.max_positions,
                }

        # 비중 제한 체크
        new_holding_value = gross_amount
        if stock_code in self._holdings:
            new_holding_value += self._holdings[stock_code].market_value

        if new_holding_value / self.total_value > self.config.max_position_pct:
            return {
                'success': False,
                'error': 'Position limit exceeded',
                'max_pct': self.config.max_position_pct,
            }

        # 실행
        self._cash -= total_cost
        self._transaction_count += 1

        if stock_code in self._holdings:
            # 기존 보유 종목 추가 매수
            holding = self._holdings[stock_code]
            total_qty = holding.quantity + quantity
            total_cost_basis = holding.cost_basis + gross_amount
            holding.avg_price = total_cost_basis / total_qty
            holding.quantity = total_qty
            holding.current_price = exec_price
        else:
            # 신규 매수
            self._holdings[stock_code] = Holding(
                stock_code=stock_code,
                stock_name=stock_name,
                quantity=quantity,
                avg_price=exec_price,
                current_price=exec_price,
            )

        logger.info(
            f"BUY: {stock_code} {quantity}주 @ {exec_price:,.0f}원 "
            f"(수수료: {commission:,.0f}원)"
        )

        return {
            'success': True,
            'stock_code': stock_code,
            'quantity': quantity,
            'price': exec_price,
            'commission': commission,
            'total_cost': total_cost,
            'remaining_cash': self._cash,
        }

    def sell(
        self,
        stock_code: str,
        price: float,
        quantity: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        매도 실행

        Args:
            stock_code: 종목 코드
            price: 가격
            quantity: 수량 (None이면 전량)

        Returns:
            Dict: 실행 결과
        """
        if stock_code not in self._holdings:
            return {
                'success': False,
                'error': 'Position not found',
            }

        holding = self._holdings[stock_code]

        # 수량 결정
        sell_qty = quantity if quantity else holding.quantity
        if sell_qty > holding.quantity:
            sell_qty = holding.quantity

        # 슬리피지 적용
        exec_price = price * (1 - self.config.slippage_pct)

        # 금액 계산
        gross_amount = exec_price * sell_qty
        commission = max(
            gross_amount * self.config.commission_rate,
            self.config.min_commission
        )
        tax = gross_amount * self.config.tax_rate
        net_amount = gross_amount - commission - tax

        # 손익 계산
        cost_basis = holding.avg_price * sell_qty
        realized_pnl = net_amount - cost_basis + commission + tax

        # 실행
        self._cash += net_amount
        self._realized_pnl += realized_pnl
        self._transaction_count += 1

        if sell_qty >= holding.quantity:
            # 전량 매도
            del self._holdings[stock_code]
        else:
            # 일부 매도
            holding.quantity -= sell_qty
            holding.current_price = exec_price

        logger.info(
            f"SELL: {stock_code} {sell_qty}주 @ {exec_price:,.0f}원 "
            f"(손익: {realized_pnl:+,.0f}원)"
        )

        return {
            'success': True,
            'stock_code': stock_code,
            'quantity': sell_qty,
            'price': exec_price,
            'gross_amount': gross_amount,
            'commission': commission,
            'tax': tax,
            'net_amount': net_amount,
            'realized_pnl': realized_pnl,
            'remaining_cash': self._cash,
        }

    def update_prices(self, prices: Dict[str, float]) -> None:
        """
        가격 업데이트

        Args:
            prices: {종목코드: 현재가} 딕셔너리
        """
        for stock_code, price in prices.items():
            if stock_code in self._holdings:
                self._holdings[stock_code].current_price = price

    def get_holding(self, stock_code: str) -> Optional[Holding]:
        """보유 종목 조회"""
        return self._holdings.get(stock_code)

    def get_holdings(self) -> Dict[str, Holding]:
        """전체 보유 종목"""
        return self._holdings.copy()

    def get_position_weight(self, stock_code: str) -> float:
        """포지션 비중"""
        if stock_code not in self._holdings:
            return 0.0

        if self.total_value == 0:
            return 0.0

        return self._holdings[stock_code].market_value / self.total_value

    def get_snapshot(self) -> PortfolioSnapshot:
        """현재 스냅샷 조회 (이력에 저장 안함)"""
        return PortfolioSnapshot(
            timestamp=datetime.now(),
            cash=self._cash,
            holdings_value=self.holdings_value,
            total_value=self.total_value,
            realized_pnl=self._realized_pnl,
            unrealized_pnl=self.unrealized_pnl,
            total_pnl=self.total_pnl,
            total_pnl_pct=self.total_pnl_pct,
            num_positions=len(self._holdings),
        )

    def take_snapshot(self) -> PortfolioSnapshot:
        """스냅샷 생성 및 이력에 저장"""
        snapshot = self.get_snapshot()
        self._snapshots.append(snapshot)
        return snapshot

    def get_snapshots(
        self,
        limit: Optional[int] = None
    ) -> List[PortfolioSnapshot]:
        """스냅샷 이력"""
        if limit:
            return self._snapshots[-limit:]
        return self._snapshots.copy()

    def reset(self) -> None:
        """포트폴리오 초기화"""
        self._cash = self.config.initial_capital
        self._holdings.clear()
        self._realized_pnl = 0.0
        self._snapshots.clear()
        self._transaction_count = 0

        logger.info("Portfolio reset")

    def get_summary(self) -> Dict[str, Any]:
        """요약 정보"""
        return {
            'initial_capital': self._initial_capital,
            'cash': self._cash,
            'cash_pct': self._cash / self.total_value if self.total_value > 0 else 1.0,
            'holdings_value': self.holdings_value,
            'total_value': self.total_value,
            'realized_pnl': self._realized_pnl,
            'unrealized_pnl': self.unrealized_pnl,
            'total_pnl': self.total_pnl,
            'total_pnl_pct': self.total_pnl_pct,
            'num_positions': len(self._holdings),
            'transaction_count': self._transaction_count,
            'holdings': {
                code: holding.to_dict()
                for code, holding in self._holdings.items()
            },
        }

    def can_buy(
        self,
        stock_code: str,
        price: float,
        quantity: int
    ) -> Dict[str, Any]:
        """
        매수 가능 여부 체크

        Args:
            stock_code: 종목 코드
            price: 가격
            quantity: 수량

        Returns:
            Dict: 체크 결과
        """
        gross_amount = price * quantity
        commission = max(
            gross_amount * self.config.commission_rate,
            self.config.min_commission
        )
        total_cost = gross_amount + commission

        # 자금 체크
        if total_cost > self._cash:
            return {
                'can_buy': False,
                'reason': 'insufficient_cash',
                'required': total_cost,
                'available': self._cash,
                'max_quantity': int(self._cash / (price * (1 + self.config.commission_rate))),
            }

        # 포지션 수 체크
        if stock_code not in self._holdings:
            if len(self._holdings) >= self.config.max_positions:
                return {
                    'can_buy': False,
                    'reason': 'max_positions_reached',
                }

        # 비중 체크
        new_value = gross_amount
        if stock_code in self._holdings:
            new_value += self._holdings[stock_code].market_value

        position_pct = new_value / self.total_value if self.total_value > 0 else 1.0

        if position_pct > self.config.max_position_pct:
            return {
                'can_buy': False,
                'reason': 'position_limit_exceeded',
                'position_pct': position_pct,
                'max_pct': self.config.max_position_pct,
            }

        return {
            'can_buy': True,
            'total_cost': total_cost,
            'commission': commission,
        }
