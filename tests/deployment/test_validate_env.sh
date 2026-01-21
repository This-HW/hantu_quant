#!/bin/bash
# Unit tests for validate_env.sh
# Tests environment variable validation functionality

set -euo pipefail

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test env file (use temp directory)
TEST_ENV_FILE="/tmp/test_env_$$.env"

# Track test results
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# Cleanup on exit
cleanup() {
    rm -f "$TEST_ENV_FILE"
    # Unset test environment variables
    unset DB_HOST DB_USER DB_PASSWORD DB_NAME TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID
    unset KIS_APP_KEY KIS_APP_SECRET KIS_ACCOUNT_NO API_SERVER_KEY
}
trap cleanup EXIT

# Print test result
print_result() {
    local test_name="$1"
    local result="$2"

    TOTAL_TESTS=$((TOTAL_TESTS + 1))

    if [[ "$result" == "PASS" ]]; then
        echo -e "${GREEN}✓ PASS${NC}: $test_name"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    elif [[ "$result" == "FAIL" ]]; then
        echo -e "${RED}✗ FAIL${NC}: $test_name"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    else
        echo -e "${YELLOW}⊘ SKIP${NC}: $test_name"
    fi
}

# Source the validate_env script (without running main)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../../scripts/deployment/validate_env.sh"

# Test: All required vars present
test_all_required_present() {
    local test_name="test_all_required_present"

    # Create env file with all required vars
    cat > "$TEST_ENV_FILE" << EOF
DB_HOST=localhost
DB_USER=test_user
DB_PASSWORD=test_pass
DB_NAME=test_db
TELEGRAM_BOT_TOKEN=test_token
TELEGRAM_CHAT_ID=test_chat_id
EOF

    # Load and validate
    load_env_file "$TEST_ENV_FILE" > /dev/null 2>&1

    if validate_env_vars > /dev/null 2>&1; then
        print_result "$test_name" "PASS"
        return 0
    else
        print_result "$test_name" "FAIL"
        echo "  Error: Validation should pass with all required vars"
        return 1
    fi
}

# Test: Missing required var
test_missing_required_var() {
    local test_name="test_missing_required_var"

    # Unset all vars first
    cleanup

    # Create env file missing DB_PASSWORD
    cat > "$TEST_ENV_FILE" << EOF
DB_HOST=localhost
DB_USER=test_user
DB_NAME=test_db
TELEGRAM_BOT_TOKEN=test_token
TELEGRAM_CHAT_ID=test_chat_id
EOF

    # Load env file
    load_env_file "$TEST_ENV_FILE" > /dev/null 2>&1

    # Validation should fail
    if validate_env_vars > /dev/null 2>&1; then
        print_result "$test_name" "FAIL"
        echo "  Error: Validation should fail with missing required var"
        return 1
    else
        print_result "$test_name" "PASS"
        return 0
    fi
}

# Test: Missing optional var (warning but success)
test_missing_optional_var() {
    local test_name="test_missing_optional_var"

    # Unset all vars first
    cleanup

    # Create env file with required vars only (no optional)
    cat > "$TEST_ENV_FILE" << EOF
DB_HOST=localhost
DB_USER=test_user
DB_PASSWORD=test_pass
DB_NAME=test_db
TELEGRAM_BOT_TOKEN=test_token
TELEGRAM_CHAT_ID=test_chat_id
EOF

    # Load and validate
    load_env_file "$TEST_ENV_FILE" > /dev/null 2>&1

    # Should pass even with missing optional vars
    if validate_env_vars > /dev/null 2>&1; then
        print_result "$test_name" "PASS"
        return 0
    else
        print_result "$test_name" "FAIL"
        echo "  Error: Validation should pass with missing optional vars"
        return 1
    fi
}

# Test: Empty env file
test_empty_env_file() {
    local test_name="test_empty_env_file"

    # Unset all vars first
    cleanup

    # Create empty env file
    echo "" > "$TEST_ENV_FILE"

    # Load env file
    load_env_file "$TEST_ENV_FILE" > /dev/null 2>&1

    # Validation should fail
    if validate_env_vars > /dev/null 2>&1; then
        print_result "$test_name" "FAIL"
        echo "  Error: Validation should fail with empty env file"
        return 1
    else
        print_result "$test_name" "PASS"
        return 0
    fi
}

# Test: Check color output for missing required var
test_color_output_missing() {
    local test_name="test_color_output_missing"

    # Unset all vars first
    cleanup

    # Create env file missing required var
    cat > "$TEST_ENV_FILE" << EOF
DB_HOST=localhost
DB_USER=test_user
DB_NAME=test_db
TELEGRAM_BOT_TOKEN=test_token
TELEGRAM_CHAT_ID=test_chat_id
EOF

    # Load env file
    load_env_file "$TEST_ENV_FILE" > /dev/null 2>&1

    # Capture output
    local output
    output=$(validate_env_vars 2>&1 || true)

    # Check for red color code (error indicator)
    if echo "$output" | grep -q "DB_PASSWORD"; then
        print_result "$test_name" "PASS"
        return 0
    else
        print_result "$test_name" "FAIL"
        echo "  Error: Output should mention missing DB_PASSWORD"
        return 1
    fi
}

# Test: All vars including optional
test_all_vars_present() {
    local test_name="test_all_vars_present"

    # Create env file with all vars (required + optional)
    cat > "$TEST_ENV_FILE" << EOF
DB_HOST=localhost
DB_USER=test_user
DB_PASSWORD=test_pass
DB_NAME=test_db
TELEGRAM_BOT_TOKEN=test_token
TELEGRAM_CHAT_ID=test_chat_id
KIS_APP_KEY=test_app_key
KIS_APP_SECRET=test_app_secret
KIS_ACCOUNT_NO=test_account
API_SERVER_KEY=test_api_key
EOF

    # Load and validate
    load_env_file "$TEST_ENV_FILE" > /dev/null 2>&1

    # Should pass
    if validate_env_vars > /dev/null 2>&1; then
        print_result "$test_name" "PASS"
        return 0
    else
        print_result "$test_name" "FAIL"
        echo "  Error: Validation should pass with all vars"
        return 1
    fi
}

# Main test runner
main() {
    echo "=========================================="
    echo "Validate Env Unit Tests"
    echo "=========================================="
    echo ""
    echo "Test env file: $TEST_ENV_FILE"
    echo ""

    # Run all tests
    test_all_required_present
    test_missing_required_var
    test_missing_optional_var
    test_empty_env_file
    test_color_output_missing
    test_all_vars_present

    # Print summary
    echo ""
    echo "=========================================="
    echo "Test Summary"
    echo "=========================================="
    echo "Total:  $TOTAL_TESTS"
    echo -e "Passed: ${GREEN}$PASSED_TESTS${NC}"
    echo -e "Failed: ${RED}$FAILED_TESTS${NC}"
    echo ""

    if [[ "$FAILED_TESTS" -eq 0 ]]; then
        echo -e "${GREEN}✓ All tests passed!${NC}"
        exit 0
    else
        echo -e "${RED}✗ Some tests failed${NC}"
        exit 1
    fi
}

# Run main
main
