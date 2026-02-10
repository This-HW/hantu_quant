# 서버 복구 가이드

> OCI 인스턴스 다운 시 복구 절차

---

## 현재 상황 확인

### 증상

- SSH 접속 타임아웃
- Ping 응답 없음 (100% 패킷 손실)
- DB 연결 실패

### 원인 분석

```bash
# 로컬에서 확인
ping -c 3 158.180.87.156
ssh ubuntu@158.180.87.156

# 결과: 타임아웃
# → 서버가 완전히 다운된 상태
```

---

## 복구 절차

### Step 1: OCI 콘솔 접속

1. **브라우저에서 OCI 콘솔 접속**

   ```
   https://cloud.oracle.com/
   ```

2. **로그인**
   - Email: [사용자 이메일]
   - Password: [사용자 비밀번호]

3. **리전 선택**
   - 우측 상단: "Seoul (ap-seoul-1)" 확인

---

### Step 2: 인스턴스 상태 확인

1. **Compute > Instances 이동**

   ```
   좌측 메뉴 > Compute > Instances
   ```

2. **인스턴스 확인**

   ```
   Name: hantu-server
   Public IP: 158.180.87.156
   Status: ? (확인 필요)
   ```

3. **상태별 조치**

   | Status              | 의미          | 조치                     |
   | ------------------- | ------------- | ------------------------ |
   | ⭕ **Running**      | 정상 실행 중  | → Step 3 (네트워크 확인) |
   | ❌ **Stopped**      | 중지됨        | → **재시작** (아래 참조) |
   | ⚠️ **Stopping**     | 중지 중       | → 완료 대기 후 재시작    |
   | ⚠️ **Provisioning** | 프로비저닝 중 | → 완료 대기              |

---

### Step 3: 인스턴스 재시작

**Stopped 상태인 경우:**

1. **인스턴스 선택**
   - hantu-server 클릭

2. **재시작**

   ```
   우측 상단 > More Actions > Start
   또는
   Stop/Start 버튼 클릭
   ```

3. **대기**
   - Status가 "Starting..." → "Running"으로 변경될 때까지 대기 (1-2분)

4. **Public IP 확인**
   - IP가 변경되었는지 확인 (보통 고정 IP이므로 동일)

---

### Step 4: 네트워크 문제 확인

**Running 상태인데도 접속 안 되는 경우:**

#### 4.1 방화벽 규칙 확인

1. **Security List 확인**

   ```
   인스턴스 상세 > Primary VNIC > Subnet > Security Lists
   ```

2. **Ingress Rules 확인**

   ```
   필수 규칙:
   - Source: 0.0.0.0/0, Port: 22 (SSH)
   - Source: [로컬 IP]/32, Port: 5432 (PostgreSQL)
   ```

3. **누락된 경우 추가**
   ```
   Add Ingress Rules 클릭
   Source: 0.0.0.0/0
   IP Protocol: TCP
   Destination Port Range: 22
   ```

#### 4.2 Network Security Group 확인

1. **NSG 확인**

   ```
   인스턴스 상세 > Network Security Groups
   ```

2. **규칙 확인**
   - SSH(22), PostgreSQL(5432) 허용 여부 확인

---

### Step 5: 서버 재부팅 (강제)

**위 방법으로도 안 되는 경우:**

1. **Hard Reboot**

   ```
   More Actions > Reboot
   또는
   More Actions > Stop → Start
   ```

2. **대기**
   - 2-3분 대기

---

## 복구 후 검증

### 로컬에서 연결 테스트

```bash
# 1. Ping 테스트
ping -c 3 158.180.87.156
# 예상: 응답 정상

# 2. SSH 접속 테스트
ssh ubuntu@158.180.87.156 "echo 'connection ok'"
# 예상: "connection ok" 출력

# 3. SSH 터널 재시작
./scripts/db-tunnel.sh start

# 4. SSH 터널 상태 확인
./scripts/db-tunnel.sh status
# 예상: Status: ✅ Running

# 5. DB 연결 테스트
source venv/bin/activate
python3 scripts/diagnose-db.py
# 예상: DB 연결 성공
```

---

## 서버 내부 서비스 확인

**SSH 접속 후:**

```bash
# 1. 시스템 상태 확인
sudo systemctl status hantu-scheduler hantu-api

# 2. 로그 확인
sudo journalctl -u hantu-scheduler -n 50 --no-pager
sudo journalctl -u hantu-api -n 50 --no-pager

# 3. 서비스 재시작 (필요 시)
sudo systemctl restart hantu-scheduler
sudo systemctl restart hantu-api

# 4. 최근 로그 모니터링
tail -f /opt/hantu_quant/logs/scheduler.log
```

---

## 트러블슈팅

### Q1. Status가 "Running"인데 접속 안 됨

**원인**: 네트워크 설정 문제

**해결**:

1. Security List 규칙 확인
2. NSG 규칙 확인
3. 서버 재부팅 (Hard Reboot)

---

### Q2. 재시작해도 계속 멈춤

**원인**: 부팅 문제 또는 디스크 에러

**해결**:

1. OCI 콘솔 > Boot Diagnostics 확인
2. Console Connection 설정 후 직접 콘솔 접속
3. 지원 티켓 생성 (Support > Create Request)

---

### Q3. Public IP가 변경됨

**원인**: Ephemeral IP 사용 (Free Tier 제한)

**해결**:

1. 새 IP를 모든 설정 파일에 업데이트
   - `~/.ssh/config`
   - `scripts/db-tunnel.sh` (REMOTE_HOST)
   - `deploy/SERVERS.md`
2. Git commit 후 CI/CD 재배포

---

## 예방 조치

### 자동 알림 설정 (권장)

```bash
# 서버에 cron 추가 (5분마다 헬스체크)
*/5 * * * * /opt/hantu_quant/scripts/health-check.sh
```

### 모니터링 도구 사용

- OCI Monitoring 대시보드 설정
- Uptime Robot 무료 모니터링 (외부)
- Telegram 알림 활성화

---

## 참고 문서

- [OCI 문서: Troubleshooting Instances](https://docs.oracle.com/en-us/iaas/Content/Compute/Tasks/troubleshootinginstances.htm)
- [deploy/SERVERS.md](../deploy/SERVERS.md) - 서버 정보
- [scripts/db-tunnel.sh](../../scripts/db-tunnel.sh) - SSH 터널 스크립트
