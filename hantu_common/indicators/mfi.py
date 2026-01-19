"""
MFI (Money Flow Index) 지표
거래량을 포함한 RSI로, 자금 흐름의 강도를 측정
"""

import pandas as pd
from typing import Dict, Any


class MFI:
    """Money Flow Index 계산 및 분석"""

    @staticmethod
    def calculate(high: pd.Series, low: pd.Series, close: pd.Series,
                  volume: pd.Series, period: int = 14) -> pd.Series:
        """
        MFI 계산

        Args:
            high: 고가 시리즈
            low: 저가 시리즈
            close: 종가 시리즈
            volume: 거래량 시리즈
            period: 계산 기간

        Returns:
            MFI 시리즈
        """
        # Typical Price 계산
        typical_price = (high + low + close) / 3

        # Raw Money Flow 계산
        raw_money_flow = typical_price * volume

        # Positive/Negative Money Flow 분리
        money_flow_positive = pd.Series(0.0, index=close.index)
        money_flow_negative = pd.Series(0.0, index=close.index)

        # 가격 상승/하락 판단
        for i in range(1, len(typical_price)):
            if typical_price.iloc[i] > typical_price.iloc[i-1]:
                money_flow_positive.iloc[i] = raw_money_flow.iloc[i]
            elif typical_price.iloc[i] < typical_price.iloc[i-1]:
                money_flow_negative.iloc[i] = raw_money_flow.iloc[i]

        # Money Flow Ratio 계산
        positive_flow = money_flow_positive.rolling(window=period).sum()
        negative_flow = money_flow_negative.rolling(window=period).sum()

        # 0으로 나누기 방지
        negative_flow = negative_flow.replace(0, 0.001)

        money_flow_ratio = positive_flow / negative_flow

        # MFI 계산
        mfi = 100 - (100 / (1 + money_flow_ratio))

        return mfi

    @staticmethod
    def analyze_level(mfi_value: float) -> str:
        """
        MFI 레벨 분석

        Args:
            mfi_value: MFI 값

        Returns:
            과매수/과매도 상태
        """
        if mfi_value > 80:
            return 'extreme_overbought'
        elif mfi_value > 70:
            return 'overbought'
        elif mfi_value < 20:
            return 'extreme_oversold'
        elif mfi_value < 30:
            return 'oversold'
        else:
            return 'neutral'

    @staticmethod
    def calculate_divergence(prices: pd.Series, mfi: pd.Series,
                           window: int = 20) -> pd.Series:
        """
        가격과 MFI 간의 다이버전스 계산

        Args:
            prices: 가격 시리즈
            mfi: MFI 시리즈
            window: 비교 윈도우

        Returns:
            다이버전스 신호 (1: 강세, -1: 약세, 0: 없음)
        """
        divergence = pd.Series(0, index=prices.index)

        for i in range(window, len(prices)):
            # 현재 구간
            price_slice = prices.iloc[i-window:i]
            mfi_slice = mfi.iloc[i-window:i]

            # 최고/최저점 찾기
            price_high_idx = price_slice.idxmax()
            price_low_idx = price_slice.idxmin()
            mfi_high_idx = mfi_slice.idxmax()
            mfi_low_idx = mfi_slice.idxmin()

            # Bullish Divergence: 가격은 하락하나 MFI는 상승
            if prices.iloc[i] < prices[price_low_idx] and mfi.iloc[i] > mfi[mfi_low_idx]:
                divergence.iloc[i] = 1

            # Bearish Divergence: 가격은 상승하나 MFI는 하락
            elif prices.iloc[i] > prices[price_high_idx] and mfi.iloc[i] < mfi[mfi_high_idx]:
                divergence.iloc[i] = -1

        return divergence

    @staticmethod
    def analyze(mfi: float, mfi_prev: float,
               price: float, price_prev: float) -> Dict[str, Any]:
        """
        MFI 종합 분석

        Args:
            mfi: 현재 MFI 값
            mfi_prev: 이전 MFI 값
            price: 현재 가격
            price_prev: 이전 가격

        Returns:
            분석 결과 딕셔너리
        """
        result = {
            'mfi': mfi,
            'level': MFI.analyze_level(mfi),
            'mfi_rising': mfi > mfi_prev,
            'price_rising': price > price_prev,
            'signal': None
        }

        # 다이버전스 체크
        if price > price_prev and mfi < mfi_prev:
            result['divergence'] = 'bearish'
        elif price < price_prev and mfi > mfi_prev:
            result['divergence'] = 'bullish'
        else:
            result['divergence'] = None

        # 매매 신호 판단
        if mfi < 20 and mfi > mfi_prev:
            result['signal'] = 'strong_buy'
        elif mfi < 30 and result['divergence'] == 'bullish':
            result['signal'] = 'buy'
        elif mfi > 80 and mfi < mfi_prev:
            result['signal'] = 'strong_sell'
        elif mfi > 70 and result['divergence'] == 'bearish':
            result['signal'] = 'sell'
        else:
            result['signal'] = 'hold'

        return result

    @staticmethod
    def calculate_money_flow_volume(high: pd.Series, low: pd.Series,
                                   close: pd.Series, volume: pd.Series) -> Dict[str, pd.Series]:
        """
        자금 흐름량 계산

        Args:
            high: 고가 시리즈
            low: 저가 시리즈
            close: 종가 시리즈
            volume: 거래량 시리즈

        Returns:
            자금 흐름 관련 데이터
        """
        typical_price = (high + low + close) / 3
        money_flow_volume = typical_price * volume

        # 누적 자금 흐름
        cumulative_mfv = money_flow_volume.cumsum()

        # 자금 흐름 변화율
        mfv_change = money_flow_volume.pct_change()

        return {
            'money_flow_volume': money_flow_volume,
            'cumulative_mfv': cumulative_mfv,
            'mfv_change': mfv_change,
            'avg_mfv': money_flow_volume.rolling(window=20).mean()
        }

    @staticmethod
    def get_trade_signals(df: pd.DataFrame, overbought: float = 70,
                         oversold: float = 30, divergence_window: int = 20) -> pd.DataFrame:
        """
        MFI 기반 매매 신호 생성

        Args:
            df: OHLCV 데이터프레임
            overbought: 과매수 기준
            oversold: 과매도 기준
            divergence_window: 다이버전스 확인 윈도우

        Returns:
            매매 신호가 포함된 데이터프레임
        """
        # MFI 계산
        mfi = MFI.calculate(df['high'], df['low'], df['close'], df['volume'])

        # 다이버전스 계산
        divergence = MFI.calculate_divergence(df['close'], mfi, divergence_window)

        # 자금 흐름 계산
        mf_data = MFI.calculate_money_flow_volume(
            df['high'], df['low'], df['close'], df['volume']
        )

        signals = pd.DataFrame(index=df.index)
        signals['mfi'] = mfi
        signals['divergence'] = divergence
        signals['money_flow_volume'] = mf_data['money_flow_volume']

        # MFI 레벨
        signals['mfi_level'] = mfi.apply(MFI.analyze_level)

        # 매수 신호
        buy_condition = (
            ((mfi < oversold) & (mfi > mfi.shift(1))) |  # 과매도 반등
            ((divergence == 1) & (mfi < 50)) |  # Bullish 다이버전스
            ((mfi.shift(1) < oversold) & (mfi > oversold))  # 과매도 탈출
        )

        # 매도 신호
        sell_condition = (
            ((mfi > overbought) & (mfi < mfi.shift(1))) |  # 과매수 하락
            ((divergence == -1) & (mfi > 50)) |  # Bearish 다이버전스
            ((mfi.shift(1) > overbought) & (mfi < overbought))  # 과매수 탈출
        )

        signals['buy_signal'] = buy_condition.astype(int)
        signals['sell_signal'] = sell_condition.astype(int)

        return signals