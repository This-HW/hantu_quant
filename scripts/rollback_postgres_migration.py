#!/usr/bin/env python3
"""
PostgreSQL 마이그레이션 롤백 스크립트 (T-014)

PostgreSQL 데이터를 삭제하고 SQLite 폴백을 활성화합니다.

사용법:
    python scripts/rollback_postgres_migration.py --dry-run  # 테스트 실행
    python scripts/rollback_postgres_migration.py            # 실제 롤백
    python scripts/rollback_postgres_migration.py --table screening_history  # 특정 테이블만
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

# 프로젝트 루트 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text, inspect
from sqlalchemy.exc import SQLAlchemyError

from core.database.session import DatabaseSession
from core.utils.log_utils import get_logger

logger = get_logger(__name__)

# 롤백 대상 테이블 목록 (마이그레이션된 테이블들)
ROLLBACK_TABLES = [
    # learning_data.db
    "screening_history",
    "selection_history",
    "performance_tracking",
    "learning_metrics",
    # notification_history.db
    "notification_history",
    "notification_stats",
    # system_alerts.db
    "system_alerts",
    "alert_settings",
    "alert_statistics",
    # error_recovery.db
    "error_events",
    "recovery_rules",
    # api_tracking.db
    "api_calls",
    # performance_tracking.db
    "backtest_predictions",
    "actual_performance",
    "performance_comparisons",
    "daily_tracking",
    # accuracy_tracking.db
    "daily_selections",
    "daily_accuracy",
    # strategy_performance.db
    "strategy_performance",
    "strategy_comparisons",
    "market_regimes",
    "daily_strategy_returns",
    # model_performance.db
    "model_performance",
    "performance_alerts",
    "model_baselines",
]

# 외래키 의존성에 따른 삭제 순서 (자식 테이블 먼저)
DELETION_ORDER = [
    # 자식 테이블 먼저
    "actual_performance",
    "performance_comparisons",
    # 나머지 테이블
    "backtest_predictions",
    "screening_history",
    "selection_history",
    "performance_tracking",
    "learning_metrics",
    "notification_history",
    "notification_stats",
    "system_alerts",
    "alert_settings",
    "alert_statistics",
    "error_events",
    "recovery_rules",
    "api_calls",
    "daily_tracking",
    "daily_selections",
    "daily_accuracy",
    "strategy_performance",
    "strategy_comparisons",
    "market_regimes",
    "daily_strategy_returns",
    "model_performance",
    "performance_alerts",
    "model_baselines",
]


class RollbackStats:
    """롤백 통계"""

    def __init__(self):
        self.tables_processed = 0
        self.tables_success = 0
        self.tables_failed = 0
        self.records_deleted = 0
        self.start_time = datetime.now()
        self.errors: List[str] = []

    def add_error(self, error: str):
        self.errors.append(error)
        logger.error(error)

    def summary(self) -> Dict[str, Any]:
        elapsed = (datetime.now() - self.start_time).total_seconds()
        return {
            "timestamp": datetime.now().isoformat(),
            "tables_processed": self.tables_processed,
            "tables_success": self.tables_success,
            "tables_failed": self.tables_failed,
            "records_deleted": self.records_deleted,
            "elapsed_seconds": elapsed,
            "errors_count": len(self.errors),
            "errors": self.errors,
        }


class PostgresRollback:
    """PostgreSQL 롤백 관리자"""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.stats = RollbackStats()
        self._pg_engine = None

    def _get_postgres_engine(self):
        """PostgreSQL 엔진 반환"""
        if self._pg_engine is None:
            db = DatabaseSession()
            self._pg_engine = db.engine
        return self._pg_engine

    def _get_table_count(self, table_name: str) -> int:
        """테이블 레코드 수 조회"""
        try:
            engine = self._get_postgres_engine()
            with engine.connect() as conn:
                result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                return result.scalar() or 0
        except Exception:
            return 0

    def _table_exists(self, table_name: str) -> bool:
        """테이블 존재 확인"""
        try:
            engine = self._get_postgres_engine()
            inspector = inspect(engine)
            return table_name in inspector.get_table_names()
        except Exception:
            return False

    def delete_table_data(self, table_name: str) -> int:
        """테이블 데이터 삭제

        Returns:
            삭제된 레코드 수
        """
        logger.info(f"롤백 중: {table_name}")

        if not self._table_exists(table_name):
            logger.warning(f"  테이블 없음: {table_name}")
            return 0

        count = self._get_table_count(table_name)
        logger.info(f"  현재 레코드 수: {count}")

        if count == 0:
            logger.info(f"  건너뛰기: 데이터 없음")
            return 0

        if self.dry_run:
            logger.info(f"  [DRY-RUN] {count}개 레코드 삭제 예정")
            return count

        try:
            engine = self._get_postgres_engine()
            with engine.begin() as conn:
                result = conn.execute(text(f"DELETE FROM {table_name}"))
                deleted = result.rowcount
                logger.info(f"  ✓ {deleted}개 레코드 삭제 완료")
                return deleted
        except SQLAlchemyError as e:
            self.stats.add_error(f"Delete error for {table_name}: {e}")
            return 0

    def set_fallback_flag(self, enable: bool = True):
        """SQLite 폴백 플래그 설정

        환경 변수 또는 설정 파일로 폴백 모드 활성화
        """
        fallback_file = project_root / ".use_sqlite_fallback"

        if enable:
            logger.info("SQLite 폴백 모드 활성화")
            if not self.dry_run:
                with open(fallback_file, "w") as f:
                    f.write(f"# SQLite fallback enabled at {datetime.now().isoformat()}\n")
                    f.write("USE_SQLITE_FALLBACK=true\n")
                logger.info(f"  ✓ 폴백 플래그 파일 생성: {fallback_file}")
        else:
            logger.info("SQLite 폴백 모드 비활성화")
            if not self.dry_run and fallback_file.exists():
                fallback_file.unlink()
                logger.info(f"  ✓ 폴백 플래그 파일 제거")

    def create_rollback_log(self):
        """롤백 로그 생성"""
        log_dir = project_root / "data" / "rollback_logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        log_file = log_dir / f"rollback_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        log_data = {
            "timestamp": datetime.now().isoformat(),
            "dry_run": self.dry_run,
            "stats": self.stats.summary(),
        }

        if not self.dry_run:
            with open(log_file, "w") as f:
                json.dump(log_data, f, indent=2)
            logger.info(f"롤백 로그 저장: {log_file}")

        return log_data

    def run_rollback(
        self,
        target_table: Optional[str] = None,
        keep_schema: bool = True
    ) -> Dict[str, Any]:
        """롤백 실행

        Args:
            target_table: 특정 테이블만 롤백
            keep_schema: 테이블 스키마 유지 (데이터만 삭제)
        """
        logger.info("=" * 60)
        logger.info("PostgreSQL 마이그레이션 롤백 시작")
        logger.info(f"Dry Run: {self.dry_run}")
        logger.info(f"Keep Schema: {keep_schema}")
        logger.info("=" * 60)

        # 사용자 확인 (실제 실행 시)
        if not self.dry_run and not target_table:
            logger.warning("\n!!! 경고: 모든 PostgreSQL 데이터가 삭제됩니다 !!!")
            logger.warning("계속하려면 'y'를 입력하세요: ")
            try:
                confirm = input()
                if confirm.lower() != 'y':
                    logger.info("롤백 취소됨")
                    return {"cancelled": True}
            except EOFError:
                # 비대화형 모드에서는 경고만 출력
                logger.warning("비대화형 모드 - 롤백 진행")

        # 삭제 순서에 따라 처리
        tables_to_process = DELETION_ORDER if not target_table else [target_table]

        for table_name in tables_to_process:
            if table_name not in ROLLBACK_TABLES and not target_table:
                continue

            self.stats.tables_processed += 1

            try:
                deleted = self.delete_table_data(table_name)
                self.stats.records_deleted += deleted
                self.stats.tables_success += 1
            except Exception as e:
                self.stats.tables_failed += 1
                self.stats.add_error(f"Rollback failed for {table_name}: {e}")

        # SQLite 폴백 플래그 설정
        if not target_table:  # 전체 롤백 시에만
            self.set_fallback_flag(enable=True)

        # 롤백 로그 생성
        self.create_rollback_log()

        # 결과 요약
        summary = self.stats.summary()
        logger.info("\n" + "=" * 60)
        logger.info("롤백 완료")
        logger.info(f"테이블: {summary['tables_success']}/{summary['tables_processed']} 처리")
        logger.info(f"삭제된 레코드: {summary['records_deleted']}")
        logger.info(f"소요 시간: {summary['elapsed_seconds']:.2f}초")
        if summary['errors_count'] > 0:
            logger.warning(f"오류: {summary['errors_count']}건")
        logger.info("=" * 60)

        return summary


def main():
    parser = argparse.ArgumentParser(
        description="PostgreSQL Migration Rollback Script"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="테스트 실행 (실제 데이터 변경 없음)"
    )
    parser.add_argument(
        "--table",
        type=str,
        help="특정 테이블만 롤백"
    )
    parser.add_argument(
        "--drop-schema",
        action="store_true",
        help="테이블 스키마도 삭제 (기본: 데이터만 삭제)"
    )
    parser.add_argument(
        "--no-confirm",
        action="store_true",
        help="확인 없이 실행"
    )

    args = parser.parse_args()

    rollback = PostgresRollback(dry_run=args.dry_run)
    result = rollback.run_rollback(
        target_table=args.table,
        keep_schema=not args.drop_schema
    )

    # 종료 코드
    if result.get("cancelled"):
        sys.exit(2)
    if result.get("tables_failed", 0) > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
