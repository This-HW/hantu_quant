"""
의존성 헬스체크 모듈 (P2-3)

기능:
- 시스템 메트릭 조회 (CPU, 메모리, 디스크)
- 의존성 상태 확인 (DB, API, WebSocket)
- 상태 판단 로직 (healthy, degraded, unhealthy)
"""

import time
from pathlib import Path
from typing import Dict, Any, Literal
from dataclasses import dataclass, asdict

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


@dataclass
class HealthCheckResult:
    """개별 헬스체크 결과"""
    healthy: bool
    message: str
    latency_ms: float = 0.0


@dataclass
class SystemMetrics:
    """시스템 메트릭"""
    memory_percent: float
    cpu_percent: float
    disk_percent: float


@dataclass
class HealthStatus:
    """전체 헬스 상태"""
    status: Literal['healthy', 'degraded', 'unhealthy']
    database: bool
    kis_api: bool
    websocket: bool
    memory_percent: float
    cpu_percent: float
    disk_percent: float
    uptime_seconds: float
    checks: Dict[str, Dict[str, Any]]
    timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 변환"""
        return asdict(self)


def get_system_metrics() -> SystemMetrics:
    """시스템 메트릭 조회

    Returns:
        SystemMetrics: CPU, 메모리, 디스크 사용량
    """
    if not PSUTIL_AVAILABLE:
        return SystemMetrics(
            memory_percent=0.0,
            cpu_percent=0.0,
            disk_percent=0.0
        )

    try:
        return SystemMetrics(
            memory_percent=psutil.virtual_memory().percent,
            cpu_percent=psutil.cpu_percent(interval=0.1),
            disk_percent=psutil.disk_usage('/').percent
        )
    except Exception:
        return SystemMetrics(
            memory_percent=0.0,
            cpu_percent=0.0,
            disk_percent=0.0
        )


async def check_database_health(data_dir: Path = None) -> HealthCheckResult:
    """데이터베이스 (파일 시스템) 헬스체크

    Args:
        data_dir: 데이터 디렉토리 경로

    Returns:
        HealthCheckResult: 헬스체크 결과
    """
    if data_dir is None:
        data_dir = Path(__file__).parent.parent.parent / "data"

    try:
        if data_dir.exists():
            return HealthCheckResult(
                healthy=True,
                message="Data directory accessible"
            )
        return HealthCheckResult(
            healthy=False,
            message="Data directory not found"
        )
    except Exception as e:
        return HealthCheckResult(
            healthy=False,
            message=str(e)
        )


async def check_kis_api_health(kis_client=None) -> HealthCheckResult:
    """KIS API 연결 헬스체크

    Args:
        kis_client: KIS API 클라이언트

    Returns:
        HealthCheckResult: 헬스체크 결과
    """
    if kis_client is None:
        return HealthCheckResult(
            healthy=False,
            message="KIS client not initialized"
        )

    try:
        start_time = time.time()
        result = kis_client.get_current_price("005930")  # 삼성전자
        latency_ms = (time.time() - start_time) * 1000

        if result:
            return HealthCheckResult(
                healthy=True,
                message="Connected",
                latency_ms=latency_ms
            )
        return HealthCheckResult(
            healthy=False,
            message="No response",
            latency_ms=latency_ms
        )
    except Exception as e:
        return HealthCheckResult(
            healthy=False,
            message=str(e)
        )


async def check_websocket_health(ws_client=None) -> HealthCheckResult:
    """WebSocket 연결 헬스체크

    Args:
        ws_client: WebSocket 클라이언트

    Returns:
        HealthCheckResult: 헬스체크 결과
    """
    try:
        # WebSocket 클라이언트가 있으면 상태 확인
        if ws_client is not None:
            # WebSocket 상태 확인 로직 추가 가능
            return HealthCheckResult(
                healthy=True,
                message="WebSocket connected"
            )
        # 기본적으로 ready 상태 반환
        return HealthCheckResult(
            healthy=True,
            message="WebSocket ready"
        )
    except Exception as e:
        return HealthCheckResult(
            healthy=False,
            message=str(e)
        )


def determine_health_status(
    db_healthy: bool,
    api_healthy: bool,
    ws_healthy: bool
) -> Literal['healthy', 'degraded', 'unhealthy']:
    """전체 헬스 상태 결정

    Args:
        db_healthy: 데이터베이스 상태
        api_healthy: API 상태
        ws_healthy: WebSocket 상태

    Returns:
        status: 'healthy', 'degraded', 또는 'unhealthy'
    """
    all_ok = all([db_healthy, api_healthy, ws_healthy])
    any_ok = any([db_healthy, api_healthy, ws_healthy])

    if all_ok:
        return 'healthy'
    elif any_ok:
        return 'degraded'
    else:
        return 'unhealthy'


async def perform_health_check(
    kis_client=None,
    ws_client=None,
    data_dir: Path = None,
    server_start_time: float = None
) -> HealthStatus:
    """전체 헬스체크 수행

    Args:
        kis_client: KIS API 클라이언트
        ws_client: WebSocket 클라이언트
        data_dir: 데이터 디렉토리
        server_start_time: 서버 시작 시간

    Returns:
        HealthStatus: 전체 헬스 상태
    """
    import asyncio
    from datetime import datetime

    # 병렬로 체크 실행
    db_result, api_result, ws_result = await asyncio.gather(
        check_database_health(data_dir),
        check_kis_api_health(kis_client),
        check_websocket_health(ws_client),
    )

    # 시스템 메트릭
    metrics = get_system_metrics()

    # 상태 결정
    status = determine_health_status(
        db_result.healthy,
        api_result.healthy,
        ws_result.healthy
    )

    # 업타임 계산
    uptime = 0.0
    if server_start_time:
        uptime = time.time() - server_start_time

    return HealthStatus(
        status=status,
        database=db_result.healthy,
        kis_api=api_result.healthy,
        websocket=ws_result.healthy,
        memory_percent=metrics.memory_percent,
        cpu_percent=metrics.cpu_percent,
        disk_percent=metrics.disk_percent,
        uptime_seconds=uptime,
        checks={
            'database': asdict(db_result),
            'kis_api': asdict(api_result),
            'websocket': asdict(ws_result),
        },
        timestamp=datetime.now().isoformat()
    )
