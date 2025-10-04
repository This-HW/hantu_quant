#!/usr/bin/env python3
"""
자동 매매 시스템 테스트 스크립트
- 매매 엔진 초기화 테스트
- 일일 선정 파일 로드 테스트
- 매수/매도 조건 테스트
"""

import sys
import asyncio
from pathlib import Path
from datetime import datetime

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.trading.trading_engine import TradingEngine, TradingConfig
from core.utils.log_utils import setup_logging, get_logger

# 로깅 설정
log_filename = f"logs/test_trading_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
setup_logging(log_filename, add_sensitive_filter=True)
logger = get_logger(__name__)

async def test_trading_engine():
    """매매 엔진 테스트"""
    print("="*60)
    print("🧪 자동 매매 엔진 테스트")
    print("="*60)

    try:
        # 1. 매매 엔진 초기화
        print("\n[1] 매매 엔진 초기화...")
        config = TradingConfig(
            max_positions=5,
            position_size_method="account_pct",
            position_size_value=0.05,  # 테스트용 5%
            stop_loss_pct=0.05,
            take_profit_pct=0.10,
            max_trades_per_day=10
        )

        engine = TradingEngine(config)
        print("✅ 매매 엔진 초기화 성공")

        # 2. API 초기화
        print("\n[2] API 초기화...")
        if engine._initialize_api():
            print("✅ API 초기화 성공")
            print(f"   서버: {engine.api_config.server}")
        else:
            print("❌ API 초기화 실패")
            return False

        # 3. 일일 선정 종목 로드
        print("\n[3] 일일 선정 종목 로드...")
        selected_stocks = engine._load_daily_selection()

        if selected_stocks:
            print(f"✅ 일일 선정 종목 로드 성공: {len(selected_stocks)}개")
            print(f"\n   상위 3개 종목:")
            for i, stock in enumerate(selected_stocks[:3], 1):
                print(f"   {i}. {stock.get('stock_name')} ({stock.get('stock_code')})")
                print(f"      현재가: {stock.get('entry_price', 0):,.0f}원")
                print(f"      기대수익: {stock.get('expected_return', 0):.2f}%")
        else:
            print("⚠️  오늘 날짜의 일일 선정 파일이 없습니다")
            print("   - Phase 1 + Phase 2를 먼저 실행해야 합니다")

        # 4. 계좌 잔고 조회
        print("\n[4] 계좌 잔고 조회...")
        balance = engine._get_account_balance()
        cash = engine._get_available_cash()

        print(f"✅ 계좌 조회 성공")
        print(f"   총 자산: {balance:,.0f}원")
        print(f"   가용 현금: {cash:,.0f}원")

        # 5. 거래 가능 여부 확인
        print("\n[5] 거래 가능 여부 확인...")
        is_tradeable = engine._is_tradeable_day()
        is_market_time = engine._is_market_time()

        print(f"   거래 가능한 날: {'✅ 예' if is_tradeable else '❌ 아니오 (주말/공휴일)'}")
        print(f"   장 시간: {'✅ 예' if is_market_time else '❌ 아니오'}")
        print(f"   설정: {config.market_start} ~ {config.market_end}")

        # 6. 매수 조건 테스트 (첫 번째 종목으로)
        if selected_stocks:
            print("\n[6] 매수 조건 테스트...")
            test_stock = selected_stocks[0]
            should_buy, reason = engine._should_buy(test_stock)

            print(f"   테스트 종목: {test_stock.get('stock_name')}")
            print(f"   매수 가능: {'✅ 예' if should_buy else '❌ 아니오'}")
            print(f"   사유: {reason}")

            # 포지션 사이징 계산
            if should_buy:
                entry_price = test_stock.get('entry_price', 0)
                if entry_price > 0:
                    quantity = engine._calculate_position_size(
                        test_stock.get('stock_code'),
                        entry_price,
                        test_stock
                    )
                    print(f"   계산된 수량: {quantity}주")
                    print(f"   투자금액: {quantity * entry_price:,.0f}원")

        # 7. 엔진 상태 조회
        print("\n[7] 엔진 상태 조회...")
        status = engine.get_status()
        print(f"   실행 상태: {status['is_running']}")
        print(f"   보유 포지션: {status['positions_count']}개")
        print(f"   오늘 거래: {status['daily_trades']}건")

        print("\n" + "="*60)
        print("✅ 모든 테스트 완료!")
        print("="*60)

        return True

    except Exception as e:
        logger.error(f"테스트 실패: {e}")
        print(f"\n❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """메인 함수"""
    print(f"\n📝 로그 파일: {log_filename}\n")

    # asyncio 이벤트 루프 실행
    result = asyncio.run(test_trading_engine())

    if result:
        print("\n✅ 자동 매매 시스템이 정상 작동합니다!")
    else:
        print("\n❌ 자동 매매 시스템에 문제가 있습니다.")
        sys.exit(1)

if __name__ == "__main__":
    main()
