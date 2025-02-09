"""
Date utility functions.
"""

from datetime import datetime, timedelta
import pandas as pd
from pandas.tseries.offsets import BDay
from core.config.trading_config import MARKET_START_TIME, MARKET_END_TIME

def get_previous_business_day(date: str = None) -> str:
    """이전 영업일 반환
    
    Args:
        date: 기준일 (YYYY-MM-DD). None인 경우 오늘
        
    Returns:
        str: 이전 영업일 (YYYY-MM-DD)
    """
    if date is None:
        date = datetime.now().strftime('%Y-%m-%d')
        
    return (pd.to_datetime(date) - BDay(1)).strftime('%Y-%m-%d')
    
def get_business_days(start_date: str, end_date: str) -> list:
    """영업일 목록 반환
    
    Args:
        start_date: 시작일 (YYYY-MM-DD)
        end_date: 종료일 (YYYY-MM-DD)
        
    Returns:
        list: 영업일 목록 (YYYY-MM-DD)
    """
    dates = pd.date_range(start=start_date, end=end_date, freq='B')
    return [d.strftime('%Y-%m-%d') for d in dates]

def is_market_closed() -> bool:
    """현재 시장 종료 여부 확인
    
    Returns:
        bool: 시장 종료 여부
    """
    now = datetime.now()
    current_time = now.strftime('%H:%M')
    
    # 주말 체크
    if now.weekday() >= 5:
        return True
        
    # 시간 체크
    if current_time < MARKET_START_TIME or current_time > MARKET_END_TIME:
        return True
        
    return False 