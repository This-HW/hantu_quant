#!/bin/bash
# Log rotation script

set -euo pipefail
export TZ=Asia/Seoul

# Configuration
LOG_DIR="${LOG_DIR:-/opt/hantu_quant/logs}"
MAX_AGE_DAYS="${MAX_AGE_DAYS:-30}"
COMPRESS_AGE_DAYS="${COMPRESS_AGE_DAYS:-7}"
DISK_WARN_THRESHOLD="${DISK_WARN_THRESHOLD:-90}"
ROTATION_LOG="${LOG_DIR}/log_rotate.log"

# Logging functions
log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[${timestamp}] [${level}] ${message}" | tee -a "$ROTATION_LOG"
}

log_info() {
    log "INFO" "$@"
}

log_warn() {
    log "WARN" "$@"
}

log_error() {
    log "ERROR" "$@"
}

# Check if directory exists
check_log_directory() {
    if [[ ! -d "$LOG_DIR" ]]; then
        log_error "Log directory does not exist: $LOG_DIR"
        return 1
    fi
}

# Compress logs older than COMPRESS_AGE_DAYS
compress_old_logs() {
    log_info "Compressing logs older than ${COMPRESS_AGE_DAYS} days..."

    local compressed_count=0
    local failed_count=0

    # Find uncompressed log files older than COMPRESS_AGE_DAYS
    while IFS= read -r -d '' logfile; do
        if gzip -9 "$logfile" 2>/dev/null; then
            log_info "Compressed: ${logfile}"
            ((compressed_count++))
        else
            log_error "Failed to compress: ${logfile}"
            ((failed_count++))
        fi
    done < <(find "$LOG_DIR" -type f -name "*.log" -mtime +"$COMPRESS_AGE_DAYS" -not -name "log_rotate.log" -print0)

    log_info "Compression complete: ${compressed_count} files compressed, ${failed_count} failed"
}

# Delete logs older than MAX_AGE_DAYS
delete_old_logs() {
    log_info "Deleting logs older than ${MAX_AGE_DAYS} days..."

    local deleted_count=0
    local failed_count=0

    # Find compressed logs older than MAX_AGE_DAYS
    while IFS= read -r -d '' logfile; do
        if rm -f "$logfile" 2>/dev/null; then
            log_info "Deleted: ${logfile}"
            ((deleted_count++))
        else
            log_error "Failed to delete: ${logfile}"
            ((failed_count++))
        fi
    done < <(find "$LOG_DIR" -type f \( -name "*.log.gz" -o -name "*.log" \) -mtime +"$MAX_AGE_DAYS" -not -name "log_rotate.log" -print0)

    log_info "Deletion complete: ${deleted_count} files deleted, ${failed_count} failed"
}

# Check disk usage
check_disk_usage() {
    log_info "Checking disk usage..."

    local partition
    partition=$(df "$LOG_DIR" | tail -1 | awk '{print $1}')

    local usage_percent
    usage_percent=$(df "$LOG_DIR" | tail -1 | awk '{print $5}' | sed 's/%//')

    local used_gb
    used_gb=$(df -h "$LOG_DIR" | tail -1 | awk '{print $3}')

    local avail_gb
    avail_gb=$(df -h "$LOG_DIR" | tail -1 | awk '{print $4}')

    log_info "Partition: ${partition}, Usage: ${usage_percent}%, Used: ${used_gb}, Available: ${avail_gb}"

    if [[ "$usage_percent" -ge "$DISK_WARN_THRESHOLD" ]]; then
        log_warn "Disk usage is ${usage_percent}% (threshold: ${DISK_WARN_THRESHOLD}%)"

        # Send Telegram alert if available
        if command -v python3 &> /dev/null && [[ -f "/opt/hantu_quant/core/utils/telegram_notifier.py" ]]; then
            python3 - << EOF
import sys
sys.path.insert(0, '/opt/hantu_quant')
from core.utils.telegram_notifier import TelegramNotifier
notifier = TelegramNotifier()
notifier.send_message(
    "⚠️ Disk Usage Warning\\n\\n"
    f"Partition: ${partition}\\n"
    f"Usage: ${usage_percent}%\\n"
    f"Used: ${used_gb}\\n"
    f"Available: ${avail_gb}\\n\\n"
    "Please check log files and clean up if necessary."
)
EOF
        fi

        return 1
    else
        log_info "Disk usage is within acceptable range"
        return 0
    fi
}

# Get log directory size
get_log_directory_size() {
    local size_mb
    size_mb=$(du -sm "$LOG_DIR" 2>/dev/null | awk '{print $1}')
    echo "$size_mb"
}

# Main rotation process
rotate_logs() {
    local start_time
    start_time=$(date '+%Y-%m-%d %H:%M:%S')

    log_info "=========================================="
    log_info "Log rotation started"
    log_info "Log directory: $LOG_DIR"
    log_info "Compress age: ${COMPRESS_AGE_DAYS} days"
    log_info "Delete age: ${MAX_AGE_DAYS} days"
    log_info "=========================================="

    # Check directory
    if ! check_log_directory; then
        log_error "Log rotation aborted: directory check failed"
        exit 1
    fi

    # Get initial size
    local initial_size
    initial_size=$(get_log_directory_size)
    log_info "Initial log directory size: ${initial_size} MB"

    # Compress old logs
    compress_old_logs

    # Delete very old logs
    delete_old_logs

    # Get final size
    local final_size
    final_size=$(get_log_directory_size)
    log_info "Final log directory size: ${final_size} MB"

    local freed_mb=$((initial_size - final_size))
    log_info "Freed space: ${freed_mb} MB"

    # Check disk usage
    check_disk_usage || log_warn "Disk usage check completed with warnings"

    local end_time
    end_time=$(date '+%Y-%m-%d %H:%M:%S')

    log_info "Log rotation completed"
    log_info "Start: ${start_time}"
    log_info "End: ${end_time}"
    log_info "=========================================="
}

# Main execution
main() {
    # Ensure rotation log directory exists
    mkdir -p "$(dirname "$ROTATION_LOG")"

    # Run rotation
    rotate_logs
}

# Run if executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
