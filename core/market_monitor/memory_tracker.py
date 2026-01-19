"""
메모리 사용량 및 API 호출 추적 시스템

시스템의 메모리 사용 패턴과 API 호출을 상세히 추적하고 분석
"""

import psutil
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field
from collections import deque, defaultdict
import sqlite3
from pathlib import Path

from ..utils.logging import get_logger

logger = get_logger(__name__)

@dataclass
class MemorySnapshot:
    """메모리 스냅샷"""
    timestamp: datetime
    
    # 시스템 메모리
    total_memory: int
    available_memory: int
    used_memory: int
    free_memory: int
    memory_percent: float
    
    # 스왑 메모리
    swap_total: int
    swap_used: int
    swap_free: int
    swap_percent: float
    
    # 프로세스별 메모리
    process_memory: Dict[str, int] = field(default_factory=dict)
    
    # 메모리 누수 감지
    memory_leak_suspects: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        result = asdict(self)
        result['timestamp'] = self.timestamp.isoformat()
        return result

@dataclass
class APICallRecord:
    """API 호출 기록"""
    timestamp: datetime
    endpoint: str
    method: str
    
    # 성능 지표
    response_time: float  # milliseconds
    request_size: int     # bytes
    response_size: int    # bytes
    
    # 상태 정보
    status_code: int
    success: bool
    error_message: Optional[str] = None
    
    # 컨텍스트 정보
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None
    session_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        result = asdict(self)
        result['timestamp'] = self.timestamp.isoformat()
        return result

@dataclass
class APIStatistics:
    """API 통계"""
    endpoint: str
    period_start: datetime
    period_end: datetime
    
    # 호출 통계
    total_calls: int
    successful_calls: int
    failed_calls: int
    error_rate: float
    
    # 성능 통계
    avg_response_time: float
    min_response_time: float
    max_response_time: float
    p95_response_time: float
    
    # 데이터 전송량
    total_request_size: int
    total_response_size: int
    avg_request_size: float
    avg_response_size: float
    
    # 에러 분석
    error_types: Dict[str, int] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        result = asdict(self)
        result['period_start'] = self.period_start.isoformat()
        result['period_end'] = self.period_end.isoformat()
        return result

