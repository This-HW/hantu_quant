# hantu_quant 최신 아키텍처/프로세스 업데이트 (2026-02-13)

작성일: 2026-02-13
반영 범위: 2026-02-09 ~ 2026-02-12 커밋 + 현재 코드 베이스

---

## 1. 최근 변경 핵심 요약

### A. KIS API 안정성 강화
- 토큰 만료(`EGW00123`) 자동 갱신 경로를 강화하고, 갱신 실패 시 재시도 허용 로직을 보완함.
- 재시도 시 헤더를 매번 재생성하도록 수정되어 "토큰 갱신 후 옛 토큰 재사용" 문제를 줄임.
- Rate Limit(`EGW00201`) 대응 대기/로깅 경로를 정리해 과호출 재발을 억제함.

핵심 파일:
- `core/config/api_config.py`
- `core/api/rest_client.py`
- `core/api/async_client.py`

### B. 스케줄러 복구 로직 강화
- 스케줄러 재시작 시 시간대별 복구(Phase1/Phase2/자동매매/장마감/성과분석) 경로를 명시적으로 수행.
- Phase2 배치 완료 여부를 "실제 파일 상태(JSON 유효성+날짜)"로 판별해 복구 정확도 개선.

핵심 파일:
- `workflows/scheduler/recovery.py`
- `workflows/scheduler/batch_utils.py`
- `workflows/integrated_scheduler.py`

### C. 운영 리소스 정책 갱신
- 시스템 서비스에서 스케줄러 메모리 제한을 `400MB -> 800MB`로 상향.

핵심 파일:
- `deploy/hantu-scheduler.service`

### D. 검증/지표 일관성 개선
- 종목코드 검증에서 일반주 외에 우선주/스팩 패턴 허용.
- 무위험수익률 상수(`RISK_FREE_RATE = 0.02`)를 SSOT로 통일.

핵심 파일:
- `core/models/validators.py`
- `core/config/constants.py`
- `docs/works/SF-R1-R4-fixes.md`

---

## 2. 프로세스 로직 (최신)

## 2.1 REST API 요청 파이프라인

1. 요청 진입
- `KISRestClient._request()` 호출
- 글로벌 Rate Limit 적용 (`_rate_limit`)
- `ensure_valid_token()`으로 토큰 유효성 보장

2. 재시도 실행
- `_request_with_retry()`에서 매 재시도마다 `get_headers()` 재호출
- 사용자 헤더는 `tr_id/hashkey` 등만 병합, 인증 헤더는 최신 토큰으로 고정

3. 응답 분기
- `200 + rt_cd=0`: 성공
- `200 + rt_cd=1 + 재시도 가능 코드`: 코드별 대기 후 재시도
- `5xx`: KIS 코드 추출 후 대기/재시도
- `4xx`: 재시도 없이 실패 반환

4. 토큰 만료 분기
- `EGW00123` 감지 시 `refresh_token(force=False)`
- 갱신 성공: 파일/메모리 동기화 후 즉시 재시도
- 갱신 실패: 짧은 대기 후 토큰 파일 재로딩, 재시도 경로 유지

## 2.2 토큰 갱신 동시성 제어

- 전역 락 파일: `hantu_token_refresh.lock`
- 규정 반영: "1분당 1회 재발급 제한" 검사
- 락 획득 후 토큰 파일 재로딩하여 타 프로세스 선갱신 시 중복 갱신 회피
- 토큰 저장 파일 권한 `600` 유지

## 2.3 비동기 시세 조회 파이프라인

- `AsyncKISClient`에서 3단계 윈도우 제한:
  - 1초: 5건
  - 1분: 80건(보수적)
  - 1시간: 1200건(보수적)
- 캐시 우선 조회 후 미스 시 API 호출
- 배치 조회에서 부분 실패 허용 + 성공/실패 분리 리턴

## 2.4 스케줄러 재시작 복구 파이프라인

평일 기준:
- 06:00 이후: Phase1/선정 데이터 존재 여부 확인 후 필요 시 스크리닝
- 07:00~09:00: 미완료 배치 자동 복구 실행
- 09:00~15:30: 장중이면 자동매매 복구 시작
- 16:00 이후: 시장 마감 정리
- 17:00 이후: 일일 성과 분석

복구 판단 기준:
- DB 선정 결과 존재 여부
- `data/daily_selection/batch_{id}.json` 존재/크기/mtime/JSON 유효성

---

## 3. 아키텍처 관점 변경 포인트

### 3.1 API 계층
- `APIConfig`: 토큰/헤더/엔드포인트/에러코드 SSOT
- `KISRestClient`: 동기 요청 + 예외 분류 + 재시도
- `AsyncKISClient`: 대량 시세 조회 최적화

### 3.2 스케줄링 계층
- `IntegratedScheduler`: 전체 오케스트레이션
- `RecoveryManager`: 재시작 복구 정책 담당
- `batch_utils`: 배치 완료 상태 판정 표준화

### 3.3 검증/품질 계층
- `core/models/validators.py`: 입력 도메인 검증 확장
- `core/watchlist/validator.py`: 스크리닝 결과 품질 검증
- `core/config/constants.py`: 금융 지표 상수 통일

---

## 4. 운영 기준 업데이트 (요약)

1. 토큰/Rate Limit 관련 장애는 APIConfig + RestClient 로그를 우선 확인.
2. 배포 후 스케줄러 재시작 시 RecoveryManager가 누락 작업을 자동 복구.
3. 메모리 한계 초과 이슈는 systemd `MemoryMax=800M` 기준으로 모니터링.
4. 종목코드 검증 실패 케이스는 우선주/스팩 패턴 허용 범위 포함 여부를 재확인.

---

## 5. 최근 참고 문서

- `docs/guides/server-recovery.md`
- `docs/works/SF-R1-R4-fixes.md`
- `docs/analysis/profitability-analysis-2026-02-08.md`
- `docs/analysis/profitability-improvement-roadmap.md`

