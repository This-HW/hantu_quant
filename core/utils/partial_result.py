"""
부분 실패 허용 처리 모듈 (P0-2)

1개 종목 실패로 전체 스크리닝/선정이 중단되는 것을 방지합니다.
- 성공률 90% 이상이면 계속 진행
- 실패 종목 로깅 및 별도 저장
"""

import logging
from dataclasses import dataclass, field
from typing import List, Tuple, Any, TypeVar, Generic, Callable, Optional
from datetime import datetime
import json
import os

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class PartialResult(Generic[T]):
    """부분 실패 허용 결과 클래스

    Attributes:
        successful: 성공한 결과 리스트
        failed: 실패한 항목 리스트 [(item_id, error_message), ...]
        min_success_rate: 최소 성공률 (기본값: 0.9 = 90%)
    """
    successful: List[T] = field(default_factory=list)
    failed: List[Tuple[str, str]] = field(default_factory=list)
    min_success_rate: float = 0.9

    @property
    def total_count(self) -> int:
        """전체 처리 항목 수"""
        return len(self.successful) + len(self.failed)

    @property
    def success_count(self) -> int:
        """성공 항목 수"""
        return len(self.successful)

    @property
    def fail_count(self) -> int:
        """실패 항목 수"""
        return len(self.failed)

    @property
    def success_rate(self) -> float:
        """성공률 (0.0 ~ 1.0)"""
        total = self.total_count
        return len(self.successful) / total if total > 0 else 0.0

    @property
    def is_acceptable(self) -> bool:
        """성공률이 최소 기준 이상인지 확인"""
        return self.success_rate >= self.min_success_rate

    def add_success(self, result: T) -> None:
        """성공 결과 추가"""
        self.successful.append(result)

    def add_failure(self, item_id: str, error_message: str) -> None:
        """실패 항목 추가"""
        self.failed.append((item_id, error_message))
        logger.warning(f"항목 처리 실패 - {item_id}: {error_message}")

    def get_summary(self) -> dict:
        """결과 요약 반환"""
        return {
            "total_count": self.total_count,
            "success_count": self.success_count,
            "fail_count": self.fail_count,
            "success_rate": self.success_rate,
            "is_acceptable": self.is_acceptable,
            "min_success_rate": self.min_success_rate,
            "failed_items": self.failed[:10]  # 처음 10개만 포함
        }

    def log_summary(self, operation_name: str = "처리") -> None:
        """결과 요약 로깅"""
        summary = self.get_summary()

        if self.is_acceptable:
            logger.info(
                f"{operation_name} 완료 - 성공: {summary['success_count']}/{summary['total_count']} "
                f"({summary['success_rate']:.1%}), 실패: {summary['fail_count']}개"
            )
        else:
            logger.warning(
                f"{operation_name} 성공률 미달 - 성공: {summary['success_count']}/{summary['total_count']} "
                f"({summary['success_rate']:.1%} < {summary['min_success_rate']:.0%}), "
                f"실패: {summary['fail_count']}개"
            )

        # 실패 항목이 있으면 상세 로깅
        if self.failed:
            logger.warning(f"실패 항목 목록 (총 {len(self.failed)}개):")
            for item_id, error_msg in self.failed[:5]:  # 처음 5개만 로그
                logger.warning(f"  - {item_id}: {error_msg}")
            if len(self.failed) > 5:
                logger.warning(f"  ... 외 {len(self.failed) - 5}개")


def save_failed_items(
    failed_items: List[Tuple[str, str]],
    operation_type: str,
    output_dir: str = "data/logs/failures"
) -> Optional[str]:
    """실패 항목을 파일로 저장

    Args:
        failed_items: 실패 항목 리스트 [(item_id, error_message), ...]
        operation_type: 작업 유형 (예: "screening", "daily_selection")
        output_dir: 출력 디렉토리

    Returns:
        저장된 파일 경로 (실패 시 None)
    """
    if not failed_items:
        return None

    try:
        os.makedirs(output_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{operation_type}_failures_{timestamp}.json"
        filepath = os.path.join(output_dir, filename)

        data = {
            "operation_type": operation_type,
            "timestamp": datetime.now().isoformat(),
            "total_failures": len(failed_items),
            "failures": [
                {"item_id": item_id, "error": error_msg}
                for item_id, error_msg in failed_items
            ]
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"실패 항목 저장 완료: {filepath}")
        return filepath

    except Exception as e:
        logger.error(f"실패 항목 저장 오류: {e}", exc_info=True)
        return None


def process_with_partial_failure(
    items: List[Any],
    processor: Callable[[Any], T],
    item_id_getter: Callable[[Any], str],
    operation_name: str = "처리",
    min_success_rate: float = 0.9,
    save_failures: bool = True,
    failure_output_dir: str = "data/logs/failures"
) -> PartialResult[T]:
    """부분 실패를 허용하면서 항목들을 처리

    Args:
        items: 처리할 항목 리스트
        processor: 각 항목을 처리하는 함수 (item -> result)
        item_id_getter: 항목에서 ID를 추출하는 함수 (item -> str)
        operation_name: 작업 이름 (로깅용)
        min_success_rate: 최소 성공률 (기본값: 0.9)
        save_failures: 실패 항목 파일 저장 여부
        failure_output_dir: 실패 항목 저장 디렉토리

    Returns:
        PartialResult: 처리 결과
    """
    result = PartialResult[T](min_success_rate=min_success_rate)

    logger.info(f"{operation_name} 시작 - 총 {len(items)}개 항목")

    for item in items:
        item_id = "unknown"
        try:
            item_id = item_id_getter(item)
            processed = processor(item)
            result.add_success(processed)
        except Exception as e:
            result.add_failure(item_id, str(e))

    # 결과 요약 로깅
    result.log_summary(operation_name)

    # 실패 항목 저장
    if save_failures and result.failed:
        save_failed_items(
            result.failed,
            operation_name.replace(" ", "_").lower(),
            failure_output_dir
        )

    return result


class PartialFailureHandler:
    """부분 실패 처리를 위한 헬퍼 클래스"""

    def __init__(
        self,
        min_success_rate: float = 0.9,
        save_failures: bool = True,
        failure_output_dir: str = "data/logs/failures"
    ):
        """초기화

        Args:
            min_success_rate: 최소 성공률
            save_failures: 실패 항목 파일 저장 여부
            failure_output_dir: 실패 항목 저장 디렉토리
        """
        self.min_success_rate = min_success_rate
        self.save_failures = save_failures
        self.failure_output_dir = failure_output_dir

    def process(
        self,
        items: List[Any],
        processor: Callable[[Any], T],
        item_id_getter: Callable[[Any], str],
        operation_name: str = "처리"
    ) -> PartialResult[T]:
        """부분 실패를 허용하면서 항목들을 처리

        Args:
            items: 처리할 항목 리스트
            processor: 각 항목을 처리하는 함수
            item_id_getter: 항목에서 ID를 추출하는 함수
            operation_name: 작업 이름

        Returns:
            PartialResult: 처리 결과
        """
        return process_with_partial_failure(
            items=items,
            processor=processor,
            item_id_getter=item_id_getter,
            operation_name=operation_name,
            min_success_rate=self.min_success_rate,
            save_failures=self.save_failures,
            failure_output_dir=self.failure_output_dir
        )

    def should_continue(self, result: PartialResult) -> bool:
        """처리를 계속해야 하는지 확인

        Args:
            result: 부분 처리 결과

        Returns:
            성공률이 최소 기준 이상이면 True
        """
        return result.is_acceptable
