"""
수급 분석 점수 계산 모듈

거래량, 매집/분산 패턴을 분석하여 수급 신호를 생성합니다.
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional
from dataclasses import dataclass

from .signal import Signal, SignalType, SignalSource


@dataclass
class SDScores:
    """수급 분석 점수 결과"""
    # 거래량 분석 (50%)
    volume_surge: float = 0.0      # 거래량 급증
    volume_trend: float = 0.0      # 거래량 추세

    # 매집/분산 지표 (30%)
    accumulation: float = 0.0      # 매집 신호
    distribution: float = 0.0      # 분산 신호

    # 가격-거래량 관계 (20%)
    price_volume_confirm: float = 0.0  # 가격-거래량 확인

    @property
    def weighted_total(self) -> float:
        """가중 종합 점수"""
        volume_score = (self.volume_surge + self.volume_trend) / 2 * 0.50
        ad_score = (self.accumulation - self.distribution) * 0.30
        pv_score = self.price_volume_confirm * 0.20

        return volume_score + ad_score + pv_score

    def to_dict(self) -> Dict[str, float]:
        return {
            'volume_surge': self.volume_surge,
            'volume_trend': self.volume_trend,
            'accumulation': self.accumulation,
            'distribution': self.distribution,
            'price_volume_confirm': self.price_volume_confirm,
            'weighted_total': self.weighted_total,
        }


class SupplyDemandScorer:
    """
    수급 분석 점수 계산기

    거래량 패턴과 매집/분산 지표를 분석하여
    수급 기반 신호를 생성합니다.
    """

    def __init__(self,
                 volume_ma_period: int = 20,
                 surge_threshold: float = 2.0,
                 ad_period: int = 14):
        """
        Args:
            volume_ma_period: 거래량 이동평균 기간
            surge_threshold: 거래량 급증 기준 (평균 대비 배수)
            ad_period: 매집/분산 분석 기간
        """
        self.volume_ma_period = volume_ma_period
        self.surge_threshold = surge_threshold
        self.ad_period = ad_period

    def calculate_scores(self, data: pd.DataFrame) -> SDScores:
        """
        전체 수급 분석 점수 계산

        Args:
            data: OHLCV DataFrame

        Returns:
            SDScores: 각 지표별 점수
        """
        if len(data) < self.volume_ma_period + 10:
            return SDScores()

        scores = SDScores()

        scores.volume_surge = self._calculate_volume_surge_score(data)
        scores.volume_trend = self._calculate_volume_trend_score(data)
        scores.accumulation = self._calculate_accumulation_score(data)
        scores.distribution = self._calculate_distribution_score(data)
        scores.price_volume_confirm = self._calculate_pv_confirmation_score(data)

        return scores

    def generate_signal(self, data: pd.DataFrame, stock_code: str) -> Signal:
        """
        수급 분석 기반 신호 생성

        점수 해석:
        - +50 이상: 강한 매수 (수급 양호)
        - +25 ~ +50: 약한 매수
        - -25 ~ +25: 중립
        - -50 ~ -25: 약한 매도
        - -50 이하: 강한 매도 (수급 악화)
        """
        scores = self.calculate_scores(data)
        total_score = scores.weighted_total

        current_price = data['close'].iloc[-1]

        if total_score >= 50:
            return Signal(
                signal_type=SignalType.BUY,
                source=SignalSource.SD,
                stock_code=stock_code,
                strength=2.0,
                confidence=min(1.0, total_score / 100),
                price=current_price,
                reason=f"SD Strong Buy (score: {total_score:.1f})",
                metadata={'scores': scores.to_dict()}
            )
        elif total_score >= 25:
            return Signal(
                signal_type=SignalType.BUY,
                source=SignalSource.SD,
                stock_code=stock_code,
                strength=1.0,
                confidence=total_score / 100,
                price=current_price,
                reason=f"SD Buy (score: {total_score:.1f})",
                metadata={'scores': scores.to_dict()}
            )
        elif total_score <= -50:
            return Signal(
                signal_type=SignalType.SELL,
                source=SignalSource.SD,
                stock_code=stock_code,
                strength=2.0,
                confidence=min(1.0, abs(total_score) / 100),
                price=current_price,
                reason=f"SD Strong Sell (score: {total_score:.1f})",
                metadata={'scores': scores.to_dict()}
            )
        elif total_score <= -25:
            return Signal(
                signal_type=SignalType.SELL,
                source=SignalSource.SD,
                stock_code=stock_code,
                strength=1.0,
                confidence=abs(total_score) / 100,
                price=current_price,
                reason=f"SD Sell (score: {total_score:.1f})",
                metadata={'scores': scores.to_dict()}
            )
        else:
            return Signal(
                signal_type=SignalType.HOLD,
                source=SignalSource.SD,
                stock_code=stock_code,
                strength=0.0,
                confidence=0.5,
                price=current_price,
                reason=f"SD Neutral (score: {total_score:.1f})",
                metadata={'scores': scores.to_dict()}
            )

    def _calculate_volume_surge_score(self, data: pd.DataFrame) -> float:
        """
        거래량 급증 점수 (-100 ~ +100)

        평균 대비 거래량과 가격 방향을 결합
        """
        close = data['close']
        volume = data['volume']

        volume_ma = volume.rolling(self.volume_ma_period).mean()
        volume_ratio = volume / (volume_ma + 1e-10)

        current_ratio = volume_ratio.iloc[-1]
        price_change = close.pct_change().iloc[-1]

        score = 0.0

        # 거래량 급증 + 가격 상승 = 강한 매수 신호
        if current_ratio >= self.surge_threshold:
            if price_change > 0.02:
                score = 80
            elif price_change > 0.01:
                score = 60
            elif price_change > 0:
                score = 40
            elif price_change < -0.02:
                score = -80  # 급락 + 대량 거래 = 매도 압력
            elif price_change < -0.01:
                score = -60
            elif price_change < 0:
                score = -40
        elif current_ratio >= 1.5:
            if price_change > 0:
                score = 30
            else:
                score = -30
        elif current_ratio < 0.5:
            score = 0  # 거래량 부족 = 중립

        return np.clip(score, -100, 100)

    def _calculate_volume_trend_score(self, data: pd.DataFrame) -> float:
        """
        거래량 추세 점수 (-100 ~ +100)

        5일 거래량 추세 분석
        """
        volume = data['volume']
        close = data['close']

        # 5일 거래량 추세
        volume_5d = volume.tail(5)
        volume_trend = np.polyfit(range(5), volume_5d.values, 1)[0]

        # 가격 추세
        close_5d = close.tail(5)
        price_trend = np.polyfit(range(5), close_5d.values, 1)[0]

        score = 0.0

        # 거래량 증가 추세
        avg_volume = volume.tail(20).mean()
        normalized_trend = volume_trend / (avg_volume + 1e-10) * 100

        if normalized_trend > 5:
            if price_trend > 0:
                score = 50  # 거래량 증가 + 가격 상승
            else:
                score = -30  # 거래량 증가 + 가격 하락 (부정적)
        elif normalized_trend < -5:
            if price_trend > 0:
                score = -20  # 거래량 감소 + 가격 상승 (의심스러운 상승)
            else:
                score = 20  # 거래량 감소 + 가격 하락 (매도 압력 감소)

        return np.clip(score, -100, 100)

    def _calculate_accumulation_score(self, data: pd.DataFrame) -> float:
        """
        매집 점수 (0 ~ +100)

        Chaikin Money Flow 및 패턴 기반
        """
        high = data['high']
        low = data['low']
        close = data['close']
        volume = data['volume']

        # Money Flow Multiplier
        mf_mult = ((close - low) - (high - close)) / (high - low + 1e-10)
        mf_volume = mf_mult * volume

        # Chaikin Money Flow (20일)
        cmf = mf_volume.rolling(20).sum() / (volume.rolling(20).sum() + 1e-10)
        current_cmf = cmf.iloc[-1]

        score = 0.0

        # CMF 양수 = 매집
        if current_cmf > 0.1:
            score = 80
        elif current_cmf > 0.05:
            score = 50
        elif current_cmf > 0:
            score = 25

        # 연속 매집 일수 가점
        positive_days = (cmf.tail(5) > 0).sum()
        score += positive_days * 4

        return np.clip(score, 0, 100)

    def _calculate_distribution_score(self, data: pd.DataFrame) -> float:
        """
        분산 점수 (0 ~ +100)

        매도 압력 분석
        """
        high = data['high']
        low = data['low']
        close = data['close']
        volume = data['volume']

        # Money Flow Multiplier
        mf_mult = ((close - low) - (high - close)) / (high - low + 1e-10)
        mf_volume = mf_mult * volume

        # Chaikin Money Flow
        cmf = mf_volume.rolling(20).sum() / (volume.rolling(20).sum() + 1e-10)
        current_cmf = cmf.iloc[-1]

        score = 0.0

        # CMF 음수 = 분산
        if current_cmf < -0.1:
            score = 80
        elif current_cmf < -0.05:
            score = 50
        elif current_cmf < 0:
            score = 25

        # 연속 분산 일수 가점
        negative_days = (cmf.tail(5) < 0).sum()
        score += negative_days * 4

        return np.clip(score, 0, 100)

    def _calculate_pv_confirmation_score(self, data: pd.DataFrame) -> float:
        """
        가격-거래량 확인 점수 (-100 ~ +100)

        가격 움직임과 거래량의 일치도
        """
        close = data['close']
        volume = data['volume']

        # 최근 5일 분석
        price_changes = close.pct_change().tail(5)
        volume_changes = volume.pct_change().tail(5)

        score = 0.0

        # 상승일 거래량 증가 = 긍정적
        up_days = price_changes > 0
        down_days = price_changes < 0

        if up_days.any():
            avg_up_vol_change = volume_changes[up_days].mean()
            if avg_up_vol_change > 0.1:
                score += 40
            elif avg_up_vol_change > 0:
                score += 20

        if down_days.any():
            avg_down_vol_change = volume_changes[down_days].mean()
            if avg_down_vol_change > 0.1:
                score -= 40  # 하락일 거래량 증가 = 매도 압력
            elif avg_down_vol_change < 0:
                score += 20  # 하락일 거래량 감소 = 매도 압력 감소

        # 전체 추세 확인
        price_trend = close.iloc[-1] > close.iloc[-5]
        volume_trend = volume.iloc[-1] > volume.rolling(5).mean().iloc[-1]

        if price_trend and volume_trend:
            score += 20  # 상승 + 거래량 증가 확인
        elif not price_trend and volume_trend:
            score -= 20  # 하락 + 거래량 증가 = 매도 압력

        return np.clip(score, -100, 100)

    def detect_volume_pattern(self, data: pd.DataFrame) -> Optional[str]:
        """
        특수 거래량 패턴 감지

        Returns:
            'climax_top': 정점 클라이맥스
            'climax_bottom': 바닥 클라이맥스
            'dry_up': 거래량 고갈
            'breakout': 돌파 거래량
            None: 특별한 패턴 없음
        """
        volume = data['volume']
        close = data['close']

        volume_ma = volume.rolling(20).mean()
        volume_std = volume.rolling(20).std()

        current_volume = volume.iloc[-1]
        current_price = close.iloc[-1]
        price_change = close.pct_change().iloc[-1]

        # 거래량 Z-점수
        z_score = (current_volume - volume_ma.iloc[-1]) / (volume_std.iloc[-1] + 1e-10)

        # 클라이맥스 탑 (대량 거래 + 급등 후)
        if z_score > 3 and price_change > 0.03:
            high_20d = close.tail(20).max()
            if current_price >= high_20d * 0.98:
                return 'climax_top'

        # 클라이맥스 바텀 (대량 거래 + 급락)
        if z_score > 3 and price_change < -0.03:
            low_20d = close.tail(20).min()
            if current_price <= low_20d * 1.02:
                return 'climax_bottom'

        # 거래량 고갈
        if z_score < -1.5:
            return 'dry_up'

        # 돌파 거래량
        if z_score > 2:
            high_5d = close.tail(5).max()
            if current_price > high_5d and price_change > 0.02:
                return 'breakout'

        return None
