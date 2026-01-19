#!/usr/bin/env python3
"""
SQLite to PostgreSQL Migration Script (T-012)

모든 SQLite 데이터베이스의 데이터를 PostgreSQL로 마이그레이션합니다.

사용법:
    python scripts/migrate_sqlite_to_postgres.py --dry-run  # 테스트 실행
    python scripts/migrate_sqlite_to_postgres.py            # 실제 마이그레이션
    python scripts/migrate_sqlite_to_postgres.py --table screening_history  # 특정 테이블만
"""

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

# 프로젝트 루트 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

from core.database.models import Base
from core.database.session import DatabaseSession
from core.utils.log_utils import get_logger

logger = get_logger(__name__)


# SQLite DB 파일 및 테이블 매핑
SQLITE_DB_MAPPING = {
    "data/learning/learning_data.db": [
        "screening_history",
        "selection_history",
        "performance_tracking",
        "learning_metrics",
    ],
    "data/notification_history.db": [
        "notification_history",
        "notification_stats",
    ],
    "data/system_alerts.db": [
        "system_alerts",
        "alert_settings",
        "alert_statistics",
    ],
    "data/error_recovery.db": [
        "error_events",
        "recovery_rules",
    ],
    "data/api_tracking.db": [
        "api_calls",
    ],
    "data/performance_tracking.db": [
        "backtest_predictions",
        "actual_performance",
        "performance_comparisons",
        "daily_tracking",
    ],
    "data/accuracy_tracking.db": [
        "daily_selections",
        "performance_tracking",
        "daily_accuracy",
    ],
    "data/strategy_performance.db": [
        "strategy_performance",
        "strategy_comparisons",
        "market_regimes",
        "daily_strategy_returns",
    ],
    "data/model_performance.db": [
        "model_performance",
        "performance_alerts",
        "model_baselines",
    ],
}

# SQLite -> PostgreSQL 컬럼 타입 매핑 (필요시)
COLUMN_TYPE_MAPPING = {
    "BOOLEAN": "INTEGER",  # SQLite는 BOOLEAN을 INTEGER로 저장
    "TIMESTAMP": "TEXT",   # SQLite는 TIMESTAMP를 TEXT로 저장
}


class MigrationStats:
    """마이그레이션 통계"""

    def __init__(self):
        self.tables_processed = 0
        self.tables_success = 0
        self.tables_failed = 0
        self.records_migrated = 0
        self.records_failed = 0
        self.start_time = datetime.now()
        self.errors: List[str] = []

    def add_error(self, error: str):
        self.errors.append(error)
        logger.error(error)

    def summary(self) -> Dict[str, Any]:
        elapsed = (datetime.now() - self.start_time).total_seconds()
        return {
            "tables_processed": self.tables_processed,
            "tables_success": self.tables_success,
            "tables_failed": self.tables_failed,
            "records_migrated": self.records_migrated,
            "records_failed": self.records_failed,
            "elapsed_seconds": elapsed,
            "errors_count": len(self.errors),
        }


