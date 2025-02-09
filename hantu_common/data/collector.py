"""
Stock data collection module.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import logging
from typing import Optional, List, Dict
import time
import json
from pykrx import stock

from core.api.kis_api import KISAPI
from core.config import settings
from core.config.api_config import APIConfig
from core.database import StockRepository
from ..utils.date_utils import get_previous_business_day, is_market_closed
from ..indicators import RSI, MovingAverage, BollingerBands, MACD, Stochastic, ATR

logger = logging.getLogger(__name__)

class StockDataCollector:
    """주식 데이터 수집기"""
    
    AVAILABLE_INDICATORS = {
        'rsi': RSI,
        'ma': MovingAverage,
        'bollinger': BollingerBands,
        'macd': MACD,
        'stochastic': Stochastic,
        'atr': ATR
    }
    
    def __init__(self, api: KISAPI):
        """초기화
        
        Args:
            api: KISAPI 인스턴스
        """
        self.api = api
        self.config = APIConfig()
        self.repository = StockRepository()
        
        # 데이터 저장 경로 설정 (캐시용)
        self.stock_data_dir = settings.STOCK_DATA_DIR
        self.technical_data_dir = settings.TECHNICAL_DATA_DIR
        self.metadata_dir = settings.METADATA_DIR
        
        # 디렉토리 생성
        for data_type in ['daily', 'minute', 'tick']:
            (self.stock_data_dir / data_type).mkdir(parents=True, exist_ok=True)
            (self.technical_data_dir / data_type).mkdir(parents=True, exist_ok=True)
            
    def collect_stock_data(self,
                          stock_codes: List[str],
                          start_date: Optional[str] = None,
                          end_date: Optional[str] = None,
                          data_type: str = 'daily',
                          delay: float = 0.5) -> pd.DataFrame:
        """주식 데이터 수집
        
        Args:
            stock_codes: 종목코드 리스트
            start_date: 시작일 (YYYYMMDD)
            end_date: 종료일 (YYYYMMDD)
            data_type: 데이터 유형 ('daily', 'minute', 'tick')
            delay: API 호출 간격 (초)
            
        Returns:
            pd.DataFrame: 수집된 데이터
        """
        try:
            logger.info(f"[collect_stock_data] 데이터 수집 시작 - {len(stock_codes)}개 종목")
            
            # 날짜 설정
            end_date = end_date or datetime.now().strftime('%Y%m%d')
            if not start_date:
                start_date = (datetime.strptime(end_date, '%Y%m%d') - 
                            timedelta(days=30)).strftime('%Y%m%d')
                
            all_data = []
            
            # 실시간/과거 데이터 구분
            is_realtime = end_date == datetime.now().strftime('%Y%m%d')
            
            for code in stock_codes:
                try:
                    # 종목 정보 저장/조회
                    stock_info = stock.get_market_ticker_name(code)
                    stock_obj = self.repository.save_stock(
                        code=code,
                        name=stock_info,
                        market='KOSPI' if stock.get_market_ticker_section(code) == 'KOSPI' else 'KOSDAQ'
                    )
                    
                    if is_realtime and not is_market_closed():
                        # 실시간 데이터는 한투 API 사용
                        data = self.api.get_stock_history(code, period=data_type)
                    else:
                        # 과거 데이터는 pykrx 사용
                        data = stock.get_market_ohlcv_by_date(
                            fromdate=start_date,
                            todate=end_date,
                            ticker=code
                        )
                        # 컬럼명 통일
                        data.columns = ['open', 'high', 'low', 'close', 'volume', 'amount']
                        
                    if data is not None and not data.empty:
                        # 데이터베이스에 저장
                        prices = []
                        for idx, row in data.iterrows():
                            prices.append({
                                'date': idx,
                                'open': row['open'],
                                'high': row['high'],
                                'low': row['low'],
                                'close': row['close'],
                                'volume': row['volume'],
                                'amount': row.get('amount')
                            })
                        self.repository.save_stock_prices(stock_obj.id, prices)
                        
                        # DataFrame 반환용
                        data['code'] = code
                        all_data.append(data)
                        
                    time.sleep(delay)
                    
                except Exception as e:
                    logger.error(f"[collect_stock_data] {code} 데이터 수집 실패: {str(e)}")
                    continue
                    
            if not all_data:
                logger.warning("[collect_stock_data] 수집된 데이터가 없습니다")
                return pd.DataFrame()
                
            # 데이터 병합
            result = pd.concat(all_data)
            
            # 캐시 파일 저장
            file_path = self._get_data_path(data_type, end_date)
            result.to_parquet(file_path)
            
            logger.info(f"[collect_stock_data] 데이터 수집 완료 - {len(result)}개 레코드")
            return result
            
        except Exception as e:
            logger.error(f"[collect_stock_data] 데이터 수집 중 오류 발생: {str(e)}")
            raise
            
    def process_technical_indicators(self,
                                   data: pd.DataFrame,
                                   indicators: List[Dict[str, any]] = None) -> pd.DataFrame:
        """기술적 지표 계산
        
        Args:
            data: OHLCV 데이터
            indicators: 계산할 지표 목록
                [{'name': 지표명, 'params': 파라미터}]
            
        Returns:
            pd.DataFrame: 지표가 추가된 데이터
        """
        try:
            if indicators is None:
                return data
                
            result = data.copy()
            
            for code in data['code'].unique():
                stock = self.repository.get_stock(code)
                if not stock:
                    continue
                    
                stock_data = data[data['code'] == code]
                
                for indicator in indicators:
                    name = indicator['name']
                    params = indicator.get('params', {})
                    
                    if name in self.AVAILABLE_INDICATORS:
                        indicator_class = self.AVAILABLE_INDICATORS[name]
                        values = indicator_class(stock_data).calculate(**params)
                        
                        if isinstance(values, pd.Series):
                            # 단일 값 지표
                            result.loc[stock_data.index, f'{name}_{params.get("period", "")}'] = values
                            
                            # 데이터베이스 저장
                            for date, value in values.items():
                                self.repository.save_technical_indicator(
                                    stock_id=stock.id,
                                    date=date,
                                    indicator_type=name,
                                    value=value,
                                    params=params
                                )
                        elif isinstance(values, tuple):
                            # 복수 값 지표
                            for i, value in enumerate(values):
                                result.loc[stock_data.index, f'{name}_{i+1}'] = value
                                
                                # 데이터베이스 저장
                                for date, val in value.items():
                                    self.repository.save_technical_indicator(
                                        stock_id=stock.id,
                                        date=date,
                                        indicator_type=f'{name}_{i+1}',
                                        value=val,
                                        params=params
                                    )
                                    
            return result
            
        except Exception as e:
            logger.error(f"[process_technical_indicators] 지표 계산 중 오류 발생: {str(e)}")
            raise
            
    def _get_data_path(self, data_type: str, date: str) -> Path:
        """데이터 파일 경로 반환 (캐시용)"""
        return self.stock_data_dir / data_type / f"stock_data_{date}.parquet" 