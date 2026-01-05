# Hantu Quant - 서버 정보

## Oracle Cloud Infrastructure (OCI)

### 리전 정보
- **리전**: ap-chuncheon-1 (춘천)
- **Availability Domain**: AD-1

---

## 인스턴스 목록

### hantu-app (메인 서버)

| 항목 | 값 |
|------|-----|
| **Public IP** | `134.185.104.141` |
| **Private IP** | `10.0.0.66` |
| **Shape** | VM.Standard.E2.1.Micro |
| **CPU** | 1 OCPU (2 vCPU) |
| **RAM** | 1GB |
| **OS** | Ubuntu 24.04 |
| **용도** | Scheduler + API Server |
| **Free Tier** | ✅ |

**SSH 접속:**
```bash
ssh -i ~/.ssh/id_rsa ubuntu@134.185.104.141
```

**서비스:**
- API Server: http://134.185.104.141:8000
- Scheduler: systemd (hantu-scheduler)

---

### hantu-db (예비 서버)

| 항목 | 값 |
|------|-----|
| **Public IP** | `168.107.3.196` |
| **Private IP** | `10.0.0.65` |
| **Shape** | VM.Standard.E2.1.Micro |
| **CPU** | 1 OCPU (2 vCPU) |
| **RAM** | 1GB |
| **OS** | Ubuntu 24.04 |
| **용도** | 예비 / 백업 / 다른 프로젝트 |
| **Free Tier** | ✅ |

**SSH 접속:**
```bash
ssh -i ~/.ssh/id_rsa ubuntu@168.107.3.196
```

---

## 네트워크

### VCN 정보
- **VCN 이름**: hw_default_vcn
- **Subnet**: public subnet-hw_default_vcn
- **CIDR**: 10.0.0.0/24

### 방화벽 (Security List)
| 포트 | 프로토콜 | 용도 |
|------|----------|------|
| 22 | TCP | SSH |
| 8000 | TCP | API Server |

---

## 리소스 한도 (Always Free)

| 리소스 | 한도 | 현재 사용 |
|--------|------|----------|
| E2.1.Micro 인스턴스 | 2개 | 2개 ✅ |
| A1.Flex (ARM) OCPU | 4 | 0 (품절) |
| A1.Flex (ARM) RAM | 24GB | 0 |
| Boot Volume | 200GB | ~100GB |
| Outbound | 10TB/월 | - |

---

## 관리 명령어

### 로컬에서 실행

```bash
# 인스턴스 목록
oci compute instance list \
  --compartment-id ocid1.tenancy.oc1..aaaaaaaadymblc2drnyhs2aujcqktu6at67ygqtviyysx2lhonhmgqfplw4a \
  --query 'data[*].{name:"display-name", state:"lifecycle-state", ip:"primary-private-ip"}' \
  --output table

# 인스턴스 시작
oci compute instance action --action START --instance-id <INSTANCE_OCID>

# 인스턴스 중지
oci compute instance action --action STOP --instance-id <INSTANCE_OCID>
```

### 인스턴스 OCID

```
hantu-app: ocid1.instance.oc1.ap-chuncheon-1.an4w4ljr6nppepacirpmpxfhgbfo7qm7zc7smownxu4eeq5n54q7izred4ta

hantu-db: ocid1.instance.oc1.ap-chuncheon-1.an4w4ljr6nppepaclfmqvgqjcagrcue32zvyqz4fa4f3gtcxvnzrvxznbwiq
```

---

## 백업 전략

### 현재 구성
- **DB**: SQLite (로컬 파일)
- **위치**: `/opt/hantu_quant/data/db/stock_data.db`

### 백업 명령어
```bash
# 로컬로 DB 백업
scp -i ~/.ssh/id_rsa ubuntu@134.185.104.141:/opt/hantu_quant/data/db/stock_data.db ./backup/

# 전체 데이터 백업
scp -r -i ~/.ssh/id_rsa ubuntu@134.185.104.141:/opt/hantu_quant/data ./backup/
```

---

## ARM 인스턴스 재시도 (진행 중)

ARM 인스턴스(VM.Standard.A1.Flex) 자동 생성 스크립트:

```bash
# 스크립트 위치
~/.oci/oci-retry.sh

# 실행
nohup ~/.oci/oci-retry.sh > ~/.oci/oci-retry.log 2>&1 &

# 로그 확인
tail -f ~/.oci/oci-retry.log

# 중단
pkill -f oci-retry
```

ARM 성공 시:
- 4 OCPU / 24GB RAM 사용 가능
- Docker + PostgreSQL + Redis 구성으로 전환
- Micro 인스턴스는 다른 용도로 활용

---

## 업데이트 이력

| 날짜 | 내용 |
|------|------|
| 2026-01-05 | hantu-app, hantu-db 인스턴스 생성 |
| 2026-01-05 | hantu-app에 hantu_quant 배포 |
