# 한투 퀀트 웹 인터페이스

React + TypeScript로 구현된 한투 퀀트 시스템의 웹 인터페이스입니다.

## 🚀 기술 스택

- **Frontend**: React 18 + TypeScript + Vite
- **Styling**: Tailwind CSS
- **Routing**: React Router v6
- **Charts**: Recharts
- **Icons**: Lucide React
- **HTTP Client**: Axios
- **WebSocket**: Socket.io-client

## 📦 설치 및 실행

### 1. 의존성 설치
```bash
npm install
```

### 2. 환경 변수 설정
`.env` 파일을 생성하고 다음 내용을 추가하세요:

```env
# API 설정
VITE_API_BASE_URL=http://localhost:8000/api
VITE_WS_URL=ws://localhost:8000/ws

# 환경 설정
VITE_APP_ENV=development

# 인증 설정 (옵션)
VITE_AUTH_ENABLED=false
```

### 3. 개발 서버 실행
```bash
npm run dev
```

### 4. 빌드
```bash
npm run build
```

## 🏗️ 프로젝트 구조

```
src/
├── components/          # 재사용 가능한 컴포넌트
│   └── Layout.tsx      # 메인 레이아웃
├── pages/              # 페이지 컴포넌트
│   └── Dashboard.tsx   # 대시보드 페이지
├── services/           # API 서비스
│   └── api.ts          # API 클라이언트
├── types/              # TypeScript 타입 정의
│   └── index.ts        # 메인 타입 정의
├── hooks/              # 커스텀 훅
├── utils/              # 유틸리티 함수
├── App.tsx             # 메인 앱 컴포넌트
└── main.tsx            # 앱 진입점
```

## 📱 주요 기능

### ✅ 구현 완료
- **대시보드**: 시스템 상태 및 성과 요약
- **반응형 레이아웃**: 모바일/데스크톱 지원
- **라우팅**: React Router 기반 페이지 네비게이션
- **API 클라이언트**: 백엔드 API 연동 준비

### 🔄 구현 예정
- **감시 리스트 관리**: 종목 추가/삭제/수정
- **일일 선정 종목**: 매일 선정된 종목 조회
- **AI 모니터링**: AI 모델 성능 및 학습 상태
- **시장 모니터링**: 실시간 알림 및 이상 감지
- **백테스트 결과**: 전략 성과 및 리포트
- **설정 관리**: 시스템 설정 및 환경 변수
- **실시간 데이터**: WebSocket 기반 실시간 업데이트

## 🎨 디자인 시스템

### 컬러 팔레트
- **Primary**: Blue (#3b82f6)
- **Success**: Green (#22c55e)
- **Warning**: Yellow (#f59e0b)
- **Danger**: Red (#ef4444)

### 컴포넌트 클래스
- `.card`: 기본 카드 스타일
- `.btn`: 기본 버튼 스타일
- `.btn-primary`: 주요 버튼 스타일
- `.btn-secondary`: 보조 버튼 스타일
- `.input`: 기본 입력 필드 스타일

## 🔗 백엔드 연동

이 웹 인터페이스는 FastAPI 백엔드와 연동되도록 설계되었습니다. 백엔드 API 엔드포인트:

### 주요 API 엔드포인트
- `GET /api/system/status` - 시스템 상태
- `GET /api/watchlist` - 감시 리스트 조회
- `POST /api/watchlist` - 감시 리스트 추가
- `GET /api/daily-selections` - 일일 선정 종목
- `GET /api/ai/models/performance` - AI 모델 성능
- `GET /api/market/alerts` - 시장 알림
- `GET /api/performance/metrics` - 성과 지표

## 🚀 다음 단계

1. **FastAPI 백엔드 서버 구현**
2. **감시 리스트 페이지 구현**
3. **실시간 WebSocket 연결**
4. **차트 및 시각화 개선**
5. **모바일 최적화**
6. **테스트 코드 작성**

## 📄 라이선스

한투 퀀트 프로젝트의 일부입니다.
