"""
데이터베이스 조회 스크립트
"""

import argparse
import logging
from datetime import datetime, timedelta
from tabulate import tabulate
from core.database import StockRepository

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def query_stocks(args):
    """종목 정보 조회"""
    repository = StockRepository()
    
    if args.code:
        # 단일 종목 조회
        stock = repository.get_stock(args.code)
        if stock:
            print("\n=== 종목 정보 ===")
            print(f"종목코드: {stock.code}")
            print(f"종목명: {stock.name}")
            print(f"시장: {stock.market}")
            print(f"섹터: {stock.sector}")
            print(f"갱신일시: {stock.updated_at}")
    else:
        # 전체 종목 목록 조회
        stocks = repository.get_all_stocks()
        data = [[s.code, s.name, s.market, s.sector] for s in stocks]
        print("\n" + tabulate(data, headers=['종목코드', '종목명', '시장', '섹터']))

def query_prices(args):
    """주가 데이터 조회"""
    repository = StockRepository()
    
    # 종목 확인
    stock = repository.get_stock(args.code)
    if not stock:
        logger.error(f"종목을 찾을 수 없습니다: {args.code}")
        return
        
    # 기간 설정
    end_date = datetime.strptime(args.end_date, '%Y-%m-%d') if args.end_date else datetime.now()
    start_date = datetime.strptime(args.start_date, '%Y-%m-%d') if args.start_date else end_date - timedelta(days=30)
    
    # 데이터 조회
    prices = repository.get_stock_prices(stock.id, start_date, end_date)
    
    # 결과 출력
    data = [[
        p.date.strftime('%Y-%m-%d'),
        f"{p.open:,}",
        f"{p.high:,}",
        f"{p.low:,}",
        f"{p.close:,}",
        f"{p.volume:,}"
    ] for p in prices]
    
    print(f"\n=== {stock.name} ({stock.code}) 주가 데이터 ===")
    print(tabulate(data, headers=['날짜', '시가', '고가', '저가', '종가', '거래량']))

def query_indicators(args):
    """기술적 지표 조회"""
    repository = StockRepository()
    
    # 종목 확인
    stock = repository.get_stock(args.code)
    if not stock:
        logger.error(f"종목을 찾을 수 없습니다: {args.code}")
        return
        
    # 기간 설정
    end_date = datetime.strptime(args.end_date, '%Y-%m-%d') if args.end_date else datetime.now()
    start_date = datetime.strptime(args.start_date, '%Y-%m-%d') if args.start_date else end_date - timedelta(days=30)
    
    # 데이터 조회
    indicators = repository.get_technical_indicators(
        stock.id,
        args.indicator_type,
        start_date,
        end_date
    )
    
    # 결과 출력
    data = [[
        i.date.strftime('%Y-%m-%d'),
        i.indicator_type,
        f"{i.value:.2f}",
        i.params
    ] for i in indicators]
    
    print(f"\n=== {stock.name} ({stock.code}) 기술적 지표 ===")
    print(tabulate(data, headers=['날짜', '지표', '값', '파라미터']))

def query_trades(args):
    """거래 내역 조회"""
    repository = StockRepository()
    
    # 종목 확인
    stock = repository.get_stock(args.code) if args.code else None
    
    # 기간 설정
    end_date = datetime.strptime(args.end_date, '%Y-%m-%d') if args.end_date else datetime.now()
    start_date = datetime.strptime(args.start_date, '%Y-%m-%d') if args.start_date else end_date - timedelta(days=30)
    
    # 데이터 조회
    trades = repository.get_trades(
        stock.id if stock else None,
        start_date,
        end_date
    )
    
    # 결과 출력
    data = [[
        t.datetime.strftime('%Y-%m-%d %H:%M:%S'),
        repository.get_stock(t.stock_id).code,
        t.type,
        f"{t.price:,}",
        t.quantity,
        f"{t.amount:,}",
        t.strategy
    ] for t in trades]
    
    print("\n=== 거래 내역 ===")
    print(tabulate(data, headers=['일시', '종목코드', '유형', '가격', '수량', '금액', '전략']))

def main():
    parser = argparse.ArgumentParser(description='데이터베이스 조회')
    subparsers = parser.add_subparsers(dest='command', help='조회 유형')
    
    # 종목 정보 조회
    stocks_parser = subparsers.add_parser('stocks', help='종목 정보 조회')
    stocks_parser.add_argument('--code', type=str, help='종목코드')
    
    # 주가 데이터 조회
    prices_parser = subparsers.add_parser('prices', help='주가 데이터 조회')
    prices_parser.add_argument('code', type=str, help='종목코드')
    prices_parser.add_argument('--start-date', type=str, help='시작일 (YYYY-MM-DD)')
    prices_parser.add_argument('--end-date', type=str, help='종료일 (YYYY-MM-DD)')
    
    # 기술적 지표 조회
    indicators_parser = subparsers.add_parser('indicators', help='기술적 지표 조회')
    indicators_parser.add_argument('code', type=str, help='종목코드')
    indicators_parser.add_argument('indicator_type', type=str, help='지표 유형')
    indicators_parser.add_argument('--start-date', type=str, help='시작일 (YYYY-MM-DD)')
    indicators_parser.add_argument('--end-date', type=str, help='종료일 (YYYY-MM-DD)')
    
    # 거래 내역 조회
    trades_parser = subparsers.add_parser('trades', help='거래 내역 조회')
    trades_parser.add_argument('--code', type=str, help='종목코드')
    trades_parser.add_argument('--start-date', type=str, help='시작일 (YYYY-MM-DD)')
    trades_parser.add_argument('--end-date', type=str, help='종료일 (YYYY-MM-DD)')
    
    args = parser.parse_args()
    
    try:
        if args.command == 'stocks':
            query_stocks(args)
        elif args.command == 'prices':
            query_prices(args)
        elif args.command == 'indicators':
            query_indicators(args)
        elif args.command == 'trades':
            query_trades(args)
        else:
            parser.print_help()
            
    except Exception as e:
        logger.error(f"조회 중 오류 발생: {str(e)}")
        raise

if __name__ == "__main__":
    main() 