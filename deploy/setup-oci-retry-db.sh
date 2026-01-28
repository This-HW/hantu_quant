#!/bin/bash
#
# ⚠️ DEPRECATED (2026-01): DB를 hantu-server (158.180.87.156)로 마이그레이션 완료
# DB 서버에 OCI VM 생성 재시도 스크립트 설정
# 로컬에서 실행: bash deploy/setup-oci-retry-db.sh
#

set -e

# DB_SERVER="ubuntu@168.107.3.196"
# API 서버로 대체
DB_SERVER="ubuntu@134.185.104.141"
SSH_KEY="~/.ssh/id_rsa"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

echo "=========================================="
echo "  OCI Retry 스크립트 - DB 서버 설정"
echo "=========================================="
echo ""

# 1. SSH 연결 테스트
log_info "DB 서버 연결 테스트 중..."
if ! ssh -i $SSH_KEY -o ConnectTimeout=10 $DB_SERVER "echo 'Connected'" 2>/dev/null; then
    log_error "DB 서버에 연결할 수 없습니다"
    exit 1
fi
log_info "연결 성공!"

# 2. OCI CLI 설치 확인
log_info "OCI CLI 설치 확인 중..."
if ssh -i $SSH_KEY $DB_SERVER "which oci" 2>/dev/null; then
    log_info "OCI CLI 이미 설치됨"
else
    log_info "OCI CLI 설치 중... (약 2-3분 소요)"
    ssh -i $SSH_KEY $DB_SERVER 'bash -c "$(curl -L https://raw.githubusercontent.com/oracle/oci-cli/master/scripts/install/install.sh)" -- --accept-all-defaults'
    log_info "OCI CLI 설치 완료"
fi

# 3. OCI 설정 디렉토리 생성
log_info "OCI 설정 디렉토리 생성 중..."
ssh -i $SSH_KEY $DB_SERVER "mkdir -p ~/.oci"

# 4. OCI 설정 파일 복사
log_info "OCI 설정 파일 복사 중..."
if [ -f ~/.oci/config ]; then
    scp -i $SSH_KEY ~/.oci/config $DB_SERVER:~/.oci/
    log_info "config 파일 복사 완료"
else
    log_error "로컬에 ~/.oci/config 파일이 없습니다"
    exit 1
fi

# 5. OCI 키 파일 복사
log_info "OCI 키 파일 복사 중..."
KEY_FILE=$(grep "key_file" ~/.oci/config | head -1 | cut -d'=' -f2 | tr -d ' ' | sed "s|~|$HOME|g")
if [ -f "$KEY_FILE" ]; then
    REMOTE_KEY_PATH=$(grep "key_file" ~/.oci/config | head -1 | cut -d'=' -f2 | tr -d ' ')
    scp -i $SSH_KEY "$KEY_FILE" $DB_SERVER:~/.oci/
    # config 파일의 key_file 경로 수정
    KEY_BASENAME=$(basename "$KEY_FILE")
    ssh -i $SSH_KEY $DB_SERVER "sed -i 's|key_file.*|key_file=~/.oci/$KEY_BASENAME|g' ~/.oci/config"
    ssh -i $SSH_KEY $DB_SERVER "chmod 600 ~/.oci/$KEY_BASENAME"
    log_info "키 파일 복사 완료"
else
    log_error "키 파일을 찾을 수 없습니다: $KEY_FILE"
    exit 1
fi

# 6. OCI CLI 테스트
log_info "OCI CLI 테스트 중..."
if ssh -i $SSH_KEY $DB_SERVER "~/bin/oci iam region list --output table" 2>/dev/null | head -5; then
    log_info "OCI CLI 정상 작동!"
else
    log_warn "OCI CLI 테스트 실패 - 설정을 확인하세요"
fi

# 7. oci-retry.sh 스크립트 생성
log_info "oci-retry.sh 스크립트 생성 중..."
ssh -i $SSH_KEY $DB_SERVER 'cat > ~/.oci/oci-retry.sh << '\''SCRIPT'\''
#!/bin/bash
#
# Oracle Cloud ARM 인스턴스 생성 재시도 스크립트
# VM.Standard.A1.Flex는 품절이 잦아서 주기적으로 재시도
#

# 설정 - 필요에 따라 수정하세요
COMPARTMENT_ID="ocid1.tenancy.oc1..aaaaaaaadymblc2drnyhs2aujcqktu6at67ygqtviyysx2lhonhmgqfplw4a"
AVAILABILITY_DOMAIN="deDa:AP-CHUNCHEON-1-AD-1"
SUBNET_ID="ocid1.subnet.oc1.ap-chuncheon-1.aaaaaaaaivizwlzhz5hj45o5n47bepxdrwi6oifgkwnydmm7b3bkdtlpu4ga"
IMAGE_ID="ocid1.image.oc1.ap-chuncheon-1.aaaaaaaadftjy2tpwrwvhapncv5w36ouvwsqm24hghlitrhhgvs5txnzpwmq"  # Ubuntu 22.04 ARM
SSH_KEY_FILE="$HOME/.ssh/id_rsa.pub"

