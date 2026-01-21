#!/bin/bash
# State management for deployment tracking

set -euo pipefail

STATE_FILE="${STATE_FILE:-/opt/hantu_quant/.deploy_state.json}"

# Initialize state file
init_state() {
    local state_dir
    state_dir=$(dirname "$STATE_FILE")

    # Create directory if not exists
    if [[ ! -d "$state_dir" ]]; then
        mkdir -p "$state_dir"
    fi

    # Create initial state if file doesn't exist
    if [[ ! -f "$STATE_FILE" ]]; then
        local temp_file="${STATE_FILE}.tmp"
        cat > "$temp_file" << EOF
{
  "consecutive_failures": 0,
  "last_success": null,
  "last_attempt": null,
  "attempts": 0
}
EOF
        mv "$temp_file" "$STATE_FILE"
        echo "State file initialized: $STATE_FILE"
    fi
}

# Update state on deployment attempt
update_state() {
    local status="$1"  # "success" or "failed"
    local reason="${2:-}"

    # Initialize if not exists
    init_state

    local temp_file="${STATE_FILE}.tmp"
    local now
    now=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    if [[ "$status" == "success" ]]; then
        # Success: reset consecutive failures, update last_success
        jq --arg now "$now" \
           --arg reason "$reason" \
           '.consecutive_failures = 0 |
            .last_success = $now |
            .last_attempt = $now |
            .attempts += 1 |
            .last_status = "success" |
            .last_reason = $reason' \
            "$STATE_FILE" > "$temp_file"
    elif [[ "$status" == "failed" ]]; then
        # Failure: increment consecutive failures
        jq --arg now "$now" \
           --arg reason "$reason" \
           '.consecutive_failures += 1 |
            .last_attempt = $now |
            .attempts += 1 |
            .last_status = "failed" |
            .last_reason = $reason' \
            "$STATE_FILE" > "$temp_file"
    else
        echo "Error: Invalid status '$status'. Must be 'success' or 'failed'." >&2
        return 1
    fi

    # Atomic write
    mv "$temp_file" "$STATE_FILE"
}

# Get consecutive failures count
get_consecutive_failures() {
    # Initialize if not exists
    init_state

    jq -r '.consecutive_failures' "$STATE_FILE"
}

# Get last success timestamp
get_last_success() {
    init_state
    jq -r '.last_success' "$STATE_FILE"
}

# Get last attempt timestamp
get_last_attempt() {
    init_state
    jq -r '.last_attempt' "$STATE_FILE"
}

# Get total attempts count
get_attempts() {
    init_state
    jq -r '.attempts' "$STATE_FILE"
}

# Get full state as JSON
get_state() {
    init_state
    cat "$STATE_FILE"
}

# Reset state (manual command)
reset_state() {
    init_state

    local temp_file="${STATE_FILE}.tmp"

    jq '.consecutive_failures = 0 |
        .last_status = "reset" |
        .last_reason = "Manual reset"' \
        "$STATE_FILE" > "$temp_file"

    mv "$temp_file" "$STATE_FILE"
    echo "State reset successfully"
}

# Main command dispatcher
main() {
    local command="${1:-help}"

    case "$command" in
        init)
            init_state
            ;;
        update)
            shift
            update_state "$@"
            ;;
        get-failures)
            get_consecutive_failures
            ;;
        get-success)
            get_last_success
            ;;
        get-attempt)
            get_last_attempt
            ;;
        get-attempts)
            get_attempts
            ;;
        get-state)
            get_state
            ;;
        reset)
            reset_state
            ;;
        help|*)
            cat << EOF
Usage: $0 <command> [args]

Commands:
  init                    Initialize state file
  update <status> [reason]  Update state (status: success|failed)
  get-failures            Get consecutive failures count
  get-success             Get last success timestamp
  get-attempt             Get last attempt timestamp
  get-attempts            Get total attempts count
  get-state               Get full state as JSON
  reset                   Reset consecutive failures to 0
  help                    Show this help message

Environment Variables:
  STATE_FILE              Path to state file (default: /opt/hantu_quant/.deploy_state.json)

Examples:
  $0 init
  $0 update success "Deployment completed"
  $0 update failed "Build failed"
  $0 get-failures
  $0 reset
EOF
            ;;
    esac
}

# Run main if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
