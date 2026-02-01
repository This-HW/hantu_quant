# 보안 테스트 문서

## 개요

`scripts/auto-fix-errors.sh`의 보안 수정사항을 검증하는 테스트 스위트입니다.

## 테스트 파일

| 파일                      | 유형               | 테스트 수 | 목적                          |
| ------------------------- | ------------------ | --------- | ----------------------------- |
| `test_sql_injection.sh`   | SQL Injection 방지 | 7개       | Prepared Statement 검증       |
| `test_path_validation.sh` | 경로 검증          | 13개      | Path Traversal 방지           |
| `test_env_vars.sh`        | 환경변수 검증      | 6개       | 필수 환경변수 및 경로 검증    |
| `run_all_tests.sh`        | 통합 테스트        | -         | 모든 테스트 실행 및 결과 요약 |

## 실행 방법

### 전체 테스트 실행

```bash
./tests/security/run_all_tests.sh
```

### 개별 테스트 실행

```bash
# SQL Injection 방지 테스트
./tests/security/test_sql_injection.sh

# 경로 검증 테스트
./tests/security/test_path_validation.sh

# 환경변수 검증 테스트
./tests/security/test_env_vars.sh
```

## 테스트 상세

### 1. SQL Injection 방지 테스트

**목적**: psql Prepared Statement 사용 여부 검증

**테스트 케이스**:

1. 작은따옴표 이스케이프: `'; DROP TABLE error_logs; --`
2. UNION 공격: `' UNION SELECT password FROM users; --`
3. Stacked queries: `'; DELETE FROM error_logs WHERE 1=1; --`
4. Comment injection (--): `test message -- comment`
5. Comment injection (/\* _/): `test /_ malicious \*/ message`
6. Semicolon injection: `test; INSERT INTO error_logs VALUES ('injected');`
7. 정상 메시지: `This is a normal error message`

**검증 방식**:

- `psql -v msg="..." -c "... VALUES (:'msg', :'type')"` 형식 확인
- `:msg`, `:type` 파라미터 바인딩 사용 여부 검증

**결과**: 7/7 통과 ✓

---

### 2. 경로 검증 테스트

**목적**: `validate_path()` 함수의 화이트리스트 기반 검증

**정상 경로 테스트**:

- `/Users/grimm/Documents/Dev/hantu_quant` (로컬 프로젝트 루트)
- `/Users/grimm/Documents/Dev/hantu_quant/scripts` (로컬 서브디렉토리)
- `/opt/hantu_quant` (서버 프로젝트 루트)

**Path Traversal 공격 테스트**:

- `../../etc/passwd` (상위 디렉토리 탈출)
- `/etc/passwd` (절대 경로 탈출)
- `/tmp/malicious` (화이트리스트 외부)
- `/home/ubuntu/malicious` (화이트리스트 외부)

**특수 케이스**:

- 존재하지 않는 경로 (화이트리스트 내)
- 심볼릭 링크 (화이트리스트 외부)
- 상대 경로 (`.`, `..`)
- Null byte injection

**검증 방식**:

- `readlink -f` / `greadlink -f`로 경로 정규화
- 화이트리스트 패턴 매칭: `/opt/hantu_quant*`, `/Users/grimm/Documents/Dev/hantu_quant*`
- Null byte 검증

**결과**: 13/13 통과 ✓

---

### 3. 환경변수 검증 테스트

**목적**: 필수 환경변수 및 경로 검증 로직 테스트

**테스트 케이스**:

1. `DB_PASSWORD` 미설정 → 실패 예상 ✓
2. `DB_PASSWORD` 빈 문자열 → 실패 예상 ✓
3. `DB_PASSWORD` 정상 + 올바른 경로 → 성공 예상 ✓
4. 모든 환경변수 정상 → 성공 예상 ✓
5. `CLAUDE_PATH` 잘못된 경로 → 실패 예상 ✓
6. `DEV_PROJECT_DIR` 잘못된 경로 → 실패 예상 ✓

**검증 방식**:

- `DB_PASSWORD` 빈 값 체크
- `CLAUDE_PATH`, `DEV_PROJECT_DIR` 화이트리스트 검증

**결과**: 6/6 통과 ✓

---

## 전체 테스트 결과

```
===== 최종 결과 =====
총 테스트 스위트: 3
통과: 3
실패: 0

✓ 모든 보안 테스트 통과!
```

### 개별 테스트 통과율

| 테스트 스위트 | 케이스 수 | 통과   | 실패  | 통과율   |
| ------------- | --------- | ------ | ----- | -------- |
| SQL Injection | 7         | 7      | 0     | 100%     |
| 경로 검증     | 13        | 13     | 0     | 100%     |
| 환경변수 검증 | 6         | 6      | 0     | 100%     |
| **총계**      | **26**    | **26** | **0** | **100%** |

---

## 보안 수정사항 요약

### 1. SQL Injection 방지

**이전 (취약)**:

```bash
psql -c "INSERT INTO error_logs (message) VALUES ('REDACTED');"
```

**이후 (안전)**:

```bash
psql -v msg="$error_msg" -c "INSERT INTO error_logs (message) VALUES (:'msg');"
```

**효과**: 악성 SQL이 문자열로만 처리되어 실행 불가

---

### 2. Path Traversal 방지

**구현**:

- `validate_path()` 함수로 모든 경로 검증
- `readlink -f` / `greadlink -f`로 경로 정규화
- 화이트리스트 기반 검증
- Null byte 체크

**효과**: `/etc/passwd`, `../../etc/passwd` 등 화이트리스트 외부 접근 차단

---

### 3. 환경변수 검증

**구현**:

- `DB_PASSWORD` 필수 검증
- `CLAUDE_PATH`, `DEV_PROJECT_DIR` 경로 검증

**효과**: 잘못된 환경변수로 인한 보안 취약점 사전 차단

---

## 로그 위치

- **통합 테스트 로그**: `logs/security_test_results.log`
- **SQL Injection 로그**: `logs/test_sql_injection.log`
- **경로 검증 로그**: `logs/test_path_validation.log`
- **환경변수 검증 로그**: `logs/test_env_vars.log`

---

## 유지보수

### 새 테스트 추가 시

1. `tests/security/test_*.sh` 파일 생성
2. `run_all_tests.sh`에 테스트 추가
3. 실행 권한 부여: `chmod +x tests/security/test_*.sh`

### 정기 실행 권장

- PR 전 필수 실행
- 배포 전 필수 실행
- 보안 수정 후 필수 실행

---

## 참고

- **프로젝트**: Hantu Quant
- **대상 스크립트**: `scripts/auto-fix-errors.sh`
- **작성일**: 2026-02-01
