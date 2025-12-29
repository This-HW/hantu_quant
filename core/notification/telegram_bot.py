"""
텔레그램 알림 모듈

텔레그램 봇을 통한 실시간 알림을 발송합니다.

Feature 1: 알림 시스템 통합
Story 1.2: TelegramNotifier 통합
"""

import logging
import time
from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass
import threading
import queue

from .alert import Alert, AlertFormatter
from .notifier import BaseNotifier, NotifierConfig, NotificationResult
from .config_loader import (
    TelegramConfigData,
    TelegramConfigLoader,
    get_telegram_config,
)
from core.utils.log_utils import (
    trace_operation,
    get_trace_id,
    get_context_logger,
)
from core.error_handler import (
    handle_error,
    ErrorAction,
    error_handler,
)
from core.exceptions import (
    NotificationException,
    NotificationSendError,
    NotificationConfigError,
    ErrorSeverity,
)

logger = get_context_logger(__name__)


@dataclass
class TelegramConfig(NotifierConfig):
    """텔레그램 설정"""
    # 봇 토큰 (BotFather에서 발급)
    bot_token: str = ""

    # 채팅 ID (사용자 또는 그룹)
    chat_id: str = ""

    # API 설정
    api_base_url: str = "https://api.telegram.org"
    timeout: int = 10

    # 메시지 설정
    parse_mode: str = "HTML"  # HTML or Markdown
    disable_notification: bool = False
    disable_web_preview: bool = True


