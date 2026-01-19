#!/usr/bin/env python3
"""
예측 정확도 개선 3단계 통합 테스트

통합 검증:
1. 추세 필터 동작 확인
2. 멀티 전략 앙상블 동작 확인
3. 주간 백테스트 스케줄 확인
"""

import sys
from pathlib import Path

# 프로젝트 루트 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_trend_filter_integration():
    """방안 A: 추세 필터 통합 확인"""
    print("\n" + "=" * 60)
    print("방안 A: 추세 필터 통합 테스트")
    print("=" * 60)

    try:
        from core.daily_selection.trend_follower import get_trend_follower

        trend_follower = get_trend_follower()
        print("✅ 추세 필터 모듈 로드 성공")

        # 간단한 동작 테스트
        print(f"   - 최소 추세 기간: {trend_follower.min_trend_days}일")
        print(f"   - 최소 추세 강도: {trend_follower.min_trend_strength}")
        print(f"   - 최소 모멘텀: {trend_follower.min_momentum}")

        return True

    except Exception as e:
        print(f"❌ 추세 필터 통합 실패: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_multi_strategy_integration():
    """방안 C: 멀티 전략 앙상블 통합 확인"""
    print("\n" + "=" * 60)
    print("방안 C: 멀티 전략 앙상블 통합 테스트")
    print("=" * 60)

    try:
        from core.strategy.multi_strategy_manager import MultiStrategyManager

        manager = MultiStrategyManager()
        print("✅ 멀티 전략 관리자 로드 성공")

        # 전략 목록 확인
        print("\n   등록된 전략:")
        for strategy_type, config in manager.strategies.items():
            print(f"   - {config.name}: {config.description}")

        return True

    except Exception as e:
        print(f"❌ 멀티 전략 통합 실패: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_backtest_schedule():
    """방안 B: 백테스트 스케줄 확인"""
    print("\n" + "=" * 60)
    print("방안 B: 주간 백테스트 스케줄 테스트")
    print("=" * 60)

    try:
        from core.backtesting.strategy_backtester import StrategyBacktester

        backtester = StrategyBacktester(initial_capital=100000000)
        print("✅ 백테스트 시스템 로드 성공")
        print(f"   - 초기 자본: {backtester.initial_capital:,}원")

        return True

    except Exception as e:
        print(f"❌ 백테스트 통합 실패: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_daily_updater_integration():
    """DailyUpdater에 모든 단계 통합 확인"""
    print("\n" + "=" * 60)
    print("DailyUpdater 통합 검증")
    print("=" * 60)

    try:
        from core.daily_selection.daily_updater import DailyUpdater

        updater = DailyUpdater()
        print("✅ DailyUpdater 초기화 성공")

        # 메서드 존재 확인
        assert hasattr(updater, '_apply_trend_filter'), "추세 필터 메서드 없음"
        print("   ✓ _apply_trend_filter() 메서드 존재")

        assert hasattr(updater, '_apply_multi_strategy_ensemble'), "멀티 전략 메서드 없음"
        print("   ✓ _apply_multi_strategy_ensemble() 메서드 존재")

        return True

    except Exception as e:
        print(f"❌ DailyUpdater 통합 실패: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_scheduler_integration():
    """IntegratedScheduler에 백테스트 스케줄 통합 확인"""
    print("\n" + "=" * 60)
    print("IntegratedScheduler 통합 검증")
    print("=" * 60)

    try:
        from workflows.integrated_scheduler import IntegratedScheduler

        scheduler = IntegratedScheduler()
        print("✅ IntegratedScheduler 초기화 성공")

        # 메서드 존재 확인
        assert hasattr(scheduler, '_run_weekly_backtest'), "주간 백테스트 메서드 없음"
        print("   ✓ _run_weekly_backtest() 메서드 존재")

        return True

    except Exception as e:
        print(f"❌ IntegratedScheduler 통합 실패: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """통합 테스트 실행"""
    print("\n" + "=" * 60)
    print("예측 정확도 개선 3단계 통합 테스트")
    print("=" * 60)

    results = {}

    # 각 단계별 테스트
    results['trend_filter'] = test_trend_filter_integration()
    results['multi_strategy'] = test_multi_strategy_integration()
    results['backtest'] = test_backtest_schedule()
    results['daily_updater'] = test_daily_updater_integration()
    results['scheduler'] = test_scheduler_integration()

    # 결과 요약
    print("\n" + "=" * 60)
    print("테스트 결과 요약")
    print("=" * 60)

    total = len(results)
    passed = sum(1 for v in results.values() if v)

    print(f"\n총 테스트: {total}개")
    print(f"통과: {passed}개")
    print(f"실패: {total - passed}개")

    for name, result in results.items():
        status = "✅" if result else "❌"
        print(f"{status} {name}")

    if passed == total:
        print("\n🎉 모든 통합 테스트 통과!")
        print("\n다음 단계:")
        print("1. 내일 아침 8:30 일일 선정 모니터링")
        print("2. 로그 확인: 추세 필터 및 멀티 전략 적용 여부")
        print("3. 금요일 20:00 첫 주간 백테스트 확인")
        return True
    else:
        print("\n⚠️ 일부 테스트 실패 - 문제 해결 필요")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
