"""
알림 시스템

다양한 채널을 통해 이상 상황 및 중요 정보를 사용자에게 전달하는 시스템
"""

import smtplib
import json
import os
import asyncio
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests

from ..utils.logging import get_logger
from .anomaly_detector import AnomalyAlert, AnomalySeverity

logger = get_logger(__name__)

class AlertChannel(Enum):
    """알림 채널"""
    EMAIL = "email"                 # 이메일
    SMS = "sms"                     # SMS
    SLACK = "slack"                 # 슬랙
    DISCORD = "discord"             # 디스코드
    WEBHOOK = "webhook"             # 웹훅
    DESKTOP = "desktop"             # 데스크톱 알림
    CONSOLE = "console"             # 콘솔 출력

class AlertPriority(Enum):
    """알림 우선순위"""
    IMMEDIATE = "immediate"         # 즉시
    HIGH = "high"                   # 높음
    NORMAL = "normal"               # 보통
    LOW = "low"                     # 낮음

@dataclass
class AlertConfig:
    """알림 설정"""
    # 채널별 활성화
    enabled_channels: List[AlertChannel] = field(default_factory=lambda: [AlertChannel.CONSOLE])
    
    # 이메일 설정
    email_smtp_server: str = "smtp.gmail.com"
    email_smtp_port: int = 587
    email_username: str = ""
    email_password: str = ""
    email_recipients: List[str] = field(default_factory=list)
    
    # SMS 설정 (예: Twilio)
    sms_account_sid: str = ""
    sms_auth_token: str = ""
    sms_from_number: str = ""
    sms_to_numbers: List[str] = field(default_factory=list)
    
    # 슬랙 설정
    slack_webhook_url: str = ""
    slack_channel: str = "#alerts"
    slack_username: str = "MarketMonitor"
    
    # 디스코드 설정
    discord_webhook_url: str = ""
    
    # 웹훅 설정
    webhook_urls: List[str] = field(default_factory=list)
    
    # 알림 제한
    max_alerts_per_hour: int = 10
    max_alerts_per_day: int = 50
    rate_limit_cooldown: int = 300  # 5분
    
    # 심각도별 설정
    severity_channels: Dict[str, List[AlertChannel]] = field(default_factory=lambda: {
        "critical": [AlertChannel.EMAIL, AlertChannel.SMS, AlertChannel.SLACK],
        "high": [AlertChannel.EMAIL, AlertChannel.SLACK],
        "medium": [AlertChannel.SLACK, AlertChannel.CONSOLE],
        "low": [AlertChannel.CONSOLE]
    })

@dataclass
class AlertMessage:
    """알림 메시지"""
    message_id: str
    channel: AlertChannel
    priority: AlertPriority
    title: str
    content: str
    timestamp: datetime
    
    # 원본 알림 정보
    source_alert: Optional[AnomalyAlert] = None
    
    # 전송 상태
    sent: bool = False
    sent_at: Optional[datetime] = None
    error_message: Optional[str] = None
    retry_count: int = 0

