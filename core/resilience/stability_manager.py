"""
시스템 안정성 관리자

시스템의 안정성을 모니터링하고 장애 시 자동 복구하는 시스템
"""

import threading
import time
import queue
import traceback
import pickle
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import functools
import signal
import atexit

from ..utils.logging import get_logger

logger = get_logger(__name__)

class FailureType(Enum):
    """장애 유형"""
    CONNECTION_ERROR = "connection_error"
    TIMEOUT_ERROR = "timeout_error"
    MEMORY_ERROR = "memory_error"
    PROCESSING_ERROR = "processing_error"
    API_ERROR = "api_error"
    DATA_ERROR = "data_error"
    SYSTEM_ERROR = "system_error"
    UNKNOWN_ERROR = "unknown_error"

class RecoveryStrategy(Enum):
    """복구 전략"""
    RETRY = "retry"                     # 재시도
    FALLBACK = "fallback"               # 대체 방법
    CIRCUIT_BREAKER = "circuit_breaker" # 회로 차단기
    GRACEFUL_DEGRADATION = "graceful_degradation"  # 점진적 성능 저하
    RESTART = "restart"                 # 재시작
    SKIP = "skip"                       # 건너뛰기

class SystemState(Enum):
    """시스템 상태"""
    HEALTHY = "healthy"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    RECOVERING = "recovering"
    MAINTENANCE = "maintenance"

@dataclass
class FailureRecord:
    """장애 기록"""
    failure_id: str
    timestamp: datetime
    failure_type: FailureType
    component: str
    error_message: str
    stack_trace: str
    
    # 복구 정보
    recovery_strategy: Optional[RecoveryStrategy] = None
    recovery_attempts: int = 0
    recovery_successful: bool = False
    recovery_time: Optional[datetime] = None
    
    # 영향도
    affected_functions: List[str] = None
    user_impact: str = ""
    
    # 메타데이터
    severity: int = 1  # 1(낮음) ~ 5(높음)
    tags: List[str] = None

@dataclass
class CircuitBreakerState:
    """회로 차단기 상태"""
    component: str
    state: str  # CLOSED, OPEN, HALF_OPEN
    failure_count: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    failure_threshold: int = 5
    timeout_seconds: int = 60
    half_open_max_calls: int = 3

@dataclass
class HealthCheck:
    """헬스 체크"""
    component: str
    check_function: Callable
    interval_seconds: int = 60
    timeout_seconds: int = 10
    critical: bool = False
    last_check: Optional[datetime] = None
    last_result: bool = True
    consecutive_failures: int = 0