# ARM 인스턴스 설정
INSTANCE_NAME="hw-arm-3"
SHAPE="VM.Standard.A1.Flex"
OCPUS=2
MEMORY_GB=12

# 재시도 설정
RETRY_INTERVAL=300  # 5분
MAX_RETRIES=0       # 0 = 무한

LOG_FILE="$HOME/.oci/oci-retry.log"
OCI_CMD="$HOME/bin/oci"

log() {
    echo "[$(date +%Y-%m-%d\ %H:%M:%S)] $1" | tee -a "$LOG_FILE"
}

check_existing_arm() {
    $OCI_CMD compute instance list \
        --compartment-id "$COMPARTMENT_ID" \
        --display-name "$INSTANCE_NAME" \
        --lifecycle-state RUNNING \
        --query "data[0].id" \
        --raw-output 2>/dev/null
}

create_instance() {
    log "ARM 인스턴스 생성 시도 중..."

    # SSH 공개키 읽기
    if [ ! -f "$SSH_KEY_FILE" ]; then
        log "ERROR: SSH 공개키 파일이 없습니다: $SSH_KEY_FILE"
        return 1
    fi
    SSH_KEY=$(cat "$SSH_KEY_FILE")

    RESULT=$($OCI_CMD compute instance launch \
        --compartment-id "$COMPARTMENT_ID" \
        --availability-domain "$AVAILABILITY_DOMAIN" \
        --subnet-id "$SUBNET_ID" \
        --image-id "$IMAGE_ID" \
        --shape "$SHAPE" \
        --shape-config "{\"ocpus\": $OCPUS, \"memoryInGBs\": $MEMORY_GB}" \
        --display-name "$INSTANCE_NAME" \
        --assign-public-ip true \
        --ssh-authorized-keys-file "$SSH_KEY_FILE" \
        --wait-for-state RUNNING \
        --wait-interval-seconds 30 \
        2>&1)

    if echo "$RESULT" | grep -q "RUNNING"; then
        return 0
    else
        return 1
    fi
}

# 메인 루프
log "=========================================="
log "OCI ARM 인스턴스 생성 스크립트 시작"
log "=========================================="
log "Shape: $SHAPE ($OCPUS OCPU, ${MEMORY_GB}GB RAM)"
log "재시도 간격: ${RETRY_INTERVAL}초"
log ""

retry_count=0
while true; do
    # 이미 생성된 인스턴스 확인
    EXISTING=$(check_existing_arm)
    if [ -n "$EXISTING" ] && [ "$EXISTING" != "null" ]; then
        log "SUCCESS! ARM 인스턴스가 이미 존재합니다: $EXISTING"
        log "스크립트를 종료합니다."
        exit 0
    fi

    # 인스턴스 생성 시도
    if create_instance; then
        log "=========================================="
        log "SUCCESS! ARM 인스턴스 생성 성공!"
        log "=========================================="

        # 새로 생성된 인스턴스 정보 조회
        sleep 10
        INSTANCE_ID=$(check_existing_arm)
        if [ -n "$INSTANCE_ID" ]; then
            PUBLIC_IP=$($OCI_CMD compute instance list-vnics \
                --instance-id "$INSTANCE_ID" \
                --query "data[0].\"public-ip\"" \
                --raw-output 2>/dev/null)
            log "Instance ID: $INSTANCE_ID"
            log "Public IP: $PUBLIC_IP"
        fi
        exit 0
    else
        retry_count=$((retry_count + 1))
        log "생성 실패 (시도 #$retry_count) - Out of host capacity 또는 기타 오류"

        if [ $MAX_RETRIES -gt 0 ] && [ $retry_count -ge $MAX_RETRIES ]; then
            log "최대 재시도 횟수 도달. 종료합니다."
            exit 1
        fi

        log "${RETRY_INTERVAL}초 후 재시도..."
        sleep $RETRY_INTERVAL
    fi
done
SCRIPT'

ssh -i $SSH_KEY $DB_SERVER "chmod +x ~/.oci/oci-retry.sh"
log_info "스크립트 생성 완료"

echo ""
echo "=========================================="
log_info "설정 완료!"
echo "=========================================="
echo ""
echo "다음 단계:"
echo ""
echo "1. DB 서버 접속:"
echo "   ssh -i $SSH_KEY $DB_SERVER"
echo ""
echo "2. 스크립트 설정 확인/수정 (필요시):"
echo "   nano ~/.oci/oci-retry.sh"
echo ""
echo "3. 스크립트 실행:"
echo "   nohup ~/.oci/oci-retry.sh > ~/.oci/oci-retry.log 2>&1 &"
echo ""
echo "4. 로그 확인:"
echo "   tail -f ~/.oci/oci-retry.log"
echo ""
echo "5. 중지:"
echo "   pkill -f oci-retry"
echo ""
