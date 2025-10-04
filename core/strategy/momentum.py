from typing import List, Dict
import pandas as pd
import numpy as np
from core.api.kis_api import KISAPI
from core.config.trading_config import (
    RSI_PERIOD, RSI_BUY_THRESHOLD, RSI_SELL_THRESHOLD,
    MIN_VOLUME, VOLUME_SURGE_RATIO,
    TRADE_AMOUNT, STOP_LOSS_RATE, TARGET_PROFIT_RATE,
    MA_SHORT, MA_MEDIUM
)
from core.utils.log_utils import get_logger

logger = get_logger(__name__)

class MomentumStrategy:
    def __init__(self, api: KISAPI):
        """모멘텀 전략 클래스 초기화
        
        Args:
            api: KISAPI 인스턴스
        """
        self.api = api
        
    def _calculate_rsi(self, prices: pd.Series) -> float:
        """RSI 계산"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=RSI_PERIOD).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=RSI_PERIOD).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1]
        
    def _calculate_momentum_score(self, stock_data: pd.DataFrame) -> float:
        """모멘텀 점수 계산"""
        try:
            # 이동평균 계산
            ma_short = stock_data['close'].rolling(window=MA_SHORT).mean()
            ma_medium = stock_data['close'].rolling(window=MA_MEDIUM).mean()
            
            # RSI 계산
            rsi = self._calculate_rsi(stock_data['close'])
            
            # 거래량 증가율
            volume_ratio = stock_data['volume'].iloc[-1] / stock_data['volume'].rolling(window=20).mean().iloc[-1]
            
            # 모멘텀 점수 계산 (0-100)
            momentum_score = 0
            
            # 1. 단기 이평선이 중기 이평선을 상향돌파 (30점)
            if ma_short.iloc[-1] > ma_medium.iloc[-1] and ma_short.iloc[-2] <= ma_medium.iloc[-2]:
                momentum_score += 30
                
            # 2. RSI가 과매도 구간에서 반등 (40점)
            if RSI_BUY_THRESHOLD <= rsi <= 50:
                momentum_score += 40
                
            # 3. 거래량 급증 (30점)
            if volume_ratio >= VOLUME_SURGE_RATIO:
                momentum_score += 30
                
            return momentum_score
            
        except Exception as e:
            logger.error(f"모멘텀 점수 계산 중 오류 발생: {str(e)}")
            return 0
        
    def find_candidates(self, min_volume: int = 10000, min_price: int = 5000, max_price: int = 50000) -> List[Dict]:
        """모멘텀 전략에 따른 매수 후보 종목 검색
        
        Args:
            min_volume: 최소 거래량 (기본값: 10,000주)
            min_price: 최소 주가 (기본값: 5,000원)
            max_price: 최대 주가 (기본값: 50,000원)
            
        Returns:
            List[Dict]: 매수 후보 종목 목록
            [
                {
                    'code': 종목코드,
                    'name': 종목명,
                    'market': 시장구분,
                    'price': 현재가,
                    'volume': 거래량,
                    'momentum_score': 모멘텀 점수
                },
                ...
            ]
        """
        try:
            # 1. KOSPI/KOSDAQ 종목 목록 조회
            stock_list = self.api.get_stock_list()
            logger.info(f"[find_candidates] 전체 종목 수: {len(stock_list)}개")
            
            # 2. 조건에 맞는 종목 필터링 및 데이터 조회
            candidates = []
            for stock in stock_list:
                try:
                    # 기본 조건 필터링
                    if not (stock['volume'] >= min_volume and 
                           min_price <= stock['price'] <= max_price):
                        continue
                        
                    # 3. 종목의 가격/거래량 데이터 조회 (최근 20일)
                    stock_data = self.api.get_stock_history(stock['code'], period=20)
                    if stock_data is None or len(stock_data) < 20:
                        continue
                        
                    # 4. 모멘텀 점수 계산
                    momentum_score = self._calculate_momentum_score(stock_data)
                    
                    # 5. 조건에 맞는 종목 선택 (50점 이상)
                    if momentum_score > 50:
                        candidates.append({
                            'code': stock['code'],
                            'name': stock['name'],
                            'market': stock['market'],
                            'price': stock['price'],
                            'volume': stock['volume'],
                            'momentum_score': momentum_score
                        })
                        
                        logger.debug(f"[find_candidates] 후보 종목 추가: {stock['name']} "
                                   f"(코드: {stock['code']}, 점수: {momentum_score:.1f})")
                                   
                except Exception as e:
                    logger.warning(f"[find_candidates] {stock['name']} 분석 중 오류 발생: {str(e)}")
                    continue
            
            # 6. 모멘텀 점수 기준으로 정렬
            candidates.sort(key=lambda x: x['momentum_score'], reverse=True)
            
            logger.info(f"[find_candidates] 후보 종목 수: {len(candidates)}개")
            if candidates:
                logger.info(f"[find_candidates] 최고점수 종목: {candidates[0]['name']} "
                          f"(점수: {candidates[0]['momentum_score']:.1f})")
            
            # 상위 5개 종목만 반환
            return candidates[:5]
            
        except Exception as e:
            logger.error(f"[find_candidates] 후보 종목 검색 중 오류 발생: {str(e)}")
            logger.error(f"[find_candidates] 상세 에러: {e.__class__.__name__}")
            raise 