class RetryDecorator:
    """재시도 데코레이터"""
    
    def __init__(self, max_attempts: int = 3, delay: float = 1.0, 
                 backoff: float = 2.0, exceptions: tuple = (Exception,)):
        self.max_attempts = max_attempts
        self.delay = delay
        self.backoff = backoff
        self.exceptions = exceptions
    
    def __call__(self, func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            delay = self.delay
            
            for attempt in range(self.max_attempts):
                try:
                    return func(*args, **kwargs)
                except self.exceptions as e:
                    last_exception = e
                    if attempt == self.max_attempts - 1:
                        break
                    
                    logger.warning(f"함수 {func.__name__} 실행 실패 (시도 {attempt + 1}/{self.max_attempts}): {e}")
                    time.sleep(delay)
                    delay *= self.backoff
            
            logger.error(f"함수 {func.__name__} 최종 실패: {last_exception}")
            raise last_exception
        
        return wrapper

def retry(max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0, 
          exceptions: tuple = (Exception,)):
    """재시도 데코레이터 팩토리"""
    return RetryDecorator(max_attempts, delay, backoff, exceptions)

class CircuitBreaker:
    """회로 차단기"""
    
    def __init__(self, component: str, failure_threshold: int = 5, 
                 timeout_seconds: int = 60, half_open_max_calls: int = 3):
        self.state = CircuitBreakerState(
            component=component,
            state="CLOSED",
            failure_threshold=failure_threshold,
            timeout_seconds=timeout_seconds,
            half_open_max_calls=half_open_max_calls
        )
        self._lock = threading.Lock()
        self._call_count = 0
    
    def __call__(self, func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return self.call(func, *args, **kwargs)
        return wrapper
    
    def call(self, func, *args, **kwargs):
        """함수 호출 (회로 차단기 적용)"""
        with self._lock:
            if self.state.state == "OPEN":
                if self._should_attempt_reset():
                    self.state.state = "HALF_OPEN"
                    self._call_count = 0
                else:
                    raise Exception(f"회로 차단기 열림: {self.state.component}")
            
            if self.state.state == "HALF_OPEN":
                if self._call_count >= self.state.half_open_max_calls:
                    raise Exception(f"회로 차단기 반열림 최대 호출 초과: {self.state.component}")
                self._call_count += 1
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e
    
    def _should_attempt_reset(self) -> bool:
        """재시도 가능 여부 확인"""
        if not self.state.last_failure_time:
            return True
        
        time_since_failure = datetime.now() - self.state.last_failure_time
        return time_since_failure.total_seconds() >= self.state.timeout_seconds
    
    def _on_success(self):
        """성공 시 처리"""
        with self._lock:
            if self.state.state == "HALF_OPEN":
                self.state.state = "CLOSED"
            
            self.state.failure_count = 0
            self.state.last_success_time = datetime.now()
            self._call_count = 0
    
    def _on_failure(self):
        """실패 시 처리"""
        with self._lock:
            self.state.failure_count += 1
            self.state.last_failure_time = datetime.now()
            
            if self.state.failure_count >= self.state.failure_threshold:
                self.state.state = "OPEN"
                logger.warning(f"회로 차단기 열림: {self.state.component}")

class FallbackManager:
    """대체 방법 관리자"""
    
    def __init__(self):
        self._fallbacks = {}
        self._logger = logger
    
    def register_fallback(self, component: str, fallback_func: Callable):
        """대체 방법 등록"""
        self._fallbacks[component] = fallback_func
        self._logger.info(f"대체 방법 등록: {component}")
    
    def execute_with_fallback(self, component: str, primary_func: Callable, *args, **kwargs):
        """주 함수 실행 및 실패 시 대체 방법 실행"""
        try:
            return primary_func(*args, **kwargs)
        except Exception as e:
            self._logger.warning(f"{component} 주 함수 실패, 대체 방법 실행: {e}")
            
            if component in self._fallbacks:
                try:
                    return self._fallbacks[component](*args, **kwargs)
                except Exception as fallback_error:
                    self._logger.error(f"{component} 대체 방법도 실패: {fallback_error}")
                    raise fallback_error
            else:
                self._logger.error(f"{component} 대체 방법 없음")
                raise e

class HealthMonitor:
    """헬스 모니터"""
    
    def __init__(self):
        self._health_checks = {}
        self._monitoring = False
        self._monitor_thread = None
        self._logger = logger
    
    def register_health_check(self, component: str, check_function: Callable,
                             interval_seconds: int = 60, timeout_seconds: int = 10,
                             critical: bool = False):
        """헬스 체크 등록"""
        health_check = HealthCheck(
            component=component,
            check_function=check_function,
            interval_seconds=interval_seconds,
            timeout_seconds=timeout_seconds,
            critical=critical
        )
        
        self._health_checks[component] = health_check
        self._logger.info(f"헬스 체크 등록: {component}")
    
    def start_monitoring(self):
        """헬스 모니터링 시작"""
        if self._monitoring:
            return
        
        self._monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self._monitor_thread.start()
        
        self._logger.info("헬스 모니터링 시작")
    
    def stop_monitoring(self):
        """헬스 모니터링 중지"""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join()
        
        self._logger.info("헬스 모니터링 중지")
    
    def _monitoring_loop(self):
        """모니터링 루프"""
        while self._monitoring:
            try:
                for component, health_check in self._health_checks.items():
                    if self._should_check(health_check):
                        self._perform_health_check(health_check)
                
                time.sleep(10)  # 10초마다 체크
                
            except Exception as e:
                self._logger.error(f"헬스 모니터링 루프 오류: {e}")
                time.sleep(10)
    
    def _should_check(self, health_check: HealthCheck) -> bool:
        """체크 필요 여부 확인"""
        if not health_check.last_check:
            return True
        
        time_since_check = datetime.now() - health_check.last_check
        return time_since_check.total_seconds() >= health_check.interval_seconds
    
    def _perform_health_check(self, health_check: HealthCheck):
        """헬스 체크 실행"""
        try:
            # 타임아웃 적용
            result = self._run_with_timeout(
                health_check.check_function, 
                health_check.timeout_seconds
            )
            
            # 성공
            health_check.last_result = True
            health_check.consecutive_failures = 0
            health_check.last_check = datetime.now()
            
        except Exception as e:
            # 실패
            health_check.last_result = False
            health_check.consecutive_failures += 1
            health_check.last_check = datetime.now()
            
            self._logger.warning(
                f"헬스 체크 실패 ({health_check.component}): {e} "
                f"(연속 실패: {health_check.consecutive_failures})"
            )
            
            # 임계 컴포넌트의 연속 실패 시 알림
            if health_check.critical and health_check.consecutive_failures >= 3:
                self._logger.error(f"임계 컴포넌트 {health_check.component} 연속 실패")
    
    def _run_with_timeout(self, func: Callable, timeout_seconds: int):
        """타임아웃과 함께 함수 실행"""
        result_queue = queue.Queue()
        exception_queue = queue.Queue()
        
        def target():
            try:
                result = func()
                result_queue.put(result)
            except Exception as e:
                exception_queue.put(e)
        
        thread = threading.Thread(target=target)
        thread.start()
        thread.join(timeout_seconds)
        
        if thread.is_alive():
            # 타임아웃
            raise TimeoutError(f"헬스 체크 타임아웃 ({timeout_seconds}초)")
        
        if not exception_queue.empty():
            raise exception_queue.get()
        
        if not result_queue.empty():
            return result_queue.get()
        
        return True
    
    def get_health_status(self) -> Dict[str, Any]:
        """헬스 상태 조회"""
        status = {
            'overall_health': 'healthy',
            'components': {},
            'critical_failures': 0,
            'total_components': len(self._health_checks)
        }
        
        critical_failures = 0
        
        for component, health_check in self._health_checks.items():
            component_status = {
                'healthy': health_check.last_result,
                'last_check': health_check.last_check.isoformat() if health_check.last_check else None,
                'consecutive_failures': health_check.consecutive_failures,
                'critical': health_check.critical
            }
            
            status['components'][component] = component_status
            
            if health_check.critical and not health_check.last_result:
                critical_failures += 1
        
        status['critical_failures'] = critical_failures
        
        # 전체 상태 결정
        if critical_failures > 0:
            status['overall_health'] = 'critical'
        elif any(not hc.last_result for hc in self._health_checks.values()):
            status['overall_health'] = 'warning'
        
        return status

class StabilityManager:
    """시스템 안정성 관리자"""
    
    def __init__(self, data_dir: str = "data/stability"):
        """
        초기화
        
        Args:
            data_dir: 안정성 데이터 저장 디렉토리
        """
        self._logger = logger
        self._data_dir = data_dir
        
        # 디렉토리 생성
        os.makedirs(data_dir, exist_ok=True)
        
        # 컴포넌트 초기화
        self._circuit_breakers = {}
        self._fallback_manager = FallbackManager()
        self._health_monitor = HealthMonitor()
        
        # 장애 기록
        self._failure_records = []
        self._system_state = SystemState.HEALTHY
        
        # 복구 전략
        self._recovery_strategies = {}
        
        # 설정
        self._auto_recovery_enabled = True
        self._graceful_shutdown_enabled = True
        
        # 기본 설정
        self._setup_default_strategies()
        self._setup_signal_handlers()
        
        self._logger.info("안정성 관리자 초기화 완료")
    
    def _setup_default_strategies(self):
        """기본 복구 전략 설정"""
        self._recovery_strategies = {
            FailureType.CONNECTION_ERROR: [RecoveryStrategy.RETRY, RecoveryStrategy.FALLBACK],
            FailureType.TIMEOUT_ERROR: [RecoveryStrategy.RETRY, RecoveryStrategy.CIRCUIT_BREAKER],
            FailureType.MEMORY_ERROR: [RecoveryStrategy.GRACEFUL_DEGRADATION, RecoveryStrategy.RESTART],
            FailureType.PROCESSING_ERROR: [RecoveryStrategy.RETRY, RecoveryStrategy.SKIP],
            FailureType.API_ERROR: [RecoveryStrategy.CIRCUIT_BREAKER, RecoveryStrategy.FALLBACK],
            FailureType.DATA_ERROR: [RecoveryStrategy.FALLBACK, RecoveryStrategy.SKIP],
            FailureType.SYSTEM_ERROR: [RecoveryStrategy.RESTART],
            FailureType.UNKNOWN_ERROR: [RecoveryStrategy.RETRY, RecoveryStrategy.FALLBACK]
        }
    
    def _setup_signal_handlers(self):
        """시그널 핸들러 설정"""
        if self._graceful_shutdown_enabled:
            signal.signal(signal.SIGTERM, self._graceful_shutdown)
            signal.signal(signal.SIGINT, self._graceful_shutdown)
            atexit.register(self._cleanup)
    
    def _graceful_shutdown(self, signum, frame):
        """점진적 종료"""
        self._logger.info(f"점진적 종료 시작 (시그널: {signum})")
        
        try:
            # 헬스 모니터링 중지
            self._health_monitor.stop_monitoring()
            
            # 현재 상태 저장
            self._save_state()
            
            self._logger.info("점진적 종료 완료")
            
        except Exception as e:
            self._logger.error(f"점진적 종료 실패: {e}")
    
    def _cleanup(self):
        """정리 작업"""
        try:
            self._save_state()
            self._logger.info("정리 작업 완료")
        except Exception as e:
            self._logger.error(f"정리 작업 실패: {e}")
    
    def register_component(self, component: str, 
                          circuit_breaker_config: Dict[str, Any] = None,
                          fallback_function: Callable = None,
                          health_check_function: Callable = None):
        """컴포넌트 등록"""
        try:
            # 회로 차단기 등록
            if circuit_breaker_config:
                cb_config = circuit_breaker_config
                circuit_breaker = CircuitBreaker(
                    component=component,
                    failure_threshold=cb_config.get('failure_threshold', 5),
                    timeout_seconds=cb_config.get('timeout_seconds', 60),
                    half_open_max_calls=cb_config.get('half_open_max_calls', 3)
                )
                self._circuit_breakers[component] = circuit_breaker
            
            # 대체 방법 등록
            if fallback_function:
                self._fallback_manager.register_fallback(component, fallback_function)
            
            # 헬스 체크 등록
            if health_check_function:
                self._health_monitor.register_health_check(
                    component=component,
                    check_function=health_check_function,
                    interval_seconds=60,
                    critical=True
                )
            
            self._logger.info(f"컴포넌트 등록 완료: {component}")
            
        except Exception as e:
            self._logger.error(f"컴포넌트 등록 실패 ({component}): {e}")
    
    def start_monitoring(self):
        """안정성 모니터링 시작"""
        try:
            self._health_monitor.start_monitoring()
            self._logger.info("안정성 모니터링 시작")
            
        except Exception as e:
            self._logger.error(f"안정성 모니터링 시작 실패: {e}")
    
    def stop_monitoring(self):
        """안정성 모니터링 중지"""
        try:
            self._health_monitor.stop_monitoring()
            self._logger.info("안정성 모니터링 중지")
            
        except Exception as e:
            self._logger.error(f"안정성 모니터링 중지 실패: {e}")
    
    def record_failure(self, component: str, error: Exception, 
                      failure_type: FailureType = None, severity: int = 3):
        """장애 기록"""
        try:
            # 장애 유형 추론
            if not failure_type:
                failure_type = self._infer_failure_type(error)
            
            # 장애 기록 생성
            failure_record = FailureRecord(
                failure_id=f"{component}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(self._failure_records)}",
                timestamp=datetime.now(),
                failure_type=failure_type,
                component=component,
                error_message=str(error),
                stack_trace=traceback.format_exc(),
                severity=severity,
                tags=[component, failure_type.value]
            )
            
            self._failure_records.append(failure_record)
            
            # 시스템 상태 업데이트
            self._update_system_state()
            
            # 자동 복구 시도
            if self._auto_recovery_enabled:
                self._attempt_recovery(failure_record)
            
            # 장애 기록 저장
            self._save_failure_record(failure_record)
            
            self._logger.warning(f"장애 기록: {component} - {failure_type.value} - {error}")
            
        except Exception as e:
            self._logger.error(f"장애 기록 실패: {e}")
    
    def _infer_failure_type(self, error: Exception) -> FailureType:
        """에러로부터 장애 유형 추론"""
        error_str = str(error).lower()
        error_type = type(error).__name__.lower()
        
        if 'connection' in error_str or 'connect' in error_str:
            return FailureType.CONNECTION_ERROR
        elif 'timeout' in error_str or 'time' in error_str:
            return FailureType.TIMEOUT_ERROR
        elif 'memory' in error_str or 'memoryerror' in error_type:
            return FailureType.MEMORY_ERROR
        elif 'api' in error_str or 'http' in error_str:
            return FailureType.API_ERROR
        elif 'data' in error_str or 'parse' in error_str:
            return FailureType.DATA_ERROR
        elif 'system' in error_str or 'os' in error_str:
            return FailureType.SYSTEM_ERROR
        else:
            return FailureType.UNKNOWN_ERROR
    
    def _update_system_state(self):
        """시스템 상태 업데이트"""
        try:
            # 최근 1시간 내 장애
            recent_failures = [
                f for f in self._failure_records
                if (datetime.now() - f.timestamp).total_seconds() < 3600
            ]
            
            # 임계 장애 개수
            critical_failures = [f for f in recent_failures if f.severity >= 4]
            high_failures = [f for f in recent_failures if f.severity >= 3]
            
            # 상태 결정
            if len(critical_failures) > 0:
                self._system_state = SystemState.CRITICAL
            elif len(high_failures) > 5:
                self._system_state = SystemState.ERROR
            elif len(recent_failures) > 10:
                self._system_state = SystemState.WARNING
            else:
                self._system_state = SystemState.HEALTHY
                
        except Exception as e:
            self._logger.error(f"시스템 상태 업데이트 실패: {e}")
    
    def _attempt_recovery(self, failure_record: FailureRecord):
        """복구 시도"""
        try:
            strategies = self._recovery_strategies.get(failure_record.failure_type, [])
            
            for strategy in strategies:
                try:
                    success = self._execute_recovery_strategy(strategy, failure_record)
                    
                    if success:
                        failure_record.recovery_strategy = strategy
                        failure_record.recovery_successful = True
                        failure_record.recovery_time = datetime.now()
                        
                        self._logger.info(f"복구 성공: {failure_record.component} - {strategy.value}")
                        break
                    
                except Exception as e:
                    self._logger.error(f"복구 전략 실행 실패 ({strategy.value}): {e}")
                    continue
            
            failure_record.recovery_attempts = len(strategies)
            
        except Exception as e:
            self._logger.error(f"복구 시도 실패: {e}")
    
    def _execute_recovery_strategy(self, strategy: RecoveryStrategy, 
                                  failure_record: FailureRecord) -> bool:
        """복구 전략 실행"""
        try:
            if strategy == RecoveryStrategy.RETRY:
                # 재시도는 애플리케이션 레벨에서 처리
                return False
            
            elif strategy == RecoveryStrategy.CIRCUIT_BREAKER:
                # 회로 차단기는 이미 적용되어 있음
                return True
            
            elif strategy == RecoveryStrategy.FALLBACK:
                # 대체 방법은 애플리케이션 레벨에서 처리
                return True
            
            elif strategy == RecoveryStrategy.GRACEFUL_DEGRADATION:
                # 점진적 성능 저하
                self._apply_graceful_degradation(failure_record.component)
                return True
            
            elif strategy == RecoveryStrategy.RESTART:
                # 컴포넌트 재시작 (제한적)
                return self._restart_component(failure_record.component)
            
            elif strategy == RecoveryStrategy.SKIP:
                # 건너뛰기
                return True
            
            return False
            
        except Exception as e:
            self._logger.error(f"복구 전략 실행 오류: {e}")
            return False
    
    def _apply_graceful_degradation(self, component: str):
        """점진적 성능 저하 적용"""
        # 성능 저하 로직 구현 (애플리케이션별)
        self._logger.info(f"점진적 성능 저하 적용: {component}")
    
    def _restart_component(self, component: str) -> bool:
        """컴포넌트 재시작"""
        try:
            # 컴포넌트별 재시작 로직 (제한적)
            self._logger.info(f"컴포넌트 재시작 시도: {component}")
            return True
            
        except Exception as e:
            self._logger.error(f"컴포넌트 재시작 실패: {e}")
            return False
    
    def _save_failure_record(self, failure_record: FailureRecord):
        """장애 기록 저장"""
        try:
            timestamp_str = failure_record.timestamp.strftime('%Y%m%d')
            filename = f"failure_records_{timestamp_str}.json"
            filepath = os.path.join(self._data_dir, filename)
            
            # 기존 기록 로드
            records = []
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    records = json.load(f)
            
            # 새 기록 추가
            record_dict = asdict(failure_record)
            record_dict['timestamp'] = failure_record.timestamp.isoformat()
            if failure_record.recovery_time:
                record_dict['recovery_time'] = failure_record.recovery_time.isoformat()
            
            records.append(record_dict)
            
            # 파일 저장
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(records, f, ensure_ascii=False, indent=2, default=str)
                
        except Exception as e:
            self._logger.error(f"장애 기록 저장 실패: {e}")
    
    def _save_state(self):
        """현재 상태 저장"""
        try:
            state_file = os.path.join(self._data_dir, "system_state.json")
            
            state = {
                'timestamp': datetime.now().isoformat(),
                'system_state': self._system_state.value,
                'failure_count_24h': len([
                    f for f in self._failure_records
                    if (datetime.now() - f.timestamp).total_seconds() < 86400
                ]),
                'health_status': self._health_monitor.get_health_status(),
                'circuit_breaker_states': {
                    component: asdict(cb.state)
                    for component, cb in self._circuit_breakers.items()
                }
            }
            
            with open(state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2, default=str)
                
        except Exception as e:
            self._logger.error(f"상태 저장 실패: {e}")
    
    def get_circuit_breaker(self, component: str) -> Optional[CircuitBreaker]:
        """회로 차단기 조회"""
        return self._circuit_breakers.get(component)
    
    def get_fallback_manager(self) -> FallbackManager:
        """대체 방법 관리자 조회"""
        return self._fallback_manager
    
    def get_stability_report(self) -> Dict[str, Any]:
        """안정성 리포트 생성"""
        try:
            # 최근 24시간 통계
            recent_failures = [
                f for f in self._failure_records
                if (datetime.now() - f.timestamp).total_seconds() < 86400
            ]
            
            # 장애 유형별 통계
            failure_by_type = {}
            for failure in recent_failures:
                type_name = failure.failure_type.value
                failure_by_type[type_name] = failure_by_type.get(type_name, 0) + 1
            
            # 컴포넌트별 통계
            failure_by_component = {}
            for failure in recent_failures:
                component = failure.component
                failure_by_component[component] = failure_by_component.get(component, 0) + 1
            
            # 복구 성공률
            recovery_attempts = [f for f in recent_failures if f.recovery_attempts > 0]
            recovery_success_rate = (
                sum(1 for f in recovery_attempts if f.recovery_successful) / len(recovery_attempts)
                if recovery_attempts else 0
            )
            
            report = {
                'system_state': self._system_state.value,
                'total_failures_24h': len(recent_failures),
                'failure_by_type': failure_by_type,
                'failure_by_component': failure_by_component,
                'recovery_success_rate': recovery_success_rate,
                'health_status': self._health_monitor.get_health_status(),
                'circuit_breakers': len(self._circuit_breakers),
                'auto_recovery_enabled': self._auto_recovery_enabled,
                'monitoring_active': True,
                'timestamp': datetime.now().isoformat()
            }
            
            return report
            
        except Exception as e:
            self._logger.error(f"안정성 리포트 생성 실패: {e}")
            return {'error': str(e)}

# 전역 인스턴스
_stability_manager = None

def get_stability_manager() -> StabilityManager:
    """안정성 관리자 싱글톤 인스턴스 반환"""
    global _stability_manager
    if _stability_manager is None:
        _stability_manager = StabilityManager()
    return _stability_manager 