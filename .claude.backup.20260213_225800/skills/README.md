# 공통 스킬 목록

> 모든 프로젝트에서 사용 가능한 스킬 목록입니다.
> 슬래시 명령어 (`/skill-name`)로 호출합니다.

---

## 개발 스킬

| 스킬          | 명령어              | 설명                                                                        |
| ------------- | ------------------- | --------------------------------------------------------------------------- |
| **auto-dev**  | `/auto-dev [작업]`  | 자동화된 개발 파이프라인. 탐색 → 계획 → 구현 → 검증 → 리뷰 순으로 진행      |
| **plan-task** | `/plan-task [작업]` | 체계적인 작업 계획 수립. 규모 판단 → 요구사항 → 사용자 여정 → 비즈니스 로직 |
| **review**    | `/review [파일]`    | 코드 리뷰. 인자 없으면 git diff 기반                                        |
| **test**      | `/test [경로]`      | 테스트 실행 및 결과 분석                                                    |
| **debug**     | `/debug [에러]`     | 에러 분석 및 수정                                                           |

---

## 운영 스킬

| 스킬         | 명령어                  | 설명                                                     |
| ------------ | ----------------------- | -------------------------------------------------------- |
| **deploy**   | `/deploy [대상] [환경]` | 배포 파이프라인. 검증 → 배포 → 모니터링                  |
| **monitor**  | `/monitor [대상]`       | 시스템 모니터링. app, infra, db 또는 전체                |
| **incident** | `/incident [상황]`      | 인시던트 대응. 복구 최우선, 대응 → 복구 → 분석           |
| **infra**    | `/infra [작업]`         | 인프라 작업 파이프라인. 탐색 → 계획 → 구현 → 검증 → 적용 |

---

## 유틸리티 스킬

| 스킬              | 명령어                 | 설명                          |
| ----------------- | ---------------------- | ----------------------------- |
| **db-query**      | `/db-query`            | PostgreSQL MCP로 DB 쿼리 실행 |
| **web-research**  | `/web-research [주제]` | MCP 서버로 외부 정보 조사     |
| **agent-creator** | `/agent-creator`       | 새로운 서브에이전트 생성      |

---

## 사용 예시

### 새 기능 개발

```bash
# 계획 수립
/plan-task 사용자 프로필 페이지 추가

# 자동 개발 파이프라인
/auto-dev 사용자 프로필 페이지 구현
```

### 버그 수정

```bash
# 에러 디버깅
/debug TypeError: Cannot read property 'name' of undefined at Profile.tsx:42

# 테스트 실행
/test src/components/Profile
```

### 배포 및 운영

```bash
# 배포
/deploy app staging

# 모니터링
/monitor app

# 장애 대응
/incident API 응답시간 급증
```

### 리서치 및 DB

```bash
# 문서 조사
/web-research context7: Next.js 15 caching

# DB 쿼리
/db-query
```

---

## 스킬 vs 에이전트

| 구분           | 스킬                                  | 에이전트                       |
| -------------- | ------------------------------------- | ------------------------------ |
| 호출 방식      | `/skill-name`                         | Task tool 자동 위임            |
| 용도           | 사용자 직접 실행 워크플로우           | 특정 작업 전문가               |
| 오케스트레이션 | 스킬이 에이전트 호출                  | 에이전트 간 위임               |
| 예시           | `/auto-dev` → 여러 에이전트 순차 호출 | `implement-code` → 코드 구현만 |

---

## 스킬 추가하기

1. `skills/common/[skill-name]/SKILL.md` 생성
2. Frontmatter 필수 필드:
   - `name`: 스킬 이름
   - `description`: 설명 (자동 완성에 표시)
   - `argument-hint`: 인자 힌트 (선택)
   - `allowed-tools`: 허용 도구 (선택)

3. 본문에 실행 지침 작성

예시:

```yaml
---
name: my-skill
description: 새로운 스킬 설명
argument-hint: [인자 설명]
allowed-tools: Read, Write, Edit, Bash
---
# 스킬 실행 지침
...
```
