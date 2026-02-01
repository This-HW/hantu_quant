#!/bin/bash
# =============================================================================
# 보안 테스트 통합 실행 스크립트
#
# 목적: 모든 보안 테스트를 순차적으로 실행하고 결과 요약
# =============================================================================

set -euo pipefail

# ===== 설정 =====
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
RESULT_LOG="$PROJECT_ROOT/logs/security_test_results.log"

# ===== 유틸리티 함수 =====

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $1" | tee -a "$RESULT_LOG"
}

# ===== 메인 실행 =====

mkdir -p "$PROJECT_ROOT/logs"
> "$RESULT_LOG"

log "===== 보안 테스트 통합 실행 시작 ====="
log ""

# 테스트 결과 카운터
total_suites=0
passed_suites=0
failed_suites=0

# ===== 1. SQL Injection 방지 테스트 =====
log "### 1. SQL Injection 방지 테스트"
total_suites=$((total_suites + 1))

if "$SCRIPT_DIR/test_sql_injection.sh" >> "$RESULT_LOG" 2>&1; then
    log "✓ SQL Injection 테스트 통과"
    passed_suites=$((passed_suites + 1))
else
    log "✗ SQL Injection 테스트 실패"
    failed_suites=$((failed_suites + 1))
fi
log ""

# ===== 2. 경로 검증 테스트 =====
log "### 2. 경로 검증 테스트"
total_suites=$((total_suites + 1))

if "$SCRIPT_DIR/test_path_validation.sh" >> "$RESULT_LOG" 2>&1; then
    log "✓ 경로 검증 테스트 통과"
    passed_suites=$((passed_suites + 1))
else
    log "✗ 경로 검증 테스트 실패"
    failed_suites=$((failed_suites + 1))
fi
log ""

# ===== 3. 환경변수 검증 테스트 =====
log "### 3. 환경변수 검증 테스트"
total_suites=$((total_suites + 1))

if "$SCRIPT_DIR/test_env_vars.sh" >> "$RESULT_LOG" 2>&1; then
    log "✓ 환경변수 검증 테스트 통과"
    passed_suites=$((passed_suites + 1))
else
    log "✗ 환경변수 검증 테스트 실패"
    failed_suites=$((failed_suites + 1))
fi
log ""

# ===== 최종 결과 요약 =====
log "===== 최종 결과 ====="
log "총 테스트 스위트: $total_suites"
log "통과: $passed_suites"
log "실패: $failed_suites"
log ""

if [ $failed_suites -eq 0 ]; then
    log "✓ 모든 보안 테스트 통과!"
    log ""
    log "상세 로그: $RESULT_LOG"
    exit 0
else
    log "✗ 일부 테스트 실패"
    log ""
    log "상세 로그: $RESULT_LOG"
    exit 1
fi
