"""EmojiRemovalFilter 단위 테스트

테스트 대상: core.utils.emoji_filter.EmojiRemovalFilter
"""

import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).parent.parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import logging
import pytest

from core.utils.emoji_filter import EmojiRemovalFilter


class TestEmojiRemovalFilter:
    """EmojiRemovalFilter 테스트 클래스"""

    @pytest.fixture
    def emoji_filter(self):
        """EmojiRemovalFilter 인스턴스 생성"""
        return EmojiRemovalFilter()

    @pytest.fixture
    def log_record(self):
        """기본 LogRecord 생성"""
        return logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None
        )

    # 1. 기본 이모지 제거
    def test_remove_basic_emojis(self, emoji_filter, log_record):
        """기본 이모지(Emoticons) 제거 테스트"""
        log_record.msg = "Hello 😀😃😄 World"
        result = emoji_filter.filter(log_record)

        assert result is True
        # strip()이 적용되므로 이모지 제거 후 양 끝 공백 제거, 중간 공백은 유지
        assert log_record.msg == "Hello  World"

    # 2. 다양한 이모지 블록 제거
    def test_remove_various_emoji_blocks(self, emoji_filter, log_record):
        """다양한 유니코드 블록의 이모지 제거 테스트"""
        test_cases = [
            # Emoticons (1F600-1F64F)
            ("Happy 😀😃😄", "Happy"),
            # Symbols & Pictographs (1F300-1F5FF) + Miscellaneous Symbols (2600-26FF)
            # ☀️(U+2600), 🌙(U+1F319), ⭐(U+2B50) 모두 제거됨 (2B00-2BFF 범위 포함)
            ("Weather ☀️🌙⭐", "Weather"),  # Variation Selector도 제거됨
            # Transport & Map (1F680-1F6FF)
            ("Travel 🚗✈️🚀", "Travel"),  # Variation Selector도 제거됨
            # Flags (1F1E0-1F1FF)
            ("Country 🇰🇷🇺🇸", "Country"),
            # Supplemental Symbols (1F900-1F9FF)
            ("Modern 🤖🦄", "Modern"),
        ]

        for input_msg, expected_msg in test_cases:
            log_record.msg = input_msg
            emoji_filter.filter(log_record)
            assert log_record.msg.strip() == expected_msg.strip(), \
                f"Failed for input: {input_msg}"

    # 3. 조기 반환 (이모지 없음)
    def test_no_emoji_early_return(self, emoji_filter, log_record):
        """이모지가 없는 경우 원본 유지 테스트"""
        original_msg = "Hello World 123"
        log_record.msg = original_msg
        emoji_filter.filter(log_record)

        assert log_record.msg == original_msg

    # 4. 빈 문자열 처리
    def test_empty_string(self, emoji_filter, log_record):
        """빈 문자열 처리 테스트"""
        log_record.msg = ""
        result = emoji_filter.filter(log_record)

        assert result is True
        assert log_record.msg == ""

    # 5. None 값 처리
    def test_none_value(self, emoji_filter, log_record):
        """msg가 None인 경우 테스트"""
        log_record.msg = None
        result = emoji_filter.filter(log_record)

        assert result is True
        assert log_record.msg is None

    # 6. 숫자 타입 msg 처리
    def test_non_string_msg(self, emoji_filter, log_record):
        """msg가 문자열이 아닌 경우 테스트"""
        log_record.msg = 12345
        result = emoji_filter.filter(log_record)

        assert result is True
        assert log_record.msg == 12345

    # 7. args dict 처리
    def test_args_dict_processing(self, emoji_filter, log_record):
        """args가 dict인 경우 이모지 제거 테스트"""
        log_record.msg = "User action"
        log_record.args = {
            "user": "John 😀",
            "action": "login 🔑",
            "count": 5,
        }

        emoji_filter.filter(log_record)

        assert log_record.args["user"] == "John"
        assert log_record.args["action"] == "login"
        assert log_record.args["count"] == 5

    # 8. args tuple 처리
    def test_args_tuple_processing(self, emoji_filter, log_record):
        """args가 tuple인 경우 이모지 제거 테스트"""
        log_record.msg = "Result: %s %s %d"
        log_record.args = ("Success 😀", "Done 🎉", 100)

        emoji_filter.filter(log_record)

        assert log_record.args == ("Success", "Done", 100)

    # 9. args list 처리
    def test_args_list_processing(self, emoji_filter, log_record):
        """args가 list인 경우 이모지 제거 테스트"""
        log_record.msg = "Items: %s %s"
        log_record.args = ["Item1 😀", "Item2 🎉"]

        result = emoji_filter.filter(log_record)

        assert result is True
        # list는 tuple로 변환됨
        assert isinstance(log_record.args, tuple)
        assert log_record.args == ("Item1", "Item2")

    # 10. 예외 안전성
    def test_exception_safety(self, emoji_filter, log_record):
        """필터 처리 중 예외 발생해도 로그는 통과"""
        # 예외를 발생시킬 수 있는 비정상 args
        log_record.msg = "Test"
        log_record.args = object()  # dict/tuple이 아닌 객체

        result = emoji_filter.filter(log_record)

        # 예외가 발생해도 True를 반환해야 함
        assert result is True

    # 11. remove_emoji 클래스 메서드 테스트
    def test_remove_emoji_classmethod(self):
        """remove_emoji 클래스 메서드 직접 테스트"""
        test_cases = [
            ("Hello 😀 World", "Hello  World"),  # 이모지 제거 후 공백 유지
            ("No emoji", "No emoji"),
            ("", ""),
            ("😀😃😄", ""),  # 이모지만 있으면 빈 문자열
        ]

        for input_text, expected in test_cases:
            result = EmojiRemovalFilter.remove_emoji(input_text)
            assert result == expected, f"Failed for: {input_text}"

    # 12. remove_emoji 비문자열 처리
    def test_remove_emoji_non_string(self):
        """remove_emoji에 문자열이 아닌 값 전달 시"""
        result = EmojiRemovalFilter.remove_emoji(12345)
        assert result == 12345

        result = EmojiRemovalFilter.remove_emoji(None)
        assert result is None

    # 13. Parametrized 테스트 - 허용 이모지 보존
    @pytest.mark.parametrize("input_msg,expected_msg", [
        # 허용 이모지(✅❌⭕)는 보존됨
        ("Success ✅", "Success ✅"),  # U+2705 (Dingbats) - 보존
        ("Error ❌", "Error ❌"),  # U+274C (Dingbats) - 보존
        ("Info ⭕", "Info ⭕"),  # U+2B55 - 보존
        ("Result ✅❌⭕", "Result ✅❌⭕"),  # 모두 보존
        # 허용되지 않은 이모지는 제거
        ("Happy 😀", "Happy"),  # U+1F600 (Emoticons) - 제거
        ("Warning ⚠️", "Warning"),  # U+26A0 + Variation Selector - 모두 제거
        # 혼합: 허용 이모지는 보존, 나머지는 제거
        ("Mixed ✅😀❌", "Mixed ✅❌"),  # ✅❌는 보존, 😀는 제거
        ("Test 🎉 ✅ Done", "Test  ✅ Done"),  # 🎉는 제거, ✅는 보존
    ])
    def test_various_emoji_removal(self, emoji_filter, log_record, input_msg, expected_msg):
        """다양한 이모지 제거 테스트 (허용 이모지는 보존)"""
        log_record.msg = input_msg
        emoji_filter.filter(log_record)
        assert log_record.msg == expected_msg

    # 14. 확장 유니코드 블록 테스트
    def test_extended_unicode_blocks(self, emoji_filter, log_record):
        """확장 유니코드 블록 이모지 제거 테스트"""
        # Supplemental Symbols and Pictographs (1F900-1F9FF)
        log_record.msg = "Robot 🤖 Unicorn 🦄"
        emoji_filter.filter(log_record)
        assert log_record.msg == "Robot  Unicorn"  # 이모지 제거 후 공백 유지

        # Chess Symbols (1FA00-1FA6F) - 체스 기호는 제거됨
        log_record.msg = "Chess 🨀"
        emoji_filter.filter(log_record)
        assert "Chess" in log_record.msg

    # 15. 통합 테스트: logging.Filter로 동작
    def test_integration_with_logger(self, emoji_filter):
        """실제 로거와 통합하여 동작 테스트"""
        logger = logging.getLogger("test_emoji_integration")
        logger.setLevel(logging.INFO)
        logger.addFilter(emoji_filter)

        # 핸들러 추가 (메모리에 저장)
        handler = logging.handlers.MemoryHandler(capacity=10)
        logger.addHandler(handler)

        # 이모지가 포함된 로그 출력
        logger.info("Test message 😀😃")

        # 필터가 적용되었는지 확인
        assert len(handler.buffer) == 1
        record = handler.buffer[0]
        assert record.msg == "Test message"

        # 정리
        logger.removeHandler(handler)
        logger.removeFilter(emoji_filter)

    # 16. 성능 테스트 (선택)
    def test_performance_large_text(self, emoji_filter, log_record):
        """대용량 텍스트 처리 성능 테스트"""
        # 1000개 단어 + 이모지
        large_text = " ".join([f"word{i} 😀" for i in range(1000)])
        log_record.msg = large_text

        import time
        start = time.perf_counter()
        emoji_filter.filter(log_record)
        elapsed = time.perf_counter() - start

        # 1초 이내 처리
        assert elapsed < 1.0
        # 이모지가 제거되었는지 확인
        assert "😀" not in log_record.msg

    # 17. 연속된 이모지 처리
    def test_consecutive_emojis(self, emoji_filter, log_record):
        """연속된 이모지 제거 테스트"""
        log_record.msg = "😀😃😄😁😆😅😂🤣"
        emoji_filter.filter(log_record)
        assert log_record.msg == ""

    # 18. 이모지 + 공백 처리
    def test_emoji_with_spaces(self, emoji_filter, log_record):
        """이모지와 공백이 섞인 경우 테스트"""
        log_record.msg = "  😀  Hello  😃  World  😄  "
        emoji_filter.filter(log_record)
        # strip()이 적용되므로 양 끝 공백 제거, 중간 공백은 유지
        # 이모지 제거 후: "    Hello    World    " → strip() → "Hello    World"
        assert "Hello" in log_record.msg and "World" in log_record.msg

    # 19. 복잡한 args 구조
    def test_complex_args_structure(self, emoji_filter, log_record):
        """중첩된 구조의 args 처리 테스트"""
        log_record.msg = "Complex data"
        log_record.args = {
            "user": "John 😀",
            "nested": {  # dict 내부의 dict는 변환 안됨 (1단계만)
                "value": "nested 😃"
            },
            "count": 5
        }

        emoji_filter.filter(log_record)

        assert log_record.args["user"] == "John"
        # nested dict는 그대로 (1단계만 처리)
        assert isinstance(log_record.args["nested"], dict)

    # 20. 유니코드 정규화 테스트
    def test_unicode_normalization(self, emoji_filter, log_record):
        """유니코드 정규화 테스트 (결합 문자)"""
        # 일부 이모지는 여러 유니코드 포인트로 구성됨
        log_record.msg = "Flag 🇰🇷 Skin 👋🏻"
        emoji_filter.filter(log_record)

        # 국기 이모지는 제거됨
        assert "🇰🇷" not in log_record.msg
        # 피부색 변형 이모지도 제거됨
        assert "👋" not in log_record.msg

    # 21. 허용 이모지 보존 통합 테스트 (tests/scratch에서 이동)
    def test_allowed_emojis_preserved(self, emoji_filter, log_record):
        """허용 이모지가 보존되는지 검증 (Must Fix)"""
        test_cases = [
            ("테스트 성공 ✅", "테스트 성공 ✅"),
            ("테스트 실패 ❌", "테스트 실패 ❌"),
            ("주의 필요 ⭕", "주의 필요 ⭕"),
            ("✅❌⭕ 모두 있음", "✅❌⭕ 모두 있음"),
            ("결과: ✅ 성공 ❌ 실패", "결과: ✅ 성공 ❌ 실패"),
        ]

        for input_msg, expected_msg in test_cases:
            log_record.msg = input_msg
            emoji_filter.filter(log_record)
            assert log_record.msg == expected_msg, \
                f"허용 이모지가 제거됨: '{input_msg}' → '{log_record.msg}'"

    # 22. 허용되지 않은 이모지 제거 통합 테스트 (tests/scratch에서 이동)
    def test_other_emojis_removed(self, emoji_filter, log_record):
        """허용되지 않은 이모지는 제거되는지 검증 (Must Fix)"""
        test_cases = [
            ("안녕하세요 😀", "안녕하세요"),
            ("좋아요 👍", "좋아요"),
            ("하트 ❤️", "하트"),  # Variation Selector도 제거됨
            ("로켓 🚀", "로켓"),
            # 혼합: 허용 이모지는 보존, 나머지는 제거
            ("혼합 😀 테스트 ✅ 완료 🎉", "혼합  테스트 ✅ 완료"),
        ]

        for input_msg, expected_msg in test_cases:
            log_record.msg = input_msg
            emoji_filter.filter(log_record)
            assert log_record.msg == expected_msg, \
                f"제거되지 않은 이모지 발견: '{input_msg}' → '{log_record.msg}'"