class TelegramNotifier(BaseNotifier):
    """
    텔레그램 알림 발송기

    텔레그램 봇 API를 통해 메시지를 발송합니다.

    Story 1.2: TelegramNotifier 통합
    - T-1.2.4: config_loader 사용
    - T-1.2.5: 분산 추적 적용
    - T-1.2.6: 에러 핸들링 강화
    """

    def __init__(
        self,
        config: Optional[TelegramConfig] = None,
        config_data: Optional[TelegramConfigData] = None,
        config_path: Optional[str] = None,
    ):
        """
        Args:
            config: 텔레그램 설정 (기존 방식)
            config_data: TelegramConfigData 객체 (신규 방식)
            config_path: 설정 파일 경로 (config_loader 사용)
        """
        super().__init__(config)

        # config_loader를 통한 설정 로드 지원
        if config_data:
            self._config_data = config_data
            self.config = self._convert_to_telegram_config(config_data)
        elif config_path:
            loader = TelegramConfigLoader(config_path)
            self._config_data = loader.load()
            self.config = self._convert_to_telegram_config(self._config_data)
        elif config:
            self.config = config
            self._config_data = None
        else:
            # 기본 config_loader 사용
            try:
                self._config_data = get_telegram_config()
                self.config = self._convert_to_telegram_config(self._config_data)
            except Exception:
                self.config = TelegramConfig()
                self._config_data = None

        # 비동기 발송 큐
        self._send_queue: queue.Queue = queue.Queue()
        self._worker_thread: Optional[threading.Thread] = None
        self._running: bool = False

        # 발송 통계
        self._send_count: int = 0
        self._error_count: int = 0
        self._last_send_time: Optional[datetime] = None

    def _convert_to_telegram_config(
        self,
        config_data: TelegramConfigData
    ) -> TelegramConfig:
        """TelegramConfigData를 TelegramConfig로 변환"""
        return TelegramConfig(
            bot_token=config_data.bot_token,
            chat_id=config_data.get_primary_chat_id() or "",
            api_base_url=config_data.api_base_url,
            timeout=config_data.timeout,
            max_retries=config_data.max_retries,
            retry_delay=config_data.retry_delay,
            parse_mode="HTML" if config_data.message_format.use_html else "Markdown",
        )

    def is_configured(self) -> bool:
        """설정 완료 여부"""
        return bool(self.config.bot_token and self.config.chat_id)

    @trace_operation("telegram_send_alert", include_result=False)
    def send(self, alert: Alert) -> NotificationResult:
        """
        알림 발송

        Args:
            alert: 알림 객체

        Returns:
            NotificationResult: 발송 결과
        """
        trace_id = get_trace_id()

        if not self.is_configured():
            logger.warning(
                "Telegram not configured",
                extra={"trace_id": trace_id, "alert_id": alert.id}
            )
            return NotificationResult(
                success=False,
                alert_id=alert.id,
                error="Telegram not configured",
            )

        if not self.should_send(alert):
            logger.debug(
                "Alert filtered out",
                extra={"trace_id": trace_id, "alert_id": alert.id}
            )
            return NotificationResult(
                success=False,
                alert_id=alert.id,
                error="Alert filtered out",
            )

        try:
            # 메시지 포맷
            message = AlertFormatter.format_telegram(alert)
            result = self._send_message(message, alert.id)

            if result.success:
                self._send_count += 1
                self._last_send_time = datetime.now()
                logger.info(
                    f"Alert sent successfully: {alert.id}",
                    extra={"trace_id": trace_id, "alert_id": alert.id}
                )
            else:
                self._error_count += 1
                logger.warning(
                    f"Alert send failed: {alert.id} - {result.error}",
                    extra={"trace_id": trace_id, "alert_id": alert.id}
                )

            return result

        except Exception as e:
            self._error_count += 1
            error = NotificationSendError(
                f"Failed to send telegram alert: {e}",
                original_error=e,
                context={"alert_id": alert.id, "trace_id": trace_id},
            )
            handle_error(error, "Telegram send error", action=ErrorAction.LOG_AND_ALERT)

            return NotificationResult(
                success=False,
                alert_id=alert.id,
                error=str(e),
            )

    def send_raw(self, message: str) -> NotificationResult:
        """
        원시 메시지 발송

        Args:
            message: 메시지 문자열

        Returns:
            NotificationResult: 발송 결과
        """
        if not self.is_configured():
            return NotificationResult(
                success=False,
                alert_id="raw",
                error="Telegram not configured",
            )

        return self._send_message(message, "raw")

    @trace_operation("telegram_send_message", include_result=False)
    def _send_message(
        self,
        message: str,
        alert_id: str
    ) -> NotificationResult:
        """
        메시지 발송 (내부)

        Args:
            message: 메시지
            alert_id: 알림 ID

        Returns:
            NotificationResult: 발송 결과
        """
        import urllib.request
        import urllib.parse
        import urllib.error
        import json

        trace_id = get_trace_id()
        url = f"{self.config.api_base_url}/bot{self.config.bot_token}/sendMessage"

        data = {
            'chat_id': self.config.chat_id,
            'text': message,
            'parse_mode': self.config.parse_mode,
            'disable_notification': self.config.disable_notification,
            'disable_web_page_preview': self.config.disable_web_preview,
        }

        retry_count = 0
        last_error = ""

        while retry_count <= self.config.max_retries:
            try:
                # URL 인코딩
                encoded_data = urllib.parse.urlencode(data).encode('utf-8')

                # 요청 생성
                request = urllib.request.Request(url, data=encoded_data)
                request.add_header('Content-Type', 'application/x-www-form-urlencoded')

                # 요청 실행
                with urllib.request.urlopen(request, timeout=self.config.timeout) as response:
                    response_data = json.loads(response.read().decode('utf-8'))

                    if response_data.get('ok'):
                        self._record_success()
                        logger.debug(
                            f"Telegram message sent: {alert_id}",
                            extra={"trace_id": trace_id, "alert_id": alert_id}
                        )

                        return NotificationResult(
                            success=True,
                            alert_id=alert_id,
                            retry_count=retry_count,
                            response=response_data,
                        )
                    else:
                        last_error = response_data.get('description', 'Unknown error')
                        logger.warning(
                            f"Telegram API error: {last_error}",
                            extra={"trace_id": trace_id, "alert_id": alert_id}
                        )

            except urllib.error.HTTPError as e:
                last_error = f"HTTP error: {e.code}"
                logger.warning(
                    f"Telegram HTTP error: {e.code}",
                    extra={"trace_id": trace_id, "alert_id": alert_id, "retry": retry_count}
                )

            except urllib.error.URLError as e:
                last_error = f"URL error: {e.reason}"
                logger.warning(
                    f"Telegram URL error: {e.reason}",
                    extra={"trace_id": trace_id, "alert_id": alert_id, "retry": retry_count}
                )

            except Exception as e:
                last_error = str(e)
                logger.warning(
                    f"Telegram error: {e}",
                    extra={"trace_id": trace_id, "alert_id": alert_id, "retry": retry_count}
                )

            retry_count += 1
            if retry_count <= self.config.max_retries:
                time.sleep(self.config.retry_delay * retry_count)

        # 모든 재시도 실패
        self._record_error()

        error = NotificationSendError(
            f"Telegram send failed after {retry_count} retries: {last_error}",
            context={
                "alert_id": alert_id,
                "retry_count": retry_count,
                "trace_id": trace_id,
            },
            severity=ErrorSeverity.WARNING,
        )
        handle_error(error, "Telegram send failed", action=ErrorAction.LOG_ONLY)

        return NotificationResult(
            success=False,
            alert_id=alert_id,
            error=last_error,
            retry_count=retry_count,
        )

    def send_async(self, alert: Alert) -> None:
        """
        비동기 알림 발송

        Args:
            alert: 알림 객체
        """
        if not self._running:
            self._start_worker()

        self._send_queue.put(alert)

    def _start_worker(self) -> None:
        """워커 스레드 시작"""
        if self._running:
            return

        self._running = True
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            daemon=True
        )
        self._worker_thread.start()
        logger.info("Telegram worker thread started")

    def _stop_worker(self) -> None:
        """워커 스레드 중지"""
        self._running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=5)

    def _worker_loop(self) -> None:
        """워커 루프"""
        while self._running:
            try:
                alert = self._send_queue.get(timeout=1)
                self.send(alert)
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Telegram worker error: {e}")

    def send_photo(
        self,
        photo_path: str,
        caption: str = ""
    ) -> NotificationResult:
        """
        사진 발송

        Args:
            photo_path: 사진 파일 경로
            caption: 캡션

        Returns:
            NotificationResult: 발송 결과
        """
        if not self.is_configured():
            return NotificationResult(
                success=False,
                alert_id="photo",
                error="Telegram not configured",
            )

        import urllib.request
        import json

        url = f"{self.config.api_base_url}/bot{self.config.bot_token}/sendPhoto"

        try:
            # 멀티파트 폼 데이터 생성
            boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'

            with open(photo_path, 'rb') as f:
                photo_data = f.read()

            body = []
            body.append(f'--{boundary}'.encode())
            body.append(f'Content-Disposition: form-data; name="chat_id"'.encode())
            body.append(b'')
            body.append(self.config.chat_id.encode())

            body.append(f'--{boundary}'.encode())
            body.append(f'Content-Disposition: form-data; name="photo"; filename="chart.png"'.encode())
            body.append(b'Content-Type: image/png')
            body.append(b'')
            body.append(photo_data)

            if caption:
                body.append(f'--{boundary}'.encode())
                body.append(f'Content-Disposition: form-data; name="caption"'.encode())
                body.append(b'')
                body.append(caption.encode())
                body.append(f'--{boundary}'.encode())
                body.append(f'Content-Disposition: form-data; name="parse_mode"'.encode())
                body.append(b'')
                body.append(self.config.parse_mode.encode())

            body.append(f'--{boundary}--'.encode())

            body_bytes = b'\r\n'.join(body)

            request = urllib.request.Request(url, data=body_bytes)
            request.add_header(
                'Content-Type',
                f'multipart/form-data; boundary={boundary}'
            )

            with urllib.request.urlopen(request, timeout=self.config.timeout * 2) as response:
                response_data = json.loads(response.read().decode('utf-8'))

                if response_data.get('ok'):
                    self._record_success()
                    return NotificationResult(
                        success=True,
                        alert_id="photo",
                        response=response_data,
                    )

        except Exception as e:
            self._record_error()
            logger.error(f"Telegram photo send failed: {e}")
            return NotificationResult(
                success=False,
                alert_id="photo",
                error=str(e),
            )

        return NotificationResult(
            success=False,
            alert_id="photo",
            error="Unknown error",
        )

    def test_connection(self) -> Dict[str, Any]:
        """
        연결 테스트

        Returns:
            Dict: 테스트 결과
        """
        if not self.is_configured():
            return {
                'success': False,
                'error': 'Not configured',
            }

        import urllib.request
        import json

        url = f"{self.config.api_base_url}/bot{self.config.bot_token}/getMe"

        try:
            with urllib.request.urlopen(url, timeout=self.config.timeout) as response:
                data = json.loads(response.read().decode('utf-8'))

                if data.get('ok'):
                    bot_info = data.get('result', {})
                    return {
                        'success': True,
                        'bot_name': bot_info.get('first_name'),
                        'bot_username': bot_info.get('username'),
                    }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
            }

        return {
            'success': False,
            'error': 'Unknown error',
        }

    def get_updates(self, offset: int = 0) -> list:
        """
        업데이트 조회 (채팅 ID 확인용)

        Args:
            offset: 오프셋

        Returns:
            list: 업데이트 리스트
        """
        if not self.config.bot_token:
            return []

        import urllib.request
        import json

        url = f"{self.config.api_base_url}/bot{self.config.bot_token}/getUpdates"
        if offset:
            url += f"?offset={offset}"

        try:
            with urllib.request.urlopen(url, timeout=self.config.timeout) as response:
                data = json.loads(response.read().decode('utf-8'))

                if data.get('ok'):
                    return data.get('result', [])

        except Exception as e:
            logger.error(f"Get updates failed: {e}")

        return []

    def get_stats(self) -> Dict[str, Any]:
        """
        발송 통계 조회

        Returns:
            Dict: 통계 정보
        """
        return {
            "send_count": self._send_count,
            "error_count": self._error_count,
            "success_rate": (
                self._send_count / (self._send_count + self._error_count)
                if (self._send_count + self._error_count) > 0
                else 0.0
            ),
            "last_send_time": (
                self._last_send_time.isoformat()
                if self._last_send_time
                else None
            ),
            "is_configured": self.is_configured(),
            "queue_size": self._send_queue.qsize(),
            "worker_running": self._running,
        }

    def get_config_info(self) -> Dict[str, Any]:
        """
        설정 정보 조회 (민감 정보 마스킹)

        Returns:
            Dict: 설정 정보
        """
        return {
            "api_base_url": self.config.api_base_url,
            "chat_id": self.config.chat_id[:4] + "***" if self.config.chat_id else "",
            "bot_token_set": bool(self.config.bot_token),
            "timeout": self.config.timeout,
            "max_retries": self.config.max_retries,
            "parse_mode": self.config.parse_mode,
            "is_configured": self.is_configured(),
        }


