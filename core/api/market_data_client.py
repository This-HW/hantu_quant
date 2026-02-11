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

            # pykrx 내부 로깅 에러 억제 (2026년 KRX 구조 변경으로 인한 로깅 버그)
            import logging
            logging.getLogger('pykrx').setLevel(logging.CRITICAL)
        except ImportError:
            self._logger.error("pykrx 패키지를 설치하세요: pip install pykrx", exc_info=True)
            raise

    @cache_with_ttl(ttl=300, key_prefix="kospi_index")
    def get_kospi(self) -> float:
        """KOSPI 지수 조회 (5분 캐시)"""
        try:
            today = datetime.now().strftime("%Y%m%d")
            df = None
            try:
                df = self._stock.get_index_ohlcv(today, today, "1001")  # KOSPI (PyKRX 1.2.3+ 티커 코드)
            except KeyError as ke:
                # PyKRX 내부 KeyError (예: '지수명') 즉시 폴백
                error_msg = repr(ke)  # KeyError 메시지를 안전하게 repr()로 변환
                self._logger.warning(f"KOSPI 오늘 조회 실패 (PyKRX 내부 에러): {error_msg}", exc_info=False)

            if df is None or (isinstance(df, pd.DataFrame) and df.empty):
                yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
                try:
                    df = self._stock.get_index_ohlcv(yesterday, yesterday, "1001")  # KOSPI
                except KeyError as ke:
                    # 어제 조회도 실패하면 에러 발생
                    error_msg = repr(ke)  # KeyError 메시지를 안전하게 repr()로 변환
                    self._logger.warning(f"KOSPI 어제 조회도 실패 (PyKRX 불안정): {error_msg}", exc_info=False)
                    raise ValueError(f"KOSPI 조회 실패: {error_msg}") from ke

            if df is None or (isinstance(df, pd.DataFrame) and df.empty):
                raise ValueError("KOSPI 데이터 없음")

            # DataFrame 검증
            if not isinstance(df, pd.DataFrame):
                raise ValueError(f"예상치 못한 데이터 타입: {type(df)}")

            # 컬럼명 폴백 로직
            for col in ['종가', 'Close', 'close', 'CLOSE']:
                if col in df.columns:
                    value = float(df.iloc[-1][col])
                    self._logger.info(f"KOSPI 조회 성공: {value:.2f}")
                    return value
            raise ValueError(f"종가 컬럼을 찾을 수 없습니다. 사용 가능한 컬럼: {df.columns.tolist()}")
        except (ValueError, AttributeError) as e:
            # 이미 위에서 KeyError는 처리했으므로 여기서는 ValueError/AttributeError만
            error_msg = repr(e)  # 에러 메시지를 안전하게 repr()로 변환
            self._logger.warning(f"KOSPI 조회 실패: {error_msg}", exc_info=False)
            raise ValueError(f"KOSPI 조회 실패: {error_msg}") from e
        except Exception as e:
            error_type = type(e).__name__
            self._logger.warning(f"KOSPI 조회 실패 (예상치 못한 에러): {error_type}", exc_info=False)
            raise ValueError(f"KOSPI 조회 실패: {error_type}") from e

    @cache_with_ttl(ttl=300, key_prefix="kosdaq_index")
    def get_kosdaq(self) -> float:
        """KOSDAQ 지수 조회 (5분 캐시)"""
        try:
            today = datetime.now().strftime("%Y%m%d")
            df = None
            try:
                df = self._stock.get_index_ohlcv(today, today, "2001")  # KOSDAQ (PyKRX 1.2.3+ 티커 코드)
            except KeyError as ke:
                # PyKRX 내부 KeyError (예: '지수명') 즉시 폴백
                error_msg = repr(ke)  # KeyError 메시지를 안전하게 repr()로 변환
                self._logger.warning(f"KOSDAQ 오늘 조회 실패 (PyKRX 내부 에러): {error_msg}", exc_info=False)

            if df is None or (isinstance(df, pd.DataFrame) and df.empty):
                yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
                try:
                    df = self._stock.get_index_ohlcv(yesterday, yesterday, "2001")  # KOSDAQ
                except KeyError as ke:
                    # 어제 조회도 실패하면 에러 발생
                    error_msg = repr(ke)  # KeyError 메시지를 안전하게 repr()로 변환
                    self._logger.warning(f"KOSDAQ 어제 조회도 실패 (PyKRX 불안정): {error_msg}", exc_info=False)
                    raise ValueError(f"KOSDAQ 조회 실패: {error_msg}") from ke

            if df is None or (isinstance(df, pd.DataFrame) and df.empty):
                raise ValueError("KOSDAQ 데이터 없음")

            # DataFrame 검증
            if not isinstance(df, pd.DataFrame):
                raise ValueError(f"예상치 못한 데이터 타입: {type(df)}")

            # 컬럼명 폴백 로직
            for col in ['종가', 'Close', 'close', 'CLOSE']:
                if col in df.columns:
                    value = float(df.iloc[-1][col])
                    self._logger.info(f"KOSDAQ 조회 성공: {value:.2f}")
                    return value
            raise ValueError(f"종가 컬럼을 찾을 수 없습니다. 사용 가능한 컬럼: {df.columns.tolist()}")
        except (ValueError, AttributeError) as e:
            # 이미 위에서 KeyError는 처리했으므로 여기서는 ValueError/AttributeError만
            error_msg = repr(e)  # 에러 메시지를 안전하게 repr()로 변환
            self._logger.warning(f"KOSDAQ 조회 실패: {error_msg}", exc_info=False)
            raise ValueError(f"KOSDAQ 조회 실패: {error_msg}") from e
        except Exception as e:
            error_type = type(e).__name__
            self._logger.warning(f"KOSDAQ 조회 실패 (예상치 못한 에러): {error_type}", exc_info=False)
            raise ValueError(f"KOSDAQ 조회 실패: {error_type}") from e

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
            raise ValueError(f"Yahoo KOSPI 조회 실패: {e}") from e

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
            raise ValueError(f"Yahoo KOSDAQ 조회 실패: {e}") from e

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
            raise ValueError(f"VIX 조회 실패: {e}") from e

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
            raise ValueError(f"USD/KRW 조회 실패: {e}") from e


