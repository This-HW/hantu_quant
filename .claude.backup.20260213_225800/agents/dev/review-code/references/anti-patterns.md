# 안티패턴 목록

## 설계 안티패턴

### God Object
하나의 클래스/모듈이 너무 많은 책임
```typescript
// Bad
class UserManager {
  login() { }
  logout() { }
  sendEmail() { }
  generateReport() { }
  validatePayment() { }
}
```

### Shotgun Surgery
하나의 변경이 여러 파일에 영향
```
UserType 변경 시:
- UserService.ts
- UserController.ts
- UserValidator.ts
- UserFormatter.ts
→ 모두 수정 필요
```

### Feature Envy
다른 클래스의 데이터를 과도하게 사용
```typescript
// Bad
function calculateDiscount(order: Order) {
  return order.items.length * order.customer.level * order.promotion.rate;
}
```

---

## 코드 안티패턴

### Deep Nesting
```typescript
// Bad
if (a) {
  if (b) {
    if (c) {
      if (d) {
        doSomething();
      }
    }
  }
}

// Good
if (!a || !b || !c || !d) return;
doSomething();
```

### Magic Numbers
```typescript
// Bad
if (user.age > 18 && user.score > 80) { }

// Good
const LEGAL_AGE = 18;
const PASS_SCORE = 80;
if (user.age > LEGAL_AGE && user.score > PASS_SCORE) { }
```

### Callback Hell
```typescript
// Bad
getUser(id, (user) => {
  getOrders(user.id, (orders) => {
    getItems(orders[0].id, (items) => {
      // ...
    });
  });
});

// Good
const user = await getUser(id);
const orders = await getOrders(user.id);
const items = await getItems(orders[0].id);
```

---

## 에러 처리 안티패턴

### Swallowing Exceptions
```typescript
// Bad
try {
  doSomething();
} catch (e) {
  // 무시
}

// Good
try {
  doSomething();
} catch (e) {
  logger.error('Failed to do something', e);
  throw new AppError('Operation failed', e);
}
```

### Pokemon Exception Handling
```typescript
// Bad: 모든 예외 포착
try {
  doSomething();
} catch (e) {
  // 뭐든 잡음
}

// Good: 특정 예외 처리
try {
  doSomething();
} catch (e) {
  if (e instanceof NetworkError) {
    handleNetworkError(e);
  } else {
    throw e; // 알 수 없는 에러는 전파
  }
}
```

---

## 성능 안티패턴

### N+1 Query
```typescript
// Bad
const users = await getUsers();
for (const user of users) {
  const orders = await getOrders(user.id); // N번 쿼리
}

// Good
const users = await getUsers();
const userIds = users.map(u => u.id);
const orders = await getOrdersByUserIds(userIds); // 1번 쿼리
```

### Premature Optimization
```typescript
// Bad: 필요없는 최적화
const cache = new Map();
function add(a: number, b: number) {
  const key = `${a}:${b}`;
  if (cache.has(key)) return cache.get(key);
  const result = a + b;
  cache.set(key, result);
  return result;
}
```

---

## 테스트 안티패턴

### Testing Implementation
```typescript
// Bad: 구현 세부사항 테스트
expect(component.state.count).toBe(1);

// Good: 동작 테스트
expect(screen.getByText('Count: 1')).toBeInTheDocument();
```

### Flaky Tests
```typescript
// Bad: 비결정적 테스트
expect(result).toContain(Date.now());

// Good: 결정적 테스트
const mockDate = new Date('2024-01-01');
jest.useFakeTimers().setSystemTime(mockDate);
expect(result).toContain('2024-01-01');
```
