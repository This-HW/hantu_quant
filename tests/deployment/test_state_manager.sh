#!/bin/bash
# Unit tests for state_manager.sh
# Tests state management functions including init, update, get, and reset

set -euo pipefail

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test state file (use temp directory)
export STATE_FILE="/tmp/test_state_manager_$$.json"

# Track test results
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# Source the state manager (without running main)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../../scripts/deployment/state_manager.sh"

# Cleanup on exit
cleanup() {
    rm -f "$STATE_FILE" "${STATE_FILE}.tmp"
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

# Test: Initialize state file
test_init_state() {
    local test_name="test_init_state"

    # Remove state file if exists
    rm -f "$STATE_FILE"

    # Run init
    init_state > /dev/null 2>&1

    # Verify file was created
    if [[ ! -f "$STATE_FILE" ]]; then
        print_result "$test_name" "FAIL"
        echo "  Error: State file was not created"
        return 1
    fi

    # Verify JSON structure
    local consecutive_failures
    local last_success
    local last_attempt
    local attempts

    consecutive_failures=$(jq -r '.consecutive_failures' "$STATE_FILE" 2>/dev/null)
    last_success=$(jq -r '.last_success' "$STATE_FILE" 2>/dev/null)
    last_attempt=$(jq -r '.last_attempt' "$STATE_FILE" 2>/dev/null)
    attempts=$(jq -r '.attempts' "$STATE_FILE" 2>/dev/null)

    if [[ "$consecutive_failures" != "0" ]]; then
        print_result "$test_name" "FAIL"
        echo "  Error: consecutive_failures should be 0, got: $consecutive_failures"
        return 1
    fi

    if [[ "$last_success" != "null" ]]; then
        print_result "$test_name" "FAIL"
        echo "  Error: last_success should be null, got: $last_success"
        return 1
    fi

    if [[ "$last_attempt" != "null" ]]; then
        print_result "$test_name" "FAIL"
        echo "  Error: last_attempt should be null, got: $last_attempt"
        return 1
    fi

    if [[ "$attempts" != "0" ]]; then
        print_result "$test_name" "FAIL"
        echo "  Error: attempts should be 0, got: $attempts"
        return 1
    fi

    print_result "$test_name" "PASS"
    return 0
}

# Test: Update state with success
test_update_state_success() {
    local test_name="test_update_state_success"

    # Initialize state
    init_state > /dev/null 2>&1

    # Set some failures first
    update_state "failed" "Test failure" > /dev/null 2>&1
    update_state "failed" "Test failure 2" > /dev/null 2>&1

    # Verify failures were set
    local failures_before
    failures_before=$(get_consecutive_failures)

    if [[ "$failures_before" != "2" ]]; then
        print_result "$test_name" "FAIL"
        echo "  Error: failures_before should be 2, got: $failures_before"
        return 1
    fi

    # Now update with success
    update_state "success" "Deployment succeeded" > /dev/null 2>&1

    # Verify failures reset to 0
    local failures_after
    failures_after=$(get_consecutive_failures)

    if [[ "$failures_after" != "0" ]]; then
        print_result "$test_name" "FAIL"
        echo "  Error: consecutive_failures should reset to 0, got: $failures_after"
        return 1
    fi

    # Verify last_success is set
    local last_success
    last_success=$(get_last_success)

    if [[ "$last_success" == "null" ]]; then
        print_result "$test_name" "FAIL"
        echo "  Error: last_success should be set after success"
        return 1
    fi

    # Verify last_status
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

# Test: Update state with failure
test_update_state_failed() {
    local test_name="test_update_state_failed"

    # Initialize fresh state
    rm -f "$STATE_FILE"
    init_state > /dev/null 2>&1

    # Update with failure
    update_state "failed" "Build failed" > /dev/null 2>&1

    # Verify failures incremented
    local failures
    failures=$(get_consecutive_failures)

    if [[ "$failures" != "1" ]]; then
        print_result "$test_name" "FAIL"
        echo "  Error: consecutive_failures should be 1, got: $failures"
        return 1
    fi

    # Update with another failure
    update_state "failed" "Deploy failed" > /dev/null 2>&1

    # Verify failures incremented again
    failures=$(get_consecutive_failures)

    if [[ "$failures" != "2" ]]; then
        print_result "$test_name" "FAIL"
        echo "  Error: consecutive_failures should be 2, got: $failures"
        return 1
    fi

    # Verify last_status
    local last_status
    last_status=$(jq -r '.last_status' "$STATE_FILE")

    if [[ "$last_status" != "failed" ]]; then
        print_result "$test_name" "FAIL"
        echo "  Error: last_status should be 'failed', got: $last_status"
        return 1
    fi

    # Verify last_reason
    local last_reason
    last_reason=$(jq -r '.last_reason' "$STATE_FILE")

    if [[ "$last_reason" != "Deploy failed" ]]; then
        print_result "$test_name" "FAIL"
        echo "  Error: last_reason should be 'Deploy failed', got: $last_reason"
        return 1
    fi

    print_result "$test_name" "PASS"
    return 0
}

# Test: Get consecutive failures
test_get_consecutive_failures() {
    local test_name="test_get_consecutive_failures"

    # Initialize fresh state
    rm -f "$STATE_FILE"
    init_state > /dev/null 2>&1

    # Initial failures should be 0
    local failures
    failures=$(get_consecutive_failures)

    if [[ "$failures" != "0" ]]; then
        print_result "$test_name" "FAIL"
        echo "  Error: initial failures should be 0, got: $failures"
        return 1
    fi

    # Add 3 failures
    update_state "failed" "Failure 1" > /dev/null 2>&1
    update_state "failed" "Failure 2" > /dev/null 2>&1
    update_state "failed" "Failure 3" > /dev/null 2>&1

    # Should return 3
    failures=$(get_consecutive_failures)

    if [[ "$failures" != "3" ]]; then
        print_result "$test_name" "FAIL"
        echo "  Error: failures should be 3, got: $failures"
        return 1
    fi

    print_result "$test_name" "PASS"
    return 0
}

# Test: Reset state
test_reset_state() {
    local test_name="test_reset_state"

    # Initialize with failures
    rm -f "$STATE_FILE"
    init_state > /dev/null 2>&1
    update_state "failed" "Failure 1" > /dev/null 2>&1
    update_state "failed" "Failure 2" > /dev/null 2>&1
    update_state "failed" "Failure 3" > /dev/null 2>&1

    # Verify failures are set
    local failures_before
    failures_before=$(get_consecutive_failures)

    if [[ "$failures_before" != "3" ]]; then
        print_result "$test_name" "FAIL"
        echo "  Error: failures_before should be 3, got: $failures_before"
        return 1
    fi

    # Reset state
    reset_state > /dev/null 2>&1

    # Verify failures reset to 0
    local failures_after
    failures_after=$(get_consecutive_failures)

    if [[ "$failures_after" != "0" ]]; then
        print_result "$test_name" "FAIL"
        echo "  Error: failures should be 0 after reset, got: $failures_after"
        return 1
    fi

    # Verify last_status
    local last_status
    last_status=$(jq -r '.last_status' "$STATE_FILE")

    if [[ "$last_status" != "reset" ]]; then
        print_result "$test_name" "FAIL"
        echo "  Error: last_status should be 'reset', got: $last_status"
        return 1
    fi

    # Verify last_reason
    local last_reason
    last_reason=$(jq -r '.last_reason' "$STATE_FILE")

    if [[ "$last_reason" != "Manual reset" ]]; then
        print_result "$test_name" "FAIL"
        echo "  Error: last_reason should be 'Manual reset', got: $last_reason"
        return 1
    fi

    print_result "$test_name" "PASS"
    return 0
}

# Test: Get attempts count
test_get_attempts() {
    local test_name="test_get_attempts"

    # Initialize fresh state
    rm -f "$STATE_FILE"
    init_state > /dev/null 2>&1

    # Initial attempts should be 0
    local attempts
    attempts=$(get_attempts)

    if [[ "$attempts" != "0" ]]; then
        print_result "$test_name" "FAIL"
        echo "  Error: initial attempts should be 0, got: $attempts"
        return 1
    fi

    # Add some updates
    update_state "failed" "Attempt 1" > /dev/null 2>&1
    update_state "failed" "Attempt 2" > /dev/null 2>&1
    update_state "success" "Attempt 3" > /dev/null 2>&1

    # Should return 3
    attempts=$(get_attempts)

    if [[ "$attempts" != "3" ]]; then
        print_result "$test_name" "FAIL"
        echo "  Error: attempts should be 3, got: $attempts"
        return 1
    fi

    print_result "$test_name" "PASS"
    return 0
}

# Main test runner
main() {
    echo "=========================================="
    echo "State Manager Unit Tests"
    echo "=========================================="
    echo ""
    echo "Test state file: $STATE_FILE"
    echo ""

    # Run all tests
    test_init_state
    test_update_state_success
    test_update_state_failed
    test_get_consecutive_failures
    test_reset_state
    test_get_attempts

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
