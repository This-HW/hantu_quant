#!/usr/bin/env python3
"""
BatchMetrics 테이블 직접 생성
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database.unified_db import get_session
from core.database.models import Base, BatchMetrics
from sqlalchemy import create_engine, inspect
from core.config import settings
from core.utils.log_utils import get_logger

logger = get_logger(__name__)


def main():
    try:
        # DB 엔진 생성
        engine = create_engine(settings.DATABASE_URL)

        # Inspector로 테이블 존재 확인
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()

        if 'batch_metrics' in existing_tables:
            print("✅ batch_metrics 테이블이 이미 존재합니다.")
            return True

        # BatchMetrics 테이블만 생성
        print("batch_metrics 테이블 생성 중...")
        BatchMetrics.__table__.create(engine)
        print("✅ batch_metrics 테이블 생성 완료")

        # 확인
        inspector = inspect(engine)
        if 'batch_metrics' in inspector.get_table_names():
            print("✅ 테이블 생성 확인됨")

            # 컬럼 정보 출력
            columns = inspector.get_columns('batch_metrics')
            print("\n테이블 컬럼:")
            for col in columns:
                print(f"  - {col['name']}: {col['type']}")

            # 인덱스 정보 출력
            indexes = inspector.get_indexes('batch_metrics')
            print("\n테이블 인덱스:")
            for idx in indexes:
                print(f"  - {idx['name']}: {idx['column_names']}")

            return True
        else:
            print("❌ 테이블 생성 실패")
            return False

    except Exception as e:
        logger.error(f"테이블 생성 실패: {e}", exc_info=True)
        print(f"❌ 에러 발생: {e}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
