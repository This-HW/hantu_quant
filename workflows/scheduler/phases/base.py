"""
Phase 실행 기본 클래스

모든 Phase 실행자가 상속받아야 하는 추상 클래스입니다.
공통 에러 처리 및 로깅 패턴을 제공합니다.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
from core.utils.log_utils import get_logger

logger = get_logger(__name__)


@dataclass
class PhaseExecutionResult:
    """Phase 실행 결과 데이터 클래스

    Attributes:
        success: 실행 성공 여부
        duration_seconds: 실행 소요 시간 (초)
        metadata: 추가 메타데이터 (Phase별 커스텀 정보)
        error_message: 실패 시 에러 메시지
        start_time: 시작 시각
        end_time: 종료 시각
    """
    success: bool
    duration_seconds: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "success": self.success,
            "duration_seconds": self.duration_seconds,
            "metadata": self.metadata,
            "error_message": self.error_message,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
        }


class PhaseExecutor(ABC):
    """Phase 실행자 추상 기본 클래스

    모든 Phase 실행자는 이 클래스를 상속받아 구현합니다.

    Features:
        - 실행 전 사전 조건 검증
        - 실행 시간 측정
        - 예외 처리 및 로깅
        - 실행 결과 반환
    """

    def __init__(self, phase_name: str):
        """초기화

        Args:
            phase_name: Phase 이름 (로깅용)
        """
        self.phase_name = phase_name
        self.logger = get_logger(f"{__name__}.{phase_name}")

    @abstractmethod
    def validate_preconditions(self) -> bool:
        """실행 전 사전 조건 검증

        Returns:
            조건 만족 시 True, 아니면 False

        Example:
            - Phase 1: 네트워크 연결 확인
            - Phase 2: 감시 리스트 파일 존재 확인
        """
        pass

    @abstractmethod
    def _execute_internal(self) -> PhaseExecutionResult:
        """내부 실행 로직 (서브클래스에서 구현)

        Returns:
            실행 결과
        """
        pass

    def execute(self) -> PhaseExecutionResult:
        """Phase 실행 (템플릿 메서드)

        실행 흐름:
        1. 사전 조건 검증
        2. 실행 시작 로깅
        3. 내부 로직 실행 (_execute_internal)
        4. 실행 시간 측정
        5. 결과 로깅
        6. 실패 시 에러 처리

        Returns:
            실행 결과
        """
        start_time = datetime.now()

        try:
            # 1. 사전 조건 검증
            if not self.validate_preconditions():
                error_msg = f"{self.phase_name}: 사전 조건 검증 실패"
                self.logger.error(error_msg)
                return PhaseExecutionResult(
                    success=False,
                    error_message=error_msg,
                    start_time=start_time,
                    end_time=datetime.now()
                )

            # 2. 실행 시작 로깅
            self.logger.info(f"=== {self.phase_name} 시작 ===")

            # 3. 내부 로직 실행
            result = self._execute_internal()

            # 4. 실행 시간 측정
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            result.start_time = start_time
            result.end_time = end_time
            result.duration_seconds = duration

            # 5. 결과 로깅
            if result.success:
                self.logger.info(
                    f"{self.phase_name} 완료 (소요 시간: {duration:.2f}초)"
                )
            else:
                self.logger.error(
                    f"{self.phase_name} 실패: {result.error_message}"
                )

            return result

        except Exception as e:
            # 6. 예외 처리
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            error_msg = f"{self.phase_name} 실행 중 예외 발생: {str(e)}"
            self.logger.error(error_msg, exc_info=True)

            return PhaseExecutionResult(
                success=False,
                duration_seconds=duration,
                error_message=error_msg,
                start_time=start_time,
                end_time=end_time
            )

    def handle_failure(self, result: PhaseExecutionResult) -> None:
        """실패 처리 (서브클래스에서 오버라이드 가능)

        Args:
            result: 실패한 실행 결과

        Example:
            - 텔레그램 알림 전송
            - 재시도 로직
            - 폴백 동작
        """
        self.logger.warning(
            f"{self.phase_name} 실패 처리: {result.error_message}"
        )
