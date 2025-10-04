"""
Historical data collection script.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import argparse
import logging
from datetime import datetime, timedelta
import json
from pathlib import Path

from core.api.kis_api import KISAPI
from core.config import settings
from core.database import StockRepository
from hantu_common.data.collector import StockDataCollector
from hantu_common.data.stock_list import StockListManager

# 로깅 설정
log_file = settings.LOG_DIR / 'data_collection.log'
logging.basicConfig(
    level=settings.LOG_LEVEL,
    format=settings.LOG_FORMAT,
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def collect_data(args):
    """데이터 수집 실행"""
    try:
        # API 클라이언트 초기화
        api = KISAPI()
        collector = StockDataCollector(api)
        stock_manager = StockListManager()
        repository = StockRepository()
        
        # 종목 목록 로드
        stock_list = stock_manager.load_latest_stock_list()
        stock_codes = [stock['ticker'] for stock in stock_list]
        
        logger.info(f"[collect_data] 데이터 수집 시작 - {len(stock_codes)}개 종목")
        logger.info(f"[collect_data] 기간: {args.start_date} ~ {args.end_date}")
        
        # 데이터 수집
        data = collector.collect_stock_data(
            stock_codes=stock_codes,
            start_date=args.start_date,
            end_date=args.end_date,
            data_type=args.data_type,
            delay=args.delay
        )
            
        # 기술적 지표 계산
        if args.calculate_indicators:
            indicators = []
            
            # 기본 지표 추가
            if args.default_indicators:
                indicators.extend([
                    {'name': 'rsi', 'params': {'period': args.rsi_period}},
                    {'name': 'ma', 'params': {'period': args.ma_period, 'ma_type': args.ma_type}},
                    {'name': 'bollinger', 'params': {'period': args.bb_period, 'num_std': args.bb_std}},
                    {'name': 'macd', 'params': {
                        'fast_period': args.macd_fast,
                        'slow_period': args.macd_slow,
                        'signal_period': args.macd_signal
                    }}
                ])
            
            # 사용자 정의 지표 추가
            if args.indicators_file:
                indicators_file = Path(args.indicators_file)
                if not indicators_file.is_absolute():
                    indicators_file = settings.ROOT_DIR / indicators_file
                    
                with open(indicators_file, 'r') as f:
                    custom_indicators = json.load(f)
                indicators.extend(custom_indicators)
            
            if indicators:
                collector.process_technical_indicators(data, indicators)
            
        logger.info("[collect_data] 데이터 수집 및 저장 완료")
            
    except Exception as e:
        logger.error(f"[collect_data] 데이터 수집 중 오류 발생: {str(e)}")
        raise

def main():
    parser = argparse.ArgumentParser(description='한투 퀀트 과거 데이터 수집')
    
    # 기간 설정
    parser.add_argument('--start-date', type=str,
                      help='수집 시작일 (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str,
                      default=(datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'),
                      help='수집 종료일 (YYYY-MM-DD)')
    
    # 데이터 유형
    parser.add_argument('--data-type', type=str, choices=['daily', 'minute', 'tick'],
                      default='daily', help='데이터 유형')
    
    # API 호출 간격
    parser.add_argument('--delay', type=float, default=0.5,
                      help='API 호출 간격 (초)')
    
    # 기술적 지표 설정
    parser.add_argument('--calculate-indicators', action='store_true',
                      help='기술적 지표 계산')
    parser.add_argument('--default-indicators', action='store_true',
                      help='기본 기술적 지표 계산')
    parser.add_argument('--indicators-file', type=str,
                      help='사용자 정의 지표 설정 파일 (JSON)')
    
    # 기본 지표 파라미터
    parser.add_argument('--rsi-period', type=int, default=14,
                      help='RSI 계산 기간')
    parser.add_argument('--ma-period', type=int, default=20,
                      help='이동평균 계산 기간')
    parser.add_argument('--ma-type', type=str, choices=['sma', 'ema', 'wma'],
                      default='sma', help='이동평균 유형')
    parser.add_argument('--bb-period', type=int, default=20,
                      help='볼린저 밴드 계산 기간')
    parser.add_argument('--bb-std', type=float, default=2.0,
                      help='볼린저 밴드 표준편차')
    parser.add_argument('--macd-fast', type=int, default=12,
                      help='MACD 단기 기간')
    parser.add_argument('--macd-slow', type=int, default=26,
                      help='MACD 장기 기간')
    parser.add_argument('--macd-signal', type=int, default=9,
                      help='MACD 시그널 기간')
    
    args = parser.parse_args()
    
    try:
        collect_data(args)
    except KeyboardInterrupt:
        logger.info("사용자에 의해 프로그램이 종료되었습니다.")
    except Exception as e:
        logger.error(f"프로그램 실행 중 오류 발생: {str(e)}")
        raise

if __name__ == "__main__":
    main() 