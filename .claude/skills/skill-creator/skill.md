---
name: skill-creator
description: Claude Code 스킬 생성을 간소화합니다. 템플릿과 베스트 프랙티스를 자동 적용합니다.
model: sonnet
domain: common
allowed-tools: Write, Read, Glob
---

# Skill Creator

> Claude Code 스킬을 빠르고 정확하게 생성

베스트 프랙티스를 적용한 스킬을 자동 생성합니다.

---

## 사용법

### 신규 스킬 생성

```
/skill-creator "데이터 분석" data-analysis
/skill-creator "API 모니터링" api-monitor
/skill-creator "보안 검사" security-audit
```

---

## 생성 워크플로우

### 1. 요구사항 수집

다음 정보를 확인합니다:

- 스킬 이름 (kebab-case)
- 스킬 설명
- 사용 시점 (when to use)
- 필요한 도구
- 모델 (opus/sonnet/haiku)

### 2. Frontmatter 생성

```yaml
---
name: skill-name
description: What it does + when to use
model: sonnet | opus | haiku
allowed-tools: [tools]
disable-model-invocation: true # MCP 전용인 경우
---
```

### 3. 본문 작성

**구조:**

1. 개요
2. 사용법
3. 워크플로우
4. 예시
5. 관련 도구

---

## 스킬 템플릿

### 기본 템플릿

````markdown
---
name: skill-name
description: Brief description. Use when [scenario].
model: sonnet
allowed-tools: Read, Write, Bash
---

# Skill Title

> One-line tagline

Brief overview of what this skill does.

---

## 사용법

\```
/skill-name [arguments]
/skill-name "specific task"
\```

---

## 워크플로우

### 1. Step One

Description...

### 2. Step Two

Description...

### 3. Step Three

Description...

---

## 예시

### Example 1

\```
/skill-name example-input
\```

**Result:** Description of result

---

## 관련 도구

- **related-tool**: Description
- **another-tool**: Description
````

### MCP 전용 템플릿

````markdown
---
name: mcp-skill
description: Uses MCP server directly
model: sonnet
disable-model-invocation: true
---

# MCP Skill Title

> Direct MCP server integration

Uses [MCP_NAME] MCP server to [purpose].

---

## 사용법

\```
/mcp-skill [query]
\```

---

## MCP 활용

Available MCP functions:

- `function_1`: Description
- `function_2`: Description

---

## 워크플로우

1. MCP function call
2. Process results
3. Return formatted output
````

---

## 모델 선택 가이드

| 작업 유형           | 권장 모델 | 이유             |
| ------------------- | --------- | ---------------- |
| 전략/분석/리뷰      | `opus`    | 복잡한 추론 필요 |
| 코드 구현/수정      | `sonnet`  | 균형잡힌 성능    |
| 탐색/검증/빠른 작업 | `haiku`   | 빠른 실행        |

---

## 도구 선택 가이드

### 읽기 전용

```yaml
allowed-tools:
  - Read
  - Glob
  - Grep
  - Bash # read-only commands only
```

### 수정 가능

```yaml
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
```

### Task 에이전트 호출

```yaml
allowed-tools:
  - Task
  - Read
  - Glob
  - Grep
```

---

## 베스트 프랙티스

### Progressive Disclosure

- 메인 파일: < 500 lines
- 상세 내용: references/ 폴더
- 복잡한 로직: 별도 문서화

### 명확한 설명

```yaml
# ✅ 좋은 예
description: Analyze database performance. Use when queries are slow or database needs optimization.

# ❌ 나쁜 예
description: Database tool
```

### $ARGUMENTS 활용

```markdown
에러 정보: $ARGUMENTS
대상: $ARGUMENTS (없으면 전체)
```

---

## 검증 체크리스트

스킬 생성 후 확인:

- [ ] Frontmatter 완전함 (name, description, model)
- [ ] 설명이 명확함 (what + when to use)
- [ ] 사용법 예시 포함
- [ ] 워크플로우 단계별 설명
- [ ] 관련 도구/에이전트 명시
- [ ] 500 lines 이하 (또는 references 분리)
- [ ] $ARGUMENTS 활용 (필요시)

---

## 스킬 위치

| Tier    | 위치                      | 용도               |
| ------- | ------------------------- | ------------------ |
| Common  | skills/common/            | 모든 프로젝트 공통 |
| Domain  | skills/domain/[domain]/   | 도메인별 특화      |
| Project | skills/project/[project]/ | 프로젝트 전용      |

---

## 참고 문서

- 스킬 가이드: docs/guides/skill-authoring.md
- Anthropic 공식 표준: docs/research/anthropic-research-findings.md
- 기존 스킬 예시: skills/common/

---

## 다음 단계

1. ✅ 스킬 파일 생성
2. ⏳ 로컬 테스트
3. ⏳ 프로젝트에 배포
4. ⏳ 사용자 문서 작성
