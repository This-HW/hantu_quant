# Deliberation Pattern: 3-Round 협의 프로세스

> 다관점 리뷰의 핵심 워크플로우

---

## 개요

Deliberation Pattern은 여러 전문가가 **독립적 의견 → 상호 검토 → 합의 도출** 순서로 협의하는 프로세스입니다.

**핵심 원칙:**

- Round 1: 독립성 (다른 의견에 영향받지 않음)
- Round 2: 상호작용 (다른 의견을 고려하여 재검토)
- Round 3: 합의 (충돌 해결 및 최종 의사결정)

---

## Round 0: Facilitation (사전 준비)

**목적:** 필요한 관점 식별 및 초점 영역 정의

**수행자:** Facilitator (Meta Agent)

**프로세스:**

```
1. 문서 읽기 및 분석
   ├─ 문서 유형 (기획/설계/API)
   ├─ 복잡도 (Small/Medium/Large)
   ├─ 주요 도메인 (인증, 결제, 데이터 등)
   └─ 리스크 레벨

2. 관점 선택
   ├─ 필수: Requirements, Technical (항상 포함)
   ├─ 조건부: 문서 내용에 따라 선택
   └─ 생략: 관련 없는 관점 제외

3. 초점 영역 정의
   ├─ Requirements: P0 모호함, 엣지 케이스
   ├─ Security: 인증/권한, 민감 데이터
   └─ ... (관점별 구체적 포커스)

4. Round 1 프롬프트 템플릿 생성
```

**출력:**

```json
{
  "perspectives": [
    {
      "name": "requirements",
      "agent": "clarify-requirements",
      "focus_areas": ["P0 모호함", "엣지 케이스"],
      "priority": "critical"
    }
  ]
}
```

---

## Round 1: 초기 의견 수집 (병렬)

**목적:** 각 관점의 독립적 의견 도출

**실행 방식:** 병렬 (동시 실행)

**프로세스:**

```
for perspective in perspectives:
    Task(
        subagent_type=perspective.agent,
        prompt=f"""
        다음 문서를 {perspective.name} 관점에서 리뷰:

        문서: {document}

        중점 영역:
        {perspective.focus_areas}

        형식:
        - Critical 이슈
        - Important 이슈
        - Nice-to-have 제안
        """
    )
```

**독립성 보장:**

- 다른 관점의 의견 미제공
- 순수하게 자신의 전문 영역만 검토
- 편향 방지

**수집 결과:**

```
Requirements: P0 모호함 3개 발견
Technical: 개발 3주 예상
Security: 감사 로그 필수
Business Logic: 적립률 5% 제안
Data/Schema: 2개 테이블 추가
```

---

## Synthesizer: Round 1 종합

**목적:** 의견 통합, 충돌/중복 식별

**프로세스:**

```
1. 의견 수집 및 구조화
   ├─ Critical/Important/Nice-to-have 분류
   ├─ 주요 이슈 추출
   └─ 제안사항 정리

2. 중복 제거
   ├─ 동일 이슈 통합 (예: "트랜잭션 무결성")
   └─ 그룹화 (관련 이슈 묶기)

3. 충돌 식별
   ├─ 관점 간 상충 의견 (예: 기획자 1주 vs 개발자 3주)
   ├─ 충돌 유형 분류 (우선순위/기술vs보안/UXvs보안)
   └─ 충돌 목록 작성

4. 우선순위 분류
   ├─ Critical (즉시 해결)
   ├─ Important (권장)
   └─ Nice-to-have (선택)
```

**출력:**

```markdown
## Round 1 종합

### Critical (2개)

1. P0 모호함: "사용자" 정의 불명확
2. 보안: 포인트 조작 방지 없음

### Important (3개)

...

### 충돌 (2개)

1. 개발 기간: 기획자 1주 vs 개발자 3주
2. Rate Limiting: 보안 Phase 1 vs 개발자 Phase 2
```

---

## Round 2: 상호 검토 (순차)

**목적:** Round 1 의견을 고려하여 재검토

**실행 방식:** 순차 (이전 의견 컨텍스트 포함)

**프로세스:**

```
for perspective in perspectives:
    Task(
        subagent_type=perspective.agent,
        prompt=f"""
        Round 1 결과를 고려하여 재검토:

        문서: {document}

        Round 1 종합:
        {round1_summary}

        당신의 Round 1 의견:
        {your_round1_opinion}

        다른 관점 의견:
        {other_perspectives}

        재검토 항목:
        1. Round 1 의견 유지/변경?
        2. 다른 관점 의견에 추가할 점?
        3. 충돌 해결 제안?
        """
    )
```

**상호작용:**

- 다른 관점 의견을 읽고 반응
- 자신의 관점에서 추가 이슈 식별
- 충돌 해결 제안

**예시:**

