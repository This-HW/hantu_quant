---
name: agent-creator
description: Create Claude Code sub-agents with optimal configuration. Use when users ask to create a new agent, custom agent, specialized assistant, or want to configure task-specific AI workflows.
---

# Agent Creator

새로운 Claude Code 서브에이전트를 생성하고 최적화합니다.

## 생성 워크플로우

1. **요구사항 수집**
   - 에이전트의 목적
   - 사용 시점 (자동 위임 트리거)
   - 필요한 도구
   - 파일 수정 필요 여부

2. **설정 결정**
   - 모델 선택 (Opus/Sonnet/Haiku)
   - 권한 모드 선택
   - 도구 화이트리스트/블랙리스트

3. **파일 생성**
   - 위치: `.claude/agents/` (프로젝트) 또는 `~/.claude/agents/` (전역)
   - 파일명: `agent-name.md`

4. **검증**
   - frontmatter 형식 확인
   - 도구 이름 검증

## 모델 선택 가이드

| 작업 유형 | 권장 모델 | 이유 |
|----------|----------|------|
| 전략/분석/리뷰 | `opus` | 복잡한 추론 |
| 코드 구현/수정 | `sonnet` | 균형잡힌 성능 |
| 탐색/검증/단순작업 | `haiku` | 빠른 실행, 비용 효율 |

상세 가이드: [references/model-selection.md](references/model-selection.md)

## 권한 모드 선택

| 모드 | 용도 |
|------|------|
| `default` | 표준 권한 확인 |
| `acceptEdits` | 파일 편집 자동 허용 |
| `plan` | 읽기 전용 |

## 사용 가능한 도구

상세 목록: [references/available-tools.md](references/available-tools.md)

**읽기 전용**: Read, Grep, Glob, Bash(read-only commands)
**수정 가능**: Read, Write, Edit, Grep, Glob, Bash

## 출력 형식

```markdown
---
name: [소문자-하이픈]
description: [역할]. [자동 위임 트리거 조건].
tools: [도구 목록]
model: [sonnet|opus|haiku|inherit]
permissionMode: [default|acceptEdits|plan]
---

[시스템 프롬프트]
```

## 자동 위임 최적화

description에 포함하면 자동 위임 빈도 증가:
- "Use PROACTIVELY"
- "MUST BE USED when"
- "Use immediately after"

## 예제

```markdown
---
name: test-runner
description: Test execution specialist. Use PROACTIVELY after code changes to run tests.
tools: Read, Bash, Grep, Glob
model: haiku
---

You are a test automation expert.

When invoked:
1. Identify changed files
2. Run relevant tests
3. Report results with fix suggestions if failed
```
