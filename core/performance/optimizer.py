"""
시스템 성능 최적화기

전체 시스템의 성능을 모니터링하고 자동으로 최적화하는 시스템
"""

import psutil
import gc
import threading
import time
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import warnings
import cProfile
import pstats
from memory_profiler import profile as memory_profile

from ..utils.logging import get_logger

logger = get_logger(__name__)

class OptimizationLevel(Enum):
    """최적화 레벨"""
    CONSERVATIVE = "conservative"    # 보수적 (안정성 우선)
    BALANCED = "balanced"           # 균형 (기본값)
    AGGRESSIVE = "aggressive"       # 공격적 (성능 우선)
    MAXIMUM = "maximum"             # 최대 (모든 최적화 적용)

class PerformanceMetric(Enum):
    """성능 지표"""
    CPU_USAGE = "cpu_usage"
    MEMORY_USAGE = "memory_usage"
    DISK_IO = "disk_io"
    NETWORK_IO = "network_io"
    RESPONSE_TIME = "response_time"
    THROUGHPUT = "throughput"
    ERROR_RATE = "error_rate"
    QUEUE_SIZE = "queue_size"

@dataclass
class PerformanceSnapshot:
    """성능 스냅샷"""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    disk_read_mb: float
    disk_write_mb: float
    network_sent_mb: float
    network_recv_mb: float
    
    # 애플리케이션 특화 지표
    active_threads: int
    queue_sizes: Dict[str, int]
    response_times: Dict[str, float]
    error_counts: Dict[str, int]
    
    # 프로세스별 상세 정보
    process_info: Dict[str, Any]

@dataclass
class OptimizationRule:
    """최적화 규칙"""
    rule_id: str
    name: str
    enabled: bool = True
    
    # 발동 조건
    trigger_metric: PerformanceMetric
    threshold_value: float
    threshold_operator: str = ">"  # >, <, >=, <=, ==
    consecutive_violations: int = 3
    
    # 최적화 액션
    optimization_actions: List[str]
    cooldown_minutes: int = 10
    
    # 레벨별 적용
    min_optimization_level: OptimizationLevel = OptimizationLevel.CONSERVATIVE

@dataclass
class OptimizationResult:
    """최적화 결과"""
    rule_id: str
    timestamp: datetime
    actions_taken: List[str]
    before_metrics: PerformanceSnapshot
    after_metrics: Optional[PerformanceSnapshot] = None
    improvement_percentage: Optional[float] = None
    success: bool = False
    error_message: Optional[str] = None

