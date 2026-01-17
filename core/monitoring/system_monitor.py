"""
시스템 모니터링 및 자동 알림 시스템
- 학습 시스템 상태 모니터링
- 성능 지표 추적
- 자동 알림 및 보고서 생성
- 이상 상황 감지 및 대응
"""

import json
import os
import psutil
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
import logging
import threading
import time

from ..utils.log_utils import get_logger
from ..utils.telegram_notifier import get_telegram_notifier
from ..learning.enhanced_adaptive_system import get_enhanced_adaptive_system
from ..data_pipeline.data_synchronizer import get_data_synchronizer

logger = get_logger(__name__)

@dataclass
class SystemAlert:
    """시스템 알림"""
    alert_id: str
    timestamp: str
    severity: str  # info, warning, critical
    category: str
    title: str
    description: str
    suggested_action: Optional[str] = None
    auto_resolved: bool = False

@dataclass
class PerformanceMetrics:
    """성능 메트릭"""
    timestamp: str
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    db_size_mb: float
    active_processes: int
    last_learning_time: Optional[str]
    learning_success_rate: float

@dataclass
class LearningHealthStatus:
    """학습 시스템 건강 상태"""
    overall_health: str  # healthy, warning, critical
    data_freshness_days: int
    prediction_accuracy: float
    system_uptime_hours: float
    last_maintenance: Optional[str]
    active_issues: List[str]

