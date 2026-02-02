"""
작업 복구 관리 모듈

스케줄러 재시작 시 누락된 작업을 자동으로 복구합니다.
시간대별 복구 로직을 통해 중단된 워크플로우를 이어서 실행합니다.

Features:
    - 시간대별 복구 로직 (Phase 1/2/자동매매/정리/성과분석)
    - DB 기반 완료 상태 확인
    - 누락된 Phase 2 배치 자동 복구
    - 텔레그램 복구 알림
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Tuple

from core.utils.log_utils import get_logger
from .config import SchedulerConfig
from .notifications import NotificationService

logger = get_logger(__name__)


class RecoveryManager:
    """작업 복구 관리 클래스

    스케줄러 재시작 시 누락된 작업을 자동으로 감지하고 복구합니다.
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

    def check_and_recover_missed_tasks(
        self,
        run_screening_callback,
        run_batch_callback,
        start_trading_callback,
        run_market_close_callback,
        run_performance_callback
    ) -> List[str]:
        """스케줄러 재시작 시 누락된 작업 자동 실행

        복구 시나리오 (평일만):
        - 06:00~07:00: Phase 1 실행
        - 07:00~09:00: Phase 2 미완료 배치 실행
        - 09:00~15:30: 매매 실행
        - 15:30~16:00: 시장 마감 정리 실행
        - 16:00~17:00: 시장 마감 정리 + 일일 성과 분석 실행
        - 17:00 이후: 모든 정리 작업 실행

        Note: 재무 데이터는 주말(토요일 10:00)에 수집하며, 평일에는 DB 데이터 재사용

        Args:
            run_screening_callback: Phase 1 스크리닝 실행 함수
            run_batch_callback: Phase 2 배치 실행 함수
            start_trading_callback: 자동 매매 시작 함수
            run_market_close_callback: 시장 마감 정리 함수
            run_performance_callback: 일일 성과 분석 함수

        Returns:
            복구된 작업 목록
        """
        try:
            now = datetime.now()

            # 주말 제외
            if now.weekday() >= 5:
                logger.info("주말 - 복구 작업 스킵")
                return []

            # 시간대 정의
            screening_time = now.replace(hour=6, minute=0, second=0, microsecond=0)
            phase2_start = now.replace(hour=7, minute=0, second=0, microsecond=0)
            phase2_end = now.replace(hour=8, minute=30, second=0, microsecond=0)
            market_open = now.replace(hour=9, minute=0, second=0, microsecond=0)
            market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
            cleanup_time = now.replace(hour=16, minute=0, second=0, microsecond=0)
            performance_time = now.replace(hour=17, minute=0, second=0, microsecond=0)

            # === 06:00 이전: 복구 불필요 ===
            if now < screening_time:
                logger.info("스크리닝 시간(06:00) 전 - 복구 작업 스킵")
                return []

            # === 복구 로직 시작 ===
            logger.info(f"재시작 감지 - 복구 작업 시작 ({now.strftime('%H:%M')})")
            print(f"\n[갱신] 스케줄러 재시작 감지 ({now.strftime('%H:%M')}) - 복구 작업 시작...")

            recovered_tasks = []

            # 재무 데이터는 주말(토요일)에 수집하므로, 평일에는 DB 데이터 확인만 수행
            try:
                from core.api.krx_client import KRXClient

                krx_client = KRXClient()
                fundamentals_df = krx_client.load_market_fundamentals()
                if fundamentals_df.empty:
                    logger.warning("재무 데이터 없음 - 토요일 수집 후 사용 가능")
                    print("재무 데이터 없음 (토요일에 자동 수집됩니다)")
                else:
                    logger.info(f"재무 데이터 확인 완료: {len(fundamentals_df)}개 종목")
            except Exception as e:
                logger.warning(f"재무 데이터 확인 실패: {e}", exc_info=True)

            # 1. Phase 1/2 스크리닝 (06:00 이후)
            screening_needed = False
            if now >= screening_time:
                db_has_selection = self._check_today_selection_in_db(now.date())
                if db_has_selection:
                    logger.info("DB에 오늘 선정 결과 있음 - 스크리닝 스킵")
                else:
                    # DB에 없으면 파일 확인
                    today_str = now.strftime("%Y%m%d")
                    selection_file = Path(f"data/daily_selection/daily_selection_{today_str}.json")

                    if selection_file.exists():
                        file_mtime = datetime.fromtimestamp(selection_file.stat().st_mtime)
                        if file_mtime >= screening_time:
                            logger.info(f"파일 정상 (생성: {file_mtime.strftime('%Y-%m-%d %H:%M')}) - 스크리닝 스킵")
                        else:
                            screening_needed = True
                            logger.info(f"파일이 오래됨 (생성: {file_mtime.strftime('%Y-%m-%d %H:%M')}) - 스크리닝 필요")
                    else:
                        screening_needed = True
                        logger.info("DB/파일 모두 없음 - 스크리닝 필요")

            if screening_needed:
                print("[상세] 일간 스크리닝 실행...")
                run_screening_callback()
                recovered_tasks.append("일간 스크리닝")

            # 2. Phase 2 미완료 배치 복구 (07:00~08:30 시간대 재시작)
            if phase2_start <= now < market_open:
                # 현재 시간 기준으로 미완료 배치 계산
                elapsed_minutes = (now.hour - 7) * 60 + now.minute
                completed_batches = elapsed_minutes // 5

                if completed_batches < 18:
                    logger.info(f"Phase 2 시간대 재시작 감지 - 배치 {completed_batches}-17 복구 실행 시작")
                    print(f"[배치] Phase 2 복구: 배치 {completed_batches}-17 실행...")

                    for i in range(completed_batches, 18):
                        run_batch_callback(i)

                    recovered_tasks.append(f"Phase 2 배치 {completed_batches}-17")

            # 3. 자동 매매 (09:00~15:30 장중이면 시작)
            if now >= market_open and now < market_close:
                print("[자동] 자동 매매 시작...")
                trading_started = start_trading_callback(from_recovery=True)
                if trading_started:
                    recovered_tasks.append("자동 매매 시작")
                else:
                    logger.info("자동 매매 시작 스킵됨 (이미 실행 중이거나 실패)")

            # 4. 시장 마감 정리 (16:00 이후)
            if now >= cleanup_time:
                print("[종료] 시장 마감 정리 실행...")
                run_market_close_callback()
                recovered_tasks.append("시장 마감 정리")

            # 5. 일일 성과 분석 (17:00 이후)
            if now >= performance_time:
                print("일일 성과 분석 실행...")
                run_performance_callback()
                recovered_tasks.append("일일 성과 분석")

            # 복구 결과 알림
            self._send_recovery_notification(now, recovered_tasks)

            # 결과 출력
            if recovered_tasks:
                print(f"복구 작업 완료: {', '.join(recovered_tasks)}\n")
            else:
                print("복구 필요 없음 - 모든 작업 이미 완료됨\n")

            logger.info(f"복구 작업 완료: {recovered_tasks if recovered_tasks else '없음'}")
            return recovered_tasks

        except Exception as e:
            logger.error(f"복구 작업 실패: {e}", exc_info=True)
            print(f"복구 작업 실패: {e}")
            return []

    def _check_today_selection_in_db(self, target_date) -> bool:
        """DB에서 오늘 선정 결과가 있는지 확인

        Args:
            target_date: 확인할 날짜

        Returns:
            선정 결과 존재 여부
        """
        try:
            from core.database.session import DatabaseSession
            from core.database.models import SelectionResult

            db = DatabaseSession()
            with db.get_session() as session:
                count = (
                    session.query(SelectionResult)
                    .filter(SelectionResult.selection_date == target_date)
                    .count()
                )
                return count > 0
        except Exception as e:
            logger.warning(f"DB 선정 결과 확인 실패: {e}", exc_info=True)
            return False

    def _send_recovery_notification(self, now: datetime, recovered_tasks: List[str]) -> None:
        """복구 알림 전송

        Args:
            now: 현재 시각
            recovered_tasks: 복구된 작업 목록
        """
        try:
            if recovered_tasks:
                task_list = "\n• ".join(recovered_tasks)
                message = (
                    f"[갱신] *스케줄러 재시작 복구*\n"
                    f"`{now.strftime('%H:%M')}` 재시작\n\n"
                    f"*복구된 작업:*\n• {task_list}"
                )
                success = self.notification_service.send_message(message, "high")
                if not success:
                    logger.warning("복구 알림 전송 실패")
            else:
                # 복구 작업이 없어도 재시작 알림 전송
                message = (
                    f"[갱신] *스케줄러 재시작*\n"
                    f"`{now.strftime('%H:%M')}` 재시작\n\n"
                    f"모든 작업이 이미 완료되어 추가 복구 불필요"
                )
                success = self.notification_service.send_message(message, "normal")
                if not success:
                    logger.warning("재시작 알림 전송 실패")

        except Exception as e:
            logger.error(f"복구 알림 전송 중 오류: {e}", exc_info=True)
