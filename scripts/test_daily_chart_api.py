"""
일봉 차트 API 통합 테스트 스크립트

KIS 표준 API (inquire-daily-itemchartprice) 실제 호출 검증
"""

import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.api.rest_client import KISRestClient
from core.utils.log_utils import get_logger
import time
import logging

# 로거 설정
logger = get_logger(__name__)
logger.setLevel(logging.INFO)

# 콘솔 핸들러 추가
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(message)s')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)


def test_daily_chart_api():
    """실제 API 호출로 일봉 데이터 검증"""

    client = KISRestClient()
    test_stocks = ["005930", "000660", "035420"]  # 삼성전자, SK하이닉스, NAVER

    logger.info("=== 일봉 차트 API 테스트 시작 ===")

    for stock_code in test_stocks:
        logger.info(f"\n[{stock_code}] 테스트 중...")

        try:
            df = client.get_daily_chart(stock_code, period_days=60)

            if df is not None:
                logger.info(f"✅ 성공: {len(df)}일 데이터 조회")
                logger.info(f"   기간: {df.index[0]} ~ {df.index[-1]}")
                logger.info(f"   최근 종가: {df['close'].iloc[-1]:,.0f}원")
                logger.info(f"   평균 거래량: {df['volume'].mean():,.0f}주")
            else:
                logger.error(f"❌ 실패: 데이터 없음")

        except Exception as e:
            logger.error(f"❌ 에러: {e}", exc_info=True)

        time.sleep(0.3)  # Rate limit

    logger.info("\n=== 테스트 완료 ===")


def test_date_range():
    """날짜 범위 파라미터 테스트"""
    client = KISRestClient()
    logger.info("\n=== 날짜 범위 테스트 ===")

    for period in [30, 60, 100]:
        logger.info(f"\n[기간: {period}일] 테스트 중...")

        try:
            df = client.get_daily_chart("005930", period_days=period)

            if df is not None:
                logger.info(f"✅ 성공: {len(df)}일 데이터 조회")
                logger.info(f"   요청: {period}일, 실제: {len(df)}일")
                logger.info(f"   기간: {df.index[0]} ~ {df.index[-1]}")
            else:
                logger.error(f"❌ 실패: 데이터 없음")

        except Exception as e:
            logger.error(f"❌ 에러: {e}", exc_info=True)

        time.sleep(0.3)


def test_api_performance():
    """API 성능 테스트 (캐싱 검증)"""
    client = KISRestClient()
    logger.info("\n=== API 성능 테스트 (캐싱) ===")

    stock_code = "005930"

    # 첫 번째 호출 (API)
    logger.info(f"\n[1차 호출] {stock_code} - API 호출")
    start_time = time.time()
    df1 = client.get_daily_chart(stock_code, period_days=60)
    elapsed1 = time.time() - start_time
    logger.info(f"   소요 시간: {elapsed1:.3f}초")

    # 두 번째 호출 (캐시)
    logger.info(f"\n[2차 호출] {stock_code} - 캐시 히트")
    start_time = time.time()
    df2 = client.get_daily_chart(stock_code, period_days=60)
    elapsed2 = time.time() - start_time
    logger.info(f"   소요 시간: {elapsed2:.3f}초")

    # 캐시 효과 확인
    if elapsed2 < elapsed1 * 0.1:
        logger.info(f"✅ 캐싱 정상 작동: {elapsed1/elapsed2:.1f}배 빠름")
    else:
        logger.warning(f"⚠️ 캐싱 효과 미약: 1차 {elapsed1:.3f}초, 2차 {elapsed2:.3f}초")


if __name__ == "__main__":
    try:
        test_daily_chart_api()
        test_date_range()
        test_api_performance()

    except KeyboardInterrupt:
        logger.info("\n테스트 중단됨")
    except Exception as e:
        logger.error(f"\n테스트 실행 오류: {e}", exc_info=True)
