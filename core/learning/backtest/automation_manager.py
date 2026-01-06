"""
백테스트 자동화 관리자

전략 변경 감지, 자동 백테스트 실행, 결과 검증 및 승인 프로세스 관리
"""

import os
import json
import threading
import time
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Set
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
import queue
import schedule

from ...utils.logging import get_logger
from .backtest_engine import BacktestEngine, BacktestConfig, BacktestResult
from .validation_system import ValidationSystem, ValidationResult, ValidationCriteria
from ..optimization.parameter_manager import ParameterManager, ParameterSet

logger = get_logger(__name__)

class AutomationStatus(Enum):
    """자동화 상태"""
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"

class TriggerType(Enum):
    """트리거 타입"""
    PARAMETER_CHANGE = "parameter_change"
    SCHEDULE = "schedule"
    MANUAL = "manual"
    PERFORMANCE_THRESHOLD = "performance_threshold"

class ActionType(Enum):
    """액션 타입"""
    RUN_BACKTEST = "run_backtest"
    VALIDATE_RESULT = "validate_result"
    AUTO_APPROVE = "auto_approve"
    SEND_NOTIFICATION = "send_notification"

@dataclass
class AutomationConfig:
    """자동화 설정"""
    # 모니터링 설정
    monitor_interval: int = 60                  # 모니터링 주기 (초)
    max_concurrent_backtests: int = 3           # 최대 동시 백테스트 수
    
    # 자동 실행 설정
    auto_validation: bool = True                # 자동 검증 여부
    auto_approval: bool = False                 # 자동 승인 여부
    auto_deployment: bool = False               # 자동 배포 여부
    
    # 알림 설정
    notification_enabled: bool = True           # 알림 활성화
    notification_channels: Optional[List[str]] = None     # 알림 채널
    
    # 백테스트 설정
    default_backtest_config: Optional[BacktestConfig] = None
    validation_criteria: Optional[ValidationCriteria] = None
    
    # 필터링 설정
    min_parameter_change_threshold: float = 0.05 # 최소 파라미터 변경 임계값
    strategy_whitelist: Optional[Set[str]] = None         # 허용 전략 목록
    strategy_blacklist: Optional[Set[str]] = None         # 차단 전략 목록
    
    def __post_init__(self):
        if self.notification_channels is None:
            self.notification_channels = ["telegram"]
        if self.default_backtest_config is None:
            self.default_backtest_config = BacktestConfig()
        if self.validation_criteria is None:
            self.validation_criteria = ValidationCriteria()
        if self.strategy_whitelist is None:
            self.strategy_whitelist = set()
        if self.strategy_blacklist is None:
            self.strategy_blacklist = set()

@dataclass
class AutomationRule:
    """자동화 규칙"""
    rule_id: str
    name: str
    description: str
    trigger_type: TriggerType
    trigger_config: Dict[str, Any]
    actions: List[ActionType]
    enabled: bool = True
    created_at: Optional[datetime] = None
    last_triggered: Optional[datetime] = None
    trigger_count: int = 0
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()

@dataclass
class AutomationJob:
    """자동화 작업"""
    job_id: str
    rule_id: str
    strategy_name: str
    parameters: Dict[str, Any]
    trigger_type: TriggerType
    status: str = "pending"
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    backtest_result: Optional[BacktestResult] = None
    validation_result: Optional[ValidationResult] = None
    error_message: Optional[str] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()

