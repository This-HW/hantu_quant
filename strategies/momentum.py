import logging
import pandas as pd
import numpy as np
from typing import Dict, Tuple, List, Optional
from .base import BaseStrategy
from core.config.trading_config import (
    RSI_PERIOD, RSI_BUY_THRESHOLD, RSI_SELL_THRESHOLD,
    MIN_VOLUME, VOLUME_SURGE_RATIO,
    TRADE_AMOUNT, STOP_LOSS_RATE, TARGET_PROFIT_RATE,
    MA_SHORT,
    MA_MEDIUM
)
from core.api.kis_api import KISAPI

logger = logging.getLogger(__name__)

class MomentumStrategy(BaseStrategy):
    """모멘텀 기반 매매 전략"""
    
    def __init__(self):
        super().__init__("Momentum")
        self.api = KISAPI()
        
    def generate_signals(self, data: pd.DataFrame) -> Tuple[bool, bool]:
        """매수/매도 신호 생성"""
        # RSI 계산
        delta = data['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=RSI_PERIOD).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=RSI_PERIOD).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        # 이동평균 계산
        ma_short = data['Close'].rolling(window=MA_SHORT).mean()
        ma_medium = data['Close'].rolling(window=MA_MEDIUM).mean()
        
        # 매수 신호: RSI 과매도 && 단기 이평선이 중기 이평선을 상향돌파
        buy_signal = (
            rsi.iloc[-1] < RSI_BUY_THRESHOLD and
            ma_short.iloc[-2] < ma_medium.iloc[-2] and
            ma_short.iloc[-1] > ma_medium.iloc[-1]
        )
        
        # 매도 신호: RSI 과매수 || 단기 이평선이 중기 이평선을 하향돌파
        sell_signal = (
            rsi.iloc[-1] > RSI_SELL_THRESHOLD or
            (ma_short.iloc[-2] > ma_medium.iloc[-2] and
             ma_short.iloc[-1] < ma_medium.iloc[-1])
        )
        
        return buy_signal, sell_signal
        
    def should_buy(self, price_data: pd.DataFrame) -> bool:
        """매수 시그널 확인"""
        try:
            # RSI 계산
            rsi = self._calculate_rsi(price_data['Close'], RSI_PERIOD)
            if rsi is None:
                return False
                
            # 거래량 확인
            volume = price_data['Volume'].iloc[-1]
            avg_volume = price_data['Volume'].rolling(window=20).mean().iloc[-1]
            
            # 매수 조건
            return (rsi < RSI_BUY_THRESHOLD and
                   volume > MIN_VOLUME and
                   volume > avg_volume * VOLUME_SURGE_RATIO)
                   
        except Exception as e:
            logger.error(f"매수 시그널 확인 중 오류 발생: {e}")
            return False
            
    def should_sell(self, price_data: pd.DataFrame, position: Dict) -> bool:
        """매도 시그널 확인"""
        try:
            current_price = price_data['Close'].iloc[-1]
            entry_price = position['entry_price']
            
            # 수익률 계산
            profit_rate = (current_price - entry_price) / entry_price
            
            # RSI 계산
            rsi = self._calculate_rsi(price_data['Close'], RSI_PERIOD)
            if rsi is None:
                return False
                
            # 매도 조건
            return (rsi > RSI_SELL_THRESHOLD or  # RSI 과매수
                   profit_rate >= TARGET_PROFIT_RATE or  # 목표 수익률 달성
                   profit_rate <= STOP_LOSS_RATE)  # 손절 라인 도달
                   
        except Exception as e:
            logger.error(f"매도 시그널 확인 중 오류 발생: {e}")
            return False
            
    def calculate_position_size(self, current_price: float, available_cash: float) -> int:
        """매수 수량 계산"""
        if current_price <= 0 or available_cash <= 0:
            return 0
            
        quantity = min(
            int(TRADE_AMOUNT / current_price),  # 기본 매매 금액 기준
            int(available_cash / current_price)  # 사용 가능 현금 기준
        )
        
        return max(quantity, 0)  # 음수 방지
        
    def _calculate_rsi(self, prices: pd.Series, period: int) -> Optional[float]:
        """RSI 계산"""
        try:
            delta = prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            
            return rsi.iloc[-1]
            
        except Exception as e:
            logger.error(f"RSI 계산 중 오류 발생: {e}")
            return None

    def find_candidates(self) -> List[Dict]:
        """모멘텀 전략에 맞는 종목 찾기
        
        Returns:
            List[Dict]: 조건에 맞는 종목 리스트
            [
                {
                    'code': 종목코드,
                    'name': 종목명,
                    'current_price': 현재가,
                    'volume': 거래량,
                    'momentum_score': 모멘텀 점수
                },
                ...
            ]
        """
        try:
            # TODO: 실제 종목 검색 로직 구현
            # 1. KOSPI/KOSDAQ 종목 목록 조회
            # 2. 각 종목의 가격/거래량 데이터 조회
            # 3. 모멘텀 지표 계산 (예: RSI, MACD, 이동평균 등)
            # 4. 조건에 맞는 종목 필터링
            
            # 임시로 테스트 데이터 반환
            candidates = [
                {
                    'code': '005930',
                    'name': '삼성전자',
                    'current_price': 73800,
                    'volume': 12345678,
                    'momentum_score': 85.5
                },
                {
                    'code': '000660',
                    'name': 'SK하이닉스',
                    'current_price': 156000,
                    'volume': 3456789,
                    'momentum_score': 82.3
                }
            ]
            
            logger.info(f"[find_candidates] 종목 검색 완료 - {len(candidates)}개 종목 발견")
            return candidates
            
        except Exception as e:
            logger.error(f"[find_candidates] 종목 검색 중 오류 발생: {str(e)}")
            logger.error(f"[find_candidates] 상세 에러: {e.__class__.__name__}")
            raise
            
    def run(self):
        """전략 실행"""
        try:
            # TODO: 자동 매매 로직 구현
            pass
        except Exception as e:
            logger.error(f"[run] 전략 실행 중 오류 발생: {str(e)}")
            raise 