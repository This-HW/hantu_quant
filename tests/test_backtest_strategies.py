#!/usr/bin/env python3
"""
전략 백테스트 실행 스크립트
"""

import sys
from pathlib import Path

# 프로젝트 루트 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.backtesting.strategy_backtester import StrategyBacktester
from datetime import datetime, timedelta


def test_current_strategy():
    """현재 전략 백테스트"""
    print("=" * 60)
    print("현재 전략 백테스트")
    print("=" * 60)

    backtester = StrategyBacktester(initial_capital=100000000)

    # 최근 30일 백테스트
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)

    selection_criteria = {
        'price_attractiveness': 80.0,
        'technical_score': 70.0,
        'risk_score_max': 25.0,
        'confidence_min': 0.75
    }

    trading_config = {
        'stop_loss_pct': 0.03,
        'take_profit_pct': 0.08,
        'max_holding_days': 10,
        'position_size': 0.05
    }

    result = backtester.backtest_selection_strategy(
        start_date=start_date.strftime("%Y-%m-%d"),
        end_date=end_date.strftime("%Y-%m-%d"),
        selection_criteria=selection_criteria,
        trading_config=trading_config
    )

    print_result(result)

    # 결과 저장
    output_path = f"data/backtesting/backtest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    backtester.save_result(result, output_path)

    return result


def test_aggressive_strategy():
    """공격적 전략 백테스트 (기존 전략)"""
    print("\n" + "=" * 60)
    print("공격적 전략 백테스트 (비교용)")
    print("=" * 60)

    backtester = StrategyBacktester(initial_capital=100000000)

    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)

    selection_criteria = {
        'price_attractiveness': 60.0,
        'technical_score': 50.0,
        'risk_score_max': 50.0,
        'confidence_min': 0.4
    }

    trading_config = {
        'stop_loss_pct': 0.05,
        'take_profit_pct': 0.10,
        'max_holding_days': 15,
        'position_size': 0.10
    }

    result = backtester.backtest_selection_strategy(
        start_date=start_date.strftime("%Y-%m-%d"),
        end_date=end_date.strftime("%Y-%m-%d"),
        selection_criteria=selection_criteria,
        trading_config=trading_config
    )

    result.strategy_name = "Aggressive Strategy"
    print_result(result)

    return result


def print_result(result):
    """결과 출력"""
    print(f"\n전략: {result.strategy_name}")
    print(f"기간: {result.start_date} ~ {result.end_date}")
    print(f"\n📊 거래 통계:")
    print(f"  - 총 거래: {result.total_trades}건")
    print(f"  - 승리: {result.winning_trades}건")
    print(f"  - 손실: {result.losing_trades}건")
    print(f"  - 승률: {result.win_rate:.1%}")
    print(f"\n💰 수익 지표:")
    print(f"  - 평균 수익률: {result.avg_return:+.2%}")
    print(f"  - 평균 승리: {result.avg_win:+.2%}")
    print(f"  - 평균 손실: {result.avg_loss:+.2%}")
    print(f"  - 총 수익률: {result.total_return:+.2%}")
    print(f"  - Profit Factor: {result.profit_factor:.2f}")
    print(f"\n📉 리스크 지표:")
    print(f"  - 최대 낙폭: {result.max_drawdown:+.2%}")
    print(f"  - Sharpe Ratio: {result.sharpe_ratio:.2f}")
    print(f"  - 최고 수익: {result.best_trade:+.2%}")
    print(f"  - 최악 손실: {result.worst_trade:+.2%}")
    print(f"  - 평균 보유일: {result.avg_holding_days:.1f}일")


def compare_strategies():
    """전략 비교"""
    print("\n" + "=" * 60)
    print("전략 비교")
    print("=" * 60)

    conservative = test_current_strategy()
    aggressive = test_aggressive_strategy()

    print("\n" + "=" * 60)
    print("비교 요약")
    print("=" * 60)
    print(f"{'지표':<20} {'보수적 전략':<15} {'공격적 전략':<15} {'우위':<10}")
    print("-" * 60)

    metrics = [
        ('승률', conservative.win_rate, aggressive.win_rate, '%'),
        ('평균수익률', conservative.avg_return, aggressive.avg_return, '%'),
        ('총수익률', conservative.total_return, aggressive.total_return, '%'),
        ('Sharpe Ratio', conservative.sharpe_ratio, aggressive.sharpe_ratio, ''),
        ('Profit Factor', conservative.profit_factor, aggressive.profit_factor, ''),
        ('최대낙폭', conservative.max_drawdown, aggressive.max_drawdown, '%'),
    ]

    for name, cons_val, agg_val, unit in metrics:
        if unit == '%':
            cons_str = f"{cons_val:+.2%}"
            agg_str = f"{agg_val:+.2%}"
        else:
            cons_str = f"{cons_val:.2f}"
            agg_str = f"{agg_val:.2f}"

        # 우위 판단 (낙폭은 낮을수록 좋음)
        if name == '최대낙폭':
            winner = "보수적" if abs(cons_val) < abs(agg_val) else "공격적"
        else:
            winner = "보수적" if cons_val > agg_val else "공격적"

        print(f"{name:<20} {cons_str:<15} {agg_str:<15} {winner:<10}")

    print("\n✅ 결론:")
    if conservative.win_rate > aggressive.win_rate:
        print(f"   보수적 전략이 승률 {conservative.win_rate - aggressive.win_rate:+.1%}p 우위")
    else:
        print(f"   공격적 전략이 승률 {aggressive.win_rate - conservative.win_rate:+.1%}p 우위")


if __name__ == "__main__":
    try:
        compare_strategies()
    except KeyboardInterrupt:
        print("\n\n중단되었습니다.")
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
