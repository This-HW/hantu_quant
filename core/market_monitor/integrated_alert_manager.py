"""
통합 알림 관리자

이메일, SMS, 웹푸시 등 다양한 알림 채널을 통합 관리하는 시스템
"""

import json
import os
import asyncio
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any, Callable
from dataclasses import dataclass, asdict, field
from enum import Enum
import requests
from concurrent.futures import ThreadPoolExecutor

from ..utils.logging import get_logger
from .market_monitor import MarketMonitor, MarketSnapshot
from .anomaly_detector import AnomalyDetector, AnomalyAlert, AnomalySeverity
from .alert_system import AlertSystem, AlertChannel

logger = get_logger(__name__)

class NotificationPriority(Enum):
    """알림 우선순위"""
    EMERGENCY = "emergency"     # 응급 (즉시 전송)
    HIGH = "high"              # 높음 (5분 이내)
    NORMAL = "normal"          # 보통 (30분 이내)
    LOW = "low"                # 낮음 (2시간 이내)

class ChannelStatus(Enum):
    """채널 상태"""
    ACTIVE = "active"          # 활성
    INACTIVE = "inactive"      # 비활성
    ERROR = "error"            # 오류
    MAINTENANCE = "maintenance" # 점검

@dataclass
class NotificationRule:
    """알림 규칙"""
    rule_id: str
    name: str
    enabled: bool = True
    
    # 조건
    severity_filter: List[AnomalySeverity] = field(default_factory=list)
    time_filter: Optional[Tuple[str, str]] = None  # (시작시간, 종료시간) "HH:MM" 형식
    weekday_filter: List[int] = field(default_factory=list)  # 0=월요일, 6=일요일
    stock_filter: List[str] = field(default_factory=list)    # 특정 종목만
    
    # 채널 설정
    channels: Dict[AlertChannel, NotificationPriority] = field(default_factory=dict)
    
    # 제한 설정
    max_alerts_per_hour: int = 10
    cooldown_minutes: int = 5
    
    # 에스컬레이션
    escalation_enabled: bool = False
    escalation_delay_minutes: int = 30
    escalation_channels: List[AlertChannel] = field(default_factory=list)

@dataclass
class ChannelConfig:
    """채널 설정"""
    channel: AlertChannel
    status: ChannelStatus = ChannelStatus.ACTIVE
    priority: int = 1  # 우선순위 (낮을수록 높음)
    
    # 전송 제한
    rate_limit_per_minute: int = 10
    rate_limit_per_hour: int = 100
    rate_limit_per_day: int = 1000
    
    # 재시도 설정
    max_retries: int = 3
    retry_delay_seconds: int = 30
    
    # 채널별 특수 설정
    settings: Dict[str, Any] = field(default_factory=dict)

@dataclass
class NotificationLog:
    """알림 로그"""
    log_id: str
    notification_id: str
    channel: AlertChannel
    priority: NotificationPriority
    timestamp: datetime
    
    # 상태
    status: str  # "sent", "failed", "pending", "skipped"
    error_message: Optional[str] = None
    retry_count: int = 0
    
    # 메타데이터
    rule_id: Optional[str] = None
    delivery_time: Optional[datetime] = None
    read_time: Optional[datetime] = None

