import logging
import pandas as pd
from pathlib import Path
from datetime import datetime
from pykrx.website.krx.market.core import (
    상장종목검색, 상폐종목검색, 전체지수기본정보
)

logger = logging.getLogger(__name__)

class KRXClient:
    """KRX 데이터 조회 클라이언트"""
    
    def __init__(self):
        """초기화"""
        self.stock_dir = Path(__file__).parent.parent.parent / 'data' / 'stock'
        self.stock_dir.mkdir(parents=True, exist_ok=True)
        
    def save_stock_list(self) -> None:
        """전체 주식 티커 정보를 파일로 저장"""
        try:
            # 상장 종목 검색
            df = 상장종목검색().fetch(mktsel="ALL")  # ALL: 전체, STK: 코스피, KSQ: 코스닥
            
            # 필요한 컬럼만 선택하고 이름 변경
            df = df[['short_code', 'codeName', 'full_code', 'marketName']]
            df.columns = ['ticker', 'name', 'isin', 'market']
            
            # 시장 이름 변경 (유가증권 -> KOSPI)
            df['market'] = df['market'].replace("유가증권", "KOSPI")
            
            # 현재 날짜로 파일명 생성
            today = datetime.now().strftime('%Y%m%d')
            file_path = self.stock_dir / f'krx_stock_list_{today}.json'
            
            # JSON 파일로 저장
            df.to_json(file_path, orient='records', force_ascii=False, indent=2)
            
            logger.info(f"[save_stock_list] 주식 목록 저장 완료 - 파일: {file_path}, 종목 수: {len(df)}개")
            
            # 상장 종목 통계 출력
            market_stats = df['market'].value_counts()
            for market, count in market_stats.items():
                logger.info(f"[save_stock_list] {market}: {count}개 종목")
            
        except Exception as e:
            logger.error(f"[save_stock_list] 주식 목록 저장 중 오류 발생: {str(e)}")
            logger.error(f"[save_stock_list] 상세 에러: {e.__class__.__name__}")
            raise
            
    def get_stock_list(self, market: str = "ALL") -> pd.DataFrame:
        """주식 종목 목록 조회
        
        Args:
            market: "ALL"(전체), "STK"(코스피), "KSQ"(코스닥)
            
        Returns:
            DataFrame: 종목 정보가 담긴 데이터프레임
                - ticker: 종목코드
                - name: 종목명
                - isin: ISIN
                - market: 시장구분
        """
        try:
            df = 상장종목검색().fetch(mktsel=market)
            
            # 필요한 컬럼만 선택하고 이름 변경
            df = df[['short_code', 'codeName', 'full_code', 'marketName']]
            df.columns = ['ticker', 'name', 'isin', 'market']
            
            # 시장 이름 변경 (유가증권 -> KOSPI)
            df['market'] = df['market'].replace("유가증권", "KOSPI")
            
            logger.info(f"[get_stock_list] 종목 목록 조회 성공 - {len(df)}개 종목")
            return df
            
        except Exception as e:
            logger.error(f"[get_stock_list] 종목 목록 조회 중 오류 발생: {str(e)}")
            logger.error(f"[get_stock_list] 상세 에러: {e.__class__.__name__}")
            raise
            
    def get_stock_info(self, ticker: str) -> dict:
        """개별 종목 정보 조회
        
        Args:
            ticker: 종목코드 (6자리)
            
        Returns:
            dict: 종목 정보
        """
        try:
            df = self.get_stock_list()
            stock_info = df[df['ticker'] == ticker].iloc[0].to_dict()
            
            logger.info(f"[get_stock_info] 종목 정보 조회 성공 - {stock_info}")
            return stock_info
            
        except Exception as e:
            logger.error(f"[get_stock_info] 종목 정보 조회 중 오류 발생: {str(e)}")
            logger.error(f"[get_stock_info] 상세 에러: {e.__class__.__name__}")
            raise 