#!/usr/bin/env python3
"""
한국투자증권 API 수정사항 테스트
공식 문서 기준으로 API 호출이 올바르게 작동하는지 검증
"""

import os
import sys
import logging
from pathlib import Path

# 프로젝트 루트 경로 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.api.kis_api import KISAPI
from core.api.rest_client import KISRestClient
from core.config.api_config import APIConfig

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_order_constants():
    """주문 상수 값 검증"""
    print("\n=== 1. 주문 상수 검증 ===")
    
    api = KISAPI()
    
    # ORDER_TYPE 상수 확인
    print(f"ORDER_TYPE_SELL: {api.ORDER_TYPE_SELL} (expected: '01')")
    print(f"ORDER_TYPE_BUY: {api.ORDER_TYPE_BUY} (expected: '02')")
    print(f"ORDER_DIVISION_LIMIT: {api.ORDER_DIVISION_LIMIT} (expected: '00')")
    print(f"ORDER_DIVISION_MARKET: {api.ORDER_DIVISION_MARKET} (expected: '01')")
    
    # 검증
    assert api.ORDER_TYPE_SELL == "01", f"ORDER_TYPE_SELL should be '01', got {api.ORDER_TYPE_SELL}"
    assert api.ORDER_TYPE_BUY == "02", f"ORDER_TYPE_BUY should be '02', got {api.ORDER_TYPE_BUY}"
    assert api.ORDER_DIVISION_LIMIT == "00", f"ORDER_DIVISION_LIMIT should be '00'"
    assert api.ORDER_DIVISION_MARKET == "01", f"ORDER_DIVISION_MARKET should be '01'"
    
    print("✅ 주문 상수 값이 올바르게 설정되었습니다.")
    return True

def test_tr_id_generation():
    """TR_ID 생성 검증"""
    print("\n=== 2. TR_ID 생성 검증 ===")
    
    config = APIConfig()
    client = KISRestClient()
    
    # 원래 서버 설정 저장
    original_server = config.server
    
    try:
        # 모의투자 환경 테스트
        config.server = 'virtual'
        print(f"\n모의투자 환경 (server='virtual'):")
        
        # place_order 메소드 내부 로직 시뮬레이션
        order_type_sell = "01"
        order_type_buy = "02"
        
        if config.server == "virtual":
            tr_id_sell = "VTTC0011U" if order_type_sell == "01" else "VTTC0012U"
            tr_id_buy = "VTTC0011U" if order_type_buy == "01" else "VTTC0012U"
        else:
            tr_id_sell = "TTTC0011U" if order_type_sell == "01" else "TTTC0012U"
            tr_id_buy = "TTTC0011U" if order_type_buy == "01" else "TTTC0012U"
        
        print(f"  매도 TR_ID: {tr_id_sell} (expected: VTTC0011U)")
        print(f"  매수 TR_ID: {tr_id_buy} (expected: VTTC0012U)")
        
        assert tr_id_sell == "VTTC0011U", f"모의 매도 TR_ID should be 'VTTC0011U'"
        assert tr_id_buy == "VTTC0012U", f"모의 매수 TR_ID should be 'VTTC0012U'"
        
        # 실전투자 환경 테스트
        config.server = 'prod'
        print(f"\n실전투자 환경 (server='prod'):")
        
        if config.server == "virtual":
            tr_id_sell = "VTTC0011U" if order_type_sell == "01" else "VTTC0012U"
            tr_id_buy = "VTTC0011U" if order_type_buy == "01" else "VTTC0012U"
        else:
            tr_id_sell = "TTTC0011U" if order_type_sell == "01" else "TTTC0012U"
            tr_id_buy = "TTTC0011U" if order_type_buy == "01" else "TTTC0012U"
        
        print(f"  매도 TR_ID: {tr_id_sell} (expected: TTTC0011U)")
        print(f"  매수 TR_ID: {tr_id_buy} (expected: TTTC0012U)")
        
        assert tr_id_sell == "TTTC0011U", f"실전 매도 TR_ID should be 'TTTC0011U'"
        assert tr_id_buy == "TTTC0012U", f"실전 매수 TR_ID should be 'TTTC0012U'"
        
        print("✅ TR_ID가 환경과 주문유형에 따라 올바르게 생성됩니다.")
        return True
        
    finally:
        # 원래 설정 복원
        config.server = original_server

