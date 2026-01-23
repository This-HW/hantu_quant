# 예제 코드

## React 컴포넌트 예제

### 기본 컴포넌트
```tsx
interface UserProfileProps {
  userId: string;
}

export function UserProfile({ userId }: UserProfileProps) {
  const { data: user, isLoading, error } = useUser(userId);

  if (isLoading) return <LoadingSpinner />;
  if (error) return <ErrorMessage error={error} />;
  if (!user) return null;

  return (
    <div className="user-profile">
      <Avatar src={user.avatar} />
      <h2>{user.name}</h2>
      <p>{user.email}</p>
    </div>
  );
}
```

---

## 커스텀 훅 예제

### 데이터 페칭 훅
```typescript
export function useUser(userId: string) {
  return useQuery({
    queryKey: ['user', userId],
    queryFn: () => fetchUser(userId),
    enabled: !!userId,
  });
}
```

### 폼 상태 훅
```typescript
export function useFormState<T>(initialState: T) {
  const [values, setValues] = useState(initialState);
  const [errors, setErrors] = useState<Partial<T>>({});

  const handleChange = (field: keyof T, value: T[keyof T]) => {
    setValues(prev => ({ ...prev, [field]: value }));
  };

  return { values, errors, handleChange, setErrors };
}
```

---

## API 서비스 예제

```typescript
// api/userService.ts
const BASE_URL = '/api/users';

export const userService = {
  async getById(id: string): Promise<User> {
    const response = await fetch(`${BASE_URL}/${id}`);
    if (!response.ok) {
      throw new ApiError('User not found', response.status);
    }
    return response.json();
  },

  async create(data: CreateUserDto): Promise<User> {
    const response = await fetch(BASE_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    return response.json();
  },
};
```

---

## 출력 보고 예제

```markdown
### 변경 사항
| 파일 | 유형 | 설명 |
|------|------|------|
| `src/features/user/UserProfile.tsx` | 생성 | 프로필 컴포넌트 |
| `src/features/user/useUser.ts` | 생성 | 데이터 훅 |
| `src/app/routes.ts` | 수정 | 라우트 추가 |

### 테스트 필요 사항
- [ ] 프로필 렌더링 테스트
- [ ] 에러 상태 테스트
```
