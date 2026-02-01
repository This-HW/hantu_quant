"""이모지 제거 필터

로그 메시지에서 이모지를 제거하여 JSON 로깅 시스템과의 호환성을 보장합니다.
"""

import logging
import re

# 허용된 이모지 (로그에서 유지할 이모지)
ALLOWED_EMOJIS = frozenset(['✅', '❌', '⭕'])


class EmojiRemovalFilter(logging.Filter):
    """로그 메시지에서 이모지를 제거하는 필터

    JSON 로깅 시스템에서 이모지로 인한 인코딩 문제를 방지합니다.
    """

    # 이모지 유니코드 범위 (확장)
    EMOJI_PATTERN = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # Emoticons
        "\U0001F300-\U0001F5FF"  # Symbols & Pictographs
        "\U0001F680-\U0001F6FF"  # Transport & Map
        "\U0001F1E0-\U0001F1FF"  # Flags
        "\U00002600-\U000026FF"  # Miscellaneous Symbols
        "\U00002700-\U000027BF"  # Dingbats
        "\U0001F900-\U0001F9FF"  # Supplemental Symbols
        "\U0001FA00-\U0001FA6F"  # Chess Symbols
        "\U0001F0A0-\U0001F0FF"  # Playing Cards
        "\U0001F100-\U0001F1FF"  # Enclosed Alphanumeric Supplement
        "\U0001F650-\U0001F67F"  # Ornamental Dingbats
        "\U00002300-\U000023FF"  # Miscellaneous Technical
        "\U0001F780-\U0001F7FF"  # Geometric Shapes Extended
        "\U00002B00-\U00002BFF"  # Miscellaneous Symbols and Arrows
        "\uFE00-\uFE0F"          # Variation Selectors
        "]+",
        flags=re.UNICODE
    )

    def filter(self, record: logging.LogRecord) -> bool:
        """로그 레코드에서 이모지 제거

        Args:
            record: 로그 레코드

        Returns:
            True (항상 로그 통과)
        """
        try:
            # 메시지 이모지 제거
            if isinstance(record.msg, str):
                record.msg = self.remove_emoji(record.msg)

            # args 처리
            if record.args:
                if isinstance(record.args, dict):
                    record.args = {
                        k: self.remove_emoji(v) if isinstance(v, str) else v
                        for k, v in record.args.items()
                    }
                elif isinstance(record.args, (list, tuple)):
                    record.args = tuple(
                        self.remove_emoji(arg) if isinstance(arg, str) else arg
                        for arg in record.args
                    )

            return True

        except Exception:
            # 필터 에러 시에도 로그는 통과시킴
            return True

    @classmethod
    def remove_emoji(cls, text: str) -> str:
        """텍스트에서 이모지 제거 (허용된 이모지 제외)

        허용된 이모지(✅❌⭕)는 유지하고 나머지만 제거합니다.

        Args:
            text: 원본 텍스트

        Returns:
            이모지가 제거된 텍스트 (허용 이모지는 유지)
        """
        # 타입 체크 (조기 반환)
        if not isinstance(text, str):
            return text

        # 빈 문자열 체크 (조기 반환)
        if not text:
            return text

        # 이모지가 없으면 바로 반환 (성능 최적화)
        if not cls.EMOJI_PATTERN.search(text):
            return text

        # 허용 이모지 임시 치환
        placeholders = {}
        temp_text = text
        for i, emoji in enumerate(ALLOWED_EMOJIS):
            if emoji in temp_text:
                placeholder = f"__EMOJI_{i}__"
                placeholders[placeholder] = emoji
                temp_text = temp_text.replace(emoji, placeholder)

        # 나머지 이모지 제거
        cleaned_text = cls.EMOJI_PATTERN.sub('', temp_text).strip()

        # 허용 이모지 복원
        for placeholder, emoji in placeholders.items():
            cleaned_text = cleaned_text.replace(placeholder, emoji)

        return cleaned_text
