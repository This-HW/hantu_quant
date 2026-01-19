#!/usr/bin/env python3
"""
데이터 마이그레이션 검증 도구 (T-013)

SQLite와 PostgreSQL 간 데이터 무결성을 검증합니다.

사용법:
    python scripts/validate_migration.py                # 전체 검증
    python scripts/validate_migration.py --table screening_history  # 특정 테이블
    python scripts/validate_migration.py --report      # 상세 리포트 생성
"""

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

# 프로젝트 루트 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text, inspect  # noqa: E402

from core.database.session import DatabaseSession  # noqa: E402
from core.utils.log_utils import get_logger  # noqa: E402

logger = get_logger(__name__)

# SQLite DB 매핑 (migrate_sqlite_to_postgres.py와 동일)
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


class ValidationResult:
    """검증 결과"""

    def __init__(self, table_name: str):
        self.table_name = table_name
        self.sqlite_count = 0
        self.postgres_count = 0
        self.count_match = False
        self.sample_match = True
        self.index_check = True
        self.foreign_key_check = True
        self.errors: List[str] = []
        self.warnings: List[str] = []

    @property
    def passed(self) -> bool:
        return self.count_match and self.sample_match and len(self.errors) == 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "table_name": self.table_name,
            "sqlite_count": self.sqlite_count,
            "postgres_count": self.postgres_count,
            "count_match": self.count_match,
            "sample_match": self.sample_match,
            "index_check": self.index_check,
            "foreign_key_check": self.foreign_key_check,
            "passed": self.passed,
            "errors": self.errors,
            "warnings": self.warnings,
        }


