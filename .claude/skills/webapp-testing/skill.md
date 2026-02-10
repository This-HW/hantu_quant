---
name: webapp-testing
description: E2E 테스트 자동화. Playwright MCP를 사용하여 웹 애플리케이션을 테스트합니다.
model: sonnet
domain: common
disable-model-invocation: true
---

# Web Application Testing

> E2E 테스트 자동화 with Playwright MCP

Playwright MCP를 활용하여 웹 애플리케이션의 End-to-End 테스트를 자동화합니다.

---

## 사용법

### 기본 테스트

```
/webapp-testing https://example.com
/webapp-testing "로그인 플로우 테스트" https://app.example.com/login
```

### 테스트 시나리오

```
/webapp-testing "결제 플로우 전체 테스트" https://shop.example.com
```

---

## 워크플로우

### 1. 브라우저 초기화

Playwright MCP로 브라우저를 시작합니다:

- Chromium (기본)
- Firefox
- WebKit

### 2. 테스트 시나리오 실행

사용자 시나리오를 자동화:

- 페이지 이동
- 요소 클릭
- 폼 입력
- 스크린샷 캡처
- 결과 검증

### 3. 결과 보고

- 통과/실패 여부
- 스크린샷
- 에러 로그
- 성능 메트릭

---

## Playwright MCP 활용

Playwright MCP는 다음 기능을 제공합니다:

- **browser_navigate**: URL 이동
- **browser_snapshot**: 접근성 스냅샷 (DOM 구조)
- **browser_click**: 요소 클릭
- **browser_type**: 텍스트 입력
- **browser_take_screenshot**: 스크린샷
- **browser_evaluate**: JavaScript 실행
- **browser_console_messages**: 콘솔 로그 확인

---

## 예시: 로그인 테스트

```
1. browser_navigate → https://app.example.com/login
2. browser_snapshot → 로그인 폼 확인
3. browser_type → 이메일 입력
4. browser_type → 비밀번호 입력
5. browser_click → 로그인 버튼 클릭
6. browser_snapshot → 대시보드 확인
7. browser_take_screenshot → 결과 캡처
```

---

## 테스트 패턴

### Smoke Test (핵심 기능 확인)

- 홈페이지 로드
- 주요 링크 동작
- 로그인/로그아웃

### Regression Test (회귀 테스트)

- 이전 버그 재발 확인
- 주요 기능 정상 동작

### User Journey (사용자 여정)

- 회원가입 → 로그인 → 프로필 수정 → 로그아웃
- 상품 검색 → 장바구니 → 결제 → 주문 확인

---

## 출력 형식

### 테스트 결과

| 항목      | 결과          |
| --------- | ------------- |
| URL       | [테스트 대상] |
| 시나리오  | [테스트 내용] |
| 통과/실패 | ✅/❌         |
| 소요 시간 | [N초]         |

### 실패 상세

[실패한 단계 및 에러 메시지]

### 스크린샷

[캡처된 이미지 경로]

---

## 관련 도구

- **Playwright MCP**: 브라우저 자동화
- **write-ui-tests** 에이전트: UI 테스트 코드 작성
- **verify-code** 에이전트: 테스트 결과 검증

---

## 참고

- Playwright 공식 문서: https://playwright.dev
- MCP 서버 설정: .claude/rules/mcp-usage.md
