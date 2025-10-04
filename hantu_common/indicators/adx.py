"""
ADX (Average Directional Index) 지표
추세의 강도를 측정하는 지표
"""

import numpy as np
import pandas as pd
from typing import Optional, Dict, Any, Tuple


class ADX:
    """ADX 계산 및 분석"""

    @staticmethod
    def calculate_true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
        """
        True Range 계산

        Args:
            high: 고가 시리즈
            low: 저가 시리즈
            close: 종가 시리즈

        Returns:
            True Range 시리즈
        """
        high_low = high - low
        high_close = np.abs(high - close.shift(1))
        low_close = np.abs(low - close.shift(1))

        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return tr

    @staticmethod
    def calculate_directional_movement(high: pd.Series, low: pd.Series) -> Tuple[pd.Series, pd.Series]:
        """
        방향성 움직임 계산

        Args:
            high: 고가 시리즈
            low: 저가 시리즈

        Returns:
            +DM, -DM 시리즈
        """
        up_move = high - high.shift(1)
        down_move = low.shift(1) - low

        plus_dm = pd.Series(np.where(
            (up_move > down_move) & (up_move > 0), up_move, 0
        ), index=high.index)

        minus_dm = pd.Series(np.where(
            (down_move > up_move) & (down_move > 0), down_move, 0
        ), index=low.index)

        return plus_dm, minus_dm

    @staticmethod
    def calculate(high: pd.Series, low: pd.Series, close: pd.Series,
                  period: int = 14) -> Dict[str, pd.Series]:
        """
        ADX 계산

        Args:
            high: 고가 시리즈
            low: 저가 시리즈
            close: 종가 시리즈
            period: 계산 기간

        Returns:
            ADX, +DI, -DI를 포함한 딕셔너리
        """
        # True Range 계산
        tr = ADX.calculate_true_range(high, low, close)

        # Directional Movement 계산
        plus_dm, minus_dm = ADX.calculate_directional_movement(high, low)

        # Smoothed 계산 (Wilder's smoothing)
        atr = tr.ewm(alpha=1/period, min_periods=period).mean()
        plus_dm_smooth = plus_dm.ewm(alpha=1/period, min_periods=period).mean()
        minus_dm_smooth = minus_dm.ewm(alpha=1/period, min_periods=period).mean()

        # Directional Indicators 계산
        plus_di = (plus_dm_smooth / atr) * 100
        minus_di = (minus_dm_smooth / atr) * 100

        # DX 계산
        di_sum = plus_di + minus_di
        di_diff = np.abs(plus_di - minus_di)
        dx = (di_diff / di_sum) * 100

        # ADX 계산 (DX의 이동평균)
        adx = dx.ewm(alpha=1/period, min_periods=period).mean()

        return {
            'adx': adx,
            'plus_di': plus_di,
            'minus_di': minus_di,
            'dx': dx
        }

    @staticmethod
    def analyze_trend_strength(adx_value: float) -> str:
        """
        ADX 값으로 추세 강도 분석

        Args:
            adx_value: ADX 값

        Returns:
            추세 강도 설명
        """
        if adx_value < 20:
            return 'no_trend'
        elif adx_value < 25:
            return 'weak_trend'
        elif adx_value < 35:
            return 'moderate_trend'
        elif adx_value < 50:
            return 'strong_trend'
        else:
            return 'very_strong_trend'

    @staticmethod
    def get_trend_direction(plus_di: float, minus_di: float) -> str:
        """
        추세 방향 판단

        Args:
            plus_di: +DI 값
            minus_di: -DI 값

        Returns:
            추세 방향
        """
        if plus_di > minus_di:
            return 'bullish'
        elif minus_di > plus_di:
            return 'bearish'
        else:
            return 'neutral'

    @staticmethod
    def analyze(adx: float, plus_di: float, minus_di: float,
               adx_prev: Optional[float] = None) -> Dict[str, Any]:
        """
        ADX 종합 분석

        Args:
            adx: 현재 ADX 값
            plus_di: 현재 +DI 값
            minus_di: 현재 -DI 값
            adx_prev: 이전 ADX 값

        Returns:
            분석 결과 딕셔너리
        """
        result = {
            'adx': adx,
            'plus_di': plus_di,
            'minus_di': minus_di,
            'trend_strength': ADX.analyze_trend_strength(adx),
            'trend_direction': ADX.get_trend_direction(plus_di, minus_di),
            'signal': None
        }

        # 추세 강도 변화
        if adx_prev:
            result['adx_rising'] = adx > adx_prev
            result['trend_developing'] = adx > adx_prev and adx > 20

        # 매매 신호 판단
        if adx > 25:  # 추세 존재
            if plus_di > minus_di and plus_di - minus_di > 10:
                result['signal'] = 'strong_buy'
            elif plus_di > minus_di:
                result['signal'] = 'buy'
            elif minus_di > plus_di and minus_di - plus_di > 10:
                result['signal'] = 'strong_sell'
            elif minus_di > plus_di:
                result['signal'] = 'sell'
        else:  # 추세 없음
            result['signal'] = 'no_trade'

        return result

    @staticmethod
    def calculate_di_crossover(plus_di: pd.Series, minus_di: pd.Series) -> pd.Series:
        """
        DI 교차 신호 계산

        Args:
            plus_di: +DI 시리즈
            minus_di: -DI 시리즈

        Returns:
            교차 신호 (1: 골든크로스, -1: 데드크로스, 0: 없음)
        """
        bullish = plus_di > minus_di
        golden_cross = (bullish & ~bullish.shift(1)).astype(int)
        death_cross = (~bullish & bullish.shift(1)).astype(int) * -1

        return golden_cross + death_cross

    @staticmethod
    def get_trade_signals(df: pd.DataFrame, adx_threshold: float = 25,
                         di_diff_threshold: float = 5) -> pd.DataFrame:
        """
        ADX 기반 매매 신호 생성

        Args:
            df: OHLCV 데이터프레임
            adx_threshold: ADX 임계값
            di_diff_threshold: DI 차이 임계값

        Returns:
            매매 신호가 포함된 데이터프레임
        """
        # ADX 계산
        adx_data = ADX.calculate(df['high'], df['low'], df['close'])

        signals = pd.DataFrame(index=df.index)
        signals['adx'] = adx_data['adx']
        signals['plus_di'] = adx_data['plus_di']
        signals['minus_di'] = adx_data['minus_di']

        # DI 교차 신호
        signals['di_crossover'] = ADX.calculate_di_crossover(
            adx_data['plus_di'], adx_data['minus_di']
        )

        # 매수 신호: 강한 추세 + +DI > -DI
        buy_condition = (
            (signals['adx'] > adx_threshold) &
            (signals['plus_di'] > signals['minus_di']) &
            (signals['plus_di'] - signals['minus_di'] > di_diff_threshold) &
            ((signals['di_crossover'] == 1) | (signals['adx'] > signals['adx'].shift(1)))
        )

        # 매도 신호: 추세 약화 또는 -DI > +DI
        sell_condition = (
            ((signals['adx'] < adx_threshold) & (signals['adx'] < signals['adx'].shift(1))) |
            ((signals['minus_di'] > signals['plus_di']) &
             (signals['minus_di'] - signals['plus_di'] > di_diff_threshold))
        )

        signals['buy_signal'] = buy_condition.astype(int)
        signals['sell_signal'] = sell_condition.astype(int)

        # 추세 강도 레이블
        signals['trend_strength'] = signals['adx'].apply(ADX.analyze_trend_strength)

        return signals