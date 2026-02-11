"""
배치 유틸리티 함수 테스트

TDD Red-Green-Refactor 사이클:
1. Red: 실패하는 테스트 작성 (이 파일)
2. Green: 최소 구현으로 통과 (workflows/scheduler/batch_utils.py)
3. Refactor: 코드 개선 (테스트는 여전히 통과)
"""

import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가 (pytest import 이슈 해결)
project_root = Path(__file__).parent.parent.parent.parent.absolute()
sys.path.insert(0, str(project_root))

import pytest
from datetime import date
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os

# 동적 import로 workflows.scheduler를 강제로 로드
import importlib
workflows_scheduler_batch_utils = importlib.import_module("workflows.scheduler.batch_utils")
workflows_scheduler_config = importlib.import_module("workflows.scheduler.config")

# 함수 및 클래스 참조
get_batch_file_path = workflows_scheduler_batch_utils.get_batch_file_path
is_batch_complete = workflows_scheduler_batch_utils.is_batch_complete
get_completed_batches = workflows_scheduler_batch_utils.get_completed_batches
get_incomplete_batches = workflows_scheduler_batch_utils.get_incomplete_batches
get_batch_completion_status = workflows_scheduler_batch_utils.get_batch_completion_status
SchedulerConfig = workflows_scheduler_config.SchedulerConfig


class TestGetBatchFilePath:
    """get_batch_file_path() 함수 테스트"""

    def test_returns_correct_path_for_batch_0(self):
        """배치 0의 파일 경로를 정확히 반환"""
        # Arrange
        batch_id = 0
        test_date = date(2026, 2, 11)

        # Act
        result = get_batch_file_path(batch_id, test_date)

        # Assert
        assert isinstance(result, Path)
        assert result.name == "batch_0.json"
        assert "daily_selection" in str(result)

    def test_returns_correct_path_for_batch_17(self):
        """배치 17의 파일 경로를 정확히 반환"""
        # Arrange
        batch_id = 17
        test_date = date(2026, 2, 11)

        # Act
        result = get_batch_file_path(batch_id, test_date)

        # Assert
        assert isinstance(result, Path)
        assert result.name == "batch_17.json"

    def test_uses_today_when_date_not_provided(self):
        """날짜가 제공되지 않으면 오늘 날짜 사용"""
        # Arrange
        batch_id = 5

        # Act
        result = get_batch_file_path(batch_id)

        # Assert
        assert isinstance(result, Path)
        assert result.name == "batch_5.json"