class MarketDataClientWithFallback:
    """통합 시장 데이터 클라이언트 (폴백 전략 포함)

    폴백 전략: PyKRX → Yahoo → Config 기본값
    """

    # 클래스 변수로 Config 캐싱
    _config_cache = None
    _config_loaded_at = None

    def __init__(self):
        self._logger = get_logger(__name__)
        self._krx_client = None  # Lazy 초기화
        self._yahoo_client = None  # Lazy 초기화
        self._config = self._load_config()

    def _load_config(self) -> dict:
        """Config 로드 (1시간 캐싱)"""
        try:
            from datetime import datetime, timedelta
            import yaml
            from pathlib import Path

            # 캐시 확인 (1시간 이내면 재사용)
            if (MarketDataClientWithFallback._config_cache is not None and
                MarketDataClientWithFallback._config_loaded_at is not None):
                elapsed = datetime.now() - MarketDataClientWithFallback._config_loaded_at
                if elapsed < timedelta(hours=1):
                    return MarketDataClientWithFallback._config_cache

            # Config 파일 로드
            config_path = Path(__file__).parent.parent.parent / "config" / "phase2.yaml"
            if not config_path.exists():
                self._logger.warning(f"Config 파일 없음: {config_path}. 하드코딩 기본값 사용")
                return self._get_default_config()

            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)

            # 캐시 저장
            MarketDataClientWithFallback._config_cache = config
            MarketDataClientWithFallback._config_loaded_at = datetime.now()

            self._logger.info("Phase2 config 로드 완료 (1시간 캐싱)")
            return config

        except Exception as e:
            self._logger.error(f"Config 로드 실패: {e}. 하드코딩 기본값 사용", exc_info=True)
            return self._get_default_config()

    def _get_default_config(self) -> dict:
        """하드코딩 기본 Config (파일 로드 실패 시)"""
        return {
            "api_fallback": {
                "kospi_default": 2500.0,
                "kosdaq_default": 850.0,
                "vix_default": 20.0,
                "usd_krw_default": 1300.0,
                "sector_momentum_neutral": 50.0,
            }
        }

    def _get_krx_client(self) -> Optional[PyKRXClient]:
        """PyKRX 클라이언트 Lazy 초기화"""
        if self._krx_client is None:
            try:
                self._krx_client = PyKRXClient()
                self._logger.debug("PyKRX 클라이언트 초기화 완료")
            except Exception as e:
                self._logger.warning(f"PyKRX 클라이언트 초기화 실패: {e}", exc_info=True)
                return None
        return self._krx_client

    def _get_yahoo_client(self) -> Optional[YahooFinanceClient]:
        """Yahoo Finance 클라이언트 Lazy 초기화"""
        if self._yahoo_client is None:
            try:
                self._yahoo_client = YahooFinanceClient()
                self._logger.debug("Yahoo Finance 클라이언트 초기화 완료")
            except Exception as e:
                self._logger.warning(f"Yahoo Finance 클라이언트 초기화 실패: {e}", exc_info=True)
                return None
        return self._yahoo_client

    def get_kospi(self) -> float:
        """KOSPI 지수 조회 (폴백: PyKRX → Yahoo → Config 기본값)"""
        # 1차: PyKRX
        krx = self._get_krx_client()
        if krx:
            try:
                value = krx.get_kospi()
                if value > 0:
                    self._logger.debug(f"KOSPI 조회 성공 (PyKRX): {value:.2f}")
                    return value
            except Exception as e:
                self._logger.warning(f"PyKRX KOSPI 조회 실패: {e}", exc_info=True)

        # 2차: Yahoo Finance
        yahoo = self._get_yahoo_client()
        if yahoo:
            try:
                value = yahoo.get_kospi()
                if value > 0:
                    self._logger.info("PyKRX 실패, Yahoo로 KOSPI 조회 성공")
                    return value
            except Exception as e:
                self._logger.warning(f"Yahoo KOSPI 조회 실패: {e}", exc_info=True)

        # 3차: Config 기본값
        fallback_value = self._config.get("api_fallback", {}).get("kospi_default", 2500.0)
        self._logger.info(f"모든 API 실패, KOSPI 폴백값 사용: {fallback_value:.2f}")
        return fallback_value

    def get_kosdaq(self) -> float:
        """KOSDAQ 지수 조회 (폴백: PyKRX → Yahoo → Config 기본값)"""
        # 1차: PyKRX
        krx = self._get_krx_client()
        if krx:
            try:
                value = krx.get_kosdaq()
                if value > 0:
                    self._logger.debug(f"KOSDAQ 조회 성공 (PyKRX): {value:.2f}")
                    return value
            except Exception as e:
                self._logger.warning(f"PyKRX KOSDAQ 조회 실패: {e}", exc_info=True)

        # 2차: Yahoo Finance
        yahoo = self._get_yahoo_client()
        if yahoo:
            try:
                value = yahoo.get_kosdaq()
                if value > 0:
                    self._logger.info("PyKRX 실패, Yahoo로 KOSDAQ 조회 성공")
                    return value
            except Exception as e:
                self._logger.warning(f"Yahoo KOSDAQ 조회 실패: {e}", exc_info=True)

        # 3차: Config 기본값
        fallback_value = self._config.get("api_fallback", {}).get("kosdaq_default", 850.0)
        self._logger.info(f"모든 API 실패, KOSDAQ 폴백값 사용: {fallback_value:.2f}")
        return fallback_value

    def get_vix(self) -> float:
        """VIX 지수 조회 (폴백: Yahoo → Config 기본값)"""
        # 1차: Yahoo Finance
        yahoo = self._get_yahoo_client()
        if yahoo:
            try:
                value = yahoo.get_vix()
                if value > 0:
                    self._logger.debug(f"VIX 조회 성공 (Yahoo): {value:.2f}")
                    return value
            except Exception as e:
                self._logger.warning(f"Yahoo VIX 조회 실패: {e}", exc_info=True)

        # 2차: Config 기본값
        fallback_value = self._config.get("api_fallback", {}).get("vix_default", 20.0)
        self._logger.info(f"VIX 폴백값 사용: {fallback_value:.2f}")
        return fallback_value

    def get_usd_krw(self) -> float:
        """USD/KRW 환율 조회 (폴백: Yahoo → Config 기본값)"""
        # 1차: Yahoo Finance
        yahoo = self._get_yahoo_client()
        if yahoo:
            try:
                value = yahoo.get_usd_krw()
                if value > 0:
                    self._logger.debug(f"USD/KRW 조회 성공 (Yahoo): {value:.2f}")
                    return value
            except Exception as e:
                self._logger.warning(f"Yahoo USD/KRW 조회 실패: {e}", exc_info=True)

        # 2차: Config 기본값
        fallback_value = self._config.get("api_fallback", {}).get("usd_krw_default", 1300.0)
        self._logger.info(f"USD/KRW 폴백값 사용: {fallback_value:.2f}")
        return fallback_value

    @cache_with_ttl(ttl=600, key_prefix="kospi_history")
    def get_kospi_history(self, start_date: str, end_date: str) -> list[dict]:
        """KOSPI 지수 히스토리 조회 (10분 캐시)

        Args:
            start_date: 시작 날짜 (YYYYMMDD)
            end_date: 종료 날짜 (YYYYMMDD)

        Returns:
            [{'date': 'YYYY-MM-DD', 'close': float, ...}, ...]
        """
        # 1차: PyKRX
        krx = self._get_krx_client()
        if krx:
            try:
                df = krx._stock.get_index_ohlcv(start_date, end_date, "1001")  # KOSPI
                if not df.empty:
                    # DataFrame을 dict 리스트로 변환
                    result = []
                    for idx, row in df.iterrows():
                        # 날짜 형식 변환
                        date_str = idx.strftime("%Y-%m-%d") if hasattr(idx, 'strftime') else str(idx)

                        # 컬럼명 폴백
                        close_val = None
                        for col in ['종가', 'Close', 'close', 'CLOSE']:
                            if col in df.columns:
                                close_val = float(row[col])
                                break

                        if close_val is not None:
                            result.append({
                                'date': date_str,
                                'close': close_val
                            })

                    if result:
                        self._logger.debug(f"KOSPI 히스토리 조회 성공 (PyKRX): {len(result)}일")
                        return result
            except Exception as e:
                self._logger.warning(f"PyKRX KOSPI 히스토리 조회 실패: {e}", exc_info=True)

        # 2차: Yahoo Finance
        yahoo = self._get_yahoo_client()
        if yahoo:
            try:
                ticker = yahoo._yf.Ticker("^KS11")
                # YYYYMMDD → YYYY-MM-DD 변환
                start_fmt = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}"
                end_fmt = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:]}"
                df = ticker.history(start=start_fmt, end=end_fmt)

                if not df.empty:
                    result = []
                    for idx, row in df.iterrows():
                        date_str = idx.strftime("%Y-%m-%d") if hasattr(idx, 'strftime') else str(idx)
                        result.append({
                            'date': date_str,
                            'close': float(row['Close'])
                        })
                    self._logger.info(f"PyKRX 실패, Yahoo로 KOSPI 히스토리 조회 성공: {len(result)}일")
                    return result
            except Exception as e:
                self._logger.warning(f"Yahoo KOSPI 히스토리 조회 실패: {e}", exc_info=True)

        # 폴백: 빈 리스트
        self._logger.warning("KOSPI 히스토리 조회 실패, 빈 리스트 반환")
        return []
