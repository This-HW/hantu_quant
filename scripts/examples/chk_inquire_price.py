#!/usr/bin/env python3
"""KIS 현재가 조회 최소 실행 샘플 (examples_llm 스타일)

환경변수:
- STOCK_CODE (기본 005930)

실행:
  python3 scripts/examples/chk_inquire_price.py
"""

import os
from core.api.kis_api import KISAPI


def main():
    code = os.getenv("STOCK_CODE", "005930")
    api = KISAPI()
    info = api.get_current_price(code)
    if not info:
        print("❌ 현재가 조회 실패 (토큰/환경 확인 필요)")
        return 1
    print(f"{code} 현재가: {info['current_price']:,} / 거래량: {info['volume']:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

