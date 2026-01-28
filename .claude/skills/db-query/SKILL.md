---
name: db-query
description: Execute database queries using PostgreSQL MCP. Use when users want to run SQL queries, analyze data, check schema, or optimize queries.
---

# Database Query

PostgreSQL MCP를 사용하여 데이터베이스 쿼리를 실행합니다.

## 사전 요구사항

SSH 터널이 실행 중이어야 합니다:

```bash
# 터널 시작
ssh -i ~/.ssh/id_rsa -f -N -L 15432:localhost:5432 ubuntu@158.180.87.156

# 또는 스크립트 사용
./scripts/ssh-tunnel.sh start
```

## 사용법

### 스키마 조회

```
/db-query show tables
/db-query describe users
/db-query show schema
```

### 데이터 조회

```
/db-query SELECT * FROM stocks LIMIT 10
/db-query count records in orders table
```

### 성능 분석

```
/db-query EXPLAIN ANALYZE SELECT ...
/db-query show slow queries
/db-query index usage stats
```

## 워크플로우

1. **SSH 터널 확인**
   - `lsof -i:15432`로 터널 상태 확인
   - 없으면 터널 시작

2. **PostgreSQL MCP 사용**
   - 쿼리 실행
   - 결과 분석
   - 필요시 최적화 제안

3. **결과 보고**
   - 결과 요약
   - 인사이트 도출
   - 추가 분석 제안

## 연결 정보

| 항목 | 값 |
|------|-----|
| Host | localhost |
| Port | 15432 |
| Database | hantu_quant |
| User | hantu |

## 관련 에이전트

- **analyze-data**: 데이터 품질 분석, 통계 분석
- **optimize-queries**: 쿼리 최적화, 실행계획 분석