class TestIsBatchComplete:
    """is_batch_complete() 함수 테스트"""

    def test_returns_true_when_file_exists_with_content(self, tmp_path):
        """파일이 존재하고 내용이 있으면 True 반환"""
        # Arrange
        batch_id = 0
        test_date = date(2026, 2, 11)

        # 임시 파일 생성 (내용 있음)
        batch_file = tmp_path / "batch_0.json"
        batch_file.write_text('{"data": "test"}')

        # Mock config to use tmp_path
        with patch("workflows.scheduler.batch_utils.SchedulerConfig") as mock_config:
            mock_instance = Mock()
            mock_instance.daily_selection_dir = tmp_path
            mock_config.return_value = mock_instance

            # Act
            result = is_batch_complete(batch_id, test_date)

            # Assert
            assert result is True

    def test_returns_false_when_file_not_exists(self, tmp_path):
        """파일이 존재하지 않으면 False 반환"""
        # Arrange
        batch_id = 5
        test_date = date(2026, 2, 11)

        # Mock config to use tmp_path
        with patch("workflows.scheduler.batch_utils.SchedulerConfig") as mock_config:
            mock_instance = Mock()
            mock_instance.daily_selection_dir = tmp_path
            mock_config.return_value = mock_instance

            # Act
            result = is_batch_complete(batch_id, test_date)

            # Assert
            assert result is False

    def test_returns_false_when_file_is_empty(self, tmp_path):
        """파일이 비어있으면 False 반환"""
        # Arrange
        batch_id = 3
        test_date = date(2026, 2, 11)

        # 빈 파일 생성
        batch_file = tmp_path / "batch_3.json"
        batch_file.write_text("")

        # Mock config to use tmp_path
        with patch("workflows.scheduler.batch_utils.SchedulerConfig") as mock_config:
            mock_instance = Mock()
            mock_instance.daily_selection_dir = tmp_path
            mock_config.return_value = mock_instance

            # Act
            result = is_batch_complete(batch_id, test_date)

            # Assert
            assert result is False

    def test_returns_false_when_file_size_is_zero(self, tmp_path):
        """파일 크기가 0이면 False 반환"""
        # Arrange
        batch_id = 7
        test_date = date(2026, 2, 11)

        # 빈 파일 생성 (크기 0)
        batch_file = tmp_path / "batch_7.json"
        batch_file.touch()

        # Mock config to use tmp_path
        with patch("workflows.scheduler.batch_utils.SchedulerConfig") as mock_config:
            mock_instance = Mock()
            mock_instance.daily_selection_dir = tmp_path
            mock_config.return_value = mock_instance

            # Act
            result = is_batch_complete(batch_id, test_date)

            # Assert
            assert result is False

    def test_handles_file_permission_error(self, tmp_path):
        """파일 읽기 권한 없을 때 False 반환"""
        # Arrange
        batch_id = 10
        test_date = date(2026, 2, 11)

        # Mock config
        with patch("workflows.scheduler.batch_utils.SchedulerConfig") as mock_config:
            mock_instance = Mock()
            mock_instance.daily_selection_dir = tmp_path
            mock_config.return_value = mock_instance

            # Mock Path.exists() to raise PermissionError
            with patch("pathlib.Path.exists", side_effect=PermissionError("권한 없음")):
                # Act
                result = is_batch_complete(batch_id, test_date)

                # Assert
                assert result is False

    def test_handles_unexpected_exception(self, tmp_path):
        """예상치 못한 예외 발생 시 False 반환"""
        # Arrange
        batch_id = 15
        test_date = date(2026, 2, 11)

        # Mock config
        with patch("workflows.scheduler.batch_utils.SchedulerConfig") as mock_config:
            mock_instance = Mock()
            mock_instance.daily_selection_dir = tmp_path
            mock_config.return_value = mock_instance

            # Mock Path.stat() to raise unexpected error
            with patch("pathlib.Path.stat", side_effect=RuntimeError("예상치 못한 에러")):
                # Act
                result = is_batch_complete(batch_id, test_date)

                # Assert
                assert result is False


class TestGetCompletedBatches:
    """get_completed_batches() 함수 테스트"""

    def test_returns_empty_list_when_no_batches_complete(self, tmp_path):
        """완료된 배치가 없으면 빈 리스트 반환"""
        # Arrange
        test_date = date(2026, 2, 11)

        # Mock config to use tmp_path
        with patch("workflows.scheduler.batch_utils.SchedulerConfig") as mock_config:
            mock_instance = Mock()
            mock_instance.daily_selection_dir = tmp_path
            mock_instance.batch_count = 18
            mock_config.return_value = mock_instance

            # Act
            result = get_completed_batches(test_date)

            # Assert
            assert result == []

    def test_returns_all_batches_when_all_complete(self, tmp_path):
        """모든 배치가 완료되면 전체 리스트 반환"""
        # Arrange
        test_date = date(2026, 2, 11)

        # 모든 배치 파일 생성 (0-17)
        for i in range(18):
            batch_file = tmp_path / f"batch_{i}.json"
            batch_file.write_text('{"data": "test"}')

        # Mock config to use tmp_path
        with patch("workflows.scheduler.batch_utils.SchedulerConfig") as mock_config:
            mock_instance = Mock()
            mock_instance.daily_selection_dir = tmp_path
            mock_instance.batch_count = 18
            mock_config.return_value = mock_instance

            # Act
            result = get_completed_batches(test_date)

            # Assert
            assert result == list(range(18))

    def test_returns_partial_list_when_some_complete(self, tmp_path):
        """일부 배치만 완료되면 해당 리스트 반환"""
        # Arrange
        test_date = date(2026, 2, 11)
        completed_batches = [0, 1, 2, 5, 7, 10]

        # 일부 배치 파일만 생성
        for i in completed_batches:
            batch_file = tmp_path / f"batch_{i}.json"
            batch_file.write_text('{"data": "test"}')

        # Mock config to use tmp_path
        with patch("workflows.scheduler.batch_utils.SchedulerConfig") as mock_config:
            mock_instance = Mock()
            mock_instance.daily_selection_dir = tmp_path
            mock_instance.batch_count = 18
            mock_config.return_value = mock_instance

            # Act
            result = get_completed_batches(test_date)

            # Assert
            assert result == completed_batches

    def test_ignores_empty_files(self, tmp_path):
        """빈 파일은 완료로 간주하지 않음"""
        # Arrange
        test_date = date(2026, 2, 11)

        # 일부는 내용 있음, 일부는 빈 파일
        batch_0 = tmp_path / "batch_0.json"
        batch_0.write_text('{"data": "test"}')

        batch_1 = tmp_path / "batch_1.json"
        batch_1.write_text("")  # 빈 파일

        batch_2 = tmp_path / "batch_2.json"
        batch_2.write_text('{"data": "test"}')

        # Mock config to use tmp_path
        with patch("workflows.scheduler.batch_utils.SchedulerConfig") as mock_config:
            mock_instance = Mock()
            mock_instance.daily_selection_dir = tmp_path
            mock_instance.batch_count = 18
            mock_config.return_value = mock_instance

            # Act
            result = get_completed_batches(test_date)

            # Assert
            assert result == [0, 2]  # 배치 1은 제외

    def test_handles_exception_gracefully(self, tmp_path):
        """예외 발생 시 빈 리스트 반환 (is_batch_complete에서 예외)"""
        # Arrange
        test_date = date(2026, 2, 11)

        # Mock config to use tmp_path
        with patch("workflows.scheduler.batch_utils.SchedulerConfig") as mock_config:
            mock_instance = Mock()
            mock_instance.daily_selection_dir = tmp_path
            mock_instance.batch_count = 18
            mock_config.return_value = mock_instance

            # Mock is_batch_complete to raise exception
            with patch("workflows.scheduler.batch_utils.is_batch_complete", side_effect=RuntimeError("예상치 못한 에러")):
                # Act
                result = get_completed_batches(test_date)

                # Assert
                assert result == []


