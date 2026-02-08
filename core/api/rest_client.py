"""
REST API client module.
"""

import os
import time
import logging  # tenacity의 before_sleep_log에서 logging.WARNING 사용
import requests
import fcntl
import tempfile
from typing import Dict, List, Optional
import pandas as pd
from datetime import datetime, timedelta

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
    RetryError
)

from core.config import settings
from core.config.api_config import APIConfig, KISErrorCode, KISEndpoint
from core.api.redis_client import cache_with_ttl, invalidate_function_cache
from core.utils.log_utils import get_logger

logger = get_logger(__name__)

# 글로벌 Rate Limiter (프로세스/스레드 간 공유)
_RATE_LIMIT_LOCK_FILE = os.path.join(tempfile.gettempdir(), "hantu_api_rate_limit.lock")
_RATE_LIMIT_TIME_FILE = os.path.join(tempfile.gettempdir(), "hantu_api_last_request.txt")
_RATE_LIMIT_BACKOFF_FILE = os.path.join(tempfile.gettempdir(), "hantu_api_backoff.txt")

# 적응형 Rate Limit 상수
_DEFAULT_MIN_INTERVAL = 2.0  # 기본 최소 간격 (초) - EGW00201 에러 방지 (초당 0.5건)
_MAX_BACKOFF_MULTIPLIER = 10.0  # 최대 백오프 배수
_BACKOFF_DECAY_RATE = 0.95  # 성공 시 백오프 감소율 (천천히 감소)


def _get_backoff_multiplier() -> float:
    """현재 백오프 배수 읽기"""
    try:
        if os.path.exists(_RATE_LIMIT_BACKOFF_FILE):
            with open(_RATE_LIMIT_BACKOFF_FILE, 'r') as f:
                content = f.read().strip()
                if content:
                    return min(float(content), _MAX_BACKOFF_MULTIPLIER)
    except (ValueError, OSError) as e:
        logger.debug(f"Backoff multiplier 파일 읽기 실패: {e}")
    return 1.0


def _set_backoff_multiplier(multiplier: float) -> None:
    """백오프 배수 설정"""
    try:
        with open(_RATE_LIMIT_BACKOFF_FILE, 'w') as f:
            f.write(str(min(multiplier, _MAX_BACKOFF_MULTIPLIER)))
    except OSError as e:
        logger.debug(f"Backoff multiplier 파일 쓰기 실패: {e}")


def _increase_backoff() -> float:
    """Rate Limit 에러 시 백오프 대폭 증가 (x5)"""
    current = _get_backoff_multiplier()
    new_multiplier = min(current * 5.0, _MAX_BACKOFF_MULTIPLIER)  # x3 → x5로 증가
    _set_backoff_multiplier(new_multiplier)
    logger.warning(f"Rate Limit 감지 - 백오프 배수 증가: {current:.1f}x -> {new_multiplier:.1f}x (다음 요청부터 {_DEFAULT_MIN_INTERVAL * new_multiplier:.2f}초 간격 적용)")
    return new_multiplier


def _decrease_backoff() -> float:
    """성공 시 백오프 점진적 감소"""
    current = _get_backoff_multiplier()
    if current > 1.0:
        new_multiplier = max(current * _BACKOFF_DECAY_RATE, 1.0)
        _set_backoff_multiplier(new_multiplier)
        if new_multiplier < current:
            logger.debug(f"백오프 배수 감소: {current:.2f} -> {new_multiplier:.2f}")
        return new_multiplier
    return 1.0


class RetryableAPIError(Exception):
    """재시도 가능한 API 에러 (5xx, Timeout, ConnectionError)"""
    def __init__(self, message: str, kis_error_code: str = None, wait_seconds: float = None):
        super().__init__(message)
        self.kis_error_code = kis_error_code
        self.wait_seconds = wait_seconds  # 에러별 권장 대기 시간


class NonRetryableAPIError(Exception):
    """재시도 불가능한 API 에러 (4xx, 인증 실패)"""
    pass


def _extract_kis_error_code(response_text: str) -> Optional[str]:
    """응답에서 KIS 에러 코드 추출

    Args:
        response_text: API 응답 텍스트

    Returns:
        str: KIS 에러 코드 (EGW로 시작) 또는 None
    """
    import re
    # EGW로 시작하는 에러 코드 추출 (예: EGW00203, EGW00201)
    match = re.search(r'EGW\d+', response_text)
    return match.group() if match else None


def _get_wait_time_for_kis_error(error_code: str) -> float:
    """KIS 에러 코드에 따른 대기 시간 반환

    Args:
        error_code: KIS 에러 코드

    Returns:
        float: 권장 대기 시간 (초)
    """
    if error_code == KISErrorCode.OPS_ROUTING_ERROR:
        # EGW00203: 서버 과부하/점검 - 긴 대기 필요
        return 15.0
    elif error_code == KISErrorCode.RATE_LIMIT:
        # EGW00201: Rate Limit - 매우 긴 대기 필요 (API 제한 회복 대기)
        return 30.0  # 10초 → 30초로 증가
    elif error_code == KISErrorCode.SERVICE_ERROR:
        # EGW00500: 서비스 오류 - 표준 대기
        return 10.0
    else:
        # 기본 대기 시간
        return 3.0

