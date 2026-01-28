# Hantu Quant - 서버 정보

## Oracle Cloud Infrastructure (OCI)

### 리전 정보

- **리전**: ap-chuncheon-1 (춘천)
- **Availability Domain**: AD-1

---

## 인스턴스 목록

### hantu-server (메인 서버 - ARM)

| 항목            | 값                                                                                             |
| --------------- | ---------------------------------------------------------------------------------------------- |
| **Public IP**   | `158.180.87.156`                                                                               |
| **Private IP**  | `10.0.0.177`                                                                                   |
| **OCID**        | ocid1.instance.oc1.ap-chuncheon-1.an4w4ljr6nppepacq54datm5nip5xoywg52e7y67progjvp5wd4siwlfhjjq |
| **Shape**       | VM.Standard.A1.Flex (ARM)                                                                      |
| **CPU**         | 1 OCPU (ARM64)                                                                                 |
| **RAM**         | 6GB                                                                                            |
| **Boot Volume** | 50GB                                                                                           |
| **OS**          | Ubuntu 24.04.3 LTS (aarch64)                                                                   |
| **용도**        | All-in-One (Scheduler + API + DB + Redis)                                                      |
| **Free Tier**   | ✅                                                                                             |

**SSH 접속:**

```bash
ssh -i ~/.ssh/id_rsa ubuntu@158.180.87.156
```

**서비스:**

- API Server: http://158.180.87.156:8000
- Scheduler: systemd (hantu-scheduler.service)
- PostgreSQL 15: localhost:5432 (내부)
- Redis 7: localhost:6379 (Docker)

**아키텍처:**

```
All-in-One Server (ARM)
├── API Server (FastAPI, port 8000)
├── Scheduler (integrated_scheduler.py)
├── PostgreSQL 15 (systemd)
└── Redis 7 (Docker container, 100MB limit)
```

---

### hantu-app (기존 x86 서버 - 예비)

| 항목           | 값                      |
| -------------- | ----------------------- |
| **Public IP**  | `134.185.104.141`       |
| **Private IP** | `10.0.0.66`             |
| **Shape**      | VM.Standard.E2.1.Micro  |
| **CPU**        | 1 OCPU (2 vCPU)         |
| **RAM**        | 1GB                     |
| **OS**         | Ubuntu 24.04            |
| **용도**       | 예비 서버 (현재 미사용) |
| **Free Tier**  | ✅                      |

**SSH 접속:**

```bash
ssh -i ~/.ssh/id_rsa ubuntu@134.185.104.141
```

---

### hantu-db (데이터베이스 서버) — ⚠️ DEPRECATED

> **마이그레이션 완료 (2026-01)**: PostgreSQL을 hantu-server (158.180.87.156)로 이전했습니다.
> 이 서버는 더 이상 사용되지 않습니다. 연결 정보는 hantu-server 섹션을 참조하세요.

| 항목           | 값                                     | 상태          |
| -------------- | -------------------------------------- | ------------- |
| **Public IP**  | `168.107.3.196`                        | 비활성화 예정 |
| **Private IP** | `10.0.0.65`                            | 비활성화 예정 |
| **Shape**      | VM.Standard.E2.1.Micro                 |               |
| **CPU**        | 1 OCPU (2 vCPU)                        |               |
| **RAM**        | 1GB                                    |               |
| **OS**         | Ubuntu 24.04                           |               |
| **용도**       | ~~PostgreSQL~~ → **마이그레이션 완료** |               |
| **Free Tier**  | ✅                                     |               |

**현재 연결 정보 (hantu-server):**

```
DATABASE_URL=postgresql://hantu:***REMOVED***@158.180.87.156:5432/hantu_quant
```

---

## 네트워크

### VCN 정보

- **VCN 이름**: hw_default_vcn
- **Subnet**: public subnet-hw_default_vcn
- **CIDR**: 10.0.0.0/24

### 방화벽 (Security List)

