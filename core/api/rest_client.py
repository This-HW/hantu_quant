"""
REST API client module.
"""

import logging
import time
import hashlib
import requests
from typing import Dict, List, Optional
import pandas as pd

from core.config import settings
from core.config.api_config import APIConfig

logger = logging.getLogger(__name__)

class KISRestClient:
    """REST API 기본 클라이언트"""
    
    def __init__(self):
        """초기화"""
        self.config = APIConfig()  # 싱글톤 인스턴스
        self.last_request_time = 0
        
    def _request(self, method: str, url: str, headers: Dict = None, 
                params: Dict = None, data: Dict = None, timeout: int = None) -> Dict:
        """API 요청 실행
        
        Args:
            method: HTTP 메서드
            url: 요청 URL
            headers: 요청 헤더
            params: URL 파라미터
            data: 요청 데이터
            timeout: 타임아웃 (초)
            
        Returns:
            Dict: API 응답
        """
        try:
            # API 호출 제한 준수
            self._rate_limit()
            
            # 토큰 유효성 확인
            if not self.config.ensure_valid_token():
                raise Exception("API 토큰이 유효하지 않습니다")
                
            # 요청 실행
            timeout = timeout or settings.REQUEST_TIMEOUT
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=data,
                timeout=timeout
            )
            
            # 응답 검증
            if response.status_code != 200:
                logger.error(f"[_request] HTTP 에러 발생 - 상태 코드: {response.status_code}")
                logger.error(f"[_request] 에러 응답: {response.text}")
                response.raise_for_status()
                
            return response.json()
            
        except Exception as e:
            logger.error(f"[_request] API 요청 중 오류 발생: {str(e)}")
            raise
            
    def _rate_limit(self):
        """API 호출 제한 준수"""
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        
        if elapsed < 1 / settings.RATE_LIMIT_PER_SEC:
            time.sleep(1 / settings.RATE_LIMIT_PER_SEC - elapsed)
            
        self.last_request_time = time.time()
        
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
                logger.error(f"[_get_hashkey] HASH 키 생성 실패 - 상태 코드: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"[_get_hashkey] HASH 키 생성 중 오류 발생: {str(e)}")
            return None
            
    def place_order(self, stock_code: str, order_type: int, quantity: int,
                   price: int = 0, order_division: str = "00") -> Dict:
        """주문 실행
        
        Args:
            stock_code: 종목코드
            order_type: 주문유형 (1: 매도, 2: 매수)
            quantity: 주문수량
            price: 주문가격 (시장가일 경우 0)
            order_division: 주문구분 (00: 지정가, 01: 시장가)
            
        Returns:
            Dict: 주문 결과
        """
        try:
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
                "SLL_BUY_DVSN_CD": str(order_type),
                "ALGO_NO": ""
            }
            
            # HASH 키 생성
            hashkey = self._get_hashkey(data)
            if not hashkey:
                raise Exception("HASH 키 생성 실패")
                
            headers = self.config.get_headers()
            headers['hashkey'] = hashkey
            
            response = self._request("POST", url, headers=headers, data=data)
            
            if response.get('rt_cd') == '0':
                logger.info(f"[place_order] 주문 실행 성공 - {response.get('msg1')}")
                return response.get('output')
            else:
                logger.error(f"[place_order] 주문 실행 실패: {response.get('msg1')}")
                return None
                
        except Exception as e:
            logger.error(f"[place_order] 주문 실행 중 오류 발생: {str(e)}")
            return None
            
    def get_balance(self) -> Dict:
        """잔고 조회
        
        Returns:
            Dict: 계좌 잔고 정보
        """
        try:
            url = f"{self.config.base_url}/uapi/domestic-stock/v1/trading/inquire-balance"
            headers = self.config.get_headers()
            
            params = {
                "CANO": self.config.account_number,
                "ACNT_PRDT_CD": self.config.account_prod_code,
                "AFHR_FLPR_YN": "N",
                "OFL_YN": "",
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
                output = response.get('output')
                if not output:
                    logger.warning("[get_balance] 잔고 정보가 없습니다")
                    return {}
                    
                # 잔고 정보 가공
                balance = {
                    'deposit': float(output[0].get('dnca_tot_amt', 0)),  # 예수금
                    'total_eval_amount': float(output[0].get('tot_evlu_amt', 0)),  # 총평가금액
                    'total_eval_profit_loss': float(output[0].get('evlu_pfls_smtl_amt', 0)),  # 총평가손익
                    'total_earning_rate': float(output[0].get('evlu_pfls_rt', 0)),  # 총수익률
                    'positions': {}  # 보유종목 정보
                }
                
                # 보유종목 정보 추가
                for item in output:
                    code = item.get('pdno')
                    balance['positions'][code] = {
                        'name': item.get('prdt_name', ''),
                        'quantity': int(float(item.get('hldg_qty', 0))),
                        'avg_price': float(item.get('pchs_avg_pric', 0)),
                        'current_price': float(item.get('prpr', 0)),
                        'eval_profit_loss': float(item.get('evlu_pfls_amt', 0)),
                        'earning_rate': float(item.get('evlu_pfls_rt', 0))
                    }
                    
                return balance
                
            else:
                logger.error(f"[get_balance] 잔고 조회 실패: {response.get('msg1')}")
                return {}
                
        except Exception as e:
            logger.error(f"[get_balance] 잔고 조회 중 오류 발생: {str(e)}")
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
            logger.debug(f"[get_stock_list] 종목 목록 조회 요청 - 헤더: {headers}")
            logger.debug(f"[get_stock_list] 종목 목록 조회 요청 - 파라미터: {params}")
            
            response = requests.get(url, headers=headers, params=params, timeout=settings.REQUEST_TIMEOUT)
            
            if response.status_code != 200:
                logger.error(f"[get_stock_list] HTTP 에러 발생 - 상태 코드: {response.status_code}")
                logger.error(f"[get_stock_list] 에러 응답: {response.text}")
                response.raise_for_status()
            
            data = response.json()
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
                logger.error(f"[get_stock_list] 종목 목록 조회 실패: {error_message}")
                raise Exception(f"종목 목록 조회 실패: {error_message}")
                
        except requests.exceptions.RequestException as e:
            logger.error(f"[get_stock_list] 종목 목록 조회 중 오류 발생: {str(e)}")
            raise Exception("API 요청 실패")
        except Exception as e:
            logger.error(f"[get_stock_list] 예상치 못한 오류 발생: {str(e)}")
            logger.error(f"[get_stock_list] 상세 에러: {e.__class__.__name__}")
            raise