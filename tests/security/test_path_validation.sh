#!/bin/bash
# =============================================================================
# 경로 검증 테스트
#
# 목적: auto-fix-errors.sh의 validate_path() 함수 검증
# 테스트 방식: 직접 함수 호출 및 반환값 확인
# =============================================================================

set -euo pipefail

# ===== 설정 =====
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TEST_LOG="$PROJECT_ROOT/logs/test_path_validation.log"

# 테스트 카운터
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# ===== validate_path 함수 복사 (테스트용) =====

validate_path() {
    local path="$1"
    local normalized

    # Null byte 체크 (문자열 길이 기반)
    if [ ${#path} -ne "$(echo -n "$path" | wc -c)" ]; then
        echo "Error: Path contains null byte" >&2
        return 1
    fi

    # macOS는 greadlink, Linux는 readlink
    if command -v greadlink >/dev/null 2>&1; then
        normalized=$(greadlink -f "$path" 2>/dev/null) || return 1
    else
        normalized=$(readlink -f "$path" 2>/dev/null) || return 1
    fi

    # 화이트리스트 검증 (루트 포함)
    case "$normalized" in
        /opt/hantu_quant|/opt/hantu_quant/*|\
        /Users/grimm/Documents/Dev/hantu_quant|/Users/grimm/Documents/Dev/hantu_quant/*)
            echo "$normalized"
            return 0
            ;;
        *)
            echo "Error: Path not allowed: $path" >&2
            return 1
            ;;
    esac
}

# ===== 유틸리티 함수 =====

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $1" | tee -a "$TEST_LOG"
}

test_path() {
    local test_name="$1"
    local test_path="$2"
    local should_pass="$3"  # "pass" 또는 "fail"

    TOTAL_TESTS=$((TOTAL_TESTS + 1))

    log ""
    log "=== 테스트 $TOTAL_TESTS: $test_name ==="
    log "경로: $test_path"
    log "예상: $should_pass"

    local result
    if result=$(validate_path "$test_path" 2>&1); then
        # 성공
        if [ "$should_pass" = "pass" ]; then
            log "✓ 통과: 허용됨 (정규화 경로: $result)"
            PASSED_TESTS=$((PASSED_TESTS + 1))
        else
            log "✗ 실패: 차단되어야 하는데 허용됨"
            FAILED_TESTS=$((FAILED_TESTS + 1))
        fi
    else
        # 실패
        if [ "$should_pass" = "fail" ]; then
            log "✓ 통과: 차단됨 (이유: $result)"
            PASSED_TESTS=$((PASSED_TESTS + 1))
        else
            log "✗ 실패: 허용되어야 하는데 차단됨 (이유: $result)"
            FAILED_TESTS=$((FAILED_TESTS + 1))
        fi
    fi
}

# ===== 메인 테스트 =====

mkdir -p "$PROJECT_ROOT/logs"
> "$TEST_LOG"

log "===== 경로 검증 테스트 시작 ====="

# ===== 정상 경로 테스트 =====
log ""
log "## 정상 경로 테스트"

test_path \
    "로컬 프로젝트 루트" \
    "/Users/grimm/Documents/Dev/hantu_quant" \
    "pass"

test_path \
    "로컬 스크립트 디렉토리" \
    "/Users/grimm/Documents/Dev/hantu_quant/scripts" \
    "pass"

test_path \
    "서버 프로젝트 루트" \
    "/opt/hantu_quant" \
    "pass"

test_path \
    "서버 로그 디렉토리 (존재하지 않음)" \
    "/opt/hantu_quant/logs" \
    "fail"

# ===== Path Traversal 공격 테스트 =====
log ""
log "## Path Traversal 공격 테스트"

test_path \
    "상위 디렉토리 탈출 (..)" \
    "/Users/grimm/Documents/Dev/hantu_quant/../../etc/passwd" \
    "fail"

test_path \
    "절대 경로 탈출" \
    "/etc/passwd" \
    "fail"

test_path \
    "tmp 디렉토리" \
    "/tmp/malicious" \
    "fail"

test_path \
    "home 디렉토리" \
    "/home/ubuntu/malicious" \
    "fail"

# ===== 특수 케이스 테스트 =====
log ""
log "## 특수 케이스 테스트"

# 존재하지 않는 경로
# 주의: greadlink -f는 존재하지 않는 경로도 정규화하지만
# 실제로는 파일 시스템에 없으므로 나중에 접근 시 실패
# 테스트는 "pass"로 설정하여 정규화 성공을 확인
test_path \
    "존재하지 않는 경로 (화이트리스트 내)" \
    "/Users/grimm/Documents/Dev/hantu_quant/nonexistent_dir_xyz123" \
    "pass"

# 심볼릭 링크 테스트 (실제 대상이 화이트리스트 밖이면 차단)
if [ -d "/tmp" ]; then
    ln -sf /etc/passwd /tmp/test_symlink_passwd 2>/dev/null || true
    test_path \
        "심볼릭 링크 (화이트리스트 외부)" \
        "/tmp/test_symlink_passwd" \
        "fail"
    rm -f /tmp/test_symlink_passwd
fi

# 상대 경로
# 주의: 현재 디렉토리가 프로젝트 루트면 허용될 수 있음
test_path \
    "상대 경로 (현재 디렉토리)" \
    "." \
    "pass"

test_path \
    "상대 경로 (상위 디렉토리)" \
    ".." \
    "fail"

# ===== Null byte 테스트 =====
log ""
log "## Null Byte 테스트"

# Null byte injection
test_path \
    "Null byte injection" \
    "/Users/grimm/Documents/Dev/hantu_quant"$'\0'"/etc/passwd" \
    "fail"

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
