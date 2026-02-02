#!/bin/bash

# SSH Tunnel Management Script for PostgreSQL
# Manages SSH tunnel to remote PostgreSQL server for local development
#
# Usage:
#   ./scripts/db-tunnel.sh {start|stop|restart|status}
#
# Environment variable overrides:
#   SSH_KEY - Override default SSH key path
#     Example: SSH_KEY=~/.ssh/custom_key ./scripts/db-tunnel.sh start

set -euo pipefail
export TZ=Asia/Seoul

# Configuration
REMOTE_HOST="ubuntu@158.180.87.156"
SSH_KEY="${SSH_KEY:-${HOME}/.ssh/id_rsa}"
LOCAL_PORT="15432"
REMOTE_PORT="5432"
PID_FILE="/tmp/db-tunnel.pid"
LOG_FILE="logs/db-tunnel.log"

# Colors for output (only if terminal supports it)
if [[ -t 1 ]]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    NC='\033[0m' # No Color
else
    RED=''
    GREEN=''
    YELLOW=''
    NC=''
fi

# Logging functions
log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[${timestamp}] [${level}] ${message}" | tee -a "$LOG_FILE"
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

# Check if SSH key exists
check_ssh_key() {
    if [[ ! -f "$SSH_KEY" ]]; then
        log_error "SSH key not found: $SSH_KEY"
        echo -e "${RED}❌ SSH key not found: $SSH_KEY${NC}"
        echo "Please ensure your SSH key is properly configured."
        return 1
    fi
    log_info "SSH key found: $SSH_KEY"
    return 0
}

# Check if port is in use
check_port() {
    local port="$1"
    if lsof -Pi :${port} -sTCP:LISTEN -t >/dev/null 2>&1; then
        return 0  # Port is in use
    else
        return 1  # Port is free
    fi
}

# Get tunnel process PID
get_tunnel_pid() {
    if [[ -f "$PID_FILE" ]]; then
        cat "$PID_FILE"
    else
        echo ""
    fi
}

# Check if tunnel is running
is_tunnel_running() {
    local pid
    pid=$(get_tunnel_pid)

    if [[ -z "$pid" ]]; then
        return 1  # No PID file
    fi

    # Check if process is actually running
    if ps -p "$pid" > /dev/null 2>&1; then
        # Verify it's our SSH tunnel
        if ps -p "$pid" -o command= | grep -q "ssh.*${LOCAL_PORT}:localhost:${REMOTE_PORT}"; then
            return 0  # Running
        fi
    fi

    # PID file exists but process is not running - clean up
    rm -f "$PID_FILE"
    return 1  # Not running
}

# Start SSH tunnel
start_tunnel() {
    log_info "Starting SSH tunnel..."

    # Check if already running
    if is_tunnel_running; then
        local pid
        pid=$(get_tunnel_pid)
        echo -e "${YELLOW}⭕ SSH tunnel is already running (PID: $pid)${NC}"
        log_warn "Attempted to start tunnel, but it's already running (PID: $pid)"
        return 0
    fi

    # Check SSH key
    if ! check_ssh_key; then
        return 1
    fi

    # Check if port is already in use by another process
    if check_port "$LOCAL_PORT"; then
        echo -e "${RED}❌ Port $LOCAL_PORT is already in use by another process${NC}"
        log_error "Port $LOCAL_PORT is already in use"
        echo "Please check: lsof -i :$LOCAL_PORT"
        return 1
    fi

    # Create logs directory if it doesn't exist
    mkdir -p "$(dirname "$LOG_FILE")"

    # Start SSH tunnel in background
    log_info "Starting SSH tunnel: localhost:${LOCAL_PORT} -> remote:${REMOTE_PORT}"

    if ssh -i "$SSH_KEY" -f -N -L ${LOCAL_PORT}:localhost:${REMOTE_PORT} ${REMOTE_HOST} 2>> "$LOG_FILE"; then
        # Get PID of the SSH tunnel
        sleep 1  # Wait a moment for the process to fully start
        local pid
        pid=$(pgrep -f "ssh.*${LOCAL_PORT}:localhost:${REMOTE_PORT}.*${REMOTE_HOST}" | head -1)

        if [[ -z "$pid" ]]; then
            echo -e "${RED}❌ Failed to get tunnel PID${NC}"
            log_error "Failed to get tunnel PID after successful SSH start"
            return 1
        fi

        echo "$pid" > "$PID_FILE"
        echo -e "${GREEN}✅ SSH tunnel started successfully (PID: $pid)${NC}"
        log_info "SSH tunnel started successfully (PID: $pid)"
        echo "   Local:  localhost:$LOCAL_PORT"
        echo "   Remote: ${REMOTE_HOST}:${REMOTE_PORT}"
        echo ""
        echo "Test connection with:"
        echo "   psql -h localhost -p $LOCAL_PORT -U hantu -d hantu_quant"
        return 0
    else
        echo -e "${RED}❌ Failed to start SSH tunnel${NC}"
        log_error "Failed to start SSH tunnel - check $LOG_FILE for details"
        echo "Check log file: $LOG_FILE"
        return 1
    fi
}

