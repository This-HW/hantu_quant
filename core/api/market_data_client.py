"""시장 데이터 API 클라이언트

PyKRX, Yahoo Finance를 통해 시장 지표 및 섹터 데이터를 조회합니다.

Feature: B3 - 시장 분석 강화
"""

from abc import ABC, abstractmethod
from typing import Optional
from datetime import datetime, timedelta
import time
import pandas as pd

from core.utils.log_utils import get_logger
from core.api.redis_client import cache_with_ttl


class MarketDataClient(ABC):
    """시장 데이터 클라이언트 기본 클래스"""

    def __init__(self):
        self._logger = get_logger(__name__)

    @abstractmethod
    def get_kospi(self) -> float:
        """KOSPI 지수 조회"""
        pass

    @abstractmethod
    def get_kosdaq(self) -> float:
        """KOSDAQ 지수 조회"""
        pass

    def _retry_with_backoff(self, func, max_retries: int = 3):
        """지수 백오프 재시도 로직"""
        for attempt in range(max_retries):
            try:
                return func()
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                wait_time = 2 ** attempt  # 1s, 2s, 4s
                self._logger.warning(f"재시도 {attempt+1}/{max_retries}: {e}", exc_info=True)
                time.sleep(wait_time)


class PyKRXClient(MarketDataClient):
    """PyKRX 기반 시장 데이터 클라이언트"""

    def __init__(self):
        super().__init__()
        try:
            from pykrx import stock
            self._stock = stock
        except ImportError:
            self._logger.error("pykrx 패키지를 설치하세요: pip install pykrx", exc_info=True)
            raise

    @cache_with_ttl(ttl=300, key_prefix="kospi_index")
    def get_kospi(self) -> float:
        """KOSPI 지수 조회 (5분 캐시)"""
        def _fetch():
            today = datetime.now().strftime("%Y%m%d")
            df = self._stock.get_index_ohlcv(today, today, "KOSPI")
            if df.empty:
                yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
                df = self._stock.get_index_ohlcv(yesterday, yesterday, "KOSPI")
            if df.empty:
                raise ValueError("KOSPI 데이터 없음")
            return float(df.iloc[-1]['종가'])

        try:
            value = self._retry_with_backoff(_fetch)
            self._logger.info(f"KOSPI 조회 성공: {value:.2f}")
            return value
        except Exception as e:
            self._logger.error(f"KOSPI 조회 실패: {e}", exc_info=True)
            return 2500.0  # 기본값 폴백

    @cache_with_ttl(ttl=300, key_prefix="kosdaq_index")
    def get_kosdaq(self) -> float:
        """KOSDAQ 지수 조회 (5분 캐시)"""
        def _fetch():
            today = datetime.now().strftime("%Y%m%d")
            df = self._stock.get_index_ohlcv(today, today, "KOSDAQ")
            if df.empty:
                yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
                df = self._stock.get_index_ohlcv(yesterday, yesterday, "KOSDAQ")
            if df.empty:
                raise ValueError("KOSDAQ 데이터 없음")
            return float(df.iloc[-1]['종가'])

        try:
            value = self._retry_with_backoff(_fetch)
            self._logger.info(f"KOSDAQ 조회 성공: {value:.2f}")
            return value
        except Exception as e:
            self._logger.error(f"KOSDAQ 조회 실패: {e}", exc_info=True)
            return 850.0  # 기본값 폴백

    @cache_with_ttl(ttl=600, key_prefix="sector_etf")
    def get_sector_etf_prices(self, etf_ticker: str, period_days: int = 60) -> Optional[pd.DataFrame]:
        """섹터 ETF 가격 조회 (10분 캐시)

        Args:
            etf_ticker: ETF 종목 코드 (예: "139270")
            period_days: 조회 기간 (일)

        Returns:
            OHLCV 데이터프레임 (없으면 None)
        """
        def _fetch():
            end_date = datetime.now().strftime("%Y%m%d")
            start_date = (datetime.now() - timedelta(days=period_days)).strftime("%Y%m%d")
            df = self._stock.get_etf_ohlcv_by_date(start_date, end_date, etf_ticker)
            if df.empty:
                raise ValueError(f"ETF 데이터 없음: {etf_ticker}")
            return df

        try:
            df = self._retry_with_backoff(_fetch)
            self._logger.debug(f"ETF 조회 성공: {etf_ticker} ({len(df)}일)")
            return df
        except Exception as e:
            self._logger.warning(f"ETF 조회 실패: {etf_ticker}: {e}", exc_info=True)
            return None


class YahooFinanceClient(MarketDataClient):
    """Yahoo Finance 기반 시장 데이터 클라이언트"""

    def __init__(self):
        super().__init__()
        try:
            import yfinance as yf
            self._yf = yf
        except ImportError:
            self._logger.error("yfinance 패키지를 설치하세요: pip install yfinance", exc_info=True)
            raise

    def get_kospi(self) -> float:
        """KOSPI 지수 조회 (폴백용)"""
        try:
            ticker = self._yf.Ticker("^KS11")
            data = ticker.history(period="1d")
            if data.empty:
                raise ValueError("KOSPI 데이터 없음")
            return float(data.iloc[-1]['Close'])
        except Exception as e:
            self._logger.error(f"Yahoo KOSPI 조회 실패: {e}", exc_info=True)
            return 2500.0

    def get_kosdaq(self) -> float:
        """KOSDAQ 지수 조회 (폴백용)"""
        try:
            ticker = self._yf.Ticker("^KQ11")
            data = ticker.history(period="1d")
            if data.empty:
                raise ValueError("KOSDAQ 데이터 없음")
            return float(data.iloc[-1]['Close'])
        except Exception as e:
            self._logger.error(f"Yahoo KOSDAQ 조회 실패: {e}", exc_info=True)
            return 850.0

    @cache_with_ttl(ttl=300, key_prefix="vix_index")
    def get_vix(self) -> float:
        """VIX 지수 조회 (5분 캐시)"""
        def _fetch():
            ticker = self._yf.Ticker("^VIX")
            data = ticker.history(period="1d")
            if data.empty:
                raise ValueError("VIX 데이터 없음")
            return float(data.iloc[-1]['Close'])

        try:
            value = self._retry_with_backoff(_fetch)
            self._logger.info(f"VIX 조회 성공: {value:.2f}")
            return value
        except Exception as e:
            self._logger.error(f"VIX 조회 실패: {e}", exc_info=True)
            return 20.0  # 기본값

    @cache_with_ttl(ttl=300, key_prefix="usd_krw")
    def get_usd_krw(self) -> float:
        """USD/KRW 환율 조회 (5분 캐시)"""
        def _fetch():
            ticker = self._yf.Ticker("KRW=X")
            data = ticker.history(period="1d")
            if data.empty:
                raise ValueError("환율 데이터 없음")
            # yfinance는 USD/KRW (1달러당 원화)를 반환
            krw_per_usd = float(data.iloc[-1]['Close'])
            return krw_per_usd

        try:
            value = self._retry_with_backoff(_fetch)
            self._logger.info(f"USD/KRW 조회 성공: {value:.2f}")
            return value
        except Exception as e:
            self._logger.error(f"USD/KRW 조회 실패: {e}", exc_info=True)
            return 1300.0  # 기본값
