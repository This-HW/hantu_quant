#!/usr/bin/env python3
"""KIS 잔고 조회 최소 실행 샘플 (examples_llm 스타일)
"""

from core.api.kis_api import KISAPI


def main():
    api = KISAPI()
    bal = api.get_balance()
    if not isinstance(bal, dict) or not bal:
        print("❌ 잔고 조회 실패 (토큰/환경 확인 필요)")
        return 1
    print(f"예수금: {bal.get('deposit', 0):,.0f}")
    print(f"보유종목 수: {len(bal.get('positions', {}))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

