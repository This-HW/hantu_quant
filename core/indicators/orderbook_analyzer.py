# -*- coding: utf-8 -*-
"""
호가 불균형 분석기 (P1-2)

기능:
- 매수/매도 호가 잔량 분석
- 불균형 비율 계산
- 매매 신호 생성 (strong_buy, buy, neutral, sell, strong_sell)
- WebSocket 실시간 데이터 연동
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional, Callable
from datetime import datetime
from enum import Enum

from ..utils.log_utils import get_logger

logger = get_logger(__name__)


class OrderBookSignal(Enum):
    """호가 불균형 신호"""
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    NEUTRAL = "neutral"
    SELL = "sell"
    STRONG_SELL = "strong_sell"


@dataclass
class OrderBookImbalance:
    """호가 불균형 분석 결과"""
    stock_code: str
    bid_volume: int  # 매수 잔량 합계
    ask_volume: int  # 매도 잔량 합계
    total_volume: int  # 총 잔량
    imbalance_ratio: float  # 불균형 비율 (-1.0 ~ 1.0)
    signal: OrderBookSignal  # 매매 신호
    confidence: float  # 신뢰도 (0.0 ~ 1.0)
    bid_price_weighted: float = 0.0  # 가중평균 매수호가
    ask_price_weighted: float = 0.0  # 가중평균 매도호가
    spread: float = 0.0  # 스프레드 (%)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict:
        """딕셔너리 변환"""
        return {
            "stock_code": self.stock_code,
            "bid_volume": self.bid_volume,
            "ask_volume": self.ask_volume,
            "total_volume": self.total_volume,
            "imbalance_ratio": self.imbalance_ratio,
            "signal": self.signal.value,
            "confidence": self.confidence,
            "bid_price_weighted": self.bid_price_weighted,
            "ask_price_weighted": self.ask_price_weighted,
            "spread": self.spread,
            "timestamp": self.timestamp,
        }


@dataclass
class OrderBookLevel:
    """호가 레벨 데이터"""
    price: int
    volume: int
    count: int = 0  # 주문 건수 (있는 경우)


class OrderBookAnalyzer:
    """호가 불균형 분석기

    매수/매도 호가 잔량의 불균형을 분석하여 단기 방향을 예측합니다.

    불균형 비율 = (매수잔량 - 매도잔량) / 총잔량
    - > 0.3: 강한 매수 신호
    - > 0.1: 매수 신호
    - -0.1 ~ 0.1: 중립
    - < -0.1: 매도 신호
    - < -0.3: 강한 매도 신호
    """

    # 신호 임계값
    STRONG_BUY_THRESHOLD = 0.3
    BUY_THRESHOLD = 0.1
    SELL_THRESHOLD = -0.1
    STRONG_SELL_THRESHOLD = -0.3

    def __init__(
        self,
        levels: int = 10,
        strong_threshold: float = 0.3,
        weak_threshold: float = 0.1,
    ):
        """초기화

        Args:
            levels: 분석할 호가 레벨 수 (기본 10)
            strong_threshold: 강한 신호 임계값 (기본 0.3)
            weak_threshold: 약한 신호 임계값 (기본 0.1)
        """
        self.levels = levels
        self.strong_threshold = strong_threshold
        self.weak_threshold = weak_threshold

        # 콜백 함수 (신호 발생 시 호출)
        self._signal_callbacks: List[Callable[[OrderBookImbalance], None]] = []

        # 종목별 최근 분석 결과 캐시
        self._cache: Dict[str, OrderBookImbalance] = {}

        logger.info(
            f"OrderBookAnalyzer 초기화 - "
            f"레벨: {levels}, 강한신호: ±{strong_threshold}, 약한신호: ±{weak_threshold}"
        )

    def analyze(
        self,
        stock_code: str,
        bids: List[Tuple[int, int]],
        asks: List[Tuple[int, int]],
        levels: Optional[int] = None
    ) -> OrderBookImbalance:
        """호가 불균형 분석

        Args:
            stock_code: 종목 코드
            bids: 매수 호가 리스트 [(가격, 수량), ...]
            asks: 매도 호가 리스트 [(가격, 수량), ...]
            levels: 분석할 호가 레벨 수 (None이면 기본값)

        Returns:
            OrderBookImbalance 분석 결과
        """
        levels = levels or self.levels

        # 지정된 레벨만큼 데이터 추출
        bid_data = bids[:levels]
        ask_data = asks[:levels]

        # 잔량 합계 계산
        bid_volume = sum(vol for _, vol in bid_data)
        ask_volume = sum(vol for _, vol in ask_data)
        total_volume = bid_volume + ask_volume

        # 불균형 비율 계산
        if total_volume > 0:
            imbalance_ratio = (bid_volume - ask_volume) / total_volume
        else:
            imbalance_ratio = 0.0

        # 신호 및 신뢰도 계산
        signal, confidence = self._calculate_signal(imbalance_ratio)

        # 가중평균 가격 계산
        bid_price_weighted = self._calculate_weighted_price(bid_data)
        ask_price_weighted = self._calculate_weighted_price(ask_data)

        # 스프레드 계산
        spread = self._calculate_spread(bid_data, ask_data)

        result = OrderBookImbalance(
            stock_code=stock_code,
            bid_volume=bid_volume,
            ask_volume=ask_volume,
            total_volume=total_volume,
            imbalance_ratio=imbalance_ratio,
            signal=signal,
            confidence=confidence,
            bid_price_weighted=bid_price_weighted,
            ask_price_weighted=ask_price_weighted,
            spread=spread,
        )

        # 캐시 업데이트
        self._cache[stock_code] = result

        # 콜백 호출
        self._notify_callbacks(result)

        logger.debug(
            f"호가 분석 - {stock_code}: "
            f"매수잔량 {bid_volume:,}, 매도잔량 {ask_volume:,}, "
            f"불균형 {imbalance_ratio:.2%}, 신호 {signal.value}"
        )

        return result

    def analyze_from_raw(
        self,
        stock_code: str,
        raw_data: Dict
    ) -> OrderBookImbalance:
        """KIS WebSocket 원시 데이터로부터 분석

        Args:
            stock_code: 종목 코드
            raw_data: H0STASP0 TR 응답 데이터

        Returns:
            OrderBookImbalance 분석 결과
        """
        bids, asks = self._parse_kis_orderbook(raw_data)
        return self.analyze(stock_code, bids, asks)

    def _parse_kis_orderbook(
        self,
        raw_data: Dict
    ) -> Tuple[List[Tuple[int, int]], List[Tuple[int, int]]]:
        """KIS 호가 데이터 파싱

        H0STASP0 TR 응답 형식:
        - ASKP1~10: 매도호가 1~10
        - ASKP_RSQN1~10: 매도호가 잔량 1~10
        - BIDP1~10: 매수호가 1~10
        - BIDP_RSQN1~10: 매수호가 잔량 1~10

        Args:
            raw_data: KIS WebSocket 응답

        Returns:
            (매수호가 리스트, 매도호가 리스트)
        """
        bids = []
        asks = []

        try:
            for i in range(1, 11):
                # 매도호가
                ask_price = int(raw_data.get(f'ASKP{i}', 0) or 0)
                ask_volume = int(raw_data.get(f'ASKP_RSQN{i}', 0) or 0)
                if ask_price > 0:
                    asks.append((ask_price, ask_volume))

                # 매수호가
                bid_price = int(raw_data.get(f'BIDP{i}', 0) or 0)
                bid_volume = int(raw_data.get(f'BIDP_RSQN{i}', 0) or 0)
                if bid_price > 0:
                    bids.append((bid_price, bid_volume))

        except Exception as e:
            logger.error(f"호가 데이터 파싱 오류: {e}")

        return bids, asks

    def _calculate_signal(
        self,
        imbalance_ratio: float
    ) -> Tuple[OrderBookSignal, float]:
        """신호 및 신뢰도 계산

        Args:
            imbalance_ratio: 불균형 비율

        Returns:
            (신호, 신뢰도) 튜플
        """
        abs_ratio = abs(imbalance_ratio)

        if imbalance_ratio > self.strong_threshold:
            signal = OrderBookSignal.STRONG_BUY
            # 신뢰도: 0.3~0.5 → 0.6~1.0
            confidence = min(abs_ratio / 0.5, 1.0)

        elif imbalance_ratio > self.weak_threshold:
            signal = OrderBookSignal.BUY
            # 신뢰도: 0.1~0.3 → 0.3~1.0
            confidence = abs_ratio / self.strong_threshold

        elif imbalance_ratio < self.strong_threshold * -1:
            signal = OrderBookSignal.STRONG_SELL
            confidence = min(abs_ratio / 0.5, 1.0)

        elif imbalance_ratio < self.weak_threshold * -1:
            signal = OrderBookSignal.SELL
            confidence = abs_ratio / self.strong_threshold

        else:
            signal = OrderBookSignal.NEUTRAL
            # 중립일 때 신뢰도: 비율이 0에 가까울수록 높음
            confidence = 1 - (abs_ratio / self.weak_threshold)

        return signal, round(confidence, 3)

    def _calculate_weighted_price(
        self,
        orders: List[Tuple[int, int]]
    ) -> float:
        """가중평균 가격 계산

        Args:
            orders: 호가 리스트 [(가격, 수량), ...]

        Returns:
            가중평균 가격
        """
        if not orders:
            return 0.0

        total_value = sum(price * vol for price, vol in orders)
        total_volume = sum(vol for _, vol in orders)

        if total_volume > 0:
            return total_value / total_volume
        return 0.0

    def _calculate_spread(
        self,
        bids: List[Tuple[int, int]],
        asks: List[Tuple[int, int]]
    ) -> float:
        """스프레드 계산 (%)

        Args:
            bids: 매수 호가 리스트
            asks: 매도 호가 리스트

        Returns:
            스프레드 비율 (%)
        """
        if not bids or not asks:
            return 0.0

        best_bid = bids[0][0]  # 최우선 매수호가
        best_ask = asks[0][0]  # 최우선 매도호가

        if best_bid > 0:
            return (best_ask - best_bid) / best_bid * 100
        return 0.0

    # ========== 콜백 관리 ==========

    def add_signal_callback(self, callback: Callable[[OrderBookImbalance], None]):
        """신호 발생 시 호출할 콜백 등록

        Args:
            callback: 콜백 함수 (OrderBookImbalance 인자)
        """
        self._signal_callbacks.append(callback)
        logger.info(f"호가 분석 콜백 등록됨 (총 {len(self._signal_callbacks)}개)")

    def remove_signal_callback(self, callback: Callable):
        """콜백 제거"""
        if callback in self._signal_callbacks:
            self._signal_callbacks.remove(callback)

    def _notify_callbacks(self, result: OrderBookImbalance):
        """콜백 호출 (비중립 신호일 때만)"""
        if result.signal != OrderBookSignal.NEUTRAL:
            for callback in self._signal_callbacks:
                try:
                    callback(result)
                except Exception as e:
                    logger.error(f"호가 분석 콜백 오류: {e}")

    # ========== 캐시 조회 ==========

    def get_cached_result(self, stock_code: str) -> Optional[OrderBookImbalance]:
        """캐시된 분석 결과 조회"""
        return self._cache.get(stock_code)

    def get_all_cached_results(self) -> Dict[str, OrderBookImbalance]:
        """모든 캐시된 결과 조회"""
        return self._cache.copy()

    def clear_cache(self):
        """캐시 초기화"""
        self._cache.clear()

    # ========== 유틸리티 ==========

    def get_signal_summary(self) -> Dict[str, int]:
        """현재 캐시된 결과의 신호별 통계"""
        summary = {signal.value: 0 for signal in OrderBookSignal}

        for result in self._cache.values():
            summary[result.signal.value] += 1

        return summary


class OrderBookMonitor:
    """호가 실시간 모니터

    WebSocketClient와 연동하여 실시간 호가 불균형을 모니터링합니다.
    """

    # KIS 호가 TR ID
    TR_ORDERBOOK = "H0STASP0"

    def __init__(
        self,
        analyzer: Optional[OrderBookAnalyzer] = None,
        ws_client=None
    ):
        """초기화

        Args:
            analyzer: OrderBookAnalyzer 인스턴스
            ws_client: KISWebSocketClient 인스턴스
        """
        self.analyzer = analyzer or OrderBookAnalyzer()
        self.ws_client = ws_client
        self._monitoring_stocks: List[str] = []
        self._running = False

        logger.info("OrderBookMonitor 초기화 완료")

    def set_websocket_client(self, ws_client):
        """WebSocket 클라이언트 설정"""
        self.ws_client = ws_client

    async def start_monitoring(self, stock_codes: List[str]):
        """호가 모니터링 시작

        Args:
            stock_codes: 모니터링할 종목 코드 리스트
        """
        if not self.ws_client:
            logger.error("WebSocket 클라이언트가 설정되지 않았습니다")
            return False

        try:
            # WebSocket 연결 확인
            if not self.ws_client.websocket:
                await self.ws_client.connect()

            # 각 종목 호가 구독
            for code in stock_codes:
                await self.ws_client.subscribe(code, [self.TR_ORDERBOOK])
                self._monitoring_stocks.append(code)

            # 호가 데이터 수신 콜백 등록
            self.ws_client.add_callback(self.TR_ORDERBOOK, self._on_orderbook_data)

            self._running = True
            logger.info(f"호가 모니터링 시작: {len(stock_codes)}개 종목")
            return True

        except Exception as e:
            logger.error(f"호가 모니터링 시작 실패: {e}")
            return False

    async def stop_monitoring(self):
        """호가 모니터링 중지"""
        self._running = False
        self._monitoring_stocks.clear()
        logger.info("호가 모니터링 중지")

    def _on_orderbook_data(self, data: Dict):
        """호가 데이터 수신 콜백

        Args:
            data: WebSocket에서 수신한 호가 데이터
        """
        try:
            stock_code = data.get('MKSC_SHRN_ISCD', '')  # 종목코드
            if not stock_code:
                return

            # 분석 수행
            result = self.analyzer.analyze_from_raw(stock_code, data)

            # 강한 신호일 때 로그
            if result.signal in [OrderBookSignal.STRONG_BUY, OrderBookSignal.STRONG_SELL]:
                logger.info(
                    f"🔔 강한 호가 신호 - {stock_code}: {result.signal.value} "
                    f"(불균형 {result.imbalance_ratio:.2%}, 신뢰도 {result.confidence:.1%})"
                )

        except Exception as e:
            logger.error(f"호가 데이터 처리 오류: {e}")

    @property
    def is_running(self) -> bool:
        """모니터링 중인지 확인"""
        return self._running

    @property
    def monitoring_stocks(self) -> List[str]:
        """모니터링 중인 종목 리스트"""
        return self._monitoring_stocks.copy()


# 편의 함수
def analyze_orderbook(
    stock_code: str,
    bids: List[Tuple[int, int]],
    asks: List[Tuple[int, int]],
    levels: int = 10
) -> OrderBookImbalance:
    """호가 불균형 분석 편의 함수

    Args:
        stock_code: 종목 코드
        bids: 매수 호가 리스트 [(가격, 수량), ...]
        asks: 매도 호가 리스트 [(가격, 수량), ...]
        levels: 분석할 호가 레벨 수

    Returns:
        OrderBookImbalance 분석 결과
    """
    analyzer = OrderBookAnalyzer(levels=levels)
    return analyzer.analyze(stock_code, bids, asks)
