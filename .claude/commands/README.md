# Claude Code 커맨드

> 슬래시 명령어로 자동화된 워크플로우를 실행합니다.
> 사용법: `/커맨드명 [인자]`

---

## 개발 커맨드

### /auto-dev
자동화된 개발 파이프라인. 탐색 → 계획 → 구현 → 검증 → 리뷰 순으로 진행합니다.

```
/auto-dev [작업 설명]
```

**예시:**
```
/auto-dev 로그인 기능에 2FA 추가
/auto-dev UserService에 캐싱 적용
```

---

### /review
현재 변경사항 또는 지정된 파일에 대한 코드 리뷰를 수행합니다.

```
/review [파일 경로 또는 빈칸]
```

**예시:**
```
/review                    # git diff 리뷰
/review src/auth/login.py  # 특정 파일 리뷰
```

---

### /test
테스트를 실행하고 결과를 분석합니다.

```
/test [테스트 경로 또는 빈칸]
```

**예시:**
```
/test                      # 전체 테스트
/test tests/unit/          # 단위 테스트만
```

---

### /debug
에러를 분석하고 수정합니다.

```
/debug [에러 메시지 또는 설명]
```

**예시:**
```
/debug TypeError: 'NoneType' object is not subscriptable
/debug 로그인 시 500 에러 발생
```

---

### /plan-task
작업 계획만 수립합니다. 구현 전 검토용.

```
/plan-task [작업 설명]
```

**예시:**
```
/plan-task 결제 시스템 리팩토링
/plan-task API 버전 2.0 마이그레이션
```

---

## 운영 커맨드

### /deploy
배포 파이프라인. 검증 → 배포 → 모니터링 순서로 진행합니다.

```
/deploy [대상] [환경]
```

**예시:**
```
/deploy app staging
/deploy infra production
```

---

### /monitor
시스템 모니터링. 현재 상태를 확인하고 이상 징후를 탐지합니다.

```
/monitor [대상]
```

**예시:**
```
/monitor              # 전체 시스템
/monitor app          # 애플리케이션만
/monitor db           # 데이터베이스만
```

---

### /incident
인시던트 대응 파이프라인. 복구 최우선으로 진행합니다.

```
/incident [상황 설명]
```

**예시:**
```
/incident 서비스 전체 다운
/incident 에러율 10% 초과
```

---

### /infra
인프라 작업 파이프라인. 탐색 → 계획 → 구현 → 검증 → 적용.

```
/infra [작업 설명]
```

**예시:**
```
/infra 새 웹서버 인스턴스 추가
/infra VCN에 private subnet 추가
```

---

## 커맨드 요약

| 커맨드 | 용도 | 인자 |
|--------|------|------|
| `/auto-dev` | 자동화 개발 | 작업 설명 |
| `/review` | 코드 리뷰 | 파일 경로 (선택) |
| `/test` | 테스트 실행 | 테스트 경로 (선택) |
| `/debug` | 디버깅 | 에러 메시지 |
| `/plan-task` | 계획 수립 | 작업 설명 |
| `/deploy` | 배포 | 대상, 환경 |
| `/monitor` | 모니터링 | 대상 (선택) |
| `/incident` | 인시던트 대응 | 상황 설명 |
| `/infra` | 인프라 작업 | 작업 설명 |