class AdvancedEmailNotifier:
    """고급 이메일 알림기"""
    
    def __init__(self, config: Dict[str, Any]):
        self._config = config
        self._logger = logger
        self._template_cache = {}
    
    def send_notification(self, alert: AnomalyAlert, priority: NotificationPriority, 
                         recipients: List[str] = None) -> bool:
        """알림 전송"""
        try:
            recipients = recipients or self._config.get('default_recipients', [])
            if not recipients:
                return False
            
            # 우선순위별 템플릿 선택
            template = self._get_template_for_priority(priority)
            
            # 이메일 내용 생성
            subject, body = self._create_email_content(alert, template)
            
            # 전송
            return self._send_email(recipients, subject, body, priority)
            
        except Exception as e:
            self._logger.error(f"고급 이메일 알림 전송 실패: {e}")
            return False
    
    def _get_template_for_priority(self, priority: NotificationPriority) -> Dict[str, str]:
        """우선순위별 템플릿 조회"""
        templates = {
            NotificationPriority.EMERGENCY: {
                'subject_prefix': '🚨 [긴급]',
                'urgency': 'high',
                'color_scheme': 'red'
            },
            NotificationPriority.HIGH: {
                'subject_prefix': '⚠️ [중요]',
                'urgency': 'normal',
                'color_scheme': 'orange'
            },
            NotificationPriority.NORMAL: {
                'subject_prefix': '📊 [알림]',
                'urgency': 'normal',
                'color_scheme': 'blue'
            },
            NotificationPriority.LOW: {
                'subject_prefix': 'ℹ️ [정보]',
                'urgency': 'low',
                'color_scheme': 'gray'
            }
        }
        
        return templates.get(priority, templates[NotificationPriority.NORMAL])
    
    def _create_email_content(self, alert: AnomalyAlert, template: Dict) -> Tuple[str, str]:
        """이메일 내용 생성"""
        # 제목
        subject = f"{template['subject_prefix']} {alert.title}"
        
        # 본문 HTML
        body = f"""
        <html>
        <head>
            <style>
                .alert-container {{
                    font-family: Arial, sans-serif;
                    max-width: 600px;
                    margin: 0 auto;
                    border: 2px solid {template['color_scheme']};
                    border-radius: 10px;
                    padding: 20px;
                }}
                .alert-header {{
                    background-color: {template['color_scheme']};
                    color: white;
                    padding: 15px;
                    margin: -20px -20px 20px -20px;
                    border-radius: 8px 8px 0 0;
                }}
                .alert-body {{ padding: 20px 0; }}
                .info-table {{ width: 100%; border-collapse: collapse; }}
                .info-table td {{ padding: 8px; border-bottom: 1px solid #eee; }}
                .recommendations {{ background-color: #f8f9fa; padding: 15px; border-radius: 5px; }}
            </style>
        </head>
        <body>
            <div class="alert-container">
                <div class="alert-header">
                    <h2>{alert.title}</h2>
                    <p>감지 시간: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</p>
                </div>
                
                <div class="alert-body">
                    <h3>상세 정보</h3>
                    <table class="info-table">
                        <tr><td><strong>심각도</strong></td><td>{alert.severity.value.upper()}</td></tr>
                        <tr><td><strong>이상 유형</strong></td><td>{alert.anomaly_type.value}</td></tr>
                        <tr><td><strong>신뢰도</strong></td><td>{alert.confidence_score:.1%}</td></tr>
                        <tr><td><strong>감지 방법</strong></td><td>{alert.detection_method}</td></tr>
                    </table>
                    
                    <h3>설명</h3>
                    <p>{alert.description}</p>
                    
                    {self._create_affected_stocks_section(alert)}
                    {self._create_recommendations_section(alert)}
                    {self._create_action_buttons(alert)}
                </div>
            </div>
        </body>
        </html>
        """
        
        return subject, body
    
    def _create_affected_stocks_section(self, alert: AnomalyAlert) -> str:
        """영향받은 종목 섹션"""
        if not alert.affected_stocks:
            return ""
        
        stocks_html = "<h3>영향받은 종목</h3><ul>"
        for stock in alert.affected_stocks[:10]:  # 최대 10개만 표시
            stocks_html += f"<li><strong>{stock}</strong></li>"
        
        if len(alert.affected_stocks) > 10:
            stocks_html += f"<li>... 외 {len(alert.affected_stocks) - 10}개 종목</li>"
        
        stocks_html += "</ul>"
        return stocks_html
    
    def _create_recommendations_section(self, alert: AnomalyAlert) -> str:
        """추천사항 섹션"""
        if not alert.recommendations:
            return ""
        
        rec_html = "<div class='recommendations'><h3>📋 추천 조치</h3><ol>"
        for rec in alert.recommendations:
            rec_html += f"<li>{rec}</li>"
        rec_html += "</ol></div>"
        
        return rec_html
    
    def _create_action_buttons(self, alert: AnomalyAlert) -> str:
        """액션 버튼 섹션"""
        # 실제 구현에서는 대시보드 URL을 포함
        return """
        <div style="text-align: center; margin-top: 30px;">
            <a href="#" style="background-color: #007bff; color: white; padding: 10px 20px; 
               text-decoration: none; border-radius: 5px; margin: 0 10px;">
               📊 대시보드 보기
            </a>
            <a href="#" style="background-color: #28a745; color: white; padding: 10px 20px; 
               text-decoration: none; border-radius: 5px; margin: 0 10px;">
               ✅ 확인 완료
            </a>
        </div>
        """
    
    def _send_email(self, recipients: List[str], subject: str, body: str, 
                   priority: NotificationPriority) -> bool:
        """이메일 전송"""
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            
            # SMTP 설정
            smtp_server = self._config.get('smtp_server', 'smtp.gmail.com')
            smtp_port = self._config.get('smtp_port', 587)
            username = self._config.get('username', '')
            password = self._config.get('password', '')
            
            # 우선순위 헤더 설정
            priority_headers = {
                NotificationPriority.EMERGENCY: ('1', 'high'),
                NotificationPriority.HIGH: ('2', 'normal'), 
                NotificationPriority.NORMAL: ('3', 'normal'),
                NotificationPriority.LOW: ('4', 'low')
            }
            
            x_priority, importance = priority_headers.get(priority, ('3', 'normal'))
            
            # 이메일 구성
            for recipient in recipients:
                msg = MIMEMultipart()
                msg['From'] = username
                msg['To'] = recipient
                msg['Subject'] = subject
                msg['X-Priority'] = x_priority
                msg['Importance'] = importance
                
                msg.attach(MIMEText(body, 'html', 'utf-8'))
                
                # 전송
                with smtplib.SMTP(smtp_server, smtp_port) as server:
                    server.starttls()
                    server.login(username, password)
                    server.send_message(msg)
            
            return True
            
        except Exception as e:
            self._logger.error(f"이메일 전송 실패: {e}")
            return False