class TestGetIncompleteBatches:
    """get_incomplete_batches() 함수 테스트"""

    def test_returns_all_batches_when_none_complete(self, tmp_path):
        """완료된 배치가 없으면 전체 리스트 반환"""
        # Arrange
        test_date = date(2026, 2, 11)

        # Mock config to use tmp_path
        with patch("workflows.scheduler.batch_utils.SchedulerConfig") as mock_config:
            mock_instance = Mock()
            mock_instance.daily_selection_dir = tmp_path
            mock_instance.batch_count = 18
            mock_config.return_value = mock_instance

            # Act
            result = get_incomplete_batches(test_date)

            # Assert
            assert result == list(range(18))

    def test_returns_empty_list_when_all_complete(self, tmp_path):
        """모든 배치가 완료되면 빈 리스트 반환"""
        # Arrange
        test_date = date(2026, 2, 11)

        # 모든 배치 파일 생성 (0-17)
        for i in range(18):
            batch_file = tmp_path / f"batch_{i}.json"
            batch_file.write_text('{"data": "test"}')

        # Mock config to use tmp_path
        with patch("workflows.scheduler.batch_utils.SchedulerConfig") as mock_config:
            mock_instance = Mock()
            mock_instance.daily_selection_dir = tmp_path
            mock_instance.batch_count = 18
            mock_config.return_value = mock_instance

            # Act
            result = get_incomplete_batches(test_date)

            # Assert
            assert result == []

    def test_returns_remaining_batches_when_partial_complete(self, tmp_path):
        """일부 완료 시 나머지 배치 반환"""
        # Arrange
        test_date = date(2026, 2, 11)
        completed_batches = [0, 1, 2, 5, 7]

        # 일부 배치 파일만 생성
        for i in completed_batches:
            batch_file = tmp_path / f"batch_{i}.json"
            batch_file.write_text('{"data": "test"}')

        # Mock config to use tmp_path
        with patch("workflows.scheduler.batch_utils.SchedulerConfig") as mock_config:
            mock_instance = Mock()
            mock_instance.daily_selection_dir = tmp_path
            mock_instance.batch_count = 18
            mock_config.return_value = mock_instance

            # Act
            result = get_incomplete_batches(test_date)

            # Assert
            expected = [i for i in range(18) if i not in completed_batches]
            assert result == expected


