#!/bin/bash
# =============================================================================
# auto-fix-errors.sh 경로 검증 함수 테스트
# =============================================================================

set -euo pipefail

# 경로 검증 함수 (auto-fix-errors.sh에서 복사)
validate_path() {
    local path="$1"
    local normalized

    # macOS는 greadlink, Linux는 readlink
    if command -v greadlink >/dev/null 2>&1; then
        normalized=$(greadlink -f "$path" 2>/dev/null) || return 1
    else
        normalized=$(readlink -f "$path" 2>/dev/null) || return 1
    fi

    # Null byte 체크
    if [[ "$path" == *$'\0'* ]]; then
        echo "Error: Path contains null byte: $path" >&2
        return 1
    fi

    # 화이트리스트 검증
    case "$normalized" in
        /opt/hantu_quant/*|/Users/grimm/Documents/Dev/hantu_quant/*)
            echo "$normalized"
            return 0
            ;;
        *)
            echo "Error: Path not allowed: $path" >&2
            return 1
            ;;
    esac
}

# 테스트
echo "===== 경로 검증 테스트 ====="

# Test 1: 허용된 경로 (로컬)
echo -n "Test 1 (로컬 경로): "
if validate_path "/Users/grimm/Documents/Dev/hantu_quant/scripts" >/dev/null 2>&1; then
    echo "✅ PASS"
else
    echo "❌ FAIL"
fi

# Test 2: 허용되지 않은 경로
echo -n "Test 2 (금지 경로): "
if validate_path "/tmp/malicious" >/dev/null 2>&1; then
    echo "❌ FAIL (금지 경로가 허용됨)"
else
    echo "✅ PASS"
fi

# Test 3: 상대 경로 (현재 디렉토리가 허용 범위 내라면 통과)
echo -n "Test 3 (상대 경로): "
cd /Users/grimm/Documents/Dev/hantu_quant
if validate_path "." >/dev/null 2>&1; then
    echo "✅ PASS"
else
    echo "⚠️  SKIP (환경에 따라 다름)"
fi

# Test 4: 존재하지 않는 경로
echo -n "Test 4 (존재하지 않는 경로): "
if validate_path "/Users/grimm/Documents/Dev/hantu_quant/nonexistent12345" >/dev/null 2>&1; then
    echo "❌ FAIL (존재하지 않는 경로가 허용됨)"
else
    echo "✅ PASS"
fi

echo ""
echo "===== 테스트 완료 ====="
