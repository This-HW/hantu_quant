# SSOT (Single Source of Truth) 원칙

> 모든 정보는 단일 출처에서 관리됩니다. 중복은 불일치를 만듭니다.

---

## 핵심 원칙

### 1. 단일 출처 원칙

```
✅ 올바른 예:
- 에러 타입 정의 → errors/types.ts 한 곳에서만
- API 엔드포인트 → api/endpoints.ts 한 곳에서만
- 환경 변수 → .env + config/env.ts 에서만

❌ 잘못된 예:
- 같은 상수를 여러 파일에 중복 정의
- API URL을 컴포넌트마다 하드코딩
- 에러 메시지를 사용처마다 다르게 작성
```

### 2. 참조 우선 원칙

**값을 복사하지 말고 참조하세요:**

```typescript
// ❌ 잘못된 예
const API_URL = "https://api.example.com"; // 여러 파일에 중복

// ✅ 올바른 예
import { API_URL } from "@/config/env";
```

### 3. 변경 시 단일 지점

**하나를 바꾸면 모든 곳에 반영되어야 합니다:**

```
에러 메시지 변경 시:
  ✅ errors/messages.ts 하나만 수정 → 모든 곳에 반영
  ❌ 10개 파일을 찾아다니며 수정
```

---

## 에러 로깅 규칙

### 중앙 집중식 에러 관리

**모든 에러는 단일 시스템으로 수집됩니다.**

```
src/
└── infrastructure/
    └── errors/
        ├── index.ts           # 에러 모듈 진입점
        ├── types.ts           # 에러 타입 정의
        ├── messages.ts        # 에러 메시지 상수
        ├── handler.ts         # 중앙 에러 핸들러
        └── logger.ts          # 에러 로깅
```

### 에러 타입 정의 (예시)

```typescript
// src/infrastructure/errors/types.ts

export enum ErrorCode {
  // 인증
  AUTH_UNAUTHORIZED = "AUTH_001",
  AUTH_TOKEN_EXPIRED = "AUTH_002",
  AUTH_INVALID_CREDENTIALS = "AUTH_003",

  // API
  API_REQUEST_FAILED = "API_001",
  API_TIMEOUT = "API_002",
  API_INVALID_RESPONSE = "API_003",

  // 데이터
  DATA_NOT_FOUND = "DATA_001",
  DATA_VALIDATION_FAILED = "DATA_002",
  DATA_DUPLICATE = "DATA_003",

  // 시스템
  SYSTEM_UNKNOWN = "SYS_001",
  SYSTEM_NETWORK = "SYS_002",
  SYSTEM_STORAGE = "SYS_003",
}

export interface AppError {
  code: ErrorCode;
  message: string;
  context?: Record<string, unknown>;
  timestamp: string;
  stack?: string;
}
```

### 에러 로깅 형식

**모든 에러는 다음 형식으로 기록됩니다:**

```typescript
// src/infrastructure/errors/logger.ts

interface ErrorLog {
  // 필수 필드
  code: string; // 에러 코드 (예: AUTH_001)
  message: string; // 사람이 읽을 수 있는 메시지
  timestamp: string; // ISO 8601 형식

  // 컨텍스트 (선택)
  userId?: string; // 사용자 ID
  sessionId?: string; // 세션 ID
  requestId?: string; // 요청 ID (추적용)

  // 위치 정보
  file?: string; // 발생 파일
  function?: string; // 발생 함수
  line?: number; // 발생 라인

  // 추가 정보
  context?: Record<string, unknown>; // 관련 데이터
  stack?: string; // 스택 트레이스

  // 심각도
  severity: "debug" | "info" | "warn" | "error" | "critical";
}
```

### 에러 로그 저장 위치

```
logs/
├── errors/
│   ├── YYYY-MM-DD.log      # 일별 에러 로그
│   └── critical/           # 심각한 에러 별도 보관
│       └── YYYY-MM-DD.log
└── audit/                   # 감사 로그 (선택)
```

### 에러 핸들러 구현 (예시)

```typescript
// src/infrastructure/errors/handler.ts

import { ErrorCode, AppError } from "./types";
import { errorLogger } from "./logger";

export function handleError(
  error: unknown,
  context?: Record<string, unknown>,
): AppError {
  const appError = normalizeError(error);

  // 중앙 로깅
  errorLogger.log({
    ...appError,
    context,
    timestamp: new Date().toISOString(),
  });

  // 심각한 에러는 즉시 알림
  if (isCritical(appError)) {
    notifyOnCall(appError);
  }

  return appError;
}

function normalizeError(error: unknown): AppError {
  if (error instanceof AppError) {
    return error;
  }

  if (error instanceof Error) {
    return {
      code: ErrorCode.SYSTEM_UNKNOWN,
      message: error.message,
      stack: error.stack,
      timestamp: new Date().toISOString(),
    };
  }

  return {
    code: ErrorCode.SYSTEM_UNKNOWN,
    message: String(error),
    timestamp: new Date().toISOString(),
  };
}
```

---

## 실전 예시: DB SSH Tunnel

### 문제 상황 (SSOT 위반)

```
❌ 여러 파일에 SSH 주소 하드코딩:
- agents/domain/data-engineering/optimize-queries.md
- agents/domain/data-analytics/analyze-data.md
- agents/domain/quant/analyze-strategy.md
- agents/domain/quant/fetch-market-data.md
- rules/mcp-usage.md (2곳)
- skills/common/db-query/skill.md
- scripts/ssh-tunnel.sh

→ 서버 주소 변경 시 여러 파일 수정 필요!
```

### 해결 방법 (SSOT 적용)

```bash
# 1. 환경 변수로 설정 (단일 출처!)
export CLAUDE_DB_SSH_HOST="user@your-server.com"

# 2. SSOT 스크립트가 환경 변수 참조
scripts/db-tunnel.sh
  ↳ REMOTE_HOST="$CLAUDE_DB_SSH_HOST"  ← 환경 변수 참조!

# 3. Agent/Skill/Rules는 스크립트 참조만
> - SSH 터널 필요: `./scripts/db-tunnel.sh start`

# 4. 서버 변경 시
vim ~/.zshrc
  ↳ CLAUDE_DB_SSH_HOST만 변경 → 전체 반영!
```

### 효과

- ✅ 서버 주소 변경: 10개 파일 → 1개 파일
- ✅ 검색/치환 불필요
- ✅ 실수 방지 (일부 파일 누락 불가능)
- ✅ Agent 파일 가독성 향상 (IP 하드코딩 제거)

**상세:** `docs/guides/ssot-db-tunnel.md`

---

## SSOT 적용 체크리스트

### 코드 작성 시

- [ ] 이 값이 다른 곳에 이미 정의되어 있는가?
- [ ] 하드코딩 대신 상수/설정을 참조하고 있는가?
- [ ] 에러는 중앙 핸들러를 통해 처리되는가?

### 코드 리뷰 시

- [ ] 중복 정의된 상수/타입이 없는가?
- [ ] 에러 로깅이 표준 형식을 따르는가?
- [ ] 설정값이 단일 출처에서 오는가?

### 유지보수 시

- [ ] 하나의 변경이 여러 파일 수정을 요구하는가? → SSOT 위반 신호
- [ ] 같은 버그가 여러 곳에서 발생하는가? → 중복 코드 신호

---

## 관련 에이전트

| 상황             | 위임 대상                   |
| ---------------- | --------------------------- |
| SSOT 위반 발견   | **Dev/review-code**         |
| 에러 구조 설계   | **Dev/plan-implementation** |
| 에러 핸들러 구현 | **Dev/implement-code**      |
