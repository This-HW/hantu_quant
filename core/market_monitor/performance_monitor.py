"""
실시간 성능 모니터링 시스템

시스템의 CPU, 메모리, API 호출량 등을 실시간으로 추적하고 모니터링
"""

import psutil
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from collections import deque
import json
import os

from ..utils.logging import get_logger

logger = get_logger(__name__)

@dataclass
class SystemMetrics:
    """시스템 성능 지표"""
    timestamp: datetime
    
    # CPU 관련
    cpu_percent: float
    cpu_count: int
    
    # 메모리 관련
    memory_total: int  # bytes
    memory_used: int   # bytes
    memory_percent: float
    memory_available: int  # bytes
    
    # 디스크 관련
    disk_usage_percent: float
    disk_free: int  # bytes
    
    # 네트워크 관련
    network_sent: int  # bytes
    network_recv: int  # bytes
    
    # 프로세스 관련
    process_count: int
    active_threads: int
    
    # 선택적 필드 (기본값 있음)
    cpu_freq: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        result = asdict(self)
        result['timestamp'] = self.timestamp.isoformat()
        return result

@dataclass
class APIMetrics:
    """API 호출 성능 지표"""
    timestamp: datetime
    
    # API 호출량
    total_calls: int
    successful_calls: int
    failed_calls: int
    
    # 호출 빈도 (최근 1분)
    calls_per_minute: float
    
    # 응답 시간
    avg_response_time: float  # milliseconds
    max_response_time: float
    min_response_time: float
    
    # 에러율
    error_rate: float
    
    # API별 상세 (선택적)
    api_details: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        result = asdict(self)
        result['timestamp'] = self.timestamp.isoformat()
        return result

@dataclass
class ApplicationMetrics:
    """애플리케이션 성능 지표"""
    timestamp: datetime
    
    # 애플리케이션 상태
    uptime: float  # seconds
    status: str    # 'running', 'idle', 'busy', 'error'
    
    # 작업 성능
    tasks_completed: int
    tasks_pending: int
    tasks_failed: int
    
    # 처리량
    throughput: float  # tasks per minute
    
    # 메모리 사용량 (애플리케이션 별)
    app_memory_mb: float
    
    # 데이터베이스 연결
    db_connections: int
    active_queries: int
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        result = asdict(self)
        result['timestamp'] = self.timestamp.isoformat()
        return result

class PerformanceAlert:
    """성능 알림 시스템"""
    
    def __init__(self):
        self._thresholds = {
            'cpu_high': 80.0,          # CPU 사용률 80% 이상
            'memory_high': 85.0,       # 메모리 사용률 85% 이상
            'disk_full': 90.0,         # 디스크 사용률 90% 이상
            'api_error_rate': 10.0,    # API 에러율 10% 이상
            'response_time_slow': 5000.0,  # 응답시간 5초 이상
        }
        self._callbacks: List[Callable] = []
        
    def add_callback(self, callback: Callable[[str, Dict], None]):
        """알림 콜백 추가"""
        self._callbacks.append(callback)
        
    def check_alerts(self, system_metrics: SystemMetrics, 
                    api_metrics: APIMetrics,
                    app_metrics: ApplicationMetrics):
        """알림 조건 확인"""
        alerts = []
        
        # CPU 사용률 확인
        if system_metrics.cpu_percent > self._thresholds['cpu_high']:
            alerts.append({
                'type': 'cpu_high',
                'message': f'CPU 사용률 높음: {system_metrics.cpu_percent:.1f}%',
                'severity': 'warning',
                'value': system_metrics.cpu_percent
            })
        
        # 메모리 사용률 확인
        if system_metrics.memory_percent > self._thresholds['memory_high']:
            alerts.append({
                'type': 'memory_high',
                'message': f'메모리 사용률 높음: {system_metrics.memory_percent:.1f}%',
                'severity': 'warning',
                'value': system_metrics.memory_percent
            })
        
        # 디스크 사용률 확인
        if system_metrics.disk_usage_percent > self._thresholds['disk_full']:
            alerts.append({
                'type': 'disk_full',
                'message': f'디스크 사용률 높음: {system_metrics.disk_usage_percent:.1f}%',
                'severity': 'critical',
                'value': system_metrics.disk_usage_percent
            })
        
        # API 에러율 확인
        if api_metrics.error_rate > self._thresholds['api_error_rate']:
            alerts.append({
                'type': 'api_error_rate',
                'message': f'API 에러율 높음: {api_metrics.error_rate:.1f}%',
                'severity': 'critical',
                'value': api_metrics.error_rate
            })
        
        # API 응답시간 확인
        if api_metrics.avg_response_time > self._thresholds['response_time_slow']:
            alerts.append({
                'type': 'response_time_slow',
                'message': f'API 응답시간 느림: {api_metrics.avg_response_time:.0f}ms',
                'severity': 'warning',
                'value': api_metrics.avg_response_time
            })
        
        # 알림 발송
        for alert in alerts:
            for callback in self._callbacks:
                try:
                    callback(alert['type'], alert)
                except Exception as e:
                    logger.error(f"알림 콜백 실행 중 오류: {e}", exc_info=True)

