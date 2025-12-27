"""
부분 실패 허용 로직 테스트 (P0-2)

테스트 항목:
1. PartialResult 기본 기능
2. 성공률 계산
3. 최소 성공률 체크
4. 실패 항목 저장
5. process_with_partial_failure 함수
"""

import pytest
import os
import json
import tempfile
from datetime import datetime

from core.utils.partial_result import (
    PartialResult,
    PartialFailureHandler,
    save_failed_items,
    process_with_partial_failure
)


class TestPartialResult:
    """PartialResult 클래스 테스트"""

    def test_initial_state(self):
        """초기 상태 테스트"""
        result = PartialResult[str]()

        assert result.total_count == 0
        assert result.success_count == 0
        assert result.fail_count == 0
        assert result.success_rate == 0.0
        assert result.is_acceptable == False  # 0/0은 0.0 < 0.9

    def test_add_success(self):
        """성공 항목 추가 테스트"""
        result = PartialResult[str]()

        result.add_success("item1")
        result.add_success("item2")

        assert result.success_count == 2
        assert result.total_count == 2
        assert result.fail_count == 0
        assert result.success_rate == 1.0
        assert result.is_acceptable == True

    def test_add_failure(self):
        """실패 항목 추가 테스트"""
        result = PartialResult[str]()

        result.add_failure("item1", "에러 메시지1")
        result.add_failure("item2", "에러 메시지2")

        assert result.fail_count == 2
        assert result.total_count == 2
        assert result.success_count == 0
        assert result.success_rate == 0.0
        assert result.is_acceptable == False

    def test_mixed_results(self):
        """성공/실패 혼합 테스트"""
        result = PartialResult[str]()

        # 9개 성공, 1개 실패 = 90% 성공률
        for i in range(9):
            result.add_success(f"success_{i}")
        result.add_failure("fail_1", "실패 이유")

        assert result.total_count == 10
        assert result.success_count == 9
        assert result.fail_count == 1
        assert result.success_rate == 0.9
        assert result.is_acceptable == True  # 90% >= 90%

    def test_below_threshold(self):
        """성공률 미달 테스트"""
        result = PartialResult[str](min_success_rate=0.9)

        # 8개 성공, 2개 실패 = 80% 성공률
        for i in range(8):
            result.add_success(f"success_{i}")
        result.add_failure("fail_1", "실패 이유1")
        result.add_failure("fail_2", "실패 이유2")

        assert result.success_rate == 0.8
        assert result.is_acceptable == False  # 80% < 90%

    def test_custom_min_success_rate(self):
        """커스텀 최소 성공률 테스트"""
        result = PartialResult[str](min_success_rate=0.5)

        # 6개 성공, 4개 실패 = 60% 성공률
        for i in range(6):
            result.add_success(f"success_{i}")
        for i in range(4):
            result.add_failure(f"fail_{i}", "실패")

        assert result.success_rate == 0.6
        assert result.is_acceptable == True  # 60% >= 50%

    def test_get_summary(self):
        """결과 요약 테스트"""
        result = PartialResult[str](min_success_rate=0.9)

        result.add_success("success1")
        result.add_failure("fail1", "에러")

        summary = result.get_summary()

        assert summary["total_count"] == 2
        assert summary["success_count"] == 1
        assert summary["fail_count"] == 1
        assert summary["success_rate"] == 0.5
        assert summary["is_acceptable"] == False
        assert summary["min_success_rate"] == 0.9
        assert len(summary["failed_items"]) == 1

    def test_generic_type(self):
        """제네릭 타입 테스트"""
        # 문자열 타입
        str_result = PartialResult[str]()
        str_result.add_success("test")
        assert str_result.successful[0] == "test"

        # 딕셔너리 타입
        dict_result = PartialResult[dict]()
        dict_result.add_success({"key": "value"})
        assert dict_result.successful[0]["key"] == "value"

        # 정수 타입
        int_result = PartialResult[int]()
        int_result.add_success(42)
        assert int_result.successful[0] == 42


class TestSaveFailedItems:
    """실패 항목 저장 테스트"""

    def test_save_empty_list(self):
        """빈 리스트 저장 테스트"""
        result = save_failed_items([], "test_operation")
        assert result is None

    def test_save_failed_items(self):
        """실패 항목 저장 테스트"""
        with tempfile.TemporaryDirectory() as tmpdir:
            failed_items = [
                ("item1", "에러1"),
                ("item2", "에러2"),
            ]

            filepath = save_failed_items(
                failed_items,
                "test_operation",
                output_dir=tmpdir
            )

            assert filepath is not None
            assert os.path.exists(filepath)

            # 파일 내용 확인
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            assert data["operation_type"] == "test_operation"
            assert data["total_failures"] == 2
            assert len(data["failures"]) == 2
            assert data["failures"][0]["item_id"] == "item1"
            assert data["failures"][0]["error"] == "에러1"