class SQLiteMigrator:
    """SQLite to PostgreSQL 마이그레이터"""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.stats = MigrationStats()
        self._pg_session = None

    def _get_postgres_session(self):
        """PostgreSQL 세션 반환"""
        if self._pg_session is None:
            db = DatabaseSession()
            Base.metadata.create_all(db.engine)
            Session = sessionmaker(bind=db.engine)
            self._pg_session = Session()
        return self._pg_session

    def _read_sqlite_table(self, db_path: str, table_name: str) -> Tuple[List[str], List[Tuple]]:
        """SQLite 테이블 데이터 읽기"""
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"SQLite DB not found: {db_path}")

        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            # 테이블 존재 확인
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,)
            )
            if not cursor.fetchone():
                raise ValueError(f"Table not found: {table_name} in {db_path}")

            # 컬럼 정보
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [row[1] for row in cursor.fetchall()]

            # 데이터 읽기
            cursor.execute(f"SELECT * FROM {table_name}")
            rows = cursor.fetchall()

            return columns, rows

    def _convert_row_for_postgres(
        self, row: Tuple, columns: List[str], table_name: str
    ) -> Dict[str, Any]:
        """SQLite 행을 PostgreSQL용 딕셔너리로 변환"""
        result = {}
        for i, col in enumerate(columns):
            value = row[i]

            # id 컬럼은 건너뛰기 (auto-increment)
            if col == 'id':
                continue

            # NULL 처리
            if value is None:
                result[col] = None
                continue

            # JSON 문자열 파싱 시도
            if isinstance(value, str) and value.startswith('{') or value.startswith('['):
                try:
                    result[col] = value  # PostgreSQL에서도 TEXT로 저장
                except json.JSONDecodeError:
                    result[col] = value
            else:
                result[col] = value

        return result

    def migrate_table(
        self, db_path: str, table_name: str, batch_size: int = 1000
    ) -> Tuple[int, int]:
        """단일 테이블 마이그레이션

        Returns:
            Tuple[성공 레코드 수, 실패 레코드 수]
        """
        logger.info(f"마이그레이션 시작: {db_path} -> {table_name}")
        success_count = 0
        fail_count = 0

        try:
            columns, rows = self._read_sqlite_table(db_path, table_name)
            total_rows = len(rows)
            logger.info(f"  총 {total_rows}개 레코드 발견")

            if self.dry_run:
                logger.info(f"  [DRY-RUN] {total_rows}개 레코드 마이그레이션 예정")
                return total_rows, 0

            session = self._get_postgres_session()

            # 배치 처리
            for i in range(0, total_rows, batch_size):
                batch = rows[i:i + batch_size]
                batch_data = []

                for row in batch:
                    try:
                        row_dict = self._convert_row_for_postgres(row, columns, table_name)
                        batch_data.append(row_dict)
                    except Exception as e:
                        fail_count += 1
                        self.stats.add_error(f"Row conversion error in {table_name}: {e}")
                        continue

                if batch_data:
                    try:
                        # INSERT 쿼리 생성 (ON CONFLICT DO NOTHING으로 중복 무시)
                        col_names = list(batch_data[0].keys())
                        col_str = ", ".join(col_names)
                        val_str = ", ".join([f":{c}" for c in col_names])

                        insert_sql = text(f"""
                            INSERT INTO {table_name} ({col_str})
                            VALUES ({val_str})
                            ON CONFLICT DO NOTHING
                        """)

                        session.execute(insert_sql, batch_data)
                        success_count += len(batch_data)

                    except SQLAlchemyError as e:
                        fail_count += len(batch_data)
                        self.stats.add_error(f"Batch insert error in {table_name}: {e}")
                        session.rollback()

                # 진행률 표시
                progress = min(i + batch_size, total_rows)
                logger.info(f"  진행: {progress}/{total_rows} ({progress*100//total_rows}%)")

            session.commit()
            logger.info(f"  완료: {success_count} 성공, {fail_count} 실패")

        except FileNotFoundError as e:
            logger.warning(f"  건너뛰기: {e}")
            return 0, 0
        except ValueError as e:
            logger.warning(f"  건너뛰기: {e}")
            return 0, 0
        except Exception as e:
            fail_count = 1
            self.stats.add_error(f"Migration error for {table_name}: {e}")
            logger.error(f"  오류: {e}", exc_info=True)

        return success_count, fail_count

    def run_migration(
        self,
        target_table: Optional[str] = None,
        target_db: Optional[str] = None
    ) -> Dict[str, Any]:
        """전체 마이그레이션 실행"""
        logger.info("=" * 60)
        logger.info("SQLite -> PostgreSQL 마이그레이션 시작")
        logger.info(f"Dry Run: {self.dry_run}")
        logger.info("=" * 60)

        for db_path, tables in SQLITE_DB_MAPPING.items():
            if target_db and target_db != db_path:
                continue

            logger.info(f"\n처리 중: {db_path}")

            for table_name in tables:
                if target_table and target_table != table_name:
                    continue

                self.stats.tables_processed += 1

                try:
                    success, fail = self.migrate_table(db_path, table_name)
                    self.stats.records_migrated += success
                    self.stats.records_failed += fail

                    if fail == 0:
                        self.stats.tables_success += 1
                    else:
                        self.stats.tables_failed += 1

                except Exception as e:
                    self.stats.tables_failed += 1
                    self.stats.add_error(f"Table migration failed: {table_name} - {e}")

        # 세션 정리
        if self._pg_session:
            self._pg_session.close()

        # 결과 요약
        summary = self.stats.summary()
        logger.info("\n" + "=" * 60)
        logger.info("마이그레이션 완료")
        logger.info(f"테이블: {summary['tables_success']}/{summary['tables_processed']} 성공")
        logger.info(f"레코드: {summary['records_migrated']} 마이그레이션됨")
        logger.info(f"소요 시간: {summary['elapsed_seconds']:.2f}초")
        if summary['errors_count'] > 0:
            logger.warning(f"오류: {summary['errors_count']}건")
        logger.info("=" * 60)

        return summary


def main():
    parser = argparse.ArgumentParser(
        description="SQLite to PostgreSQL Migration Script"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="테스트 실행 (실제 데이터 변경 없음)"
    )
    parser.add_argument(
        "--table",
        type=str,
        help="특정 테이블만 마이그레이션"
    )
    parser.add_argument(
        "--db",
        type=str,
        help="특정 SQLite DB만 마이그레이션"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="배치 크기 (기본: 1000)"
    )

    args = parser.parse_args()

    migrator = SQLiteMigrator(dry_run=args.dry_run)
    result = migrator.run_migration(
        target_table=args.table,
        target_db=args.db
    )

    # 결과 저장
    result_file = f"data/migration_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    os.makedirs("data", exist_ok=True)
    with open(result_file, "w") as f:
        json.dump(result, f, indent=2)
    logger.info(f"결과 저장: {result_file}")

    # 종료 코드
    if result["tables_failed"] > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
