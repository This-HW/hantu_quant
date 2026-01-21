"""
텔레그램 알림 전송 모듈
한투 퀀트 시스템의 각종 알림을 텔레그램으로 전송
"""

import json
import os
import requests
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict

# 성과 지표 계산 모듈 import
try:
    from ..performance.performance_metrics import get_performance_metrics
except ImportError:
    get_performance_metrics = None

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """텔레그램 알림 전송 클래스"""

    def __init__(self, config_file: str = "config/telegram_config.json"):
        """초기화

        Args:
            config_file: 텔레그램 설정 파일 경로
        """
        self._config_file = Path(config_file)
        self._bot_token = ""
        self._chat_ids = []
        self._enabled = False

        self._load_config()

    def _load_config(self):
        """텔레그램 설정 로드 (환경변수 우선, JSON 폴백)"""
        # 1. 환경변수에서 먼저 시도
        env_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        env_chat_id = os.getenv("TELEGRAM_CHAT_ID", "")

        if env_token and env_chat_id:
            self._bot_token = env_token
            self._chat_ids = [env_chat_id]
            self._enabled = True
            logger.info("텔레그램 알림 시스템 활성화됨 (환경변수)")
            return

        # 2. JSON 설정 파일에서 시도
        try:
            if not self._config_file.exists():
                logger.warning(
                    f"텔레그램 설정 없음: 환경변수(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID) 또는 {self._config_file} 필요"
                )
                return

            with open(self._config_file, "r", encoding="utf-8") as f:
                config = json.load(f)

            telegram_config = config.get("telegram", {})
            self._bot_token = telegram_config.get("bot_token", "")
            self._chat_ids = telegram_config.get("default_chat_ids", [])

            if self._bot_token and self._chat_ids:
                self._enabled = True
                logger.info("텔레그램 알림 시스템 활성화됨 (JSON 설정)")
            else:
                logger.warning("텔레그램 설정이 불완전함 - 알림 비활성화")

        except Exception as e:
            logger.error(f"텔레그램 설정 로드 실패: {e}", exc_info=True)
            self._enabled = False

    def send_message(self, message: str, priority: str = "normal") -> bool:
        """텔레그램 메시지 전송

        Args:
            message: 전송할 메시지
            priority: 우선순위
                - critical: 🚨 시스템 중단, 즉시 대응 필요
                - emergency: 🔴 심각한 오류, 긴급 확인 필요
                - high: ⚠️ 중요 알림, 빠른 확인 필요
                - normal: 📢 일반 알림
                - low: ℹ️ 정보성 알림
                - info: 💡 참고 정보

        Returns:
            전송 성공 여부
        """
        if not self._enabled:
            logger.warning("텔레그램 알림이 비활성화됨")
            return False

        try:
            # 우선순위에 따른 메시지 포맷 추가
            formatted_message = self._format_message_by_priority(message, priority)

            url = f"https://api.telegram.org/bot{self._bot_token}/sendMessage"
            success_count = 0

            # 우선순위에 따른 알림 설정
            disable_notification = self._should_silent_notification(priority)

            for chat_id in self._chat_ids:
                payload = {
                    "chat_id": chat_id,
                    "text": formatted_message,
                    "parse_mode": "Markdown",
                    "disable_web_page_preview": False,
                    "disable_notification": disable_notification,
                }

                response = requests.post(url, json=payload, timeout=10)

                if response.status_code == 200:
                    success_count += 1
                    logger.debug(f"텔레그램 메시지 전송 성공: {chat_id}")
                else:
                    # 에러 응답 상세 정보 로깅
                    try:
                        error_detail = response.json()
                        error_description = error_detail.get(
                            "description", "Unknown error"
                        )
                        error_code = error_detail.get("error_code", "N/A")
                        logger.error(
                            f"텔레그램 메시지 전송 실패: {chat_id}, "
                            f"상태코드: {response.status_code}, "
                            f"에러코드: {error_code}, "
                            f"설명: {error_description}",
                            exc_info=True,
                        )
                    except Exception:
                        logger.error(
                            f"텔레그램 메시지 전송 실패: {chat_id}, "
                            f"상태코드: {response.status_code}, "
                            f"응답: {response.text[:200] if response.text else 'Empty'}",
                            exc_info=True,
                        )

            if success_count > 0:
                logger.info(
                    f"텔레그램 알림 전송 완료 ({priority}): {success_count}/{len(self._chat_ids)}"
                )
                return True
            else:
                logger.error("모든 채널에서 텔레그램 전송 실패")
                return False

        except Exception as e:
            logger.error(f"텔레그램 메시지 전송 오류: {e}", exc_info=True)
            return False

    def _format_message_by_priority(self, message: str, priority: str) -> str:
        """우선순위에 따라 메시지 포맷 추가 (간소화)"""
        # 중요도별 간단한 이모지만 추가
        priority_prefix = {
            "critical": "🚨 ",
            "emergency": "🔴 ",
            "high": "⚠️ ",
            "normal": "",
            "low": "",
            "info": "",
        }

        prefix = priority_prefix.get(priority, "")

        return f"{prefix}{message}"

    def _should_silent_notification(self, priority: str) -> bool:
        """우선순위에 따라 무음 알림 여부 결정"""
        # critical, emergency, high는 소리 울림 (False)
        # normal, low, info는 무음 (True)
        silent_priorities = ["normal", "low", "info"]
        return priority in silent_priorities

    def send_screening_complete(self, stats: Dict) -> bool:
        """스크리닝 완료 알림 전송"""
        try:
            total_stocks = stats.get("total_count", 0)
            avg_score = stats.get("avg_score", 0.0)
            sectors = stats.get("sectors", {})

            # 상위 섹터 3개
            top_sectors = sorted(sectors.items(), key=lambda x: x[1], reverse=True)[:3]

            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            message = f"""🌅 *한투 퀀트 아침 스크리닝 완료*

⏰ 완료 시간: `{current_time}`
📊 분석 종목: `2,875개`
✅ 선정 종목: `{total_stocks}개`
📈 평균 점수: `{avg_score:.1f}점`

🏆 *상위 섹터*:"""

            for i, (sector, count) in enumerate(top_sectors, 1):
                percentage = (count / total_stocks * 100) if total_stocks > 0 else 0
                message += f"\n{i}. {sector}: {count}개 ({percentage:.1f}%)"

            message += """

🎯 *오늘의 투자 포인트*:
• 고성장 섹터 집중 모니터링
• 기술적 반등 신호 종목 주목
• 거래량 급증 종목 추적

🚀 *이제 AI가 선별한 우량 종목으로 투자하세요!*

⚙️ 다음 업데이트: 일일 매매 리스트 (Phase 2 진행 중)"""

            return self.send_message(message, "high")

        except Exception as e:
            logger.error(f"스크리닝 알림 생성 실패: {e}", exc_info=True)

            # 기본 메시지로 폴백
            fallback_message = f"""🌅 *한투 퀀트 아침 스크리닝 완료*

⏰ 완료 시간: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`
✅ 스크리닝이 성공적으로 완료되었습니다!

🚀 *AI 종목 선별 시스템이 가동 중입니다!*"""

            return self.send_message(fallback_message, "high")

    def send_daily_update_complete(self, selected_count: int) -> bool:
        """일일 업데이트 완료 알림 전송 (실제 성과 반영)"""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 실제 성과 지표 가져오기
        accuracy = 0.0
        win_rate = 0.0
        if get_performance_metrics:
            try:
                metrics = get_performance_metrics()
                hist_perf = metrics.get_historical_performance(days=30)
                accuracy = hist_perf.get("accuracy", 0.0) * 100
                win_rate = hist_perf.get("win_rate", 0.0) * 100
            except Exception as e:
                logger.error(f"성과 지표 조회 실패: {e}", exc_info=True)
                accuracy = 0.0
                win_rate = 0.0

        # 정확도가 0이면 기본값 사용 (데이터 부족)
        if accuracy == 0:
            accuracy_text = "측정 중"
        else:
            accuracy_text = f"{accuracy:.1f}%"

        if win_rate == 0:
            win_rate_text = "측정 중"
        else:
            win_rate_text = f"{win_rate:.1f}%"

        message = f"""📈 *일일 매매 리스트 업데이트 완료*

⏰ 완료 시간: `{current_time}`
🎯 선정 종목: `{selected_count}개`

💡 *오늘의 AI 추천 종목이 준비되었습니다!*

📊 *실제 성과*:
• 평균 정확도: {accuracy_text}
• 승률: {win_rate_text}
• 17개 기술지표 종합 분석
• 리스크 관리 포함

🚀 *지금 투자 기회를 확인하세요!*"""

        return self.send_message(message, "normal")

    def send_error_alert(self, error_type: str, error_message: str) -> bool:
        """오류 알림 전송"""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        message = f"""*시스템 오류*
`{current_time}` | `{error_type}`

{error_message}"""

        return self.send_message(message, "emergency")

    def send_scheduler_started(self) -> bool:
        """스케줄러 시작 알림 전송 (DB 연결 상태 포함)"""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # DB 연결 상태 확인
        db_status = self._check_db_connection()

        message = f"""🚀 *한투 퀀트 스케줄러 시작*

⏰ 시작 시간: `{current_time}`
🟢 상태: `실행 중`

🗄️ *시스템 상태*:
{db_status}

📋 *예정된 작업* (평일):
• 06:00 - 일간 스크리닝 실행
• 09:00 - 자동 매매 시작
• 15:30 - 자동 매매 종료
• 16:00 - 시장 마감 후 정리
• 17:00 - 일일 성과 분석

📅 *주말 작업*:
• 토 10:00 - 재무 데이터 수집
• 토 20:00 - 적응형 학습
• 토 22:00 - 주간 깊이 학습
• 일 10:00 - ML 학습 조건 체크

🔔 *알림 설정*:
• 스크리닝 완료 알림 ✅
• 매매 리스트 업데이트 알림 ✅
• 시스템 오류 알림 ✅

🤖 *한투 퀀트가 24시간 시장을 모니터링합니다!*

💡 스케줄러 중지: `python workflows/integrated_scheduler.py stop`"""

        return self.send_message(message, "high")

    def _check_db_connection(self) -> str:
        """DB 연결 상태 확인"""
        status_lines = []

        # PostgreSQL 연결 확인
        try:
            from sqlalchemy import text
            from core.database.session import DatabaseSession
            from core.config import settings

            db = DatabaseSession()
            # 간단한 쿼리로 연결 테스트
            with db.get_session() as session:
                session.execute(text("SELECT 1"))

            db_type = settings.DB_TYPE.upper() if hasattr(settings, "DB_TYPE") else "DB"
            status_lines.append(f"• {db_type} 연결: ✅ 정상")
        except Exception as e:
            logger.warning(f"DB 연결 확인 실패: {e}")
            status_lines.append("• DB 연결: ⚠️ 실패 (JSON 폴백 사용)")

        # Watchlist 데이터 소스 확인
        try:
            from pathlib import Path

            datetime.now().strftime("%Y%m%d")

            # DB에서 watchlist 로드 시도
            try:
                from core.database.session import DatabaseSession
                from core.database.models import Watchlist

                db = DatabaseSession()
                with db.get_session() as session:
                    count = session.query(Watchlist).count()
                    if count > 0:
                        status_lines.append(f"• Watchlist: ✅ DB ({count}종목)")
                    else:
                        # DB에 데이터가 없으면 JSON 확인
                        json_file = Path("data/watchlist/watchlist.json")
                        if json_file.exists():
                            status_lines.append("• Watchlist: ⚠️ JSON 폴백 사용")
                        else:
                            status_lines.append("• Watchlist: ❌ 데이터 없음")
            except Exception:
                json_file = Path("data/watchlist/watchlist.json")
                if json_file.exists():
                    status_lines.append("• Watchlist: ⚠️ JSON 폴백 사용")
                else:
                    status_lines.append("• Watchlist: ❌ 데이터 없음")

        except Exception as e:
            logger.warning(f"Watchlist 상태 확인 실패: {e}")
            status_lines.append("• Watchlist: ❓ 확인 불가")

        return "\n".join(status_lines) if status_lines else "• 상태 확인 불가"

    def send_scheduler_stopped(self, reason: str = "정상 종료") -> bool:
        """스케줄러 종료 알림 전송"""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 종료 이유에 따른 이모지 및 우선순위 설정
        if "오류" in reason or "실패" in reason:
            status_emoji = "🚨"
            priority = "emergency"
        elif "사용자" in reason or "정상" in reason:
            status_emoji = "⏹️"
            priority = "normal"
        else:
            status_emoji = "⚠️"
            priority = "high"

        message = f"""{status_emoji} *한투 퀀트 스케줄러 종료*

⏰ 종료 시간: `{current_time}`
🔴 상태: `정지됨`
📝 종료 이유: `{reason}`

⚠️ *스케줄된 작업이 중지되었습니다*:
• 재무 데이터 수집 (05:30) ❌
• 일간 스크리닝 (06:00) ❌
• 자동 매매 (09:00~15:30) ❌
• 시장 마감 정리 (16:00) ❌
• 일일 성과 분석 (17:00) ❌

🔄 *스케줄러 재시작*:
`python workflows/integrated_scheduler.py start`

💡 *즉시 실행*:
`python workflows/integrated_scheduler.py run`"""

        return self.send_message(message, priority)

    def send_scheduler_heartbeat(self, uptime: str, next_tasks: list) -> bool:
        """스케줄러 생존 신호 알림 전송 (선택적)"""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 다음 작업 리스트 포맷팅
        task_list = ""
        for task in next_tasks[:3]:  # 최대 3개까지만
            task_list += (
                f"• {task.get('job', 'Unknown')}: {task.get('next_run', 'Unknown')}\n"
            )

        if not task_list:
            task_list = "• 예정된 작업 없음\n"

        message = f"""💓 *한투 퀀트 스케줄러 상태*

⏰ 확인 시간: `{current_time}`
🟢 상태: `정상 가동 중`
⏱️ 실행 시간: `{uptime}`

📅 *다음 예정 작업*:
{task_list.rstrip()}

🤖 *시스템이 정상적으로 작동하고 있습니다.*"""

        return self.send_message(message, "low")

    def send_daily_performance_report(self) -> bool:
        """일일 성과 리포트 전송 (실현/평가 손익 분리)"""
        current_time = datetime.now()
        date_str = current_time.strftime("%Y%m%d")

        # 성과 지표 가져오기
        if not get_performance_metrics:
            logger.warning("성과 지표 모듈을 사용할 수 없습니다")
            return False

        try:
            metrics = get_performance_metrics()
            daily_perf = metrics.get_daily_performance(date_str)

            # 실현 손익 포맷팅
            realized_pnl = daily_perf.get("realized_pnl", 0)
            realized_return = daily_perf.get("realized_return", 0) * 100

            # 평가 손익 포맷팅
            unrealized_pnl = daily_perf.get("unrealized_pnl", 0)
            unrealized_return = daily_perf.get("unrealized_return", 0) * 100

            # 총 손익
            total_pnl = daily_perf.get("total_pnl", 0)
            total_return = daily_perf.get("total_return", 0) * 100

            # 기타 지표
            win_rate = daily_perf.get("win_rate", 0) * 100
            trade_count = daily_perf.get("trade_count", 0)
            holding_count = daily_perf.get("holding_count", 0)

            # 이모지 선택
            if total_pnl > 0:
                status_emoji = "📈"
                status_text = "수익 발생"
            elif total_pnl < 0:
                status_emoji = "📉"
                status_text = "손실 발생"
            else:
                status_emoji = "➖"
                status_text = "변동 없음"

            message = f"""{status_emoji} *일일 성과 리포트*

📅 날짜: `{current_time.strftime('%Y-%m-%d')}`
⏰ 집계 시간: `{current_time.strftime('%H:%M:%S')}`

💰 *실현 손익 (매도)*:
• 실현 손익: `{realized_pnl:,.0f}원`
• 실현 수익률: `{realized_return:+.2f}%`
• 거래 횟수: `{trade_count}건`
• 승률: `{win_rate:.1f}%`

📊 *평가 손익 (보유)*:
• 평가 손익: `{unrealized_pnl:,.0f}원`
• 평가 수익률: `{unrealized_return:+.2f}%`
• 보유 종목: `{holding_count}개`

📈 *종합 성과*:
• 총 손익: `{total_pnl:,.0f}원`
• 총 수익률: `{total_return:+.2f}%`
• 상태: `{status_text}`

🎯 *AI 트레이딩 시스템이 24시간 운영 중입니다*"""

            # 우선순위 설정 (손익에 따라)
            if total_pnl > 100000:  # 10만원 이상 수익
                priority = "high"
            elif total_pnl < -100000:  # 10만원 이상 손실
                priority = "emergency"
            else:
                priority = "normal"

            return self.send_message(message, priority)

        except Exception as e:
            logger.error(f"일일 성과 리포트 생성 실패: {e}", exc_info=True)

            # 폴백 메시지
            fallback_message = f"""📊 *일일 성과 리포트*

📅 날짜: `{current_time.strftime('%Y-%m-%d %H:%M:%S')}`

⚠️ 성과 데이터를 불러올 수 없습니다.
시스템 로그를 확인해주세요."""

            return self.send_message(fallback_message, "normal")

    def send_deployment_failure_alert(
        self, consecutive_count: int, context: dict
    ) -> bool:
        """배포 연속 실패 알림 (Critical)

        Args:
            consecutive_count: 연속 실패 횟수
            context: 배포 컨텍스트 정보 (commit, branch, last_success 등)

        Returns:
            전송 성공 여부
        """
        try:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            commit = context.get("commit", "Unknown")[:8]
            branch = context.get("branch", "Unknown")
            last_success = context.get("last_success", "Never")
            reason = context.get("reason", "Unknown error")

            # 연속 실패 횟수에 따른 긴급도 강조
            if consecutive_count >= 5:
                urgency_text = "⚠️⚠️⚠️ 긴급 조치 필요 ⚠️⚠️⚠️"
            elif consecutive_count >= 3:
                urgency_text = "⚠️ 조속한 확인 필요"
            else:
                urgency_text = "확인이 필요합니다"

            message = f"""🚨 *배포 연속 실패 알림*

⏰ 시간: `{current_time}`
🔴 상태: `배포 실패`
📊 연속 실패: `{consecutive_count}회`

{urgency_text}

📝 *배포 정보*:
• 브랜치: `{branch}`
• 커밋: `{commit}`
• 마지막 성공: `{last_success}`
• 실패 이유: `{reason}`

🔧 *조치 사항*:
1. 서버 로그 확인
2. 배포 스크립트 점검
3. 환경 변수 검증
4. 의존성 확인

💡 *수동 배포*:
```bash
cd /opt/hantu_quant
git pull origin {branch}
./scripts/deployment/deploy.sh
```

📞 *긴급 문의*: 시스템 관리자에게 연락하세요"""

            return self.send_message(message, "critical")

        except Exception as e:
            logger.error(f"배포 실패 알림 생성 실패: {e}", exc_info=True)
            return False

    def send_memory_overflow_alert(
        self, current_mb: int, threshold_mb: int, retry_count: int
    ) -> bool:
        """메모리 부족 알림 (Warning/Critical)

        Args:
            current_mb: 현재 메모리 사용량 (MB)
            threshold_mb: 임계값 (MB)
            retry_count: 재시도 횟수

        Returns:
            전송 성공 여부
        """
        try:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            usage_percent = (
                (current_mb / threshold_mb * 100) if threshold_mb > 0 else 100
            )

            # 재시도 횟수에 따른 우선순위 결정
            if retry_count >= 3:
                priority = "critical"
                status_emoji = "🚨"
                urgency_text = "⚠️ 즉시 조치 필요 ⚠️"
            elif retry_count >= 1:
                priority = "high"
                status_emoji = "⚠️"
                urgency_text = "조속한 확인 필요"
            else:
                priority = "high"
                status_emoji = "⚠️"
                urgency_text = "메모리 부족 감지"

            message = f"""{status_emoji} *메모리 부족 알림*

⏰ 시간: `{current_time}`
📊 메모리 사용: `{current_mb} MB / {threshold_mb} MB ({usage_percent:.1f}%)`
🔄 재시도: `{retry_count}회`

{urgency_text}

🔍 *원인 분석*:
• 대량 데이터 처리 중일 수 있음
• 메모리 누수 가능성
• 시스템 리소스 부족

🔧 *권장 조치*:
1. 실행 중인 프로세스 확인
2. 불필요한 프로세스 종료
3. 시스템 재시작 고려
4. 메모리 임계값 조정

💡 *시스템 확인*:
```bash
free -m
ps aux --sort=-%mem | head -10
systemctl status hantu-*
```

📞 *긴급 대응이 필요한 경우 시스템 관리자에게 연락하세요*"""

            return self.send_message(message, priority)

        except Exception as e:
            logger.error(f"메모리 부족 알림 생성 실패: {e}", exc_info=True)
            return False

    def send_env_validation_failure_alert(self, missing_vars: list) -> bool:
        """환경변수 검증 실패 알림 (Critical)

        Args:
            missing_vars: 누락된 환경변수 목록

        Returns:
            전송 성공 여부
        """
        try:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # 누락된 변수 리스트 포맷팅
            missing_list = "\n".join([f"• `{var}`" for var in missing_vars])

            # 변수 유형별 가이드
            guide_sections = []

            if any("DB_" in var for var in missing_vars):
                guide_sections.append(
                    """
📦 *데이터베이스 설정*:
```bash
DB_HOST=localhost
DB_PORT=5432
DB_USER=hantu_user
DB_PASSWORD=your_password
DB_NAME=hantu_quant
```"""
                )

            if any("TELEGRAM_" in var for var in missing_vars):
                guide_sections.append(
                    """
📱 *텔레그램 설정*:
```bash
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```"""
                )

            if any("KIS_" in var for var in missing_vars):
                guide_sections.append(
                    """
🏦 *한국투자증권 API*:
```bash
KIS_APP_KEY=your_app_key
KIS_APP_SECRET=your_app_secret
KIS_ACCOUNT_NO=your_account
```"""
                )

            guide_text = "\n".join(guide_sections) if guide_sections else ""

            message = f"""🚨 *환경변수 검증 실패*

⏰ 시간: `{current_time}`
🔴 상태: `필수 환경변수 누락`
📊 누락 개수: `{len(missing_vars)}개`

⚠️⚠️⚠️ 배포 차단됨 ⚠️⚠️⚠️

📝 *누락된 환경변수*:
{missing_list}

{guide_text}

🔧 *조치 방법*:
1. 서버 접속
   ```bash
   ssh ubuntu@서버IP
   cd /opt/hantu_quant
   ```

2. 환경변수 설정
   ```bash
   nano .env
   # 누락된 변수 추가
   ```

3. 검증 및 재배포
   ```bash
   ./scripts/deployment/validate_env.sh
   ./scripts/deployment/deploy.sh
   ```

📖 *참고 문서*:
• `.env.example` 파일 참조
• `deploy/DEPLOY_MICRO.md` 배포 가이드

📞 *환경변수 값을 확인할 수 없다면 시스템 관리자에게 문의하세요*"""

            return self.send_message(message, "critical")

        except Exception as e:
            logger.error(f"환경변수 검증 실패 알림 생성 실패: {e}", exc_info=True)
            return False

    def is_enabled(self) -> bool:
        """텔레그램 알림 활성화 상태 확인"""
        return self._enabled


# 전역 인스턴스 (싱글톤 패턴)
_notifier_instance = None


def get_telegram_notifier() -> TelegramNotifier:
    """텔레그램 알림 전송기 인스턴스 가져오기"""
    global _notifier_instance
    if _notifier_instance is None:
        _notifier_instance = TelegramNotifier()
    return _notifier_instance


def send_quick_alert(message: str, priority: str = "normal") -> bool:
    """빠른 알림 전송 (편의 함수)"""
    notifier = get_telegram_notifier()
    return notifier.send_message(message, priority)
