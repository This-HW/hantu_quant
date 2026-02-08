#!/usr/bin/env python3
"""
백테스트 실행 스크립트
특정 기간에 대해 선정 전략을 백테스트하고 성과 보고서를 생성합니다.

사용 예:
    python scripts/run_backtest.py \
        --start-date 2024-01-01 \
        --end-date 2024-12-31 \
        --strategy selection \
        --initial-capital 10000000 \
        --output reports/backtest/2024_result.txt
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# 프로젝트 루트를 경로에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.backtesting.strategy_backtester import StrategyBacktester
from core.backtesting.result_reporter import BacktestReporter
from core.utils.log_utils import get_logger
from dataclasses import asdict

logger = get_logger(__name__)


def parse_args():
    """명령줄 인자 파싱"""
    parser = argparse.ArgumentParser(
        description='백테스트 실행 스크립트',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예제:
  # 2024년 전체 백테스트
  python scripts/run_backtest.py --start-date 2024-01-01 --end-date 2024-12-31

  # 초기 자본 5천만원으로 백테스트
  python scripts/run_backtest.py --start-date 2024-01-01 --end-date 2024-12-31 --initial-capital 50000000

  # JSON 형식으로 저장
  python scripts/run_backtest.py --start-date 2024-01-01 --end-date 2024-12-31 --format json
        """
    )

    parser.add_argument(
        '--start-date',
        type=str,
        required=True,
        help='시작일 (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--end-date',
        type=str,
        required=True,
        help='종료일 (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--strategy',
        type=str,
        default='selection',
        help='전략명 (기본값: selection)'
    )
    parser.add_argument(
        '--initial-capital',
        type=float,
        default=10000000,
        help='초기 자본 (기본값: 10,000,000원)'
    )
    parser.add_argument(
        '--stop-loss',
        type=float,
        default=0.03,
        help='손절 비율 (기본값: 0.03 = 3%%)'
    )
    parser.add_argument(
        '--take-profit',
        type=float,
        default=0.08,
        help='익절 비율 (기본값: 0.08 = 8%%)'
    )
    parser.add_argument(
        '--max-holding-days',
        type=int,
        default=10,
        help='최대 보유일 (기본값: 10일)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='reports/backtest/result.txt',
        help='출력 파일 경로 (기본값: reports/backtest/result.txt)'
    )
    parser.add_argument(
        '--format',
        type=str,
        choices=['text', 'json', 'html'],
        default='text',
        help='보고서 형식 (기본값: text)'
    )

    return parser.parse_args()


def validate_dates(start_date: str, end_date: str):
    """날짜 유효성 검증"""
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")

        if start >= end:
            raise ValueError("시작일은 종료일보다 이전이어야 합니다")

        return start, end

    except ValueError as e:
        logger.error(f"날짜 형식 오류: {e}", exc_info=True)
        raise


def load_config(args) -> dict:
    """백테스트 설정 로드"""
    trading_config = {
        'stop_loss_pct': args.stop_loss,
        'take_profit_pct': args.take_profit,
        'max_holding_days': args.max_holding_days
    }

    selection_criteria = {
        'min_total_score': 50,
        'min_confidence': 0.3,
        'max_positions': 10
    }

    return {
        'trading': trading_config,
        'selection': selection_criteria
    }