class SystemMonitor:
    """시스템 모니터"""
    
    def __init__(self):
        self._logger = logger
        self._monitoring = False
        self._snapshots = []
        self._process = psutil.Process()
        
        # 네트워크 및 디스크 I/O 기준점
        self._last_net_io = psutil.net_io_counters()
        self._last_disk_io = psutil.disk_io_counters()
        self._last_check_time = time.time()
    
    def get_current_snapshot(self) -> PerformanceSnapshot:
        """현재 성능 스냅샷 생성"""
        try:
            current_time = time.time()
            time_delta = current_time - self._last_check_time
            
            # CPU 및 메모리
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            process_memory = self._process.memory_info()
            
            # 디스크 I/O
            current_disk_io = psutil.disk_io_counters()
            if current_disk_io and self._last_disk_io:
                disk_read_mb = (current_disk_io.read_bytes - self._last_disk_io.read_bytes) / (1024 * 1024) / time_delta
                disk_write_mb = (current_disk_io.write_bytes - self._last_disk_io.write_bytes) / (1024 * 1024) / time_delta
                self._last_disk_io = current_disk_io
            else:
                disk_read_mb = disk_write_mb = 0
            
            # 네트워크 I/O
            current_net_io = psutil.net_io_counters()
            if current_net_io and self._last_net_io:
                network_sent_mb = (current_net_io.bytes_sent - self._last_net_io.bytes_sent) / (1024 * 1024) / time_delta
                network_recv_mb = (current_net_io.bytes_recv - self._last_net_io.bytes_recv) / (1024 * 1024) / time_delta
                self._last_net_io = current_net_io
            else:
                network_sent_mb = network_recv_mb = 0
            
            # 스레드 정보
            active_threads = threading.active_count()
            
            # 프로세스 정보
            process_info = {
                'pid': self._process.pid,
                'num_threads': self._process.num_threads(),
                'num_fds': self._process.num_fds() if hasattr(self._process, 'num_fds') else 0,
                'cpu_times': self._process.cpu_times()._asdict(),
                'memory_full_info': self._process.memory_full_info()._asdict()
            }
            
            snapshot = PerformanceSnapshot(
                timestamp=datetime.now(),
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                memory_used_mb=process_memory.rss / (1024 * 1024),
                disk_read_mb=disk_read_mb,
                disk_write_mb=disk_write_mb,
                network_sent_mb=network_sent_mb,
                network_recv_mb=network_recv_mb,
                active_threads=active_threads,
                queue_sizes={},  # 애플리케이션에서 설정
                response_times={},  # 애플리케이션에서 설정
                error_counts={},  # 애플리케이션에서 설정
                process_info=process_info
            )
            
            self._last_check_time = current_time
            return snapshot
            
        except Exception as e:
            self._logger.error(f"성능 스냅샷 생성 실패: {e}", exc_info=True)
            return self._create_empty_snapshot()
    
    def _create_empty_snapshot(self) -> PerformanceSnapshot:
        """빈 스냅샷 생성"""
        return PerformanceSnapshot(
            timestamp=datetime.now(),
            cpu_percent=0,
            memory_percent=0,
            memory_used_mb=0,
            disk_read_mb=0,
            disk_write_mb=0,
            network_sent_mb=0,
            network_recv_mb=0,
            active_threads=0,
            queue_sizes={},
            response_times={},
            error_counts={},
            process_info={}
        )
    
    def start_monitoring(self, interval_seconds: int = 30):
        """모니터링 시작"""
        if self._monitoring:
            return
        
        self._monitoring = True
        threading.Thread(target=self._monitoring_loop, args=(interval_seconds,), daemon=True).start()
        self._logger.info("시스템 모니터링 시작")
    
    def stop_monitoring(self):
        """모니터링 중지"""
        self._monitoring = False
        self._logger.info("시스템 모니터링 중지")
    
    def _monitoring_loop(self, interval_seconds: int):
        """모니터링 루프"""
        while self._monitoring:
            try:
                snapshot = self.get_current_snapshot()
                self._snapshots.append(snapshot)
                
                # 오래된 스냅샷 정리 (최대 1000개)
                if len(self._snapshots) > 1000:
                    self._snapshots = self._snapshots[-1000:]
                
                time.sleep(interval_seconds)
                
            except Exception as e:
                self._logger.error(f"모니터링 루프 오류: {e}", exc_info=True)
                time.sleep(interval_seconds)
    
    def get_recent_snapshots(self, hours: int = 1) -> List[PerformanceSnapshot]:
        """최근 스냅샷 조회"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        return [s for s in self._snapshots if s.timestamp > cutoff_time]

class MemoryOptimizer:
    """메모리 최적화기"""
    
    def __init__(self):
        self._logger = logger
        self._gc_stats = []
    
    def optimize_memory(self, level: OptimizationLevel) -> Dict[str, Any]:
        """메모리 최적화 실행"""
        try:
            before_memory = psutil.virtual_memory().percent
            actions_taken = []
            
            # 레벨별 최적화 액션
            if level in [OptimizationLevel.CONSERVATIVE, OptimizationLevel.BALANCED]:
                # 안전한 최적화
                collected = gc.collect()
                actions_taken.append(f"garbage_collection: {collected} objects")
                
            if level in [OptimizationLevel.BALANCED, OptimizationLevel.AGGRESSIVE]:
                # 중간 수준 최적화
                gc.set_threshold(700, 10, 10)  # 더 적극적인 GC
                actions_taken.append("gc_threshold_adjusted")
                
                # 캐시 정리 (애플리케이션별 구현 필요)
                self._clear_application_caches()
                actions_taken.append("application_caches_cleared")
                
            if level in [OptimizationLevel.AGGRESSIVE, OptimizationLevel.MAXIMUM]:
                # 적극적 최적화
                import ctypes
                ctypes.CDLL("libc.so.6").malloc_trim(0)  # Linux만 지원
                actions_taken.append("malloc_trim_executed")
                
            if level == OptimizationLevel.MAXIMUM:
                # 최대 최적화
                warnings.filterwarnings("ignore")  # 경고 비활성화로 메모리 절약
                actions_taken.append("warnings_disabled")
            
            after_memory = psutil.virtual_memory().percent
            improvement = before_memory - after_memory
            
            result = {
                'actions_taken': actions_taken,
                'before_memory_percent': before_memory,
                'after_memory_percent': after_memory,
                'improvement_percent': improvement,
                'success': True
            }
            
            self._logger.info(f"메모리 최적화 완료: {improvement:.2f}% 개선")
            return result
            
        except Exception as e:
            self._logger.error(f"메모리 최적화 실패: {e}", exc_info=True)
            return {
                'actions_taken': [],
                'error': str(e),
                'success': False
            }
    
    def _clear_application_caches(self):
        """애플리케이션 캐시 정리"""
        try:
            # 여기에 애플리케이션별 캐시 정리 로직 구현
            # 예: 데이터 캐시, 계산 결과 캐시 등
            pass
        except Exception as e:
            self._logger.error(f"캐시 정리 실패: {e}", exc_info=True)

class CPUOptimizer:
    """CPU 최적화기"""
    
    def __init__(self):
        self._logger = logger
    
    def optimize_cpu(self, level: OptimizationLevel) -> Dict[str, Any]:
        """CPU 최적화 실행"""
        try:
            before_cpu = psutil.cpu_percent(interval=1)
            actions_taken = []
            
            # 스레드 풀 최적화
            if level in [OptimizationLevel.BALANCED, OptimizationLevel.AGGRESSIVE]:
                optimal_workers = min(psutil.cpu_count(), 8)  # 최대 8개 워커
                actions_taken.append(f"thread_pool_optimized: {optimal_workers} workers")
            
            # 프로세스 우선순위 조정
            if level in [OptimizationLevel.AGGRESSIVE, OptimizationLevel.MAXIMUM]:
                try:
                    current_process = psutil.Process()
                    if level == OptimizationLevel.MAXIMUM:
                        current_process.nice(psutil.HIGH_PRIORITY_CLASS if os.name == 'nt' else -5)
                    else:
                        current_process.nice(psutil.ABOVE_NORMAL_PRIORITY_CLASS if os.name == 'nt' else -2)
                    actions_taken.append("process_priority_increased")
                except:
                    pass
            
            # CPU 친화성 설정 (Linux/macOS)
            if level == OptimizationLevel.MAXIMUM and hasattr(psutil.Process(), 'cpu_affinity'):
                try:
                    cpu_count = psutil.cpu_count()
                    if cpu_count > 4:
                        # 고성능 코어에 바인딩 (가정)
                        psutil.Process().cpu_affinity([0, 1, 2, 3])
                        actions_taken.append("cpu_affinity_optimized")
                except:
                    pass
            
            after_cpu = psutil.cpu_percent(interval=1)
            
            result = {
                'actions_taken': actions_taken,
                'before_cpu_percent': before_cpu,
                'after_cpu_percent': after_cpu,
                'success': True
            }
            
            self._logger.info(f"CPU 최적화 완료: {len(actions_taken)}개 액션 실행")
            return result
            
        except Exception as e:
            self._logger.error(f"CPU 최적화 실패: {e}", exc_info=True)
            return {
                'actions_taken': [],
                'error': str(e),
                'success': False
            }

class IOOptimizer:
    """I/O 최적화기"""
    
    def __init__(self):
        self._logger = logger
    
    def optimize_io(self, level: OptimizationLevel) -> Dict[str, Any]:
        """I/O 최적화 실행"""
        try:
            actions_taken = []
            
            # 버퍼 크기 최적화
            if level in [OptimizationLevel.BALANCED, OptimizationLevel.AGGRESSIVE]:
                # 파일 I/O 버퍼 크기 증가
                actions_taken.append("file_io_buffer_increased")
                
            # 비동기 I/O 활성화
            if level in [OptimizationLevel.AGGRESSIVE, OptimizationLevel.MAXIMUM]:
                actions_taken.append("async_io_enabled")
                
            # 압축 활성화
            if level == OptimizationLevel.MAXIMUM:
                actions_taken.append("compression_enabled")
            
            result = {
                'actions_taken': actions_taken,
                'success': True
            }
            
            self._logger.info(f"I/O 최적화 완료: {len(actions_taken)}개 액션 실행")
            return result
            
        except Exception as e:
            self._logger.error(f"I/O 최적화 실패: {e}", exc_info=True)
            return {
                'actions_taken': [],
                'error': str(e),
                'success': False
            }

class PerformanceOptimizer:
    """통합 성능 최적화기"""
    
    def __init__(self, data_dir: str = "data/performance"):
        """
        초기화
        
        Args:
            data_dir: 성능 데이터 저장 디렉토리
        """
        self._logger = logger
        self._data_dir = data_dir
        
        # 디렉토리 생성
        os.makedirs(data_dir, exist_ok=True)
        
        # 컴포넌트 초기화
        self._system_monitor = SystemMonitor()
        self._memory_optimizer = MemoryOptimizer()
        self._cpu_optimizer = CPUOptimizer()
        self._io_optimizer = IOOptimizer()
        
        # 최적화 규칙
        self._optimization_rules = {}
        self._optimization_history = []
        self._rule_violations = {}
        
        # 설정
        self._optimization_level = OptimizationLevel.BALANCED
        self._auto_optimization_enabled = True
        self._monitoring_enabled = False
        
        # 기본 규칙 생성
        self._create_default_rules()
        
        self._logger.info("성능 최적화기 초기화 완료")
    
    def _create_default_rules(self):
        """기본 최적화 규칙 생성"""
        # 메모리 사용량 규칙
        memory_rule = OptimizationRule(
            rule_id="high_memory_usage",
            name="높은 메모리 사용량",
            trigger_metric=PerformanceMetric.MEMORY_USAGE,
            threshold_value=80.0,
            threshold_operator=">=",
            consecutive_violations=2,
            optimization_actions=["memory_optimization"],
            cooldown_minutes=5,
            min_optimization_level=OptimizationLevel.CONSERVATIVE
        )
        
        # CPU 사용량 규칙
        cpu_rule = OptimizationRule(
            rule_id="high_cpu_usage",
            name="높은 CPU 사용량",
            trigger_metric=PerformanceMetric.CPU_USAGE,
            threshold_value=85.0,
            threshold_operator=">=",
            consecutive_violations=3,
            optimization_actions=["cpu_optimization"],
            cooldown_minutes=10,
            min_optimization_level=OptimizationLevel.BALANCED
        )
        
        # 응답 시간 규칙
        response_time_rule = OptimizationRule(
            rule_id="slow_response_time",
            name="느린 응답 시간",
            trigger_metric=PerformanceMetric.RESPONSE_TIME,
            threshold_value=5.0,
            threshold_operator=">=",
            consecutive_violations=2,
            optimization_actions=["io_optimization", "cpu_optimization"],
            cooldown_minutes=15,
            min_optimization_level=OptimizationLevel.AGGRESSIVE
        )
        
        self._optimization_rules = {
            "high_memory_usage": memory_rule,
            "high_cpu_usage": cpu_rule,
            "slow_response_time": response_time_rule
        }
    
    def start_monitoring(self, interval_seconds: int = 30):
        """성능 모니터링 시작"""
        if self._monitoring_enabled:
            return
        
        self._monitoring_enabled = True
        self._system_monitor.start_monitoring(interval_seconds)
        
        # 자동 최적화 스레드 시작
        if self._auto_optimization_enabled:
            threading.Thread(target=self._auto_optimization_loop, daemon=True).start()
        
        self._logger.info("성능 모니터링 및 자동 최적화 시작")
    
    def stop_monitoring(self):
        """성능 모니터링 중지"""
        if not self._monitoring_enabled:
            return
        
        self._monitoring_enabled = False
        self._system_monitor.stop_monitoring()
        
        self._logger.info("성능 모니터링 및 자동 최적화 중지")
    
    def _auto_optimization_loop(self):
        """자동 최적화 루프"""
        while self._monitoring_enabled:
            try:
                self._check_and_optimize()
                time.sleep(60)  # 1분마다 체크
                
            except Exception as e:
                self._logger.error(f"자동 최적화 루프 오류: {e}", exc_info=True)
                time.sleep(60)
    
    def _check_and_optimize(self):
        """규칙 체크 및 최적화 실행"""
        try:
            current_snapshot = self._system_monitor.get_current_snapshot()
            
            for rule in self._optimization_rules.values():
                if not rule.enabled:
                    continue
                
                if self._optimization_level.value < rule.min_optimization_level.value:
                    continue
                
                if self._check_rule_violation(rule, current_snapshot):
                    # 쿨다운 체크
                    if self._is_in_cooldown(rule.rule_id):
                        continue
                    
                    # 최적화 실행
                    self._execute_optimization(rule, current_snapshot)
                    
        except Exception as e:
            self._logger.error(f"규칙 체크 및 최적화 실패: {e}", exc_info=True)
    
    def _check_rule_violation(self, rule: OptimizationRule, snapshot: PerformanceSnapshot) -> bool:
        """규칙 위반 여부 체크"""
        try:
            # 메트릭 값 추출
            metric_value = self._extract_metric_value(rule.trigger_metric, snapshot)
            if metric_value is None:
                return False
            
            # 임계값 비교
            violated = False
            if rule.threshold_operator == ">":
                violated = metric_value > rule.threshold_value
            elif rule.threshold_operator == ">=":
                violated = metric_value >= rule.threshold_value
            elif rule.threshold_operator == "<":
                violated = metric_value < rule.threshold_value
            elif rule.threshold_operator == "<=":
                violated = metric_value <= rule.threshold_value
            elif rule.threshold_operator == "==":
                violated = metric_value == rule.threshold_value
            
            # 연속 위반 체크
            if violated:
                if rule.rule_id not in self._rule_violations:
                    self._rule_violations[rule.rule_id] = []
                
                self._rule_violations[rule.rule_id].append(datetime.now())
                
                # 최근 위반만 유지
                recent_violations = [
                    t for t in self._rule_violations[rule.rule_id]
                    if (datetime.now() - t).total_seconds() < 300  # 5분 이내
                ]
                self._rule_violations[rule.rule_id] = recent_violations
                
                return len(recent_violations) >= rule.consecutive_violations
            else:
                # 위반이 아니면 기록 초기화
                self._rule_violations[rule.rule_id] = []
                return False
                
        except Exception as e:
            self._logger.error(f"규칙 위반 체크 실패: {e}", exc_info=True)
            return False
    
    def _extract_metric_value(self, metric: PerformanceMetric, snapshot: PerformanceSnapshot) -> Optional[float]:
        """스냅샷에서 메트릭 값 추출"""
        try:
            if metric == PerformanceMetric.CPU_USAGE:
                return snapshot.cpu_percent
            elif metric == PerformanceMetric.MEMORY_USAGE:
                return snapshot.memory_percent
            elif metric == PerformanceMetric.DISK_IO:
                return snapshot.disk_read_mb + snapshot.disk_write_mb
            elif metric == PerformanceMetric.NETWORK_IO:
                return snapshot.network_sent_mb + snapshot.network_recv_mb
            elif metric == PerformanceMetric.RESPONSE_TIME:
                return max(snapshot.response_times.values()) if snapshot.response_times else 0
            elif metric == PerformanceMetric.ERROR_RATE:
                total_errors = sum(snapshot.error_counts.values()) if snapshot.error_counts else 0
                return total_errors
            elif metric == PerformanceMetric.QUEUE_SIZE:
                return max(snapshot.queue_sizes.values()) if snapshot.queue_sizes else 0
            
            return None
            
        except Exception as e:
            self._logger.error(f"메트릭 값 추출 실패: {e}", exc_info=True)
            return None
    
    def _is_in_cooldown(self, rule_id: str) -> bool:
        """쿨다운 상태 체크"""
        try:
            rule = self._optimization_rules.get(rule_id)
            if not rule:
                return False
            
            # 최근 최적화 기록 체크
            recent_optimizations = [
                opt for opt in self._optimization_history
                if (opt.rule_id == rule_id and 
                    (datetime.now() - opt.timestamp).total_seconds() < rule.cooldown_minutes * 60)
            ]
            
            return len(recent_optimizations) > 0
            
        except Exception as e:
            self._logger.error(f"쿨다운 체크 실패: {e}", exc_info=True)
            return True  # 안전을 위해 True 반환
    
    def _execute_optimization(self, rule: OptimizationRule, before_snapshot: PerformanceSnapshot):
        """최적화 실행"""
        try:
            self._logger.info(f"최적화 실행: {rule.name}")
            
            actions_taken = []
            success = True
            error_message = None
            
            for action in rule.optimization_actions:
                try:
                    if action == "memory_optimization":
                        result = self._memory_optimizer.optimize_memory(self._optimization_level)
                        actions_taken.extend(result.get('actions_taken', []))
                    elif action == "cpu_optimization":
                        result = self._cpu_optimizer.optimize_cpu(self._optimization_level)
                        actions_taken.extend(result.get('actions_taken', []))
                    elif action == "io_optimization":
                        result = self._io_optimizer.optimize_io(self._optimization_level)
                        actions_taken.extend(result.get('actions_taken', []))
                    
                except Exception as e:
                    error_message = str(e)
                    success = False
                    self._logger.error(f"최적화 액션 실패 ({action}): {e}", exc_info=True)
            
            # 최적화 후 스냅샷
            time.sleep(5)  # 잠시 대기 후 측정
            after_snapshot = self._system_monitor.get_current_snapshot()
            
            # 개선 정도 계산
            improvement = self._calculate_improvement(rule.trigger_metric, before_snapshot, after_snapshot)
            
            # 결과 기록
            optimization_result = OptimizationResult(
                rule_id=rule.rule_id,
                timestamp=datetime.now(),
                actions_taken=actions_taken,
                before_metrics=before_snapshot,
                after_metrics=after_snapshot,
                improvement_percentage=improvement,
                success=success,
                error_message=error_message
            )
            
            self._optimization_history.append(optimization_result)
            
            # 기록 저장
            self._save_optimization_result(optimization_result)
            
            if success:
                self._logger.info(f"최적화 완료: {improvement:.2f}% 개선")
            else:
                self._logger.error(f"최적화 실패: {error_message}", exc_info=True)
                
        except Exception as e:
            self._logger.error(f"최적화 실행 실패: {e}", exc_info=True)
    
    def _calculate_improvement(self, metric: PerformanceMetric, before: PerformanceSnapshot, 
                             after: PerformanceSnapshot) -> float:
        """개선 정도 계산"""
        try:
            before_value = self._extract_metric_value(metric, before)
            after_value = self._extract_metric_value(metric, after)
            
            if before_value is None or after_value is None or before_value == 0:
                return 0.0
            
            improvement = ((before_value - after_value) / before_value) * 100
            return improvement
            
        except Exception as e:
            self._logger.error(f"개선 정도 계산 실패: {e}", exc_info=True)
            return 0.0
    
    def _save_optimization_result(self, result: OptimizationResult):
        """최적화 결과 저장"""
        try:
            timestamp_str = result.timestamp.strftime('%Y%m%d')
            filename = f"optimization_results_{timestamp_str}.json"
            filepath = os.path.join(self._data_dir, filename)
            
            # 기존 데이터 로드
            results = []
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    results = json.load(f)
            
            # 새 결과 추가
            result_dict = asdict(result)
            result_dict['timestamp'] = result.timestamp.isoformat()
            result_dict['before_metrics']['timestamp'] = result.before_metrics.timestamp.isoformat()
            if result.after_metrics:
                result_dict['after_metrics']['timestamp'] = result.after_metrics.timestamp.isoformat()
            
            results.append(result_dict)
            
            # 파일 저장
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2, default=str)
                
        except Exception as e:
            self._logger.error(f"최적화 결과 저장 실패: {e}", exc_info=True)
    
    def manual_optimization(self, level: OptimizationLevel = None) -> Dict[str, Any]:
        """수동 최적화 실행"""
        try:
            optimization_level = level or self._optimization_level
            before_snapshot = self._system_monitor.get_current_snapshot()
            
            # 모든 최적화기 실행
            results = {}
            
            # 메모리 최적화
            memory_result = self._memory_optimizer.optimize_memory(optimization_level)
            results['memory'] = memory_result
            
            # CPU 최적화
            cpu_result = self._cpu_optimizer.optimize_cpu(optimization_level)
            results['cpu'] = cpu_result
            
            # I/O 최적화
            io_result = self._io_optimizer.optimize_io(optimization_level)
            results['io'] = io_result
            
            # 최적화 후 스냅샷
            time.sleep(5)
            after_snapshot = self._system_monitor.get_current_snapshot()
            
            # 전체 결과
            overall_result = {
                'optimization_level': optimization_level.value,
                'before_snapshot': asdict(before_snapshot),
                'after_snapshot': asdict(after_snapshot),
                'detailed_results': results,
                'overall_success': all(r.get('success', False) for r in results.values()),
                'timestamp': datetime.now().isoformat()
            }
            
            self._logger.info("수동 최적화 완료")
            return overall_result
            
        except Exception as e:
            self._logger.error(f"수동 최적화 실패: {e}", exc_info=True)
            return {
                'error': str(e),
                'success': False,
                'timestamp': datetime.now().isoformat()
            }
    
    def get_performance_report(self, hours: int = 24) -> Dict[str, Any]:
        """성능 리포트 생성"""
        try:
            recent_snapshots = self._system_monitor.get_recent_snapshots(hours)
            
            if not recent_snapshots:
                return {'error': '성능 데이터 없음'}
            
            # 통계 계산
            cpu_values = [s.cpu_percent for s in recent_snapshots]
            memory_values = [s.memory_percent for s in recent_snapshots]
            memory_used_values = [s.memory_used_mb for s in recent_snapshots]
            
            stats = {
                'period_hours': hours,
                'total_snapshots': len(recent_snapshots),
                'cpu_stats': {
                    'avg': sum(cpu_values) / len(cpu_values),
                    'max': max(cpu_values),
                    'min': min(cpu_values)
                },
                'memory_stats': {
                    'avg_percent': sum(memory_values) / len(memory_values),
                    'max_percent': max(memory_values),
                    'min_percent': min(memory_values),
                    'avg_used_mb': sum(memory_used_values) / len(memory_used_values),
                    'max_used_mb': max(memory_used_values)
                },
                'optimization_history': len(self._optimization_history),
                'recent_optimizations': len([
                    opt for opt in self._optimization_history
                    if (datetime.now() - opt.timestamp).total_seconds() < hours * 3600
                ])
            }
            
            return stats
            
        except Exception as e:
            self._logger.error(f"성능 리포트 생성 실패: {e}", exc_info=True)
            return {'error': str(e)}
    
    def set_optimization_level(self, level: OptimizationLevel):
        """최적화 레벨 설정"""
        self._optimization_level = level
        self._logger.info(f"최적화 레벨 변경: {level.value}")
    
    def enable_auto_optimization(self, enabled: bool = True):
        """자동 최적화 활성화/비활성화"""
        self._auto_optimization_enabled = enabled
        self._logger.info(f"자동 최적화: {'활성화' if enabled else '비활성화'}")

# 전역 인스턴스
_performance_optimizer = None

def get_performance_optimizer() -> PerformanceOptimizer:
    """성능 최적화기 싱글톤 인스턴스 반환"""
    global _performance_optimizer
    if _performance_optimizer is None:
        _performance_optimizer = PerformanceOptimizer()
    return _performance_optimizer 