"""
퀀트 전략 통합 설정
30년 퀀트 경험 기반 파라미터 - 단순하고 견고한 시스템
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum


class MarketRegime(Enum):
    """시장 레짐 (상태)"""
    BULL = "bull"           # 상승장
    BEAR = "bear"           # 하락장
    SIDEWAYS = "sideways"   # 횡보장
    HIGH_VOL = "high_vol"   # 고변동성


@dataclass
class LiquidityFilter:
    """
    유동성 필터 (Hard Filter)
    - 이 조건을 통과하지 못하면 절대 선정 불가
    - 슬리피지와 체결 리스크 최소화가 목적
    """
    min_trading_value: float = 500_000_000      # 일평균 거래대금 5억원
    min_market_cap: float = 50_000_000_000      # 시가총액 500억원
    min_price: int = 1000                        # 최소 주가 1,000원 (동전주 제외)
    min_volume: int = 10000                      # 최소 거래량 1만주


@dataclass
class MomentumConfig:
    """
    모멘텀 스코어 설정
    - 학술 연구 기반: Jegadeesh & Titman (1993)
    - "최근 수익률이 좋은 주식이 계속 좋다" (모멘텀 효과)
    """
    # 수익률 계산 기간
    return_period: int = 20                     # 20일 수익률 (약 1개월)
    volume_short_period: int = 5                # 단기 거래량 평균 (5일)
    volume_long_period: int = 20                # 장기 거래량 평균 (20일)

    # 가중치 (합계 = 1.0)
    relative_return_weight: float = 0.50        # 시장 대비 초과수익률 50%
    volume_surge_weight: float = 0.30           # 거래량 서지 30%
    price_strength_weight: float = 0.20         # 가격 위치 강도 20%

    # 선정 기준
    top_percentile: float = 0.10                # 상위 10% 선정
    max_stocks: int = 15                        # 최대 15개
    sector_limit: int = 3                       # 섹터당 최대 3개


@dataclass
class PositionSizingConfig:
    """
    포지션 사이징 설정 (ATR 기반)
    - 핵심 원리: 모든 종목이 동일한 리스크 기여
    - 변동성 높은 종목 = 적은 비중
    """
    # 변동성 목표
    target_daily_vol: float = 0.02              # 목표 일일 변동성 2%
    max_portfolio_vol: float = 0.15             # 포트폴리오 최대 변동성 15%

    # 포지션 크기 제한
    max_position_pct: float = 0.10              # 최대 단일 포지션 10%
    min_position_pct: float = 0.03              # 최소 단일 포지션 3%

    # ATR 설정
    atr_period: int = 14                        # ATR 계산 기간

    # 손절/익절 설정 (ATR 배수)
    stop_loss_atr: float = 2.0                  # 손절 = 2 ATR
    take_profit_atr: float = 3.0                # 익절 = 3 ATR

    # 트레일링 스탑
    use_trailing_stop: bool = True
    trailing_activation_pct: float = 0.03       # 3% 수익 후 트레일링 활성화
    trailing_atr: float = 1.5                   # 트레일링 = 1.5 ATR


@dataclass
class FeedbackConfig:
    """
    학습 피드백 설정
    - 거래 결과를 즉시 반영하여 파라미터 조정
    """
    # 피드백 윈도우
    rolling_window: int = 20                    # 최근 20거래 기준

    # 파라미터 조정 임계값
    win_rate_tighten: float = 0.35              # 승률 35% 미만 → 기준 강화
    win_rate_loosen: float = 0.55               # 승률 55% 초과 → 기준 완화

    # EMA 가중치 (최근 데이터 중시)
    ema_alpha: float = 0.3                      # 최근 30% + 과거 70%

    # 조정 폭
    adjustment_step: float = 0.05               # 5%씩 조정


@dataclass
class RegimeConfig:
    """
    시장 레짐별 설정 조정
    - 상승장/하락장에 따라 전략 조정
    """
    # 레짐 판단 기준
    bull_threshold: float = 0.05                # KOSPI 20일 수익률 > 5% → 상승장
    bear_threshold: float = -0.05               # KOSPI 20일 수익률 < -5% → 하락장
    high_vol_threshold: float = 0.25            # VIX > 25 → 고변동성

    # 레짐별 포지션 조정
    regime_adjustments: Dict[str, Dict] = field(default_factory=lambda: {
        "bull": {
            "max_stocks": 20,
            "max_position_pct": 0.12,
            "stop_loss_atr": 2.5,
        },
        "bear": {
            "max_stocks": 8,
            "max_position_pct": 0.06,
            "stop_loss_atr": 1.5,
        },
        "sideways": {
            "max_stocks": 15,
            "max_position_pct": 0.10,
            "stop_loss_atr": 2.0,
        },
        "high_vol": {
            "max_stocks": 10,
            "max_position_pct": 0.05,
            "stop_loss_atr": 3.0,
        }
    })


@dataclass
class QuantConfig:
    """
    퀀트 전략 통합 설정
    - 모든 설정을 하나로 통합
    - 기존 FilteringCriteria 대체
    """
    liquidity: LiquidityFilter = field(default_factory=LiquidityFilter)
    momentum: MomentumConfig = field(default_factory=MomentumConfig)
    position_sizing: PositionSizingConfig = field(default_factory=PositionSizingConfig)
    feedback: FeedbackConfig = field(default_factory=FeedbackConfig)
    regime: RegimeConfig = field(default_factory=RegimeConfig)

    # 현재 시장 레짐 (동적으로 업데이트)
    current_regime: MarketRegime = MarketRegime.SIDEWAYS

    def get_adjusted_config(self) -> Dict:
        """현재 레짐에 맞게 조정된 설정 반환"""
        regime_key = self.current_regime.value
        adjustments = self.regime.regime_adjustments.get(regime_key, {})

        return {
            "max_stocks": adjustments.get("max_stocks", self.momentum.max_stocks),
            "max_position_pct": adjustments.get("max_position_pct", self.position_sizing.max_position_pct),
            "stop_loss_atr": adjustments.get("stop_loss_atr", self.position_sizing.stop_loss_atr),
        }


# 싱글톤 인스턴스 (스레드 안전)
import threading
_quant_config: Optional[QuantConfig] = None
_quant_config_lock = threading.Lock()


def get_quant_config() -> QuantConfig:
    """퀀트 설정 싱글톤 인스턴스 반환 (스레드 안전)"""
    global _quant_config
    if _quant_config is None:
        with _quant_config_lock:
            # Double-checked locking
            if _quant_config is None:
                _quant_config = QuantConfig()
    return _quant_config


def reset_quant_config():
    """퀀트 설정 초기화 (테스트용)"""
    global _quant_config
    with _quant_config_lock:
        _quant_config = None
