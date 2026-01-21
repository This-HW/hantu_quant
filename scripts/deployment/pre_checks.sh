#!/bin/bash
# Pre-deployment checks library
# Validates system resources and environment before deployment

set -euo pipefail
export TZ=Asia/Seoul

# Source required scripts
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/state_manager.sh"
source "${SCRIPT_DIR}/validate_env.sh"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
MEMORY_THRESHOLD_MB=200  # Adjusted for 1GB OCI Free Tier
MAX_RETRY_ATTEMPTS=3
RETRY_WAIT_SECONDS=300  # 5 minutes

# Logging with timestamp
log() {
    echo -e "[$(date '+%Y-%m-%d %H:%M:%S KST')] $1"
}

log_info() {
    log "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    log "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    log "${RED}[ERROR]${NC} $1"
}

# Clean up memory before deployment
cleanup_memory() {
    log_info "Cleaning up system memory..."

    local freed_mb=0

    # 1. Clear PageCache, dentries and inodes (safe operation)
    log_info "  → Clearing system caches..."
    if sudo sh -c 'sync; echo 3 > /proc/sys/vm/drop_caches' 2>/dev/null; then
        log_info "  ✓ System caches cleared"
    else
        log_warn "  ⚠ Could not clear system caches (need sudo)"
    fi

    # 2. Remove old rotated logs (older than 30 days)
    log_info "  → Removing old logs..."
    local logs_removed=0
    if [ -d "/opt/hantu_quant/logs" ]; then
        logs_removed=$(find /opt/hantu_quant/logs -name "*.log.gz" -mtime +30 -delete -print 2>/dev/null | wc -l || echo 0)
        if [ "$logs_removed" -gt 0 ]; then
            log_info "  ✓ Removed $logs_removed old log files"
        else
            log_info "  ✓ No old logs to remove"
        fi
    fi

    # 3. Clear Python cache files
    log_info "  → Clearing Python cache..."
    local cache_removed=0
    if [ -d "/opt/hantu_quant" ]; then
        cache_removed=$(find /opt/hantu_quant -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null; echo $?)
        find /opt/hantu_quant -type f -name "*.pyc" -delete 2>/dev/null || true
        log_info "  ✓ Python cache cleared"
    fi

    # 4. Show memory improvement
    sleep 1  # Give system time to reclaim memory
    local available_after
    available_after=$(free -m | awk 'NR==2 {print $7}')
    log_info "✓ Memory cleanup complete"
    log_info "  Available memory: ${available_after} MB"

    return 0
}

# Check available memory
check_memory_availability() {
    log_info "Checking memory availability..."

    # Get available memory in MB
    local available_mb
    available_mb=$(free -m | awk 'NR==2 {print $7}')

    log_info "Available memory: ${available_mb} MB (Threshold: ${MEMORY_THRESHOLD_MB} MB)"

    if [[ "$available_mb" -lt "$MEMORY_THRESHOLD_MB" ]]; then
        log_error "Insufficient memory: ${available_mb} MB < ${MEMORY_THRESHOLD_MB} MB"
        return 1
    fi

    log_info "Memory check passed: ${available_mb} MB available"
    return 0
}

# Run all pre-deployment checks
run_pre_deployment_checks() {
    log_info "=========================================="
    log_info "Pre-deployment Checks Started"
    log_info "=========================================="

    local check_failed=0

    # Check 0: Memory cleanup (proactive)
    log_info ""
    log_info "Step 0: Memory Cleanup"
    log_info "------------------------------------------"
    cleanup_memory

    # Check 1: Memory availability
    log_info ""
    log_info "Check 1: Memory Availability"
    log_info "------------------------------------------"
    if ! check_memory_availability; then
        log_error "Memory availability check failed"
        check_failed=1
    fi

    # Check 2: Environment variables validation
    log_info ""
    log_info "Check 2: Environment Variables"
    log_info "------------------------------------------"
    if ! bash "${SCRIPT_DIR}/validate_env.sh"; then
        log_error "Environment variables validation failed"
        check_failed=1
    fi

    # Summary
    log_info ""
    log_info "=========================================="
    if [[ "$check_failed" -eq 0 ]]; then
        log_info "${GREEN}✓ All pre-deployment checks passed${NC}"
        log_info "=========================================="
        return 0
    else
        log_error "${RED}✗ Pre-deployment checks failed${NC}"
        log_info "=========================================="
        return 1
    fi
}

