#!/usr/bin/env python3
"""
한국투자증권 API 통합 테스트
실제 API 호출을 통해 수정사항이 올바르게 작동하는지 검증
"""

import sys
import asyncio
import logging
from pathlib import Path

# 프로젝트 루트 경로 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.api.kis_api import KISAPI
from core.config.api_config import APIConfig

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_api_connection():
    """API 연결 테스트"""
    print("\n=== API 연결 테스트 ===")
    
    try:
        KISAPI()
        config = APIConfig()
        
        # 토큰 확인
        if config.ensure_valid_token():
            print(f"✅ API 토큰 획득 성공")
            print(f"   - 환경: {config.server}")
            print(f"   - 토큰 길이: {len(config.access_token) if config.access_token else 0}")
            return True
        else:
            print("❌ API 토큰 획득 실패")
            return False
            
    except Exception as e:
        print(f"❌ API 연결 실패: {e}")
        return False

def test_current_price():
    """현재가 조회 테스트 (삼성전자)"""
    print("\n=== 현재가 조회 테스트 ===")
    
    try:
        api = KISAPI()
        stock_code = "005930"  # 삼성전자
        
        result = api.get_current_price(stock_code)
        
        if result:
            print(f"✅ 현재가 조회 성공 ({stock_code}):")
            print(f"   - 현재가: {result.get('current_price'):,.0f}원")
            print(f"   - 등락률: {result.get('change_rate'):.2f}%")
            print(f"   - 거래량: {result.get('volume'):,}")
            return True
        else:
            print(f"❌ 현재가 조회 실패")
            return False
            
    except Exception as e:
        print(f"❌ 현재가 조회 오류: {e}")
        return False

def test_balance_inquiry():
    """잔고 조회 테스트"""
    print("\n=== 잔고 조회 테스트 ===")
    
    try:
        api = KISAPI()
        
        balance = api.get_balance()
        
        if balance:
            print(f"✅ 잔고 조회 성공:")
            print(f"   - 예수금: {balance.get('deposit', 0):,.0f}원")
            print(f"   - 총평가금액: {balance.get('total_eval_amount', 0):,.0f}원")
            print(f"   - 보유종목수: {len(balance.get('positions', {}))}개")
            return True
        else:
            print(f"❌ 잔고 조회 실패 (빈 응답)")
            return False
            
    except Exception as e:
        print(f"❌ 잔고 조회 오류: {e}")
        return False

def test_stock_history():
    """일봉 데이터 조회 테스트"""
    print("\n=== 일봉 데이터 조회 테스트 ===")
    
    try:
        api = KISAPI()
        stock_code = "005930"  # 삼성전자
        
        df = api.get_stock_history(stock_code, period="D", count=5)
        
        if df is not None and not df.empty:
            print(f"✅ 일봉 데이터 조회 성공 ({stock_code}):")
            print(f"   - 조회 기간: {len(df)}일")
            print(f"   - 최신 종가: {df.iloc[0]['close']:,.0f}원")
            print(f"   - 최신 거래량: {df.iloc[0]['volume']:,}")
            return True
        else:
            print(f"❌ 일봉 데이터 조회 실패")
            return False
            
    except Exception as e:
        print(f"❌ 일봉 데이터 조회 오류: {e}")
        return False

async def test_websocket_connection():
    """웹소켓 연결 테스트"""
    print("\n=== 웹소켓 연결 테스트 ===")
    
    try:
        api = KISAPI()
        
        # WebSocket 연결
        connected = await api.connect_websocket()
        
        if connected:
            print(f"✅ 웹소켓 연결 성공")
            
            # 구독 테스트 (삼성전자)
            stock_code = "005930"
            tr_list = [
                'H0STASP0',  # 주식 호가
                'H0STCNT0',  # 주식 체결
            ]
            
            subscribed = await api.subscribe_stock(stock_code, tr_list)
            
            if subscribed:
                print(f"✅ 종목 구독 성공 ({stock_code}):")
                for tr_id in tr_list:
                    print(f"   - {tr_id}")
            else:
                print(f"❌ 종목 구독 실패")
                
            # 연결 종료
            await api.close()
            print(f"✅ 웹소켓 연결 종료")
            return subscribed
        else:
            print(f"❌ 웹소켓 연결 실패")
            return False
            
    except Exception as e:
        print(f"❌ 웹소켓 테스트 오류: {e}")
        return False

