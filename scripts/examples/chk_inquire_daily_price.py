#!/usr/bin/env python3
"""KIS 일봉 조회 최소 실행 샘플 (examples_llm 스타일)

환경변수:
- STOCK_CODE (기본 005930)
"""

import os
from core.api.kis_api import KISAPI


def main():
    code = os.getenv("STOCK_CODE", "005930")
    api = KISAPI()
    df = api.get_daily_chart(code, period_days=30)
    if df is None or df.empty:
        print("❌ 일봉 조회 실패 (토큰/환경 확인 필요)")
        return 1
    print(df.tail(5))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