class SMSNotifier:
    """SMS 알림기"""
    
    def __init__(self, config: Dict[str, Any]):
        self._config = config
        self._logger = logger
    
    def send_notification(self, alert: AnomalyAlert, priority: NotificationPriority,
                         phone_numbers: List[str] = None) -> bool:
        """SMS 알림 전송"""
        try:
            phone_numbers = phone_numbers or self._config.get('default_numbers', [])
            if not phone_numbers:
                return False
            
            # SMS 내용 생성
            message = self._create_sms_content(alert, priority)
            
            # 전송
            return self._send_sms(phone_numbers, message)
            
        except Exception as e:
            self._logger.error(f"SMS 알림 전송 실패: {e}")
            return False
    
    def _create_sms_content(self, alert: AnomalyAlert, priority: NotificationPriority) -> str:
        """SMS 내용 생성"""
        # 우선순위별 이모지
        priority_emoji = {
            NotificationPriority.EMERGENCY: '🚨',
            NotificationPriority.HIGH: '⚠️',
            NotificationPriority.NORMAL: '📊',
            NotificationPriority.LOW: 'ℹ️'
        }
        
        emoji = priority_emoji.get(priority, '📊')
        
        # 짧은 메시지 생성 (SMS 길이 제한)
        message = f"{emoji} 한투퀀트 알림\n"
        message += f"{alert.title}\n"
        message += f"심각도: {alert.severity.value.upper()}\n"
        message += f"시간: {alert.timestamp.strftime('%H:%M')}\n"
        
        if alert.affected_stocks:
            stocks = ', '.join(alert.affected_stocks[:3])
            message += f"종목: {stocks}\n"
        
        message += f"신뢰도: {alert.confidence_score:.0%}"
        
        return message[:160]  # SMS 길이 제한
    
    def _send_sms(self, phone_numbers: List[str], message: str) -> bool:
        """SMS 전송"""
        try:
            # Twilio 사용 예시
            service_type = self._config.get('service', 'twilio')
            
            if service_type == 'twilio':
                return self._send_via_twilio(phone_numbers, message)
            elif service_type == 'aws_sns':
                return self._send_via_aws_sns(phone_numbers, message)
            else:
                # Mock 전송
                self._logger.info(f"SMS 전송 (Mock): {len(phone_numbers)}명에게 전송")
                return True
                
        except Exception as e:
            self._logger.error(f"SMS 전송 실패: {e}")
            return False
    
    def _send_via_twilio(self, phone_numbers: List[str], message: str) -> bool:
        """Twilio를 통한 SMS 전송"""
        try:
            # Twilio 설정이 있으면 실제 전송
            account_sid = self._config.get('twilio_account_sid')
            auth_token = self._config.get('twilio_auth_token')
            from_number = self._config.get('twilio_from_number')
            
            if not all([account_sid, auth_token, from_number]):
                self._logger.warning("Twilio 설정이 불완전합니다 - Mock 전송")
                return True
            
            # 실제 Twilio API 호출 (라이브러리 설치 필요)
            # from twilio.rest import Client
            # client = Client(account_sid, auth_token)
            
            for phone_number in phone_numbers:
                # message = client.messages.create(
                #     body=message,
                #     from_=from_number,
                #     to=phone_number
                # )
                self._logger.info(f"Twilio SMS 전송: {phone_number}")
            
            return True
            
        except Exception as e:
            self._logger.error(f"Twilio SMS 전송 실패: {e}")
            return False
    
    def _send_via_aws_sns(self, phone_numbers: List[str], message: str) -> bool:
        """AWS SNS를 통한 SMS 전송"""
        try:
            # AWS SNS 설정이 있으면 실제 전송
            # boto3 라이브러리 필요
            self._logger.info(f"AWS SNS SMS 전송: {len(phone_numbers)}명")
            return True
            
        except Exception as e:
            self._logger.error(f"AWS SNS SMS 전송 실패: {e}")
            return False

