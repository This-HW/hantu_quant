#!/bin/bash

# Redis 모니터링 스크립트
# 용도: Redis 서비스 상태, 메모리 사용량, 캐시 키 등 실시간 모니터링
# 실행: ./scripts/monitor-redis.sh [--watch]

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# 환경 감지
if [[ "$PWD" == /opt/hantu_quant* ]]; then
    ENV_TYPE="server"
    APP_DIR="/opt/hantu_quant"
elif [[ "$PWD" == /home/ubuntu/hantu_quant* ]]; then
    ENV_TYPE="dev"
    APP_DIR="/home/ubuntu/hantu_quant_dev"
else
    ENV_TYPE="local"
    APP_DIR="$PWD"
fi

# .env 파일에서 비밀번호 추출
ENV_FILE="$APP_DIR/.env"

if [ -f "$ENV_FILE" ]; then
    # Python으로 URL 파싱 및 디코딩 (URL 인코딩된 비밀번호 처리)
    REDIS_PASSWORD=$(ENV_FILE_PATH="$ENV_FILE" python3 -c '
import os
from urllib.parse import urlparse, unquote

env_file = os.environ.get("ENV_FILE_PATH")
try:
    with open(env_file) as f:
        for line in f:
            if line.startswith("REDIS_URL="):
                url = line.split("=", 1)[1].strip()
                parsed = urlparse(url)
                if parsed.password:
                    print(unquote(parsed.password))
                break
except Exception:
    pass
')
fi

# Redis 연결 확인
check_redis_connection() {
    if [ -n "$REDIS_PASSWORD" ]; then
        redis-cli -a "$REDIS_PASSWORD" PING 2>/dev/null | grep -q PONG
    else
        redis-cli PING 2>/dev/null | grep -q PONG
    fi
}

# Redis 명령어 실행
redis_cmd() {
    if [ -n "$REDIS_PASSWORD" ]; then
        redis-cli -a "$REDIS_PASSWORD" --no-auth-warning "$@" 2>/dev/null
    else
        redis-cli "$@" 2>/dev/null
    fi
}

# 모니터링 정보 출력
show_monitoring() {
    clear

    echo -e "${CYAN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║           Redis 캐싱 시스템 모니터링 대시보드              ║${NC}"
    echo -e "${CYAN}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    # 환경 정보
    echo -e "${BLUE}[환경 정보]${NC}"
    echo "  환경: $ENV_TYPE"
    echo "  앱 디렉토리: $APP_DIR"
    echo "  업데이트: $(date '+%Y-%m-%d %H:%M:%S')"
    echo ""

    # ============================================================
    # 1. Redis 서비스 상태
    # ============================================================
    echo -e "${BLUE}[1. Redis 서비스 상태]${NC}"

    if systemctl is-active --quiet redis-server 2>/dev/null; then
        echo -e "  상태: ${GREEN}✅ Active (running)${NC}"

        # Uptime
        UPTIME=$(systemctl show redis-server --property=ActiveEnterTimestamp --value 2>/dev/null)
        if [ -n "$UPTIME" ]; then
            echo "  시작 시간: $UPTIME"
        fi
    else
        echo -e "  상태: ${RED}❌ Inactive${NC}"
    fi

    # 자동 시작 설정
    if systemctl is-enabled --quiet redis-server 2>/dev/null; then
        echo -e "  자동 시작: ${GREEN}✅ Enabled${NC}"
    else
        echo -e "  자동 시작: ${YELLOW}⚠️  Disabled${NC}"
    fi

    echo ""

    # ============================================================
    # 2. Redis 연결 상태
    # ============================================================
    echo -e "${BLUE}[2. Redis 연결 상태]${NC}"

    if check_redis_connection; then
        echo -e "  연결: ${GREEN}✅ PONG${NC}"

        # 연결된 클라이언트 수
        CLIENTS=$(redis_cmd INFO clients | grep "connected_clients:" | cut -d: -f2 | tr -d '\r')
        echo "  연결된 클라이언트: $CLIENTS"

        # 바인딩 주소 확인
        BIND_ADDR=$(netstat -tlnp 2>/dev/null | grep ":6379" | awk '{print $4}' || ss -tlnp 2>/dev/null | grep ":6379" | awk '{print $5}')
        if [ -n "$BIND_ADDR" ]; then
            echo "  바인딩: $BIND_ADDR"
        fi
    else
        echo -e "  연결: ${RED}❌ Failed${NC}"
        if [ -z "$REDIS_PASSWORD" ]; then
            echo -e "  ${YELLOW}⚠️  .env에 REDIS_URL이 없습니다.${NC}"
        fi
    fi

    echo ""

    # ============================================================
    # 3. 메모리 사용량
    # ============================================================
    echo -e "${BLUE}[3. 메모리 사용량]${NC}"

    if check_redis_connection; then
        # 사용 중인 메모리
        USED_MEMORY=$(redis_cmd INFO memory | grep "^used_memory_human:" | cut -d: -f2 | tr -d '\r')
        USED_MEMORY_PEAK=$(redis_cmd INFO memory | grep "^used_memory_peak_human:" | cut -d: -f2 | tr -d '\r')
        MAXMEMORY=$(redis_cmd CONFIG GET maxmemory | tail -1)

        # maxmemory를 MB로 변환
        if [ "$MAXMEMORY" == "0" ]; then
            MAXMEMORY_MB="무제한"
        else
            MAXMEMORY_MB="$((MAXMEMORY / 1024 / 1024))MB"
        fi

        echo "  사용 중: $USED_MEMORY"
        echo "  최대 사용: $USED_MEMORY_PEAK"
        echo "  제한: $MAXMEMORY_MB"

        # 메모리 정책
        MAXMEMORY_POLICY=$(redis_cmd CONFIG GET maxmemory-policy | tail -1)
        echo "  정책: $MAXMEMORY_POLICY"

        # 메모리 사용률 (maxmemory 설정된 경우)
        if [ "$MAXMEMORY" != "0" ]; then
            USED_MEMORY_BYTES=$(redis_cmd INFO memory | grep "^used_memory:" | cut -d: -f2 | tr -d '\r')
            USAGE_PERCENT=$((USED_MEMORY_BYTES * 100 / MAXMEMORY))

            if [ $USAGE_PERCENT -lt 50 ]; then
                echo -e "  사용률: ${GREEN}$USAGE_PERCENT%${NC}"
            elif [ $USAGE_PERCENT -lt 80 ]; then
                echo -e "  사용률: ${YELLOW}$USAGE_PERCENT%${NC}"
            else
                echo -e "  사용률: ${RED}$USAGE_PERCENT%${NC}"
            fi
        fi
    else
        echo -e "  ${RED}Redis 연결 실패${NC}"
    fi

    echo ""

    # ============================================================
    # 4. 캐시 통계
    # ============================================================
    echo -e "${BLUE}[4. 캐시 통계]${NC}"

    if check_redis_connection; then
        # 총 키 개수
        TOTAL_KEYS=$(redis_cmd DBSIZE | awk '{print $2}')
        echo "  총 키 개수: $TOTAL_KEYS"

        # 캐시 히트/미스
        KEYSPACE_HITS=$(redis_cmd INFO stats | grep "^keyspace_hits:" | cut -d: -f2 | tr -d '\r')
        KEYSPACE_MISSES=$(redis_cmd INFO stats | grep "^keyspace_misses:" | cut -d: -f2 | tr -d '\r')

        if [ -n "$KEYSPACE_HITS" ] && [ -n "$KEYSPACE_MISSES" ]; then
            TOTAL_OPS=$((KEYSPACE_HITS + KEYSPACE_MISSES))

            if [ $TOTAL_OPS -gt 0 ]; then
                HIT_RATE=$((KEYSPACE_HITS * 100 / TOTAL_OPS))
                echo "  캐시 히트: $KEYSPACE_HITS"
                echo "  캐시 미스: $KEYSPACE_MISSES"
                echo -e "  히트율: ${GREEN}$HIT_RATE%${NC}"
            else
                echo "  캐시 히트: 0"
                echo "  캐시 미스: 0"
            fi
        fi

        # Evicted keys (메모리 부족으로 삭제된 키)
        EVICTED_KEYS=$(redis_cmd INFO stats | grep "^evicted_keys:" | cut -d: -f2 | tr -d '\r')
        if [ -n "$EVICTED_KEYS" ] && [ "$EVICTED_KEYS" != "0" ]; then
            echo -e "  Evicted 키: ${YELLOW}$EVICTED_KEYS${NC}"
        fi
    else
        echo -e "  ${RED}Redis 연결 실패${NC}"
    fi

    echo ""

    # ============================================================
    # 5. 캐시 키 목록 (최근 10개)
    # ============================================================
    echo -e "${BLUE}[5. 캐시 키 목록 (최근 10개)]${NC}"

    if check_redis_connection; then
        # SCAN으로 키 목록 조회 (KEYS 대신 - 프로덕션 안전)
        redis_cmd --scan --count 10 | head -10 | while read -r key; do
            # TTL 확인
            TTL=$(redis_cmd TTL "$key")

            if [ "$TTL" == "-1" ]; then
                echo "  - $key (영구)"
            elif [ "$TTL" == "-2" ]; then
                echo "  - $key (만료됨)"
            else
                echo "  - $key (TTL: ${TTL}초)"
            fi
        done

        # 키가 없는 경우
        if [ "$TOTAL_KEYS" == "0" ]; then
            echo "  (캐시 키 없음)"
        fi
    else
        echo -e "  ${RED}Redis 연결 실패${NC}"
    fi

    echo ""

    # ============================================================
    # 6. 애플리케이션 연결 상태
    # ============================================================
    if [ "$ENV_TYPE" == "server" ]; then
        echo -e "${BLUE}[6. 애플리케이션 연결 상태]${NC}"

        # API 서비스 로그
        if journalctl -u hantu-api -n 20 --since "5 minutes ago" 2>/dev/null | grep -qi "redis"; then
            echo -e "  hantu-api: ${GREEN}✅ Redis 사용 중${NC}"
        else
            echo -e "  hantu-api: ${YELLOW}⚠️  Redis 로그 없음${NC}"
        fi

        # Scheduler 서비스 로그
        if journalctl -u hantu-scheduler -n 20 --since "5 minutes ago" 2>/dev/null | grep -qi "redis"; then
            echo -e "  hantu-scheduler: ${GREEN}✅ Redis 사용 중${NC}"
        else
            echo -e "  hantu-scheduler: ${YELLOW}⚠️  Redis 로그 없음${NC}"
        fi

        echo ""
    fi

    # ============================================================
    # 하단 도움말
    # ============================================================
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    if [ "$1" == "--watch" ]; then
        echo -e "${YELLOW}실시간 모니터링 중... (5초 갱신, Ctrl+C로 종료)${NC}"
    else
        echo "실시간 모니터링: ./scripts/monitor-redis.sh --watch"
        echo "Redis CLI: redis-cli -a [비밀번호]"
        echo "서비스 재시작: sudo systemctl restart redis-server"
    fi
}

# ============================================================
# 메인 로직
# ============================================================

if [ "$1" == "--watch" ]; then
    # Watch 모드 (5초 간격 갱신)
    while true; do
        show_monitoring "--watch"
        sleep 5
    done
else
    # 1회 출력
    show_monitoring
fi
