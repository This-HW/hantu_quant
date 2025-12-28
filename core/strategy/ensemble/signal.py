"""
신호 정의 모듈

거래 신호의 데이터 구조와 유형을 정의합니다.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from enum import Enum
from datetime import datetime


class SignalType(Enum):
    """신호 유형"""
    BUY = 1       # 매수
    SELL = -1     # 매도
    HOLD = 0      # 관망


class SignalSource(Enum):
    """신호 소스"""
    LSTM = "lstm"           # LSTM 딥러닝 예측
    TA = "ta"               # 기술적 분석
    SD = "sd"               # 수급 분석 (Supply-Demand)
    MTF = "mtf"             # 멀티타임프레임
    SECTOR = "sector"       # 섹터 분석


@dataclass
class Signal:
    """
    개별 전략 신호

    Attributes:
        signal_type: 신호 유형 (BUY/SELL/HOLD)
        source: 신호 발생 소스
        stock_code: 종목 코드
        strength: 신호 강도 (0.0 ~ 2.0, 1.0이 기준)
        confidence: 신뢰도 (0.0 ~ 1.0)
        price: 신호 발생 시점 가격
        timestamp: 신호 발생 시각
        reason: 신호 발생 이유
        stop_loss: 제안 손절가
        take_profit: 제안 익절가
        metadata: 추가 정보
    """
    signal_type: SignalType
    source: SignalSource
    stock_code: str
    strength: float = 1.0
    confidence: float = 0.5
    price: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    reason: str = ""
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """입력값 검증"""
        self.strength = max(0.0, min(2.0, self.strength))
        self.confidence = max(0.0, min(1.0, self.confidence))

    @property
    def is_actionable(self) -> bool:
        """실행 가능한 신호인지 확인"""
        return self.signal_type != SignalType.HOLD and self.confidence >= 0.5

    @property
    def weighted_score(self) -> float:
        """가중 점수 (강도 × 신뢰도)"""
        direction = 1 if self.signal_type == SignalType.BUY else -1
        if self.signal_type == SignalType.HOLD:
            return 0.0
        return direction * self.strength * self.confidence

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 변환"""
        return {
            'signal_type': self.signal_type.name,
            'source': self.source.value,
            'stock_code': self.stock_code,
            'strength': self.strength,
            'confidence': self.confidence,
            'price': self.price,
            'timestamp': self.timestamp.isoformat(),
            'reason': self.reason,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'metadata': self.metadata,
        }


@dataclass
class FinalSignal:
    """
    최종 앙상블 신호

    여러 전략의 신호를 집계한 최종 결정

    Attributes:
        action: 최종 액션 (BUY/SELL/HOLD)
        stock_code: 종목 코드
        confidence: 종합 신뢰도
        strength: 종합 강도 (포지션 크기 결정용, 1~3단계)
        agreement_count: 동의 전략 수
        sources: 동의한 전략 소스들
        reason: 종합 판단 근거
        individual_signals: 개별 신호들
        stop_loss: 제안 손절가
        take_profit: 제안 익절가
        position_size_multiplier: 포지션 크기 배수
        timestamp: 생성 시각
    """
    action: SignalType
    stock_code: str
    confidence: float = 0.0
    strength: int = 1  # 1, 2, 3 단계
    agreement_count: int = 0
    sources: List[SignalSource] = field(default_factory=list)
    reason: str = ""
    individual_signals: List[Signal] = field(default_factory=list)
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    position_size_multiplier: float = 1.0
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def is_actionable(self) -> bool:
        """실행 가능한 신호인지"""
        return self.action != SignalType.HOLD and self.confidence >= 0.6

    @property
    def risk_reward_ratio(self) -> Optional[float]:
        """손익비"""
        if self.stop_loss and self.take_profit and self.individual_signals:
            entry_price = self.individual_signals[0].price
            if entry_price > 0 and self.stop_loss > 0:
                risk = abs(entry_price - self.stop_loss)
                reward = abs(self.take_profit - entry_price)
                return reward / risk if risk > 0 else None
        return None

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 변환"""
        return {
            'action': self.action.name,
            'stock_code': self.stock_code,
            'confidence': self.confidence,
            'strength': self.strength,
            'agreement_count': self.agreement_count,
            'sources': [s.value for s in self.sources],
            'reason': self.reason,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'position_size_multiplier': self.position_size_multiplier,
            'risk_reward_ratio': self.risk_reward_ratio,
            'timestamp': self.timestamp.isoformat(),
        }

    def __str__(self) -> str:
        sources_str = ', '.join(s.value for s in self.sources)
        return (
            f"FinalSignal({self.stock_code}: {self.action.name}, "
            f"conf={self.confidence:.1%}, strength={self.strength}, "
            f"sources=[{sources_str}])"
        )
