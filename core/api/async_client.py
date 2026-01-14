"""
비동기 KIS API 클라이언트 (P2-4)

기능:
- aiohttp 기반 비동기 HTTP 요청
- 동시 요청 제한 (세마포어)
- 배치 가격 조회
- 부분 실패 허용

성능 개선:
- 100개 종목 순차 조회: ~30초
- 100개 종목 병렬 조회: ~3초 (10배 향상)
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import time

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

from core.config.api_config import APIConfig

logger = logging.getLogger(__name__)


@dataclass
class PriceData:
    """가격 데이터"""
    stock_code: str
    current_price: float
    change_rate: float
    volume: int
    high: float
    low: float
    open_price: float
    prev_close: float
    fetched_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class BatchResult:
    """배치 조회 결과"""
    successful: Dict[str, PriceData]
    failed: List[Tuple[str, str]]  # (stock_code, error_message)
    total_time_ms: float

    @property
    def success_rate(self) -> float:
        """성공률"""
        total = len(self.successful) + len(self.failed)
        return len(self.successful) / total if total > 0 else 0

    @property
    def success_count(self) -> int:
        return len(self.successful)

    @property
    def failure_count(self) -> int:
        return len(self.failed)


class AsyncKISClient:
    """비동기 KIS API 클라이언트

    동시 요청 제한을 통해 API 서버 부하를 방지하면서
    빠른 배치 조회를 수행합니다.

    Usage:
        # 비동기 컨텍스트에서 사용
        async def main():
            async with AsyncKISClient() as client:
                result = await client.get_prices_batch(['005930', '000660', '035720'])
                print(result.successful)

        # 동기 코드에서 호출
        result = get_prices_sync(['005930', '000660', '035720'])
    """

    def __init__(
        self,
        max_concurrent: int = 10,
        timeout: float = 10.0,
        retry_count: int = 2,
    ):
        """초기화

        Args:
            max_concurrent: 최대 동시 요청 수 (기본 10)
            timeout: 요청 타임아웃 (초)
            retry_count: 재시도 횟수
        """
        if not AIOHTTP_AVAILABLE:
            raise ImportError("aiohttp가 설치되어 있지 않습니다. pip install aiohttp")

        self.max_concurrent = max_concurrent
        self.timeout = timeout
        self.retry_count = retry_count
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.config = APIConfig()
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """컨텍스트 매니저 진입"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout)
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """컨텍스트 매니저 종료"""
        if self.session:
            await self.session.close()

    def _get_headers(self) -> Dict[str, str]:
        """요청 헤더 생성"""
        # 토큰 유효성 확인
        self.config.ensure_valid_token()

        # 시세 조회 API (inquire-price)는 모의/실전 동일한 tr_id 사용
        # 참고: 거래 API (order, balance)만 모의/실전 tr_id가 다름 (TTTC.../VTTC...)
        tr_id = "FHKST01010100"

        return {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {self.config.access_token}",
            "appkey": self.config.app_key,
            "appsecret": self.config.app_secret,
            "tr_id": tr_id,
            "custtype": "P",
        }

    async def _get_price(
        self,
        stock_code: str
    ) -> Tuple[str, Optional[PriceData], Optional[str]]:
        """단일 종목 가격 조회 (세마포어 적용)

        Args:
            stock_code: 종목코드

        Returns:
            (stock_code, price_data or None, error_message or None)
        """
        async with self.semaphore:
            for attempt in range(self.retry_count + 1):
                try:
                    url = f"{self.config.base_url}/uapi/domestic-stock/v1/quotations/inquire-price"
                    headers = self._get_headers()
                    params = {
                        "FID_COND_MRKT_DIV_CODE": "J",
                        "FID_INPUT_ISCD": stock_code
                    }

                    async with self.session.get(url, headers=headers, params=params) as response:
                        if response.status == 200:
                            data = await response.json()
                            output = data.get("output", {})

                            price_data = PriceData(
                                stock_code=stock_code,
                                current_price=float(output.get("stck_prpr", 0)),
                                change_rate=float(output.get("prdy_ctrt", 0)),
                                volume=int(output.get("acml_vol", 0)),
                                high=float(output.get("stck_hgpr", 0)),
                                low=float(output.get("stck_lwpr", 0)),
                                open_price=float(output.get("stck_oprc", 0)),
                                prev_close=float(output.get("stck_sdpr", 0)),
                            )
                            return (stock_code, price_data, None)

                        elif response.status >= 500:
                            # 서버 에러는 재시도
                            if attempt < self.retry_count:
                                await asyncio.sleep(1 * (attempt + 1))  # 백오프
                                continue
                            return (stock_code, None, f"HTTP {response.status}")
                        else:
                            # 클라이언트 에러는 재시도 안함
                            return (stock_code, None, f"HTTP {response.status}")

                except asyncio.TimeoutError:
                    if attempt < self.retry_count:
                        await asyncio.sleep(1 * (attempt + 1))
                        continue
                    return (stock_code, None, "Timeout")

                except aiohttp.ClientError as e:
                    if attempt < self.retry_count:
                        await asyncio.sleep(1 * (attempt + 1))
                        continue
                    return (stock_code, None, str(e))

                except Exception as e:
                    return (stock_code, None, str(e))

            return (stock_code, None, "최대 재시도 횟수 초과")

    async def get_prices_batch(
        self,
        stock_codes: List[str]
    ) -> BatchResult:
        """여러 종목 가격 배치 조회

        Args:
            stock_codes: 종목코드 리스트

        Returns:
            BatchResult: 배치 조회 결과
        """
        if not self.session:
            raise RuntimeError("세션이 초기화되지 않았습니다. async with 구문을 사용하세요.")

        start_time = time.time()
        logger.info(f"배치 가격 조회 시작: {len(stock_codes)}개 종목")

        # 병렬 조회
        tasks = [self._get_price(code) for code in stock_codes]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        successful = {}
        failed = []

        for result in results:
            if isinstance(result, Exception):
                failed.append(("unknown", str(result)))
            else:
                code, price_data, error = result
                if price_data:
                    successful[code] = price_data
                else:
                    failed.append((code, error or "Unknown error"))

        elapsed_ms = (time.time() - start_time) * 1000
        logger.info(
            f"배치 가격 조회 완료: 성공 {len(successful)}/{len(stock_codes)}, "
            f"실패 {len(failed)}, 소요시간 {elapsed_ms:.1f}ms"
        )

        return BatchResult(
            successful=successful,
            failed=failed,
            total_time_ms=elapsed_ms
        )

    async def get_price(self, stock_code: str) -> Optional[PriceData]:
        """단일 종목 가격 조회

        Args:
            stock_code: 종목코드

        Returns:
            PriceData or None
        """
        if not self.session:
            raise RuntimeError("세션이 초기화되지 않았습니다. async with 구문을 사용하세요.")

        code, price_data, error = await self._get_price(stock_code)
        if error:
            logger.warning(f"가격 조회 실패 ({code}): {error}")
        return price_data


