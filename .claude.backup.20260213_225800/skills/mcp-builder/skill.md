---
name: mcp-builder
description: MCP 서버 개발. Model Context Protocol 서버를 생성하고 설정합니다.
model: sonnet
domain: common
allowed-tools: Write, Read, Bash, Glob
---

# MCP Server Builder

> Model Context Protocol 서버 개발 및 구성

MCP 서버를 생성하고 Claude Code에 통합합니다.

---

## 사용법

### 신규 MCP 서버 생성

```
/mcp-builder "파일 시스템 접근" filesystem
/mcp-builder "데이터베이스 조회" database-query
/mcp-builder "API 통합" external-api
```

### 기존 MCP 서버 설정

```
/mcp-builder setup postgres
/mcp-builder configure playwright
```

---

## MCP 서버 유형

### 1. Tools 서버

외부 도구 및 API 접근:

- 데이터베이스 쿼리
- 파일 시스템 조작
- 외부 API 호출
- 시스템 명령 실행

### 2. Resources 서버

정적 리소스 제공:

- 문서 검색
- 설정 파일 읽기
- 템플릿 제공

### 3. Prompts 서버

사전 정의된 프롬프트:

- 재사용 가능한 질의
- 템플릿 프롬프트

---

## 개발 워크플로우

### 1. 프로젝트 초기화

```bash
# Python MCP 서버
mkdir mcp-server-myproject
cd mcp-server-myproject
python -m venv venv
source venv/bin/activate
pip install mcp
```

### 2. 서버 구조 생성

```
mcp-server-myproject/
├── src/
│   ├── __init__.py
│   └── server.py           # MCP 서버 구현
├── pyproject.toml          # 의존성
└── README.md               # 사용법
```

### 3. Tools 정의

```python
from mcp import Server, Tool

server = Server("myproject-server")

@server.tool()
async def my_tool(arg1: str, arg2: int) -> str:
    """도구 설명"""
    # 구현
    return result
```

### 4. 서버 실행

```python
if __name__ == "__main__":
    server.run()
```

---

## Claude Code 통합

### 1. MCP 설정 파일 수정

`~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "myproject": {
      "command": "python",
      "args": ["-m", "mcp_server_myproject"],
      "env": {
        "API_KEY": "your-key"
      }
    }
  }
}
```

### 2. 서버 시작

```bash
claude mcp list           # MCP 서버 목록 확인
claude mcp restart        # 서버 재시작
```

### 3. 테스트

```
/mcp-test myproject
```

---

## 템플릿

### Python MCP Tools 서버

```python
from mcp import Server, Tool
from typing import Any

server = Server("example-server")

@server.tool()
async def example_tool(
    param1: str,
    param2: int = 10
) -> dict[str, Any]:
    """
    Example tool description.

    Args:
        param1: First parameter
        param2: Second parameter (default: 10)

    Returns:
        Result dictionary
    """
    return {
        "result": f"Processed {param1} with {param2}",
        "status": "success"
    }

if __name__ == "__main__":
    server.run()
```

### Python MCP Resources 서버

```python
from mcp import Server, Resource

server = Server("docs-server")

@server.resource("docs://guide")
async def get_guide() -> str:
    """Return user guide"""
    return "User guide content..."

@server.resource("docs://api")
async def get_api_docs() -> str:
    """Return API documentation"""
    return "API documentation..."

if __name__ == "__main__":
    server.run()
```

---

## 베스트 프랙티스

### 에러 처리

```python
@server.tool()
async def safe_tool(param: str) -> dict:
    try:
        result = await risky_operation(param)
        return {"result": result, "error": None}
    except Exception as e:
        return {"result": None, "error": str(e)}
```

### 로깅

```python
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@server.tool()
async def logged_tool(param: str) -> str:
    logger.info(f"Tool called with param: {param}")
    result = process(param)
    logger.info(f"Tool result: {result}")
    return result
```

### 환경 변수

```python
import os

API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise ValueError("API_KEY environment variable required")
```

---

## 디버깅

### 서버 로그 확인

```bash
# Claude Code 로그
tail -f ~/.claude/logs/mcp/*.log

# 서버 직접 실행 (디버그 모드)
python -m mcp_server_myproject --debug
```

### 연결 테스트

```bash
# MCP 서버 상태 확인
claude mcp status myproject

# 수동 테스트
echo '{"jsonrpc":"2.0","method":"tools/list","id":1}' | python -m mcp_server_myproject
```

---

## 관련 리소스

- MCP 공식 문서: https://modelcontextprotocol.io
- Python MCP SDK: https://github.com/anthropics/python-mcp
- TypeScript MCP SDK: https://github.com/anthropics/typescript-mcp
- MCP 서버 예제: https://github.com/anthropics/mcp-servers

---

## 다음 단계

1. ✅ MCP 서버 생성
2. ✅ Claude Code에 등록
3. ⏳ 스킬에서 MCP 서버 활용
4. ⏳ 프로덕션 배포
