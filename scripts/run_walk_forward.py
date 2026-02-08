#!/usr/bin/env python3
"""
Walk-Forward Analysis 실행 스크립트
Rolling window 방식으로 전략을 Out-of-Sample 검증합니다.

사용 예:
    python scripts/run_walk_forward.py \
        --start-date 2024-01-01 \
        --end-date 2024-12-31 \
        --train-window 180 \
        --test-window 30 \
        --step 30 \
        --output reports/walk_forward/2024_result.txt
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# 프로젝트 루트를 경로에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.backtesting.walk_forward import WalkForwardAnalyzer, WalkForwardConfig, WalkForwardResult
from core.utils.log_utils import get_logger
from dataclasses import asdict

logger = get_logger(__name__)


def parse_args():
    """명령줄 인자 파싱"""
    parser = argparse.ArgumentParser(
        description='Walk-Forward Analysis 실행 스크립트',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예제:
  # 기본 설정 (180일 train, 30일 test, 30일 step)
  python scripts/run_walk_forward.py --start-date 2024-01-01 --end-date 2024-12-31

  # 윈도우 설정 커스터마이징
  python scripts/run_walk_forward.py \
      --start-date 2024-01-01 \
      --end-date 2024-12-31 \
      --train-window 120 \
      --test-window 20 \
      --step 20

  # JSON 형식으로 저장
  python scripts/run_walk_forward.py \
      --start-date 2024-01-01 \
      --end-date 2024-12-31 \
      --format json \
      --output reports/walk_forward/2024.json
        """
    )

    parser.add_argument(
        '--start-date',
        type=str,
        required=True,
        help='전체 분석 시작일 (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--end-date',
        type=str,
        required=True,
        help='전체 분석 종료일 (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--train-window',
        type=int,
        default=180,
        help='Train 윈도우 일수 (기본값: 180일 = 6개월)'
    )
    parser.add_argument(
        '--test-window',
        type=int,
        default=30,
        help='Test 윈도우 일수 (기본값: 30일 = 1개월)'
    )
    parser.add_argument(
        '--step',
        type=int,
        default=30,
        help='윈도우 이동 일수 (기본값: 30일)'
    )
    parser.add_argument(
        '--min-trades',
        type=int,
        default=20,
        help='윈도우 최소 거래 수 (기본값: 20건)'
    )
    parser.add_argument(
        '--purge-days',
        type=int,
        default=5,
        help='Train/Test 사이 격리 기간 (기본값: 5일)'
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
        default='reports/walk_forward/result.txt',
        help='출력 파일 경로 (기본값: reports/walk_forward/result.txt)'
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
    """Walk-Forward 설정 로드"""
    wf_config = WalkForwardConfig(
        train_window_days=args.train_window,
        test_window_days=args.test_window,
        step_days=args.step,
        min_train_trades=args.min_trades,
        purge_days=args.purge_days
    )

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
        'walk_forward': wf_config,
        'trading': trading_config,
        'selection': selection_criteria
    }


def run_walk_forward(args) -> WalkForwardResult:
    """Walk-Forward Analysis 메인 로직

    Returns:
        WalkForwardResult: 종합 결과
    """
    logger.info("=" * 80)
    logger.info("Walk-Forward Analysis 시작")
    logger.info("=" * 80)
    logger.info(f"기간: {args.start_date} ~ {args.end_date}")
    logger.info(f"Train: {args.train_window}일, Test: {args.test_window}일, Step: {args.step}일")
    logger.info(f"최소 거래: {args.min_trades}건, Purge: {args.purge_days}일")

    # 날짜 검증
    validate_dates(args.start_date, args.end_date)

    # 설정 로드
    config = load_config(args)

    # Walk-Forward Analyzer 초기화
    analyzer = WalkForwardAnalyzer(config=config['walk_forward'])

    # 실행
    logger.info("Walk-Forward Analysis 실행 중...")
    print("\nWalk-Forward Analysis 실행 중...")
    print(f"기간: {args.start_date} ~ {args.end_date}")
    print(f"Train: {args.train_window}일, Test: {args.test_window}일, Step: {args.step}일")
    print("=" * 80)

    result = analyzer.run(
        start_date=args.start_date,
        end_date=args.end_date,
        selection_criteria=config['selection'],
        trading_config=config['trading'],
        strategy_name="walk_forward_strategy"
    )

    logger.info("Walk-Forward Analysis 완료")
    logger.info(f"유효 윈도우: {result.valid_windows}/{result.total_windows}")
    logger.info(f"평균 Test Sharpe: {result.avg_test_sharpe:.3f}, OF Ratio: {result.overall_overfitting_ratio:.3f}")

    return result


