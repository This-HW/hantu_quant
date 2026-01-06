"""
알림 관리자 모듈

여러 알림 채널을 통합 관리하고 중복/과다 알림을 방지합니다.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from collections import defaultdict
import hashlib
import threading

from .alert import Alert, AlertType, AlertLevel, AlertFormatter
from .notifier import BaseNotifier, NotificationResult
from .telegram_bot import TelegramNotifier, TelegramConfig

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """레이트 리밋 설정"""
    # 동일 알림 중복 방지
    dedup_window_seconds: int = 300  # 5분

    # 시간당 최대 알림 수
    max_per_hour: int = 60

    # 분당 최대 알림 수
    max_per_minute: int = 10

    # 종목당 시간당 최대 알림 수
    max_per_stock_per_hour: int = 10

    # 유형별 쿨다운 (초)
    type_cooldown: Dict[AlertType, int] = field(default_factory=lambda: {
        AlertType.SIGNAL_BUY: 60,
        AlertType.SIGNAL_SELL: 60,
        AlertType.DRAWDOWN_WARNING: 300,
    })


@dataclass
class AlertHistory:
    """알림 이력"""
    alert_hash: str
    alert_type: AlertType
    stock_code: Optional[str]
    timestamp: datetime
    sent: bool


class NotificationManager:
    """
    알림 관리자

    여러 알림 채널을 통합 관리하고 중복/과다 알림을 방지합니다.
    """

    def __init__(
        self,
        rate_limit_config: Optional[RateLimitConfig] = None
    ):
        """
        Args:
            rate_limit_config: 레이트 리밋 설정
        """
        self.rate_config = rate_limit_config or RateLimitConfig()

        # 알림 발송기
        self._notifiers: Dict[str, BaseNotifier] = {}

        # 알림 이력 (중복 방지용)
        self._history: List[AlertHistory] = []
        self._sent_hashes: Set[str] = set()

        # 통계
        self._sent_count: int = 0
        self._filtered_count: int = 0
        self._error_count: int = 0

        # 락
        self._lock = threading.Lock()

    def register_notifier(
        self,
        name: str,
        notifier: BaseNotifier
    ) -> None:
        """
        알림 발송기 등록

        Args:
            name: 발송기 이름
            notifier: 발송기 객체
        """
        with self._lock:
            self._notifiers[name] = notifier
            logger.info(f"Notifier registered: {name}")

    def register_telegram(
        self,
        bot_token: str,
        chat_id: str,
        **kwargs
    ) -> TelegramNotifier:
        """
        텔레그램 발송기 등록

        Args:
            bot_token: 봇 토큰
            chat_id: 채팅 ID
            **kwargs: 추가 설정

        Returns:
            TelegramNotifier: 등록된 발송기
        """
        config = TelegramConfig(
            bot_token=bot_token,
            chat_id=chat_id,
            **kwargs
        )
        notifier = TelegramNotifier(config)

        self.register_notifier('telegram', notifier)
        return notifier

    def unregister_notifier(self, name: str) -> bool:
        """발송기 해제"""
        with self._lock:
            if name in self._notifiers:
                del self._notifiers[name]
                return True
        return False

    def send_alert(
        self,
        alert: Alert,
        channels: Optional[List[str]] = None
    ) -> Dict[str, NotificationResult]:
        """
        알림 발송

        Args:
            alert: 알림 객체
            channels: 발송 채널 (None이면 모든 채널)

        Returns:
            Dict[str, NotificationResult]: 채널별 발송 결과
        """
        results = {}

        # 레이트 리밋 체크
        if not self._check_rate_limit(alert):
            self._filtered_count += 1
            logger.debug(f"Alert rate limited: {alert.alert_type.value}")
            return {'_rate_limited': NotificationResult(
                success=False,
                alert_id=str(id(alert)),
                error="Rate limited",
            )}

        # 중복 체크
        if self._is_duplicate(alert):
            self._filtered_count += 1
            logger.debug(f"Alert deduplicated: {alert.alert_type.value}")
            return {'_duplicate': NotificationResult(
                success=False,
                alert_id=str(id(alert)),
                error="Duplicate alert",
            )}

        # 발송
        with self._lock:
            target_channels = channels or list(self._notifiers.keys())

            for channel_name in target_channels:
                if channel_name not in self._notifiers:
                    continue

                notifier = self._notifiers[channel_name]

                try:
                    result = notifier.send(alert)
                    results[channel_name] = result

                    if result.success:
                        self._sent_count += 1
                    else:
                        self._error_count += 1

                except Exception as e:
                    self._error_count += 1
                    results[channel_name] = NotificationResult(
                        success=False,
                        alert_id=str(id(alert)),
                        error=str(e),
                    )
                    logger.error(f"Send error on {channel_name}: {e}", exc_info=True)

        # 이력 기록
        self._record_history(alert, any(r.success for r in results.values()))

        return results

    def send_raw(
        self,
        message: str,
        channels: Optional[List[str]] = None
    ) -> Dict[str, NotificationResult]:
        """
        원시 메시지 발송

        Args:
            message: 메시지
            channels: 발송 채널

        Returns:
            Dict[str, NotificationResult]: 채널별 발송 결과
        """
        results = {}

        with self._lock:
            target_channels = channels or list(self._notifiers.keys())

            for channel_name in target_channels:
                if channel_name not in self._notifiers:
                    continue

                notifier = self._notifiers[channel_name]

                try:
                    result = notifier.send_raw(message)
                    results[channel_name] = result

                except Exception as e:
                    results[channel_name] = NotificationResult(
                        success=False,
                        alert_id="raw",
                        error=str(e),
                    )

        return results

    def _check_rate_limit(self, alert: Alert) -> bool:
        """레이트 리밋 체크"""
        now = datetime.now()

        # 최근 이력 정리 (1시간 이전 삭제)
        cutoff = now - timedelta(hours=1)
        self._history = [h for h in self._history if h.timestamp >= cutoff]

        # 시간당 최대 체크
        hour_count = sum(1 for h in self._history if h.sent)
        if hour_count >= self.rate_config.max_per_hour:
            return False

        # 분당 최대 체크
        minute_cutoff = now - timedelta(minutes=1)
        minute_count = sum(
            1 for h in self._history
            if h.sent and h.timestamp >= minute_cutoff
        )
        if minute_count >= self.rate_config.max_per_minute:
            return False

        # 종목별 시간당 체크
        if alert.stock_code:
            stock_count = sum(
                1 for h in self._history
                if h.sent and h.stock_code == alert.stock_code
            )
            if stock_count >= self.rate_config.max_per_stock_per_hour:
                return False

        # 유형별 쿨다운 체크
        cooldown = self.rate_config.type_cooldown.get(alert.alert_type, 0)
        if cooldown > 0:
            cooldown_cutoff = now - timedelta(seconds=cooldown)
            recent_same_type = [
                h for h in self._history
                if h.sent and
                h.alert_type == alert.alert_type and
                h.timestamp >= cooldown_cutoff
            ]
            if recent_same_type:
                return False

        return True

    def _is_duplicate(self, alert: Alert) -> bool:
        """중복 알림 체크"""
        alert_hash = self._compute_hash(alert)

        # 해시가 최근 발송된 것과 동일하면 중복
        if alert_hash in self._sent_hashes:
            return True

        return False

    def _compute_hash(self, alert: Alert) -> str:
        """알림 해시 계산"""
        # 핵심 정보만 사용하여 해시 생성
        key = f"{alert.alert_type.value}:{alert.stock_code}:{alert.title}"
        return hashlib.md5(key.encode()).hexdigest()

    def _record_history(self, alert: Alert, sent: bool) -> None:
        """이력 기록"""
        alert_hash = self._compute_hash(alert)

        history = AlertHistory(
            alert_hash=alert_hash,
            alert_type=alert.alert_type,
            stock_code=alert.stock_code,
            timestamp=datetime.now(),
            sent=sent,
        )

        self._history.append(history)

        if sent:
            self._sent_hashes.add(alert_hash)

            # 중복 해시는 dedup_window 후 삭제
            def remove_hash():
                import time
                time.sleep(self.rate_config.dedup_window_seconds)
                self._sent_hashes.discard(alert_hash)

            thread = threading.Thread(target=remove_hash, daemon=True)
            thread.start()

    # 편의 메서드

    def notify_trade_entry(
        self,
        stock_code: str,
        stock_name: str,
        direction: str,
        price: float,
        quantity: int,
        signal_source: List[str],
        confidence: float
    ) -> Dict[str, NotificationResult]:
        """거래 진입 알림"""
        alert = AlertFormatter.format_trade_entry(
            stock_code=stock_code,
            stock_name=stock_name,
            direction=direction,
            price=price,
            quantity=quantity,
            signal_source=signal_source,
            confidence=confidence,
        )
        return self.send_alert(alert)

    def notify_trade_exit(
        self,
        stock_code: str,
        stock_name: str,
        exit_reason: str,
        entry_price: float,
        exit_price: float,
        pnl: float,
        pnl_pct: float,
        holding_days: int
    ) -> Dict[str, NotificationResult]:
        """거래 청산 알림"""
        alert = AlertFormatter.format_trade_exit(
            stock_code=stock_code,
            stock_name=stock_name,
            exit_reason=exit_reason,
            entry_price=entry_price,
            exit_price=exit_price,
            pnl=pnl,
            pnl_pct=pnl_pct,
            holding_days=holding_days,
        )
        return self.send_alert(alert)

    def notify_drawdown(
        self,
        current_drawdown: float,
        max_drawdown: float,
        alert_level: str
    ) -> Dict[str, NotificationResult]:
        """드로우다운 알림"""
        alert = AlertFormatter.format_drawdown_alert(
            current_drawdown=current_drawdown,
            max_drawdown=max_drawdown,
            alert_level=alert_level,
        )
        return self.send_alert(alert)

    def notify_daily_summary(
        self,
        date: datetime,
        total_trades: int,
        win_rate: float,
        total_pnl: float,
        total_pnl_pct: float,
        top_winners: List[Dict],
        top_losers: List[Dict]
    ) -> Dict[str, NotificationResult]:
        """일일 요약 알림"""
        alert = AlertFormatter.format_daily_summary(
            date=date,
            total_trades=total_trades,
            win_rate=win_rate,
            total_pnl=total_pnl,
            total_pnl_pct=total_pnl_pct,
            top_winners=top_winners,
            top_losers=top_losers,
        )
        return self.send_alert(alert)

    def notify_circuit_breaker(
        self,
        reason: str,
        triggered_at: datetime,
        cooldown_until: Optional[datetime] = None
    ) -> Dict[str, NotificationResult]:
        """서킷 브레이커 알림"""
        alert = AlertFormatter.format_circuit_breaker(
            reason=reason,
            triggered_at=triggered_at,
            cooldown_until=cooldown_until,
        )
        return self.send_alert(alert)

    def notify_signal(
        self,
        stock_code: str,
        stock_name: str,
        signal_type: str,
        strength: float,
        sources: List[str],
        recommendation: str
    ) -> Dict[str, NotificationResult]:
        """매매 신호 알림"""
        alert = AlertFormatter.format_signal(
            stock_code=stock_code,
            stock_name=stock_name,
            signal_type=signal_type,
            strength=strength,
            sources=sources,
            recommendation=recommendation,
        )
        return self.send_alert(alert)

    def notify_system(
        self,
        status: str,
        message: str,
        details: Optional[Dict] = None
    ) -> Dict[str, NotificationResult]:
        """시스템 상태 알림"""
        alert = AlertFormatter.format_system_status(
            status=status,
            message=message,
            details=details,
        )
        return self.send_alert(alert)

    def get_stats(self) -> Dict[str, Any]:
        """통계 조회"""
        with self._lock:
            notifier_stats = {
                name: notifier.get_stats()
                for name, notifier in self._notifiers.items()
            }

        return {
            'sent_count': self._sent_count,
            'filtered_count': self._filtered_count,
            'error_count': self._error_count,
            'notifiers': notifier_stats,
            'history_size': len(self._history),
            'rate_config': {
                'max_per_hour': self.rate_config.max_per_hour,
                'max_per_minute': self.rate_config.max_per_minute,
                'dedup_window': self.rate_config.dedup_window_seconds,
            },
        }

    def test_all_channels(self) -> Dict[str, Any]:
        """모든 채널 테스트"""
        results = {}

        for name, notifier in self._notifiers.items():
            if hasattr(notifier, 'test_connection'):
                results[name] = notifier.test_connection()
            else:
                results[name] = {'success': True, 'message': 'No test available'}

        return results
