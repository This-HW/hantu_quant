#!/usr/bin/env python3
"""
한국투자증권 가상계좌 상태 확인

확인 사항:
1. 계좌 잔고 조회
2. 보유 종목 조회
3. API 연결 상태
"""

import sys
from pathlib import Path

# 프로젝트 루트 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.api.kis_api import KISAPI
from core.config.api_config import APIConfig


def test_virtual_account():
    """가상계좌 상태 확인"""
    print("\n" + "=" * 60)
    print("한국투자증권 가상계좌 상태 확인")
    print("=" * 60)

    try:
        # API 설정 로드
        api_config = APIConfig()
        print(f"\n✅ API 설정 로드")
        print(f"   - 서버: {api_config.server}")
        print(f"   - 계좌번호: {api_config.account_number}")

        if api_config.server != "virtual":
            print(f"\n⚠️ 경고: 실전 서버로 설정되어 있습니다!")
            print(f"   모의투자 서버로 변경하는 것을 권장합니다.")
            return

        # API 초기화
        api = KISAPI()

        # 토큰 발급
        if not api_config.ensure_valid_token():
            print(f"\n❌ 토큰 발급 실패")
            return

        print(f"\n✅ 토큰 발급 성공")

        # 잔고 조회
        print(f"\n" + "=" * 60)
        print(f"1. 계좌 잔고 조회")
        print(f"=" * 60)

        balance = api.get_balance()

        if balance:
            deposit = balance.get('deposit', 0)
            stock_eval = balance.get('stock_eval_amount', 0)
            total_eval = balance.get('total_eval_amount', 0)

            print(f"\n💰 계좌 정보:")
            print(f"   - 예수금 (현금): {deposit:,.0f}원")
            print(f"   - 평가금액 (주식): {stock_eval:,.0f}원")
            print(f"   - 총자산: {total_eval:,.0f}원")

            if total_eval == 0:
                print(f"\n❌ 문제: 계좌 잔고가 0원입니다!")
                print(f"\n해결 방법:")
                print(f"   1. 한국투자증권 홈페이지 접속")
                print(f"   2. 모의투자 > 나의 계좌 메뉴로 이동")
                print(f"   3. 초기 자금 설정 (권장: 1억원)")
                print(f"   4. 설정 후 이 스크립트를 다시 실행")

        else:
            print(f"\n❌ 잔고 조회 실패")
            print(f"   - 응답: {balance}")

        # 보유 종목 조회
        print(f"\n" + "=" * 60)
        print(f"2. 보유 종목 조회")
        print(f"=" * 60)

        holdings = api.get_holdings()

        if holdings:
            print(f"\n📊 보유 종목: {len(holdings)}개")
            for i, holding in enumerate(holdings, 1):
                print(f"\n{i}. {holding.get('stock_name')} ({holding.get('stock_code')})")
                print(f"   - 수량: {holding.get('quantity', 0):,}주")
                print(f"   - 평가금액: {holding.get('eval_amount', 0):,.0f}원")
                print(f"   - 평가손익: {holding.get('profit_loss', 0):+,.0f}원")
        else:
            print(f"\n보유 종목 없음")

        # API 연결 상태
        print(f"\n" + "=" * 60)
        print(f"3. API 연결 상태")
        print(f"=" * 60)

        # 현재가 조회 테스트 (삼성전자)
        test_code = "005930"
        price_data = api.get_current_price(test_code)

        if price_data:
            print(f"\n✅ API 연결 정상")
            print(f"   테스트 종목: 삼성전자 ({test_code})")
            print(f"   현재가: {price_data.get('current_price', 0):,.0f}원")
        else:
            print(f"\n⚠️ 현재가 조회 실패")

        print(f"\n" + "=" * 60)
        print(f"요약")
        print(f"=" * 60)

        if balance and balance.get('total_eval_amount', 0) > 0:
            print(f"\n✅ 가상계좌 정상 - 자동 매매 가능")
        else:
            print(f"\n❌ 가상계좌 초기 자금 설정 필요")
            print(f"\n다음 단계:")
            print(f"   1. https://securities.koreainvestment.com 접속")
            print(f"   2. 로그인 > 모의투자 메뉴")
            print(f"   3. 계좌 초기화 및 자금 설정")
            print(f"   4. 초기 자금: 1억원 권장")

    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_virtual_account()
