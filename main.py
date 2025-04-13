# main.py

import argparse
import asyncio
import logging
import schedule
import time
from datetime import datetime

from core.api.kis_api import KISAPI
from core.api.krx_client import KRXClient
from core.trading.auto_trader import AutoTrader
from hantu_backtest.strategies.momentum import MomentumStrategy as BacktestMomentumStrategy
from core.strategy.momentum import MomentumStrategy as TradingMomentumStrategy
from core.config.settings import LOG_LEVEL, LOG_FORMAT
from core.utils.log_utils import setup_logging

# 로깅 설정
setup_logging('trading.log', LOG_LEVEL, add_sensitive_filter=True)
logger = logging.getLogger(__name__)

def reset_daily_counts(trader: AutoTrader):
    """일일 거래 횟수 초기화"""
    trader.reset_daily_counts()
    logger.info("일일 거래 횟수가 초기화되었습니다.")

async def main():
    parser = argparse.ArgumentParser(description='한투 퀀트 트레이딩 시스템')
    parser.add_argument('command', choices=['trade', 'balance', 'find', 'list-stocks'],
                      help='실행할 명령 (trade: 자동매매, balance: 잔고조회, find: 종목검색, list-stocks: KRX 종목 목록 저장)')
    
    args = parser.parse_args()
    
    logger.info("[main] 프로그램을 시작합니다.")
    
    try:
        if args.command == 'trade':
            await run_trading()
        elif args.command == 'balance':
            check_balance()
        elif args.command == 'find':
            find_stocks()
        elif args.command == 'list-stocks':
            save_krx_stock_list()
            
    except KeyboardInterrupt:
        logger.info("[main] 프로그램을 종료합니다.")
    except Exception as e:
        logger.error(f"[main] 오류 발생: {str(e)}")

def check_balance():
    """계좌 잔고 조회"""
    try:
        api = KISAPI()
        balance = api.get_balance()
        
        print("\n=== 계좌 잔고 현황 ===")
        print(f"예수금: {balance.get('deposit', 0):,}원")
        print(f"총 평가금액: {balance.get('total_eval_amount', 0):,}원")
        print(f"총평가손익: {balance['total_eval_profit_loss']:,}원")
        print(f"순자산: {balance.get('net_worth', 0):,}원")
        
        positions = balance.get('positions', {})
        if positions:
            print("\n=== 보유 종목 현황 ===")
            for code, position in positions.items():
                profit_loss = position['eval_profit_loss']
                print(f"\n종목코드: {code}")
                print(f"보유수량: {position['quantity']:,}주")
                print(f"평균단가: {position['avg_price']:,}원")
                print(f"현재가: {position['current_price']:,}원")
                print(f"평가손익: {profit_loss:,}원")
        else:
            print("\n보유 중인 종목이 없습니다.")
            
    except Exception as e:
        logger.error(f"[check_balance] 잔고 조회 중 오류 발생: {str(e)}")
        print(f"\n잔고 조회에 실패했습니다: {str(e)}")

def find_stocks():
    """조건에 맞는 종목 찾기"""
    try:
        # API 클라이언트 초기화
        api = KISAPI()
        
        # 트레이딩용 전략 클래스 사용
        strategy = TradingMomentumStrategy(api)
        
        # 종목 검색
        stocks = strategy.find_candidates()
        
        print("\n=== 조건에 맞는 종목 목록 ===")
        if stocks:
            for stock in stocks:
                print(f"종목코드: {stock['code']}")
                print(f"종목명: {stock['name']}")
                print(f"현재가: {stock['price']:,}원")  # current_price 대신 price 사용
                print(f"거래량: {stock['volume']:,}")
                print(f"모멘텀 점수: {stock['momentum_score']:.1f}")  # 모멘텀 점수 추가
                print("---")
        else:
            print("조건에 맞는 종목이 없습니다.")
    except Exception as e:
        logger.error(f"[find_stocks] 종목 검색 실패: {str(e)}")
        print(f"\n종목 검색에 실패했습니다: {str(e)}")

def save_krx_stock_list():
    """KRX 주식 목록 저장"""
    try:
        client = KRXClient()
        client.save_stock_list()
        logger.info("[save_krx_stock_list] KRX 주식 목록 저장 완료")
    except Exception as e:
        logger.error(f"[save_krx_stock_list] KRX 주식 목록 저장 실패: {str(e)}")
        raise

async def run_trading():
    """자동 매매 실행"""
    try:
        logger.info("[run_trading] 자동 매매를 시작합니다.")
        # API 클라이언트 초기화
        api = KISAPI()
        
        # 전략 설정 - 트레이딩용 전략 사용
        strategy = TradingMomentumStrategy(api)
        
        # 트레이더 초기화
        trader = AutoTrader(api, strategy)
        
        # 거래 대상 종목 설정
        target_codes = [
            "005930",  # 삼성전자
            "000660",  # SK하이닉스
            "035720",  # 카카오
            "035420",  # NAVER
            "051910",  # LG화학
        ]
        
        # 일일 초기화 작업 예약 (매일 09:00)
        schedule.every().day.at("09:00").do(reset_daily_counts, trader)
        
        # 자동 매매 시작
        start_result = await trader.start(target_codes)
        if not start_result:
            logger.error("[run_trading] 자동 매매 시작 실패")
            return
            
        logger.info("[run_trading] 자동 매매가 성공적으로 시작되었습니다.")
        
        # 스케줄러 실행
        while True:
            schedule.run_pending()
            await asyncio.sleep(1)
            
    except Exception as e:
        logger.error(f"[run_trading] 자동 매매 실행 실패: {str(e)}")
    finally:
        # 트레이더가 실행 중이면 종료
        if 'trader' in locals() and trader:
            try:
                await trader.stop()
                logger.info("[run_trading] 트레이더가 정상적으로 종료되었습니다.")
            except Exception as e:
                logger.error(f"[run_trading] 트레이더 종료 중 오류: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())