class KISRestClient:
    """REST API 기본 클라이언트"""
    
    def __init__(self):
        """초기화"""
        self.config = APIConfig()  # 싱글톤 인스턴스
        self.last_request_time = 0
        
    def _request(self, method: str, url: str, headers: Dict = None,
                params: Dict = None, data: Dict = None, timeout: int = None) -> Dict:
        """API 요청 실행 (재시도 로직 포함)

        Args:
            method: HTTP 메서드
            url: 요청 URL
            headers: 요청 헤더
            params: URL 파라미터
            data: 요청 데이터
            timeout: 타임아웃 (초)

        Returns:
            Dict: API 응답

        Note:
            - Timeout, ConnectionError, 5xx 에러: 최대 3회 재시도 (지수 백오프: 2초, 4초, 8초)
            - 4xx 에러, 인증 실패: 재시도 없이 즉시 반환
        """
        try:
            # API 호출 제한 준수
            self._rate_limit()

            # 토큰 유효성 확인 (헤더 생성 전에 보장)
            if not self.config.ensure_valid_token():
                raise NonRetryableAPIError("API 토큰이 유효하지 않습니다")

            # 재시도 로직이 적용된 내부 요청 실행
            return self._request_with_retry(
                method=method,
                url=url,
                headers=headers,
                params=params,
                data=data,
                timeout=timeout or settings.REQUEST_TIMEOUT
            )

        except NonRetryableAPIError as e:
            logger.error(f"API 요청 실패 (재시도 불가): {e}", exc_info=True)
            return {"error": str(e), "retryable": False}
        except RetryError as e:
            logger.error(f"API 요청 실패 (최대 재시도 횟수 초과): {e}", exc_info=True)
            return {"error": f"최대 재시도 횟수 초과: {e}", "retryable": True}
        except Exception as e:
            logger.error(f"API 요청 오류: {e}", exc_info=True)
            return {"error": str(e)}

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=3, max=30),
        retry=retry_if_exception_type((RetryableAPIError, requests.Timeout, requests.ConnectionError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True
    )
    def _request_with_retry(self, method: str, url: str, headers: Dict = None,
                           params: Dict = None, data: Dict = None, timeout: int = 30) -> Dict:
        """재시도 로직이 적용된 API 요청 실행

        Args:
            method: HTTP 메서드
            url: 요청 URL
            headers: 요청 헤더
            params: URL 파라미터
            data: 요청 데이터
            timeout: 타임아웃 (초)

        Returns:
            Dict: API 응답

        Raises:
            RetryableAPIError: 재시도 가능한 에러 (5xx)
            NonRetryableAPIError: 재시도 불가능한 에러 (4xx)
            requests.Timeout: 타임아웃 에러
            requests.ConnectionError: 연결 에러
        """
        response = requests.request(
            method=method,
            url=url,
            headers=headers or {},
            params=params,
            json=data,
            timeout=timeout
        )

        status_code = response.status_code

        # 성공 응답
        if status_code == 200:
            result = response.json()
            # 성공 응답이지만 KIS 에러 코드가 있는 경우 (rt_cd != '0')
            if result.get('rt_cd') == '1':
                kis_error_code = result.get('msg_cd', '')
                if kis_error_code in KISErrorCode.RETRYABLE_ERRORS:
                    # Rate Limit 에러 시 적응형 백오프 증가
                    if kis_error_code == KISErrorCode.RATE_LIMIT:
                        _increase_backoff()
                    wait_time = _get_wait_time_for_kis_error(kis_error_code)
                    logger.warning(
                        f"KIS API 에러 (재시도 예정): {kis_error_code}, {result.get('msg1', '')} - {wait_time}초 대기"
                    )
                    time.sleep(wait_time)  # 에러 코드별 대기 시간 적용
                    raise RetryableAPIError(
                        f"KIS Error {kis_error_code}: {result.get('msg1', '')}",
                        kis_error_code=kis_error_code,
                        wait_seconds=wait_time
                    )
            # 성공 시 백오프 점진적 감소
            _decrease_backoff()
            return result

        # 5xx 서버 에러 → 재시도
        if 500 <= status_code < 600:
            kis_error_code = _extract_kis_error_code(response.text)
            wait_time = _get_wait_time_for_kis_error(kis_error_code) if kis_error_code else 3.0

            if kis_error_code == KISErrorCode.OPS_ROUTING_ERROR:
                logger.warning(
                    f"KIS OPS 라우팅 에러 (EGW00203) - 서버 과부하/점검 중, {wait_time}초 후 재시도"
                )
            elif kis_error_code == KISErrorCode.RATE_LIMIT:
                _increase_backoff()  # Rate Limit 시 적응형 백오프 증가
                logger.warning(
                    f"KIS Rate Limit 에러 (EGW00201) - 호출 제한 초과, {wait_time}초 후 재시도"
                )
            else:
                logger.warning(f"API 서버 에러 (재시도 예정): {status_code}, {response.text}")

            time.sleep(wait_time)  # 에러 코드별 대기 시간 적용
            raise RetryableAPIError(
                f"HTTP {status_code}: {response.text}",
                kis_error_code=kis_error_code,
                wait_seconds=wait_time
            )

        # 4xx 클라이언트 에러 → 재시도 불가
        if 400 <= status_code < 500:
            logger.error(f"API 클라이언트 에러 (재시도 불가): {status_code}, {response.text}", exc_info=True)
            raise NonRetryableAPIError(f"HTTP {status_code}: {response.text}")

        # 기타 에러
        logger.error(f"API 요청 실패: {status_code}, {response.text}", exc_info=True)
        return {"error": f"HTTP {status_code}", "message": response.text}
    
    def _rate_limit(self):
        """API 호출 제한 준수 (글로벌 파일 락 사용 + 적응형 백오프)

        멀티프로세스/스레드 환경에서도 안전하게 rate limit 적용
        Rate Limit 에러 발생 시 자동으로 간격 증가
        """
        # 설정 기반 간격 계산 (KIS API 권장: 초당 3~5건)
        base_interval = max(_DEFAULT_MIN_INTERVAL, 1.0 / max(1, settings.RATE_LIMIT_PER_SEC))

        # 적응형 백오프 적용
        backoff_multiplier = _get_backoff_multiplier()
        min_interval = base_interval * backoff_multiplier

        try:
            # 파일 락을 사용한 글로벌 rate limiting
            with open(_RATE_LIMIT_LOCK_FILE, 'w') as lock_file:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                try:
                    # 마지막 요청 시간 읽기
                    last_request_time = 0.0
                    if os.path.exists(_RATE_LIMIT_TIME_FILE):
                        with open(_RATE_LIMIT_TIME_FILE, 'r') as f:
                            try:
                                last_request_time = float(f.read().strip())
                            except (ValueError, OSError):
                                pass

                    current_time = time.time()
                    time_diff = current_time - last_request_time

                    if time_diff < min_interval:
                        sleep_time = min_interval - time_diff
                        if backoff_multiplier > 1.0:
                            logger.debug(f"적응형 Rate Limit 적용: {sleep_time:.2f}초 대기 (백오프: {backoff_multiplier:.1f}x)")
                        time.sleep(sleep_time)

                    # 현재 시간 저장
                    with open(_RATE_LIMIT_TIME_FILE, 'w') as f:
                        f.write(str(time.time()))

                finally:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

        except Exception as e:
            # 락 실패 시 로컬 rate limit 사용 (fallback)
            logger.warning(f"글로벌 rate limit 실패, 로컬 사용: {e}")
            current_time = time.time()
            time_diff = current_time - self.last_request_time
            if time_diff < min_interval:
                time.sleep(min_interval - time_diff)
            self.last_request_time = time.time()

    # ---- 내부 유틸: TR ID 해더 처리 ----
    def _resolve_tr_id(self, key: str, default_tr_id: str = "") -> str:
        """환경/설정 기반으로 TR ID를 결정
        - 환경변수 KIS_TR_ID_<KEY>가 있으면 우선 사용 (예: KIS_TR_ID_INQUIRE_PRICE)
        - 없으면 기본값 사용
        - [미검증] 서버 환경에 따라 접두어가 달라질 수 있음. 필요 시 ENV 기반 매핑 확장
        """
        env_key = f"KIS_TR_ID_{key.upper()}"
        return os.getenv(env_key, default_tr_id)

    def _headers_with_tr_id(self, default_tr_id: str, key: str) -> Dict:
        headers = self.config.get_headers()
        tr_id = self._resolve_tr_id(key, default_tr_id)
        if tr_id:
            headers['tr_id'] = tr_id
        return headers

    def request_endpoint(
        self,
        endpoint: dict,
        params: Dict = None,
        data: Dict = None,
        order_type: str = None
    ) -> Dict:
        """KISEndpoint 레지스트리 기반 API 호출

        EGW00203 에러 방지를 위해 tr_id와 필수 파라미터를 자동으로 처리합니다.

        Args:
            endpoint: KISEndpoint.INQUIRE_PRICE 등의 엔드포인트 정의
            params: GET 파라미터 (시세 조회 등)
            data: POST 바디 (주문 등)
            order_type: 주문 시 "buy" 또는 "sell"

        Returns:
            Dict: API 응답

        Usage:
            # 현재가 조회
            result = client.request_endpoint(
                KISEndpoint.INQUIRE_PRICE,
                params={"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": "005930"}
            )

            # 잔고 조회
            result = client.request_endpoint(
                KISEndpoint.INQUIRE_BALANCE,
                params={"CANO": "12345678", "ACNT_PRDT_CD": "01", ...}
            )
        """
        try:
            if not self.config.ensure_valid_token():
                raise Exception("API 토큰이 유효하지 않습니다")

            # 엔드포인트 정보 추출
            path = endpoint.get("path", "")
            method = endpoint.get("method", "GET")
            tr_id = KISEndpoint.get_tr_id(endpoint, self.config.server, order_type)

            # 필수 파라미터 검증
            check_params = params if method == "GET" else data
            if check_params and not KISEndpoint.validate_params(endpoint, check_params):
                logger.error(f"[request_endpoint] 필수 파라미터 누락: {endpoint.get('name')}")
                return {"error": "필수 파라미터 누락", "endpoint": endpoint.get("name")}

            # URL 및 헤더 생성
            url = f"{self.config.base_url}{path}"
            headers = self.config.get_headers()
            headers['tr_id'] = tr_id

            # API 호출
            return self._request(method, url, headers=headers, params=params, data=data)

        except Exception as e:
            logger.error(f"[request_endpoint] 오류: {e}", exc_info=True)
            return {"error": str(e)}

    @cache_with_ttl(ttl=300, key_prefix="price")
    def get_current_price(self, stock_code: str) -> Optional[Dict]:
        """현재가 조회

        Args:
            stock_code: 종목코드

        Returns:
            Optional[Dict]: 현재가 정보

        Note:
            캐시 TTL: 300초 (5분)
        """
        try:
            # 토큰 유효성 선확보 (헤더 생성 전)
            if not self.config.ensure_valid_token():
                raise Exception("API 토큰이 유효하지 않습니다")
            url = f"{self.config.base_url}/uapi/domestic-stock/v1/quotations/inquire-price"
            headers = self._headers_with_tr_id(default_tr_id="FHKST01010100", key="inquire_price")
            params = {
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": stock_code
            }
            
            response = self._request("GET", url, headers=headers, params=params)
            
            if "output" in response:
                output = response["output"]
                return {
                    "stock_code": stock_code,
                    "current_price": float(output.get("stck_prpr", 0)),
                    "change_rate": float(output.get("prdy_ctrt", 0)),
                    "volume": int(output.get("acml_vol", 0)),
                    "high": float(output.get("stck_hgpr", 0)),
                    "low": float(output.get("stck_lwpr", 0)),
                    "open": float(output.get("stck_oprc", 0)),
                    # [미검증] 일부 환경에서 시가총액 키가 제공될 수 있음 (KIS 응답 스펙에 의존)
                    # 제공되지 않으면 0으로 반환
                    "market_cap": float(output.get("hts_avls", 0)) if isinstance(output.get("hts_avls", None), (int, float, str)) else 0.0,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                logger.error(f"현재가 조회 실패: {stock_code}", exc_info=True)
                return None
                
        except Exception as e:
            logger.error(f"현재가 조회 오류: {e}", exc_info=True)
            return None
    
    @cache_with_ttl(ttl=600, key_prefix="daily_chart")
    def get_daily_chart(self, stock_code: str, period_days: int = 100) -> Optional[pd.DataFrame]:
        """일봉 데이터 조회

        Args:
            stock_code: 종목코드
            period_days: 조회 기간 (일)

        Returns:
            Optional[pd.DataFrame]: OHLCV 데이터프레임

        Note:
            캐시 TTL: 600초 (10분)
            KIS 표준 API (inquire-daily-itemchartprice) 사용
            휴장일 고려하여 요청 기간을 1.3배로 확장
        """
        try:
            # 날짜 범위 계산 (YYYYMMDD 형식)
            # 휴장일(주말, 공휴일)을 고려하여 요청 기간을 1.3배로 확장
            end_date = datetime.now()
            buffer_days = int(period_days * 1.3)
            start_date = end_date - timedelta(days=buffer_days)

            params = {
                "FID_COND_MRKT_DIV_CODE": "J",  # 시장 구분 코드 (J: 주식, ETF, ETN)
                "FID_INPUT_ISCD": stock_code,
                "FID_INPUT_DATE_1": start_date.strftime("%Y%m%d"),  # 시작일자
                "FID_INPUT_DATE_2": end_date.strftime("%Y%m%d"),     # 종료일자
                "FID_PERIOD_DIV_CODE": "D",  # D:일봉, W:주봉, M:월봉, Y:년봉
                "FID_ORG_ADJ_PRC": "0"  # 0:수정주가(권리락 반영), 1:원주가
            }

            # SSOT 원칙: KISEndpoint 레지스트리 활용
            response = self.request_endpoint(
                KISEndpoint.INQUIRE_DAILY_ITEMCHARTPRICE,
                params=params
            )

            # 표준 API는 output2에 차트 데이터 반환
            if "output2" in response and response["output2"]:
                data = []
                for item in response["output2"]:
                    data.append({
                        "date": datetime.strptime(item["stck_bsop_date"], "%Y%m%d"),
                        "open": float(item["stck_oprc"]),
                        "high": float(item["stck_hgpr"]),
                        "low": float(item["stck_lwpr"]),
                        "close": float(item["stck_clpr"]),
                        "volume": int(item["acml_vol"])
                    })

                df = pd.DataFrame(data)
                df = df.sort_values("date").reset_index(drop=True)
                df.set_index("date", inplace=True)

                # 요청한 기간만큼 데이터 제한
                if len(df) > period_days:
                    df = df.tail(period_days)

                logger.info(f"일봉 데이터 조회 완료: {stock_code}, {len(df)}일 (표준 API)")
                return df
            else:
                logger.error(f"일봉 데이터 조회 실패: {stock_code}", exc_info=True)
                return None

        except Exception as e:
            logger.error(f"일봉 데이터 조회 오류: {e}", exc_info=True)
            return None
    
    @cache_with_ttl(ttl=600, key_prefix="stock_info")
    def get_stock_info(self, stock_code: str) -> Optional[Dict]:
        """종목 정보 조회

        Args:
            stock_code: 종목코드

        Returns:
            Optional[Dict]: 종목 정보

        Note:
            캐시 TTL: 600초 (10분)
        """
        try:
            if not self.config.ensure_valid_token():
                raise Exception("API 토큰이 유효하지 않습니다")
            url = f"{self.config.base_url}/uapi/domestic-stock/v1/quotations/inquire-price"
            headers = self._headers_with_tr_id(default_tr_id="FHKST01010100", key="inquire_price")
            params = {
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": stock_code
            }
            
            response = self._request("GET", url, headers=headers, params=params)
            
            if "output" in response:
                output = response["output"]
                return {
                    "stock_code": stock_code,
                    "stock_name": output.get("hts_kor_isnm", ""),
                    "market_type": output.get("rprs_mrkt_kor_name", ""),
                    "current_price": float(output.get("stck_prpr", 0)),
                    "market_cap": int(output.get("hts_avls", 0)) if output.get("hts_avls") else 0,
                    "per": float(output.get("per", 0)) if output.get("per") else 0,
                    "pbr": float(output.get("pbr", 0)) if output.get("pbr") else 0,
                    "eps": float(output.get("eps", 0)) if output.get("eps") else 0,
                    "bps": float(output.get("bps", 0)) if output.get("bps") else 0
                }
            else:
                logger.error(f"종목 정보 조회 실패: {stock_code}", exc_info=True)
                return None
                
        except Exception as e:
            logger.error(f"종목 정보 조회 오류: {e}", exc_info=True)
            return None
    
    def get_multiple_current_prices(self, stock_codes: List[str]) -> Dict[str, Dict]:
        """여러 종목 현재가 일괄 조회
        
        Args:
            stock_codes: 종목코드 리스트
            
        Returns:
            Dict[str, Dict]: 종목별 현재가 정보
        """
        results = {}
        
        for stock_code in stock_codes:
            price_info = self.get_current_price(stock_code)
            if price_info:
                results[stock_code] = price_info
            
            # API 호출 제한 준수를 위한 대기는 _rate_limit에서 처리됨
        
        logger.info(f"여러 종목 현재가 조회 완료: {len(results)}/{len(stock_codes)}개")
        return results
            
    def _get_hashkey(self, data: Dict) -> Optional[str]:
        """HASH 키 생성

        Args:
            data: 요청 데이터

        Returns:
            str: HASH 키
        """
        try:
            # rate limit 적용 (EGW00203 에러 방지)
            self._rate_limit()

            url = f"{self.config.base_url}/uapi/hashkey"
            headers = {
                "content-type": "application/json",
                "appkey": self.config.app_key,
                "appsecret": self.config.app_secret
            }

            response = requests.post(url, json=data, headers=headers, timeout=settings.REQUEST_TIMEOUT)

            if response.status_code == 200:
                return response.json()['HASH']
            else:
                logger.error(f"[_get_hashkey] HASH 키 생성 실패 - 상태 코드: {response.status_code}", exc_info=True)
                return None

        except Exception as e:
            logger.error(f"[_get_hashkey] HASH 키 생성 중 오류 발생: {str(e)}", exc_info=True)
            return None
            
    def place_order(self, stock_code: str, order_type: str, quantity: int,
                   price: int = 0, order_division: str = "00") -> Dict:
        """주문 실행
        
        Args:
            stock_code: 종목코드 (6자리)
            order_type: 주문유형 ("01": 매도, "02": 매수)
            quantity: 주문수량
            price: 주문가격 (시장가일 경우 0)
            order_division: 주문구분 (00: 지정가, 01: 시장가)
            
        Returns:
            Dict: 주문 결과
        
        주의:
            - KIS 표준 매핑을 엄수합니다.
            - 시장가 주문 시 order_division="01" 및 price=0을 사용합니다.
        """
        try:
            # 실제 투자 보호 가드
            if self.config.server == 'prod' and not settings.TRADING_PROD_ENABLE:
                logger.error("[place_order] 실제투자 모드이지만 TRADING_PROD_ENABLE=false - 주문 차단")
                return {"error": "TRADING_PROD_DISABLED", "message": "Production trading disabled by guard"}

            if not self.config.ensure_valid_token():
                raise Exception("API 토큰이 유효하지 않습니다")

            # API 요청 설정
            url = f"{self.config.base_url}/uapi/domestic-stock/v1/trading/order-cash"
            
            data = {
                "CANO": self.config.account_number,
                "ACNT_PRDT_CD": self.config.account_prod_code,
                "PDNO": stock_code,
                "ORD_DVSN": order_division,
                "ORD_QTY": str(quantity),
                "ORD_UNPR": str(price) if price > 0 else "0",
                "CTAC_TLNO": "",
                "SLL_BUY_DVSN_CD": order_type,  # "01"=매도, "02"=매수
                "ALGO_NO": ""
            }
            
            # HASH 키 생성
            hashkey = self._get_hashkey(data)
            if not hashkey:
                raise Exception("HASH 키 생성 실패")
                
            # 주문 TR ID 설정 - 매수/매도 및 실전/모의에 따라 동적 설정
            if self.config.server == "virtual":  # 모의투자
                tr_id = "VTTC0011U" if order_type == "01" else "VTTC0012U"  # 매도/매수
            else:  # 실전투자
                tr_id = "TTTC0011U" if order_type == "01" else "TTTC0012U"  # 매도/매수
            
            headers = self.config.get_headers()
            headers['tr_id'] = tr_id
            headers['hashkey'] = hashkey
            
            response = self._request("POST", url, headers=headers, data=data)
            
            if response and response.get('rt_cd') == '0':
                logger.info(f"[place_order] 주문 실행 성공 - {response.get('msg1')}")
                return {
                    'success': True,
                    'data': response.get('output'),
                    'message': response.get('msg1', '주문 성공')
                }
            else:
                error_msg = response.get('msg1') if isinstance(response, dict) else str(response)
                error_code = response.get('rt_cd') if isinstance(response, dict) else 'UNKNOWN'
                logger.error(
                    f"[place_order] 주문 실행 실패: {error_msg}",
                    exc_info=True,
                    extra={'error_code': error_code, 'response': response}
                )
                return {
                    'success': False,
                    'error_code': error_code,
                    'message': error_msg,
                    'detail': response
                }
                
        except Exception as e:
            logger.error(f"[place_order] 주문 실행 중 오류 발생: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error_code': 'EXCEPTION',
                'message': str(e),
                'detail': None
            }
            
    def get_balance(self) -> Dict:
        """잔고 조회
        
        Returns:
            Dict: 계좌 잔고 정보
        """
        try:
            if not self.config.ensure_valid_token():
                raise Exception("API 토큰이 유효하지 않습니다")
            url = f"{self.config.base_url}/uapi/domestic-stock/v1/trading/inquire-balance"
            # 환경별 기본 TR ID (모의: VTTC8434R / 실전: TTTC8434R) - 문서 기준
            default_tr = "VTTC8434R" if self.config.server == "virtual" else "TTTC8434R"
            headers = self._headers_with_tr_id(default_tr_id=default_tr, key="inquire_balance")
            
            params = {
                "CANO": self.config.account_number,       # 앞 8자리
                "ACNT_PRDT_CD": self.config.account_prod_code,  # 뒤 2자리(예: 01)
                "AFHR_FLPR_YN": "N",
                "OFL_YN": "N",
                "INQR_DVSN": "02",
                "UNPR_DVSN": "01",
                "FUND_STTL_ICLD_YN": "N",
                "FNCG_AMT_AUTO_RDPT_YN": "N",
                "PRCS_DVSN": "01",
                "CTX_AREA_FK100": "",
                "CTX_AREA_NK100": ""
            }
            
            response = self._request("GET", url, headers=headers, params=params)
            
            if response.get('rt_cd') == '0':
                # 모의투자 응답 구조:
                # - output1: 보유 종목 리스트 (실전계좌와 동일)
                # - output2: 계좌 요약 정보 (배열의 첫 번째 요소)
                output1 = response.get('output1', [])  # 보유 종목
                output2 = response.get('output2', [])  # 계좌 요약

                # 계좌 요약 정보가 output2[0]에 있음
                if not output2 or len(output2) == 0:
                    logger.warning("[get_balance] 계좌 정보가 없습니다")
                    return {
                        'deposit': 0.0,
                        'total_eval_amount': 0.0,
                        'total_eval_profit_loss': 0.0,
                        'total_earning_rate': 0.0,
                        'output2': []
                    }

                account_info = output2[0]

                # 잔고 정보 가공
                # 필드 매핑:
                # - dnca_tot_amt: 예수금총액 (현금)
                # - scts_evlu_amt: 유가증권평가금액 (주식 평가금액)
                # - tot_evlu_amt: 총평가금액 (현금 + 주식)
                # - evlu_pfls_smtl_amt: 평가손익합계금액
                # - asst_icdc_erng_rt: 자산증감수익률
                balance = {
                    'deposit': float(account_info.get('dnca_tot_amt', 0)),  # 예수금 (현금)
                    'stock_eval_amount': float(account_info.get('scts_evlu_amt', 0)),  # 주식 평가금액
                    'total_eval_amount': float(account_info.get('tot_evlu_amt', 0)),  # 총평가금액
                    'total_eval_profit_loss': float(account_info.get('evlu_pfls_smtl_amt', 0)),  # 총평가손익
                    'total_earning_rate': float(account_info.get('asst_icdc_erng_rt', 0)),  # 자산증감수익률
                    'output2': []  # 보유종목 정보 (get_holdings용)
                }

                # 보유종목 정보 추가 (output1에 있음)
                for item in output1:
                    code = item.get('pdno', '')
                    if not code:
                        continue
                    balance['output2'].append(item)

                return balance
                
            else:
                logger.error(f"[get_balance] 잔고 조회 실패: {response.get('msg1')}", exc_info=True)
                return {}
                
        except Exception as e:
            logger.error(f"[get_balance] 잔고 조회 중 오류 발생: {str(e)}", exc_info=True)
            return {}

    def get_stock_list(self, market_type: str = "J") -> List[Dict]:
        """주식 종목 목록 조회

        Args:
            market_type: "J"(전체), "0"(코스피), "1"(코스닥)

        Returns:
            List[Dict]: 종목 목록
            [
                {
                    'code': 종목코드,
                    'name': 종목명,
                    'market': 시장구분,
                    'price': 현재가,
                    'volume': 거래량
                },
                ...
            ]
        """
        try:
            if not self.config.ensure_valid_token():
                raise Exception("토큰 갱신 실패")

            url = f"{self.config.base_url}/uapi/domestic-stock/v1/quotations/inquire-price"
            # 헤더 생성 방식 일관성 유지 (_headers_with_tr_id 사용)
            # tr_id: FHKST01010100 (inquire-price API 공식 tr_id)
            headers = self._headers_with_tr_id(default_tr_id="FHKST01010100", key="inquire_price")
            params = {
                "FID_COND_MRKT_DIV_CODE": market_type,  # J:전체, 0:코스피, 1:코스닥
                "FID_INPUT_ISCD": ""
            }

            logger.debug(f"[get_stock_list] 종목 목록 조회 요청 - URL: {url}")
            logger.debug(f"[get_stock_list] 종목 목록 조회 요청 - 파라미터: {params}")

            # _request() 사용하여 rate limit 적용
            data = self._request("GET", url, headers=headers, params=params)

            if "error" in data:
                logger.error(f"[get_stock_list] API 에러: {data}", exc_info=True)
                raise Exception(f"API 요청 실패: {data.get('error')}")
            logger.debug(f"[get_stock_list] 종목 목록 조회 응답: {data}")
            
            if data.get('rt_cd') == '0':  # 정상 응답
                stock_list = []
                for item in data.get('output', []):
                    stock_list.append({
                        'code': item.get('mksc_shrn_iscd', ''),  # 종목코드
                        'name': item.get('hts_kor_isnm', ''),  # 종목명
                        'market': item.get('bstp_kor_isnm', ''),  # 시장구분
                        'price': int(float(item.get('stck_prpr', 0))),  # 현재가
                        'volume': int(float(item.get('acml_vol', 0)))  # 거래량
                    })
                
                logger.info(f"[get_stock_list] 종목 목록 조회 성공 - {len(stock_list)}개 종목")
                return stock_list
            else:
                error_message = data.get('msg1', '알 수 없는 오류가 발생했습니다')
                logger.error(f"[get_stock_list] 종목 목록 조회 실패: {error_message}", exc_info=True)
                raise Exception(f"종목 목록 조회 실패: {error_message}")
                
        except Exception as e:
            logger.error(f"[get_stock_list] 예상치 못한 오류 발생: {str(e)}", exc_info=True)
            logger.error(f"[get_stock_list] 상세 에러: {e.__class__.__name__}", exc_info=True)
            raise

    # ====== 추가 시세/체결/호가/수급 래퍼 ======
    def get_orderbook(self, stock_code: str) -> Optional[Dict]:
        """호가/예상체결 조회 (inquire-asking-price-exp-ccn)
        TR: FHKST01010200 (모의/실전 동일)
        """
        try:
            if not self.config.ensure_valid_token():
                raise Exception("API 토큰이 유효하지 않습니다")

            url = f"{self.config.base_url}/uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn"
            headers = self._headers_with_tr_id(default_tr_id="FHKST01010200", key="inquire_asking_price_exp_ccn")
            params = {
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": stock_code,
            }
            response = self._request("GET", url, headers=headers, params=params)
            if "output" in response:
                return response["output"]
            logger.error(f"[get_orderbook] 실패: {response}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"[get_orderbook] 오류: {e}", exc_info=True)
            return None

    def get_tick_conclusions(self, stock_code: str, count: int = 100) -> Optional[pd.DataFrame]:
        """주식현재가 체결 조회 (inquire-ccnl)
        TR: FHKST01010300 (모의/실전 동일)
        [미검증] count는 서버 스펙에 따라 제한될 수 있음
        """
        try:
            if not self.config.ensure_valid_token():
                raise Exception("API 토큰이 유효하지 않습니다")

            url = f"{self.config.base_url}/uapi/domestic-stock/v1/quotations/inquire-ccnl"
            headers = self._headers_with_tr_id(default_tr_id="FHKST01010300", key="inquire_ccnl")
            params = {
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": stock_code,
            }
            res = self._request("GET", url, headers=headers, params=params)
            output = res.get("output", []) if isinstance(res, dict) else []
            if not output:
                return None
            df = pd.DataFrame(output)
            return df
        except Exception as e:
            logger.error(f"[get_tick_conclusions] 오류: {e}", exc_info=True)
            return None

    def get_minute_bars(self, stock_code: str, time_unit: int = 1, count: int = 60) -> Optional[pd.DataFrame]:
        """주식당일분봉조회 (inquire-time-itemchartprice)
        TR: FHKST03010200 (모의/실전 동일)

        Args:
            stock_code: 종목코드
            time_unit: 시간 단위 (분) - 현재 미사용, 향후 확장용
            count: 조회 건수 - 현재 미사용, 최대 30건

        Returns:
            분봉 데이터 DataFrame 또는 None
        """
        try:
            if not self.config.ensure_valid_token():
                raise Exception("API 토큰이 유효하지 않습니다")

            url = f"{self.config.base_url}/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice"
            headers = self._headers_with_tr_id(default_tr_id="FHKST03010200", key="inquire_time_itemchartprice")

            # 현재 시간 기준으로 입력 시간 설정 (HHMMSS 형식)
            current_time = datetime.now().strftime("%H%M%S")

            params = {
                "FID_COND_MRKT_DIV_CODE": "J",           # 시장 구분 (J: KRX)
                "FID_INPUT_ISCD": stock_code,            # 종목코드
                "FID_INPUT_HOUR_1": current_time,        # 입력 시간 (필수)
                "FID_PW_DATA_INCU_YN": "Y",              # 과거 데이터 포함 여부 (필수)
            }
            res = self._request("GET", url, headers=headers, params=params)
            output = res.get("output2", []) if isinstance(res, dict) else []
            if not output:
                # output2가 없으면 output 확인
                output = res.get("output", []) if isinstance(res, dict) else []
            if not output:
                return None
            df = pd.DataFrame(output)
            return df
        except Exception as e:
            logger.error(f"[get_minute_bars] 오류: {e}", exc_info=True)
            return None

    def get_investor_flow(self, stock_code: str) -> Optional[Dict]:
        """주식현재가 투자자 (inquire-investor)
        TR: FHKST01010900 (모의/실전 동일)
        """
        try:
            if not self.config.ensure_valid_token():
                raise Exception("API 토큰이 유효하지 않습니다")
            url = f"{self.config.base_url}/uapi/domestic-stock/v1/quotations/inquire-investor"
            headers = self._headers_with_tr_id(default_tr_id="FHKST01010900", key="inquire_investor")
            params = {
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": stock_code,
            }
            res = self._request("GET", url, headers=headers, params=params)
            return res.get("output") if isinstance(res, dict) else None
        except Exception as e:
            logger.error(f"[get_investor_flow] 오류: {e}", exc_info=True)
            return None

    def get_member_flow(self, stock_code: str) -> Optional[Dict]:
        """주식현재가 회원사 (inquire-member)
        TR: FHKST01010600 (모의/실전 동일)
        """
        try:
            if not self.config.ensure_valid_token():
                raise Exception("API 토큰이 유효하지 않습니다")
            url = f"{self.config.base_url}/uapi/domestic-stock/v1/quotations/inquire-member"
            headers = self._headers_with_tr_id(default_tr_id="FHKST01010600", key="inquire_member")
            params = {
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": stock_code,
            }
            res = self._request("GET", url, headers=headers, params=params)
            return res.get("output") if isinstance(res, dict) else None
        except Exception as e:
            logger.error(f"[get_member_flow] 오류: {e}", exc_info=True)
            return None

    # ====== 캐시 관리 메서드 ======
    def clear_price_cache(self, stock_code: Optional[str] = None):
        """가격 캐시 무효화

        Args:
            stock_code: 특정 종목 캐시만 삭제. None이면 전체 가격 캐시 삭제

        Example:
            # 특정 종목 캐시 삭제
            client.clear_price_cache("005930")

            # 전체 가격 캐시 삭제
            client.clear_price_cache()
        """
        if stock_code:
            # 특정 종목 캐시 삭제
            from core.api.redis_client import invalidate_cache
            invalidate_cache(self.get_current_price, stock_code)
            logger.info(f"가격 캐시 무효화: {stock_code}")
        else:
            # 전체 가격 캐시 삭제
            invalidate_function_cache(self.get_current_price)
            logger.info("전체 가격 캐시 무효화")

    def clear_daily_chart_cache(self, stock_code: Optional[str] = None, period_days: Optional[int] = None):
        """일봉 차트 캐시 무효화

        Args:
            stock_code: 특정 종목 캐시만 삭제. None이면 전체 삭제
            period_days: 특정 기간 캐시만 삭제. None이면 해당 종목의 모든 기간 삭제

        Example:
            # 특정 종목+기간 캐시 삭제
            client.clear_daily_chart_cache("005930", 100)

            # 특정 종목의 모든 기간 삭제
            client.clear_daily_chart_cache("005930")

            # 전체 차트 캐시 삭제
            client.clear_daily_chart_cache()
        """
        if stock_code and period_days:
            # 특정 종목+기간 캐시 삭제
            from core.api.redis_client import invalidate_cache
            invalidate_cache(self.get_daily_chart, stock_code, period_days)
            logger.info(f"일봉 차트 캐시 무효화: {stock_code} (period={period_days})")
        else:
            # 전체 또는 종목별 캐시 삭제
            invalidate_function_cache(self.get_daily_chart)
            if stock_code:
                logger.info(f"일봉 차트 캐시 무효화: {stock_code} (모든 기간)")
            else:
                logger.info("전체 일봉 차트 캐시 무효화")

    def clear_stock_info_cache(self, stock_code: Optional[str] = None):
        """종목 정보 캐시 무효화

        Args:
            stock_code: 특정 종목 캐시만 삭제. None이면 전체 삭제

        Example:
            # 특정 종목 캐시 삭제
            client.clear_stock_info_cache("005930")

            # 전체 종목 정보 캐시 삭제
            client.clear_stock_info_cache()
        """
        if stock_code:
            # 특정 종목 캐시 삭제
            from core.api.redis_client import invalidate_cache
            invalidate_cache(self.get_stock_info, stock_code)
            logger.info(f"종목 정보 캐시 무효화: {stock_code}")
        else:
            # 전체 종목 정보 캐시 삭제
            invalidate_function_cache(self.get_stock_info)
            logger.info("전체 종목 정보 캐시 무효화")

    def clear_all_cache(self):
        """모든 REST API 캐시 무효화

        가격, 차트, 종목 정보 캐시를 모두 삭제합니다.

        Example:
            client.clear_all_cache()
        """
        self.clear_price_cache()
        self.clear_daily_chart_cache()
        self.clear_stock_info_cache()
        logger.info("모든 REST API 캐시 무효화 완료")


# 하위 호환성 별칭
RestClient = KISRestClient