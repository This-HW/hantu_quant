#!/bin/bash
# Integration tests for deployment flow
# Tests end-to-end deployment process with pre-checks, state management, and retry logic

set -euo pipefail

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test fixtures
TEST_DIR="/tmp/test_deploy_integration_$$"
export STATE_FILE="${TEST_DIR}/.deploy_state.json"
TEST_ENV_FILE="${TEST_DIR}/.env"

# Track test results
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# Source deployment scripts
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../../scripts/deployment/state_manager.sh"

# Cleanup on exit
cleanup() {
    rm -rf "$TEST_DIR"
}
trap cleanup EXIT

# Setup test fixtures
setup_fixtures() {
    mkdir -p "$TEST_DIR"

    # Create test env file with all required vars
    cat > "$TEST_ENV_FILE" << EOF
DB_HOST=localhost
DB_USER=test_user
DB_PASSWORD=test_pass
DB_NAME=test_db
TELEGRAM_BOT_TOKEN=test_token
TELEGRAM_CHAT_ID=test_chat_id
EOF

    # Export vars for validation
    export DB_HOST=localhost
    export DB_USER=test_user
    export DB_PASSWORD=test_pass
    export DB_NAME=test_db
    export TELEGRAM_BOT_TOKEN=test_token
    export TELEGRAM_CHAT_ID=test_chat_id
}

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

# Mock deployment command (success)
mock_deploy_success() {
    echo "Mock deployment: SUCCESS"
    return 0
}

# Mock deployment command (failure)
mock_deploy_failure() {
    echo "Mock deployment: FAILURE"
    return 1
}

# Scenario 1: Initialize state file
test_scenario_init_state() {
    local test_name="Scenario 1: Initialize state file"

    # Remove state file if exists
    rm -f "$STATE_FILE"

    # Initialize
    init_state > /dev/null 2>&1

    # Verify state file exists
    if [[ ! -f "$STATE_FILE" ]]; then
        print_result "$test_name" "FAIL"
        echo "  Error: State file not created"
        return 1
    fi

    # Verify initial values
    local failures
    failures=$(get_consecutive_failures)

    if [[ "$failures" != "0" ]]; then
        print_result "$test_name" "FAIL"
        echo "  Error: Initial failures should be 0, got: $failures"
        return 1
    fi

    print_result "$test_name" "PASS"
    return 0
}

# Scenario 2: Run pre-deployment checks (memory + env)
test_scenario_pre_checks() {
    local test_name="Scenario 2: Pre-deployment checks"

    # This test verifies that validate_env.sh can be sourced and run
    # We skip actual memory check since it depends on system state

    # Load env vars
    source "$TEST_ENV_FILE"

    # Source validate_env.sh
    source "${SCRIPT_DIR}/../../scripts/deployment/validate_env.sh"

    # Run validation
    if validate_env_vars > /dev/null 2>&1; then
        print_result "$test_name" "PASS"
        return 0
    else
        print_result "$test_name" "FAIL"
        echo "  Error: Pre-deployment checks failed"
        return 1
    fi
}

# Scenario 3: Simulate deployment success
test_scenario_deploy_success() {
    local test_name="Scenario 3: Deployment success"

    # Initialize state
    rm -f "$STATE_FILE"
    init_state > /dev/null 2>&1

    # Simulate deployment
    if mock_deploy_success > /dev/null 2>&1; then
        update_state "success" "Mock deployment succeeded" > /dev/null 2>&1
    else
        update_state "failed" "Mock deployment failed" > /dev/null 2>&1
    fi

    # Verify state
    local failures
    failures=$(get_consecutive_failures)

    if [[ "$failures" != "0" ]]; then
        print_result "$test_name" "FAIL"
        echo "  Error: Failures should be 0 after success, got: $failures"
        return 1
    fi

    local last_status
    last_status=$(jq -r '.last_status' "$STATE_FILE")

    if [[ "$last_status" != "success" ]]; then
        print_result "$test_name" "FAIL"
        echo "  Error: last_status should be 'success', got: $last_status"
        return 1
    fi

    print_result "$test_name" "PASS"
    return 0
}

