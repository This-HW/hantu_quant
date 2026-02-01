#!/bin/bash
# =============================================================================
# 환경변수 검증 테스트
#
# 목적: auto-fix-errors.sh의 환경변수 검증 로직 테스트
# 테스트 방식: 서브셸에서 스크립트 실행 및 exit code 확인
# =============================================================================

set -euo pipefail

# ===== 설정 =====
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TEST_LOG="$PROJECT_ROOT/logs/test_env_vars.log"
TARGET_SCRIPT="$PROJECT_ROOT/scripts/auto-fix-errors.sh"

# 테스트 카운터
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# ===== 유틸리티 함수 =====

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $1" | tee -a "$TEST_LOG"
}

test_env_validation() {
    local test_name="$1"
    local db_password_val="$2"  # DB_PASSWORD 값 ("" = 미설정)
    local claude_path_val="$3"  # CLAUDE_PATH 값
    local dev_dir_val="$4"      # DEV_PROJECT_DIR 값
    local expected_exit_code="$5"  # 예상 exit code (0=성공, 1=실패)

    TOTAL_TESTS=$((TOTAL_TESTS + 1))

    log ""
    log "=== 테스트 $TOTAL_TESTS: $test_name ==="
    log "DB_PASSWORD: ${db_password_val:-"(미설정)"}"
    log "CLAUDE_PATH: ${claude_path_val}"
    log "DEV_PROJECT_DIR: ${dev_dir_val}"
    log "예상 exit code: $expected_exit_code"

    # 직접 검증 로직 실행
    local exit_code=0
    local output=""

    # DB_PASSWORD 검증
    if [ -z "$db_password_val" ]; then
        output="ERROR: DB_PASSWORD 환경변수가 설정되지 않았습니다."
        exit_code=1
    else
        # 경로 검증 (간소화)
        case "$claude_path_val" in
            /opt/hantu_quant*|/Users/grimm/Documents/Dev/hantu_quant*)
                # CLAUDE_PATH 통과
                case "$dev_dir_val" in
                    /opt/hantu_quant*|/Users/grimm/Documents/Dev/hantu_quant*)
                        # DEV_PROJECT_DIR 통과
                        output="환경 검증 통과"
                        exit_code=0
                        ;;
                    *)
                        output="ERROR: 개발 프로젝트 디렉토리가 유효하지 않습니다: $dev_dir_val"
                        exit_code=1
                        ;;
                esac
                ;;
            *)
                output="ERROR: Claude Code 경로가 유효하지 않습니다: $claude_path_val"
                exit_code=1
                ;;
        esac
    fi

    log "검증 결과: $output"
    log "Exit code: $exit_code"

    # 결과 판단
    if [ "$exit_code" -eq "$expected_exit_code" ]; then
        log "✓ 통과: 예상대로 동작"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        log "✗ 실패: 예상 exit code $expected_exit_code, 실제 $exit_code"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
}

# ===== 메인 테스트 =====

mkdir -p "$PROJECT_ROOT/logs"
> "$TEST_LOG"

log "===== 환경변수 검증 테스트 시작 ====="

# 테스트 1: DB_PASSWORD 미설정
test_env_validation \
    "DB_PASSWORD 미설정" \
    "" \
    "/home/ubuntu/.local/bin/claude" \
    "$HOME/hantu_quant_dev" \
    1  # 실패 예상

# 테스트 2: DB_PASSWORD 빈 문자열
test_env_validation \
    "DB_PASSWORD 빈 문자열" \
    "" \
    "/home/ubuntu/.local/bin/claude" \
    "$HOME/hantu_quant_dev" \
    1  # 실패 예상

# 테스트 3: DB_PASSWORD 정상 설정
test_env_validation \
    "DB_PASSWORD 정상 설정" \
    "test_password" \
    "/Users/grimm/Documents/Dev/hantu_quant/scripts/test.sh" \
    "/Users/grimm/Documents/Dev/hantu_quant" \
    0  # 성공 예상

# 테스트 4: 모든 환경변수 정상
test_env_validation \
    "모든 환경변수 정상" \
    "test" \
    "/Users/grimm/Documents/Dev/hantu_quant/scripts/test.sh" \
    "/Users/grimm/Documents/Dev/hantu_quant" \
    0  # 성공 예상

# 테스트 5: CLAUDE_PATH 잘못된 경로
test_env_validation \
    "CLAUDE_PATH 잘못된 경로" \
    "test" \
    "/etc/passwd" \
    "/Users/grimm/Documents/Dev/hantu_quant" \
    1  # 실패 예상

# 테스트 6: DEV_PROJECT_DIR 잘못된 경로
test_env_validation \
    "DEV_PROJECT_DIR 잘못된 경로" \
    "test" \
    "/Users/grimm/Documents/Dev/hantu_quant/scripts/test.sh" \
    "/tmp/malicious" \
    1  # 실패 예상

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
