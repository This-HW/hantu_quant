"""
포지션 사이징 엔진 (ATR 기반)
30년 퀀트 경험 기반 - 리스크 동일화 원칙

핵심 원리:
- 모든 종목이 포트폴리오에 동일한 리스크 기여
- 변동성 높은 종목 = 적은 비중
- 변동성 낮은 종목 = 많은 비중
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from core.utils.log_utils import get_logger
from core.selection.quant_config import get_quant_config, QuantConfig

logger = get_logger(__name__)


@dataclass
class PositionSize:
    """포지션 사이징 결과"""
    stock_code: str

    # 포지션 크기
    weight: float                   # 포트폴리오 비중 (0-1)
    amount: float                   # 투자 금액
    shares: int                     # 주식 수량

    # 손절/익절 가격
    stop_loss: float
    target_price: float
    expected_return: float          # 기대 수익률 (%)

    # 변동성 정보
    atr_value: float                # ATR 값
    daily_volatility: float         # 일일 변동성 (%)

    # 리스크 정보
    risk_amount: float              # 리스크 금액 (손실 시)
    risk_reward_ratio: float        # 손익비


class PositionSizer:
    """
    ATR 기반 포지션 사이징 엔진

    사용법:
        sizer = PositionSizer()
        position = sizer.calculate_position(
            stock_code="005930",
            current_price=70000,
            total_capital=10000000,
            price_data=df
        )
    """

    def __init__(
        self,
        config: Optional[QuantConfig] = None,
        api_client=None  # API 인스턴스 주입 (Rate Limit 공유용)
    ):
        """
        초기화

        Args:
            config: 퀀트 설정 (None이면 기본값 사용)
            api_client: KIS API 클라이언트 (None이면 내부 생성)
        """
        self.config = config or get_quant_config()
        self.ps_config = self.config.position_sizing
        self.logger = logger
        self._api = api_client  # 외부 주입 또는 None (지연 로딩)

    @property
    def api(self):
        """API 클라이언트 지연 로딩"""
        if self._api is None:
            from core.api.kis_api import KISAPI
            self._api = KISAPI()
        return self._api

    def calculate_position(
        self,
        stock_code: str,
        current_price: float,
        total_capital: float,
        price_data: Optional[pd.DataFrame] = None
    ) -> PositionSize:
        """
        단일 종목 포지션 사이징

        Args:
            stock_code: 종목코드
            current_price: 현재가
            total_capital: 총 투자 자본금
            price_data: 일봉 데이터 (없으면 자동 조회)

        Returns:
            PositionSize: 포지션 사이징 결과
        """
        try:
            # 1. 일봉 데이터 확보
            if price_data is None:
                price_data = self.api.get_daily_chart(stock_code, period_days=30)

            if price_data is None or len(price_data) < self.ps_config.atr_period:
                return self._create_default_position(stock_code, current_price, total_capital)

            # 2. ATR 계산
            atr = self._calculate_atr(price_data)

            # 3. 일일 변동성 계산
            daily_vol = atr / current_price

            # 4. 포지션 비중 계산 (변동성 기반)
            raw_weight = self.ps_config.target_daily_vol / daily_vol if daily_vol > 0 else 0.05

            # 5. 상하한 적용
            weight = max(
                self.ps_config.min_position_pct,
                min(raw_weight, self.ps_config.max_position_pct)
            )

            # 레짐 조정 적용
            adjusted = self.config.get_adjusted_config()
            weight = min(weight, adjusted.get('max_position_pct', self.ps_config.max_position_pct))

            # 6. 투자 금액 및 수량 계산
            amount = total_capital * weight
            shares = int(amount / current_price) if current_price > 0 else 0

            # 실제 투자 금액 재계산 (정수 주식)
            actual_amount = shares * current_price
            actual_weight = actual_amount / total_capital if total_capital > 0 else 0

            # 7. 손절/익절 가격 계산 (ATR 기반)
            stop_loss_atr = adjusted.get('stop_loss_atr', self.ps_config.stop_loss_atr)
            stop_loss = current_price - (atr * stop_loss_atr)
            target_price = current_price + (atr * self.ps_config.take_profit_atr)

            # 8. 기대 수익률 및 리스크 계산
            expected_return = ((target_price / current_price) - 1) * 100
            risk_amount = (current_price - stop_loss) * shares
            risk_reward_ratio = self.ps_config.take_profit_atr / stop_loss_atr

            return PositionSize(
                stock_code=stock_code,
                weight=round(actual_weight, 4),
                amount=actual_amount,
                shares=shares,
                stop_loss=round(stop_loss, 0),
                target_price=round(target_price, 0),
                expected_return=round(expected_return, 2),
                atr_value=round(atr, 2),
                daily_volatility=round(daily_vol * 100, 2),
                risk_amount=round(risk_amount, 0),
                risk_reward_ratio=round(risk_reward_ratio, 2)
            )

        except Exception as e:
            self.logger.error(f"포지션 사이징 오류 ({stock_code}): {e}", exc_info=True)
            return self._create_default_position(stock_code, current_price, total_capital)

    def calculate_portfolio_positions(
        self,
        stocks: List[Dict],
        total_capital: float
    ) -> Tuple[List[PositionSize], Dict]:
        """
        포트폴리오 전체 포지션 사이징

        Args:
            stocks: 선정 종목 리스트
                각 항목: {stock_code, current_price, price_data(optional)}
            total_capital: 총 투자 자본금

        Returns:
            Tuple[List[PositionSize], Dict]: (포지션 리스트, 포트폴리오 통계)
        """
        positions = []
        total_weight = 0.0
        total_risk = 0.0

        for stock in stocks:
            position = self.calculate_position(
                stock_code=stock['stock_code'],
                current_price=stock['current_price'],
                total_capital=total_capital,
                price_data=stock.get('price_data')
            )
            positions.append(position)
            total_weight += position.weight
            total_risk += position.risk_amount

        # 포트폴리오 통계
        portfolio_stats = {
            'total_positions': len(positions),
            'total_weight': round(total_weight, 4),
            'cash_weight': round(1 - total_weight, 4),
            'total_risk': round(total_risk, 0),
            'avg_volatility': np.mean([p.daily_volatility for p in positions]) if positions else 0,
            'portfolio_volatility': self._estimate_portfolio_volatility(positions)
        }

        # 가중치 조정 (총합 > 1인 경우)
        if total_weight > 1.0:
            positions = self._normalize_weights(positions, total_capital)
            portfolio_stats['normalized'] = True

        return positions, portfolio_stats

    def _calculate_atr(self, df: pd.DataFrame) -> float:
        """
        ATR (Average True Range) 계산

        True Range = max(
            High - Low,
            abs(High - Previous Close),
            abs(Low - Previous Close)
        )
        ATR = EMA(True Range, period)
        """
        period = self.ps_config.atr_period

        if len(df) < period:
            return 0.0

        # True Range 계산
        df = df.copy()
        df['prev_close'] = df['close'].shift(1)
        df['tr1'] = df['high'] - df['low']
        df['tr2'] = abs(df['high'] - df['prev_close'])
        df['tr3'] = abs(df['low'] - df['prev_close'])
        df['true_range'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)

        # ATR 계산 (EMA)
        atr = df['true_range'].ewm(span=period, adjust=False).mean().iloc[-1]

        return atr if not np.isnan(atr) else 0.0

    def _estimate_portfolio_volatility(self, positions: List[PositionSize]) -> float:
        """
        포트폴리오 변동성 추정 (단순 가정: 상관계수 0.5)

        실제로는 종목 간 상관관계를 계산해야 하지만,
        단순화를 위해 평균 상관계수 0.5 가정
        """
        if not positions:
            return 0.0

        weights = [p.weight for p in positions]
        vols = [p.daily_volatility / 100 for p in positions]  # % → 소수

        # 단순 추정: sqrt(sum(w^2 * vol^2) + 2 * sum(wi * wj * voli * volj * corr))
        # corr = 0.5 가정
        corr = 0.5

        variance = 0.0
        for i, (wi, vi) in enumerate(zip(weights, vols)):
            variance += (wi ** 2) * (vi ** 2)
            for j in range(i + 1, len(weights)):
                wj, vj = weights[j], vols[j]
                variance += 2 * wi * wj * vi * vj * corr

        return round(np.sqrt(variance) * 100, 2)  # % 단위

    def _normalize_weights(
        self,
        positions: List[PositionSize],
        total_capital: float
    ) -> List[PositionSize]:
        """가중치 정규화 (총합 = 1.0 이하)"""
        total_weight = sum(p.weight for p in positions)

        if total_weight <= 1.0:
            return positions

        scale_factor = 0.95 / total_weight  # 5% 현금 유지

        normalized = []
        for p in positions:
            new_weight = p.weight * scale_factor
            new_amount = total_capital * new_weight

            # 주식 가격 계산: 기존 amount/shares에서 역산
            # stop_loss가 아닌 실제 주가를 사용해야 함
            share_price = p.amount / p.shares if p.shares > 0 else p.stop_loss
            new_shares = int(new_amount / share_price) if share_price > 0 else p.shares

            normalized.append(PositionSize(
                stock_code=p.stock_code,
                weight=round(new_weight, 4),
                amount=new_amount,
                shares=new_shares,
                stop_loss=p.stop_loss,
                target_price=p.target_price,
                expected_return=p.expected_return,
                atr_value=p.atr_value,
                daily_volatility=p.daily_volatility,
                risk_amount=p.risk_amount * scale_factor,
                risk_reward_ratio=p.risk_reward_ratio
            ))

        return normalized

    def _create_default_position(
        self,
        stock_code: str,
        current_price: float,
        total_capital: float
    ) -> PositionSize:
        """기본 포지션 (ATR 계산 실패 시)"""
        # 기본 비중 5%
        default_weight = 0.05
        amount = total_capital * default_weight
        shares = int(amount / current_price) if current_price > 0 else 0

        # 기본 손절/익절 (가격의 3%/5%)
        stop_loss = current_price * 0.97
        target_price = current_price * 1.05

        return PositionSize(
            stock_code=stock_code,
            weight=default_weight,
            amount=shares * current_price,
            shares=shares,
            stop_loss=round(stop_loss, 0),
            target_price=round(target_price, 0),
            expected_return=5.0,
            atr_value=0,
            daily_volatility=2.0,  # 기본 2%
            risk_amount=(current_price - stop_loss) * shares,
            risk_reward_ratio=1.67
        )

    def calculate_trailing_stop(
        self,
        entry_price: float,
        current_price: float,
        highest_price: float,
        atr: float
    ) -> Optional[float]:
        """
        트레일링 스탑 계산

        Args:
            entry_price: 진입가
            current_price: 현재가
            highest_price: 진입 후 최고가
            atr: ATR 값

        Returns:
            Optional[float]: 트레일링 스탑 가격 (활성화 안 됐으면 None)
        """
        if not self.ps_config.use_trailing_stop:
            return None

        # 수익률 확인
        current_return = (current_price / entry_price) - 1

        # 활성화 조건 확인
        if current_return < self.ps_config.trailing_activation_pct:
            return None

        # 트레일링 스탑 계산 (최고가 - 1.5 ATR)
        trailing_stop = highest_price - (atr * self.ps_config.trailing_atr)

        return round(trailing_stop, 0)

    def adjust_stop_loss(
        self,
        current_stop: float,
        current_price: float,
        atr: float,
        profit_pct: float
    ) -> float:
        """
        손절가 동적 조정

        수익률에 따라 손절가 상향 조정:
        - 수익 3% 이상: 손절가 = 진입가
        - 수익 5% 이상: 손절가 = 진입가 + 1 ATR
        - 수익 8% 이상: 손절가 = 현재가 - 1 ATR
        """
        if profit_pct >= 0.08:
            return current_price - atr
        elif profit_pct >= 0.05:
            return current_price - (atr * 1.5)
        elif profit_pct >= 0.03:
            return current_price - (atr * 2.0)

        return current_stop
