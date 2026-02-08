#!/usr/bin/env python3
"""
P0 개선 후 백테스트 실행 스크립트
Train: 2025-07-10 ~ 2025-12-31 (In-Sample)
Test: 2026-01-01 ~ 2026-02-03 (Out-of-Sample)
"""

import json
import sys
from datetime import datetime
from pathlib import Path

# 프로젝트 루트를 경로에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.backtesting.simple_backtester import SimpleBacktester
from core.utils.log_utils import get_logger

logger = get_logger(__name__)


def print_result(result, period_name: str):
    """백테스트 결과 출력"""
    print(f"\n{'=' * 80}")
    print(f"{period_name} 백테스트 결과")
    print(f"{'=' * 80}")
    print(f"기간: {result.start_date} ~ {result.end_date}")
    print(f"전략: {result.strategy_name}")
    print(f"\n[성과 요약]")
    print(f"총 거래 수: {result.total_trades}건")
    print(f"승리 거래: {result.winning_trades}건")
    print(f"손실 거래: {result.losing_trades}건")
    print(f"승률: {result.win_rate:.2%}")
    print(f"\n[수익률]")
    print(f"평균 수익률: {result.avg_return:.2%}")
    print(f"총 수익률: {result.total_return:.2%}")

    # 연수익률 계산
    days = (datetime.strptime(result.end_date, "%Y-%m-%d") -
            datetime.strptime(result.start_date, "%Y-%m-%d")).days

    # 평균 거래 수익률 기준 연율화 (더 현실적)
    avg_trade_days = result.avg_holding_days if result.avg_holding_days > 0 else 7
    trades_per_year = 365 / avg_trade_days
    annualized_return = result.avg_return * trades_per_year

    print(f"연수익률 (추정): {annualized_return:.2%}")

    print(f"\n[거래 분석]")
    print(f"평균 승리: {result.avg_win:.2%}")
    print(f"평균 손실: {result.avg_loss:.2%}")
    print(f"최대 수익: {result.best_trade:.2%}")
    print(f"최대 손실: {result.worst_trade:.2%}")
    print(f"Profit Factor: {result.profit_factor:.2f}")
    print(f"평균 보유 기간: {result.avg_holding_days:.1f}일")

    print(f"\n[리스크]")
    print(f"Sharpe Ratio: {result.sharpe_ratio:.2f}")
    print(f"Max Drawdown: {result.max_drawdown:.2%}")
    print(f"{'=' * 80}\n")

    return annualized_return


