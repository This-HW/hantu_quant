# 구현 패턴 가이드

## 파일 위치 규칙

```
✅ 올바른 위치:
- 기능 코드: src/features/[기능명]/
- 엔티티: src/entities/[엔티티명]/
- 공유 코드: src/shared/
- 테스트: tests/unit/ 또는 tests/scratch/ (임시)

❌ 금지:
- src/ 내 .md 파일
- 루트에 임의 폴더
- temp*, backup* 파일
```

---

## 아키텍처 패턴

### Feature-Based 구조
```
src/features/user-profile/
├── index.ts           # 진입점 (exports)
├── UserProfile.tsx    # 메인 컴포넌트
├── useUserProfile.ts  # 커스텀 훅
├── types.ts           # 타입 정의
└── api.ts             # API 호출
```

### 계층 분리
```
UI Layer    → 컴포넌트, 페이지
Logic Layer → 훅, 서비스
Data Layer  → API, Repository
```

---

## 에러 처리 패턴

### Try-Catch with Context
```typescript
try {
  const result = await fetchData();
  return result;
} catch (error) {
  if (error instanceof ApiError) {
    throw new UserFacingError('데이터를 불러올 수 없습니다');
  }
  throw error;
}
```

### Error Boundary (React)
```typescript
<ErrorBoundary fallback={<ErrorFallback />}>
  <RiskyComponent />
</ErrorBoundary>
```

---

## API 호출 패턴

### React Query
```typescript
const { data, isLoading, error } = useQuery({
  queryKey: ['user', userId],
  queryFn: () => fetchUser(userId),
});
```

### SWR
```typescript
const { data, error, isLoading } = useSWR(
  `/api/user/${userId}`,
  fetcher
);
```

---

## 상태 관리 패턴

### Local State (useState)
단일 컴포넌트 내 상태

### Lifted State
부모-자식 간 공유 상태

### Context
앱 전역 상태 (테마, 인증)

### External Store (Zustand, Jotai)
복잡한 클라이언트 상태