class TestGetBatchCompletionStatus:
    """get_batch_completion_status() 함수 테스트"""

    def test_returns_tuple_of_completed_and_incomplete(self, tmp_path):
        """완료/미완료 배치를 튜플로 반환"""
        # Arrange
        test_date = date(2026, 2, 11)
        completed_batches = [0, 1, 2, 5, 7]

        # 일부 배치 파일만 생성
        for i in completed_batches:
            batch_file = tmp_path / f"batch_{i}.json"
            batch_file.write_text('{"data": "test"}')

        # Mock config to use tmp_path
        with patch("workflows.scheduler.batch_utils.SchedulerConfig") as mock_config:
            mock_instance = Mock()
            mock_instance.daily_selection_dir = tmp_path
            mock_instance.batch_count = 18
            mock_config.return_value = mock_instance

            # Act
            completed, incomplete = get_batch_completion_status(test_date)

            # Assert
            assert completed == completed_batches
            expected_incomplete = [i for i in range(18) if i not in completed_batches]
            assert incomplete == expected_incomplete

    def test_completed_and_incomplete_are_mutually_exclusive(self, tmp_path):
        """완료/미완료 리스트가 상호 배타적"""
        # Arrange
        test_date = date(2026, 2, 11)
        completed_batches = [3, 8, 12]

        # 일부 배치 파일만 생성
        for i in completed_batches:
            batch_file = tmp_path / f"batch_{i}.json"
            batch_file.write_text('{"data": "test"}')

        # Mock config to use tmp_path
        with patch("workflows.scheduler.batch_utils.SchedulerConfig") as mock_config:
            mock_instance = Mock()
            mock_instance.daily_selection_dir = tmp_path
            mock_instance.batch_count = 18
            mock_config.return_value = mock_instance

            # Act
            completed, incomplete = get_batch_completion_status(test_date)

            # Assert
            # 완료 + 미완료 = 전체 배치
            assert len(completed) + len(incomplete) == 18
            # 겹치는 항목 없음
            assert set(completed).isdisjoint(set(incomplete))

    def test_covers_all_batches(self, tmp_path):
        """완료 + 미완료 = 전체 배치 개수"""
        # Arrange
        test_date = date(2026, 2, 11)

        # Mock config to use tmp_path
        with patch("workflows.scheduler.batch_utils.SchedulerConfig") as mock_config:
            mock_instance = Mock()
            mock_instance.daily_selection_dir = tmp_path
            mock_instance.batch_count = 18
            mock_config.return_value = mock_instance

            # Act
            completed, incomplete = get_batch_completion_status(test_date)

            # Assert
            assert set(completed) | set(incomplete) == set(range(18))


class TestEdgeCases:
    """경계값 및 엣지 케이스 테스트"""

    def test_batch_0_first_batch(self, tmp_path):
        """배치 0 (첫 번째 배치) 처리"""
        # Arrange
        batch_id = 0
        test_date = date(2026, 2, 11)

        batch_file = tmp_path / "batch_0.json"
        batch_file.write_text('{"data": "test"}')

        # Mock config to use tmp_path
        with patch("workflows.scheduler.batch_utils.SchedulerConfig") as mock_config:
            mock_instance = Mock()
            mock_instance.daily_selection_dir = tmp_path
            mock_config.return_value = mock_instance

            # Act
            result = is_batch_complete(batch_id, test_date)

            # Assert
            assert result is True

    def test_batch_17_last_batch(self, tmp_path):
        """배치 17 (마지막 배치) 처리"""
        # Arrange
        batch_id = 17
        test_date = date(2026, 2, 11)

        batch_file = tmp_path / "batch_17.json"
        batch_file.write_text('{"data": "test"}')

        # Mock config to use tmp_path
        with patch("workflows.scheduler.batch_utils.SchedulerConfig") as mock_config:
            mock_instance = Mock()
            mock_instance.daily_selection_dir = tmp_path
            mock_config.return_value = mock_instance

            # Act
            result = is_batch_complete(batch_id, test_date)

            # Assert
            assert result is True

    def test_date_in_past(self, tmp_path):
        """과거 날짜로 조회 가능"""
        # Arrange
        past_date = date(2026, 1, 1)

        # Mock config to use tmp_path
        with patch("workflows.scheduler.batch_utils.SchedulerConfig") as mock_config:
            mock_instance = Mock()
            mock_instance.daily_selection_dir = tmp_path
            mock_instance.batch_count = 18
            mock_config.return_value = mock_instance

            # Act
            completed = get_completed_batches(past_date)

            # Assert
            assert isinstance(completed, list)

    def test_date_in_future(self, tmp_path):
        """미래 날짜로 조회 가능"""
        # Arrange
        future_date = date(2027, 12, 31)

        # Mock config to use tmp_path
        with patch("workflows.scheduler.batch_utils.SchedulerConfig") as mock_config:
            mock_instance = Mock()
            mock_instance.daily_selection_dir = tmp_path
            mock_instance.batch_count = 18
            mock_config.return_value = mock_instance

            # Act
            completed = get_completed_batches(future_date)

            # Assert
            assert isinstance(completed, list)
