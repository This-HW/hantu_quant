#!/bin/bash

# 한투 퀀트 프로젝트 문서 동기화 자동화 설정 스크립트

echo "🚀 한투 퀀트 문서 동기화 자동화 설정을 시작합니다..."

# Git hooks 디렉토리 확인 및 생성
if [ ! -d ".git/hooks" ]; then
    echo "❌ .git/hooks 디렉토리를 찾을 수 없습니다. Git 저장소인지 확인해주세요."
    exit 1
fi

# pre-commit hook 설치
echo "📋 pre-commit hook 설치 중..."
cp .githooks/pre-commit .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit

# post-commit hook 생성 (선택사항)
cat > .git/hooks/post-commit << 'EOF'
#!/bin/bash
echo "✅ 커밋 완료: 문서가 자동으로 동기화되었습니다."
EOF
chmod +x .git/hooks/post-commit

# Python 스크립트 실행 권한 설정
chmod +x scripts/doc_sync_automation.py

# 필요한 디렉토리 생성
mkdir -p .ai/history

echo "✅ 설정 완료!"
echo ""
echo "📖 사용 방법:"
echo "1. TODO 완료 시 자동으로 문서가 동기화됩니다."
echo "2. 수동 실행: python3 scripts/doc_sync_automation.py"
echo "3. Git 커밋 시 자동으로 관련 문서들이 업데이트됩니다."
echo ""
echo "📁 자동 업데이트되는 파일들:"
echo "  - PROJECT_SUMMARY.md"
echo "  - ROADMAP.md" 
echo "  - STATUS_REPORT.md"
echo "  - .cursor/rules/project-status.mdc"
echo "  - .cursor/rules/implementation_checklist.md"
echo "  - .ai/history/ (작업 히스토리)"
echo ""
echo "🔧 문제가 발생하면 'git config core.hooksPath .githooks'를 실행해보세요." 