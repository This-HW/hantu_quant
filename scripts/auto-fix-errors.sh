#!/bin/bash
# =============================================================================
# 자동 에러 수정 스크립트
#
# 목적: 에러 로그를 수집하고 Claude Code로 자동 분석/수정
# 실행: crontab으로 평일 6:00~17:30 30분마다 실행 (24회/일)
#
# 주요 기능:
#   1. 로컬 로그, systemd 로그, DB 에러 로그 수집
#   2. 에러가 없으면 즉시 종료 (토큰 절약)
#   3. 에러 있으면 Claude Code로 분석 및 수정
#   4. 테스트 통과 시 [skip ci] 커밋 후 서비스 재시작
#
# 환경변수 (필수):
#   - DB_HOST: PostgreSQL 호스트
#   - DB_USER: PostgreSQL 사용자
#   - DB_PASSWORD: PostgreSQL 비밀번호
#   - DB_NAME: PostgreSQL 데이터베이스명
# =============================================================================

set -uo pipefail
# Note: -e 제거 (에러 트랩이 제대로 작동하도록)

# ===== 설정 =====
# 프로덕션 환경 (로그 읽기용)
PROD_LOG_DIR="/opt/hantu_quant/logs"
PROD_PROJECT_DIR="/opt/hantu_quant"

# 개발 레포 (코드 수정용)
DEV_PROJECT_DIR="$HOME/hantu_quant_dev"

# Auto-fix 결과 로그는 개발 레포에 저장
RESULT_LOG="$DEV_PROJECT_DIR/logs/auto-fix.log"
LOCKFILE="/tmp/auto-fix-errors.lock"
CLAUDE_PATH="/home/ubuntu/.local/bin/claude"

# DB 설정 (서버와 DB가 같은 머신에 있음)
DB_HOST="${DB_HOST:-localhost}"  # 기본값: localhost (서버 내부)
DB_USER="${DB_USER:-hantu}"      # 기본값: hantu
DB_PASS="${DB_PASSWORD:-}"
DB_NAME="${DB_NAME:-hantu_quant}"  # 기본값: hantu_quant

# 필수 환경변수 검증 (DB_PASSWORD만 필수)
if [ -z "$DB_PASS" ]; then
    echo "ERROR: DB_PASSWORD 환경변수가 설정되지 않았습니다." >&2
    # DB 접속 불가로 에러 적재 불가, 즉시 종료
    exit 1
fi

# Claude Code 존재 확인
if [ ! -x "$CLAUDE_PATH" ]; then
    ERROR_MSG="Claude Code가 설치되지 않았습니다: $CLAUDE_PATH"
    echo "ERROR: $ERROR_MSG" >&2
    # 로그 디렉토리 생성 후 DB 적재 시도
    mkdir -p "$DEV_PROJECT_DIR/logs"
    PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -c "
        INSERT INTO error_logs (timestamp, level, service, module, message, error_type)
        VALUES (NOW(), 'ERROR', 'auto-fix-cron', 'auto-fix-errors.sh', :'msg', 'MissingDependency');
    " 2>/dev/null || true
    exit 1
fi

# 로그 디렉토리 생성 (개발 레포)
mkdir -p "$DEV_PROJECT_DIR/logs"

# 로그 함수
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $1" >> "$RESULT_LOG"
}

# DB 에러 적재 함수
log_error_to_db() {
    local error_msg="$1"
    local error_type="${2:-ScriptError}"
    PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -c "
        INSERT INTO error_logs (timestamp, level, service, module, message, error_type)
        VALUES (NOW(), 'ERROR', 'auto-fix-cron', 'auto-fix-errors.sh', :'msg', :'type');
    " 2>/dev/null || true
}

# 에러 트랩 설정 (스크립트 에러 시 DB 적재)
trap 'log_error_to_db "Auto-fix script failed at line $LINENO" "ScriptFailure"; rm -f $LOCKFILE' ERR

log "DB 접속 정보: $DB_USER@$DB_HOST:5432/$DB_NAME"

# ===== 0. 중복 실행 방지 (Lockfile) =====
if [ -f "$LOCKFILE" ]; then
    # Lockfile이 있으면 프로세스 확인
    LOCK_PID=$(cat "$LOCKFILE" 2>/dev/null || echo "")
    if [ -n "$LOCK_PID" ] && kill -0 "$LOCK_PID" 2>/dev/null; then
        log "이미 실행 중 (PID: $LOCK_PID) - 종료"
        exit 0
    else
        # Stale lockfile 제거
        log "Stale lockfile 제거 (PID: $LOCK_PID)"
        rm -f "$LOCKFILE"
    fi
fi

# Lockfile 생성
echo $$ > "$LOCKFILE"
trap "rm -f $LOCKFILE" EXIT

log "===== 자동 에러 수정 시작 ====="

# ===== 1. 에러 로그 수집 =====

# 프로덕션 로그 읽기 (최근 30분 이내 에러)
LOCAL_ERRORS=$(cat "$PROD_LOG_DIR/$(date +%Y%m%d).log" 2>/dev/null | grep -i 'error\|exception\|traceback' | tail -30 || true)