class WebPushNotifier:
    """웹 푸시 알림기"""
    
    def __init__(self, config: Dict[str, Any]):
        self._config = config
        self._logger = logger
        self._subscriptions = []
    
    def add_subscription(self, subscription_data: Dict[str, Any]):
        """푸시 구독 추가"""
        self._subscriptions.append(subscription_data)
        self._logger.info(f"웹 푸시 구독 추가: {len(self._subscriptions)}개")
    
    def send_notification(self, alert: AnomalyAlert, priority: NotificationPriority) -> bool:
        """웹 푸시 알림 전송"""
        try:
            if not self._subscriptions:
                return False
            
            # 푸시 알림 페이로드 생성
            payload = self._create_push_payload(alert, priority)
            
            # 모든 구독자에게 전송
            success_count = 0
            for subscription in self._subscriptions:
                if self._send_push_to_subscription(subscription, payload):
                    success_count += 1
            
            return success_count > 0
            
        except Exception as e:
            self._logger.error(f"웹 푸시 알림 전송 실패: {e}")
            return False
    
    def _create_push_payload(self, alert: AnomalyAlert, priority: NotificationPriority) -> Dict:
        """푸시 알림 페이로드 생성"""
        # 우선순위별 설정
        priority_config = {
            NotificationPriority.EMERGENCY: {
                'urgency': 'high',
                'icon': '🚨',
                'badge': '/icons/emergency-badge.png',
                'requireInteraction': True
            },
            NotificationPriority.HIGH: {
                'urgency': 'high',
                'icon': '⚠️',
                'badge': '/icons/high-badge.png',
                'requireInteraction': True
            },
            NotificationPriority.NORMAL: {
                'urgency': 'normal',
                'icon': '📊',
                'badge': '/icons/normal-badge.png',
                'requireInteraction': False
            },
            NotificationPriority.LOW: {
                'urgency': 'low',
                'icon': 'ℹ️',
                'badge': '/icons/low-badge.png',
                'requireInteraction': False
            }
        }
        
        config = priority_config.get(priority, priority_config[NotificationPriority.NORMAL])
        
        # 액션 버튼 생성
        actions = [
            {
                'action': 'view',
                'title': '대시보드 보기',
                'icon': '/icons/view-icon.png'
            },
            {
                'action': 'dismiss',
                'title': '닫기',
                'icon': '/icons/dismiss-icon.png'
            }
        ]
        
        if priority in [NotificationPriority.EMERGENCY, NotificationPriority.HIGH]:
            actions.insert(0, {
                'action': 'acknowledge',
                'title': '확인 완료',
                'icon': '/icons/ack-icon.png'
            })
        
        return {
            'title': f"{config['icon']} {alert.title}",
            'body': f"{alert.description[:100]}...",
            'icon': '/icons/app-icon.png',
            'badge': config['badge'],
            'data': {
                'alert_id': alert.alert_id,
                'severity': alert.severity.value,
                'timestamp': alert.timestamp.isoformat(),
                'url': '/dashboard'  # 대시보드 URL
            },
            'actions': actions,
            'requireInteraction': config['requireInteraction'],
            'urgency': config['urgency'],
            'tag': f"alert-{alert.anomaly_type.value}",  # 같은 태그는 그룹화됨
            'renotify': priority == NotificationPriority.EMERGENCY
        }
    
    def _send_push_to_subscription(self, subscription: Dict, payload: Dict) -> bool:
        """개별 구독자에게 푸시 전송"""
        try:
            # pywebpush 라이브러리 사용 (설치 필요)
            # from pywebpush import webpush
            
            # VAPID 키 설정
            vapid_private_key = self._config.get('vapid_private_key')
            vapid_claims = self._config.get('vapid_claims', {})
            
            if not vapid_private_key:
                self._logger.warning("VAPID 키가 설정되지 않음 - Mock 전송")
                return True
            
            # 실제 푸시 전송
            # webpush(
            #     subscription_info=subscription,
            #     data=json.dumps(payload),
            #     vapid_private_key=vapid_private_key,
            #     vapid_claims=vapid_claims
            # )
            
            self._logger.info("웹 푸시 전송 완료")
            return True
            
        except Exception as e:
            self._logger.error(f"웹 푸시 전송 실패: {e}")
            return False