class EmailNotifier:
    """이메일 알림기"""
    
    def __init__(self, config: AlertConfig):
        self._config = config
        self._logger = logger
    
    def send_alert(self, alert: AnomalyAlert) -> bool:
        """이메일 알림 전송"""
        try:
            if not self._config.email_recipients:
                return False
            
            # 이메일 내용 생성
            subject = f"[{alert.severity.value.upper()}] {alert.title}"
            body = self._create_email_body(alert)
            
            # SMTP 연결
            with smtplib.SMTP(self._config.email_smtp_server, self._config.email_smtp_port) as server:
                server.starttls()
                server.login(self._config.email_username, self._config.email_password)
                
                for recipient in self._config.email_recipients:
                    msg = MIMEMultipart()
                    msg['From'] = self._config.email_username
                    msg['To'] = recipient
                    msg['Subject'] = subject
                    
                    msg.attach(MIMEText(body, 'html', 'utf-8'))
                    
                    server.send_message(msg)
            
            self._logger.info(f"이메일 알림 전송 완료: {alert.alert_id}")
            return True
            
        except Exception as e:
            self._logger.error(f"이메일 알림 전송 실패: {e}", exc_info=True)
            return False
    
    def _create_email_body(self, alert: AnomalyAlert) -> str:
        """이메일 본문 생성"""
        html_body = f"""
        <html>
        <body>
            <h2 style="color: {'red' if alert.severity == AnomalySeverity.CRITICAL else 'orange'};">
                {alert.title}
            </h2>
            
            <h3>상세 정보</h3>
            <p><strong>감지 시간:</strong> {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p><strong>심각도:</strong> {alert.severity.value.upper()}</p>
            <p><strong>이상 유형:</strong> {alert.anomaly_type.value}</p>
            <p><strong>신뢰도:</strong> {alert.confidence_score:.1%}</p>
            
            <h3>설명</h3>
            <p>{alert.description}</p>
            
            {self._create_affected_stocks_section(alert)}
            {self._create_recommendations_section(alert)}
            {self._create_data_section(alert)}
            
            <hr>
            <p style="font-size: 12px; color: gray;">
                한투 퀀트 시장 모니터링 시스템에서 자동 생성된 알림입니다.
            </p>
        </body>
        </html>
        """
        
        return html_body
    
    def _create_affected_stocks_section(self, alert: AnomalyAlert) -> str:
        """영향받은 종목 섹션"""
        if not alert.affected_stocks:
            return ""
        
        stocks_html = "<h3>영향받은 종목</h3><ul>"
        for stock in alert.affected_stocks:
            stocks_html += f"<li>{stock}</li>"
        stocks_html += "</ul>"
        
        return stocks_html
    
    def _create_recommendations_section(self, alert: AnomalyAlert) -> str:
        """추천사항 섹션"""
        if not alert.recommendations:
            return ""
        
        rec_html = "<h3>추천 조치</h3><ul>"
        for rec in alert.recommendations:
            rec_html += f"<li>{rec}</li>"
        rec_html += "</ul>"
        
        return rec_html
    
    def _create_data_section(self, alert: AnomalyAlert) -> str:
        """상세 데이터 섹션"""
        if not alert.data:
            return ""
        
        data_html = "<h3>상세 데이터</h3><table border='1' cellpadding='5'>"
        
        for key, value in alert.data.items():
            if isinstance(value, (int, float)):
                if isinstance(value, float):
                    value_str = f"{value:.4f}"
                else:
                    value_str = str(value)
            else:
                value_str = str(value)
            
            data_html += f"<tr><td><strong>{key}</strong></td><td>{value_str}</td></tr>"
        
        data_html += "</table>"
        
        return data_html

