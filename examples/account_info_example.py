"""
한국투자증권 API를 통한 계좌 정보 조회 예제
"""

import logging
import sys
import json
from pathlib import Path
import requests

# 로깅 설정
logging.basicConfig(
    level=logging.DEBUG,  # 로깅 레벨을 DEBUG로 변경
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)

# 프로젝트 루트 경로를 sys.path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config.api_config import APIConfig  # noqa: E402
from core.config import settings  # noqa: E402

def get_account_balance(api_config: APIConfig):
    """
    계좌 잔고 조회
    
    Args:
        api_config (APIConfig): API 설정 객체
        
    Returns:
        dict: 계좌 잔고 정보
    """
    # API 호출 제한 적용
    api_config.apply_rate_limit()
    
    # 유효한 토큰 확보
    if not api_config.ensure_valid_token():
        logger.error("유효한 토큰을 확보할 수 없습니다.")
        return None
    
    # API 엔드포인트 구성
    url = f"{api_config.base_url}/uapi/domestic-stock/v1/trading/inquire-balance"
    
    # 요청 헤더 준비
    headers = api_config.get_headers()
    # 필수 추가 헤더
    headers.update({
        "tr_id": "VTTC8434R" if api_config.server == "virtual" else "TTTC8434R",  # 거래 ID (모의투자/실투자 구분)
        "tr_cont": "N",  # 연속 거래 여부
    })
    
    # 요청 파라미터 구성
    params = {
        "CANO": api_config.account_number,          # 계좌번호
        "ACNT_PRDT_CD": api_config.account_prod_code,  # 계좌상품코드
        "AFHR_FLPR_YN": "N",                        # 시간외단일가여부
        "OFL_YN": "N",                              # 오프라인여부
        "INQR_DVSN": "02",                          # 조회구분, 01: 주식, 02: 잔고
        "UNPR_DVSN": "01",                          # 단가구분, 01: 원화
        "FUND_STTL_ICLD_YN": "N",                   # 펀드결제분포함여부
        "FNCG_AMT_AUTO_RDPT_YN": "N",               # 융자금액자동상환여부
        "PRCS_DVSN": "01",                          # 처리구분, 00: 전일매매, 01: 당일매매
        "CTX_AREA_FK100": "",                       # 연속조회검색조건100
        "CTX_AREA_NK100": ""                        # 연속조회키100
    }

    # 요청 전송 및 결과 처리
    try:
        logger.info(f"계좌 잔고 조회 요청 - URL: {url}")
        logger.debug(f"요청 헤더: {headers}")  # 민감 정보는 로깅에서 마스킹 처리 필요
        logger.debug(f"요청 파라미터: {params}")
        
        response = requests.get(
            url, 
            headers=headers, 
            params=params,
            timeout=settings.REQUEST_TIMEOUT
        )
        
        logger.info(f"응답 상태 코드: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            # 전체 응답 내용 로깅
            logger.debug(f"응답 내용: {json.dumps(result, indent=2, ensure_ascii=False)}")
            return result
        else:
            logger.error(f"API 호출 실패 - 상태 코드: {response.status_code}")
            logger.debug(f"응답 내용: {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"API 호출 중 오류 발생: {str(e)}")
        return None

def get_account_info(api_config: APIConfig):
    """
    계좌 기본 정보 조회
    
    Args:
        api_config (APIConfig): API 설정 객체
        
    Returns:
        dict: 계좌 기본 정보
    """
    # API 호출 제한 적용
    api_config.apply_rate_limit()
    
    # 유효한 토큰 확보
    if not api_config.ensure_valid_token():
        logger.error("유효한 토큰을 확보할 수 없습니다.")
        return None
    
    # API 엔드포인트 구성
    url = f"{api_config.base_url}/uapi/domestic-stock/v1/trading/inquire-psbl-order"
    
    # 요청 헤더 준비
    headers = api_config.get_headers()
    # 필수 추가 헤더
    headers.update({
        "tr_id": "VTTC8908R" if api_config.server == "virtual" else "TTTC8908R",  # 거래 ID (모의투자/실투자 구분)
        "tr_cont": "N",  # 연속 거래 여부
    })
    
    # 요청 파라미터 구성
    params = {
        "CANO": api_config.account_number,           # 계좌번호
        "ACNT_PRDT_CD": api_config.account_prod_code,   # 계좌상품코드
        "PDNO": "005930",                            # 종목번호(삼성전자)
        "ORD_UNPR": "0",                             # 주문단가
        "ORD_DVSN": "01",                            # 주문구분
        "CMA_EVLU_AMT_ICLD_YN": "Y",                 # CMA평가금액포함여부
        "OVRS_ICLD_YN": "N"                          # 해외포함여부
    }

    # 요청 전송 및 결과 처리
    try:
        logger.info(f"계좌 기본 정보 조회 요청 - URL: {url}")
        logger.debug(f"요청 헤더: {headers}")  # 민감 정보는 로깅에서 마스킹 처리 필요
        logger.debug(f"요청 파라미터: {params}")
        
        response = requests.get(
            url, 
            headers=headers, 
            params=params,
            timeout=settings.REQUEST_TIMEOUT
        )
        
        logger.info(f"응답 상태 코드: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            # 전체 응답 내용 로깅
            logger.debug(f"응답 내용: {json.dumps(result, indent=2, ensure_ascii=False)}")
            return result
        else:
            logger.error(f"API 호출 실패 - 상태 코드: {response.status_code}")
            logger.debug(f"응답 내용: {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"API 호출 중 오류 발생: {str(e)}")
        return None

def get_stock_holdings(api_config: APIConfig):
    """
    주식 보유 내역 조회
    
    Args:
        api_config (APIConfig): API 설정 객체
        
    Returns:
        dict: 주식 보유 내역 정보
    """
    # API 호출 제한 적용
    api_config.apply_rate_limit()
    
    # 유효한 토큰 확보
    if not api_config.ensure_valid_token():
        logger.error("유효한 토큰을 확보할 수 없습니다.")
        return None
    
    # API 엔드포인트 구성
    url = f"{api_config.base_url}/uapi/domestic-stock/v1/trading/inquire-balance"
    
    # 요청 헤더 준비
    headers = api_config.get_headers()
    # 필수 추가 헤더
    headers.update({
        "tr_id": "VTTC8434R" if api_config.server == "virtual" else "TTTC8434R",  # 거래 ID (모의투자/실투자 구분)
        "tr_cont": "N",  # 연속 거래 여부
    })
    
    # 요청 파라미터 구성
    params = {
        "CANO": api_config.account_number,          # 계좌번호
        "ACNT_PRDT_CD": api_config.account_prod_code,  # 계좌상품코드
        "AFHR_FLPR_YN": "N",                        # 시간외단일가여부
        "OFL_YN": "N",                              # 오프라인여부
        "INQR_DVSN": "01",                          # 조회구분, 01: 주식, 02: 잔고
        "UNPR_DVSN": "01",                          # 단가구분, 01: 원화
        "FUND_STTL_ICLD_YN": "N",                   # 펀드결제분포함여부
        "FNCG_AMT_AUTO_RDPT_YN": "N",               # 융자금액자동상환여부
        "PRCS_DVSN": "01",                          # 처리구분, 00: 전일매매, 01: 당일매매
        "CTX_AREA_FK100": "",                       # 연속조회검색조건100
        "CTX_AREA_NK100": ""                        # 연속조회키100
    }

    # 요청 전송 및 결과 처리
    try:
        logger.info(f"주식 보유 내역 조회 요청 - URL: {url}")
        logger.debug(f"요청 헤더: {headers}")  # 민감 정보는 로깅에서 마스킹 처리 필요
        logger.debug(f"요청 파라미터: {params}")
        
        response = requests.get(
            url, 
            headers=headers, 
            params=params,
            timeout=settings.REQUEST_TIMEOUT
        )
        
        logger.info(f"응답 상태 코드: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            # 전체 응답 내용 로깅
            logger.debug(f"응답 내용: {json.dumps(result, indent=2, ensure_ascii=False)}")
            return result
        else:
            logger.error(f"API 호출 실패 - 상태 코드: {response.status_code}")
            logger.debug(f"응답 내용: {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"API 호출 중 오류 발생: {str(e)}")
        return None

def main():
    """메인 함수"""
    # APIConfig 인스턴스 생성
    api_config = APIConfig()
    
    # 현재 환경 출력
    print(f"현재 설정된 환경: {'모의투자' if api_config.server == 'virtual' else '실제투자'}")
    print(f"계좌번호: {api_config.account_number}")
    
    # 토큰 갱신 확인
    if not api_config.ensure_valid_token():
        print("토큰 갱신 실패")
        return
    
    print("토큰 갱신 성공")
    
    # 1. 계좌 기본 정보 조회
    print("\n===== 계좌 기본 정보 조회 =====")
    account_info = get_account_info(api_config)
    
    if account_info:
        # 민감 정보 마스킹
        masked_info = json.dumps(account_info, indent=2, ensure_ascii=False)
        print(f"계좌 기본 정보:\n{masked_info}")
    else:
        print("계좌 기본 정보 조회 실패")
    
    # 2. 계좌 잔고 조회
    print("\n===== 계좌 잔고 조회 =====")
    balance_info = get_account_balance(api_config)
    
    if balance_info:
        # 민감 정보 마스킹
        masked_balance = json.dumps(balance_info, indent=2, ensure_ascii=False)
        print(f"계좌 잔고 정보:\n{masked_balance}")
    else:
        print("계좌 잔고 조회 실패")
        
    # 3. 주식 보유 내역 조회
    print("\n===== 주식 보유 내역 조회 =====")
    holdings_info = get_stock_holdings(api_config)
    
    if holdings_info:
        # 민감 정보 마스킹
        masked_holdings = json.dumps(holdings_info, indent=2, ensure_ascii=False)
        print(f"주식 보유 내역:\n{masked_holdings}")
    else:
        print("주식 보유 내역 조회 실패")

if __name__ == "__main__":
    main() 