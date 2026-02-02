#!/usr/bin/env python3
"""에러 로그 테이블 전체 삭제 스크립트"""

import os
import sys

# 프로젝트 루트를 sys.path에 추가
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from core.config.settings import DATABASE_URL
from sqlalchemy import create_engine, text

def main():
    try:
        # DB 연결
        engine = create_engine(DATABASE_URL)

        with engine.connect() as conn:
            # 현재 레코드 수 확인
            result = conn.execute(text("SELECT COUNT(*) FROM error_logs"))
            count = result.scalar()
            print(f"현재 error_logs 레코드 수: {count}개")

            if count == 0:
                print("❌ 이미 error_logs 테이블이 비어있습니다.")
                return

            # error_logs 테이블 비우기
            conn.execute(text("TRUNCATE TABLE error_logs"))
            conn.commit()
            print("✅ error_logs 테이블 전체 삭제 완료")

            # 확인
            result = conn.execute(text("SELECT COUNT(*) FROM error_logs"))
            count_after = result.scalar()
            print(f"삭제 후 error_logs 레코드 수: {count_after}개")

    except Exception as e:
        print(f"❌ 에러 발생: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