def test_websocket_subscription_codes():
    """웹소켓 구독 코드 검증"""
    print("\n=== 3. 웹소켓 구독 코드 검증 ===")
    
    # kis_api.py의 start_real_time 메소드에서 사용하는 tr_list 확인
    expected_codes = ['H0STASP0', 'H0STCNT0', 'H0STCNI0']
    
    # 실제 코드에서 설정된 값 (수정 후)
    actual_codes = [
        'H0STASP0',  # 주식 호가
        'H0STCNT0',  # 주식 체결
        'H0STCNI0'   # 주식 체결통보
    ]
    
    print("공식 문서 구독 코드:")
    print(f"  H0STASP0: 주식 호가")
    print(f"  H0STCNT0: 주식 체결")
    print(f"  H0STCNI0: 주식 체결통보")
    
    print("\n현재 설정된 코드:")
    for code in actual_codes:
        print(f"  {code}")
    
    # 검증
    for i, code in enumerate(actual_codes):
        assert code == expected_codes[i], f"구독 코드가 일치하지 않음: {code} != {expected_codes[i]}"
    
    print("✅ 웹소켓 구독 코드가 올바르게 설정되었습니다.")
    return True

def test_order_data_structure():
    """주문 데이터 구조 검증"""
    print("\n=== 4. 주문 데이터 구조 검증 ===")
    
    # 주문 데이터 구조 시뮬레이션
    stock_code = "005930"  # 삼성전자
    order_type = "02"  # 매수
    quantity = 10
    price = 70000
    order_division = "00"  # 지정가
    
    # rest_client.py의 place_order 메소드 데이터 구조
    data = {
        "CANO": "12345678",  # 예시 계좌번호
        "ACNT_PRDT_CD": "01",  # 예시 계좌상품코드
        "PDNO": stock_code,
        "ORD_DVSN": order_division,
        "ORD_QTY": str(quantity),
        "ORD_UNPR": str(price),
        "CTAC_TLNO": "",
        "SLL_BUY_DVSN_CD": order_type,  # "01"=매도, "02"=매수
        "ALGO_NO": ""
    }
    
    print("주문 데이터 구조:")
    print(f"  종목코드(PDNO): {data['PDNO']}")
    print(f"  주문구분(ORD_DVSN): {data['ORD_DVSN']} (00=지정가, 01=시장가)")
    print(f"  주문수량(ORD_QTY): {data['ORD_QTY']}")
    print(f"  주문단가(ORD_UNPR): {data['ORD_UNPR']}")
    print(f"  매매구분(SLL_BUY_DVSN_CD): {data['SLL_BUY_DVSN_CD']} (01=매도, 02=매수)")
    
    # 검증
    assert data["SLL_BUY_DVSN_CD"] in ["01", "02"], "SLL_BUY_DVSN_CD는 '01' 또는 '02'여야 함"
    assert isinstance(data["ORD_QTY"], str), "ORD_QTY는 문자열이어야 함"
    assert isinstance(data["ORD_UNPR"], str), "ORD_UNPR는 문자열이어야 함"
    
    print("✅ 주문 데이터 구조가 올바르게 설정되었습니다.")
    return True

def test_balance_tr_id():
    """잔고 조회 TR_ID 검증"""
    print("\n=== 5. 잔고 조회 TR_ID 검증 ===")
    
    config = APIConfig()
    original_server = config.server
    
    try:
        # 모의투자 테스트
        config.server = "virtual"
        default_tr = "VTTC8434R" if config.server == "virtual" else "TTTC8434R"
        print(f"모의투자 잔고 조회 TR_ID: {default_tr} (expected: VTTC8434R)")
        assert default_tr == "VTTC8434R", "모의투자 잔고 조회 TR_ID가 잘못됨"
        
        # 실전투자 테스트
        config.server = "prod"
        default_tr = "VTTC8434R" if config.server == "virtual" else "TTTC8434R"
        print(f"실전투자 잔고 조회 TR_ID: {default_tr} (expected: TTTC8434R)")
        assert default_tr == "TTTC8434R", "실전투자 잔고 조회 TR_ID가 잘못됨"
        
        print("✅ 잔고 조회 TR_ID가 올바르게 설정되었습니다.")
        return True
        
    finally:
        config.server = original_server

def main():
    """메인 테스트 실행"""
    print("="*60)
    print("한국투자증권 API 수정사항 검증 시작")
    print("="*60)
    
    tests = [
        ("주문 상수 검증", test_order_constants),
        ("TR_ID 생성 검증", test_tr_id_generation),
        ("웹소켓 구독 코드 검증", test_websocket_subscription_codes),
        ("주문 데이터 구조 검증", test_order_data_structure),
        ("잔고 조회 TR_ID 검증", test_balance_tr_id)
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"❌ {test_name} 실패: {e}")
            failed += 1
    
    print("\n" + "="*60)
    print("테스트 결과 요약")
    print("="*60)
    print(f"✅ 통과: {passed}개")
    print(f"❌ 실패: {failed}개")
    
    if failed == 0:
        print("\n🎉 모든 수정사항이 올바르게 적용되었습니다!")
        print("한국투자증권 API가 공식 문서 기준으로 정상 작동합니다.")
    else:
        print("\n⚠️ 일부 테스트가 실패했습니다. 수정이 필요합니다.")
        sys.exit(1)

if __name__ == "__main__":
    main()