# Scenario 4: Simulate deployment failure
test_scenario_deploy_failure() {
    local test_name="Scenario 4: Deployment failure"

    # Initialize state
    rm -f "$STATE_FILE"
    init_state > /dev/null 2>&1

    # Simulate deployment failure
    if mock_deploy_failure > /dev/null 2>&1; then
        update_state "success" "Mock deployment succeeded" > /dev/null 2>&1
    else
        update_state "failed" "Mock deployment failed" > /dev/null 2>&1
    fi

    # Verify state
    local failures
    failures=$(get_consecutive_failures)

    if [[ "$failures" != "1" ]]; then
        print_result "$test_name" "FAIL"
        echo "  Error: Failures should be 1 after failure, got: $failures"
        return 1
    fi

    local last_status
    last_status=$(jq -r '.last_status' "$STATE_FILE")

    if [[ "$last_status" != "failed" ]]; then
        print_result "$test_name" "FAIL"
        echo "  Error: last_status should be 'failed', got: $last_status"
        return 1
    fi

    print_result "$test_name" "PASS"
    return 0
}

# Scenario 5: Test retry logic (2 failures then success)
test_scenario_retry_logic() {
    local test_name="Scenario 5: Retry logic (2 failures then success)"

    # Initialize state
    rm -f "$STATE_FILE"
    init_state > /dev/null 2>&1

    # Attempt 1: Failure
    if mock_deploy_failure > /dev/null 2>&1; then
        update_state "success" "Attempt 1" > /dev/null 2>&1
    else
        update_state "failed" "Attempt 1 failed" > /dev/null 2>&1
    fi

    local failures_1
    failures_1=$(get_consecutive_failures)

    if [[ "$failures_1" != "1" ]]; then
        print_result "$test_name" "FAIL"
        echo "  Error: After attempt 1, failures should be 1, got: $failures_1"
        return 1
    fi

    # Attempt 2: Failure (shortened wait for test - 2 seconds instead of 300)
    sleep 2
    if mock_deploy_failure > /dev/null 2>&1; then
        update_state "success" "Attempt 2" > /dev/null 2>&1
    else
        update_state "failed" "Attempt 2 failed" > /dev/null 2>&1
    fi

    local failures_2
    failures_2=$(get_consecutive_failures)

    if [[ "$failures_2" != "2" ]]; then
        print_result "$test_name" "FAIL"
        echo "  Error: After attempt 2, failures should be 2, got: $failures_2"
        return 1
    fi

    # Attempt 3: Success
    sleep 2
    if mock_deploy_success > /dev/null 2>&1; then
        update_state "success" "Attempt 3 succeeded" > /dev/null 2>&1
    else
        update_state "failed" "Attempt 3 failed" > /dev/null 2>&1
    fi

    local failures_3
    failures_3=$(get_consecutive_failures)

    if [[ "$failures_3" != "0" ]]; then
        print_result "$test_name" "FAIL"
        echo "  Error: After success, failures should be 0, got: $failures_3"
        return 1
    fi

    print_result "$test_name" "PASS"
    return 0
}

# Scenario 6: Verify alert triggering (≥2 failures)
test_scenario_alert_threshold() {
    local test_name="Scenario 6: Alert threshold (≥2 failures)"

    # Initialize state
    rm -f "$STATE_FILE"
    init_state > /dev/null 2>&1

    # First failure - should not trigger alert
    update_state "failed" "First failure" > /dev/null 2>&1
    local failures_1
    failures_1=$(get_consecutive_failures)

    if [[ "$failures_1" -ge 2 ]]; then
        print_result "$test_name" "FAIL"
        echo "  Error: Alert should not trigger at 1 failure"
        return 1
    fi

    # Second failure - should trigger alert
    update_state "failed" "Second failure" > /dev/null 2>&1
    local failures_2
    failures_2=$(get_consecutive_failures)

    if [[ "$failures_2" -lt 2 ]]; then
        print_result "$test_name" "FAIL"
        echo "  Error: Alert should trigger at ≥2 failures, got: $failures_2"
        return 1
    fi

    print_result "$test_name" "PASS"
    return 0
}

