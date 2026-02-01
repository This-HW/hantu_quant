---
name: doc-coauthoring
description: 문서 협업. 문서 작성, 리뷰, 업데이트를 자동화합니다.
model: opus
allowed-tools: Read, Write, Edit, Glob, Grep
---

# Document Co-authoring

> AI 기반 문서 작성 및 협업

문서의 작성, 리뷰, 업데이트를 자동화하여 일관성 있는 고품질 문서를 유지합니다.

---

## 사용법

### 신규 문서 작성

```
/doc-coauthoring "API 문서 작성" docs/api/README.md
/doc-coauthoring "사용자 가이드" docs/user-guide.md
```

### 기존 문서 업데이트

```
/doc-coauthoring "업데이트" docs/architecture/design.md
/doc-coauthoring "리뷰 및 개선" README.md
```

---

## 문서 유형별 워크플로우

### 1. API 문서

**구조:**

- 개요 (Overview)
- 인증 (Authentication)
- 엔드포인트 (Endpoints)
  - 요청/응답 예시
  - 에러 코드
- 사용 예시 (Examples)

**생성 프로세스:**

1. 코드에서 API 정의 추출 (Glob + Read)
2. OpenAPI/Swagger 스펙 읽기 (있으면)
3. 표준 템플릿 적용
4. 예시 코드 생성

### 2. 아키텍처 문서

**구조:**

- 시스템 개요
- 구성 요소 (Components)
- 데이터 플로우
- 기술 스택
- 의사결정 기록 (ADR)

**생성 프로세스:**

1. 프로젝트 구조 분석 (Glob)
2. 주요 파일 읽기 (Read)
3. 다이어그램 생성 (Mermaid)
4. 의사결정 맥락 추가

### 3. 사용자 가이드

**구조:**

- 시작하기 (Getting Started)
- 주요 기능 (Features)
- 튜토리얼 (Tutorials)
- FAQ
- 트러블슈팅 (Troubleshooting)

**생성 프로세스:**

1. 사용자 여정 파악
2. 스크린샷 위치 표시
3. 단계별 가이드 작성
4. 일반적인 문제 정리

### 4. README

**구조:**

- 프로젝트 설명
- 기능 (Features)
- 설치 (Installation)
- 사용법 (Usage)
- 기여 가이드 (Contributing)
- 라이센스 (License)

**생성 프로세스:**

1. 프로젝트 메타데이터 추출
2. 주요 기능 식별
3. 설치 단계 자동 감지
4. 배지 (Badges) 추가

---

## 문서 품질 체크

### 자동 검증

- [ ] **구조**: 표준 헤딩 구조 (H1 → H2 → H3)
- [ ] **링크**: 깨진 링크 없음
- [ ] **코드 블록**: 언어 지정 (`python, `bash)
- [ ] **일관성**: 용어 통일 (API vs api, Node.js vs nodejs)
- [ ] **완전성**: 필수 섹션 포함

### 스타일 가이드

```markdown
# 제목은 문장형 (Sentence case)

## 부제목도 문장형

- 리스트는 일관된 형식
  - 들여쓰기 유지
  - 마침표 규칙 통일

**굵게**: 중요 용어
`코드`: 명령어, 파일명, 함수명

> 인용구: 주의사항, 팁
```

---

## 문서 리뷰 프로세스

### 1. 구조 리뷰

- 논리적 흐름 확인
- 섹션 순서 검증
- 중복 제거

### 2. 내용 리뷰

- 기술적 정확성
- 예시 코드 동작 확인
- 스크린샷 최신화

### 3. 언어 리뷰

- 문법 및 맞춤법
- 일관된 톤 & 보이스
- 전문 용어 정확성

### 4. 형식 리뷰

- Markdown 문법 확인
- 링크 검증
- 코드 블록 형식

---

## 자동 업데이트 트리거

다음 변경 시 관련 문서 자동 업데이트:

| 변경                     | 영향받는 문서         |
| ------------------------ | --------------------- |
| API 엔드포인트 추가/변경 | API 문서, README      |
| 새 기능 추가             | 사용자 가이드, README |
| 의존성 변경              | README (Installation) |
| 아키텍처 변경            | 아키텍처 문서, ADR    |

---

## 템플릿

### API 엔드포인트

````markdown
## POST /api/users

Creates a new user.

### Request

\```json
{
"email": "user@example.com",
"name": "John Doe"
}
\```

### Response

**Success (200 OK)**

\```json
{
"id": "usr_123",
"email": "user@example.com",
"name": "John Doe",
"created_at": "2026-01-30T10:00:00Z"
}
\```

**Error (400 Bad Request)**

\```json
{
"error": "INVALID_EMAIL",
"message": "Email format is invalid"
}
\```

### Example

\```bash
curl -X POST https://api.example.com/api/users \
 -H "Content-Type: application/json" \
 -d '{"email":"user@example.com","name":"John Doe"}'
\```
````

### 의사결정 기록 (ADR)

```markdown
# ADR-001: 데이터베이스 선택

**날짜**: 2026-01-30
**상태**: Accepted

## 컨텍스트

우리는 사용자 데이터를 저장할 데이터베이스가 필요합니다.

## 고려한 옵션

1. **PostgreSQL** - 관계형 DB, ACID 보장
2. **MongoDB** - NoSQL, 유연한 스키마
3. **SQLite** - 경량, 파일 기반

## 결정

PostgreSQL을 선택합니다.

## 근거

- 트랜잭션 무결성 필요
- 복잡한 쿼리 지원
- 팀 경험 풍부

## 결과

- 안정적인 데이터 관리
- 학습 곡선 최소화
- 확장성 확보
```

---

## 출력 형식

### 작성 완료 시

```
## 문서 작성 완료

### 생성된 문서
- [경로]: [문서 제목]

### 포함된 섹션
- [섹션 1]
- [섹션 2]
- [섹션 3]

### 다음 단계
- [ ] 스크린샷 추가 (필요시)
- [ ] 리뷰 요청
- [ ] 버전 관리 커밋
```

### 리뷰 완료 시

```
## 문서 리뷰 결과

### 수정 사항
- [개선 1]: [설명]
- [개선 2]: [설명]

### 권장 사항
- [제안 1]
- [제안 2]

### 품질 점수
- 구조: ✅
- 내용: ✅
- 언어: ⚠️ (경미한 수정 필요)
- 형식: ✅
```

---

## 관련 도구

- **sync-docs** 에이전트: 문서 자동 동기화
- **review-code** 에이전트: 기술 문서 리뷰
- **Glob/Grep**: 프로젝트 구조 분석

---

## 참고

- Markdown 가이드: https://www.markdownguide.org
- Google Developer Documentation Style Guide
- Write the Docs: https://www.writethedocs.org

---

## 다음 단계

1. ✅ 문서 작성/업데이트
2. ⏳ 팀 리뷰
3. ⏳ 피드백 반영
4. ⏳ 버전 관리 시스템에 커밋
