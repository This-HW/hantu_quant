"""
서킷브레이커 모듈

거래 중단 조건 관리
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import logging

from .drawdown_monitor import DrawdownStatus, AlertLevel

logger = logging.getLogger(__name__)


class BreakerState(Enum):
    """브레이커 상태"""
    ACTIVE = "active"  # 정상 거래
    TRIGGERED = "triggered"  # 발동
    COOLDOWN = "cooldown"  # 쿨다운 중


@dataclass
class BreakerConfig:
    """서킷브레이커 설정"""
    # 발동 조건
    max_daily_loss: float = 0.03  # 3%
    max_weekly_loss: float = 0.07  # 7%
    max_drawdown: float = 0.15  # 15%

    # 쿨다운 기간
    cooldown_hours: int = 24

    # 단계별 조치
    stage1_reduction: float = 0.50  # 50% 감소
    stage2_reduction: float = 0.75  # 75% 감소
    stage3_halt: bool = True  # 거래 중단

    # 자동 해제 조건
    auto_release_profit: float = 0.02  # 2% 수익 시


@dataclass
class BreakerStatus:
    """브레이커 상태"""
    state: BreakerState = BreakerState.ACTIVE
    trigger_reason: str = ""
    triggered_at: Optional[datetime] = None
    cooldown_until: Optional[datetime] = None
    current_stage: int = 0  # 0: 정상, 1-3: 단계
    position_reduction: float = 0.0  # 포지션 축소 비율
    can_trade: bool = True
    next_check: Optional[datetime] = None

    def to_dict(self) -> Dict:
        return {
            'state': self.state.value,
            'trigger_reason': self.trigger_reason,
            'triggered_at': self.triggered_at.isoformat() if self.triggered_at else None,
            'cooldown_until': self.cooldown_until.isoformat() if self.cooldown_until else None,
            'current_stage': self.current_stage,
            'position_reduction': self.position_reduction,
            'can_trade': self.can_trade,
        }


class CircuitBreaker:
    """
    서킷브레이커

    과도한 손실 발생 시 자동으로 거래를 제한합니다.
    """

    def __init__(self, config: Optional[BreakerConfig] = None):
        self.config = config or BreakerConfig()

        # 상태
        self._state = BreakerState.ACTIVE
        self._trigger_reason = ""
        self._triggered_at: Optional[datetime] = None
        self._cooldown_until: Optional[datetime] = None
        self._current_stage = 0
        self._trigger_history: List[Dict] = []

    @property
    def is_active(self) -> bool:
        """정상 거래 가능 여부"""
        return self._state == BreakerState.ACTIVE

    @property
    def can_trade(self) -> bool:
        """거래 가능 여부"""
        if self._state == BreakerState.TRIGGERED and self._current_stage >= 3:
            return False
        if self._state == BreakerState.COOLDOWN:
            return self._check_cooldown_expired()
        return True

    def check(self, drawdown_status: DrawdownStatus) -> BreakerStatus:
        """
        서킷브레이커 체크

        Args:
            drawdown_status: 드로다운 상태

        Returns:
            BreakerStatus: 브레이커 상태
        """
        now = datetime.now()

        # 쿨다운 체크
        if self._state == BreakerState.COOLDOWN:
            if self._check_cooldown_expired():
                self._release_breaker("쿨다운 완료")

        # 자동 해제 체크 (수익 발생 시)
        if self._state == BreakerState.TRIGGERED:
            if drawdown_status.daily_drawdown < -self.config.auto_release_profit:
                self._release_breaker("수익 회복")

        # 발동 조건 체크
        if self._state == BreakerState.ACTIVE:
            self._check_trigger_conditions(drawdown_status, now)

        return self._get_status()

    def _check_trigger_conditions(
        self,
        status: DrawdownStatus,
        now: datetime
    ):
        """발동 조건 체크"""
        trigger_reason = None
        stage = 0

        # Stage 1: 일간 한도 초과
        if status.daily_drawdown >= self.config.max_daily_loss:
            trigger_reason = f"일간 손실 {status.daily_drawdown:.1%} (한도: {self.config.max_daily_loss:.1%})"
            stage = 1

        # Stage 2: 주간 한도 초과
        if status.weekly_drawdown >= self.config.max_weekly_loss:
            trigger_reason = f"주간 손실 {status.weekly_drawdown:.1%} (한도: {self.config.max_weekly_loss:.1%})"
            stage = 2

        # Stage 3: 최대 낙폭 초과
        if status.current_drawdown >= self.config.max_drawdown:
            trigger_reason = f"최대 낙폭 {status.current_drawdown:.1%} (한도: {self.config.max_drawdown:.1%})"
            stage = 3

        # 경고 수준에 따른 추가 체크
        if status.alert_level == AlertLevel.CRITICAL and stage < 2:
            trigger_reason = f"치명적 경고 (낙폭: {status.current_drawdown:.1%})"
            stage = max(stage, 2)

        if trigger_reason:
            self._trigger_breaker(trigger_reason, stage, now)

    def _trigger_breaker(self, reason: str, stage: int, now: datetime):
        """브레이커 발동"""
        self._state = BreakerState.TRIGGERED
        self._trigger_reason = reason
        self._triggered_at = now
        self._current_stage = stage

        # 쿨다운 설정
        self._cooldown_until = now + timedelta(hours=self.config.cooldown_hours)

        # 히스토리 기록
        self._trigger_history.append({
            'timestamp': now,
            'reason': reason,
            'stage': stage
        })

        logger.warning(f"서킷브레이커 발동: {reason} (Stage {stage})")

    def _release_breaker(self, reason: str):
        """브레이커 해제"""
        logger.info(f"서킷브레이커 해제: {reason}")

        self._state = BreakerState.ACTIVE
        self._trigger_reason = ""
        self._triggered_at = None
        self._cooldown_until = None
        self._current_stage = 0

    def _check_cooldown_expired(self) -> bool:
        """쿨다운 만료 체크"""
        if self._cooldown_until is None:
            return True
        return datetime.now() >= self._cooldown_until

    def _get_status(self) -> BreakerStatus:
        """현재 상태 반환"""
        position_reduction = 0.0
        if self._current_stage == 1:
            position_reduction = self.config.stage1_reduction
        elif self._current_stage == 2:
            position_reduction = self.config.stage2_reduction
        elif self._current_stage >= 3:
            position_reduction = 1.0  # 전체 청산

        return BreakerStatus(
            state=self._state,
            trigger_reason=self._trigger_reason,
            triggered_at=self._triggered_at,
            cooldown_until=self._cooldown_until,
            current_stage=self._current_stage,
            position_reduction=position_reduction,
            can_trade=self.can_trade,
            next_check=self._cooldown_until
        )

    def force_trigger(self, reason: str = "수동 발동", stage: int = 3):
        """강제 발동"""
        self._trigger_breaker(reason, stage, datetime.now())

    def force_release(self, reason: str = "수동 해제"):
        """강제 해제"""
        self._release_breaker(reason)

    def get_trigger_history(self, limit: int = 10) -> List[Dict]:
        """발동 히스토리"""
        return self._trigger_history[-limit:]

    def get_recommended_action(self) -> Dict:
        """권장 조치"""
        if self._state == BreakerState.ACTIVE:
            return {
                'action': 'NORMAL',
                'description': '정상 거래 가능',
                'position_limit': 1.0
            }

        if self._current_stage == 1:
            return {
                'action': 'REDUCE',
                'description': f'신규 포지션 {self.config.stage1_reduction:.0%} 축소',
                'position_limit': 1 - self.config.stage1_reduction
            }
        elif self._current_stage == 2:
            return {
                'action': 'REDUCE',
                'description': f'신규 포지션 {self.config.stage2_reduction:.0%} 축소',
                'position_limit': 1 - self.config.stage2_reduction
            }
        else:
            return {
                'action': 'HALT',
                'description': '거래 중단 - 모든 신규 포지션 금지',
                'position_limit': 0.0
            }
