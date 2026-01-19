# -*- coding: utf-8 -*-
"""
시장 적응형 리스크 관리 (P1-5)

기능:
- KOSPI/시장 변동성 계산 (연율화)
- 5단계 시장 상황 분류 (very_low ~ very_high)
- 상황별 손절배수, 포지션 크기, 최대 종목수 자동 조정

고변동성 시장에서 동일 전략 = 큰 손실 위험
→ 시장 상황에 따라 리스크 파라미터 자동 조정
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple
from datetime import datetime
from enum import Enum
import pandas as pd
import numpy as np

from ..utils.log_utils import get_logger

logger = get_logger(__name__)


class MarketVolatility(Enum):
    """시장 변동성 단계"""
    VERY_LOW = "very_low"      # VIX < 12 equivalent
    LOW = "low"                # 12-16
    NORMAL = "normal"          # 16-20
    HIGH = "high"              # 20-30
    VERY_HIGH = "very_high"    # > 30


@dataclass
class RiskConfig:
    """리스크 설정"""
    stop_multiplier: float      # ATR 손절 배수
    profit_multiplier: float    # ATR 익절 배수
    position_factor: float      # 포지션 크기 배수 (1.0 = 기본)
    max_positions: int          # 최대 동시 보유 종목 수
    max_single_exposure: float  # 단일 종목 최대 비중 (%)
    max_total_exposure: float   # 총 투자 비중 (%)

    def to_dict(self) -> Dict:
        return {
            "stop_multiplier": self.stop_multiplier,
            "profit_multiplier": self.profit_multiplier,
            "position_factor": self.position_factor,
            "max_positions": self.max_positions,
            "max_single_exposure": self.max_single_exposure,
            "max_total_exposure": self.max_total_exposure,
        }


@dataclass
class MarketState:
    """시장 상태"""
    volatility_level: MarketVolatility
    volatility_pct: float           # 연율화 변동성 (%)
    trend: str                      # up, down, sideways
    risk_config: RiskConfig
    analysis_date: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict:
        return {
            "volatility_level": self.volatility_level.value,
            "volatility_pct": round(self.volatility_pct, 2),
            "trend": self.trend,
            "risk_config": self.risk_config.to_dict(),
            "analysis_date": self.analysis_date,
            "timestamp": self.timestamp,
        }


class MarketAdaptiveRisk:
    """시장 적응형 리스크 관리자

    시장 변동성에 따라 리스크 파라미터를 자동 조정합니다.

    변동성 기준 (연율화, %):
    - very_low: < 12
    - low: 12 ~ 16
    - normal: 16 ~ 20
    - high: 20 ~ 30
    - very_high: > 30
    """

    # 변동성별 기본 설정
    DEFAULT_CONFIGS: Dict[MarketVolatility, Dict] = {
        MarketVolatility.VERY_LOW: {
            'stop_multiplier': 1.5,
            'profit_multiplier': 2.5,
            'position_factor': 1.2,
            'max_positions': 15,
            'max_single_exposure': 15.0,
            'max_total_exposure': 95.0,
        },
        MarketVolatility.LOW: {
            'stop_multiplier': 1.8,
            'profit_multiplier': 2.8,
            'position_factor': 1.1,
            'max_positions': 12,
            'max_single_exposure': 12.0,
            'max_total_exposure': 90.0,
        },
        MarketVolatility.NORMAL: {
            'stop_multiplier': 2.0,
            'profit_multiplier': 3.0,
            'position_factor': 1.0,
            'max_positions': 10,
            'max_single_exposure': 10.0,
            'max_total_exposure': 80.0,
        },
        MarketVolatility.HIGH: {
            'stop_multiplier': 2.5,
            'profit_multiplier': 3.5,
            'position_factor': 0.7,
            'max_positions': 7,
            'max_single_exposure': 8.0,
            'max_total_exposure': 60.0,
        },
        MarketVolatility.VERY_HIGH: {
            'stop_multiplier': 3.0,
            'profit_multiplier': 4.0,
            'position_factor': 0.5,
            'max_positions': 5,
            'max_single_exposure': 5.0,
            'max_total_exposure': 40.0,
        },
    }

    # 변동성 임계값 (연율화, %)
    VOLATILITY_THRESHOLDS = {
        'very_low': 12.0,
        'low': 16.0,
        'normal': 20.0,
        'high': 30.0,
        # very_high: > 30
    }

    def __init__(
        self,
        custom_configs: Optional[Dict[MarketVolatility, Dict]] = None,
        trading_days: int = 252,
    ):
        """초기화

        Args:
            custom_configs: 커스텀 설정 (없으면 기본값 사용)
            trading_days: 연간 거래일 수 (연율화에 사용)
        """
        self.trading_days = trading_days
        self.configs = custom_configs or self.DEFAULT_CONFIGS.copy()

        # 현재 시장 상태 캐시
        self._current_state: Optional[MarketState] = None
        self._cache_date: Optional[str] = None

        logger.info("MarketAdaptiveRisk 초기화 완료")

    def analyze_market(
        self,
        market_df: pd.DataFrame,
        period: int = 20
    ) -> MarketState:
        """시장 상태 분석

        Args:
            market_df: 시장(KOSPI) OHLCV 데이터
            period: 변동성 계산 기간 (일)

        Returns:
            MarketState 시장 상태
        """
        if market_df is None or len(market_df) < period:
            logger.warning("시장 데이터 부족, 기본 설정 사용")
            return self._get_default_state()

        # 변동성 계산
        volatility_pct = self._calculate_volatility(market_df, period)

        # 변동성 레벨 분류
        volatility_level = self._classify_volatility(volatility_pct)

        # 추세 분석
        trend = self._analyze_trend(market_df, period)

        # 리스크 설정 가져오기
        risk_config = self._get_risk_config(volatility_level)

        state = MarketState(
            volatility_level=volatility_level,
            volatility_pct=volatility_pct,
            trend=trend,
            risk_config=risk_config,
        )

        # 캐시 업데이트
        self._current_state = state
        self._cache_date = datetime.now().strftime("%Y-%m-%d")

        logger.info(
            f"시장 분석 완료 - 변동성: {volatility_pct:.1f}% ({volatility_level.value}), "
            f"추세: {trend}, 손절배수: {risk_config.stop_multiplier}x"
        )

        return state

    def _calculate_volatility(
        self,
        df: pd.DataFrame,
        period: int
    ) -> float:
        """연율화 변동성 계산 (%)

        Args:
            df: OHLCV DataFrame
            period: 계산 기간

        Returns:
            연율화 변동성 (%)
        """
        # close 컬럼 확인
        close_col = 'close' if 'close' in df.columns else 'Close'

        if close_col not in df.columns:
            return 16.0  # 기본값 (normal)

        # 일별 수익률
        returns = df[close_col].pct_change().dropna()

        if len(returns) < period:
            return 16.0

        # 최근 period일 표준편차
        daily_std = returns.tail(period).std()

        # 연율화 (√252)
        annualized_vol = daily_std * np.sqrt(self.trading_days) * 100

        return annualized_vol

    def _classify_volatility(self, volatility_pct: float) -> MarketVolatility:
        """변동성 레벨 분류

        Args:
            volatility_pct: 연율화 변동성 (%)

        Returns:
            MarketVolatility 레벨
        """
        if volatility_pct < self.VOLATILITY_THRESHOLDS['very_low']:
            return MarketVolatility.VERY_LOW
        elif volatility_pct < self.VOLATILITY_THRESHOLDS['low']:
            return MarketVolatility.LOW
        elif volatility_pct < self.VOLATILITY_THRESHOLDS['normal']:
            return MarketVolatility.NORMAL
        elif volatility_pct < self.VOLATILITY_THRESHOLDS['high']:
            return MarketVolatility.HIGH
        else:
            return MarketVolatility.VERY_HIGH

    def _analyze_trend(self, df: pd.DataFrame, period: int) -> str:
        """시장 추세 분석

        Args:
            df: OHLCV DataFrame
            period: 분석 기간

        Returns:
            추세: 'up', 'down', 'sideways'
        """
        close_col = 'close' if 'close' in df.columns else 'Close'

        if close_col not in df.columns or len(df) < period:
            return 'sideways'

        # 이동평균 기반 추세 판단
        ma_short = df[close_col].tail(period // 2).mean()
        ma_long = df[close_col].tail(period).mean()

        # 가격 변화율
        price_change = (df[close_col].iloc[-1] - df[close_col].iloc[-period]) / df[close_col].iloc[-period]

        if price_change > 0.05 and ma_short > ma_long:
            return 'up'
        elif price_change < -0.05 and ma_short < ma_long:
            return 'down'
        else:
            return 'sideways'

    def _get_risk_config(self, volatility_level: MarketVolatility) -> RiskConfig:
        """변동성 레벨에 맞는 리스크 설정 반환

        Args:
            volatility_level: 변동성 레벨

        Returns:
            RiskConfig
        """
        config = self.configs.get(volatility_level, self.configs[MarketVolatility.NORMAL])

        return RiskConfig(
            stop_multiplier=config['stop_multiplier'],
            profit_multiplier=config['profit_multiplier'],
            position_factor=config['position_factor'],
            max_positions=config['max_positions'],
            max_single_exposure=config['max_single_exposure'],
            max_total_exposure=config['max_total_exposure'],
        )

    def _get_default_state(self) -> MarketState:
        """기본 시장 상태 반환"""
        return MarketState(
            volatility_level=MarketVolatility.NORMAL,
            volatility_pct=16.0,
            trend='sideways',
            risk_config=self._get_risk_config(MarketVolatility.NORMAL),
        )

    # ========== 편의 메서드 ==========

    def get_current_state(self) -> Optional[MarketState]:
        """현재 캐시된 시장 상태"""
        return self._current_state

    def get_stop_multiplier(self) -> float:
        """현재 손절 배수"""
        if self._current_state:
            return self._current_state.risk_config.stop_multiplier
        return 2.0  # 기본값

    def get_profit_multiplier(self) -> float:
        """현재 익절 배수"""
        if self._current_state:
            return self._current_state.risk_config.profit_multiplier
        return 3.0

    def get_position_factor(self) -> float:
        """현재 포지션 크기 배수"""
        if self._current_state:
            return self._current_state.risk_config.position_factor
        return 1.0

    def get_max_positions(self) -> int:
        """현재 최대 보유 종목 수"""
        if self._current_state:
            return self._current_state.risk_config.max_positions
        return 10

    def get_volatility_for_level(self, level: str) -> Tuple[float, float]:
        """특정 레벨의 변동성 범위 반환

        Args:
            level: 변동성 레벨 ('very_low', 'low', 'normal', 'high', 'very_high')

        Returns:
            (최소, 최대) 변동성 범위
        """
        thresholds = list(self.VOLATILITY_THRESHOLDS.values())

        if level == 'very_low':
            return (0.0, thresholds[0])
        elif level == 'low':
            return (thresholds[0], thresholds[1])
        elif level == 'normal':
            return (thresholds[1], thresholds[2])
        elif level == 'high':
            return (thresholds[2], thresholds[3])
        else:  # very_high
            return (thresholds[3], 100.0)

    def get_all_configs(self) -> Dict[str, Dict]:
        """모든 변동성 레벨별 설정 반환"""
        return {
            level.value: self._get_risk_config(level).to_dict()
            for level in MarketVolatility
        }

    def update_config(
        self,
        volatility_level: MarketVolatility,
        **kwargs
    ):
        """특정 변동성 레벨의 설정 업데이트

        Args:
            volatility_level: 변동성 레벨
            **kwargs: 업데이트할 설정 (stop_multiplier, position_factor, etc.)
        """
        if volatility_level not in self.configs:
            self.configs[volatility_level] = self.DEFAULT_CONFIGS[volatility_level].copy()

        for key, value in kwargs.items():
            if key in self.configs[volatility_level]:
                self.configs[volatility_level][key] = value

        logger.info(f"{volatility_level.value} 설정 업데이트: {kwargs}")


# 편의 함수
def analyze_market_risk(
    market_df: pd.DataFrame,
    period: int = 20
) -> MarketState:
    """시장 리스크 분석 편의 함수

    Args:
        market_df: 시장(KOSPI) OHLCV 데이터
        period: 변동성 계산 기간

    Returns:
        MarketState
    """
    analyzer = MarketAdaptiveRisk()
    return analyzer.analyze_market(market_df, period)


def get_risk_config_for_volatility(volatility_pct: float) -> RiskConfig:
    """변동성에 맞는 리스크 설정 반환

    Args:
        volatility_pct: 연율화 변동성 (%)

    Returns:
        RiskConfig
    """
    analyzer = MarketAdaptiveRisk()
    level = analyzer._classify_volatility(volatility_pct)
    return analyzer._get_risk_config(level)