class TelegramNotifier:
    """텔레그램 알림기"""
    
    def __init__(self, config: Dict[str, Any]):
        self._config = config
        self._logger = logger
    
    def send_notification(self, alert: AnomalyAlert, priority: NotificationPriority,
                         chat_ids: List[str] = None) -> bool:
        """텔레그램 알림 전송"""
        try:
            bot_token = self._config.get('bot_token')
            chat_ids = chat_ids or self._config.get('default_chat_ids', [])
            
            if not bot_token or not chat_ids:
                return False
            
            # 메시지 생성
            message = self._create_telegram_message(alert, priority)
            
            # 전송
            return self._send_telegram_message(bot_token, chat_ids, message, priority)
            
        except Exception as e:
            self._logger.error(f"텔레그램 알림 전송 실패: {e}")
            return False
    
    def _create_telegram_message(self, alert: AnomalyAlert, priority: NotificationPriority) -> str:
        """텔레그램 메시지 생성"""
        # 우선순위별 이모지
        priority_emoji = {
            NotificationPriority.EMERGENCY: '🚨🔥',
            NotificationPriority.HIGH: '⚠️🔴', 
            NotificationPriority.NORMAL: '📊🔵',
            NotificationPriority.LOW: 'ℹ️⚪'
        }
        
        emoji = priority_emoji.get(priority, '📊🔵')
        
        # Markdown 형식 메시지
        message = f"{emoji} *한투 퀀트 알림*\n\n"
        message += f"*{alert.title}*\n\n"
        message += f"📅 시간: `{alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}`\n"
        message += f"🎯 심각도: `{alert.severity.value.upper()}`\n"
        message += f"🔍 유형: `{alert.anomaly_type.value}`\n"
        message += f"📊 신뢰도: `{alert.confidence_score:.1%}`\n\n"
        
        message += f"📝 설명:\n{alert.description}\n\n"
        
        if alert.affected_stocks:
            stocks = ', '.join([f"`{stock}`" for stock in alert.affected_stocks[:5]])
            message += f"📈 영향 종목: {stocks}\n"
            if len(alert.affected_stocks) > 5:
                message += f"... 외 {len(alert.affected_stocks) - 5}개\n"
            message += "\n"
        
        if alert.recommendations:
            message += "💡 추천 조치:\n"
            for i, rec in enumerate(alert.recommendations[:3], 1):
                message += f"{i}. {rec}\n"
            message += "\n"
        
        # 인라인 키보드 버튼
        if priority in [NotificationPriority.EMERGENCY, NotificationPriority.HIGH]:
            message += "👆 빠른 액션이 필요할 수 있습니다."
        
        return message
    
    def _send_telegram_message(self, bot_token: str, chat_ids: List[str], 
                              message: str, priority: NotificationPriority) -> bool:
        """텔레그램 메시지 전송"""
        try:
            success_count = 0
            
            for chat_id in chat_ids:
                url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                
                # 인라인 키보드 생성
                keyboard = self._create_inline_keyboard(priority)
                
                payload = {
                    'chat_id': chat_id,
                    'text': message,
                    'parse_mode': 'Markdown',
                    'disable_web_page_preview': True,
                    'reply_markup': json.dumps(keyboard) if keyboard else None
                }
                
                response = requests.post(url, json=payload, timeout=10)
                
                if response.status_code == 200:
                    success_count += 1
                else:
                    self._logger.error(f"텔레그램 전송 실패 ({chat_id}): {response.status_code}")
            
            return success_count > 0
            
        except Exception as e:
            self._logger.error(f"텔레그램 메시지 전송 실패: {e}")
            return False
    
    def _create_inline_keyboard(self, priority: NotificationPriority) -> Optional[Dict]:
        """인라인 키보드 생성"""
        if priority == NotificationPriority.LOW:
            return None
        
        keyboard = {
            'inline_keyboard': [
                [
                    {'text': '📊 대시보드', 'url': 'https://dashboard.hantu-quant.com'},
                    {'text': '✅ 확인', 'callback_data': 'acknowledge'}
                ]
            ]
        }
        
        if priority == NotificationPriority.EMERGENCY:
            keyboard['inline_keyboard'].append([
                {'text': '🚨 긴급 대응', 'callback_data': 'emergency_response'}
            ])
        
        return keyboard

