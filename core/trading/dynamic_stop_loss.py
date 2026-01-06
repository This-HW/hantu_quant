"""
ATR 기반 동적 손절/익절 시스템 (P1-1)

기능:
- ATR(14일) 계산을 통한 변동성 측정
- 동적 손절가 = 진입가 - ATR × 배수
- 동적 익절가 = 진입가 + ATR × 배수
- 트레일링 스탑 자동 조정
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, Optional, List, Tuple
from datetime import datetime

from ..utils.log_utils import get_logger

logger = get_logger(__name__)


@dataclass
class StopLossResult:
    """손절/익절 계산 결과"""
    entry_price: int
    stop_loss: int
    take_profit: int
    atr: float
    atr_percent: float  # ATR / 현재가 비율
    risk_reward_ratio: float  # 손익비
    stop_distance_pct: float  # 손절까지 거리 (%)
    profit_distance_pct: float  # 익절까지 거리 (%)
    calculation_time: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class TrailingStopState:
    """트레일링 스탑 상태"""
    stock_code: str
    entry_price: int
    highest_price: int
    current_stop: int
    initial_stop: int
    atr: float
    trailing_multiplier: float
    is_activated: bool = False  # 트레일링 활성화 여부 (일정 수익 도달 후)
    activation_threshold: float = 0.02  # 2% 수익 후 트레일링 활성화


class DynamicStopLossCalculator:
    """ATR 기반 동적 손절/익절 계산기"""

    def __init__(
        self,
        atr_period: int = 14,
        stop_multiplier: float = 2.0,
        profit_multiplier: float = 3.0,
        trailing_multiplier: float = 1.5,
        min_stop_pct: float = 0.02,  # 최소 손절 2%
        max_stop_pct: float = 0.10,  # 최대 손절 10%
    ):
        """초기화

        Args:
            atr_period: ATR 계산 기간 (기본 14일)
            stop_multiplier: 손절 ATR 배수 (기본 2.0)
            profit_multiplier: 익절 ATR 배수 (기본 3.0)
            trailing_multiplier: 트레일링 스탑 ATR 배수 (기본 1.5)
            min_stop_pct: 최소 손절 비율 (기본 2%)
            max_stop_pct: 최대 손절 비율 (기본 10%)
        """
        self.atr_period = atr_period
        self.stop_multiplier = stop_multiplier
        self.profit_multiplier = profit_multiplier
        self.trailing_multiplier = trailing_multiplier
        self.min_stop_pct = min_stop_pct
        self.max_stop_pct = max_stop_pct

        # 트레일링 스탑 상태 관리
        self._trailing_states: Dict[str, TrailingStopState] = {}

        logger.info(
            f"DynamicStopLossCalculator 초기화 - "
            f"ATR기간: {atr_period}, 손절배수: {stop_multiplier}, "
            f"익절배수: {profit_multiplier}, 트레일링배수: {trailing_multiplier}"
        )

    def calculate_atr(self, df: pd.DataFrame) -> float:
        """ATR (Average True Range) 계산

        Args:
            df: OHLCV 데이터프레임 (high, low, close 컬럼 필요)

        Returns:
            ATR 값
        """
        if df is None or len(df) < self.atr_period:
            logger.warning(f"데이터 부족: {len(df) if df is not None else 0}일 (최소 {self.atr_period}일 필요)")
            return 0.0

        try:
            high = df['high']
            low = df['low']
            close = df['close'].shift(1)

            # True Range 계산
            tr1 = high - low  # 당일 고가 - 당일 저가
            tr2 = abs(high - close)  # 당일 고가 - 전일 종가
            tr3 = abs(low - close)  # 당일 저가 - 전일 종가

            true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

            # ATR = True Range의 이동평균
            atr = true_range.rolling(window=self.atr_period).mean().iloc[-1]

            if pd.isna(atr):
                logger.warning("ATR 계산 결과가 NaN입니다")
                return 0.0

            return float(atr)

        except Exception as e:
            logger.error(f"ATR 계산 오류: {e}", exc_info=True)
            return 0.0

    def calculate_atr_from_prices(
        self,
        high_prices: List[float],
        low_prices: List[float],
        close_prices: List[float]
    ) -> float:
        """가격 리스트로부터 ATR 계산

        Args:
            high_prices: 고가 리스트
            low_prices: 저가 리스트
            close_prices: 종가 리스트

        Returns:
            ATR 값
        """
        if len(close_prices) < self.atr_period:
            logger.warning(f"데이터 부족: {len(close_prices)}일")
            return 0.0

        df = pd.DataFrame({
            'high': high_prices,
            'low': low_prices,
            'close': close_prices
        })

        return self.calculate_atr(df)

    def get_stops(
        self,
        entry_price: int,
        df: pd.DataFrame,
        custom_stop_mult: Optional[float] = None,
        custom_profit_mult: Optional[float] = None
    ) -> StopLossResult:
        """동적 손절/익절 가격 계산

        Args:
            entry_price: 진입가
            df: OHLCV 데이터프레임
            custom_stop_mult: 커스텀 손절 배수 (None이면 기본값)
            custom_profit_mult: 커스텀 익절 배수 (None이면 기본값)

        Returns:
            StopLossResult 객체
        """
        atr = self.calculate_atr(df)

        stop_mult = custom_stop_mult or self.stop_multiplier
        profit_mult = custom_profit_mult or self.profit_multiplier

        return self._calculate_stops_from_atr(entry_price, atr, stop_mult, profit_mult)

    def get_stops_from_atr(
        self,
        entry_price: int,
        atr: float,
        custom_stop_mult: Optional[float] = None,
        custom_profit_mult: Optional[float] = None
    ) -> StopLossResult:
        """ATR 값으로부터 직접 손절/익절 계산

        Args:
            entry_price: 진입가
            atr: ATR 값
            custom_stop_mult: 커스텀 손절 배수
            custom_profit_mult: 커스텀 익절 배수

        Returns:
            StopLossResult 객체
        """
        stop_mult = custom_stop_mult or self.stop_multiplier
        profit_mult = custom_profit_mult or self.profit_multiplier

        return self._calculate_stops_from_atr(entry_price, atr, stop_mult, profit_mult)

    def _calculate_stops_from_atr(
        self,
        entry_price: int,
        atr: float,
        stop_mult: float,
        profit_mult: float
    ) -> StopLossResult:
        """ATR 기반 손절/익절 내부 계산"""

        # ATR이 0인 경우 기본 비율 사용
        if atr <= 0:
            logger.warning("ATR이 0이므로 기본 비율 사용 (손절 3%, 익절 8%)")
            stop_loss = int(entry_price * (1 - 0.03))
            take_profit = int(entry_price * (1 + 0.08))
            atr_percent = 0.0
        else:
            # 손절가 계산
            stop_distance = atr * stop_mult
            stop_loss = int(entry_price - stop_distance)

            # 익절가 계산
            profit_distance = atr * profit_mult
            take_profit = int(entry_price + profit_distance)

            # ATR 비율
            atr_percent = atr / entry_price

        # 손절 비율 제한 적용
        stop_distance_pct = (entry_price - stop_loss) / entry_price

        if stop_distance_pct < self.min_stop_pct:
            stop_loss = int(entry_price * (1 - self.min_stop_pct))
            stop_distance_pct = self.min_stop_pct
            logger.debug(f"최소 손절 비율({self.min_stop_pct:.1%}) 적용")
        elif stop_distance_pct > self.max_stop_pct:
            stop_loss = int(entry_price * (1 - self.max_stop_pct))
            stop_distance_pct = self.max_stop_pct
            logger.debug(f"최대 손절 비율({self.max_stop_pct:.1%}) 적용")

        # 익절 거리 비율
        profit_distance_pct = (take_profit - entry_price) / entry_price

        # 손익비 계산
        risk_reward_ratio = profit_distance_pct / stop_distance_pct if stop_distance_pct > 0 else 0

        result = StopLossResult(
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            atr=atr,
            atr_percent=atr_percent,
            risk_reward_ratio=risk_reward_ratio,
            stop_distance_pct=stop_distance_pct,
            profit_distance_pct=profit_distance_pct
        )

        logger.info(
            f"동적 손절/익절 계산 완료 - "
            f"진입가: {entry_price:,}원, 손절가: {stop_loss:,}원 ({stop_distance_pct:.1%}), "
            f"익절가: {take_profit:,}원 ({profit_distance_pct:.1%}), "
            f"ATR: {atr:.0f}원, 손익비: {risk_reward_ratio:.2f}"
        )

        return result

    # ========== 트레일링 스탑 기능 ==========

    def init_trailing_stop(
        self,
        stock_code: str,
        entry_price: int,
        df: pd.DataFrame,
        activation_threshold: float = 0.02
    ) -> TrailingStopState:
        """트레일링 스탑 초기화

        Args:
            stock_code: 종목 코드
            entry_price: 진입가
            df: OHLCV 데이터프레임
            activation_threshold: 활성화 임계값 (기본 2% 수익 시)

        Returns:
            TrailingStopState 객체
        """
        atr = self.calculate_atr(df)
        initial_stop = int(entry_price - atr * self.stop_multiplier)

        # 최소 손절 비율 적용
        min_stop = int(entry_price * (1 - self.max_stop_pct))
        initial_stop = max(initial_stop, min_stop)

        state = TrailingStopState(
            stock_code=stock_code,
            entry_price=entry_price,
            highest_price=entry_price,
            current_stop=initial_stop,
            initial_stop=initial_stop,
            atr=atr,
            trailing_multiplier=self.trailing_multiplier,
            is_activated=False,
            activation_threshold=activation_threshold
        )

        self._trailing_states[stock_code] = state

        logger.info(
            f"트레일링 스탑 초기화 - {stock_code}: "
            f"진입가 {entry_price:,}원, 초기 손절가 {initial_stop:,}원, "
            f"ATR {atr:.0f}원"
        )

        return state

    def update_trailing_stop(
        self,
        stock_code: str,
        current_price: int
    ) -> Tuple[int, bool]:
        """트레일링 스탑 업데이트

        Args:
            stock_code: 종목 코드
            current_price: 현재가

        Returns:
            (새로운 손절가, 손절 트리거 여부)
        """
        if stock_code not in self._trailing_states:
            logger.warning(f"트레일링 스탑 상태 없음: {stock_code}")
            return 0, False

        state = self._trailing_states[stock_code]

        # 트레일링 활성화 체크
        profit_pct = (current_price - state.entry_price) / state.entry_price

        if not state.is_activated and profit_pct >= state.activation_threshold:
            state.is_activated = True
            logger.info(
                f"트레일링 스탑 활성화 - {stock_code}: "
                f"현재 수익률 {profit_pct:.1%} >= {state.activation_threshold:.1%}"
            )

        # 손절 트리거 체크
        if current_price <= state.current_stop:
            logger.warning(
                f"🔴 트레일링 스탑 트리거 - {stock_code}: "
                f"현재가 {current_price:,}원 <= 손절가 {state.current_stop:,}원"
            )
            return state.current_stop, True

        # 트레일링 활성화 상태에서 신고가 갱신 시 손절가 조정
        if state.is_activated and current_price > state.highest_price:
            old_stop = state.current_stop
            state.highest_price = current_price

            # 새로운 손절가 = 신고가 - ATR × 트레일링 배수
            new_stop = int(current_price - state.atr * state.trailing_multiplier)

            # 손절가는 올라가기만 함 (내려가지 않음)
            if new_stop > state.current_stop:
                state.current_stop = new_stop
                logger.info(
                    f"트레일링 스탑 조정 - {stock_code}: "
                    f"신고가 {current_price:,}원, "
                    f"손절가 {old_stop:,}원 → {new_stop:,}원"
                )

        return state.current_stop, False

    def get_trailing_state(self, stock_code: str) -> Optional[TrailingStopState]:
        """트레일링 스탑 상태 조회"""
        return self._trailing_states.get(stock_code)

    def remove_trailing_state(self, stock_code: str) -> bool:
        """트레일링 스탑 상태 제거 (포지션 종료 시)"""
        if stock_code in self._trailing_states:
            del self._trailing_states[stock_code]
            logger.info(f"트레일링 스탑 상태 제거: {stock_code}")
            return True
        return False

    def get_all_trailing_states(self) -> Dict[str, TrailingStopState]:
        """모든 트레일링 스탑 상태 조회"""
        return self._trailing_states.copy()

    # ========== 시장 상황별 설정 ==========

    def get_market_adjusted_multipliers(
        self,
        market_volatility: str
    ) -> Tuple[float, float, float]:
        """시장 변동성에 따른 배수 조정

        Args:
            market_volatility: 시장 변동성 수준
                              ('very_low', 'low', 'normal', 'high', 'very_high')

        Returns:
            (손절배수, 익절배수, 트레일링배수) 튜플
        """
        configs = {
            'very_low': (1.5, 2.5, 1.0),   # 저변동성: 타이트한 손절
            'low': (1.8, 2.8, 1.2),
            'normal': (2.0, 3.0, 1.5),      # 기본값
            'high': (2.5, 3.5, 2.0),        # 고변동성: 넓은 손절
            'very_high': (3.0, 4.0, 2.5),
        }

        return configs.get(market_volatility, (2.0, 3.0, 1.5))


# 편의 함수
def calculate_dynamic_stops(
    entry_price: int,
    df: pd.DataFrame,
    atr_period: int = 14,
    stop_multiplier: float = 2.0,
    profit_multiplier: float = 3.0
) -> StopLossResult:
    """동적 손절/익절 계산 편의 함수

    Args:
        entry_price: 진입가
        df: OHLCV 데이터프레임
        atr_period: ATR 기간
        stop_multiplier: 손절 배수
        profit_multiplier: 익절 배수

    Returns:
        StopLossResult 객체
    """
    calculator = DynamicStopLossCalculator(
        atr_period=atr_period,
        stop_multiplier=stop_multiplier,
        profit_multiplier=profit_multiplier
    )

    return calculator.get_stops(entry_price, df)


def calculate_atr(df: pd.DataFrame, period: int = 14) -> float:
    """ATR 계산 편의 함수

    Args:
        df: OHLCV 데이터프레임
        period: ATR 기간

    Returns:
        ATR 값
    """
    calculator = DynamicStopLossCalculator(atr_period=period)
    return calculator.calculate_atr(df)