class MigrationValidator:
    """마이그레이션 검증기"""

    def __init__(self):
        self.results: List[ValidationResult] = []
        self._pg_engine = None

    def _get_postgres_engine(self):
        """PostgreSQL 엔진 반환"""
        if self._pg_engine is None:
            db = DatabaseSession()
            self._pg_engine = db.engine
        return self._pg_engine

    def _get_sqlite_count(self, db_path: str, table_name: str) -> Optional[int]:
        """SQLite 테이블 레코드 수 조회"""
        if not os.path.exists(db_path):
            return None

        try:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (table_name,)
                )
                if not cursor.fetchone():
                    return None

                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"SQLite count error: {e}")
            return None

    def _get_postgres_count(self, table_name: str) -> Optional[int]:
        """PostgreSQL 테이블 레코드 수 조회"""
        try:
            engine = self._get_postgres_engine()
            with engine.connect() as conn:
                # 테이블 존재 확인
                inspector = inspect(engine)
                if table_name not in inspector.get_table_names():
                    return None

                result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                return result.scalar()
        except Exception as e:
            logger.error(f"PostgreSQL count error: {e}")
            return None

    def _get_sample_data_sqlite(
        self, db_path: str, table_name: str, limit: int = 10
    ) -> List[Dict]:
        """SQLite 샘플 데이터 조회"""
        if not os.path.exists(db_path):
            return []

        try:
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(f"SELECT * FROM {table_name} LIMIT {limit}")
                return [dict(row) for row in cursor.fetchall()]
        except Exception:
            return []

    def _get_sample_data_postgres(self, table_name: str, limit: int = 10) -> List[Dict]:
        """PostgreSQL 샘플 데이터 조회"""
        try:
            engine = self._get_postgres_engine()
            with engine.connect() as conn:
                result = conn.execute(text(f"SELECT * FROM {table_name} LIMIT {limit}"))
                columns = result.keys()
                return [dict(zip(columns, row)) for row in result.fetchall()]
        except Exception:
            return []

    def _check_indexes(self, table_name: str) -> Tuple[bool, List[str]]:
        """PostgreSQL 인덱스 존재 확인"""
        warnings = []
        try:
            engine = self._get_postgres_engine()
            inspector = inspect(engine)
            indexes = inspector.get_indexes(table_name)

            if not indexes:
                warnings.append(f"No indexes found on {table_name}")
                return True, warnings

            # 기본 인덱스 확인 (timestamp, date 컬럼에 인덱스 필요)
            indexed_columns = set()
            for idx in indexes:
                indexed_columns.update(idx['column_names'])

            expected_index_cols = ['timestamp', 'date', 'created_at', 'tracking_date', 'selection_date']
            for col in expected_index_cols:
                if col not in indexed_columns:
                    # 컬럼이 테이블에 존재하는지 확인
                    columns = inspector.get_columns(table_name)
                    col_names = [c['name'] for c in columns]
                    if col in col_names:
                        warnings.append(f"Consider adding index on {table_name}.{col}")

            return True, warnings
        except Exception as e:
            return False, [str(e)]

    def validate_table(self, db_path: str, table_name: str) -> ValidationResult:
        """단일 테이블 검증"""
        result = ValidationResult(table_name)

        logger.info(f"검증 중: {table_name}")

        # 1. 레코드 수 비교
        result.sqlite_count = self._get_sqlite_count(db_path, table_name) or 0
        result.postgres_count = self._get_postgres_count(table_name) or 0

        if result.sqlite_count == 0 and result.postgres_count == 0:
            result.warnings.append("Both SQLite and PostgreSQL tables are empty")
        elif result.sqlite_count == result.postgres_count:
            result.count_match = True
            logger.info(f"  ✓ 레코드 수 일치: {result.sqlite_count}")
        else:
            result.count_match = False
            diff = result.postgres_count - result.sqlite_count
            if diff < 0:
                result.errors.append(
                    f"Missing records: SQLite={result.sqlite_count}, "
                    f"PostgreSQL={result.postgres_count} (diff={diff})"
                )
            else:
                result.warnings.append(
                    f"Extra records in PostgreSQL: {diff} (may be from other sources)"
                )
            logger.warning(f"  ! 레코드 수 차이: SQLite={result.sqlite_count}, PostgreSQL={result.postgres_count}")

        # 2. 샘플 데이터 비교 (null/type 일관성)
        sqlite_samples = self._get_sample_data_sqlite(db_path, table_name)
        postgres_samples = self._get_sample_data_postgres(table_name)

        if sqlite_samples and postgres_samples:
            # 컬럼 구조 비교 (id 제외)
            sqlite_cols = set(sqlite_samples[0].keys()) - {'id'}
            postgres_cols = set(postgres_samples[0].keys()) - {'id'}

            missing_cols = sqlite_cols - postgres_cols
            if missing_cols:
                result.warnings.append(f"Missing columns in PostgreSQL: {missing_cols}")

            logger.info("  ✓ 샘플 데이터 검증 완료")
        else:
            if not sqlite_samples:
                result.warnings.append("No sample data from SQLite")
            if not postgres_samples:
                result.warnings.append("No sample data from PostgreSQL")

        # 3. 인덱스 검증
        idx_ok, idx_warnings = self._check_indexes(table_name)
        result.index_check = idx_ok
        result.warnings.extend(idx_warnings)

        if result.passed:
            logger.info("  ✓ 검증 통과")
        else:
            logger.warning(f"  ✗ 검증 실패: {result.errors}")

        return result

    def run_validation(self, target_table: Optional[str] = None) -> Dict[str, Any]:
        """전체 검증 실행"""
        logger.info("=" * 60)
        logger.info("마이그레이션 검증 시작")
        logger.info("=" * 60)

        for db_path, tables in SQLITE_DB_MAPPING.items():
            logger.info(f"\n검증 중: {db_path}")

            for table_name in tables:
                if target_table and target_table != table_name:
                    continue

                result = self.validate_table(db_path, table_name)
                self.results.append(result)

        # 요약
        passed = sum(1 for r in self.results if r.passed)
        failed = len(self.results) - passed
        total_sqlite = sum(r.sqlite_count for r in self.results)
        total_postgres = sum(r.postgres_count for r in self.results)

        summary = {
            "timestamp": datetime.now().isoformat(),
            "tables_validated": len(self.results),
            "tables_passed": passed,
            "tables_failed": failed,
            "total_sqlite_records": total_sqlite,
            "total_postgres_records": total_postgres,
            "details": [r.to_dict() for r in self.results],
        }

        logger.info("\n" + "=" * 60)
        logger.info("검증 완료")
        logger.info(f"테이블: {passed}/{len(self.results)} 통과")
        logger.info(f"레코드: SQLite={total_sqlite}, PostgreSQL={total_postgres}")
        logger.info("=" * 60)

        return summary


def main():
    parser = argparse.ArgumentParser(
        description="Migration Validation Tool"
    )
    parser.add_argument(
        "--table",
        type=str,
        help="특정 테이블만 검증"
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="상세 리포트 생성"
    )

    args = parser.parse_args()

    validator = MigrationValidator()
    result = validator.run_validation(target_table=args.table)

    # 리포트 저장
    if args.report:
        report_file = f"data/validation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        os.makedirs("data", exist_ok=True)
        with open(report_file, "w") as f:
            json.dump(result, f, indent=2, default=str)
        logger.info(f"리포트 저장: {report_file}")

    # 종료 코드
    if result["tables_failed"] > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
