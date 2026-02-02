"""
모니터링 및 헬스체크 모듈

시스템 모니터링 시작, 자동 매매 헬스체크, 학습 시스템 모니터링을 관리합니다.

Features:
    - 시스템 모니터링 시작 (백그라운드)
    - 자동 매매 헬스체크
    - 학습 시스템 상태 모니터링
    - 텔레그램 알림
"""

from datetime import datetime
from typing import Dict, Any

from core.utils.log_utils import get_logger
from .config import SchedulerConfig
from .notifications import NotificationService

logger = get_logger(__name__)


class MonitoringService:
    """모니터링 서비스 클래스

    시스템 모니터링, 헬스체크 등을 수행합니다.
    """

    def __init__(
        self,
        config: SchedulerConfig,
        notification_service: NotificationService
    ):
        """초기화

        Args:
            config: 스케줄러 설정
            notification_service: 알림 서비스
        """
        self.config = config
        self.notification_service = notification_service
        self._monitoring_started = False

    def start_monitoring(self) -> bool:
        """시스템 모니터링 시작

        백그라운드 스레드에서 시스템 상태를 지속적으로 모니터링합니다.
        - CPU, 메모리, 디스크 사용량
        - 학습 시스템 건강 상태
        - 데이터 신선도 및 무결성
        - 예측 정확도 추적

        Returns:
            시작 성공 여부
        """
        try:
            logger.info("=== 시스템 모니터링 시작 ===")
            print(f"[모니터] 시스템 모니터링 시작 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

            # 지연 import (순환 참조 방지)
            from core.monitoring.system_monitor import get_system_monitor

            monitor = get_system_monitor()
            success = monitor.start_monitoring()

            if success:
                logger.info("시스템 모니터링 시작 완료")
                print("시스템 모니터링이 백그라운드에서 시작되었습니다!")
                print("   - CPU, 메모리, 디스크 사용량 모니터링")
                print("   - 학습 시스템 건강 상태 추적")
                print("   - 자동 알림 및 보고서 생성")

                # 모니터링 시작 알림
                self._send_monitoring_start_notification()
                self._monitoring_started = True

                return True
            else:
                logger.warning("시스템 모니터링 시작 실패 (이미 실행 중일 수 있음)")
                print("시스템 모니터링 시작 실패 (이미 실행 중일 수 있음)")
                return False

        except ImportError as ie:
            logger.warning(f"시스템 모니터링 모듈 로드 실패: {ie}", exc_info=True)
            print("시스템 모니터링 모듈을 찾을 수 없습니다")
            return False

        except Exception as e:
            logger.error(f"시스템 모니터링 시작 오류: {e}", exc_info=True)
            print(f"시스템 모니터링 시작 오류: {e}")

            # 에러 알림
            self.notification_service.send_error(
                error_message=str(e),
                context="시스템 모니터링 시작"
            )

            return False

    def health_check(self) -> Dict[str, Any]:
        """자동 매매 헬스체크 실행

        자동 매매 시스템의 건강 상태를 체크합니다.
        - 주문 실행 가능 여부
        - API 연결 상태
        - 잔고 정보 조회 가능 여부

        Returns:
            헬스체크 결과
                - is_healthy: 전체 건강 상태
                - issues: 발견된 문제 목록
                - details: 상세 정보
        """
        try:
            logger.info("=== 자동 매매 헬스체크 시작 ===")

            # 지연 import (순환 참조 방지)
            from core.monitoring.trading_health_checker import get_health_checker

            health_checker = get_health_checker()
            result = health_checker.check_trading_health()

            if result.is_healthy:
                logger.info("헬스체크 완료: 시스템 정상")
            else:
                logger.warning(f"헬스체크 완료: {len(result.issues)}개 문제 발견")

                # 문제 발견 시 알림
                self._send_health_issue_notification(result)

            return {
                "is_healthy": result.is_healthy,
                "issues": result.issues,
                "details": result.__dict__
            }

        except ImportError as ie:
            logger.warning(f"헬스체크 모듈 로드 실패: {ie}", exc_info=True)
            return {"error": "module_not_found"}

        except Exception as e:
            logger.error(f"헬스체크 실행 오류: {e}", exc_info=True)

            # 에러 알림
            self.notification_service.send_error(
                error_message=str(e),
                context="자동 매매 헬스체크"
            )

            return {"error": str(e)}

    def get_status(self) -> Dict[str, Any]:
        """모니터링 상태 조회

        현재 모니터링 시스템의 상태를 조회합니다.

        Returns:
            상태 정보
                - monitoring_active: 모니터링 활성화 여부
                - latest_metrics: 최신 시스템 메트릭
                - recent_alerts: 최근 알림
                - learning_health: 학습 시스템 건강 상태
        """
        try:
            # 지연 import (순환 참조 방지)
            from core.monitoring.system_monitor import get_system_monitor

            monitor = get_system_monitor()
            status = monitor.get_system_status()

            return status

        except ImportError as ie:
            logger.warning(f"시스템 모니터 모듈 로드 실패: {ie}", exc_info=True)
            return {"error": "module_not_found"}

        except Exception as e:
            logger.error(f"상태 조회 실패: {e}", exc_info=True)
            return {"error": str(e)}

    def check_ml_trigger(self) -> bool:
        """ML 학습 트리거 체크

        학습 시스템에서 새로운 학습이 필요한지 체크합니다.

        Returns:
            학습 필요 여부
        """
        try:
            # 지연 import (순환 참조 방지)
            from core.learning.enhanced_adaptive_system import get_enhanced_adaptive_system

            system = get_enhanced_adaptive_system()
            health = system.check_system_health()

            # 데이터 신선도 체크
            data_freshness = health.get("data_freshness", {})
            days_since_update = data_freshness.get("days_since_update", 0)

            # 2일 이상 학습하지 않았으면 학습 필요
            if days_since_update >= 2:
                logger.info(f"ML 학습 필요: {days_since_update}일 경과")
                return True

            # 성능 저하 체크
            perf_metrics = health.get("performance_metrics", {})
            win_rate = perf_metrics.get("win_rate", 0) / 100
            total_trades = perf_metrics.get("total_trades", 0)

            # 거래 수가 충분하고 승률이 낮으면 학습 필요
            if total_trades >= 30 and win_rate < 0.35:
                logger.info(f"ML 학습 필요: 승률 저하 ({win_rate:.1%})")
                return True

            logger.info("ML 학습 불필요: 시스템 정상")
            return False

        except ImportError as ie:
            logger.warning(f"학습 시스템 모듈 로드 실패: {ie}", exc_info=True)
            return False

        except Exception as e:
            logger.error(f"ML 트리거 체크 실패: {e}", exc_info=True)
            return False

    def _send_monitoring_start_notification(self) -> None:
        """모니터링 시작 알림 전송"""
        try:
            message = (
                f"[모니터] *시스템 모니터링 시작*\n\n"
                f"**모니터링 항목**:\n"
                f"• 시스템 리소스 (CPU, 메모리, 디스크)\n"
                f"• 학습 시스템 건강 상태\n"
                f"• 데이터 신선도 및 무결성\n"
                f"• 예측 정확도 추적\n\n"
                f"[설정] **설정**:\n"
                f"• 체크 주기: 5분마다\n"
                f"• 일일 보고서: 오후 6시\n"
                f"• 자동 알림: 임계값 초과 시\n\n"
                f"시작 시간: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n\n"
                f"[자동] *AI 시스템이 스스로를 지속적으로 모니터링합니다!*"
            )

            self.notification_service.send_message(message, "normal")

        except Exception as e:
            logger.error(f"모니터링 시작 알림 전송 실패: {e}", exc_info=True)

    def _send_health_issue_notification(self, result) -> None:
        """헬스체크 문제 알림 전송

        Args:
            result: 헬스체크 결과
        """
        try:
            issues = result.issues[:5]  # 최대 5개만 표시

            message = (
                f"⚠️ *자동 매매 헬스체크 경고*\n\n"
                f"**발견된 문제**: {len(result.issues)}건\n\n"
                f"**주요 문제**:"
            )

            for issue in issues:
                message += f"\n• {issue}"

            if len(result.issues) > 5:
                message += f"\n• ... 외 {len(result.issues) - 5}건"

            message += (
                f"\n\n시간: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n\n"
                f"💡 *시스템 점검이 필요할 수 있습니다*"
            )

            self.notification_service.send_message(message, "high")

        except Exception as e:
            logger.error(f"헬스체크 문제 알림 전송 실패: {e}", exc_info=True)

    @property
    def is_monitoring_active(self) -> bool:
        """모니터링 활성화 여부 반환

        Returns:
            모니터링 활성화 여부
        """
        return self._monitoring_started