class TestProcessWithPartialFailure:
    """process_with_partial_failure 함수 테스트"""

    def test_all_success(self):
        """모든 항목 성공 테스트"""
        items = [1, 2, 3, 4, 5]

        def processor(item):
            return item * 2

        def id_getter(item):
            return str(item)

        result = process_with_partial_failure(
            items=items,
            processor=processor,
            item_id_getter=id_getter,
            save_failures=False
        )

        assert result.success_count == 5
        assert result.fail_count == 0
        assert result.successful == [2, 4, 6, 8, 10]
        assert result.is_acceptable == True

    def test_some_failures(self):
        """일부 실패 테스트"""
        items = [1, 2, 0, 4, 5]

        def processor(item):
            if item == 0:
                raise ValueError("0으로 나눌 수 없음")
            return 10 / item

        def id_getter(item):
            return str(item)

        result = process_with_partial_failure(
            items=items,
            processor=processor,
            item_id_getter=id_getter,
            save_failures=False
        )

        assert result.success_count == 4
        assert result.fail_count == 1
        assert result.success_rate == 0.8
        assert result.is_acceptable == False  # 80% < 90%

    def test_all_failures(self):
        """모든 항목 실패 테스트"""
        items = ["a", "b", "c"]

        def processor(item):
            raise Exception("항상 실패")

        def id_getter(item):
            return item

        result = process_with_partial_failure(
            items=items,
            processor=processor,
            item_id_getter=id_getter,
            save_failures=False
        )

        assert result.success_count == 0
        assert result.fail_count == 3
        assert result.is_acceptable == False

    def test_custom_min_success_rate(self):
        """커스텀 최소 성공률 테스트"""
        items = [1, 2, 3, 4, 5]

        def processor(item):
            if item > 3:
                raise Exception("실패")
            return item

        def id_getter(item):
            return str(item)

        # 60% 성공 (3/5), 50% 기준이면 통과
        result = process_with_partial_failure(
            items=items,
            processor=processor,
            item_id_getter=id_getter,
            min_success_rate=0.5,
            save_failures=False
        )

        assert result.success_rate == 0.6
        assert result.is_acceptable == True


class TestPartialFailureHandler:
    """PartialFailureHandler 클래스 테스트"""

    def test_handler_process(self):
        """핸들러 처리 테스트"""
        handler = PartialFailureHandler(
            min_success_rate=0.8,
            save_failures=False
        )

        items = [1, 2, 3, 4, 5]

        result = handler.process(
            items=items,
            processor=lambda x: x * 2,
            item_id_getter=lambda x: str(x)
        )

        assert result.success_count == 5
        assert result.is_acceptable == True

    def test_should_continue(self):
        """계속 진행 여부 확인 테스트"""
        handler = PartialFailureHandler(min_success_rate=0.9)

        # 성공률 높은 경우
        result_good = PartialResult[str](min_success_rate=0.9)
        for i in range(10):
            result_good.add_success(str(i))
        assert handler.should_continue(result_good) == True

        # 성공률 낮은 경우
        result_bad = PartialResult[str](min_success_rate=0.9)
        for i in range(5):
            result_bad.add_success(str(i))
        for i in range(5):
            result_bad.add_failure(str(i + 5), "실패")
        assert handler.should_continue(result_bad) == False


class TestEdgeCases:
    """엣지 케이스 테스트"""

    def test_single_item_success(self):
        """단일 항목 성공 테스트"""
        result = PartialResult[str]()
        result.add_success("only_one")

        assert result.success_rate == 1.0
        assert result.is_acceptable == True

    def test_single_item_failure(self):
        """단일 항목 실패 테스트"""
        result = PartialResult[str]()
        result.add_failure("only_one", "실패")

        assert result.success_rate == 0.0
        assert result.is_acceptable == False

    def test_exact_threshold(self):
        """정확히 임계값에서 테스트"""
        result = PartialResult[str](min_success_rate=0.9)

        # 정확히 90%
        for i in range(9):
            result.add_success(str(i))
        result.add_failure("fail", "실패")

        assert result.success_rate == 0.9
        assert result.is_acceptable == True  # >= 이므로 통과

    def test_large_scale(self):
        """대규모 데이터 테스트"""
        result = PartialResult[int]()

        # 10000개 중 9500개 성공 = 95%
        for i in range(9500):
            result.add_success(i)
        for i in range(500):
            result.add_failure(str(i), "실패")

        assert result.total_count == 10000
        assert result.success_rate == 0.95
        assert result.is_acceptable == True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
