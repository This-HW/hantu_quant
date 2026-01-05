-- PostgreSQL 초기화 스크립트
-- hantu_quant 데이터베이스 설정

-- 확장 기능 활성화
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 타임존 설정
SET timezone = 'Asia/Seoul';

-- 기본 스키마 설정
COMMENT ON DATABASE hantu_quant IS 'Hantu Quant Trading System Database';

-- 성능 최적화를 위한 인덱스 힌트
-- (실제 테이블은 SQLAlchemy가 생성하므로 여기서는 설정만)
