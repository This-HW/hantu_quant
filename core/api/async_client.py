"""
비동기 KIS API 클라이언트 (P2-4)

기능:
- aiohttp 기반 비동기 HTTP 요청
- 동시 요청 제한 (세마포어)
- 요청 간 Rate Limit 준수 (초당 최대 요청 수 제한)
- 배치 가격 조회
- 부분 실패 허용

성능 개선:
- 100개 종목 순차 조회: ~30초
- 100개 종목 병렬 조회 (Rate Limit 적용): ~10초
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

from core.config.api_config import APIConfig, KISErrorCode
from core.config import settings

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

    동시 요청 제한 + Rate Limit을 통해 API 서버 부하를 방지하면서
    빠른 배치 조회를 수행합니다.

    Rate Limit 정책:
    - KIS API 공식 제한: 실전 초당 20건, 모의 초당 5건
    - 안전 마진 적용: 초당 10건으로 제한 (슬라이딩 윈도우 대응)
    - 동시 요청은 세마포어로 제한, 요청 간격은 Rate Limiter로 제어

    Usage:
        # 비동기 컨텍스트에서 사용
        async def main():
            async with AsyncKISClient() as client:
                result = await client.get_prices_batch(['005930', '000660', '035720'])
                print(result.successful)

        # 동기 코드에서 호출
        result = get_prices_sync(['005930', '000660', '035720'])
    """

    # Rate Limit 설정 (초당 최대 요청 수)
    # KIS API: 실전 20건/초, 모의 5건/초
    # 안전 마진 적용하여 5건/초로 제한 (모의투자 기준, 슬라이딩 윈도우 대응)
    DEFAULT_RATE_LIMIT_PER_SEC = 5

    # Rate Limit 에러 발생 시 대기 시간 (초)
    RATE_LIMIT_WAIT_TIME = 10.0

    # 청크 처리 시 청크 간 대기 시간 (초)
    CHUNK_WAIT_TIME = 1.5

    def __init__(
        self,
        max_concurrent: int = 1,
        timeout: float = 10.0,
        retry_count: int = 3,
        rate_limit_per_sec: Optional[int] = None,
    ):
        """초기화

        Args:
            max_concurrent: 최대 동시 요청 수 (기본 1, 순차 처리)
            timeout: 요청 타임아웃 (초)
            retry_count: 재시도 횟수 (기본 3)
            rate_limit_per_sec: 초당 최대 요청 수 (기본 5, 모의투자 기준)
        """
        if not AIOHTTP_AVAILABLE:
            raise ImportError("aiohttp가 설치되어 있지 않습니다. pip install aiohttp")

        self.max_concurrent = max_concurrent
        self.timeout = timeout
        self.retry_count = retry_count
        self.rate_limit_per_sec = rate_limit_per_sec or self.DEFAULT_RATE_LIMIT_PER_SEC

        # 요청 간 최소 대기 시간 계산 (예: 5건/초 → 0.2초)
        self.min_interval = 1.0 / self.rate_limit_per_sec

        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.config = APIConfig()
        self.session: Optional[aiohttp.ClientSession] = None

        # Rate Limit 관리용 Lock과 마지막 요청 시간
        self._rate_limit_lock = asyncio.Lock()
        self._last_request_time: float = 0.0

        # 슬라이딩 윈도우 기반 Rate Limit 추적
        self._request_timestamps: List[float] = []

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

    async def _rate_limit_wait(self):
        """Rate Limit 준수를 위한 대기 (슬라이딩 윈도우 방식)

        1초 윈도우 내 요청 수를 추적하여 Rate Limit을 정확하게 준수합니다.
        """
        async with self._rate_limit_lock:
            now = time.time()

            # 1초 이전 타임스탬프 제거 (슬라이딩 윈도우)
            self._request_timestamps = [
                ts for ts in self._request_timestamps if now - ts < 1.0
            ]

            # 현재 윈도우 내 요청 수가 제한에 도달한 경우 대기
            while len(self._request_timestamps) >= self.rate_limit_per_sec:
                # 가장 오래된 요청이 윈도우를 벗어날 때까지 대기
                oldest = self._request_timestamps[0]
                wait_time = 1.0 - (now - oldest) + 0.05  # 50ms 여유
                if wait_time > 0:
                    logger.debug(f"Rate Limit 대기: {wait_time:.2f}초")
                    await asyncio.sleep(wait_time)

                # 다시 확인
                now = time.time()
                self._request_timestamps = [
                    ts for ts in self._request_timestamps if now - ts < 1.0
                ]

            # 요청 간 최소 간격도 유지
            if self._last_request_time > 0:
                elapsed = now - self._last_request_time
                if elapsed < self.min_interval:
                    await asyncio.sleep(self.min_interval - elapsed)

            # 현재 요청 시간 기록
            now = time.time()
            self._request_timestamps.append(now)
            self._last_request_time = now

    def _is_rate_limit_error(self, data: dict) -> bool:
        """Rate Limit 에러인지 확인"""
        rt_cd = data.get("rt_cd")
        msg_cd = data.get("msg_cd", "")

        # rt_cd가 '1'이면 에러, msg_cd가 EGW00201이면 Rate Limit
        if rt_cd == "1" and msg_cd == KISErrorCode.RATE_LIMIT:
            return True
        return False

    def _is_retryable_error(self, data: dict) -> bool:
        """재시도 가능한 에러인지 확인"""
        msg_cd = data.get("msg_cd", "")
        return msg_cd in KISErrorCode.RETRYABLE_ERRORS

    async def _get_price(
        self,
        stock_code: str
    ) -> Tuple[str, Optional[PriceData], Optional[str]]:
        """단일 종목 가격 조회 (세마포어 + Rate Limit 적용)

        Args:
            stock_code: 종목코드

        Returns:
            (stock_code, price_data or None, error_message or None)
        """
        async with self.semaphore:
            for attempt in range(self.retry_count + 1):
                try:
                    # Rate Limit 대기
                    await self._rate_limit_wait()

                    url = f"{self.config.base_url}/uapi/domestic-stock/v1/quotations/inquire-price"
                    headers = self._get_headers()
                    params = {
                        "FID_COND_MRKT_DIV_CODE": "J",
                        "FID_INPUT_ISCD": stock_code
                    }

                    async with self.session.get(url, headers=headers, params=params) as response:
                        data = await response.json()

                        # Rate Limit 에러 처리 (EGW00201)
                        if self._is_rate_limit_error(data):
                            logger.warning(
                                f"Rate Limit 에러 발생 ({stock_code}), "
                                f"{self.RATE_LIMIT_WAIT_TIME}초 대기 후 재시도 "
                                f"({attempt + 1}/{self.retry_count + 1})"
                            )
                            if attempt < self.retry_count:
                                await asyncio.sleep(self.RATE_LIMIT_WAIT_TIME)
                                continue
                            return (stock_code, None, f"Rate Limit 초과 (EGW00201)")

                        # 다른 재시도 가능 에러 처리
                        if self._is_retryable_error(data):
                            msg_cd = data.get("msg_cd", "")
                            msg1 = data.get("msg1", "")
                            logger.warning(
                                f"재시도 가능 에러 ({stock_code}): {msg_cd} - {msg1}"
                            )
                            if attempt < self.retry_count:
                                await asyncio.sleep(2 * (attempt + 1))
                                continue
                            return (stock_code, None, f"{msg_cd}: {msg1}")

                        if response.status == 200:
                            output = data.get("output", {})

                            # 정상 응답이지만 데이터가 없는 경우
                            if not output or not output.get("stck_prpr"):
                                return (stock_code, None, "데이터 없음")

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
                                await asyncio.sleep(2 * (attempt + 1))  # 백오프
                                continue
                            return (stock_code, None, f"HTTP {response.status}")
                        else:
                            # 클라이언트 에러는 재시도 안함
                            return (stock_code, None, f"HTTP {response.status}")

                except asyncio.TimeoutError:
                    if attempt < self.retry_count:
                        await asyncio.sleep(2 * (attempt + 1))
                        continue
                    return (stock_code, None, "Timeout")

                except aiohttp.ClientError as e:
                    if attempt < self.retry_count:
                        await asyncio.sleep(2 * (attempt + 1))
                        continue
                    return (stock_code, None, str(e))

                except Exception as e:
                    logger.error(f"가격 조회 예외 ({stock_code}): {e}", exc_info=True)
                    return (stock_code, None, str(e))

            return (stock_code, None, "최대 재시도 횟수 초과")

    async def get_prices_batch(
        self,
        stock_codes: List[str],
        chunk_size: Optional[int] = None,
    ) -> BatchResult:
        """여러 종목 가격 배치 조회 (순차 처리, Rate Limit 준수)

        Args:
            stock_codes: 종목코드 리스트
            chunk_size: 청크 크기 (None이면 rate_limit_per_sec 사용)

        Returns:
            BatchResult: 배치 조회 결과
        """
        if not self.session:
            raise RuntimeError("세션이 초기화되지 않았습니다. async with 구문을 사용하세요.")

        start_time = time.time()
        logger.info(f"배치 가격 조회 시작: {len(stock_codes)}개 종목 (순차 처리)")

        successful = {}
        failed = []

        # 청크 크기 설정 (기본: rate_limit_per_sec)
        actual_chunk_size = chunk_size or self.rate_limit_per_sec

        # 종목을 청크로 분할
        chunks = [
            stock_codes[i:i + actual_chunk_size]
            for i in range(0, len(stock_codes), actual_chunk_size)
        ]

        for chunk_idx, chunk in enumerate(chunks):
            chunk_start = time.time()

            # 청크 내 종목들을 순차 처리
            for code in chunk:
                try:
                    code, price_data, error = await self._get_price(code)
                    if price_data:
                        successful[code] = price_data
                    else:
                        failed.append((code, error or "Unknown error"))
                except Exception as e:
                    logger.error(f"가격 조회 예외 ({code}): {e}", exc_info=True)
                    failed.append((code, str(e)))

            # 청크 간 대기 (마지막 청크 제외)
            if chunk_idx < len(chunks) - 1:
                chunk_elapsed = time.time() - chunk_start
                # 최소 1초 간격 유지 (슬라이딩 윈도우 대응)
                if chunk_elapsed < self.CHUNK_WAIT_TIME:
                    await asyncio.sleep(self.CHUNK_WAIT_TIME - chunk_elapsed)

            # 진행 상황 로깅
            processed = (chunk_idx + 1) * actual_chunk_size
            logger.debug(
                f"청크 {chunk_idx + 1}/{len(chunks)} 완료 "
                f"({min(processed, len(stock_codes))}/{len(stock_codes)})"
            )

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
    max_concurrent: int = 1,
    timeout: float = 10.0,
    rate_limit_per_sec: int = 5,
) -> BatchResult:
    """동기 코드에서 배치 가격 조회 호출 (순차 처리, Rate Limit 준수)

    비동기 코드를 동기적으로 실행합니다.
    이미 이벤트 루프가 실행 중인 경우 에러가 발생할 수 있습니다.

    Args:
        stock_codes: 종목코드 리스트
        max_concurrent: 최대 동시 요청 수 (기본 1, 순차 처리)
        timeout: 요청 타임아웃 (초)
        rate_limit_per_sec: 초당 최대 요청 수 (기본 5, 모의투자 기준)

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
            timeout=timeout,
            rate_limit_per_sec=rate_limit_per_sec,
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
    max_concurrent: int = 1,
    timeout: float = 10.0,
    rate_limit_per_sec: int = 5,
) -> BatchResult:
    """비동기 컨텍스트에서 배치 가격 조회 (순차 처리, Rate Limit 준수)

    이미 이벤트 루프가 실행 중인 경우 이 함수를 사용합니다.

    Args:
        stock_codes: 종목코드 리스트
        max_concurrent: 최대 동시 요청 수 (기본 1, 순차 처리)
        timeout: 요청 타임아웃 (초)
        rate_limit_per_sec: 초당 최대 요청 수 (기본 5, 모의투자 기준)

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
        timeout=timeout,
        rate_limit_per_sec=rate_limit_per_sec,
    ) as client:
        return await client.get_prices_batch(stock_codes)