def print_window_results(wf_result: WalkForwardResult):
    """윈도우별 결과 출력"""
    if not wf_result.windows:
        print("\n유효한 윈도우가 없습니다.")
        return

    print("\n" + "=" * 80)
    print("윈도우별 결과".center(80))
    print("=" * 80)

    for i, window in enumerate(wf_result.windows, start=1):
        print(f"\n[윈도우 {window.window_index}]")
        print(f"  Train: {window.train_start} ~ {window.train_end}")
        print(f"  Test:  {window.test_start} ~ {window.test_end}")
        print("  Train 결과:")
        print(f"    - 거래수: {window.train_result.total_trades}건")
        print(f"    - 승률: {window.train_result.win_rate:.1%}")
        print(f"    - 수익률: {window.train_result.total_return:+.2%}")
        print(f"    - Sharpe: {window.train_result.sharpe_ratio:.3f}")
        print("  Test 결과:")
        print(f"    - 거래수: {window.test_result.total_trades}건")
        print(f"    - 승률: {window.test_result.win_rate:.1%}")
        print(f"    - 수익률: {window.test_result.total_return:+.2%}")
        print(f"    - Sharpe: {window.test_result.sharpe_ratio:.3f}")
        print(f"  Overfitting Ratio: {window.overfitting_ratio:.3f}")

    print("=" * 80)


def print_summary(wf_result: WalkForwardResult):
    """종합 결과 요약 출력"""
    print("\n" + "=" * 80)
    print("Walk-Forward Analysis 종합 결과".center(80))
    print("=" * 80)

    print("\n[윈도우 정보]")
    print(f"  전체 윈도우: {wf_result.total_windows}개")
    print(f"  유효 윈도우: {wf_result.valid_windows}개")
    print(f"  Train: {wf_result.config.train_window_days}일")
    print(f"  Test: {wf_result.config.test_window_days}일")
    print(f"  Step: {wf_result.config.step_days}일")

    print("\n[평균 성과 - Train]")
    print(f"  평균 수익률: {wf_result.avg_train_return:>10.2%}")
    print(f"  평균 Sharpe: {wf_result.avg_train_sharpe:>10.3f}")

    print("\n[평균 성과 - Test]")
    print(f"  평균 수익률: {wf_result.avg_test_return:>10.2%}")
    print(f"  평균 Sharpe: {wf_result.avg_test_sharpe:>10.3f}")

    print("\n[과적합 분석]")
    print(f"  Overfitting Ratio: {wf_result.overall_overfitting_ratio:>10.3f}")
    of_status = "✅ 양호" if wf_result.overall_overfitting_ratio > 0.5 else "❌ 과적합 의심"
    print(f"  평가: {of_status}")

    print("\n[일관성 분석]")
    print(f"  Consistency Score: {wf_result.consistency_score:>10.4f}")
    consistency_status = "✅ 안정적" if wf_result.consistency_score < 0.05 else "⭕ 변동성 높음"
    print(f"  평가: {consistency_status}")

    print("=" * 80)


