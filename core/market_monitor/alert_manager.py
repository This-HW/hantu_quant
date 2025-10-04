"""
시스템 상태 알림 시스템 (텔레그램 통합)

시스템 상태를 모니터링하고 텔레그램을 통해 실시간 알림을 전송
"""

import asyncio
import json
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
import requests

from ..utils.logging import get_logger

logger = get_logger(__name__)

class AlertLevel(Enum):
    """알림 레벨"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class AlertCategory(Enum):
    """알림 카테고리"""
    SYSTEM = "system"
    TRADING = "trading"
    API = "api"
    PERFORMANCE = "performance"
    SECURITY = "security"
    DATA_QUALITY = "data_quality"

@dataclass
class SystemAlert:
    """시스템 알림"""
    alert_id: str
    timestamp: datetime
    level: AlertLevel
    category: AlertCategory
    title: str
    message: str
    
    # 컨텍스트 정보
    component: str
    metrics: Dict[str, Any] = None
    
    # 알림 설정
    urgent: bool = False
    actionable: bool = False
    auto_resolve: bool = False
    
    # 처리 상태
    sent: bool = False
    acknowledged: bool = False
    resolved: bool = False
    
    def __post_init__(self):
        if self.metrics is None:
            self.metrics = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        result = asdict(self)
        result['timestamp'] = self.timestamp.isoformat()
        result['level'] = self.level.value
        result['category'] = self.category.value
        return result

@dataclass
class TelegramConfig:
    """텔레그램 설정"""
    bot_token: str
    chat_id: str
    enabled: bool = True
    
    # 알림 필터
    min_level: AlertLevel = AlertLevel.WARNING
    categories: List[AlertCategory] = None
    
    # 발송 제한
    rate_limit: int = 10  # 분당 최대 메시지 수
    quiet_hours: tuple = None  # (시작시간, 종료시간) 예: (22, 8)
    
    def __post_init__(self):
        if self.categories is None:
            self.categories = list(AlertCategory)

class TelegramNotifier:
    """텔레그램 알림 전송기"""
    
    def __init__(self, config: TelegramConfig):
        """초기화
        
        Args:
            config: 텔레그램 설정
        """
        self._logger = logger
        self._config = config
        
        # 메시지 발송 이력 (rate limiting용)
        self._message_history: List[datetime] = []
        
        # 메시지 템플릿
        self._message_templates = {
            AlertLevel.INFO: "ℹ️ {title}\n\n{message}",
            AlertLevel.WARNING: "⚠️ {title}\n\n{message}\n\n컴포넌트: {component}",
            AlertLevel.ERROR: "❌ {title}\n\n{message}\n\n컴포넌트: {component}\n시간: {timestamp}",
            AlertLevel.CRITICAL: "🚨 CRITICAL: {title}\n\n{message}\n\n컴포넌트: {component}\n시간: {timestamp}\n\n즉시 확인이 필요합니다!"
        }
        
        # 이모지 매핑
        self._category_emojis = {
            AlertCategory.SYSTEM: "⚙️",
            AlertCategory.TRADING: "📈",
            AlertCategory.API: "🔌", 
            AlertCategory.PERFORMANCE: "⚡",
            AlertCategory.SECURITY: "🔒",
            AlertCategory.DATA_QUALITY: "📊"
        }
        
        self._logger.info("TelegramNotifier 초기화 완료")
    
    def send_alert(self, alert: SystemAlert) -> bool:
        """알림 전송
        
        Args:
            alert: 시스템 알림
            
        Returns:
            전송 성공 여부
        """
        try:
            # 설정 확인
            if not self._config.enabled:
                return False
            
            # 레벨 필터링
            if not self._should_send_alert(alert):
                return False
            
            # Rate limiting 확인
            if not self._check_rate_limit():
                self._logger.warning("텔레그램 메시지 발송 제한 초과")
                return False
            
            # 조용한 시간 확인
            if self._is_quiet_hours() and alert.level != AlertLevel.CRITICAL:
                self._logger.debug("조용한 시간대로 인해 알림 발송 지연")
                return False
            
            # 메시지 생성
            message = self._format_message(alert)
            
            # 텔레그램 API 호출
            success = self._send_telegram_message(message, alert.urgent)
            
            if success:
                self._record_message_sent()
                alert.sent = True
                self._logger.info(f"텔레그램 알림 전송 완료: {alert.title}")
            else:
                self._logger.error(f"텔레그램 알림 전송 실패: {alert.title}")
            
            return success
            
        except Exception as e:
            self._logger.error(f"텔레그램 알림 전송 중 오류: {e}")
            return False
    
    def _should_send_alert(self, alert: SystemAlert) -> bool:
        """알림 전송 여부 확인"""
        # 레벨 확인
        level_priorities = {
            AlertLevel.INFO: 1,
            AlertLevel.WARNING: 2,
            AlertLevel.ERROR: 3,
            AlertLevel.CRITICAL: 4
        }
        
        if level_priorities[alert.level] < level_priorities[self._config.min_level]:
            return False
        
        # 카테고리 확인
        if alert.category not in self._config.categories:
            return False
        
        return True
    
    def _check_rate_limit(self) -> bool:
        """Rate limit 확인"""
        now = datetime.now()
        cutoff_time = now - timedelta(minutes=1)
        
        # 최근 1분간 메시지 수 확인
        recent_messages = [
            timestamp for timestamp in self._message_history
            if timestamp > cutoff_time
        ]
        
        return len(recent_messages) < self._config.rate_limit
    
    def _is_quiet_hours(self) -> bool:
        """조용한 시간대 확인"""
        if not self._config.quiet_hours:
            return False
        
        start_hour, end_hour = self._config.quiet_hours
        current_hour = datetime.now().hour
        
        if start_hour <= end_hour:
            return start_hour <= current_hour <= end_hour
        else:  # 밤 시간대 (예: 22시-8시)
            return current_hour >= start_hour or current_hour <= end_hour
    
    def _format_message(self, alert: SystemAlert) -> str:
        """메시지 형식 지정"""
        template = self._message_templates.get(alert.level, self._message_templates[AlertLevel.INFO])
        
        # 카테고리 이모지 추가
        category_emoji = self._category_emojis.get(alert.category, "")
        title_with_emoji = f"{category_emoji} {alert.title}"
        
        # 메트릭 정보 추가
        metrics_text = ""
        if alert.metrics:
            metrics_lines = []
            for key, value in alert.metrics.items():
                if isinstance(value, float):
                    metrics_lines.append(f"• {key}: {value:.2f}")
                else:
                    metrics_lines.append(f"• {key}: {value}")
            
            if metrics_lines:
                metrics_text = f"\n\n📊 지표:\n" + "\n".join(metrics_lines)
        
        message = template.format(
            title=title_with_emoji,
            message=alert.message + metrics_text,
            component=alert.component,
            timestamp=alert.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        )
        
        # 액션 가능한 알림인 경우 추가 정보
        if alert.actionable:
            message += "\n\n🔧 조치가 필요합니다."
        
        return message
    
    def _send_telegram_message(self, message: str, urgent: bool = False) -> bool:
        """텔레그램 메시지 전송"""
        try:
            url = f"https://api.telegram.org/bot{self._config.bot_token}/sendMessage"
            
            data = {
                'chat_id': self._config.chat_id,
                'text': message,
                'parse_mode': 'HTML' if urgent else 'Markdown',
                'disable_notification': not urgent
            }
            
            response = requests.post(url, data=data, timeout=10)
            
            if response.status_code == 200:
                return True
            else:
                self._logger.error(f"텔레그램 API 오류: {response.status_code} - {response.text}")
                return False
                
        except requests.RequestException as e:
            self._logger.error(f"텔레그램 API 요청 중 오류: {e}")
            return False
    
    def _record_message_sent(self):
        """메시지 발송 기록"""
        self._message_history.append(datetime.now())
        
        # 오래된 기록 정리 (최근 1시간만 유지)
        cutoff_time = datetime.now() - timedelta(hours=1)
        self._message_history = [
            timestamp for timestamp in self._message_history
            if timestamp > cutoff_time
        ]
    
    def test_connection(self) -> bool:
        """텔레그램 연결 테스트"""
        try:
            test_message = "🔧 한투 퀀트 시스템 알림 테스트\n\n텔레그램 연결이 정상적으로 작동합니다."
            return self._send_telegram_message(test_message)
        except Exception as e:
            self._logger.error(f"텔레그램 연결 테스트 중 오류: {e}")
            return False

class SystemAlertManager:
    """시스템 알림 관리자"""
    
    def __init__(self, db_path: str = "data/system_alerts.db"):
        """초기화
        
        Args:
            db_path: 알림 데이터베이스 경로
        """
        self._logger = logger
        self._db_path = db_path
        
        # 텔레그램 설정
        self._telegram_config: Optional[TelegramConfig] = None
        self._telegram_notifier: Optional[TelegramNotifier] = None
        
        # 알림 큐
        self._alert_queue: List[SystemAlert] = []
        self._queue_lock = threading.Lock()
        
        # 알림 처리 스레드
        self._processing = False
        self._processor_thread: Optional[threading.Thread] = None
        
        # 알림 규칙
        self._alert_rules: Dict[str, Dict] = {}
        
        # 중복 알림 방지
        self._recent_alerts: Dict[str, datetime] = {}
        self._dedupe_window = timedelta(minutes=5)  # 5분 내 중복 방지
        
        # 데이터베이스 초기화
        self._init_database()
        
        # 기본 알림 규칙 설정
        self._setup_default_rules()
        
        self._logger.info("SystemAlertManager 초기화 완료")
    
    def _init_database(self):
        """데이터베이스 초기화"""
        try:
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
            
            with sqlite3.connect(self._db_path) as conn:
                # 시스템 알림 테이블
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS system_alerts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        alert_id TEXT NOT NULL UNIQUE,
                        timestamp TEXT NOT NULL,
                        level TEXT NOT NULL,
                        category TEXT NOT NULL,
                        title TEXT NOT NULL,
                        message TEXT NOT NULL,
                        component TEXT NOT NULL,
                        metrics TEXT,
                        urgent INTEGER DEFAULT 0,
                        actionable INTEGER DEFAULT 0,
                        auto_resolve INTEGER DEFAULT 0,
                        sent INTEGER DEFAULT 0,
                        acknowledged INTEGER DEFAULT 0,
                        resolved INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # 알림 설정 테이블
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS alert_settings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        setting_name TEXT NOT NULL UNIQUE,
                        setting_value TEXT NOT NULL,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # 알림 통계 테이블
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS alert_statistics (
                        date TEXT PRIMARY KEY,
                        total_alerts INTEGER DEFAULT 0,
                        critical_alerts INTEGER DEFAULT 0,
                        error_alerts INTEGER DEFAULT 0,
                        warning_alerts INTEGER DEFAULT 0,
                        info_alerts INTEGER DEFAULT 0,
                        sent_alerts INTEGER DEFAULT 0,
                        acknowledged_alerts INTEGER DEFAULT 0,
                        resolved_alerts INTEGER DEFAULT 0
                    )
                ''')
                
                conn.commit()
                self._logger.info("시스템 알림 데이터베이스 초기화 완료")
                
        except Exception as e:
            self._logger.error(f"데이터베이스 초기화 중 오류: {e}")
    
    def _setup_default_rules(self):
        """기본 알림 규칙 설정"""
        self._alert_rules = {
            'cpu_high': {
                'threshold': 80.0,
                'level': AlertLevel.WARNING,
                'category': AlertCategory.SYSTEM,
                'message_template': "CPU 사용률이 {value:.1f}%로 높습니다."
            },
            'memory_high': {
                'threshold': 85.0,
                'level': AlertLevel.ERROR,
                'category': AlertCategory.SYSTEM,
                'message_template': "메모리 사용률이 {value:.1f}%로 위험합니다."
            },
            'disk_full': {
                'threshold': 90.0,
                'level': AlertLevel.CRITICAL,
                'category': AlertCategory.SYSTEM,
                'message_template': "디스크 사용률이 {value:.1f}%로 매우 위험합니다."
            },
            'api_error_rate': {
                'threshold': 10.0,
                'level': AlertLevel.ERROR,
                'category': AlertCategory.API,
                'message_template': "API 에러율이 {value:.1f}%로 높습니다."
            },
            'trading_loss': {
                'threshold': -5.0,
                'level': AlertLevel.WARNING,
                'category': AlertCategory.TRADING,
                'message_template': "트레이딩 손실이 {value:.2f}%입니다."
            }
        }
    
    def configure_telegram(self, bot_token: str, chat_id: str, **kwargs):
        """텔레그램 설정
        
        Args:
            bot_token: 텔레그램 봇 토큰
            chat_id: 채팅 ID
            **kwargs: 추가 설정 옵션
        """
        try:
            self._telegram_config = TelegramConfig(
                bot_token=bot_token,
                chat_id=chat_id,
                **kwargs
            )
            
            self._telegram_notifier = TelegramNotifier(self._telegram_config)
            
            # 연결 테스트
            if self._telegram_notifier.test_connection():
                self._logger.info("텔레그램 알림 설정 완료")
                return True
            else:
                self._logger.error("텔레그램 연결 테스트 실패")
                return False
                
        except Exception as e:
            self._logger.error(f"텔레그램 설정 중 오류: {e}")
            return False
    
    def create_alert(self, level: AlertLevel, category: AlertCategory,
                    title: str, message: str, component: str,
                    metrics: Dict[str, Any] = None,
                    urgent: bool = False, actionable: bool = False) -> SystemAlert:
        """알림 생성
        
        Args:
            level: 알림 레벨
            category: 알림 카테고리
            title: 알림 제목
            message: 알림 메시지
            component: 발생 컴포넌트
            metrics: 관련 지표
            urgent: 긴급 여부
            actionable: 조치 필요 여부
            
        Returns:
            생성된 알림
        """
        # 알림 ID 생성
        alert_id = f"{category.value}_{component}_{int(time.time())}"
        
        # 중복 알림 확인
        dedup_key = f"{category.value}_{component}_{title}"
        if self._is_duplicate_alert(dedup_key):
            self._logger.debug(f"중복 알림 스킵: {title}")
            return None
        
        # 알림 객체 생성
        alert = SystemAlert(
            alert_id=alert_id,
            timestamp=datetime.now(),
            level=level,
            category=category,
            title=title,
            message=message,
            component=component,
            metrics=metrics or {},
            urgent=urgent or level == AlertLevel.CRITICAL,
            actionable=actionable,
            auto_resolve=False
        )
        
        # 중복 방지 기록
        self._recent_alerts[dedup_key] = alert.timestamp
        
        # 알림 큐에 추가
        with self._queue_lock:
            self._alert_queue.append(alert)
        
        self._logger.info(f"알림 생성: {level.value} - {title}")
        
        return alert
    
    def _is_duplicate_alert(self, dedup_key: str) -> bool:
        """중복 알림 확인"""
        if dedup_key in self._recent_alerts:
            last_time = self._recent_alerts[dedup_key]
            if datetime.now() - last_time < self._dedupe_window:
                return True
        
        return False
    
    def send_system_metric_alert(self, metric_name: str, value: float, component: str):
        """시스템 지표 기반 알림 전송
        
        Args:
            metric_name: 지표명
            value: 지표값
            component: 컴포넌트명
        """
        if metric_name in self._alert_rules:
            rule = self._alert_rules[metric_name]
            
            if value >= rule['threshold']:
                message = rule['message_template'].format(value=value)
                
                self.create_alert(
                    level=rule['level'],
                    category=rule['category'],
                    title=f"{metric_name.replace('_', ' ').title()} 알림",
                    message=message,
                    component=component,
                    metrics={metric_name: value},
                    actionable=True
                )
    
    def start_processing(self):
        """알림 처리 시작"""
        if self._processing:
            self._logger.warning("알림 처리가 이미 실행 중입니다.")
            return
        
        self._processing = True
        
        def processing_loop():
            while self._processing:
                try:
                    # 큐에서 알림 처리
                    alerts_to_process = []
                    
                    with self._queue_lock:
                        if self._alert_queue:
                            alerts_to_process = self._alert_queue.copy()
                            self._alert_queue.clear()
                    
                    for alert in alerts_to_process:
                        self._process_alert(alert)
                    
                    # 중복 방지 캐시 정리
                    self._cleanup_dedup_cache()
                    
                except Exception as e:
                    self._logger.error(f"알림 처리 중 오류: {e}")
                
                time.sleep(1)  # 1초 간격으로 처리
        
        self._processor_thread = threading.Thread(target=processing_loop, daemon=True)
        self._processor_thread.start()
        
        self._logger.info("알림 처리 시작")
    
    def stop_processing(self):
        """알림 처리 중지"""
        if not self._processing:
            return
        
        self._processing = False
        if self._processor_thread:
            self._processor_thread.join(timeout=5)
        
        self._logger.info("알림 처리 중지")
    
    def _process_alert(self, alert: SystemAlert):
        """개별 알림 처리"""
        try:
            # 데이터베이스 저장
            self._save_alert(alert)
            
            # 텔레그램 전송
            if self._telegram_notifier:
                self._telegram_notifier.send_alert(alert)
            
            # 통계 업데이트
            self._update_statistics(alert)
            
        except Exception as e:
            self._logger.error(f"알림 처리 중 오류: {e}")
    
    def _save_alert(self, alert: SystemAlert):
        """알림 저장"""
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO system_alerts
                    (alert_id, timestamp, level, category, title, message,
                     component, metrics, urgent, actionable, auto_resolve,
                     sent, acknowledged, resolved)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    alert.alert_id, alert.timestamp.isoformat(),
                    alert.level.value, alert.category.value,
                    alert.title, alert.message, alert.component,
                    json.dumps(alert.metrics, ensure_ascii=False),
                    1 if alert.urgent else 0, 1 if alert.actionable else 0,
                    1 if alert.auto_resolve else 0,
                    1 if alert.sent else 0, 1 if alert.acknowledged else 0,
                    1 if alert.resolved else 0
                ))
                conn.commit()
                
        except Exception as e:
            self._logger.error(f"알림 저장 중 오류: {e}")
    
    def _update_statistics(self, alert: SystemAlert):
        """알림 통계 업데이트"""
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            
            with sqlite3.connect(self._db_path) as conn:
                # 오늘 통계 조회
                cursor = conn.execute(
                    'SELECT * FROM alert_statistics WHERE date = ?',
                    (today,)
                )
                stats = cursor.fetchone()
                
                if not stats:
                    # 새 통계 생성
                    conn.execute('''
                        INSERT INTO alert_statistics
                        (date, total_alerts, critical_alerts, error_alerts,
                         warning_alerts, info_alerts, sent_alerts)
                        VALUES (?, 1, ?, ?, ?, ?, ?)
                    ''', (
                        today,
                        1 if alert.level == AlertLevel.CRITICAL else 0,
                        1 if alert.level == AlertLevel.ERROR else 0,
                        1 if alert.level == AlertLevel.WARNING else 0,
                        1 if alert.level == AlertLevel.INFO else 0,
                        1 if alert.sent else 0
                    ))
                else:
                    # 기존 통계 업데이트
                    level_column = f"{alert.level.value}_alerts"
                    conn.execute(f'''
                        UPDATE alert_statistics 
                        SET total_alerts = total_alerts + 1,
                            {level_column} = {level_column} + 1,
                            sent_alerts = sent_alerts + ?
                        WHERE date = ?
                    ''', (1 if alert.sent else 0, today))
                
                conn.commit()
                
        except Exception as e:
            self._logger.error(f"알림 통계 업데이트 중 오류: {e}")
    
    def _cleanup_dedup_cache(self):
        """중복 방지 캐시 정리"""
        try:
            cutoff_time = datetime.now() - self._dedupe_window
            
            keys_to_remove = [
                key for key, timestamp in self._recent_alerts.items()
                if timestamp < cutoff_time
            ]
            
            for key in keys_to_remove:
                del self._recent_alerts[key]
                
        except Exception as e:
            self._logger.error(f"중복 방지 캐시 정리 중 오류: {e}")
    
    def get_alert_statistics(self, days: int = 7) -> Dict[str, Any]:
        """알림 통계 조회"""
        try:
            cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.execute('''
                    SELECT 
                        SUM(total_alerts) as total,
                        SUM(critical_alerts) as critical,
                        SUM(error_alerts) as error,
                        SUM(warning_alerts) as warning,
                        SUM(info_alerts) as info,
                        SUM(sent_alerts) as sent
                    FROM alert_statistics
                    WHERE date >= ?
                ''', (cutoff_date,))
                
                stats = cursor.fetchone()
                
                return {
                    'period_days': days,
                    'total_alerts': stats[0] or 0,
                    'critical_alerts': stats[1] or 0,
                    'error_alerts': stats[2] or 0,
                    'warning_alerts': stats[3] or 0,
                    'info_alerts': stats[4] or 0,
                    'sent_alerts': stats[5] or 0,
                    'delivery_rate': (stats[5] / stats[0] * 100) if stats[0] > 0 else 0
                }
                
        except Exception as e:
            self._logger.error(f"알림 통계 조회 중 오류: {e}")
            return {}

# 글로벌 인스턴스
_system_alert_manager: Optional[SystemAlertManager] = None

def get_system_alert_manager() -> SystemAlertManager:
    """시스템 알림 관리자 인스턴스 반환 (싱글톤)"""
    global _system_alert_manager
    if _system_alert_manager is None:
        _system_alert_manager = SystemAlertManager()
    return _system_alert_manager

def send_alert(level: AlertLevel, category: AlertCategory, title: str,
              message: str, component: str, **kwargs):
    """알림 전송 헬퍼 함수"""
    get_system_alert_manager().create_alert(
        level, category, title, message, component, **kwargs
    ) 