#!/usr/bin/env python3
import os
from core.api.kis_api import KISAPI


def main():
    code = os.getenv("STOCK_CODE", "005930")
    api = KISAPI()
    df = api.get_minute_bars(code, time_unit=1, count=60)
    if df is None:
        print("❌ 분봉 조회 실패")
        return 1
    print(df.tail())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

