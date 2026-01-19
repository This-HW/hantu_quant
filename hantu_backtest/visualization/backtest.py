"""
Backtest results visualization module.
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, List
import logging

from .base import BaseVisualizer

logger = logging.getLogger(__name__)

class BacktestVisualizer(BaseVisualizer):
    """백테스트 결과 시각화"""
    
    def plot_equity_curve(self, equity_curve: pd.Series):
        """자본금 곡선 플롯
        
        Args:
            equity_curve: 일별 자본금 시리즈
        """
        try:
            fig, ax = plt.subplots(figsize=(12, 6))
            
            # 자본금 곡선
            equity_curve.plot(ax=ax, label='Portfolio Value')
            
            # Drawdown 표시
            cummax = equity_curve.cummax()
            drawdown = (equity_curve - cummax) / cummax * 100
            
            # 10% 이상 Drawdown 구간 강조
            significant_dd = drawdown <= -10
            if significant_dd.any():
                ax.fill_between(equity_curve.index, equity_curve, cummax,
                              where=significant_dd, color='red', alpha=0.3,
                              label='Drawdown > 10%')
            
            ax.set_title('Portfolio Equity Curve')
            ax.set_xlabel('Date')
            ax.set_ylabel('Portfolio Value')
            ax.grid(True)
            ax.legend()
            
            # 차트 저장
            self.save_figure(fig, 'equity_curve')
            
        except Exception as e:
            logger.error(f"[plot_equity_curve] 차트 생성 중 오류 발생: {str(e)}")
            raise
            
    def plot_returns_distribution(self, returns: pd.Series):
        """수익률 분포 플롯
        
        Args:
            returns: 일별 수익률 시리즈
        """
        try:
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
            
            # 히스토그램
            sns.histplot(returns * 100, bins=50, ax=ax1)
            ax1.set_title('Daily Returns Distribution')
            ax1.set_xlabel('Returns (%)')
            ax1.set_ylabel('Frequency')
            
            # Q-Q 플롯
            from scipy import stats
            stats.probplot(returns, dist="norm", plot=ax2)
            ax2.set_title('Q-Q Plot')
            
            plt.tight_layout()
            self.save_figure(fig, 'returns_distribution')
            
        except Exception as e:
            logger.error(f"[plot_returns_distribution] 차트 생성 중 오류 발생: {str(e)}")
            raise
            
    def plot_drawdown(self, equity_curve: pd.Series):
        """Drawdown 플롯
        
        Args:
            equity_curve: 일별 자본금 시리즈
        """
        try:
            # Drawdown 계산
            cummax = equity_curve.cummax()
            drawdown = (equity_curve - cummax) / cummax * 100
            
            fig, ax = plt.subplots(figsize=(12, 6))
            
            # Drawdown 플롯
            drawdown.plot(ax=ax, color='red', label='Drawdown')
            
            # 구간별 색상 설정
            ax.fill_between(drawdown.index, 0, drawdown, 
                          where=drawdown >= -5, color='green', alpha=0.3)
            ax.fill_between(drawdown.index, 0, drawdown,
                          where=(drawdown < -5) & (drawdown >= -10),
                          color='yellow', alpha=0.3)
            ax.fill_between(drawdown.index, 0, drawdown,
                          where=drawdown < -10, color='red', alpha=0.3)
            
            ax.set_title('Portfolio Drawdown')
            ax.set_xlabel('Date')
            ax.set_ylabel('Drawdown (%)')
            ax.grid(True)
            
            # 수평선 추가
            ax.axhline(y=-5, color='yellow', linestyle='--', alpha=0.5)
            ax.axhline(y=-10, color='red', linestyle='--', alpha=0.5)
            
            self.save_figure(fig, 'drawdown')
            
        except Exception as e:
            logger.error(f"[plot_drawdown] 차트 생성 중 오류 발생: {str(e)}")
            raise
            
    def plot_monthly_returns(self, returns: pd.Series):
        """월별 수익률 히트맵
        
        Args:
            returns: 일별 수익률 시리즈
        """
        try:
            # 월별 수익률 계산
            monthly_returns = returns.groupby([
                returns.index.year,
                returns.index.month
            ]).apply(lambda x: (1 + x).prod() - 1) * 100
            
            # 데이터프레임으로 변환
            monthly_returns = monthly_returns.unstack()
            monthly_returns.columns = [
                'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'
            ]
            
            fig, ax = plt.subplots(figsize=(12, 8))
            
            # 히트맵 생성
            sns.heatmap(monthly_returns, annot=True, fmt='.1f',
                       cmap='RdYlGn', center=0, ax=ax)
            
            ax.set_title('Monthly Returns (%)')
            ax.set_xlabel('Month')
            ax.set_ylabel('Year')
            
            self.save_figure(fig, 'monthly_returns')
            
        except Exception as e:
            logger.error(f"[plot_monthly_returns] 차트 생성 중 오류 발생: {str(e)}")
            raise
            
    def plot_trade_analysis(self, trades: List[Dict]):
        """거래 분석 차트
        
        Args:
            trades: 거래 내역 리스트
        """
        try:
            if not trades:
                logger.warning("[plot_trade_analysis] 거래 내역이 없습니다")
                return
                
            # 거래 데이터프레임 생성
            df = pd.DataFrame(trades)
            df['datetime'] = pd.to_datetime(df['datetime'])
            df['profit'] = df.apply(
                lambda x: x['total'] if x['type'] == 'sell' else -x['total'],
                axis=1
            )
            
            fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 15))
            
            # 1. 거래별 수익/손실
            df['profit'].plot(kind='bar', ax=ax1)
            ax1.set_title('Profit/Loss per Trade')
            ax1.set_xlabel('Trade Number')
            ax1.set_ylabel('Profit/Loss')
            
            # 2. 누적 수익/손실
            df['profit'].cumsum().plot(ax=ax2)
            ax2.set_title('Cumulative Profit/Loss')
            ax2.set_xlabel('Trade Number')
            ax2.set_ylabel('Cumulative Profit/Loss')
            
            # 3. 월별 거래 횟수
            monthly_trades = df.groupby(df['datetime'].dt.to_period('M')).size()
            monthly_trades.plot(kind='bar', ax=ax3)
            ax3.set_title('Monthly Trade Count')
            ax3.set_xlabel('Month')
            ax3.set_ylabel('Number of Trades')
            
            plt.tight_layout()
            self.save_figure(fig, 'trade_analysis')
            
        except Exception as e:
            logger.error(f"[plot_trade_analysis] 차트 생성 중 오류 발생: {str(e)}")
            raise 