"""
REST 클라이언트 캐시 통합 테스트

B2: REST 클라이언트 캐시 통합 검증
"""

import time
from core.api.rest_client import KISRestClient
from core.utils.log_utils import get_logger

logger = get_logger(__name__)


def test_cache_integration():
    """캐시 통합 동작 검증"""
    print("\n=== REST 클라이언트 캐시 통합 테스트 ===\n")

    client = KISRestClient()
    test_stock_code = "005930"  # 삼성전자

    # 1. 가격 캐시 테스트
    print("1. 가격 캐시 테스트")
    print("   첫 호출 (캐시 미스 예상)...")
    start = time.time()
    price1 = client.get_current_price(test_stock_code)
    duration1 = time.time() - start
    print(f"   소요 시간: {duration1:.3f}초")
    print(f"   결과: {price1.get('current_price') if price1 else 'None'}")

    print("\n   두 번째 호출 (캐시 히트 예상)...")
    start = time.time()
    price2 = client.get_current_price(test_stock_code)
    duration2 = time.time() - start
    print(f"   소요 시간: {duration2:.3f}초")
    print(f"   결과: {price2.get('current_price') if price2 else 'None'}")

    if duration2 < duration1 * 0.5:
        print("   ✅ 캐시 히트 확인 (응답 속도 개선)")
    else:
        print("   ⚠️  캐시 미스 가능성 (속도 개선 없음)")

    # 2. 캐시 무효화 테스트
    print("\n2. 캐시 무효화 테스트")
    print("   특정 종목 캐시 무효화...")
    client.clear_price_cache(test_stock_code)

    print("   무효화 후 호출 (캐시 미스 예상)...")
    start = time.time()
    price3 = client.get_current_price(test_stock_code)
    duration3 = time.time() - start
    print(f"   소요 시간: {duration3:.3f}초")

    if duration3 > duration2 * 2:
        print("   ✅ 캐시 무효화 확인 (응답 시간 증가)")
    else:
        print("   ⚠️  캐시 무효화 미확인")

    # 3. 일봉 캐시 테스트
    print("\n3. 일봉 차트 캐시 테스트")
    print("   첫 호출 (캐시 미스 예상)...")
    start = time.time()
    chart1 = client.get_daily_chart(test_stock_code, period_days=60)
    duration1 = time.time() - start
    print(f"   소요 시간: {duration1:.3f}초")
    print(f"   결과: {len(chart1)}일 데이터" if chart1 is not None else "   결과: None")

    print("\n   두 번째 호출 (캐시 히트 예상)...")
    start = time.time()
    chart2 = client.get_daily_chart(test_stock_code, period_days=60)
    duration2 = time.time() - start
    print(f"   소요 시간: {duration2:.3f}초")

    if duration2 < duration1 * 0.5:
        print("   ✅ 캐시 히트 확인 (응답 속도 개선)")
    else:
        print("   ⚠️  캐시 미스 가능성")

    # 4. 전체 캐시 삭제 테스트
    print("\n4. 전체 캐시 삭제 테스트")
    client.clear_all_cache()
    print("   ✅ 전체 캐시 삭제 완료")

    # 5. 종목 정보 캐시 테스트
    print("\n5. 종목 정보 캐시 테스트")
    print("   첫 호출 (캐시 미스 예상)...")
    start = time.time()
    info1 = client.get_stock_info(test_stock_code)
    duration1 = time.time() - start
    print(f"   소요 시간: {duration1:.3f}초")
    print(f"   결과: {info1.get('stock_name') if info1 else 'None'}")

    print("\n   두 번째 호출 (캐시 히트 예상)...")
    start = time.time()
    info2 = client.get_stock_info(test_stock_code)
    duration2 = time.time() - start
    print(f"   소요 시간: {duration2:.3f}초")

    if duration2 < duration1 * 0.5:
        print("   ✅ 캐시 히트 확인 (응답 속도 개선)")
    else:
        print("   ⚠️  캐시 미스 가능성")

    print("\n=== 테스트 완료 ===")
    print("\n[참고]")
    print("- 캐시 히트 시 응답 시간이 현저히 감소해야 합니다.")
    print("- Rate Limit 때문에 첫 호출들 사이에 자동 대기가 발생합니다.")
    print("- 캐시 로그는 logger 설정에 따라 파일에 기록됩니다.")


if __name__ == "__main__":
    test_cache_integration()
