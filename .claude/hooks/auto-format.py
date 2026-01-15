#!/usr/bin/env python3
"""
PostToolUse Hook: 파일 저장 후 자동 포맷팅

Edit 또는 Write 도구 사용 후 파일 타입에 따라 자동 포맷팅을 실행합니다.

사용법:
  settings.json에서 PostToolUse hook으로 등록

입력:
  stdin으로 JSON 형식의 tool 실행 정보를 받습니다.
  {
    "tool_name": "Edit",
    "tool_input": {
      "file_path": "/path/to/file.ts"
    }
  }
"""

import json
import sys
import subprocess
import os
from pathlib import Path


def get_formatter(file_path: str) -> tuple[list[str], str] | None:
    """파일 확장자에 따른 포맷터 반환"""
    ext = Path(file_path).suffix.lower()

    formatters = {
        # JavaScript/TypeScript
        '.js': (['npx', 'prettier', '--write'], 'Prettier'),
        '.jsx': (['npx', 'prettier', '--write'], 'Prettier'),
        '.ts': (['npx', 'prettier', '--write'], 'Prettier'),
        '.tsx': (['npx', 'prettier', '--write'], 'Prettier'),
        '.json': (['npx', 'prettier', '--write'], 'Prettier'),
        '.md': (['npx', 'prettier', '--write'], 'Prettier'),
        '.yaml': (['npx', 'prettier', '--write'], 'Prettier'),
        '.yml': (['npx', 'prettier', '--write'], 'Prettier'),

        # Python
        '.py': (['black', '-q'], 'Black'),

        # Go
        '.go': (['gofmt', '-w'], 'gofmt'),

        # Rust
        '.rs': (['rustfmt'], 'rustfmt'),
    }

    return formatters.get(ext)


def format_file(file_path: str) -> bool:
    """파일 포맷팅 실행"""
    if not os.path.exists(file_path):
        return False

    formatter_info = get_formatter(file_path)
    if not formatter_info:
        return True  # 지원하지 않는 파일 타입은 무시

    command, name = formatter_info

    try:
        result = subprocess.run(
            command + [file_path],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            print(f"✓ Formatted with {name}: {file_path}")
            return True
        else:
            # 포맷터가 없어도 에러로 처리하지 않음
            if "not found" in result.stderr.lower() or "command not found" in result.stderr.lower():
                return True
            print(f"⚠ Format warning: {result.stderr}", file=sys.stderr)
            return True  # 포맷 실패해도 진행

    except FileNotFoundError:
        # 포맷터가 설치되지 않은 경우 무시
        return True
    except subprocess.TimeoutExpired:
        print(f"⚠ Format timeout: {file_path}", file=sys.stderr)
        return True
    except Exception as e:
        print(f"⚠ Format error: {e}", file=sys.stderr)
        return True


def main():
    try:
        # stdin에서 JSON 입력 읽기
        input_data = json.load(sys.stdin)

        tool_name = input_data.get('tool_name', '')
        tool_input = input_data.get('tool_input', {})

        # Edit 또는 Write 도구인 경우만 처리
        if tool_name not in ('Edit', 'Write'):
            sys.exit(0)

        file_path = tool_input.get('file_path', '')
        if not file_path:
            sys.exit(0)

        # 포맷팅 실행
        format_file(file_path)
        sys.exit(0)

    except json.JSONDecodeError:
        # JSON 파싱 실패 시 무시
        sys.exit(0)
    except Exception as e:
        print(f"Hook error: {e}", file=sys.stderr)
        sys.exit(0)  # 에러가 나도 작업 중단하지 않음


if __name__ == '__main__':
    main()