class SlackNotifier:
    """슬랙 알림기"""
    
    def __init__(self, config: AlertConfig):
        self._config = config
        self._logger = logger
    
    def send_alert(self, alert: AnomalyAlert) -> bool:
        """슬랙 알림 전송"""
        try:
            if not self._config.slack_webhook_url:
                return False
            
            # 슬랙 메시지 생성
            payload = self._create_slack_payload(alert)
            
            # 웹훅으로 전송
            response = requests.post(
                self._config.slack_webhook_url,
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                self._logger.info(f"슬랙 알림 전송 완료: {alert.alert_id}")
                return True
            else:
                self._logger.error(f"슬랙 알림 전송 실패: {response.status_code}", exc_info=True)
                return False
                
        except Exception as e:
            self._logger.error(f"슬랙 알림 전송 실패: {e}", exc_info=True)
            return False
    
    def _create_slack_payload(self, alert: AnomalyAlert) -> Dict:
        """슬랙 메시지 페이로드 생성"""
        # 심각도별 색상
        color_map = {
            AnomalySeverity.CRITICAL: "danger",
            AnomalySeverity.HIGH: "warning", 
            AnomalySeverity.MEDIUM: "good",
            AnomalySeverity.LOW: "#CCCCCC"
        }
        
        # 기본 필드
        fields = [
            {
                "title": "심각도",
                "value": alert.severity.value.upper(),
                "short": True
            },
            {
                "title": "이상 유형",
                "value": alert.anomaly_type.value,
                "short": True
            },
            {
                "title": "신뢰도",
                "value": f"{alert.confidence_score:.1%}",
                "short": True
            },
            {
                "title": "감지 시간",
                "value": alert.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                "short": True
            }
        ]
        
        # 영향받은 종목 추가
        if alert.affected_stocks:
            fields.append({
                "title": "영향받은 종목",
                "value": ", ".join(alert.affected_stocks[:5]),  # 최대 5개만
                "short": False
            })
        
        # 시장 영향도 추가
        if alert.market_impact:
            fields.append({
                "title": "시장 영향도",
                "value": f"{alert.market_impact:.2%}",
                "short": True
            })
        
        payload = {
            "channel": self._config.slack_channel,
            "username": self._config.slack_username,
            "icon_emoji": ":warning:",
            "attachments": [
                {
                    "color": color_map.get(alert.severity, "good"),
                    "title": alert.title,
                    "text": alert.description,
                    "fields": fields,
                    "footer": "한투 퀀트 모니터링",
                    "ts": int(alert.timestamp.timestamp())
                }
            ]
        }
        
        # 추천사항 추가
        if alert.recommendations:
            payload["attachments"][0]["actions"] = [
                {
                    "type": "button",
                    "text": "추천 조치 보기",
                    "url": "#",  # 실제로는 대시보드 URL
                    "style": "primary" if alert.severity == AnomalySeverity.CRITICAL else "default"
                }
            ]
        
        return payload

class DiscordNotifier:
    """디스코드 알림기"""
    
    def __init__(self, config: AlertConfig):
        self._config = config
        self._logger = logger
    
    def send_alert(self, alert: AnomalyAlert) -> bool:
        """디스코드 알림 전송"""
        try:
            if not self._config.discord_webhook_url:
                return False
            
            # 디스코드 임베드 생성
            payload = self._create_discord_payload(alert)
            
            # 웹훅으로 전송
            response = requests.post(
                self._config.discord_webhook_url,
                json=payload,
                timeout=10
            )
            
            if response.status_code == 204:  # Discord는 204 반환
                self._logger.info(f"디스코드 알림 전송 완료: {alert.alert_id}")
                return True
            else:
                self._logger.error(f"디스코드 알림 전송 실패: {response.status_code}", exc_info=True)
                return False
                
        except Exception as e:
            self._logger.error(f"디스코드 알림 전송 실패: {e}", exc_info=True)
            return False
    
    def _create_discord_payload(self, alert: AnomalyAlert) -> Dict:
        """디스코드 메시지 페이로드 생성"""
        # 심각도별 색상 (16진수)
        color_map = {
            AnomalySeverity.CRITICAL: 0xFF0000,  # 빨강
            AnomalySeverity.HIGH: 0xFF8C00,      # 주황
            AnomalySeverity.MEDIUM: 0xFFD700,    # 노랑
            AnomalySeverity.LOW: 0x808080        # 회색
        }
        
        # 임베드 필드
        fields = [
            {
                "name": "심각도",
                "value": alert.severity.value.upper(),
                "inline": True
            },
            {
                "name": "이상 유형",
                "value": alert.anomaly_type.value,
                "inline": True
            },
            {
                "name": "신뢰도",
                "value": f"{alert.confidence_score:.1%}",
                "inline": True
            }
        ]
        
        # 영향받은 종목
        if alert.affected_stocks:
            fields.append({
                "name": "영향받은 종목",
                "value": ", ".join(alert.affected_stocks[:5]),
                "inline": False
            })
        
        # 추천사항
        if alert.recommendations:
            recommendations_text = "\n".join([f"• {rec}" for rec in alert.recommendations[:3]])
            fields.append({
                "name": "추천 조치",
                "value": recommendations_text,
                "inline": False
            })
        
        embed = {
            "title": alert.title,
            "description": alert.description,
            "color": color_map.get(alert.severity, 0x808080),
            "fields": fields,
            "timestamp": alert.timestamp.isoformat(),
            "footer": {
                "text": "한투 퀀트 모니터링"
            }
        }
        
        return {
            "username": "MarketMonitor",
            "embeds": [embed]
        }

class WebhookNotifier:
    """웹훅 알림기"""
    
    def __init__(self, config: AlertConfig):
        self._config = config
        self._logger = logger
    
    def send_alert(self, alert: AnomalyAlert) -> bool:
        """웹훅 알림 전송"""
        try:
            if not self._config.webhook_urls:
                return False
            
            # 웹훅 페이로드 생성
            payload = self._create_webhook_payload(alert)
            
            # 모든 웹훅 URL에 전송
            success_count = 0
            for webhook_url in self._config.webhook_urls:
                try:
                    response = requests.post(
                        webhook_url,
                        json=payload,
                        timeout=10,
                        headers={'Content-Type': 'application/json'}
                    )
                    
                    if response.status_code in [200, 201, 204]:
                        success_count += 1
                    else:
                        self._logger.warning(f"웹훅 전송 실패 ({webhook_url}): {response.status_code}")
                        
                except Exception as e:
                    self._logger.error(f"웹훅 전송 오류 ({webhook_url}): {e}", exc_info=True)
            
            if success_count > 0:
                self._logger.info(f"웹훅 알림 전송 완료: {success_count}/{len(self._config.webhook_urls)}")
                return True
            else:
                return False
                
        except Exception as e:
            self._logger.error(f"웹훅 알림 전송 실패: {e}", exc_info=True)
            return False
    
    def _create_webhook_payload(self, alert: AnomalyAlert) -> Dict:
        """웹훅 페이로드 생성"""
        return {
            "alert_id": alert.alert_id,
            "anomaly_type": alert.anomaly_type.value,
            "severity": alert.severity.value,
            "timestamp": alert.timestamp.isoformat(),
            "title": alert.title,
            "description": alert.description,
            "affected_stocks": alert.affected_stocks,
            "market_impact": alert.market_impact,
            "confidence_score": alert.confidence_score,
            "recommendations": alert.recommendations,
            "detection_method": alert.detection_method,
            "false_positive_risk": alert.false_positive_risk,
            "data": alert.data
        }

class ConsoleNotifier:
    """콘솔 알림기"""
    
    def __init__(self, config: AlertConfig):
        self._config = config
        self._logger = logger
    
    def send_alert(self, alert: AnomalyAlert) -> bool:
        """콘솔 알림 출력"""
        try:
            # 심각도별 색상 코드 (ANSI)
            color_map = {
                AnomalySeverity.CRITICAL: "\033[91m",  # 빨강
                AnomalySeverity.HIGH: "\033[93m",      # 노랑
                AnomalySeverity.MEDIUM: "\033[92m",    # 초록
                AnomalySeverity.LOW: "\033[94m"        # 파랑
            }
            
            reset_color = "\033[0m"
            
            # 콘솔 출력
            color = color_map.get(alert.severity, "")
            
            print(f"\n{color}{'='*60}")
            print(f"🚨 {alert.title}")
            print(f"{'='*60}{reset_color}")
            print(f"시간: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"심각도: {color}{alert.severity.value.upper()}{reset_color}")
            print(f"유형: {alert.anomaly_type.value}")
            print(f"신뢰도: {alert.confidence_score:.1%}")
            print(f"\n설명: {alert.description}")
            
            if alert.affected_stocks:
                print(f"\n영향받은 종목: {', '.join(alert.affected_stocks)}")
            
            if alert.recommendations:
                print(f"\n추천 조치:")
                for i, rec in enumerate(alert.recommendations, 1):
                    print(f"  {i}. {rec}")
            
            print(f"{color}{'='*60}{reset_color}\n")
            
            return True
            
        except Exception as e:
            self._logger.error(f"콘솔 알림 출력 실패: {e}", exc_info=True)
            return False

class AlertRateLimiter:
    """알림 속도 제한기"""
    
    def __init__(self, config: AlertConfig):
        self._config = config
        self._alert_counts = {
            'hourly': [],
            'daily': []
        }
        self._last_cleanup = datetime.now()
    
    def is_rate_limited(self) -> bool:
        """속도 제한 여부 확인"""
        self._cleanup_old_records()
        
        now = datetime.now()
        
        # 시간당 제한 확인
        hour_ago = now - timedelta(hours=1)
        hourly_count = len([t for t in self._alert_counts['hourly'] if t > hour_ago])
        
        if hourly_count >= self._config.max_alerts_per_hour:
            return True
        
        # 일일 제한 확인
        day_ago = now - timedelta(days=1)
        daily_count = len([t for t in self._alert_counts['daily'] if t > day_ago])
        
        if daily_count >= self._config.max_alerts_per_day:
            return True
        
        return False
    
    def record_alert(self):
        """알림 기록"""
        now = datetime.now()
        self._alert_counts['hourly'].append(now)
        self._alert_counts['daily'].append(now)
    
    def _cleanup_old_records(self):
        """오래된 기록 정리"""
        now = datetime.now()
        
        # 1시간에 한 번씩 정리
        if (now - self._last_cleanup).total_seconds() < 3600:
            return
        
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(days=1)
        
        self._alert_counts['hourly'] = [t for t in self._alert_counts['hourly'] if t > hour_ago]
        self._alert_counts['daily'] = [t for t in self._alert_counts['daily'] if t > day_ago]
        
        self._last_cleanup = now

class AlertSystem:
    """통합 알림 시스템"""
    
    def __init__(self, config: AlertConfig = None, data_dir: str = "data/alerts"):
        """
        초기화
        
        Args:
            config: 알림 설정
            data_dir: 알림 데이터 저장 디렉토리
        """
        self._logger = logger
        self._config = config or AlertConfig()
        self._data_dir = data_dir
        
        # 디렉토리 생성
        os.makedirs(data_dir, exist_ok=True)
        
        # 알림기들 초기화
        self._notifiers = {
            AlertChannel.EMAIL: EmailNotifier(self._config),
            AlertChannel.SLACK: SlackNotifier(self._config),
            AlertChannel.DISCORD: DiscordNotifier(self._config),
            AlertChannel.WEBHOOK: WebhookNotifier(self._config),
            AlertChannel.CONSOLE: ConsoleNotifier(self._config)
        }
        
        # 속도 제한기
        self._rate_limiter = AlertRateLimiter(self._config)
        
        # 알림 큐 및 스레드
        self._alert_queue = asyncio.Queue()
        self._processing_thread = None
        self._is_running = False
        
        # 알림 기록
        self._sent_alerts = []
        self._failed_alerts = []
        
        self._logger.info("통합 알림 시스템 초기화 완료")
    
    def start(self):
        """알림 시스템 시작"""
        if self._is_running:
            self._logger.warning("알림 시스템이 이미 실행 중입니다")
            return
        
        self._is_running = True
        self._processing_thread = threading.Thread(target=self._process_alerts_sync)
        self._processing_thread.start()
        
        self._logger.info("알림 시스템 시작")
    
    def stop(self):
        """알림 시스템 중지"""
        if not self._is_running:
            return
        
        self._is_running = False
        
        if self._processing_thread:
            self._processing_thread.join()
        
        self._logger.info("알림 시스템 중지")
    
    def send_alert(self, alert: AnomalyAlert, priority: AlertPriority = AlertPriority.NORMAL):
        """알림 전송"""
        try:
            # 속도 제한 확인
            if self._rate_limiter.is_rate_limited():
                self._logger.warning(f"알림 속도 제한으로 인해 스킵: {alert.alert_id}")
                return
            
            # 심각도별 채널 결정
            channels = self._get_channels_for_severity(alert.severity)
            
            # 각 채널별 알림 메시지 생성
            for channel in channels:
                if channel in self._config.enabled_channels:
                    message = AlertMessage(
                        message_id=f"{alert.alert_id}_{channel.value}",
                        channel=channel,
                        priority=priority,
                        title=alert.title,
                        content=alert.description,
                        timestamp=datetime.now(),
                        source_alert=alert
                    )
                    
                    # 즉시 전송 또는 큐에 추가
                    if priority == AlertPriority.IMMEDIATE:
                        self._send_message_sync(message)
                    else:
                        # 비동기 큐에 추가 (동기적으로 처리)
                        self._add_to_queue_sync(message)
            
            # 속도 제한 기록
            self._rate_limiter.record_alert()
            
        except Exception as e:
            self._logger.error(f"알림 전송 실패: {e}", exc_info=True)
    
    def _get_channels_for_severity(self, severity: AnomalySeverity) -> List[AlertChannel]:
        """심각도별 채널 조회"""
        severity_key = severity.value
        
        if severity_key in self._config.severity_channels:
            return self._config.severity_channels[severity_key]
        
        # 기본값
        if severity == AnomalySeverity.CRITICAL:
            return [AlertChannel.EMAIL, AlertChannel.SLACK, AlertChannel.CONSOLE]
        elif severity == AnomalySeverity.HIGH:
            return [AlertChannel.SLACK, AlertChannel.CONSOLE]
        else:
            return [AlertChannel.CONSOLE]
    
    def _add_to_queue_sync(self, message: AlertMessage):
        """동기적으로 큐에 메시지 추가"""
        try:
            # 간단한 리스트 큐 사용 (스레드 안전성을 위해 락 사용)
            if not hasattr(self, '_simple_queue'):
                self._simple_queue = []
                self._queue_lock = threading.Lock()
            
            with self._queue_lock:
                self._simple_queue.append(message)
                
        except Exception as e:
            self._logger.error(f"큐 추가 실패: {e}", exc_info=True)
    
    def _process_alerts_sync(self):
        """동기적 알림 처리 루프"""
        while self._is_running:
            try:
                # 큐에서 메시지 가져오기
                message = None
                if hasattr(self, '_simple_queue'):
                    with self._queue_lock:
                        if self._simple_queue:
                            message = self._simple_queue.pop(0)
                
                if message:
                    self._send_message_sync(message)
                else:
                    time.sleep(1)  # 1초 대기
                    
            except Exception as e:
                self._logger.error(f"알림 처리 루프 오류: {e}", exc_info=True)
                time.sleep(5)
    
    def _send_message_sync(self, message: AlertMessage):
        """동기적 메시지 전송"""
        try:
            notifier = self._notifiers.get(message.channel)
            if not notifier:
                self._logger.error(f"알 수 없는 채널: {message.channel}", exc_info=True)
                return
            
            # 알림 전송
            success = False
            if message.source_alert:
                success = notifier.send_alert(message.source_alert)
            
            # 결과 기록
            message.sent = success
            message.sent_at = datetime.now() if success else None
            
            if success:
                self._sent_alerts.append(message)
                self._logger.info(f"알림 전송 성공: {message.message_id} via {message.channel.value}")
            else:
                message.error_message = "전송 실패"
                self._failed_alerts.append(message)
                self._logger.error(f"알림 전송 실패: {message.message_id} via {message.channel.value}", exc_info=True)
            
            # 기록 저장
            self._save_alert_record(message)
            
        except Exception as e:
            self._logger.error(f"메시지 전송 오류: {e}", exc_info=True)
            message.error_message = str(e)
            self._failed_alerts.append(message)
    
    def _save_alert_record(self, message: AlertMessage):
        """알림 기록 저장"""
        try:
            timestamp_str = message.timestamp.strftime('%Y%m%d')
            filename = f"alert_records_{timestamp_str}.json"
            filepath = os.path.join(self._data_dir, filename)
            
            # 기존 기록 로드
            records = []
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    records = json.load(f)
            
            # 새 기록 추가
            record = {
                'message_id': message.message_id,
                'channel': message.channel.value,
                'priority': message.priority.value,
                'title': message.title,
                'timestamp': message.timestamp.isoformat(),
                'sent': message.sent,
                'sent_at': message.sent_at.isoformat() if message.sent_at else None,
                'error_message': message.error_message,
                'retry_count': message.retry_count
            }
            
            records.append(record)
            
            # 파일 저장
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(records, f, ensure_ascii=False, indent=2, default=str)
                
        except Exception as e:
            self._logger.error(f"알림 기록 저장 실패: {e}", exc_info=True)
    
    def get_alert_statistics(self, days: int = 7) -> Dict[str, Any]:
        """알림 통계 조회"""
        cutoff_time = datetime.now() - timedelta(days=days)
        
        # 최근 전송된 알림 필터링
        recent_sent = [
            alert for alert in self._sent_alerts
            if alert.timestamp > cutoff_time
        ]
        
        recent_failed = [
            alert for alert in self._failed_alerts
            if alert.timestamp > cutoff_time
        ]
        
        # 채널별 통계
        channel_stats = {}
        for channel in AlertChannel:
            sent_count = len([a for a in recent_sent if a.channel == channel])
            failed_count = len([a for a in recent_failed if a.channel == channel])
            
            channel_stats[channel.value] = {
                'sent': sent_count,
                'failed': failed_count,
                'success_rate': (sent_count / (sent_count + failed_count)) if (sent_count + failed_count) > 0 else 0
            }
        
        return {
            'period_days': days,
            'total_sent': len(recent_sent),
            'total_failed': len(recent_failed),
            'overall_success_rate': len(recent_sent) / (len(recent_sent) + len(recent_failed)) if (len(recent_sent) + len(recent_failed)) > 0 else 0,
            'channel_statistics': channel_stats,
            'hourly_limit_remaining': self._config.max_alerts_per_hour - len([t for t in self._rate_limiter._alert_counts['hourly'] if t > datetime.now() - timedelta(hours=1)]),
            'daily_limit_remaining': self._config.max_alerts_per_day - len([t for t in self._rate_limiter._alert_counts['daily'] if t > datetime.now() - timedelta(days=1)])
        }
    
    def test_channels(self) -> Dict[str, bool]:
        """채널 테스트"""
        test_results = {}
        
        # 테스트 알림 생성
        from .anomaly_detector import AnomalyType
        
        test_alert = AnomalyAlert(
            alert_id="test_alert",
            anomaly_type=AnomalyType.UNUSUAL_PATTERN,
            severity=AnomalySeverity.LOW,
            timestamp=datetime.now(),
            title="테스트 알림",
            description="이것은 알림 시스템 테스트입니다.",
            confidence_score=1.0,
            detection_method="manual_test"
        )
        
        # 각 채널 테스트
        for channel in self._config.enabled_channels:
            try:
                notifier = self._notifiers.get(channel)
                if notifier:
                    success = notifier.send_alert(test_alert)
                    test_results[channel.value] = success
                else:
                    test_results[channel.value] = False
                    
            except Exception as e:
                self._logger.error(f"채널 테스트 실패 ({channel.value}): {e}", exc_info=True)
                test_results[channel.value] = False
        
        return test_results

# 전역 인스턴스
_alert_system = None

def get_alert_system() -> AlertSystem:
    """알림 시스템 싱글톤 인스턴스 반환"""
    global _alert_system
    if _alert_system is None:
        _alert_system = AlertSystem()
    return _alert_system 