| 포트 | 프로토콜 | 용도       | Source             |
| ---- | -------- | ---------- | ------------------ |
| 22   | TCP      | SSH        | 0.0.0.0/0          |
| 8000 | TCP      | API Server | 0.0.0.0/0          |
| 5432 | TCP      | PostgreSQL | 134.185.104.141/32 |

---

## 리소스 한도 (Always Free)

| 리소스              | 한도    | 현재 사용           |
| ------------------- | ------- | ------------------- |
| E2.1.Micro 인스턴스 | 2개     | 2개 ✅              |
| A1.Flex (ARM) OCPU  | 4       | 1 ✅                |
| A1.Flex (ARM) RAM   | 24GB    | 6GB ✅              |
| Boot Volume         | 200GB   | 150GB (50GB x 3) ✅ |
| Outbound            | 10TB/월 | -                   |

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
hantu-server (ARM): ocid1.instance.oc1.ap-chuncheon-1.an4w4ljr6nppepacq54datm5nip5xoywg52e7y67progjvp5wd4siwlfhjjq

hantu-app: ocid1.instance.oc1.ap-chuncheon-1.an4w4ljr6nppepacirpmpxfhgbfo7qm7zc7smownxu4eeq5n54q7izred4ta

hantu-db: ocid1.instance.oc1.ap-chuncheon-1.an4w4ljr6nppepaclfmqvgqjcagrcue32zvyqz4fa4f3gtcxvnzrvxznbwiq
```

---

## 백업 전략

### 현재 구성

- **DB**: PostgreSQL 15 (hantu-server 내부)
- **Database**: hantu_quant
- **User**: hantu
- **Location**: hantu-server (158.180.87.156)

### 백업 명령어

```bash
# PostgreSQL 백업 (로컬로)
ssh -i ~/.ssh/id_rsa ubuntu@158.180.87.156 \
  "sudo -u postgres pg_dump hantu_quant | gzip" > ./backup/hantu_quant_$(date +%Y%m%d).sql.gz

# 전체 데이터 디렉토리 백업
scp -r -i ~/.ssh/id_rsa ubuntu@158.180.87.156:/opt/hantu_quant/data ./backup/

# 로그 백업
scp -r -i ~/.ssh/id_rsa ubuntu@158.180.87.156:/opt/hantu_quant/logs ./backup/
```

### 복구 명령어

```bash
# PostgreSQL 복구
gunzip -c ./backup/***REMOVED***0129.sql.gz | \
  ssh -i ~/.ssh/id_rsa ubuntu@158.180.87.156 \
  "PGPASSWORD='***REMOVED***' psql -U hantu -h localhost hantu_quant"
```

---

## ARM 인스턴스 구성 완료 ✅

ARM 인스턴스(VM.Standard.A1.Flex) 생성 및 배포 완료:

**현재 상태:**

- ✅ hantu-server (158.180.87.156) 생성 완료
- ✅ All-in-One 아키텍처 배포 완료
- ✅ 1 OCPU / 6GB RAM / 50GB Boot Volume 사용 중
- ✅ PostgreSQL 15 + Redis 7 + API Server + Scheduler 실행 중

**향후 확장 가능:**

- 3 OCPU / 18GB RAM 추가 확보 가능 (Free Tier 한도 내)
- hantu-app (x86) 예비 서버로 전환 가능
- hantu-db 통합 완료 (데이터 마이그레이션 완료)

---

## 업데이트 이력

| 날짜       | 내용                                                        |
| ---------- | ----------------------------------------------------------- |
| 2026-01-05 | hantu-app, hantu-db 인스턴스 생성                           |
| 2026-01-05 | hantu-app에 hantu_quant 배포                                |
| 2026-01-06 | hantu-db에 PostgreSQL 16 설치                               |
| 2026-01-29 | ARM 인스턴스(hantu-server) 생성 완료                        |
| 2026-01-29 | All-in-One 아키텍처 배포 (PostgreSQL 15 + Redis + Services) |
| 2026-01-29 | hantu-db에서 hantu-server로 데이터 마이그레이션 완료        |
