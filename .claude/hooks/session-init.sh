#!/bin/bash
#
# SessionStart Hook: 세션 초기화
#
# Claude Code 세션 시작 시 환경을 설정합니다.
#
# 기능:
# - 환경 변수 확인
# - 필수 도구 확인
# - 프로젝트 타입 감지
#

set -e

# 색상 정의
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "🚀 Claude Code 세션 초기화..."

# 1. 필수 환경 변수 확인
check_env() {
    if [ -z "$ANTHROPIC_API_KEY" ]; then
        echo -e "${YELLOW}⚠ ANTHROPIC_API_KEY가 설정되지 않았습니다${NC}"
    fi
}

# 2. 필수 도구 확인
check_tools() {
    local tools=("git" "node" "npm")
    local missing=()

    for tool in "${tools[@]}"; do
        if ! command -v "$tool" &> /dev/null; then
            missing+=("$tool")
        fi
    done

    if [ ${#missing[@]} -gt 0 ]; then
        echo -e "${YELLOW}⚠ 누락된 도구: ${missing[*]}${NC}"
    fi
}

# 3. 프로젝트 타입 감지
detect_project() {
    if [ -f "package.json" ]; then
        echo -e "${GREEN}✓ Node.js 프로젝트 감지${NC}"
    elif [ -f "pyproject.toml" ] || [ -f "setup.py" ] || [ -f "requirements.txt" ]; then
        echo -e "${GREEN}✓ Python 프로젝트 감지${NC}"
    elif [ -f "go.mod" ]; then
        echo -e "${GREEN}✓ Go 프로젝트 감지${NC}"
    elif [ -f "Cargo.toml" ]; then
        echo -e "${GREEN}✓ Rust 프로젝트 감지${NC}"
    fi
}

# 4. Git 상태 확인
check_git() {
    if [ -d ".git" ]; then
        local branch=$(git branch --show-current 2>/dev/null || echo "unknown")
        local status=$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')
        echo -e "${GREEN}✓ Git: ${branch} (변경 ${status}개)${NC}"
    fi
}

# 실행
check_env
check_tools
detect_project
check_git

echo -e "${GREEN}✓ 세션 초기화 완료${NC}"
exit 0