# Deploy with retry logic
deploy_with_retry() {
    local deploy_command="$1"
    local attempt=1

    log_info "Starting deployment with retry (max ${MAX_RETRY_ATTEMPTS} attempts)"

    while [[ "$attempt" -le "$MAX_RETRY_ATTEMPTS" ]]; do
        log_info ""
        log_info "=========================================="
        log_info "Deployment Attempt ${attempt}/${MAX_RETRY_ATTEMPTS}"
        log_info "=========================================="

        # Update state with attempt count
        local temp_file="${STATE_FILE}.tmp"
        jq --arg attempt "$attempt" \
           '.deploy_attempt = ($attempt | tonumber)' \
           "$STATE_FILE" > "$temp_file" 2>/dev/null || echo '{"deploy_attempt": 1}' > "$temp_file"
        mv "$temp_file" "$STATE_FILE"

        # Execute deployment
        if eval "$deploy_command"; then
            log_info "${GREEN}✓ Deployment successful on attempt ${attempt}${NC}"
            update_state "success" "Deployment succeeded on attempt ${attempt}"
            return 0
        else
            local exit_code=$?
            log_error "Deployment failed on attempt ${attempt} (exit code: ${exit_code})"
            update_state "failed" "Deployment failed on attempt ${attempt}"

            # Send alert via Python Telegram API
            local failures
            failures=$(get_consecutive_failures)

            python3 -c "
from core.utils.telegram_notifier import get_telegram_notifier
notifier = get_telegram_notifier()
notifier.send_deployment_failure_alert(
    ${failures},
    {
        'commit': 'Attempt ${attempt}/${MAX_RETRY_ATTEMPTS}',
        'branch': 'main',
        'last_success': '$(get_last_success)',
        'reason': 'Deployment command failed (exit code: ${exit_code})'
    }
)
" 2>/dev/null || log_warn "Failed to send Telegram alert"

            # Check if we should retry
            if [[ "$attempt" -lt "$MAX_RETRY_ATTEMPTS" ]]; then
                log_warn "Waiting ${RETRY_WAIT_SECONDS} seconds before retry..."
                sleep "$RETRY_WAIT_SECONDS"

                # Check memory before retry
                log_info "Checking system resources before retry..."
                if ! check_memory_availability; then
                    log_error "Insufficient memory for retry"

                    # Send memory overflow alert
                    local available_mb
                    available_mb=$(free -m | awk 'NR==2 {print $7}')

                    python3 -c "
from core.utils.telegram_notifier import get_telegram_notifier
notifier = get_telegram_notifier()
notifier.send_memory_overflow_alert(
    ${available_mb},
    ${MEMORY_THRESHOLD_MB},
    ${attempt}
)
" 2>/dev/null || log_warn "Failed to send memory overflow alert"

                    # Wait longer for memory to free up
                    log_warn "Waiting additional time for memory recovery..."
                    sleep 60
                fi

                attempt=$((attempt + 1))
            else
                log_error "${RED}✗ All deployment attempts failed (${MAX_RETRY_ATTEMPTS}/${MAX_RETRY_ATTEMPTS})${NC}"
                return 1
            fi
        fi
    done

    return 1
}

# Main execution (if run directly)
main() {
    local command="${1:-help}"

    case "$command" in
        check-memory)
            check_memory_availability
            ;;
        check-all)
            run_pre_deployment_checks
            ;;
        deploy-with-retry)
            shift
            deploy_with_retry "$@"
            ;;
        help|*)
            cat << EOF
Usage: $0 <command> [args]

Commands:
  check-memory           Check memory availability
  check-all              Run all pre-deployment checks (includes memory cleanup)
  deploy-with-retry <cmd> Deploy with retry logic (max ${MAX_RETRY_ATTEMPTS} attempts)
  help                   Show this help message

Configuration:
  MEMORY_THRESHOLD_MB    Minimum available memory (default: ${MEMORY_THRESHOLD_MB} MB)
  MAX_RETRY_ATTEMPTS     Maximum retry attempts (default: ${MAX_RETRY_ATTEMPTS})
  RETRY_WAIT_SECONDS     Wait time between retries (default: ${RETRY_WAIT_SECONDS}s)

Features:
  - Automatic memory cleanup before deployment (clears caches, old logs, Python cache)
  - Consecutive failure tracking with Telegram alerts
  - Retry logic with configurable wait times

Examples:
  $0 check-memory
  $0 check-all
  $0 deploy-with-retry "./deploy.sh"
EOF
            ;;
    esac
}

# Run main if executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
