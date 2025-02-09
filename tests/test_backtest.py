"""백테스트 시스템 테스트"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from decimal import Decimal

from hantu_backtest.core.backtest import Backtest
from hantu_backtest.strategies.momentum import MomentumStrategy
from core.database.session import DatabaseSession
from core.database.repository import StockRepository

@pytest.fixture
def db_session():
    """데이터베이스 세션 픽스처"""
    session = DatabaseSession()
    yield session.session
    session.close()

@pytest.fixture
def repository(db_session):
    """StockRepository 픽스처"""
    return StockRepository(db_session)

@pytest.fixture
def strategy():
    """MomentumStrategy 픽스처"""
    return MomentumStrategy(
        rsi_period=14,
        rsi_upper=70,
        rsi_lower=30,
        ma_short=5,
        ma_long=20
    )

def test_strategy_initialization(strategy):
    """전략 초기화 테스트"""
    assert strategy.rsi_period == 14
    assert strategy.rsi_upper == 70
    assert strategy.rsi_lower == 30
    assert strategy.ma_short == 5
    assert strategy.ma_long == 20

def test_portfolio_management(strategy):
    """포트폴리오 관리 테스트"""
    # 포트폴리오 초기화
    initial_capital = 100_000_000
    strategy.initialize_portfolio(initial_capital)
    
    assert strategy.portfolio.cash == initial_capital
    assert len(strategy.portfolio.positions) == 0

def test_backtest_execution(strategy, repository):
    """백테스트 실행 테스트"""
    # 테스트 기간 설정
    start_date = datetime.now() - timedelta(days=30)
    end_date = datetime.now()
    
    # 백테스터 초기화
    backtest = Backtest(
        strategy=strategy,
        start_date=start_date.strftime('%Y-%m-%d'),
        end_date=end_date.strftime('%Y-%m-%d'),
        initial_capital=100_000_000
    )
    
    # 백테스트 실행
    results = backtest.run()
    
    assert results is not None
    assert 'returns' in results
    assert 'positions' in results
    assert 'trades' in results

def test_technical_indicators(strategy):
    """기술적 지표 계산 테스트"""
    # 테스트 데이터 생성
    dates = pd.date_range(start='2024-01-01', end='2024-02-01', freq='D')
    data = pd.DataFrame({
        'open': np.random.normal(100, 10, len(dates)),
        'high': np.random.normal(105, 10, len(dates)),
        'low': np.random.normal(95, 10, len(dates)),
        'close': np.random.normal(100, 10, len(dates)),
        'volume': np.random.randint(1000, 10000, len(dates))
    }, index=dates)
    
    # RSI 계산
    rsi = strategy._calculate_rsi(data['close'])
    assert isinstance(rsi, pd.Series)
    assert len(rsi) == len(data)
    assert all((rsi >= 0) & (rsi <= 100))

def test_trade_execution(strategy, repository):
    """거래 실행 테스트"""
    # 포트폴리오 초기화
    initial_capital = 100_000_000
    strategy.initialize_portfolio(initial_capital)
    
    # 테스트 데이터
    stock_code = '005930'  # 삼성전자
    price = Decimal('70000')
    quantity = 100
    
    # 매수 실행
    strategy.execute_trade(
        code=stock_code,
        action='buy',
        price=price,
        quantity=quantity
    )
    
    # 포지션 확인
    assert stock_code in strategy.portfolio.positions
    assert strategy.portfolio.positions[stock_code].quantity == quantity
    assert strategy.portfolio.cash == initial_capital - (price * quantity)

if __name__ == '__main__':
    pytest.main(['-v', __file__]) 