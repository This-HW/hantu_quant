"""
Performance metrics calculation module.
"""

import pandas as pd
import numpy as np
from typing import Dict, List
from scipy import stats

def calculate_metrics(equity_curve: pd.Series,
                     trades: List[Dict],
                     initial_capital: float) -> Dict:
    """백테스트 성과 지표 계산
    
    Args:
        equity_curve: 일별 자본금 곡선
        trades: 거래 내역
        initial_capital: 초기 자본금
        
    Returns:
        Dict: 성과 지표
    """
    metrics = {}
    
    # Decimal을 float로 변환
    equity_curve = equity_curve.astype(float)
    initial_capital = float(initial_capital)
    
    # 1. 수익률 관련 지표
    returns = equity_curve.pct_change().dropna()
    total_return = (equity_curve.iloc[-1] / initial_capital - 1) * 100
    
    metrics['total_return'] = total_return
    metrics['annual_return'] = (
        (1 + total_return/100) ** (252/len(equity_curve)) - 1
    ) * 100
    metrics['daily_returns_mean'] = returns.mean() * 100
    metrics['daily_returns_std'] = returns.std() * 100
    
    # 2. 리스크 관련 지표
    # Drawdown 계산
    cummax = equity_curve.cummax()
    drawdown = (equity_curve - cummax) / cummax * 100
    max_drawdown = drawdown.min()
    
    metrics['max_drawdown'] = max_drawdown
    metrics['volatility'] = returns.std() * np.sqrt(252) * 100
    
    # 3. 위험조정수익률
    risk_free_rate = 0.03  # 3% (연간)
    daily_rf = (1 + risk_free_rate) ** (1/252) - 1
    excess_returns = returns - daily_rf
    
    # Sharpe Ratio
    metrics['sharpe_ratio'] = (
        np.sqrt(252) * excess_returns.mean() / returns.std()
        if returns.std() != 0 else 0
    )
    
    # Sortino Ratio
    downside_returns = returns[returns < 0]
    downside_std = downside_returns.std()
    metrics['sortino_ratio'] = (
        np.sqrt(252) * excess_returns.mean() / downside_std
        if downside_std != 0 else 0
    )
    
    # 4. 거래 관련 지표
    if trades:
        # 수익 거래와 손실 거래 분리
        profit_trades = [t for t in trades if t.get('profit', 0) > 0]
        loss_trades = [t for t in trades if t.get('profit', 0) <= 0]
        
        total_trades = len(trades)
        win_rate = len(profit_trades) / total_trades if total_trades > 0 else 0
        
        # 평균 수익/손실
        avg_profit = np.mean([t['profit'] for t in profit_trades]) if profit_trades else 0
        avg_loss = np.mean([t['profit'] for t in loss_trades]) if loss_trades else 0
        profit_factor = abs(avg_profit / avg_loss) if avg_loss != 0 else 0
        
        metrics.update({
            'total_trades': total_trades,
            'win_rate': win_rate * 100,
            'profit_factor': profit_factor,
            'avg_profit': avg_profit,
            'avg_loss': avg_loss,
            'largest_win': max([t['profit'] for t in profit_trades]) if profit_trades else 0,
            'largest_loss': min([t['profit'] for t in loss_trades]) if loss_trades else 0
        })
    
    # 5. 추가 통계
    # Skewness & Kurtosis
    metrics['returns_skewness'] = stats.skew(returns)
    metrics['returns_kurtosis'] = stats.kurtosis(returns)
    
    # Value at Risk (VaR)
    metrics['var_95'] = np.percentile(returns, 5)
    metrics['var_99'] = np.percentile(returns, 1)
    
    # Conditional VaR (CVaR)
    metrics['cvar_95'] = returns[returns <= metrics['var_95']].mean()
    metrics['cvar_99'] = returns[returns <= metrics['var_99']].mean()
    
    return metrics 