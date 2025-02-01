import requests
import logging
import time
import json
import os
from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from core.config.settings import (
    APP_KEY, APP_SECRET, ACCOUNT_NUMBER,
    SERVER, VIRTUAL_URL, PROD_URL,
    REQUEST_TIMEOUT, RATE_LIMIT_PER_SEC, ACCOUNT_PROD_CODE
)

logger = logging.getLogger(__name__)

class KISRestClient:
    """한국투자증권 REST API 클라이언트"""
    
    def __init__(self):
        """초기화"""
        self.domain = PROD_URL if SERVER == "prod" else VIRTUAL_URL
        self.app_key = APP_KEY
        self.app_secret = APP_SECRET
        self.account_number = ACCOUNT_NUMBER
        self.server = SERVER
        self._last_request_time = 0
        
        # 토큰 파일 경로 설정 (프로젝트 루트의 data/token 디렉토리)
        current_dir = Path(__file__).parent.parent.parent  # 프로젝트 루트 디렉토리
        self.token_dir = current_dir / 'data' / 'token'
        self.token_file = self.token_dir / f'token_info_{SERVER}.json'
        
        # 토큰 디렉토리 생성 및 권한 설정
        self.token_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self.token_dir, 0o700)  # 700: 소유자만 읽기/쓰기/실행 가능
        
        # 저장된 토큰 불러오기 시도
        self.token_info = self._load_token()
        
        # 토큰이 없거나 만료되었으면 새로 발급
        if not self.token_info or self._is_token_expired():
            if not self._ensure_valid_token():
                raise Exception("API 인증 실패")
            
        logger.debug(f"[__init__] 초기화 완료 - 서버: {self.server}, 계좌: {self.account_number}, 토큰파일: {self.token_file}")
    
    def _save_token(self) -> None:
        """토큰 정보를 파일로 저장"""
        if self.token_info:
            try:
                # 만료 시간을 문자열로 변환
                token_info = self.token_info.copy()
                token_info['expires_at'] = token_info['expires_at'].strftime('%Y-%m-%d %H:%M:%S')
                
                # 토큰 파일 권한 설정 (600: 소유자만 읽기/쓰기 가능)
                if self.token_file.exists():
                    os.chmod(self.token_file, 0o600)
                
                with open(self.token_file, 'w') as f:
                    json.dump(token_info, f, indent=2)
                
                # 새로 생성된 파일의 권한 설정
                os.chmod(self.token_file, 0o600)
                
                logger.debug(f"[_save_token] 토큰 정보 저장 완료: {self.token_file}")
            except Exception as e:
                logger.error(f"[_save_token] 토큰 정보 저장 실패: {str(e)}")
    
    def _load_token(self) -> Optional[Dict]:
        """저장된 토큰 정보 불러오기"""
        try:
            if self.token_file.exists():
                with open(self.token_file, 'r') as f:
                    token_info = json.load(f)
                    
                # 만료 시간을 datetime 객체로 변환
                token_info['expires_at'] = datetime.strptime(token_info['expires_at'], '%Y-%m-%d %H:%M:%S')
                
                # 토큰이 아직 유효한지 확인 (만료 1시간 전부터는 새로 발급)
                if token_info['expires_at'] > datetime.now() + timedelta(hours=1):
                    logger.info(f"[_load_token] 저장된 토큰 불러오기 성공 (만료: {token_info['expires_at']})")
                    return token_info
                else:
                    logger.info("[_load_token] 저장된 토큰이 곧 만료되어 새로 발급이 필요합니다.")
                    self.token_file.unlink(missing_ok=True)  # 만료된 토큰 파일 삭제
                    return None
        except Exception as e:
            logger.error(f"[_load_token] 토큰 정보 불러오기 실패: {str(e)}")
            return None
            
    def _get_access_token(self) -> Optional[Dict]:
        """액세스 토큰 발급"""
        try:
            # 저장된 토큰이 있다면 불러오기 시도
            saved_token = self._load_token()
            if saved_token:
                self.token_info = saved_token
                return saved_token

            url = f"{self.domain}/oauth2/tokenP"
            headers = {
                "content-type": "application/json",
                "appkey": APP_KEY,
                "appsecret": APP_SECRET
            }
            body = {
                "grant_type": "client_credentials",
                "appkey": APP_KEY,
                "appsecret": APP_SECRET
            }
            
            logger.debug(f"[_get_access_token] 토큰 발급 요청 URL: {url}")
            logger.debug(f"[_get_access_token] 요청 헤더: {headers}")
            logger.debug(f"[_get_access_token] 요청 바디: {body}")
            
            response = requests.post(url, headers=headers, json=body)
            
            if response.status_code != 200:
                logger.error(f"[_get_access_token] HTTP 에러 발생 - 상태 코드: {response.status_code}")
                logger.error(f"[_get_access_token] 에러 응답: {response.text}")
                response.raise_for_status()
            
            data = response.json()
            logger.debug(f"[_get_access_token] 토큰 발급 응답: {data}")
            
            if data.get('access_token'):
                # API에서 제공하는 만료시간 사용
                expires_at = None
                if data.get('access_token_token_expired'):
                    try:
                        expires_at = datetime.strptime(data['access_token_token_expired'], '%Y-%m-%d %H:%M:%S')
                        logger.info(f"[_get_access_token] API 제공 만료시간 사용: {expires_at}")
                    except ValueError:
                        logger.warning("[_get_access_token] API 만료시간 파싱 실패, 24시간 후로 설정")
                        expires_at = datetime.now() + timedelta(days=1)
                else:
                    logger.warning("[_get_access_token] API 만료시간 없음, 24시간 후로 설정")
                    expires_at = datetime.now() + timedelta(days=1)
                
                token_info = {
                    'access_token': data['access_token'],
                    'token_type': data.get('token_type', 'Bearer'),
                    'expires_in': data.get('expires_in', 86400),
                    'expires_at': expires_at
                }
                logger.info(f"[_get_access_token] 토큰 발급 성공: {token_info['access_token'][:10]}... (만료: {expires_at})")
                
                # 토큰 정보 설정 및 저장
                self.token_info = token_info
                self._save_token()
                
                return token_info
            else:
                logger.error(f"[_get_access_token] 토큰 발급 실패: 응답에 access_token이 없습니다. 응답 데이터: {data}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"[_get_access_token] 토큰 발급 중 오류 발생: {str(e)}")
            logger.error(f"[_get_access_token] 상세 에러: {e.__class__.__name__}")
            return None
        except Exception as e:
            logger.error(f"[_get_access_token] 예상치 못한 오류 발생: {str(e)}")
            logger.error(f"[_get_access_token] 상세 에러: {e.__class__.__name__}")
            return None

    def _is_token_expired(self) -> bool:
        """토큰 만료 여부 확인"""
        if not self.token_info:
            logger.debug("[_is_token_expired] 토큰 정보가 없음")
            return True
        
        now = datetime.now()
        is_expired = now >= self.token_info['expires_at']
        
        if is_expired:
            logger.debug(f"[_is_token_expired] 토큰 만료됨 (만료시간: {self.token_info['expires_at']}, 현재시간: {now})")
        
        return is_expired

    def _ensure_valid_token(self) -> bool:
        """유효한 토큰 보장"""
        try:
            if self._is_token_expired():
                logger.info("[_ensure_valid_token] 토큰이 만료되어 재발급을 시도합니다.")
                token_info = self._get_access_token()
                if not token_info:
                    logger.error("[_ensure_valid_token] 토큰 재발급 실패")
                    return False
                self.token_info = token_info
                logger.info("[_ensure_valid_token] 토큰 재발급 성공")
            return True
        except Exception as e:
            logger.error(f"[_ensure_valid_token] 토큰 갱신 중 오류 발생: {str(e)}")
            logger.error(f"[_ensure_valid_token] 상세 에러: {e.__class__.__name__}")
            return False

    def _rate_limit(self):
        """API 호출 제한 준수"""
        current_time = time.time()
        time_diff = current_time - self._last_request_time
        if time_diff < 1/RATE_LIMIT_PER_SEC:
            time.sleep(1/RATE_LIMIT_PER_SEC - time_diff)
        self._last_request_time = time.time()
        
    def _get_hashkey(self, data: Dict) -> Optional[str]:
        """Hashkey 발급"""
        try:
            if not self._ensure_valid_token():
                raise Exception("토큰 갱신 실패")
                
            url = f"{self.domain}/uapi/hashkey"
            headers = {
                'content-type': 'application/json',
                'appkey': self.app_key,
                'appsecret': self.app_secret,
                'authorization': f"Bearer {self.token_info['access_token']}"
            }
            
            response = requests.post(url, headers=headers, json=data, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            return response.json()['HASH']
        except Exception as e:
            logger.error(f"Hashkey 발급 실패: {e}")
            return None
            
    def place_order(self, stock_code: str, order_type: int, quantity: int,
                   price: int = 0, order_division: str = "00") -> Optional[Dict]:
        """주문 실행
        order_type: 1(매도), 2(매수)
        order_division: "00"(지정가), "01"(시장가)
        """
        try:
            if not self._ensure_valid_token():
                raise Exception("토큰 갱신 실패")
                
            self._rate_limit()
            
            url = f"{self.domain}/uapi/domestic-stock/v1/trading/order-cash"
            body = {
                "CANO": self.account_number,
                "ACNT_PRDT_CD": "01",
                "PDNO": stock_code,
                "ORD_DVSN": order_division,
                "ORD_QTY": str(quantity),
                "ORD_UNPR": str(price) if price > 0 else "0",
            }
            
            # TR_ID 설정
            if self.server == "prod":
                body["TR_ID"] = "TTTC0802U" if order_type == 2 else "TTTC0801U"
            else:
                body["TR_ID"] = "VTTC0802U" if order_type == 2 else "VTTC0801U"
                
            logger.debug(f"[place_order] 주문 요청 - URL: {url}")
            logger.debug(f"[place_order] 주문 요청 - 바디: {body}")
                
            # Hashkey 발급
            hashkey = self._get_hashkey(body)
            if not hashkey:
                logger.error("[place_order] Hashkey 발급 실패")
                return None
                
            headers = {
                "content-type": "application/json",
                "authorization": f"Bearer {self.token_info['access_token']}",
                "appkey": self.app_key,
                "appsecret": self.app_secret,
                "tr_id": body["TR_ID"],
                "custtype": "P",
                "hashkey": hashkey
            }
            
            logger.debug(f"[place_order] 주문 요청 - 헤더: {headers}")
            
            response = requests.post(url, headers=headers, json=body, timeout=REQUEST_TIMEOUT)
            
            if response.status_code != 200:
                logger.error(f"[place_order] HTTP 에러 발생 - 상태 코드: {response.status_code}")
                logger.error(f"[place_order] 에러 응답: {response.text}")
                response.raise_for_status()
                
            result = response.json()
            logger.debug(f"[place_order] 주문 응답: {result}")
            
            if result.get('rt_cd') == '0':
                logger.info(f"[place_order] 주문 성공: {result}")
                return result
            else:
                logger.error(f"[place_order] 주문 실패: {result.get('msg1')}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"[place_order] 주문 중 오류 발생: {str(e)}")
            logger.error(f"[place_order] 상세 에러: {e.__class__.__name__}")
            return None
        except Exception as e:
            logger.error(f"[place_order] 예상치 못한 오류 발생: {str(e)}")
            logger.error(f"[place_order] 상세 에러: {e.__class__.__name__}")
            return None
            
    def get_balance(self) -> Dict:
        """계좌 잔고 조회"""
        try:
            if not self._ensure_valid_token():
                raise Exception("토큰 갱신 실패")
                
            balance_info = {
                'deposit': 0,  # 예수금총금액
                'deposit_d1': 0,  # D+1 예수금
                'deposit_d2': 0,  # D+2 예수금
                'stock_eval_amount': 0,  # 유가증권 평가금액
                'total_eval_amount': 0,  # 총평가금액 (유가증권 평가금액 + D+2 예수금)
                'net_worth': 0,  # 순자산금액
                'total_purchase_amount': 0,  # 매입금액합계금액
                'total_eval_profit_loss': 0,  # 평가손익합계금액
                'positions': {}  # 보유종목
            }

            # 연속 조회를 위한 변수들
            tr_cont = ""  # 연속 거래 여부 (공백: 최초 조회)
            ctx_area_fk100 = ""  # 연속 조회 검색 조건
            ctx_area_nk100 = ""  # 연속 조회 키

            while True:
                url = f"{self.domain}/uapi/domestic-stock/v1/trading/inquire-balance"
                headers = {
                    "content-type": "application/json; charset=utf-8",
                    "authorization": f"Bearer {self.token_info['access_token']}",
                    "appkey": self.app_key,
                    "appsecret": self.app_secret,
                    "tr_id": "VTTC8434R" if self.server == "virtual" else "TTTC8434R",
                    "custtype": "P",
                    "tr_cont": tr_cont  # 연속 거래 여부
                }
                params = {
                    "CANO": self.account_number,
                    "ACNT_PRDT_CD": ACCOUNT_PROD_CODE,
                    "AFHR_FLPR_YN": "N",
                    "OFL_YN": "",
                    "INQR_DVSN": "02",
                    "UNPR_DVSN": "01",
                    "FUND_STTL_ICLD_YN": "N",
                    "FNCG_AMT_AUTO_RDPT_YN": "N",
                    "PRCS_DVSN": "00",
                    "CTX_AREA_FK100": ctx_area_fk100,  # 연속 조회 검색 조건
                    "CTX_AREA_NK100": ctx_area_nk100   # 연속 조회 키
                }
                
                logger.debug(f"[get_balance] 잔고 조회 요청 - URL: {url}")
                logger.debug(f"[get_balance] 잔고 조회 요청 - 헤더: {headers}")
                logger.debug(f"[get_balance] 잔고 조회 요청 - 파라미터: {params}")
                
                response = requests.get(url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
                
                if response.status_code != 200:
                    logger.error(f"[get_balance] HTTP 에러 발생 - 상태 코드: {response.status_code}")
                    logger.error(f"[get_balance] 에러 응답: {response.text}")
                    response.raise_for_status()
                
                data = response.json()
                logger.debug(f"[get_balance] 잔고 조회 응답: {data}")
                
                if data.get('rt_cd') == '0':  # 정상 응답
                    # output2 처리 (계좌 요약정보) - 첫 페이지에만 있음
                    if data.get('output2') and not tr_cont:  # 최초 조회시에만 처리
                        summary = data['output2'][0]
                        balance_info.update({
                            'deposit': int(float(summary.get('dnca_tot_amt', 0))),
                            'deposit_d1': int(float(summary.get('nxdy_excc_amt', 0))),
                            'deposit_d2': int(float(summary.get('prvs_rcdl_excc_amt', 0))),
                            'stock_eval_amount': int(float(summary.get('scts_evlu_amt', 0))),
                            'total_eval_amount': int(float(summary.get('tot_evlu_amt', 0))),
                            'net_worth': int(float(summary.get('nass_amt', 0))),
                            'total_purchase_amount': int(float(summary.get('pchs_amt_smtl_amt', 0))),
                            'total_eval_profit_loss': int(float(summary.get('evlu_pfls_smtl_amt', 0)))
                        })
                        
                        logger.debug(f"[get_balance] 계좌 요약 - "
                                   f"예수금: {balance_info['deposit']:,}원, "
                                   f"D+1예수금: {balance_info['deposit_d1']:,}원, "
                                   f"D+2예수금: {balance_info['deposit_d2']:,}원, "
                                   f"유가증권평가금액: {balance_info['stock_eval_amount']:,}원, "
                                   f"총평가금액: {balance_info['total_eval_amount']:,}원, "
                                   f"순자산: {balance_info['net_worth']:,}원, "
                                   f"평가손익: {balance_info['total_eval_profit_loss']:,}원")
                    
                    # output1 처리 (보유종목 상세정보)
                    if data.get('output1'):
                        for position in data['output1']:
                            stock_code = position.get('pdno', '')
                            if stock_code:
                                if stock_code in balance_info['positions']:
                                    existing = balance_info['positions'][stock_code]
                                    new_quantity = existing['quantity'] + int(position.get('hldg_qty', 0))
                                    total_value = (existing['quantity'] * existing['avg_price'] + 
                                                 int(position.get('hldg_qty', 0)) * float(position.get('pchs_avg_pric', 0)))
                                    new_avg_price = total_value / new_quantity if new_quantity > 0 else 0
                                    
                                    balance_info['positions'][stock_code].update({
                                        'quantity': new_quantity,
                                        'avg_price': new_avg_price
                                    })
                                else:
                                    balance_info['positions'][stock_code] = {
                                        'name': position.get('prdt_name', ''),
                                        'quantity': int(position.get('hldg_qty', 0)),
                                        'orderable_quantity': int(position.get('ord_psbl_qty', 0)),
                                        'avg_price': float(position.get('pchs_avg_pric', 0)),
                                        'purchase_amount': float(position.get('pchs_amt', 0)),
                                        'current_price': float(position.get('prpr', 0)),
                                        'eval_amount': float(position.get('evlu_amt', 0)),
                                        'eval_profit_loss': float(position.get('evlu_pfls_amt', 0)),
                                        'earning_rate': float(position.get('evlu_pfls_rt', 0)),
                                        'trade_type': position.get('trad_dvsn_name', ''),
                                        'loan_date': position.get('loan_dt', ''),
                                        'loan_amount': float(position.get('loan_amt', 0)),
                                        'today_buy': int(position.get('thdt_buyqty', 0)),
                                        'today_sell': int(position.get('thdt_sll_qty', 0))
                                    }
                                
                                logger.debug(f"[get_balance] 보유종목 - "
                                           f"종목코드: {stock_code}, "
                                           f"종목명: {balance_info['positions'][stock_code]['name']}, "
                                           f"거래구분: {balance_info['positions'][stock_code]['trade_type']}, "
                                           f"보유수량: {balance_info['positions'][stock_code]['quantity']:,}주, "
                                           f"주문가능: {balance_info['positions'][stock_code]['orderable_quantity']:,}주, "
                                           f"매입금액: {balance_info['positions'][stock_code]['purchase_amount']:,.0f}원, "
                                           f"평가금액: {balance_info['positions'][stock_code]['eval_amount']:,.0f}원, "
                                           f"평가손익: {balance_info['positions'][stock_code]['eval_profit_loss']:,.0f}원 "
                                           f"({balance_info['positions'][stock_code]['earning_rate']:.2f}%)")
                
                    # 연속 조회 여부 확인
                    tr_cont = response.headers.get('tr_cont', '')
                    if tr_cont == 'M':  # 다음 데이터가 있는 경우
                        tr_cont = 'N'  # 다음 조회를 위해 'N' 설정
                        ctx_area_fk100 = data.get('ctx_area_fk100', '')
                        ctx_area_nk100 = data.get('ctx_area_nk100', '')
                        logger.debug(f"[get_balance] 연속 조회 필요 - tr_cont: {tr_cont}, "
                                   f"ctx_area_fk100: {ctx_area_fk100}, ctx_area_nk100: {ctx_area_nk100}")
                        continue
                    else:
                        break  # 더 이상 조회할 데이터가 없음
                else:
                    error_message = data.get('msg1', '알 수 없는 오류가 발생했습니다')
                    logger.error(f"[get_balance] 잔고 조회 실패: {error_message}")
                    raise Exception(f"잔고 조회 실패: {error_message}")
            
            logger.info("[get_balance] 잔고 조회 성공")
            return balance_info
                
        except requests.exceptions.RequestException as e:
            logger.error(f"[get_balance] 잔고 조회 중 오류 발생: {e}")
            raise Exception("API 요청 실패")
        except Exception as e:
            logger.error(f"[get_balance] 예상치 못한 오류 발생: {str(e)}")
            logger.error(f"[get_balance] 상세 에러: {e.__class__.__name__}")
            raise

    def get_stock_list(self, market_type: str = "ALL") -> List[Dict]:
        """주식 종목 목록 조회
        
        Args:
            market_type: "ALL"(전체), "KOSPI"(코스피), "KOSDAQ"(코스닥)
            
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
            if not self._ensure_valid_token():
                raise Exception("토큰 갱신 실패")
                
            url = f"{self.domain}/uapi/domestic-stock/v1/quotations/inquire-price"
            headers = {
                "content-type": "application/json; charset=utf-8",
                "authorization": f"Bearer {self.token_info['access_token']}",
                "appkey": self.app_key,
                "appsecret": self.app_secret,
                "tr_id": "FHKST03010100"  # 주식현재가 시세
            }
            params = {
                "FID_COND_MRKT_DIV_CODE": market_type,
                "FID_INPUT_ISCD": ""
            }
            
            logger.debug(f"[get_stock_list] 종목 목록 조회 요청 - URL: {url}")
            logger.debug(f"[get_stock_list] 종목 목록 조회 요청 - 헤더: {headers}")
            logger.debug(f"[get_stock_list] 종목 목록 조회 요청 - 파라미터: {params}")
            
            response = requests.get(url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
            
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