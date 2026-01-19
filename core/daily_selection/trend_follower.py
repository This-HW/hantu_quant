#!/usr/bin/env python3
"""
추세 추종 전략 모듈
역추세 전략의 보완으로 상승 추세 종목 선정
"""

import pandas as pd
from typing import Dict, List, Optional
from dataclasses import dataclass

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
    """추세 추종 필터 (개선: Adaptive Minimum Data)"""

    # 데이터 길이별 분석 모드
    ANALYSIS_MODE_FULL = "full"      # 60일+ 전체 분석
    ANALYSIS_MODE_MEDIUM = "medium"  # 30-59일 중간 분석
    ANALYSIS_MODE_SHORT = "short"    # 20-29일 간이 분석
    ANALYSIS_MODE_MINIMAL = "minimal"  # 10-19일 최소 분석

    def __init__(self):
        self.logger = logger
        # 기본 임계값 (완화됨)
        self.min_trend_days = 3          # 최소 추세 지속 일수 (5 → 3)
        self.min_trend_strength = 0.5    # 최소 추세 강도 (0.7 → 0.5)
        self.min_momentum = 45.0         # 최소 모멘텀 점수 (60 → 45)

        # 데이터 길이별 임계값 조정
        self.thresholds_by_mode = {
            self.ANALYSIS_MODE_FULL: {
                "min_trend_days": 5,
                "min_trend_strength": 0.6,
                "min_momentum": 55.0,
            },
            self.ANALYSIS_MODE_MEDIUM: {
                "min_trend_days": 3,
                "min_trend_strength": 0.5,
                "min_momentum": 50.0,
            },
            self.ANALYSIS_MODE_SHORT: {
                "min_trend_days": 2,
                "min_trend_strength": 0.45,
                "min_momentum": 45.0,
            },
            self.ANALYSIS_MODE_MINIMAL: {
                "min_trend_days": 1,
                "min_trend_strength": 0.4,
                "min_momentum": 40.0,
            },
        }

    def _get_analysis_mode(self, data_len: int) -> Optional[str]:
        """데이터 길이에 따른 분석 모드 결정"""
        if data_len >= 60:
            return self.ANALYSIS_MODE_FULL
        elif data_len >= 30:
            return self.ANALYSIS_MODE_MEDIUM
        elif data_len >= 20:
            return self.ANALYSIS_MODE_SHORT
        elif data_len >= 10:
            return self.ANALYSIS_MODE_MINIMAL
        else:
            return None  # 분석 불가

    def analyze_trend(self, df: pd.DataFrame) -> TrendSignal:
        """추세 분석 (개선: Adaptive Minimum Data)

        데이터 길이에 따라 다른 분석 방식 적용:
        - 60일+: 전체 분석 (ma5, ma20, ma60)
        - 30-59일: 중간 분석 (ma5, ma20만)
        - 20-29일: 간이 분석 (ma5, ma10만)
        - 10-19일: 최소 분석 (ma5만, 모멘텀 중심)

        Args:
            df: OHLCV 데이터프레임 (최소 10일)

        Returns:
            TrendSignal: 추세 신호
        """
        try:
            data_len = len(df)
            mode = self._get_analysis_mode(data_len)

            if mode is None:
                return TrendSignal(False, 0.0, 0, False, 0.0, f"데이터 부족 ({data_len}일 < 10일)")

            # 분석 모드에 따른 임계값 설정
            thresholds = self.thresholds_by_mode[mode]

            # 분석 모드별 처리
            if mode == self.ANALYSIS_MODE_FULL:
                return self._analyze_full(df, thresholds)
            elif mode == self.ANALYSIS_MODE_MEDIUM:
                return self._analyze_medium(df, thresholds)
            elif mode == self.ANALYSIS_MODE_SHORT:
                return self._analyze_short(df, thresholds)
            else:  # MINIMAL
                return self._analyze_minimal(df, thresholds)

        except Exception as e:
            self.logger.error(f"추세 분석 실패: {e}", exc_info=True)
            return TrendSignal(False, 0.0, 0, False, 0.0, f"분석 오류: {str(e)}")

    def _analyze_full(self, df: pd.DataFrame, thresholds: dict) -> TrendSignal:
        """전체 분석 (60일 이상): ma5, ma20, ma60 사용"""
        # 이동평균선 계산
        df = df.copy()
        df['ma5'] = df['close'].rolling(window=5).mean()
        df['ma20'] = df['close'].rolling(window=20).mean()
        df['ma60'] = df['close'].rolling(window=60).mean()

        latest = df.iloc[-1]

        # 정배열 확인 (close > ma5 > ma20 > ma60)
        ma_alignment = (
            latest['close'] > latest['ma5'] and
            latest['ma5'] > latest['ma20'] and
            latest['ma20'] > latest['ma60']
        )

        trend_strength = self._calculate_trend_strength(df, window=20)
        trend_duration = self._count_trend_days(df, ma_col='ma20')
        momentum_score = self._calculate_momentum(df)

        is_uptrend = (
            ma_alignment and
            trend_strength >= thresholds["min_trend_strength"] and
            trend_duration >= thresholds["min_trend_days"] and
            momentum_score >= thresholds["min_momentum"]
        )

        reason = self._generate_reason(
            ma_alignment, trend_strength, trend_duration, momentum_score, mode="전체분석(60일+)"
        )

        return TrendSignal(is_uptrend, trend_strength, trend_duration, ma_alignment, momentum_score, reason)

    def _analyze_medium(self, df: pd.DataFrame, thresholds: dict) -> TrendSignal:
        """중간 분석 (30-59일): ma5, ma20만 사용"""
        df = df.copy()
        df['ma5'] = df['close'].rolling(window=5).mean()
        df['ma20'] = df['close'].rolling(window=20).mean()

        latest = df.iloc[-1]

        # 정배열 확인 (close > ma5 > ma20)
        ma_alignment = (
            latest['close'] > latest['ma5'] and
            latest['ma5'] > latest['ma20']
        )

        trend_strength = self._calculate_trend_strength(df, window=20)
        trend_duration = self._count_trend_days(df, ma_col='ma20')
        momentum_score = self._calculate_momentum_medium(df)

        is_uptrend = (
            ma_alignment and
            trend_strength >= thresholds["min_trend_strength"] and
            trend_duration >= thresholds["min_trend_days"] and
            momentum_score >= thresholds["min_momentum"]
        )

        reason = self._generate_reason(
            ma_alignment, trend_strength, trend_duration, momentum_score, mode="중간분석(30-59일)"
        )

        return TrendSignal(is_uptrend, trend_strength, trend_duration, ma_alignment, momentum_score, reason)

    def _analyze_short(self, df: pd.DataFrame, thresholds: dict) -> TrendSignal:
        """간이 분석 (20-29일): ma5, ma10 사용"""
        df = df.copy()
        df['ma5'] = df['close'].rolling(window=5).mean()
        df['ma10'] = df['close'].rolling(window=10).mean()

        latest = df.iloc[-1]

        # 정배열 확인 (close > ma5 > ma10)
        ma_alignment = (
            latest['close'] > latest['ma5'] and
            latest['ma5'] > latest['ma10']
        )

        trend_strength = self._calculate_trend_strength_short(df)
        trend_duration = self._count_trend_days(df, ma_col='ma10')
        momentum_score = self._calculate_momentum_short(df)

        is_uptrend = (
            ma_alignment and
            trend_strength >= thresholds["min_trend_strength"] and
            trend_duration >= thresholds["min_trend_days"] and
            momentum_score >= thresholds["min_momentum"]
        )

        reason = self._generate_reason(
            ma_alignment, trend_strength, trend_duration, momentum_score, mode="간이분석(20-29일)"
        )

        return TrendSignal(is_uptrend, trend_strength, trend_duration, ma_alignment, momentum_score, reason)

    def _analyze_minimal(self, df: pd.DataFrame, thresholds: dict) -> TrendSignal:
        """최소 분석 (10-19일): ma5만, 모멘텀 중심"""
        df = df.copy()
        df['ma5'] = df['close'].rolling(window=5).mean()

        latest = df.iloc[-1]

        # 단순 상승 확인 (close > ma5)
        ma_alignment = latest['close'] > latest['ma5']

        # 간단한 추세 강도 (최근 5일 상승률)
        trend_strength = self._calculate_simple_strength(df)
        trend_duration = self._count_trend_days(df, ma_col='ma5')
        momentum_score = self._calculate_momentum_minimal(df)

        # 최소 분석에서는 조건 더 완화
        is_uptrend = (
            ma_alignment and
            (trend_strength >= thresholds["min_trend_strength"] or momentum_score >= 55) and
            momentum_score >= thresholds["min_momentum"]
        )

        reason = self._generate_reason(
            ma_alignment, trend_strength, trend_duration, momentum_score, mode="최소분석(10-19일)"
        )

        return TrendSignal(is_uptrend, trend_strength, trend_duration, ma_alignment, momentum_score, reason)

    def _calculate_trend_strength(self, df: pd.DataFrame, window: int = 20) -> float:
        """추세 강도 계산 (0-1)

        - MA 기울기의 일관성
        - 가격과 MA의 거리
        """
        try:
            ma_col = f'ma{window}'
            if ma_col not in df.columns:
                df[ma_col] = df['close'].rolling(window=window).mean()

            # MA 기울기
            ma_slope = (df[ma_col].iloc[-1] - df[ma_col].iloc[-window]) / df[ma_col].iloc[-window]

            # 가격과 MA의 거리 (%)
            price_distance = (df['close'].iloc[-1] - df[ma_col].iloc[-1]) / df[ma_col].iloc[-1]

            # 최근 n일 MA 상승 일수 비율
            ma_rising_days = (df[ma_col].diff().tail(window) > 0).sum() / window

            # 종합 점수 (0-1)
            strength = (
                min(abs(ma_slope) * 10, 1.0) * 0.4 +  # 기울기
                min(max(price_distance * 5, 0), 1.0) * 0.3 +  # 거리 (음수면 0)
                ma_rising_days * 0.3                    # 일관성
            )

            return max(0.0, min(1.0, strength))

        except Exception as e:
            self.logger.error(f"추세 강도 계산 실패: {e}", exc_info=True)
            return 0.0

    def _calculate_trend_strength_short(self, df: pd.DataFrame) -> float:
        """간이 분석용 추세 강도 계산 (20-29일 데이터)"""
        try:
            # MA10 기울기
            ma10_slope = (df['ma10'].iloc[-1] - df['ma10'].iloc[-10]) / df['ma10'].iloc[-10]

            # 가격과 MA10의 거리
            price_distance = (df['close'].iloc[-1] - df['ma10'].iloc[-1]) / df['ma10'].iloc[-1]

            # MA10 상승 일수
            ma10_rising_days = (df['ma10'].diff().tail(10) > 0).sum() / 10

            strength = (
                min(abs(ma10_slope) * 12, 1.0) * 0.35 +
                min(max(price_distance * 6, 0), 1.0) * 0.35 +
                ma10_rising_days * 0.30
            )

            return max(0.0, min(1.0, strength))

        except Exception as e:
            self.logger.error(f"간이 추세 강도 계산 실패: {e}", exc_info=True)
            return 0.0

    def _calculate_simple_strength(self, df: pd.DataFrame) -> float:
        """최소 분석용 단순 추세 강도 (10-19일 데이터)"""
        try:
            # 최근 5일 수익률
            returns_5d = (df['close'].iloc[-1] / df['close'].iloc[-6] - 1) if len(df) >= 6 else 0

            # 최근 5일 상승일 비율
            price_up_days = (df['close'].diff().tail(5) > 0).sum() / 5

            # MA5 위에 있는지
            above_ma5 = 1.0 if df['close'].iloc[-1] > df['ma5'].iloc[-1] else 0.5

            strength = (
                min(returns_5d * 8, 1.0) * 0.4 +
                price_up_days * 0.3 +
                above_ma5 * 0.3
            )

            return max(0.0, min(1.0, strength))

        except Exception as e:
            self.logger.error(f"단순 추세 강도 계산 실패: {e}", exc_info=True)
            return 0.0

    def _count_trend_days(self, df: pd.DataFrame, ma_col: str = 'ma20') -> int:
        """연속 상승 추세 일수"""
        try:
            if ma_col not in df.columns:
                return 0

            count = 0
            for i in range(len(df) - 1, 0, -1):
                if df['close'].iloc[i] > df[ma_col].iloc[i]:
                    count += 1
                else:
                    break
            return count
        except Exception as e:
            self.logger.error(f"추세 일수 계산 실패: {e}", exc_info=True)
            return 0

    def _calculate_momentum(self, df: pd.DataFrame) -> float:
        """모멘텀 점수 계산 (0-100) - 60일+ 데이터용

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
            self.logger.error(f"모멘텀 계산 실패: {e}", exc_info=True)
            return 50.0  # 기본값 반환

    def _calculate_momentum_medium(self, df: pd.DataFrame) -> float:
        """모멘텀 점수 계산 (0-100) - 30-59일 데이터용"""
        try:
            # 5일, 10일 ROC만 사용
            roc5 = (df['close'].iloc[-1] / df['close'].iloc[-6] - 1) * 100
            roc10 = (df['close'].iloc[-1] / df['close'].iloc[-11] - 1) * 100 if len(df) >= 11 else roc5

            momentum = (roc5 * 0.6 + roc10 * 0.4)
            score = (momentum + 15) * 3.0  # 범위 조정
            return max(0.0, min(100.0, score))

        except Exception as e:
            self.logger.error(f"중간 모멘텀 계산 실패: {e}", exc_info=True)
            return 50.0

    def _calculate_momentum_short(self, df: pd.DataFrame) -> float:
        """모멘텀 점수 계산 (0-100) - 20-29일 데이터용"""
        try:
            # 3일, 5일 ROC
            roc3 = (df['close'].iloc[-1] / df['close'].iloc[-4] - 1) * 100 if len(df) >= 4 else 0
            roc5 = (df['close'].iloc[-1] / df['close'].iloc[-6] - 1) * 100 if len(df) >= 6 else roc3

            momentum = (roc3 * 0.5 + roc5 * 0.5)
            score = (momentum + 10) * 4.0  # 범위 조정
            return max(0.0, min(100.0, score))

        except Exception as e:
            self.logger.error(f"간이 모멘텀 계산 실패: {e}", exc_info=True)
            return 50.0

    def _calculate_momentum_minimal(self, df: pd.DataFrame) -> float:
        """모멘텀 점수 계산 (0-100) - 10-19일 데이터용"""
        try:
            # 3일 ROC만 사용
            roc3 = (df['close'].iloc[-1] / df['close'].iloc[-4] - 1) * 100 if len(df) >= 4 else 0

            # 가격 상승률
            total_return = (df['close'].iloc[-1] / df['close'].iloc[0] - 1) * 100

            momentum = (roc3 * 0.6 + total_return * 0.4)
            score = (momentum + 8) * 5.0  # 범위 조정
            return max(0.0, min(100.0, score))

        except Exception as e:
            self.logger.error(f"최소 모멘텀 계산 실패: {e}", exc_info=True)
            return 50.0

    def _generate_reason(
        self,
        ma_alignment: bool,
        trend_strength: float,
        trend_duration: int,
        momentum_score: float,
        mode: str = ""
    ) -> str:
        """선정 사유 생성"""
        reasons = []

        # 분석 모드 표시
        if mode:
            reasons.append(f"[{mode}]")

        if ma_alignment:
            reasons.append("이동평균 정배열")

        if trend_strength >= 0.7:
            reasons.append(f"강한 추세 ({trend_strength:.2f})")
        elif trend_strength >= 0.5:
            reasons.append(f"중간 추세 ({trend_strength:.2f})")
        elif trend_strength >= 0.4:
            reasons.append(f"약한 추세 ({trend_strength:.2f})")

        if trend_duration >= 10:
            reasons.append(f"{trend_duration}일 연속 상승")
        elif trend_duration >= 5:
            reasons.append(f"{trend_duration}일 상승")

        if momentum_score >= 70:
            reasons.append(f"강한 모멘텀 ({momentum_score:.0f})")
        elif momentum_score >= 50:
            reasons.append(f"양호 모멘텀 ({momentum_score:.0f})")
        elif momentum_score >= 40:
            reasons.append(f"보통 모멘텀 ({momentum_score:.0f})")

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
