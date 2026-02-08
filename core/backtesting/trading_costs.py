#!/usr/bin/env python3
"""
거래 비용 계산 모듈
한국 주식 거래 비용을 정확히 반영
"""

from core.utils.log_utils import get_logger

logger = get_logger(__name__)


class TradingCosts:
    """거래 비용 계산 클래스"""

    # 한국투자증권 가상계좌 수수료율 (2024년 기준)
    COMMISSION_RATE = 0.00015  # 0.015% (거래소 수수료 포함)
    TRANSACTION_TAX = 0.0023   # 0.23% (매도만, 증권거래세)
    SLIPPAGE_RATE = 0.0005     # 0.05% (예상 슬리피지)

    def __init__(self):
        """초기화"""
        self.logger = logger
        self.logger.info(
            f"거래 비용 초기화 - 수수료: {self.COMMISSION_RATE:.4%}, "
            f"거래세: {self.TRANSACTION_TAX:.4%}, 슬리피지: {self.SLIPPAGE_RATE:.4%}"
        )

    def calculate_buy_cost(self, price: float, quantity: int) -> float:
        """매수 비용 계산 (총 지불 금액)

        Args:
            price: 매수가
            quantity: 수량

        Returns:
            총 지불 금액 (가격 × 수량 + 수수료 + 슬리피지)
        """
        try:
            gross = price * quantity
            commission = gross * self.COMMISSION_RATE
            slippage = gross * self.SLIPPAGE_RATE

            total_cost = gross + commission + slippage

            self.logger.debug(
                f"매수 비용: {gross:,.0f}원 + 수수료 {commission:,.0f}원 + "
                f"슬리피지 {slippage:,.0f}원 = {total_cost:,.0f}원"
            )

            return total_cost

        except Exception as e:
            self.logger.error(f"매수 비용 계산 오류: {e}", exc_info=True)
            return price * quantity

    def calculate_sell_proceeds(self, price: float, quantity: int) -> float:
        """매도 수령액 계산 (실제 받는 금액)

        Args:
            price: 매도가
            quantity: 수량

        Returns:
            실제 수령액 (가격 × 수량 - 수수료 - 거래세 - 슬리피지)
        """
        try:
            gross = price * quantity
            commission = gross * self.COMMISSION_RATE
            tax = gross * self.TRANSACTION_TAX
            slippage = gross * self.SLIPPAGE_RATE

            net_proceeds = gross - commission - tax - slippage

            self.logger.debug(
                f"매도 수령액: {gross:,.0f}원 - 수수료 {commission:,.0f}원 - "
                f"거래세 {tax:,.0f}원 - 슬리피지 {slippage:,.0f}원 = {net_proceeds:,.0f}원"
            )

            return net_proceeds

        except Exception as e:
            self.logger.error(f"매도 수령액 계산 오류: {e}", exc_info=True)
            return price * quantity

    def calculate_net_pnl(
        self,
        buy_price: float,
        sell_price: float,
        quantity: int
    ) -> float:
        """순손익 계산 (비용 반영 후)

        Args:
            buy_price: 매수가
            sell_price: 매도가
            quantity: 수량

        Returns:
            순손익 (매도 수령액 - 매수 비용)
        """
        try:
            buy_cost = self.calculate_buy_cost(buy_price, quantity)
            sell_proceeds = self.calculate_sell_proceeds(sell_price, quantity)

            net_pnl = sell_proceeds - buy_cost

            self.logger.debug(
                f"순손익: 매도수령 {sell_proceeds:,.0f}원 - 매수비용 {buy_cost:,.0f}원 = "
                f"{net_pnl:+,.0f}원"
            )

            return net_pnl

        except Exception as e:
            self.logger.error(f"순손익 계산 오류: {e}", exc_info=True)
            return (sell_price - buy_price) * quantity

    def get_total_cost_rate(self, is_buy: bool = True) -> float:
        """총 비용률 조회

        Args:
            is_buy: 매수 여부 (False면 매도)

        Returns:
            총 비용률 (소수)
        """
        if is_buy:
            return self.COMMISSION_RATE + self.SLIPPAGE_RATE
        else:
            return self.COMMISSION_RATE + self.TRANSACTION_TAX + self.SLIPPAGE_RATE

    def calculate_breakeven_price(self, buy_price: float) -> float:
        """손익분기점 가격 계산

        Args:
            buy_price: 매수가

        Returns:
            손익분기점 가격 (비용을 감안한 최소 매도가)
        """
        try:
            # 매수 비용률
            buy_cost_rate = self.get_total_cost_rate(is_buy=True)

            # 매도 비용률
            sell_cost_rate = self.get_total_cost_rate(is_buy=False)

            # 손익분기점 = 매수가 × (1 + 매수비용률) / (1 - 매도비용률)
            breakeven = buy_price * (1 + buy_cost_rate) / (1 - sell_cost_rate)

            breakeven_pct = (breakeven - buy_price) / buy_price

            self.logger.debug(
                f"손익분기점: 매수가 {buy_price:,.0f}원 → "
                f"최소 매도가 {breakeven:,.0f}원 (+{breakeven_pct:.2%})"
            )

            return breakeven

        except Exception as e:
            self.logger.error(f"손익분기점 계산 오류: {e}", exc_info=True)
            return buy_price


# 편의 함수
def calculate_net_pnl(buy_price: float, sell_price: float, quantity: int) -> float:
    """순손익 계산 편의 함수

    Args:
        buy_price: 매수가
        sell_price: 매도가
        quantity: 수량

    Returns:
        순손익 (비용 반영 후)
    """
    costs = TradingCosts()
    return costs.calculate_net_pnl(buy_price, sell_price, quantity)
