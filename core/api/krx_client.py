import logging
import pandas as pd
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, List

# pykrx 임포트 (폴백용, 2025년 12월 KRX 로그인 필수화로 현재 사용 불가)
try:
    from pykrx.website.krx.market.core import (
        상장종목검색, 상폐종목검색, 전체지수기본정보
    )
    from pykrx import stock
    PYKRX_AVAILABLE = True
except ImportError:
    PYKRX_AVAILABLE = False

logger = logging.getLogger(__name__)

# 데이터 소스 우선순위 설정
DEFAULT_DATA_SOURCE = "kis"  # "kis" 또는 "pykrx"


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

    def get_fundamental_from_kis(self, stock_code: str) -> Optional[Dict]:
        """KIS API로 개별 종목 재무 데이터 조회

        Args:
            stock_code: 종목코드 (6자리)

        Returns:
            dict: 재무 데이터 (PER, PBR, EPS, BPS 등)
        """
        try:
            from core.api.kis_api import KISAPI

            kis = KISAPI()
            info = kis.get_stock_info(stock_code)

            if not info:
                logger.debug(f"[get_fundamental_from_kis] {stock_code} 조회 실패")
                return None

            # KIS API 응답에서 재무 데이터 추출
            per = float(info.get('per', 0)) if info.get('per') else 0.0
            pbr = float(info.get('pbr', 0)) if info.get('pbr') else 0.0
            eps = float(info.get('eps', 0)) if info.get('eps') else 0.0
            bps = float(info.get('bps', 0)) if info.get('bps') else 0.0

            # ROE 계산: ROE = EPS / BPS * 100
            roe = (eps / bps * 100) if bps > 0 else 0.0

            return {
                'ticker': stock_code,
                'per': per,
                'pbr': pbr,
                'eps': eps,
                'bps': bps,
                'div': 0.0,  # KIS API에서 미제공
                'dps': 0.0,  # KIS API에서 미제공
                'roe': roe,
            }

        except Exception as e:
            logger.warning(f"[get_fundamental_from_kis] {stock_code} 조회 오류: {e}")
            return None

    def collect_fundamentals_via_kis(
        self,
        stock_codes: Optional[List[str]] = None,
        batch_size: int = 50,
        delay_between_batches: float = 1.0
    ) -> pd.DataFrame:
        """KIS API로 전체 종목 재무 데이터 배치 수집

        Args:
            stock_codes: 종목코드 리스트 (None이면 전체 종목)
            batch_size: 배치당 처리 종목 수
            delay_between_batches: 배치 간 대기 시간 (초)

        Returns:
            DataFrame: 재무 데이터
        """
        try:
            # 종목 리스트 준비
            if stock_codes is None:
                stock_list_files = list(self.stock_dir.glob('krx_stock_list_*.json'))
                if stock_list_files:
                    latest_file = max(stock_list_files, key=lambda x: x.name)
                    stock_list = pd.read_json(latest_file)
                    stock_codes = stock_list['ticker'].tolist()
                else:
                    logger.error("[collect_fundamentals_via_kis] 종목 리스트 파일 없음")
                    return pd.DataFrame()

            logger.info(f"[collect_fundamentals_via_kis] KIS API로 {len(stock_codes)}개 종목 수집 시작")

            results = []
            failed_count = 0
            total = len(stock_codes)

            for i in range(0, total, batch_size):
                batch = stock_codes[i:i + batch_size]
                batch_num = i // batch_size + 1
                total_batches = (total + batch_size - 1) // batch_size

                logger.info(f"[collect_fundamentals_via_kis] 배치 {batch_num}/{total_batches} 처리 중...")

                for code in batch:
                    data = self.get_fundamental_from_kis(code)
                    if data:
                        results.append(data)
                    else:
                        failed_count += 1

                # 배치 간 대기 (Rate Limit 방지)
                if i + batch_size < total:
                    time.sleep(delay_between_batches)

            logger.info(
                f"[collect_fundamentals_via_kis] 수집 완료 - "
                f"성공: {len(results)}, 실패: {failed_count}"
            )

            if results:
                return pd.DataFrame(results)
            return pd.DataFrame()

        except Exception as e:
            logger.error(f"[collect_fundamentals_via_kis] 배치 수집 오류: {e}", exc_info=True)
            return pd.DataFrame()

    def _get_valid_trading_date(self, target_date: str, max_days_back: int = 14) -> Optional[str]:
        """유효한 거래일 찾기 (주말/휴일 고려)

        Args:
            target_date: 시작 날짜 (YYYYMMDD)
            max_days_back: 최대 몇 일 전까지 시도할지

        Returns:
            유효한 거래일 (YYYYMMDD) 또는 None
        """
        try:
            # 종목 목록으로 거래일 확인 (데이터가 있으면 거래일)
            for i in range(max_days_back):
                check_date = (datetime.strptime(target_date, '%Y%m%d') - timedelta(days=i)).strftime('%Y%m%d')
                try:
                    tickers = stock.get_market_ticker_list(check_date, market='KOSPI')
                    if tickers and len(tickers) > 0:
                        logger.debug(f"[_get_valid_trading_date] 유효한 거래일 발견: {check_date}")
                        return check_date
                except Exception:
                    continue
            return None
        except Exception as e:
            logger.warning(f"[_get_valid_trading_date] 거래일 확인 오류: {e}")
            return None

    def get_market_fundamentals(
        self,
        date: Optional[str] = None,
        market: str = "ALL",
        source: Optional[str] = None
    ) -> pd.DataFrame:
        """전체 종목 재무 데이터 조회 (PER, PBR, EPS, BPS, DIV, ROE)

        Args:
            date: 조회 일자 (YYYYMMDD 형식, 기본값: 최근 거래일)
            market: "ALL"(전체), "KOSPI", "KOSDAQ"
            source: 데이터 소스 ("kis" 또는 "pykrx", 기본값: DEFAULT_DATA_SOURCE)

        Returns:
            DataFrame: 재무 데이터
        """
        if source is None:
            source = DEFAULT_DATA_SOURCE

        # 1. KIS API 시도 (기본)
        if source == "kis":
            logger.info("[get_market_fundamentals] KIS API로 재무 데이터 수집 시도")
            df = self.collect_fundamentals_via_kis()
            if not df.empty:
                # 컬럼명 통일 (대문자)
                df = df.rename(columns={
                    'per': 'PER', 'pbr': 'PBR', 'eps': 'EPS',
                    'bps': 'BPS', 'div': 'DIV', 'dps': 'DPS', 'roe': 'ROE'
                })
                logger.info(f"[get_market_fundamentals] KIS API 성공 - {len(df)}개 종목")
                return df
            else:
                logger.warning("[get_market_fundamentals] KIS API 실패, pykrx로 폴백")

        # 2. pykrx 시도 (폴백)
        if not PYKRX_AVAILABLE:
            logger.warning("[get_market_fundamentals] pykrx 사용 불가")
            return pd.DataFrame()

        return self._get_market_fundamentals_pykrx(date, market)

    def _get_market_fundamentals_pykrx(
        self,
        date: Optional[str] = None,
        market: str = "ALL"
    ) -> pd.DataFrame:
        """pykrx로 재무 데이터 조회 (폴백용)

        Args:
            date: 조회 일자 (YYYYMMDD 형식)
            market: 시장 구분

        Returns:
            DataFrame: 재무 데이터
        """
        try:
            # 날짜 설정 (시스템 날짜가 미래일 수 있으므로 실제 거래일 찾기)
            if date is None:
                date = datetime.now().strftime('%Y%m%d')

            # 유효한 거래일 찾기
            valid_date = self._get_valid_trading_date(date)
            if valid_date:
                date = valid_date
                logger.info(f"[_get_market_fundamentals_pykrx] 유효한 거래일 사용: {date}")

            # pykrx에서 재무 데이터 조회 (에러 발생 시 이전 날짜로 재시도)
            df = pd.DataFrame()
            last_error = None

            for i in range(14):  # 최대 2주 전까지 시도
                try_date = (datetime.strptime(date, '%Y%m%d') - timedelta(days=i)).strftime('%Y%m%d')
                try:
                    df = stock.get_market_fundamental(try_date, market=market)
                    if not df.empty and len(df.columns) > 0:
                        if i > 0:
                            logger.info(f"[_get_market_fundamentals_pykrx] {date} 실패, {try_date} 사용")
                        break
                except Exception as e:
                    last_error = e
                    logger.debug(f"[_get_market_fundamentals_pykrx] {try_date} 조회 실패: {e}")
                    continue

            if df.empty:
                if last_error:
                    logger.warning(f"[_get_market_fundamentals_pykrx] 재무 데이터 조회 실패: {last_error}")
                else:
                    logger.warning(f"[_get_market_fundamentals_pykrx] 재무 데이터 조회 실패: 데이터 없음")
                return pd.DataFrame()

            # 인덱스(종목코드)를 컬럼으로 변환
            df = df.reset_index()
            if '티커' in df.columns:
                df = df.rename(columns={'티커': 'ticker'})
            elif 'index' in df.columns:
                df = df.rename(columns={'index': 'ticker'})

            # ROE 계산: ROE = EPS / BPS * 100 (BPS가 0이면 0)
            if 'EPS' in df.columns and 'BPS' in df.columns:
                df['ROE'] = df.apply(
                    lambda row: (row['EPS'] / row['BPS'] * 100) if row['BPS'] > 0 else 0.0,
                    axis=1
                )
            else:
                df['ROE'] = 0.0

            logger.info(f"[_get_market_fundamentals_pykrx] 재무 데이터 조회 성공 - {len(df)}개 종목")
            return df

        except Exception as e:
            logger.error(f"[_get_market_fundamentals_pykrx] 재무 데이터 조회 오류: {e}", exc_info=True)
            return pd.DataFrame()

    def get_stock_fundamental(self, ticker: str, date: Optional[str] = None) -> Optional[Dict]:
        """개별 종목 재무 데이터 조회 (KIS API 우선)

        Args:
            ticker: 종목코드 (6자리)
            date: 조회 일자 (YYYYMMDD 형식, 기본값: 오늘)

        Returns:
            dict: 재무 데이터 (PER, PBR, EPS, BPS, DIV, DPS, ROE)
        """
        try:
            # 1. KIS API로 개별 종목 조회 시도 (빠름)
            if DEFAULT_DATA_SOURCE == "kis":
                kis_data = self.get_fundamental_from_kis(ticker)
                if kis_data:
                    logger.debug(f"[get_stock_fundamental] KIS API로 {ticker} 조회 성공")
                    return kis_data

            # 2. pykrx 폴백 (전체 데이터에서 필터링)
            if PYKRX_AVAILABLE:
                df = self._get_market_fundamentals_pykrx(date=date)

                if df.empty:
                    return None

                stock_data = df[df['ticker'] == ticker]

                if stock_data.empty:
                    logger.warning(f"[get_stock_fundamental] 종목 {ticker} 데이터 없음")
                    return None

                row = stock_data.iloc[0]
                return {
                    'ticker': ticker,
                    'per': float(row.get('PER', 0)) if pd.notna(row.get('PER')) else 0.0,
                    'pbr': float(row.get('PBR', 0)) if pd.notna(row.get('PBR')) else 0.0,
                    'eps': float(row.get('EPS', 0)) if pd.notna(row.get('EPS')) else 0.0,
                    'bps': float(row.get('BPS', 0)) if pd.notna(row.get('BPS')) else 0.0,
                    'div': float(row.get('DIV', 0)) if pd.notna(row.get('DIV')) else 0.0,
                    'dps': float(row.get('DPS', 0)) if pd.notna(row.get('DPS')) else 0.0,
                    'roe': float(row.get('ROE', 0)) if pd.notna(row.get('ROE')) else 0.0,
                }

            return None

        except Exception as e:
            logger.error(f"[get_stock_fundamental] 종목 {ticker} 재무 데이터 조회 오류: {e}", exc_info=True)
            return None

    def save_market_fundamentals_to_db(self, date: Optional[str] = None) -> int:
        """전체 종목 재무 데이터를 DB에 저장

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
                logger.warning(f"[save_market_fundamentals_to_db] 저장할 데이터 없음")
                return 0

            # DB 저장
            from core.database.unified_db import get_session
            from core.database.models import StockFundamental

            saved_count = 0
            data_date = datetime.strptime(date, '%Y%m%d').date()

            with get_session() as session:
                for _, row in df.iterrows():
                    stock_code = str(row.get('ticker', ''))
                    if not stock_code:
                        continue

                    # 기존 데이터 확인 (upsert)
                    existing = session.query(StockFundamental).filter_by(
                        stock_code=stock_code,
                        date=data_date
                    ).first()

                    if existing:
                        # 업데이트
                        existing.per = float(row.get('PER', 0)) if pd.notna(row.get('PER')) else None
                        existing.pbr = float(row.get('PBR', 0)) if pd.notna(row.get('PBR')) else None
                        existing.eps = float(row.get('EPS', 0)) if pd.notna(row.get('EPS')) else None
                        existing.bps = float(row.get('BPS', 0)) if pd.notna(row.get('BPS')) else None
                        existing.div = float(row.get('DIV', 0)) if pd.notna(row.get('DIV')) else None
                        existing.dps = float(row.get('DPS', 0)) if pd.notna(row.get('DPS')) else None
                        existing.roe = float(row.get('ROE', 0)) if pd.notna(row.get('ROE')) else None
                        existing.updated_at = datetime.now()
                    else:
                        # 신규 생성
                        fundamental = StockFundamental(
                            stock_code=stock_code,
                            date=data_date,
                            per=float(row.get('PER', 0)) if pd.notna(row.get('PER')) else None,
                            pbr=float(row.get('PBR', 0)) if pd.notna(row.get('PBR')) else None,
                            eps=float(row.get('EPS', 0)) if pd.notna(row.get('EPS')) else None,
                            bps=float(row.get('BPS', 0)) if pd.notna(row.get('BPS')) else None,
                            div=float(row.get('DIV', 0)) if pd.notna(row.get('DIV')) else None,
                            dps=float(row.get('DPS', 0)) if pd.notna(row.get('DPS')) else None,
                            roe=float(row.get('ROE', 0)) if pd.notna(row.get('ROE')) else None,
                        )
                        session.add(fundamental)

                    saved_count += 1

                session.commit()

            logger.info(f"[save_market_fundamentals_to_db] DB 저장 완료 - {saved_count}개 종목")
            return saved_count

        except Exception as e:
            logger.error(f"[save_market_fundamentals_to_db] DB 저장 오류: {e}", exc_info=True)
            return 0

    def load_fundamentals_from_db(self, stock_code: str, date: Optional[str] = None) -> Optional[Dict]:
        """DB에서 종목 재무 데이터 로드

        Args:
            stock_code: 종목코드
            date: 조회 일자 (YYYYMMDD 형식, 기본값: 가장 최신)

        Returns:
            dict: 재무 데이터
        """
        try:
            from core.database.unified_db import get_session
            from core.database.models import StockFundamental
            from sqlalchemy import desc

            with get_session() as session:
                query = session.query(StockFundamental).filter_by(stock_code=stock_code)

                if date:
                    data_date = datetime.strptime(date, '%Y%m%d').date()
                    query = query.filter_by(date=data_date)
                else:
                    query = query.order_by(desc(StockFundamental.date))

                result = query.first()

                if result:
                    return result.to_dict()
                return None

        except Exception as e:
            logger.error(f"[load_fundamentals_from_db] DB 조회 오류: {e}", exc_info=True)
            return None

    def save_market_fundamentals(self, date: Optional[str] = None) -> int:
        """전체 종목 재무 데이터 저장 (DB + 파일 백업)

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

            # 1. DB 저장 (주요)
            db_count = self.save_market_fundamentals_to_db(date=date)

            # 2. 파일 백업 (보조)
            file_path = self.stock_dir / f'krx_fundamentals_{date}.json'
            df.to_json(file_path, orient='records', force_ascii=False, indent=2)

            logger.info(f"[save_market_fundamentals] 저장 완료 - DB: {db_count}개, 파일: {file_path}")
            return db_count

        except Exception as e:
            logger.error(f"[save_market_fundamentals] 재무 데이터 저장 오류: {e}", exc_info=True)
            return 0

    def load_market_fundamentals(self, date: Optional[str] = None) -> pd.DataFrame:
        """저장된 재무 데이터 로드 (DB 우선, 파일 폴백)

        Args:
            date: 조회 일자 (YYYYMMDD 형식, 기본값: 가장 최신)

        Returns:
            DataFrame: 재무 데이터
        """
        try:
            # 1. DB에서 먼저 로드 시도
            from core.database.unified_db import get_session
            from core.database.models import StockFundamental
            from sqlalchemy import desc

            with get_session() as session:
                if date:
                    data_date = datetime.strptime(date, '%Y%m%d').date()
                    results = session.query(StockFundamental).filter_by(date=data_date).all()
                else:
                    # 가장 최신 날짜 조회
                    latest = session.query(StockFundamental.date).order_by(
                        desc(StockFundamental.date)
                    ).first()
                    if latest:
                        results = session.query(StockFundamental).filter_by(date=latest[0]).all()
                    else:
                        results = []

                if results:
                    data = [r.to_dict() for r in results]
                    df = pd.DataFrame(data)
                    df = df.rename(columns={'stock_code': 'ticker'})
                    logger.info(f"[load_market_fundamentals] DB에서 로드 성공 - {len(df)}개 종목")
                    return df

            # 2. DB에 없으면 파일에서 로드
            logger.debug("[load_market_fundamentals] DB에 데이터 없음, 파일에서 로드 시도")

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
                logger.info(f"[load_market_fundamentals] 파일에서 로드 성공 - {latest_file}")
                return df

        except Exception as e:
            logger.error(f"[load_market_fundamentals] 재무 데이터 로드 오류: {e}", exc_info=True)
            return pd.DataFrame()
