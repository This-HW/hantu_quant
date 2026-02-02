"""
Phase 1 실행 모듈

전체 종목 스크리닝을 실행하고 감시 리스트를 생성합니다.

처리 흐름:
1. 전체 시장 스크리닝 (코스피 + 코스닥)
2. 점수 기준 필터링
3. 감시 리스트 업데이트
4. 결과 알림 (텔레그램)
"""

import os
import json
from typing import Optional
from datetime import datetime
from pathlib import Path

from .base import PhaseExecutor, PhaseExecutionResult
from workflows.phase1_watchlist import Phase1Workflow
from workflows.scheduler.notifications import get_notification_service
from core.utils.log_utils import get_logger

logger = get_logger(__name__)


class Phase1Executor(PhaseExecutor):
    """Phase 1 스크리닝 실행자

    Attributes:
        workflow: Phase1Workflow 인스턴스
        notification_service: 알림 서비스
    """

    def __init__(
        self,
        workflow: Optional[Phase1Workflow] = None,
        parallel_workers: int = 4
    ):
        """초기화

        Args:
            workflow: Phase1Workflow 인스턴스 (None이면 생성)
            parallel_workers: 병렬 처리 워커 수
        """
        super().__init__("Phase1")
        self.workflow = workflow or Phase1Workflow(p_parallel_workers=parallel_workers)
        self.notification_service = get_notification_service()

    def validate_preconditions(self) -> bool:
        """사전 조건 검증

        검증 항목:
        - Phase1Workflow 인스턴스 존재
        - 데이터 디렉토리 존재

        Returns:
            조건 만족 시 True
        """
        try:
            # workflow 인스턴스 확인
            if self.workflow is None:
                self.logger.error("Phase1Workflow 인스턴스가 없습니다")
                return False

            # 데이터 디렉토리 확인 및 생성
            data_dir = Path("data/watchlist")
            data_dir.mkdir(parents=True, exist_ok=True)

            return True

        except Exception as e:
            self.logger.error(f"사전 조건 검증 실패: {e}", exc_info=True)
            return False

    def _execute_internal(self) -> PhaseExecutionResult:
        """Phase 1 스크리닝 실행

        Returns:
            실행 결과 (total_screened, added_count 포함)
        """
        try:
            # 전체 스크리닝 실행 (알림은 Phase1Workflow에서 발송)
            success = self.workflow.run_full_screening(p_send_notification=True)

            if not success:
                return PhaseExecutionResult(
                    success=False,
                    error_message="스크리닝 실행 실패"
                )

            # 결과 파일에서 통계 추출
            stats = self._extract_screening_stats()

            return PhaseExecutionResult(
                success=True,
                metadata={
                    "total_screened": stats["total_screened"],
                    "added_count": stats["added_count"],
                }
            )

        except Exception as e:
            error_msg = f"Phase 1 실행 중 예외: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            return PhaseExecutionResult(
                success=False,
                error_message=error_msg
            )

    def _extract_screening_stats(self) -> dict:
        """최신 스크리닝 결과 파일에서 통계 추출

        Returns:
            통계 딕셔너리 (total_screened, added_count)
        """
        try:
            screening_files = [
                f for f in os.listdir("data/watchlist/")
                if f.startswith("screening_results_")
            ]

            if not screening_files:
                self.logger.warning("스크리닝 결과 파일이 없습니다")
                return {"total_screened": 0, "added_count": 0}

            # 최신 파일 선택
            latest_file = sorted(screening_files)[-1]
            filepath = os.path.join("data/watchlist", latest_file)

            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            results = data.get('results', [])
            total_screened = len(results)
            added_count = len([r for r in results if r.get('overall_passed', False)])

            return {
                "total_screened": total_screened,
                "added_count": added_count
            }

        except Exception as e:
            self.logger.warning(f"통계 추출 실패: {e}", exc_info=True)
            return {"total_screened": 0, "added_count": 0}

    def handle_failure(self, result: PhaseExecutionResult) -> None:
        """실패 처리: 긴급 텔레그램 알림 전송

        Args:
            result: 실패한 실행 결과
        """
        try:
            error_message = (
                f"*Phase 1 스크리닝 실패*\n\n"
                f"시간: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n"
                f"에러: {result.error_message}\n\n"
                f"시스템 점검이 필요합니다."
            )
            self.notification_service.send_message(error_message, priority="emergency")
        except Exception as e:
            self.logger.error(f"실패 알림 전송 실패: {e}", exc_info=True)
