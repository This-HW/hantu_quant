-- PostgreSQL 마이그레이션 스크립트
-- 버전: 1.1
-- 날짜: 2026-01-23
-- 설명: trade_history 테이블에 Phase 2 예측 정보 컬럼 추가
-- 데이터 상태: 0건 (안전)

-- 타임존 설정
SET timezone = 'Asia/Seoul';

-- 마이그레이션 시작 로그
DO $$
BEGIN
    RAISE NOTICE '마이그레이션 시작: trade_history 컬럼 추가 (v1.1)';
    RAISE NOTICE '현재 시각: %', NOW();
END $$;

-- 기존 데이터 확인 (참고용)
DO $$
DECLARE
    row_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO row_count FROM trade_history;
    RAISE NOTICE 'trade_history 기존 레코드 수: %', row_count;
END $$;

-- 컬럼 추가 (IF NOT EXISTS로 중복 실행 안전)
ALTER TABLE trade_history ADD COLUMN IF NOT EXISTS entry_price DOUBLE PRECISION;
ALTER TABLE trade_history ADD COLUMN IF NOT EXISTS target_price DOUBLE PRECISION;
ALTER TABLE trade_history ADD COLUMN IF NOT EXISTS stop_loss_price DOUBLE PRECISION;
ALTER TABLE trade_history ADD COLUMN IF NOT EXISTS expected_return DOUBLE PRECISION;
ALTER TABLE trade_history ADD COLUMN IF NOT EXISTS predicted_probability DOUBLE PRECISION;
ALTER TABLE trade_history ADD COLUMN IF NOT EXISTS predicted_class INTEGER;
ALTER TABLE trade_history ADD COLUMN IF NOT EXISTS model_name VARCHAR(50);

-- 컬럼 코멘트 추가 (문서화)
COMMENT ON COLUMN trade_history.entry_price IS 'Phase 2: 진입가';
COMMENT ON COLUMN trade_history.target_price IS 'Phase 2: 목표가';
COMMENT ON COLUMN trade_history.stop_loss_price IS 'Phase 2: 손절가';
COMMENT ON COLUMN trade_history.expected_return IS 'Phase 2: 예상 수익률 (%)';
COMMENT ON COLUMN trade_history.predicted_probability IS 'Phase 2: 예측 신뢰도 (0-1)';
COMMENT ON COLUMN trade_history.predicted_class IS 'Phase 2: 예측 분류 (0: 실패, 1: 성공)';
COMMENT ON COLUMN trade_history.model_name IS 'Phase 2: 예측 모델명';

-- 마이그레이션 완료 확인
DO $$
DECLARE
    col_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO col_count
    FROM information_schema.columns
    WHERE table_name = 'trade_history'
    AND column_name IN (
        'entry_price', 'target_price', 'stop_loss_price',
        'expected_return', 'predicted_probability',
        'predicted_class', 'model_name'
    );

    IF col_count = 7 THEN
        RAISE NOTICE '마이그레이션 성공: 7개 컬럼 모두 추가됨';
    ELSE
        RAISE WARNING '마이그레이션 경고: 추가된 컬럼 수 = % (예상: 7)', col_count;
    END IF;
END $$;

-- 결과 출력
SELECT
    column_name,
    data_type,
    is_nullable,
    col_description((table_schema || '.' || table_name)::regclass, ordinal_position) as comment
FROM information_schema.columns
WHERE table_name = 'trade_history'
ORDER BY ordinal_position;

-- 마이그레이션 종료 로그
DO $$
BEGIN
    RAISE NOTICE '마이그레이션 완료: %', NOW();
END $$;
