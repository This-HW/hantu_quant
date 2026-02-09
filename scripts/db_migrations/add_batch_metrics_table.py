#!/usr/bin/env python3
"""
DB 마이그레이션: BatchMetrics 테이블 생성

실행 방법:
    python scripts/db_migrations/add_batch_metrics_table.py
"""

from sqlalchemy import create_engine, text
from core.config import settings
from core.utils.log_utils import get_logger

logger = get_logger(__name__)


def migrate():
    """BatchMetrics 테이블 생성"""
    try:
        # DB 연결
        engine = create_engine(settings.DATABASE_URL)

        # 테이블 생성 SQL
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS batch_metrics (
            id SERIAL PRIMARY KEY,
            phase_name VARCHAR(20) NOT NULL,
            batch_number INTEGER NOT NULL,
            start_time TIMESTAMP NOT NULL,
            end_time TIMESTAMP NOT NULL,
            duration_seconds FLOAT NOT NULL,
            api_calls_count INTEGER DEFAULT 0,
            stocks_processed INTEGER DEFAULT 0,
            stocks_selected INTEGER DEFAULT 0,
            error_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """

        # 인덱스 생성 SQL
        create_index_sql = """
        CREATE INDEX IF NOT EXISTS ix_batch_metrics_phase_batch_time
        ON batch_metrics (phase_name, batch_number, start_time);
        """

        with engine.connect() as conn:
            # 트랜잭션 시작
            with conn.begin():
                # 테이블 생성
                conn.execute(text(create_table_sql))
                logger.info("batch_metrics 테이블 생성 완료")

                # 인덱스 생성
                conn.execute(text(create_index_sql))
                logger.info("batch_metrics 인덱스 생성 완료")

        logger.info("마이그레이션 완료")
        return True

    except Exception as e:
        logger.error(f"마이그레이션 실패: {e}", exc_info=True)
        return False


def rollback():
    """BatchMetrics 테이블 삭제 (롤백)"""
    try:
        engine = create_engine(settings.DATABASE_URL)

        drop_table_sql = "DROP TABLE IF EXISTS batch_metrics CASCADE;"

        with engine.connect() as conn:
            with conn.begin():
                conn.execute(text(drop_table_sql))
                logger.info("batch_metrics 테이블 삭제 완료 (롤백)")

        return True

    except Exception as e:
        logger.error(f"롤백 실패: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "rollback":
        print("롤백 실행...")
        success = rollback()
    else:
        print("마이그레이션 실행...")
        success = migrate()

    sys.exit(0 if success else 1)
