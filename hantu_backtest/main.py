"""
Backtesting main script.
"""

import argparse
import logging
from datetime import datetime, timedelta
from pathlib import Path

from core.backtest import Backtest
from strategies.momentum import MomentumStrategy

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('backtest.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def run_backtest(args):
    """백테스트 실행"""
    try:
        # 전략 초기화
        strategy = MomentumStrategy(
            rsi_period=args.rsi_period,
            rsi_buy_threshold=args.rsi_buy_threshold,
            rsi_sell_threshold=args.rsi_sell_threshold,
            ma_short=args.ma_short,
            ma_medium=args.ma_medium,
            min_volume=args.min_volume,
            volume_surge_ratio=args.volume_surge_ratio
        )
        
        # 백테스터 초기화
        backtest = Backtest(
            strategy=strategy,
            start_date=args.start_date,
            end_date=args.end_date,
            initial_capital=args.initial_capital,
            commission=args.commission,
            slippage=args.slippage
        )
        
        # 백테스트 실행
        results = backtest.run()
        
        # 결과 출력
        print("\n=== 백테스트 결과 ===")
        print(f"전략: {strategy.name}")
        print(f"기간: {args.start_date} ~ {args.end_date}")
        print(f"초기자본: {args.initial_capital:,.0f}원")
        print(f"최종자본: {results['equity_curve'].iloc[-1]:,.0f}원")
        print(f"총수익률: {results['metrics']['total_return']:.2f}%")
        print(f"연간수익률: {results['metrics']['annual_return']:.2f}%")
        print(f"최대낙폭: {results['metrics']['max_drawdown']:.2f}%")
        print(f"샤프비율: {results['metrics']['sharpe_ratio']:.2f}")
        print(f"총거래횟수: {results['metrics']['total_trades']}회")
        print(f"승률: {results['metrics']['win_rate']:.2f}%")
        
    except Exception as e:
        logger.error(f"백테스트 실행 중 오류 발생: {str(e)}")
        raise

def main():
    parser = argparse.ArgumentParser(description='한투 퀀트 백테스팅 시스템')
    
    # 기간 설정
    parser.add_argument('--start-date', type=str, default='2023-01-01',
                      help='백테스트 시작일 (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, 
                      default=(datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'),
                      help='백테스트 종료일 (YYYY-MM-DD)')
    
    # 자본금 설정
    parser.add_argument('--initial-capital', type=float, default=100_000_000,
                      help='초기자본금')
    parser.add_argument('--commission', type=float, default=0.00015,
                      help='수수료율')
    parser.add_argument('--slippage', type=float, default=0.0001,
                      help='슬리피지')
    
    # 전략 파라미터
    parser.add_argument('--rsi-period', type=int, default=14,
                      help='RSI 계산 기간')
    parser.add_argument('--rsi-buy-threshold', type=int, default=30,
                      help='RSI 매수 임계값')
    parser.add_argument('--rsi-sell-threshold', type=int, default=70,
                      help='RSI 매도 임계값')
    parser.add_argument('--ma-short', type=int, default=5,
                      help='단기 이동평균 기간')
    parser.add_argument('--ma-medium', type=int, default=20,
                      help='중기 이동평균 기간')
    parser.add_argument('--min-volume', type=int, default=10000,
                      help='최소 거래량')
    parser.add_argument('--volume-surge-ratio', type=float, default=2.0,
                      help='거래량 급증 비율')
    
    args = parser.parse_args()
    
    try:
        run_backtest(args)
    except KeyboardInterrupt:
        logger.info("사용자에 의해 프로그램이 종료되었습니다.")
    except Exception as e:
        logger.error(f"프로그램 실행 중 오류 발생: {str(e)}")
        raise

if __name__ == "__main__":
    main() 