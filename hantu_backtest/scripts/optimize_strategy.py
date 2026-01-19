"""
Strategy optimization script.
"""

import argparse
import logging
from datetime import datetime, timedelta

from ..strategies.momentum import MomentumStrategy
from ..optimization.optimizer import StrategyOptimizer

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('optimization.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def optimize_strategy(args):
    """전략 최적화 실행"""
    try:
        # 파라미터 그리드 설정
        param_grid = {
            'rsi_period': [10, 14, 20],
            'rsi_buy_threshold': [20, 25, 30, 35],
            'rsi_sell_threshold': [65, 70, 75, 80],
            'ma_short': [3, 5, 10],
            'ma_medium': [15, 20, 25],
            'min_volume': [5000, 10000, 20000],
            'volume_surge_ratio': [1.5, 2.0, 2.5]
        }
        
        # 최적화 실행
        optimizer = StrategyOptimizer(
            strategy_class=MomentumStrategy,
            param_grid=param_grid,
            start_date=args.start_date,
            end_date=args.end_date,
            initial_capital=args.initial_capital,
            commission=args.commission,
            slippage=args.slippage,
            metric=args.metric,
            n_jobs=args.n_jobs
        )
        
        best_params, results = optimizer.optimize()
        
        # 결과 출력
        print("\n=== 최적화 결과 ===")
        print(f"최적 파라미터:")
        for param, value in best_params.items():
            print(f"  - {param}: {value}")
            
        best_result = results.loc[results[args.metric].idxmax()]
        print(f"\n최적 성과:")
        print(f"  - {args.metric}: {best_result[args.metric]:.4f}")
        print(f"  - 총수익률: {best_result['total_return']:.2f}%")
        print(f"  - 샤프비율: {best_result['sharpe_ratio']:.2f}")
        print(f"  - 최대낙폭: {best_result['max_drawdown']:.2f}%")
        print(f"  - 승률: {best_result['win_rate']:.2f}%")
        
    except Exception as e:
        logger.error(f"최적화 실행 중 오류 발생: {str(e)}")
        raise

def main():
    parser = argparse.ArgumentParser(description='한투 퀀트 전략 최적화')
    
    # 기간 설정
    parser.add_argument('--start-date', type=str, default='2023-01-01',
                      help='최적화 시작일 (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, 
                      default=(datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'),
                      help='최적화 종료일 (YYYY-MM-DD)')
    
    # 자본금 설정
    parser.add_argument('--initial-capital', type=float, default=100_000_000,
                      help='초기자본금')
    parser.add_argument('--commission', type=float, default=0.00015,
                      help='수수료율')
    parser.add_argument('--slippage', type=float, default=0.0001,
                      help='슬리피지')
    
    # 최적화 설정
    parser.add_argument('--metric', type=str, default='sharpe_ratio',
                      choices=['sharpe_ratio', 'total_return', 'win_rate'],
                      help='최적화 기준 지표')
    parser.add_argument('--n-jobs', type=int, default=-1,
                      help='병렬 처리 수 (-1: 모든 CPU 사용)')
    
    args = parser.parse_args()
    
    try:
        optimize_strategy(args)
    except KeyboardInterrupt:
        logger.info("사용자에 의해 프로그램이 종료되었습니다.")
    except Exception as e:
        logger.error(f"프로그램 실행 중 오류 발생: {str(e)}")
        raise

if __name__ == "__main__":
    main() 