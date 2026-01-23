# 코드 품질 기준

## 네이밍 규칙

| 종류 | 규칙 | 예시 |
|------|------|------|
| 컴포넌트 | PascalCase | `UserProfile.tsx` |
| 훅 | camelCase, use 접두사 | `useAuth.ts` |
| 유틸 | camelCase | `formatDate.ts` |
| 상수 | UPPER_SNAKE | `API_ENDPOINTS.ts` |
| 폴더 | kebab-case | `user-profile/` |

---

## 함수 크기

- **권장**: 20줄 이하
- **최대**: 50줄 (리팩토링 고려)
- **파라미터**: 3개 이하

---

## 금지 사항

- ❌ 하드코딩된 시크릿/API 키
- ❌ console.log 남기기 (디버깅용)
- ❌ any 타입 남용 (TypeScript)
- ❌ 주석 처리된 코드 남기기
- ❌ 미사용 import/변수
- ❌ src/ 내 .md 파일 생성
- ❌ temp, backup 파일 생성

---

## 타입 안전성

### Good
```typescript
function getUser(id: string): Promise<User> {
  return api.get<User>(`/users/${id}`);
}
```

### Bad
```typescript
function getUser(id: any): Promise<any> {
  return api.get(`/users/${id}`);
}
```

---

## 주석 가이드

### 필요한 주석
- 복잡한 비즈니스 로직 설명
- TODO(P1/P2) 태그
- API 문서 (JSDoc)

### 불필요한 주석
- 코드가 하는 일을 그대로 설명
- 주석 처리된 코드
- 명확한 변수명에 대한 설명

---

## Import 정리

```typescript
// 1. 외부 라이브러리
import React from 'react';
import { useQuery } from '@tanstack/react-query';

// 2. 절대 경로 import
import { Button } from '@/components/ui';

// 3. 상대 경로 import
import { useUserData } from './hooks';
import type { User } from './types';
```
