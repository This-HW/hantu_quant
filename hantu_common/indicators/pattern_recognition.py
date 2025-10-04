"""
차트 패턴 인식 시스템
주요 차트 패턴과 캔들스틱 패턴을 자동으로 감지
"""

import numpy as np
import pandas as pd
from typing import Optional, Dict, Any, List, Tuple
from scipy.signal import argrelextrema


class PatternRecognition:
    """차트 패턴 인식 클래스"""

    @staticmethod
    def find_peaks_and_troughs(prices: pd.Series, order: int = 5) -> Tuple[np.ndarray, np.ndarray]:
        """
        고점과 저점 찾기

        Args:
            prices: 가격 시리즈
            order: 비교할 이웃 수

        Returns:
            고점 인덱스, 저점 인덱스
        """
        peaks = argrelextrema(prices.values, np.greater, order=order)[0]
        troughs = argrelextrema(prices.values, np.less, order=order)[0]

        return peaks, troughs

    @staticmethod
    def detect_support_resistance(prices: pd.Series, window: int = 20,
                                 min_touches: int = 2) -> Dict[str, List[float]]:
        """
        지지선과 저항선 감지

        Args:
            prices: 가격 시리즈
            window: 검색 윈도우
            min_touches: 최소 터치 횟수

        Returns:
            지지선과 저항선 레벨
        """
        peaks, troughs = PatternRecognition.find_peaks_and_troughs(prices, order=window//4)

        # 저항선 후보
        resistance_levels = []
        if len(peaks) > 0:
            peak_prices = prices.iloc[peaks].values
            for level in np.unique(np.round(peak_prices, -1)):  # 10원 단위로 반올림
                touches = np.sum(np.abs(peak_prices - level) < level * 0.01)  # 1% 오차
                if touches >= min_touches:
                    resistance_levels.append(level)

        # 지지선 후보
        support_levels = []
        if len(troughs) > 0:
            trough_prices = prices.iloc[troughs].values
            for level in np.unique(np.round(trough_prices, -1)):
                touches = np.sum(np.abs(trough_prices - level) < level * 0.01)
                if touches >= min_touches:
                    support_levels.append(level)

        return {
            'support': sorted(support_levels),
            'resistance': sorted(resistance_levels)
        }

    @staticmethod
    def detect_triangle(prices: pd.Series, min_points: int = 4) -> Optional[Dict[str, Any]]:
        """
        삼각형 패턴 감지 (상승/하강/대칭)

        Args:
            prices: 가격 시리즈
            min_points: 최소 포인트 수

        Returns:
            삼각형 패턴 정보
        """
        peaks, troughs = PatternRecognition.find_peaks_and_troughs(prices)

        if len(peaks) < min_points//2 or len(troughs) < min_points//2:
            return None

        # 최근 포인트들만 사용
        recent_peaks = peaks[-min_points//2:]
        recent_troughs = troughs[-min_points//2:]

        # 추세선 계산
        peak_prices = prices.iloc[recent_peaks].values
        trough_prices = prices.iloc[recent_troughs].values

        # 선형 회귀로 추세 계산
        peak_slope = np.polyfit(range(len(peak_prices)), peak_prices, 1)[0]
        trough_slope = np.polyfit(range(len(trough_prices)), trough_prices, 1)[0]

        # 패턴 분류
        if peak_slope < -0.01 and trough_slope > 0.01:
            pattern_type = 'symmetric_triangle'
        elif abs(peak_slope) < 0.01 and trough_slope > 0.01:
            pattern_type = 'ascending_triangle'
        elif peak_slope < -0.01 and abs(trough_slope) < 0.01:
            pattern_type = 'descending_triangle'
        else:
            return None

        return {
            'type': pattern_type,
            'peak_slope': peak_slope,
            'trough_slope': trough_slope,
            'breakout_level': peak_prices[-1] if pattern_type != 'descending_triangle' else trough_prices[-1]
        }

    @staticmethod
    def detect_head_and_shoulders(prices: pd.Series) -> Optional[Dict[str, Any]]:
        """
        헤드앤숄더 패턴 감지

        Args:
            prices: 가격 시리즈

        Returns:
            헤드앤숄더 패턴 정보
        """
        peaks, troughs = PatternRecognition.find_peaks_and_troughs(prices, order=10)

        if len(peaks) < 3 or len(troughs) < 2:
            return None

        # 최근 3개 고점과 2개 저점
        last_peaks = peaks[-3:]
        last_troughs = troughs[-2:]

        # 헤드앤숄더 조건
        # 1. 중간 고점(헤드)이 가장 높아야 함
        # 2. 양쪽 고점(숄더)이 비슷해야 함
        # 3. 저점들(넥라인)이 비슷해야 함

        peak_prices = prices.iloc[last_peaks].values
        trough_prices = prices.iloc[last_troughs].values

        head = peak_prices[1]
        left_shoulder = peak_prices[0]
        right_shoulder = peak_prices[2]
        neckline = np.mean(trough_prices)

        # 조건 확인
        is_head_highest = head > left_shoulder and head > right_shoulder
        shoulders_similar = abs(left_shoulder - right_shoulder) / left_shoulder < 0.03
        neckline_flat = np.std(trough_prices) / np.mean(trough_prices) < 0.02

        if is_head_highest and shoulders_similar and neckline_flat:
            return {
                'type': 'head_and_shoulders',
                'head': head,
                'left_shoulder': left_shoulder,
                'right_shoulder': right_shoulder,
                'neckline': neckline,
                'target': neckline - (head - neckline)  # 목표가
            }

        return None

    @staticmethod
    def detect_double_top_bottom(prices: pd.Series) -> Optional[Dict[str, Any]]:
        """
        이중 천정/바닥 패턴 감지

        Args:
            prices: 가격 시리즈

        Returns:
            패턴 정보
        """
        peaks, troughs = PatternRecognition.find_peaks_and_troughs(prices, order=10)

        # Double Top 확인
        if len(peaks) >= 2:
            last_peaks = peaks[-2:]
            peak_prices = prices.iloc[last_peaks].values

            if abs(peak_prices[0] - peak_prices[1]) / peak_prices[0] < 0.03:  # 3% 이내
                # 중간 저점 찾기
                middle_trough = troughs[(troughs > last_peaks[0]) & (troughs < last_peaks[1])]
                if len(middle_trough) > 0:
                    support = prices.iloc[middle_trough[0]]
                    return {
                        'type': 'double_top',
                        'first_top': peak_prices[0],
                        'second_top': peak_prices[1],
                        'support': support,
                        'target': support - (peak_prices[0] - support)
                    }

        # Double Bottom 확인
        if len(troughs) >= 2:
            last_troughs = troughs[-2:]
            trough_prices = prices.iloc[last_troughs].values

            if abs(trough_prices[0] - trough_prices[1]) / trough_prices[0] < 0.03:
                # 중간 고점 찾기
                middle_peak = peaks[(peaks > last_troughs[0]) & (peaks < last_troughs[1])]
                if len(middle_peak) > 0:
                    resistance = prices.iloc[middle_peak[0]]
                    return {
                        'type': 'double_bottom',
                        'first_bottom': trough_prices[0],
                        'second_bottom': trough_prices[1],
                        'resistance': resistance,
                        'target': resistance + (resistance - trough_prices[0])
                    }

        return None

    @staticmethod
    def detect_candlestick_patterns(df: pd.DataFrame) -> pd.DataFrame:
        """
        캔들스틱 패턴 감지

        Args:
            df: OHLC 데이터프레임

        Returns:
            패턴 신호가 포함된 데이터프레임
        """
        patterns = pd.DataFrame(index=df.index)

        # 기본 계산
        body = df['close'] - df['open']
        body_abs = np.abs(body)
        upper_shadow = df['high'] - np.maximum(df['open'], df['close'])
        lower_shadow = np.minimum(df['open'], df['close']) - df['low']
        total_range = df['high'] - df['low']

        # Doji (십자형)
        patterns['doji'] = (body_abs / total_range < 0.1).astype(int)

        # Hammer (망치형)
        patterns['hammer'] = (
            (lower_shadow > body_abs * 2) &
            (upper_shadow < body_abs * 0.3) &
            (df['close'] > df['open'])
        ).astype(int)

        # Shooting Star (유성형)
        patterns['shooting_star'] = (
            (upper_shadow > body_abs * 2) &
            (lower_shadow < body_abs * 0.3) &
            (df['close'] < df['open'])
        ).astype(int)

        # Engulfing (장악형)
        patterns['bullish_engulfing'] = (
            (df['close'] > df['open']) &
            (df['open'] < df['close'].shift(1)) &
            (df['close'] > df['open'].shift(1)) &
            (df['open'].shift(1) > df['close'].shift(1))
        ).astype(int)

        patterns['bearish_engulfing'] = (
            (df['close'] < df['open']) &
            (df['open'] > df['close'].shift(1)) &
            (df['close'] < df['open'].shift(1)) &
            (df['open'].shift(1) < df['close'].shift(1))
        ).astype(int)

        # Morning/Evening Star (샛별/저녁별)
        small_body = body_abs < body_abs.rolling(20).mean() * 0.3

        patterns['morning_star'] = (
            (df['close'].shift(2) < df['open'].shift(2)) &  # 첫날: 음봉
            small_body.shift(1) &  # 둘째날: 작은 몸통
            (df['close'] > df['open']) &  # 셋째날: 양봉
            (df['close'] > df['open'].shift(2))  # 셋째날 종가 > 첫날 시가
        ).astype(int)

        patterns['evening_star'] = (
            (df['close'].shift(2) > df['open'].shift(2)) &  # 첫날: 양봉
            small_body.shift(1) &  # 둘째날: 작은 몸통
            (df['close'] < df['open']) &  # 셋째날: 음봉
            (df['close'] < df['open'].shift(2))  # 셋째날 종가 < 첫날 시가
        ).astype(int)

        return patterns

    @staticmethod
    def detect_breakout(prices: pd.Series, volume: pd.Series,
                       window: int = 20, volume_multiplier: float = 1.5) -> pd.Series:
        """
        돌파 패턴 감지

        Args:
            prices: 가격 시리즈
            volume: 거래량 시리즈
            window: 비교 윈도우
            volume_multiplier: 거래량 배수

        Returns:
            돌파 신호 (1: 상향돌파, -1: 하향돌파, 0: 없음)
        """
        # 최근 고점/저점
        rolling_high = prices.rolling(window).max()
        rolling_low = prices.rolling(window).min()

        # 평균 거래량
        avg_volume = volume.rolling(window).mean()

        # 상향 돌파
        upward_breakout = (
            (prices > rolling_high.shift(1)) &
            (volume > avg_volume * volume_multiplier)
        )

        # 하향 돌파
        downward_breakout = (
            (prices < rolling_low.shift(1)) &
            (volume > avg_volume * volume_multiplier)
        )

        signal = pd.Series(0, index=prices.index)
        signal[upward_breakout] = 1
        signal[downward_breakout] = -1

        return signal

    @staticmethod
    def get_pattern_signals(df: pd.DataFrame) -> pd.DataFrame:
        """
        모든 패턴 신호 종합

        Args:
            df: OHLCV 데이터프레임

        Returns:
            패턴 신호가 포함된 데이터프레임
        """
        signals = pd.DataFrame(index=df.index)

        # 캔들스틱 패턴
        candlestick = PatternRecognition.detect_candlestick_patterns(df)
        signals = pd.concat([signals, candlestick], axis=1)

        # 돌파 패턴
        signals['breakout'] = PatternRecognition.detect_breakout(
            df['close'], df['volume']
        )

        # 차트 패턴 (최근 데이터만)
        if len(df) > 50:
            recent_prices = df['close'].tail(50)

            # 삼각형 패턴
            triangle = PatternRecognition.detect_triangle(recent_prices)
            signals['triangle_pattern'] = 0
            if triangle:
                signals.iloc[-1, signals.columns.get_loc('triangle_pattern')] = 1

            # 헤드앤숄더
            hs = PatternRecognition.detect_head_and_shoulders(recent_prices)
            signals['head_shoulders'] = 0
            if hs:
                signals.iloc[-1, signals.columns.get_loc('head_shoulders')] = -1

            # 이중 천정/바닥
            double = PatternRecognition.detect_double_top_bottom(recent_prices)
            signals['double_pattern'] = 0
            if double:
                if double['type'] == 'double_top':
                    signals.iloc[-1, signals.columns.get_loc('double_pattern')] = -1
                else:
                    signals.iloc[-1, signals.columns.get_loc('double_pattern')] = 1

        # 종합 신호
        bull_patterns = (
            signals['bullish_engulfing'] + signals['morning_star'] +
            signals['hammer'] + (signals['breakout'] == 1).astype(int)
        )

        bear_patterns = (
            signals['bearish_engulfing'] + signals['evening_star'] +
            signals['shooting_star'] + (signals['breakout'] == -1).astype(int)
        )

        signals['pattern_score'] = bull_patterns - bear_patterns

        return signals