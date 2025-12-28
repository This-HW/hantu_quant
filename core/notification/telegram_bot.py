"""
텔레그램 알림 모듈

텔레그램 봇을 통한 실시간 알림을 발송합니다.
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

logger = logging.getLogger(__name__)


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
    """

    def __init__(self, config: Optional[TelegramConfig] = None):
        """
        Args:
            config: 텔레그램 설정
        """
        super().__init__(config)
        self.config: TelegramConfig = config or TelegramConfig()

        # 비동기 발송 큐
        self._send_queue: queue.Queue = queue.Queue()
        self._worker_thread: Optional[threading.Thread] = None
        self._running: bool = False

    def is_configured(self) -> bool:
        """설정 완료 여부"""
        return bool(self.config.bot_token and self.config.chat_id)

    def send(self, alert: Alert) -> NotificationResult:
        """
        알림 발송

        Args:
            alert: 알림 객체

        Returns:
            NotificationResult: 발송 결과
        """
        if not self.is_configured():
            return NotificationResult(
                success=False,
                alert_id=str(id(alert)),
                error="Telegram not configured",
            )

        if not self.should_send(alert):
            return NotificationResult(
                success=False,
                alert_id=str(id(alert)),
                error="Alert filtered out",
            )

        # 메시지 포맷
        message = AlertFormatter.format_telegram(alert)

        return self._send_message(message, str(id(alert)))

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
                        logger.debug(f"Telegram message sent: {alert_id}")

                        return NotificationResult(
                            success=True,
                            alert_id=alert_id,
                            retry_count=retry_count,
                            response=response_data,
                        )
                    else:
                        last_error = response_data.get('description', 'Unknown error')

            except urllib.error.HTTPError as e:
                last_error = f"HTTP error: {e.code}"
                logger.warning(f"Telegram HTTP error: {e.code}")

            except urllib.error.URLError as e:
                last_error = f"URL error: {e.reason}"
                logger.warning(f"Telegram URL error: {e.reason}")

            except Exception as e:
                last_error = str(e)
                logger.warning(f"Telegram error: {e}")

            retry_count += 1
            if retry_count <= self.config.max_retries:
                time.sleep(self.config.retry_delay * retry_count)

        # 모든 재시도 실패
        self._record_error()
        logger.error(f"Telegram send failed after {retry_count} retries: {last_error}")

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