def run_backtest(args) -> tuple:
    """백테스트 메인 로직

    Returns:
        tuple: (BacktestResult, List[Trade])
    """
    logger.info("=" * 80)
    logger.info("백테스트 시작")
    logger.info("=" * 80)
    logger.info(f"기간: {args.start_date} ~ {args.end_date}")
    logger.info(f"전략: {args.strategy}")
    logger.info(f"초기 자본: {args.initial_capital:,.0f}원")
    logger.info(f"손절: {args.stop_loss:.1%}, 익절: {args.take_profit:.1%}, 최대 보유: {args.max_holding_days}일")

    # 날짜 검증
    validate_dates(args.start_date, args.end_date)

    # 백테스터 초기화
    backtester = StrategyBacktester(initial_capital=args.initial_capital)

    # 설정 로드
    config = load_config(args)

    # 백테스트 실행
    logger.info("백테스트 실행 중...")
    print("\n백테스트 실행 중...")
    print(f"기간: {args.start_date} ~ {args.end_date}")
    print("=" * 80)

    result = backtester.backtest_selection_strategy(
        start_date=args.start_date,
        end_date=args.end_date,
        selection_criteria=config['selection'],
        trading_config=config['trading'],
        strategy_name=args.strategy
    )

    # 거래 내역 로드 (백테스터 내부에서 생성된 trades 사용)
    # Note: 현재 구조상 trades를 반환하지 않으므로 빈 리스트 사용
    # TODO: StrategyBacktester가 trades를 반환하도록 수정 필요
    trades = []

    logger.info("백테스트 완료")
    logger.info(f"총 거래: {result.total_trades}건, 승률: {result.win_rate:.1%}, 총수익률: {result.total_return:.2%}")

    return result, trades


def print_summary(result):
    """결과 요약 출력"""
    print("\n" + "=" * 80)
    print("백테스트 결과 요약".center(80))
    print("=" * 80)
    print(f"\n전략명: {result.strategy_name}")
    print(f"기간: {result.start_date} ~ {result.end_date}")
    print("\n[성과 지표]")
    print(f"  총 수익률:        {result.total_return:>10.2%}")
    print(f"  Sharpe Ratio:     {result.sharpe_ratio:>10.2f}")
    print(f"  최대 손실폭:      {result.max_drawdown:>10.2%}")
    print(f"  승률:            {result.win_rate:>10.1%}")
    print("\n[거래 통계]")
    print(f"  총 거래 수:      {result.total_trades:>10}건")
    print(f"  승리 거래:       {result.winning_trades:>10}건")
    print(f"  손실 거래:       {result.losing_trades:>10}건")
    print(f"  평균 보유일:     {result.avg_holding_days:>10.1f}일")
    print("\n[수익/손실 분석]")
    print(f"  평균 수익:       {result.avg_return:>10.2%}")
    print(f"  평균 이익:       {result.avg_win:>10.2%}")
    print(f"  평균 손실:       {result.avg_loss:>10.2%}")
    print(f"  Profit Factor:   {result.profit_factor:>10.2f}")
    print(f"  최고 거래:       {result.best_trade:>10.2%}")
    print(f"  최악 거래:       {result.worst_trade:>10.2%}")
    print("=" * 80)


def save_results(result, trades, output_path: str, format: str):
    """결과 저장"""
    try:
        # 디렉토리 생성
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # 형식별 저장
        if format == 'text':
            # BacktestReporter 사용
            reporter = BacktestReporter(result, trades)
            reporter.save_report(str(output_file), format='text')

        elif format == 'json':
            # JSON 직렬화
            result_dict = asdict(result)
            trades_dict = [asdict(t) for t in trades]

            output_data = {
                'result': result_dict,
                'trades': trades_dict,
                'generated_at': datetime.now().isoformat()
            }

            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)

        elif format == 'html':
            # BacktestReporter 사용
            reporter = BacktestReporter(result, trades)
            reporter.save_report(str(output_file), format='html')

        logger.info(f"결과 저장 완료: {output_file}")
        print(f"\n✅ 결과 저장: {output_file}")

    except Exception as e:
        logger.error(f"결과 저장 중 오류: {e}", exc_info=True)
        print(f"\n❌ 결과 저장 실패: {e}", file=sys.stderr)
        raise


def main():
    """메인 진입점"""
    try:
        # 인자 파싱
        args = parse_args()

        # 백테스트 실행
        result, trades = run_backtest(args)

        # 결과 출력
        print_summary(result)

        # 결과 저장
        save_results(result, trades, args.output, args.format)

        print("\n✅ 백테스트 완료")
        print(f"   상세 결과: {args.output}")

    except KeyboardInterrupt:
        print("\n\n사용자에 의해 중단되었습니다.")
        sys.exit(0)

    except Exception as e:
        logger.error(f"백테스트 실행 중 오류: {e}", exc_info=True)
        print(f"\n❌ 오류 발생: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
