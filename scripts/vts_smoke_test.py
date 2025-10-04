"""
VTS(모의투자) 스모크 테스트 스크립트

용도:
- 토큰/잔고/현재가/주문(매수·매도) 최소 경로 확인

실행 전제:
- .env: SERVER=virtual, TRADING_PROD_ENABLE=false
- APP_KEY/APP_SECRET/ACCOUNT_NUMBER 설정
- 1주 매매 가능한 잔액

실행:
  python3 scripts/vts_smoke_test.py

환경 변수:
- VTS_TEST_CODE (기본 005930)
"""

import os
import sys
import time

from core.api.kis_api import KISAPI
from core.config.api_config import APIConfig
from core.config import settings


def _assert(cond: bool, msg: str):
    if not cond:
        raise AssertionError(msg)


def main():
    cfg = APIConfig()
    print(f"[ENV] SERVER={cfg.server}, TRADING_PROD_ENABLE={settings.TRADING_PROD_ENABLE}")
    _assert(cfg.server == 'virtual', "SERVER=virtual 이어야 합니다")
    _assert(settings.TRADING_PROD_ENABLE is False, "TRADING_PROD_ENABLE=false 이어야 합니다")

    api = KISAPI()

    # 1) 잔고
    bal = api.get_balance()
    _assert(isinstance(bal, dict), "잔고 조회 실패")
    deposit = float(bal.get('deposit', 0))
    print(f"[BALANCE] deposit={deposit:,.0f}")

    # 2) 현재가
    code = os.getenv("VTS_TEST_CODE", "005930")
    price_info = api.get_current_price(code)
    _assert(price_info and price_info.get('current_price', 0) > 0, "현재가 조회 실패")
    print(f"[PRICE] {code} {price_info['current_price']:,.0f}")

    # 3) 시장가 매수 1주
    print("[BUY] market 1 share")
    buy = api.market_buy(code, 1)
    _assert(buy is not None, "시장가 매수 실패")
    time.sleep(0.5)

    # 4) 보유 확인
    bal2 = api.get_balance()
    pos = bal2.get('positions', {}).get(code)
    _assert(pos and int(pos.get('quantity', 0)) >= 1, "매수 후 보유수량 확인 실패")
    print(f"[POSITION AFTER BUY] qty={pos['quantity']} avg={pos['avg_price']}")

    # 5) 시장가 매도 1주
    print("[SELL] market 1 share")
    sell = api.market_sell(code, 1)
    _assert(sell is not None, "시장가 매도 실패")
    time.sleep(0.5)

    # 6) 최종 보유 상태
    bal3 = api.get_balance()
    pos3 = bal3.get('positions', {}).get(code, {})
    qty3 = int(pos3.get('quantity', 0))
    _assert(qty3 >= 0, "잔여 수량 파싱 오류")
    print(f"[POSITION AFTER SELL] qty={qty3}")

    print("✅ VTS 스모크 테스트 성공")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ VTS 스모크 테스트 실패: {e}")
        sys.exit(1)