# 글로벌 인스턴스 (싱글톤 패턴)
_telegram_notifier_instance: Optional[TelegramNotifier] = None


def get_telegram_notifier(
    config_path: Optional[str] = None,
    force_reload: bool = False,
) -> TelegramNotifier:
    """
    TelegramNotifier 싱글톤 인스턴스 반환

    Args:
        config_path: 설정 파일 경로
        force_reload: 강제 재로드 여부

    Returns:
        TelegramNotifier: 인스턴스
    """
    global _telegram_notifier_instance

    if _telegram_notifier_instance is None or force_reload:
        _telegram_notifier_instance = TelegramNotifier(config_path=config_path)

    return _telegram_notifier_instance


def send_telegram_alert(
    alert: Alert,
    config_path: Optional[str] = None,
) -> NotificationResult:
    """
    텔레그램 알림 발송 헬퍼 함수

    Args:
        alert: 알림 객체
        config_path: 설정 파일 경로

    Returns:
        NotificationResult: 발송 결과
    """
    notifier = get_telegram_notifier(config_path)
    return notifier.send(alert)


def send_telegram_message(
    message: str,
    config_path: Optional[str] = None,
) -> NotificationResult:
    """
    텔레그램 메시지 발송 헬퍼 함수

    Args:
        message: 메시지 내용
        config_path: 설정 파일 경로

    Returns:
        NotificationResult: 발송 결과
    """
    notifier = get_telegram_notifier(config_path)
    return notifier.send_raw(message)
