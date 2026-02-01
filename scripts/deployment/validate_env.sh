#!/bin/bash
# Validate required environment variables

set -euo pipefail

# Required environment variables for deployment
# DB_PASSWORD는 .pgpass 파일로 관리 (환경변수 불필요)
REQUIRED_ENV_VARS=(
    "DB_HOST"
    "DB_USER"
    "DB_NAME"
    "TELEGRAM_BOT_TOKEN"
    "TELEGRAM_CHAT_ID"
)

# Optional environment variables (warnings only)
OPTIONAL_ENV_VARS=(
    "KIS_APP_KEY"
    "KIS_APP_SECRET"
    "KIS_ACCOUNT_NO"
    "API_SERVER_KEY"
)

# Color codes for output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

# Function to check if environment variable exists
check_env_var() {
    local var_name="$1"
    if [[ -z "${!var_name:-}" ]]; then
        return 1
    else
        return 0
    fi
}

# Function to check .pgpass file
check_pgpass_file() {
    local pgpass_file="$HOME/.pgpass"

    if [[ ! -f "$pgpass_file" ]]; then
        echo -e "${RED}✗${NC} .pgpass: Missing (REQUIRED)"
        echo "  생성 방법: echo 'localhost:5432:hantu_quant:hantu:PASSWORD' > ~/.pgpass && chmod 600 ~/.pgpass"
        return 1
    fi

    # Check permissions
    local perms=$(stat -c '%a' "$pgpass_file" 2>/dev/null || stat -f '%A' "$pgpass_file" 2>/dev/null)
    if [[ "$perms" != "600" ]]; then
        echo -e "${RED}✗${NC} .pgpass: Wrong permissions (Current: $perms, Required: 600)"
        echo "  수정 방법: chmod 600 ~/.pgpass"
        return 1
    fi

    echo -e "${GREEN}✓${NC} .pgpass: Exists with correct permissions (600)"
    return 0
}

# Main validation function
validate_env_vars() {
    local missing_vars=()
    local missing_optional=()
    local validation_failed=0

    echo "=========================================="
    echo "Environment Variable Validation"
    echo "=========================================="
    echo ""

    # Check .pgpass file first
    echo "Checking PostgreSQL authentication..."
    if ! check_pgpass_file; then
        validation_failed=1
    fi

    echo ""

    # Check required variables
    echo "Checking required variables..."
    for var in "${REQUIRED_ENV_VARS[@]}"; do
        if check_env_var "$var"; then
            echo -e "${GREEN}✓${NC} $var: Set"
        else
            echo -e "${RED}✗${NC} $var: Missing (REQUIRED)"
            missing_vars+=("$var")
            validation_failed=1
        fi
    done

    echo ""

    # Check optional variables
    echo "Checking optional variables..."
    for var in "${OPTIONAL_ENV_VARS[@]}"; do
        if check_env_var "$var"; then
            echo -e "${GREEN}✓${NC} $var: Set"
        else
            echo -e "${YELLOW}⚠${NC} $var: Missing (Optional)"
            missing_optional+=("$var")
        fi
    done

    echo ""
    echo "=========================================="

    # Print summary
    if [[ ${#missing_vars[@]} -eq 0 ]]; then
        echo -e "${GREEN}✓ All required environment variables are set${NC}"

        if [[ ${#missing_optional[@]} -gt 0 ]]; then
            echo -e "${YELLOW}⚠ Some optional variables are missing:${NC}"
            for var in "${missing_optional[@]}"; do
                echo "  - $var"
            done
        fi

        echo ""
        echo "Validation: PASSED"
        return 0
    else
        echo -e "${RED}✗ Missing required environment variables:${NC}"
        for var in "${missing_vars[@]}"; do
            echo "  - $var"
        done

        echo ""
        echo -e "${RED}Validation: FAILED${NC}"
        echo ""
        echo "To fix this issue:"
        echo "1. Copy .env.example to .env"
        echo "2. Fill in the missing variables"
        echo "3. Source the .env file: source .env"
        echo "4. Run validation again: $0"

        return 1
    fi
}

# Load .env file if exists (for manual testing)
load_env_file() {
    local env_file="${1:-.env}"

    if [[ -f "$env_file" ]]; then
        echo "Loading environment from: $env_file"
        # Export variables from .env file
        set -a
        # shellcheck disable=SC1090
        source "$env_file"
        set +a
        echo ""
    else
        echo "Note: .env file not found at: $env_file"
        echo "Checking environment variables from current shell..."
        echo ""
    fi
}

# Main execution
main() {
    local env_file="${1:-.env}"

    # Load .env if exists
    load_env_file "$env_file"

    # Run validation
    validate_env_vars
}

# Run if executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
