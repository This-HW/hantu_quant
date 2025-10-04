"""
자동 매매 시스템 헬스체크 모니터링
- 매매 실행 여부 모니터링
- 오류 발생 감지 및 알림
- 이상 상태 감지 (매매 미실행, 반복 실패 등)
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict

from ..utils.log_utils import get_logger
from ..utils.telegram_notifier import get_telegram_notifier

logger = get_logger(__name__)


@dataclass
class HealthCheckResult:
    """헬스체크 결과"""
    timestamp: str
    is_healthy: bool
    issues: List[str]
    warnings: List[str]
    metrics: Dict[str, any]


class TradingHealthChecker:
    """자동 매매 헬스체크"""

    def __init__(self):
        self.logger = logger
        self.notifier = get_telegram_notifier()
        self.data_dir = Path("data/health_check")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # 헬스체크 설정
        self.check_interval = 300  # 5분마다 체크
        self.error_threshold = 3   # 3회 연속 오류 시 알림
        self.no_trade_alert_hours = 2  # 2시간 동안 매매 없으면 알림

        # 상태 추적
        self.consecutive_errors = 0
        self.last_successful_trade = None
        self.last_health_check = None
        self.last_alert_sent = None

        self.logger.info("TradingHealthChecker 초기화 완료")

    def check_trading_health(self) -> HealthCheckResult:
        """종합 헬스체크 실행"""
        timestamp = datetime.now()
        issues = []
        warnings = []
        metrics = {}

        try:
            # 1. 매매 엔진 실행 상태 확인
            engine_status = self._check_engine_status()
            metrics['engine_running'] = engine_status['is_running']

            if not engine_status['is_running']:
                issues.append("매매 엔진이 실행 중이 아닙니다")

            # 2. 최근 매매 활동 확인
            trade_activity = self._check_trade_activity()
            metrics['recent_trades'] = trade_activity['count']
            metrics['last_trade_time'] = trade_activity['last_time']

            if trade_activity['should_alert']:
                issues.append(
                    f"장 시간 중 {trade_activity['hours_since_trade']}시간 동안 매매가 없습니다"
                )

            # 3. 오류 로그 확인
            error_check = self._check_error_logs()
            metrics['recent_errors'] = error_check['count']

            if error_check['count'] > 0:
                warnings.append(f"최근 1시간 내 {error_check['count']}건의 오류 발생")

            if error_check['critical_errors']:
                for error in error_check['critical_errors']:
                    issues.append(f"심각한 오류: {error}")

            # 4. API 연결 상태 확인
            api_status = self._check_api_connection()
            metrics['api_connected'] = api_status['connected']

            if not api_status['connected']:
                issues.append(f"API 연결 실패: {api_status.get('error', '알 수 없음')}")

            # 5. 일일 선정 파일 존재 확인
            selection_status = self._check_daily_selection()
            metrics['selection_file_exists'] = selection_status['exists']
            metrics['selection_count'] = selection_status['count']

            if not selection_status['exists']:
                issues.append("오늘 날짜의 일일 선정 파일이 없습니다")
            elif selection_status['count'] == 0:
                warnings.append("일일 선정 종목이 0개입니다")

            # 6. 계좌 잔고 확인
            balance_status = self._check_account_balance()
            metrics['available_cash'] = balance_status['cash']
            metrics['total_assets'] = balance_status['total']

            if balance_status['cash'] <= 0:
                warnings.append("가용 현금이 0원입니다 (매매 불가)")

            # 7. 시스템 리소스 확인
            resource_status = self._check_system_resources()
            metrics['cpu_usage'] = resource_status.get('cpu', 0)
            metrics['memory_usage'] = resource_status.get('memory', 0)

            if resource_status.get('cpu', 0) > 90:
                warnings.append(f"CPU 사용률 높음: {resource_status['cpu']}%")

            # 전체 건강 상태 판단
            is_healthy = len(issues) == 0

            result = HealthCheckResult(
                timestamp=timestamp.isoformat(),
                is_healthy=is_healthy,
                issues=issues,
                warnings=warnings,
                metrics=metrics
            )

            # 상태 저장
            self._save_health_check(result)

            # 문제 발생 시 자동 복구 시도
            if not is_healthy:
                recovery_results = self._attempt_auto_recovery(issues)
                result.metrics['recovery_attempted'] = recovery_results['attempted']
                result.metrics['recovery_succeeded'] = recovery_results['succeeded']

                # 복구 후 알림 전송 (우선순위 결정)
                self._send_health_alert(result, recovery_results)

            self.last_health_check = timestamp

            return result

        except Exception as e:
            self.logger.error(f"헬스체크 실행 실패: {e}")
            return HealthCheckResult(
                timestamp=timestamp.isoformat(),
                is_healthy=False,
                issues=[f"헬스체크 실행 오류: {e}"],
                warnings=[],
                metrics={}
            )

    def _check_engine_status(self) -> Dict:
        """매매 엔진 상태 확인"""
        try:
            from ..trading.trading_engine import get_trading_engine
            engine = get_trading_engine()
            status = engine.get_status()

            return {
                'is_running': status['is_running'],
                'positions': status['positions_count'],
                'daily_trades': status['daily_trades']
            }
        except Exception as e:
            self.logger.error(f"엔진 상태 확인 실패: {e}")
            return {'is_running': False, 'error': str(e)}

    def _check_trade_activity(self) -> Dict:
        """최근 매매 활동 확인"""
        try:
            from ..trading.trade_journal import TradeJournal
            journal = TradeJournal()

            # 오늘 거래 내역 조회
            today = datetime.now().strftime("%Y%m%d")
            trades_file = journal._base_dir / f"trades_{today}.json"

            if not trades_file.exists():
                return {
                    'count': 0,
                    'last_time': None,
                    'should_alert': self._is_market_hours() and self._should_have_trades(),
                    'hours_since_trade': None
                }

            with open(trades_file, 'r', encoding='utf-8') as f:
                trades = json.load(f)

            if not trades:
                hours_since_start = self._hours_since_market_open()
                return {
                    'count': 0,
                    'last_time': None,
                    'should_alert': hours_since_start > self.no_trade_alert_hours,
                    'hours_since_trade': hours_since_start
                }

            # 마지막 거래 시간
            last_trade = trades[-1]
            last_time = datetime.fromisoformat(last_trade['timestamp'])
            hours_since = (datetime.now() - last_time).total_seconds() / 3600

            should_alert = (
                self._is_market_hours() and
                hours_since > self.no_trade_alert_hours
            )

            return {
                'count': len(trades),
                'last_time': last_time.isoformat(),
                'should_alert': should_alert,
                'hours_since_trade': hours_since
            }

        except Exception as e:
            self.logger.error(f"거래 활동 확인 실패: {e}")
            return {'count': 0, 'last_time': None, 'should_alert': False, 'hours_since_trade': None}

    def _check_error_logs(self) -> Dict:
        """최근 오류 로그 확인"""
        try:
            log_file = Path(f"logs/{datetime.now().strftime('%Y%m%d')}.log")

            if not log_file.exists():
                return {'count': 0, 'critical_errors': []}

            # 최근 1시간 로그 확인
            one_hour_ago = datetime.now() - timedelta(hours=1)

            error_count = 0
            critical_errors = []

            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if 'ERROR' in line or 'CRITICAL' in line:
                        # 타임스탬프 파싱
                        try:
                            timestamp_str = line.split(' - ')[0]
                            log_time = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S,%f')

                            if log_time > one_hour_ago:
                                error_count += 1

                                # 심각한 오류 패턴 감지
                                if any(pattern in line for pattern in [
                                    'asyncio',
                                    'ImportError',
                                    'ModuleNotFoundError',
                                    'AttributeError',
                                    'API 연결 실패',
                                    '매매 실행 오류'
                                ]):
                                    # 오류 메시지 추출
                                    error_msg = line.split('ERROR - ')[-1].strip()[:100]
                                    critical_errors.append(error_msg)
                        except:
                            continue

            return {
                'count': error_count,
                'critical_errors': critical_errors[:5]  # 최대 5개만
            }

        except Exception as e:
            self.logger.error(f"오류 로그 확인 실패: {e}")
            return {'count': 0, 'critical_errors': []}

    def _check_api_connection(self) -> Dict:
        """API 연결 상태 확인"""
        try:
            from ..config.api_config import APIConfig
            config = APIConfig()

            # 토큰 유효성 확인
            is_valid = config.ensure_valid_token()

            return {
                'connected': is_valid,
                'server': config.server
            }

        except Exception as e:
            self.logger.error(f"API 연결 확인 실패: {e}")
            return {'connected': False, 'error': str(e)}

    def _check_daily_selection(self) -> Dict:
        """일일 선정 파일 확인"""
        try:
            today = datetime.now().strftime("%Y%m%d")
            selection_file = Path(f"data/daily_selection/daily_selection_{today}.json")

            if not selection_file.exists():
                return {'exists': False, 'count': 0}

            with open(selection_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            count = len(data.get('data', {}).get('selected_stocks', []))

            return {'exists': True, 'count': count}

        except Exception as e:
            self.logger.error(f"일일 선정 확인 실패: {e}")
            return {'exists': False, 'count': 0}

    def _check_account_balance(self) -> Dict:
        """계좌 잔고 확인"""
        try:
            from ..api.kis_api import KISAPI
            api = KISAPI()
            balance = api.get_balance()

            if not balance:
                return {'cash': 0, 'total': 0}

            return {
                'cash': balance.get('deposit', 0),
                'total': balance.get('deposit', 0) + balance.get('total_eval_amount', 0)
            }

        except Exception as e:
            self.logger.error(f"잔고 확인 실패: {e}")
            return {'cash': 0, 'total': 0}

    def _check_system_resources(self) -> Dict:
        """시스템 리소스 확인"""
        try:
            import psutil

            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()

            return {
                'cpu': cpu_percent,
                'memory': memory.percent
            }

        except Exception as e:
            self.logger.error(f"시스템 리소스 확인 실패: {e}")
            return {}

    def _is_market_hours(self) -> bool:
        """현재 장 시간인지 확인"""
        now = datetime.now()

        # 주말 제외
        if now.weekday() >= 5:
            return False

        # 장 시간: 09:00 ~ 15:30
        market_start = now.replace(hour=9, minute=0, second=0)
        market_end = now.replace(hour=15, minute=30, second=0)

        return market_start <= now <= market_end

    def _should_have_trades(self) -> bool:
        """지금까지 거래가 있어야 하는지 판단"""
        # 장 시작 후 1시간 이상 경과 시 거래가 있어야 함
        return self._hours_since_market_open() > 1

    def _hours_since_market_open(self) -> float:
        """장 시작 이후 경과 시간 (시간 단위)"""
        now = datetime.now()
        market_start = now.replace(hour=9, minute=0, second=0)

        if now < market_start:
            return 0

        return (now - market_start).total_seconds() / 3600

    def _save_health_check(self, result: HealthCheckResult):
        """헬스체크 결과 저장"""
        try:
            today = datetime.now().strftime("%Y%m%d")
            health_file = self.data_dir / f"health_check_{today}.json"

            # 기존 데이터 로드
            if health_file.exists():
                with open(health_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                data = []

            # 새 결과 추가
            data.append(asdict(result))

            # 저장
            with open(health_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            self.logger.error(f"헬스체크 결과 저장 실패: {e}")

    def _attempt_auto_recovery(self, issues: List[str]) -> Dict:
        """자동 복구 시도"""
        try:
            from .auto_recovery_system import get_recovery_system

            recovery_system = get_recovery_system()
            recovery_results = recovery_system.attempt_recovery(issues)

            self.logger.info(
                f"자동 복구 완료: 시도 {recovery_results['attempted']}건, "
                f"성공 {recovery_results['succeeded']}건, 실패 {recovery_results['failed']}건"
            )

            return recovery_results

        except Exception as e:
            self.logger.error(f"자동 복구 시도 실패: {e}")
            return {
                'attempted': 0,
                'succeeded': 0,
                'failed': 0,
                'actions': [],
                'unrecoverable': issues
            }

    def _determine_alert_priority(self, result: HealthCheckResult, recovery_results: Dict) -> str:
        """알림 우선순위 결정"""
        # 1. critical: 시스템 완전 중단 상태
        critical_keywords = ['매매 엔진', 'API 연결 실패', '심각한 오류']
        has_critical = any(
            any(keyword in issue for keyword in critical_keywords)
            for issue in result.issues
        )

        # 복구 실패 시 critical
        if has_critical and recovery_results.get('succeeded', 0) == 0:
            return 'critical'

        # 2. emergency: 긴급 대응 필요하지만 복구 시도됨
        if has_critical and recovery_results.get('succeeded', 0) > 0:
            return 'emergency'

        # 3. high: 중요한 문제 (매매 영향 있음)
        if len(result.issues) > 2 or result.metrics.get('recent_errors', 0) > 5:
            return 'high'

        # 4. normal: 일반 문제
        if len(result.issues) > 0:
            return 'normal'

        # 5. low: 경고만 있음
        return 'low'

    def _send_health_alert(self, result: HealthCheckResult, recovery_results: Dict = None):
        """헬스체크 이상 알림 전송"""
        try:
            # 우선순위 결정
            priority = self._determine_alert_priority(result, recovery_results or {})

            # critical이 아닌 경우 중복 방지 (30분)
            if priority not in ['critical', 'emergency']:
                if self.last_alert_sent:
                    minutes_since = (datetime.now() - self.last_alert_sent).total_seconds() / 60
                    if minutes_since < 30:
                        self.logger.info("최근 알림 전송 이력 있음 - 중복 알림 방지")
                        return

            # 알림 메시지 작성
            message = self._format_health_alert(result, recovery_results)

            # 텔레그램 전송
            if self.notifier.is_enabled():
                success = self.notifier.send_message(message, priority=priority)

                if success:
                    self.logger.info(f"헬스체크 알림 전송 완료 (우선순위: {priority})")
                    self.last_alert_sent = datetime.now()
                else:
                    self.logger.error("헬스체크 알림 전송 실패")

        except Exception as e:
            self.logger.error(f"헬스체크 알림 전송 오류: {e}")

    def _format_health_alert(self, result: HealthCheckResult, recovery_results: Dict = None) -> str:
        """헬스체크 알림 메시지 포맷"""
        message = f"""*자동 매매 시스템 이상 감지*

