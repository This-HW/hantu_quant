"""
에러 감지 및 자동 복구 메커니즘

시스템 에러를 자동으로 감지하고 복구 작업을 수행
"""

import traceback
import threading
import time
import json
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
import psutil

from ..utils.log_utils import get_logger

logger = get_logger(__name__)

class ErrorSeverity(Enum):
    """에러 심각도"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class RecoveryAction(Enum):
    """복구 작업 유형"""
    RESTART_PROCESS = "restart_process"
    RESTART_SERVICE = "restart_service"
    CLEAR_CACHE = "clear_cache"
    RESET_CONNECTION = "reset_connection"
    SCALE_UP = "scale_up"
    FAILOVER = "failover"
    MANUAL_INTERVENTION = "manual_intervention"

@dataclass
class ErrorEvent:
    """에러 이벤트"""
    timestamp: datetime
    error_type: str
    severity: ErrorSeverity
    component: str
    message: str
    
    # 컨텍스트 정보
    stack_trace: Optional[str] = None
    system_metrics: Optional[Dict[str, Any]] = None
    affected_users: int = 0
    
    # 복구 정보
    recovery_attempted: bool = False
    recovery_action: Optional[RecoveryAction] = None
    recovery_success: bool = False
    recovery_time: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        result = asdict(self)
        result['timestamp'] = self.timestamp.isoformat()
        result['severity'] = self.severity.value
        if self.recovery_action:
            result['recovery_action'] = self.recovery_action.value
        return result

@dataclass
class RecoveryRule:
    """복구 규칙"""
    name: str
    error_pattern: str  # 에러 패턴 (정규식)
    severity_threshold: ErrorSeverity
    recovery_actions: List[RecoveryAction]
    max_attempts: int = 3
    cooldown_seconds: int = 300  # 5분
    
    # 조건
    conditions: Dict[str, Any] = None
    enabled: bool = True

class ErrorDetector:
    """에러 감지기"""
    
    def __init__(self):
        self._logger = logger
        self._error_patterns = {
            'api_timeout': r'timeout|연결 시간 초과',
            'memory_error': r'OutOfMemoryError|메모리 부족',
            'database_error': r'database|DB|sql',
            'network_error': r'network|연결 실패|connection',
            'file_error': r'FileNotFoundError|파일을 찾을 수 없습니다',
            'permission_error': r'PermissionError|권한',
            'api_rate_limit': r'rate limit|호출 제한',
        }
        
        # 시스템 메트릭 임계값
        self._system_thresholds = {
            'cpu_high': 90.0,
            'memory_high': 95.0,
            'disk_full': 95.0,
            'network_error_rate': 10.0,
        }
        
        self._logger.info("ErrorDetector 초기화 완료")
    
    def classify_error(self, error_message: str, component: str) -> tuple[str, ErrorSeverity]:
        """에러 분류 및 심각도 결정"""
        error_message_lower = error_message.lower()
        
        # 에러 패턴 매칭
        error_type = "unknown"
        for pattern_name, pattern in self._error_patterns.items():
            import re
            if re.search(pattern, error_message_lower):
                error_type = pattern_name
                break
        
        # 심각도 결정
        severity = ErrorSeverity.MEDIUM
        
        if any(keyword in error_message_lower for keyword in ['critical', '치명적', 'fatal']):
            severity = ErrorSeverity.CRITICAL
        elif any(keyword in error_message_lower for keyword in ['memory', '메모리', 'timeout']):
            severity = ErrorSeverity.HIGH
        elif any(keyword in error_message_lower for keyword in ['warning', '경고']):
            severity = ErrorSeverity.LOW
        
        # 컴포넌트별 심각도 조정
        if component in ['api', 'database', 'core']:
            if severity == ErrorSeverity.MEDIUM:
                severity = ErrorSeverity.HIGH
        
        return error_type, severity
    
    def detect_system_anomalies(self) -> List[ErrorEvent]:
        """시스템 이상 상황 감지"""
        anomalies = []
        current_time = datetime.now()
        
        try:
            # CPU 사용률 체크
            cpu_percent = psutil.cpu_percent(interval=1)
            if cpu_percent > self._system_thresholds['cpu_high']:
                anomalies.append(ErrorEvent(
                    timestamp=current_time,
                    error_type="system_cpu_high",
                    severity=ErrorSeverity.HIGH,
                    component="system",
                    message=f"CPU 사용률 과부하: {cpu_percent:.1f}%",
                    system_metrics={'cpu_percent': cpu_percent}
                ))
            
            # 메모리 사용률 체크
            memory = psutil.virtual_memory()
            if memory.percent > self._system_thresholds['memory_high']:
                anomalies.append(ErrorEvent(
                    timestamp=current_time,
                    error_type="system_memory_high",
                    severity=ErrorSeverity.CRITICAL,
                    component="system",
                    message=f"메모리 사용률 위험: {memory.percent:.1f}%",
                    system_metrics={'memory_percent': memory.percent}
                ))
            
            # 디스크 사용률 체크
            disk = psutil.disk_usage('/')
            if disk.percent > self._system_thresholds['disk_full']:
                anomalies.append(ErrorEvent(
                    timestamp=current_time,
                    error_type="system_disk_full",
                    severity=ErrorSeverity.HIGH,
                    component="system",
                    message=f"디스크 공간 부족: {disk.percent:.1f}%",
                    system_metrics={'disk_percent': disk.percent}
                ))
            
        except Exception as e:
            self._logger.error(f"시스템 이상 감지 중 오류: {e}", exc_info=True)
        
        return anomalies

class RecoveryManager:
    """복구 관리자"""

    def __init__(self, db_path: str = "data/error_recovery.db",
                 use_unified_db: bool = True):
        self._logger = logger
        self._db_path = db_path
        self._unified_db_available = False

        # 통합 DB 초기화 시도
        if use_unified_db:
            try:
                from ..database.unified_db import ensure_tables_exist
                ensure_tables_exist()
                self._unified_db_available = True
                self._logger.info("RecoveryManager: 통합 DB 사용")
            except Exception as e:
                self._logger.warning(f"통합 DB 초기화 실패, SQLite 폴백 사용: {e}")
                self._unified_db_available = False

        # 복구 규칙
        self._recovery_rules: List[RecoveryRule] = []

        # 복구 작업 이력
        self._recovery_attempts: Dict[str, List[datetime]] = {}

        # 복구 액션 매핑
        self._recovery_actions = {
            RecoveryAction.RESTART_PROCESS: self._restart_process,
            RecoveryAction.RESTART_SERVICE: self._restart_service,
            RecoveryAction.CLEAR_CACHE: self._clear_cache,
            RecoveryAction.RESET_CONNECTION: self._reset_connection,
            RecoveryAction.SCALE_UP: self._scale_up,
            RecoveryAction.FAILOVER: self._failover,
        }

        # SQLite 데이터베이스 초기화 (폴백용)
        if not self._unified_db_available:
            self._init_database()

        # 기본 복구 규칙 설정
        self._setup_default_rules()

        self._logger.info("RecoveryManager 초기화 완료")
    
    def _init_database(self):
        """데이터베이스 초기화"""
        try:
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
            
            with sqlite3.connect(self._db_path) as conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS error_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        error_type TEXT NOT NULL,
                        severity TEXT NOT NULL,
                        component TEXT NOT NULL,
                        message TEXT NOT NULL,
                        stack_trace TEXT,
                        system_metrics TEXT,
                        affected_users INTEGER,
                        recovery_attempted INTEGER,
                        recovery_action TEXT,
                        recovery_success INTEGER,
                        recovery_time REAL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS recovery_rules (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL UNIQUE,
                        error_pattern TEXT NOT NULL,
                        severity_threshold TEXT NOT NULL,
                        recovery_actions TEXT NOT NULL,
                        max_attempts INTEGER DEFAULT 3,
                        cooldown_seconds INTEGER DEFAULT 300,
                        conditions TEXT,
                        enabled INTEGER DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                conn.commit()
                self._logger.info("에러 복구 데이터베이스 초기화 완료")
                
        except Exception as e:
            self._logger.error(f"데이터베이스 초기화 중 오류: {e}", exc_info=True)
    
    def _setup_default_rules(self):
        """기본 복구 규칙 설정"""
        default_rules = [
            RecoveryRule(
                name="api_timeout_recovery",
                error_pattern="timeout|연결 시간 초과",
                severity_threshold=ErrorSeverity.MEDIUM,
                recovery_actions=[RecoveryAction.RESET_CONNECTION, RecoveryAction.RESTART_SERVICE],
                max_attempts=3,
                cooldown_seconds=300
            ),
            RecoveryRule(
                name="memory_error_recovery",
                error_pattern="memory|메모리",
                severity_threshold=ErrorSeverity.HIGH,
                recovery_actions=[RecoveryAction.CLEAR_CACHE, RecoveryAction.RESTART_PROCESS],
                max_attempts=2,
                cooldown_seconds=600
            ),
            RecoveryRule(
                name="database_error_recovery",
                error_pattern="database|DB",
                severity_threshold=ErrorSeverity.HIGH,
                recovery_actions=[RecoveryAction.RESET_CONNECTION, RecoveryAction.FAILOVER],
                max_attempts=2,
                cooldown_seconds=300
            ),
            RecoveryRule(
                name="system_overload_recovery",
                error_pattern="cpu|memory|disk",
                severity_threshold=ErrorSeverity.CRITICAL,
                recovery_actions=[RecoveryAction.SCALE_UP, RecoveryAction.CLEAR_CACHE],
                max_attempts=1,
                cooldown_seconds=900
            )
        ]
        
        for rule in default_rules:
            self.add_recovery_rule(rule)
    
    def add_recovery_rule(self, rule: RecoveryRule):
        """복구 규칙 추가"""
        self._recovery_rules.append(rule)
        self._save_recovery_rule(rule)
        self._logger.info(f"복구 규칙 추가: {rule.name}")
    
    def _save_recovery_rule(self, rule: RecoveryRule):
        """복구 규칙 데이터베이스 저장"""
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO recovery_rules
                    (name, error_pattern, severity_threshold, recovery_actions,
                     max_attempts, cooldown_seconds, conditions, enabled)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    rule.name, rule.error_pattern, rule.severity_threshold.value,
                    json.dumps([action.value for action in rule.recovery_actions]),
                    rule.max_attempts, rule.cooldown_seconds,
                    json.dumps(rule.conditions) if rule.conditions else None,
                    1 if rule.enabled else 0
                ))
                conn.commit()
                
        except Exception as e:
            self._logger.error(f"복구 규칙 저장 중 오류: {e}", exc_info=True)
    
    def attempt_recovery(self, error_event: ErrorEvent) -> bool:
        """에러 복구 시도"""
        try:
            # 적용 가능한 복구 규칙 찾기
            applicable_rule = None
            for rule in self._recovery_rules:
                if not rule.enabled:
                    continue
                
                # 패턴 매칭
                import re
                if re.search(rule.error_pattern, error_event.message, re.IGNORECASE):
                    # 심각도 확인
                    if self._compare_severity(error_event.severity, rule.severity_threshold):
                        applicable_rule = rule
                        break
            
            if not applicable_rule:
                self._logger.debug(f"적용 가능한 복구 규칙 없음: {error_event.error_type}")
                return False
            
            # 쿨다운 시간 확인
            rule_key = applicable_rule.name
            if not self._can_attempt_recovery(rule_key, applicable_rule.cooldown_seconds, applicable_rule.max_attempts):
                self._logger.debug(f"복구 규칙 {rule_key} 쿨다운 중")
                return False
            
            # 복구 시도
            recovery_success = False
            recovery_start_time = time.time()
            
            for action in applicable_rule.recovery_actions:
                try:
                    self._logger.info(f"복구 작업 시도: {action.value} for {error_event.error_type}")
                    
                    if action in self._recovery_actions:
                        success = self._recovery_actions[action](error_event)
                        if success:
                            recovery_success = True
                            error_event.recovery_action = action
                            break
                    else:
                        self._logger.warning(f"구현되지 않은 복구 작업: {action.value}")
                        
                except Exception as e:
                    self._logger.error(f"복구 작업 {action.value} 실행 중 오류: {e}", exc_info=True)
                    continue
            
            recovery_time = time.time() - recovery_start_time
            
            # 복구 결과 업데이트
            error_event.recovery_attempted = True
            error_event.recovery_success = recovery_success
            error_event.recovery_time = recovery_time
            
            # 시도 기록
            self._record_recovery_attempt(rule_key)
            
            if recovery_success:
                self._logger.info(f"복구 성공: {error_event.error_type} ({recovery_time:.2f}초)")
            else:
                self._logger.warning(f"복구 실패: {error_event.error_type}")
            
            return recovery_success
            
        except Exception as e:
            self._logger.error(f"복구 시도 중 오류: {e}", exc_info=True)
            return False
    
    def _compare_severity(self, event_severity: ErrorSeverity, threshold: ErrorSeverity) -> bool:
        """심각도 비교"""
        severity_order = {
            ErrorSeverity.LOW: 1,
            ErrorSeverity.MEDIUM: 2,
            ErrorSeverity.HIGH: 3,
            ErrorSeverity.CRITICAL: 4
        }
        
        return severity_order[event_severity] >= severity_order[threshold]
    
    def _can_attempt_recovery(self, rule_key: str, cooldown_seconds: int, max_attempts: int) -> bool:
        """복구 시도 가능 여부 확인"""
        if rule_key not in self._recovery_attempts:
            return True
        
        attempts = self._recovery_attempts[rule_key]
        cutoff_time = datetime.now() - timedelta(seconds=cooldown_seconds)
        
        # 쿨다운 시간 내 시도 횟수 확인
        recent_attempts = [attempt for attempt in attempts if attempt > cutoff_time]
        
        return len(recent_attempts) < max_attempts
    
    def _record_recovery_attempt(self, rule_key: str):
        """복구 시도 기록"""
        if rule_key not in self._recovery_attempts:
            self._recovery_attempts[rule_key] = []
        
        self._recovery_attempts[rule_key].append(datetime.now())
        
        # 오래된 기록 정리 (24시간 이전)
        cutoff_time = datetime.now() - timedelta(hours=24)
        self._recovery_attempts[rule_key] = [
            attempt for attempt in self._recovery_attempts[rule_key]
            if attempt > cutoff_time
        ]
    
    # 복구 액션 구현
    def _restart_process(self, error_event: ErrorEvent) -> bool:
        """프로세스 재시작"""
        try:
            self._logger.info(f"프로세스 재시작 시도: {error_event.component}")
            # 실제 구현에서는 해당 프로세스를 재시작
            # 여기서는 시뮬레이션
            time.sleep(2)
            return True
        except Exception as e:
            self._logger.error(f"프로세스 재시작 중 오류: {e}", exc_info=True)
            return False
    
    def _restart_service(self, error_event: ErrorEvent) -> bool:
        """서비스 재시작"""
        try:
            self._logger.info(f"서비스 재시작 시도: {error_event.component}")
            # 실제 구현에서는 systemctl restart 등 사용
            time.sleep(3)
            return True
        except Exception as e:
            self._logger.error(f"서비스 재시작 중 오류: {e}", exc_info=True)
            return False
    
    def _clear_cache(self, error_event: ErrorEvent) -> bool:
        """캐시 정리"""
        try:
            self._logger.info("캐시 정리 시도")
            # 실제 구현에서는 메모리 캐시, 파일 캐시 등 정리
            import gc
            gc.collect()
            time.sleep(1)
            return True
        except Exception as e:
            self._logger.error(f"캐시 정리 중 오류: {e}", exc_info=True)
            return False
    
    def _reset_connection(self, error_event: ErrorEvent) -> bool:
        """연결 재설정"""
        try:
            self._logger.info(f"연결 재설정 시도: {error_event.component}")
            # 실제 구현에서는 데이터베이스, API 연결 등 재설정
            time.sleep(2)
            return True
        except Exception as e:
            self._logger.error(f"연결 재설정 중 오류: {e}", exc_info=True)
            return False
    
    def _scale_up(self, error_event: ErrorEvent) -> bool:
        """스케일 업"""
        try:
            self._logger.info("시스템 리소스 확장 시도")
            # 실제 구현에서는 프로세스 수 증가, 메모리 할당 등
            time.sleep(3)
            return True
        except Exception as e:
            self._logger.error(f"스케일 업 중 오류: {e}", exc_info=True)
            return False
    
    def _failover(self, error_event: ErrorEvent) -> bool:
        """페일오버"""
        try:
            self._logger.info(f"페일오버 시도: {error_event.component}")
            # 실제 구현에서는 백업 시스템으로 전환
            time.sleep(5)
            return True
        except Exception as e:
            self._logger.error(f"페일오버 중 오류: {e}", exc_info=True)
            return False

class ErrorRecoverySystem:
    """통합 에러 감지 및 복구 시스템"""
    
    def __init__(self, db_path: str = "data/error_recovery.db"):
        self._logger = logger
        self._db_path = db_path
        
        # 컴포넌트 초기화
        self._detector = ErrorDetector()
        self._recovery_manager = RecoveryManager(db_path)
        
        # 모니터링 상태
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        
        # 에러 핸들러 콜백
        self._error_handlers: List[Callable] = []
        
        self._logger.info("ErrorRecoverySystem 초기화 완료")
    
    def add_error_handler(self, handler: Callable[[ErrorEvent], None]):
        """에러 핸들러 추가"""
        self._error_handlers.append(handler)
    
    def report_error(self, error: Union[Exception, str], component: str, 
                    severity: Optional[ErrorSeverity] = None,
                    affected_users: int = 0) -> ErrorEvent:
        """에러 보고 및 자동 복구 시도
        
        Args:
            error: 에러 객체 또는 메시지
            component: 발생 컴포넌트
            severity: 심각도 (자동 분류되지 않는 경우)
            affected_users: 영향받은 사용자 수
            
        Returns:
            ErrorEvent 객체
        """
        try:
            # 에러 정보 추출
            if isinstance(error, Exception):
                error_message = str(error)
                stack_trace = traceback.format_exc()
            else:
                error_message = error
                stack_trace = None
            
            # 에러 분류 및 심각도 결정
            if severity is None:
                error_type, severity = self._detector.classify_error(error_message, component)
            else:
                error_type, _ = self._detector.classify_error(error_message, component)
            
            # 시스템 메트릭 수집
            system_metrics = self._collect_system_metrics()
            
            # ErrorEvent 생성
            error_event = ErrorEvent(
                timestamp=datetime.now(),
                error_type=error_type,
                severity=severity,
                component=component,
                message=error_message,
                stack_trace=stack_trace,
                system_metrics=system_metrics,
                affected_users=affected_users
            )
            
            # 데이터베이스 저장
            self._save_error_event(error_event)
            
            # 에러 핸들러 호출
            for handler in self._error_handlers:
                try:
                    handler(error_event)
                except Exception as e:
                    self._logger.error(f"에러 핸들러 실행 중 오류: {e}", exc_info=True)
            
            # 자동 복구 시도
            if severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
                self._recovery_manager.attempt_recovery(error_event)
                self._save_error_event(error_event)  # 복구 결과 업데이트
            
            self._logger.error(f"에러 보고: {component} - {error_message} (심각도: {severity.value})", exc_info=True)
            
            return error_event
            
        except Exception as e:
            self._logger.error(f"에러 보고 처리 중 오류: {e}", exc_info=True)
            raise
    
    def _collect_system_metrics(self) -> Dict[str, Any]:
        """시스템 메트릭 수집"""
        try:
            return {
                'cpu_percent': psutil.cpu_percent(),
                'memory_percent': psutil.virtual_memory().percent,
                'disk_percent': psutil.disk_usage('/').percent,
                'process_count': len(psutil.pids()),
                'timestamp': datetime.now().isoformat()
            }
        except Exception:
            return {}
    
    def _save_error_event(self, error_event: ErrorEvent):
        """에러 이벤트 저장"""
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO error_events
                    (timestamp, error_type, severity, component, message,
                     stack_trace, system_metrics, affected_users,
                     recovery_attempted, recovery_action, recovery_success, recovery_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    error_event.timestamp.isoformat(), error_event.error_type,
                    error_event.severity.value, error_event.component, error_event.message,
                    error_event.stack_trace, json.dumps(error_event.system_metrics),
                    error_event.affected_users, 1 if error_event.recovery_attempted else 0,
                    error_event.recovery_action.value if error_event.recovery_action else None,
                    1 if error_event.recovery_success else 0, error_event.recovery_time
                ))
                conn.commit()
                
        except Exception as e:
            self._logger.error(f"에러 이벤트 저장 중 오류: {e}", exc_info=True)
    
    def start_monitoring(self, interval_seconds: int = 60):
        """자동 모니터링 시작"""
        if self._monitoring:
            self._logger.warning("모니터링이 이미 실행 중입니다.")
            return
        
        self._monitoring = True
        
        def monitoring_loop():
            while self._monitoring:
                try:
                    # 시스템 이상 감지
                    anomalies = self._detector.detect_system_anomalies()
                    
                    for anomaly in anomalies:
                        self.report_error(
                            anomaly.message, 
                            anomaly.component,
                            anomaly.severity,
                            0
                        )
                    
                except Exception as e:
                    self._logger.error(f"모니터링 중 오류: {e}", exc_info=True)
                
                time.sleep(interval_seconds)
        
        self._monitor_thread = threading.Thread(target=monitoring_loop, daemon=True)
        self._monitor_thread.start()
        
        self._logger.info("에러 모니터링 시작")
    
    def stop_monitoring(self):
        """모니터링 중지"""
        if not self._monitoring:
            return
        
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        
        self._logger.info("에러 모니터링 중지")
    
    def get_error_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """에러 통계 조회"""
        try:
            cutoff_time = (datetime.now() - timedelta(hours=hours)).isoformat()
            
            with sqlite3.connect(self._db_path) as conn:
                # 전체 에러 수
                cursor = conn.execute(
                    'SELECT COUNT(*) FROM error_events WHERE timestamp >= ?',
                    (cutoff_time,)
                )
                total_errors = cursor.fetchone()[0]
                
                # 심각도별 에러 수
                cursor = conn.execute('''
                    SELECT severity, COUNT(*) FROM error_events 
                    WHERE timestamp >= ? GROUP BY severity
                ''', (cutoff_time,))
                severity_stats = dict(cursor.fetchall())
                
                # 컴포넌트별 에러 수
                cursor = conn.execute('''
                    SELECT component, COUNT(*) FROM error_events 
                    WHERE timestamp >= ? GROUP BY component
                ''', (cutoff_time,))
                component_stats = dict(cursor.fetchall())
                
                # 복구 성공률
                cursor = conn.execute('''
                    SELECT 
                        COUNT(*) as total_recovery_attempts,
                        SUM(recovery_success) as successful_recoveries
                    FROM error_events 
                    WHERE timestamp >= ? AND recovery_attempted = 1
                ''', (cutoff_time,))
                
                recovery_data = cursor.fetchone()
                recovery_rate = 0
                if recovery_data and recovery_data[0] > 0:
                    recovery_rate = (recovery_data[1] / recovery_data[0]) * 100
                
                return {
                    'period_hours': hours,
                    'total_errors': total_errors,
                    'severity_distribution': severity_stats,
                    'component_distribution': component_stats,
                    'recovery_attempts': recovery_data[0] if recovery_data else 0,
                    'successful_recoveries': recovery_data[1] if recovery_data else 0,
                    'recovery_success_rate': recovery_rate
                }
                
        except Exception as e:
            self._logger.error(f"에러 통계 조회 중 오류: {e}", exc_info=True)
            return {}

# 글로벌 인스턴스
_error_recovery_system: Optional[ErrorRecoverySystem] = None

def get_error_recovery_system() -> ErrorRecoverySystem:
    """에러 복구 시스템 인스턴스 반환 (싱글톤)"""
    global _error_recovery_system
    if _error_recovery_system is None:
        _error_recovery_system = ErrorRecoverySystem()
    return _error_recovery_system

def report_error(error: Union[Exception, str], component: str = "unknown",
                severity: Optional[ErrorSeverity] = None, affected_users: int = 0) -> ErrorEvent:
    """에러 보고 헬퍼 함수"""
    return get_error_recovery_system().report_error(error, component, severity, affected_users) 