def get_prices_sync(
    stock_codes: List[str],
    max_concurrent: int = 10,
    timeout: float = 10.0,
) -> BatchResult:
    """동기 코드에서 배치 가격 조회 호출

    비동기 코드를 동기적으로 실행합니다.
    이미 이벤트 루프가 실행 중인 경우 에러가 발생할 수 있습니다.

    Args:
        stock_codes: 종목코드 리스트
        max_concurrent: 최대 동시 요청 수
        timeout: 요청 타임아웃 (초)

    Returns:
        BatchResult: 배치 조회 결과

    Usage:
        result = get_prices_sync(['005930', '000660', '035720'])
        for code, price in result.successful.items():
            print(f"{code}: {price.current_price:,.0f}원")
    """
    async def _run():
        async with AsyncKISClient(
            max_concurrent=max_concurrent,
            timeout=timeout
        ) as client:
            return await client.get_prices_batch(stock_codes)

    return asyncio.run(_run())


def get_price_sync(stock_code: str, timeout: float = 10.0) -> Optional[PriceData]:
    """동기 코드에서 단일 가격 조회 호출

    Args:
        stock_code: 종목코드
        timeout: 요청 타임아웃 (초)

    Returns:
        PriceData or None
    """
    async def _run():
        async with AsyncKISClient(timeout=timeout) as client:
            return await client.get_price(stock_code)

    return asyncio.run(_run())


async def get_prices_async(
    stock_codes: List[str],
    max_concurrent: int = 10,
    timeout: float = 10.0,
) -> BatchResult:
    """비동기 컨텍스트에서 배치 가격 조회

    이미 이벤트 루프가 실행 중인 경우 이 함수를 사용합니다.

    Args:
        stock_codes: 종목코드 리스트
        max_concurrent: 최대 동시 요청 수
        timeout: 요청 타임아웃 (초)

    Returns:
        BatchResult: 배치 조회 결과

    Usage:
        # FastAPI, async 함수 등에서 사용
        async def handler():
            result = await get_prices_async(['005930', '000660'])
            return result.successful
    """
    async with AsyncKISClient(
        max_concurrent=max_concurrent,
        timeout=timeout
    ) as client:
        return await client.get_prices_batch(stock_codes)
