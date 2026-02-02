"""
Phase 2 실행 모듈

감시 리스트 기반 일일 종목 선정을 실행합니다.

처리 흐름:
1. 감시 리스트 로드
2. 가격 매력도 분석
3. 기술적 지표 계산
4. 최종 선정 (점수 기반)
5. 결과 저장 및 알림

분산 배치 모드:
- 18개 배치로 분산 처리 (07:00-08:30, 5분 간격)
- 배치별 독립 실행 (부분 실패 허용)
"""

import json
from typing import Optional
from datetime import datetime
from pathlib import Path

from .base import PhaseExecutor, PhaseExecutionResult
from workflows.phase2_daily_selection import Phase2CLI
from core.daily_selection.daily_updater import DailyUpdater
from workflows.scheduler.notifications import get_notification_service
from core.utils.log_utils import get_logger

logger = get_logger(__name__)


class Phase2Executor(PhaseExecutor):
    """Phase 2 일일 선정 실행자

    Attributes:
        cli: Phase2CLI 인스턴스
        daily_updater: DailyUpdater 인스턴스
        notification_service: 알림 서비스
    """

    def __init__(
        self,
        cli: Optional[Phase2CLI] = None,
        daily_updater: Optional[DailyUpdater] = None,
        parallel_workers: int = 4
    ):
        """초기화

        Args:
            cli: Phase2CLI 인스턴스 (None이면 생성)
            daily_updater: DailyUpdater 인스턴스 (None이면 생성)
            parallel_workers: 병렬 처리 워커 수
        """
        super().__init__("Phase2")
        self.cli = cli or Phase2CLI(p_parallel_workers=parallel_workers)
        self.daily_updater = daily_updater or DailyUpdater(
            p_watchlist_file="data/watchlist/watchlist.json",
            p_output_dir="data/daily_selection"
        )
        self.notification_service = get_notification_service()

    def validate_preconditions(self) -> bool:
        """사전 조건 검증

        검증 항목:
        - Phase2CLI, DailyUpdater 인스턴스 존재
        - 감시 리스트 파일 존재
        - 출력 디렉토리 존재

        Returns:
            조건 만족 시 True
        """
        try:
            # 인스턴스 확인
            if self.cli is None or self.daily_updater is None:
                self.logger.error("Phase2 인스턴스가 없습니다")
                return False

            # 감시 리스트 파일 확인
            watchlist_path = Path("data/watchlist/watchlist.json")
            if not watchlist_path.exists():
                self.logger.error(f"감시 리스트 파일이 없습니다: {watchlist_path}")
                return False

            # 출력 디렉토리 확인 및 생성
            output_dir = Path("data/daily_selection")
            output_dir.mkdir(parents=True, exist_ok=True)

            return True

        except Exception as e:
            self.logger.error(f"사전 조건 검증 실패: {e}", exc_info=True)
            return False

    def _execute_internal(self) -> PhaseExecutionResult:
        """Phase 2 일일 선정 실행 (통합 모드)

        Returns:
            실행 결과 (evaluated_count, selected_count 포함)
        """
        try:
            # 일일 업데이트 실행 (분산 모드 아님)
            success = self.daily_updater.run_daily_update(
                distributed_mode=False,
                batch_index=None
            )

            if not success:
                return PhaseExecutionResult(
                    success=False,
                    error_message="일일 업데이트 실행 실패"
                )

            # 결과 파일에서 통계 추출
            stats = self._extract_selection_stats()

            return PhaseExecutionResult(
                success=True,
                metadata={
                    "evaluated_count": stats["evaluated_count"],
                    "selected_count": stats["selected_count"],
                }
            )

        except Exception as e:
            error_msg = f"Phase 2 실행 중 예외: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            return PhaseExecutionResult(
                success=False,
                error_message=error_msg
            )

    def execute_batch(self, batch_index: int) -> PhaseExecutionResult:
        """Phase 2 분산 배치 실행

        Args:
            batch_index: 배치 번호 (0-17)

        Returns:
            실행 결과
        """
        start_time = datetime.now()

        try:
            self.logger.info(f"[배치] 배치 {batch_index}/17 시작")

            # 첫 번째 배치: Phase 2 시작 알림
            if batch_index == 0:
                self.logger.info("=" * 50)
                self.logger.info("[배치] Phase 2 분산 배치 실행 시작")
                self._send_phase2_start_notification()

            # 배치 실행
            success = self.daily_updater.run_daily_update(
                distributed_mode=True,
                batch_index=batch_index
            )

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            if success:
                self.logger.info(f"배치 {batch_index}/17 완료")

                # 마지막 배치: Phase 2 완료 알림
                if batch_index == 17:
                    self.logger.info("=" * 50)
                    self.logger.info("Phase 2 분산 배치 실행 완료")
                    self._send_phase2_complete_notification()

                return PhaseExecutionResult(
                    success=True,
                    duration_seconds=duration,
                    metadata={"batch_index": batch_index},
                    start_time=start_time,
                    end_time=end_time
                )
            else:
                error_msg = f"배치 {batch_index}/17 실행 실패"
                self.logger.error(error_msg)

                # 배치 실패 알림
                self._send_batch_failure_notification(batch_index)

                return PhaseExecutionResult(
                    success=False,
                    duration_seconds=duration,
                    error_message=error_msg,
                    metadata={"batch_index": batch_index},
                    start_time=start_time,
                    end_time=end_time
                )

        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            error_msg = f"배치 {batch_index}/17 실행 중 예외: {str(e)}"
            self.logger.error(error_msg, exc_info=True)

            # 에러 알림
            self._send_batch_failure_notification(batch_index, str(e))

            return PhaseExecutionResult(
                success=False,
                duration_seconds=duration,
                error_message=error_msg,
                metadata={"batch_index": batch_index},
                start_time=start_time,
                end_time=end_time
            )

    def _extract_selection_stats(self) -> dict:
        """최신 선정 결과 파일에서 통계 추출

        Returns:
            통계 딕셔너리 (evaluated_count, selected_count)
        """
        try:
            today_str = datetime.now().strftime("%Y%m%d")
            selection_file = Path(f"data/daily_selection/daily_selection_{today_str}.json")

            if not selection_file.exists():
                self.logger.warning(f"선정 결과 파일이 없습니다: {selection_file}")
                return {"evaluated_count": 0, "selected_count": 0}

            with open(selection_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            selected_stocks = data.get("selected_stocks", [])
            evaluated_count = data.get("total_evaluated", 0)
            selected_count = len(selected_stocks)

            return {
                "evaluated_count": evaluated_count,
                "selected_count": selected_count
            }

        except Exception as e:
            self.logger.warning(f"통계 추출 실패: {e}", exc_info=True)
            return {"evaluated_count": 0, "selected_count": 0}

    def _send_phase2_start_notification(self) -> None:
        """Phase 2 시작 알림 전송"""
        try:
            message = (
                f"[배치] *Phase 2 시작*\n\n"
                f"• 총 배치: 18개\n"
                f"• 예상 완료: 08:30"
            )
            self.notification_service.send_message(message, priority="normal")
        except Exception as e:
            self.logger.warning(f"Phase 2 시작 알림 전송 실패: {e}", exc_info=True)

    def _send_phase2_complete_notification(self) -> None:
        """Phase 2 완료 알림 전송"""
        try:
            stats = self._extract_selection_stats()
            total_selected = stats["selected_count"]

            message = (
                f"*Phase 2 완료*\n\n"
                f"• 총 선정 종목: {total_selected}개\n"
                f"• 소요 시간: 90분\n"
                f"• 저장: DB (`selection_results` 테이블)"
            )
            self.notification_service.send_message(message, priority="normal")
        except Exception as e:
            self.logger.warning(f"Phase 2 완료 알림 전송 실패: {e}", exc_info=True)

    def _send_batch_failure_notification(
        self,
        batch_index: int,
        error_detail: Optional[str] = None
    ) -> None:
        """배치 실패 알림 전송

        Args:
            batch_index: 배치 번호
            error_detail: 에러 상세 메시지 (선택)
        """
        try:
            if error_detail:
                message = (
                    f"*배치 {batch_index} 실패*\n\n"
                    f"• 에러: {error_detail[:50]}...\n"
                    f"• 다음 배치 진행 중..."
                )
            else:
                message = (
                    f"*배치 {batch_index} 실패*\n\n"
                    f"• 에러: 배치 실행 실패\n"
                    f"• 다음 배치 진행 중..."
                )

            self.notification_service.send_message(message, priority="high")
        except Exception as e:
            self.logger.warning(f"배치 실패 알림 전송 실패: {e}", exc_info=True)

    def handle_failure(self, result: PhaseExecutionResult) -> None:
        """실패 처리: 텔레그램 알림 전송

        Args:
            result: 실패한 실행 결과
        """
        try:
            error_message = (
                f"*Phase 2 일일 선정 실패*\n\n"
                f"시간: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n"
                f"에러: {result.error_message}\n\n"
                f"점검이 필요합니다."
            )
            self.notification_service.send_message(error_message, priority="high")
        except Exception as e:
            self.logger.error(f"실패 알림 전송 실패: {e}", exc_info=True)
