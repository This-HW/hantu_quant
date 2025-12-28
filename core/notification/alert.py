"""
알림 정의 모듈

알림 유형, 레벨, 포맷팅을 정의합니다.
"""

import logging
from datetime import datetime
from typing import Dict, Optional, Any, List
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class AlertType(Enum):
    """알림 유형"""
    # 거래 관련
    TRADE_ENTRY = "trade_entry"          # 매수/매도 진입
    TRADE_EXIT = "trade_exit"            # 청산
    STOP_LOSS = "stop_loss"              # 손절
    TAKE_PROFIT = "take_profit"          # 익절

    # 신호 관련
    SIGNAL_BUY = "signal_buy"            # 매수 신호
    SIGNAL_SELL = "signal_sell"          # 매도 신호
    SIGNAL_STRONG = "signal_strong"      # 강한 신호

    # 리스크 관련
    DRAWDOWN_WARNING = "drawdown_warning"  # 드로우다운 경고
    DRAWDOWN_CRITICAL = "drawdown_critical"  # 드로우다운 위험
    CIRCUIT_BREAKER = "circuit_breaker"  # 서킷 브레이커
    POSITION_LIMIT = "position_limit"    # 포지션 한도

    # 시스템 관련
    SYSTEM_START = "system_start"        # 시스템 시작
    SYSTEM_STOP = "system_stop"          # 시스템 중지
    SYSTEM_ERROR = "system_error"        # 시스템 오류
    SYSTEM_WARNING = "system_warning"    # 시스템 경고

    # 성과 관련
    DAILY_SUMMARY = "daily_summary"      # 일일 요약
    WEEKLY_SUMMARY = "weekly_summary"    # 주간 요약
    PERFORMANCE_ALERT = "performance"    # 성과 알림

    # 학습 관련
    MODEL_RETRAIN = "model_retrain"      # 모델 재학습
    WEIGHT_UPDATE = "weight_update"      # 가중치 업데이트

    # 시장 관련
    MARKET_OPEN = "market_open"          # 시장 개장
    MARKET_CLOSE = "market_close"        # 시장 마감
    REGIME_CHANGE = "regime_change"      # 레짐 변화


class AlertLevel(Enum):
    """알림 레벨"""
    DEBUG = 0      # 디버그 (개발용)
    INFO = 1       # 정보
    WARNING = 2    # 경고
    CRITICAL = 3   # 위험
    EMERGENCY = 4  # 긴급


@dataclass
class Alert:
    """알림 객체"""
    alert_type: AlertType
    level: AlertLevel
    title: str
    message: str
    timestamp: datetime = field(default_factory=datetime.now)

    # 추가 데이터
    data: Dict[str, Any] = field(default_factory=dict)
    stock_code: Optional[str] = None
    stock_name: Optional[str] = None

    # 메타데이터
    source: str = "system"
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            'alert_type': self.alert_type.value,
            'level': self.level.value,
            'title': self.title,
            'message': self.message,
            'timestamp': self.timestamp.isoformat(),
            'data': self.data,
            'stock_code': self.stock_code,
            'stock_name': self.stock_name,
            'source': self.source,
            'tags': self.tags,
        }


