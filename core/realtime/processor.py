"""실시간 데이터 처리 모듈"""

from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, List, Callable, Optional
from collections import deque
import json

from core.utils import get_logger

logger = get_logger(__name__)

class DataProcessor:
    """실시간 데이터 처리기"""

    def __init__(self):
        """초기화"""
        self.running = False
        self.callbacks = []
        self.data_buffer = []
        self.buffer_size = 100

    async def start(self):
        """데이터 처리 시작"""
        self.running = True
        logger.info("실시간 데이터 처리 시작")

    async def stop(self):
        """데이터 처리 중지"""
        self.running = False
        logger.info("실시간 데이터 처리 중지")

    def add_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """
        콜백 함수 추가

        Args:
            callback (Callable[[Dict[str, Any]], None]): 데이터 처리 콜백 함수
        """
        self.callbacks.append(callback)
        logger.debug(f"콜백 함수 추가: {callback.__name__}")

    async def process_data(self, data: Dict[str, Any]):
        """
        데이터 처리

        Args:
            data (Dict[str, Any]): 처리할 데이터
        """
        if not self.running:
            return

        try:
            # 데이터 정규화
            normalized_data = self._normalize_data(data)
            
            # 데이터 검증
            if not self._validate_data(normalized_data):
                logger.warning(f"유효하지 않은 데이터: {data}")
                return

            # 데이터 버퍼링
            self.data_buffer.append(normalized_data)
            if len(self.data_buffer) > self.buffer_size:
                self.data_buffer.pop(0)

            # 콜백 함수 실행
            for callback in self.callbacks:
                try:
                    await callback(normalized_data)
                except Exception as e:
                    logger.error(f"콜백 함수 실행 중 오류 발생: {str(e)}", exc_info=True)

            # 거래 데이터 저장
            await self._save_trade_data(normalized_data)

        except Exception as e:
            logger.error(f"데이터 처리 중 오류 발생: {str(e)}", exc_info=True)

    def _normalize_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        데이터 정규화

        Args:
            data (Dict[str, Any]): 원본 데이터

        Returns:
            Dict[str, Any]: 정규화된 데이터
        """
        try:
            normalized = {
                'code': data.get('code', '').strip(),
                'timestamp': datetime.fromtimestamp(data.get('timestamp', 0)),
                'price': Decimal(str(data.get('price', 0))),
                'volume': int(data.get('volume', 0)),
                'type': data.get('type', '').upper()
            }
            return normalized
        except Exception as e:
            logger.error(f"데이터 정규화 중 오류 발생: {str(e)}", exc_info=True)
            return data

    def _validate_data(self, data: Dict[str, Any]) -> bool:
        """
        데이터 검증

        Args:
            data (Dict[str, Any]): 검증할 데이터

        Returns:
            bool: 검증 결과
        """
        try:
            required_fields = ['code', 'timestamp', 'price', 'volume', 'type']
            if not all(field in data for field in required_fields):
                return False

            if not data['code'] or not isinstance(data['code'], str):
                return False

            if not isinstance(data['timestamp'], datetime):
                return False

            if not isinstance(data['price'], (int, float, Decimal)) or data['price'] <= 0:
                return False

            if not isinstance(data['volume'], int) or data['volume'] < 0:
                return False

            if data['type'] not in ['BID', 'ASK', 'TRADE']:
                return False

            return True
        except Exception as e:
            logger.error(f"데이터 검증 중 오류 발생: {str(e)}", exc_info=True)
            return False

    async def _save_trade_data(self, data: Dict[str, Any]):
        """
        거래 데이터 저장

        Args:
            data (Dict[str, Any]): 저장할 데이터
        """
        try:
            if data['type'] != 'TRADE':
                return

            # TODO: 데이터베이스에 거래 데이터 저장
            logger.debug(f"거래 데이터 저장: {json.dumps(data, default=str)}")

        except Exception as e:
            logger.error(f"거래 데이터 저장 중 오류 발생: {str(e)}", exc_info=True)

    def get_buffer_data(self) -> List[Dict[str, Any]]:
        """
        버퍼 데이터 조회

        Returns:
            List[Dict[str, Any]]: 버퍼에 저장된 데이터 목록
        """
        return self.data_buffer.copy()


class RealtimeProcessor:
    """실시간 데이터 처리기 (Phase 3: WebSocket)

    WebSocket으로 수신된 실시간 체결가/호가 데이터를 처리하고,
    포지션별 손절/익절가를 계산하며, 메모리 버퍼를 관리합니다.

    Business Rules:
        - CALC-001: 손절가 계산 (고정비율 vs ATR 기반, 큰 값 선택)
        - CALC-002: 익절가 계산 (고정비율 vs ATR 기반, 큰 값 선택)
    """

    def __init__(self, buffer_maxlen: int = 1000):
        """초기화

        Args:
            buffer_maxlen: deque 버퍼 최대 길이 (기본값: 1000)
        """
        # 실시간 가격 버퍼 (종목코드별)
        # FIFO 방식으로 자동 overflow 처리
        self.price_buffers: Dict[str, deque] = {}
        self.buffer_maxlen = buffer_maxlen

        # 포지션 정보 (종목코드 -> 포지션 데이터)
        self.positions: Dict[str, Dict[str, Any]] = {}

        # 손절/익절 비율 (기본값)
        self.default_stop_loss_ratio = 0.03  # 3% 손절
        self.default_take_profit_ratio = 0.05  # 5% 익절

        logger.info(f"RealtimeProcessor 초기화 완료 (버퍼 크기: {buffer_maxlen})")

    def add_position(
        self,
        stock_code: str,
        entry_price: float,
        quantity: int,
        stop_loss_ratio: Optional[float] = None,
        take_profit_ratio: Optional[float] = None,
        atr: Optional[float] = None
    ):
        """포지션 추가 및 손절/익절가 계산

        Args:
            stock_code: 종목코드
            entry_price: 진입가
            quantity: 수량
            stop_loss_ratio: 손절 비율 (기본값: 0.03)
            take_profit_ratio: 익절 비율 (기본값: 0.05)
            atr: Average True Range 값 (선택)
        """
        if stop_loss_ratio is None:
            stop_loss_ratio = self.default_stop_loss_ratio
        if take_profit_ratio is None:
            take_profit_ratio = self.default_take_profit_ratio

        # CALC-001: 손절가 계산
        stop_loss_price = self.calculate_stop_loss(entry_price, stop_loss_ratio, atr)

        # CALC-002: 익절가 계산
        take_profit_price = self.calculate_take_profit(entry_price, take_profit_ratio, atr)

        self.positions[stock_code] = {
            "entry_price": entry_price,
            "quantity": quantity,
            "stop_loss_price": stop_loss_price,
            "take_profit_price": take_profit_price,
            "stop_loss_ratio": stop_loss_ratio,
            "take_profit_ratio": take_profit_ratio,
            "atr": atr,
            "status": "active",  # active, stop_loss_triggered, take_profit_triggered
            "current_price": entry_price,
            "unrealized_pnl": 0.0,
        }

        logger.info(
            f"포지션 추가: {stock_code}, "
            f"진입={entry_price}, 손절={stop_loss_price:.2f}, 익절={take_profit_price:.2f}"
        )

    def calculate_stop_loss(
        self,
        entry_price: float,
        stop_loss_ratio: float,
        atr: Optional[float] = None
    ) -> float:
        """손절가 계산 (CALC-001)

        고정 비율 방식과 ATR 기반 방식 중 더 큰 값을 선택합니다.
        (보수적 손절 = 더 높은 손절가)

        Args:
            entry_price: 진입가
            stop_loss_ratio: 손절 비율 (예: 0.03 = 3%)
            atr: Average True Range (선택)

        Returns:
            계산된 손절가
        """
        # 고정 비율 방식
        fixed_stop_loss = entry_price * (1 - stop_loss_ratio)

        # ATR 기반 방식 (ATR이 제공된 경우)
        if atr is not None and atr > 0:
            atr_stop_loss = entry_price - (atr * 2.0)  # ATR의 2배
            # 더 높은 값 선택 (보수적 손절)
            return max(fixed_stop_loss, atr_stop_loss)

        return fixed_stop_loss

    def calculate_take_profit(
        self,
        entry_price: float,
        take_profit_ratio: float,
        atr: Optional[float] = None
    ) -> float:
        """익절가 계산 (CALC-002)

        고정 비율 방식과 ATR 기반 방식 중 더 큰 값을 선택합니다.
        (보수적 익절 = 더 높은 익절가)

        Args:
            entry_price: 진입가
            take_profit_ratio: 익절 비율 (예: 0.05 = 5%)
            atr: Average True Range (선택)

        Returns:
            계산된 익절가
        """
        # 고정 비율 방식
        fixed_take_profit = entry_price * (1 + take_profit_ratio)

        # ATR 기반 방식 (ATR이 제공된 경우)
        if atr is not None and atr > 0:
            atr_take_profit = entry_price + (atr * 3.0)  # ATR의 3배
            # 더 높은 값 선택 (보수적 익절)
            return max(fixed_take_profit, atr_take_profit)

        return fixed_take_profit

    def process_realtime_price(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """실시간 가격 데이터 처리

        WebSocket으로 수신된 체결가 데이터를 버퍼에 저장하고,
        포지션이 있는 경우 손익을 계산합니다.

        Args:
            data: 정규화된 체결가 데이터 (from _normalize_kis_message)

        Returns:
            포지션 업데이트 정보 (있는 경우) 또는 None
        """
        stock_code = data.get("stock_code")
        current_price = data.get("current_price", 0)

        if not stock_code or current_price <= 0:
            return None

        # 가격 버퍼 초기화 (필요시)
        if stock_code not in self.price_buffers:
            self.price_buffers[stock_code] = deque(maxlen=self.buffer_maxlen)

        # 버퍼에 추가 (자동 overflow)
        self.price_buffers[stock_code].append({
            "price": current_price,
            "timestamp": data.get("timestamp"),
            "volume": data.get("volume", 0),
        })

        # 포지션이 있는 경우 손익 계산
        if stock_code in self.positions:
            position = self.positions[stock_code]

            # 미실현 손익 계산
            entry_price = position["entry_price"]
            quantity = position["quantity"]
            unrealized_pnl = (current_price - entry_price) * quantity

            # 포지션 업데이트
            position["current_price"] = current_price
            position["unrealized_pnl"] = unrealized_pnl

            return {
                "stock_code": stock_code,
                "current_price": current_price,
                "entry_price": entry_price,
                "stop_loss_price": position["stop_loss_price"],
                "take_profit_price": position["take_profit_price"],
                "unrealized_pnl": unrealized_pnl,
                "status": position["status"],
            }

        return None

    def get_position(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """포지션 조회

        Args:
            stock_code: 종목코드

        Returns:
            포지션 정보 또는 None
        """
        return self.positions.get(stock_code)

    def remove_position(self, stock_code: str):
        """포지션 제거

        Args:
            stock_code: 종목코드
        """
        if stock_code in self.positions:
            del self.positions[stock_code]
            logger.info(f"포지션 제거: {stock_code}")

    def get_price_buffer(self, stock_code: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """가격 버퍼 조회

        Args:
            stock_code: 종목코드
            limit: 최대 개수 (기본값: 전체)

        Returns:
            가격 데이터 리스트
        """
        if stock_code not in self.price_buffers:
            return []

        buffer = list(self.price_buffers[stock_code])
        if limit:
            return buffer[-limit:]
        return buffer

    def get_buffer_stats(self) -> Dict[str, Any]:
        """버퍼 상태 조회 (모니터링용)

        Returns:
            버퍼 통계 정보
        """
        total_items = sum(len(buf) for buf in self.price_buffers.values())
        max_capacity = len(self.price_buffers) * self.buffer_maxlen if self.price_buffers else 0

        stats = {
            "total_stocks": len(self.price_buffers),
            "total_items": total_items,
            "buffer_maxlen": self.buffer_maxlen,
            "usage_percent": (total_items / max_capacity * 100) if max_capacity > 0 else 0.0,
            "stocks": [],
        }

        for stock_code, buffer in self.price_buffers.items():
            stats["stocks"].append({
                "stock_code": stock_code,
                "buffer_size": len(buffer),
                "is_full": len(buffer) >= self.buffer_maxlen,
            })

        return stats

    def check_buffer_overflow(self) -> Optional[str]:
        """버퍼 오버플로우 감지 (경고 로깅용)

        Returns:
            경고 메시지 (오버플로우 발생 시) 또는 None
        """
        stats = self.get_buffer_stats()

        # 전체 사용률이 80% 이상이면 경고
        if stats["usage_percent"] >= 80.0:
            warning_msg = (
                f"버퍼 사용률 높음: {stats['usage_percent']:.1f}% "
                f"({stats['total_items']}/{len(self.price_buffers) * self.buffer_maxlen})"
            )
            logger.warning(
                warning_msg,
                extra={
                    "total_stocks": stats["total_stocks"],
                    "total_items": stats["total_items"],
                    "usage_percent": stats["usage_percent"],
                },
            )
            return warning_msg

        return None