#!/usr/bin/env python3
"""
피드백 데이터베이스 마이그레이션 스크립트

이 스크립트는 기존 feedback_data 테이블에 factor_scores 컬럼을 추가합니다.
FeedbackSystem 초기화 시 자동으로 마이그레이션이 실행되지만,
수동으로 실행해야 할 경우 이 스크립트를 사용합니다.

Usage:
    python scripts/migrate_feedback_db.py [--db-path PATH] [--dry-run]

Examples:
    python scripts/migrate_feedback_db.py
    python scripts/migrate_feedback_db.py --db-path data/feedback.db
    python scripts/migrate_feedback_db.py --dry-run
"""

import argparse
import sqlite3
import sys
from pathlib import Path
from datetime import datetime


def check_column_exists(cursor: sqlite3.Cursor, table: str, column: str) -> bool:
    """컬럼 존재 여부 확인"""
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    return column in columns


def get_table_info(cursor: sqlite3.Cursor, table: str) -> list:
    """테이블 정보 조회"""
    cursor.execute(f"PRAGMA table_info({table})")
    return cursor.fetchall()


def migrate_feedback_db(db_path: str, dry_run: bool = False) -> bool:
    """
    피드백 데이터베이스 마이그레이션

    Args:
        db_path: 데이터베이스 파일 경로
        dry_run: True면 실제 변경 없이 시뮬레이션만

    Returns:
        성공 여부
    """
    db_file = Path(db_path)

    if not db_file.exists():
        print(f"[INFO] 데이터베이스 파일이 없습니다: {db_path}")
        print("[INFO] FeedbackSystem 초기화 시 자동으로 생성됩니다.")
        return True

    print(f"[INFO] 데이터베이스 경로: {db_path}")
    print(f"[INFO] Dry run: {dry_run}")
    print()

    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            # 테이블 존재 확인
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='feedback_data'
            """)
            if not cursor.fetchone():
                print("[WARN] feedback_data 테이블이 존재하지 않습니다.")
                print("[INFO] FeedbackSystem 초기화 시 자동으로 생성됩니다.")
                return True

            # 현재 테이블 구조 출력
            print("[INFO] 현재 테이블 구조:")
            table_info = get_table_info(cursor, 'feedback_data')
            for col in table_info:
                print(f"       {col[1]} ({col[2]})")
            print()

            # factor_scores 컬럼 확인
            if check_column_exists(cursor, 'feedback_data', 'factor_scores'):
                print("[OK] factor_scores 컬럼이 이미 존재합니다.")
                return True

            # 마이그레이션 실행
            print("[INFO] factor_scores 컬럼 추가 필요")

            if dry_run:
                print("[DRY-RUN] ALTER TABLE feedback_data ADD COLUMN factor_scores TEXT")
                print("[DRY-RUN] 마이그레이션이 시뮬레이션되었습니다.")
                return True

            # 실제 마이그레이션
            print("[INFO] 마이그레이션 실행 중...")
            cursor.execute("ALTER TABLE feedback_data ADD COLUMN factor_scores TEXT")
            conn.commit()

            # 확인
            if check_column_exists(cursor, 'feedback_data', 'factor_scores'):
                print("[OK] factor_scores 컬럼이 성공적으로 추가되었습니다.")

                # 업데이트된 테이블 구조 출력
                print()
                print("[INFO] 업데이트된 테이블 구조:")
                table_info = get_table_info(cursor, 'feedback_data')
                for col in table_info:
                    print(f"       {col[1]} ({col[2]})")

                # 기존 레코드 수 확인
                cursor.execute("SELECT COUNT(*) FROM feedback_data")
                count = cursor.fetchone()[0]
                print()
                print(f"[INFO] 기존 레코드 수: {count}")
                print("[INFO] 기존 레코드의 factor_scores는 NULL로 유지됩니다.")

                return True
            else:
                print("[ERROR] 컬럼 추가 실패")
                return False

    except sqlite3.Error as e:
        print(f"[ERROR] SQLite 오류: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] 예상치 못한 오류: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description='피드백 데이터베이스 마이그레이션 (factor_scores 컬럼 추가)'
    )
    parser.add_argument(
        '--db-path',
        default='data/feedback.db',
        help='데이터베이스 파일 경로 (기본값: data/feedback.db)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='실제 변경 없이 시뮬레이션만 수행'
    )

    args = parser.parse_args()

    print("=" * 60)
    print("피드백 데이터베이스 마이그레이션")
    print(f"실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()

    success = migrate_feedback_db(args.db_path, args.dry_run)

    print()
    print("=" * 60)
    if success:
        print("마이그레이션 완료")
    else:
        print("마이그레이션 실패")
    print("=" * 60)

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
