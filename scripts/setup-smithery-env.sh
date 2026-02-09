#!/bin/bash

# Smithery API 환경 변수 설정 스크립트
# 로컬과 서버 모두에서 사용 가능

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$PROJECT_ROOT/.env"

# 색상 정의
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Smithery API 환경 변수 설정 ===${NC}\n"

# .env 파일 존재 확인
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}❌ .env 파일을 찾을 수 없습니다: $ENV_FILE${NC}"
    exit 1
fi

# 이미 SMITHERY_API_KEY가 있는지 확인
if grep -q "^SMITHERY_API_KEY=" "$ENV_FILE"; then
    echo -e "${YELLOW}⚠️  SMITHERY_API_KEY가 이미 설정되어 있습니다.${NC}"
    read -p "덮어쓰시겠습니까? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "취소되었습니다."
        exit 0
    fi
    # 기존 항목 제거
    sed -i.bak '/^SMITHERY_API_KEY=/d' "$ENV_FILE"
    rm -f "$ENV_FILE.bak"
fi

# API 키 추가
echo "" >> "$ENV_FILE"
echo "# Smithery.ai MCP API Key (kis-code-assistant-mcp)" >> "$ENV_FILE"
echo "SMITHERY_API_KEY=d9e6136a-ca80-4f6f-8387-eb00980831b2" >> "$ENV_FILE"

echo -e "${GREEN}✅ SMITHERY_API_KEY가 .env에 추가되었습니다.${NC}"

# 현재 셸에 export
export SMITHERY_API_KEY=d9e6136a-ca80-4f6f-8387-eb00980831b2

echo -e "\n${YELLOW}⭕ 현재 셸 세션에도 적용하려면 다음 명령을 실행하세요:${NC}"
echo -e "  ${GREEN}source $ENV_FILE${NC}"
echo -e "\n${YELLOW}⭕ Claude Code를 재시작하여 변경사항을 적용하세요.${NC}"

# 서버 환경인 경우 추가 안내
if [[ "$PWD" == /opt/* ]] || [[ "$PWD" == /home/ubuntu/* ]]; then
    echo -e "\n${YELLOW}📌 서버 환경 감지됨${NC}"
    echo -e "systemd 서비스에도 환경 변수를 추가해야 합니다:"
    echo -e "  ${GREEN}sudo systemctl edit hantu-scheduler${NC}"
    echo -e "  ${GREEN}sudo systemctl edit hantu-api${NC}"
    echo -e "\n다음 내용을 추가:"
    echo -e "  [Service]"
    echo -e "  Environment=\"SMITHERY_API_KEY=d9e6136a-ca80-4f6f-8387-eb00980831b2\""
fi

echo -e "\n${GREEN}설정 완료!${NC}"
