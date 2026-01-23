# Database Migration Log

> 데이터베이스 스키마 변경 이력을 기록합니다.

---

## v1.1 - trade_history Phase 2 컬럼 추가

**날짜**: 2026-01-23
**대상**: PostgreSQL (hantu-db 서버)
**스크립트**: `deploy/migrate_trade_history_v1.1.sql`

### 변경 내용

`trade_history` 테이블에 Phase 2 예측 정보 컬럼 7개 추가:

| 컬럼명                  | 타입             | 설명                         |
| ----------------------- | ---------------- | ---------------------------- |
| `entry_price`           | DOUBLE PRECISION | 진입가                       |
| `target_price`          | DOUBLE PRECISION | 목표가                       |
| `stop_loss_price`       | DOUBLE PRECISION | 손절가                       |
| `expected_return`       | DOUBLE PRECISION | 예상 수익률 (%)              |
| `predicted_probability` | DOUBLE PRECISION | 예측 신뢰도 (0-1)            |
| `predicted_class`       | INTEGER          | 예측 분류 (0: 실패, 1: 성공) |
| `model_name`            | VARCHAR(50)      | 예측 모델명                  |

### 배경

- ORM 모델(`core/database/models.py`)에 Phase 2 컬럼이 정의되어 있었으나 DB 스키마에 반영되지 않음
- `Base.metadata.create_all()` 방식은 기존 테이블을 수정하지 않음
- 에러 발생: `column trade_history.entry_price does not exist` (30분마다 반복)

### 실행 결과

```
마이그레이션 시작: trade_history 컬럼 추가 (v1.1)
trade_history 기존 레코드 수: 0
마이그레이션 성공: 7개 컬럼 모두 추가됨
```

### 검증

```sql
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'trade_history'
AND column_name IN ('entry_price', 'target_price', 'stop_loss_price',
                    'expected_return', 'predicted_probability',
                    'predicted_class', 'model_name');
-- 결과: 7개 컬럼 확인
```

### 롤백 (필요시)

```sql
ALTER TABLE trade_history DROP COLUMN IF EXISTS entry_price;
ALTER TABLE trade_history DROP COLUMN IF EXISTS target_price;
ALTER TABLE trade_history DROP COLUMN IF EXISTS stop_loss_price;
ALTER TABLE trade_history DROP COLUMN IF EXISTS expected_return;
ALTER TABLE trade_history DROP COLUMN IF EXISTS predicted_probability;
ALTER TABLE trade_history DROP COLUMN IF EXISTS predicted_class;
ALTER TABLE trade_history DROP COLUMN IF EXISTS model_name;
```

---

## 마이그레이션 가이드

### 새 마이그레이션 추가 시

1. `deploy/migrate_<table>_v<version>.sql` 파일 생성
2. `IF NOT EXISTS` 또는 `ADD COLUMN IF NOT EXISTS` 사용 (멱등성 보장)
3. 컬럼 코멘트 추가 (문서화)
4. 이 파일에 변경 이력 기록

### 실행 방법

```bash
# SSH 접속 후 실행
ssh ubuntu@168.107.3.196
cd /tmp
# 스크립트 복사 후
psql -U hantu_quant -d hantu_quant -f migrate_trade_history_v1.1.sql
```