class PerformanceMonitor:
    """실시간 성능 모니터링 시스템"""
    
    def __init__(self, monitoring_interval: int = 10):
        """초기화
        
        Args:
            monitoring_interval: 모니터링 간격 (초)
        """
        self._logger = logger
        self._monitoring_interval = monitoring_interval
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None
        
        # 데이터 저장 (최근 1시간 분량)
        max_samples = 3600 // monitoring_interval  # 1시간 분량
        self._system_metrics: deque = deque(maxlen=max_samples)
        self._api_metrics: deque = deque(maxlen=max_samples)
        self._app_metrics: deque = deque(maxlen=max_samples)
        
        # API 호출 추적
        self._api_call_history: deque = deque(maxlen=1000)
        
        # 시작 시간
        self._start_time = datetime.now()
        
        # 알림 시스템
        self._alert_system = PerformanceAlert()
        
        # 네트워크 통계 초기값
        self._last_network_stats = psutil.net_io_counters()
        
        self._logger.info("PerformanceMonitor 초기화 완료")
    
    def add_alert_callback(self, callback: Callable[[str, Dict], None]):
        """알림 콜백 추가"""
        self._alert_system.add_callback(callback)
    
    def record_api_call(self, endpoint: str, response_time: float, 
                       success: bool, error_code: Optional[str] = None):
        """API 호출 기록
        
        Args:
            endpoint: API 엔드포인트
            response_time: 응답 시간 (milliseconds)
            success: 성공 여부
            error_code: 에러 코드 (실패 시)
        """
        self._api_call_history.append({
            'timestamp': datetime.now(),
            'endpoint': endpoint,
            'response_time': response_time,
            'success': success,
            'error_code': error_code
        })
    
    def _collect_system_metrics(self) -> SystemMetrics:
        """시스템 지표 수집"""
        # CPU 정보
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count() or 1  # None인 경우 1로 기본값
        
        try:
            cpu_freq = psutil.cpu_freq().current if psutil.cpu_freq() else None
        except:
            cpu_freq = None
        
        # 메모리 정보
        memory = psutil.virtual_memory()
        
        # 디스크 정보
        disk = psutil.disk_usage('/')
        
        # 네트워크 정보
        network_stats = psutil.net_io_counters()
        network_sent = network_stats.bytes_sent - self._last_network_stats.bytes_sent
        network_recv = network_stats.bytes_recv - self._last_network_stats.bytes_recv
        self._last_network_stats = network_stats
        
        # 프로세스 정보
        process_count = len(psutil.pids())
        active_threads = threading.active_count()
        
        return SystemMetrics(
            timestamp=datetime.now(),
            cpu_percent=cpu_percent,
            cpu_count=cpu_count,
            cpu_freq=cpu_freq,
            memory_total=memory.total,
            memory_used=memory.used,
            memory_percent=memory.percent,
            memory_available=memory.available,
            disk_usage_percent=disk.percent,
            disk_free=disk.free,
            network_sent=network_sent,
            network_recv=network_recv,
            process_count=process_count,
            active_threads=active_threads
        )
    
    def _collect_api_metrics(self) -> APIMetrics:
        """API 지표 수집"""
        now = datetime.now()
        one_minute_ago = now - timedelta(minutes=1)
        
        # 최근 1분간 API 호출 분석
        recent_calls = [
            call for call in self._api_call_history 
            if call['timestamp'] >= one_minute_ago
        ]
        
        if not recent_calls:
            return APIMetrics(
                timestamp=now,
                total_calls=0,
                successful_calls=0,
                failed_calls=0,
                calls_per_minute=0.0,
                avg_response_time=0.0,
                max_response_time=0.0,
                min_response_time=0.0,
                error_rate=0.0
            )
        
        # 통계 계산
        total_calls = len(recent_calls)
        successful_calls = sum(1 for call in recent_calls if call['success'])
        failed_calls = total_calls - successful_calls
        
        response_times = [call['response_time'] for call in recent_calls]
        avg_response_time = sum(response_times) / len(response_times)
        max_response_time = max(response_times)
        min_response_time = min(response_times)
        
        error_rate = (failed_calls / total_calls * 100) if total_calls > 0 else 0.0
        
        return APIMetrics(
            timestamp=now,
            total_calls=total_calls,
            successful_calls=successful_calls,
            failed_calls=failed_calls,
            calls_per_minute=total_calls,  # 1분간의 호출 수
            avg_response_time=avg_response_time,
            max_response_time=max_response_time,
            min_response_time=min_response_time,
            error_rate=error_rate
        )
    
    def _collect_app_metrics(self) -> ApplicationMetrics:
        """애플리케이션 지표 수집"""
        now = datetime.now()
        uptime = (now - self._start_time).total_seconds()
        
        # 프로세스별 메모리 사용량
        current_process = psutil.Process()
        app_memory_mb = current_process.memory_info().rss / 1024 / 1024
        
        # 임시 상태 (실제 구현에서는 애플리케이션 상태를 추적)
        status = "running"
        tasks_completed = len(self._api_call_history)
        tasks_pending = 0
        tasks_failed = sum(1 for call in self._api_call_history if not call['success'])
        
        # 처리량 (최근 1분간)
        one_minute_ago = now - timedelta(minutes=1)
        recent_completed = sum(
            1 for call in self._api_call_history 
            if call['timestamp'] >= one_minute_ago and call['success']
        )
        throughput = recent_completed  # tasks per minute
        
        return ApplicationMetrics(
            timestamp=now,
            uptime=uptime,
            status=status,
            tasks_completed=tasks_completed,
            tasks_pending=tasks_pending,
            tasks_failed=tasks_failed,
            throughput=throughput,
            app_memory_mb=app_memory_mb,
            db_connections=0,  # 실제 구현에서는 DB 연결 수 추적
            active_queries=0   # 실제 구현에서는 활성 쿼리 수 추적
        )
    
    def _monitoring_loop(self):
        """모니터링 루프"""
        while self._running:
            try:
                # 지표 수집
                system_metrics = self._collect_system_metrics()
                api_metrics = self._collect_api_metrics()
                app_metrics = self._collect_app_metrics()
                
                # 데이터 저장
                self._system_metrics.append(system_metrics)
                self._api_metrics.append(api_metrics)
                self._app_metrics.append(app_metrics)
                
                # 알림 확인
                self._alert_system.check_alerts(system_metrics, api_metrics, app_metrics)
                
                self._logger.debug(f"성능 지표 수집 완료: CPU {system_metrics.cpu_percent:.1f}%, "
                                 f"메모리 {system_metrics.memory_percent:.1f}%, "
                                 f"API 호출 {api_metrics.calls_per_minute}/분")
                
            except Exception as e:
                self._logger.error(f"성능 모니터링 중 오류: {e}", exc_info=True)
            
            time.sleep(self._monitoring_interval)
    
    def start_monitoring(self):
        """모니터링 시작"""
        if self._running:
            self._logger.warning("모니터링이 이미 실행 중입니다.")
            return
        
        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self._monitor_thread.start()
        self._logger.info("성능 모니터링 시작")
    
    def stop_monitoring(self):
        """모니터링 중지"""
        if not self._running:
            return
        
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        self._logger.info("성능 모니터링 중지")
    
    def get_current_metrics(self) -> Dict[str, Any]:
        """현재 성능 지표 반환"""
        if not self._system_metrics:
            return {}
        
        return {
            'system': self._system_metrics[-1].to_dict(),
            'api': self._api_metrics[-1].to_dict() if self._api_metrics else {},
            'application': self._app_metrics[-1].to_dict() if self._app_metrics else {}
        }
    
    def get_historical_metrics(self, minutes: int = 60) -> Dict[str, List[Dict]]:
        """과거 지표 반환
        
        Args:
            minutes: 반환할 과거 데이터 시간 (분)
        """
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        
        def filter_by_time(metrics_list):
            return [
                m.to_dict() for m in metrics_list 
                if m.timestamp >= cutoff_time
            ]
        
        return {
            'system': filter_by_time(self._system_metrics),
            'api': filter_by_time(self._api_metrics),
            'application': filter_by_time(self._app_metrics)
        }
    
    def export_metrics(self, file_path: str, format: str = 'json'):
        """지표를 파일로 내보내기
        
        Args:
            file_path: 저장할 파일 경로
            format: 저장 형식 ('json', 'csv')
        """
        try:
            metrics_data = self.get_historical_metrics(60)  # 최근 1시간
            
            if format == 'json':
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(metrics_data, f, ensure_ascii=False, indent=2)
            
            elif format == 'csv':
                import pandas as pd
                
                # 시스템 지표를 DataFrame으로 변환
                if metrics_data['system']:
                    df_system = pd.DataFrame(metrics_data['system'])
                    df_system.to_csv(file_path.replace('.csv', '_system.csv'), index=False)
                
                if metrics_data['api']:
                    df_api = pd.DataFrame(metrics_data['api'])
                    df_api.to_csv(file_path.replace('.csv', '_api.csv'), index=False)
                
                if metrics_data['application']:
                    df_app = pd.DataFrame(metrics_data['application'])
                    df_app.to_csv(file_path.replace('.csv', '_application.csv'), index=False)
            
            self._logger.info(f"성능 지표를 {file_path}에 저장했습니다.")
            
        except Exception as e:
            self._logger.error(f"지표 내보내기 중 오류: {e}", exc_info=True)

# 글로벌 인스턴스 (싱글톤 패턴)
_performance_monitor_instance: Optional[PerformanceMonitor] = None

def get_performance_monitor() -> PerformanceMonitor:
    """성능 모니터 인스턴스 반환 (싱글톤)"""
    global _performance_monitor_instance
    if _performance_monitor_instance is None:
        _performance_monitor_instance = PerformanceMonitor()
    return _performance_monitor_instance 