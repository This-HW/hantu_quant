# SSH 터널 자동 시작 - 빠른 시작 가이드

## ✅ 설정 완료!

SSH 터널 자동 시작이 `~/.zshrc`에 설정되었습니다.

## 동작 방식

### 자동 시작 조건

1. **프로젝트 디렉토리 진입 시**

   ```bash
   cd ~/Documents/Dev/hantu_quant
   # 🔗 Starting SSH tunnel for Hantu Quant...
   # ✅ SSH tunnel ready (localhost:15432)
   ```

2. **새 터미널 열기**
   - 프로젝트 디렉토리에서 터미널을 열면 자동 시작
   - iTerm2, Terminal.app 모두 지원

3. **VS Code 터미널**
   - VS Code에서 프로젝트를 열면 통합 터미널에서 자동 시작

### 중복 실행 방지

- 15432 포트가 이미 사용 중이면 스킵
- 여러 터미널을 열어도 1개의 터널만 실행

## 수동 제어

자동 시작과 상관없이 언제든지 수동 제어 가능:

```bash
# 상태 확인
./scripts/db-tunnel.sh status

# 중지
./scripts/db-tunnel.sh stop

# 시작
./scripts/db-tunnel.sh start

# 재시작
./scripts/db-tunnel.sh restart
```

## 테스트

### 1. 자동 시작 테스트

```bash
# 1. 터널 중지
./scripts/db-tunnel.sh stop

# 2. 새 터미널 열기 또는
source ~/.zshrc

# 3. 자동 시작 메시지 확인
# 🔗 Starting SSH tunnel for Hantu Quant...
# ✅ SSH tunnel ready (localhost:15432)
```

### 2. DB 연결 테스트

```bash
# Python으로 연결 테스트
python3 << 'EOF'
import psycopg2
conn = psycopg2.connect(host="localhost", port=15432, database="hantu_quant", user="hantu")
cur = conn.cursor()
cur.execute("SELECT version();")
print("✅ DB 연결 성공:", cur.fetchone()[0])
conn.close()
EOF
```

## 로그 확인

자동 시작 로그는 백그라운드에서 실행되므로:

```bash
# 터널 로그
tail -f logs/db-tunnel.log

# 터널 상태 (실시간)
watch -n 1 './scripts/db-tunnel.sh status'
```

## 비활성화

자동 시작을 끄려면:

```bash
# 1. ~/.zshrc 편집
vim ~/.zshrc

# 2. 다음 섹션 주석 처리 또는 삭제
# # ========================================
# # Hantu Quant SSH Tunnel Auto-Start
# # ========================================
# ... (삭제)

# 3. 적용
source ~/.zshrc
```

## 트러블슈팅

### 자동 시작이 안 됨

**원인**: 스크립트 권한 문제

```bash
# 실행 권한 확인
ls -l ~/Documents/Dev/hantu_quant/scripts/db-tunnel.sh

# 권한 부여
chmod +x ~/Documents/Dev/hantu_quant/scripts/db-tunnel.sh
```

**원인**: .zshrc 문법 오류

```bash
# .zshrc 테스트
zsh -n ~/.zshrc

# 에러가 있으면 수정
vim ~/.zshrc
```

### 터미널 시작이 느려짐

**원인**: 터널 시작 대기 시간 (최대 3초)

**해결**: 대기 시간 단축 (선택 사항)

```bash
# ~/.zshrc 편집
vim ~/.zshrc

# 다음 부분 수정
for i in {1..6}; do  # 3초 대기
    # ...
done

# 변경 →
for i in {1..2}; do  # 1초 대기
    # ...
done
```

### SSH 키 문제

```bash
# SSH 키 확인
ls -la ~/.ssh/id_rsa

# 권한 확인
chmod 600 ~/.ssh/id_rsa

# 서버 연결 테스트
ssh -i ~/.ssh/id_rsa ubuntu@158.180.87.156 "echo OK"
```

### 포트 충돌

```bash
# 15432 포트 사용 프로세스 확인
lsof -i :15432

# 다른 프로세스가 사용 중이면 종료 또는
# .env에서 DATABASE_URL 포트 변경 (비권장)
```

## 참고

### 관련 문서

- [SSH 터널 상세 가이드](./auto-tunnel-setup.md)
- [환경 변수 설정](./env-setup.md)
- [DB 연결 진단](../../scripts/diagnose-db.py)

### 설정 위치

- **자동 시작**: `~/.zshrc` (마지막 섹션)
- **터널 스크립트**: `scripts/db-tunnel.sh`
- **로그**: `logs/db-tunnel.log`

### 서버 정보

- **원격**: ubuntu@158.180.87.156:5432
- **로컬**: localhost:15432
- **DB**: hantu_quant
- **User**: hantu (비밀번호는 ~/.pgpass)
