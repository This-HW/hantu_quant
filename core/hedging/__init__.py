"""
Phase 3: 헤징 시스템 (P3-3)

선물 기반 포트폴리오 헤징 시스템

포함:
- FuturesHedger: KOSPI200 선물 헤징
- PortfolioBeta: 베타 계산기
- HedgePosition: 헤지 포지션 관리
"""

from .futures_hedger import (
    HedgeConfig,
    HedgePosition,
    HedgeSignal,
    PortfolioBeta,
    FuturesHedger,
)

__all__ = [
    'HedgeConfig',
    'HedgePosition',
    'HedgeSignal',
    'PortfolioBeta',
    'FuturesHedger',
]
