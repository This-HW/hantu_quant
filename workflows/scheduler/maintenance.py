"""
유지보수 작업 모듈

자정 캐시 초기화, 자동 유지보수 등의 정기 유지보수 작업을 관리합니다.

Features:
    - 자정 캐시 초기화 (00:00)
    - 자동 유지보수 체크 및 실행
    - 텔레그램 알림
"""

from datetime import datetime
from typing import Dict, Any

from core.utils.log_utils import get_logger
from .config import SchedulerConfig
from .notifications import NotificationService

logger = get_logger(__name__)


class MaintenanceService:
    """유지보수 서비스 클래스

    자정 캐시 초기화, 자동 유지보수 등을 수행합니다.
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

    def clear_cache(self) -> bool:
        """자정 캐시 초기화 (00:00 실행)

        목적:
        - 전날 캐시 데이터 삭제
        - Redis 연결 상태 확인
        - 당일 시작 준비

        처리:
        1. Redis 연결 확인
        2. hantu:* 패턴 키 삭제
        3. 텔레그램 알림 (삭제된 키 개수)
        4. 에러 시 경고 로그 (서비스 지속)

        Returns:
            성공 여부
        """
        try:
            logger.info("=" * 50)
            logger.info("[캐시] 캐시 초기화 시작")

            from core.api.redis_client import cache

            # Redis 클라이언트 확인
            if not cache.is_available():
                logger.warning("Redis를 사용할 수 없음 - 캐시 초기화 스킵 (MemoryCache 사용 중)")
                return False

            # Redis SCAN으로 hantu:* 패턴 키 찾기 (KEYS * 대신 SCAN 사용)
            deleted_count = cache.delete_by_pattern("hantu:*")

            logger.info(f"캐시 초기화 완료: {deleted_count}개 키 삭제")

            # 텔레그램 알림
            message = (
                f"🔄 *자정 캐시 초기화 완료*\n\n"
                f"삭제된 키: `{deleted_count}`개\n"
                f"시간: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n\n"
                f"_새로운 하루가 시작되었습니다!_"
            )
            self.notification_service.send_message(message, "normal")

            print(f"[캐시] 캐시 초기화 완료: {deleted_count}개 키 삭제")
            logger.info("=" * 50)

            return True

        except Exception as e:
            logger.error(f"캐시 초기화 실패: {e}", exc_info=True)

            # 에러 알림
            self.notification_service.send_error(
                error_message=str(e),
                context="캐시 초기화"
            )

            return False

    def run_auto_maintenance(self) -> Dict[str, Any]:
        """자동 유지보수 실행

        학습 시스템의 유지보수 필요성을 체크하고, 필요시 자동으로 실행합니다.

        Returns:
            유지보수 결과
                - needs_maintenance: 유지보수 필요 여부
                - maintenance_executed: 유지보수 실행 여부
                - reasons: 유지보수 필요 사유
                - maintenance_result: 유지보수 실행 결과
        """
        try:
            logger.info("=== 자동 유지보수 시작 ===")
            print(f"[초기화] 자동 유지보수 시작 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

            # 지연 import (순환 참조 방지)
            from core.monitoring.system_monitor import get_system_monitor

            monitor = get_system_monitor()
            maintenance_result = monitor.run_maintenance_check()

            needs_maintenance = maintenance_result.get("needs_maintenance", False)
            maintenance_executed = maintenance_result.get("maintenance_executed", False)
            reasons = maintenance_result.get("reasons", [])

            logger.info(
                f"유지보수 체크 완료: 필요={'예' if needs_maintenance else '아니오'}, "
                f"실행={'예' if maintenance_executed else '아니오'}"
            )
            print("자동 유지보수 체크 완료!")
            print(f"   - 유지보수 필요: {'예' if needs_maintenance else '아니오'}")
            print(f"   - 유지보수 실행: {'예' if maintenance_executed else '아니오'}")

            if needs_maintenance:
                print(f"   - 필요 사유: {', '.join(reasons[:3])}")

                # 유지보수 실행 알림
                if maintenance_executed:
                    self._send_maintenance_notification(maintenance_result)
                else:
                    # 유지보수 필요하지만 실행 안 된 경우
                    self._send_maintenance_needed_notification(reasons)

            return maintenance_result

        except ImportError as ie:
            logger.warning(f"시스템 모니터링 모듈 로드 실패: {ie}", exc_info=True)
            print("시스템 모니터링 모듈을 찾을 수 없습니다")
            return {"error": "module_not_found"}

        except Exception as e:
            logger.error(f"자동 유지보수 실행 오류: {e}", exc_info=True)
            print(f"자동 유지보수 실행 오류: {e}")

            # 에러 알림
            self.notification_service.send_error(
                error_message=str(e),
                context="자동 유지보수"
            )

            return {"error": str(e)}

    def _send_maintenance_notification(self, maintenance_result: Dict[str, Any]) -> None:
        """유지보수 실행 알림 전송

        Args:
            maintenance_result: 유지보수 결과
        """
        try:
            reasons = maintenance_result.get("reasons", [])
            maintenance_details = maintenance_result.get("maintenance_result", {})
            tasks_completed = maintenance_details.get("tasks_completed", [])

            message = (
                f"[초기화] *자동 유지보수 실행*\n\n"
                f"**유지보수 완료**:\n"
                f"• 필요 사유: {len(reasons)}건\n"
                f"• 실행 작업: {len(tasks_completed)}개\n\n"
                f"[상세] **주요 사유**:"
            )

            for reason in reasons[:3]:
                message += f"\n• {reason}"

            message += "\n\n[작업] **실행된 작업**:"

            for task in tasks_completed:
                task_name = task.replace("_", " ").title()
                message += f"\n• {task_name}"

            message += (
                f"\n\n실행 시간: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n\n"
                f"*시스템이 자동으로 최적화되었습니다!*"
            )

            self.notification_service.send_message(message, "normal")

        except Exception as e:
            logger.error(f"유지보수 알림 전송 실패: {e}", exc_info=True)

    def _send_maintenance_needed_notification(self, reasons: list) -> None:
        """유지보수 필요 알림 전송

        Args:
            reasons: 유지보수 필요 사유
        """
        try:
            message = (
                f"⚠️ *유지보수 필요*\n\n"
                f"**점검 결과**:\n"
                f"시스템 유지보수가 필요합니다\n\n"
                f"**사유**:"
            )

            for reason in reasons[:5]:
                message += f"\n• {reason}"

            message += (
                f"\n\n시간: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n\n"
                f"💡 *관리자 확인이 필요합니다*"
            )

            self.notification_service.send_message(message, "high")

        except Exception as e:
            logger.error(f"유지보수 필요 알림 전송 실패: {e}", exc_info=True)