class AutomationManager:
    """백테스트 자동화 관리자"""
    
    def __init__(self,
                 backtest_engine: BacktestEngine,
                 validation_system: ValidationSystem,
                 parameter_manager: ParameterManager,
                 config: Optional[AutomationConfig] = None,
                 data_dir: str = "data/automation"):
        """
        초기화
        
        Args:
            backtest_engine: 백테스트 엔진
            validation_system: 검증 시스템
            parameter_manager: 파라미터 관리자
            config: 자동화 설정
            data_dir: 자동화 데이터 저장 디렉토리
        """
        self._logger = logger
        self._backtest_engine = backtest_engine
        self._validation_system = validation_system
        self._parameter_manager = parameter_manager
        self._config = config or AutomationConfig()
        self._data_dir = Path(data_dir)
        
        # 디렉토리 생성
        self._data_dir.mkdir(parents=True, exist_ok=True)
        
        # 상태 관리
        self._status = AutomationStatus.STOPPED
        self._automation_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        # 규칙 및 작업 관리
        self._rules: Dict[str, AutomationRule] = {}
        self._job_queue = queue.Queue()
        self._active_jobs: Dict[str, AutomationJob] = {}
        self._job_history: List[AutomationJob] = []
        
        # 모니터링 상태
        self._last_parameter_hashes: Dict[str, str] = {}
        self._performance_history: Dict[str, List[float]] = {}
        
        # 통계
        self._total_jobs = 0
        self._successful_jobs = 0
        self._failed_jobs = 0
        
        # 알림 콜백
        self._notification_callbacks: List[Callable] = []
        
        self._logger.info("백테스트 자동화 관리자 초기화 완료")
    
    def start_automation(self) -> bool:
        """자동화 시작"""
        if self._status == AutomationStatus.RUNNING:
            self._logger.warning("자동화가 이미 실행 중입니다")
            return False
        
        try:
            self._status = AutomationStatus.RUNNING
            self._stop_event.clear()
            
            # 자동화 스레드 시작
            self._automation_thread = threading.Thread(
                target=self._automation_loop,
                name="BacktestAutomation"
            )
            self._automation_thread.start()
            
            # 기본 규칙 추가 (처음 시작 시)
            if not self._rules:
                self._add_default_rules()
            
            self._logger.info("백테스트 자동화 시작")
            self._send_notification("백테스트 자동화 시스템이 시작되었습니다.")
            
            return True
            
        except Exception as e:
            self._status = AutomationStatus.ERROR
            self._logger.error(f"자동화 시작 실패: {e}", exc_info=True)
            return False
    
    def stop_automation(self) -> bool:
        """자동화 중지"""
        if self._status == AutomationStatus.STOPPED:
            return True
        
        try:
            self._logger.info("백테스트 자동화 중지 중...")
            
            # 중지 신호
            self._stop_event.set()
            self._status = AutomationStatus.STOPPED
            
            # 스레드 종료 대기
            if self._automation_thread and self._automation_thread.is_alive():
                self._automation_thread.join(timeout=10)
            
            self._logger.info("백테스트 자동화 중지 완료")
            self._send_notification("백테스트 자동화 시스템이 중지되었습니다.")
            
            return True
            
        except Exception as e:
            self._logger.error(f"자동화 중지 실패: {e}", exc_info=True)
            return False
    
    def pause_automation(self) -> bool:
        """자동화 일시정지"""
        if self._status == AutomationStatus.RUNNING:
            self._status = AutomationStatus.PAUSED
            self._logger.info("백테스트 자동화 일시정지")
            return True
        return False
    
    def resume_automation(self) -> bool:
        """자동화 재개"""
        if self._status == AutomationStatus.PAUSED:
            self._status = AutomationStatus.RUNNING
            self._logger.info("백테스트 자동화 재개")
            return True
        return False
    
    def add_rule(self, rule: AutomationRule) -> bool:
        """자동화 규칙 추가"""
        try:
            self._rules[rule.rule_id] = rule
            self._logger.info(f"자동화 규칙 추가: {rule.name} [{rule.rule_id}]")
            
            # 규칙 저장
            self._save_rules()
            return True
            
        except Exception as e:
            self._logger.error(f"규칙 추가 실패: {e}", exc_info=True)
            return False
    
    def remove_rule(self, rule_id: str) -> bool:
        """자동화 규칙 제거"""
        if rule_id in self._rules:
            removed_rule = self._rules.pop(rule_id)
            self._logger.info(f"자동화 규칙 제거: {removed_rule.name} [{rule_id}]")
            self._save_rules()
            return True
        return False
    
    def enable_rule(self, rule_id: str) -> bool:
        """규칙 활성화"""
        if rule_id in self._rules:
            self._rules[rule_id].enabled = True
            self._save_rules()
            return True
        return False
    
    def disable_rule(self, rule_id: str) -> bool:
        """규칙 비활성화"""
        if rule_id in self._rules:
            self._rules[rule_id].enabled = False
            self._save_rules()
            return True
        return False
    
    def trigger_manual_backtest(self, 
                               strategy_name: str, 
                               parameters: Dict[str, Any],
                               backtest_config: Optional[BacktestConfig] = None) -> str:
        """수동 백테스트 트리거"""
        job_id = f"manual_{strategy_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        job = AutomationJob(
            job_id=job_id,
            rule_id="manual",
            strategy_name=strategy_name,
            parameters=parameters,
            trigger_type=TriggerType.MANUAL
        )
        
        self._job_queue.put(job)
        self._logger.info(f"수동 백테스트 작업 큐에 추가: {job_id}")
        
        return job_id
    
    def get_job_status(self, job_id: str) -> Optional[str]:
        """작업 상태 조회"""
        # 활성 작업 확인
        if job_id in self._active_jobs:
            return self._active_jobs[job_id].status
        
        # 히스토리 확인
        for job in self._job_history:
            if job.job_id == job_id:
                return job.status
        
        return None
    
    def get_job_result(self, job_id: str) -> Optional[AutomationJob]:
        """작업 결과 조회"""
        # 활성 작업 확인
        if job_id in self._active_jobs:
            return self._active_jobs[job_id]
        
        # 히스토리 확인
        for job in self._job_history:
            if job.job_id == job_id:
                return job
        
        return None
    
    def add_notification_callback(self, callback: Callable[[str, Dict[str, Any]], None]):
        """알림 콜백 추가"""
        self._notification_callbacks.append(callback)
    
    def _automation_loop(self):
        """자동화 메인 루프"""
        self._logger.info("자동화 루프 시작")
        
        while not self._stop_event.is_set():
            try:
                if self._status == AutomationStatus.RUNNING:
                    # 규칙 평가 및 트리거
                    self._evaluate_rules()
                    
                    # 작업 처리
                    self._process_jobs()
                    
                    # 활성 작업 모니터링
                    self._monitor_active_jobs()
                
                # 대기
                self._stop_event.wait(self._config.monitor_interval)
                
            except Exception as e:
                self._logger.error(f"자동화 루프 오류: {e}", exc_info=True)
                self._status = AutomationStatus.ERROR
                time.sleep(60)  # 오류 시 1분 대기
                self._status = AutomationStatus.RUNNING
        
        self._logger.info("자동화 루프 종료")
    
    def _evaluate_rules(self):
        """규칙 평가 및 트리거"""
        for rule in self._rules.values():
            if not rule.enabled:
                continue
            
            try:
                if self._should_trigger_rule(rule):
                    self._trigger_rule(rule)
                    rule.last_triggered = datetime.now()
                    rule.trigger_count += 1
                    
            except Exception as e:
                self._logger.error(f"규칙 평가 실패 [{rule.rule_id}]: {e}", exc_info=True)
    
    def _should_trigger_rule(self, rule: AutomationRule) -> bool:
        """규칙 트리거 여부 판단"""
        trigger_type = rule.trigger_type
        trigger_config = rule.trigger_config
        
        if trigger_type == TriggerType.PARAMETER_CHANGE:
            return self._check_parameter_changes(trigger_config)
        
        elif trigger_type == TriggerType.SCHEDULE:
            return self._check_schedule_trigger(rule, trigger_config)
        
        elif trigger_type == TriggerType.PERFORMANCE_THRESHOLD:
            return self._check_performance_threshold(trigger_config)
        
        return False
    
    def _check_parameter_changes(self, config: Dict[str, Any]) -> bool:
        """파라미터 변경 확인"""
        strategy_name = config.get('strategy_name')
        if not strategy_name:
            return False
        
        try:
            # 현재 파라미터 해시 계산
            current_params = self._parameter_manager.load_best_parameters(strategy_name)
            if not current_params:
                return False
            
            current_hash = hashlib.md5(
                json.dumps(current_params.parameters, sort_keys=True).encode()
            ).hexdigest()
            
            # 이전 해시와 비교
            last_hash = self._last_parameter_hashes.get(strategy_name)
            
            if last_hash is None:
                # 처음 실행
                self._last_parameter_hashes[strategy_name] = current_hash
                return False
            
            if current_hash != last_hash:
                self._last_parameter_hashes[strategy_name] = current_hash
                return True
            
            return False
            
        except Exception as e:
            self._logger.error(f"파라미터 변경 확인 실패: {e}", exc_info=True)
            return False
    
    def _check_schedule_trigger(self, rule: AutomationRule, config: Dict[str, Any]) -> bool:
        """스케줄 트리거 확인"""
        schedule_type = config.get('schedule_type', 'daily')
        schedule_time = config.get('schedule_time', '09:00')
        
        now = datetime.now()
        
        if schedule_type == 'daily':
            # 매일 지정 시간
            target_time = datetime.strptime(schedule_time, '%H:%M').time()
            
            # 마지막 트리거 이후 지정 시간이 지났는지 확인
            if rule.last_triggered:
                last_date = rule.last_triggered.date()
                if last_date >= now.date():
                    return False  # 오늘 이미 트리거됨
            
            # 현재 시간이 지정 시간 이후인지 확인
            return now.time() >= target_time
        
        elif schedule_type == 'weekly':
            # 주간 스케줄 (추후 구현)
            pass
        
        return False
    
    def _check_performance_threshold(self, config: Dict[str, Any]) -> bool:
        """성과 임계값 확인"""
        strategy_name = config.get('strategy_name')
        threshold_type = config.get('threshold_type', 'decline')
        threshold_value = config.get('threshold_value', 0.05)
        
        if not strategy_name or strategy_name not in self._performance_history:
            return False
        
        performance_data = self._performance_history[strategy_name]
        if len(performance_data) < 2:
            return False
        
        if threshold_type == 'decline':
            # 성과 하락 감지
            recent_performance = performance_data[-1]
            previous_performance = performance_data[-2]
            decline_ratio = (previous_performance - recent_performance) / previous_performance
            return decline_ratio > threshold_value
        
        return False
    
    def _trigger_rule(self, rule: AutomationRule):
        """규칙 트리거 실행"""
        self._logger.info(f"규칙 트리거: {rule.name} [{rule.rule_id}]")
        
        # 전략 이름 추출
        strategy_name = rule.trigger_config.get('strategy_name', 'momentum')
        
        # 현재 파라미터 로드
        try:
            param_set = self._parameter_manager.load_best_parameters(strategy_name)
            parameters = param_set.parameters if param_set else {}
        except:
            parameters = {}
        
        # 작업 생성
        job_id = f"{rule.rule_id}_{strategy_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        job = AutomationJob(
            job_id=job_id,
            rule_id=rule.rule_id,
            strategy_name=strategy_name,
            parameters=parameters,
            trigger_type=rule.trigger_type
        )
        
        # 작업 큐에 추가
        self._job_queue.put(job)
    
    def _process_jobs(self):
        """작업 처리"""
        # 동시 실행 제한 확인
        if len(self._active_jobs) >= self._config.max_concurrent_backtests:
            return
        
        # 큐에서 작업 가져오기
        try:
            job = self._job_queue.get_nowait()
            self._start_job(job)
        except queue.Empty:
            pass
    
    def _start_job(self, job: AutomationJob):
        """작업 시작"""
        self._logger.info(f"작업 시작: {job.job_id} [{job.strategy_name}]")
        
        job.status = "running"
        job.started_at = datetime.now()
        self._active_jobs[job.job_id] = job
        self._total_jobs += 1
        
        # 백테스트 실행 (별도 스레드)
        thread = threading.Thread(
            target=self._execute_job,
            args=(job,),
            name=f"Job_{job.job_id}"
        )
        thread.start()
    
    def _execute_job(self, job: AutomationJob):
        """작업 실행"""
        try:
            # 백테스트 실행
            backtest_result = self._backtest_engine.run_backtest(
                job.strategy_name,
                job.parameters,
                self._config.default_backtest_config
            )
            
            job.backtest_result = backtest_result
            
            # 검증 실행 (설정된 경우)
            if self._config.auto_validation:
                validation_result = self._validation_system.validate_backtest(
                    backtest_result,
                    self._config.validation_criteria
                )
                job.validation_result = validation_result
                
                # 자동 승인 (설정된 경우)
                if self._config.auto_approval and validation_result.status.value == "passed":
                    self._auto_approve_job(job)
            
            job.status = "completed"
            self._successful_jobs += 1
            
            self._logger.info(f"작업 완료: {job.job_id}")
            self._send_notification(f"백테스트 작업 완료: {job.strategy_name}", {
                'job_id': job.job_id,
                'total_return': backtest_result.total_return,
                'sharpe_ratio': backtest_result.sharpe_ratio
            })
            
        except Exception as e:
            job.status = "failed"
            job.error_message = str(e)
            self._failed_jobs += 1
            
            self._logger.error(f"작업 실패: {job.job_id} - {e}", exc_info=True)
            self._send_notification(f"백테스트 작업 실패: {job.strategy_name}", {
                'job_id': job.job_id,
                'error': str(e)
            })
        
        finally:
            job.completed_at = datetime.now()
            
            # 활성 작업에서 제거하고 히스토리에 추가
            if job.job_id in self._active_jobs:
                del self._active_jobs[job.job_id]
            
            self._job_history.append(job)
            
            # 히스토리 크기 제한
            if len(self._job_history) > 1000:
                self._job_history = self._job_history[-500:]
    
    def _auto_approve_job(self, job: AutomationJob):
        """작업 자동 승인"""
        self._logger.info(f"작업 자동 승인: {job.job_id}")
        
        # 최적 파라미터로 저장
        if job.backtest_result and job.validation_result:
            param_set = ParameterSet(
                component_name=job.strategy_name,
                parameters=job.parameters,
                fitness_score=job.validation_result.overall_score,
                timestamp=datetime.now()
            )
            
            try:
                self._parameter_manager.save_optimization_result(
                    component_name=job.strategy_name,
                    result_data={
                        'best_parameters': param_set,
                        'validation_score': job.validation_result.overall_score,
                        'backtest_result': job.backtest_result.to_dict()
                    }
                )
                
                self._send_notification(f"파라미터 자동 승인: {job.strategy_name}", {
                    'job_id': job.job_id,
                    'validation_score': job.validation_result.overall_score
                })
                
            except Exception as e:
                self._logger.error(f"자동 승인 실패: {e}", exc_info=True)
    
    def _monitor_active_jobs(self):
        """활성 작업 모니터링"""
        current_time = datetime.now()
        timeout_jobs = []
        
        for job_id, job in self._active_jobs.items():
            if job.started_at:
                duration = (current_time - job.started_at).total_seconds()
                
                # 타임아웃 체크 (30분)
                if duration > 1800:
                    timeout_jobs.append(job_id)
        
        # 타임아웃된 작업 처리
        for job_id in timeout_jobs:
            job = self._active_jobs[job_id]
            job.status = "timeout"
            job.error_message = "작업 타임아웃"
            job.completed_at = current_time
            
            del self._active_jobs[job_id]
            self._job_history.append(job)
            self._failed_jobs += 1
            
            self._logger.warning(f"작업 타임아웃: {job_id}")
    
    def _send_notification(self, message: str, data: Optional[Dict[str, Any]] = None):
        """알림 전송"""
        if not self._config.notification_enabled:
            return
        
        notification_data = {
            'message': message,
            'timestamp': datetime.now(),
            'data': data or {}
        }
        
        # 등록된 콜백 호출
        for callback in self._notification_callbacks:
            try:
                callback(message, notification_data)
            except Exception as e:
                self._logger.error(f"알림 콜백 실행 실패: {e}", exc_info=True)
    
    def _add_default_rules(self):
        """기본 자동화 규칙 추가"""
        # 파라미터 변경 감지 규칙
        param_change_rule = AutomationRule(
            rule_id="param_change_momentum",
            name="모멘텀 전략 파라미터 변경 감지",
            description="모멘텀 전략의 파라미터가 변경되면 자동으로 백테스트 실행",
            trigger_type=TriggerType.PARAMETER_CHANGE,
            trigger_config={'strategy_name': 'momentum'},
            actions=[ActionType.RUN_BACKTEST, ActionType.VALIDATE_RESULT]
        )
        
        # 일일 백테스트 규칙
        daily_backtest_rule = AutomationRule(
            rule_id="daily_backtest",
            name="일일 백테스트 실행",
            description="매일 오전 9시에 주요 전략 백테스트 실행",
            trigger_type=TriggerType.SCHEDULE,
            trigger_config={'schedule_type': 'daily', 'schedule_time': '09:00', 'strategy_name': 'momentum'},
            actions=[ActionType.RUN_BACKTEST, ActionType.VALIDATE_RESULT]
        )
        
        self.add_rule(param_change_rule)
        self.add_rule(daily_backtest_rule)
    
    def _save_rules(self):
        """규칙 저장"""
        try:
            rules_file = self._data_dir / "automation_rules.json"
            
            rules_data = {}
            for rule_id, rule in self._rules.items():
                rule_dict = asdict(rule)
                rule_dict['trigger_type'] = rule.trigger_type.value
                rule_dict['actions'] = [action.value for action in rule.actions]
                if rule.created_at:
                    rule_dict['created_at'] = rule.created_at.isoformat()
                if rule.last_triggered:
                    rule_dict['last_triggered'] = rule.last_triggered.isoformat()
                rules_data[rule_id] = rule_dict
            
            with open(rules_file, 'w', encoding='utf-8') as f:
                json.dump(rules_data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            self._logger.error(f"규칙 저장 실패: {e}", exc_info=True)
    
    def get_automation_status(self) -> Dict[str, Any]:
        """자동화 상태 정보"""
        return {
            'status': self._status.value,
            'total_rules': len(self._rules),
            'enabled_rules': len([r for r in self._rules.values() if r.enabled]),
            'active_jobs': len(self._active_jobs),
            'queue_size': self._job_queue.qsize(),
            'total_jobs': self._total_jobs,
            'successful_jobs': self._successful_jobs,
            'failed_jobs': self._failed_jobs,
            'success_rate': self._successful_jobs / self._total_jobs if self._total_jobs > 0 else 0,
            'recent_jobs': len(self._job_history[-10:]),
            'config': {
                'monitor_interval': self._config.monitor_interval,
                'max_concurrent_backtests': self._config.max_concurrent_backtests,
                'auto_validation': self._config.auto_validation,
                'auto_approval': self._config.auto_approval
            }
        }
    
    def get_recent_jobs(self, limit: int = 20) -> List[Dict[str, Any]]:
        """최근 작업 목록"""
        recent_jobs = self._job_history[-limit:]
        
        job_summaries = []
        for job in recent_jobs:
            summary = {
                'job_id': job.job_id,
                'strategy_name': job.strategy_name,
                'status': job.status,
                'trigger_type': job.trigger_type.value,
                'created_at': job.created_at.isoformat() if job.created_at else None,
                'completed_at': job.completed_at.isoformat() if job.completed_at else None
            }
            
            if job.backtest_result:
                summary['total_return'] = job.backtest_result.total_return
                summary['sharpe_ratio'] = job.backtest_result.sharpe_ratio
            
            if job.validation_result:
                summary['validation_status'] = job.validation_result.status.value
                summary['validation_score'] = job.validation_result.overall_score
            
            job_summaries.append(summary)
        
        return job_summaries 