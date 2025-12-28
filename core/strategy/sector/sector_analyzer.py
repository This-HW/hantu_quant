"""
섹터 분석기 모듈

섹터별 수익률, 모멘텀, 거래량 추세를 분석합니다.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging

from .sector_map import Sector, SectorMap

logger = logging.getLogger(__name__)


@dataclass
class SectorMetrics:
    """섹터 지표"""
    sector: Sector
    return_1m: float = 0.0  # 1개월 수익률
    return_3m: float = 0.0  # 3개월 수익률
    return_6m: float = 0.0  # 6개월 수익률
    rsi: float = 50.0  # RSI (0-100)
    volume_trend: float = 0.0  # 거래량 추세 (-1 ~ +1)
    momentum_score: float = 0.0  # 종합 모멘텀 점수 (-100 ~ +100)
    volatility: float = 0.0  # 변동성
    relative_strength: float = 0.0  # 시장 대비 상대강도
    stock_count: int = 0
    advancing: int = 0  # 상승 종목 수
    declining: int = 0  # 하락 종목 수

    @property
    def advance_decline_ratio(self) -> float:
        """상승/하락 비율"""
        if self.declining == 0:
            return float(self.advancing)
        return self.advancing / self.declining

    @property
    def is_strong(self) -> bool:
        """강세 섹터 여부"""
        return self.momentum_score > 30 and self.relative_strength > 0

    @property
    def is_weak(self) -> bool:
        """약세 섹터 여부"""
        return self.momentum_score < -30 and self.relative_strength < 0

    def to_dict(self) -> Dict:
        return {
            'sector': self.sector.value,
            'return_1m': self.return_1m,
            'return_3m': self.return_3m,
            'return_6m': self.return_6m,
            'rsi': self.rsi,
            'volume_trend': self.volume_trend,
            'momentum_score': self.momentum_score,
            'volatility': self.volatility,
            'relative_strength': self.relative_strength,
            'stock_count': self.stock_count,
            'advancing': self.advancing,
            'declining': self.declining,
            'ad_ratio': self.advance_decline_ratio,
        }


class SectorAnalyzer:
    """
    섹터 분석기

    섹터별 모멘텀과 상대강도를 분석합니다.
    """

    def __init__(
        self,
        sector_map: Optional[SectorMap] = None,
        rsi_period: int = 14,
        momentum_weights: Optional[Dict[str, float]] = None
    ):
        """
        Args:
            sector_map: 섹터 매핑 객체
            rsi_period: RSI 계산 기간
            momentum_weights: 모멘텀 점수 가중치
        """
        self.sector_map = sector_map or SectorMap()
        self.rsi_period = rsi_period
        self.momentum_weights = momentum_weights or {
            'return_1m': 0.25,
            'return_3m': 0.30,
            'return_6m': 0.20,
            'rsi': 0.15,
            'volume': 0.10,
        }

    def analyze_sector(
        self,
        sector: Sector,
        stock_data: Dict[str, pd.DataFrame],
        market_data: Optional[pd.DataFrame] = None
    ) -> SectorMetrics:
        """
        개별 섹터 분석

        Args:
            sector: 분석할 섹터
            stock_data: {종목코드: OHLCV DataFrame} 딕셔너리
            market_data: 시장 지수 데이터 (상대강도 계산용)

        Returns:
            SectorMetrics: 섹터 지표
        """
        stocks = self.sector_map.get_stocks_in_sector(sector)
        available_stocks = [s for s in stocks if s in stock_data]

        if not available_stocks:
            return SectorMetrics(sector=sector)

        # 섹터 합성 가격 계산
        sector_prices = self._calculate_sector_price(available_stocks, stock_data)

        if sector_prices is None or len(sector_prices) < 60:
            return SectorMetrics(sector=sector)

        # 수익률 계산
        return_1m = self._calculate_return(sector_prices, 21)
        return_3m = self._calculate_return(sector_prices, 63)
        return_6m = self._calculate_return(sector_prices, 126)

        # RSI 계산
        rsi = self._calculate_rsi(sector_prices)

        # 거래량 추세
        sector_volume = self._calculate_sector_volume(available_stocks, stock_data)
        volume_trend = self._calculate_volume_trend(sector_volume)

        # 변동성
        volatility = sector_prices.pct_change().std() * np.sqrt(252)

        # 상대강도 (시장 대비)
        relative_strength = 0.0
        if market_data is not None and len(market_data) >= len(sector_prices):
            relative_strength = self._calculate_relative_strength(
                sector_prices, market_data
            )

        # 상승/하락 종목 수
        advancing, declining = self._count_advance_decline(available_stocks, stock_data)

        # 모멘텀 점수 계산
        momentum_score = self._calculate_momentum_score(
            return_1m, return_3m, return_6m, rsi, volume_trend
        )

        return SectorMetrics(
            sector=sector,
            return_1m=return_1m,
            return_3m=return_3m,
            return_6m=return_6m,
            rsi=rsi,
            volume_trend=volume_trend,
            momentum_score=momentum_score,
            volatility=volatility,
            relative_strength=relative_strength,
            stock_count=len(available_stocks),
            advancing=advancing,
            declining=declining
        )

    def analyze_all_sectors(
        self,
        stock_data: Dict[str, pd.DataFrame],
        market_data: Optional[pd.DataFrame] = None
    ) -> Dict[Sector, SectorMetrics]:
        """
        전체 섹터 분석

        Args:
            stock_data: {종목코드: OHLCV DataFrame} 딕셔너리
            market_data: 시장 지수 데이터

        Returns:
            {섹터: 지표} 딕셔너리
        """
        results = {}

        for sector in self.sector_map.get_active_sectors():
            metrics = self.analyze_sector(sector, stock_data, market_data)
            if metrics.stock_count > 0:
                results[sector] = metrics

        return results

    def rank_sectors(
        self,
        metrics: Dict[Sector, SectorMetrics],
        sort_by: str = 'momentum_score'
    ) -> List[Tuple[Sector, SectorMetrics, int]]:
        """
        섹터 순위 정렬

        Args:
            metrics: 섹터 지표 딕셔너리
            sort_by: 정렬 기준 ('momentum_score', 'return_1m', 'relative_strength')

        Returns:
            [(섹터, 지표, 순위)] 리스트
        """
        sorted_sectors = sorted(
            metrics.items(),
            key=lambda x: getattr(x[1], sort_by),
            reverse=True
        )

        return [
            (sector, m, rank + 1)
            for rank, (sector, m) in enumerate(sorted_sectors)
        ]

    def get_top_sectors(
        self,
        metrics: Dict[Sector, SectorMetrics],
        n: int = 3
    ) -> List[Sector]:
        """상위 N개 섹터"""
        ranked = self.rank_sectors(metrics)
        return [sector for sector, _, _ in ranked[:n]]

    def get_bottom_sectors(
        self,
        metrics: Dict[Sector, SectorMetrics],
        n: int = 3
    ) -> List[Sector]:
        """하위 N개 섹터"""
        ranked = self.rank_sectors(metrics)
        return [sector for sector, _, _ in ranked[-n:]]

    def _calculate_sector_price(
        self,
        stocks: List[str],
        stock_data: Dict[str, pd.DataFrame]
    ) -> Optional[pd.Series]:
        """섹터 합성 가격 계산 (시가총액 가중)"""
        prices = []
        weights = []

        for stock in stocks:
            if stock in stock_data:
                data = stock_data[stock]
                info = self.sector_map.get_stock_info(stock)
                weight = info.get('weight', 0.01) if info else 0.01

                # 정규화된 가격
                if len(data) > 0:
                    normalized = data['close'] / data['close'].iloc[0] * 100
                    prices.append(normalized)
                    weights.append(weight)

        if not prices:
            return None

        # 가중 평균 가격
        total_weight = sum(weights)
        weights = [w / total_weight for w in weights]

        sector_price = sum(p * w for p, w in zip(prices, weights))
        return sector_price

    def _calculate_sector_volume(
        self,
        stocks: List[str],
        stock_data: Dict[str, pd.DataFrame]
    ) -> pd.Series:
        """섹터 총 거래량 계산"""
        volumes = []

        for stock in stocks:
            if stock in stock_data:
                volumes.append(stock_data[stock]['volume'])

        if not volumes:
            return pd.Series()

        return sum(volumes)

    def _calculate_return(self, prices: pd.Series, days: int) -> float:
        """기간 수익률 계산"""
        if len(prices) < days + 1:
            return 0.0

        current = prices.iloc[-1]
        past = prices.iloc[-days - 1]

        return (current / past - 1) * 100

    def _calculate_rsi(self, prices: pd.Series) -> float:
        """RSI 계산"""
        if len(prices) < self.rsi_period + 1:
            return 50.0

        delta = prices.diff()
        gain = delta.where(delta > 0, 0).rolling(self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(self.rsi_period).mean()

        rs = gain / (loss + 1e-10)
        rsi = 100 - (100 / (1 + rs))

        return rsi.iloc[-1]

    def _calculate_volume_trend(self, volume: pd.Series) -> float:
        """거래량 추세 계산 (-1 ~ +1)"""
        if len(volume) < 20:
            return 0.0

        # 단기 vs 장기 이동평균
        vol_short = volume.rolling(5).mean().iloc[-1]
        vol_long = volume.rolling(20).mean().iloc[-1]

        if vol_long == 0:
            return 0.0

        ratio = vol_short / vol_long - 1
        return np.clip(ratio, -1, 1)

    def _calculate_relative_strength(
        self,
        sector_prices: pd.Series,
        market_prices: pd.Series
    ) -> float:
        """시장 대비 상대강도"""
        # 최근 20일 상대 성과
        lookback = min(20, len(sector_prices) - 1, len(market_prices) - 1)

        if lookback < 5:
            return 0.0

        sector_return = (sector_prices.iloc[-1] / sector_prices.iloc[-lookback - 1] - 1)

        # market_prices가 DataFrame인 경우 'close' 컬럼 사용
        if isinstance(market_prices, pd.DataFrame):
            market_close = market_prices['close']
        else:
            market_close = market_prices

        market_return = (market_close.iloc[-1] / market_close.iloc[-lookback - 1] - 1)

        relative = (sector_return - market_return) * 100
        return np.clip(relative, -50, 50)

    def _count_advance_decline(
        self,
        stocks: List[str],
        stock_data: Dict[str, pd.DataFrame]
    ) -> Tuple[int, int]:
        """상승/하락 종목 수 계산"""
        advancing = 0
        declining = 0

        for stock in stocks:
            if stock in stock_data:
                data = stock_data[stock]
                if len(data) >= 2:
                    change = data['close'].pct_change().iloc[-1]
                    if change > 0:
                        advancing += 1
                    elif change < 0:
                        declining += 1

        return advancing, declining

    def _calculate_momentum_score(
        self,
        return_1m: float,
        return_3m: float,
        return_6m: float,
        rsi: float,
        volume_trend: float
    ) -> float:
        """종합 모멘텀 점수 계산 (-100 ~ +100)"""
        # 수익률 점수 (-50 ~ +50)
        return_1m_score = np.clip(return_1m * 2, -50, 50)
        return_3m_score = np.clip(return_3m, -50, 50)
        return_6m_score = np.clip(return_6m / 2, -50, 50)

        # RSI 점수 (-50 ~ +50)
        rsi_score = (rsi - 50)  # 50 기준

        # 거래량 점수 (-50 ~ +50)
        volume_score = volume_trend * 50

        # 가중 합계
        score = (
            return_1m_score * self.momentum_weights['return_1m'] +
            return_3m_score * self.momentum_weights['return_3m'] +
            return_6m_score * self.momentum_weights['return_6m'] +
            rsi_score * self.momentum_weights['rsi'] +
            volume_score * self.momentum_weights['volume']
        )

        return np.clip(score, -100, 100)

    def get_sector_summary(
        self,
        metrics: Dict[Sector, SectorMetrics]
    ) -> Dict:
        """섹터 분석 요약"""
        ranked = self.rank_sectors(metrics)

        strong_sectors = [s.value for s, m, _ in ranked if m.is_strong]
        weak_sectors = [s.value for s, m, _ in ranked if m.is_weak]

        return {
            'total_sectors': len(metrics),
            'strong_sectors': strong_sectors,
            'weak_sectors': weak_sectors,
            'top_3': [(s.value, m.momentum_score) for s, m, _ in ranked[:3]],
            'bottom_3': [(s.value, m.momentum_score) for s, m, _ in ranked[-3:]],
            'average_momentum': np.mean([m.momentum_score for m in metrics.values()]),
        }
