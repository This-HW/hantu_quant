#!/usr/bin/env python3
"""
자동 매매 시스템 디버깅 및 테스트
- 매매 엔진 초기화 테스트
- 일일 선정 종목 로드 테스트
- 매매 신호 생성 테스트
"""

import sys
import os
import asyncio
from datetime import datetime

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

def test_trading_engine_init():
    """매매 엔진 초기화 테스트"""
    print("=" * 60)
    print("🔧 매매 엔진 초기화 테스트")
    print("=" * 60)

    try:
        from core.trading.trading_engine import TradingEngine, TradingConfig

        config = TradingConfig(
            max_positions=5,
            position_size_method="account_pct",
            position_size_value=0.05,  # 5%
            max_trades_per_day=10
        )

        engine = TradingEngine(config)
        print(f"✅ 매매 엔진 초기화 성공")
        print(f"   - 최대 포지션: {engine.config.max_positions}")
        print(f"   - 포지션 크기: {engine.config.position_size_value*100:.1f}%")
        print(f"   - 실행 상태: {engine.is_running}")

        return engine

    except Exception as e:
        print(f"❌ 매매 엔진 초기화 실패: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_daily_selection_load():
    """일일 선정 종목 로드 테스트"""
    print("\n" + "=" * 60)
    print("📊 일일 선정 종목 로드 테스트")
    print("=" * 60)

    try:
        from core.trading.trading_engine import TradingEngine

        engine = TradingEngine()

        # _load_daily_selection 메서드 테스트
        selected_stocks = engine._load_daily_selection()

        if selected_stocks:
            print(f"✅ 일일 선정 종목 로드 성공: {len(selected_stocks)}개")
            print(f"\n상위 3개 종목:")
            for i, stock in enumerate(selected_stocks[:3], 1):
                print(f"   {i}. {stock.get('stock_name', 'N/A')} ({stock.get('stock_code', 'N/A')})")
                print(f"      - 진입가: {stock.get('entry_price', 0):,}원")
                print(f"      - 매력도: {stock.get('price_attractiveness', 0):.1f}")
                print(f"      - 신뢰도: {stock.get('confidence', 0):.2f}")
        else:
            print("❌ 일일 선정 종목이 없습니다")

        return selected_stocks

    except Exception as e:
        print(f"❌ 일일 선정 종목 로드 실패: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_api_initialization():
    """API 초기화 테스트"""
    print("\n" + "=" * 60)
    print("🔌 API 초기화 테스트")
    print("=" * 60)

    try:
        from core.trading.trading_engine import TradingEngine

        engine = TradingEngine()

        # API 초기화 테스트
        api_success = engine._initialize_api()

        if api_success:
            print("✅ API 초기화 성공")
            print(f"   - API 상태: {'활성' if engine.api else '비활성'}")
            print(f"   - 설정 서버: {engine.api_config.server if engine.api_config else 'N/A'}")
        else:
            print("❌ API 초기화 실패")

        return api_success

    except Exception as e:
        print(f"❌ API 초기화 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_market_time_check():
    """거래 시간 체크 테스트"""
    print("\n" + "=" * 60)
    print("⏰ 거래 시간 체크 테스트")
    print("=" * 60)

    try:
        from core.trading.trading_engine import TradingEngine

        engine = TradingEngine()

        # 거래 가능한 날인지 체크
        is_tradeable_day = engine._is_tradeable_day()
        print(f"거래 가능한 날: {'예' if is_tradeable_day else '아니오'}")

        # 거래 시간인지 체크
        is_market_time = engine._is_market_time()
        print(f"거래 시간: {'예' if is_market_time else '아니오'}")

        current_time = datetime.now().strftime('%H:%M')
        print(f"현재 시간: {current_time}")
        print(f"거래 시간: {engine.config.market_start} ~ {engine.config.market_end}")

        return is_tradeable_day and is_market_time

    except Exception as e:
        print(f"❌ 거래 시간 체크 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_trading_start():
    """매매 시작 테스트 (비동기)"""
    print("\n" + "=" * 60)
    print("🚀 매매 시작 테스트")
    print("=" * 60)

    try:
        from core.trading.trading_engine import TradingEngine, TradingConfig

        config = TradingConfig(
            max_positions=3,
            position_size_method="fixed",
            fixed_position_size=100000,  # 10만원
            max_trades_per_day=5
        )

        engine = TradingEngine(config)

        print("매매 시작 시도...")
        result = await engine.start_trading()

        if result:
            print("✅ 매매 시작 성공")
            print(f"   - 실행 상태: {engine.is_running}")
            print(f"   - 시작 시간: {engine.start_time}")

            # 잠깐 실행 후 중지
            await asyncio.sleep(5)
            await engine.stop_trading("테스트 완료")
        else:
            print("❌ 매매 시작 실패")

        return result

    except Exception as e:
        print(f"❌ 매매 시작 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_scheduler_integration():
    """스케줄러 통합 테스트"""
    print("\n" + "=" * 60)
    print("📅 스케줄러 통합 테스트")
    print("=" * 60)

    try:
        from workflows.integrated_scheduler import IntegratedScheduler

        scheduler = IntegratedScheduler(p_parallel_workers=1)

        print("스케줄러 자동 매매 시작 함수 테스트...")
        scheduler._start_auto_trading()

        print("✅ 스케줄러 자동 매매 함수 실행 완료")
        return True

    except Exception as e:
        print(f"❌ 스케줄러 통합 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """메인 테스트 함수"""
    print("🚀 자동 매매 시스템 디버깅 테스트 시작")
    print(f"⏰ 시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    test_results = []

    # 1. 매매 엔진 초기화 테스트
    engine = test_trading_engine_init()
    test_results.append(("매매 엔진 초기화", engine is not None))

    # 2. 일일 선정 종목 로드 테스트
    selected_stocks = test_daily_selection_load()
    test_results.append(("일일 선정 종목 로드", selected_stocks is not None and len(selected_stocks) > 0))

    # 3. API 초기화 테스트
    api_success = test_api_initialization()
    test_results.append(("API 초기화", api_success))

    # 4. 거래 시간 체크 테스트
    market_check = test_market_time_check()
    test_results.append(("거래 시간 체크", market_check))

    # 5. 스케줄러 통합 테스트
    scheduler_success = test_scheduler_integration()
    test_results.append(("스케줄러 통합", scheduler_success))

    # 6. 매매 시작 테스트 (조건부)
    if api_success and selected_stocks:
        print("\n매매 시작 테스트 실행...")
        try:
            trading_result = asyncio.run(test_trading_start())
            test_results.append(("매매 시작 테스트", trading_result))
        except Exception as e:
            print(f"매매 시작 테스트 오류: {e}")
            test_results.append(("매매 시작 테스트", False))
    else:
        print("\n매매 시작 테스트 건너뜀 (선행 조건 미충족)")
        test_results.append(("매매 시작 테스트", None))

    # 결과 요약
    print("\n" + "=" * 80)
    print("📋 디버깅 테스트 결과 요약")
    print("=" * 80)

    passed_tests = 0
    failed_tests = 0
    skipped_tests = 0

    for test_name, result in test_results:
        if result is True:
            status = "✅ 성공"
            passed_tests += 1
        elif result is False:
            status = "❌ 실패"
            failed_tests += 1
        else:
            status = "⏭️ 건너뜀"
            skipped_tests += 1

        print(f"{status} {test_name}")

    print(f"\n📊 전체 결과: {passed_tests}개 성공, {failed_tests}개 실패, {skipped_tests}개 건너뜀")

    if failed_tests == 0:
        print("🎉 자동 매매 시스템이 정상 작동합니다!")
    else:
        print("⚠️ 일부 기능에 문제가 있습니다. 실패한 항목을 점검하세요.")

    print(f"\n⏰ 종료 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()