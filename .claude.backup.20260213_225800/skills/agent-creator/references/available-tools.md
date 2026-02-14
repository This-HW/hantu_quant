# Available Tools Reference

## 기본 도구

| 도구 | 설명 | 권한 필요 |
|------|------|----------|
| `Read` | 파일 읽기 | No |
| `Write` | 파일 생성/덮어쓰기 | Yes |
| `Edit` | 파일 편집 | Yes |
| `Glob` | 패턴 기반 파일 찾기 | No |
| `Grep` | 텍스트 검색 | No |
| `Bash` | 셸 명령 실행 | Yes |
| `WebFetch` | URL 조회 | Yes |
| `WebSearch` | 웹 검색 | No |
| `Task` | 서브에이전트 호출 | No |
| `TodoWrite` | 작업 목록 관리 | No |
| `AskUserQuestion` | 사용자에게 질문 | No |

## 도구 조합 패턴

### 읽기 전용 (탐색/분석)
```yaml
tools: Read, Grep, Glob
```

### 읽기 + 제한된 Bash
```yaml
tools: Read, Grep, Glob, Bash
# Bash는 ls, git status, git log 등 읽기 명령만 사용
```

### 코드 수정
```yaml
tools: Read, Write, Edit, Grep, Glob, Bash
```

### 웹 조사
```yaml
tools: WebFetch, WebSearch, Read
```

### 전체 접근
```yaml
# tools 필드 생략 시 모든 도구 상속
```

## 도구 제한 방법

### 화이트리스트 (허용 도구 명시)
```yaml
tools: Read, Grep, Glob
```

### 블랙리스트 (특정 도구 거부)
```yaml
disallowedTools: Write, Edit, Task
```

## Bash 도구 세부 제어

settings.json의 permissions로 제어:
```json
{
  "permissions": {
    "allow": ["Bash(git:*)", "Bash(npm run:*)"],
    "deny": ["Bash(rm:*)", "Bash(sudo:*)"]
  }
}
```
