"""
백테스트 설정 모듈

슬리피지, 수수료, 포지션 관리 등 백테스트 실행에 필요한 설정을 정의합니다.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import date
from enum import Enum


class PositionSizeMethod(Enum):
    """포지션 사이즈 계산 방법"""
    FIXED = "fixed"              # 고정 금액
    PERCENT = "percent"          # 자본금 비율
    RISK_BASED = "risk_based"    # 리스크 기반 (ATR)
    KELLY = "kelly"              # 켈리 공식


class CommissionType(Enum):
    """수수료 유형"""
    PERCENT = "percent"          # 비율 수수료
    FIXED = "fixed"              # 고정 수수료
    TIERED = "tiered"            # 계층형 수수료


@dataclass
class CommissionConfig:
    """수수료 설정"""
    type: CommissionType = CommissionType.PERCENT
    buy_rate: float = 0.00015    # 매수 수수료 (0.015%)
    sell_rate: float = 0.00015   # 매도 수수료 (0.015%)
    tax_rate: float = 0.0023     # 매도세 (0.23% - 증권거래세)
    min_commission: float = 0    # 최소 수수료

    def calculate_buy_cost(self, amount: float) -> float:
        """매수 비용 계산"""
        if self.type == CommissionType.PERCENT:
            commission = amount * self.buy_rate
            return max(commission, self.min_commission)
        elif self.type == CommissionType.FIXED:
            return self.buy_rate
        return 0

    def calculate_sell_cost(self, amount: float) -> float:
        """매도 비용 계산 (수수료 + 세금)"""
        if self.type == CommissionType.PERCENT:
            commission = amount * self.sell_rate
            tax = amount * self.tax_rate
            return max(commission, self.min_commission) + tax
        elif self.type == CommissionType.FIXED:
            return self.sell_rate + (amount * self.tax_rate)
        return 0


@dataclass
class SlippageConfig:
    """슬리피지 설정"""
    type: str = "percent"        # "percent" 또는 "ticks"
    value: float = 0.001         # 슬리피지 비율 (0.1%)
    random_range: tuple = (0.0005, 0.002)  # 랜덤 범위
    use_random: bool = False     # 랜덤 슬리피지 사용 여부

    def apply_slippage(self, price: float, is_buy: bool) -> float:
        """슬리피지 적용"""
        import random

        if self.use_random:
            slippage = random.uniform(*self.random_range)
        else:
            slippage = self.value

        if self.type == "percent":
            if is_buy:
                return price * (1 + slippage)  # 매수: 가격 상승
            else:
                return price * (1 - slippage)  # 매도: 가격 하락
        else:  # ticks
            tick_value = slippage
            if is_buy:
                return price + tick_value
            else:
                return price - tick_value


@dataclass
class RiskConfig:
    """리스크 관리 설정"""
    max_drawdown: float = 0.20           # 최대 허용 낙폭 (20%)
    max_position_size: float = 0.10      # 최대 단일 포지션 (10%)
    max_positions: int = 10              # 최대 동시 포지션 수
    max_daily_loss: float = 0.05         # 일일 최대 손실 (5%)
    stop_on_max_drawdown: bool = True    # MDD 도달시 거래 중단
    use_dynamic_stops: bool = True       # ATR 기반 동적 손절
    stop_loss_pct: float = 0.03          # 기본 손절 비율 (3%)
    take_profit_pct: float = 0.08        # 기본 익절 비율 (8%)
    atr_stop_multiplier: float = 2.0     # ATR 손절 배수
    atr_profit_multiplier: float = 3.0   # ATR 익절 배수
    use_trailing_stop: bool = True       # 트레일링 스탑 사용


@dataclass
class BacktestConfig:
    """백테스트 설정"""
    # 기본 설정
    initial_capital: float = 100_000_000  # 초기 자본금 (1억원)
    start_date: Optional[date] = None
    end_date: Optional[date] = None

    # 포지션 설정
    position_size_method: PositionSizeMethod = PositionSizeMethod.PERCENT
    position_size_value: float = 0.05    # 포지션 크기 (5%)

    # 비용 설정
    commission: CommissionConfig = field(default_factory=CommissionConfig)
    slippage: SlippageConfig = field(default_factory=SlippageConfig)

    # 리스크 설정
    risk: RiskConfig = field(default_factory=RiskConfig)

    # 실행 설정
    warmup_period: int = 20              # 워밍업 기간 (바)
    data_frequency: str = "daily"        # 데이터 주기 ("daily", "hourly", "minute")
    allow_shorting: bool = False         # 공매도 허용
    allow_fractional: bool = False       # 소수점 주수 허용

    # 기타 설정
    random_seed: Optional[int] = None    # 랜덤 시드
    verbose: bool = True                 # 상세 로그
    name: str = "Backtest"               # 백테스트 이름

    def __post_init__(self):
        """설정 검증"""
        if self.initial_capital <= 0:
            raise ValueError("초기 자본금은 0보다 커야 합니다")
        if self.position_size_value <= 0 or self.position_size_value > 1:
            raise ValueError("포지션 크기 비율은 0~1 사이여야 합니다")
        if self.warmup_period < 0:
            raise ValueError("워밍업 기간은 0 이상이어야 합니다")

    def to_dict(self) -> Dict[str, Any]:
        """설정을 딕셔너리로 변환"""
        return {
            'initial_capital': self.initial_capital,
            'start_date': str(self.start_date) if self.start_date else None,
            'end_date': str(self.end_date) if self.end_date else None,
            'position_size_method': self.position_size_method.value,
            'position_size_value': self.position_size_value,
            'commission_buy_rate': self.commission.buy_rate,
            'commission_sell_rate': self.commission.sell_rate,
            'tax_rate': self.commission.tax_rate,
            'slippage': self.slippage.value,
            'max_drawdown': self.risk.max_drawdown,
            'max_positions': self.risk.max_positions,
            'stop_loss_pct': self.risk.stop_loss_pct,
            'take_profit_pct': self.risk.take_profit_pct,
            'use_dynamic_stops': self.risk.use_dynamic_stops,
            'name': self.name
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BacktestConfig':
        """딕셔너리에서 설정 생성"""
        commission = CommissionConfig(
            buy_rate=data.get('commission_buy_rate', 0.00015),
            sell_rate=data.get('commission_sell_rate', 0.00015),
            tax_rate=data.get('tax_rate', 0.0023)
        )
        slippage = SlippageConfig(
            value=data.get('slippage', 0.001)
        )
        risk = RiskConfig(
            max_drawdown=data.get('max_drawdown', 0.20),
            max_positions=data.get('max_positions', 10),
            stop_loss_pct=data.get('stop_loss_pct', 0.03),
            take_profit_pct=data.get('take_profit_pct', 0.08),
            use_dynamic_stops=data.get('use_dynamic_stops', True)
        )

        return cls(
            initial_capital=data.get('initial_capital', 100_000_000),
            start_date=date.fromisoformat(data['start_date']) if data.get('start_date') else None,
            end_date=date.fromisoformat(data['end_date']) if data.get('end_date') else None,
            position_size_method=PositionSizeMethod(data.get('position_size_method', 'percent')),
            position_size_value=data.get('position_size_value', 0.05),
            commission=commission,
            slippage=slippage,
            risk=risk,
            name=data.get('name', 'Backtest')
        )


# 사전 정의된 설정 프리셋
CONSERVATIVE_CONFIG = BacktestConfig(
    position_size_value=0.03,
    risk=RiskConfig(
        max_drawdown=0.10,
        max_positions=5,
        stop_loss_pct=0.02,
        take_profit_pct=0.05
    ),
    name="Conservative"
)

MODERATE_CONFIG = BacktestConfig(
    position_size_value=0.05,
    risk=RiskConfig(
        max_drawdown=0.15,
        max_positions=10,
        stop_loss_pct=0.03,
        take_profit_pct=0.08
    ),
    name="Moderate"
)

AGGRESSIVE_CONFIG = BacktestConfig(
    position_size_value=0.10,
    risk=RiskConfig(
        max_drawdown=0.25,
        max_positions=15,
        stop_loss_pct=0.05,
        take_profit_pct=0.15
    ),
    name="Aggressive"
)
