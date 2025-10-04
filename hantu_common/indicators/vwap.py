"""
VWAP (Volume Weighted Average Price) 지표
기관 투자자들이 주로 사용하는 거래 기준선
"""

import numpy as np
import pandas as pd
from typing import Optional, Dict, Any, Union, Tuple


class VWAP:
    """VWAP 계산 및 분석"""

    @staticmethod
    def calculate(prices: pd.Series, volumes: pd.Series,
                  high: Optional[pd.Series] = None,
                  low: Optional[pd.Series] = None) -> pd.Series:
        """
        VWAP 계산

        Args:
            prices: 종가 시리즈
            volumes: 거래량 시리즈
            high: 고가 시리즈 (optional)
            low: 저가 시리즈 (optional)

        Returns:
            VWAP 값 시리즈
        """
        # Typical Price 계산 (고가, 저가가 있으면 사용)
        if high is not None and low is not None:
            typical_price = (high + low + prices) / 3
        else:
            typical_price = prices

        # VWAP 계산
        cumulative_volume = volumes.cumsum()
        cumulative_pv = (typical_price * volumes).cumsum()

        vwap = cumulative_pv / cumulative_volume

        return vwap

    @staticmethod
    def calculate_intraday(df: pd.DataFrame,
                          reset_time: str = '09:00') -> pd.Series:
        """
        일중 VWAP 계산 (매일 리셋)

        Args:
            df: OHLCV 데이터프레임
            reset_time: VWAP 리셋 시간

        Returns:
            일중 VWAP 시리즈
        """
        # 날짜별로 그룹화
        df['date'] = pd.to_datetime(df.index).date

        vwap_list = []
        for date, group in df.groupby('date'):
            typical_price = (group['high'] + group['low'] + group['close']) / 3
            group_vwap = (typical_price * group['volume']).cumsum() / group['volume'].cumsum()
            vwap_list.append(group_vwap)

        return pd.concat(vwap_list)

    @staticmethod
    def calculate_bands(vwap: pd.Series, prices: pd.Series,
                       std_multiplier: float = 2.0) -> Tuple[pd.Series, pd.Series]:
        """
        VWAP 밴드 계산

        Args:
            vwap: VWAP 시리즈
            prices: 가격 시리즈
            std_multiplier: 표준편차 배수

        Returns:
            상단 밴드, 하단 밴드
        """
        deviation = prices - vwap
        std_dev = deviation.rolling(window=20).std()

        upper_band = vwap + (std_dev * std_multiplier)
        lower_band = vwap - (std_dev * std_multiplier)

        return upper_band, lower_band

    @staticmethod
    def analyze_position(current_price: float, vwap_value: float,
                        upper_band: Optional[float] = None,
                        lower_band: Optional[float] = None) -> Dict[str, Any]:
        """
        VWAP 대비 현재 가격 위치 분석

        Args:
            current_price: 현재 가격
            vwap_value: VWAP 값
            upper_band: 상단 밴드
            lower_band: 하단 밴드

        Returns:
            분석 결과 딕셔너리
        """
        position_pct = ((current_price - vwap_value) / vwap_value) * 100

        result = {
            'vwap': vwap_value,
            'current_price': current_price,
            'position_pct': position_pct,
            'above_vwap': current_price > vwap_value,
            'signal': None
        }

        # 시그널 판단
        if position_pct > 2:
            result['signal'] = 'overbought'
        elif position_pct < -2:
            result['signal'] = 'oversold'
        elif 0 < position_pct < 1:
            result['signal'] = 'bullish'
        elif -1 < position_pct < 0:
            result['signal'] = 'bearish'
        else:
            result['signal'] = 'neutral'

        # 밴드 위치 분석
        if upper_band and lower_band:
            if current_price > upper_band:
                result['band_position'] = 'above_upper'
            elif current_price < lower_band:
                result['band_position'] = 'below_lower'
            else:
                result['band_position'] = 'within_bands'

        return result

    @staticmethod
    def calculate_vwap_cross(prices: pd.Series, vwap: pd.Series) -> pd.Series:
        """
        VWAP 교차 신호 계산

        Args:
            prices: 가격 시리즈
            vwap: VWAP 시리즈

        Returns:
            교차 신호 (1: 상향돌파, -1: 하향돌파, 0: 없음)
        """
        above = prices > vwap
        cross_up = (above & ~above.shift(1)).astype(int)
        cross_down = (~above & above.shift(1)).astype(int) * -1

        return cross_up + cross_down

    @staticmethod
    def calculate_vwap_trend(vwap: pd.Series, window: int = 20) -> pd.Series:
        """
        VWAP 추세 계산

        Args:
            vwap: VWAP 시리즈
            window: 추세 계산 윈도우

        Returns:
            VWAP 추세 (기울기)
        """
        return vwap.diff(window) / vwap.shift(window) * 100

    @staticmethod
    def get_trade_signals(df: pd.DataFrame,
                         vwap_threshold: float = 0.5,
                         volume_threshold: float = 1.5) -> pd.DataFrame:
        """
        VWAP 기반 매매 신호 생성

        Args:
            df: OHLCV 데이터프레임
            vwap_threshold: VWAP 돌파 임계값 (%)
            volume_threshold: 거래량 임계값 배수

        Returns:
            매매 신호가 포함된 데이터프레임
        """
        # VWAP 계산
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        vwap = VWAP.calculate(typical_price, df['volume'], df['high'], df['low'])

        # VWAP 밴드 계산
        upper_band, lower_band = VWAP.calculate_bands(vwap, df['close'])

        # 거래량 평균
        avg_volume = df['volume'].rolling(window=20).mean()

        # 신호 생성
        signals = pd.DataFrame(index=df.index)
        signals['vwap'] = vwap
        signals['upper_band'] = upper_band
        signals['lower_band'] = lower_band

        # 매수 신호: VWAP 상향 돌파 + 거래량 증가
        buy_condition = (
            (df['close'] > vwap * (1 + vwap_threshold/100)) &
            (df['close'].shift(1) <= vwap.shift(1) * (1 + vwap_threshold/100)) &
            (df['volume'] > avg_volume * volume_threshold)
        )

        # 매도 신호: VWAP 하향 돌파 또는 상단 밴드 도달
        sell_condition = (
            ((df['close'] < vwap * (1 - vwap_threshold/100)) &
             (df['close'].shift(1) >= vwap.shift(1) * (1 - vwap_threshold/100))) |
            (df['close'] > upper_band)
        )

        signals['buy_signal'] = buy_condition.astype(int)
        signals['sell_signal'] = sell_condition.astype(int)

        return signals