#!/usr/bin/env python3
import os
from core.api.kis_api import KISAPI


def main():
    code = os.getenv("STOCK_CODE", "005930")
    api = KISAPI()
    df = api.get_tick_conclusions(code, count=100)
    if df is None:
        print("❌ 체결 조회 실패")
        return 1
    print(df.head())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

