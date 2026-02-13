#!/usr/bin/env python3
"""
DB 마이그레이션: RedisMetrics 테이블 생성

Redis 캐싱 시스템 메트릭을 저장하는 테이블을 생성합니다.
- 메모리 사용률, 히트율, 키 개수 등 추적
- 5분 간격 자동 수집
- 임계값 초과 시 텔레그램 알림 연동

실행 방법:
    python scripts/db_migrations/add_redis_metrics_table.py

롤백:
    python scripts/db_migrations/add_redis_metrics_table.py rollback
"""

from sqlalchemy import create_engine, text
from core.config import settings
from core.utils.log_utils import get_logger

logger = get_logger(__name__)


def migrate():
    """RedisMetrics 테이블 생성"""
    try:
        # DB 연결
        engine = create_engine(settings.DATABASE_URL)

        # 테이블 생성 SQL
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS redis_metrics (
            id SERIAL PRIMARY KEY,
            timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

            -- 메모리 메트릭
            used_memory_mb FLOAT NOT NULL,
            max_memory_mb FLOAT NOT NULL,
            memory_usage_percent FLOAT NOT NULL,
            evicted_keys INTEGER DEFAULT 0,

            -- 캐시 성능
            total_keys INTEGER DEFAULT 0,
            keyspace_hits INTEGER DEFAULT 0,
            keyspace_misses INTEGER DEFAULT 0,
            hit_rate_percent FLOAT DEFAULT 0.0,

            -- 성능 지표
            latency_ms FLOAT,

            -- 상태
            is_available INTEGER DEFAULT 1,
            fallback_in_use INTEGER DEFAULT 0,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """

        # 인덱스 생성 SQL
        create_indexes_sql = """
        CREATE INDEX IF NOT EXISTS ix_redis_metrics_timestamp
        ON redis_metrics (timestamp);

        CREATE INDEX IF NOT EXISTS ix_redis_metrics_memory
        ON redis_metrics (memory_usage_percent);

        CREATE INDEX IF NOT EXISTS ix_redis_metrics_hit_rate
        ON redis_metrics (hit_rate_percent);
        """

        with engine.connect() as conn:
            # 트랜잭션 시작
            with conn.begin():
                # 테이블 생성
                conn.execute(text(create_table_sql))
                logger.info("✅ redis_metrics 테이블 생성 완료")

                # 인덱스 생성
                conn.execute(text(create_indexes_sql))
                logger.info("✅ redis_metrics 인덱스 생성 완료")

        logger.info("🎉 마이그레이션 완료")
        return True

    except Exception as e:
        logger.error(f"❌ 마이그레이션 실패: {e}", exc_info=True)
        return False


def rollback():
    """RedisMetrics 테이블 삭제 (롤백)"""
    try:
        engine = create_engine(settings.DATABASE_URL)

        drop_table_sql = "DROP TABLE IF EXISTS redis_metrics CASCADE;"

        with engine.connect() as conn:
            with conn.begin():
                conn.execute(text(drop_table_sql))
                logger.info("✅ redis_metrics 테이블 삭제 완료 (롤백)")

        logger.info("🔄 롤백 완료")
        return True

    except Exception as e:
        logger.error(f"❌ 롤백 실패: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "rollback":
        print("=" * 60)
        print("🔄 RedisMetrics 테이블 롤백 중...")
        print("=" * 60)
        success = rollback()
    else:
        print("=" * 60)
        print("🚀 RedisMetrics 테이블 마이그레이션 중...")
        print("=" * 60)
        success = migrate()

    if success:
        print("\n✅ 작업 성공")
    else:
        print("\n❌ 작업 실패 (로그 확인 필요)")

    sys.exit(0 if success else 1)