⏰ 시간: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`
🔴 상태: *비정상*

"""

        if result.issues:
            message += "❌ *발견된 문제*:\n"
            for i, issue in enumerate(result.issues, 1):
                message += f"{i}. {issue}\n"
            message += "\n"

        # 자동 복구 결과 추가
        if recovery_results:
            message += "🔧 *자동 복구 시도*:\n"
            message += f"• 시도: {recovery_results['attempted']}건\n"
            message += f"• 성공: {recovery_results['succeeded']}건\n"
            message += f"• 실패: {recovery_results['failed']}건\n\n"

            # 성공한 복구 액션
            successful_actions = [a for a in recovery_results['actions'] if a.success]
            if successful_actions:
                message += "✅ *복구 성공*:\n"
                for action in successful_actions[:3]:
                    message += f"• {action.description}\n"
                message += "\n"

            # 실패한 복구 액션
            failed_actions = [a for a in recovery_results['actions'] if not a.success]
            if failed_actions:
                message += "❌ *복구 실패*:\n"
                for action in failed_actions[:3]:
                    message += f"• {action.description}\n"
                message += "\n"

        if result.warnings:
            message += "⚠️ *경고사항*:\n"
            for i, warning in enumerate(result.warnings, 1):
                message += f"{i}. {warning}\n"
            message += "\n"

        if result.metrics:
            message += "📊 *시스템 메트릭*:\n"

            if 'engine_running' in result.metrics:
                status = "🟢 실행중" if result.metrics['engine_running'] else "🔴 중지됨"
                message += f"• 매매 엔진: {status}\n"

            if 'recent_trades' in result.metrics:
                message += f"• 오늘 거래: {result.metrics['recent_trades']}건\n"

            if 'available_cash' in result.metrics:
                cash = result.metrics['available_cash']
                message += f"• 가용 현금: {cash:,.0f}원\n"

            if 'selection_count' in result.metrics:
                message += f"• 일일 선정 종목: {result.metrics['selection_count']}개\n"

        return message


# 싱글톤 인스턴스
_health_checker = None

def get_health_checker() -> TradingHealthChecker:
    """헬스체커 싱글톤 인스턴스 반환"""
    global _health_checker
    if _health_checker is None:
        _health_checker = TradingHealthChecker()
    return _health_checker
