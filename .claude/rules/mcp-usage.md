# MCP 서버 활용 가이드

> MCP(Model Context Protocol) 서버를 상황에 맞게 활용하여 최신 정보와 전문 도구를 사용합니다.

---

## 설치된 MCP 서버 목록

### 1. Context7 (문서/라이브러리)

**용도:** 최신 라이브러리 문서 및 코드 예제 조회

```
사용 시점:
- 라이브러리 사용법이 필요할 때
- 최신 버전 API가 궁금할 때
- 공식 문서 기반 구현이 필요할 때
```

**사용 방법:**
```
"use context7 to show me [라이브러리] [버전] [기능]"
```

**예시:**
```
"use context7 to show me Next.js 15 App Router setup"
"use context7 for React 19 Server Components"
```

---

### 2. Magic MCP - 21st.dev (UI/UX)

**용도:** 자연어로 UI 컴포넌트 생성

```
사용 시점:
- 프론트엔드 UI 컴포넌트 구현 시
- 디자인 시스템 구축 시
- UX 패턴 참고가 필요할 때
- 애니메이션/인터랙션 구현 시
```

**사용 방법:**
```
"create a [컴포넌트] with [특징]"
```

**예시:**
```
"create a login form with email and password using shadcn/ui"
"create a responsive navbar with dark mode toggle"
```

---

### 3. Exa (AI 시맨틱 검색)

**용도:** AI 기반 의미 검색, 코드 검색, 연구 자료 검색

```
사용 시점:
- 정확한 기술 문서 검색이 필요할 때
- 코드 예제/구현 패턴 찾을 때
- 최신 기술 트렌드 조사 시
- WebSearch보다 정확한 결과가 필요할 때
```

**장점:**
- 시맨틱 검색 (의미 기반)
- 코드/문서 특화 검색
- 토큰 효율적 (필터링된 결과)

**예시:**
```
"use exa to search for Python FastAPI authentication best practices"
"use exa to find React Server Components implementation examples"
```

---

### 4. Tavily (리서치 특화 검색)

**용도:** 심층 리서치, 팩트체크, 종합 조사

```
사용 시점:
- 여러 소스를 종합한 리서치 필요 시
- 최신 뉴스/트렌드 조사 시
- 기술 비교 분석 시
- 팩트체크가 필요할 때
```

**장점:**
- 검색 결과 자동 요약
- 신뢰도 기반 소스 필터링
- 중복 제거

**예시:**
```
"use tavily to research AI coding assistant market trends 2026"
"use tavily to compare Next.js vs Remix vs Astro"
```

---

### 5. Playwright (브라우저 자동화)

**용도:** 웹 브라우저 자동화, E2E 테스트, 스크래핑

```
사용 시점:
- 동적 웹페이지 데이터 수집 시
- E2E 테스트 자동화
- 로그인 필요한 페이지 접근 시
- 스크린샷/PDF 생성 시
```

**장점:**
- JavaScript 렌더링 후 데이터 접근
- 인증이 필요한 페이지 처리
- 병렬 브라우저 실행

**예시:**
```
"use playwright to take screenshot of example.com"
"use playwright to test login flow on staging site"
```

---

### 6. Sequential Thinking (복잡한 추론)

**용도:** 단계별 사고, 복잡한 문제 분해

```
사용 시점:
- 복잡한 아키텍처 설계 시
- 다단계 문제 해결 시
- 논리적 분석이 필요할 때
- 의사결정 과정 명확화 시
```

**장점:**
- 체계적 문제 분해
- 각 단계 검증
- 추론 과정 투명화

**예시:**
```
"use sequential thinking to design authentication system"
"use sequential thinking to analyze performance bottleneck"
```

---

### 7. PostgreSQL (데이터베이스)

**용도:** PostgreSQL 데이터베이스 직접 쿼리

```
사용 시점:
- 데이터 분석/조회 시
- 스키마 탐색 시
- 쿼리 최적화 테스트 시
- 데이터 품질 검증 시
```

**현재 설정:**
- 연결: hantu_quant DB (SSH 터널 경유)
- 로컬 포트: localhost:15432

**⚠️ 사전 요구사항:**
```bash
# SSH 터널 실행 필요 (세션 시작 전)
ssh -i ~/.ssh/id_rsa -f -N -L 15432:localhost:5432 ubuntu@168.107.3.196
```

**예시:**
```
"show me all tables in the database"
"run EXPLAIN ANALYZE on this query: SELECT ..."
"what's the schema of the stocks table?"
```

---

## MCP 선택 가이드

### 작업별 권장 MCP

| 작업 유형 | 1순위 MCP | 2순위 MCP |
|----------|----------|----------|
| 라이브러리 문서 | **Context7** | Exa |
| UI 컴포넌트 생성 | **Magic** | Context7 |
| 기술 검색 | **Exa** | Tavily |
| 종합 리서치 | **Tavily** | Exa |
| 웹 스크래핑 | **Playwright** | - |
| 복잡한 설계 | **Sequential Thinking** | - |
| DB 분석 | **PostgreSQL** | - |

