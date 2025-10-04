#!/usr/bin/env python3
"""
자동 매매 엔진 직접 테스트

문제 진단:
1. API 연결 확인
2. 일일 선정 종목 로드 확인
3. 매수 조건 확인
4. 실제 매수 주문 테스트
"""

import sys
import os
import asyncio
from pathlib import Path
from datetime import datetime

# 프로젝트 루트 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.trading.trading_engine import TradingEngine, TradingConfig
from core.api.kis_api import KISAPI
from core.config.api_config import APIConfig
from core.utils.log_utils import get_logger

logger = get_logger(__name__)


async def test_api_connection():
    """API 연결 테스트"""
    print("\n" + "=" * 60)
    print("1. API 연결 테스트")
    print("=" * 60)

    try:
        api_config = APIConfig()
        print(f"✅ API 설정 로드 완료")
        print(f"   - 서버: {api_config.server}")
        print(f"   - 앱키: {api_config.app_key[:10]}...")

        # 토큰 발급
        if api_config.ensure_valid_token():
            print(f"✅ 토큰 발급 성공")
            print(f"   - 토큰: {api_config.access_token[:20]}...")
        else:
            print(f"❌ 토큰 발급 실패")
            return False

        # API 연결 테스트
        api = KISAPI()
        balance = api.get_balance()

        if balance:
            print(f"✅ 계좌 조회 성공")
            print(f"   - 예수금: {balance.get('deposit', 0):,.0f}원")
            print(f"   - 평가금액: {balance.get('total_eval_amount', 0):,.0f}원")
            print(f"   - 총자산: {balance.get('deposit', 0) + balance.get('total_eval_amount', 0):,.0f}원")
            return True
        else:
            print(f"❌ 계좌 조회 실패")
            return False

    except Exception as e:
        print(f"❌ API 연결 오류: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_load_daily_selection():
    """일일 선정 종목 로드 테스트"""
    print("\n" + "=" * 60)
    print("2. 일일 선정 종목 로드 테스트")
    print("=" * 60)

    try:
        import json
        today = datetime.now().strftime("%Y%m%d")
        selection_file = f"data/daily_selection/daily_selection_{today}.json"

        if not os.path.exists(selection_file):
            print(f"❌ 일일 선정 파일 없음: {selection_file}")
            return None

        with open(selection_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        selected_stocks = data.get('data', {}).get('selected_stocks', [])

        print(f"✅ 일일 선정 종목 로드 성공: {len(selected_stocks)}개")
        print(f"\n상위 5개 종목:")
        for i, stock in enumerate(selected_stocks[:5], 1):
            print(f"   {i}. {stock.get('stock_name')} ({stock.get('stock_code')})")
            print(f"      - 진입가: {stock.get('entry_price', 0):,.0f}원")
            print(f"      - 기대수익: {stock.get('expected_return', 0):.2f}%")
            print(f"      - 신뢰도: {stock.get('confidence', 0):.2f}")

        return selected_stocks

    except Exception as e:
        print(f"❌ 종목 로드 오류: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_trading_engine_init():
    """매매 엔진 초기화 테스트"""
    print("\n" + "=" * 60)
    print("3. 매매 엔진 초기화 테스트")
    print("=" * 60)

    try:
        config = TradingConfig(
            max_positions=10,
            position_size_method="account_pct",
            position_size_value=0.10,
            stop_loss_pct=0.05,
            take_profit_pct=0.10
        )

        engine = TradingEngine(config)
        print(f"✅ 매매 엔진 생성 성공")
        print(f"   - 최대 포지션: {config.max_positions}개")
        print(f"   - 포지션 크기: {config.position_size_value*100:.0f}%")
        print(f"   - 손절매: {config.stop_loss_pct:.1%}")
        print(f"   - 익절매: {config.take_profit_pct:.1%}")

        # API 초기화
        if engine._initialize_api():
            print(f"✅ API 초기화 성공")
        else:
            print(f"❌ API 초기화 실패")
            return None

        return engine

    except Exception as e:
        print(f"❌ 엔진 초기화 오류: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_buy_conditions(engine, selected_stocks):
    """매수 조건 테스트"""
    print("\n" + "=" * 60)
    print("4. 매수 조건 확인 테스트")
    print("=" * 60)

    if not engine or not selected_stocks:
        print(f"❌ 엔진 또는 종목 데이터 없음")
        return

    buy_candidates = []

    for i, stock in enumerate(selected_stocks[:10], 1):  # 상위 10개만 체크
        stock_code = stock.get('stock_code')
        stock_name = stock.get('stock_name')

        # 매수 조건 확인
        should_buy, reason = engine._should_buy(stock)

        print(f"\n{i}. {stock_name} ({stock_code})")
        print(f"   - 매수 가능: {'✅ 예' if should_buy else '❌ 아니오'}")
        print(f"   - 사유: {reason}")

        if should_buy:
            buy_candidates.append(stock)

    print(f"\n{'='*60}")
    print(f"매수 가능 종목: {len(buy_candidates)}개")
    print(f"{'='*60}")

    return buy_candidates


async def test_dry_run_buy(engine, stock_data):
    """실제 매수 주문 테스트 (시험 실행)"""
    print("\n" + "=" * 60)
    print("5. 매수 주문 실행 테스트 (Dry Run)")
    print("=" * 60)

    if not engine or not stock_data:
        print(f"❌ 엔진 또는 종목 데이터 없음")
        return

    stock_code = stock_data.get('stock_code')
    stock_name = stock_data.get('stock_name')

    print(f"\n매수 시도 종목: {stock_name} ({stock_code})")

    try:
        # 현재가 조회
        price_data = engine.api.get_current_price(stock_code)
        if not price_data:
            print(f"❌ 현재가 조회 실패")
            return

        current_price = price_data.get('current_price')
        print(f"   - 현재가: {current_price:,.0f}원")

        # 포지션 사이징
        quantity = engine._calculate_position_size(stock_code, current_price, stock_data)
        print(f"   - 매수 수량: {quantity}주")
        print(f"   - 투자 금액: {current_price * quantity:,.0f}원")

        if quantity <= 0:
            print(f"❌ 포지션 크기 계산 실패 (수량 0)")
            return

        print(f"\n🔥 실제 주문 실행...")

        # 실제 매수 주문 실행
        result = await engine._execute_buy_order(stock_data)

        if result:
            print(f"✅ 매수 주문 성공!")
            print(f"   - 종목: {stock_name}")
            print(f"   - 수량: {quantity}주")
            print(f"   - 가격: {current_price:,.0f}원")
        else:
            print(f"❌ 매수 주문 실패")

    except Exception as e:
        print(f"❌ 매수 주문 오류: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """메인 테스트 실행"""
    print("\n" + "=" * 60)
    print("자동 매매 엔진 직접 테스트")
    print("=" * 60)

    # 1. API 연결 테스트
    api_ok = await test_api_connection()
    if not api_ok:
        print("\n❌ API 연결 실패로 테스트 중단")
        return

    # 2. 일일 선정 종목 로드
    selected_stocks = await test_load_daily_selection()
    if not selected_stocks:
        print("\n❌ 선정 종목 없음으로 테스트 중단")
        return

    # 3. 매매 엔진 초기화
    engine = await test_trading_engine_init()
    if not engine:
        print("\n❌ 엔진 초기화 실패로 테스트 중단")
        return

    # 4. 매수 조건 확인
    buy_candidates = await test_buy_conditions(engine, selected_stocks)

    if buy_candidates:
        # 5. 첫 번째 매수 가능 종목으로 실제 주문 테스트
        response = input(f"\n첫 번째 매수 가능 종목({buy_candidates[0].get('stock_name')})으로 실제 주문을 실행하시겠습니까? (y/N): ").strip().lower()

        if response == 'y':
            await test_dry_run_buy(engine, buy_candidates[0])
        else:
            print("\n테스트를 건너뜁니다.")
    else:
        print("\n⚠️ 현재 매수 가능한 종목이 없습니다.")

    print("\n" + "=" * 60)
    print("테스트 완료")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
