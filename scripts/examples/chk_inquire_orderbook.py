#!/usr/bin/env python3
import os
from core.api.kis_api import KISAPI


def main():
    code = os.getenv("STOCK_CODE", "005930")
    api = KISAPI()
    ob = api.get_orderbook(code)
    if not ob:
        print("❌ 호가 조회 실패")
        return 1
    # 상위 레벨 몇 개만 출력
    keys = [k for k in ob.keys() if k.lower().startswith("askp") or k.lower().startswith("bidp")]
    show = {k: ob[k] for k in sorted(keys)[:5]}
    print("호가 상위:", show)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