### MCP vs 기본 도구

| 상황 | MCP 사용 | 기본 도구 사용 |
|------|:--------:|:-------------:|
| 라이브러리 최신 문서 | Context7 ✅ | WebFetch ❌ |
| 단순 웹 검색 | - | WebSearch ✅ |
| 의미 기반 검색 | Exa ✅ | WebSearch ❌ |
| 정적 페이지 조회 | - | WebFetch ✅ |
| 동적 페이지 조회 | Playwright ✅ | WebFetch ❌ |
| DB 쿼리 | PostgreSQL ✅ | Bash(psql) ❌ |

---

## MCP 활용 원칙

### 1. 최신 정보 우선

```
❌ 기억에 의존한 구현
   "내가 알기로 React 18에서는..."

✅ MCP로 확인 후 구현
   "use context7 for React 19 공식 문서 확인"
```

### 2. 토큰 효율성 고려

```
MCP는 필터링된 결과를 반환하여 토큰을 절약합니다:

✅ Context7: 필요한 문서 섹션만 반환
✅ Exa: AI가 관련성 높은 결과만 필터링
✅ Tavily: 검색 결과 자동 요약
✅ PostgreSQL: 쿼리 결과만 반환 (전체 덤프 X)

❌ WebFetch로 전체 페이지 로드 → 토큰 낭비
```

### 3. 버전 명시

```
MCP 조회 시 버전을 명시하세요:

✅ "use context7 for Next.js 15 App Router"
✅ "use context7 for React 19 Suspense"
✅ "use context7 for TypeScript 5.x satisfies"

❌ "Next.js 사용법" (버전 불명확)
```

---

## 개발 워크플로우별 MCP 활용

### 프론트엔드 개발

```
1. 컴포넌트 생성
   └→ Magic MCP로 자연어 → UI 코드

2. 라이브러리 API 확인
   └→ Context7로 React/Next.js 문서 조회

3. 베스트 프랙티스 검색
   └→ Exa로 구현 패턴 검색

4. 구현 및 테스트
   └→ Playwright로 E2E 테스트
```

### 백엔드 개발

```
1. 프레임워크 문서 확인
   └→ Context7 (FastAPI, NestJS 등)

2. DB 스키마/데이터 확인
   └→ PostgreSQL MCP로 직접 조회

3. 쿼리 최적화
   └→ PostgreSQL MCP로 EXPLAIN ANALYZE

4. 외부 API 조사
   └→ Exa/Tavily로 문서 검색
```

### 데이터 분석

```
1. 테이블 구조 파악
   └→ PostgreSQL MCP로 스키마 조회

2. 데이터 품질 검증
   └→ PostgreSQL MCP로 검증 쿼리

3. 분석 쿼리 실행
   └→ PostgreSQL MCP로 직접 실행

4. 시각화 라이브러리 확인
   └→ Context7로 문서 조회
```

### 복잡한 설계

```
1. 문제 분해
   └→ Sequential Thinking으로 단계별 분석

2. 관련 패턴 조사
   └→ Exa로 아키텍처 패턴 검색

3. 참고 구현 확인
   └→ Tavily로 종합 리서치
```

---

## MCP 활용 체크리스트

### 구현 전

- [ ] Context7로 라이브러리 최신 문서 확인했는가?
- [ ] Magic MCP로 UI 패턴 참조했는가? (프론트엔드)
- [ ] PostgreSQL MCP로 DB 스키마 확인했는가? (백엔드)

### 구현 중

- [ ] 불확실한 API는 Context7로 재확인하고 있는가?
- [ ] 복잡한 로직은 Sequential Thinking 활용했는가?
- [ ] 외부 연동은 Exa/Tavily로 문서 검색했는가?

### 구현 후

- [ ] Playwright로 E2E 테스트 실행했는가? (웹)
- [ ] PostgreSQL MCP로 쿼리 성능 확인했는가? (DB)

---

## MCP 사전 요구사항

### PostgreSQL MCP (SSH 터널)

```bash
# 세션 시작 전 실행 필요
ssh -i ~/.ssh/id_rsa -f -N -L 15432:localhost:5432 ubuntu@168.107.3.196

# 터널 상태 확인
lsof -i:15432
```

### Playwright MCP

```bash
# 브라우저 설치 (최초 1회)
npx playwright install
```

---

## 관련 에이전트

| 상황 | 위임 대상 | 활용 MCP |
|------|----------|----------|
| 라이브러리 조사 | **research-external** | Exa, Tavily, Context7 |
| UI 컴포넌트 구현 | **implement-ui** | Magic, Context7 |
| DB 분석 | **analyze-data** | PostgreSQL |
| 쿼리 최적화 | **optimize-queries** | PostgreSQL |
| E2E 테스트 | **write-ui-tests** | Playwright |
| 복잡한 설계 | **plan-implementation** | Sequential Thinking |