```
Technical (Round 2):
"보안 관점에서 감사 로그가 필수라고 했는데, 동의합니다.
다만 개발 기간이 2일 추가됩니다. 총 3주로 조정합니다."

Security (Round 2):
"개발자가 트랜잭션 설계를 SERIALIZABLE로 하겠다고 했는데,
이것만으로도 포인트 조작 1차 방어는 충분합니다.
Rate Limiting은 2차 방어이므로 Phase 2 연기 수용합니다."
```

---

## Round 3: 합의 도출

**목적:** 충돌 해결 및 최종 의사결정

**수행자:** Consensus-Builder + Impact-Analyzer

### 3-1. 충돌 분석 (Consensus-Builder)

```
for conflict in conflicts:
    1. 충돌 근본 원인 파악
       ├─ 정보 부족?
       ├─ 목표 불일치?
       └─ 제약 충돌?

    2. 트레이드오프 분석
       ├─ 옵션 A: 장단점, 리스크
       ├─ 옵션 B: 장단점, 리스크
       └─ 옵션 C (중간 지점)

    3. 합의 전략
       ├─ Win-Win 찾기 (우선)
       ├─ 조건부 합의 (차선)
       └─ 사용자 결정 (최후)
```

**예시:**

```
충돌: 개발 기간 (기획자 1주 vs 개발자 3주)

트레이드오프:
A) 1주 출시: 빠르지만 버그 위험 높음
B) 3주 출시: 품질 보장하지만 시장 지연
C) Phase 분할: MVP 2주 + 고급 기능 1주

합의안: C) Phase 분할
- 기획자 우려 해소: 2주면 시장 선점 가능
- 개발자 우려 해소: 핵심 기능 품질 보장
- 리스크 완화: MVP로 빠른 검증 후 개선
```

### 3-2. 영향도 분석 (Impact-Analyzer)

```
1. 변경 범위 식별
   ├─ 직접 영향: 변경될 파일/모듈
   ├─ 간접 영향: 의존하는 시스템
   └─ 숨겨진 영향: 성능, 리소스, 운영

2. 리스크 분류
   ├─ High Risk: 데이터 손실, 보안 취약점
   ├─ Medium Risk: 성능 저하, 기존 기능 영향
   └─ Low Risk: 독립 기능, 롤백 쉬움

3. 비용 추정
   ├─ 개발 비용: 설계 + 구현 + 리뷰 + 버그 수정
   ├─ 테스트 비용: 단위 + 통합 + E2E + 성능
   ├─ 인프라 비용: 서버, DB, 외부 API
   └─ 운영 비용: 배포, 모니터링, 문서화

4. 권장사항
   └─ 승인 / 조건부 승인 / 재검토
```

### 3-3. 최종 리포트 (Synthesizer)

```
Round 1 + Round 2 + 합의안 + 영향도 → 최종 문서

구조:
1. Executive Summary
2. Critical 이슈 (즉시 해결)
3. Important 이슈 (권장)
4. Nice-to-have (선택)
5. 합의 과정 (충돌 해결)
6. 영향도 분석
7. 다음 단계 (액션 아이템)
```

---

## 실행 시간

| Round       | 실행 방식 | 예상 시간   | 비고               |
| ----------- | --------- | ----------- | ------------------ |
| Round 0     | 단일      | 2-3분       | Facilitator        |
| Round 1     | 병렬      | 5-10분      | 관점 수에 따라     |
| 종합 1      | 단일      | 2-3분       | Synthesizer        |
| Round 2     | 순차      | 10-15분     | 관점 수 × 2분      |
| Round 3     | 단일      | 5분         | Consensus + Impact |
| 최종 리포트 | 단일      | 2-3분       | Synthesizer        |
| **총계**    | -         | **26-41분** | 보통 30분          |

---

## 성공 요소

### 1. 독립성 (Round 1)

- 다른 의견에 영향받지 않음
- 순수한 전문가 시각
- 편향 방지

### 2. 상호작용 (Round 2)

- 다른 관점 이해
- 자신의 의견 재검토
- 충돌 인식

### 3. 합의 (Round 3)

- 트레이드오프 명확화
- Win-Win 탐색
- 합리적 결정

---

## 실패 케이스 및 대응

### 케이스 1: 관점 간 소통 부족

**증상:** Round 2에서도 충돌 지속

**원인:** Round 1 의견이 불명확

**대응:** Synthesizer가 Round 1 종합 시 명확히 정리

### 케이스 2: 무한 논쟁

**증상:** Round 3에서도 합의 실패

**원인:** Hard Constraint 충돌

**대응:** 사용자에게 AskUserQuestion으로 위임

### 케이스 3: 시간 초과

**증상:** 30분 이상 소요

**원인:** 너무 많은 관점 또는 복잡한 문서

**대응:** 문서를 섹션별로 나누어 반복 리뷰