class SystemMonitor:
    """시스템 모니터링 클래스"""

    def __init__(self, monitoring_dir: str = "data/monitoring"):
        self.monitoring_dir = Path(monitoring_dir)
        self.monitoring_dir.mkdir(parents=True, exist_ok=True)

        self.logger = logger
        self.telegram_notifier = get_telegram_notifier()

        # 모니터링 설정
        self.monitoring_interval = 300  # 5분마다 체크
        self.alert_cooldown = 21600  # 6시간 쿨다운 (같은 알림 반복 방지)

        # 임계값 설정
        self.thresholds = {
            'cpu_usage': 80.0,
            'memory_usage': 85.0,
            'disk_usage': 90.0,
            'data_staleness_days': 2,
            'min_prediction_accuracy': 0.35,  # 35%로 낮춤 (초기 데이터 부족 고려)
            'min_trades_for_accuracy_check': 30,  # 최소 거래 수 (30건 이상일 때만 경고)
            'max_db_size_gb': 2.0
        }

        # 상태 추적
        self.is_monitoring = False
        self.monitoring_thread = None
        self.last_alerts = {}  # 알림 쿨다운 관리

        self.logger.info("시스템 모니터 초기화 완료")

    def start_monitoring(self):
        """모니터링 시작"""
        if self.is_monitoring:
            self.logger.warning("모니터링이 이미 실행 중입니다")
            return False

        self.is_monitoring = True
        self.monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitoring_thread.start()

        self.logger.info("시스템 모니터링 시작")
        return True

    def stop_monitoring(self):
        """모니터링 중지"""
        self.is_monitoring = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=10)

        self.logger.info("시스템 모니터링 중지")

    def _monitoring_loop(self):
        """모니터링 루프"""
        self.logger.info("모니터링 루프 시작")

        while self.is_monitoring:
            try:
                # 시스템 상태 체크
                self._check_system_health()

                # 학습 시스템 상태 체크
                self._check_learning_health()

                # 데이터 상태 체크
                self._check_data_health()

                # 성능 메트릭 수집
                self._collect_performance_metrics()

                # 정기 보고서 생성 (매일 한 번)
                self._check_daily_report()

                time.sleep(self.monitoring_interval)

            except Exception as e:
                self.logger.error(f"모니터링 루프 오류: {e}", exc_info=True)
                time.sleep(60)  # 오류 시 1분 대기

        self.logger.info("모니터링 루프 종료")

    def _check_system_health(self):
        """시스템 건강 상태 체크"""
        try:
            # CPU 사용률
            cpu_usage = psutil.cpu_percent(interval=1)
            if cpu_usage > self.thresholds['cpu_usage']:
                self._create_alert(
                    "high_cpu_usage",
                    "warning",
                    "system",
                    "높은 CPU 사용률",
                    f"CPU 사용률이 {cpu_usage:.1f}%입니다",
                    "시스템 리소스를 확인하고 불필요한 프로세스를 종료하세요"
                )

            # 메모리 사용률
            memory = psutil.virtual_memory()
            if memory.percent > self.thresholds['memory_usage']:
                self._create_alert(
                    "high_memory_usage",
                    "warning",
                    "system",
                    "높은 메모리 사용률",
                    f"메모리 사용률이 {memory.percent:.1f}%입니다",
                    "메모리를 많이 사용하는 프로세스를 확인하세요"
                )

            # 디스크 사용률
            disk = psutil.disk_usage('/')
            disk_usage_pct = (disk.used / disk.total) * 100
            if disk_usage_pct > self.thresholds['disk_usage']:
                self._create_alert(
                    "high_disk_usage",
                    "critical",
                    "system",
                    "디스크 공간 부족",
                    f"디스크 사용률이 {disk_usage_pct:.1f}%입니다",
                    "불필요한 파일을 삭제하거나 로그 정리를 실행하세요"
                )

        except Exception as e:
            self.logger.error(f"시스템 건강 상태 체크 실패: {e}", exc_info=True)

    def _check_learning_health(self):
        """학습 시스템 건강 상태 체크"""
        try:
            enhanced_system = get_enhanced_adaptive_system()
            health_check = enhanced_system.check_system_health()

            # 전체 상태 확인
            if health_check.get('overall_status') == 'critical':
                self._create_alert(
                    "learning_system_critical",
                    "critical",
                    "learning",
                    "학습 시스템 심각한 문제",
                    f"학습 시스템에 심각한 문제가 발생했습니다: {health_check.get('issues', [])}",
                    "시스템 유지보수를 즉시 실행하세요"
                )
            elif health_check.get('overall_status') == 'warning':
                self._create_alert(
                    "learning_system_warning",
                    "warning",
                    "learning",
                    "학습 시스템 경고",
                    f"학습 시스템에 경고사항이 있습니다: {health_check.get('issues', [])}",
                    "시스템 상태를 확인하고 필요시 조치하세요"
                )

            # 데이터 신선도 확인
            data_freshness = health_check.get('data_freshness', {})
            days_since_update = data_freshness.get('days_since_update', 999)

            if days_since_update > self.thresholds['data_staleness_days']:
                self._create_alert(
                    "stale_data",
                    "warning",
                    "data",
                    "데이터가 오래됨",
                    f"마지막 데이터 업데이트로부터 {days_since_update}일이 경과했습니다",
                    "스크리닝 시스템이 정상 작동하는지 확인하세요"
                )

            # 성능 지표 확인
            perf_metrics = health_check.get('performance_metrics', {})
            win_rate = perf_metrics.get('win_rate', 0) / 100
            total_trades = perf_metrics.get('total_trades', 0)

            # 최소 거래 수 이상일 때만 정확도 경고
            if (total_trades >= self.thresholds['min_trades_for_accuracy_check'] and
                win_rate < self.thresholds['min_prediction_accuracy']):
                self._create_alert(
                    "low_prediction_accuracy",
                    "warning",
                    "performance",
                    "예측 정확도 낮음",
                    f"현재 예측 승률이 {win_rate:.1%}로 낮습니다 (총 {total_trades}건)",
                    "학습 파라미터 조정이나 전략 재검토를 고려하세요"
                )

        except Exception as e:
            self.logger.error(f"학습 건강 상태 체크 실패: {e}", exc_info=True)

    def _get_database_size_gb(self) -> float:
        """데이터베이스 크기 조회 (GB 단위)

        PostgreSQL과 SQLite 모두 지원
        """
        try:
            from core.config import settings

            if settings.DB_TYPE == 'postgresql':
                # PostgreSQL: pg_database_size 쿼리 사용
                try:
                    from sqlalchemy import text
                    from core.database.session import DatabaseSession

                    db = DatabaseSession()
                    with db.get_session() as session:
                        result = session.execute(
                            text("SELECT pg_database_size(current_database())")
                        ).scalar()
                        return result / (1024**3) if result else 0.0
                except Exception as e:
                    self.logger.warning(f"PostgreSQL 크기 조회 실패: {e}")
                    return 0.0
            else:
                # SQLite: 파일 크기 확인
                db_path = Path(settings.DB_PATH)
                if db_path.exists():
                    return db_path.stat().st_size / (1024**3)
                return 0.0

        except Exception as e:
            self.logger.error(f"데이터베이스 크기 조회 실패: {e}", exc_info=True)
            return 0.0

    def _get_database_size_mb(self) -> float:
        """데이터베이스 크기 조회 (MB 단위)"""
        return self._get_database_size_gb() * 1024

    def _check_data_health(self):
        """데이터 건강 상태 체크"""
        try:
            # 데이터베이스 크기 확인
            db_size_gb = self._get_database_size_gb()

            if db_size_gb > self.thresholds['max_db_size_gb']:
                self._create_alert(
                    "large_database",
                    "warning",
                    "data",
                    "데이터베이스 크기 증가",
                    f"데이터베이스 크기가 {db_size_gb:.2f}GB입니다",
                    "데이터 정리나 아카이빙을 고려하세요"
                )

            # 중요 디렉토리 존재 확인
            critical_dirs = [
                "data/watchlist",
                "data/daily_selection",
                "data/learning",
                "data/trades"
            ]

            for dir_path in critical_dirs:
                if not Path(dir_path).exists():
                    self._create_alert(
                        f"missing_directory_{dir_path.replace('/', '_')}",
                        "critical",
                        "data",
                        "중요 디렉토리 누락",
                        f"필수 디렉토리 {dir_path}가 존재하지 않습니다",
                        f"디렉토리를 생성하고 관련 시스템을 재시작하세요"
                    )

        except Exception as e:
            self.logger.error(f"데이터 건강 상태 체크 실패: {e}", exc_info=True)

    def _collect_performance_metrics(self):
        """성능 메트릭 수집"""
        try:
            # 시스템 리소스
            cpu_usage = psutil.cpu_percent()
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            # 데이터베이스 크기 (공통 메서드 사용)
            db_size_mb = self._get_database_size_mb()

            # 활성 프로세스 수
            active_processes = len([p for p in psutil.process_iter() if p.is_running()])

            # 마지막 학습 시간
            learning_history_file = Path("data/learning/enhanced_adaptation_history.json")
            last_learning_time = None
            if learning_history_file.exists():
                try:
                    with open(learning_history_file, 'r', encoding='utf-8') as f:
                        history = json.load(f)
                    if history:
                        last_learning_time = history[-1].get('date')
                except:
                    pass

            # 학습 성공률 (간단한 추정)
            learning_success_rate = 0.85  # 기본값, 실제로는 더 정교한 계산 필요

            metrics = PerformanceMetrics(
                timestamp=datetime.now().isoformat(),
                cpu_usage=cpu_usage,
                memory_usage=memory.percent,
                disk_usage=(disk.used / disk.total) * 100,
                db_size_mb=db_size_mb,
                active_processes=active_processes,
                last_learning_time=last_learning_time,
                learning_success_rate=learning_success_rate
            )

            # 메트릭 저장
            self._save_performance_metrics(metrics)

        except Exception as e:
            self.logger.error(f"성능 메트릭 수집 실패: {e}", exc_info=True)

    def _save_performance_metrics(self, metrics: PerformanceMetrics):
        """성능 메트릭 저장"""
        try:
            metrics_file = self.monitoring_dir / "performance_metrics.json"

            # 기존 메트릭 로드
            metrics_list = []
            if metrics_file.exists():
                with open(metrics_file, 'r', encoding='utf-8') as f:
                    metrics_list = json.load(f)

            # 새 메트릭 추가
            metrics_list.append(asdict(metrics))

            # 최근 1440개만 유지 (5분 간격으로 5일치)
            metrics_list = metrics_list[-1440:]

            # 저장
            with open(metrics_file, 'w', encoding='utf-8') as f:
                json.dump(metrics_list, f, indent=2, ensure_ascii=False)

        except Exception as e:
            self.logger.error(f"성능 메트릭 저장 실패: {e}", exc_info=True)

    def _create_alert(
        self,
        alert_id: str,
        severity: str,
        category: str,
        title: str,
        description: str,
        suggested_action: Optional[str] = None
    ):
        """알림 생성"""
        try:
            # 쿨다운 체크
            now = datetime.now()
            if alert_id in self.last_alerts:
                last_alert_time = self.last_alerts[alert_id]
                if (now - last_alert_time).seconds < self.alert_cooldown:
                    return  # 쿨다운 중이므로 알림 건너뛰기

            alert = SystemAlert(
                alert_id=alert_id,
                timestamp=now.isoformat(),
                severity=severity,
                category=category,
                title=title,
                description=description,
                suggested_action=suggested_action
            )

            # 알림 저장
            self._save_alert(alert)

            # 텔레그램 알림 전송
            if severity in ['warning', 'critical']:
                self._send_telegram_alert(alert)

            # 쿨다운 업데이트
            self.last_alerts[alert_id] = now

            self.logger.warning(f"알림 생성: {title} - {description}")

        except Exception as e:
            self.logger.error(f"알림 생성 실패: {e}", exc_info=True)

    def _save_alert(self, alert: SystemAlert):
        """알림 저장"""
        try:
            alerts_file = self.monitoring_dir / "system_alerts.json"

            # 기존 알림 로드
            alerts = []
            if alerts_file.exists():
                with open(alerts_file, 'r', encoding='utf-8') as f:
                    alerts = json.load(f)

            # 새 알림 추가
            alerts.append(asdict(alert))

            # 최근 1000개만 유지
            alerts = alerts[-1000:]

            # 저장
            with open(alerts_file, 'w', encoding='utf-8') as f:
                json.dump(alerts, f, indent=2, ensure_ascii=False)

        except Exception as e:
            self.logger.error(f"알림 저장 실패: {e}", exc_info=True)

    def _send_telegram_alert(self, alert: SystemAlert):
        """텔레그램 알림 전송"""
        try:
            if not self.telegram_notifier.is_enabled():
                return

            # 심각도에 따른 이모지
            emoji_map = {
                'info': 'ℹ️',
                'warning': '⚠️',
                'critical': '🚨'
            }

            emoji = emoji_map.get(alert.severity, 'ℹ️')

            message = f"""{emoji} *시스템 알림*

🏷️ *카테고리*: {alert.category}
📢 *제목*: {alert.title}
📝 *설명*: {alert.description}"""

            if alert.suggested_action:
                message += f"\n\n💡 *권장 조치*: {alert.suggested_action}"

            message += f"\n\n⏰ 시간: `{alert.timestamp}`"

            # 심각도에 따라 우선순위 설정
            priority = "high" if alert.severity == "critical" else "normal"

            success = self.telegram_notifier.send_message(message, priority)
            if success:
                self.logger.info(f"텔레그램 알림 전송 완료: {alert.title}")
            else:
                self.logger.warning(f"텔레그램 알림 전송 실패: {alert.title}")

        except Exception as e:
            self.logger.error(f"텔레그램 알림 전송 오류: {e}", exc_info=True)

    def _check_daily_report(self):
        """일일 보고서 생성 체크"""
        try:
            # 마지막 보고서 시간 확인
            report_file = self.monitoring_dir / "last_daily_report.json"

            now = datetime.now()
            should_generate = False

            if report_file.exists():
                with open(report_file, 'r', encoding='utf-8') as f:
                    last_report = json.load(f)

                last_date = datetime.fromisoformat(last_report['date'])

                # 마지막 보고서가 어제 이전이고, 현재 시간이 오후 6시 이후면 생성
                if (now.date() > last_date.date() and now.hour >= 18):
                    should_generate = True
            else:
                # 첫 실행이면 오후 6시 이후 생성
                if now.hour >= 18:
                    should_generate = True

            if should_generate:
                self._generate_daily_report()

                # 보고서 생성 시간 기록
                with open(report_file, 'w', encoding='utf-8') as f:
                    json.dump({'date': now.isoformat()}, f)

        except Exception as e:
            self.logger.error(f"일일 보고서 체크 실패: {e}", exc_info=True)

    def _generate_daily_report(self):
        """일일 모니터링 보고서 생성"""
        try:
            self.logger.info("일일 모니터링 보고서 생성 시작")

            # 오늘의 알림 수집
            alerts_file = self.monitoring_dir / "system_alerts.json"
            today_alerts = []

            if alerts_file.exists():
                with open(alerts_file, 'r', encoding='utf-8') as f:
                    all_alerts = json.load(f)

                today = datetime.now().strftime('%Y-%m-%d')
                today_alerts = [
                    alert for alert in all_alerts
                    if alert['timestamp'].startswith(today)
                ]

            # 성능 메트릭 요약
            metrics_file = self.monitoring_dir / "performance_metrics.json"
            avg_metrics = {}

            if metrics_file.exists():
                with open(metrics_file, 'r', encoding='utf-8') as f:
                    all_metrics = json.load(f)

                # 최근 24시간 데이터 (5분 간격 = 288개)
                recent_metrics = all_metrics[-288:]

                if recent_metrics:
                    avg_metrics = {
                        'avg_cpu_usage': sum(m['cpu_usage'] for m in recent_metrics) / len(recent_metrics),
                        'avg_memory_usage': sum(m['memory_usage'] for m in recent_metrics) / len(recent_metrics),
                        'avg_disk_usage': sum(m['disk_usage'] for m in recent_metrics) / len(recent_metrics),
                        'current_db_size_mb': recent_metrics[-1]['db_size_mb']
                    }

            # 학습 시스템 상태
            enhanced_system = get_enhanced_adaptive_system()
            system_health = enhanced_system.check_system_health()

            # 보고서 생성
            report = {
                'date': datetime.now().isoformat(),
                'summary': {
                    'total_alerts': len(today_alerts),
                    'critical_alerts': len([a for a in today_alerts if a['severity'] == 'critical']),
                    'warning_alerts': len([a for a in today_alerts if a['severity'] == 'warning']),
                    'system_health': system_health.get('overall_status', 'unknown')
                },
                'performance_metrics': avg_metrics,
                'system_health_details': system_health,
                'alerts_today': today_alerts
            }

            # 보고서 저장
            report_file = self.monitoring_dir / f"daily_report_{datetime.now().strftime('%Y%m%d')}.json"
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)

            # 텔레그램으로 요약 전송
            self._send_daily_report_summary(report)

            self.logger.info("일일 모니터링 보고서 생성 완료")

        except Exception as e:
            self.logger.error(f"일일 보고서 생성 실패: {e}", exc_info=True)

    def _send_daily_report_summary(self, report: Dict[str, Any]):
        """일일 보고서 요약 전송"""
        try:
            if not self.telegram_notifier.is_enabled():
                return

            summary = report['summary']
            metrics = report['performance_metrics']

            # 상태 이모지
            health_emoji = {
                'healthy': '🟢',
                'warning': '🟡',
                'critical': '🔴',
                'unknown': '⚪'
            }

            health_status = summary['system_health']
            emoji = health_emoji.get(health_status, '⚪')

            # DB 타입 확인
            try:
                from core.config import settings
                db_type = settings.DB_TYPE.upper()
            except Exception:
                db_type = "DB"

            # 현재 DB 크기 (실시간 조회)
            current_db_size_mb = self._get_database_size_mb()

            message = f"""📊 *일일 시스템 모니터링 보고서*

{emoji} *전체 상태*: {health_status.upper()}

🚨 *오늘의 알림*:
• 총 알림: {summary['total_alerts']}건
• 심각: {summary['critical_alerts']}건
• 경고: {summary['warning_alerts']}건

💻 *평균 시스템 사용률* (24시간):"""

            if metrics:
                message += f"""
• CPU: {metrics.get('avg_cpu_usage', 0):.1f}%
• 메모리: {metrics.get('avg_memory_usage', 0):.1f}%
• 디스크: {metrics.get('avg_disk_usage', 0):.1f}%
• {db_type} 크기: {current_db_size_mb:.1f}MB"""

            message += f"""

📅 날짜: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`

🔍 *자세한 내용은 시스템 로그를 확인하세요*"""

            success = self.telegram_notifier.send_message(message, "normal")
            if success:
                self.logger.info("일일 보고서 요약 전송 완료")
            else:
                self.logger.warning("일일 보고서 요약 전송 실패")

        except Exception as e:
            self.logger.error(f"일일 보고서 요약 전송 오류: {e}", exc_info=True)

    def get_system_status(self) -> Dict[str, Any]:
        """현재 시스템 상태 조회"""
        try:
            # 최신 메트릭 조회
            metrics_file = self.monitoring_dir / "performance_metrics.json"
            latest_metrics = None

            if metrics_file.exists():
                with open(metrics_file, 'r', encoding='utf-8') as f:
                    all_metrics = json.load(f)
                if all_metrics:
                    latest_metrics = all_metrics[-1]

            # 최근 알림 조회 (24시간)
            alerts_file = self.monitoring_dir / "system_alerts.json"
            recent_alerts = []

            if alerts_file.exists():
                with open(alerts_file, 'r', encoding='utf-8') as f:
                    all_alerts = json.load(f)

                cutoff_time = datetime.now() - timedelta(hours=24)
                recent_alerts = [
                    alert for alert in all_alerts
                    if datetime.fromisoformat(alert['timestamp']) > cutoff_time
                ]

            # 학습 시스템 상태
            enhanced_system = get_enhanced_adaptive_system()
            learning_health = enhanced_system.check_system_health()

            return {
                'monitoring_active': self.is_monitoring,
                'timestamp': datetime.now().isoformat(),
                'latest_metrics': latest_metrics,
                'recent_alerts_count': len(recent_alerts),
                'critical_alerts_count': len([a for a in recent_alerts if a['severity'] == 'critical']),
                'learning_system_health': learning_health,
                'thresholds': self.thresholds
            }

        except Exception as e:
            self.logger.error(f"시스템 상태 조회 실패: {e}", exc_info=True)
            return {'error': str(e)}

    def run_maintenance_check(self) -> Dict[str, Any]:
        """유지보수 필요성 체크"""
        try:
            enhanced_system = get_enhanced_adaptive_system()

            # 시스템 건강 상태 확인
            health_check = enhanced_system.check_system_health()

            # 유지보수 필요성 판단
            needs_maintenance = False
            maintenance_reasons = []

            if health_check.get('overall_status') in ['warning', 'critical']:
                needs_maintenance = True
                maintenance_reasons.append("시스템 건강 상태 이상")

            # 데이터베이스 크기 확인
            db_health = health_check.get('database_health', {})
            total_records = db_health.get('total_records', 0)
            if total_records > 50000:  # 5만 레코드 이상
                needs_maintenance = True
                maintenance_reasons.append("데이터베이스 크기 증가")

            # 마지막 유지보수 시간 확인
            try:
                maintenance_file = Path("data/learning/last_maintenance.json")
                if maintenance_file.exists():
                    with open(maintenance_file, 'r', encoding='utf-8') as f:
                        last_maintenance = json.load(f)

                    last_time = datetime.fromisoformat(last_maintenance['timestamp'])
                    days_since = (datetime.now() - last_time).days

                    if days_since > 7:  # 1주일 이상
                        needs_maintenance = True
                        maintenance_reasons.append(f"마지막 유지보수로부터 {days_since}일 경과")
                else:
                    needs_maintenance = True
                    maintenance_reasons.append("유지보수 이력 없음")

            except Exception:
                needs_maintenance = True
                maintenance_reasons.append("유지보수 이력 확인 불가")

            # 자동 유지보수 실행 (필요시)
            maintenance_result = None
            if needs_maintenance:
                self.logger.info("자동 유지보수 실행 필요")
                maintenance_result = enhanced_system.run_maintenance()

                # 유지보수 이력 저장
                maintenance_record = {
                    'timestamp': datetime.now().isoformat(),
                    'reasons': maintenance_reasons,
                    'result': maintenance_result
                }

                maintenance_file = Path("data/learning/last_maintenance.json")
                with open(maintenance_file, 'w', encoding='utf-8') as f:
                    json.dump(maintenance_record, f, indent=2, ensure_ascii=False)

            return {
                'needs_maintenance': needs_maintenance,
                'reasons': maintenance_reasons,
                'maintenance_executed': maintenance_result is not None,
                'maintenance_result': maintenance_result,
                'health_status': health_check
            }

        except Exception as e:
            self.logger.error(f"유지보수 체크 실패: {e}", exc_info=True)
            return {'error': str(e)}

# 싱글톤 인스턴스
_system_monitor = None

def get_system_monitor() -> SystemMonitor:
    """시스템 모니터 싱글톤 인스턴스 반환"""
    global _system_monitor
    if _system_monitor is None:
        _system_monitor = SystemMonitor()
    return _system_monitor