#!/bin/bash
# Git hooks 설치 스크립트
# 보안 검사를 커밋 전에 자동 실행

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
HOOKS_DIR="$PROJECT_ROOT/.git/hooks"

echo "==================================="
echo "Git 보안 Hooks 설치"
echo "==================================="

# pre-commit hook 생성
PRE_COMMIT_HOOK="$HOOKS_DIR/pre-commit"

cat > "$PRE_COMMIT_HOOK" << 'EOF'
#!/bin/bash
# Pre-commit hook: 보안 검사 자동 실행

echo "🔒 보안 검사 실행 중..."

# 프로젝트 루트로 이동
cd "$(git rev-parse --show-toplevel)"

# 민감한 파일이 스테이징되어 있는지 확인
SENSITIVE_FILES=$(git diff --cached --name-only | grep -E '\.env$|token.*\.json$|telegram_config\.json$|\.pem$|\.key$' || true)

if [ -n "$SENSITIVE_FILES" ]; then
    echo "❌ 민감한 파일이 커밋에 포함되어 있습니다:"
    echo "$SENSITIVE_FILES"
    echo ""
    echo "이 파일들을 스테이징에서 제거하세요:"
    echo "  git reset HEAD <파일명>"
    exit 1
fi

# 하드코딩된 시크릿 확인 (스테이징된 파일만)
STAGED_PY_FILES=$(git diff --cached --name-only --diff-filter=ACM | grep '\.py$' || true)

if [ -n "$STAGED_PY_FILES" ]; then
    for file in $STAGED_PY_FILES; do
        # 하드코딩된 API 키 패턴 검사
        if grep -E 'APP_KEY\s*=\s*["\047][^"\047]{10,}["\047]|APP_SECRET\s*=\s*["\047][^"\047]{10,}["\047]' "$file" > /dev/null 2>&1; then
            echo "❌ $file 에서 하드코딩된 API 키가 감지되었습니다!"
            exit 1
        fi

        # Telegram 토큰 패턴 검사
        if grep -E 'bot_token.*[0-9]{10}:[A-Za-z0-9_-]{35}' "$file" > /dev/null 2>&1; then
            echo "❌ $file 에서 Telegram 봇 토큰이 감지되었습니다!"
            exit 1
        fi
    done
fi

# JSON 파일 검사
STAGED_JSON_FILES=$(git diff --cached --name-only --diff-filter=ACM | grep '\.json$' || true)

if [ -n "$STAGED_JSON_FILES" ]; then
    for file in $STAGED_JSON_FILES; do
        # 예제 파일은 건너뛰기
        if [[ "$file" == *".example."* ]] || [[ "$file" == *"example"* ]]; then
            continue
        fi

        # Telegram 토큰 패턴 검사
        if grep -E '"bot_token".*[0-9]{10}:[A-Za-z0-9_-]{35}' "$file" > /dev/null 2>&1; then
            echo "❌ $file 에서 Telegram 봇 토큰이 감지되었습니다!"
            exit 1
        fi

        # access_token 패턴 검사
        if grep -E '"access_token".*eyJ' "$file" > /dev/null 2>&1; then
            echo "❌ $file 에서 액세스 토큰이 감지되었습니다!"
            exit 1
        fi
    done
fi

echo "✅ 보안 검사 통과"
exit 0
EOF

chmod +x "$PRE_COMMIT_HOOK"
echo "✅ pre-commit hook 설치 완료: $PRE_COMMIT_HOOK"

echo ""
echo "==================================="
echo "설치 완료!"
echo "==================================="
echo ""
echo "이제 다음 기능이 활성화됩니다:"
echo "  - 커밋 전 민감한 파일 자동 검사"
echo "  - 하드코딩된 API 키/토큰 자동 감지"
echo ""
echo "Hook을 비활성화하려면:"
echo "  rm $PRE_COMMIT_HOOK"
echo ""
