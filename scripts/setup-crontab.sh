#!/bin/bash
# =============================================================================
# Crontab 설정 스크립트
#
# 목적: 자동 에러 수정 스케줄러 crontab 등록
# 실행: 배포 시 자동 실행 또는 수동 실행
#
# 스케줄: 평일(월-금) 08:00~15:30, 30분마다
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
AUTO_FIX_SCRIPT="$PROJECT_DIR/scripts/auto-fix-errors.sh"

# 색상 출력
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 스크립트 존재 확인
if [ ! -f "$AUTO_FIX_SCRIPT" ]; then
    log_error "auto-fix-errors.sh를 찾을 수 없습니다: $AUTO_FIX_SCRIPT"
    exit 1
fi

# 실행 권한 부여
chmod +x "$AUTO_FIX_SCRIPT"
log_info "실행 권한 부여: $AUTO_FIX_SCRIPT"

# crontab 항목 정의
CRON_COMMENT="# Auto-fix errors scheduler (hantu_quant)"
CRON_SCHEDULE="0,30 * * * *"
CRON_COMMAND="$AUTO_FIX_SCRIPT"
CRON_ENTRY="$CRON_SCHEDULE $CRON_COMMAND"

# 환경변수 로드 설정 (cron에서 환경변수 사용을 위해)
ENV_LOADER="set -a; source $PROJECT_DIR/.env 2>/dev/null || true; set +a; "
CRON_ENTRY_FULL="$CRON_SCHEDULE ${ENV_LOADER}${CRON_COMMAND}"

# Log rotation cron entry
LOG_ROTATE_COMMENT="# Log rotation (hantu_quant)"
LOG_ROTATE_SCHEDULE="0 2 * * *"
LOG_ROTATE_COMMAND="cd $PROJECT_DIR && bash scripts/log_rotate.sh >> logs/log_rotate.log 2>&1"
LOG_ROTATE_ENTRY="$LOG_ROTATE_SCHEDULE $LOG_ROTATE_COMMAND"

# 기존 crontab 백업 및 확인
CURRENT_CRONTAB=$(crontab -l 2>/dev/null || echo "")

# 이미 등록되어 있는지 확인
if echo "$CURRENT_CRONTAB" | grep -q "auto-fix-errors.sh"; then
    log_warn "auto-fix-errors.sh가 이미 crontab에 등록되어 있습니다."
    log_info "기존 항목을 업데이트합니다."

    # 기존 항목 제거
    CURRENT_CRONTAB=$(echo "$CURRENT_CRONTAB" | grep -v "auto-fix-errors.sh" | grep -v "Auto-fix errors scheduler")
fi

# Remove existing log rotation entries if present
if echo "$CURRENT_CRONTAB" | grep -q "log_rotate.sh"; then
    log_warn "log_rotate.sh가 이미 crontab에 등록되어 있습니다."
    log_info "기존 항목을 업데이트합니다."

    # 기존 항목 제거
    CURRENT_CRONTAB=$(echo "$CURRENT_CRONTAB" | grep -v "log_rotate.sh" | grep -v "Log rotation")
fi

# 새 crontab 생성
NEW_CRONTAB="CRON_TZ=Asia/Seoul

$CURRENT_CRONTAB

$CRON_COMMENT
$CRON_ENTRY_FULL

$LOG_ROTATE_COMMENT
$LOG_ROTATE_ENTRY"

# crontab 등록
echo "$NEW_CRONTAB" | crontab -

log_info "Crontab 등록 완료!"
log_info ""
log_info "등록된 작업:"
log_info "1. 자동 에러 수정: 매일 24시간, 30분마다 (48회/일)"
log_info "2. 로그 정리: 매일 02:00 (압축/삭제)"
log_info ""
log_info "현재 crontab 내용:"
crontab -l | grep -E "(Auto-fix|Log rotation)" -A1 || true

log_info ""
log_info "타임존: Asia/Seoul (CRON_TZ 설정됨)"
log_info "환경변수는 $PROJECT_DIR/.env 에서 로드됩니다."
log_info "프로젝트 경로: $PROJECT_DIR"
