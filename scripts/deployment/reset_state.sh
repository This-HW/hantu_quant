#!/bin/bash
# Reset deployment state
# Simple wrapper to reset consecutive failures counter

set -euo pipefail
export TZ=Asia/Seoul

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source state manager
source "${SCRIPT_DIR}/state_manager.sh"

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "Deployment State Reset"
echo "=========================================="
echo ""

# Show current state before reset
echo "Current state:"
get_state | jq '.'
echo ""

# Confirm reset
read -p "Are you sure you want to reset the deployment state? (y/N): " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Reset cancelled."
    exit 0
fi

# Perform reset
echo "Resetting deployment state..."
reset_state

echo ""
echo -e "${GREEN}✓ Deployment state has been reset${NC}"
echo ""

# Show new state
echo "New state:"
get_state | jq '.'

echo ""
echo -e "${YELLOW}Note:${NC} This resets the consecutive failures counter to 0."
echo "      Use this after manually fixing deployment issues."
echo ""
echo "=========================================="
