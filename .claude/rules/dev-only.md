# 개발 환경 보호 규칙

> 운영 서버 직접 수정을 방지하고 안전한 개발 플로우를 보장합니다.

---

## 환경별 규칙

### 1. 서버 환경 (/home/ubuntu/)

#### ✅ 허용

**개발 작업 (dev 레포)**:
- `/home/ubuntu/hantu_quant_dev/**` 모든 작업 가능
  - Edit, Write, git commit/push
  - 테스트 실행
  - 로컬 서비스 재시작 (필요 시)

**운영 모니터링 (prd 레포)**:
- `/opt/hantu_quant/**` 읽기만 가능
  - Read: 로그 확인, 코드 참조
  - Bash: 로그 조회 (tail, grep)
  - 상태 확인 (systemctl status)

#### ❌ 금지

```bash
# /opt/hantu_quant 파일 수정
❌ Edit /opt/hantu_quant/core/...
❌ Write /opt/hantu_quant/config/...
❌ cd /opt/hantu_quant && git commit

# 운영 서비스 제어
❌ systemctl restart hantu-scheduler
❌ systemctl restart hantu-api
❌ systemctl stop hantu-*

# 예외: 상태 확인은 가능
✅ systemctl status hantu-*
✅ journalctl -u hantu-*
```

---

### 2. 로컬 PC 환경 (/Users/grimm/)

#### ✅ 제한 없음

- 로컬 개발 환경이므로 모든 작업 자유
- git push → CI/CD 자동 배포

---

## 올바른 개발 플로우

### 서버에서 작업 시

```bash
# 1. dev 레포에서 개발
cd /home/ubuntu/hantu_quant_dev
vim core/api/market_data_client.py  # 코드 수정

# 2. 테스트 (선택)
python test_something.py

# 3. git 작업
git add .
git commit -m "fix: ..."
git push origin main

# 4. CI/CD 자동 배포 대기 (2-4분)
# - 텔레그램 알림 확인
# - 배포 완료 후 /opt/hantu_quant 로그 확인
tail -f /opt/hantu_quant/logs/scheduler.log  # ✅ 읽기 OK
```

### 로컬 PC에서 작업 시

```bash
# 로컬 작업 → push → CI/CD 자동 배포
cd /Users/grimm/hantu_quant
# ... 작업 ...
git push origin main
```

---

## 긴급 상황 (Hotfix)

**원칙**: hotfix 하지 않음 (CI/CD로만 배포)

**만약 정말 긴급하다면**:
1. 사용자에게 명시적 승인 요청
2. `[skip ci]` 커밋 메시지 사용
3. 작업 후 즉시 dev 레포 동기화

---

## 위반 사례 (이전 실수)

```bash
# ❌ 잘못된 예
cd /opt/hantu_quant
vim core/api/market_data_client.py  # 운영 서버 직접 수정
sudo systemctl restart hantu-scheduler  # 테스트 없이 재시작
git commit && git push  # 운영에서 직접 push

# 결과: 운영 환경에 테스트되지 않은 코드 즉시 반영
```

---

## 체크리스트

### 코드 수정 전

- [ ] 현재 경로가 `/home/ubuntu/hantu_quant_dev`인가?
- [ ] `/opt/hantu_quant` 경로를 수정하려고 하지 않는가?

### 서비스 재시작 전

- [ ] 정말 필요한가? (CI/CD가 자동으로 처리함)
- [ ] dev 환경인가? (prd 서비스 재시작 금지)

### git push 전

- [ ] dev 레포에서 작업했는가?
- [ ] CI/CD가 자동 배포할 준비가 되었는가?
