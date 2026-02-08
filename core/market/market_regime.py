#!/usr/bin/env python3
"""
시장 체제 감지 모듈
KOSPI 기반 Bull/Bear/Sideways/High Volatility 분류
"""

from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Optional
import numpy as np

from core.utils.log_utils import get_logger
from core.api.market_data_client import MarketDataClientWithFallback

logger = get_logger(__name__)


class MarketRegime(Enum):
    """시장 체제"""
    BULL = "bull"
    BEAR = "bear"
    SIDEWAYS = "sideways"
    HIGH_VOLATILITY = "high_vol"


@dataclass
class RegimeResult:
    """체제 감지 결과"""
    regime: MarketRegime
    confidence: float  # 0.0 ~ 1.0
    metrics: Dict[str, float]
    detected_at: str


class MarketRegimeDetector:
    """시장 체제 감지기"""

    def __init__(
        self,
        lookback_days: int = 60,
        bull_threshold: float = 0.0005,  # 일평균 0.05% 이상
        bear_threshold: float = -0.0005,  # 일평균 -0.05% 이하
        high_vol_threshold: float = 0.25  # 연율화 변동성 25% 이상
    ):
        """
        Args:
            lookback_days: 분석 기간 (기본 60일)
            bull_threshold: 상승장 판단 임계값
            bear_threshold: 하락장 판단 임계값
            high_vol_threshold: 고변동성 판단 임계값
        """
        # 입력 검증
        if lookback_days < 20:
            raise ValueError(f"lookback_days must be >= 20, got {lookback_days}")
        if bull_threshold <= bear_threshold:
            raise ValueError(
                f"bull_threshold ({bull_threshold}) must be > bear_threshold ({bear_threshold})"
            )
        if high_vol_threshold <= 0:
            raise ValueError(f"high_vol_threshold must be > 0, got {high_vol_threshold}")

        self.lookback_days = lookback_days
        self.bull_threshold = bull_threshold
        self.bear_threshold = bear_threshold
        self.high_vol_threshold = high_vol_threshold
        self.market_client = MarketDataClientWithFallback()

        logger.info(
            f"MarketRegimeDetector 초기화: lookback={lookback_days}일, "
            f"bull_threshold={bull_threshold:.4f}, "
            f"bear_threshold={bear_threshold:.4f}, "
            f"high_vol_threshold={high_vol_threshold:.2f}"
        )

    def detect_regime(
        self,
        reference_date: Optional[str] = None
    ) -> RegimeResult:
        """현재 시장 체제 감지

        Args:
            reference_date: 기준 날짜 (YYYY-MM-DD, 기본: 오늘)

        Returns:
            RegimeResult: 감지 결과
        """
        if reference_date is None:
            reference_date = datetime.now().strftime("%Y-%m-%d")

        # 날짜 형식 검증
        try:
            datetime.strptime(reference_date, "%Y-%m-%d")
        except ValueError as e:
            logger.error(f"잘못된 날짜 형식: {reference_date}", exc_info=True)
            raise ValueError(
                f"Invalid date format: {reference_date}, expected YYYY-MM-DD"
            ) from e

        try:
            # 1. KOSPI 데이터 조회 (lookback_days)
            end_date = datetime.strptime(reference_date, "%Y-%m-%d")
            start_date = end_date - timedelta(days=self.lookback_days + 30)  # 여유분

            kospi_data = self.market_client.get_kospi_history(
                start_date=start_date.strftime("%Y%m%d"),
                end_date=end_date.strftime("%Y%m%d")
            )

            if not kospi_data or len(kospi_data) < 20:
                logger.warning(f"KOSPI 데이터 부족: {len(kospi_data) if kospi_data else 0}개")
                return self._default_regime()

            # 2. 지표 계산
            closes = np.array([d['close'] for d in kospi_data[-self.lookback_days:]])
            daily_returns = np.diff(closes) / closes[:-1]

            trend = np.mean(daily_returns)  # 일평균 수익률
            volatility = np.std(daily_returns) * np.sqrt(252)  # 연율화

            # 3. 이동평균 크로스오버 (20일/60일)
            sma_20 = np.mean(closes[-20:])
            if len(closes) < 60:
                logger.warning(
                    f"데이터 {len(closes)}일 < 60일: SMA 크로스오버 신뢰도 저하 "
                    f"(reference_date={reference_date})"
                )
                sma_60 = sma_20
            else:
                sma_60 = np.mean(closes[-60:])
            sma_cross = (sma_20 - sma_60) / sma_60 if sma_60 > 0 else 0.0

            # 4. 체제 분류
            regime, confidence = self._classify_regime(
                trend, volatility, sma_cross
            )

            metrics = {
                'daily_avg_return': float(trend),
                'annualized_volatility': float(volatility),
                'sma_20': float(sma_20),
                'sma_60': float(sma_60),
                'sma_cross_pct': float(sma_cross * 100)
            }

            logger.info(
                f"시장 체제 감지: {regime.value} (신뢰도 {confidence:.1%}), "
                f"추세={trend:.4f}, 변동성={volatility:.2%}"
            )

            return RegimeResult(
                regime=regime,
                confidence=confidence,
                metrics=metrics,
                detected_at=reference_date
            )

        except Exception as e:
            logger.error(f"시장 체제 감지 실패: {e}", exc_info=True)
            return self._default_regime()

    def _classify_regime(
        self,
        trend: float,
        volatility: float,
        sma_cross: float
    ) -> tuple[MarketRegime, float]:
        """체제 분류 로직

        Returns:
            (MarketRegime, confidence)
        """
        # 1. 고변동성 체크 (최우선)
        if volatility > self.high_vol_threshold:
            confidence = min(1.0, volatility / (self.high_vol_threshold * 1.5))
            return MarketRegime.HIGH_VOLATILITY, confidence

        # 2. 추세 + SMA 크로스오버 종합 판단
        if trend > self.bull_threshold and sma_cross > 0.01:
            # 상승 추세 + 단기 평균 > 장기 평균
            confidence = min(1.0, abs(trend) / (self.bull_threshold * 10))
            return MarketRegime.BULL, confidence

        if trend < self.bear_threshold and sma_cross < -0.01:
            # 하락 추세 + 단기 평균 < 장기 평균
            confidence = min(1.0, abs(trend) / (abs(self.bear_threshold) * 10))
            return MarketRegime.BEAR, confidence

        # 3. 횡보 (추세 약하거나 SMA 크로스 미미)
        confidence = 1.0 - min(abs(trend) / 0.001, 1.0)
        return MarketRegime.SIDEWAYS, confidence

    def _default_regime(self) -> RegimeResult:
        """기본 체제 (데이터 부족 시)"""
        logger.warning("기본 체제(SIDEWAYS) 반환")
        return RegimeResult(
            regime=MarketRegime.SIDEWAYS,
            confidence=0.5,
            metrics={},
            detected_at=datetime.now().strftime("%Y-%m-%d")
        )