# systemd 서비스 로그 (최근 30분)
SYSTEM_ERRORS=$(journalctl -u hantu-api -u hantu-scheduler --since '30 minutes ago' --no-pager 2>/dev/null | grep -i 'error\|exception\|traceback' | tail -30 || true)

# DB 에러 로그 (미해결, 최근 30분)
DB_ERRORS=$(PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -t -c "
SELECT
    'ID:' || id || ' | ' ||
    'Time:' || timestamp || ' | ' ||
    'Service:' || COALESCE(service, '-') || ' | ' ||
    'Module:' || COALESCE(module, '-') || ' | ' ||
    'Type:' || COALESCE(error_type, '-') || ' | ' ||
    'Msg:' || LEFT(message, 200) ||
    CASE WHEN stack_trace IS NOT NULL THEN ' | Stack:' || LEFT(stack_trace, 300) ELSE '' END
FROM error_logs
WHERE resolved IS NULL
  AND timestamp > NOW() - INTERVAL '30 minutes'
ORDER BY timestamp DESC
LIMIT 20
" 2>/dev/null || true)

# ===== 2. 에러 개수 계산 =====
LOCAL_COUNT=$(echo "$LOCAL_ERRORS" | grep -c . || echo 0)
SYSTEM_COUNT=$(echo "$SYSTEM_ERRORS" | grep -c . || echo 0)
DB_COUNT=$(echo "$DB_ERRORS" | grep -c . || echo 0)

# ===== 3. 에러 없으면 즉시 종료 (토큰 절약) =====
if [ -z "$LOCAL_ERRORS" ] && [ -z "$SYSTEM_ERRORS" ] && [ -z "$DB_ERRORS" ]; then
    log "✅ 정상 - 에러 없음 (로컬:${LOCAL_COUNT}, 시스템:${SYSTEM_COUNT}, DB:${DB_COUNT})"
    exit 0
fi

# 에러 개수 로깅
log "에러 발견 - 로컬: ${LOCAL_COUNT}건, 시스템: ${SYSTEM_COUNT}건, DB: ${DB_COUNT}건"

# ===== 3. Claude Code로 분석 및 수정 =====
# 개발 레포로 이동
cd "$DEV_PROJECT_DIR"

# 최신 코드 가져오기 (중요!)
log "최신 코드 가져오기 (git pull)"
git fetch origin main
git reset --hard origin/main
if [ $? -ne 0 ]; then
    ERROR_MSG="git pull 실패 - 작업 중단"
    log "ERROR: $ERROR_MSG"
    log_error_to_db "$ERROR_MSG" "GitSyncFailure"
    exit 1
fi
log "최신 코드 동기화 완료: $(git rev-parse --short HEAD)"

# 가상환경 활성화
source "$DEV_PROJECT_DIR/venv/bin/activate"

PROMPT="에러 로그를 분석하고 수정해줘.

## 로컬 애플리케이션 로그
${LOCAL_ERRORS:-없음}

## Systemd 서비스 로그
${SYSTEM_ERRORS:-없음}

## DB 에러 로그 (미해결)
${DB_ERRORS:-없음}

## 작업 규칙 (반드시 준수)
1. 에러 원인을 분석하고 해당 코드를 수정해
2. 수정 후 pytest tests/unit/ -x --tb=short 실행
3. 테스트 통과하면:
   - git add -A
   - git commit -m 'fix: 자동 에러 수정 - \$(date +%Y%m%d_%H%M)

     Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>'
   - git push origin main
   - (배포는 CI/CD가 자동 처리)
4. 테스트 실패하면:
   - git checkout -- . 로 모든 변경사항 롤백
   - 실패 원인만 간단히 보고
5. 수정한 DB 에러는 resolved 컬럼 업데이트:
   - PGPASSWORD=\"\$DB_PASSWORD\" psql -h \"\$DB_HOST\" -U \"\$DB_USER\" -d \"\$DB_NAME\" -c \"UPDATE error_logs SET resolved = NOW(), resolution_note = '자동 수정' WHERE id IN (수정된_에러_ID들)\"
6. 최종 결과를 한 줄로 요약해줘
"

log "Claude Code 실행 시작"

# Claude Code 실행 (타임아웃 10분)
timeout 600 "$CLAUDE_PATH" --dangerously-skip-permissions -p "$PROMPT" 2>&1 | tee -a "$RESULT_LOG"

CLAUDE_EXIT_CODE=${PIPESTATUS[0]}

if [ $CLAUDE_EXIT_CODE -eq 0 ]; then
    log "Claude Code 정상 완료"
elif [ $CLAUDE_EXIT_CODE -eq 124 ]; then
    log "Claude Code 타임아웃 (10분 초과)"
    log_error_to_db "Auto-fix timeout after 10 minutes" "Timeout"
else
    log "Claude Code 종료 코드: $CLAUDE_EXIT_CODE"
    log_error_to_db "Auto-fix failed with exit code $CLAUDE_EXIT_CODE" "ClaudeCodeFailure"
fi

log "===== 자동 에러 수정 완료 ====="
