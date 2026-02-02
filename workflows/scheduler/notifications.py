"""
알림 서비스 모듈

텔레그램 알림을 안전하게 전송하고 관리합니다.
스레드 안전성과 예외 처리가 보장됩니다.
"""

import threading
from typing import Optional
from core.utils.telegram_notifier import get_telegram_notifier, TelegramNotifier
from core.utils.log_utils import get_logger

logger = get_logger(__name__)


class NotificationService:
    """알림 서비스 클래스

    텔레그램 알림을 안전하게 전송합니다.
    지연 초기화, 캐싱, 스레드 안전성을 보장합니다.

    Features:
        - 지연 초기화 (lazy initialization)
        - 싱글톤 패턴 활용 (get_telegram_notifier)
        - 스레드 안전성 (Lock 사용)
        - 예외 처리 및 로깅
        - 우선순위별 메시지 전송
    """

    def __init__(self):
        """초기화

        notifier는 첫 사용 시 지연 초기화됩니다.
        """
        self._notifier: Optional[TelegramNotifier] = None
        self._lock = threading.Lock()
        self._initialization_attempted = False

    def _get_notifier(self) -> Optional[TelegramNotifier]:
        """텔레그램 notifier 반환 (지연 초기화, 캐시)

        스레드 안전하게 notifier를 초기화하고 반환합니다.
        Double-checked locking 패턴을 사용하여 Lock 오버헤드를 최소화합니다.

        Note:
            Python GIL 덕분에 실질적으로 안전하며, 변수 할당은 atomic합니다.
            _notifier와 _initialization_attempted는 초기화 후 변경되지 않으므로
            memory barrier 이슈가 발생하지 않습니다.

        Returns:
            TelegramNotifier 인스턴스 또는 None (비활성화/오류 시)
        """
        # 1차 체크: Lock 없이 빠르게 캐시된 인스턴스 반환
        if self._notifier is None and not self._initialization_attempted:
            with self._lock:
                # 2차 체크: Lock 획득 후 다시 확인 (다른 스레드가 먼저 초기화했을 수 있음)
                if self._notifier is None and not self._initialization_attempted:
                    try:
                        self._notifier = get_telegram_notifier()
                        self._initialization_attempted = True
                        if self._notifier and self._notifier.is_enabled():
                            logger.info("텔레그램 notifier 초기화 완료")
                        else:
                            logger.warning("텔레그램 notifier가 비활성화 상태입니다")
                    except Exception as e:
                        logger.warning(f"텔레그램 notifier 초기화 실패: {e}", exc_info=True)
                        self._initialization_attempted = True
                        return None

        return self._notifier

    def send_message(self, message: str, priority: str = "normal") -> bool:
        """텔레그램 알림을 안전하게 전송 (예외 처리 포함)

        Args:
            message: 전송할 메시지
            priority: 우선순위
                - "normal": 일반 알림
                - "high": 중요 알림
                - "emergency": 긴급 알림

        Returns:
            전송 성공 여부
        """
        try:
            notifier = self._get_notifier()
            if notifier and notifier.is_enabled():
                success = notifier.send_message(message, priority)
                if success:
                    logger.debug(f"텔레그램 알림 전송 성공 (priority={priority})")
                else:
                    logger.warning(f"텔레그램 알림 전송 실패 (priority={priority})")
                return success
            else:
                logger.debug("텔레그램 notifier가 비활성화되어 알림을 건너뜁니다")
                return False
        except Exception as e:
            logger.error(f"텔레그램 알림 전송 중 예외 발생: {e}", exc_info=True)
            return False

    def is_enabled(self) -> bool:
        """텔레그램 알림이 활성화되어 있는지 확인

        Returns:
            활성화 여부
        """
        try:
            notifier = self._get_notifier()
            return notifier is not None and notifier.is_enabled()
        except Exception as e:
            logger.warning(f"텔레그램 활성화 상태 확인 실패: {e}", exc_info=True)
            return False

    def send_phase1_complete(self, watchlist_count: int) -> bool:
        """Phase 1 완료 알림 전송

        Args:
            watchlist_count: 감시 리스트에 추가된 종목 수

        Returns:
            전송 성공 여부
        """
        message = f"✅ Phase 1 스크리닝 완료\n감시 리스트: {watchlist_count}개 종목"
        return self.send_message(message, priority="normal")

    def send_phase2_batch_complete(self, batch_id: int, selected_count: int) -> bool:
        """Phase 2 배치 완료 알림 전송

        Args:
            batch_id: 배치 번호 (0부터 시작)
            selected_count: 선정된 종목 수

        Returns:
            전송 성공 여부
        """
        message = f"✅ Phase 2 Batch {batch_id} 완료\n선정 종목: {selected_count}개"
        return self.send_message(message, priority="normal")

    def send_cache_init_complete(self, deleted_count: int) -> bool:
        """캐시 초기화 완료 알림 전송

        Args:
            deleted_count: 삭제된 캐시 키 개수

        Returns:
            전송 성공 여부
        """
        message = f"🔄 캐시 초기화 완료\n삭제된 키: {deleted_count}개"
        return self.send_message(message, priority="normal")

    def send_error(self, error_message: str, context: str = "") -> bool:
        """에러 알림 전송

        Args:
            error_message: 에러 메시지
            context: 에러 발생 컨텍스트 (선택)

        Returns:
            전송 성공 여부
        """
        if context:
            message = f"❌ 에러 발생\n위치: {context}\n내용: {error_message}"
        else:
            message = f"❌ 에러 발생\n{error_message}"

        return self.send_message(message, priority="high")

    def send_ai_data_complete(self, total_screened: int, total_selected: int) -> bool:
        """AI 학습 데이터 연동 완료 알림 전송

        Args:
            total_screened: Phase 1 스크리닝 종목 수
            total_selected: Phase 2 선정 종목 수

        Returns:
            전송 성공 여부
        """
        message = (
            f"🤖 AI 학습 데이터 연동 완료\n"
            f"스크리닝: {total_screened}개\n"
            f"선정: {total_selected}개"
        )
        return self.send_message(message, priority="normal")

    def send_daily_performance_report(self) -> bool:
        """일일 성과 리포트 전송

        TelegramNotifier의 send_daily_performance_report를 래핑합니다.

        Returns:
            전송 성공 여부
        """
        try:
            notifier = self._get_notifier()
            if notifier and notifier.is_enabled():
                success = notifier.send_daily_performance_report()
                if success:
                    logger.info("일일 성과 리포트 전송 완료")
                else:
                    logger.warning("일일 성과 리포트 전송 실패")
                return success
            else:
                logger.info("텔레그램 알림이 비활성화되어 있음")
                return False
        except Exception as e:
            logger.error(f"일일 성과 리포트 전송 중 예외 발생: {e}", exc_info=True)
            return False


# === 싱글톤 인스턴스 ===
_notification_service: Optional[NotificationService] = None
_service_lock = threading.Lock()


def get_notification_service() -> NotificationService:
    """NotificationService 싱글톤 인스턴스 반환

    스레드 안전하게 싱글톤을 보장합니다.

    Returns:
        NotificationService 인스턴스
    """
    global _notification_service

    if _notification_service is None:
        with _service_lock:
            # Double-checked locking
            if _notification_service is None:
                _notification_service = NotificationService()

    return _notification_service