# Scenario 7: State resets on success after failures
test_scenario_state_reset() {
    local test_name="Scenario 7: State resets on success"

    # Initialize with 3 failures
    rm -f "$STATE_FILE"
    init_state > /dev/null 2>&1
    update_state "failed" "Failure 1" > /dev/null 2>&1
    update_state "failed" "Failure 2" > /dev/null 2>&1
    update_state "failed" "Failure 3" > /dev/null 2>&1

    # Verify failures
    local failures_before
    failures_before=$(get_consecutive_failures)

    if [[ "$failures_before" != "3" ]]; then
        print_result "$test_name" "FAIL"
        echo "  Error: Should have 3 failures before success, got: $failures_before"
        return 1
    fi

    # Now succeed
    update_state "success" "Deployment succeeded" > /dev/null 2>&1

    # Verify reset
    local failures_after
    failures_after=$(get_consecutive_failures)

    if [[ "$failures_after" != "0" ]]; then
        print_result "$test_name" "FAIL"
        echo "  Error: Failures should reset to 0 after success, got: $failures_after"
        return 1
    fi

    print_result "$test_name" "PASS"
    return 0
}

# Scenario 8: Verify state persistence across operations
test_scenario_state_persistence() {
    local test_name="Scenario 8: State persistence"

    # Initialize state
    rm -f "$STATE_FILE"
    init_state > /dev/null 2>&1

    # Add some failures
    update_state "failed" "Failure 1" > /dev/null 2>&1
    update_state "failed" "Failure 2" > /dev/null 2>&1

    # Get failures (this re-reads the file)
    local failures_1
    failures_1=$(get_consecutive_failures)

    # Get failures again (should be same)
    local failures_2
    failures_2=$(get_consecutive_failures)

    if [[ "$failures_1" != "$failures_2" ]]; then
        print_result "$test_name" "FAIL"
        echo "  Error: State not persistent. Got $failures_1 then $failures_2"
        return 1
    fi

    if [[ "$failures_1" != "2" ]]; then
        print_result "$test_name" "FAIL"
        echo "  Error: Expected 2 failures, got: $failures_1"
        return 1
    fi

    print_result "$test_name" "PASS"
    return 0
}

# Main test runner
main() {
    echo "=========================================="
    echo "Deployment Integration Tests"
    echo "=========================================="
    echo ""
    echo "Test directory: $TEST_DIR"
    echo "State file: $STATE_FILE"
    echo ""

    # Setup fixtures
    setup_fixtures

    echo "Running test scenarios..."
    echo ""

    # Run all test scenarios
    test_scenario_init_state
    test_scenario_pre_checks
    test_scenario_deploy_success
    test_scenario_deploy_failure
    test_scenario_retry_logic
    test_scenario_alert_threshold
    test_scenario_state_reset
    test_scenario_state_persistence

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
        echo -e "${GREEN}✓ All integration tests passed!${NC}"
        echo ""
        echo "Test scenarios covered:"
        echo "  1. State file initialization"
        echo "  2. Pre-deployment checks (env validation)"
        echo "  3. Deployment success handling"
        echo "  4. Deployment failure handling"
        echo "  5. Retry logic with multiple attempts"
        echo "  6. Alert triggering at ≥2 failures"
        echo "  7. State reset on success"
        echo "  8. State persistence"
        exit 0
    else
        echo -e "${RED}✗ Some integration tests failed${NC}"
        exit 1
    fi
}

# Run main
main
