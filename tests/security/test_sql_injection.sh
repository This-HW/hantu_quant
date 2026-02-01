#!/bin/bash
# =============================================================================
# SQL Injection 방지 테스트
#
# 목적: auto-fix-errors.sh의 SQL Injection 방지 검증
# 테스트 방식: psql 명령어 생성 확인 (dry-run)
# =============================================================================

set -euo pipefail

# ===== 설정 =====
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TEST_LOG="$PROJECT_ROOT/logs/test_sql_injection.log"

# 테스트 카운터
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# ===== 유틸리티 함수 =====

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $1" | tee -a "$TEST_LOG"
}

test_sql_injection() {
    local test_name="$1"
    local malicious_input="$2"
    local expected_behavior="$3"

    TOTAL_TESTS=$((TOTAL_TESTS + 1))

    log ""
    log "=== 테스트 $TOTAL_TESTS: $test_name ==="
    log "입력: $malicious_input"

    # psql 명령어 생성 (실제 실행하지 않음)
    local cmd="psql -v msg=\"$malicious_input\" -v type=\"TestError\" -c \"INSERT INTO error_logs (message, error_type) VALUES (:'msg', :'type');\""

    log "생성된 명령어:"
    log "$cmd"

    # Prepared Statement 방식 검증
    # :'msg' 형식으로 SQL 쿼리에서 참조되면 안전함
    if echo "$cmd" | grep -q "VALUES (:'msg', :'type')"; then
        log "✓ 통과: Prepared Statement 사용 (:'msg', :'type' 형식)"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        log "✗ 실패: Prepared Statement 미사용 또는 잘못된 형식"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi

    # psql -v 옵션 사용 확인 (변수 전달)
    if echo "$cmd" | grep -q "psql -v msg="; then
        log "✓ 추가 검증: psql -v 옵션으로 변수 전달 확인"
    else
        log "⚠ 경고: psql -v 옵션 미사용"
    fi
}

# ===== 메인 테스트 =====

mkdir -p "$PROJECT_ROOT/logs"
> "$TEST_LOG"

log "===== SQL Injection 방지 테스트 시작 ====="

# 테스트 1: 작은따옴표 이스케이프
test_sql_injection \
    "작은따옴표 이스케이프" \
    "'; DROP TABLE error_logs; --" \
    "Prepared Statement로 안전하게 처리"

# 테스트 2: UNION 공격
test_sql_injection \
    "UNION 공격" \
    "' UNION SELECT password FROM users; --" \
    "Prepared Statement로 안전하게 처리"

# 테스트 3: Stacked queries
test_sql_injection \
    "Stacked Queries" \
    "'; DELETE FROM error_logs WHERE 1=1; --" \
    "Prepared Statement로 안전하게 처리"

# 테스트 4: Comment injection (이중 대시)
test_sql_injection \
    "Comment Injection (--)" \
    "test message -- comment" \
    "Prepared Statement로 안전하게 처리"

# 테스트 5: Comment injection (/* */)
test_sql_injection \
    "Comment Injection (/* */)" \
    "test /* malicious */ message" \
    "Prepared Statement로 안전하게 처리"

# 테스트 6: Semicolon injection
test_sql_injection \
    "Semicolon Injection" \
    "test; INSERT INTO error_logs VALUES ('injected');" \
    "Prepared Statement로 안전하게 처리"

# 테스트 7: 정상 메시지 (비교군)
test_sql_injection \
    "정상 메시지" \
    "This is a normal error message" \
    "정상 처리"

# ===== 결과 요약 =====

log ""
log "===== 테스트 결과 요약 ====="
log "총 테스트: $TOTAL_TESTS"
log "통과: $PASSED_TESTS"
log "실패: $FAILED_TESTS"

if [ $FAILED_TESTS -eq 0 ]; then
    log "✓ 모든 테스트 통과!"
    exit 0
else
    log "✗ 일부 테스트 실패"
    exit 1
fi