# Stop SSH tunnel
stop_tunnel() {
    log_info "Stopping SSH tunnel..."

    if ! is_tunnel_running; then
        echo -e "${YELLOW}⭕ SSH tunnel is not running${NC}"
        log_warn "Attempted to stop tunnel, but it's not running"
        # Clean up PID file if it exists
        rm -f "$PID_FILE"
        return 0
    fi

    local pid
    pid=$(get_tunnel_pid)

    log_info "Killing SSH tunnel process (PID: $pid)"
    if kill "$pid" 2>> "$LOG_FILE"; then
        rm -f "$PID_FILE"
        echo -e "${GREEN}✅ SSH tunnel stopped successfully${NC}"
        log_info "SSH tunnel stopped successfully (PID: $pid)"
        return 0
    else
        echo -e "${RED}❌ Failed to stop SSH tunnel${NC}"
        log_error "Failed to kill process (PID: $pid)"
        return 1
    fi
}

# Show tunnel status
show_status() {
    echo "SSH Tunnel Status"
    echo "=================="
    echo "Remote: ${REMOTE_HOST}:${REMOTE_PORT}"
    echo "Local:  localhost:${LOCAL_PORT}"
    echo ""

    if is_tunnel_running; then
        local pid
        pid=$(get_tunnel_pid)
        echo -e "Status: ${GREEN}✅ Running${NC}"
        echo "PID:    $pid"
        echo ""
        echo "Process details:"
        ps -p "$pid" -o pid,etime,command | tail -n 1
        echo ""
        echo "Port status:"
        lsof -i :${LOCAL_PORT} | head -2
    else
        echo -e "Status: ${RED}❌ Not running${NC}"

        # Check if port is in use by another process
        if check_port "$LOCAL_PORT"; then
            echo ""
            echo -e "${YELLOW}⚠️ Warning: Port $LOCAL_PORT is in use by another process:${NC}"
            lsof -i :${LOCAL_PORT}
        fi
    fi

    echo ""
    echo "Log file: $LOG_FILE"
}

# Restart tunnel
restart_tunnel() {
    log_info "Restarting SSH tunnel..."
    echo "Restarting SSH tunnel..."
    echo ""

    if is_tunnel_running; then
        stop_tunnel
        sleep 1
    fi

    start_tunnel
}

# Show usage
show_usage() {
    cat << EOF
Usage: $0 {start|stop|restart|status}

Commands:
  start     Start SSH tunnel to PostgreSQL server
  stop      Stop SSH tunnel
  restart   Restart SSH tunnel
  status    Show tunnel status

Configuration:
  Remote:   ${REMOTE_HOST}:${REMOTE_PORT}
  Local:    localhost:${LOCAL_PORT}
  SSH Key:  $SSH_KEY
  PID File: $PID_FILE
  Log File: $LOG_FILE

Examples:
  $0 start    # Start tunnel
  $0 status   # Check if running
  $0 stop     # Stop tunnel

After starting the tunnel, connect to PostgreSQL with:
  psql -h localhost -p $LOCAL_PORT -U hantu -d hantu_quant

Or use in Python:
  DATABASE_URL=postgresql://hantu@localhost:$LOCAL_PORT/hantu_quant
  # Password authentication uses ~/.pgpass file
EOF
}

# Main execution
main() {
    if [[ $# -eq 0 ]]; then
        show_usage
        exit 1
    fi

    case "$1" in
        start)
            start_tunnel
            exit $?
            ;;
        stop)
            stop_tunnel
            exit $?
            ;;
        restart)
            restart_tunnel
            exit $?
            ;;
        status)
            show_status
            exit 0
            ;;
        *)
            echo "Error: Unknown command '$1'"
            echo ""
            show_usage
            exit 1
            ;;
    esac
}

# Run if executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