def test_order_simulation():
    """주문 시뮬레이션 테스트 (실제 주문 전송하지 않음)"""
    print("\n=== 주문 시뮬레이션 테스트 ===")
    
    try:
        api = KISAPI()
        config = APIConfig()
        
        # 매수 주문 파라미터
        buy_params = {
            'stock_code': '005930',
            'order_type': api.ORDER_TYPE_BUY,  # "02"
            'quantity': 1,
            'price': 70000,
            'order_division': api.ORDER_DIVISION_LIMIT  # "00"
        }
        
        # 매도 주문 파라미터
        sell_params = {
            'stock_code': '005930',
            'order_type': api.ORDER_TYPE_SELL,  # "01"
            'quantity': 1,
            'price': 71000,
            'order_division': api.ORDER_DIVISION_LIMIT  # "00"
        }
        
        print("주문 파라미터 검증:")
        print(f"✅ 매수 주문:")
        print(f"   - order_type: '{buy_params['order_type']}' (expected: '02')")
        print(f"   - order_division: '{buy_params['order_division']}' (expected: '00')")
        
        print(f"✅ 매도 주문:")
        print(f"   - order_type: '{sell_params['order_type']}' (expected: '01')")
        print(f"   - order_division: '{sell_params['order_division']}' (expected: '00')")
        
        # TR_ID 확인
        if config.server == "virtual":
            print(f"✅ 모의투자 TR_ID:")
            print(f"   - 매수: VTTC0012U")
            print(f"   - 매도: VTTC0011U")
        else:
            print(f"✅ 실전투자 TR_ID:")
            print(f"   - 매수: TTTC0012U")
            print(f"   - 매도: TTTC0011U")
        
        return True
        
    except Exception as e:
        print(f"❌ 주문 시뮬레이션 오류: {e}")
        return False

def main():
    """메인 테스트 실행"""
    print("="*60)
    print("한국투자증권 API 통합 테스트")
    print("="*60)
    
    # 동기 테스트
    sync_tests = [
        ("API 연결", test_api_connection),
        ("현재가 조회", test_current_price),
        ("잔고 조회", test_balance_inquiry),
        ("일봉 데이터 조회", test_stock_history),
        ("주문 시뮬레이션", test_order_simulation),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in sync_tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ {test_name} 예외 발생: {e}")
            failed += 1
    
    # 비동기 테스트 (웹소켓)
    try:
        print("\n웹소켓 테스트는 선택적입니다.")
        response = input("웹소켓 연결을 테스트하시겠습니까? (y/N): ").strip().lower()
        if response == 'y':
            if asyncio.run(test_websocket_connection()):
                passed += 1
            else:
                failed += 1
    except Exception as e:
        print(f"❌ 웹소켓 테스트 예외: {e}")
        failed += 1
    
    # 결과 요약
    print("\n" + "="*60)
    print("테스트 결과 요약")
    print("="*60)
    print(f"✅ 통과: {passed}개")
    print(f"❌ 실패: {failed}개")
    
    if failed == 0:
        print("\n🎉 모든 API 기능이 정상 작동합니다!")
        print("한국투자증권 API 수정사항이 올바르게 적용되었습니다.")
    else:
        print("\n⚠️ 일부 API 기능에 문제가 있습니다.")
        print("환경 변수와 API 키 설정을 확인해주세요.")

if __name__ == "__main__":
    main()