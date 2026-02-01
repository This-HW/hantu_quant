---
name: web-research
description: Research external information using MCP servers. Use when users need to find documentation, compare technologies, or research best practices.
model: sonnet
disable-model-invocation: true
---

# Web Research

MCP 서버를 활용하여 외부 정보를 조사합니다.

## 사용 가능한 MCP

### 1. Context7 - 라이브러리 문서

공식 문서 기반 정확한 API 정보:

```
/web-research context7: React 19 Server Components
/web-research context7: Next.js 15 App Router
/web-research context7: FastAPI authentication
```

### 2. Exa - AI 시맨틱 검색

코드 예제 및 구현 패턴:

```
/web-research exa: Python async best practices
/web-research exa: TypeScript type guards examples
/web-research exa: React performance optimization
```

### 3. Tavily - 종합 리서치

기술 비교, 트렌드 조사:

```
/web-research tavily: Next.js vs Remix comparison 2026
/web-research tavily: AI coding assistant market trends
/web-research tavily: microservices vs monolith decision
```

## 사용법

### 라이브러리 조사

```
/web-research [라이브러리명] [버전] [기능]
```

### 기술 비교

```
/web-research compare [A] vs [B]
```

### 베스트 프랙티스

```
/web-research best practices for [주제]
```

## 워크플로우

1. **MCP 선택**
   - 라이브러리 문서 → Context7
   - 코드 예제 → Exa
   - 비교/트렌드 → Tavily

2. **조사 실행**
   - MCP로 정보 수집
   - 복수 소스 교차 검증
   - 버전 호환성 확인

3. **결과 정리**
   - 핵심 내용 요약
   - 코드 예제 제공
   - 출처 명시

## MCP 선택 가이드

| 작업            | 1순위    | 2순위    |
| --------------- | -------- | -------- |
| 라이브러리 문서 | Context7 | Exa      |
| 코드 예제       | Exa      | Context7 |
| 기술 비교       | Tavily   | Exa      |
| 트렌드 조사     | Tavily   | -        |
| 에러 해결       | Exa      | Tavily   |

## 관련 에이전트

- **research-external**: 외부 정보 조사 전문가
- **plan-implementation**: 조사 결과 기반 구현 계획
