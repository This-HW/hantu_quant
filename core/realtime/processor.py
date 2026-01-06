"""실시간 데이터 처리 모듈"""

import asyncio
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, List, Callable, Optional
import json

from core.utils import get_logger
from core.database.models import Stock, Price, Indicator

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

            if not data['type'] in ['BID', 'ASK', 'TRADE']:
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