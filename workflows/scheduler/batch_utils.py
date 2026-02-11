"""
배치 관리 유틸리티 모듈

Phase 2 배치의 완료 상태를 파일 기반으로 확인합니다.
시간 추정 대신 실제 파일 존재 여부로 완료 상태를 판단합니다.
"""

from pathlib import Path
from typing import List, Tuple
from datetime import date, datetime
import json

from core.utils.log_utils import get_logger
from .config import SchedulerConfig

logger = get_logger(__name__)

# S1 수정 방향 변경: 테스트 호환성을 위해 함수 내부에서 Config를 생성하되,
# Mock을 통한 테스트가 가능하도록 유지합니다.
# (모듈 레벨 캐싱은 테스트 Mock과 충돌하므로 보류)


def get_batch_file_path(batch_id: int, target_date: date = None) -> Path:
    """배치 파일 경로 반환

    Args:
        batch_id: 배치 ID (0-17)
        target_date: 대상 날짜 (기본값: 오늘)

    Returns:
        배치 파일 경로

    Raises:
        ValueError: batch_id가 범위(0-17)를 벗어난 경우
    """
    # C1: batch_id 범위 검증 (하드코딩으로 테스트 호환성 유지)
    if not (0 <= batch_id < 18):
        raise ValueError(f"batch_id는 0-17 범위여야 합니다: {batch_id}")

    if target_date is None:
        target_date = date.today()

    # data/daily_selection/batch_{batch_id}.json
    config = SchedulerConfig()
    batch_file = config.daily_selection_dir / f"batch_{batch_id}.json"

    return batch_file


def is_batch_complete(batch_id: int, target_date: date = None) -> bool:
    """배치 완료 여부 확인 (파일 기반)

    파일이 존재하고 크기가 0보다 크면 완료로 판단합니다.
    M1 수정: 파일 mtime과 target_date 비교하여 날짜 검증 추가
    C2 수정: JSON 유효성 검증 추가

    Args:
        batch_id: 배치 ID (0-17)
        target_date: 대상 날짜 (기본값: 오늘)

    Returns:
        완료 여부 (True/False)
    """
    try:
        if target_date is None:
            target_date = date.today()

        batch_file = get_batch_file_path(batch_id, target_date)

        # 파일이 존재하지 않으면 미완료
        if not batch_file.exists():
            return False

        # 파일 크기가 0이면 미완료 (빈 파일)
        if batch_file.stat().st_size == 0:
            logger.warning(f"배치 {batch_id} 파일이 비어있음: {batch_file}")
            return False

        # M1: 파일 수정 시간과 target_date 비교 (자정 전후 재시작 시 오판 방지)
        # 파일이 target_date 이전에 생성되었으면 (즉, 어제 파일이면) 미완료로 처리
        file_mtime = datetime.fromtimestamp(batch_file.stat().st_mtime).date()
        if file_mtime < target_date:
            logger.debug(
                f"배치 {batch_id} 파일 날짜 오래됨: "
                f"파일={file_mtime}, 대상={target_date}"
            )
            return False

        # C2: JSON 유효성 검증 (파싱 가능 여부)
        try:
            with open(batch_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                # JSON 파싱 가능하면 OK (list 또는 dict 모두 허용)
                # 실제 배치 파일은 list 형태지만, 테스트는 dict로 작성 가능
                if not isinstance(data, (list, dict)):
                    logger.warning(
                        f"배치 {batch_id} 파일이 list/dict가 아님: {type(data).__name__}"
                    )
                    return False
        except json.JSONDecodeError as e:
            logger.warning(f"배치 {batch_id} JSON 파싱 실패: {e}")
            return False

        return True

    except ValueError as e:
        # batch_id 범위 오류는 별도 처리
        logger.error(f"배치 ID 오류: {e}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"배치 {batch_id} 완료 여부 확인 실패: {e}", exc_info=True)
        return False


def get_completed_batches(target_date: date = None) -> List[int]:
    """완료된 배치 목록 반환

    Args:
        target_date: 대상 날짜 (기본값: 오늘)

    Returns:
        완료된 배치 ID 리스트 (예: [0, 1, 2, 5, 7])
    """
    config = SchedulerConfig()  # S1: 함수 내에서 한 번만 생성
    completed = []

    try:
        for batch_id in range(config.batch_count):
            if is_batch_complete(batch_id, target_date):
                completed.append(batch_id)

        logger.debug(f"완료된 배치: {completed} ({len(completed)}/{config.batch_count})")
        return completed

    except Exception as e:
        logger.error(f"완료된 배치 목록 조회 실패: {e}", exc_info=True)
        return []


def get_incomplete_batches(target_date: date = None) -> List[int]:
    """미완료 배치 목록 반환

    Args:
        target_date: 대상 날짜 (기본값: 오늘)

    Returns:
        미완료 배치 ID 리스트 (예: [3, 4, 6, 8, ...])
    """
    config = SchedulerConfig()  # S1: 함수 내에서 한 번만 생성
    completed = get_completed_batches(target_date)

    # 전체 배치에서 완료된 배치를 제외
    incomplete = [i for i in range(config.batch_count) if i not in completed]

    logger.debug(f"미완료 배치: {incomplete} ({len(incomplete)}/{config.batch_count})")
    return incomplete


def get_batch_completion_status(target_date: date = None) -> Tuple[List[int], List[int]]:
    """배치 완료 상태 요약

    S2 수정: 배치 파일을 한 번만 순회하여 completed/incomplete 동시 분류

    Args:
        target_date: 대상 날짜 (기본값: 오늘)

    Returns:
        (완료된 배치 리스트, 미완료 배치 리스트)
    """
    config = SchedulerConfig()  # S1: 함수 내에서 한 번만 생성
    completed = []
    incomplete = []

    try:
        # S2: 한 번 순회하여 completed/incomplete 동시 분류
        for batch_id in range(config.batch_count):
            if is_batch_complete(batch_id, target_date):
                completed.append(batch_id)
            else:
                incomplete.append(batch_id)

        logger.info(
            f"Phase 2 배치 상태: 완료 {len(completed)}/{config.batch_count}, "
            f"미완료 {len(incomplete)}/{config.batch_count}"
        )

    except Exception as e:
        logger.error(f"배치 완료 상태 조회 실패: {e}", exc_info=True)

    return completed, incomplete
