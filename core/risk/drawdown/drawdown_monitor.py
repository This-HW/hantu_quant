"""
드로다운 모니터 모듈

포트폴리오 낙폭 추적 및 경고
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import deque
import logging

logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    """경고 수준"""
    NORMAL = "normal"
    CAUTION = "caution"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class DrawdownConfig:
    """드로다운 모니터 설정"""
    # 경고 임계값
    caution_threshold: float = 0.05  # 5%
    warning_threshold: float = 0.10  # 10%
    critical_threshold: float = 0.15  # 15%

    # 일간/주간/월간 한도
    daily_limit: float = 0.03  # 3%
    weekly_limit: float = 0.07  # 7%
    monthly_limit: float = 0.12  # 12%

    # 연속 손실 한도
    max_consecutive_losses: int = 5

    # 히스토리 크기
    history_days: int = 252


@dataclass
class DrawdownStatus:
    """드로다운 상태"""
    current_drawdown: float = 0.0
    max_drawdown: float = 0.0
    peak_value: float = 0.0
    current_value: float = 0.0

    daily_drawdown: float = 0.0
    weekly_drawdown: float = 0.0
    monthly_drawdown: float = 0.0

    consecutive_loss_days: int = 0
    days_since_peak: int = 0

    alert_level: AlertLevel = AlertLevel.NORMAL
    alerts: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            'current_drawdown': self.current_drawdown,
            'max_drawdown': self.max_drawdown,
            'peak_value': self.peak_value,
            'current_value': self.current_value,
            'daily_drawdown': self.daily_drawdown,
            'weekly_drawdown': self.weekly_drawdown,
            'monthly_drawdown': self.monthly_drawdown,
            'consecutive_loss_days': self.consecutive_loss_days,
            'days_since_peak': self.days_since_peak,
            'alert_level': self.alert_level.value,
            'alerts': self.alerts,
        }


class DrawdownMonitor:
    """
    드로다운 모니터

    포트폴리오 가치 변동을 추적하고
    드로다운 상황을 모니터링합니다.
    """

    def __init__(self, config: Optional[DrawdownConfig] = None):
        self.config = config or DrawdownConfig()

        # 가치 히스토리
        self._value_history: deque = deque(maxlen=self.config.history_days)
        self._daily_returns: deque = deque(maxlen=self.config.history_days)

        # 상태
        self._peak_value: float = 0.0
        self._peak_date: Optional[datetime] = None
        self._max_drawdown: float = 0.0
        self._consecutive_losses: int = 0

    def update(
        self,
        portfolio_value: float,
        timestamp: Optional[datetime] = None
    ) -> DrawdownStatus:
        """
        포트폴리오 가치 업데이트

        Args:
            portfolio_value: 현재 포트폴리오 가치
            timestamp: 타임스탬프

        Returns:
            DrawdownStatus: 현재 드로다운 상태
        """
        timestamp = timestamp or datetime.now()

        # 일간 수익률 계산
        daily_return = 0.0
        if self._value_history:
            prev_value = self._value_history[-1]['value']
            if prev_value > 0:
                daily_return = (portfolio_value - prev_value) / prev_value

        # 히스토리 추가
        self._value_history.append({
            'timestamp': timestamp,
            'value': portfolio_value
        })
        self._daily_returns.append(daily_return)

        # 피크 업데이트
        if portfolio_value > self._peak_value:
            self._peak_value = portfolio_value
            self._peak_date = timestamp
            self._consecutive_losses = 0
        elif daily_return < 0:
            self._consecutive_losses += 1
        else:
            self._consecutive_losses = 0

        # 드로다운 계산
        current_dd = self._calculate_drawdown(portfolio_value)

        # 최대 드로다운 업데이트
        if current_dd > self._max_drawdown:
            self._max_drawdown = current_dd

        # 기간별 드로다운
        daily_dd = self._calculate_period_drawdown(1)
        weekly_dd = self._calculate_period_drawdown(5)
        monthly_dd = self._calculate_period_drawdown(21)

        # 피크 이후 일수
        days_since_peak = 0
        if self._peak_date:
            days_since_peak = (timestamp - self._peak_date).days

        # 경고 수준 및 알림
        alert_level, alerts = self._evaluate_alerts(
            current_dd, daily_dd, weekly_dd, monthly_dd
        )

        return DrawdownStatus(
            current_drawdown=current_dd,
            max_drawdown=self._max_drawdown,
            peak_value=self._peak_value,
            current_value=portfolio_value,
            daily_drawdown=daily_dd,
            weekly_drawdown=weekly_dd,
            monthly_drawdown=monthly_dd,
            consecutive_loss_days=self._consecutive_losses,
            days_since_peak=days_since_peak,
            alert_level=alert_level,
            alerts=alerts
        )

    def _calculate_drawdown(self, current_value: float) -> float:
        """현재 드로다운 계산"""
        if self._peak_value <= 0:
            return 0.0
        return (self._peak_value - current_value) / self._peak_value

    def _calculate_period_drawdown(self, days: int) -> float:
        """기간별 드로다운 계산"""
        if len(self._value_history) < days + 1:
            return 0.0

        start_value = self._value_history[-days - 1]['value']
        end_value = self._value_history[-1]['value']

        if start_value <= 0:
            return 0.0

        return max(0, (start_value - end_value) / start_value)

    def _evaluate_alerts(
        self,
        current_dd: float,
        daily_dd: float,
        weekly_dd: float,
        monthly_dd: float
    ) -> Tuple[AlertLevel, List[str]]:
        """경고 평가"""
        alerts = []
        alert_level = AlertLevel.NORMAL

        # 현재 드로다운 체크
        if current_dd >= self.config.critical_threshold:
            alert_level = AlertLevel.CRITICAL
            alerts.append(f"치명적 낙폭: {current_dd:.1%}")
        elif current_dd >= self.config.warning_threshold:
            if alert_level.value < AlertLevel.WARNING.value:
                alert_level = AlertLevel.WARNING
            alerts.append(f"경고 낙폭: {current_dd:.1%}")
        elif current_dd >= self.config.caution_threshold:
            if alert_level.value < AlertLevel.CAUTION.value:
                alert_level = AlertLevel.CAUTION
            alerts.append(f"주의 낙폭: {current_dd:.1%}")

        # 일간 한도 체크
        if daily_dd >= self.config.daily_limit:
            if alert_level.value < AlertLevel.WARNING.value:
                alert_level = AlertLevel.WARNING
            alerts.append(f"일간 한도 초과: {daily_dd:.1%}")

        # 주간 한도 체크
        if weekly_dd >= self.config.weekly_limit:
            if alert_level.value < AlertLevel.WARNING.value:
                alert_level = AlertLevel.WARNING
            alerts.append(f"주간 한도 초과: {weekly_dd:.1%}")

        # 월간 한도 체크
        if monthly_dd >= self.config.monthly_limit:
            if alert_level.value < AlertLevel.CRITICAL.value:
                alert_level = AlertLevel.CRITICAL
            alerts.append(f"월간 한도 초과: {monthly_dd:.1%}")

        # 연속 손실 체크
        if self._consecutive_losses >= self.config.max_consecutive_losses:
            if alert_level.value < AlertLevel.WARNING.value:
                alert_level = AlertLevel.WARNING
            alerts.append(f"연속 손실: {self._consecutive_losses}일")

        return alert_level, alerts

    def get_drawdown_history(self) -> pd.DataFrame:
        """드로다운 히스토리 반환"""
        if not self._value_history:
            return pd.DataFrame()

        data = []
        peak = 0

        for record in self._value_history:
            value = record['value']
            peak = max(peak, value)
            dd = (peak - value) / peak if peak > 0 else 0

            data.append({
                'timestamp': record['timestamp'],
                'value': value,
                'peak': peak,
                'drawdown': dd
            })

        return pd.DataFrame(data)

    def get_recovery_estimate(self, current_value: float) -> Dict:
        """회복 예상 정보"""
        if current_value >= self._peak_value:
            return {
                'status': '피크 상태',
                'recovery_needed': 0.0,
                'estimated_days': 0
            }

        recovery_needed = (self._peak_value - current_value) / current_value

        # 평균 일간 수익률 기반 예상
        if self._daily_returns:
            avg_return = np.mean([r for r in self._daily_returns if r > 0])
            if avg_return > 0:
                estimated_days = int(np.log(1 + recovery_needed) / np.log(1 + avg_return))
            else:
                estimated_days = None
        else:
            estimated_days = None

        return {
            'status': '회복 중',
            'recovery_needed': recovery_needed,
            'estimated_days': estimated_days,
            'peak_value': self._peak_value,
            'current_value': current_value
        }

    def reset(self, initial_value: float = 0.0):
        """모니터 리셋"""
        self._value_history.clear()
        self._daily_returns.clear()
        self._peak_value = initial_value
        self._peak_date = None
        self._max_drawdown = 0.0
        self._consecutive_losses = 0

        if initial_value > 0:
            self.update(initial_value)
