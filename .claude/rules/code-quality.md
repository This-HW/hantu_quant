# 코드 품질 규칙

> 읽기 쉽고, 유지보수하기 쉽고, 테스트 가능한 코드를 작성합니다.

---

## 핵심 원칙

### 1. 단순함 (Simplicity)

```
✅ 좋은 코드
- 한 눈에 이해 가능
- 한 가지 일만 수행
- 불필요한 추상화 없음

❌ 나쁜 코드
- 읽으려면 스크롤 필요
- 여러 책임이 섞임
- 과도한 추상화
```

### 2. 명확함 (Clarity)

```
✅ 좋은 코드
- 이름만 봐도 역할 파악
- 의도가 드러남
- 주석 없이도 이해 가능

❌ 나쁜 코드
- 약어, 축약어 남발
- 매직 넘버 사용
- 복잡한 조건문
```

### 3. 일관성 (Consistency)

```
✅ 좋은 코드
- 프로젝트 컨벤션 준수
- 같은 패턴 반복 사용
- 예측 가능한 구조

❌ 나쁜 코드
- 파일마다 다른 스타일
- 비슷한 로직, 다른 구현
- 예외적인 패턴 남발
```

---

## 함수/메서드 규칙

### 크기

```
✅ 권장
- 함수 길이: 20줄 이하
- 파라미터: 3개 이하
- 들여쓰기: 2단계 이하

⚠️ 경고 신호
- 함수 길이: 50줄 이상
- 파라미터: 5개 이상
- 들여쓰기: 4단계 이상
```

### 네이밍

```typescript
// ✅ 좋은 예
function calculateTotalPrice(items: CartItem[]): number
function validateUserInput(input: FormData): ValidationResult
function fetchUserProfile(userId: string): Promise<User>

// ❌ 나쁜 예
function calc(i: any): any
function process(data: any): any
function doStuff(): void
```

### 단일 책임

```typescript
// ❌ 여러 책임
function saveUserAndSendEmail(user: User) {
  db.save(user);           // 저장
  email.send(user.email);  // 이메일
  log.info("saved");       // 로깅
}

// ✅ 분리된 책임
function saveUser(user: User) { ... }
function sendWelcomeEmail(email: string) { ... }
function logUserCreation(userId: string) { ... }

// 조합
async function createUser(user: User) {
  const saved = await saveUser(user);
  await sendWelcomeEmail(saved.email);
  logUserCreation(saved.id);
}
```

---

## 에러 처리

### 명시적 에러 처리

```typescript
// ❌ 에러 무시
try {
  await fetchData();
} catch (e) {
  // 무시
}

// ❌ 모호한 처리
try {
  await fetchData();
} catch (e) {
  console.log(e);
}

// ✅ 명시적 처리
try {
  await fetchData();
} catch (error) {
  if (error instanceof NetworkError) {
    return handleNetworkError(error);
  }
  if (error instanceof ValidationError) {
    return handleValidationError(error);
  }
  throw error; // 알 수 없는 에러는 상위로
}
```

### 에러 전파

```typescript
// ✅ 에러 컨텍스트 보존
async function getUserOrders(userId: string) {
  try {
    return await orderService.findByUser(userId);
  } catch (error) {
    throw new AppError({
      code: ErrorCode.DATA_FETCH_FAILED,
      message: `Failed to fetch orders for user ${userId}`,
      cause: error,
    });
  }
}
```

---

## 조건문 규칙

### Early Return

```typescript
// ❌ 중첩된 조건
function processUser(user: User | null) {
  if (user) {
    if (user.isActive) {
      if (user.hasPermission) {
        return doProcess(user);
      }
    }
  }
  return null;
}

// ✅ Early Return
function processUser(user: User | null) {
  if (!user) return null;
  if (!user.isActive) return null;
  if (!user.hasPermission) return null;

  return doProcess(user);
}
```

### 복잡한 조건 추출

```typescript
// ❌ 복잡한 인라인 조건
if (user.age >= 18 && user.country === "KR" && user.verified && !user.banned) {
  // ...
}

// ✅ 의미 있는 이름으로 추출
const isEligibleUser = user.age >= 18
  && user.country === "KR"
  && user.verified
  && !user.banned;

if (isEligibleUser) {
  // ...
}

// 또는 함수로 추출
function isEligibleForService(user: User): boolean {
  return user.age >= 18
    && user.country === "KR"
    && user.verified
    && !user.banned;
}
```

---

## 타입 안전성

### TypeScript 규칙

```typescript
// ❌ any 사용 금지
function process(data: any): any { ... }

// ✅ 명시적 타입
function process(data: InputData): OutputData { ... }

// ❌ 타입 단언 남용
const user = data as User;

// ✅ 타입 가드 사용
function isUser(data: unknown): data is User {
  return typeof data === "object"
    && data !== null
    && "id" in data;
}

if (isUser(data)) {
  // data는 User 타입
}
```

### Null 처리

```typescript
// ❌ null 체크 누락
function getUserName(user: User | null) {
  return user.name; // 런타임 에러 가능
}

// ✅ 명시적 null 처리
function getUserName(user: User | null): string {
  if (!user) {
    return "Unknown";
  }
  return user.name;
}

// ✅ Optional chaining + Nullish coalescing
const userName = user?.name ?? "Unknown";
```

---

## 테스트 가능성

### 의존성 주입

```typescript
// ❌ 하드코딩된 의존성
class UserService {
  private db = new Database(); // 테스트 어려움

  async getUser(id: string) {
    return this.db.findById(id);
  }
}

// ✅ 주입된 의존성
class UserService {
  constructor(private db: IDatabase) {}

  async getUser(id: string) {
    return this.db.findById(id);
  }
}

// 테스트 시
const mockDb = { findById: jest.fn() };
const service = new UserService(mockDb);
```

### 순수 함수 선호

```typescript
// ❌ 부수 효과
function calculateDiscount(price: number) {
  const discount = price * 0.1;
  globalState.totalDiscount += discount; // 부수 효과
  return discount;
}

// ✅ 순수 함수
function calculateDiscount(price: number): number {
  return price * 0.1;
}
```

---

## 코드 품질 체크리스트

### 작성 시

- [ ] 함수가 한 가지 일만 하는가?
- [ ] 이름이 역할을 명확히 표현하는가?
- [ ] 에러 처리가 명시적인가?
- [ ] 타입이 명확한가?

### 리뷰 시

- [ ] 코드가 한 눈에 이해되는가?
- [ ] 불필요한 복잡성이 없는가?
- [ ] 프로젝트 컨벤션을 따르는가?
- [ ] 테스트 가능한 구조인가?

### 리팩토링 시

- [ ] 중복 코드가 있는가?
- [ ] 너무 큰 함수/클래스가 있는가?
- [ ] 의존성이 명확한가?

---

## 관련 에이전트

| 상황 | 위임 대상 |
|------|----------|
| 코드 품질 검토 | **Dev/review-code** |
| 리팩토링 계획 | **Dev/plan-refactor** |
| 테스트 작성 | **Dev/write-tests** |
| 보안 검사 | **Dev/security-scan** |