class MemoryTracker:
    """메모리 사용량 추적기"""
    
    def __init__(self, tracking_interval: int = 30):
        """초기화
        
        Args:
            tracking_interval: 추적 간격 (초)
        """
        self._logger = logger
        self._tracking_interval = tracking_interval
        self._running = False
        self._tracker_thread: Optional[threading.Thread] = None
        
        # 메모리 스냅샷 저장 (최근 24시간)
        max_snapshots = 24 * 3600 // tracking_interval
        self._memory_snapshots: deque = deque(maxlen=max_snapshots)
        
        # 프로세스별 메모리 추적
        self._process_memory_history: defaultdict = defaultdict(lambda: deque(maxlen=100))
        
        # 메모리 누수 임계값
        self._leak_threshold = 0.1  # 10% 증가
        self._leak_window = 10      # 10개 샘플
        
        self._logger.info("MemoryTracker 초기화 완료")
    
    def _collect_memory_snapshot(self) -> MemorySnapshot:
        """메모리 스냅샷 수집"""
        # 시스템 메모리 정보
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()
        
        # 프로세스별 메모리 사용량
        process_memory = {}
        memory_leak_suspects = []
        
        try:
            for proc in psutil.process_iter(['pid', 'name', 'memory_info']):
                try:
                    name = proc.info['name']
                    memory_mb = proc.info['memory_info'].rss / 1024 / 1024
                    
                    if memory_mb > 10:  # 10MB 이상인 프로세스만 추적
                        process_memory[f"{name}_{proc.info['pid']}"] = int(memory_mb)
                        
                        # 메모리 누수 의심 프로세스 감지
                        proc_key = name
                        self._process_memory_history[proc_key].append(memory_mb)
                        
                        if self._is_memory_leak_suspect(proc_key):
                            memory_leak_suspects.append(name)
                            
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
                    
        except Exception as e:
            self._logger.error(f"프로세스 메모리 정보 수집 중 오류: {e}", exc_info=True)
        
        return MemorySnapshot(
            timestamp=datetime.now(),
            total_memory=memory.total,
            available_memory=memory.available,
            used_memory=memory.used,
            free_memory=memory.free,
            memory_percent=memory.percent,
            swap_total=swap.total,
            swap_used=swap.used,
            swap_free=swap.free,
            swap_percent=swap.percent,
            process_memory=process_memory,
            memory_leak_suspects=memory_leak_suspects
        )
    
    def _is_memory_leak_suspect(self, process_name: str) -> bool:
        """메모리 누수 의심 프로세스인지 확인"""
        history = self._process_memory_history[process_name]
        
        if len(history) < self._leak_window:
            return False
        
        # 최근 값들의 증가 추세 확인
        recent_values = list(history)[-self._leak_window:]
        first_value = recent_values[0]
        last_value = recent_values[-1]
        
        if first_value == 0:
            return False
        
        growth_rate = (last_value - first_value) / first_value
        return growth_rate > self._leak_threshold
    
    def start_tracking(self):
        """메모리 추적 시작"""
        if self._running:
            self._logger.warning("메모리 추적이 이미 실행 중입니다.")
            return
        
        self._running = True
        
        def tracking_loop():
            while self._running:
                try:
                    snapshot = self._collect_memory_snapshot()
                    self._memory_snapshots.append(snapshot)
                    
                    # 메모리 누수 의심 프로세스 로그
                    if snapshot.memory_leak_suspects:
                        self._logger.warning(f"메모리 누수 의심 프로세스: {snapshot.memory_leak_suspects}")
                    
                except Exception as e:
                    self._logger.error(f"메모리 추적 중 오류: {e}", exc_info=True)
                
                time.sleep(self._tracking_interval)
        
        self._tracker_thread = threading.Thread(target=tracking_loop, daemon=True)
        self._tracker_thread.start()
        self._logger.info("메모리 추적 시작")
    
    def stop_tracking(self):
        """메모리 추적 중지"""
        if not self._running:
            return
        
        self._running = False
        if self._tracker_thread:
            self._tracker_thread.join(timeout=5)
        self._logger.info("메모리 추적 중지")
    
    def get_current_memory_status(self) -> Optional[MemorySnapshot]:
        """현재 메모리 상태 반환"""
        return self._memory_snapshots[-1] if self._memory_snapshots else None
    
    def get_memory_history(self, hours: int = 24) -> List[MemorySnapshot]:
        """메모리 사용 이력 반환"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        return [
            snapshot for snapshot in self._memory_snapshots
            if snapshot.timestamp >= cutoff_time
        ]
    
    def analyze_memory_trends(self, hours: int = 24) -> Dict[str, Any]:
        """메모리 사용 트렌드 분석"""
        history = self.get_memory_history(hours)
        
        if len(history) < 2:
            return {}
        
        # 메모리 사용률 트렌드
        memory_percentages = [s.memory_percent for s in history]
        avg_usage = sum(memory_percentages) / len(memory_percentages)
        max_usage = max(memory_percentages)
        min_usage = min(memory_percentages)
        
        # 스왑 사용 분석
        swap_usage = [s.swap_percent for s in history if s.swap_total > 0]
        avg_swap = sum(swap_usage) / len(swap_usage) if swap_usage else 0
        
        # 메모리 누수 의심 프로세스 집계
        all_suspects = []
        for snapshot in history:
            all_suspects.extend(snapshot.memory_leak_suspects)
        
        suspect_counts = defaultdict(int)
        for suspect in all_suspects:
            suspect_counts[suspect] += 1
        
        return {
            'period_hours': hours,
            'average_memory_usage': avg_usage,
            'peak_memory_usage': max_usage,
            'min_memory_usage': min_usage,
            'average_swap_usage': avg_swap,
            'memory_leak_suspects': dict(suspect_counts),
            'total_snapshots': len(history)
        }

class APICallTracker:
    """API 호출 추적기"""

    def __init__(self, db_path: str = "data/api_tracking.db",
                 use_unified_db: bool = True):
        """초기화

        Args:
            db_path: API 추적 데이터베이스 경로 (SQLite 폴백용)
            use_unified_db: 통합 DB 사용 여부 (기본값: True)
        """
        self._logger = logger
        self._db_path = db_path
        self._unified_db_available = False

        # 통합 DB 초기화 시도
        if use_unified_db:
            try:
                from ..database.unified_db import ensure_tables_exist
                ensure_tables_exist()
                self._unified_db_available = True
                self._logger.info("APICallTracker: 통합 DB 사용")
            except Exception as e:
                self._logger.warning(f"통합 DB 초기화 실패, SQLite 폴백 사용: {e}")
                self._unified_db_available = False

        # 메모리 내 호출 기록 (최근 1시간)
        self._call_history: deque = deque(maxlen=10000)

        # 통계 캐시
        self._stats_cache: Dict[str, APIStatistics] = {}
        self._cache_expiry: Dict[str, datetime] = {}

        # SQLite 데이터베이스 초기화 (폴백용)
        if not self._unified_db_available:
            self._init_database()

        self._logger.info("APICallTracker 초기화 완료")
    
    def _init_database(self):
        """데이터베이스 초기화"""
        try:
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
            
            with sqlite3.connect(self._db_path) as conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS api_calls (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        endpoint TEXT NOT NULL,
                        method TEXT NOT NULL,
                        response_time REAL NOT NULL,
                        request_size INTEGER,
                        response_size INTEGER,
                        status_code INTEGER,
                        success INTEGER,
                        error_message TEXT,
                        user_agent TEXT,
                        ip_address TEXT,
                        session_id TEXT
                    )
                ''')
                
                # 인덱스 생성
                conn.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON api_calls(timestamp)')
                conn.execute('CREATE INDEX IF NOT EXISTS idx_endpoint ON api_calls(endpoint)')
                conn.execute('CREATE INDEX IF NOT EXISTS idx_success ON api_calls(success)')
                
                conn.commit()
                self._logger.info("API 추적 데이터베이스 초기화 완료")
                
        except Exception as e:
            self._logger.error(f"API 추적 데이터베이스 초기화 중 오류: {e}", exc_info=True)
    
    def record_api_call(self, endpoint: str, method: str = "GET", 
                       response_time: float = 0.0, request_size: int = 0,
                       response_size: int = 0, status_code: int = 200,
                       success: bool = True, error_message: Optional[str] = None,
                       user_agent: Optional[str] = None, ip_address: Optional[str] = None,
                       session_id: Optional[str] = None):
        """API 호출 기록
        
        Args:
            endpoint: API 엔드포인트
            method: HTTP 메서드
            response_time: 응답 시간 (milliseconds)
            request_size: 요청 크기 (bytes)
            response_size: 응답 크기 (bytes)
            status_code: HTTP 상태 코드
            success: 성공 여부
            error_message: 에러 메시지
            user_agent: User Agent
            ip_address: IP 주소
            session_id: 세션 ID
        """
        record = APICallRecord(
            timestamp=datetime.now(),
            endpoint=endpoint,
            method=method,
            response_time=response_time,
            request_size=request_size,
            response_size=response_size,
            status_code=status_code,
            success=success,
            error_message=error_message,
            user_agent=user_agent,
            ip_address=ip_address,
            session_id=session_id
        )
        
        # 메모리에 저장
        self._call_history.append(record)
        
        # 데이터베이스에 비동기 저장
        threading.Thread(target=self._save_to_db, args=(record,), daemon=True).start()
        
        # 통계 캐시 무효화
        self._invalidate_stats_cache(endpoint)
        
        self._logger.debug(f"API 호출 기록: {method} {endpoint} - {response_time:.0f}ms")
    
    def _save_to_db(self, record: APICallRecord):
        """데이터베이스에 저장"""
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute('''
                    INSERT INTO api_calls 
                    (timestamp, endpoint, method, response_time, request_size, 
                     response_size, status_code, success, error_message, 
                     user_agent, ip_address, session_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    record.timestamp.isoformat(), record.endpoint, record.method,
                    record.response_time, record.request_size, record.response_size,
                    record.status_code, 1 if record.success else 0, record.error_message,
                    record.user_agent, record.ip_address, record.session_id
                ))
                conn.commit()
                
        except Exception as e:
            self._logger.error(f"API 호출 기록 저장 중 오류: {e}", exc_info=True)
    
    def _invalidate_stats_cache(self, endpoint: str):
        """통계 캐시 무효화"""
        if endpoint in self._stats_cache:
            del self._stats_cache[endpoint]
        if endpoint in self._cache_expiry:
            del self._cache_expiry[endpoint]
    
    def get_api_statistics(self, endpoint: str, hours: int = 24) -> Optional[APIStatistics]:
        """API 통계 조회
        
        Args:
            endpoint: API 엔드포인트
            hours: 분석 기간 (시간)
            
        Returns:
            API 통계 정보
        """
        cache_key = f"{endpoint}_{hours}h"
        
        # 캐시 확인
        if (cache_key in self._stats_cache and 
            cache_key in self._cache_expiry and
            datetime.now() < self._cache_expiry[cache_key]):
            return self._stats_cache[cache_key]
        
        try:
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=hours)
            
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.execute('''
                    SELECT response_time, request_size, response_size, 
                           status_code, success, error_message
                    FROM api_calls
                    WHERE endpoint = ? AND timestamp >= ? AND timestamp <= ?
                    ORDER BY timestamp
                ''', (endpoint, start_time.isoformat(), end_time.isoformat()))
                
                records = cursor.fetchall()
                
                if not records:
                    return None
                
                # 통계 계산
                response_times = [r[0] for r in records]
                request_sizes = [r[1] for r in records if r[1] is not None]
                response_sizes = [r[2] for r in records if r[2] is not None]
                
                total_calls = len(records)
                successful_calls = sum(1 for r in records if r[4] == 1)
                failed_calls = total_calls - successful_calls
                error_rate = (failed_calls / total_calls * 100) if total_calls > 0 else 0
                
                # 응답 시간 통계
                avg_response_time = sum(response_times) / len(response_times)
                min_response_time = min(response_times)
                max_response_time = max(response_times)
                
                # P95 계산
                sorted_times = sorted(response_times)
                p95_index = int(len(sorted_times) * 0.95)
                p95_response_time = sorted_times[p95_index] if sorted_times else 0
                
                # 데이터 크기 통계
                total_request_size = sum(request_sizes)
                total_response_size = sum(response_sizes)
                avg_request_size = total_request_size / len(request_sizes) if request_sizes else 0
                avg_response_size = total_response_size / len(response_sizes) if response_sizes else 0
                
                # 에러 타입 분석
                error_types = defaultdict(int)
                for record in records:
                    if record[4] == 0 and record[5]:  # 실패한 호출
                        error_types[record[5]] += 1
                
                statistics = APIStatistics(
                    endpoint=endpoint,
                    period_start=start_time,
                    period_end=end_time,
                    total_calls=total_calls,
                    successful_calls=successful_calls,
                    failed_calls=failed_calls,
                    error_rate=error_rate,
                    avg_response_time=avg_response_time,
                    min_response_time=min_response_time,
                    max_response_time=max_response_time,
                    p95_response_time=p95_response_time,
                    total_request_size=total_request_size,
                    total_response_size=total_response_size,
                    avg_request_size=avg_request_size,
                    avg_response_size=avg_response_size,
                    error_types=dict(error_types)
                )
                
                # 캐시 저장 (5분간 유효)
                self._stats_cache[cache_key] = statistics
                self._cache_expiry[cache_key] = datetime.now() + timedelta(minutes=5)
                
                return statistics
                
        except Exception as e:
            self._logger.error(f"API 통계 조회 중 오류: {e}", exc_info=True)
            return None
    
    def get_recent_calls(self, minutes: int = 60) -> List[APICallRecord]:
        """최근 API 호출 기록 반환"""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        return [
            call for call in self._call_history
            if call.timestamp >= cutoff_time
        ]
    
    def get_endpoint_list(self) -> List[str]:
        """추적 중인 엔드포인트 목록 반환"""
        try:
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.execute('SELECT DISTINCT endpoint FROM api_calls')
                return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            self._logger.error(f"엔드포인트 목록 조회 중 오류: {e}", exc_info=True)
            return []
    
    def generate_traffic_report(self, hours: int = 24) -> Dict[str, Any]:
        """트래픽 리포트 생성"""
        try:
            endpoints = self.get_endpoint_list()
            endpoint_stats = {}
            
            total_calls = 0
            total_errors = 0
            total_response_time = 0
            
            for endpoint in endpoints:
                stats = self.get_api_statistics(endpoint, hours)
                if stats:
                    endpoint_stats[endpoint] = stats.to_dict()
                    total_calls += stats.total_calls
                    total_errors += stats.failed_calls
                    total_response_time += stats.avg_response_time * stats.total_calls
            
            overall_avg_response_time = (total_response_time / total_calls) if total_calls > 0 else 0
            overall_error_rate = (total_errors / total_calls * 100) if total_calls > 0 else 0
            
            return {
                'period_hours': hours,
                'generated_at': datetime.now().isoformat(),
                'summary': {
                    'total_calls': total_calls,
                    'total_errors': total_errors,
                    'overall_error_rate': overall_error_rate,
                    'overall_avg_response_time': overall_avg_response_time,
                    'endpoints_count': len(endpoints)
                },
                'endpoint_statistics': endpoint_stats
            }
            
        except Exception as e:
            self._logger.error(f"트래픽 리포트 생성 중 오류: {e}", exc_info=True)
            return {}

class SystemResourceTracker:
    """통합 시스템 리소스 추적기"""
    
    def __init__(self):
        """초기화"""
        self._logger = logger
        self._memory_tracker = MemoryTracker()
        self._api_tracker = APICallTracker()
        
        self._logger.info("SystemResourceTracker 초기화 완료")
    
    def start_all_tracking(self):
        """모든 추적 시작"""
        self._memory_tracker.start_tracking()
        self._logger.info("통합 리소스 추적 시작")
    
    def stop_all_tracking(self):
        """모든 추적 중지"""
        self._memory_tracker.stop_tracking()
        self._logger.info("통합 리소스 추적 중지")
    
    def get_memory_tracker(self) -> MemoryTracker:
        """메모리 추적기 반환"""
        return self._memory_tracker
    
    def get_api_tracker(self) -> APICallTracker:
        """API 추적기 반환"""
        return self._api_tracker
    
    def generate_comprehensive_report(self, hours: int = 24) -> Dict[str, Any]:
        """종합 리소스 리포트 생성"""
        return {
            'generated_at': datetime.now().isoformat(),
            'period_hours': hours,
            'memory_analysis': self._memory_tracker.analyze_memory_trends(hours),
            'api_traffic': self._api_tracker.generate_traffic_report(hours)
        }

# 글로벌 인스턴스
_resource_tracker_instance: Optional[SystemResourceTracker] = None

def get_system_resource_tracker() -> SystemResourceTracker:
    """시스템 리소스 추적기 인스턴스 반환 (싱글톤)"""
    global _resource_tracker_instance
    if _resource_tracker_instance is None:
        _resource_tracker_instance = SystemResourceTracker()
    return _resource_tracker_instance 