"""
Ichimoku Cloud (일목균형표) 지표
다중 시간대 분석을 통한 종합적인 추세 판단 시스템
"""

import numpy as np
import pandas as pd
from typing import Optional, Dict, Any


class Ichimoku:
    """Ichimoku Cloud 계산 및 분석"""

    @staticmethod
    def calculate(high: pd.Series, low: pd.Series, close: pd.Series,
                  tenkan_period: int = 9, kijun_period: int = 26,
                  senkou_span_b_period: int = 52, chikou_period: int = 26) -> Dict[str, pd.Series]:
        """
        Ichimoku Cloud 전체 요소 계산

        Args:
            high: 고가 시리즈
            low: 저가 시리즈
            close: 종가 시리즈
            tenkan_period: 전환선 기간 (기본 9)
            kijun_period: 기준선 기간 (기본 26)
            senkou_span_b_period: 선행스팬B 기간 (기본 52)
            chikou_period: 후행스팬 기간 (기본 26)

        Returns:
            Ichimoku 구성 요소들
        """
        # 전환선 (Tenkan-sen): (9일 최고가 + 9일 최저가) / 2
        high_9 = high.rolling(window=tenkan_period).max()
        low_9 = low.rolling(window=tenkan_period).min()
        tenkan_sen = (high_9 + low_9) / 2

        # 기준선 (Kijun-sen): (26일 최고가 + 26일 최저가) / 2
        high_26 = high.rolling(window=kijun_period).max()
        low_26 = low.rolling(window=kijun_period).min()
        kijun_sen = (high_26 + low_26) / 2

        # 선행스팬A (Senkou Span A): (전환선 + 기준선) / 2, 26일 선행
        senkou_span_a = ((tenkan_sen + kijun_sen) / 2).shift(kijun_period)

        # 선행스팬B (Senkou Span B): (52일 최고가 + 52일 최저가) / 2, 26일 선행
        high_52 = high.rolling(window=senkou_span_b_period).max()
        low_52 = low.rolling(window=senkou_span_b_period).min()
        senkou_span_b = ((high_52 + low_52) / 2).shift(kijun_period)

        # 후행스팬 (Chikou Span): 현재 종가를 26일 뒤로
        chikou_span = close.shift(-chikou_period)

        return {
            'tenkan_sen': tenkan_sen,
            'kijun_sen': kijun_sen,
            'senkou_span_a': senkou_span_a,
            'senkou_span_b': senkou_span_b,
            'chikou_span': chikou_span
        }

    @staticmethod
    def analyze_cloud_position(price: float, span_a: float, span_b: float) -> str:
        """
        구름대 대비 가격 위치 분석

        Args:
            price: 현재 가격
            span_a: 선행스팬A 값
            span_b: 선행스팬B 값

        Returns:
            위치 설명
        """
        cloud_top = max(span_a, span_b)
        cloud_bottom = min(span_a, span_b)

        if price > cloud_top:
            return 'above_cloud'  # 강세
        elif price < cloud_bottom:
            return 'below_cloud'  # 약세
        else:
            return 'in_cloud'  # 중립/보합

    @staticmethod
    def analyze_cloud_trend(span_a: float, span_b: float) -> str:
        """
        구름대 추세 분석

        Args:
            span_a: 선행스팬A 값
            span_b: 선행스팬B 값

        Returns:
            구름대 추세
        """
        if span_a > span_b:
            return 'bullish_cloud'  # 상승 구름
        else:
            return 'bearish_cloud'  # 하락 구름

    @staticmethod
    def calculate_tk_cross(tenkan: pd.Series, kijun: pd.Series) -> pd.Series:
        """
        전환선/기준선 교차 신호

        Args:
            tenkan: 전환선 시리즈
            kijun: 기준선 시리즈

        Returns:
            교차 신호 (1: 골든크로스, -1: 데드크로스, 0: 없음)
        """
        tk_diff = tenkan - kijun
        cross_up = ((tk_diff > 0) & (tk_diff.shift(1) <= 0)).astype(int)
        cross_down = ((tk_diff < 0) & (tk_diff.shift(1) >= 0)).astype(int) * -1

        return cross_up + cross_down

    @staticmethod
    def analyze(ichimoku_data: Dict[str, float], price: float) -> Dict[str, Any]:
        """
        Ichimoku 종합 분석

        Args:
            ichimoku_data: Ichimoku 구성 요소 값들
            price: 현재 가격

        Returns:
            분석 결과 딕셔너리
        """
        result = {
            'price': price,
            'cloud_position': Ichimoku.analyze_cloud_position(
                price,
                ichimoku_data['senkou_span_a'],
                ichimoku_data['senkou_span_b']
            ),
            'cloud_trend': Ichimoku.analyze_cloud_trend(
                ichimoku_data['senkou_span_a'],
                ichimoku_data['senkou_span_b']
            ),
            'tk_position': 'bullish' if ichimoku_data['tenkan_sen'] > ichimoku_data['kijun_sen'] else 'bearish',
            'signal': None,
            'strength': 0
        }

        # 신호 강도 계산
        strength = 0

        # 1. 가격이 구름 위에 있으면 +2
        if result['cloud_position'] == 'above_cloud':
            strength += 2
        elif result['cloud_position'] == 'below_cloud':
            strength -= 2

        # 2. 상승 구름이면 +1
        if result['cloud_trend'] == 'bullish_cloud':
            strength += 1
        else:
            strength -= 1

        # 3. 전환선 > 기준선이면 +1
        if result['tk_position'] == 'bullish':
            strength += 1
        else:
            strength -= 1

        # 4. 가격 > 전환선이면 +1
        if price > ichimoku_data['tenkan_sen']:
            strength += 1
        else:
            strength -= 1

        # 5. 가격 > 기준선이면 +1
        if price > ichimoku_data['kijun_sen']:
            strength += 1
        else:
            strength -= 1

        result['strength'] = strength

        # 최종 신호 판단
        if strength >= 4:
            result['signal'] = 'strong_buy'
        elif strength >= 2:
            result['signal'] = 'buy'
        elif strength <= -4:
            result['signal'] = 'strong_sell'
        elif strength <= -2:
            result['signal'] = 'sell'
        else:
            result['signal'] = 'neutral'

        return result

    @staticmethod
    def calculate_future_cloud(ichimoku_data: Dict[str, pd.Series],
                             periods: int = 26) -> Dict[str, pd.Series]:
        """
        미래 구름대 계산 (26일 후의 구름)

        Args:
            ichimoku_data: Ichimoku 데이터
            periods: 미래 기간

        Returns:
            미래 구름대 데이터
        """
        # 현재 시점의 선행스팬들이 미래 구름
        future_span_a = ichimoku_data['senkou_span_a'].shift(-periods)
        future_span_b = ichimoku_data['senkou_span_b'].shift(-periods)

        # 구름 두께
        cloud_thickness = np.abs(future_span_a - future_span_b)

        return {
            'future_span_a': future_span_a,
            'future_span_b': future_span_b,
            'cloud_thickness': cloud_thickness,
            'thick_cloud': cloud_thickness > cloud_thickness.rolling(20).mean()
        }

    @staticmethod
    def get_trade_signals(df: pd.DataFrame) -> pd.DataFrame:
        """
        Ichimoku 기반 매매 신호 생성

        Args:
            df: OHLCV 데이터프레임

        Returns:
            매매 신호가 포함된 데이터프레임
        """
        # Ichimoku 계산
        ichimoku = Ichimoku.calculate(df['high'], df['low'], df['close'])

        signals = pd.DataFrame(index=df.index)

        # 기본 지표 저장
        for key, value in ichimoku.items():
            signals[key] = value

        # TK 교차 신호
        signals['tk_cross'] = Ichimoku.calculate_tk_cross(
            ichimoku['tenkan_sen'], ichimoku['kijun_sen']
        )

        # 구름대 위치
        cloud_position = []
        for i in range(len(df)):
            if pd.isna(ichimoku['senkou_span_a'].iloc[i]) or pd.isna(ichimoku['senkou_span_b'].iloc[i]):
                cloud_position.append('unknown')
            else:
                cloud_position.append(Ichimoku.analyze_cloud_position(
                    df['close'].iloc[i],
                    ichimoku['senkou_span_a'].iloc[i],
                    ichimoku['senkou_span_b'].iloc[i]
                ))
        signals['cloud_position'] = cloud_position

        # 구름대 추세
        signals['cloud_trend'] = np.where(
            ichimoku['senkou_span_a'] > ichimoku['senkou_span_b'],
            'bullish', 'bearish'
        )

        # 미래 구름
        future = Ichimoku.calculate_future_cloud(ichimoku)
        signals['cloud_thickness'] = future['cloud_thickness']

        # 매수 신호
        buy_condition = (
            # 강력한 매수: TK 골든크로스 + 구름 위
            ((signals['tk_cross'] == 1) & (signals['cloud_position'] == 'above_cloud')) |
            # 중간 매수: 가격이 구름 상단 돌파
            ((signals['cloud_position'] == 'above_cloud') &
             (signals['cloud_position'].shift(1) != 'above_cloud')) |
            # 추세 전환: 구름이 상승 전환
            ((signals['cloud_trend'] == 'bullish') &
             (signals['cloud_trend'].shift(1) == 'bearish'))
        )

        # 매도 신호
        sell_condition = (
            # 강력한 매도: TK 데드크로스 + 구름 아래
            ((signals['tk_cross'] == -1) & (signals['cloud_position'] == 'below_cloud')) |
            # 중간 매도: 가격이 구름 하단 이탈
            ((signals['cloud_position'] == 'below_cloud') &
             (signals['cloud_position'].shift(1) != 'below_cloud')) |
            # 추세 전환: 구름이 하락 전환
            ((signals['cloud_trend'] == 'bearish') &
             (signals['cloud_trend'].shift(1) == 'bullish'))
        )

        signals['buy_signal'] = buy_condition.astype(int)
        signals['sell_signal'] = sell_condition.astype(int)

        # 신호 강도
        signals['signal_strength'] = (
            (signals['cloud_position'] == 'above_cloud').astype(int) * 2 +
            (signals['cloud_trend'] == 'bullish').astype(int) +
            (df['close'] > ichimoku['tenkan_sen']).astype(int) +
            (df['close'] > ichimoku['kijun_sen']).astype(int) +
            (ichimoku['tenkan_sen'] > ichimoku['kijun_sen']).astype(int) - 3
        )

        return signals