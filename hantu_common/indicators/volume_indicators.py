# -*- coding: utf-8 -*-
"""
거래량 지표 모듈 (P1-4)

기능:
- OBV (On Balance Volume) 계산
- OBV 다이버전스 감지
- 가격-거래량 추세 전환 조기 감지

OBV 다이버전스:
- Bullish: 가격 하락 + OBV 상승 = 매수 신호
- Bearish: 가격 상승 + OBV 하락 = 매도 신호
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime


class OBVSignal(Enum):
    """OBV 신호"""
    BULLISH_DIVERGENCE = "bullish_divergence"    # 가격 하락 + OBV 상승
    BEARISH_DIVERGENCE = "bearish_divergence"    # 가격 상승 + OBV 하락
    NO_DIVERGENCE = "no_divergence"              # 다이버전스 없음
    BULLISH_CONFIRM = "bullish_confirm"          # 가격 상승 + OBV 상승
    BEARISH_CONFIRM = "bearish_confirm"          # 가격 하락 + OBV 하락


@dataclass
class OBVAnalysisResult:
    """OBV 분석 결과"""
    stock_code: str
    obv_current: float
    obv_change: float
    price_change: float
    signal: OBVSignal
    confidence: float  # 0.0 ~ 1.0
    lookback_period: int
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict:
        """딕셔너리 변환"""
        return {
            "stock_code": self.stock_code,
            "obv_current": self.obv_current,
            "obv_change": self.obv_change,
            "price_change": self.price_change,
            "signal": self.signal.value,
            "confidence": self.confidence,
            "lookback_period": self.lookback_period,
            "timestamp": self.timestamp,
        }


class VolumeIndicators:
    """거래량 기반 지표 계산기

    정적 메서드로 OBV 관련 지표를 계산합니다.
    """

    @staticmethod
    def obv(df: pd.DataFrame) -> pd.Series:
        """OBV (On Balance Volume) 계산

        가격이 상승하면 거래량을 더하고, 하락하면 빼는 누적 지표.
        거래량과 가격의 관계를 파악하는 데 사용됩니다.

        Args:
            df: OHLCV DataFrame (close, volume 필수)

        Returns:
            pd.Series: OBV 값
        """
        if df is None or len(df) < 2:
            return pd.Series(dtype=float)

        # close와 volume 컬럼 확인
        close_col = 'close' if 'close' in df.columns else 'Close'
        volume_col = 'volume' if 'volume' in df.columns else 'Volume'

        if close_col not in df.columns or volume_col not in df.columns:
            return pd.Series(dtype=float)

        close = df[close_col]
        volume = df[volume_col]

        obv = [volume.iloc[0]]

        for i in range(1, len(df)):
            if close.iloc[i] > close.iloc[i - 1]:
                obv.append(obv[-1] + volume.iloc[i])
            elif close.iloc[i] < close.iloc[i - 1]:
                obv.append(obv[-1] - volume.iloc[i])
            else:
                obv.append(obv[-1])

        return pd.Series(obv, index=df.index)

    @staticmethod
    def obv_divergence(df: pd.DataFrame, lookback: int = 20) -> str:
        """OBV 다이버전스 감지

        가격과 OBV의 추세가 반대인 경우 다이버전스로 판단합니다.

        Args:
            df: OHLCV DataFrame
            lookback: 비교 기간 (일)

        Returns:
            str: 다이버전스 유형
                - 'bullish_divergence': 가격 하락 + OBV 상승 → 매수 신호
                - 'bearish_divergence': 가격 상승 + OBV 하락 → 매도 신호
                - 'no_divergence': 다이버전스 없음
        """
        if df is None or len(df) < lookback + 1:
            return 'no_divergence'

        # OBV 계산
        obv = VolumeIndicators.obv(df)
        if len(obv) < lookback + 1:
            return 'no_divergence'

        # close 컬럼 확인
        close_col = 'close' if 'close' in df.columns else 'Close'

        # 가격 및 OBV 추세 계산
        price_trend = df[close_col].iloc[-1] - df[close_col].iloc[-lookback]
        obv_trend = obv.iloc[-1] - obv.iloc[-lookback]

        # 다이버전스 판단
        if price_trend > 0 and obv_trend < 0:
            return 'bearish_divergence'
        if price_trend < 0 and obv_trend > 0:
            return 'bullish_divergence'

        return 'no_divergence'

    @staticmethod
    def obv_signal(df: pd.DataFrame, lookback: int = 20) -> OBVSignal:
        """OBV 신호 생성 (확장 버전)

        다이버전스뿐만 아니라 추세 확인 신호도 생성합니다.

        Args:
            df: OHLCV DataFrame
            lookback: 비교 기간 (일)

        Returns:
            OBVSignal: OBV 신호
        """
        if df is None or len(df) < lookback + 1:
            return OBVSignal.NO_DIVERGENCE

        obv = VolumeIndicators.obv(df)
        if len(obv) < lookback + 1:
            return OBVSignal.NO_DIVERGENCE

        close_col = 'close' if 'close' in df.columns else 'Close'

        price_trend = df[close_col].iloc[-1] - df[close_col].iloc[-lookback]
        obv_trend = obv.iloc[-1] - obv.iloc[-lookback]

        # 다이버전스
        if price_trend > 0 and obv_trend < 0:
            return OBVSignal.BEARISH_DIVERGENCE
        if price_trend < 0 and obv_trend > 0:
            return OBVSignal.BULLISH_DIVERGENCE

        # 추세 확인
        if price_trend > 0 and obv_trend > 0:
            return OBVSignal.BULLISH_CONFIRM
        if price_trend < 0 and obv_trend < 0:
            return OBVSignal.BEARISH_CONFIRM

        return OBVSignal.NO_DIVERGENCE

    @staticmethod
    def obv_ma(df: pd.DataFrame, period: int = 20) -> pd.Series:
        """OBV 이동평균

        Args:
            df: OHLCV DataFrame
            period: 이동평균 기간

        Returns:
            pd.Series: OBV 이동평균
        """
        obv = VolumeIndicators.obv(df)
        return obv.rolling(window=period).mean()

    @staticmethod
    def obv_slope(df: pd.DataFrame, period: int = 5) -> float:
        """OBV 기울기 (추세 강도)

        Args:
            df: OHLCV DataFrame
            period: 기울기 계산 기간

        Returns:
            float: OBV 기울기 (양수: 상승, 음수: 하락)
        """
        obv = VolumeIndicators.obv(df)
        if len(obv) < period:
            return 0.0

        # 선형 회귀 기울기 계산
        x = np.arange(period)
        y = obv.tail(period).values

        if len(y) < period:
            return 0.0

        # numpy polyfit으로 기울기 계산
        try:
            slope, _ = np.polyfit(x, y, 1)
            return slope
        except Exception:
            return 0.0


class OBVAnalyzer:
    """OBV 분석기

    OBV를 활용한 다이버전스 감지 및 매매 신호 생성.
    """

    # 다이버전스 신뢰도 가중치
    PRICE_WEIGHT = 0.4
    OBV_WEIGHT = 0.6

    def __init__(
        self,
        default_lookback: int = 20,
        slope_period: int = 5,
        ma_period: int = 20,
    ):
        """초기화

        Args:
            default_lookback: 기본 다이버전스 비교 기간
            slope_period: 기울기 계산 기간
            ma_period: OBV 이동평균 기간
        """
        self.default_lookback = default_lookback
        self.slope_period = slope_period
        self.ma_period = ma_period

        # 캐시
        self._cache: Dict[str, OBVAnalysisResult] = {}

    def analyze(
        self,
        stock_code: str,
        df: pd.DataFrame,
        lookback: Optional[int] = None
    ) -> Optional[OBVAnalysisResult]:
        """OBV 분석

        Args:
            stock_code: 종목 코드
            df: OHLCV DataFrame
            lookback: 다이버전스 비교 기간

        Returns:
            OBVAnalysisResult 또는 None
        """
        if df is None or len(df) < 2:
            return None

        lookback = lookback or self.default_lookback

        # OBV 계산
        obv = VolumeIndicators.obv(df)
        if len(obv) < lookback + 1:
            return None

        # 컬럼 확인
        close_col = 'close' if 'close' in df.columns else 'Close'

        # 가격 및 OBV 변화 계산
        price_change = df[close_col].iloc[-1] - df[close_col].iloc[-lookback]
        obv_change = obv.iloc[-1] - obv.iloc[-lookback]
        obv_current = obv.iloc[-1]

        # 신호 생성
        signal = VolumeIndicators.obv_signal(df, lookback)

        # 신뢰도 계산
        confidence = self._calculate_confidence(df, signal, lookback)

        result = OBVAnalysisResult(
            stock_code=stock_code,
            obv_current=obv_current,
            obv_change=obv_change,
            price_change=price_change,
            signal=signal,
            confidence=confidence,
            lookback_period=lookback,
        )

        # 캐시 저장
        self._cache[stock_code] = result

        return result

    def _calculate_confidence(
        self,
        df: pd.DataFrame,
        signal: OBVSignal,
        lookback: int
    ) -> float:
        """신뢰도 계산

        Args:
            df: OHLCV DataFrame
            signal: OBV 신호
            lookback: 비교 기간

        Returns:
            float: 신뢰도 (0.0 ~ 1.0)
        """
        if signal in [OBVSignal.NO_DIVERGENCE]:
            return 0.3

        # OBV 기울기
        slope = VolumeIndicators.obv_slope(df, self.slope_period)

        # close 컬럼 확인
        close_col = 'close' if 'close' in df.columns else 'Close'

        # 가격 변화율
        price_change_pct = (
            (df[close_col].iloc[-1] - df[close_col].iloc[-lookback]) /
            df[close_col].iloc[-lookback]
        ) if df[close_col].iloc[-lookback] != 0 else 0

        # OBV 이동평균 대비 위치
        obv = VolumeIndicators.obv(df)
        obv_ma = VolumeIndicators.obv_ma(df, self.ma_period)
        obv_position = 0.5
        if len(obv_ma) > 0 and not pd.isna(obv_ma.iloc[-1]):
            if obv_ma.iloc[-1] != 0:
                obv_position = obv.iloc[-1] / obv_ma.iloc[-1]
                obv_position = min(max(obv_position - 0.8, 0) / 0.4, 1)

        # 다이버전스 유형에 따른 기본 신뢰도
        if signal in [OBVSignal.BULLISH_DIVERGENCE, OBVSignal.BEARISH_DIVERGENCE]:
            base_confidence = 0.6
        else:  # Confirm signals
            base_confidence = 0.5

        # 추가 신뢰도 계산
        slope_factor = min(abs(slope) / 1000000, 0.2)  # 최대 0.2
        price_factor = min(abs(price_change_pct) * 5, 0.2)  # 최대 0.2

        confidence = base_confidence + slope_factor + price_factor
        return min(confidence, 1.0)

    def get_divergence_stocks(self) -> Dict[str, list]:
        """다이버전스 종목 분류

        Returns:
            Dict: {'bullish': [...], 'bearish': [...]}
        """
        bullish = []
        bearish = []

        for code, result in self._cache.items():
            if result.signal == OBVSignal.BULLISH_DIVERGENCE:
                bullish.append(code)
            elif result.signal == OBVSignal.BEARISH_DIVERGENCE:
                bearish.append(code)

        return {'bullish': bullish, 'bearish': bearish}

    def get_cached_result(self, stock_code: str) -> Optional[OBVAnalysisResult]:
        """캐시된 결과 조회"""
        return self._cache.get(stock_code)

    def clear_cache(self):
        """캐시 초기화"""
        self._cache.clear()


# 편의 함수
def calculate_obv(df: pd.DataFrame) -> pd.Series:
    """OBV 계산 편의 함수"""
    return VolumeIndicators.obv(df)


def detect_obv_divergence(df: pd.DataFrame, lookback: int = 20) -> str:
    """OBV 다이버전스 감지 편의 함수"""
    return VolumeIndicators.obv_divergence(df, lookback)


def analyze_obv(
    stock_code: str,
    df: pd.DataFrame,
    lookback: int = 20
) -> Optional[OBVAnalysisResult]:
    """OBV 분석 편의 함수"""
    analyzer = OBVAnalyzer(default_lookback=lookback)
    return analyzer.analyze(stock_code, df)
