#!/usr/bin/env python3
"""
추세 추종 전략 모듈
역추세 전략의 보완으로 상승 추세 종목 선정
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import logging

from core.utils.log_utils import get_logger

logger = get_logger(__name__)

@dataclass
class TrendSignal:
    """추세 신호"""
    is_uptrend: bool
    trend_strength: float  # 0-1
    trend_duration: int  # 일수
    ma_alignment: bool  # 이평선 정배열
    momentum_score: float  # 0-100
    reason: str


class TrendFollower:
    """추세 추종 필터"""

    def __init__(self):
        self.logger = logger
        self.min_trend_days = 5  # 최소 추세 지속 일수
        self.min_trend_strength = 0.7  # 최소 추세 강도
        self.min_momentum = 60.0  # 최소 모멘텀 점수

    def analyze_trend(self, df: pd.DataFrame) -> TrendSignal:
        """추세 분석

        Args:
            df: OHLCV 데이터프레임 (최소 60일)

        Returns:
            TrendSignal: 추세 신호
        """
        try:
            if len(df) < 60:
                return TrendSignal(False, 0.0, 0, False, 0.0, "데이터 부족")

            # 1. 이동평균선 계산
            df['ma5'] = df['close'].rolling(window=5).mean()
            df['ma20'] = df['close'].rolling(window=20).mean()
            df['ma60'] = df['close'].rolling(window=60).mean()

            # 2. 이동평균 정배열 확인 (close > ma5 > ma20 > ma60)
            latest = df.iloc[-1]
            ma_alignment = (
                latest['close'] > latest['ma5'] and
                latest['ma5'] > latest['ma20'] and
                latest['ma20'] > latest['ma60']
            )

            # 3. 추세 강도 계산 (ADX 대용)
            trend_strength = self._calculate_trend_strength(df)

            # 4. 추세 지속 기간
            trend_duration = self._count_trend_days(df)

            # 5. 모멘텀 점수 (ROC)
            momentum_score = self._calculate_momentum(df)

            # 6. 상승 추세 판단
            is_uptrend = (
                ma_alignment and
                trend_strength >= self.min_trend_strength and
                trend_duration >= self.min_trend_days and
                momentum_score >= self.min_momentum
            )

            reason = self._generate_reason(
                ma_alignment, trend_strength, trend_duration, momentum_score
            )

            return TrendSignal(
                is_uptrend=is_uptrend,
                trend_strength=trend_strength,
                trend_duration=trend_duration,
                ma_alignment=ma_alignment,
                momentum_score=momentum_score,
                reason=reason
            )

        except Exception as e:
            self.logger.error(f"추세 분석 실패: {e}")
            return TrendSignal(False, 0.0, 0, False, 0.0, f"분석 오류: {str(e)}")

    def _calculate_trend_strength(self, df: pd.DataFrame) -> float:
        """추세 강도 계산 (0-1)

        - MA 기울기의 일관성
        - 가격과 MA의 거리
        """
        try:
            # MA20 기울기
            ma20_slope = (df['ma20'].iloc[-1] - df['ma20'].iloc[-20]) / df['ma20'].iloc[-20]

            # 가격과 MA20의 거리 (%)
            price_distance = (df['close'].iloc[-1] - df['ma20'].iloc[-1]) / df['ma20'].iloc[-1]

            # 최근 20일 MA20 상승 일수 비율
            ma20_rising_days = (df['ma20'].diff().tail(20) > 0).sum() / 20

            # 종합 점수 (0-1)
            strength = (
                min(abs(ma20_slope) * 10, 1.0) * 0.4 +  # 기울기
                min(price_distance * 5, 1.0) * 0.3 +     # 거리
                ma20_rising_days * 0.3                    # 일관성
            )

            return max(0.0, min(1.0, strength))

        except Exception as e:
            self.logger.error(f"추세 강도 계산 실패: {e}")
            return 0.0

    def _count_trend_days(self, df: pd.DataFrame) -> int:
        """연속 상승 추세 일수"""
        try:
            count = 0
            for i in range(len(df) - 1, 0, -1):
                if df['close'].iloc[i] > df['ma20'].iloc[i]:
                    count += 1
                else:
                    break
            return count
        except Exception as e:
            self.logger.error(f"추세 일수 계산 실패: {e}")
            return 0

    def _calculate_momentum(self, df: pd.DataFrame) -> float:
        """모멘텀 점수 계산 (0-100)

        ROC (Rate of Change) 기반
        """
        try:
            # 5일, 10일, 20일 ROC
            roc5 = (df['close'].iloc[-1] / df['close'].iloc[-6] - 1) * 100
            roc10 = (df['close'].iloc[-1] / df['close'].iloc[-11] - 1) * 100
            roc20 = (df['close'].iloc[-1] / df['close'].iloc[-21] - 1) * 100

            # 가중 평균 (최근일 가중치 높음)
            momentum = (roc5 * 0.5 + roc10 * 0.3 + roc20 * 0.2)

            # 0-100 스케일링 (-20% ~ +20% 를 0-100으로)
            score = (momentum + 20) * 2.5
            return max(0.0, min(100.0, score))

        except Exception as e:
            self.logger.error(f"모멘텀 계산 실패: {e}")
            return 0.0

    def _generate_reason(
        self,
        ma_alignment: bool,
        trend_strength: float,
        trend_duration: int,
        momentum_score: float
    ) -> str:
        """선정 사유 생성"""
        reasons = []

        if ma_alignment:
            reasons.append("이동평균 정배열")

        if trend_strength >= 0.8:
            reasons.append(f"강한 추세 (강도: {trend_strength:.2f})")
        elif trend_strength >= 0.7:
            reasons.append(f"중강도 추세 (강도: {trend_strength:.2f})")

        if trend_duration >= 10:
            reasons.append(f"{trend_duration}일 연속 상승 추세")

        if momentum_score >= 80:
            reasons.append(f"강한 모멘텀 (점수: {momentum_score:.1f})")
        elif momentum_score >= 60:
            reasons.append(f"양호한 모멘텀 (점수: {momentum_score:.1f})")

        if not reasons:
            return "추세 추종 조건 미달"

        return " + ".join(reasons)

    def filter_stocks(self, stocks: List[Dict], market_data: Dict[str, pd.DataFrame]) -> List[Dict]:
        """추세 추종 조건으로 종목 필터링

        Args:
            stocks: 후보 종목 리스트
            market_data: 종목별 가격 데이터 {stock_code: DataFrame}

        Returns:
            필터링된 종목 리스트
        """
        filtered = []

        for stock in stocks:
            code = stock.get('stock_code')
            if code not in market_data:
                continue

            df = market_data[code]
            signal = self.analyze_trend(df)

            if signal.is_uptrend:
                # 추세 정보 추가
                stock['trend_strength'] = signal.trend_strength
                stock['trend_duration'] = signal.trend_duration
                stock['momentum_score'] = signal.momentum_score
                stock['trend_reason'] = signal.reason

                # 기존 선정 사유에 추세 정보 추가
                if 'selection_reason' in stock:
                    stock['selection_reason'] += f" | {signal.reason}"
                else:
                    stock['selection_reason'] = signal.reason

                filtered.append(stock)
                self.logger.debug(f"추세 추종 통과: {stock.get('stock_name')} - {signal.reason}")

        self.logger.info(f"추세 추종 필터: {len(stocks)}개 → {len(filtered)}개")
        return filtered


def get_trend_follower() -> TrendFollower:
    """TrendFollower 싱글톤 인스턴스 반환"""
    if not hasattr(get_trend_follower, '_instance'):
        get_trend_follower._instance = TrendFollower()
    return get_trend_follower._instance