def main():
    """메인 실행 함수"""
    logger.info("P0 개선 후 백테스트 시작")

    # 백테스터 초기화
    backtester = SimpleBacktester(initial_capital=100_000_000)

    # Trading 설정
    trading_config = {
        'achievement_rate': 0.5,  # 예상 수익률 50% 달성
        'max_holding_days': 10  # 최대 10일 보유
    }

    # Selection 기준 (Phase 1 개선 반영)
    selection_criteria = {
        'min_total_score': 50,
        'min_confidence': 0.3,
        'max_positions': 10
    }

    # 1. Train 기간 백테스트 (In-Sample)
    logger.info("Train 기간 백테스트 실행 중...")
    train_result = backtester.backtest_selection_strategy(
        start_date="2025-07-10",
        end_date="2025-12-31",
        selection_criteria=selection_criteria,
        trading_config=trading_config,
        strategy_name="P0 Improved Strategy (Train)"
    )

    train_annualized = print_result(train_result, "Train 기간 (In-Sample)")

    # 2. Test 기간 백테스트 (Out-of-Sample)
    logger.info("Test 기간 백테스트 실행 중...")
    test_result = backtester.backtest_selection_strategy(
        start_date="2026-01-01",
        end_date="2026-02-03",
        selection_criteria=selection_criteria,
        trading_config=trading_config,
        strategy_name="P0 Improved Strategy (Test)"
    )

    test_annualized = print_result(test_result, "Test 기간 (Out-of-Sample)")

    # 3. 비교 분석
    print(f"\n{'=' * 80}")
    print("Before vs After 비교 분석")
    print(f"{'=' * 80}")
    print(f"\n{'메트릭':<20} {'Before (추정)':<15} {'After (Train)':<15} {'After (Test)':<15} {'개선'}")
    print("-" * 80)

    # Before 추정치
    before_return = 0.10  # 10%
    before_win_rate = 0.475  # 47.5%
    before_sharpe = 0.9  # 0.9

    # 연수익률 비교
    train_improvement = train_annualized - before_return
    test_improvement = test_annualized - before_return
    print(f"{'연수익률':<20} {before_return:>13.1%} {train_annualized:>14.1%} {test_annualized:>14.1%} {test_improvement:>+13.1%}p")

    # 승률 비교
    train_wr_improvement = train_result.win_rate - before_win_rate
    test_wr_improvement = test_result.win_rate - before_win_rate
    print(f"{'승률':<20} {before_win_rate:>13.1%} {train_result.win_rate:>14.1%} {test_result.win_rate:>14.1%} {test_wr_improvement:>+13.1%}p")

    # 샤프비율 비교
    train_sharpe_improvement = train_result.sharpe_ratio - before_sharpe
    test_sharpe_improvement = test_result.sharpe_ratio - before_sharpe
    print(f"{'샤프비율':<20} {before_sharpe:>13.2f} {train_result.sharpe_ratio:>14.2f} {test_result.sharpe_ratio:>14.2f} {test_sharpe_improvement:>+13.2f}")

    # 4. 검증 결과
    print(f"\n{'=' * 80}")
    print("검증 결과")
    print(f"{'=' * 80}")

    pass_return = bool(test_annualized > 0.10)
    pass_sharpe = bool(test_result.sharpe_ratio > 1.0)
    pass_overfitting = bool(abs(train_annualized - test_annualized) / train_annualized < 0.20 if train_annualized != 0 else True)

    print(f"\n✅ Out-of-Sample 연수익률 > 10%: {'통과' if pass_return else '실패'} ({test_annualized:.1%})")
    print(f"✅ Out-of-Sample 샤프비율 > 1.0: {'통과' if pass_sharpe else '실패'} ({test_result.sharpe_ratio:.2f})")
    print(f"✅ Train vs Test 차이 < 20%: {'통과' if pass_overfitting else '실패'} ({abs(train_annualized - test_annualized) / train_annualized * 100:.1f}%)")

    all_passed = pass_return and pass_sharpe and pass_overfitting

    # 5. 권장사항
    print(f"\n{'=' * 80}")
    print("권장사항")
    print(f"{'=' * 80}\n")

    if all_passed:
        print("✅ P0 개선 목표 달성!")
        print("   - 실거래 준비 진행 가능")
        print("   - 소액 실전 테스트 권장")
        print("   - 지속적 모니터링 필요")
    else:
        print("❌ P0 목표 미달성")
        print("   - 추가 파라미터 조정 필요")
        if not pass_return:
            print("   - 연수익률 개선: 진입/청산 기준 재검토")
        if not pass_sharpe:
            print("   - 샤프비율 개선: 리스크 관리 강화")
        if not pass_overfitting:
            print("   - 과적합 방지: 파라미터 단순화")

    # 6. 결과 저장
    output_dir = Path("data/backtest_results")
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    report = {
        "timestamp": timestamp,
        "train": {
            **train_result.__dict__,
            "annualized_return": train_annualized
        },
        "test": {
            **test_result.__dict__,
            "annualized_return": test_annualized
        },
        "comparison": {
            "before_return": before_return,
            "before_win_rate": before_win_rate,
            "before_sharpe": before_sharpe,
            "train_return_improvement": train_improvement,
            "test_return_improvement": test_improvement,
            "train_wr_improvement": train_wr_improvement,
            "test_wr_improvement": test_wr_improvement,
            "train_sharpe_improvement": train_sharpe_improvement,
            "test_sharpe_improvement": test_sharpe_improvement
        },
        "validation": {
            "pass_return": pass_return,
            "pass_sharpe": pass_sharpe,
            "pass_overfitting": pass_overfitting,
            "all_passed": all_passed
        }
    }

    output_path = output_dir / f"p0_backtest_{timestamp}.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    logger.info(f"백테스트 결과 저장: {output_path}")

    print(f"\n📊 상세 결과 저장: {output_path}")
    print(f"{'=' * 80}\n")


if __name__ == "__main__":
    main()
