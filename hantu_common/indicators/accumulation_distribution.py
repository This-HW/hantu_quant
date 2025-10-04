"""
Accumulation/Distribution Line (A/D Line) 지표
매집과 분산을 측정하여 가격과 거래량의 관계 분석
"""

import numpy as np
import pandas as pd
from typing import Optional, Dict, Any, Tuple


class AccumulationDistribution:
    """Accumulation/Distribution Line 계산 및 분석"""

    @staticmethod
    def calculate_money_flow_multiplier(high: pd.Series, low: pd.Series,
                                       close: pd.Series) -> pd.Series:
        """
        Money Flow Multiplier 계산

        Args:
            high: 고가 시리즈
            low: 저가 시리즈
            close: 종가 시리즈

        Returns:
            Money Flow Multiplier 시리즈
        """
        # CLV (Close Location Value) 계산
        # ((종가 - 저가) - (고가 - 종가)) / (고가 - 저가)
        numerator = (close - low) - (high - close)
        denominator = high - low

        # 0으로 나누기 방지
        denominator = denominator.replace(0, 0.0001)

        mf_multiplier = numerator / denominator

        return mf_multiplier

    @staticmethod
    def calculate(high: pd.Series, low: pd.Series, close: pd.Series,
                  volume: pd.Series) -> pd.Series:
        """
        A/D Line 계산

        Args:
            high: 고가 시리즈
            low: 저가 시리즈
            close: 종가 시리즈
            volume: 거래량 시리즈

        Returns:
            A/D Line 시리즈
        """
        # Money Flow Multiplier 계산
        mf_multiplier = AccumulationDistribution.calculate_money_flow_multiplier(
            high, low, close
        )

        # Money Flow Volume 계산
        mf_volume = mf_multiplier * volume

        # A/D Line 계산 (누적)
        ad_line = mf_volume.cumsum()

        return ad_line

    @staticmethod
    def calculate_chaikin_oscillator(ad_line: pd.Series,
                                    fast_period: int = 3,
                                    slow_period: int = 10) -> pd.Series:
        """
        Chaikin Oscillator 계산 (A/D Line의 MACD)

        Args:
            ad_line: A/D Line 시리즈
            fast_period: 빠른 EMA 기간
            slow_period: 느린 EMA 기간

        Returns:
            Chaikin Oscillator 시리즈
        """
        ema_fast = ad_line.ewm(span=fast_period, adjust=False).mean()
        ema_slow = ad_line.ewm(span=slow_period, adjust=False).mean()

        chaikin_osc = ema_fast - ema_slow

        return chaikin_osc

    @staticmethod
    def detect_divergence(price: pd.Series, ad_line: pd.Series,
                         window: int = 20) -> pd.Series:
        """
        가격과 A/D Line 간의 다이버전스 감지

        Args:
            price: 가격 시리즈
            ad_line: A/D Line 시리즈
            window: 비교 윈도우

        Returns:
            다이버전스 신호 (1: Bullish, -1: Bearish, 0: None)
        """
        divergence = pd.Series(0, index=price.index)

        # 가격과 A/D Line의 추세 비교
        price_trend = price.diff(window)
        ad_trend = ad_line.diff(window)

        # Bullish Divergence: 가격 하락, A/D 상승
        bullish = (price_trend < 0) & (ad_trend > 0)

        # Bearish Divergence: 가격 상승, A/D 하락
        bearish = (price_trend > 0) & (ad_trend < 0)

        divergence[bullish] = 1
        divergence[bearish] = -1

        return divergence

    @staticmethod
    def calculate_ad_ratio(ad_line: pd.Series, window: int = 20) -> pd.Series:
        """
        A/D Ratio 계산 (현재 A/D vs 평균 A/D)

        Args:
            ad_line: A/D Line 시리즈
            window: 이동평균 윈도우

        Returns:
            A/D Ratio 시리즈
        """
        ad_ma = ad_line.rolling(window).mean()
        ad_ratio = (ad_line - ad_ma) / ad_ma * 100

        return ad_ratio

    @staticmethod
    def analyze_trend(ad_line: pd.Series, ad_line_prev: pd.Series,
                     price: pd.Series, price_prev: pd.Series) -> Dict[str, Any]:
        """
        A/D Line 추세 분석

        Args:
            ad_line: 현재 A/D Line 값
            ad_line_prev: 이전 A/D Line 값
            price: 현재 가격
            price_prev: 이전 가격

        Returns:
            분석 결과 딕셔너리
        """
        result = {
            'ad_line': ad_line,
            'ad_rising': ad_line > ad_line_prev,
            'price_rising': price > price_prev,
            'signal': None,
            'accumulation_phase': None
        }

        # 매집/분산 단계 판단
        if result['ad_rising'] and result['price_rising']:
            result['accumulation_phase'] = 'strong_accumulation'
            result['signal'] = 'buy'
        elif result['ad_rising'] and not result['price_rising']:
            result['accumulation_phase'] = 'hidden_accumulation'
            result['signal'] = 'accumulate'
        elif not result['ad_rising'] and result['price_rising']:
            result['accumulation_phase'] = 'distribution'
            result['signal'] = 'caution'
        else:
            result['accumulation_phase'] = 'strong_distribution'
            result['signal'] = 'sell'

        return result

    @staticmethod
    def calculate_volume_force(high: pd.Series, low: pd.Series,
                              close: pd.Series, volume: pd.Series) -> pd.Series:
        """
        Volume Force Index 계산

        Args:
            high: 고가 시리즈
            low: 저가 시리즈
            close: 종가 시리즈
            volume: 거래량 시리즈

        Returns:
            Volume Force Index
        """
        # Force Index = (Close - Previous Close) * Volume
        force = close.diff() * volume

        # Smoothed Force Index
        force_smoothed = force.ewm(span=13, adjust=False).mean()

        return force_smoothed

    @staticmethod
    def get_breakout_confirmation(ad_line: pd.Series, price: pd.Series,
                                 window: int = 20) -> pd.Series:
        """
        A/D Line을 통한 돌파 확인

        Args:
            ad_line: A/D Line 시리즈
            price: 가격 시리즈
            window: 확인 윈도우

        Returns:
            돌파 확인 신호
        """
        # 가격과 A/D Line 모두 신고점
        price_high = price == price.rolling(window).max()
        ad_high = ad_line == ad_line.rolling(window).max()

        # 가격과 A/D Line 모두 신저점
        price_low = price == price.rolling(window).min()
        ad_low = ad_line == ad_line.rolling(window).min()

        confirmation = pd.Series('none', index=price.index)
        confirmation[price_high & ad_high] = 'bullish_breakout'
        confirmation[price_low & ad_low] = 'bearish_breakdown'
        confirmation[price_high & ~ad_high] = 'false_breakout'
        confirmation[price_low & ~ad_low] = 'false_breakdown'

        return confirmation

    @staticmethod
    def get_trade_signals(df: pd.DataFrame, divergence_window: int = 20,
                         chaikin_threshold: float = 0) -> pd.DataFrame:
        """
        A/D Line 기반 매매 신호 생성

        Args:
            df: OHLCV 데이터프레임
            divergence_window: 다이버전스 확인 윈도우
            chaikin_threshold: Chaikin Oscillator 임계값

        Returns:
            매매 신호가 포함된 데이터프레임
        """
        # A/D Line 계산
        ad_line = AccumulationDistribution.calculate(
            df['high'], df['low'], df['close'], df['volume']
        )

        # Chaikin Oscillator
        chaikin_osc = AccumulationDistribution.calculate_chaikin_oscillator(ad_line)

        # 다이버전스
        divergence = AccumulationDistribution.detect_divergence(
            df['close'], ad_line, divergence_window
        )

        # A/D Ratio
        ad_ratio = AccumulationDistribution.calculate_ad_ratio(ad_line)

        # Volume Force
        volume_force = AccumulationDistribution.calculate_volume_force(
            df['high'], df['low'], df['close'], df['volume']
        )

        # 돌파 확인
        breakout = AccumulationDistribution.get_breakout_confirmation(
            ad_line, df['close']
        )

        signals = pd.DataFrame(index=df.index)
        signals['ad_line'] = ad_line
        signals['chaikin_osc'] = chaikin_osc
        signals['divergence'] = divergence
        signals['ad_ratio'] = ad_ratio
        signals['volume_force'] = volume_force
        signals['breakout'] = breakout

        # 매수 신호
        buy_condition = (
            # Chaikin Oscillator 상승 전환
            ((chaikin_osc > chaikin_threshold) & (chaikin_osc.shift(1) <= chaikin_threshold)) |
            # Bullish 다이버전스
            (divergence == 1) |
            # A/D Line 급등
            (ad_ratio > ad_ratio.rolling(20).mean() + ad_ratio.rolling(20).std() * 2) |
            # 강한 매집
            ((ad_line > ad_line.shift(1)) & (df['close'] > df['close'].shift(1)) &
             (volume_force > 0)) |
            # 돌파 확인
            (breakout == 'bullish_breakout')
        )

        # 매도 신호
        sell_condition = (
            # Chaikin Oscillator 하락 전환
            ((chaikin_osc < -chaikin_threshold) & (chaikin_osc.shift(1) >= -chaikin_threshold)) |
            # Bearish 다이버전스
            (divergence == -1) |
            # A/D Line 급락
            (ad_ratio < ad_ratio.rolling(20).mean() - ad_ratio.rolling(20).std() * 2) |
            # 강한 분산
            ((ad_line < ad_line.shift(1)) & (df['close'] < df['close'].shift(1)) &
             (volume_force < 0)) |
            # 붕괴 확인
            (breakout == 'bearish_breakdown')
        )

        signals['buy_signal'] = buy_condition.astype(int)
        signals['sell_signal'] = sell_condition.astype(int)

        # 매집/분산 단계
        accumulation_phase = []
        for i in range(1, len(df)):
            if pd.isna(ad_line.iloc[i]) or pd.isna(ad_line.iloc[i-1]):
                accumulation_phase.append('unknown')
            else:
                phase = AccumulationDistribution.analyze_trend(
                    ad_line.iloc[i], ad_line.iloc[i-1],
                    df['close'].iloc[i], df['close'].iloc[i-1]
                )['accumulation_phase']
                accumulation_phase.append(phase)
        accumulation_phase = ['unknown'] + accumulation_phase  # 첫 번째 값

        signals['accumulation_phase'] = accumulation_phase

        return signals