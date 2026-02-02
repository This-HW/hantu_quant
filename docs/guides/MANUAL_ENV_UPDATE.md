# .env.example 수동 업데이트 필요

## 배경

Phase 2 계획에 따라 DATABASE_URL 환경변수의 우선순위와 자동 감지 동작을 명확히 문서화했습니다.

`.env.example` 파일은 보안 훅으로 보호되어 있어 자동 수정이 불가능합니다.
따라서 **수동으로** 아래 내용을 반영해야 합니다.

## 필요한 변경사항

### .env.example 파일 위치

`/Users/grimm/Documents/Dev/hantu_quant/.env.example`

### 수정할 섹션: DATABASE_URL

**현재 상태** (예상):

```bash
# DATABASE_URL - PostgreSQL 연결 문자열
DATABASE_URL=postgresql://hantu@localhost:15432/hantu_quant
```

**변경 후**:

```bash
# DATABASE_URL - PostgreSQL 연결 문자열
# ⚠️ 이 값을 설정하면 settings.py의 자동 감지를 오버라이드합니다!
# 권장: 이 항목을 제거하고 자동 감지 사용 (HANTU_ENV 또는 경로 기반)
#
# 자동 감지 동작:
# - 로컬 (/Users/*, /home/username): localhost:15432 (SSH 터널)
# - 서버 (/opt/*, /home/ubuntu): localhost:5432 (직접 연결)
#
# 수동 설정이 필요한 경우에만 아래 주석 해제:
# DATABASE_URL=postgresql://hantu@localhost:15432/hantu_quant
```

### 추가할 섹션: HANTU_ENV (선택사항)

```bash
# HANTU_ENV - 환경 명시 (선택사항)
# 설정하지 않으면 프로젝트 경로로 자동 감지됨
# 값: local (로컬 개발), server (서버), test (테스트)
#
# HANTU_ENV=local
```

## 수동 업데이트 단계

1. `.env.example` 파일 열기:

   ```bash
   vim .env.example
   # 또는
   code .env.example
   ```

2. DATABASE_URL 섹션 찾기 (Ctrl+F 또는 /DATABASE_URL)

3. 위의 "변경 후" 내용으로 교체

4. 파일 저장

5. 기존 .env 파일 업데이트 (개발자별):
   ```bash
   # DATABASE_URL 라인 제거 또는 주석 처리
   vim .env
   ```

## 검증

수정 후 다음 명령으로 동작 확인:

```bash
# 1. SSH 터널 시작
./scripts/db-tunnel.sh start

# 2. 환경 감지 확인
python -c "from core.config.settings import DATABASE_URL; print(DATABASE_URL)"
# 예상 출력: postgresql://hantu@localhost:15432/hantu_quant (로컬)

# 3. 연결 테스트
python scripts/diagnose-db.py
```

## 완료된 작업

- ✅ CLAUDE.md 업데이트 (DATABASE_URL 우선순위 섹션 추가)
- ✅ 환경 변수 섹션 업데이트 (트러블슈팅 추가)
- ✅ docs/guides/env-setup.md 생성 (상세 가이드)
- ⚠️ .env.example 업데이트 (수동 작업 필요)

## 참고 문서

- [환경 변수 설정 가이드](./env-setup.md)
- [CLAUDE.md - 인프라 구성](../../CLAUDE.md#인프라-구성)
- [CLAUDE.md - 환경 변수](../../CLAUDE.md#환경-변수)