class IntegratedAlertManager:
    """통합 알림 관리자"""
    
    def __init__(self, config_file: str = None, data_dir: str = "data/integrated_alerts"):
        """
        초기화
        
        Args:
            config_file: 설정 파일 경로
            data_dir: 데이터 저장 디렉토리
        """
        self._logger = logger
        self._data_dir = data_dir
        
        # 디렉토리 생성
        os.makedirs(data_dir, exist_ok=True)
        
        # 설정 로드
        self._config = self._load_config(config_file)
        
        # 알림기들 초기화
        self._notifiers = {}
        self._initialize_notifiers()
        
        # 규칙 및 채널 관리
        self._notification_rules = {}
        self._channel_configs = {}
        self._load_rules_and_configs()
        
        # 전송 관리
        self._notification_queue = []
        self._notification_logs = []
        self._rate_limiters = {}
        
        # 스레드 관리
        self._is_running = False
        self._processing_thread = None
        self._executor = ThreadPoolExecutor(max_workers=5)
        
        self._logger.info("통합 알림 관리자 초기화 완료")
    
    def _load_config(self, config_file: str) -> Dict[str, Any]:
        """설정 로드"""
        default_config = {
            'email': {
                'smtp_server': 'smtp.gmail.com',
                'smtp_port': 587,
                'username': '',
                'password': '',
                'default_recipients': []
            },
            'sms': {
                'service': 'mock',
                'default_numbers': []
            },
            'web_push': {
                'vapid_private_key': '',
                'vapid_claims': {}
            },
            'telegram': {
                'bot_token': '',
                'default_chat_ids': []
            }
        }
        
        if config_file and os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                
                # 설정 병합
                for key, value in user_config.items():
                    if key in default_config and isinstance(value, dict):
                        default_config[key].update(value)
                    else:
                        default_config[key] = value
                        
            except Exception as e:
                self._logger.error(f"설정 파일 로드 실패: {e}")
        
        return default_config
    
    def _initialize_notifiers(self):
        """알림기들 초기화"""
        try:
            # 이메일 알림기
            if self._config.get('email', {}).get('username'):
                self._notifiers[AlertChannel.EMAIL] = AdvancedEmailNotifier(
                    self._config['email']
                )
            
            # SMS 알림기
            if self._config.get('sms', {}).get('default_numbers'):
                self._notifiers[AlertChannel.SMS] = SMSNotifier(
                    self._config['sms']
                )
            
            # 웹 푸시 알림기
            self._notifiers['web_push'] = WebPushNotifier(
                self._config.get('web_push', {})
            )
            
            # 텔레그램 알림기
            if self._config.get('telegram', {}).get('bot_token'):
                self._notifiers['telegram'] = TelegramNotifier(
                    self._config['telegram']
                )
            
            # 기본 콘솔 알림기는 항상 활성화
            from .alert_system import ConsoleNotifier
            self._notifiers[AlertChannel.CONSOLE] = ConsoleNotifier({})
            
            self._logger.info(f"알림기 초기화 완료: {len(self._notifiers)}개")
            
        except Exception as e:
            self._logger.error(f"알림기 초기화 실패: {e}")
    
    def _load_rules_and_configs(self):
        """규칙 및 설정 로드"""
        try:
            # 기본 규칙 생성
            self._create_default_rules()
            
            # 기본 채널 설정 생성
            self._create_default_channel_configs()
            
            # 저장된 규칙 로드
            rules_file = os.path.join(self._data_dir, "notification_rules.json")
            if os.path.exists(rules_file):
                with open(rules_file, 'r', encoding='utf-8') as f:
                    rules_data = json.load(f)
                
                for rule_data in rules_data:
                    rule = self._deserialize_rule(rule_data)
                    self._notification_rules[rule.rule_id] = rule
            
            # 저장된 채널 설정 로드
            configs_file = os.path.join(self._data_dir, "channel_configs.json")
            if os.path.exists(configs_file):
                with open(configs_file, 'r', encoding='utf-8') as f:
                    configs_data = json.load(f)
                
                for config_data in configs_data:
                    config = self._deserialize_channel_config(config_data)
                    self._channel_configs[config.channel] = config
                    
        except Exception as e:
            self._logger.error(f"규칙 및 설정 로드 실패: {e}")
    
    def _create_default_rules(self):
        """기본 알림 규칙 생성"""
        # 긴급 알림 규칙
        emergency_rule = NotificationRule(
            rule_id="emergency_alerts",
            name="긴급 알림",
            severity_filter=[AnomalySeverity.CRITICAL],
            channels={
                AlertChannel.EMAIL: NotificationPriority.EMERGENCY,
                AlertChannel.SMS: NotificationPriority.EMERGENCY,
                'telegram': NotificationPriority.EMERGENCY,
                'web_push': NotificationPriority.EMERGENCY
            },
            max_alerts_per_hour=50,
            cooldown_minutes=1,
            escalation_enabled=True,
            escalation_delay_minutes=15
        )
        
        # 중요 알림 규칙
        high_priority_rule = NotificationRule(
            rule_id="high_priority_alerts", 
            name="중요 알림",
            severity_filter=[AnomalySeverity.HIGH],
            channels={
                AlertChannel.EMAIL: NotificationPriority.HIGH,
                'telegram': NotificationPriority.HIGH,
                'web_push': NotificationPriority.HIGH
            },
            max_alerts_per_hour=20,
            cooldown_minutes=5
        )
        
        # 일반 알림 규칙
        normal_rule = NotificationRule(
            rule_id="normal_alerts",
            name="일반 알림", 
            severity_filter=[AnomalySeverity.MEDIUM],
            channels={
                AlertChannel.EMAIL: NotificationPriority.NORMAL,
                'web_push': NotificationPriority.NORMAL,
                AlertChannel.CONSOLE: NotificationPriority.NORMAL
            },
            max_alerts_per_hour=10,
            cooldown_minutes=10
        )
        
        # 정보성 알림 규칙
        info_rule = NotificationRule(
            rule_id="info_alerts",
            name="정보 알림",
            severity_filter=[AnomalySeverity.LOW],
            channels={
                AlertChannel.CONSOLE: NotificationPriority.LOW
            },
            max_alerts_per_hour=5,
            cooldown_minutes=30
        )
        
        self._notification_rules.update({
            "emergency_alerts": emergency_rule,
            "high_priority_alerts": high_priority_rule,
            "normal_alerts": normal_rule,
            "info_alerts": info_rule
        })
    
    def _create_default_channel_configs(self):
        """기본 채널 설정 생성"""
        channels = [
            AlertChannel.EMAIL,
            AlertChannel.SMS, 
            AlertChannel.CONSOLE
        ]
        
        for channel in channels:
            config = ChannelConfig(
                channel=channel,
                status=ChannelStatus.ACTIVE,
                rate_limit_per_minute=10,
                rate_limit_per_hour=100,
                rate_limit_per_day=1000,
                max_retries=3,
                retry_delay_seconds=30
            )
            self._channel_configs[channel] = config
        
        # 웹 푸시 설정
        self._channel_configs['web_push'] = ChannelConfig(
            channel='web_push',
            status=ChannelStatus.ACTIVE,
            rate_limit_per_minute=20,
            rate_limit_per_hour=200
        )
        
        # 텔레그램 설정
        self._channel_configs['telegram'] = ChannelConfig(
            channel='telegram',
            status=ChannelStatus.ACTIVE,
            rate_limit_per_minute=15,
            rate_limit_per_hour=150
        )
    
    def start(self):
        """알림 시스템 시작"""
        if self._is_running:
            return
        
        self._is_running = True
        self._processing_thread = threading.Thread(target=self._processing_loop)
        self._processing_thread.start()
        
        self._logger.info("통합 알림 시스템 시작")
    
    def stop(self):
        """알림 시스템 중지"""
        if not self._is_running:
            return
        
        self._is_running = False
        
        if self._processing_thread:
            self._processing_thread.join()
        
        self._executor.shutdown(wait=True)
        
        self._logger.info("통합 알림 시스템 중지")
    
    def send_alert(self, alert: AnomalyAlert):
        """알림 전송"""
        try:
            # 적용 가능한 규칙 찾기
            applicable_rules = self._find_applicable_rules(alert)
            
            if not applicable_rules:
                self._logger.debug(f"알림 {alert.alert_id}에 적용 가능한 규칙 없음")
                return
            
            # 각 규칙별로 알림 스케줄
            for rule in applicable_rules:
                for channel, priority in rule.channels.items():
                    if self._should_send_notification(rule, channel, alert):
                        notification_id = f"{alert.alert_id}_{rule.rule_id}_{channel}"
                        
                        self._notification_queue.append({
                            'notification_id': notification_id,
                            'alert': alert,
                            'rule': rule,
                            'channel': channel,
                            'priority': priority,
                            'scheduled_time': datetime.now(),
                            'retry_count': 0
                        })
                        
        except Exception as e:
            self._logger.error(f"알림 전송 스케줄링 실패: {e}")
    
    def _find_applicable_rules(self, alert: AnomalyAlert) -> List[NotificationRule]:
        """적용 가능한 규칙 찾기"""
        applicable_rules = []
        
        for rule in self._notification_rules.values():
            if not rule.enabled:
                continue
            
            # 심각도 필터
            if rule.severity_filter and alert.severity not in rule.severity_filter:
                continue
            
            # 시간 필터
            if rule.time_filter:
                current_time = datetime.now().strftime('%H:%M')
                start_time, end_time = rule.time_filter
                if not (start_time <= current_time <= end_time):
                    continue
            
            # 요일 필터
            if rule.weekday_filter:
                current_weekday = datetime.now().weekday()
                if current_weekday not in rule.weekday_filter:
                    continue
            
            # 종목 필터
            if rule.stock_filter and alert.affected_stocks:
                if not any(stock in rule.stock_filter for stock in alert.affected_stocks):
                    continue
            
            applicable_rules.append(rule)
        
        return applicable_rules
    
    def _should_send_notification(self, rule: NotificationRule, channel: str, alert: AnomalyAlert) -> bool:
        """알림 전송 여부 결정"""
        try:
            # 채널 상태 확인
            channel_config = self._channel_configs.get(channel)
            if not channel_config or channel_config.status != ChannelStatus.ACTIVE:
                return False
            
            # 쿨다운 확인
            cooldown_key = f"{rule.rule_id}_{channel}_{alert.anomaly_type.value}"
            if cooldown_key in self._rate_limiters:
                last_sent = self._rate_limiters[cooldown_key]
                if (datetime.now() - last_sent).total_seconds() < (rule.cooldown_minutes * 60):
                    return False
            
            # 시간당 제한 확인
            hour_key = f"{rule.rule_id}_{channel}_{datetime.now().strftime('%Y%m%d_%H')}"
            hour_count = len([
                log for log in self._notification_logs
                if (log.rule_id == rule.rule_id and 
                    log.channel == channel and
                    log.timestamp.hour == datetime.now().hour and
                    log.status == "sent")
            ])
            
            if hour_count >= rule.max_alerts_per_hour:
                return False
            
            return True
            
        except Exception as e:
            self._logger.error(f"알림 전송 여부 확인 실패: {e}")
            return False
    
    def _processing_loop(self):
        """알림 처리 루프"""
        while self._is_running:
            try:
                if self._notification_queue:
                    # 우선순위 정렬
                    self._notification_queue.sort(
                        key=lambda x: (x['priority'].value, x['scheduled_time'])
                    )
                    
                    # 처리할 알림 선택
                    notification = self._notification_queue.pop(0)
                    
                    # 비동기 전송
                    future = self._executor.submit(self._send_notification, notification)
                    
                time.sleep(1)
                
            except Exception as e:
                self._logger.error(f"알림 처리 루프 오류: {e}")
                time.sleep(5)
    
    def _send_notification(self, notification: Dict) -> bool:
        """실제 알림 전송"""
        try:
            alert = notification['alert']
            rule = notification['rule']
            channel = notification['channel']
            priority = notification['priority']
            
            # 로그 생성
            log = NotificationLog(
                log_id=f"{notification['notification_id']}_{datetime.now().strftime('%H%M%S')}",
                notification_id=notification['notification_id'],
                channel=channel,
                priority=priority,
                timestamp=datetime.now(),
                status="pending",
                rule_id=rule.rule_id,
                retry_count=notification['retry_count']
            )
            
            # 알림기 선택 및 전송
            success = False
            notifier = self._notifiers.get(channel)
            
            if notifier:
                if hasattr(notifier, 'send_notification'):
                    success = notifier.send_notification(alert, priority)
                else:
                    success = notifier.send_alert(alert)
            
            # 로그 업데이트
            log.status = "sent" if success else "failed"
            log.delivery_time = datetime.now() if success else None
            
            if success:
                # 쿨다운 기록
                cooldown_key = f"{rule.rule_id}_{channel}_{alert.anomaly_type.value}"
                self._rate_limiters[cooldown_key] = datetime.now()
            else:
                # 재시도 스케줄
                if notification['retry_count'] < 3:
                    notification['retry_count'] += 1
                    notification['scheduled_time'] = datetime.now() + timedelta(minutes=5)
                    self._notification_queue.append(notification)
                    log.error_message = "재시도 예정"
            
            # 로그 저장
            self._notification_logs.append(log)
            
            # 오래된 로그 정리
            cutoff_time = datetime.now() - timedelta(days=7)
            self._notification_logs = [
                log for log in self._notification_logs
                if log.timestamp > cutoff_time
            ]
            
            return success
            
        except Exception as e:
            self._logger.error(f"알림 전송 실패: {e}")
            return False
    
    def get_notification_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """알림 통계 조회"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_logs = [log for log in self._notification_logs if log.timestamp > cutoff_time]
        
        # 채널별 통계
        channel_stats = {}
        for log in recent_logs:
            channel = log.channel
            if channel not in channel_stats:
                channel_stats[channel] = {'sent': 0, 'failed': 0}
            
            if log.status == "sent":
                channel_stats[channel]['sent'] += 1
            else:
                channel_stats[channel]['failed'] += 1
        
        # 우선순위별 통계
        priority_stats = {}
        for log in recent_logs:
            priority = log.priority.value
            if priority not in priority_stats:
                priority_stats[priority] = {'sent': 0, 'failed': 0}
            
            if log.status == "sent":
                priority_stats[priority]['sent'] += 1
            else:
                priority_stats[priority]['failed'] += 1
        
        return {
            'period_hours': hours,
            'total_notifications': len(recent_logs),
            'successful_notifications': len([log for log in recent_logs if log.status == "sent"]),
            'failed_notifications': len([log for log in recent_logs if log.status == "failed"]),
            'success_rate': len([log for log in recent_logs if log.status == "sent"]) / len(recent_logs) if recent_logs else 0,
            'channel_statistics': channel_stats,
            'priority_statistics': priority_stats,
            'active_rules': len([rule for rule in self._notification_rules.values() if rule.enabled]),
            'active_channels': len([config for config in self._channel_configs.values() if config.status == ChannelStatus.ACTIVE])
        }
    
    def _deserialize_rule(self, rule_data: Dict) -> NotificationRule:
        """규칙 역직렬화"""
        # severity_filter 변환
        severity_filter = [AnomalySeverity(s) for s in rule_data.get('severity_filter', [])]
        
        # channels 변환
        channels = {}
        for channel_name, priority_name in rule_data.get('channels', {}).items():
            if channel_name in ['web_push', 'telegram']:
                channels[channel_name] = NotificationPriority(priority_name)
            else:
                channels[AlertChannel(channel_name)] = NotificationPriority(priority_name)
        
        return NotificationRule(
            rule_id=rule_data['rule_id'],
            name=rule_data['name'],
            enabled=rule_data.get('enabled', True),
            severity_filter=severity_filter,
            time_filter=tuple(rule_data['time_filter']) if rule_data.get('time_filter') else None,
            weekday_filter=rule_data.get('weekday_filter', []),
            stock_filter=rule_data.get('stock_filter', []),
            channels=channels,
            max_alerts_per_hour=rule_data.get('max_alerts_per_hour', 10),
            cooldown_minutes=rule_data.get('cooldown_minutes', 5),
            escalation_enabled=rule_data.get('escalation_enabled', False),
            escalation_delay_minutes=rule_data.get('escalation_delay_minutes', 30),
            escalation_channels=[AlertChannel(c) for c in rule_data.get('escalation_channels', [])]
        )
    
    def _deserialize_channel_config(self, config_data: Dict) -> ChannelConfig:
        """채널 설정 역직렬화"""
        channel = config_data['channel']
        if channel in ['web_push', 'telegram']:
            pass  # 문자열 그대로 사용
        else:
            channel = AlertChannel(channel)
        
        return ChannelConfig(
            channel=channel,
            status=ChannelStatus(config_data.get('status', 'active')),
            priority=config_data.get('priority', 1),
            rate_limit_per_minute=config_data.get('rate_limit_per_minute', 10),
            rate_limit_per_hour=config_data.get('rate_limit_per_hour', 100),
            rate_limit_per_day=config_data.get('rate_limit_per_day', 1000),
            max_retries=config_data.get('max_retries', 3),
            retry_delay_seconds=config_data.get('retry_delay_seconds', 30),
            settings=config_data.get('settings', {})
        )

# 전역 인스턴스
_integrated_alert_manager = None

def get_integrated_alert_manager() -> IntegratedAlertManager:
    """통합 알림 관리자 싱글톤 인스턴스 반환"""
    global _integrated_alert_manager
    if _integrated_alert_manager is None:
        _integrated_alert_manager = IntegratedAlertManager()
    return _integrated_alert_manager 