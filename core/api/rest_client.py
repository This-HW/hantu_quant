"""
REST API client module.
"""

import logging
import os
import time
import hashlib
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
from core.config.api_config import APIConfig

logger = logging.getLogger(__name__)

# 글로벌 Rate Limiter (프로세스/스레드 간 공유)
_RATE_LIMIT_LOCK_FILE = os.path.join(tempfile.gettempdir(), "hantu_api_rate_limit.lock")
_RATE_LIMIT_TIME_FILE = os.path.join(tempfile.gettempdir(), "hantu_api_last_request.txt")


class RetryableAPIError(Exception):
    """재시도 가능한 API 에러 (5xx, Timeout, ConnectionError)"""
    pass


class NonRetryableAPIError(Exception):
    """재시도 불가능한 API 에러 (4xx, 인증 실패)"""
    pass

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
            return response.json()

        # 5xx 서버 에러 → 재시도
        if 500 <= status_code < 600:
            logger.warning(f"API 서버 에러 (재시도 예정): {status_code}, {response.text}")
            raise RetryableAPIError(f"HTTP {status_code}: {response.text}")

        # 4xx 클라이언트 에러 → 재시도 불가
        if 400 <= status_code < 500:
            logger.error(f"API 클라이언트 에러 (재시도 불가): {status_code}, {response.text}", exc_info=True)
            raise NonRetryableAPIError(f"HTTP {status_code}: {response.text}")

        # 기타 에러
        logger.error(f"API 요청 실패: {status_code}, {response.text}", exc_info=True)
        return {"error": f"HTTP {status_code}", "message": response.text}
    
    def _rate_limit(self):
        """API 호출 제한 준수 (글로벌 파일 락 사용)

        멀티프로세스/스레드 환경에서도 안전하게 rate limit 적용
        """
        # 설정 기반 간격 계산 (KIS API 권장: 초당 3~5건)
        min_interval = max(0.35, 1.0 / max(1, settings.RATE_LIMIT_PER_SEC))

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
    
    def get_current_price(self, stock_code: str) -> Optional[Dict]:
        """현재가 조회
        
        Args:
            stock_code: 종목코드
            
        Returns:
            Optional[Dict]: 현재가 정보
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
    
    def get_daily_chart(self, stock_code: str, period_days: int = 100) -> Optional[pd.DataFrame]:
        """일봉 데이터 조회
        
        Args:
            stock_code: 종목코드
            period_days: 조회 기간 (일)
            
        Returns:
            Optional[pd.DataFrame]: OHLCV 데이터프레임
        """
        try:
            if not self.config.ensure_valid_token():
                raise Exception("API 토큰이 유효하지 않습니다")
            url = f"{self.config.base_url}/uapi/domestic-stock/v1/quotations/inquire-daily-price"
            headers = self._headers_with_tr_id(default_tr_id="FHKST01010400", key="inquire_daily_price")
            
            # 시작일 계산
            end_date = datetime.now()
            start_date = end_date - timedelta(days=period_days + 30)  # 여유분 추가
            
            params = {
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": stock_code,
                "FID_ORG_ADJ_PRC": "1",  # 수정주가
                "FID_PERIOD_DIV_CODE": "D"  # 일봉
            }
            
            response = self._request("GET", url, headers=headers, params=params)
            
            if "output" in response and response["output"]:
                data = []
                for item in response["output"]:
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
                
                logger.info(f"일봉 데이터 조회 완료: {stock_code}, {len(df)}일")
                return df
            else:
                logger.error(f"일봉 데이터 조회 실패: {stock_code}", exc_info=True)
                return None
                
        except Exception as e:
            logger.error(f"일봉 데이터 조회 오류: {e}", exc_info=True)
            return None
    
    def get_stock_info(self, stock_code: str) -> Optional[Dict]:
        """종목 정보 조회
        
        Args:
            stock_code: 종목코드
            
        Returns:
            Optional[Dict]: 종목 정보
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
                return response.get('output')
            else:
                msg = response.get('msg1') if isinstance(response, dict) else str(response)
                logger.error(f"[place_order] 주문 실행 실패: {msg}", exc_info=True)
                return None
                
        except Exception as e:
            logger.error(f"[place_order] 주문 실행 중 오류 발생: {str(e)}", exc_info=True)
            return None
            
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
            headers = {
                "content-type": "application/json; charset=utf-8",
                "authorization": f"Bearer {self.config.access_token}",
                "appkey": self.config.app_key,
                "appsecret": self.config.app_secret,
                "tr_id": "FHKST03010100"  # 주식현재가 시세
            }
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
        [미검증] 파라미터는 KIS 문서에 따라 추가 조정 필요 가능
        """
        try:
            if not self.config.ensure_valid_token():
                raise Exception("API 토큰이 유효하지 않습니다")

            url = f"{self.config.base_url}/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice"
            headers = self._headers_with_tr_id(default_tr_id="FHKST03010200", key="inquire_time_itemchartprice")
            params = {
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": stock_code,
                # [미검증] 실제 스펙의 시간단위/카운트 파라미터는 문서에 맞춰 조정 필요
            }
            res = self._request("GET", url, headers=headers, params=params)
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