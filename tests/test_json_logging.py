"""
JSON 구조화 로깅 테스트 (P2-2)

테스트 항목:
1. JSONFormatter JSON 출력
2. trace_id 기능
3. 구조화된 로거
4. 로그 로테이션 설정
"""

import pytest
import json
import logging
import tempfile
import os
from unittest.mock import MagicMock

from core.utils.log_utils import (
    JSONFormatter,
    StructuredLogger,
    TraceIdContext,
    get_trace_id,
    set_trace_id,
    clear_trace_id,
    setup_json_logging,
    get_structured_logger,
    get_logger,
)


class TestJSONFormatter:
    """JSONFormatter 테스트"""

    def test_basic_format(self):
        """기본 JSON 포맷"""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )

        result = formatter.format(record)
        data = json.loads(result)

        assert data['level'] == 'INFO'
        assert data['logger'] == 'test_logger'
        assert data['message'] == 'Test message'
        assert 'timestamp' in data

    def test_format_with_trace_id(self):
        """trace_id 포함 포맷"""
        formatter = JSONFormatter()

        with TraceIdContext("test123"):
            record = logging.LogRecord(
                name="test_logger",
                level=logging.INFO,
                pathname="test.py",
                lineno=10,
                msg="Test message",
                args=(),
                exc_info=None
            )

            result = formatter.format(record)
            data = json.loads(result)

            assert data['trace_id'] == 'test123'

    def test_format_with_exception(self):
        """예외 정보 포함"""
        formatter = JSONFormatter()

        try:
            raise ValueError("Test error")
        except ValueError:
            import sys
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test_logger",
            level=logging.ERROR,
            pathname="test.py",
            lineno=10,
            msg="Error occurred",
            args=(),
            exc_info=exc_info
        )

        result = formatter.format(record)
        data = json.loads(result)

        assert 'exception' in data
        assert 'ValueError' in data['exception']

    def test_korean_message(self):
        """한글 메시지 지원"""
        formatter = JSONFormatter(ensure_ascii=False)
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="한글 메시지 테스트",
            args=(),
            exc_info=None
        )

        result = formatter.format(record)
        data = json.loads(result)

        assert data['message'] == '한글 메시지 테스트'


class TestTraceId:
    """trace_id 기능 테스트"""

    def test_set_and_get_trace_id(self):
        """trace_id 설정 및 조회"""
        clear_trace_id()
        assert get_trace_id() == ''

        set_trace_id("abc123")
        assert get_trace_id() == "abc123"

        clear_trace_id()
        assert get_trace_id() == ''

    def test_auto_generate_trace_id(self):
        """자동 trace_id 생성"""
        clear_trace_id()

        trace_id = set_trace_id()

        assert len(trace_id) == 8
        assert trace_id == get_trace_id()

    def test_trace_id_context(self):
        """TraceIdContext 컨텍스트 관리자"""
        clear_trace_id()
        set_trace_id("outer")

        with TraceIdContext("inner") as trace_id:
            assert trace_id == "inner"
            assert get_trace_id() == "inner"

        # 컨텍스트 종료 후 원래 값 복원
        assert get_trace_id() == "outer"

    def test_nested_trace_id_context(self):
        """중첩 TraceIdContext"""
        clear_trace_id()

        with TraceIdContext("level1"):
            assert get_trace_id() == "level1"

            with TraceIdContext("level2"):
                assert get_trace_id() == "level2"

            assert get_trace_id() == "level1"

        assert get_trace_id() == ""


class TestStructuredLogger:
    """StructuredLogger 테스트"""

    def test_info_logging(self):
        """INFO 레벨 로깅"""
        mock_logger = MagicMock()
        structured = StructuredLogger(mock_logger)

        structured.info("Test message", user_id=123, action="login")

        mock_logger.log.assert_called_once()
        call_args = mock_logger.log.call_args
        assert call_args[0][0] == logging.INFO
        assert call_args[0][1] == "Test message"

    def test_error_logging(self):
        """ERROR 레벨 로깅"""
        mock_logger = MagicMock()
        structured = StructuredLogger(mock_logger)

        structured.error("Error occurred", error_code=500)

        mock_logger.log.assert_called_once()
        call_args = mock_logger.log.call_args
        assert call_args[0][0] == logging.ERROR


class TestSetupJsonLogging:
    """setup_json_logging 테스트"""

    def test_setup_creates_file_handler(self):
        """파일 핸들러 생성"""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")

            logger = setup_json_logging(log_file, add_console=False)

            # 핸들러가 추가되었는지 확인
            assert len(logger.handlers) >= 1

            # 로그 기록
            logger.info("Test message")

            # 파일에 기록되었는지 확인
            assert os.path.exists(log_file)

    def test_setup_with_console(self):
        """콘솔 핸들러 포함"""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")

            logger = setup_json_logging(log_file, add_console=True)

            # 파일 + 콘솔 = 2개 핸들러
            assert len(logger.handlers) >= 2

    def test_json_format_in_file(self):
        """파일에 JSON 형식 기록"""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")

            logger = setup_json_logging(log_file, add_console=False)
            logger.info("Test message for JSON")

            # 파일에서 로그 읽기
            with open(log_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # JSON 파싱 가능한지 확인
            data = json.loads(content.strip())
            assert data['message'] == 'Test message for JSON'
            assert data['level'] == 'INFO'


class TestGetStructuredLogger:
    """get_structured_logger 테스트"""

    def test_returns_structured_logger(self):
        """StructuredLogger 반환"""
        logger = get_structured_logger("test")

        assert isinstance(logger, StructuredLogger)


class TestIntegration:
    """통합 테스트"""

    def test_full_logging_flow(self):
        """전체 로깅 흐름"""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "app.log")

            # 로깅 설정
            setup_json_logging(log_file, add_console=False)

            # trace_id 설정
            with TraceIdContext("req-001"):
                logger = get_logger("myapp")
                logger.info("Request received")
                logger.info("Processing...")
                logger.info("Request completed")

            # 로그 확인
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            assert len(lines) == 3

            for line in lines:
                data = json.loads(line)
                assert data['trace_id'] == 'req-001'
                assert data['logger'] == 'myapp'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