def save_results(wf_result: WalkForwardResult, output_path: str, format: str):
    """결과 저장"""
    try:
        # 디렉토리 생성
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        if format == 'text':
            # 텍스트 보고서 생성
            lines = []
            lines.append("=" * 80)
            lines.append("Walk-Forward Analysis 결과 보고서".center(80))
            lines.append("=" * 80)
            lines.append("")
            lines.append(f"생성일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            lines.append("")

            lines.append("-" * 80)
            lines.append("[설정]")
            lines.append("-" * 80)
            lines.append(f"Train 윈도우: {wf_result.config.train_window_days}일")
            lines.append(f"Test 윈도우: {wf_result.config.test_window_days}일")
            lines.append(f"Step: {wf_result.config.step_days}일")
            lines.append(f"최소 거래: {wf_result.config.min_train_trades}건")
            lines.append(f"Purge: {wf_result.config.purge_days}일")
            lines.append("")

            lines.append("-" * 80)
            lines.append("[종합 결과]")
            lines.append("-" * 80)
            lines.append(f"전체 윈도우: {wf_result.total_windows}개")
            lines.append(f"유효 윈도우: {wf_result.valid_windows}개")
            lines.append(f"평균 Train 수익률: {wf_result.avg_train_return:.2%}")
            lines.append(f"평균 Test 수익률: {wf_result.avg_test_return:.2%}")
            lines.append(f"평균 Train Sharpe: {wf_result.avg_train_sharpe:.3f}")
            lines.append(f"평균 Test Sharpe: {wf_result.avg_test_sharpe:.3f}")
            lines.append(f"Overfitting Ratio: {wf_result.overall_overfitting_ratio:.3f}")
            lines.append(f"Consistency Score: {wf_result.consistency_score:.4f}")
            lines.append("")

            if wf_result.windows:
                lines.append("-" * 80)
                lines.append("[윈도우별 결과]")
                lines.append("-" * 80)
                for window in wf_result.windows:
                    lines.append(f"\nWindow {window.window_index}:")
                    lines.append(f"  Train: {window.train_start} ~ {window.train_end}")
                    lines.append(f"  Test:  {window.test_start} ~ {window.test_end}")
                    lines.append(f"  Train Sharpe: {window.train_result.sharpe_ratio:.3f}")
                    lines.append(f"  Test Sharpe:  {window.test_result.sharpe_ratio:.3f}")
                    lines.append(f"  OF Ratio:     {window.overfitting_ratio:.3f}")
                lines.append("")

            lines.append("=" * 80)

            with open(output_file, 'w', encoding='utf-8') as f:
                f.write("\n".join(lines))

        elif format == 'json':
            # JSON 직렬화
            output_data = {
                'config': asdict(wf_result.config),
                'summary': {
                    'total_windows': wf_result.total_windows,
                    'valid_windows': wf_result.valid_windows,
                    'avg_train_sharpe': wf_result.avg_train_sharpe,
                    'avg_test_sharpe': wf_result.avg_test_sharpe,
                    'avg_train_return': wf_result.avg_train_return,
                    'avg_test_return': wf_result.avg_test_return,
                    'overall_overfitting_ratio': wf_result.overall_overfitting_ratio,
                    'consistency_score': wf_result.consistency_score
                },
                'windows': [
                    {
                        'window_index': w.window_index,
                        'train_start': w.train_start,
                        'train_end': w.train_end,
                        'test_start': w.test_start,
                        'test_end': w.test_end,
                        'train_result': asdict(w.train_result),
                        'test_result': asdict(w.test_result),
                        'overfitting_ratio': w.overfitting_ratio
                    }
                    for w in wf_result.windows
                ],
                'generated_at': datetime.now().isoformat()
            }

            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)

        elif format == 'html':
            # 간단한 HTML 보고서
            html = f"""
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <title>Walk-Forward Analysis 결과</title>
    <style>
        body {{ font-family: 'Segoe UI', sans-serif; margin: 20px; background-color: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }}
        h1 {{ text-align: center; color: #333; border-bottom: 3px solid #4CAF50; padding-bottom: 10px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background-color: #4CAF50; color: white; }}
        tr:hover {{ background-color: #f5f5f5; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Walk-Forward Analysis 결과</h1>
        <p><strong>생성일시:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

        <h2>설정</h2>
        <p>Train: {wf_result.config.train_window_days}일, Test: {wf_result.config.test_window_days}일, Step: {wf_result.config.step_days}일</p>

        <h2>종합 결과</h2>
        <table>
            <tr><th>항목</th><th>값</th></tr>
            <tr><td>전체 윈도우</td><td>{wf_result.total_windows}개</td></tr>
            <tr><td>유효 윈도우</td><td>{wf_result.valid_windows}개</td></tr>
            <tr><td>평균 Train Sharpe</td><td>{wf_result.avg_train_sharpe:.3f}</td></tr>
            <tr><td>평균 Test Sharpe</td><td>{wf_result.avg_test_sharpe:.3f}</td></tr>
            <tr><td>Overfitting Ratio</td><td>{wf_result.overall_overfitting_ratio:.3f}</td></tr>
            <tr><td>Consistency Score</td><td>{wf_result.consistency_score:.4f}</td></tr>
        </table>

        <h2>윈도우별 결과</h2>
        <table>
            <tr>
                <th>윈도우</th>
                <th>Train 기간</th>
                <th>Test 기간</th>
                <th>Train Sharpe</th>
                <th>Test Sharpe</th>
                <th>OF Ratio</th>
            </tr>
"""
            for window in wf_result.windows:
                html += f"""
            <tr>
                <td>{window.window_index}</td>
                <td>{window.train_start} ~ {window.train_end}</td>
                <td>{window.test_start} ~ {window.test_end}</td>
                <td>{window.train_result.sharpe_ratio:.3f}</td>
                <td>{window.test_result.sharpe_ratio:.3f}</td>
                <td>{window.overfitting_ratio:.3f}</td>
            </tr>
"""
            html += """
        </table>
    </div>
</body>
</html>
"""
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(html)

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

        # Walk-Forward Analysis 실행
        result = run_walk_forward(args)

        # 결과 출력
        print_window_results(result)
        print_summary(result)

        # 결과 저장
        save_results(result, args.output, args.format)

        print("\n✅ Walk-Forward Analysis 완료")
        print(f"   상세 결과: {args.output}")

    except KeyboardInterrupt:
        print("\n\n사용자에 의해 중단되었습니다.")
        sys.exit(0)

    except Exception as e:
        logger.error(f"Walk-Forward Analysis 실행 중 오류: {e}", exc_info=True)
        print(f"\n❌ 오류 발생: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
