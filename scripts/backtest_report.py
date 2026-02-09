#!/usr/bin/env python3
"""
백테스트 결과 보고서 생성 유틸리티
저장된 백테스트 결과 JSON 파일을 다양한 형식으로 변환합니다.

사용 예:
    # JSON → HTML 변환
    python scripts/backtest_report.py \
        --input reports/backtest/2024_result.json \
        --format html \
        --output reports/backtest/2024_result.html

    # JSON → Text 변환
    python scripts/backtest_report.py \
        --input reports/backtest/2024_result.json \
        --format text \
        --output reports/backtest/2024_result.txt
"""

import argparse
import json
import sys
from pathlib import Path

# 프로젝트 루트를 경로에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.backtesting.models import BacktestResult, Trade
from core.backtesting.result_reporter import BacktestReporter
from core.utils.log_utils import get_logger

logger = get_logger(__name__)


def parse_args():
    """명령줄 인자 파싱"""
    parser = argparse.ArgumentParser(
        description='백테스트 결과 보고서 생성 유틸리티',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예제:
  # JSON을 HTML로 변환
  python scripts/backtest_report.py \\
      --input reports/backtest/2024_result.json \\
      --format html \\
      --output reports/backtest/2024_result.html

  # JSON을 Text로 변환
  python scripts/backtest_report.py \\
      --input reports/backtest/2024_result.json \\
      --format text \\
      --output reports/backtest/2024_result.txt

  # 출력 경로 자동 생성 (확장자만 변경)
  python scripts/backtest_report.py \\
      --input reports/backtest/2024_result.json \\
      --format html
        """
    )

    parser.add_argument(
        '--input',
        type=str,
        required=True,
        help='입력 JSON 파일 경로'
    )
    parser.add_argument(
        '--format',
        type=str,
        choices=['text', 'json', 'html'],
        required=True,
        help='출력 형식'
    )
    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='출력 파일 경로 (미지정 시 입력 파일명 + 확장자 변경)'
    )

    return parser.parse_args()


def load_backtest_result(input_path: str) -> tuple:
    """백테스트 결과 JSON 로드

    Args:
        input_path: JSON 파일 경로

    Returns:
        tuple: (BacktestResult, List[Trade])
    """
    try:
        input_file = Path(input_path)

        if not input_file.exists():
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {input_path}")

        logger.info(f"백테스트 결과 로드 중: {input_path}")

        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # BacktestResult 복원
        result_dict = data.get('result', {})
        result = BacktestResult(
            strategy_name=result_dict.get('strategy_name', 'Unknown'),
            start_date=result_dict.get('start_date', ''),
            end_date=result_dict.get('end_date', ''),
            total_trades=result_dict.get('total_trades', 0),
            winning_trades=result_dict.get('winning_trades', 0),
            losing_trades=result_dict.get('losing_trades', 0),
            win_rate=result_dict.get('win_rate', 0.0),
            avg_return=result_dict.get('avg_return', 0.0),
            avg_win=result_dict.get('avg_win', 0.0),
            avg_loss=result_dict.get('avg_loss', 0.0),
            max_drawdown=result_dict.get('max_drawdown', 0.0),
            sharpe_ratio=result_dict.get('sharpe_ratio', 0.0),
            sortino_ratio=result_dict.get('sortino_ratio', 0.0),
            total_return=result_dict.get('total_return', 0.0),
            profit_factor=result_dict.get('profit_factor', 0.0),
            best_trade=result_dict.get('best_trade', 0.0),
            worst_trade=result_dict.get('worst_trade', 0.0),
            avg_holding_days=result_dict.get('avg_holding_days', 0.0)
        )

        # Trade 리스트 복원
        trades_data = data.get('trades', [])
        trades = []
        for trade_dict in trades_data:
            trade = Trade(
                stock_code=trade_dict.get('stock_code', ''),
                stock_name=trade_dict.get('stock_name', ''),
                entry_date=trade_dict.get('entry_date', ''),
                entry_price=trade_dict.get('entry_price', 0.0),
                exit_date=trade_dict.get('exit_date'),
                exit_price=trade_dict.get('exit_price'),
                quantity=trade_dict.get('quantity', 0),
                return_pct=trade_dict.get('return_pct'),
                holding_days=trade_dict.get('holding_days'),
                exit_reason=trade_dict.get('exit_reason')
            )
            trades.append(trade)

        logger.info(f"백테스트 결과 로드 완료: {result.total_trades}건 거래")
        return result, trades

    except FileNotFoundError as e:
        logger.error(f"파일 로드 실패: {e}", exc_info=True)
        raise

    except json.JSONDecodeError as e:
        logger.error(f"JSON 파싱 실패: {e}", exc_info=True)
        raise ValueError(f"유효하지 않은 JSON 파일: {input_path}")

    except Exception as e:
        logger.error(f"백테스트 결과 로드 중 오류: {e}", exc_info=True)
        raise


def generate_report(result: BacktestResult, trades: list, format: str) -> str:
    """지정된 형식으로 보고서 생성

    Args:
        result: 백테스트 결과
        trades: 거래 내역
        format: 출력 형식 ('text', 'json', 'html')

    Returns:
        str: 생성된 보고서 내용
    """
    try:
        reporter = BacktestReporter(result, trades)

        if format == 'text':
            return reporter.generate_text_report()

        elif format == 'json':
            return reporter.generate_json_report()

        elif format == 'html':
            return reporter.generate_html_report()

        else:
            raise ValueError(f"지원하지 않는 형식: {format}")

    except Exception as e:
        logger.error(f"보고서 생성 중 오류: {e}", exc_info=True)
        raise


def determine_output_path(input_path: str, output_path: str, format: str) -> str:
    """출력 파일 경로 결정

    Args:
        input_path: 입력 파일 경로
        output_path: 사용자 지정 출력 경로 (None 가능)
        format: 출력 형식

    Returns:
        str: 결정된 출력 파일 경로
    """
    if output_path:
        return output_path

    # 출력 경로 미지정 시: 입력 파일명 + 확장자 변경
    input_file = Path(input_path)
    extension_map = {
        'text': '.txt',
        'json': '.json',
        'html': '.html'
    }

    extension = extension_map.get(format, '.txt')
    output_file = input_file.with_suffix(extension)

    return str(output_file)


def save_report(content: str, output_path: str):
    """보고서 파일 저장

    Args:
        content: 보고서 내용
        output_path: 출력 파일 경로
    """
    try:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(content)

        logger.info(f"보고서 저장 완료: {output_path}")
        print(f"✅ 보고서 저장: {output_path}")

    except Exception as e:
        logger.error(f"보고서 저장 중 오류: {e}", exc_info=True)
        raise


def main():
    """메인 진입점"""
    try:
        # 인자 파싱
        args = parse_args()

        print("백테스트 보고서 생성 중...")
        print(f"입력: {args.input}")
        print(f"형식: {args.format}")

        # 백테스트 결과 로드
        result, trades = load_backtest_result(args.input)

        # 출력 경로 결정
        output_path = determine_output_path(args.input, args.output, args.format)
        print(f"출력: {output_path}")
        print("=" * 80)

        # 보고서 생성
        content = generate_report(result, trades, args.format)

        # 보고서 저장
        save_report(content, output_path)

        # 요약 출력
        print("\n백테스트 결과 요약:")
        print(f"  전략: {result.strategy_name}")
        print(f"  기간: {result.start_date} ~ {result.end_date}")
        print(f"  총 거래: {result.total_trades}건")
        print(f"  승률: {result.win_rate:.1%}")
        print(f"  총 수익률: {result.total_return:+.2%}")
        print(f"  Sharpe Ratio: {result.sharpe_ratio:.2f}")

        print("\n✅ 보고서 생성 완료")
        print(f"   출력: {output_path}")

    except KeyboardInterrupt:
        print("\n\n사용자에 의해 중단되었습니다.")
        sys.exit(0)

    except Exception as e:
        logger.error(f"보고서 생성 중 오류: {e}", exc_info=True)
        print(f"\n❌ 오류 발생: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