class AlertFormatter:
    """
    알림 포매터

    알림을 텔레그램 메시지 형식으로 변환합니다.
    """

    # 레벨별 이모지
    LEVEL_EMOJI = {
        AlertLevel.DEBUG: "🔧",
        AlertLevel.INFO: "ℹ️",
        AlertLevel.WARNING: "⚠️",
        AlertLevel.CRITICAL: "🚨",
        AlertLevel.EMERGENCY: "🆘",
    }

    # 유형별 이모지
    TYPE_EMOJI = {
        AlertType.TRADE_ENTRY: "📈",
        AlertType.TRADE_EXIT: "📉",
        AlertType.STOP_LOSS: "🛑",
        AlertType.TAKE_PROFIT: "💰",
        AlertType.SIGNAL_BUY: "🟢",
        AlertType.SIGNAL_SELL: "🔴",
        AlertType.SIGNAL_STRONG: "💪",
        AlertType.DRAWDOWN_WARNING: "⚠️",
        AlertType.DRAWDOWN_CRITICAL: "🚨",
        AlertType.CIRCUIT_BREAKER: "⛔",
        AlertType.POSITION_LIMIT: "🚫",
        AlertType.SYSTEM_START: "🚀",
        AlertType.SYSTEM_STOP: "🛑",
        AlertType.SYSTEM_ERROR: "❌",
        AlertType.SYSTEM_WARNING: "⚠️",
        AlertType.DAILY_SUMMARY: "📊",
        AlertType.WEEKLY_SUMMARY: "📈",
        AlertType.PERFORMANCE_ALERT: "📉",
        AlertType.MODEL_RETRAIN: "🤖",
        AlertType.WEIGHT_UPDATE: "⚖️",
        AlertType.MARKET_OPEN: "🔔",
        AlertType.MARKET_CLOSE: "🔕",
        AlertType.REGIME_CHANGE: "🔄",
    }

    @classmethod
    def format_telegram(cls, alert: Alert) -> str:
        """
        텔레그램 메시지 형식으로 변환

        Args:
            alert: 알림 객체

        Returns:
            str: 포맷된 메시지
        """
        level_emoji = cls.LEVEL_EMOJI.get(alert.level, "📌")
        type_emoji = cls.TYPE_EMOJI.get(alert.alert_type, "📌")

        lines = [
            f"{level_emoji} {type_emoji} <b>{alert.title}</b>",
            "",
        ]

        # 종목 정보
        if alert.stock_code:
            stock_info = f"[{alert.stock_code}]"
            if alert.stock_name:
                stock_info += f" {alert.stock_name}"
            lines.append(f"📌 {stock_info}")

        # 메시지
        lines.append(alert.message)

        # 추가 데이터
        if alert.data:
            lines.append("")
            for key, value in alert.data.items():
                if isinstance(value, float):
                    if 'pct' in key.lower() or 'rate' in key.lower():
                        formatted = f"{value:.2%}"
                    elif 'price' in key.lower():
                        formatted = f"{value:,.0f}원"
                    else:
                        formatted = f"{value:.2f}"
                else:
                    formatted = str(value)
                lines.append(f"• {key}: {formatted}")

        # 타임스탬프
        lines.append("")
        lines.append(f"🕐 {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")

        return "\n".join(lines)

    @classmethod
    def format_trade_entry(
        cls,
        stock_code: str,
        stock_name: str,
        direction: str,
        price: float,
        quantity: int,
        signal_source: List[str],
        confidence: float
    ) -> Alert:
        """
        거래 진입 알림 생성

        Args:
            stock_code: 종목 코드
            stock_name: 종목명
            direction: 방향 (buy/sell)
            price: 가격
            quantity: 수량
            signal_source: 신호 소스
            confidence: 신뢰도

        Returns:
            Alert: 알림 객체
        """
        action = "매수" if direction == "buy" else "매도"
        title = f"{action} 진입"

        return Alert(
            alert_type=AlertType.TRADE_ENTRY,
            level=AlertLevel.INFO,
            title=title,
            message=f"{stock_name} {action} 진입",
            stock_code=stock_code,
            stock_name=stock_name,
            data={
                '가격': price,
                '수량': quantity,
                '신호소스': ", ".join(signal_source),
                '신뢰도': confidence,
            },
            tags=['trade', direction],
        )

    @classmethod
    def format_trade_exit(
        cls,
        stock_code: str,
        stock_name: str,
        exit_reason: str,
        entry_price: float,
        exit_price: float,
        pnl: float,
        pnl_pct: float,
        holding_days: int
    ) -> Alert:
        """
        거래 청산 알림 생성
        """
        is_profit = pnl > 0
        title = "익절 청산" if exit_reason == "take_profit" else \
                "손절 청산" if exit_reason == "stop_loss" else \
                "청산"

        alert_type = AlertType.TAKE_PROFIT if exit_reason == "take_profit" else \
                     AlertType.STOP_LOSS if exit_reason == "stop_loss" else \
                     AlertType.TRADE_EXIT

        level = AlertLevel.INFO if is_profit else AlertLevel.WARNING

        return Alert(
            alert_type=alert_type,
            level=level,
            title=title,
            message=f"{stock_name} {'수익' if is_profit else '손실'} 청산",
            stock_code=stock_code,
            stock_name=stock_name,
            data={
                '진입가': entry_price,
                '청산가': exit_price,
                '손익': pnl,
                '수익률': pnl_pct / 100,  # % 표시용
                '보유일': holding_days,
                '청산사유': exit_reason,
            },
            tags=['trade', 'exit', 'profit' if is_profit else 'loss'],
        )

    @classmethod
    def format_drawdown_alert(
        cls,
        current_drawdown: float,
        max_drawdown: float,
        alert_level: str
    ) -> Alert:
        """
        드로우다운 알림 생성
        """
        if alert_level == "critical":
            alert_type = AlertType.DRAWDOWN_CRITICAL
            level = AlertLevel.CRITICAL
            title = "드로우다운 위험"
        else:
            alert_type = AlertType.DRAWDOWN_WARNING
            level = AlertLevel.WARNING
            title = "드로우다운 경고"

        return Alert(
            alert_type=alert_type,
            level=level,
            title=title,
            message=f"현재 드로우다운: {current_drawdown:.2%}",
            data={
                '현재 DD': current_drawdown,
                '최대 DD': max_drawdown,
                '경고레벨': alert_level,
            },
            tags=['risk', 'drawdown'],
        )

    @classmethod
    def format_daily_summary(
        cls,
        date: datetime,
        total_trades: int,
        win_rate: float,
        total_pnl: float,
        total_pnl_pct: float,
        top_winners: List[Dict],
        top_losers: List[Dict]
    ) -> Alert:
        """
        일일 요약 알림 생성
        """
        is_profit = total_pnl >= 0

        message_lines = [
            f"거래 {total_trades}건, 승률 {win_rate:.1%}",
        ]

        if top_winners:
            message_lines.append("\n<b>상위 수익:</b>")
            for w in top_winners[:3]:
                message_lines.append(f"  • {w.get('stock', '')} {w.get('pnl_pct', 0):.2%}")

        if top_losers:
            message_lines.append("\n<b>상위 손실:</b>")
            for l in top_losers[:3]:
                message_lines.append(f"  • {l.get('stock', '')} {l.get('pnl_pct', 0):.2%}")

        return Alert(
            alert_type=AlertType.DAILY_SUMMARY,
            level=AlertLevel.INFO,
            title=f"일일 요약 ({date.strftime('%m/%d')})",
            message="\n".join(message_lines),
            data={
                '총손익': total_pnl,
                '수익률': total_pnl_pct / 100,
            },
            tags=['summary', 'daily'],
        )

    @classmethod
    def format_circuit_breaker(
        cls,
        reason: str,
        triggered_at: datetime,
        cooldown_until: Optional[datetime] = None
    ) -> Alert:
        """
        서킷 브레이커 알림 생성
        """
        message = f"거래 일시 중단: {reason}"
        if cooldown_until:
            message += f"\n재개 예정: {cooldown_until.strftime('%H:%M:%S')}"

        return Alert(
            alert_type=AlertType.CIRCUIT_BREAKER,
            level=AlertLevel.CRITICAL,
            title="서킷 브레이커 발동",
            message=message,
            data={
                '발동사유': reason,
                '발동시각': triggered_at.strftime('%H:%M:%S'),
            },
            tags=['risk', 'circuit_breaker'],
        )

    @classmethod
    def format_signal(
        cls,
        stock_code: str,
        stock_name: str,
        signal_type: str,
        strength: float,
        sources: List[str],
        recommendation: str
    ) -> Alert:
        """
        매매 신호 알림 생성
        """
        alert_type = AlertType.SIGNAL_BUY if signal_type == "buy" else \
                     AlertType.SIGNAL_SELL if signal_type == "sell" else \
                     AlertType.SIGNAL_STRONG

        is_strong = strength >= 0.8
        level = AlertLevel.INFO if not is_strong else AlertLevel.WARNING

        title = f"{'매수' if signal_type == 'buy' else '매도'} 신호"
        if is_strong:
            title = f"강한 {title}"

        return Alert(
            alert_type=alert_type,
            level=level,
            title=title,
            message=f"{stock_name}: {recommendation}",
            stock_code=stock_code,
            stock_name=stock_name,
            data={
                '신호강도': strength,
                '신호소스': ", ".join(sources),
            },
            tags=['signal', signal_type],
        )

    @classmethod
    def format_system_status(
        cls,
        status: str,
        message: str,
        details: Optional[Dict] = None
    ) -> Alert:
        """
        시스템 상태 알림 생성
        """
        if status == "start":
            alert_type = AlertType.SYSTEM_START
            level = AlertLevel.INFO
            title = "시스템 시작"
        elif status == "stop":
            alert_type = AlertType.SYSTEM_STOP
            level = AlertLevel.INFO
            title = "시스템 종료"
        elif status == "error":
            alert_type = AlertType.SYSTEM_ERROR
            level = AlertLevel.CRITICAL
            title = "시스템 오류"
        else:
            alert_type = AlertType.SYSTEM_WARNING
            level = AlertLevel.WARNING
            title = "시스템 경고"

        return Alert(
            alert_type=alert_type,
            level=level,
            title=title,
            message=message,
            data=details or {},
            tags=['system', status],
        )
