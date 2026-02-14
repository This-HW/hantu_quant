# hantu_quant 변경 이력 다이제스트 (2026-02-13)

기준 기간: 2026-02-09 ~ 2026-02-12
목적: 최근 기술 변경사항을 NotebookLM에서 추적 가능하도록 요약

## 핵심 테마
- KIS API 토큰 만료/재발급/재시도 안정화
- Rate Limit 에러(EGW00201) 대응 강화
- 스케줄러 재시작 복구 로직 보강
- 검증/상수 SSOT 정리
- 서비스 리소스 정책 조정(메모리 상향)

## 커밋 스냅샷
- 2026-02-12 | 8e8b647 | fix: 스케줄러 메모리 제한 400MB → 800MB 증가
- 2026-02-12 | 6f52122 | fix: KIS API 연결 실패 시 명확한 로깅 추가
- 2026-02-12 | 583cf70 | fix: 토큰 갱신 후 메모리 동기화 누락 수정
- 2026-02-12 | 9acdf28 | fix: 토큰 갱신 후 재시도 시 헤더 완전 재생성
- 2026-02-12 | f308fae | fix: 토큰 갱신 후 재시도 시 새 토큰 미반영 수정
- 2026-02-12 | 6f6e2cb | fix: Rate Limit 에러 재발 방지
- 2026-02-11 | 0cbe6c2 | fix: pykrx 로깅 에러 억제
- 2026-02-11 | 2b54db6 | fix: 토큰 갱신 실패 시 재시도 허용
- 2026-02-11 | bdbccca | fix: 토큰 갱신 Race Condition 해결
- 2026-02-11 | 044ccf6 | fix: 메모리 제한 증가 및 Rate Limit 개선
- 2026-02-11 | 3b132e7 | feat: Dexter 패턴 기반 검증 및 에러 복구 시스템 구현
- 2026-02-11 | 585f20f | fix: 서버 복구 및 에러 수정 - DB 폴백 + INQR_DVSN 파라미터 수정
- 2026-02-10 | 3c1ca07 | fix: 토큰 만료 에러(EGW00123) 자동 갱신 처리
- 2026-02-10 | c78ee1c | fix: 잔고 조회 API INQR_DVSN 파라미터 수정 (01→02)
- 2026-02-10 | 90f8989 | fix: 종목코드 검증 규칙 완화 (우선주/스팩 허용)
- 2026-02-10 | 0a5d344 | fix: VACUUM 트랜잭션 에러 수정 + 종목 코드 검증 강화 + 로그 레벨 조정
- 2026-02-10 | 46c81d3 | feat: 섹터 데이터 연동 + 배치 모니터링 + 코드 리뷰 개선
- 2026-02-09 | 6b88a2f | fix: Phase 2 일일 선정 스코어링 시스템 개선
- 2026-02-09 | 2e1298d | fix: 리뷰 Must Fix 항목 수정 (MF-1, MF-2)
- 2026-02-09 | 5a17ec5 | refactor: 코드 리뷰 이슈 수정 (MF/SF 항목)
- 2026-02-09 | 2c1072b | fix: Rate Limit 에러 처리 개선 (EGW00201)

## 영향 파일(대표)
- API: `core/config/api_config.py`, `core/api/rest_client.py`, `core/api/async_client.py`
- Scheduler: `workflows/integrated_scheduler.py`, `workflows/scheduler/recovery.py`, `workflows/scheduler/batch_utils.py`
- Validation: `core/models/validators.py`, `core/watchlist/validator.py`
- Ops: `deploy/hantu-scheduler.service`, `docs/guides/server-recovery.md`
- Refactor 기록: `docs/works/SF-R1-R4-fixes.md`

