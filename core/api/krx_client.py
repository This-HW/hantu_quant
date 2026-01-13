import logging
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from pykrx.website.krx.market.core import (
    상장종목검색, 상폐종목검색, 전체지수기본정보
)
from pykrx import stock

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
            logger.error(f"[save_stock_list] 주식 목록 저장 중 오류 발생: {str(e)}", exc_info=True)
            logger.error(f"[save_stock_list] 상세 에러: {e.__class__.__name__}", exc_info=True)
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
            logger.error(f"[get_stock_list] 종목 목록 조회 중 오류 발생: {str(e)}", exc_info=True)
            logger.error(f"[get_stock_list] 상세 에러: {e.__class__.__name__}", exc_info=True)
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
            logger.error(f"[get_stock_info] 종목 정보 조회 중 오류 발생: {str(e)}", exc_info=True)
            logger.error(f"[get_stock_info] 상세 에러: {e.__class__.__name__}", exc_info=True)
            raise

    def get_market_fundamentals(
        self,
        date: Optional[str] = None,
        market: str = "ALL"
    ) -> pd.DataFrame:
        """전체 종목 재무 데이터 조회 (PER, PBR, EPS, BPS, DIV, ROE)

        Args:
            date: 조회 일자 (YYYYMMDD 형식, 기본값: 오늘)
            market: "ALL"(전체), "KOSPI", "KOSDAQ"

        Returns:
            DataFrame: 재무 데이터
                - ticker: 종목코드
                - BPS: 주당순자산
                - PER: 주가수익비율
                - PBR: 주가순자산비율
                - EPS: 주당순이익
                - DIV: 배당수익률
                - DPS: 주당배당금
                - ROE: 자기자본이익률 (계산값: EPS/BPS*100)
        """
        try:
            if date is None:
                date = datetime.now().strftime('%Y%m%d')

            # pykrx market 파라미터 변환
            market_param = market
            if market == "ALL":
                market_param = "ALL"
            elif market == "KOSPI":
                market_param = "KOSPI"
            elif market == "KOSDAQ":
                market_param = "KOSDAQ"

            # pykrx에서 재무 데이터 조회
            df = stock.get_market_fundamental(date, market=market_param)

            if df.empty:
                # 주말/휴일인 경우 이전 영업일 시도
                for i in range(1, 8):
                    prev_date = (datetime.strptime(date, '%Y%m%d') - timedelta(days=i)).strftime('%Y%m%d')
                    df = stock.get_market_fundamental(prev_date, market=market_param)
                    if not df.empty:
                        logger.info(f"[get_market_fundamentals] {date} 데이터 없음, {prev_date} 사용")
                        break

            if df.empty:
                logger.warning(f"[get_market_fundamentals] 재무 데이터 조회 실패: {date}")
                return pd.DataFrame()

            # 인덱스(종목코드)를 컬럼으로 변환
            df = df.reset_index()
            df = df.rename(columns={'티커': 'ticker'})

            # ROE 계산: ROE = EPS / BPS * 100 (BPS가 0이면 0)
            df['ROE'] = df.apply(
                lambda row: (row['EPS'] / row['BPS'] * 100) if row['BPS'] > 0 else 0.0,
                axis=1
            )

            logger.info(f"[get_market_fundamentals] 재무 데이터 조회 성공 - {len(df)}개 종목")
            return df

        except Exception as e:
            logger.error(f"[get_market_fundamentals] 재무 데이터 조회 오류: {e}", exc_info=True)
            return pd.DataFrame()

    def get_stock_fundamental(self, ticker: str, date: Optional[str] = None) -> Optional[Dict]:
        """개별 종목 재무 데이터 조회

        Args:
            ticker: 종목코드 (6자리)
            date: 조회 일자 (YYYYMMDD 형식, 기본값: 오늘)

        Returns:
            dict: 재무 데이터 (PER, PBR, EPS, BPS, DIV, DPS, ROE)
        """
        try:
            df = self.get_market_fundamentals(date=date)

            if df.empty:
                return None

            stock_data = df[df['ticker'] == ticker]

            if stock_data.empty:
                logger.warning(f"[get_stock_fundamental] 종목 {ticker} 데이터 없음")
                return None

            row = stock_data.iloc[0]
            return {
                'ticker': ticker,
                'per': float(row.get('PER', 0)),
                'pbr': float(row.get('PBR', 0)),
                'eps': float(row.get('EPS', 0)),
                'bps': float(row.get('BPS', 0)),
                'div': float(row.get('DIV', 0)),
                'dps': float(row.get('DPS', 0)),
                'roe': float(row.get('ROE', 0)),
            }

        except Exception as e:
            logger.error(f"[get_stock_fundamental] 종목 {ticker} 재무 데이터 조회 오류: {e}", exc_info=True)
            return None

    def save_market_fundamentals(self, date: Optional[str] = None) -> int:
        """전체 종목 재무 데이터를 파일로 저장

        Args:
            date: 조회 일자 (YYYYMMDD 형식, 기본값: 오늘)

        Returns:
            int: 저장된 종목 수
        """
        try:
            if date is None:
                date = datetime.now().strftime('%Y%m%d')

            df = self.get_market_fundamentals(date=date)

            if df.empty:
                logger.warning(f"[save_market_fundamentals] 저장할 데이터 없음")
                return 0

            # 파일 저장
            file_path = self.stock_dir / f'krx_fundamentals_{date}.json'
            df.to_json(file_path, orient='records', force_ascii=False, indent=2)

            logger.info(f"[save_market_fundamentals] 재무 데이터 저장 완료 - 파일: {file_path}, 종목 수: {len(df)}개")
            return len(df)

        except Exception as e:
            logger.error(f"[save_market_fundamentals] 재무 데이터 저장 오류: {e}", exc_info=True)
            return 0

    def load_market_fundamentals(self, date: Optional[str] = None) -> pd.DataFrame:
        """저장된 재무 데이터 파일 로드

        Args:
            date: 조회 일자 (YYYYMMDD 형식, 기본값: 가장 최신 파일)

        Returns:
            DataFrame: 재무 데이터
        """
        try:
            if date:
                file_path = self.stock_dir / f'krx_fundamentals_{date}.json'
                if file_path.exists():
                    return pd.read_json(file_path)
                else:
                    logger.warning(f"[load_market_fundamentals] 파일 없음: {file_path}")
                    return pd.DataFrame()
            else:
                # 가장 최신 파일 찾기
                files = list(self.stock_dir.glob('krx_fundamentals_*.json'))
                if not files:
                    logger.warning("[load_market_fundamentals] 재무 데이터 파일 없음")
                    return pd.DataFrame()

                latest_file = max(files, key=lambda x: x.name)
                df = pd.read_json(latest_file)
                logger.info(f"[load_market_fundamentals] 재무 데이터 로드 성공 - 파일: {latest_file}")
                return df

        except Exception as e:
            logger.error(f"[load_market_fundamentals] 재무 데이터 로드 오류: {e}", exc_info=True)
            return pd.DataFrame()